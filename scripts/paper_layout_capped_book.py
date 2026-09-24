#!/usr/bin/env python3
"""Lay a PAPER capped book out exactly like the entered one (laptop ask, 2026-09-24), so Monday's per-contest-type
scoring compares the refinement-2 cap effect and not a different layout. Writes a scratch bundle; never ENTER/.

    python scripts/paper_layout_capped_book.py --capped-book <exposure-caps-r2-TAG/capped_book.csv> --run-dir <K90 run dir>
        --contests contests.json --sets ownership_sets.csv --out <scratch dir> [--layout head] [--order fewest-low]

Steps: each capped lineup (gsis ids, from exposure_cap_book.py) is put into DraftKings slot order (QB, RB, RB, WR, WR,
WR, TE, FLEX, DST; the FLEX takes the surplus RB/WR/TE with the latest kickoff, as a late-swap-friendly roster would),
mapped through the run's frame to dk_player_id (book.csv) and dk_draftable_id (the upload), given injury flags from the
frame's report status (report:<status>, the Saturday rule's tag), and laid out by enter_layout with the protected ranks.
The entered chain also vets with live DK tags; this paper bundle uses the frame's report status only (stated in its
layout record).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.inference import enter_layout as EL  # noqa: E402

SLOTS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
FLAG_STATUSES = {"Questionable", "Doubtful", "Out", "IR"}
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def slot_order(players: list[str], pos: dict[str, str], kick: dict[str, pd.Timestamp]) -> list[str]:
    need = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}
    by = {p: [] for p in need}
    for g in sorted(players, key=lambda g: (kick.get(g, EPOCH), g)):
        if pos[g] not in by:
            raise SystemExit(f"player {g} has position {pos[g]!r}")
        by[pos[g]].append(g)
    flex = [g for p in ("RB", "WR", "TE") for g in by[p][need[p]:]]
    if len(flex) != 1 or any(len(by[p]) < need[p] for p in need):
        raise SystemExit(f"lineup {players} is not a DK classic roster")
    out = by["QB"][:1] + by["RB"][:2] + by["WR"][:3] + by["TE"][:1] + flex + by["DST"][:1]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capped-book", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--contests", type=Path, required=True)
    ap.add_argument("--sets", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--layout", default="head")
    ap.add_argument("--order", default="fewest-low")
    a = ap.parse_args(argv)
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit(f"--out {a.out} is not empty (scratch only)")
    if a.out.resolve().name == "ENTER":
        raise SystemExit("refusing to write into an ENTER directory")
    fr = pd.read_parquet(a.run_dir / "frame.parquet")
    # capped rosters name skill players by gsis_id and defenses by the frame's `id` (e.g. CIN_DST; their gsis_id is 0)
    fr["key"] = fr["gsis_id"].astype(str).where(fr["position"].astype(str) != "DST", fr["id"].astype(str))
    if fr["key"].duplicated().any():
        raise SystemExit(f"frame keys repeat: {fr.loc[fr['key'].duplicated(), 'key'].tolist()[:5]}")
    fr = fr.set_index("key")
    pos = fr["position"].astype(str).to_dict()
    kick = pd.to_datetime(fr["game_start"], utc=True).to_dict() if "game_start" in fr else {}
    cap = pd.read_csv(a.capped_book)
    sort_col = "book_rank" if "book_rank" in cap.columns else None
    if sort_col:
        cap = cap.sort_values(sort_col, kind="stable")
    rows_g = [slot_order(str(p).split(","), pos, kick) for p in cap["players"]]
    book_rows = [[str(fr.loc[g, "dk_player_id"]) for g in r] for r in rows_g]
    up_rows = [[str(fr.loc[g, "dk_draftable_id"]) for g in r] for r in rows_g]
    status = fr["report_status"].astype("string").fillna("") if "report_status" in fr else pd.Series("", index=fr.index)
    names = fr["display_name"].astype(str)
    vetting = {"version": "paper-capped-book-v1", "publishable": False, "lineups": [
        {"position": i + 1, "source": f"capped-rank-{i + 1}", "salary": None,
         "flags": {names[g]: [f"report:{status[g]}"] for g in r if status[g] in FLAG_STATUSES}}
        for i, r in enumerate(rows_g)]}
    work = a.out / "book"
    work.mkdir(parents=True)
    with open(work / "book.csv", "w", newline="") as f:
        csv.writer(f).writerows([SLOTS] + book_rows)
    with open(work / "upload.csv", "w", newline="") as f:
        csv.writer(f).writerows([SLOTS] + up_rows)
    (work / "vetting_final.json").write_text(json.dumps(vetting, indent=1) + "\n")
    contests = EL._contests(a.contests)
    info = EL.load_order(a.order, len(book_rows), book=work / "book.csv", vetting=work / "vetting_final.json",
                         sets=a.sets, pin_first=False, upload_rows=up_rows, protect=EL.protected_ranks(contests, a.layout))
    info[1]["flag_rule"] = "frame report_status (paper; no live DK tags)"
    bundle = a.out / "bundle"
    lines = EL.write(contests, work / "upload.csv", bundle, a.layout, info)
    (bundle / "ENTER-layout.txt").write_text("\n".join(lines) + "\n")
    (bundle / "PAPER-ONLY-NOT-FOR-UPLOAD.txt").write_text("Refinement-2 paper bundle. Never upload these files.\n")
    print(lines[0])
    print(f"paper bundle -> {bundle} ({len(book_rows)} book rows; flagged {info[1].get('flagged_rows', 0)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
