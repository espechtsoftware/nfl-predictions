"""Which PRE-LOCK player facts separate the winners' players from the projection's picks? (operator 2026-10-07: "exactly
what kind of additional player data is needed to better select?") For each week: every slate player's share of the real
Millionaire top-1% lineups vs his share of the whole field (the lift), and his actual points minus the projection we played.
Then, feature by feature (z-scored within week x position), (a) the lift-weighted mean of the feature among the top-1%
player-slots minus its ownership-weighted mean in the field; (b) the partial slope of log(lift) on the feature controlling
for projection, salary and projected ownership (where it exists), pooled with week effects, with the sign per week;
(c) the same slope for the residual (actual - projection). Output: one table. Usage: attribution.py OUT_DIR"""
import importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
FEATS = ["proj", "market_points", "salary", "pown", "implied_team_total", "total_line", "spread", "targets_l4", "target_share_l4",
         "target_share_last", "target_share_jump", "target_share_trend", "rz20_targets_l4", "rz10_targets_l4", "rz20_target_share_l4",
         "ez_targets_l4", "deep_targets_l4", "air_yards_share_l4", "wopr_l4", "carries_l4", "carry_share_l4", "carry_share_jump",
         "gl3_carries_l4", "gl3_carry_share_l4", "snap_share_l4", "snap_share_jump", "fp_route_share_l4", "fp_route_share_jump",
         "team_vacated_target_share", "team_vacated_carry_share", "depth_rank", "xfp_l4", "yards_per_target_l8", "yards_per_carry_l8",
         "pace_l4", "proe_l4", "games_played_prior", "dk_ppg"]
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); rows = []
for w in (1, 2, 3, 4):
    W, fr, f = WSS.load_week(w); N = len(f); fr = fr.copy()
    raw = pd.read_parquet(Path(WSS.CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id")
    raw["id"] = raw.dk_player_id.astype("Int64").astype(str); raw = raw.set_index("id")
    for c in FEATS:
        if c not in fr.columns and c in raw.columns: fr[c] = fr.id.map(pd.to_numeric(raw[c], errors="coerce"))
    fr["value"] = fr.proj / fr.salary * 1000
    top = f[f["rank"] <= 0.01 * N]
    from collections import Counter
    ct = Counter(i for v in top.ix for i in v if i >= 0); cf = Counter(i for v in f.ix for i in v if i >= 0)
    fr["top_share"] = [ct.get(i, 0) / len(top) for i in range(len(fr))]; fr["field_share"] = [cf.get(i, 0) / N for i in range(len(fr))]
    fr["lift"] = (fr.top_share + 0.002) / (fr.field_share + 0.002); fr["resid"] = fr.actual - fr.proj
    sk = fr[fr.pos.isin(["QB", "RB", "WR", "TE"]) & (fr.field_share >= 0.002) & fr.eligible].copy()
    feats = [c for c in FEATS + ["value"] if c in sk.columns and sk[c].notna().mean() > 0.5]
    z = sk.groupby("pos")[feats].transform(lambda s: (s - s.mean()) / (s.std() + 1e-9)).fillna(0.0)
    ctrl = [c for c in ("proj", "salary", "pown") if c in feats and sk[c].notna().mean() > 0.5]
    for c in feats:
        a = float(np.average(z[c], weights=sk.top_share + 1e-9) - np.average(z[c], weights=sk.field_share + 1e-9))
        X = np.column_stack([np.ones(len(sk))] + [z[k].values for k in ctrl if k != c] + [z[c].values]); y = np.log(sk.lift.values)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None); res = y - X @ beta; dof = max(1, len(y) - X.shape[1])
        cov = np.linalg.pinv(X.T @ X) * (res @ res / dof); t = beta[-1] / np.sqrt(cov[-1, -1] + 1e-12)
        Xr = X; yr = sk.resid.values; br, *_ = np.linalg.lstsq(Xr, yr, rcond=None); rr = yr - Xr @ br
        covr = np.linalg.pinv(Xr.T @ Xr) * (rr @ rr / dof); tr = br[-1] / np.sqrt(covr[-1, -1] + 1e-12)
        rows.append({"week": w, "feature": c, "n": len(sk), "winners_minus_field_z": round(a, 3), "lift_slope": round(float(beta[-1]), 3), "lift_t": round(float(t), 2),
                     "resid_slope_pts": round(float(br[-1]), 2), "resid_t": round(float(tr), 2)})
    print(f"W{w}: {len(sk)} players, top-1% lineups {len(top)}", flush=True)
df = pd.DataFrame(rows); df.to_csv(out / "attribution_by_week.csv", index=False)
g = df.groupby("feature").agg(weeks=("week", "count"), wmf_mean=("winners_minus_field_z", "mean"), wmf_pos=("winners_minus_field_z", lambda s: int((s > 0).sum())),
                              lift_slope=("lift_slope", "mean"), lift_t_mean=("lift_t", "mean"), lift_pos=("lift_slope", lambda s: int((s > 0).sum())),
                              resid_slope=("resid_slope_pts", "mean"), resid_t_mean=("resid_t", "mean"), resid_pos=("resid_slope_pts", lambda s: int((s > 0).sum()))).round(3)
g = g.sort_values("lift_t_mean", key=lambda s: -s.abs()); g.to_csv(out / "attribution_pooled.csv")
print("\n== pooled over weeks (sorted by |mean t| of the lift slope; controls: projection, salary, projected ownership where it exists) ==")
print(g.to_string())
