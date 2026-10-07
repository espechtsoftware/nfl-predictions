"""A player's PAST top-1% frequency (prior weeks' real fields) as a pre-lock feature for the next week: does it separate
the winners' players from the field's picks beyond projection, salary and ownership? (The winner-likeness plan's one
player-level input.) prior_lift = mean over prior weeks of log(top-1% share / field share); prior_top = mean prior top-1%
share; players without history get the position's mean (flagged). Usage: OUT_DIR"""
import importlib.util, sys
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
out = Path(sys.argv[1]); hist = {}; rows = []
for w in (1, 2, 3, 4):
    W, fr, f = WSS.load_week(w); N = len(f); fr = fr.copy()
    top = f[f["rank"] <= 0.01 * N]; ct = Counter(i for v in top.ix for i in v if i >= 0); cf = Counter(i for v in f.ix for i in v if i >= 0)
    fr["top_share"] = [ct.get(i, 0) / len(top) for i in range(len(fr))]; fr["field_share"] = [cf.get(i, 0) / N for i in range(len(fr))]
    fr["lift"] = (fr.top_share + 0.002) / (fr.field_share + 0.002); fr["resid"] = fr.actual - fr.proj
    if w > 1:
        sk = fr[fr.pos.isin(["QB", "RB", "WR", "TE"]) & (fr.field_share >= 0.002) & fr.eligible].copy()
        h = pd.DataFrame(hist).T  # index id; columns: lift_w{k}, top_w{k}
        sk["prior_lift"] = sk.id.map(h[[c for c in h.columns if c.startswith("lift_")]].mean(axis=1)); sk["prior_top"] = sk.id.map(h[[c for c in h.columns if c.startswith("top_")]].mean(axis=1))
        has = sk.prior_lift.notna(); print(f"W{w}: {len(sk)} players, {int(has.sum())} with prior-week history", flush=True)
        sk = sk[has].copy()
        feats = ["prior_lift", "prior_top"]; ctrl = [c for c in ("proj", "salary", "pown") if sk[c].notna().mean() > 0.5]
        z = sk.groupby("pos")[feats + ctrl].transform(lambda s: (s - s.mean()) / (s.std() + 1e-9)).fillna(0.0)
        for cc in feats:
            a = float(np.average(z[cc], weights=sk.top_share + 1e-9) - np.average(z[cc], weights=sk.field_share + 1e-9))
            X = np.column_stack([np.ones(len(sk))] + [z[k].values for k in ctrl] + [z[cc].values]); dof = max(1, len(sk) - X.shape[1])
            y = np.log(sk.lift.values); b, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ b; t = b[-1] / np.sqrt((np.linalg.pinv(X.T @ X) * (r @ r / dof))[-1, -1] + 1e-12)
            yr = sk.resid.values; br, *_ = np.linalg.lstsq(X, yr, rcond=None); rr = yr - X @ br; tr = br[-1] / np.sqrt((np.linalg.pinv(X.T @ X) * (rr @ rr / dof))[-1, -1] + 1e-12)
            # the raw (uncontrolled) correlation too: is past top-1% frequency just ownership / projection?
            raw = float(np.corrcoef(z[cc], np.log(sk.lift))[0, 1]); own = float(np.corrcoef(z[cc], z["pown"])[0, 1]) if "pown" in z else float("nan"); pj = float(np.corrcoef(z[cc], z["proj"])[0, 1])
            rows.append({"week": w, "feature": cc, "n": len(sk), "winners_minus_field_z": round(a, 3), "raw_corr_with_lift": round(raw, 3), "corr_with_proj": round(pj, 3), "corr_with_pown": round(own, 3),
                         "lift_slope": round(float(b[-1]), 3), "lift_t": round(float(t), 2), "resid_slope_pts": round(float(br[-1]), 2), "resid_t": round(float(tr), 2)})
    for _, r_ in fr[fr.field_share >= 0.002].iterrows():
        hist.setdefault(r_.id, {})[f"lift_w{w}"] = float(np.log(r_.lift)); hist[r_.id][f"top_w{w}"] = float(r_.top_share)
df = pd.DataFrame(rows); df.to_csv(out / "attribution_history.csv", index=False); print(df.to_string())
print("\npooled:"); print(df.groupby("feature")[["winners_minus_field_z", "raw_corr_with_lift", "corr_with_proj", "corr_with_pown", "lift_slope", "lift_t", "resid_slope_pts", "resid_t"]].mean().round(3).to_string())
