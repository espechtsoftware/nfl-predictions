#!/usr/bin/env python3
"""Calibration of the then-model on the operator's REAL Weeks 1-4 entries (descriptive; changes nothing for Week 5).

The operator 10-09 ("I do want to do 3"), after the money-gate summary: was "about a 30% chance of a big win in a week"
ever true? The outside reviewer's design, approved with five notes; the laptop builds and runs it.

For every reconciled W1-4 entry (the money gate's known-answer path: 534 entries, contest 196305080 excluded, no ladder):
  the model's PRE-LOCK predicted probability of
    (a) a top-1% finish (rank <= max(1, floor(0.01 N)), N = the contest's entries),
    (b) a top-10% finish (rank <= max(1, floor(0.10 N))),
    (c) a cash (any cash or ticket),
    (d) a big win (cash >= $500 or a ticket worth >= $300: moneygate_describe's rule, his 10-05 rule),
  and its realized outcome from moneygate_score.place() on the real points (asserted equal to the reconcile file).

FIELD A (this script): each contest's REAL field rosters (all of our entries removed, as place() does), scored by the
week's T-70 score banks (incumbent_player_scores and corrected_hsim_player_scores, players x 10,000 sims each). The
opponents' rosters are not outcomes; this isolates the score model + our lineups from any field model.
  - Lineup totals are rounded to hundredths (DK's resolution) so identical rosters tie exactly; ranks and prizes follow
    DK's tie rule (Ladder.split: tied entries share the positions' prizes), as place() does.
  - A contest with more than --cap others uses a fixed-seed sample of --cap of them; counts are scaled to the full
    field (disclosed: the deepest Milly ranks are then estimated, not counted).
  - A field lineup holding a player who is not in the T-70 frame cannot be scored; it is left out of the sample and the
    known lineups stand for all others (exchangeability; the share is reported per week).
  - An entry of OURS holding such a player is excluded from every count, predicted and realized (reported, not silent).
  - The predictive distribution of each COUNT comes from the joint sims (entries in a week share each sim), not from a
    Poisson-binomial (independence would make the ranges far too narrow). Weeks are independent draws, so the pooled
    count in sim s is the sum of the weekly counts in sim s.
  - PIT: for each entry, P(model finish percentile < realized) + 0.5 P(=), in deciles; flat if calibrated.

What it calibrates: W1-4 ran our own score model (from W5 the book is solved on FP's means), so this checks the then-model's
sims: their centre, shape and spread, which the harness also uses.

Private per-entry rows go to ~/private/calibration/ (no dollars there either; ids only). The aggregate JSON + text (counts,
probabilities, no contest ids, no dollars) go to --out and stdout.

  python scripts/calibration_w1_4.py --out ~/private/calibration/run-<ts> [--weeks 1,2,3,4] [--cap 100000] [--chunk 500]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402  (the gate's loaders, ladders and place(); its pinned inputs)

BANKS = ("incumbent", "hsim")
BANK_FILES = {"incumbent": "incumbent_player_scores.npy", "hsim": "corrected_hsim_player_scores.npy"}
BUCKETS = ("top1", "top10", "cash", "big")
BIG_CASH, BIG_TICKET = 500.0, 300.0          # moneygate_describe.BIG_CASH / BIG_TICKET (his 10-05 rule)
OFFSET, BASE = 1_000_000, 500_000            # column offset and base (hundredths): a lineup total in (-5,000, +5,000) DK
                                             # points stays inside its own column


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cut(rank: np.ndarray, n: int, share: float) -> np.ndarray:
    return rank <= max(1, int(np.floor(share * n)))


def buckets(rank, cash, ticket, n_total: int) -> dict[str, np.ndarray]:
    return {"top1": cut(rank, n_total, 0.01), "top10": cut(rank, n_total, 0.10),
            "cash": (cash + ticket) > 1e-9, "big": (cash >= BIG_CASH - 1e-9) | (ticket >= BIG_TICKET - 1e-9)}


def roster_rows(names_col, row_of: dict[str, int]) -> np.ndarray:
    """(n, 9) frame rows; -1 where a name is not in the frame (or is ambiguous there)."""
    return np.array([[row_of.get(n, -1) for n in names] for names in names_col], dtype=np.int64).reshape(-1, 9)


def incidence(rows: np.ndarray, n_players: int) -> np.ndarray:
    x = np.zeros((len(rows), n_players), dtype=np.float32)
    for k in range(rows.shape[1]):
        np.add.at(x, (np.arange(len(rows)), rows[:, k]), 1.0)
    return x


def model_contest(bank: np.ndarray, x_field: np.ndarray, x_mine: np.ndarray, scale: float, n_oth: int,
                  n_total: int, lad: "MS.Ladder", pct_real: np.ndarray, chunk: int) -> tuple[dict, np.ndarray]:
    """Per entry x sim bucket indicators (uint8) for one contest and one bank, plus each entry's PIT."""
    n_s, m = x_field.shape[0], x_mine.shape[0]
    S = bank.shape[1]
    out = {b: np.zeros((m, S), dtype=np.uint8) for b in BUCKETS}
    pit_lt = np.zeros(m); pit_eq = np.zeros(m)
    for s0 in range(0, S, chunk):
        s1 = min(S, s0 + chunk); C = s1 - s0
        B = np.ascontiguousarray(bank[:, s0:s1], dtype=np.float32)
        off = (np.arange(C, dtype=np.int64) * OFFSET + BASE)[None, :]
        F = np.rint((x_field @ B) * 100.0).astype(np.int64) + off          # (n_s, C), hundredths + column offset
        E = np.rint((x_mine @ B) * 100.0).astype(np.int64)                  # (m, C)
        flat = np.sort(F, axis=None)
        q = (E + off).ravel()
        lo = np.searchsorted(flat, q, "left").reshape(m, C) - (np.arange(C) * n_s)[None, :]
        hi = np.searchsorted(flat, q, "right").reshape(m, C) - (np.arange(C) * n_s)[None, :]
        above, eq, below = (n_s - hi) * scale, (hi - lo) * scale, lo * scale
        own_above = (E[None, :, :] > E[:, None, :]).sum(axis=1)             # our other entries in this contest
        own_eq = (E[None, :, :] == E[:, None, :]).sum(axis=1)               # includes the entry itself
        rank = 1 + np.rint(above).astype(np.int64) + own_above
        ties = np.maximum(1, np.rint(eq).astype(np.int64) + own_eq)
        cash, ticket = lad.split(rank.ravel(), ties.ravel())
        bk = buckets(rank.ravel(), cash, ticket, n_total)
        for b in BUCKETS:
            out[b][:, s0:s1] = bk[b].reshape(m, C)
        pct = 100.0 * (below + 0.5 * eq) / max(n_oth, 1)
        pit_lt += (pct < pct_real[:, None] - 1e-9).sum(axis=1)
        pit_eq += (np.abs(pct - pct_real[:, None]) <= 1e-9).sum(axis=1)
    return out, (pit_lt + 0.5 * pit_eq) / S


def week_run(cfg: dict, w: int, cap: int, chunk: int, recon: pd.DataFrame, log) -> dict:
    W = MS.load_week(cfg, w)
    e = cfg["weeks"][str(w)]
    run = Path(e["t70_run"])
    pins = {"t70_frame": run / "frame.parquet", **{BANK_FILES[b]: run / BANK_FILES[b] for b in BANKS}}
    for key, p in pins.items():
        if sha256(p) != e["sha256"][key]:
            raise SystemExit(f"W{w}: {p} sha256 differs from the money gate's pin ({key})")
    fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
    bank = {b: np.load(run / BANK_FILES[b], mmap_mode="r") for b in BANKS}
    for b in BANKS:
        if bank[b].shape[0] != len(fr):
            raise SystemExit(f"W{w}: {b} bank has {bank[b].shape[0]} rows for a {len(fr)}-row frame")
    names = fr.display_name.map(MS.canon)
    dup = set(names[names.duplicated(keep=False)])
    row_of = {n: i for i, n in enumerate(names) if n not in dup}
    exclude = {str(k): v for k, v in (e.get("reconcile_exclude") or {}).items()}
    h = W.history
    rows_out, excluded = [], {}
    ind = {b: {k: [] for k in BUCKETS} for b in BANKS}
    stats = {"contests": 0, "contests_sampled": 0, "field_lineups": 0, "field_unknown": 0, "entries": 0,
             "entries_missing_player": 0, "missing_names": {}, "ambiguous_frame_names": len(dup)}
    for cid in sorted(set(h.Contest_Key)):
        if cid in exclude:
            excluded[cid] = exclude[cid]; continue
        if cid not in W.details:
            excluded[cid] = "no payout ladder"; continue
        lad = MS.Ladder.from_details(W.details[cid])
        fc = W.field[W.field.contest_id == cid]
        mine = fc[fc.entry_id.isin(set(h[h.Contest_Key == cid].Entry_Key))].reset_index(drop=True)
        n_total = len(fc)
        pts = np.array([MS.lineup_points(list(n), W.fpts)[0] for n in mine.names], dtype=np.int64)
        real = MS.place(pts, W.others_sorted(cid), lad)
        rr = recon[(recon.week == w) & (recon.contest_id.astype(str) == cid)].set_index("entry_id")
        for i, eid in enumerate(mine.entry_id):
            r = rr.loc[int(eid)] if int(eid) in rr.index else rr.loc[str(eid)]
            if not (int(real["rank"][i]) == int(r.rank_calc) and abs(float(real["cash"][i]) - float(r.cash_calc)) < 0.005
                    and abs(float(real["ticket"][i]) - float(r.ticket_calc)) < 0.005):
                raise SystemExit(f"W{w}: the realized path disagrees with the reconcile file for an entry (known-answer gate)")
        oth = fc[~fc.entry_id.isin(W.ours)]
        n_oth = len(oth)
        if n_oth > cap:
            oth = oth.sample(n=cap, random_state=int(cid) % (2 ** 32)); stats["contests_sampled"] += 1
        fr_rows = roster_rows(oth.names, row_of)
        known = (fr_rows >= 0).all(axis=1)
        stats["field_lineups"] += len(fr_rows); stats["field_unknown"] += int((~known).sum())
        for names_t, ok in zip(oth.names, known):
            if not ok:
                for n in names_t:
                    if n not in row_of:
                        stats["missing_names"][n] = stats["missing_names"].get(n, 0) + 1
        fr_rows = fr_rows[known]
        scale = n_oth / max(len(fr_rows), 1)
        my_rows = roster_rows(mine.names, row_of)
        ok_mine = (my_rows >= 0).all(axis=1)
        stats["entries"] += len(mine); stats["entries_missing_player"] += int((~ok_mine).sum())
        stats["contests"] += 1
        real_b = buckets(real["rank"], real["cash"], real["ticket"], n_total)
        x_field = incidence(fr_rows, len(fr))
        x_mine = incidence(np.where(my_rows >= 0, my_rows, 0), len(fr))
        pits = {}
        for b in BANKS:
            t0 = time.time()
            res, pit = model_contest(bank[b], x_field, x_mine, scale, n_oth, n_total, lad, np.asarray(real["pct"]), chunk)
            pits[b] = pit
            for k in BUCKETS:
                ind[b][k].append(res[k][ok_mine])
            log(f"  W{w} contest {stats['contests']:>2}: N {n_total:>7}  others scored {len(fr_rows):>6} (scale {scale:.2f})"
                f"  ours {len(mine):>3}  bank {b:9s} {time.time() - t0:6.1f}s")
        for i in range(len(mine)):
            if not ok_mine[i]:
                continue
            row = {"week": w, "contest_id": cid, "entry_id": str(mine.entry_id[i]), "n_entries": n_total,
                   "rank_real": int(real["rank"][i]), "pct_real": round(float(real["pct"][i]), 4)}
            for k in BUCKETS:
                row[f"{k}_real"] = int(real_b[k][i])
            for b in BANKS:
                row[f"pit_{b}"] = round(float(pits[b][i]), 6)
            rows_out.append(row)
    k_ok = len(rows_out)
    for b in BANKS:
        for k in BUCKETS:
            ind[b][k] = np.concatenate(ind[b][k], axis=0) if ind[b][k] else np.zeros((0, 10000), np.uint8)
        for k in BUCKETS:
            p = ind[b][k].mean(axis=1)
            for i in range(k_ok):
                rows_out[i][f"p_{k}_{b}"] = round(float(p[i]), 6)
    stats["excluded"] = excluded
    stats["missing_names"] = dict(sorted(stats["missing_names"].items(), key=lambda kv: -kv[1])[:15])
    return {"rows": rows_out, "ind": ind, "stats": stats}


def summarize(counts: np.ndarray, realized: int) -> dict:
    return {"predicted_mean": round(float(counts.mean()), 3),
            "range90": [int(np.percentile(counts, 5)), int(np.percentile(counts, 95))],
            "realized": int(realized),
            "p_at_or_below_realized": round(float((counts <= realized).mean()), 4),
            "p_at_or_above_realized": round(float((counts >= realized).mean()), 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--weeks", default="1,2,3,4")
    ap.add_argument("--cap", type=int, default=100_000)
    ap.add_argument("--chunk", type=int, default=500)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists (create-once)")
    a.out.mkdir(parents=True)
    logf = open(a.out / "run.log", "w")

    def log(s):
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    cfg = MS.load_config()
    recon = pd.read_csv(MS.PRIVATE / "reconcile_entries.csv")
    weeks = [int(x) for x in a.weeks.split(",")]
    log(f"calibration W{weeks} cap {a.cap} chunk {a.chunk} script {sha256(Path(__file__))[:12]} "
        f"scorer {sha256(MS.SCORER)[:12]} reconcile {sha256(MS.PRIVATE / 'reconcile_entries.csv')[:12]}")
    res = {w: week_run(cfg, w, a.cap, a.chunk, recon, log) for w in weeks}
    rows = [r for w in weeks for r in res[w]["rows"]]
    pd.DataFrame(rows).to_csv(a.out / "entries.csv", index=False)

    summary = {"weeks": weeks, "cap": a.cap, "stats": {w: res[w]["stats"] for w in weeks}, "buckets": {}, "p_any_big": {},
               "pit_deciles": {}}
    views = {"incumbent": ("incumbent",), "hsim": ("hsim",), "pooled": BANKS}
    for v, bs in views.items():
        for k in BUCKETS:
            per_week = {}
            pooled_counts = None
            for w in weeks:
                real = sum(r[f"{k}_real"] for r in res[w]["rows"])
                c = np.concatenate([res[w]["ind"][b][k].sum(axis=0) for b in bs]).astype(np.int64)
                per_week[w] = summarize(c, real)
                pooled_counts = c if pooled_counts is None else pooled_counts + c
            real_all = sum(r[f"{k}_real"] for r in rows)
            per_week["all"] = summarize(pooled_counts, real_all)
            summary["buckets"].setdefault(v, {})[k] = per_week
        pab = {}
        for w in weeks:
            c = np.concatenate([res[w]["ind"][b]["big"].sum(axis=0) for b in bs])
            pab[w] = {"predicted": round(float((c >= 1).mean()), 4),
                      "realized": int(any(r["big_real"] for r in res[w]["rows"]))}
        summary["p_any_big"][v] = pab
        pit = np.array([np.mean([r[f"pit_{b}"] for b in bs]) for r in rows])
        wk = np.array([r["week"] for r in rows])
        dec = {"all": np.histogram(pit, bins=np.linspace(0, 1, 11))[0].tolist()}
        for w in weeks:
            dec[w] = np.histogram(pit[wk == w], bins=np.linspace(0, 1, 11))[0].tolist()
        summary["pit_deciles"][v] = dec
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    log("\n== SUMMARY (counts of entries; predicted = the model's mean count; range90 = the 5th-95th percentile of the "
        "count over the joint sims)")
    for v in views:
        log(f"-- view {v}")
        for k in BUCKETS:
            for w, s in summary["buckets"][v][k].items():
                log(f"   {k:6s} W{w!s:4s} predicted {s['predicted_mean']:8.2f}  range90 {s['range90']}  realized {s['realized']:4d}"
                    f"  P(<= realized) {s['p_at_or_below_realized']:.3f}  P(>= realized) {s['p_at_or_above_realized']:.3f}")
        for w, s in summary["p_any_big"][v].items():
            log(f"   P(>= 1 big win) W{w}: predicted {s['predicted']:.3f}  realized {s['realized']}")
        log(f"   PIT deciles (flat if calibrated; low deciles = finished worse than the model expected): "
            f"{summary['pit_deciles'][v]}")
    for w in weeks:
        st = res[w]["stats"]
        log(f"-- W{w} stats: contests {st['contests']} (sampled {st['contests_sampled']}), entries {st['entries']}, "
            f"ours with a player missing from the frame {st['entries_missing_player']}, field lineups scored "
            f"{st['field_lineups'] - st['field_unknown']} of {st['field_lineups']} sampled ({st['field_unknown']} unknown), "
            f"ambiguous frame names {st['ambiguous_frame_names']}, excluded {list(st['excluded'].values())}")
        log(f"   most-missing field names: {st['missing_names']}")
    log(f"== done {time.strftime('%H:%M:%S')}  entries {len(rows)}  out {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
