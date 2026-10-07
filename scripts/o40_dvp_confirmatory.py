#!/usr/bin/env python3
"""O-40's CONFIRMATORY ablation (reports/2026-10-07-prereg-o40-dvp-ablation.md §2, frozen 2026-10-07 before it runs):
does adding the four position-matchup columns (qb/rb/wr/te_fp_allowed_adj_l6) to the O-22-REPAIRED projection model
improve its within-week ranking on untouched seasons?

- Arms: BASE_R (the repaired model) vs DVP4_R (+ the four columns) = the DECISION; DEF7_R (+ the three defence EPA / red-zone
  columns as well) exploratory. The columns must be REGISTERED in featureset.CANDIDATE_FEATURES (Monday's merge); this script
  refuses to register them in-process.
- Targets: 2020, 2021, 2022, each walk-forward trained on the seasons before it (components.train(panel, target)).
- Rows: the target season's active player-weeks with an actual whose BASE_R projection is >= 5 (the same rows in every arm).
- PRIMARY per season: the mean over weeks of the equal-weighted mean over QB / RB / WR / TE of the within-week x position
  Spearman between actual DK points and the projection (a group needs >= MIN_GROUP rows: 10, the screen's convention).
- PASS needs all three: (1) DVP4_R - BASE_R > 0 in at least 2 of 3 seasons; (2) the pooled difference -- the mean of the
  weekly differences over all target weeks -- has a one-sided 95% lower bound > 0 by resampling weeks within each season
  (B 20,000, seed 20261040); (3) no season's MAE (same rows) worse by more than 1%. Otherwise NOT PASS. 2026 W3-W4 descriptive.
- Mean DK points come from the components exactly as the screen did (mean_dk: no yardage bonuses; identical across arms).

- Provenance (the reviewer 10-07): REFUSES unless the O-22 repair (0bc6b6bc and the o22-leak-fixes branch tip) is an
  ancestor of HEAD, or if DROP_FEATURES is set; the JSON records the code commit, featureset's sha256 and the training
  panel's identity (the table's modified time and rows, and a content fingerprint of the panel read).
- --smoke-target <season> (mechanics only, never 2020-2022 or 2026): rows, weeks and dropped groups per arm; no
  correlations, no verdict. Monday: the 2019 smoke, then the frozen run with the default targets.

    python scripts/o40_dvp_confirmatory.py [--out o40_confirmatory.json] [--smoke-target 2019]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DVP4 = ["qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6", "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6"]
DEF3 = ["epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6", "rz_td_rate_allowed_l6"]
ARMS = {"BASE_R": [], "DVP4_R": DVP4, "DEF7_R": DVP4 + DEF3}
TARGETS = (2020, 2021, 2022)
POSITIONS = ("QB", "RB", "WR", "TE")
MIN_GROUP = 10
PROJ_FLOOR = 5.0
B, SEED = 20_000, 20261040
MAE_GUARD = 1.01
O22_FIX = "0bc6b6bc"                               # the as-of serving fix inside the O-22 repair
O22_BRANCH = "origin/production/o22-leak-fixes-20261005"
FORBIDDEN_SMOKE = set(TARGETS) | {2026}


def mean_dk(pc: pd.DataFrame) -> np.ndarray:
    """The screen's mean DK points from the component predictions (no yardage bonuses)."""
    g = lambda c: pc[c].to_numpy(float) if c in pc else 0.0     # noqa: E731
    rec = g("targets") * g("catch_rate")
    return (0.04 * g("pass_attempts") * g("ypa") + 4 * g("pass_tds") - g("interceptions")
            + 0.1 * g("carries") * g("ypc") + 6 * g("rush_tds")
            + rec + 0.1 * rec * g("ypr") + 6 * g("rec_tds"))


def weekly_rank_corr(df: pd.DataFrame, pred: str, y: str = "y") -> pd.Series:
    """Per week: the equal-weighted mean over positions of the within-week x position Spearman (groups >= MIN_GROUP)."""
    out = {}
    for w, g in df.groupby("week"):
        rhos = []
        for pos in POSITIONS:
            h = g[g.position == pos]
            if len(h) >= MIN_GROUP and h[pred].nunique() > 1 and h[y].nunique() > 1:
                rhos.append(stats.spearmanr(h[pred], h[y]).statistic)
        if rhos:
            out[w] = float(np.mean(rhos))
    return pd.Series(out, dtype=float)


def pooled_lower_bound(diffs: dict[int, pd.Series], b: int = B, seed: int = SEED) -> tuple[float, float]:
    """The pooled mean of the weekly differences over every target week, and its one-sided 95% lower bound by resampling
    weeks within each season (each season keeps its week count)."""
    rng = np.random.default_rng(seed)
    arrays = [d.to_numpy(float) for d in diffs.values() if len(d)]
    pooled = float(np.concatenate(arrays).mean())
    sums = np.zeros(b); n = sum(len(x) for x in arrays)
    for x in arrays:
        idx = rng.integers(0, len(x), size=(b, len(x)))
        sums += x[idx].sum(axis=1)
    return pooled, float(np.quantile(sums / n, 0.05))


def dropped_groups(df: pd.DataFrame) -> int:
    """Week x position groups with fewer than MIN_GROUP rows (mechanics for the smoke)."""
    return int(sum(len(df[(df.week == w) & (df.position == p)]) < MIN_GROUP for w in df.week.unique() for p in POSITIONS))


def provenance(repo: Path) -> dict:
    """The code identity; refuses (SystemExit) unless the O-22 repair is in HEAD's history."""
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)     # noqa: E731
    head = git("rev-parse", "HEAD").stdout.strip()
    tip = git("rev-parse", O22_BRANCH).stdout.strip()
    for c, name in ((O22_FIX, "the as-of fix 0bc6b6bc"), (tip, f"{O22_BRANCH} ({tip[:8] or 'unresolved'})")):
        if not c or git("merge-base", "--is-ancestor", c, head).returncode != 0:
            raise SystemExit(f"O-40 CONFIRMATORY REFUSED: {name} is not an ancestor of HEAD {head[:8]}: not the O-22-repaired base")
    return {"code_commit": head, "o22_branch_tip": tip}


def decide(season_diff: dict[int, float], lower: float, mae: dict[int, tuple[float, float]]) -> tuple[str, list[str]]:
    why = []
    pos = sum(v > 0 for v in season_diff.values())
    if pos < 2:
        why.append(f"(1) positive in {pos} of {len(season_diff)} seasons (< 2)")
    if not lower > 0:
        why.append(f"(2) pooled one-sided 95% lower bound {lower:+.5f} is not > 0")
    worse = [s for s, (base, dvp) in mae.items() if dvp > MAE_GUARD * base]
    if worse:
        why.append(f"(3) MAE worse by more than 1% in {worse}")
    return ("PASS" if not why else "NOT PASS"), why


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); ap.add_argument("--out", default="o40_confirmatory.json")
    ap.add_argument("--smoke-target", type=int, help="mechanics only on one season (never 2020-2022 or 2026)")
    a = ap.parse_args(argv)
    if a.smoke_target is not None and a.smoke_target in FORBIDDEN_SMOKE:
        print(f"O-40 SMOKE REFUSED: {a.smoke_target} is a decision / descriptive season; smoke on an earlier one (2019)", file=sys.stderr)
        return 2
    if os.environ.get("DROP_FEATURES", "").strip():
        print("O-40 CONFIRMATORY REFUSED: DROP_FEATURES is set; BASE_R must be exactly the repaired base", file=sys.stderr)
        return 2
    from nfl_dfs.models import featureset as FS
    from nfl_dfs.models import components as C
    from nfl_dfs.models import train_job as TJ
    missing = [c for c in DVP4 + DEF3 if c not in FS.CANDIDATE_FEATURES]
    if missing:
        print(f"O-40 CONFIRMATORY REFUSED: {missing} are not registered CANDIDATE_FEATURES (Monday's merge registers them; "
              "this script never registers in-process)", file=sys.stderr)
        return 2
    prov = provenance(Path(__file__).resolve().parents[1])
    panel = TJ.training_panel()
    from nfl_dfs.bq import client as bq_client
    from nfl_dfs.config import settings
    t = bq_client().get_table(f"{settings.features}.player_week_training")
    prov.update({"featureset_sha256": hashlib.sha256(Path(FS.__file__).read_bytes()).hexdigest(),
                 "panel_table_modified": t.modified.isoformat() if t.modified else None, "panel_table_rows": int(t.num_rows or 0),
                 "panel_rows_read": int(len(panel)),
                 "panel_fingerprint": int(pd.util.hash_pandas_object(panel, index=False).sum() & 0xFFFFFFFFFFFF)})
    print("provenance:", json.dumps(prov), flush=True)
    ycol = "y_dk_points" if "y_dk_points" in panel else "dk_points"
    res = {"provenance": prov, "targets": {}, "descriptive_2026": {}}
    for target in ((a.smoke_target,) if a.smoke_target is not None else TARGETS + (2026,)):
        rows = panel[panel.season == target]
        rows = FS.active_training_rows(rows)
        rows = rows[rows[ycol].notna()].copy()
        if target == 2026:
            rows = rows[rows.week.isin([3, 4])]
        preds = {}
        for arm, extra in ARMS.items():
            os.environ["EXTRA_FEATURES"] = ",".join(extra)
            m = C.train(panel, target)
            preds[arm] = mean_dk(m.predict_components(rows))
        os.environ.pop("EXTRA_FEATURES", None)
        d = rows.assign(y=rows[ycol].to_numpy(float), **{f"p_{k}": v for k, v in preds.items()})
        d = d[d.p_BASE_R >= PROJ_FLOOR]                                   # the same rows in every arm
        if a.smoke_target is not None:                                    # mechanics only: no correlation, no verdict
            print(f"SMOKE {target}: rows {len(d)} weeks {d.week.nunique()} groups dropped (< {MIN_GROUP}) {dropped_groups(d)} "
                  f"of {d.week.nunique() * len(POSITIONS)}; arms trained {list(preds)}", flush=True)
            with open(a.out, "w") as h:
                json.dump({"provenance": prov, "smoke": {"target": target, "rows": int(len(d)), "weeks": int(d.week.nunique()),
                                                         "groups_dropped": dropped_groups(d)}}, h, indent=1)
            return 0
        wk = {arm: weekly_rank_corr(d, f"p_{arm}") for arm in ARMS}
        mae = {arm: float(np.abs(d[f"p_{arm}"] - d.y).mean()) for arm in ARMS}
        entry = {"rows": int(len(d)), "weeks": int(len(wk["BASE_R"])),
                 "rank_corr": {arm: float(v.mean()) for arm, v in wk.items()}, "mae": mae,
                 "weekly_diff_dvp4": (wk["DVP4_R"] - wk["BASE_R"]).dropna().round(6).to_dict()}
        (res["descriptive_2026"] if target == 2026 else res["targets"])[str(target)] = entry
        print(f"{target}: rows {entry['rows']} weeks {entry['weeks']}  rank corr " +
              "  ".join(f"{k} {v:.5f}" for k, v in entry["rank_corr"].items()) + "  MAE " +
              "  ".join(f"{k} {v:.4f}" for k, v in mae.items()), flush=True)
    diffs = {int(t): pd.Series(e["weekly_diff_dvp4"], dtype=float) for t, e in res["targets"].items()}
    season_diff = {int(t): e["rank_corr"]["DVP4_R"] - e["rank_corr"]["BASE_R"] for t, e in res["targets"].items()}
    pooled, lower = pooled_lower_bound(diffs)
    mae = {int(t): (e["mae"]["BASE_R"], e["mae"]["DVP4_R"]) for t, e in res["targets"].items()}
    verdict, why = decide(season_diff, lower, mae)
    res.update({"season_diff_dvp4": season_diff, "pooled": pooled, "lower_95": lower, "verdict": verdict, "why": why,
                "constants": {"MIN_GROUP": MIN_GROUP, "PROJ_FLOOR": PROJ_FLOOR, "B": B, "SEED": SEED, "MAE_GUARD": MAE_GUARD}})
    print("DVP4_R - BASE_R by season: " + "  ".join(f"{t} {v:+.5f}" for t, v in season_diff.items()))
    print(f"pooled {pooled:+.5f}, one-sided 95% lower bound {lower:+.5f} (B {B}, seed {SEED})")
    print(f"-> {verdict}" + (f": {'; '.join(why)}" if why else ""))
    with open(a.out, "w") as h:
        json.dump(res, h, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
