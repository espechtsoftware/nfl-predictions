"""Is there a simulator-free SORT key for the sequential layout that beats random?  (Week 2, 2026)

GRID AND CRITERION — fixed before any number below was computed (laptop, 2026-09-22):
  Book: the 97 lineups actually entered in Week 2 (resolved in-query by the 12-contest / 97-entry
  signature; no account name is printed or stored). A key only PERMUTES this book.
  Layout: Week-2 payout order (tracked in reports/2026-09-18-satellite-entry-allocation-question.md):
    milly 1 | flea 23 | huddle 1 | nickel 5 | pylon 1 | $555 sat 2 | $1 supersats 10+10+10 |
    $0.25 supersats 16+16 | ffwc sat 2   -> book ranks 1..97, in that order.
  Keys (declared direction; rank 1 = first in the sort):
    sim_mean  desc  incumbent hsim (matches book sel_mean exactly)      [the current key]
    sim_p194  desc  incumbent hsim P(lineup >= 194)
    proj_sum  desc  frame proj
    own_naive asc   sum of pre-lock naive_ownership (deployable)
    own_real  asc   sum of realized contest ownership       (ORACLE: post-lock)
    dup_exact asc   Millionaire-field entries with the identical 9 (ORACLE)
    dup_core  asc   Millionaire-field entries sharing >= 7 of 9  (ORACLE)
    random          5,000 permutations = the null
  Lines, from each contest's real field (payout is NULL in the warehouse):
    ticket contests: the K-th best field score (K = tickets: 25 / 2 / 4, tracked report);
    GPPs (milly, flea, huddle, nickel, pylon): the field's top-20% score (the usual DK cash depth).
  Scores:  (A) CASHES = entries at or above their contest's line (multi-winner currency);
           (B) MILLY  = field percentile of the single Millionaire lineup (single-winner: the max);
           (C) FLEA_BEST = best field percentile inside the flea block ($50K to 1st: the max).
  Each key is reported with its percentile inside the random distribution (the null).
  Diagnostic (direction-free): within-book Spearman(key, realized) with a permutation p.
  Two slates at most; this NOMINATES, it does not adopt.
Caveat: sim/proj come from the Saturday 15:10Z run's frame, not the Sunday T-70 frame that built the book.
"""
import sys, numpy as np, pandas as pd
from scipy.stats import spearmanr
from nfl_dfs.bq import query_df
from nfl_dfs.backtest.field import naive_ownership
D, OUT = sys.argv[1], sys.argv[2]
T = "`nfl-predictions-503414.nfl_raw.contest_entries`"; SIG = "REGEXP_REPLACE(entry_name, r' \\(.*\\)$', '')"
ours = query_df(f"""WITH acct AS (SELECT {SIG} nm FROM {T} WHERE season=2026 AND week=2 GROUP BY 1
                      HAVING COUNT(DISTINCT contest_id)=12 AND COUNT(*)=97)
   SELECT contest_id, points, players_key FROM {T} WHERE season=2026 AND week=2 AND {SIG} IN (SELECT nm FROM acct)""")
assert len(ours) == 97
BLOCKS = [("milly", [195648007], 1, "gpp"), ("flea", [195661344], 23, "gpp"), ("huddle", [195661326], 1, "gpp"),
          ("nickel", [195661365], 5, "gpp"), ("pylon", [195661380], 1, "gpp"), ("sat555", [195660061], 2, 2),
          ("ss1a", [195660200], 10, 25), ("ss1b", [195660201], 10, 25), ("ss1c", [195660202], 10, 25),
          ("ss25a", [195660198], 16, 25), ("ss25b", [195660199], 16, 25), ("ffwc", [195660229], 2, 4)]
assert sum(b[2] for b in BLOCKS) == 97
fields = {}
for name, ids, n, pay in BLOCKS:
    f = query_df(f"SELECT points FROM {T} WHERE season=2026 AND week=2 AND contest_id=@c", {"c": str(ids[0])}).points.to_numpy(float).copy()
    f.sort(); line = np.quantile(f, 0.80) if pay == "gpp" else f[::-1][pay - 1]
    fields[name] = (f, line)
    print(f"  {name:7s} field {len(f):6d}  line {line:7.2f}  ({'top-20%' if pay=='gpp' else f'{pay} tickets'})")
pts = ours.points.to_numpy(float).copy()
fr = pd.read_parquet(f"{D}/frame.parquet"); ix = {n: i for i, n in enumerate(fr.display_name.astype(str))}
M = np.load(f"{D}/incumbent_player_scores.npy")
rows = [[ix[p] for p in k.split("|")] for k in ours.players_key]
sims = np.stack([M[r].sum(0) for r in rows])
own_n = naive_ownership(fr[["pos", "proj", "salary"]]); proj = fr.proj.to_numpy(float)
ow = query_df("SELECT display_name, MAX(pct_drafted) o FROM `nfl-predictions-503414.nfl_raw.contest_ownership` WHERE season=2026 AND week=2 AND contest_id='195648007' GROUP BY 1")
olut = dict(zip(ow.display_name.astype(str), ow.o.astype(float)))
milly = query_df(f"SELECT players_key FROM {T} WHERE season=2026 AND week=2 AND contest_id='195648007'").players_key
vocab = {}; F = np.array([[vocab.setdefault(p, len(vocab)) for p in k.split("|")] for k in milly if k and k.count("|") == 8])
exact = pd.Series([ "|".join(sorted(k.split("|"))) for k in milly]).value_counts()
def core(k):
    q = np.array([vocab.get(p, -1) for p in k.split("|")]); return int((np.isin(F, q).sum(1) >= 7).sum())
keys = {
    "sim_mean":  -sims.mean(1),
    "sim_p194":  -(sims >= 194).mean(1),
    "proj_sum":  -np.array([proj[r].sum() for r in rows]),
    "own_naive": np.array([own_n[r].sum() for r in rows]),
    "own_real":  np.array([sum(olut.get(p, 0.0) for p in k.split("|")) for k in ours.players_key]),
    "dup_exact": np.array([exact.get("|".join(sorted(k.split("|"))), 0) for k in ours.players_key], float),
    "dup_core":  np.array([core(k) for k in ours.players_key], float),
}
def score(order):
    s = pts[order]; i = 0; cash = 0; out = {}
    for name, ids, n, pay in BLOCKS:
        f, line = fields[name]; blk = s[i:i + n]; i += n
        cash += int((blk >= line).sum())
        pct = 100 * np.searchsorted(f, blk, side="right") / len(f)
        if name == "milly": out["milly"] = float(pct[0])
        if name == "flea": out["flea_best"] = float(pct.max())
    out["cashes"] = cash; return out
rng = np.random.default_rng(20260922)
null = pd.DataFrame([score(rng.permutation(97)) for _ in range(5000)])
res = []
for k, v in keys.items():
    o = np.argsort(v, kind="stable"); sc = score(o)
    rho = spearmanr(-v, pts).correlation
    perm = np.array([spearmanr(-v, rng.permutation(pts)).correlation for _ in range(2000)])
    res.append({"key": k, **sc, **{f"{m}_pctl_vs_random": round(100 * (null[m] < sc[m]).mean() + 50 * (null[m] == sc[m]).mean(), 1)
                                   for m in ("cashes", "milly", "flea_best")},
                "rho_with_realized": round(rho, 3), "perm_p_two_sided": round(float((np.abs(perm) >= abs(rho)).mean()), 3)})
res.append({"key": "random (mean)", **null.mean().round(2).to_dict()})
res.append({"key": "oracle (sort by realized)", **score(np.argsort(-pts, kind="stable"))})
r = pd.DataFrame(res); print(r.to_string(index=False)); r.to_csv(OUT, index=False)
print(f"\nrealized book: mean {pts.mean():.2f} max {pts.max():.2f}; null cashes 5-95%: {null.cashes.quantile(.05):.0f}-{null.cashes.quantile(.95):.0f}")
