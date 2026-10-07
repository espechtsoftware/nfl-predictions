"""Per-player PAST top-1% frequency from the prior weeks' REAL Millionaire fields, as a union bonus file (the ownership-term
format: dk_player_id, pred_own). pred_own = 5 x z(prior_top within position), negatives -> 0, so tilt 0.20 adds ~1 projected
point per standard deviation (the attribution's residual slope). Files for W2 (from W1), W3 (W1-2), W4 (W1-3), W5 (W1-4)."""
import importlib.util, sys
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path("/home/erich/projects/.nfl-predictions-worktrees/review/outside-fill-order-20261006/reports/2026-10-07-winners-strategy-study")
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
out = Path(sys.argv[1]); hist = []
for w in (1, 2, 3, 4):
    W, fr, f = WSS.load_week(w); N = len(f); top = f[f["rank"] <= 0.01 * N]
    ct = Counter(i for v in top.ix for i in v if i >= 0); cf = Counter(i for v in f.ix for i in v if i >= 0)
    fr = fr.assign(top_share=[ct.get(i, 0) / len(top) for i in range(len(fr))], field_share=[cf.get(i, 0) / N for i in range(len(fr))], week=w)
    hist.append(fr[["id", "display_name", "pos", "team", "week", "top_share", "field_share"]])
H = pd.concat(hist, ignore_index=True)
for w in (2, 3, 4, 5):
    prior = H[H.week < w].groupby("id").agg(prior_top=("top_share", "mean"), weeks=("week", "count"), display_name=("display_name", "last"), pos=("pos", "last"), team=("team", "last")).reset_index()
    z = prior.groupby("pos").prior_top.transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    prior["pred_own"] = np.clip(5.0 * z, 0.0, None).round(4)
    d = pd.DataFrame({"dk_player_id": prior.id.astype(int), "id": prior.id, "display_name": prior.display_name, "pos": prior.pos, "team": prior.team, "pred_own": prior.pred_own, "prior_top": prior.prior_top.round(5), "weeks": prior.weeks})
    d.to_csv(out / f"priortop-w{w}.csv", index=False)
    print(f"W{w} file: {len(d)} players from weeks < {w}; pred_own > 0 for {int((d.pred_own > 0).sum())}; max {d.pred_own.max():.2f}; top 5: " + ", ".join(f"{r.display_name} {r.pred_own:.1f}" for r in d.sort_values('pred_own', ascending=False).head(5).itertuples()), flush=True)
