"""The MONKEY BENCHMARK, permanent weekly arm (operator 10-04: "I think a monkey could have chosen better this week";
the reviewer's binding design). For one week: is our entered book better than random books built from the same inputs?

  M1  uniform random rows from OUR pool (the entered run's candidates), the same number of entries per contest
  M2  M1 under the caps the entered book ACTUALLY respected (max non-DST exposure, max DST exposure, max pairwise
      overlap, max players per game, measured on its distinct lineups) and with its SHARING pattern (entries that share
      a lineup share a monkey row): isolates the selection step from the constraints and the dealing
  M3  uniform random LEGAL DraftKings classic lineups from the week's T-70 frame (projection > 0; salary 49,000-50,000;
      9 distinct players; at least 2 games)

Each monkey makes NB books (default 1,000; the seed is recorded). Every book is placed in the REAL contest fields with
the REAL payout ladders by moneygate_score's validated path (load_week / place: the A0 known-answer gate reproduced all
534 entered entries), so the entered book and the monkeys are scored identically. Reported per monkey: the entered
book's PERCENTILE (mid-rank, ties half) among the monkey books on cashes, mean points and the share of entries >= 100,
with the plain-words reading: above the median = "beats the monkey"; below the 25th percentile = "worse than random".

    python scripts/moneygate_monkeys.py --week 4 --pool <entered run's candidates.parquet> [--frame <T-70 frame.parquet>]
Writes the per-book results privately (PRIVATE/monkeys/w<W>.pkl) and the aggregate summary publicly
(PUBLIC/monkeys_w<W>.json); prints the summary. Pool and frame default to weeks.json (entered_union, else t70_run).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402

NB = 1000
SALARY_MIN, SALARY_MAX = 49_000, 50_000


def percentile(x: float, dist: np.ndarray) -> float:
    """Mid-rank percentile of x among dist (ties count half)."""
    d = np.asarray(dist, float)
    return float(100.0 * ((d < x).mean() + 0.5 * (d == x).mean()))


def reading(p: float) -> str:
    return "beats the monkey" if p > 50 else ("WORSE THAN RANDOM" if p < 25 else "no better than the monkey")


def empirical_caps(lineups: list[list[str]], pos_of: dict, game_of: dict) -> dict:
    ex = collections.Counter(n for L in lineups for n in L)
    return {"max_exp": max(v for n, v in ex.items() if pos_of.get(n) != "DST"),
            "max_dst": max([v for n, v in ex.items() if pos_of.get(n) == "DST"] or [len(lineups)]),
            "max_shared": max((len(set(a) & set(b)) for a, b in itertools.combinations(lineups, 2)), default=9),
            "max_per_game": max(max(collections.Counter(game_of.get(n) for n in L).values()) for L in lineups)}


def m2_rows(rng, pool: list[list[str]], k: int, caps: dict, pos_of: dict, game_of: dict) -> list[int]:
    """K distinct random pool rows (random order) that respect the entered book's empirical caps."""
    expo, taken, sets = collections.Counter(), [], []
    for r in rng.permutation(len(pool)):
        L = pool[r]
        if max(collections.Counter(game_of.get(n) for n in L).values()) > caps["max_per_game"]:
            continue
        if any(expo[n] >= (caps["max_dst"] if pos_of.get(n) == "DST" else caps["max_exp"]) for n in L):
            continue
        s = set(L)
        if any(len(s & t) > caps["max_shared"] for t in sets):
            continue
        taken.append(int(r)); sets.append(s); expo.update(L)
        if len(taken) == k:
            return taken
    raise SystemExit(f"M2: only {len(taken)} pool rows respect the entered caps {caps} (needed {k})")


def m3_bank(rng, fr: pd.DataFrame, n: int, batch: int = 2_000_000) -> np.ndarray:
    """n uniform random legal DK classic lineups (indices into fr) by rejection."""
    pos = fr.pos.astype(str).to_numpy(); sal = fr.salary.to_numpy(np.int64); game = fr.game_code.to_numpy()
    ids = {p: np.where(pos == p)[0] for p in ("QB", "RB", "WR", "TE", "DST")}
    flex = np.concatenate([ids["RB"], ids["WR"], ids["TE"]])
    out, got = [], 0
    while got < n:
        L = np.stack([rng.choice(ids["QB"], batch), rng.choice(ids["RB"], batch), rng.choice(ids["RB"], batch),
                      rng.choice(ids["WR"], batch), rng.choice(ids["WR"], batch), rng.choice(ids["WR"], batch),
                      rng.choice(ids["TE"], batch), rng.choice(flex, batch), rng.choice(ids["DST"], batch)], 1)
        s = sal[L].sum(1); L = L[(s >= SALARY_MIN) & (s <= SALARY_MAX)]
        L = L[(np.diff(np.sort(L, 1), axis=1) != 0).all(1)]
        L = L[(game[L] != game[L][:, :1]).any(1)]
        out.append(L); got += len(L)
    return np.concatenate(out)[:n]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", type=int, required=True); ap.add_argument("--pool"); ap.add_argument("--frame")
    ap.add_argument("--books", type=int, default=NB); ap.add_argument("--seed", type=int)
    a = ap.parse_args(argv)
    cfg = MS.load_config(); wc = cfg["weeks"][str(a.week)]
    run = Path(wc.get("entered_union") or wc["t70_run"])
    pool_path = Path(a.pool) if a.pool else run / "candidates.parquet"
    frame_path = Path(a.frame) if a.frame else Path(wc["t70_run"]) / "frame.parquet"
    seed = a.seed if a.seed is not None else 20260900 + a.week
    W = MS.load_week(cfg, a.week)
    fr = pd.read_parquet(frame_path)
    canon_pos = {MS.canon(n): p for n, p in zip(fr.display_name, fr.pos)}
    canon_game = {MS.canon(n): g for n, g in zip(fr.display_name, fr.game_id)}
    fp = W.fpts                                            # canonical name -> hundredths
    ours = W.field[W.field.entry_id.isin(W.ours)]
    plan = {str(c["contest_id"]) for c in W.contests}         # the money gate's contests (outside-plan entries excluded)
    excluded = sorted(set(ours.contest_id) - plan)
    ours = ours[ours.contest_id.isin(plan)]
    cids = sorted(ours.contest_id.unique())
    n_c = {c: int((ours.contest_id == c).sum()) for c in cids}
    ladders = {c: MS.Ladder.from_details(W.details[c]) for c in cids}

    def score(per: dict) -> dict:
        res, allp = {"cashes": 0}, []
        for c in cids:
            p = np.asarray(per[c], np.int64)
            pl = MS.place(p, W.others_sorted(c), ladders[c])
            res["cashes"] += int((pl["payout"] > 0).sum()); allp.append(p)
        x = np.concatenate(allp) / 100.0
        res["mean"] = float(x.mean()); res["ge100"] = float((x >= 100).mean()); res["best"] = float(x.max())
        return res

    def pts(names) -> int:
        return int(sum(fp.get(MS.canon(n), 0) for n in names))

    entered = score({c: ours[ours.contest_id == c].points.to_numpy(np.int64) for c in cids})
    cand = pd.read_parquet(pool_path)
    pool = [str(x).split("|") for x in cand.names]
    pool_pts = np.array([pts(L) for L in pool], np.int64)
    rng = np.random.default_rng(seed)
    M1 = pd.DataFrame([score({c: pool_pts[rng.choice(len(pool), n_c[c], replace=False)] for c in cids}) for _ in range(a.books)])
    # the entered book's distinct lineups (canonical names) and its sharing pattern
    keys = [tuple(sorted(x)) for x in ours.names]
    uniq = sorted(set(keys)); kid = {k: i for i, k in enumerate(uniq)}
    ours = ours.assign(row=[kid[k] for k in keys])
    pos_of = {n: canon_pos.get(MS.canon(n)) for L in pool for n in L} | {n: canon_pos.get(MS.canon(n)) for k in uniq for n in k}
    game_of = {n: canon_game.get(MS.canon(n)) for L in pool for n in L} | {n: canon_game.get(MS.canon(n)) for k in uniq for n in k}
    caps = empirical_caps([list(k) for k in uniq], pos_of, game_of)
    M2 = []
    for _ in range(a.books):
        rows = m2_rows(rng, pool, len(uniq), caps, pos_of, game_of)
        M2.append(score({c: pool_pts[np.asarray(rows)[ours[ours.contest_id == c].row.to_numpy()]] for c in cids}))
    M2 = pd.DataFrame(M2)
    f3 = fr[pd.to_numeric(fr.mean_projection, errors="coerce") > 0].copy().reset_index(drop=True)
    f3["game_code"] = f3.game_id.astype("category").cat.codes
    f3["pts"] = [fp.get(MS.canon(n), 0) for n in f3.display_name]
    total = sum(n_c.values())
    sc = f3.pts.to_numpy(np.int64)[m3_bank(rng, f3, a.books * total)].sum(1)
    M3, k = [], 0
    for _ in range(a.books):
        per = {}
        for c in cids:
            per[c] = sc[k:k + n_c[c]]; k += n_c[c]
        M3.append(score(per))
    M3 = pd.DataFrame(M3)
    summary = {"week": a.week, "seed": seed, "books": a.books, "entries": total, "contests": len(cids), "distinct_lineups": len(uniq),
               "pool": str(pool_path), "pool_rows": len(pool), "pool_sha256": hashlib.sha256(pool_path.read_bytes()).hexdigest(),
               "m2_caps": caps, "excluded_contests_outside_plan": excluded, "entered": entered, "monkeys": {}}
    for nm, D in (("M1", M1), ("M2", M2), ("M3", M3)):
        summary["monkeys"][nm] = {
            "median": {m: float(D[m].median()) for m in ("cashes", "mean", "ge100")},
            "q25": {m: float(D[m].quantile(0.25)) for m in ("cashes", "mean", "ge100")},
            "entered_percentile": {m: percentile(entered[m], D[m].to_numpy()) for m in ("cashes", "mean", "ge100")}}
        summary["monkeys"][nm]["reading_cashes"] = reading(summary["monkeys"][nm]["entered_percentile"]["cashes"])
    priv = MS.PRIVATE / "monkeys"; priv.mkdir(parents=True, exist_ok=True)
    pickle.dump({"M1": M1, "M2": M2, "M3": M3, "entered": entered, "cids": cids, "n_c": n_c}, open(priv / f"w{a.week}.pkl", "wb"))
    MS.PUBLIC.mkdir(parents=True, exist_ok=True)
    (MS.PUBLIC / f"monkeys_w{a.week}.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"MONKEY BENCHMARK W{a.week}  seed {seed}  books {a.books}  entries {total} in {len(cids)} contests; "
          f"pool {len(pool)} rows; M2 caps {caps}; excluded (outside the plan) {excluded}")
    print(f"  entered: cashes {entered['cashes']}  mean {entered['mean']:.2f}  share >= 100 {entered['ge100']:.3f}")
    for nm, s in summary["monkeys"].items():
        p = s["entered_percentile"]
        print(f"  {nm}: median cashes {s['median']['cashes']:.1f}, mean {s['median']['mean']:.2f}  |  the entered book's percentile: "
              f"cashes {p['cashes']:.1f}, mean {p['mean']:.1f}, >=100 {p['ge100']:.1f}  ->  {s['reading_cashes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
