#!/usr/bin/env python3
"""Study row 69: pool hit density on the real settled fields (descriptive; it gates nothing).

The outside review of 10-06 (§2.1): selection inside a good pool is about chance, so the quantity that moves the odds of
a big win is how many of the rows we COULD enter would have reached a big result. For the T-70 pool and for the entered
book, it reports per big contest the share of rows that, entered ALONE into that contest's real field, would have taken
a big seat, plus the chance that 26 rows drawn at chance from that set would hold at least one.

Inputs:
  pre-lock   --t70-run   the T-70 run directory: candidates.parquet (the generated pool; `players` = frame ids) and
                         frame.parquet (frame id -> DraftKings player id);
             --union     the entered union's directory: book.csv (the DraftKings upload, one DK player id per slot);
             --plan      the week's s24 plan (the lab's scripts/s38_plan.py, as P3 uses it): contest_id, big, seats.
  post-lock  the real settled fields through scripts/moneygate_score.py: load_week (DraftKings' own per-player fpts in
             integer hundredths, every contest's real standings and payout ladder) and Week.others_sorted (the field
             without ANY real entry of ours). It runs only behind the money gate's reconcile receipt, as P3 does.
A row's points are moneygate_score.lineup_points (a name nobody in the field rostered scores 0 and is counted). A row
clears contest c when it would finish at rank <= seats placed ALONE among c's real entrants (moneygate_score.place; P3's
big rule), i.e. its points >= c's line = the seats-th best real score of the others (checked against place()).
  d                       the share of DISTINCT pool rows (and of book rows) that clear; d_all over every generated row
  P(>=1 | 26 at chance)   1 - (1 - d) ** 26
  5-95%                   a cluster bootstrap over each row's QB game (B 2000, seed 1)

    python scripts/pool_hit_density.py --season 2026 --week 5 --t70-run <T-70 run dir> --union <entered union dir> \\
        --plan <plan-w05-s24.json> --out-dir ~/private/pool-hit-density [--summary <path>]
Writes PRIVATE rows (<out-dir>/phd-S-wWW.parquet + .json: every row's points and the contests it clears). Prints
aggregates only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
B, SEED, K = 2000, 1, 26
CAVEAT = ("The T-70 pool is generated from OUR projections; the book's rows are solved on FP's (since W5). d_pool measures "
          "our pool, not FP's book.")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------------------------------- pure parts
def contest_line(others_sorted: np.ndarray, seats: int) -> int:
    """The lowest score (hundredths) that finishes at rank <= seats when entered ALONE: the seats-th best other score
    (rank = 1 + the others strictly above). With seats >= the field, any score clears."""
    o = np.asarray(others_sorted, dtype=np.int64)
    if seats <= 0:
        raise ValueError("seats must be positive")
    if seats > len(o):
        return int(np.iinfo(np.int64).min)
    return int(o[len(o) - seats])


def implied(d: float, k: int = K) -> float:
    return float(1.0 - (1.0 - d) ** k)


def cluster_boot(clears: np.ndarray, clusters: np.ndarray, b: int = B, seed: int = SEED) -> tuple[float, float]:
    """5-95% of the share clearing, resampling whole clusters (the row's QB game) with replacement."""
    if len(clears) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    keys, inv = np.unique(clusters, return_inverse=True)
    hit = np.bincount(inv, weights=clears.astype(float), minlength=len(keys)); n = np.bincount(inv, minlength=len(keys))
    draws = rng.integers(0, len(keys), size=(b, len(keys)))
    v = hit[draws].sum(axis=1) / np.maximum(n[draws].sum(axis=1), 1)
    return float(np.percentile(v, 5)), float(np.percentile(v, 95))


def read_pool(cands: pd.DataFrame, id_to_dk: dict[str, str]) -> tuple[list[tuple[str, ...]], list[str], dict]:
    """The pool's rows as tuples of DraftKings player ids (sorted), their tags, and counts."""
    rows, tags, unmapped = [], [], 0
    for players, tag in zip(cands["players"].astype(str), cands.get("tag", pd.Series("", index=cands.index)).astype(str)):
        ids = [p for p in players.split(",") if p]
        dk = [id_to_dk.get(p) for p in ids]
        if any(x is None for x in dk) or len(ids) != 9:
            unmapped += 1; continue
        rows.append(tuple(sorted(dk))); tags.append(tag)
    return rows, tags, {"pool_rows": int(len(cands)), "pool_unmapped": unmapped, "pool_used": len(rows), "pool_distinct": len(set(rows))}


def read_book(path: Path) -> list[tuple[str, ...]]:
    with Path(path).open(newline="") as f:
        r = list(csv.reader(f))
    out = []
    for row in r[1:]:
        ids = [c.strip().split("(")[-1].rstrip(")").strip() for c in row if c.strip()]
        ids = [x[:-2] if x.endswith(".0") else x for x in ids]
        if len(ids) != 9:
            raise SystemExit(f"POOL HIT DENSITY REFUSED: a book row has {len(ids)} players: {row}")
        out.append(tuple(sorted(ids)))
    return out


# ------------------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--t70-run", type=Path, required=True); ap.add_argument("--union", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True); ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--summary", type=Path, default=None)
    a = ap.parse_args(argv)
    M = _load("moneygate_score"); P3 = _load("p3_score")
    rec = json.loads(M.receipt_path().read_text()) if M.receipt_path().is_file() else {}
    if a.week not in rec.get("weeks", []):
        raise SystemExit(f"POOL HIT DENSITY REFUSED: the reconcile receipt does not cover week {a.week} (run moneygate_score.py reconcile)")
    M.require_reconcile(sorted(rec["weeks"]))                    # PASS, this scorer's sha, the week's data unchanged
    cfg = M.load_config()
    W = M.load_week(cfg, a.week)
    cfg_frame = Path(cfg["weeks"][str(a.week)]["t70_run"]) / "frame.parquet"
    frame_p, cands_p, book_p = a.t70_run / "frame.parquet", a.t70_run / "candidates.parquet", a.union / "book.csv"
    for p in (frame_p, cands_p, book_p, a.plan):
        if not p.is_file():
            raise SystemExit(f"POOL HIT DENSITY REFUSED: {p} is missing")
    if sha256(frame_p) != sha256(cfg_frame):
        raise SystemExit(f"POOL HIT DENSITY REFUSED: --t70-run's frame is not the money gate's W{a.week} frame ({cfg_frame})")
    fr = pd.read_parquet(frame_p).drop_duplicates("id")
    id_to_dk = {str(i): str(k).removesuffix(".0") for i, k in zip(fr["id"].astype(str), fr["dk_player_id"].astype(str))}
    qb_game = {str(k).removesuffix(".0"): g for k, g, p in zip(fr["dk_player_id"].astype(str), fr["game_id"].astype(str), fr["pos"].astype(str)) if p == "QB"}
    big = P3.plan_big(a.plan)
    contests = [c for c in W.contests if big.get(str(c["contest_id"]), (False, 0))[0]]
    if not contests:
        raise SystemExit("POOL HIT DENSITY REFUSED: the plan marks none of the week's contests big")
    pool, tags, counts = read_pool(pd.read_parquet(cands_p), id_to_dk)
    book = read_book(book_p)

    def score(rows):
        pts, miss = [], 0
        for r in rows:
            names = [W.name_of[x] for x in r]
            p, m = M.lineup_points(names, W.fpts, impute_missing=True); pts.append(p); miss += len(m)
        return np.asarray(pts, dtype=np.int64), miss

    def qb_of(rows):
        out = []
        for r in rows:
            g = [qb_game[x] for x in r if x in qb_game]
            out.append(g[0] if g else "none")
        return np.asarray(out)

    distinct = sorted(set(pool))
    pts_all, miss_pool = score(pool); pts_d, _ = score(distinct); pts_b, miss_book = score(book)
    qb_d, qb_b = qb_of(distinct), qb_of(book)
    lines, per = {}, []
    clear_d = np.zeros((len(distinct), len(contests)), bool); clear_b = np.zeros((len(book), len(contests)), bool)
    for j, c in enumerate(contests):
        cid = str(c["contest_id"]); seats = big[cid][1]
        others = W.others_sorted(cid); lad = M.Ladder.from_details(W.details[cid])
        line = contest_line(others, seats)
        if line > np.iinfo(np.int64).min:                         # the line, checked against the money gate's own place()
            assert M.place(np.array([line]), others, lad)["rank"][0] <= seats
            assert M.place(np.array([line - 1]), others, lad)["rank"][0] > seats
        cls = M.contest_class(W.details[cid]["name"])
        clear_d[:, j] = pts_d >= line; clear_b[:, j] = pts_b >= line
        d_pool, d_all, d_book = float(clear_d[:, j].mean()), float((pts_all >= line).mean()), float(clear_b[:, j].mean()) if len(book) else float("nan")
        lo_p, hi_p = cluster_boot(clear_d[:, j], qb_d); lo_b, hi_b = cluster_boot(clear_b[:, j], qb_b)
        lines[cid] = {"name": c.get("name"), "class": cls, "seats": seats, "line": line / 100.0, "field_others": int(len(others))}
        per.append({"cid": cid, "name": c.get("name") or cid, "class": cls, "seats": seats, "line": line / 100.0,
                    "d_pool": d_pool, "d_pool_all": d_all, "pool_lo": lo_p, "pool_hi": hi_p, "p26_pool": implied(d_pool),
                    "d_book": d_book, "book_lo": lo_b, "book_hi": hi_b, "p26_book": implied(d_book) if len(book) else float("nan")})
    a.out_dir.mkdir(parents=True, exist_ok=True)
    stem = a.out_dir / f"phd-{a.season}-w{a.week:02d}"
    cid_list = [str(c["contest_id"]) for c in contests]
    rows = pd.DataFrame({"row": ["|".join(r) for r in distinct] + ["|".join(r) for r in book],
                         "source": ["pool"] * len(distinct) + ["book"] * len(book),
                         "points": np.concatenate([pts_d, pts_b]) / 100.0, "qb_game": np.concatenate([qb_d, qb_b]),
                         "clears": [",".join(np.array(cid_list)[m]) for m in np.vstack([clear_d, clear_b])]})
    rows.to_parquet(f"{stem}.parquet")
    side = {**counts, "book_rows": len(book), "missing_names_pool": miss_pool, "missing_names_book": miss_book,
            "inputs": {"candidates": str(cands_p), "candidates_sha256": sha256(cands_p), "frame_sha256": sha256(frame_p),
                       "book": str(book_p), "book_sha256": sha256(book_p), "plan": str(a.plan), "plan_sha256": sha256(a.plan),
                       "scorer_sha256": M.sha256(M.SCORER), "week_receipt": json.loads((M.data_dir() / f"w{a.week}_receipt.json").read_text())},
            "lines": lines, "rows_sha256": sha256(Path(f"{stem}.parquet")), "written_utc": datetime.now(timezone.utc).isoformat()}
    Path(f"{stem}.json").write_text(json.dumps(side, indent=1, default=str) + "\n")

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"== POOL HIT DENSITY {a.season} W{a.week} -- descriptive, gates nothing. A row clears a big contest when, entered "
              f"ALONE into its real field (our real entries removed), it would finish inside the seats (P3's big rule).")
        print(f"   {CAVEAT}")
        print(f"   pool: {counts['pool_rows']} generated rows, {counts['pool_distinct']} distinct ({counts['pool_unmapped']} unmapped); "
              f"book: {len(book)} rows; names nobody rostered (scored 0): pool {miss_pool}, book {miss_book}")
        print(f"   d = share of distinct pool rows / book rows clearing; P26 = 1 - (1 - d)^26; [5-95%] cluster bootstrap over "
              f"the row's QB game, B {B}, seed {SEED}")
        for r in per:
            print(f"   {r['name']:14s} {r['class']:20s} seats {r['seats']:>4d}  line {r['line']:7.2f}   pool d {r['d_pool']:.4f} "
                  f"[{r['pool_lo']:.4f}, {r['pool_hi']:.4f}] (all rows {r['d_pool_all']:.4f}) P26 {r['p26_pool']:.3f}   "
                  f"book d {r['d_book']:.4f} [{r['book_lo']:.4f}, {r['book_hi']:.4f}] P26 {r['p26_book']:.3f}")
        cl = pd.DataFrame(per).groupby("class").agg(contests=("cid", "size"), median_line=("line", "median"),
                                                    d_pool=("d_pool", "mean"), d_book=("d_book", "mean"))
        print("   by class (mean d over the class's contests):")
        for k, r in cl.iterrows():
            print(f"      {k:20s} contests {int(r.contests):2d}  median line {r.median_line:7.2f}  pool d {r.d_pool:.4f} "
                  f"(P26 {implied(r.d_pool):.3f})  book d {r.d_book:.4f} (P26 {implied(r.d_book):.3f})")
        any_d = clear_d.any(axis=1).mean() if len(distinct) else float("nan")
        any_b = clear_b.any(axis=1).mean() if len(book) else float("nan")
        print(f"   any big contest: pool d {any_d:.4f}  book d {any_b:.4f}")
    text = buf.getvalue()
    print(text, end="")
    if a.summary:
        a.summary.parent.mkdir(parents=True, exist_ok=True)
        with a.summary.open("a") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
