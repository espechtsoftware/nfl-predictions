#!/usr/bin/env python3
"""The weekly ours / Fantasy Points / blend accuracy row: the operator's revisit condition for FP projections (10-05,
verbatim: "we should just use fantasy points unless we've seen that our projections or the blend have beat them").
FROZEN 2026-10-06, before any Week-5 outcome, at the reviewer's request (10-05: "use the same 12-game cluster bootstrap
and the >= 3 eligibility every week, frozen now, so the comparison can't drift"). Week 4 is the first row.

    # one week: writes the player rows (PRIVATE: FP's numbers are licensed) and prints the week's row
    python scripts/weekly_projection_accuracy.py week --season 2026 --week 5 --frame <T-70 run>/frame.parquet \\
        --lock-utc 2026-10-11T17:00:00Z --contest <the week's Millionaire id> --out-dir ~/private/projection-accuracy
    # every week so far, pooled: the revisit check
    python scripts/weekly_projection_accuracy.py pool --out-dir ~/private/projection-accuracy

Sources, per week (all captured BEFORE the lock):
  OURS   the T-70 build's frame.parquet `mean_projection` (the frame on disk is always ours: --proj-source replaces it
         only inside the union step);
  FP     nfl_raw.fantasy_points_dfs_projections, DraftKings, the Main slate, the newest capture before --lock-utc
         (the same selection the build's FP override makes), joined EXACTLY on the DraftKings draftable id;
  BLEND  0.5 OURS + 0.5 FP (fixed);
  ACTUAL the week's Millionaire `fpts` per player (nfl_raw.contest_ownership; DraftKings' own scoring), by normalised
         display name; a name two slate players share is dropped (counted).
Population (fixed): QB / RB / WR / TE with OURS >= 3 or FP >= 3, an FP projection and an actual, and game-day
rosters_weekly status ACT (the O-32 rule, `nfl_dfs.analysis.game_day_active`: a player who did not play is a miss no
projection can explain, and the build removes him anyway). Drops are counted and printed.
Zero points: an ACT player who scores 0 STAYS IN (a real miss). A player not ACT on game day is OUT. An ACT player missing
from the Millionaire's player list (nobody drafted him, so DraftKings lists no score) has no actual and is OUT (counted
as dropped_no_actual). Rows are sorted by player id, so the written player list (and its sha256) is reproducible.
Metrics: MAE and bias against the actual, Spearman rank correlation, MAE by position.
Uncertainty: a game-cluster bootstrap (resample the week's games with replacement; pooled: games resampled WITHIN each
week), B 2000, seed 1. For each pair: the mean MAE improvement, its 5-95% range, and the share of resamples better.
THE REVISIT CHECK (pooled weeks only; single weeks are descriptive): "ours (or the blend) beats FP" is printed when its
pooled MAE is lower than FP's AND at least 95% of the pooled resamples are better (B 2000, seed 1). The operator
decides; this decides nothing by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ownership_blend import norm  # noqa: E402

SKILL = ("QB", "RB", "WR", "TE")
MIN_PROJ = 3.0
B, SEED = 2000, 1
REVISIT_SHARE = 0.95
RULE = (f"REVISIT RULE: a source beats FP when its pooled MAE is lower than FP's AND at least {REVISIT_SHARE:.0%} of "
        f"B {B} game-cluster resamples (seed {SEED}, games resampled within week) are better")
SOURCES = ("ours", "fp", "blend")
PAIRS = (("ours", "fp"), ("blend", "fp"), ("blend", "ours"))   # (challenger, incumbent): improvement = MAE(inc) - MAE(chal)


def _key(v) -> str:
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def population(fr: pd.DataFrame, fp: pd.DataFrame, actual: pd.Series, active: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    """Pure: the week's player rows (id, name, pos, game, gsis_id, ours, fp, blend, actual) and the drop counts.
    `actual` is indexed by normalised display name; `active` is rosters_weekly's (season, week, gsis_id, act) or None."""
    fr = fr.drop_duplicates("id").copy()
    names = fr["display_name"].astype(str).map(norm)
    dup = set(names[names.duplicated(keep=False)])                 # over the WHOLE slate (any position): actuals are by name
    actual = actual[~actual.index.duplicated(keep=False)]
    fr = fr[fr.pos.astype(str).isin(SKILL)]
    fr["dk"] = fr["dk_draftable_id"].map(_key)
    fp = fp.assign(dk=fp["slate_player_id"].map(_key)).drop_duplicates("dk")
    d = pd.DataFrame({"id": fr["id"].astype(str), "name": fr["display_name"].astype(str), "pos": fr["pos"].astype(str),
                      "game": fr["game_id"].astype(str), "gsis_id": fr["gsis_id"].astype(str),
                      "season": fr["season"].astype(int), "week": fr["week"].astype(int),
                      "ours": pd.to_numeric(fr["mean_projection"], errors="coerce"), "dk": fr["dk"]})
    d["fp"] = d.dk.map(fp.set_index("dk")["fantasy_points"].astype(float))
    audit = {"skill_rows": int(len(d))}
    d = d[(d.ours >= MIN_PROJ) | (d.fp >= MIN_PROJ)]
    audit["eligible_ge3"] = int(len(d))
    audit["dropped_no_fp"] = int(d.fp.isna().sum()); d = d[d.fp.notna()]
    audit["dropped_no_ours"] = int(d.ours.isna().sum()); d = d[d.ours.notna()]
    nk = d.name.map(norm)
    audit["dropped_name_collision"] = int(nk.isin(dup).sum()); d = d[~nk.isin(dup)]
    d["actual"] = d.name.map(norm).map(actual)
    audit["dropped_no_actual"] = int(d.actual.isna().sum()); d = d[d.actual.notna()]
    if active is not None:
        from nfl_dfs.analysis.game_day_active import filter_game_day_active
        d, a = filter_game_day_active(d, active)
        audit["dropped_not_act"] = a["dropped_not_act"]; audit["dropped_no_roster_row"] = a["dropped_no_roster_row"]
    d["blend"] = 0.5 * d.ours + 0.5 * d.fp
    audit["population"] = int(len(d)); audit["games"] = int(d.game.nunique())
    return d.drop(columns=["dk"]).sort_values("id").reset_index(drop=True), audit


def metrics(d: pd.DataFrame) -> dict:
    out = {}
    for s in SOURCES:
        e = d[s] - d.actual
        out[s] = {"MAE": float(e.abs().mean()), "bias": float(e.mean()), "spearman": float(d[s].corr(d.actual, method="spearman")),
                  **{f"MAE_{p}": float(e[d.pos == p].abs().mean()) for p in SKILL if (d.pos == p).any()}}
    return out


def bootstrap(d: pd.DataFrame, b: int = B, seed: int = SEED) -> dict:
    """Game-cluster bootstrap; games resampled within each week. Improvement of challenger over incumbent = MAE(inc) -
    MAE(chal) (> 0: the challenger is more accurate)."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in d.groupby(["season", "week", "game"], sort=True)}
    by_week: dict[tuple, list] = {}
    for key in groups:
        by_week.setdefault((int(key[0]), int(key[1])), []).append(key)
    # absolute errors per cluster, summed: the resample's MAE is sum / count
    err = {k: np.array([(g[s] - g.actual).abs().sum() for s in SOURCES]) for k, g in groups.items()}
    cnt = {k: len(g) for k, g in groups.items()}
    idx = {s: i for i, s in enumerate(SOURCES)}
    imp = {f"{c}_vs_{i}": [] for c, i in PAIRS}
    for _ in range(b):
        tot, n = np.zeros(len(SOURCES)), 0
        for w in sorted(by_week):
            keys = by_week[w]
            for j in rng.integers(0, len(keys), len(keys)):
                tot += err[keys[j]]; n += cnt[keys[j]]
        mae = tot / n
        for c, i in PAIRS:
            imp[f"{c}_vs_{i}"].append(mae[idx[i]] - mae[idx[c]])
    out = {}
    for k, v in imp.items():
        v = np.asarray(v)
        lo, hi = np.percentile(v, [5, 95])
        out[k] = {"mean": float(v.mean()), "p05": float(lo), "p95": float(hi), "share_better": float((v > 0).mean())}
    return out


def revisit(pooled: pd.DataFrame, boot: dict) -> list[str]:
    m = metrics(pooled)
    msgs = []
    for c in ("ours", "blend"):
        k = f"{c}_vs_fp"
        if m[c]["MAE"] < m["fp"]["MAE"] and boot[k]["share_better"] >= REVISIT_SHARE:
            msgs.append(f"{c.upper()} BEATS FP on the pooled weeks (MAE {m[c]['MAE']:.3f} vs {m['fp']['MAE']:.3f}; "
                        f"{boot[k]['share_better']:.3f} of resamples better >= {REVISIT_SHARE}): bring to the operator")
    return msgs or [f"no source beats FP at the frozen check (MAE lower AND >= {REVISIT_SHARE} of pooled resamples better)"]


def report(d: pd.DataFrame, title: str) -> None:
    m, bs = metrics(d), bootstrap(d)
    weeks = sorted({f"{int(s)} W{int(w)}" for s, w in zip(d.season, d.week)})
    print(f"{title}: players {len(d)}, games {d.groupby(['season', 'week', 'game']).ngroups}, weeks {weeks}")
    for s in SOURCES:
        x = m[s]
        print(f"  {s:6s} MAE {x['MAE']:.3f}  bias {x['bias']:+.3f}  rank corr {x['spearman']:.3f}  "
              + "  ".join(f"{p} {x[f'MAE_{p}']:.2f}" for p in SKILL if f"MAE_{p}" in x))
    for k, v in bs.items():
        print(f"  {k:14s} MAE improvement {v['mean']:+.3f} (5-95% {v['p05']:+.3f} to {v['p95']:+.3f}); "
              f"share of resamples better {v['share_better']:.3f}")


def load_fp(season: int, week: int, lock_utc: str) -> tuple[pd.DataFrame, dict]:
    """FP's DraftKings Main-slate projections, the newest capture retrieved before the lock (one capture, one slate)."""
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    fp = query_df(f"""SELECT slate_id, slate_player_id, fantasy_points, retrieved_at, source_sha256
        FROM `{settings.raw}.fantasy_points_dfs_projections`
        WHERE season = @s AND week = @w AND operator = 'DraftKings' AND slate_name = 'Main' AND retrieved_at < TIMESTAMP(@b)
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""", params={"s": season, "w": week, "b": str(lock_utc)})
    if fp.empty:
        raise SystemExit(f"no FP DraftKings Main-slate capture for {season} W{week} before {lock_utc}")
    if fp.slate_id.nunique() != 1:
        raise SystemExit(f"the newest capture holds {fp.slate_id.nunique()} Main slates")
    return fp, {"retrieved_at": pd.Timestamp(fp.retrieved_at.iloc[0]).isoformat(), "slate_id": str(fp.slate_id.iloc[0]),
                "source_sha256": str(fp.source_sha256.iloc[0]), "rows": int(len(fp))}


def load_week(a) -> tuple[pd.DataFrame, dict]:
    from nfl_dfs.analysis.game_day_active import load_active
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    if settings.project == "nfl-dfs-prod":
        raise SystemExit("GCP_PROJECT is not set (O-31)")
    fr = pd.read_parquet(a.frame)
    if not ((fr.season.astype(int) == a.season) & (fr.week.astype(int) == a.week)).all():
        raise SystemExit(f"the frame is not {a.season} W{a.week}")
    fp, cap = load_fp(a.season, a.week, a.lock_utc)
    act = query_df(f"""SELECT display_name, MAX(CAST(fpts AS FLOAT64)) fpts FROM `{settings.raw}.contest_ownership`
        WHERE season = @s AND week = @w AND contest_id = @c GROUP BY 1""", params={"s": a.season, "w": a.week, "c": str(a.contest)})
    if act.empty:
        raise SystemExit(f"no contest_ownership rows for contest {a.contest}")
    actual = pd.Series(act.fpts.to_numpy(float), index=act.display_name.map(norm))
    d, audit = population(fr, fp, actual, load_active([a.season]))
    audit.update({"capture": cap, "frame": str(a.frame), "lock_utc": a.lock_utc, "contest": str(a.contest),
                  "written_utc": datetime.now(timezone.utc).isoformat()})
    return d, audit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week"); w.add_argument("--season", type=int, required=True); w.add_argument("--week", type=int, required=True)
    w.add_argument("--frame", type=Path, required=True); w.add_argument("--lock-utc", required=True)
    w.add_argument("--contest", required=True); w.add_argument("--out-dir", type=Path, required=True)
    p = sub.add_parser("pool"); p.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "week":
        d, audit = load_week(a)
        a.out_dir.mkdir(parents=True, exist_ok=True)
        stem = a.out_dir / f"accuracy-{a.season}-w{a.week:02d}"
        d.to_csv(f"{stem}.csv", index=False)
        audit["rows_sha256"] = hashlib.sha256(Path(f"{stem}.csv").read_bytes()).hexdigest()
        Path(f"{stem}.json").write_text(json.dumps(audit, indent=1) + "\n")
        print("population:", {k: v for k, v in audit.items() if isinstance(v, int)})
        print(f"player rows: {stem}.csv  n {len(d)}  sha256 {audit['rows_sha256']}")
        print(f"FP capture {audit['capture']['retrieved_at']} (slate {audit['capture']['slate_id']})")
        report(d, f"{a.season} W{a.week}")
        return 0
    files = sorted(a.out_dir.glob("accuracy-*-w*.csv"))
    if not files:
        raise SystemExit(f"no weekly rows in {a.out_dir}")
    pooled = pd.concat([pd.read_csv(f, dtype={"game": str, "gsis_id": str, "id": str}) for f in files], ignore_index=True)
    for f in files:
        print(f"player rows: {f.name}  sha256 {hashlib.sha256(f.read_bytes()).hexdigest()}")
    for (s, wk), g in pooled.groupby(["season", "week"]):
        report(g, f"{s} W{wk}")
    report(pooled, "POOLED")
    print(RULE)
    for line in revisit(pooled, bootstrap(pooled)):
        print("REVISIT CHECK:", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
