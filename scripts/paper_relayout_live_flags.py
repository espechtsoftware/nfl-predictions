#!/usr/bin/env python3
"""Refinement 1 PAPER test (operator, 2026-09-24): re-lay the entered book out after the Sunday inactives with the flag
rule "live DraftKings status only", into a SCRATCH directory. Never touches ENTER/ and uploads nothing.

Why: DraftKings drops a player's Q tag when he is declared active (Week 2: Olave and Burrow by the 10:49 CT pull after the
10:30 inactives), but the entered layout's flag rule also counts the Friday injury-report tag, which never clears. So an
early-game Questionable player who has been declared active still bars his lineups from the protected ranks (the head
and the single-entry contests). This shows which lineups a live-status rule would have moved into those ranks; Monday's
paper scoring compares them with what was entered.

    python scripts/paper_relayout_live_flags.py --book-dir <final book dir: book.csv + vetting_final.json>
        --upload <the entered upload CSV> --contests contests.json --sets ownership_sets.csv --group 153769
        --out <scratch dir> [--pin-first] [--status-csv dk_id,status]   # --status-csv replaces the live DK pull (tests)

Flag rule here: a row is flagged when any player's CURRENT DraftKings status is Q/D/O/IR (or OUT), or the vetting gave
it a QB-availability note (qb:/backup_qb:, which DraftKings does not carry). The injury-report tag is not used.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.inference import enter_layout as EL  # noqa: E402

LIVE_FLAG_STATUSES = {"Q", "D", "O", "OUT", "IR", "QUESTIONABLE", "DOUBTFUL"}
QB_TAGS = ("qb", "backup_qb")


def live_statuses(group: int | None, status_csv: Path | None) -> dict[str, str]:
    if status_csv:
        return {str(r["id"]): str(r.get("status") or "") for r in csv.DictReader(open(status_csv))}
    from nfl_dfs.ingest.dk_client import fetch_draftables
    out: dict[str, str] = {}
    for d in fetch_draftables(int(group))["draftables"]:
        st = d.get("status")
        out[str(d.get("playerId"))] = "" if st in (None, "None", "") else str(st)
    return out


def live_flagged(book_rows: list[list[str]], vetting: dict, status: dict[str, str]) -> set[int]:
    lineups = vetting["lineups"]
    qb_noted = {int(x["position"]) - 1 for x in lineups
                if any(str(t).split(":", 1)[0] in QB_TAGS for tags in (x.get("flags") or {}).values() for t in tags)}
    live = {i for i, row in enumerate(book_rows) if any(status.get(p, "").upper() in LIVE_FLAG_STATUSES for p in row)}
    return live | qb_noted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book-dir", type=Path, required=True)
    ap.add_argument("--upload", type=Path, required=True)
    ap.add_argument("--contests", type=Path, required=True)
    ap.add_argument("--sets", type=Path, required=True)
    ap.add_argument("--group", type=int)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--layout", default="head")
    ap.add_argument("--pin-first", action="store_true")
    ap.add_argument("--status-csv", type=Path)
    a = ap.parse_args(argv)
    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit(f"--out {a.out} is not empty (scratch only; never the live ENTER/)")
    if a.out.resolve().name == "ENTER" or (a.out / "..").resolve().name == "ENTER":
        raise SystemExit("refusing to write into an ENTER directory")
    contests = EL._contests(a.contests)
    book_rows = EL._read_rows(a.book_dir / "book.csv")[1]
    vf_path = a.book_dir / "vetting_final.json"
    if not vf_path.is_file():
        raise SystemExit(f"{vf_path} missing: the paper test needs the final vetting (positions) of the entered book")
    vetting = json.loads(vf_path.read_text())
    upload_rows = EL._read_rows(a.upload)[1]
    EL.check_aligned(book_rows, upload_rows)
    protect = EL.protected_ranks(contests, a.layout)
    # the entered order (the Saturday rule) and the live-status order, from the same book and sets
    entered_perm, _ = EL.load_order("fewest-low", len(book_rows), book=a.book_dir / "book.csv", vetting=vf_path,
                                    sets=a.sets, pin_first=a.pin_first, upload_rows=upload_rows, protect=protect)
    with open(a.sets, newline="") as f:
        low_ids = {str(r["dk_player_id"]) for r in csv.DictReader(f) if r["set"] == "LOW"}
    status = live_statuses(a.group, a.status_csv)
    flagged = live_flagged(book_rows, vetting, status)
    live_perm = EL.fewest_low_order(book_rows, low_ids, flagged, a.pin_first, protect=protect)
    info = {"order": "fewest-low (live DK status flags)", "flagged_rows": len(flagged), "protected_ranks": protect,
            "status_source": str(a.status_csv) if a.status_csv else f"live DK draftables, group {a.group}"}
    a.out.mkdir(parents=True, exist_ok=True)
    lines = EL.write(contests, a.upload, a.out, a.layout, (live_perm, info))
    entered_prot, live_prot = set(entered_perm[:protect]), set(live_perm[:protect])
    moved_in, moved_out = sorted(live_prot - entered_prot), sorted(entered_prot - live_prot)
    summary = {"protected_ranks": protect, "flagged_saturday_rule": None, "flagged_live_rule": len(flagged),
               "rows_newly_protected": [i + 1 for i in moved_in], "rows_leaving_protection": [i + 1 for i in moved_out]}
    (a.out / "PAPER-ONLY-NOT-FOR-UPLOAD.txt").write_text(
        "Refinement 1 paper re-layout (live DK status flags). Never upload these files.\n")
    (a.out / "paper-relayout.json").write_text(json.dumps(summary, indent=1) + "\n")
    print("\n".join(lines))
    print(f"protected ranks {protect}: {len(moved_in)} book rows newly protected {summary['rows_newly_protected']}, "
          f"{len(moved_out)} leave {summary['rows_leaving_protection']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
