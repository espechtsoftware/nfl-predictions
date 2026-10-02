"""PREREG-B2 reader: Fantasy Points in the projection blend (frozen spec: reports/2026-10-02-PREREG-A3-B2-escalated.md).

Per week, from captures made BEFORE the lock only:
  OURS    nfl_predictions.market_source_log, the newest batch generated before the lock: proj_points (the served
          0.45 model / 0.55 market), model_points_pre (model), market_points (market; NULL where no market)
  FP      nfl_raw.fantasy_points_dfs_projections, the week's main DraftKings slate (--slate), the newest capture before the
          lock: fantasy_points
GATE (amendment, 10-02 before the lock): market_source_log's components are logged BEFORE the availability/backup-QB
gates (Week 4: Caleb Williams 18.2, out; backups 9-14), so OURS = the SERVED proj_points (player_projections, the newest
pre-lock batch) and the model and market components are scaled by r = served / logged proj_points (0 when the served
projection is 0), carrying our own gates into our components; FP is FP's own.
Arms (FIXED weights): OURS; B2_EQ = 1/3 model, 1/3 market, 1/3 FP; B2_45 = 0.45 model, 0.275 market, 0.275 FP. Where FP
or the market is missing for a player the weights renormalise over the sources present (coverage reported by position).
Population: players OURS projects >= 3 who have an actual DK score (the Millionaire's fpts per player).
Metric: MAE against actual DK points, overall and by position; also the bias. Decides nothing by itself.

Usage: score_projection_blend.py --season 2026 --week 4 --slate 154078 --contest <Millionaire id> --lock-utc 2026-10-04T17:00:00Z
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ownership_blend import norm  # noqa: E402

PROJECT = "nfl-predictions-503414"
WEIGHTS = {"B2_EQ": (1 / 3, 1 / 3, 1 / 3), "B2_45": (0.45, 0.275, 0.275)}
MIN_PROJ = 3.0
SAME_RUN_SECONDS = 300          # the log and the projections of one project-slate run, stamped separately


def blend(model: pd.Series, market: pd.Series, fp: pd.Series, w: tuple[float, float, float]) -> pd.Series:
    """The weighted mean over the sources present for each player (weights renormalised)."""
    parts = pd.concat([model, market, fp], axis=1); wts = np.array(w, float)
    have = parts.notna().to_numpy()
    num = np.nansum(parts.to_numpy(float) * wts, axis=1); den = (have * wts).sum(axis=1)
    return pd.Series(np.where(den > 0, num / np.where(den > 0, den, 1), np.nan), index=parts.index)


def gate(ours: pd.DataFrame, served: pd.Series) -> pd.DataFrame:
    """OURS := the served projection; model and market scaled by served / logged (our gates carried into our components;
    a served 0 zeroes both). Players without a served projection are dropped (not part of our week)."""
    o = ours[ours.index.isin(served.index)].copy()
    sv = served.reindex(o.index).astype(float); logged = o.proj_points.astype(float)
    r = np.where(logged > 0, sv / logged.where(logged > 0, 1.0), np.where(sv > 0, 1.0, 0.0))
    o["model_points_pre"] = o.model_points_pre.astype(float) * r
    o["market_points"] = o.market_points.astype(float) * r
    o["proj_points"] = sv
    return o


def score(pred: pd.Series, actual: pd.Series, pos: pd.Series) -> dict:
    ok = pred.notna() & actual.notna(); e = (pred - actual)[ok]
    out = {"n": int(ok.sum()), "MAE": round(float(e.abs().mean()), 3), "bias": round(float(e.mean()), 3)}
    for p in ("QB", "RB", "WR", "TE", "DST"):
        m = ok & (pos == p)
        if m.any():
            out[f"MAE_{p}"] = round(float((pred - actual)[m].abs().mean()), 3)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--slate", required=True); ap.add_argument("--contest", required=True); ap.add_argument("--lock-utc", required=True)
    a = ap.parse_args(argv)
    from google.cloud import bigquery
    c = bigquery.Client(project=PROJECT); P = PROJECT
    # ONE batch (reviewer 10-02): the served batch's generated_at, and market_source_log AT that generated_at -- otherwise
    # r would carry projection UPDATES between two runs, not our gates
    g = c.query(f"""SELECT MAX(generated_at) g FROM `{P}.nfl_predictions.player_projections`
        WHERE season={a.season} AND week={a.week} AND generated_at < TIMESTAMP('{a.lock_utc}')""").to_dataframe().g.iloc[0]
    if pd.isna(g):
        raise SystemExit("no pre-lock projection batch")
    # the same run stamps market_source_log a few seconds BEFORE player_projections (10-02: 09:24:33 vs 09:24:47), so the
    # pair is the newest log batch at or before g and within SAME_RUN_SECONDS of it; anything else is refused
    gl = c.query(f"""SELECT MAX(generated_at) g FROM `{P}.nfl_predictions.market_source_log`
        WHERE season={a.season} AND week={a.week} AND generated_at <= TIMESTAMP('{g}')""").to_dataframe().g.iloc[0]
    if pd.isna(gl) or (pd.Timestamp(g) - pd.Timestamp(gl)).total_seconds() > SAME_RUN_SECONDS:
        raise SystemExit(f"no market_source_log batch within {SAME_RUN_SECONDS}s before the served batch {g} (newest {gl}): "
                         "not one run; refused")
    ours = c.query(f"""SELECT display_name, position, proj_points, model_points_pre, market_points FROM `{P}.nfl_predictions.market_source_log`
        WHERE season={a.season} AND week={a.week} AND generated_at = TIMESTAMP('{gl}')""").to_dataframe()
    print(f"batch: player_projections {g} / market_source_log {gl} ({(pd.Timestamp(g) - pd.Timestamp(gl)).total_seconds():.0f}s apart: one run)")
    fp = c.query(f"""SELECT name, fantasy_points FROM `{P}.nfl_raw.fantasy_points_dfs_projections`
        WHERE season={a.season} AND week={a.week} AND slate_id='{a.slate}' AND operator='DraftKings'
          AND retrieved_at < TIMESTAMP('{a.lock_utc}')
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""").to_dataframe()
    # the main slate's own player list (DraftKings, newest pull before the lock): independent of FP, so the population is
    # "main-slate players", not "players FP covers" (dry run 10-02: the projection log spans every game of the week)
    slate = c.query(f"""SELECT display_name, position FROM `{P}.nfl_raw.dk_salaries` WHERE draft_group_id={int(a.slate)}
        AND pulled_at < TIMESTAMP('{a.lock_utc}') QUALIFY pulled_at = MAX(pulled_at) OVER ()""").to_dataframe()
    # DSTs are not in market_source_log: OURS from the projection batch, model = OURS, no market (renormalised)
    dst = c.query(f"""SELECT display_name, 'DST' AS position, proj_points, proj_points AS model_points_pre, CAST(NULL AS FLOAT64) market_points
        FROM `{P}.nfl_predictions.player_projections` WHERE season={a.season} AND week={a.week} AND position='DST'
          AND generated_at = TIMESTAMP('{g}')""").to_dataframe()
    act = c.query(f"""SELECT display_name, MAX(fpts) fpts FROM `{P}.nfl_raw.contest_ownership`
        WHERE season={a.season} AND week={a.week} AND contest_id='{a.contest}' GROUP BY 1""").to_dataframe()
    served = c.query(f"""SELECT display_name, proj_points AS served FROM `{P}.nfl_predictions.player_projections`
        WHERE season={a.season} AND week={a.week} AND generated_at = TIMESTAMP('{g}')""").to_dataframe()
    ours = pd.concat([ours, dst], ignore_index=True)
    ours["key"] = ours.display_name.map(norm)
    # a key whose rows differ in position is two players (e.g. two "Mike Williams"); an exact repeat of one player collapses
    multi = ours.groupby("key").position.nunique()
    coll = ours[ours.key.isin(set(multi[multi > 1].index))]
    if len(coll):
        print(f"name collisions (dropped from the population): {sorted(set(coll.display_name))}")
    ours = ours[~ours.key.isin(set(coll.key))].drop_duplicates("key").set_index("key")
    sv = pd.Series(served.served.to_numpy(float), index=served.display_name.map(norm)).groupby(level=0).max()
    ours = gate(ours, sv)
    on_slate = set(slate.display_name.map(norm))
    print(f"main slate {a.slate}: {len(on_slate)} DK players; projected players on it {int(ours.index.isin(on_slate).sum())}")
    ours = ours[ours.index.isin(on_slate)]
    fps = pd.Series(fp.fantasy_points.to_numpy(float), index=fp.name.map(norm)).groupby(level=0).max()
    actual = pd.Series(act.fpts.to_numpy(float), index=act.display_name.map(norm)).groupby(level=0).max()
    pop = ours[ours.proj_points >= MIN_PROJ]
    pos = pop.position.astype(str); actual = actual.reindex(pop.index)
    model, market, fpp = pop.model_points_pre.astype(float), pop.market_points.astype(float), fps.reindex(pop.index)
    print(f"population: {len(pop)} projected >= {MIN_PROJ}; with an actual DK score {int(actual.notna().sum())}; "
          f"without one (nobody drafted them) {int(actual.isna().sum())}")
    print("coverage by position (market / FP):",
          {p: (round(float(market[pos == p].notna().mean()), 2), round(float(fpp[pos == p].notna().mean()), 2)) for p in sorted(set(pos))})
    rows = [{"arm": "OURS", **score(pop.proj_points.astype(float), actual, pos)}]
    for name, w in WEIGHTS.items():
        rows.append({"arm": name, **score(blend(model, market, fpp, w), actual, pos)})
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
