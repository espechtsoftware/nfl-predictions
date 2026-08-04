"""Retrieval-augmented projection (research round 11): kNN comps.

Embed each player-week as its standardized feature vector, retrieve the
K most similar HISTORICAL player-weeks (strictly earlier seasons — the
walk-forward law), forecast from the comps' actual outcome
distribution. Naturally distributional and interpretable. Bar: the
quick-LGB mean + q90 on identical 2025 rows.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.neighbors import NearestNeighbors

S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"
df = pd.read_parquet(f"{S}/panel.parquet")
df = df[df.y_dk_points.notna()].copy()
feats = open(f"{S}/features.txt").read().split()
df["pos_code"] = df.position.map({p: i for i, p in enumerate(["QB","RB","WR","TE"])})
X_cols = sorted(feats) + ["pos_code"]
for c in X_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

tr = df[df.season <= 2024]
te = df[df.season == 2025]
y_tr, y_te = tr.y_dk_points.to_numpy(), te.y_dk_points.to_numpy()

# standardize on train, median-impute
mu = tr[X_cols].median()
sd = tr[X_cols].std().replace(0, 1)
Xtr = ((tr[X_cols].fillna(mu) - mu) / sd).to_numpy(np.float32)
Xte = ((te[X_cols].fillna(mu) - mu) / sd).to_numpy(np.float32)

def pinball(y, qp, q=0.9):
    d = y - qp
    return float(np.mean(np.maximum(q*d, (q-1)*d)))

for K in (30, 50, 100):
    # comps within position: weight position heavily by adding scaled col
    nn = NearestNeighbors(n_neighbors=K).fit(
        np.hstack([Xtr, 10*Xtr[:, [X_cols.index("pos_code")]]]))
    _, idx = nn.kneighbors(
        np.hstack([Xte, 10*Xte[:, [X_cols.index("pos_code")]]]))
    comp_out = y_tr[idx]                       # (n_test, K) outcome draws
    mean_p = comp_out.mean(axis=1)
    q90_p = np.quantile(comp_out, 0.9, axis=1)
    print(f"kNN K={K:3d}: rmse={np.sqrt(np.mean((y_te-mean_p)**2)):.3f} "
          f"pinball90={pinball(y_te, q90_p):.4f} "
          f"cov={np.mean(y_te <= q90_p):.3f}")

common = dict(n_estimators=600, learning_rate=0.04, num_leaves=63,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
              n_jobs=4, random_state=7, verbose=-1)
m = lgb.LGBMRegressor(**common).fit(tr[X_cols], y_tr)
q = lgb.LGBMRegressor(objective="quantile", alpha=0.9, **common).fit(tr[X_cols], y_tr)
mp, qp = m.predict(te[X_cols]), q.predict(te[X_cols])
print(f"LGB       : rmse={np.sqrt(np.mean((y_te-mp)**2)):.3f} "
      f"pinball90={pinball(y_te, qp):.4f} cov={np.mean(y_te <= qp):.3f}")
# blend check: kNN distribution + LGB mean recentering
print("KNN_DONE", flush=True)
