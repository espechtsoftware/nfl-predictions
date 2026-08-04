"""TabPFN-2.5 vs LightGBM vs trailing baseline on the real player-week panel.

Walk-forward by season (the validation law): train/context = 2019-2024,
test = ALL of 2025. Metrics that match how the system actually uses
projections: RMSE on the mean (accuracy) and pinball loss at q90
(ceiling quality — the GPP-relevant tail).
CPU-only, thread-capped: the box must stay alive for the panel queue.
"""
import time

import numpy as np
import pandas as pd
import torch

torch.set_num_threads(4)
S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"

df = pd.read_parquet(f"{S}/panel.parquet")
feats = open(f"{S}/features.txt").read().split()
df = df[df.y_dk_points.notna()].copy()
pos_codes = {p: i for i, p in enumerate(["QB", "RB", "WR", "TE"])}
df["pos_code"] = df.position.map(pos_codes)
X_cols = sorted(feats) + ["pos_code"]
for c in X_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce")

train = df[df.season <= 2024]
test = df[df.season == 2025]
Xtr, ytr = train[X_cols].to_numpy(np.float32), train.y_dk_points.to_numpy(np.float32)
Xte, yte = test[X_cols].to_numpy(np.float32), test.y_dk_points.to_numpy(np.float32)
print(f"train {Xtr.shape} test {Xte.shape}", flush=True)


def pinball(y, q_pred, q=0.9):
    d = y - q_pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def report(name, mean_pred, q90_pred, elapsed):
    rows = []
    for label, mask in [("ALL", np.ones(len(yte), bool))] + [
            (p, (test.position == p).to_numpy()) for p in pos_codes]:
        rmse = float(np.sqrt(np.mean((yte[mask] - mean_pred[mask]) ** 2)))
        pb = pinball(yte[mask], q90_pred[mask])
        cov = float(np.mean(yte[mask] <= q90_pred[mask]))
        rows.append(f"  {label:4s} rmse={rmse:6.3f} pinball90={pb:6.4f} P(y<=q90)={cov:.3f}")
    print(f"== {name} ({elapsed:.0f}s) ==\n" + "\n".join(rows), flush=True)


# --- baseline: trailing dk_points_l4 as mean; l4 + 1.2816*std as q90
t0 = time.time()
l4 = pd.to_numeric(test.dk_points_l4, errors="coerce").fillna(0).to_numpy(np.float32)
sd = pd.to_numeric(test.dk_points_std, errors="coerce").fillna(6).to_numpy(np.float32)
report("BASELINE dk_points_l4", l4, l4 + 1.2816 * sd, time.time() - t0)

# --- LightGBM (our shape: mean model + q90 quantile model)
import lightgbm as lgb

t0 = time.time()
common = dict(n_estimators=600, learning_rate=0.04, num_leaves=63,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
              n_jobs=4, random_state=7, verbose=-1)
m = lgb.LGBMRegressor(**common).fit(Xtr, ytr)
q = lgb.LGBMRegressor(objective="quantile", alpha=0.9, **common).fit(Xtr, ytr)
report("LightGBM mean+q90", m.predict(Xte).astype(np.float32),
       q.predict(Xte).astype(np.float32), time.time() - t0)

# --- TabPFN: subsampled context (CPU envelope), full-distribution output
from tabpfn import TabPFNRegressor

rng = np.random.default_rng(7)
for n_ctx in (8000,):
    idx = rng.choice(len(Xtr), size=min(n_ctx, len(Xtr)), replace=False)
    t0 = time.time()
    reg = TabPFNRegressor(device="cpu", n_estimators=2,
                          ignore_pretraining_limits=True, random_state=7)
    reg.fit(Xtr[idx], ytr[idx])
    try:
        qs = reg.predict(Xte, output_type="quantiles", quantiles=[0.5, 0.9])
        med, q90 = np.asarray(qs[0]), np.asarray(qs[1])
        mean_pred = reg.predict(Xte)
    except TypeError:
        mean_pred = reg.predict(Xte)
        med, q90 = mean_pred, mean_pred  # quantile API unavailable
    report(f"TabPFN ctx={len(idx)} mean+q90",
           np.asarray(mean_pred, np.float32), np.asarray(q90, np.float32),
           time.time() - t0)
print("EXPERIMENT_DONE", flush=True)
