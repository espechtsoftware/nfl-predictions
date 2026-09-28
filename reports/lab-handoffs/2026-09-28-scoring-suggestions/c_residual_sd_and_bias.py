"""Residual SD and mean by position x projection band, and mean residual by salary tier (played only)."""
import pandas as pd
df = pd.read_parquet("ls_main.parquet")
pl = df[df.pos.isin(["QB", "RB", "WR", "TE"]) & (df.pp >= 4)].copy(); pl["res"] = pl.ps - pl.pp
pl["band"] = pd.cut(pl.pp, [4, 8, 12, 16, 20, 40], right=False)
print(pl.groupby(["pos", "band"], observed=True).res.agg(["std", "mean", "size"]).round(2).to_string())
pl["tier"] = pd.cut(pl.sal, [0, 3999, 4999, 5999, 6999, 7999, 12000], labels=["<4k", "4-5k", "5-6k", "6-7k", "7-8k", "8k+"])
print(pl[pl.ps > 0].groupby(["pos", "tier"], observed=True).res.agg(["mean", "size"]).round(2).unstack(0).to_string())
