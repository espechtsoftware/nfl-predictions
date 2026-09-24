#!/usr/bin/env python
"""Re-select a book from the delivered candidate pool under explicit exposure caps.

Why this exists
---------------
Week 2 entered a book in which Zay Flowers -- listed **Doubtful** at build time --
held 48 of 97 rows including the Millionaire entry, and scored 0.0. Nothing had to
be predicted: the designation was already in the frame. A tool that could have
bounded that existed but was never in the chain, so this one is wired into the
Sunday build and emits alongside vetting.

What it does
------------
Constrained re-selection with the SAME objective the delivered book used (greedy
expected weekly maximum over the equal-mass concatenation of the incumbent and
corrected-hsim world banks), from the SAME candidate pool, at the SAME K. The caps
are the only difference, so the emitted book is comparable to the delivered one
lineup for lineup -- see reports/2026-09-21-laptop-item3-isolated-cap-effect.md,
where this construction reproduces the delivered Week-2 book exactly, in order.

Two caps a book-share limit cannot express are first-class here:

* **status caps.** A Doubtful player is capped at zero rows by default. This is not
  a forecast and needs no threshold.
* **per-contest caps.** A share-of-book cap constrains how MANY rows hold a player,
  never WHICH, and the greedy reshuffles underneath it: capping a Questionable
  player 26 -> 4 rows in the Week-2 study moved one of the four INTO the
  Millionaire. Contest membership is therefore counted inside the selection loop,
  not checked afterwards.

Nothing here enters a contest. It writes a book and a receipt for the operator to
read before upload, and fails closed rather than quietly emitting a short book.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DK_CLASSIC_SLOTS = 9
# DraftKings prints %Drafted to two decimals; unrelated to caps, kept for the sheet.
STATUS_DOUBTFUL = "Doubtful"
STATUS_QUESTIONABLE = "Questionable"


class CapError(RuntimeError):
    """Any condition under which an emitted book would be misleading."""


# ---------------------------------------------------------------- run artifacts


@dataclass(frozen=True)
class Run:
    frame: pd.DataFrame
    cands: pd.DataFrame
    roster_idx: np.ndarray          # (n_cands, 9) row indices into frame
    t_inc: np.ndarray               # (n_cands, n_worlds) incumbent bank
    t_hs: np.ndarray                # (n_cands, n_worlds) corrected-hsim bank
    receipt: dict


def load_run(run_dir: Path) -> Run:
    """Load a lab run directory, refusing anything that would make the arms
    incomparable. The world banks are written only under --emit-a5-sidecars; without
    them the delivered objective cannot be reproduced and there is no honest cap arm,
    so their absence is an error and never a fallback to a different objective."""
    need = ["candidates.parquet", "frame.parquet", "receipt.json",
            "incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"]
    missing = [n for n in need if not (run_dir / n).is_file()]
    if missing:
        raise CapError(
            f"{run_dir} is missing {missing}. The player-world banks are emitted only "
            "when live_week.py runs with --emit-a5-sidecars; without them the delivered "
            "expected-max objective cannot be reproduced and no cap arm is comparable."
        )
    receipt = json.loads((run_dir / "receipt.json").read_text())
    sidecars = receipt.get("a5_sidecars") or {}
    for name, key in (("incumbent_player_scores.npy", "incumbent_player_scores"),
                      ("corrected_hsim_player_scores.npy", "corrected_hsim_player_scores")):
        want = (sidecars.get(key) or {}).get("sha256")
        if not want:
            raise CapError(f"receipt.json does not pin {key}; refusing to trust {name}")
        h = hashlib.sha256()
        with open(run_dir / name, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        if h.hexdigest() != want:
            raise CapError(f"{name} sha256 {h.hexdigest()} != receipted {want}")

    frame = pd.read_parquet(run_dir / "frame.parquet").reset_index(drop=True)
    cands = pd.read_parquet(run_dir / "candidates.parquet").reset_index(drop=True)
    inc = np.load(run_dir / "incumbent_player_scores.npy")
    hsm = np.load(run_dir / "corrected_hsim_player_scores.npy")
    if inc.shape[0] != len(frame) or hsm.shape[0] != len(frame):
        raise CapError(
            f"player banks have {inc.shape[0]}/{hsm.shape[0]} rows for a {len(frame)}-row frame")

    index = {pid: i for i, pid in enumerate(frame.id.astype(str))}
    rosters = []
    for spec in cands.players.astype(str):
        ids = spec.split(",")
        if len(ids) != DK_CLASSIC_SLOTS:
            raise CapError(f"candidate roster has {len(ids)} players, expected {DK_CLASSIC_SLOTS}")
        try:
            rosters.append([index[p] for p in ids])
        except KeyError as exc:
            raise CapError(f"candidate references player {exc} that is not in the frame") from exc
    roster_idx = np.asarray(rosters, dtype=np.int32)

    t_inc = inc[roster_idx].sum(axis=1).astype(np.float32)
    t_hs = hsm[roster_idx].sum(axis=1).astype(np.float32)
    # sel_mean is the incumbent-bank mean of each lineup: an independent check that the
    # roster-to-row mapping is right before anything is selected from it.
    if "sel_mean" in cands:
        drift = float(np.abs(t_inc.mean(axis=1) - cands.sel_mean.to_numpy(np.float32)).max())
        if drift > 0.01:
            raise CapError(
                f"rebuilt lineup means differ from candidates.parquet sel_mean by {drift:.4f}; "
                "the roster-to-player mapping is wrong and every arm would be meaningless")
    return Run(frame, cands, roster_idx, t_inc, t_hs, receipt)


# ------------------------------------------------------------------ the layout


def contest_of_position(contests: list[dict], k: int, layout: str) -> list[list[int]]:
    """Map each book position 0..k-1 to the contest indices that receive it.

    sequential: contests take disjoint consecutive slices of the book.
    top:        every contest independently receives ranks 1..entries, so the slices
                OVERLAP and an early position sits in many contests at once.
    """
    if layout not in ("sequential", "top", "head"):
        raise CapError(f"unknown ENTER_LAYOUT {layout!r}; expected 'sequential', 'top' or 'head'")
    out: list[list[int]] = [[] for _ in range(k)]
    if layout == "head":
        # 2026-09-24: the rule lives in enter_layout.py. Positions here are greedy ranks; ENTER_ORDER=fewest-low
        # re-orders rows at ENTER time, so this report-only tool's per-contest caps are approximate under it.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from nfl_dfs.inference.enter_layout import LayoutError, assign_ranks
        try:
            ranks = assign_ranks(contests, "head")
        except LayoutError as exc:
            raise CapError(str(exc)) from exc
        for ci, rs in enumerate(ranks):
            for p in rs:
                if p >= k:
                    raise CapError(f"head layout reads rank {p + 1} but the book is {k}")
                out[p].append(ci)
        return out
    if layout == "sequential":
        pos = 0
        for ci, c in enumerate(contests):
            n = int(c["entries"])
            if pos + n > k:
                raise CapError(
                    f"sequential layout needs {sum(int(x['entries']) for x in contests)} "
                    f"unique lineups but the book is {k}")
            for p in range(pos, pos + n):
                out[p].append(ci)
            pos += n
    else:
        for ci, c in enumerate(contests):
            for p in range(min(int(c["entries"]), k)):
                out[p].append(ci)
    return out


# ------------------------------------------------------------------- the caps


def build_player_caps(frame: pd.DataFrame, k: int, *, player_share: float,
                      dst_share: float, doubtful_share: float,
                      questionable_share: float, questionable_qb_share: float | None = None,
                      questionable_dnp_share: float | None = None) -> tuple[np.ndarray, dict]:
    """Per-player maximum rows, and a per-player reason for every binding cap.

    Refinement 2 (operator, 2026-09-24; external analysis 2018-25): two Questionable groups play only about half the
    time -- Questionable QBs (50%) and Questionable players whose latest practice was Did Not Participate
    (practice_level 0; 52%) -- against 72% for Questionable players overall. `questionable_qb_share` and
    `questionable_dnp_share` give them a tighter cap than `questionable_share`; None keeps the Questionable cap."""
    if "report_status" not in frame:
        raise CapError("frame has no report_status column; injury caps cannot be applied")
    caps = np.full(len(frame), int(np.floor(player_share * k)), dtype=np.int32)
    reasons: dict[str, str] = {}
    status = frame.report_status.astype("string").fillna("")
    position = frame.position.astype(str)

    is_dst = position.eq("DST").to_numpy()
    caps[is_dst] = int(np.floor(dst_share * k))

    q = status.eq(STATUS_QUESTIONABLE).to_numpy()
    caps[q] = np.minimum(caps[q], int(np.floor(questionable_share * k)))
    qb_q = q & position.eq("QB").to_numpy()
    dnp_q = np.zeros(len(frame), dtype=bool)
    if questionable_dnp_share is not None:
        if "practice_level" not in frame:
            raise CapError("frame has no practice_level column; the missed-practice cap cannot be applied")
        dnp_q = q & pd.to_numeric(frame.practice_level, errors="coerce").eq(0).to_numpy()
    if questionable_qb_share is not None:
        caps[qb_q] = np.minimum(caps[qb_q], int(np.floor(questionable_qb_share * k)))
    if questionable_dnp_share is not None:
        caps[dnp_q] = np.minimum(caps[dnp_q], int(np.floor(questionable_dnp_share * k)))
    d = status.eq(STATUS_DOUBTFUL).to_numpy()
    caps[d] = int(np.floor(doubtful_share * k))

    for i in np.flatnonzero(d):
        reasons[str(frame.display_name.iloc[i])] = f"Doubtful -> {caps[i]} rows"
    for i in np.flatnonzero(q):
        why = ("Questionable QB" if qb_q[i] and questionable_qb_share is not None else
               "Questionable, missed last practice" if dnp_q[i] else "Questionable")
        reasons[str(frame.display_name.iloc[i])] = f"{why} -> {caps[i]} rows"
    for i in np.flatnonzero(is_dst):
        reasons.setdefault(str(frame.display_name.iloc[i]), f"DST -> {caps[i]} rows")
    return caps, reasons


# -------------------------------------------------------------- the selection


def select_capped(run: Run, k: int, *, player_caps: np.ndarray,
                  contest_positions: list[list[int]] | None = None,
                  contest_caps: list[int] | None = None) -> tuple[list[int], dict]:
    """Greedy expected weekly maximum, exactly as the delivered selector, with the caps
    as constraints. Lazy (CELF) evaluation only changes the ORDER gains are computed in,
    never the result: the marginal gain is submodular, so it is monotone non-increasing
    in the book and a stale top-of-heap entry is re-priced before it can be taken.

    Exposure counts never decrease, so a candidate that violates a cap now violates it
    for the rest of the run and is dropped permanently.
    """
    t_inc, t_hs, rix = run.t_inc, run.t_hs, run.roster_idx
    n = t_inc.shape[0]
    n_worlds = t_inc.shape[1] + t_hs.shape[1]
    cur_i = np.full(t_inc.shape[1], -np.inf, dtype=np.float64)
    cur_h = np.full(t_hs.shape[1], -np.inf, dtype=np.float64)
    counts = np.zeros(run.frame.shape[0], dtype=np.int32)
    per_contest = (np.zeros((len(contest_caps), run.frame.shape[0]), dtype=np.int32)
                   if contest_caps is not None else None)
    base = 0.0
    seeded = False

    blocked_by = {"player": 0, "contest": 0}

    gains = np.empty(n, dtype=np.float64)
    for a in range(0, n, 512):
        b = min(a + 512, n)
        gains[a:b] = (t_inc[a:b].astype(np.float64).sum(axis=1)
                      + t_hs[a:b].astype(np.float64).sum(axis=1)) / n_worlds
    heap = [(-gains[i], i, 0) for i in range(n)]
    heapq.heapify(heap)

    def gain_of(i: int) -> float:
        if not seeded:
            return gains[i]
        return ((np.maximum(t_inc[i], cur_i).sum() + np.maximum(t_hs[i], cur_h).sum())
                / n_worlds) - base

    book: list[int] = []
    taken = np.zeros(n, dtype=bool)
    dropped = np.zeros(n, dtype=bool)
    deferred: list[tuple[float, int, int]] = []
    while len(book) < k and (heap or deferred):
        if not heap:
            # Every remaining candidate is legal on its player caps but blocked by the
            # contest this position belongs to. Nothing can fill the seat.
            raise CapError(
                f"no candidate satisfies the per-contest caps at book position "
                f"{len(book) + 1}; loosen --contest-max-share or widen the pool")
        neg, i, stamp = heapq.heappop(heap)
        if taken[i] or dropped[i]:
            continue
        roster = rix[i]
        if (counts[roster] + 1 > player_caps[roster]).any():
            dropped[i] = True
            blocked_by["player"] += 1
            continue
        # A candidate blocked only by the contest its POSITION falls in may be legal at a
        # later position, so it is set aside for this seat and restored once one is
        # filled -- never dropped, and never re-offered at the same position, which would
        # spin instead of trying the next-best candidate.
        if per_contest is not None and any(
            (per_contest[ci][roster] + 1 > contest_caps[ci]).any()
            for ci in contest_positions[len(book)]
        ):
            blocked_by["contest"] += 1
            deferred.append((neg, i, stamp))
            continue
        if stamp == len(book):
            taken[i] = True
            book.append(i)
            np.maximum(cur_i, t_inc[i], out=cur_i)
            np.maximum(cur_h, t_hs[i], out=cur_h)
            seeded = True
            base = (cur_i.sum() + cur_h.sum()) / n_worlds
            np.add.at(counts, roster, 1)
            if per_contest is not None:
                for ci in contest_positions[len(book) - 1]:
                    np.add.at(per_contest[ci], roster, 1)
            for entry in deferred:
                heapq.heappush(heap, entry)
            deferred = []
        else:
            heapq.heappush(heap, (-gain_of(i), i, len(book)))

    if len(book) < k:
        raise CapError(
            f"the caps admit only {len(book)} of {k} lineups from this pool "
            f"({blocked_by['player']} candidates blocked by a player cap). A short book "
            "is never emitted silently: loosen a cap or widen the pool.")
    emax = (np.maximum.reduce(t_inc[book]).astype(np.float64).sum()
            + np.maximum.reduce(t_hs[book]).astype(np.float64).sum()) / n_worlds
    return book, {"sim_expected_max": round(float(emax), 4),
                  "candidates_blocked_by_player_cap": blocked_by["player"],
                  "position_retries_from_contest_cap": blocked_by["contest"]}


# ------------------------------------------------------------------- reporting


def exposure_table(run: Run, book: list[int]) -> pd.DataFrame:
    counts = np.zeros(len(run.frame), dtype=int)
    np.add.at(counts, run.roster_idx[book], 1)
    held = np.flatnonzero(counts)
    return pd.DataFrame({
        "player": run.frame.display_name.astype(str).iloc[held].to_numpy(),
        "position": run.frame.position.astype(str).iloc[held].to_numpy(),
        "salary": run.frame.salary.iloc[held].to_numpy(),
        "status": run.frame.report_status.astype("string").fillna("").iloc[held].to_numpy(),
        "rows": counts[held],
        "share": (counts[held] / len(book)).round(4),
    }).sort_values("rows", ascending=False).reset_index(drop=True)


def _sheet(delivered: pd.DataFrame, capped: pd.DataFrame, diag: dict, policy: dict,
           reasons: dict, k: int) -> str:
    out = ["# Exposure cap sheet", "",
           f"Book of {k}. Objective, pool and K are identical to the delivered book; "
           "the caps are the only difference.", ""]
    cost = diag["delivered_expected_max"] - diag["capped_expected_max"]
    out += [f"- delivered simulated E[max] **{diag['delivered_expected_max']:.2f}**",
            f"- capped simulated E[max] **{diag['capped_expected_max']:.2f}** "
            f"(cost **{cost:.2f}**, {100 * cost / max(diag['delivered_expected_max'], 1e-9):.2f}%)",
            f"- lineups shared with the delivered book: **{diag['overlap_with_delivered']} / {k}**", ""]
    flagged = delivered[delivered.status.ne("")]
    if len(flagged):
        out += ["## Players carrying an injury designation, as the delivered book holds them", "",
                "| player | status | delivered rows | capped rows | cap reason |", "|---|---|---:|---:|---|"]
        cap_rows = dict(zip(capped.player, capped.rows))
        for _, r in flagged.iterrows():
            out.append(f"| {r.player} | {r.status} | {int(r.rows)} | {int(cap_rows.get(r.player, 0))} "
                       f"| {reasons.get(r.player, '-')} |")
        out.append("")
    out += ["## Largest exposures after the caps", "",
            "| player | pos | status | rows | share |", "|---|---|---|---:|---:|"]
    for _, r in capped.head(15).iterrows():
        out.append(f"| {r.player} | {r.position} | {r.status or '-'} | {int(r.rows)} | {r.share:.1%} |")
    out += ["", "## Policy", ""] + [f"- `{k2}` = {v}" for k2, v in policy.items()]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path, help="lab run directory (needs --emit-a5-sidecars artifacts)")
    ap.add_argument("--contests", type=Path, required=True, help="contests.json (never committed)")
    ap.add_argument("--entries", type=int, required=True, help="book size K")
    ap.add_argument("--layout", default="sequential", choices=["sequential", "top", "head"])
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--player-max-share", type=float, default=0.30)
    ap.add_argument("--dst-max-share", type=float, default=0.20)
    ap.add_argument("--questionable-max-share", type=float, default=0.10)
    ap.add_argument("--questionable-qb-max-share", type=float, default=None,
                    help="refinement 2: tighter cap for Questionable QBs (default: the Questionable cap)")
    ap.add_argument("--questionable-dnp-max-share", type=float, default=None,
                    help="refinement 2: tighter cap for Questionable players whose latest practice was DNP")
    ap.add_argument("--doubtful-max-share", type=float, default=0.0,
                    help="default 0.0: a Doubtful player takes no rows. Week 2 entered one "
                         "in 48 of 97 rows including the Millionaire seat; he scored 0.0.")
    ap.add_argument("--contest-max-share", type=float, default=0.50,
                    help="per-contest cap: no player in more than this share of any one "
                         "contest's rows. Default 0.50 is deliberately weak -- it stops the "
                         "pathological case (a player in 20 of 23 rows) without choosing a "
                         "tight level off a single slate. Selection is a positional greedy, "
                         "so a tight cap can dead-end; that fails closed with the position "
                         "named rather than emitting a breaching book. A contest smaller "
                         "than 1/share cannot be constrained below one row and is reported "
                         "as unconstrained.")
    a = ap.parse_args(argv)

    run = load_run(a.run_dir)
    contests = json.loads(a.contests.read_text())
    k = int(a.entries)
    if k > len(run.cands):
        raise CapError(f"asked for {k} lineups from a {len(run.cands)}-candidate pool")

    positions = contest_of_position(contests, k, a.layout)
    sizes = [int(c["entries"]) for c in contests]
    contest_caps = [max(1, int(np.floor(a.contest_max_share * n))) for n in sizes]
    # Report distinct names with a count. contests.json is the stake plan; the receipt is
    # committed, so it carries aggregates and never a per-contest breakdown.
    _unc: dict[str, int] = {}
    for c, n, cap in zip(contests, sizes, contest_caps):
        if cap >= n:
            _unc[str(c["name"])] = _unc.get(str(c["name"]), 0) + 1
    unconstrained = [f"{name} x{n}" for name, n in sorted(_unc.items())]

    caps, reasons = build_player_caps(
        run.frame, k, player_share=a.player_max_share, dst_share=a.dst_max_share,
        doubtful_share=a.doubtful_max_share, questionable_share=a.questionable_max_share,
        questionable_qb_share=a.questionable_qb_max_share, questionable_dnp_share=a.questionable_dnp_max_share)

    uncapped, u_diag = select_capped(run, k, player_caps=np.full(len(run.frame), k, dtype=np.int32))
    book, diag = select_capped(run, k, player_caps=caps,
                               contest_positions=positions, contest_caps=contest_caps)

    diag = {**diag, "delivered_expected_max": u_diag["sim_expected_max"],
            "capped_expected_max": diag["sim_expected_max"],
            "overlap_with_delivered": len(set(book) & set(uncapped))}

    out = a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    delivered_tbl, capped_tbl = exposure_table(run, uncapped), exposure_table(run, book)
    capped_tbl.to_csv(out / "exposures.csv", index=False)
    run.cands.iloc[book].assign(book_rank=range(1, k + 1)).to_csv(out / "capped_book.csv", index=False)
    policy = {"player_max_share": a.player_max_share, "dst_max_share": a.dst_max_share,
              "questionable_max_share": a.questionable_max_share,
              "questionable_qb_max_share": a.questionable_qb_max_share,
              "questionable_dnp_max_share": a.questionable_dnp_max_share,
              "doubtful_max_share": a.doubtful_max_share,
              "contest_max_share": a.contest_max_share, "layout": a.layout, "entries": k}
    (out / "exposure_sheet.md").write_text(
        _sheet(delivered_tbl, capped_tbl, diag, policy, reasons, k))
    (out / "receipt.json").write_text(json.dumps({
        "run_dir": str(a.run_dir), "source_identity": run.receipt.get("identity"),
        "policy": policy, "diagnostics": diag,
        "contests_unconstrained_by_contest_cap": unconstrained,
        "cap_reasons": reasons,
        "max_exposure_rows": int(capped_tbl.rows.max()),
        "delivered_max_exposure_rows": int(delivered_tbl.rows.max()),
    }, indent=2, sort_keys=True) + "\n")
    print(f"capped book -> {out}/capped_book.csv")
    print(f"exposure sheet -> {out}/exposure_sheet.md")
    print(f"E[max] {diag['delivered_expected_max']:.2f} -> {diag['capped_expected_max']:.2f}; "
          f"peak exposure {int(delivered_tbl.rows.max())} -> {int(capped_tbl.rows.max())} rows; "
          f"overlap {diag['overlap_with_delivered']}/{k}")
    if unconstrained:
        print(f"NOTE: too small for the per-contest cap to bind: {sorted(set(unconstrained))}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CapError as exc:
        print(f"exposure_cap_book: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
