# PRO METHODS, analysis A2 (W4): (1) is the per-user FP-vs-props lean real (split-half reliability across users)?
# (2) disagreement players: when FP and props disagree, whose side do the regulars / leaders / field take?
# (3) WHEN: segments (position, price, chalk, game total, disagreement) -- how much a market projection explains the
# regulars' tilt there and which source they lean on. PRIVATE.
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path.home() / "private" / "pro-methods"
exec(open(OUT / "a_fp_alignment.py").read().split("SRC = [")[0])   # reuses d, pc, edge(), fit()
ux = pd.read_parquet(OUT / "user_exposure.parquet"); ur = pd.read_parquet(OUT / "user_results.parquet")
uxw = ux[ux.week == 4].pivot_table(index="key", columns="u", values="share", fill_value=0.0)
regs = ur[(ur.week == 4) & ur.is_reg].u.tolist()
SRC = ["e_fp", "e_props", "e_model"]

# (1) split-half reliability of b_fp - b_props across the 117 regulars
rng = np.random.default_rng(7)
rel = []
for rep in range(200):
    half = rng.permutation(len(pc)) < len(pc) // 2
    a, b = [], []
    for u in regs:
        y = ((pc.key.map(uxw[u]).fillna(0.0) - pc.exp_rest) * 100).values
        ba, _, _ = fit(y[half], pc[SRC].values[half]); bb, _, _ = fit(y[~half], pc[SRC].values[~half])
        a.append(ba[0] - ba[1]); b.append(bb[0] - bb[1])
    rel.append(np.corrcoef(a, b)[0, 1])
r = np.mean(rel)
print(f"(1) split-half reliability of each regular's (b_fp - b_props): r {r:.2f} (Spearman-Brown full-length {2*r/(1+r):.2f}); 200 random splits")
# the same for the general projection weight (b_fp + b_props) and for b_model
for nm, f in (("b_fp + b_props (any market projection)", lambda x: x[0] + x[1]), ("b_model (our model)", lambda x: x[2])):
    rr = []
    for rep in range(100):
        half = rng.permutation(len(pc)) < len(pc) // 2
        a, b = [], []
        for u in regs:
            y = ((pc.key.map(uxw[u]).fillna(0.0) - pc.exp_rest) * 100).values
            a.append(f(fit(y[half], pc[SRC].values[half])[0])); b.append(f(fit(y[~half], pc[SRC].values[~half])[0]))
        rr.append(np.corrcoef(a, b)[0, 1])
    print(f"    split-half reliability of {nm}: r {np.mean(rr):.2f}")

# (2) disagreement players
pc["dis"] = pc.e_fp - pc.e_props
big = pc[pc.dis.abs() >= pc.dis.abs().quantile(0.67)].copy()
print(f"\n(2) the third of prop-covered players where FP and props disagree most (n {len(big)}): tilt per 1 sd of (FP edge - props edge)")
for name, col in (("regulars pooled", "exp_reg"), ("top 1% lineups", "exp_top1"), ("top 0.1% lineups", "exp_top01")):
    y = ((big[col] - big.exp_rest) * 100).values
    b, se, r2 = fit(y, np.column_stack([big.dis.values, ((big.e_fp + big.e_props) / 2).values]))
    print(f"    {name:18s} side-with-FP slope {b[0]:+.2f} pp (se {se[0]:.2f})  [market level {b[1]:+.2f}]")
y = np.log(big.field_own.clip(lower=1e-3)).values
b, se, _ = fit(y, np.column_stack([big.dis.values, ((big.e_fp + big.e_props) / 2).values]))
print(f"    {'field log-own':18s} side-with-FP slope {b[0]:+.3f} (se {se[0]:.3f})")
# per regular: the share siding with FP on the disagreement set
side = []
for u in regs:
    y = ((big.key.map(uxw[u]).fillna(0.0) - big.exp_rest) * 100).values
    b, se, _ = fit(y, np.column_stack([big.dis.values, ((big.e_fp + big.e_props) / 2).values]))
    side.append((b[0], se[0]))
side = np.array(side)
print(f"    regulars individually: side with FP (slope > 0) {np.mean(side[:,0] > 0):.0%}; significantly FP (t > 2) "
      f"{np.mean(side[:,0]/side[:,1] > 2):.0%}; significantly props (t < -2) {np.mean(side[:,0]/side[:,1] < -2):.0%}")
# realized: on disagreement players, whose number was closer to the actual?
ok = big.actual.notna()
print(f"    on these players, mean |actual - FP| {np.mean(np.abs(big.actual[ok]-big.fp[ok])):.2f} vs |actual - props| "
      f"{np.mean(np.abs(big.actual[ok]-big.props[ok])):.2f} (n {ok.sum()}); corr(actual - props, FP - props) "
      f"{np.corrcoef(big.actual[ok]-big.props[ok], big.fp[ok]-big.props[ok])[0,1]:+.2f}")

# (3) WHEN: segments, regulars pooled, on the whole W4 pool with FP (props not required); R2 of FP edge alone
dd = d[d.fp.notna()].copy()
dd["tier"] = pd.cut(dd.salary, [0, 4000, 5500, 7000, 20000], labels=["<$4k", "$4-5.5k", "$5.5-7k", "$7k+"])
dd["chalk"] = pd.cut(dd.fp_own, [-1, 0.05, 0.15, 2], labels=["<5% proj own", "5-15%", "15%+"])
gt = dd.groupby("game").game_total.transform("max")
dd["env"] = np.where(gt >= gt.quantile(0.67), "top-third game totals", np.where(gt <= gt.quantile(0.33), "bottom-third totals", "middle totals"))
dd["y_reg"] = (dd.exp_reg - dd.exp_rest) * 100
dd["y_top1"] = (dd.exp_top1 - dd.exp_rest) * 100
print("\n(3) WHEN (W4, regulars pooled): tilt per 1 sd of FP edge, and how much of the tilt FP's edge explains")
def seg(col):
    out = []
    for k, g in dd.groupby(col, observed=True):
        if len(g) < 12:
            continue
        b, se, r2 = fit(g.y_reg.values, g[["e_fp"]].values)
        gp = g[g.e_props.notna()]
        bp = fit(gp.y_reg.values, gp[["e_fp", "e_props"]].values)[0] if len(gp) >= 12 else [np.nan, np.nan]
        out.append({"segment": f"{col}={k}", "n": len(g), "b_fp_alone": round(b[0], 2), "se": round(se[0], 2), "R2_fp": round(r2, 2),
                    "joint_b_fp": round(bp[0], 2), "joint_b_props": round(bp[1], 2), "mean_abs_tilt": round(g.y_reg.abs().mean(), 2)})
    return out
S = pd.DataFrame(seg("pos") + seg("tier") + seg("chalk") + seg("env"))
print(S.to_string(index=False))
S.to_csv(OUT / "a2_segments_w4.csv", index=False)
