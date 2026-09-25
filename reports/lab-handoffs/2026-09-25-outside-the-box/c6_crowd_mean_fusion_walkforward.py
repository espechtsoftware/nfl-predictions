import pandas as pd, numpy as np, warnings
from scipy import stats
warnings.filterwarnings("ignore")
sk=pd.read_parquet("ls_skill_analysis.parquet")
d=sk[sk.played].copy()
d["prev_surprise"]=d.prev_surprise.fillna(0.0)
# pre-lock only: PP, excess projected ownership (e_proj, computed within slate from pre-lock quantities), last-week surprise
def fit_apply(tr,te,cols):
    X=lambda g: np.column_stack([np.ones(len(g))]+[g[c].values for c in cols])
    b,*_=np.linalg.lstsq(X(tr),(tr.ps-tr.pp).values,rcond=None)
    return te.pp.values+X(te)@b, b
rows=[]
for test in [2023,2024,2025]:
    tr=d[d.season<test]; te=d[d.season==test].copy()
    base_mae=np.abs(te.ps-te.pp).mean(); base_r=np.mean([stats.pearsonr(g.pp,g.ps)[0] for _,g in te.groupby("week")])
    for name,cols in [("PP + excess projected own",["e_proj"]),("PP + excess projected own + last-week surprise",["e_proj","prev_surprise"])]:
        pred,b=fit_apply(tr,te,cols); te["pred"]=pred
        mae=np.abs(te.ps-te.pred).mean(); r=np.mean([stats.pearsonr(g.pred,g.ps)[0] for _,g in te.groupby("week")])
        rows.append((test,name,round(base_mae,3),round(mae,3),round(base_r,4),round(r,4),np.round(b,3).tolist()))
print(pd.DataFrame(rows,columns=["test","model","MAE PP","MAE fused","r PP","r fused","coef"]).to_string(index=False))
