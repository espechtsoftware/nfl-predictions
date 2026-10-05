"""F2 (PRELIMINARY): portfolio anatomy of top-100 user-weeks with >=20 Millionaire entries vs matched mid-field user-weeks.
Cores = greedy clusters: a row joins the first existing core whose SEED row shares >=6 of 9 players; else it seeds a new core."""
import os
import pandas as pd, numpy as np, itertools
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60); pd.set_option('display.max_rows', 300)
N = {1: 831028, 2: 172692, 3: 161682}
df = pd.read_csv('portfolios.csv')
df['wk'] = df.week
df['slots'] = df.lineup.map(lambda s: [x.split('=', 1) for x in s.split('|')])
df['pset'] = df.slots.map(lambda L: frozenset(p for _, p in L))
GROUPS = {'QB': ['QB'], 'RB': ['RB'], 'WR': ['WR'], 'TE': ['TE'], 'FLEX': ['FLEX'], 'DST': ['DST']}
def anatomy(g):
    n = len(g); w = int(g.wk.iloc[0])
    cnt = pd.Series([p for s in g.pset for p in s]).value_counts() / n
    top = cnt.values
    sets = list(g.sort_values('rank').pset)
    # cores (greedy, seed-based)
    seeds = []; assign = []
    for s in sets:
        for i, sd in enumerate(seeds):
            if len(s & sd) >= 6: assign.append(i); break
        else: seeds.append(s); assign.append(len(seeds) - 1)
    sizes = pd.Series(assign).value_counts().values
    # pairwise overlap on up to 150 rows
    pairs = [len(a & b) for a, b in itertools.combinations(sets[:150], 2)]
    # per-slot variation: distinct players used in the slot group and share of rows carrying the group's modal player(s)
    slot = {}
    for grp in GROUPS:
        per_row = [[p for sl, p in L if sl == grp] for L in g.slots]
        k = len(per_row[0]) if per_row and per_row[0] else 1
        c = pd.Series([p for r in per_row for p in r]).value_counts()
        slot[f'{grp}_distinct'] = len(c)
        slot[f'{grp}_modal_share'] = round(c.head(k).sum() / (n * k), 3) if len(c) else np.nan
    cash = (g['rank'] <= 0.2 * N[w]).mean()
    return pd.Series(dict(n=n, mean_pts=g.points.mean(), cash_share=cash, best_rank=g['rank'].min(), top1pct_share=(g['rank'] <= 0.01 * N[w]).mean(),
                          exp_top1=top[0], exp_top3=top[:3].mean(), exp_top5=top[:5].mean(), n_players=len(cnt), n_ge50=(cnt >= .5).sum(), n_ge25=(cnt >= .25).sum(),
                          n_qb=slot['QB_distinct'], n_cores=len(seeds), core1_share=sizes[0] / n, cores_ge5=(sizes >= 5).sum(), mean_overlap=np.mean(pairs), overlap_ge6=np.mean(np.array(pairs) >= 6),
                          unique_share=(g.n_same == 1).mean(), dup_field_mean=g.n_same.mean(), **slot))
A = df.groupby(['week', 'grp', 'user']).apply(anatomy, include_groups=False).reset_index()
A.to_csv('f2_anatomy_all.csv', index=False)
top = A[A.grp == 'top100']; mid = A[A.grp == 'mid']
# match: for each top user-week, nearest-n mid user-week same week, without replacement
used = set(); rows = []
for _, r in top.sort_values('n', ascending=False).iterrows():
    c = mid[(mid.week == r.week) & (~mid.index.isin(used))]
    j = (c.n - r.n).abs().idxmin(); used.add(j); rows.append(j)
M = mid.loc[rows]
cols = ['n', 'mean_pts', 'cash_share', 'top1pct_share', 'exp_top1', 'exp_top3', 'exp_top5', 'n_players', 'n_ge50', 'n_ge25', 'n_qb', 'n_cores', 'core1_share', 'cores_ge5', 'mean_overlap', 'overlap_ge6', 'unique_share', 'dup_field_mean']
scols = [c for c in A.columns if c.endswith('_distinct') or c.endswith('_modal_share')]
print('== user-weeks: top100 (>=20 entries, best rank <=100)', len(top), ' matched mid (mean pct 35-65, best rank >1000)', len(M))
for w in (1, 2, 3):
    t = top[top.week == w]; m = M[M.week == w]
    print(f'\n-- W{w}: top100 n={len(t)} vs matched mid n={len(m)} (means; medians for n)')
    print(pd.DataFrame({'top100': t[cols].mean(), 'mid': m[cols].mean()}).T.round(3).to_string())
    print(pd.DataFrame({'top100': t[scols].mean(), 'mid': m[scols].mean()}).T.round(3).to_string())
print('\n-- POOLED all weeks')
print(pd.DataFrame({'top100': top[cols].mean(), 'mid': M[cols].mean(), 'top100_median': top[cols].median(), 'mid_median': M[cols].median()}).T.round(3).to_string())
print(pd.DataFrame({'top100': top[scols].mean(), 'mid': M[scols].mean()}).T.round(3).to_string())
# by entry-count bucket, pooled
for lab, lo, hi in [('20-49', 20, 49), ('50-149', 50, 149), ('150', 150, 150)]:
    t = top[(top.n >= lo) & (top.n <= hi)]; m = M[(M.n >= lo) & (M.n <= hi)]
    print(f'\n-- bucket {lab}: top100 n={len(t)} mid n={len(m)}')
    print(pd.DataFrame({'top100': t[cols].mean(), 'mid': m[cols].mean()}).T.round(3).to_string())
print('\n== the named 150-entry top-10 users (W2/W3) and the top-100 repeaters')
# The DK usernames analysed here are PRIVATE (operator policy 2026-10-03): never commit them. They are read from a
# private file (one per line); the labels used in F-portfolios.md map to them in ~/private/dk-handle-labels-20261005.csv.
names = [n.strip() for n in open(os.path.expanduser(os.environ.get('DK_HANDLES_FILE', '~/private/dk_handles_f2.txt'))) if n.strip()]
T = A[A.user.isin(names)].sort_values(['user', 'week'])
print(T[['week', 'grp', 'user'] + cols].round(3).to_string(index=False))
print(T[['week', 'user'] + scols].round(2).to_string(index=False))
# correlation of anatomy with mean_pts within all >=20-entry user-weeks pulled (top100 + mid, note selection)
print('\n== within-week Spearman of anatomy vs mean_pts (top100+mid user-weeks; SELECTED sample, descriptive only)')
from scipy.stats import spearmanr
for c in ['exp_top1', 'exp_top3', 'n_cores', 'core1_share', 'mean_overlap', 'n_qb', 'unique_share', 'n_players', 'TE_modal_share', 'FLEX_distinct']:
    print(c, {w: round(spearmanr(A[A.week == w][c], A[A.week == w].mean_pts)[0], 3) for w in (1, 2, 3)})
