"""Split-conformal calibration vs our interval sources, on the real panel.

Question (research round 7): does conformal calibration produce better
q90/intervals than (a) the LightGBM quantile model and (b) the
Gaussian proj+sd shape the sim uses? Walk-forward: train 2019-2023,
calibrate 2024 (conformal residual quantiles), test 2025.
Conformalized Quantile Regression (CQR, Romano et al.): adjust the raw
quantile prediction by the calibration-set residual quantile.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb

S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"
df = pd.read_parquet(f"{S}/panel.parquet")
feats = open(f"{S}/features.txt").read().split()
df = df[df.y_dk_points.notna()].copy()
df["pos_code"] = df.position.map({p: i for i, p in enumerate(["QB", "RB", "WR", "TE"])})
X_cols = sorted(feats) + ["pos_code"]
for c in X_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce")

tr = df[df.season <= 2023]
cal = df[df.season == 2024]
te = df[df.season == 2025]
common = dict(n_estimators=600, learning_rate=0.04, num_leaves=63,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
              n_jobs=4, random_state=7, verbose=-1)
Xtr, ytr = tr[X_cols], tr.y_dk_points.to_numpy()
Xcal, ycal = cal[X_cols], cal.y_dk_points.to_numpy()
Xte, yte = te[X_cols], te.y_dk_points.to_numpy()

mean_m = lgb.LGBMRegressor(**common).fit(Xtr, ytr)
q90_m = lgb.LGBMRegressor(objective="quantile", alpha=0.9, **common).fit(Xtr, ytr)


def pinball(y, qp, q=0.9):
    d = y - qp
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def rep(name, q90):
    cov = float(np.mean(yte <= q90))
    print(f"{name:34s} P(y<=q90)={cov:.3f} pinball90={pinball(yte, q90):.4f} "
          f"mean_q90={q90.mean():6.2f}", flush=True)


# 1) raw LGB quantile model
raw_q90_te = q90_m.predict(Xte)
rep("LGB quantile raw", raw_q90_te)

# 2) CQR: shift raw q90 by calibration residual quantile (target 0.90)
resid = ycal - q90_m.predict(Xcal)          # >0 where q90 under-covers
shift = np.quantile(resid, 0.90)
rep(f"CQR-conformalized (shift {shift:+.2f})", raw_q90_te + shift)

# 3) Gaussian proj+sd (the sim's marginal shape pre-EMP): mean + z*sd,
#    sd from a second model on absolute residuals (our proj_sd analogue)
res_m = lgb.LGBMRegressor(**common).fit(
    Xtr, np.abs(ytr - mean_m.predict(Xtr)))
sd_te = np.maximum(res_m.predict(Xte), 1e-3) * 1.2533  # E|X-mu| -> sd
rep("Gaussian mean+1.2816*sd", mean_m.predict(Xte) + 1.2816 * sd_te)

# 4) conformalized Gaussian: z chosen on calibration set for exact 90%
sd_cal = np.maximum(res_m.predict(Xcal), 1e-3) * 1.2533
zscore = np.quantile((ycal - mean_m.predict(Xcal)) / sd_cal, 0.90)
rep(f"Conformal-z Gaussian (z={zscore:.2f})", mean_m.predict(Xte) + zscore * sd_te)

# positional coverage drift of the best two, the actionable detail
for name, q90 in [("raw", raw_q90_te), ("CQR", raw_q90_te + shift)]:
    covs = {p: round(float(np.mean(yte[(te.position == p).to_numpy()] <=
                                   q90[(te.position == p).to_numpy()])), 3)
            for p in ["QB", "RB", "WR", "TE"]}
    print(f"  {name} coverage by pos: {covs}", flush=True)
print("CONFORMAL_DONE", flush=True)
