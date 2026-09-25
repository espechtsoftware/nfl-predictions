#!/usr/bin/env python3
"""R1(c) (outside-the-box plan; pulled into Week 3 by the operator, production 98508b59): the Sunday re-selection, PAPER ONLY.

Keep the Saturday pool; after the 10:30 CT inactives, drop every lineup holding a player who is OUT / IR / Doubtful /
inactive, then re-select with the live objective (greedy expected maximum over the incumbent + corrected-hsim banks, nfl2
`select_expected_max`) on the **T-70 run's** player-score banks, to the same K. Nothing is entered: the output is a book in
`exposure_cap_book.py`'s capped-book format, which `paper_layout_capped_book.py` lays out (head / fewest-low) into a
scratch dir. Monday scores it beside the entered bundle (`reports/lab-handoffs/paper_bundle_outcomes.py`).

Drop rule for a Saturday candidate (any one player suffices):
  * absent from the T-70 frame (the T-70 build removes players it will not project);
  * T-70 frame `status` (DraftKings) in OUT_STATUSES, or `roster_status` present and not ACT;
  * with --dk-status (the `sunday_live_relayout.sh` snapshot, columns id = dk_player_id, status): status in OUT_STATUSES.
Players map between the runs by the frame `id` (gsis_id for skill players, the team DST id for defenses).

    PYTHONPATH=<pinned nfl2 src>:$PROD/src python scripts/r1c_sunday_reselect.py --saturday-run <D12800 paid run dir> \
        --t70-run <T-70 run dir> --k 144 --out <scratch dir> [--dk-status $OUT/dk-status-<utc>.csv]
    then: python scripts/paper_layout_capped_book.py --capped-book <scratch>/r1c_book.csv --run-dir <T-70 run dir> \
        --contests contests.json --sets ownership_sets.csv --out <scratch>/bundle
Both run dirs need the A5 sidecars (incumbent_player_scores.npy, corrected_hsim_player_scores.npy).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

OUT_STATUSES = {"O", "OUT", "IR", "D", "DOUBTFUL", "PUP", "NFI", "SUS", "SUSPENDED", "INJURED RESERVE"}
BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")


def unavailable_ids(t70: pd.DataFrame, dk_status: pd.DataFrame | None = None) -> set[str]:
    """Frame ids the T-70 information says will not play."""
    st = t70.get("status", pd.Series("", index=t70.index)).astype(str).str.strip().str.upper()
    bad = st.isin(OUT_STATUSES)
    if "roster_status" in t70:
        rs = t70.roster_status.astype("string")
        bad |= rs.notna() & (rs.str.upper() != "ACT") & (t70.get("pos", t70.get("position")).astype(str) != "DST")
    out = set(t70.id.astype(str)[bad])
    if dk_status is not None:
        s = dk_status.status.astype(str).str.strip().str.upper()
        gone = set(dk_status.id.astype(str)[s.isin(OUT_STATUSES)])
        dk = pd.to_numeric(t70.get("dk_player_id"), errors="coerce").astype("Int64").astype(str)
        out |= set(t70.id.astype(str)[dk.isin(gone)])
    return out


def reselect(sat_cands: pd.DataFrame, t70: pd.DataFrame, inc: np.ndarray, hs: np.ndarray, k: int,
             selector: Callable[[np.ndarray, int], list[int]], dk_status: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Survivors of the Saturday pool, re-selected to K on the T-70 banks. Returns (book, receipt)."""
    row_of = {str(i): r for r, i in enumerate(t70.id.astype(str))}
    gone = unavailable_ids(t70, dk_status)
    rosters = [str(p).split(",") for p in sat_cands.players]
    missing = [any(i not in row_of for i in ids) for ids in rosters]
    out_flag = [any(i in gone for i in ids) for ids in rosters]
    keep = [i for i in range(len(rosters)) if not missing[i] and not out_flag[i]]
    if len(keep) < k:
        raise SystemExit(f"only {len(keep)} Saturday lineups survive; cannot re-select K={k}")
    idx = np.array([[row_of[i] for i in rosters[c]] for c in keep])
    mat = np.concatenate([inc[idx].sum(axis=1), hs[idx].sum(axis=1)], axis=1).astype(np.float32)
    pick = list(selector(mat, k))
    if len(pick) != k or len(set(pick)) != k:
        raise SystemExit("the selector did not return K distinct lineups")
    book = sat_cands.iloc[[keep[p] for p in pick]].copy()
    book["r1c_rank"] = range(1, k + 1)
    book["saturday_book_rank"] = book.get("book_rank")
    receipt = {"saturday_pool": len(rosters), "dropped_missing_from_t70": int(sum(missing)),
               "dropped_unavailable": int(sum(o and not m for o, m in zip(out_flag, missing))),
               "survivors": len(keep), "k": k, "unavailable_players": sorted(gone),
               "kept_from_saturday_book": int(book.book_rank.notna().sum()) if "book_rank" in book else None}
    return book, receipt


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saturday-run", type=Path, required=True); ap.add_argument("--t70-run", type=Path, required=True)
    ap.add_argument("--k", type=int, default=144); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dk-status", type=Path)
    a = ap.parse_args(argv)
    from nfl2.selectors import select_expected_max          # the live selector (pinned nfl2 on PYTHONPATH)
    for f in ("candidates.parquet", "frame.parquet"):
        if not (a.saturday_run / f).is_file():
            raise SystemExit(f"{a.saturday_run / f} missing")
    for f in ("frame.parquet", *BANKS):
        if not (a.t70_run / f).is_file():
            raise SystemExit(f"{a.t70_run / f} missing (the T-70 run needs its A5 sidecars)")
    out = a.out.expanduser()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; a paper re-selection is written once")
    out.mkdir(parents=True, exist_ok=True)
    cands = pd.read_parquet(a.saturday_run / "candidates.parquet").reset_index(drop=True)
    t70 = pd.read_parquet(a.t70_run / "frame.parquet").reset_index(drop=True)
    inc, hs = (np.load(a.t70_run / b) for b in BANKS)
    if inc.shape[0] != len(t70) or hs.shape[0] != len(t70):
        raise SystemExit("T-70 banks do not match the T-70 frame's rows")
    dk = pd.read_csv(a.dk_status, dtype=str) if a.dk_status else None
    book, rec = reselect(cands, t70, inc, hs, a.k, select_expected_max, dk)
    book.to_csv(out / "r1c_book.csv", index=False)
    rec.update({"kind": "PAPER Sunday re-selection (R1(c)); never entered", "saturday_run": str(a.saturday_run),
                "t70_run": str(a.t70_run), "dk_status": str(a.dk_status) if a.dk_status else None,
                "input_sha256": {"saturday_candidates": _sha(a.saturday_run / "candidates.parquet"),
                                 "t70_frame": _sha(a.t70_run / "frame.parquet"),
                                 **{b: _sha(a.t70_run / b) for b in BANKS}},
                "book_sha256": _sha(out / "r1c_book.csv")})
    (out / "receipt.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(f"R1(c): {rec['saturday_pool']} Saturday lineups; dropped {rec['dropped_missing_from_t70']} (a player not in T-70) + "
          f"{rec['dropped_unavailable']} (OUT/IR/D/inactive); {rec['survivors']} survive; K={a.k} re-selected on the T-70 banks; "
          f"{rec['kept_from_saturday_book']} of them were in the Saturday book -> {out / 'r1c_book.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
