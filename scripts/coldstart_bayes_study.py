"""Hierarchical partial pooling vs LGB on COLD-START rows (round 10).

Empirical-Bayes version (closed form; NumPyro only if this shows
signal): player estimate = shrink(trailing mean -> group mean ->
position mean), groups = (position, draft-round bucket, depth bucket).
Test slice: 2025 rows with games_played_prior <= 2. Incumbent: the
quick-LGB with ALL features (it sees draft_round/depth/is_cold_start,
so it can pool implicitly — the question is whether explicit pooling
beats it on the thin slice).
"""
import numpy as np
import pandas as pd
import lightgbm as lgb

S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"
df = pd.read_parquet(f"{S}/panel.parquet")
df = df[df.y_dk_points.notna()].copy()
feats = open(f"{S}/features.txt").read().split()
df["pos_code"] = df.position.map({p: i for i, p in enumerate(["QB","RB","WR","TE"])})
X_cols = sorted(feats) + ["pos_code"]
for c in X_cols + ["draft_round", "depth_rank", "games_played_prior"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

tr = df[df.season <= 2024]
te = df[df.season == 2025]
cold_te = te[te.games_played_prior <= 2]
print(f"cold-start 2025 rows: {len(cold_te)}")

common = dict(n_estimators=600, learning_rate=0.04, num_leaves=63,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
              n_jobs=4, random_state=7, verbose=-1)
m = lgb.LGBMRegressor(**common).fit(tr[X_cols], tr.y_dk_points)
lgb_pred = m.predict(cold_te[X_cols])

# hierarchical: position -> (pos, dr bucket, depth bucket) -> player
tr = tr.assign(drb=tr.draft_round.fillna(8).clip(1, 8).astype(int),
               dpb=tr.depth_rank.fillna(3).clip(1, 3).astype(int))
cold = cold_te.assign(drb=cold_te.draft_round.fillna(8).clip(1, 8).astype(int),
                      dpb=cold_te.depth_rank.fillna(3).clip(1, 3).astype(int))
pos_mean = tr.groupby("position").y_dk_points.mean()
K_GROUP, K_PLAYER = 30, 3
grp = tr.groupby(["position", "drb", "dpb"]).y_dk_points.agg(["mean", "size"])
rows = []
for r in cold.itertuples():
    pm = pos_mean[r.position]
    if (r.position, r.drb, r.dpb) in grp.index:
        g = grp.loc[(r.position, r.drb, r.dpb)]
        gm = (g["mean"] * g["size"] + pm * K_GROUP) / (g["size"] + K_GROUP)
    else:
        gm = pm
    n = r.games_played_prior if not np.isnan(r.games_played_prior) else 0
    own = r.dk_points_l4 if not np.isnan(r.dk_points_l4) else gm
    rows.append((own * n + gm * K_PLAYER) / (n + K_PLAYER))
bayes_pred = np.array(rows)
blend = 0.5 * lgb_pred + 0.5 * bayes_pred

y = cold_te.y_dk_points.to_numpy()
for name, p in [("LGB", lgb_pred), ("hier-EB", bayes_pred), ("blend", blend)]:
    print(f"{name:8s} rmse={np.sqrt(np.mean((y-p)**2)):.3f} "
          f"mae={np.abs(y-p).mean():.3f} bias={np.mean(p-y):+.2f}")
# and on the not-cold slice for contrast
warm = te[te.games_played_prior > 8]
wp = m.predict(warm[X_cols])
print(f"(contrast) LGB warm rmse={np.sqrt(np.mean((warm.y_dk_points-wp)**2)):.3f}")
print("COLDSTART_DONE", flush=True)
