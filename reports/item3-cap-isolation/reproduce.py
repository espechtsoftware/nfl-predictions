"""Gate: does the archived-sidecar rebuild reproduce the DELIVERED 97-lineup book?

If it does not, no capped arm computed from these matrices can claim to isolate
the cap, and the whole study stops here.
"""
import numpy as np, pandas as pd, time
from emax import emax_select

T = np.load("T_inc.npy"); Tv = np.load("T_hs.npy")
cd = pd.read_parquet("cands.parquet")

delivered = cd.loc[cd.book_rank.notna()].sort_values("book_rank").index.to_numpy()
print("delivered book:", len(delivered))

t0 = time.time()
book, _ = emax_select(T, Tv, 97, verbose=True)
print(f"reproduced in {time.time()-t0:.1f}s")

book = np.array(book)
print("exact order match:", bool((book == delivered).all()))
print("set match:", set(book.tolist()) == set(delivered.tolist()))
if not (book == delivered).all():
    first = int(np.argmax(book != delivered))
    print("first divergence at rank", first + 1, "got", book[first], "want", delivered[first])
    print("overlap:", len(set(book.tolist()) & set(delivered.tolist())), "/ 97")
np.save("book_delivered.npy", delivered)
np.save("book_repro.npy", book)
