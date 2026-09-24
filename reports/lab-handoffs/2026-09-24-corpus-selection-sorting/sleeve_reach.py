"""Does the sleeve's pre-lock region (predicted ownership) contain the real top finishers? 2026 W1/W2 Millionaires."""
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats
import sys, os; sys.path.insert(0, os.environ["WIN_SCRIPTS"])
from feat import MILLY, ownership
P = pd.read_parquet(__import__("os").environ["TESTBED"] + "/players_bed.parquet")
tr = P[P.own_act.notna() & P.salary.notna()]
F = ["pos_c", "salary", "mean_projection", "value", "proj_rank", "value_rank", "sal_rank", "value_z", "implied_team_total", "proj_p90"]
m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=40, verbose=-1).fit(tr[F], np.log(tr.own_act + 0.1))
p90 = pd.read_csv("p90_2026.csv")
f = pd.read_parquet("lineups.parquet"); pool = pd.read_parquet("pool_w2.parquet")
for w in (1, 2):
    pl = pd.read_parquet(f"players_w{w}.parquet")
    pl = pl.merge(p90[p90.week == w][["display_name", "proj_p90"]], on="display_name", how="left")
    pl["mean_projection"] = pl.proj_points
    pl["value"] = pl.mean_projection / (pl.salary / 1000); g = pl.groupby("position")
    pl["proj_rank"] = g.mean_projection.rank(ascending=False); pl["value_rank"] = g.value.rank(ascending=False)
    pl["sal_rank"] = g.salary.rank(ascending=False); pl["value_z"] = (pl.value - g.value.transform("mean")) / g.value.transform("std")
    pl["pos_c"] = pl.pos_code; pl["implied_team_total"] = pl.team_total
    pl["pred"] = np.exp(m.predict(pl[F])) - 0.1
    pl.loc[pl.proj_points.isna() & (pl.position != "DST"), "pred"] = 0.0     # unprojected fringe
    act = ownership(MILLY[w]); pl["act"] = pl.display_name.map(act).fillna(0)
    print(f"W{w}: Spearman(pred, actual) {stats.spearmanr(pl.pred, pl.act).correlation:.3f}")
    sk = (pl.position != "DST").to_numpy()
    n_sk = int(sk.sum()); n_act = int(((pl.act >= 5) & sk).sum())
    import os
    rule = os.environ.get("RULE", "prod")
    n_hi = int(round(0.101 * n_sk)) if rule == "prod" else n_act
    print(f"   rule {rule}: non-LOW = top {n_hi} of {n_sk} skill players by predicted ownership (actual >=5%: {n_act})")
    rk_sk = pl.pred.where(sk).rank(ascending=False, method="first")
    low = (sk & (rk_sk > n_hi)).to_numpy()
    print(f"   LOW set precision (share truly under 5%): {(pl.act[low] < 5).mean():.3f}; actual-under-5% skill players labelled LOW: {low[(pl.act < 5).to_numpy() & sk].mean():.3f}")
    chalk = (pl.pred.rank(ascending=False, method="first") <= 15).to_numpy()
    L = np.load(f"L_{MILLY[w]}.npy")
    g = f[f.contest_id == MILLY[w]].reset_index(drop=True)
    nlow = low[L].sum(axis=1); nch = chalk[L].sum(axis=1); sal = g.salary.to_numpy()
    L1 = (nlow <= 1) & (nch >= 1) & (sal >= 49500); L2 = (nlow <= 2) & (nch >= 1) & (sal >= 49500)
    for lab, msk in (("field", np.ones(len(g), bool)), ("top 1%", g.pct.to_numpy() <= 0.01), ("top 0.1%", g.pct.to_numpy() <= 0.001), ("top 100", g["rank"].to_numpy() <= 100)):
        print(f"   {lab:<9} inside L1 region {100*L1[msk].mean():5.1f}%   inside L2 region {100*L2[msk].mean():5.1f}%   mean predicted LOW {nlow[msk].mean():.2f}")
    if w == 2:
        RUN = __import__("os").environ["W2_RUN"]      # archived Week-2 D12800 run dir
        fr = pd.read_parquet(f"{RUN}/frame.parquet"); c = pd.read_parquet(f"{RUN}/candidates.parquet")
        name_of = dict(zip(fr.id.astype(str), fr.display_name.astype(str).str.strip())); idx = {n: i for i, n in enumerate(pl.display_name)}
        LP = np.array([[idx.get(name_of[p], 0) for p in s.split(",")] for s in c.players.astype(str)])
        nl = low[LP].sum(axis=1); nc = chalk[LP].sum(axis=1); sp = pl.salary.to_numpy()[LP].sum(axis=1)
        print(f"   our pool  inside L1 region {100*((nl<=1)&(nc>=1)&(sp>=49500)).mean():5.1f}%   inside L2 region {100*((nl<=2)&(nc>=1)&(sp>=49500)).mean():5.1f}%   mean predicted LOW {nl.mean():.2f}")
