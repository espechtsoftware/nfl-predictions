import pandas as pd, numpy as np, warnings
from scipy import stats
warnings.filterwarnings("ignore")
sk=pd.read_parquet("ls_skill_analysis.parquet")
d=sk.dropna(subset=["prev_surprise"]).copy()           # all main-slate skill rows with a prior week (played or not)
d["lo_act"]=np.log(d.own_act+0.1); d["lo_proj"]=np.log(d.own_proj+0.1)
d["top"]=d.groupby(["season","week"]).own_act.transform(lambda s: s>=s.quantile(0.9)).astype(int)
def feats(g, with_rec):
    cols=[np.ones(len(g)), g.lo_proj.values]
    if with_rec: cols += [g.prev_surprise.values, np.clip(g.prev_surprise.values,0,None)]
    return np.column_stack(cols)
res=[]
for test in [2023,2024,2025]:
    tr=d[d.season<test]; te=d[d.season==test]
    # demean within slate so the fit is a within-slate relation
    for with_rec in (False,True):
        Xtr=feats(tr,with_rec); b,*_=np.linalg.lstsq(Xtr,tr.lo_act.values,rcond=None)
        pred=feats(te,with_rec)@b; te=te.assign(pred=pred)
        rho=np.mean([stats.spearmanr(g.pred,g.lo_act)[0] for _,g in te.groupby(["season","week"])])
        mae=np.mean([np.abs(np.exp(g.pred)-np.exp(g.lo_act)).mean() for _,g in te.groupby(["season","week"])])
        # error on last week's boomers
        bm=te[te.prev_surprise>=8]; bias_boom=(np.exp(bm.pred)-np.exp(bm.lo_act)).mean()
        res.append((test,"LineStar proj-own + recency" if with_rec else "LineStar proj-own only",round(rho,4),round(mae,3),round(bias_boom,2), np.round(b,3).tolist()))
print(pd.DataFrame(res,columns=["test season","model","within-slate Spearman","MAE (own %)","bias on last-week boomers (pp)","coefs"]).to_string(index=False))
