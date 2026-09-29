"""Does re-projecting on Sunday morning add information about players who play? (2026 Weeks 1-3; Week 1 has Sunday batches only)"""
import numpy as np, pandas as pd
pd.set_option("display.width", 250)
PB = pd.read_parquet("proj_batches.parquet"); OP = pd.read_parquet("own_pts.parquet").rename(columns={"display_name": "player"})
PB = PB.rename(columns={"display_name": "player"})
rows = []
for w in (1, 2, 3):
    b = PB[PB.week == w]; ts = sorted(b.generated_at.unique())
    first, last = b[b.generated_at == ts[0]].set_index("player"), b[b.generated_at == ts[-1]].set_index("player")
    d = first[["position", "salary", "proj_points"]].rename(columns={"proj_points": "p_first"}).join(last[["proj_points"]].rename(columns={"proj_points": "p_last"}), how="inner")
    d = d.join(OP[OP.week == w].set_index("player")[["fpts", "own"]], how="left")
    d["played"] = d.fpts.notna() & (d.fpts != 0); d["fpts"] = d.fpts.fillna(0.0); d["week"] = w; d["first_batch"] = ts[0]; d["last_batch"] = ts[-1]
    rows.append(d.reset_index())
D = pd.concat(rows); D = D[D.position != "DST"]
D["chg"] = D.p_last - D.p_first; D["r_first"] = D.fpts - D.p_first; D["r_last"] = D.fpts - D.p_last
def rep(d, label):
    if len(d) < 20: return None
    r = np.corrcoef(d.chg, d.r_first)[0, 1]; n = len(d); t = r * np.sqrt((n - 2) / (1 - r * r))
    # slope: residual explained per point of change (1 = the change is fully informative, 0 = noise)
    s = np.polyfit(d.chg, d.r_first, 1)[0] if d.chg.std() > 0 else np.nan
    return {"group": label, "n": n, "mean |change|": d.chg.abs().mean(), "share changed by 1+": (d.chg.abs() >= 1).mean(), "MAE first": d.r_first.abs().mean(), "MAE last": d.r_last.abs().mean(),
            "corr(change, residual of first)": r, "t": t, "slope": s, "corr(first, actual)": np.corrcoef(d.p_first, d.fpts)[0, 1], "corr(last, actual)": np.corrcoef(d.p_last, d.fpts)[0, 1]}
out = []
for w in (1, 2, 3):
    d = D[D.week == w]
    print(f"week {w}: first batch {d.first_batch.iloc[0]} -> last batch {d.last_batch.iloc[0]}")
    for label, m in (("all skill players projected 5+ in the first batch", d.p_first >= 5), ("...who played and kept a projection (active both times)", (d.p_first >= 5) & d.played & (d.p_last >= 1)),
                     ("...active, and the projection moved by 1+ point", (d.p_first >= 5) & d.played & (d.p_last >= 1) & (d.chg.abs() >= 1))):
        r = rep(d[m], label)
        if r: r["week"] = w; out.append(r)
R = pd.DataFrame(out).set_index(["week", "group"]); print(R.round(3).to_string())
a = D[(D.week.isin([2, 3])) & (D.p_first >= 5) & D.played & (D.p_last >= 1)]
print("\nWeeks 2-3 pooled, active players: ", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in rep(a, "pooled").items()})
print("\nlargest Saturday -> Sunday moves among active players, Week 3:")
x = D[(D.week == 3) & D.played & (D.p_first >= 5)].assign(a=lambda z: z.chg.abs()).nlargest(14, "a")[["player", "position", "salary", "p_first", "p_last", "chg", "fpts", "own"]]
print(x.round(2).to_string(index=False))
D.to_parquet("sat_sun.parquet")
