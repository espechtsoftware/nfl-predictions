#!/usr/bin/env python3
"""Pre-lock predicted ownership and the LOW / CHALK player sets for the chalk-core boom sleeve.

External review 2026-09-22 (§2.4, §2.7) and production's response: top Millionaire finishers carry at most
one or two players under 5% ownership and at least one at 20%+, while ~90% of our Week-2 corpus carried 3+
sub-5% players. The laptop's nfl2 sleeve constrains boom solves with the sets written here.

The model is a walk-forward LightGBM on pre-lock inputs only (position, salary, served projection and p90,
value and its within-position ranks, implied team total), trained on the 2022-2025 Sunday Millionaire
ownership. Predictions compress (a 20%+ player is often predicted 12%), so the sets are defined by RANK:
CHALK is the top `round(chalk_share * n)` players by predicted ownership and LOW the bottom
`round(low_share * n_skill)` skill players, where the shares are the historical per-slate fractions of
players at >= 20% and skill players under 5%.

    python scripts/ownership_sets.py validate                      # walk-forward 2023-25 Spearman
    python scripts/ownership_sets.py sets --week 3 --group 153769 --out ~/week3-sunday/ownership_sets.csv
    python scripts/ownership_sets.py replay-sets --seasons 2023,2024 --out DIR   # walk-forward, one file per slate

Reads BigQuery; the output holds no DraftKings standings and may live on the build host.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PANEL = "20260811-pitclean-e80-k1-a12ab31"      # point-in-time replay projections, 2019/2021-2025
FEATURES = ["pos_c", "salary", "proj", "proj_p90", "value", "proj_rank", "value_rank", "sal_rank",
            "value_z", "implied_team_total"]
SKILL = ("QB", "RB", "WR", "TE")
LOW_PCT, CHALK_PCT = 5.0, 20.0


def norm(s: object) -> str:
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower())
    return re.sub(r"[^a-z]", "", s)


def add_features(x: pd.DataFrame, slate_cols: list[str]) -> pd.DataFrame:
    """Within-slate, within-position ranks and value; `x` needs pos, salary, proj, proj_p90,
    implied_team_total."""
    x = x.copy()
    x["value"] = x.proj / (x.salary / 1000.0)
    g = x.groupby(slate_cols + ["pos"])
    x["proj_rank"] = g.proj.rank(ascending=False)
    x["value_rank"] = g.value.rank(ascending=False)
    x["sal_rank"] = g.salary.rank(ascending=False)
    x["value_z"] = (x.value - g.value.transform("mean")) / g.value.transform("std")
    x["pos_c"] = x.pos.map({"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}).astype(float)
    return x


def set_shares(hist: pd.DataFrame) -> tuple[float, float]:
    """Mean per-slate fraction of all players at >= CHALK_PCT, and of skill players under LOW_PCT."""
    rows = []
    for _, s in hist.groupby(["season", "week"]):
        sk = s[s.pos.isin(SKILL)]
        rows.append(((s.own >= CHALK_PCT).mean(), (sk.own < LOW_PCT).mean()))
    a = np.array(rows)
    return float(a[:, 0].mean()), float(a[:, 1].mean())


def assign_sets(pred: pd.DataFrame, chalk_share: float, low_share: float) -> pd.DataFrame:
    """Rank-defined sets. `pred` needs pos and pred_own. CHALK: top round(chalk_share*n) of all players;
    LOW: bottom round(low_share*n_skill) of skill players; the rest MID. Ties break by input order."""
    out = pred.copy()
    out["pred_rank"] = out.pred_own.rank(ascending=False, method="first").astype(int)
    n_chalk = max(1, int(round(chalk_share * len(out))))
    skill = out.pos.isin(SKILL)
    n_low = int(round(low_share * int(skill.sum())))
    out["set"] = "MID"
    out.loc[out.pred_rank <= n_chalk, "set"] = "CHALK"
    low_idx = out[skill].sort_values("pred_own", kind="stable").index[:n_low]
    out.loc[low_idx, "set"] = "LOW"
    return out


def training_frame(query_df, project: str) -> pd.DataFrame:
    own = query_df(f"""
        WITH c AS (
          SELECT season, week, contest_id, ANY_VALUE(contest_name) nm,
                 SAFE_CAST(REGEXP_EXTRACT(ANY_VALUE(contest_name), r"\\[(\\d+) entries") AS INT64) ent
          FROM `{project}.nfl_raw.contest_ownership` WHERE season BETWEEN 2022 AND 2025 GROUP BY 1,2,3),
        pick AS (
          SELECT season, week, ARRAY_AGG(STRUCT(contest_id, ent) ORDER BY ent DESC LIMIT 1)[OFFSET(0)] AS p
          FROM c WHERE REGEXP_CONTAINS(nm, r"Fantasy Football Millionaire")
            AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555") GROUP BY 1,2)
        SELECT o.season, o.week, o.display_name, MAX(o.pct_drafted) pct
        FROM `{project}.nfl_raw.contest_ownership` o
        JOIN pick ON o.season = pick.season AND o.week = pick.week AND o.contest_id = pick.p.contest_id
        GROUP BY 1,2,3""")
    own["key"] = own.display_name.map(norm)
    own = own.groupby(["season", "week", "key"], as_index=False).pct.max()
    spf = query_df(f"""
        SELECT season, week, id, gsis_id, name, team, pos, salary, mean_projection AS proj, proj_p90, implied_team_total
        FROM `{project}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = "{PANEL}" AND season BETWEEN 2022 AND 2025""")
    spf["key"] = spf.name.map(norm)
    d = spf[spf.salary.notna() & spf.proj.notna()].drop_duplicates(["season", "week", "key"])
    have = set(map(tuple, own[["season", "week"]].drop_duplicates().to_numpy()))
    d = d[[(s, w) in have for s, w in zip(d.season, d.week)]]
    d = d.merge(own, on=["season", "week", "key"], how="left")
    d["own"] = d.pct.fillna(0.0)
    return add_features(d, ["season", "week"])


def fit(train: pd.DataFrame):
    import lightgbm as lgb
    return lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=40,
                             verbose=-1, random_state=20260922).fit(train[FEATURES], np.log(train.own + 0.1))


def predict(model, x: pd.DataFrame) -> np.ndarray:
    return np.exp(model.predict(x[FEATURES])) - 0.1


def validate(d: pd.DataFrame) -> dict[int, float]:
    from scipy.stats import spearmanr
    out = {}
    for y in (2023, 2024, 2025):
        m = fit(d[d.season < y])
        te = d[d.season == y].copy()
        te["pred"] = predict(m, te)
        r = [spearmanr(g.pred, g.own).statistic for _, g in te[te.proj >= 3].groupby("week")]
        out[y] = float(np.mean(r))
    return out


def slate_frame(query_df, settings, week: int, group: int) -> pd.DataFrame:
    """The Sunday-main slate's served projections (latest generation) with the implied team total."""
    x = query_df(f"""
        WITH latest AS (SELECT MAX(pulled_at) ts FROM `{settings.raw}.dk_salaries`
                        WHERE draft_group_id = {int(group)}),
        slate AS (SELECT DISTINCT dk_player_id FROM `{settings.raw}.dk_salaries`, latest
                  WHERE draft_group_id = {int(group)} AND pulled_at = latest.ts),
        proj AS (SELECT * FROM `{settings.predictions}.player_projections_current` WHERE week = {int(week)})
        SELECT p.gsis_id, p.dk_player_id, p.display_name, p.position AS pos, p.team, p.salary,
               p.proj_points AS proj, p.proj_p90, f.implied_team_total
        FROM proj p JOIN slate s ON CAST(p.dk_player_id AS STRING) = CAST(s.dk_player_id AS STRING)
        LEFT JOIN `{settings.features}.player_week_inference` f
          ON f.gsis_id = p.gsis_id AND f.week = {int(week)}""")
    if x.empty:
        raise SystemExit(f"no served projections for week {week} on draft group {group}; "
                         "run the projection refresh first")
    x["slate"] = int(group)
    return add_features(x, ["slate"])


def replay_frame(query_df, project: str, seasons: list[int]) -> pd.DataFrame:
    """Every player of each replay slate, deduplicated on gsis_id -- NOT the name key training uses: the panel table
    has players with no name (minimum-salary fringe rows), and a name-key dedup collapses all of them into one row,
    which would leave the sets file unable to cover the slate (the sleeve's loader fails closed on that)."""
    spf = query_df(f"""
        SELECT season, week, id, gsis_id, name, team, pos, salary, mean_projection AS proj, proj_p90, implied_team_total
        FROM `{project}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = "{PANEL}" AND season IN ({", ".join(str(int(v)) for v in seasons)})""")
    x = spf[spf.salary.notna() & spf.proj.notna() & spf.gsis_id.notna()].drop_duplicates(["season", "week", "gsis_id"])
    return add_features(x, ["season", "week"])


def replay_sets(d: pd.DataFrame, seasons: list[int], out_dir: Path, pred_frame: pd.DataFrame | None = None) -> list[dict]:
    """Walk-forward historical sets for the replay panel (laptop, 2026-09-22): for season S the model AND the rank-rule
    shares are fit on seasons < S only (training frame `d`, unchanged), then every S slate that has Millionaire
    ownership in `d` is predicted from its pre-lock inputs in `pred_frame` (all players; see replay_frame).
    One file per slate, the live schema plus the lab's frame `id`, keyed by gsis_id so nfl2 frames join."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_frame = d if pred_frame is None else pred_frame
    receipts = []
    for season in seasons:
        train = d[d.season < season]
        if train.empty:
            raise SystemExit(f"no seasons before {season} to fit on; walk-forward sets need a prior fold")
        chalk_share, low_share = set_shares(train)
        model = fit(train)
        matched = set(d[d.season == season].week.unique())
        for week, x in pred_frame[(pred_frame.season == season) & pred_frame.week.isin(matched)].groupby("week"):
            x = x.copy(); x["pred_own"] = predict(model, x)
            sets = assign_sets(x, chalk_share, low_share)
            f = out_dir / f"{season}-w{int(week):02d}.csv"
            cols = ["gsis_id", "id", "name", "pos", "team", "salary", "proj", "pred_own", "pred_rank", "set"]
            sets[cols].sort_values("pred_rank").rename(columns={"name": "display_name"}).to_csv(f, index=False)
            receipts.append({"season": season, "week": int(week), "file": str(f), "players": len(sets),
                             "chalk": int((sets.set == "CHALK").sum()), "low": int((sets.set == "LOW").sum()),
                             "fit_seasons": sorted(int(v) for v in train.season.unique())})
    return receipts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["validate", "sets", "replay-sets"])
    ap.add_argument("--seasons", default="2023,2024")
    ap.add_argument("--week", type=int)
    ap.add_argument("--group", type=int)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--min-spearman", type=float, default=0.70)
    a = ap.parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    d = training_frame(query_df, settings.project)
    val = validate(d)
    print("walk-forward within-slate Spearman:", {k: round(v, 3) for k, v in val.items()})
    if min(val.values()) < a.min_spearman:
        raise SystemExit(f"ownership model below the {a.min_spearman} gate on history; refusing to write sets")
    if a.mode == "validate":
        return
    if a.mode == "replay-sets":
        if not a.out:
            raise SystemExit("replay-sets needs --out DIR")
        seasons = [int(v) for v in a.seasons.split(",")]
        recs = replay_sets(d, seasons, a.out, pred_frame=replay_frame(query_df, settings.project, seasons))
        import json
        (a.out / "receipt.json").write_text(json.dumps({"panel": PANEL, "validation": val, "slates": recs}, indent=1))
        print(f"wrote {len(recs)} slate files to {a.out}")
        return
    if not (a.week and a.group and a.out):
        raise SystemExit("sets needs --week, --group and --out")
    chalk_share, low_share = set_shares(d)
    x = slate_frame(query_df, settings, a.week, a.group)
    x["pred_own"] = predict(fit(d), x)
    s = assign_sets(x, chalk_share, low_share)
    cols = ["gsis_id", "dk_player_id", "display_name", "pos", "team", "salary", "proj", "pred_own",
            "pred_rank", "set"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    s[cols].sort_values("pred_rank").to_csv(a.out, index=False)
    print(f"wrote {a.out}: {len(s)} players; CHALK {int((s.set == 'CHALK').sum())} "
          f"(share {chalk_share:.3f}), LOW {int((s.set == 'LOW').sum())} skill (share {low_share:.3f})")


if __name__ == "__main__":
    sys.exit(main())
