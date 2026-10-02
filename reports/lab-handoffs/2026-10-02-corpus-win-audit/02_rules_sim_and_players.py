"""Why the Week-1/3 pools could not reach the winning lines (hindsight; run after 01_ from the same data directory).

  D. House rules against the whole field: the share of a random field sample that satisfies every rule, against the
     share among the top-0.1% lineups. Below 1x = the rules exclude winners more than they exclude lineups in general.
  E. Is the simulator's tail wide enough? Each player's realized score is placed in his own 10,000 simulated draws
     (the independent selection bank stored with the run, `incumbent_player_scores.npy`). A calibrated tail puts 1% of
     players above their simulated p99. Ties (many draws at 0) are broken uniformly (randomized PIT).
     Then 300 simulated worlds: the best house-legal lineup of each world, and the pool's best in the same world. The
     realized week is placed in those distributions.
  F. The players behind the winners: exposure among the Millionaire's top-0.1% lineups against exposure in our pool,
     with our projection rank, the realized score and its PIT.
"""
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

H = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("h01", H / "01_history_pool_vs_winners.py"); h01 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h01)
norm, lineup_names = h01.norm, h01.lineup_names

RUNS = {1: "pools/w1-e7255e9", 3: "pools/w3-union-w3z"}
N_WORLDS = 300
rng = np.random.default_rng(20261002)


def house_mask(R: pd.DataFrame, lineups: pd.Series) -> pd.DataFrame:
    v = lineups.map(lambda r: h01.house_rule_violations(r, R))
    out = pd.DataFrame({"legal": v.map(len).eq(0)})
    for k in ("QB stack < 2", "no bring-back", "> 4 in one game", "RB vs own DST", "two RBs one team", "salary"):
        out[k] = v.map(lambda vs, k=k: any(x.startswith(k) for x in vs))
    return out


def best_in_world(frame: pd.DataFrame, R: pd.DataFrame, world: np.ndarray) -> float:
    pts = {norm(n): float(s) for n, s in zip(frame.display_name, world)}
    return h01.best_lineup(R, pts, house=True, universe=set(pts))[0]


def main() -> int:
    field = pd.read_parquet("field_points.parquet"); top = pd.read_parquet("field_top2pct.parquet")
    samp = pd.read_parquet("field_sample.parquet"); own = pd.read_parquet("milly_ownership_fpts.parquet")
    for week in (1, 3):
        rd = RUNS[week]; frame = pd.read_parquet(f"{rd}/frame.parquet"); R = h01.roster_table(week, frame)
        cid = h01.MILLY[week]; f = field[field.contest_id == cid].points.to_numpy(); p999 = np.quantile(f, .999)
        print(f"\n{'=' * 100}\nWEEK {week}")

        # D
        S = samp[samp.contest_id == cid]; W = top[(top.contest_id == cid) & (top.points >= p999)]
        ms = house_mask(R, S.players_key.map(lineup_names)); mw = house_mask(R, W.players_key.map(lineup_names))
        D = pd.DataFrame({"random field sample": ms.mean(), "top 0.1%": mw.mean()}); D["winners / field"] = D["top 0.1%"] / D["random field sample"]
        print(f"--- D. house rules: field sample n={len(S):,}, top-0.1% n={len(W):,} (share of lineups; rule rows = share BREAKING it)")
        print(D.round(3).to_string())

        # E1: per-player PIT
        sims = np.load(f"{rd}/incumbent_player_scores.npy")
        pts = h01.week_points(own, week)
        real = frame.display_name.map(lambda n: pts.get(norm(n), np.nan)).to_numpy()
        ok = ~np.isnan(real); u = rng.random(len(frame))
        below = (sims < real[:, None]).sum(1); tie = (sims == real[:, None]).sum(1)
        pit = (below + u * tie) / sims.shape[1]
        p99 = np.quantile(sims, .99, axis=1); p999s = np.quantile(sims, .999, axis=1)
        skill = (frame.pos != "DST").to_numpy() & ok
        print(f"\n--- E1. per-player tail calibration ({skill.sum()} skill players with a realized score; DST separately)")
        for lab, m in (("skill", skill), ("DST", (frame.pos == "DST").to_numpy() & ok)):
            print(f"  {lab}: above sim p99 {np.mean(real[m] > p99[m]):.3%} (calibrated 1%), above p99.9 {np.mean(real[m] > p999s[m]):.3%} "
                  f"(0.1%); PIT deciles {np.histogram(pit[m], bins=10, range=(0, 1))[0].tolist()}")
        big = skill & (real >= 25)
        print(f"  players who scored 25+: {big.sum()}; their median PIT {np.median(pit[big]):.3f}; share above their sim p99 {np.mean(real[big] > p99[big]):.1%}")

        # E2: world optimum and pool best in 300 worlds vs the realized week
        cands = pd.read_parquet(f"{rd}/candidates.parquet"); pos = {str(i): k for k, i in enumerate(frame.id)}
        M = np.zeros((len(cands), len(frame)), dtype=np.float32)
        for r, cell in enumerate(cands.players.astype(str)):
            for p in cell.split(","):
                M[r, pos[p]] = 1.0
        ws = rng.choice(sims.shape[1], N_WORLDS, replace=False)
        opt = np.array([best_in_world(frame, R, sims[:, w]) for w in ws]); pool_best = (M @ sims[:, ws]).max(0)
        gap = opt - pool_best
        real_scores = np.nan_to_num(real); real_opt = h01.best_lineup(R, pts, house=True, universe=set(frame.display_name.map(norm)))[0]
        real_pool = float((M @ real_scores).max())
        pct = lambda a, x: float((a < x).mean())
        print(f"\n--- E2. {N_WORLDS} simulated worlds (house rules), pool of {len(cands):,}")
        print(f"  world optimum: median {np.median(opt):.1f}, p90 {np.quantile(opt, .9):.1f}, max {opt.max():.1f} | realized {real_opt:.1f} "
              f"(percentile {pct(opt, real_opt):.3f})")
        print(f"  pool best: median {np.median(pool_best):.1f}, p90 {np.quantile(pool_best, .9):.1f} | realized {real_pool:.1f} (percentile {pct(pool_best, real_pool):.3f})")
        print(f"  gap optimum - pool best: median {np.median(gap):.1f}, p90 {np.quantile(gap, .9):.1f}, max {gap.max():.1f} | realized {real_opt - real_pool:.1f} "
              f"(percentile {pct(gap, real_opt - real_pool):.3f})")
        print(f"  pool best >= this week's real top-0.1% line ({p999:.1f}) in {np.mean(pool_best >= p999):.1%} of worlds; realized: {real_pool >= p999}")

        # F: players behind the winners
        wn = Counter(norm(n) for r in W.players_key.map(lineup_names) for n in r)
        pool_n = Counter(norm(n) for r in cands["names"].map(lineup_names) for n in r)
        rank = frame.assign(k=frame.display_name.map(norm)).set_index("k")
        rank["proj_rank_pos"] = rank.groupby("pos").mean_projection.rank(ascending=False)
        # ownership is reported per roster slot (an RB has an RB row and a FLEX row): the player's ownership is the sum
        o = own[(own.contest_id == cid)].assign(k=lambda d: d.display_name.map(norm)).groupby("k").agg(pct_drafted=("pct_drafted", "sum"))
        pit_of = dict(zip(frame.display_name.map(norm), pit))
        rows = []
        for k, n in wn.most_common(15):
            rows.append({"player": rank.display_name.get(k, k), "pos": rank.pos.get(k, ""), "share of top-0.1%": round(n / len(W), 3),
                         "share of our pool": round(pool_n.get(k, 0) / len(cands), 3), "our proj": round(float(rank.mean_projection.get(k, np.nan)), 1),
                         "proj rank in pos": rank.proj_rank_pos.get(k, np.nan), "realized": pts.get(k), "field own %": o.pct_drafted.get(k),
                         "sim PIT": round(float(pit_of.get(k, np.nan)), 4)})
        print("\n--- F. the 15 players most used by the top-0.1% lineups"); print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
