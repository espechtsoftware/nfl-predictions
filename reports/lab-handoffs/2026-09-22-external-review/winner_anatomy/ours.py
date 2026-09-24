import numpy as np, pandas as pd
from feat import *
RUN = __import__("os").environ["W2_RUN"]          # archived Week-2 D12800 run dir
pl = pd.read_parquet("players_w2.parquet")
fr = pd.read_parquet(f"{RUN}/frame.parquet"); c = pd.read_parquet(f"{RUN}/candidates.parquet")
name_of = dict(zip(fr.id.astype(str), fr.display_name.astype(str).str.strip()))
idx = {n: i for i, n in enumerate(pl.display_name)}
L = np.array([[idx.get(name_of[p], -1) for p in s.split(",")] for s in c.players.astype(str)])
print("pool unmatched rows", (L < 0).any(axis=1).sum())
own = ownership(MILLY[2])
f = features(L, pl, own)
f["tag"] = c.tag.to_numpy(); f["book"] = c.book_rank.notna().to_numpy()
f.to_parquet("pool_w2.parquet")
