import re, numpy as np, pandas as pd
from scipy import stats
from feat import ownership, MILLY
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
pl = pd.read_parquet("players_w1.parquet"); pl["key"] = pl.display_name.map(norm)
sh = pd.read_csv("own_shadow_w1.csv"); sh["key"] = sh.name.map(norm)
pm = sh.groupby("key").pred_own.max() * 100
pl["pown"] = pl.key.map(pm)
act = ownership(MILLY[1]); pl["aown"] = pl.display_name.map(act).fillna(0)
m = pl.pown.notna()
print(f"own_shadow coverage {m.mean():.2f}; Spearman(pred, actual) {stats.spearmanr(pl.pown[m], pl.aown[m]).correlation:.3f}; mass {pl.pown.sum():.0f}%")
pl["pown"] = pl.pown.fillna(0)
f = pd.read_parquet("lineups.parquet"); g = f[f.contest_id == MILLY[1]].copy()
L = np.load(f"L_{MILLY[1]}.npy")
skill = (pl.position != "DST").to_numpy()[L]
for col, lab in (("pown", "pre-lock own_shadow"), ("aown", "actual")):
    v = pl[col].to_numpy()[L]
    g["x"] = ((v < 5) & skill).sum(axis=1)
    b = pd.cut(g.x, [-1, 1, 2, 9], labels=["0-1", "2", "3+"])
    base = b.value_counts(normalize=True)
    print(f"\n{lab}: # skill players under 5%  field share / lift top1% / top0.1%")
    for k in ["0-1", "2", "3+"]:
        print(f"  {k:>4}: {100*base[k]:5.1f}%  {b[g.pct<=0.01].value_counts(normalize=True)[k]/base[k]:.2f}  {b[g.pct<=0.001].value_counts(normalize=True)[k]/base[k]:.2f}")
    ours = b[g.ours].value_counts(normalize=True).reindex(["0-1","2","3+"]).fillna(0)
    print("  our entered W1 Milly rows:", (100*ours).round(1).to_dict())
