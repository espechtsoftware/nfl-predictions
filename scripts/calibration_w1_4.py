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
  - FAIL CLOSED (the outside reviewer's review of fd09493b): bank row i must be frame row i (the incumbent bank's row means
    equal the frame's mean_projection; the hsim bank correlates >= 0.90 with it); every one of OUR entries must map to frame
    players; a contest's field may hold at most --max-unknown (2%) lineups with a player not in the frame (one lineup is always
    tolerated: a 23-entry W4 contest has one), and never none scorable; every contest's entries must be in the field
    (history rows = placed + excluded; placed = the gate's 534).
    --prepass runs these checks without sims (seconds).
  - A field lineup holding a player who is not in the T-70 frame cannot be scored; it is left out of the sample and the
    known lineups stand for all others (exchangeability; the share is reported). Such a player is often a late scratch, so
    dropping them makes the field slightly stronger and our predictions lean low; --unknown-zero is the sensitivity that
    scores him at 0 in every sim instead.
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


UNKNOWN, EMPTY = -1, -2                     # a name not in the frame (or ambiguous there); an empty roster slot


def roster_rows(names_col, row_of: dict[str, int]) -> np.ndarray:
    """(n, 9) frame rows; UNKNOWN where a name is not in the frame (or is ambiguous there); EMPTY for the slots of a
    lineup that was never set (W4's field has 314 such entries, 0 DK points; they stay in the field at 0)."""
    out = np.full((len(names_col), 9), EMPTY, dtype=np.int64)
    for i, names in enumerate(names_col):
        nm = [n for n in names if n]
        if len(nm) > 9:
            raise SystemExit(f"a lineup with {len(nm)} players")
        out[i, :len(nm)] = [row_of.get(n, UNKNOWN) for n in nm]
    return out


def incidence(rows: np.ndarray, n_players: int) -> np.ndarray:
    x = np.zeros((len(rows), n_players), dtype=np.float32)
    for k in range(rows.shape[1]):
        m = rows[:, k] >= 0
        np.add.at(x, (np.arange(len(rows))[m], rows[m, k]), 1.0)
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


def check_alignment(w: int, fr: pd.DataFrame, bank: dict[str, np.ndarray]) -> dict:
    """Fail closed unless bank row i is frame row i (review A): the incumbent bank's row means ARE the frame's
    mean_projection (the writer stores one from the other; candidates' sel_mean is their lineup sum), and the corrected
    hsim bank (re-centred, so not equal) tracks the same players (a permuted bank would correlate near 0)."""
    proj = pd.to_numeric(fr["mean_projection"], errors="coerce").to_numpy(float)
    ok = np.isfinite(proj)
    mi = np.asarray(bank["incumbent"]).mean(axis=1); mh = np.asarray(bank["hsim"]).mean(axis=1)
    gap = float(np.abs(mi[ok] - proj[ok]).max())
    r_h = float(np.corrcoef(mh[ok], proj[ok])[0, 1])
    if ok.sum() < 0.95 * len(fr) or gap > 0.01 or r_h < 0.90:
        raise SystemExit(f"W{w}: bank rows do not line up with the frame (incumbent max gap {gap:.3f}, hsim r {r_h:.3f}, "
                         f"{int(ok.sum())} of {len(fr)} projections)")
    return {"incumbent_max_gap_vs_mean_projection": round(gap, 5), "hsim_r_vs_mean_projection": round(r_h, 4)}


def name_maps(fr: pd.DataFrame, unknown_zero: bool):
    names = fr.display_name.map(MS.canon)
    dup = set(names[names.duplicated(keep=False)])
    row_of = {n: i for i, n in enumerate(names) if n not in dup}
    return row_of, dup


def week_run(cfg: dict, w: int, cap: int, chunk: int, recon: pd.DataFrame, log, max_unknown: float,
             unknown_zero: bool, prepass: bool, recentre_fp: Path | None = None) -> dict:
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
    align = check_alignment(w, fr, bank)
    if recentre_fp is not None:                              # Field A': each player's sims shifted to FP's pre-lock mean
        fp = pd.read_csv(recentre_fp, dtype={"id": str}).drop_duplicates("id").set_index("id")["fp"]
        target = pd.to_numeric(fr.id.astype(str).map(fp), errors="coerce").to_numpy(float)
        cov = np.isfinite(target)
        if cov.mean() < 0.95:
            raise SystemExit(f"W{w}: FP projections cover {cov.mean():.1%} of the frame (< 95%)")
        bank = {b: (np.asarray(bank[b], dtype=np.float32)
                    + np.where(cov, target - np.asarray(bank[b]).mean(axis=1), 0.0)[:, None].astype(np.float32)) for b in BANKS}
        align["recentred_on_fp"] = {"file_sha256": sha256(Path(recentre_fp))[:12], "covered": round(float(cov.mean()), 4)}
    row_of, dup = name_maps(fr, unknown_zero)
    P = len(fr)
    if unknown_zero:                                         # review F: the sensitivity, unknown players at 0 in every sim
        bank = {b: np.vstack([np.asarray(bank[b], dtype=np.float32), np.zeros((1, bank[b].shape[1]), np.float32)])
                for b in BANKS}
    exclude = {str(k): v for k, v in (e.get("reconcile_exclude") or {}).items()}
    h = W.history
    rec_w = recon[recon.week == w]
    rows_out, excluded = [], {}
    ind = {b: {k: [] for k in BUCKETS} for b in BANKS}
    stats = {"alignment": align, "contests": 0, "contests_sampled": 0, "field_lineups": 0, "field_unknown": 0,
             "entries_placed": 0, "entries_missing_player": 0, "missing_names": {}, "ambiguous_frame_names": sorted(dup),
             "max_contest_unknown_share": 0.0, "field_empty_lineups": 0, "excluded_entries_by_reason": {}, "unknown_zero": unknown_zero}
    problems = []
    for cid in sorted(set(h.Contest_Key)):
        n_hist = int((h.Contest_Key == cid).sum())
        reason = exclude.get(cid) or (None if cid in W.details else "no payout ladder")
        if reason:
            excluded[cid] = reason
            stats["excluded_entries_by_reason"][reason] = stats["excluded_entries_by_reason"].get(reason, 0) + n_hist
            continue
        lad = MS.Ladder.from_details(W.details[cid])
        fc = W.field[W.field.contest_id == cid]
        mine = fc[fc.entry_id.isin(set(h[h.Contest_Key == cid].Entry_Key))].reset_index(drop=True)
        if len(mine) != n_hist:                              # review C: coverage, never silently empty
            raise SystemExit(f"W{w}: a contest has {n_hist} entries in the history but {len(mine)} in the field")
        n_total = len(fc)
        oth = fc[~fc.entry_id.isin(W.ours)]
        n_oth = len(oth)
        if n_oth > cap:
            oth = oth.sample(n=cap, random_state=int(cid) % (2 ** 32)); stats["contests_sampled"] += 1
        fr_rows = roster_rows(oth.names, row_of)
        known = (fr_rows != UNKNOWN).all(axis=1)
        share = float((~known).mean()) if len(known) else 0.0
        stats["field_lineups"] += len(fr_rows); stats["field_unknown"] += int((~known).sum())
        stats["field_empty_lineups"] += int((fr_rows == EMPTY).all(axis=1).sum())
        stats["max_contest_unknown_share"] = max(stats["max_contest_unknown_share"], round(share, 5))
        for names_t, ok in zip(oth.names, known):
            if not ok:
                for n in names_t:
                    if n and n not in row_of:
                        stats["missing_names"][n] = stats["missing_names"].get(n, 0) + 1
        my_rows = roster_rows(mine.names, row_of)
        ok_mine = (my_rows >= 0).all(axis=1)
        if (~ok_mine).any():
            miss = sorted({n or "(empty slot)" for names_t, ok in zip(mine.names, ok_mine) if not ok for n in names_t if n not in row_of})
            problems.append(f"W{w}: {int((~ok_mine).sum())} of our entries in a contest hold players not in the frame: {miss}")
        if not known.any() and len(known):
            problems.append(f"W{w}: a contest has no scorable field lineup")
        n_unk = int((~known).sum())
        if n_unk > max(1, int(np.floor(max_unknown * len(known)))) and not unknown_zero:   # one lineup is always tolerated
            problems.append(f"W{w}: a contest's field has {n_unk} of {len(known)} lineups ({share:.1%}) with a player not in "
                            f"the frame (> {max_unknown:.0%} and > 1)")
        stats["entries_placed"] += len(mine); stats["entries_missing_player"] += int((~ok_mine).sum())
        stats["contests"] += 1
        if prepass:
            continue
        if problems:
            raise SystemExit("FAIL CLOSED (review B):\n  " + "\n  ".join(problems))
        pts = np.array([MS.lineup_points(list(n), W.fpts)[0] for n in mine.names], dtype=np.int64)
        real = MS.place(pts, W.others_sorted(cid), lad)
        rr = rec_w[rec_w.contest_id.astype(str) == cid].assign(entry_id=lambda d: d.entry_id.astype(str)).set_index("entry_id")
        if len(rr) != len(mine):
            raise SystemExit(f"W{w}: a contest has {len(mine)} placed entries but {len(rr)} reconcile rows")
        for i, eid in enumerate(mine.entry_id.astype(str)):
            r = rr.loc[eid]
            if not (int(real["rank"][i]) == int(r.rank_calc) and abs(float(real["cash"][i]) - float(r.cash_calc)) < 0.005
                    and abs(float(real["ticket"][i]) - float(r.ticket_calc)) < 0.005):
                raise SystemExit(f"W{w}: the realized path disagrees with the reconcile file for an entry (known-answer gate)")
        if unknown_zero:
            fr_rows = np.where(fr_rows == UNKNOWN, P, fr_rows)
        else:
            fr_rows = fr_rows[known]
        scale = n_oth / max(len(fr_rows), 1)
        real_b = buckets(real["rank"], real["cash"], real["ticket"], n_total)
        width = P + 1 if unknown_zero else P
        x_field = incidence(fr_rows, width)
        x_mine = incidence(my_rows, width)                   # review E: every one of ours is scorable here (fail-closed)
        pits = {}
        for b in BANKS:
            t0 = time.time()
            res, pit = model_contest(bank[b], x_field, x_mine, scale, n_oth, n_total, lad, np.asarray(real["pct"]), chunk)
            pits[b] = pit
            for k in BUCKETS:
                ind[b][k].append(res[k])
            log(f"  W{w} contest {stats['contests']:>2}: N {n_total:>7}  others scored {len(fr_rows):>6} (scale {scale:.3f})"
                f"  ours {len(mine):>3}  bank {b:9s} {time.time() - t0:6.1f}s")
        for i in range(len(mine)):
            row = {"week": w, "contest_id": cid, "entry_id": str(mine.entry_id[i]), "n_entries": n_total,
                   "rank_real": int(real["rank"][i]), "pct_real": round(float(real["pct"][i]), 4)}
            for k in BUCKETS:
                row[f"{k}_real"] = int(real_b[k][i])
            for b in BANKS:
                row[f"pit_{b}"] = round(float(pits[b][i]), 6)
            rows_out.append(row)
    n_excl = sum(stats["excluded_entries_by_reason"].values())
    if stats["entries_placed"] + n_excl != len(h):            # review C: placed + excluded == the history
        raise SystemExit(f"W{w}: placed {stats['entries_placed']} + excluded {n_excl} != {len(h)} history rows")
    if stats["entries_placed"] != len(rec_w):
        raise SystemExit(f"W{w}: placed {stats['entries_placed']} != {len(rec_w)} reconcile rows (the gate's entries)")
    stats["excluded"] = excluded
    stats["missing_names"] = dict(sorted(stats["missing_names"].items(), key=lambda kv: -kv[1])[:20])
    if prepass:
        stats["problems"] = problems
        return {"rows": [], "ind": None, "stats": stats}
    k_ok = len(rows_out)
    for b in BANKS:
        for k in BUCKETS:
            ind[b][k] = np.concatenate(ind[b][k], axis=0) if ind[b][k] else np.zeros((0, 10000), np.uint8)
            p = ind[b][k].mean(axis=1)
            for i in range(k_ok):
                rows_out[i][f"p_{k}_{b}"] = round(float(p[i]), 6)
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
    ap.add_argument("--max-unknown", type=float, default=0.02, help="fail closed above this share of unscorable field lineups")
    ap.add_argument("--unknown-zero", action="store_true", help="sensitivity: score players not in the frame at 0 in every sim")
    ap.add_argument("--prepass", action="store_true", help="names and coverage only, no sims (seconds)")
    ap.add_argument("--recentre-fp", type=Path, default=None,
                    help="Field A': shift every player's sims to FP's pre-lock mean (a CSV with id, fp; one week only)")
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists (create-once)")
    a.out.mkdir(parents=True)
    logf = open(a.out / "run.log", "w")

    def log(s):
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    cfg = MS.load_config()
    recon = pd.read_csv(MS.PRIVATE / "reconcile_entries.csv", dtype={"entry_id": str, "contest_id": str})
    weeks = [int(x) for x in a.weeks.split(",")]
    if a.recentre_fp is not None and len(weeks) != 1:
        raise SystemExit("--recentre-fp takes one week (its FP file)")
    log(f"calibration W{weeks} cap {a.cap} chunk {a.chunk} max_unknown {a.max_unknown} unknown_zero {a.unknown_zero} "
        f"prepass {a.prepass} script {sha256(Path(__file__))[:12]} scorer {sha256(MS.SCORER)[:12]} "
        f"reconcile {sha256(MS.PRIVATE / 'reconcile_entries.csv')[:12]} ({len(recon)} rows)")
    t_start = time.time()
    res = {}
    for w in weeks:
        t0 = time.time()
        res[w] = week_run(cfg, w, a.cap, a.chunk, recon, log, a.max_unknown, a.unknown_zero, a.prepass, a.recentre_fp)
        st = res[w]["stats"]
        log(f"-- W{w} {time.time() - t0:6.1f}s: contests {st['contests']} (sampled {st['contests_sampled']}), entries placed "
            f"{st['entries_placed']}, excluded by reason {st['excluded_entries_by_reason']}, ours with a player not in the frame "
            f"{st['entries_missing_player']}, field lineups unscorable {st['field_unknown']} of {st['field_lineups']} "
            f"(max contest share {st['max_contest_unknown_share']:.2%}), empty field lineups (0 points) {st['field_empty_lineups']}, ambiguous frame names {st['ambiguous_frame_names']}, "
            f"alignment {st['alignment']}")
        log(f"   names not in the frame (field lineups holding each, top 20): {st['missing_names']}")
        if a.prepass and st.get("problems"):
            log("   PROBLEMS: " + " | ".join(st["problems"]))
    if set(weeks) == {1, 2, 3, 4} and sum(res[w]["stats"]["entries_placed"] for w in weeks) != len(recon):
        raise SystemExit(f"placed entries != the gate's {len(recon)} (review C)")
    if a.prepass:
        log(f"== prepass done {time.strftime('%H:%M:%S')}")
        return 0
    rows = [r for w in weeks for r in res[w]["rows"]]
    pd.DataFrame(rows).to_csv(a.out / "entries.csv", index=False)

    summary = {"weeks": weeks, "cap": a.cap, "unknown_zero": a.unknown_zero, "stats": {w: res[w]["stats"] for w in weeks},
               "buckets": {}, "p_any_big": {}, "headline": {}, "pit_deciles": {}, "pit_week_mean": {}}
    views = {"incumbent": ("incumbent",), "hsim": ("hsim",), "pooled": BANKS}
    for v, bs in views.items():
        for k in BUCKETS:
            per_week, pooled_counts = {}, None
            for w in weeks:
                real = sum(r[f"{k}_real"] for r in res[w]["rows"])
                c = np.concatenate([res[w]["ind"][b][k].sum(axis=0) for b in bs]).astype(np.int64)
                per_week[w] = summarize(c, real)
                pooled_counts = c if pooled_counts is None else pooled_counts + c
            per_week["all"] = summarize(pooled_counts, sum(r[f"{k}_real"] for r in rows))
            summary["buckets"].setdefault(v, {})[k] = per_week
            if k == "big":
                summary["headline"].setdefault(v, {})["p_no_big_win_all_weeks"] = round(float((pooled_counts == 0).mean()), 4)
        pab = {}
        for w in weeks:
            c = np.concatenate([res[w]["ind"][b]["big"].sum(axis=0) for b in bs])
            pab[w] = {"predicted": round(float((c >= 1).mean()), 4), "realized": int(any(r["big_real"] for r in res[w]["rows"]))}
        summary["p_any_big"][v] = pab
        summary["headline"][v]["mean_weekly_p_any_big"] = round(float(np.mean([pab[w]["predicted"] for w in weeks])), 4)
        pit = np.array([np.mean([r[f"pit_{b}"] for b in bs]) for r in rows])
        wk = np.array([r["week"] for r in rows])
        dec = {"all": np.histogram(pit, bins=np.linspace(0, 1, 11))[0].tolist()}
        for w in weeks:
            dec[w] = np.histogram(pit[wk == w], bins=np.linspace(0, 1, 11))[0].tolist()
        summary["pit_deciles"][v] = dec
        summary["pit_week_mean"][v] = {w: round(float(pit[wk == w].mean()), 4) for w in weeks}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    log("\n== SUMMARY (counts of entries; predicted = the model's mean count; range90 = the 5th-95th percentile of the "
        "count over the joint sims; the weeks are the independent units)")
    for v in views:
        hd = summary["headline"][v]
        log(f"-- view {v}: the model's per-week chance of >= 1 big win on his real entries and real fields (mean of the "
            f"weeks) {hd['mean_weekly_p_any_big']:.3f}; its chance of NO big win in all of W{weeks} {hd['p_no_big_win_all_weeks']:.3f}")
        for k in BUCKETS:
            for w, s in summary["buckets"][v][k].items():
                log(f"   {k:6s} W{w!s:4s} predicted {s['predicted_mean']:8.2f}  range90 {s['range90']}  realized {s['realized']:4d}"
                    f"  P(<= realized) {s['p_at_or_below_realized']:.3f}  P(>= realized) {s['p_at_or_above_realized']:.3f}")
        for w, s in summary["p_any_big"][v].items():
            log(f"   P(>= 1 big win) W{w}: predicted {s['predicted']:.3f}  realized {s['realized']}")
        log(f"   PIT deciles (flat if calibrated; low deciles = finished worse than the model expected): "
            f"{summary['pit_deciles'][v]}")
        log(f"   PIT mean by week (0.5 if calibrated; the weeks, not the entries, are independent): {summary['pit_week_mean'][v]}")
    log(f"== done {time.strftime('%H:%M:%S')} ({time.time() - t_start:.0f}s)  entries {len(rows)}  out {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
