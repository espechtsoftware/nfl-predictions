"""Does the corpus contain the lineups that win? (run after 01_/02_, same data directory; W1 and W3 in hindsight, and any
run dir given on the command line outcome-blind).

  G. Nearest pool lineup to each real top-0.1% Millionaire lineup: the most players any pool lineup shares with it
     (9 = the pool holds that exact lineup). Field baseline: the same statistic for a random field sample of the same
     size as the pool, so "8 of 9" can be read against what an equally large slice of the crowd achieves.
  H. Winning margin inside our own model: in 300 simulated worlds (independent selection bank), the share of worlds
     whose pool holds a lineup within g points of that world's best house-legal lineup, g = 3 / 10 / 17 (the realized
     winner's distance from the realized best lineup: W1 3.1, W3 17.0).
  I. DST: the pool's DST shares against the top-0.1% lineups' (the generation bank holds every DST at its projection).
Usage: 03_nearest_and_margin.py [extra run dir ...]   (extra run dirs: H and I only, no outcomes)
"""
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

H = Path(__file__).resolve().parent
def _load(name, file):
    s = importlib.util.spec_from_file_location(name, H / file); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
h01 = _load("h01", "01_history_pool_vs_winners.py"); h02 = _load("h02", "02_rules_sim_and_players.py")
norm, lineup_names = h01.norm, h01.lineup_names
rng = np.random.default_rng(7)
GAPS = (3.0, 10.0, 17.0)


def nearest(sets_a: list[frozenset], sets_b: list[frozenset]) -> np.ndarray:
    """For each lineup in a, the most players shared with any lineup in b."""
    vocab = {p: i for i, p in enumerate(sorted({p for s in sets_a + sets_b for p in s}))}
    A = np.zeros((len(sets_a), len(vocab)), np.int8); B = np.zeros((len(sets_b), len(vocab)), np.int8)
    for r, s in enumerate(sets_a):
        A[r, [vocab[p] for p in s]] = 1
    for r, s in enumerate(sets_b):
        B[r, [vocab[p] for p in s]] = 1
    out = np.zeros(len(sets_a), int)
    for lo in range(0, len(sets_b), 4000):
        out = np.maximum(out, (A.astype(np.int32) @ B[lo:lo + 4000].T.astype(np.int32)).max(1))
    return out


def margin_and_dst(rd: str, week: int | None) -> None:
    frame = pd.read_parquet(f"{rd}/frame.parquet"); cands = pd.read_parquet(f"{rd}/candidates.parquet")
    sims = np.load(f"{rd}/incumbent_player_scores.npy")
    R = h01.roster_table(week, frame) if week else roster_from_frame(frame)
    pos = {str(i): k for k, i in enumerate(frame.id)}
    M = np.zeros((len(cands), len(frame)), np.float32)
    for r, cell in enumerate(cands.players.astype(str)):
        for p in cell.split(","):
            M[r, pos[p]] = 1.0
    ws = rng.choice(sims.shape[1], 300, replace=False)
    opt = np.array([h02.best_in_world(frame, R, sims[:, w]) for w in ws]); best = (M @ sims[:, ws]).max(0)
    print(f"  H. {rd}: pool {len(cands):,}; world optimum median {np.median(opt):.1f}; gap median {np.median(opt - best):.1f}; "
          + "; ".join(f"within {g:.0f}: {np.mean(opt - best <= g):.1%}" for g in GAPS))
    dst_ids = set(frame.id[frame.pos == "DST"].astype(str))
    d = Counter(p for cell in cands.players.astype(str) for p in cell.split(",") if p in dst_ids)
    print("  I. pool DST shares:", {k: round(v / len(cands), 3) for k, v in d.most_common(6)})


def roster_from_frame(frame: pd.DataFrame) -> pd.DataFrame:
    t = pd.DataFrame({"key": frame.display_name.map(norm), "name": frame.display_name, "pos": frame.pos, "team": frame.team,
                      "salary": frame.salary, "opp": frame.opp, "game": frame.game_id})
    return t.drop_duplicates("key").set_index("key")


def main(argv: list[str]) -> int:
    top = pd.read_parquet("field_top2pct.parquet"); field = pd.read_parquet("field_points.parquet")
    samp = pd.read_parquet("field_sample.parquet")
    for week, rd in h02.RUNS.items():
        cid = h01.MILLY[week]; f = field[field.contest_id == cid].points.to_numpy(); p999 = np.quantile(f, .999)
        W = top[(top.contest_id == cid) & (top.points >= p999)]
        wsets = [frozenset(norm(n) for n in lineup_names(k)) for k in W.players_key]
        print(f"\n{'=' * 100}\nWEEK {week}: {len(W)} top-0.1% Millionaire lineups")
        for label, cpath, _ in h01.POOLS[week]:
            c = pd.read_pickle(cpath) if cpath.endswith(".pkl") else pd.read_parquet(cpath)
            psets = [frozenset(norm(n) for n in lineup_names(x)) for x in c["names"]]
            near = nearest(wsets, psets)
            S = samp[samp.contest_id == cid]; S = S.sample(min(len(psets), len(S)), random_state=1)
            fnear = nearest(wsets, [frozenset(norm(n) for n in lineup_names(k)) for k in S.players_key])
            dist = lambda a: {k: round(float(np.mean(a == k)), 3) for k in (9, 8, 7, 6)} | {"<=5": round(float(np.mean(a <= 5)), 3)}
            print(f"  G. {label} ({len(psets):,}): nearest pool lineup shares {dist(near)}")
            print(f"     same-size random field slice ({len(S):,}):           {dist(fnear)}")
        margin_and_dst(rd, week)
        wd = Counter(n for k in W.players_key for n in lineup_names(k) if n in set(pd.read_parquet(f"{rd}/frame.parquet").query("pos == 'DST'").display_name))
        print("  I. top-0.1% DST shares:", {k: round(v / len(W), 3) for k, v in wd.most_common(6)})
    for rd in argv:
        print(f"\n{'=' * 100}\nOUTCOME-BLIND: {rd}"); margin_and_dst(rd, None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
