import numpy as np, pandas as pd, json
T=np.load("T_inc.npy"); Tv=np.load("T_hs.npy"); rix=np.load("roster_idx.npy")
realized=np.load("cand_realized.npy"); pa=np.load("player_actual.npy")
fr=pd.read_parquet("frame.parquet"); cd=pd.read_parquet("cands.parquet")
books=json.load(open("books.json")); K=97

print("pool oracle (best realized of 12,555):", round(float(realized.max()),2),
      "| pool rows >=194:", int((realized>=194).sum()), "| >=150:", int((realized>=150).sum()))

base=np.array(books["dual_emax|none"]); cap25=np.array(books["dual_emax|25%"])
prop=np.array(books["dual_emax|proposal"])
print("overlap delivered vs 25% cap:", len(set(base.tolist())&set(cap25.tolist())), "/97")
print("overlap delivered vs proposal:", len(set(base.tolist())&set(prop.tolist())), "/97")

top=int(np.argmax(realized))
pos_in=lambda b,i: (int(np.where(b==i)[0][0])+1) if i in b else None
print(f"\nbest realized lineup cand={int(cd.cand.iloc[top])} score={realized[top]:.2f}")
print("  in delivered book at rank:", pos_in(base,top), "| in 25% cap book at rank:", pos_in(cap25,top))
print("  ", cd.names.iloc[top])

def exp_tbl(b):
    c=np.zeros(len(fr),dtype=int); np.add.at(c,rix[b],1); return c
cb,cc=exp_tbl(base),exp_tbl(cap25)
d=pd.DataFrame(dict(player=fr.display_name.astype(str), pos=fr.position.astype(str),
                    delivered=cb, cap25=cc, pts=pa))
d["delta"]=d.cap25-d.delivered
d["contrib"]=d.delta*d.pts/K
d=d[(d.delivered>0)|(d.cap25>0)].sort_values("contrib")
print("\nlargest NEGATIVE contributors to the mean change (exposure cut x points):")
print(d.head(8).to_string(index=False))
print("\nlargest POSITIVE contributors:")
print(d.tail(10).to_string(index=False))
print(f"\nsum of contributions = {d.contrib.sum():.2f} (= realized mean delta "
      f"{realized[cap25].mean()-realized[base].mean():.2f})")
