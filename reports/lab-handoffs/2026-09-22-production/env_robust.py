"""Is the 43.6% environment forecastability an artifact of the 2022 inactive-row break?"""
import numpy as np, pandas as pd
from numpy.linalg import lstsq
d=pd.read_parquet("ceiling_panel.parquet")
d["y"]=pd.to_numeric(d.y_dk_points,errors="coerce")
for c in ("implied_team_total","game_total","dk_points_l4","salary"): d[c]=pd.to_numeric(d[c],errors="coerce")
d["active"]=d.was_active.astype(bool)
print("inactive share by era:", d.groupby(d.season>=2022).active.apply(lambda s:round(1-s.mean(),3)).to_dict())
def run(sub, lab, extra_era=False):
    g=sub.groupby(["season","week"]).agg(n=("y","size"),env=("y","mean"),itt=("implied_team_total","mean"),
        gt=("game_total","mean"),l4=("dk_points_l4","mean"),sal=("salary","mean")).reset_index()
    g=g[g.n>=150].sort_values(["season","week"]).reset_index(drop=True)
    g["era"]=(g.season>=2022).astype(float)
    preds=["itt","gt","l4","sal"]+(["era"] if extra_era else [])
    g=g.dropna(subset=preds+["env"]).reset_index(drop=True)
    em,ec,ep=[],[],[]
    for i in range(40,len(g)):
        tr=g.iloc[:i]; te=g.iloc[i]
        A=np.c_[np.ones(len(tr)),tr[preds].to_numpy(float)]
        b=lstsq(A,tr.env.to_numpy(float),rcond=None)[0]
        em.append(abs(float(np.r_[1,te[preds].to_numpy(float)]@b)-te.env))
        ec.append(abs(tr.env.mean()-te.env))
        # fairer constant: same-era trailing mean (knows the era, nothing else)
        same=tr[tr.era==te.era]
        ep.append(abs((same.env.mean() if len(same) else tr.env.mean())-te.env))
    print(f"\n{lab}: {len(em)} slates | env mean {g.env.mean():.2f} sd {g.env.std():.2f}")
    print(f"  MAE constant (all history)   {np.mean(ec):.3f}")
    print(f"  MAE constant (same-era mean) {np.mean(ep):.3f}   <- the honest baseline")
    print(f"  MAE OLS pre-lock predictors  {np.mean(em):.3f}")
    print(f"  --> vs all-history const {100*(1-np.mean(em)/np.mean(ec)):+.1f}%   "
          f"vs same-era const {100*(1-np.mean(em)/np.mean(ep)):+.1f}%")
run(d, "ALL ROWS (my original)")
run(d[d.active], "ACTIVE ROWS ONLY (no inactive zeros)")
run(d[d.active & (d.season>=2014)], "ACTIVE ROWS, era dummy added", extra_era=True)
