import os, numpy as np, pandas as pd
os.environ["RULE"] = "prod"
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sleeve_reach.py")).read()
src = src.replace('''    for lab, msk in (("field"''', '''    house = ((g["stack"] >= 2) & (g.bringback >= 1) & (g.salary >= 49000)).to_numpy()
    relaxed = ((g["stack"] >= 1) & (g.salary >= 49000)).to_numpy()
    cap4 = (g.max_game <= 4).to_numpy()
    for lab, msk in (("field", np.ones(len(g), bool)), ("top 1%", g.pct.to_numpy() <= 0.01), ("top 0.1%", g.pct.to_numpy() <= 0.001), ("top 100", g["rank"].to_numpy() <= 100)):
        print(f"   {lab:<9} house-legal & cap4 {100*(house&cap4)[msk].mean():5.1f}%  | L2 & house & cap4 {100*(L2&house&cap4)[msk].mean():5.1f}%  | L2 & QB+1 relaxed & cap4 {100*(L2&relaxed&cap4)[msk].mean():5.1f}%  | L1 & relaxed & cap4 {100*(L1&relaxed&cap4)[msk].mean():5.1f}%")
    for lab, msk in (("zzz"''')
exec(src)
