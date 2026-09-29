"""F1 (PRELIMINARY): persistence across the three 2026 Millionaires from userweek.csv + shape.csv (BigQuery groupings)."""
import pandas as pd, numpy as np
from scipy.stats import spearmanr
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 400)
uw = pd.read_csv('userweek.csv'); sh = pd.read_csv('shape.csv')
uw = uw.merge(sh.drop(columns=['n', 'n_unmatched']), on=['week', 'user'], how='left')
N = {1: 831028, 2: 172692, 3: 161682}
print('user-weeks', len(uw), 'unmatched ownership names', uw.n_unmatched.sum())
W = {w: uw[uw.week == w].set_index('user') for w in (1, 2, 3)}
print('\n== Spearman of per-user mean finish percentile (and mean points), users with >=20 entries in both weeks')
for a, b in [(1, 2), (2, 3), (1, 3)]:
    j = W[a][W[a].n >= 20].join(W[b][W[b].n >= 20], lsuffix='_a', rsuffix='_b', how='inner')
    r1, p1 = spearmanr(j.mean_pct_a, j.mean_pct_b); r2, p2 = spearmanr(j.mean_pts_a, j.mean_pts_b)
    r3, p3 = spearmanr(j.best_pct_a, j.best_pct_b)
    print(f'W{a}->W{b}: users={len(j):4d}  rho(mean_pct)={r1:+.3f} p={p1:.3g}   rho(mean_pts)={r2:+.3f} p={p2:.3g}   rho(best_pct)={r3:+.3f} p={p3:.3g}')
    # two-by-two: top 20% of these users by mean_pct in A vs in B
    ta = j.mean_pct_a <= j.mean_pct_a.quantile(0.2); tb = j.mean_pct_b <= j.mean_pct_b.quantile(0.2)
    ct = pd.crosstab(ta, tb); base = tb.mean(); cond = tb[ta].mean()
    print(f'   2x2 (top20% in W{a} rows x top20% in W{b} cols):\n{ct}\n   P(top20 in W{b} | top20 in W{a}) = {cond:.3f} vs base {base:.3f}; lift {cond/base:.2f}x')
    # shapes: persistent = top20 in BOTH; described in week b
    pers = j[ta & tb]; non = j[~(ta & tb)]
    cols = ['own_sum_b', 'n_sub5_b', 'n_chalk_b', 'max_own_b', 'stk_b', 'stk2_rate_b', 'bb_rate_b', 'n_games_b', 'max_game_b', 'n_te_b', 'n_7k_b', 'qb_sal_b', 'n_qb_b', 'mean_pts_b']
    print('   shapes in W%d: persistent (top20 both, n=%d) vs others (n=%d)' % (b, len(pers), len(non)))
    print(pd.DataFrame({'persistent': pers[cols].mean().round(2), 'others': non[cols].mean().round(2)}).T.to_string())
print('\n== Top-10 finishers of each week, by name: where they finished the other weeks (mean pct / best rank / entries)')
allu = uw.pivot(index='user', columns='week', values=['n', 'mean_pct', 'best_rank', 'mean_pts', 'n_top100', 'own_sum'])
def fmt(u, w):
    if w not in W or u not in W[w].index: return '-'
    r = W[w].loc[u]; return f"n={int(r.n)} best#{int(r.best_rank)} ({r.best_pct:.2f}%) meanpct={r.mean_pct:.1f} meanpts={r.mean_pts:.1f}"
rows = []
for w in (1, 2, 3):
    t = W[w][W[w].n_top10 > 0].sort_values('best_rank')
    for u, r in t.iterrows():
        rows.append({'week': w, 'user': u, 'best_rank': int(r.best_rank), 'entries': int(r.n), 'W1': fmt(u, 1), 'W2': fmt(u, 2), 'W3': fmt(u, 3)})
print(pd.DataFrame(rows).to_string(index=False))
print('\n== Top-100 finishers of each week: other-week summary')
for w in (1, 2, 3):
    t = W[w][W[w].n_top100 > 0]
    for o in (1, 2, 3):
        if o == w: continue
        j = t.join(W[o], rsuffix='_o', how='inner')
        played = len(j); nusers = len(t)
        print(f'W{w} top-100 users: {nusers}; played W{o}: {played} ({played/nusers:.0%}); of those: median mean_pct in W{o} {j.mean_pct_o.median():.1f}, '
              f'best_rank median {j.best_rank_o.median():.0f}, top-1% again {(j.n_top1pct_o>0).mean():.0%}, top-100 again {(j.n_top100_o>0).mean():.0%}, '
              f'top-1000 again {(j.best_rank_o<=1000).mean():.0%}, mean-pct<50 {(j.mean_pct_o<50).mean():.0%}, entries median {j.n_o.median():.0f}')
    # base rates for comparison: any user who played week o
    for o in (1, 2, 3):
        b = W[o]; print(f'   base W{o}: users {len(b)}, top-1% {(b.n_top1pct>0).mean():.2%}, top-100 {(b.n_top100>0).mean():.3%}, top-1000 {(b.best_rank<=1000).mean():.2%}, mean_pct<50 {(b.mean_pct<50).mean():.1%}')
print('\n== Named repeaters: users top-100 in at least two weeks')
tt = uw[uw.n_top100 > 0].groupby('user').agg(weeks=('week', lambda s: ','.join(map(str, sorted(s)))), k=('week', 'size'))
rep = tt[tt.k >= 2].index
out = uw[uw.user.isin(rep)].pivot(index='user', columns='week', values='best_rank').join(uw[uw.user.isin(rep)].pivot(index='user', columns='week', values='n'), rsuffix='_n')
print(out.to_string())
# expected number of repeaters under independence
for a, b in [(1, 2), (2, 3), (1, 3)]:
    ja = set(W[a][W[a].n_top100 > 0].index); jb = set(W[b][W[b].n_top100 > 0].index)
    both = set(W[a].index) & set(W[b].index)
    pa = len(ja & both) / len(both); pb = len(jb & both) / len(both)
    print(f'W{a}&W{b}: users in both weeks {len(both)}; top100 both {len(ja & jb)}; expected under independence {pa*pb*len(both):.2f}')
print('\n== Entry-count-weighted: top-100 FINISHERS reweighted; share of top-100 entries by entry-count bucket, and per-entry rate')
for w in (1, 2, 3):
    b = W[w]; b = b.assign(bucket=pd.cut(b.n, [0, 1, 3, 20, 50, 149, 150], labels=['1', '2-3', '4-20', '21-50', '51-149', '150']))
    g = b.groupby('bucket', observed=True).agg(users=('n', 'size'), entries=('n', 'sum'), top100=('n_top100', 'sum'), top1pct=('n_top1pct', 'sum'), mean_pts=('mean_pts', lambda s: np.average(s, weights=b.loc[s.index, 'n'])))
    g['top100_per_1k_entries'] = g.top100 / g.entries * 1000; g['top1pct_rate'] = g.top1pct / g.entries
    print(f'W{w}\n{g.round(3).to_string()}')
