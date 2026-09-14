"""Payout retro-test on the Week-1 Millionaire field (2026-09-14).
For each of the final build's 800 candidates and each of 10,000 simulated worlds (incumbent law), score the ENTIRE real field
(831,028 lineups) in that world, read the world's payout-tier cutoffs from DraftKings' actual 34-tier table, and convert the
candidate's world score to a payout. Expected payout per candidate = mean over worlds. Compare the expected-max books (the
K90 book order) with the top-K by expected payout, on overlap, simulated expected payout, and ACTUAL payout (official points,
actual field ranks)."""
import json, sys, time, pathlib, re, numpy as np, pandas as pd
sys.path.insert(0, "/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912/src")
from nfl_dfs.names import norm_name
from nfl_dfs.ingest.ownership_import import parse_entries_csv, parse_standings_csv
OUT = pathlib.Path("/home/erich/week1-sunday/payout"); RUN = pathlib.Path("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01/20260913T160405364118Z-e7255e9")
t0 = time.time()
tiers = json.load(open(OUT / "contest_193028206.json"))["contestDetail"]["payoutSummary"]
tiers = sorted([(int(t["minPosition"]), int(t["maxPosition"]), float(t["payoutDescriptions"][0]["value"])) for t in tiers], key=lambda x: x[0])
maxpos = np.array([t[1] for t in tiers]); values = np.array([t[2] for t in tiers]); print("payout tiers:", len(tiers), "| last paid position", maxpos[-1], "| top", values[:3])
def payout_for_rank(r):
    i = np.searchsorted(maxpos, r, side="left"); return np.where(i < len(values), values[np.minimum(i, len(values) - 1)], 0.0)
fr = pd.read_parquet(RUN / "frame.parquet"); fr["nn"] = fr.display_name.astype(str).map(norm_name); ids = fr.id.astype(str).tolist()
TEAMN = {"ARI":"Cardinals","ATL":"Falcons","BAL":"Ravens","BUF":"Bills","CAR":"Panthers","CHI":"Bears","CIN":"Bengals","CLE":"Browns","DAL":"Cowboys","DEN":"Broncos","DET":"Lions","GB":"Packers","HOU":"Texans","IND":"Colts","JAX":"Jaguars","KC":"Chiefs","LV":"Raiders","LAC":"Chargers","MIA":"Dolphins","MIN":"Vikings","NE":"Patriots","NO":"Saints","NYG":"Giants","NYJ":"Jets","PHI":"Eagles","PIT":"Steelers","SF":"49ers","SEA":"Seahawks","TB":"Buccaneers","TEN":"Titans","WAS":"Commanders"}
name2row = {}
for i, r in fr.reset_index(drop=True).iterrows():
    key = norm_name(TEAMN.get(str(r.team), str(r.team))) if r.position == "DST" else r.nn; name2row.setdefault(key, i)
M = np.load(RUN / "incumbent_player_scores.npy").astype(np.float32); ZERO = M.shape[0]; M = np.vstack([M, np.zeros((1, M.shape[1]), np.float32)]); W = M.shape[1]; print("players", ZERO, "worlds", W)
# the real field
e = parse_entries_csv("/home/erich/projects/nfl-predictions/results/2026-09-13/contest-standings-193028206.csv")
def lineup_rows(slots_json):
    return [name2row.get(norm_name(s["player"]), ZERO) for s in json.loads(slots_json)]
F = np.array([lineup_rows(j) for j in e.lineup_slots_json], dtype=np.int32); actual_field = e.points.to_numpy(float)
unmatched = float((F == ZERO).mean()); print(f"field lineups {len(F):,} | slots unmatched to the frame (scored 0): {unmatched:.2%} | {time.time()-t0:.0f}s")
# our candidates (the final build's pool) + actual official points
cands = pd.read_parquet(RUN / "candidates.parquet"); idx = {p: i for i, p in enumerate(ids)}
C = np.array([[idx[p] for p in pl.split(",")] for pl in cands.players], dtype=np.int32)
own = parse_standings_csv("/home/erich/projects/nfl-predictions/results/2026-09-13/contest-standings-193028206.csv"); own["nn"] = own.display_name.map(norm_name); fp = dict(zip(own.nn, own.fpts.fillna(0.0)))
row_pts = np.zeros(ZERO + 1)
for i, r in fr.reset_index(drop=True).iterrows():
    key = norm_name(TEAMN.get(str(r.team), str(r.team))) if r.position == "DST" else r.nn; row_pts[i] = fp.get(key, 0.0)
cands["actual"] = row_pts[C].sum(axis=1)
sorted_field = np.sort(actual_field)[::-1]
def actual_rank(s): return int((sorted_field > s).sum()) + 1
cands["actual_rank"] = cands.actual.map(actual_rank); cands["actual_payout"] = payout_for_rank(cands.actual_rank.to_numpy())
# per-world cutoffs from the whole field, chunked over worlds
CH = 200; cut = np.zeros((W, len(tiers)), np.float32); kth = (len(F) - maxpos).astype(int)  # index in ascending partition for the r-th largest
for s in range(0, W, CH):
    Mc = M[:, s:s + CH]; S = np.zeros((len(F), Mc.shape[1]), np.float32)
    for j in range(9): S += Mc[F[:, j]]
    P = np.partition(S, kth, axis=0); cut[s:s + CH] = P[kth].T
    if (s // CH) % 10 == 0: print(f"  worlds {s}-{s+CH}: {time.time()-t0:.0f}s", flush=True)
np.save(OUT / "field_cutoffs_incumbent.npy", cut)
# candidate payouts per world
SC = np.zeros((len(C), W), np.float32)
for j in range(9): SC += M[C[:, j]]
pay = np.zeros_like(SC)
for t in range(len(tiers) - 1, -1, -1):   # worst tier first, better tiers overwrite
    pay = np.where(SC >= cut[:, t][None, :], values[t], pay)
cands["e_payout"] = pay.mean(axis=1); cands["p_cash"] = (pay > 0).mean(axis=1); cands["p_top1000"] = (SC >= cut[:, np.searchsorted(maxpos, 1000)][None, :]).mean(axis=1); cands["p_top100"] = (SC >= cut[:, np.searchsorted(maxpos, 100)][None, :]).mean(axis=1)
cands["sim_mean"] = SC.mean(axis=1); cands["sim_q99"] = np.quantile(SC, 0.99, axis=1)
cands.drop(columns=["names", "all_tags"], errors="ignore").to_csv(OUT / "candidates_payout.csv", index=False)
book = cands[cands.book_rank.notna()].sort_values("book_rank"); byp = cands.sort_values("e_payout", ascending=False)
lines = [f"# Payout retro-test, Week-1 Millionaire field (final build pool, {len(cands)} candidates, {W} worlds, incumbent law)", "",
         f"field: {len(F):,} lineups; unmatched slots {unmatched:.2%}; candidate actual points from official FPTS", "",
         "| book | n | overlap with DEMAX same-K | sim E[payout] per entry | sim P(cash) | sim P(top-1000) | actual best score | actual payout total | actual best rank |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
def row(name, df, ref):
    lines.append(f"| {name} | {len(df)} | {len(set(df.index) & set(ref.index))} | ${df.e_payout.mean():.2f} | {df.p_cash.mean():.1%} | {df.p_top1000.mean():.2%} | {df.actual.max():.2f} | ${df.actual_payout.sum():.0f} | {int(df.actual_rank.min()):,} |")
for K in (30, 80, 90):
    d = book.head(K); p = byp.head(K); row(f"DEMAX first {K}", d, d); row(f"top {K} by expected payout", p, d)
    # a mixed book: DEMAX first K/2 + payout fill
    mix = pd.concat([d.head(K // 2), byp[~byp.index.isin(d.head(K // 2).index)].head(K - K // 2)]); row(f"half DEMAX / half payout, K={K}", mix, d)
lines += ["", f"whole pool: E[payout] mean ${cands.e_payout.mean():.2f} (entry fee $5); top candidate E[payout] ${cands.e_payout.max():.2f}; actual payouts in the pool: {int((cands.actual_payout>0).sum())} of {len(cands)} cash, best actual {cands.actual.max():.2f} (rank {int(cands.actual_rank.min()):,})",
          f"correlation across candidates: E[payout] vs sim mean {cands.e_payout.corr(cands.sim_mean):.2f}, vs sim q99 {cands.e_payout.corr(cands.sim_q99):.2f}; DEMAX rank (80) vs E[payout] rank: Spearman {book.book_rank.corr(book.e_payout.rank(ascending=False), method='spearman'):.2f}",
          f"top-10 by expected payout: " + "; ".join(f"{r.tag} cand {int(r.cand)} E${r.e_payout:.2f} p1000 {r.p_top1000:.1%} actual {r.actual:.1f}" for r in byp.head(10).itertuples())]
(OUT / "payout_retro_test.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines)); print(f"DONE {time.time()-t0:.0f}s")
