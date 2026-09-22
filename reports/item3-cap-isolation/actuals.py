"""Per-player realized DK points, derived from the DK standings exports and
cross-checked candidate-by-candidate against the post-mortem receipt."""
import numpy as np, pandas as pd

D = ("/home/erich/projects/.nfl2-worktrees/ws-reply-20260921/handoffs/receipts/"
     "2026-09-21-week2-post-mortem/")
fr = pd.read_parquet("frame.parquet"); cd = pd.read_parquet("cands.parquet")
rix = np.load("roster_idx.npy")

st = pd.read_csv(D + "standings-player-ownership-fpts.csv")
fp = st.groupby("display_name").fpts.agg(["min", "max", "mean"])
amb = fp[(fp["max"] - fp["min"]).abs() > 1e-6]
print(f"players in standings: {len(fp)}; ambiguous fpts across contests: {len(amb)}")

lut = fp["mean"].to_dict()
names = fr.display_name.astype(str).tolist()
actual = np.array([lut.get(nm, np.nan) for nm in names], dtype=float)
missing = [names[i] for i in np.flatnonzero(np.isnan(actual))]
print(f"frame players with no standings row: {len(missing)}")

# players nobody rostered in the twelve captured contests get 0.0 only if they
# are absent from every export; that is the same convention the receipt used.
actual0 = np.nan_to_num(actual, nan=0.0)
realized = actual0[rix].sum(axis=1)

pr = pd.read_csv(D + "pool-realized-12555.csv").set_index("cand")
ref = pr.realized.reindex(cd.cand).to_numpy(float)
d = np.abs(realized - ref)
print(f"candidate realized vs receipt: max {d.max():.4f}, mean {d.mean():.6f}, "
      f">0.05 on {int((d > 0.05).sum())} / {len(d)} candidates")
if d.max() > 0.05:
    bad = np.argsort(-d)[:5]
    for i in bad:
        print("  cand", int(cd.cand.iloc[i]), "mine", round(realized[i], 2),
              "ref", round(ref[i], 2), "|", cd.names.iloc[i][:90])
np.save("player_actual.npy", actual0)
np.save("cand_realized.npy", ref)   # authority = the receipt
