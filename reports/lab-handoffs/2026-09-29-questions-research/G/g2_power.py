"""G2: paired book-mean differences between selectors on the SAME pool, per slate-bank, from the L-series result files.
The per-slate-bank SD of (mean_A - mean_B) is the noise a live paired comparison faces each week; the MDD over n weeks
at 80% power, two-sided alpha 0.05, is (1.96+0.84)*sd/sqrt(n) (large-n normal approx; for n=1,3 a t-based number is also shown).
Single-threaded pandas on 72-row frames."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
RES = Path(sys.argv[1])
def load(d):
    rows=[json.loads(l)["result"] for f in sorted(glob.glob(str(RES/d/"results_bank*.jsonl"))) for l in open(f) if "result" in json.loads(l)]
    return pd.DataFrame(rows).drop_duplicates(["bank","season","week"],keep="last")
pairs=[("l13","PMO_X50_mean","MEAN_mean"),("l13","PMO_mean","MEAN_mean"),("l13","MEAN_mean","EMAX_mean"),
       ("l17","X67_mean","X50_mean"),("l17","X100_mean","X50_mean"),("l18","X40_mean","X50_mean"),("l18","X25_mean","X50_mean"),
       ("l09","K144_MEAN_mean","K144_EMAX_mean"),("l09","K144_PLF89_mean","K144_MEAN_mean"),("l11","MEAN_mean_swap","MEAN_mean_keep"),
       ("l12","T10_mean","MEAN_mean"),("l14","EMPP99_mean","MEAN_mean")]
print(f"{'pair':40s} {'mean d':>8s} {'sd d':>7s} {'sd A':>7s} {'sd B':>7s} {'corr':>6s} | MDD80 n=1 (t) n=3 (t) n=6 (t) | n for d=5 | n for d=10")
for d,a,b in pairs:
    df=load(d); x=df[a]-df[b]; sd=x.std(); n=len(x)
    # t-based MDD for small n at alpha .05 two-sided, power .8 -- solve via noncentral t approx: use z-approx and t-approx
    def mdd(nw):
        if nw<2: return float('nan')
        tcrit=stats.t.ppf(0.975,nw-1); tpow=stats.t.ppf(0.8,nw-1)
        return (tcrit+tpow)*sd/np.sqrt(nw)
    z=(1.96+0.8416)
    print(f"{d+' '+a+'-'+b:40s} {x.mean():8.2f} {sd:7.2f} {df[a].std():7.2f} {df[b].std():7.2f} {np.corrcoef(df[a],df[b])[0,1]:6.2f} | {z*sd:6.1f}       {mdd(3):6.1f} {mdd(6):6.1f}  | {(z*sd/5)**2:5.1f}    | {(z*sd/10)**2:5.1f}")
# also the per-slate-bank SD of the book mean itself (level noise a single-arm week carries)
for d,c in [("l13","MEAN_mean"),("l17","X50_mean"),("l18","X50_mean")]:
    df=load(d); print(d,c,"book-mean level: mean",round(df[c].mean(),1),"sd across slate-banks",round(df[c].std(),1))
