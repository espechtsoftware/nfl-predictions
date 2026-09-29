"""What our pre-lock projection is worth on the real 2026 Millionaire fields: every entry by its projected-sum percentile."""
import os, numpy as np, pandas as pd
pd.set_option("display.width", 220)
F = pd.read_parquet(os.environ["FIELD_INPUT"]); E = pd.read_parquet("entries_paid.parquet")[["week", "entry_id", "points", "prize", "fee", "pct"]]
F = F.merge(E, on=["week", "entry_id"]); F["z"] = F.groupby("week").points.transform(lambda x: (x - x.mean()) / x.std())
F["band"] = pd.cut(F.proj_pct, [0, .2, .4, .6, .8, .9, .95, .98, .99, .995, 1.0])
g = F[F.week.isin([1, 3])].groupby("band", observed=True).agg(entries=("z", "size"), avg_z=("z", "mean"), cash=("prize", lambda x: (x > 0).mean()), top10=("pct", lambda x: (x <= .1).mean()), top1=("top1", "mean"))
print("weeks 1 and 3 pooled"); print(g.round(3).to_string())
print(F.groupby(["band", "week"], observed=True).z.mean().unstack().round(3).to_string())
h = F[F.week.isin([1, 3]) & (F.proj_pct >= .8) & (F.proj_pct < .95)].copy(); h["own_band"] = pd.qcut(h.own_pct, 5, labels=["least owned", "2", "3", "4", "most owned"])
print(h.groupby("own_band", observed=True).agg(entries=("z", "size"), avg_z=("z", "mean"), cash=("prize", lambda x: (x > 0).mean()), top1=("top1", "mean")).round(3).to_string())
