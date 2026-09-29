"""C5: duplication in the three 2026 Millionaires. Input: distinct lineups (duplicate_key) with copies, best rank,
points, realized-ownership sum (Millionaire, post-settlement), counts under 5% / at 20%+, ours flag."""
import numpy as np, pandas as pd
S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/72305fd0-5efb-4d88-a744-a668e10ec3e9/scratchpad/q/C"
L = pd.read_csv(f"{S}/milly_lineups_2026.csv")
lines = {1: {"cash": None, "top100": None, "top1000": None}, 2: {}, 3: {}}
for w, g in L.groupby("week"):
    n_entries = g.copies.sum(); n_distinct = len(g)
    ent = g.loc[g.index.repeat(g.copies)]  # entry-level view
    uniq_share = (g.copies == 1).sum() / n_entries
    print(f"\n=== Week {w}: entries {n_entries:,}, distinct lineups {n_distinct:,}, entries that are unique {uniq_share:.1%}, entries sharing a lineup {(1-uniq_share):.1%}, max copies {g.copies.max()}")
    for band, r in [("top 10", 10), ("top 100", 100), ("top 1000", 1000)]:
        gb = g[g.best_rank <= r]
        n_ent = ent[ent.best_rank <= r]
        print(f"  {band}: distinct lineups with best rank<= {r}: {len(gb)}; duplicated among them {(gb.copies>1).sum()} (copies {sorted(gb.copies[gb.copies>1].tolist())}); entries in band that are duplicated {(n_ent.copies>1).sum()}")
    ours = g[g.ours]
    print(f"  ours: {len(ours)} distinct lineups, {ours.copies.sum()} entries incl. copies by others; duplicated {(ours.copies>1).sum()}: copies {ours.copies[ours.copies>1].tolist()}, best ranks {ours.best_rank[ours.copies>1].tolist()}; ours own_sum mean {ours.own_sum.mean():.0f} vs field {ent.own_sum.mean():.0f}")
    # duplicates by ownership sum decile (entry-weighted deciles)
    ent = ent.copy(); ent["dec"] = pd.qcut(ent.own_sum, 10, labels=False, duplicates="drop") + 1
    tab = ent.groupby("dec").agg(entries=("copies","size"), own_sum_lo=("own_sum","min"), own_sum_hi=("own_sum","max"), share_duplicated=("copies", lambda x: (x>1).mean()), mean_copies=("copies","mean"), max_copies=("copies","max"), mean_points=("points","mean"), n_under5=("n_under5","mean"))
    print("  by realized-ownership-sum decile (entry-weighted):"); print(tab.round(2).to_string())
    tab2 = ent.groupby("n_under5").agg(entries=("copies","size"), share_duplicated=("copies", lambda x: (x>1).mean()), mean_copies=("copies","mean"), mean_points=("points","mean")); print("  by # players under 5% owned:"); print(tab2.round(3).to_string())
    # score bands: how often is a lineup at each line duplicated -> expected prize split
    for lab, q in [("cash (top 23%)", 0.23), ("top 1%", 0.01), ("top 0.1%", 0.001)]:
        thr = ent.points.quantile(1-q); gb = ent[ent.points >= thr]
        print(f"  entries at/above {lab} line {thr:.1f}: n {len(gb)}, duplicated {(gb.copies>1).mean():.1%}, mean copies {gb.copies.mean():.2f} -> expected prize share per entry at that line {(1/gb.copies).mean():.3f}")
    pu = g[g.copies>1].own_sum.quantile([.1,.5,.9]).round(0).tolist(); ps = g[g.copies==1].own_sum.quantile([.1,.5,.9]).round(0).tolist()
    print(f"  own_sum p10/p50/p90: duplicated lineups {pu} vs unique {ps}")
