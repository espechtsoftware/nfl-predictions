"""F5 (PRELIMINARY): per-winner decomposition + our pool/book exposure. Inputs all realized (post-lock)."""
import pandas as pd, numpy as np, pickle, glob, re
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
B = '/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live'
def norm(s): return re.sub(r'\s+(Sr\.|Jr\.|III|II|IV)$', '', str(s).strip()) if isinstance(s, str) else ''
def pool_sets(df): return [set(norm(x) for x in n.split('|')) for n in df['names']]
pools = {}
w1 = pd.concat([pd.read_parquet(d) for d in sorted(glob.glob(B + '/2026-w01/*-e7255e9/candidates.parquet'))])
pools[1] = ('W1 union of 12 e7255e9 builds (pre-lock, Sat 09-12/Sun 09-13)', pool_sets(w1.drop_duplicates('players')))
w1d800 = pd.read_parquet(B + '/2026-w01/20260912T192221336726Z-e7255e9/candidates.parquet')
pools['1_entered_build'] = ('W1 build that produced the entered book (20260912T1922Z)', pool_sets(w1d800))
w2 = pd.read_parquet(B + '/2026-w02/20260916T165251953256Z-e7255e9/candidates.parquet')
pools[2] = ('W2 12,559-candidate build (20260916T1652Z, Wed pre-lock)', pool_sets(w2))
w3 = pickle.load(open('/home/erich/week3-sunday/postmortem/cands_scored.pkl', 'rb'))
pools[3] = ('W3 12,559-candidate pool (cands_scored.pkl)', pool_sets(w3))
ours = pd.read_csv('ours.csv')
books = {1: [set(norm(x) for x in k.split('|')) for k in ours[ours.week == 1].players_key],
         2: [set(norm(x) for x in k.split('|')) for k in ours[ours.week == 2].players_key],
         3: [set(norm(x) for x in k.split('|')) for k in ours[ours.week == 3].players_key]}
book3 = pickle.load(open('/home/erich/week3-sunday/postmortem/our_book.pkl', 'rb'))
books['3_full144'] = [set(norm(x) for x in n) for n in book3['names']]
univ = {1: set(norm(x) for x in pd.read_parquet(B + '/2026-w01/20260912T204921889774Z-e7255e9/frame.parquet').display_name),
        2: set(norm(x) for x in pd.read_parquet(B + '/2026-w02/20260916T165251953256Z-e7255e9/frame.parquet').display_name),
        3: set(norm(x) for x in pd.read_csv('/home/erich/week3-sunday/postmortem/players.csv').name)}
win = pd.read_csv('winners.csv'); win['p'] = win.player.map(norm)
def share(sets, p): return np.mean([p in s for s in sets]) if sets else np.nan
rows = []
for (w, r, u), g in win.groupby(['week', 'rank', 'user'], sort=False):
    f = g.sort_values('fpts', ascending=False)
    pts = f.fpts.values
    pn, ps = pools[w]; bk = books[w]
    inpool = [share(ps, p) for p in f.p]; inbook = [share(bk, p) for p in f.p]
    d = dict(week=w, rank=r, user=u, entries=g.entry_n.iloc[0], total=round(g.points.iloc[0], 1), best1=pts[0], best1_name=f.p.iloc[0],
             top3=round(pts[:3].sum(), 1), top3_share=round(pts[:3].sum() / g.points.iloc[0], 2), n25=int((pts >= 25).sum()), n30=int((pts >= 30).sum()), n40=int((pts >= 40).sum()),
             own_sum=round(f.own.sum(), 1), n_sub5=int((f.own < 5).sum()),
             in_universe=sum(p in univ[w] for p in f.p), in_pool=sum(x > 0 for x in inpool), in_book=sum(x > 0 for x in inbook),
             pool_share_mean=round(np.nanmean(inpool), 3), pool_min=round(np.nanmin(inpool), 4),
             book_share_mean=round(np.nanmean(inbook), 3))
    if w == 3:
        ib = [share(books['3_full144'], p) for p in f.p]; d['in_book144'] = sum(x > 0 for x in ib); d['book144_share_mean'] = round(np.mean(ib), 3)
    if w == 1:
        ib = [share(pools['1_entered_build'][1], p) for p in f.p]; d['in_entered_build_pool'] = sum(x > 0 for x in ib)
    rows.append(d)
    print(f'\n== W{w} #{r} {u} ({g.entry_n.iloc[0]} entries) {g.points.iloc[0]:.1f} pts')
    print(pd.DataFrame({'player': f.p.values, 'slot': f.slot.values, 'fpts': pts, 'milly_own%': f.own.round(1).values,
                        'in_universe': [p in univ[w] for p in f.p], 'pool_share': np.round(inpool, 4), 'book_share': np.round(inbook, 3)}).to_string(index=False))
out = pd.DataFrame(rows); print('\n== SUMMARY'); print(out.to_string(index=False))
out.to_csv('f5_summary.csv', index=False)
print('\npool sizes:', {k: len(v[1]) for k, v in pools.items()}, 'book sizes:', {k: len(v) for k, v in books.items()})
# which deciding players were absent from every pool row
for w in (1, 2, 3):
    g = win[win.week == w]; pn, ps = pools[w]
    miss = sorted(set(p for p in g.p if share(ps, p) == 0)); print(f'W{w} players in winning rows with ZERO pool rows: {miss}')
    cnt = pd.Series([p for s in ps for p in s]).value_counts(normalize=True)
    print(f'   pool top-8 exposures W{w}:', cnt.head(8).round(3).to_dict())
    bk = books[w]; cntb = pd.Series([p for s in bk for p in s]).value_counts(normalize=True)
    print(f'   book top-8 exposures W{w} (Millionaire rows, n={len(bk)}):', cntb.head(8).round(3).to_dict())
