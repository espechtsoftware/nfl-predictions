"""Is the slate scoring ENVIRONMENT predictable pre-lock? ~200 historical slates.

The simulator outputs ~123 every week while reality swings 94-141. If the environment
is predictable from pre-lock information the simulator already has, that is a fixable
calibration defect rather than irreducible noise.
"""
import numpy as np, pandas as pd, sys
from scipy.stats import spearmanr
d = pd.read_parquet("ceiling_panel.parquet")
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce")
num = lambda c: pd.to_numeric(d[c],errors="coerce") if c in d.columns else pd.Series(np.nan,index=d.index)
d["itt"]=num("implied_team_total"); d["gt"]=num("game_total"); d["sal"]=num("salary")
d["l4"]=num("dk_points_l4")
g=d.groupby(["season","week"]).agg(
    n=("y","size"), env=("y","mean"), env_top=("y",lambda s:s.nlargest(50).mean()),
    itt=("itt","mean"), gt=("gt","mean"), l4=("l4","mean"), sal=("sal","mean"),
    n30=("y",lambda s:(s>=30).mean())).reset_index()
g=g[g.n>=200]
print(f"{len(g)} slates, seasons {g.season.min()}-{g.season.max()}")
print(f"environment (slate mean DK pts): mean {g.env.mean():.2f}  sd {g.env.std():.2f}  "
      f"range {g.env.min():.1f}-{g.env.max():.1f}")
print(f"top-50 mean: {g.env_top.mean():.1f}  sd {g.env_top.std():.2f}  range {g.env_top.min():.1f}-{g.env_top.max():.1f}")
print(f"\n{'pre-lock predictor':<26}{'corr w env':>12}{'spearman':>11}{'corr w top50':>14}{'corr w P(30+)':>15}")
for c,lab in [("itt","mean implied team total"),("gt","mean game total"),
              ("l4","mean dk_points_l4"),("sal","mean salary")]:
    m=g[c].notna()&g.env.notna()
    if m.sum()<20: continue
    print(f"{lab:<26}{np.corrcoef(g[c][m],g.env[m])[0,1]:>12.3f}"
          f"{spearmanr(g[c][m],g.env[m]).statistic:>11.3f}"
          f"{np.corrcoef(g[c][m],g.env_top[m])[0,1]:>14.3f}"
          f"{np.corrcoef(g[c][m],g.n30[m])[0,1]:>15.3f}")
# how much of the swing is predictable at all? walk-forward OLS on the pre-lock predictors
from numpy.linalg import lstsq
g=g.sort_values(["season","week"]).reset_index(drop=True)
preds=["itt","gt","l4","sal"]
ok=g[preds+["env"]].notna().all(axis=1)
gg=g[ok].reset_index(drop=True)
errs_model, errs_const = [], []
for i in range(40,len(gg)):
    tr=gg.iloc[:i]; te=gg.iloc[i]
    A=np.c_[np.ones(len(tr)), tr[preds].to_numpy(dtype=float)]
    b,_,_,_=lstsq(A,tr.env.to_numpy(dtype=float),rcond=None)
    pred=float(np.r_[1, te[preds].to_numpy(dtype=float)] @ b)
    errs_model.append(abs(pred-te.env)); errs_const.append(abs(tr.env.mean()-te.env))
print(f"\nwalk-forward one-step-ahead MAE over {len(errs_model)} slates:")
print(f"  constant (predict the historical mean, ~what the simulator does): {np.mean(errs_const):.3f}")
print(f"  OLS on pre-lock predictors                                     : {np.mean(errs_model):.3f}")
imp=100*(1-np.mean(errs_model)/np.mean(errs_const))
print(f"  --> {imp:+.1f}% MAE reduction" +
      ("  PREDICTABLE" if imp>5 else "  essentially NOT predictable from these"))
