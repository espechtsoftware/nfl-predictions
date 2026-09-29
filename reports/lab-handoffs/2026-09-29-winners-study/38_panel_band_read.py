"""The same question inside the historical panel: the sampled field's lineups by projected-sum band."""
import json, glob, numpy as np, pandas as pd
B = [json.load(open(f)) for f in sorted(glob.glob("band/*.json"))]; rows = []
for b in B[0]["bands"]:
    rows.append({"band": b, "avg z": np.mean([s["bands"][b]["z"] for s in B]), "cash": np.mean([s["bands"][b]["cash"] for s in B]), "top 10%": np.mean([s["bands"][b]["top10"] for s in B]), "top 1%": np.mean([s["bands"][b]["top1"] for s in B])})
print(pd.DataFrame(rows).round(3).to_string(index=False))
print("80-95th band by ownership fifth, avg z:", [round(np.mean([s["own_in_80_95"][str(k)]["z"] for s in B]), 3) for k in range(5)])
