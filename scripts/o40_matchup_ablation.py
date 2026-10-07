"""Matchup ablation (the operator 10-07, "five alarm fire"): does adding position-level opponent points-allowed to the
projection model improve its accuracy? Walk-forward by season (train on seasons < target), the production component
models, three arms: BASE (production NUMERIC_FEATURES), DVP4 (+ qb/rb/wr/te_fp_allowed_adj_l6), DEF7 (+ the three
defence EPA / red-zone columns as well). Mean DK points from the components (no yardage bonuses; identical across arms).
Metrics on the target season's active player-weeks: MAE, and the mean within-week Spearman rank correlation by position.
Research only: the candidates are registered in-process, never in production."""
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats

WT = os.environ["WT"]
sys.path.insert(0, f"{WT}/src")
from nfl_dfs.models import featureset as FS          # noqa: E402
from nfl_dfs.models import components as C          # noqa: E402
from nfl_dfs.models import train_job as TJ          # noqa: E402

DVP4 = ["qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6", "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6"]
DEF3 = ["epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6", "rz_td_rate_allowed_l6"]
FS.CANDIDATE_FEATURES = tuple(FS.CANDIDATE_FEATURES) + tuple(DVP4 + DEF3)
ARMS = {"BASE": [], "DVP4": DVP4, "DEF7": DVP4 + DEF3}


def mean_dk(pc: pd.DataFrame) -> np.ndarray:
    g = lambda c: pc[c].to_numpy(float) if c in pc else 0.0     # noqa: E731
    rec = g("targets") * g("catch_rate")
    return (0.04 * g("pass_attempts") * g("ypa") + 4 * g("pass_tds") - g("interceptions")
            + 0.1 * g("carries") * g("ypc") + 6 * g("rush_tds")
            + rec + 0.1 * rec * g("ypr") + 6 * g("rec_tds"))


def scores(df: pd.DataFrame, pred: np.ndarray) -> dict:
    y = df.y_dk_points.to_numpy(float) if "y_dk_points" in df else df.dk_points.to_numpy(float)
    out = {"n": len(df), "mae": float(np.abs(pred - y).mean())}
    rhos = []
    for (_, pos), g in df.assign(_p=pred, _y=y).groupby(["week", "position"]):
        if len(g) >= 10:
            rhos.append(stats.spearmanr(g._p, g._y).statistic)
    out["rank_corr"] = float(np.nanmean(rhos))
    return out


panel = TJ.training_panel()
print("panel", panel.shape, "seasons", sorted(panel.season.unique())[-6:], flush=True)
ycol = "y_dk_points" if "y_dk_points" in panel else "dk_points"
rows = []
for target in (2023, 2024, 2025, 2026):
    test = FS.active_training_rows(panel[panel.season == target]) if hasattr(FS, "active_training_rows") else panel[panel.season == target]
    test = test[test[ycol].notna()]
    if target == 2026:
        test = test[test.week.isin([3, 4])]                       # the weeks whose matchup columns exist
    for arm, extra in ARMS.items():
        os.environ["EXTRA_FEATURES"] = ",".join(extra)
        t0 = time.time()
        m = C.train(panel, target)
        pred = mean_dk(m.predict_components(test))
        r = {"target": target, "arm": arm, **scores(test, pred), "secs": round(time.time() - t0)}
        rows.append(r); print(r, flush=True)
df = pd.DataFrame(rows)
base = df[df.arm == "BASE"].set_index("target")
for arm in ("DVP4", "DEF7"):
    a = df[df.arm == arm].set_index("target")
    print(arm, "minus BASE:", {int(t): {"mae": round(a.mae[t] - base.mae[t], 4), "rank_corr": round(a.rank_corr[t] - base.rank_corr[t], 4)}
                              for t in base.index})
df.to_csv(os.environ.get("OUT", "matchup_ablation.csv"), index=False)
