"""Which book rows each contest's entries receive -- the one layout rule every ENTER writer and checker uses.

Before 2026-09-24 the rule was vendored inline in `sunday_after_build.sh`, `relayout_enter.sh` and its check, and
assumed (sequential only) in `exposure_cap_book.py`, `promote_first.py`, the lineage report and the exposure sheet.
A layout added in one place and not the others fails late or, worse, silently falls into another branch. Every
consumer now asks this module.

Layouts (ENTER_LAYOUT):
  sequential  each contest takes its own consecutive block (keepers first, fills from the tail); unique lineups.
  top         every contest takes ranks 1..n; a contest marked "block": true takes its own consecutive block.
  head        (operator, 2026-09-24, Week 3) every contest opens with the book's best rows and fills the rest with
              lineups used nowhere else:
                - head size h = 2 for contests of <= 5 entries, 4 for larger ones (never more than n);
                - contests whose entries are all head (n <= 2) take rows 1-4 in blocks of n, per group of contests of
                  the same SIZE (whatever their names), and NEVER repeat a lineup inside the group (operator, 2026-09-24:
                  the nineteen $2 single-entry satellites must not share entries): two 2-entry contests take rows 1-2
                  and 3-4; of nineteen 1-entry contests four take rows 1-4 and the other fifteen take the next unique
                  rows (5-19), which are dealt before any other contest's unique rows;
                - the other contests take rows 1..h, then unique rows, dealt snake-fashion (one per contest per
                  round, in contests.json order, reversing each round);
                - a contest may pin its rows explicitly with "ranks": [1-based ranks] (operator, 2026-09-25: the $20
                  Millionaire takes row 1, three $13 satellites rows 1, 2, 3). Pinned ranks must lie inside the
                  head rows 1-4, and the contest takes no part in the rotation, the overflow or the deal.

Order (ENTER_ORDER): the ranks above index an ORDER over the upload's rows.
  greedy      the book's own order (vetted, replaced and promoted), rank r = upload row r.
  fewest-low  (external review 2026-09-24 §5.3) rows sorted by their count of predicted LOW-owned players, fewest
              first, ties in the book's order; a promoted row 1 stays row 1, and flagged rows are kept out of the
              PROTECTED ranks only -- the head rows and every rank an all-head (1-2 entry) contest takes, so the
              wildcats and the nineteen single-entry satellites hold clean lineups (operator, 2026-09-24) -- elsewhere they take their fewest-LOW place, so they spread across the
              contests instead of piling into the last-dealt ones (operator, 2026-09-24, after the external
              reviewer showed that "flagged behind every clean row" put all 50 flagged rows into the six supersat25s). "Flagged" (operator, 2026-09-24: "any injury flag") is any player tag from INJURY_TAGS --
              a DK status, an injury-report status or a QB-availability note -- read the same way from
              vetting_final.json and vetting.json, so one book always gets one order. LOW comes from the ownership sets file, matched on the book's dk_player_id.

Command line (the chain's writer and the relayout check call these):
  python -m nfl_dfs.inference.enter_layout write CONTESTS UPLOAD_CSV STAGE_DIR [order options]
  python -m nfl_dfs.inference.enter_layout check CONTESTS UPLOAD_CSV STAGE_DIR [order options]
  python -m nfl_dfs.inference.enter_layout rows-needed CONTESTS [--layout L]
order options: --layout L (default $ENTER_LAYOUT, else sequential) --order O (default $ENTER_ORDER, else greedy)
               --book BOOK_CSV --vetting VETTING_FINAL_JSON --sets SETS_CSV --pin-first
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

LAYOUTS = ("sequential", "top", "head")
ORDERS = ("greedy", "fewest-low")
HEAD_TOP = 4             # the head rows every contest draws from
HEAD_SMALL, HEAD_LARGE = 2, 4
SMALL_MAX_ENTRIES = 5
MIN_SETS_COVERAGE = 0.90  # share of the book's distinct skill ids the sets file must know
INJURY_TAGS = ("DK", "report", "qb", "backup_qb")   # flag-tag prefixes that bar a row from the head (not practice/market)
# Deliberately NOT "features:" (vet_book.py's designation read from player_week_inference, which can be Wednesday's and
# stale; vet_replace_v4.py never emits it). Only the live DK status, the injury report and QB-availability notes count.


class LayoutError(ValueError):
    pass


def head_size(n: int) -> int:
    return min(n, HEAD_SMALL if n <= SMALL_MAX_ENTRIES else HEAD_LARGE)


def assign_ranks(contests: list[dict], layout: str) -> list[list[int]]:
    """Per contest (contests.json order), the 0-based RANKS its entries take, in file order."""
    if layout not in LAYOUTS:
        raise LayoutError(f"unknown ENTER_LAYOUT {layout!r}; expected one of {LAYOUTS}")
    sizes = []
    for c in contests:
        n = c.get("entries")
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise LayoutError(f"contests.json: entries for {c.get('name')!r} must be a positive integer (got {n!r})")
        sizes.append(n)
    if layout == "sequential":
        keep_total = sum(int(c["keep"]) for c in contests)
        keep_next, fill_next, out = 0, keep_total, []
        for c, n in zip(contests, sizes):
            k = int(c["keep"])
            out.append(list(range(keep_next, keep_next + k)) + list(range(fill_next, fill_next + n - k)))
            keep_next += k
            fill_next += n - k
        return out
    if layout == "top":
        cursor, out = 0, []
        for c, n in zip(contests, sizes):
            if c.get("block"):
                out.append(list(range(cursor, cursor + n)))
                cursor += n
            else:
                out.append(list(range(n)))
        return out
    # head
    out = [[] for _ in contests]
    seen: dict[tuple, int] = {}
    unique_slots = [0] * len(contests)
    overflow: list[int] = []                   # all-head contests past their group's head blocks
    for i, (c, n) in enumerate(zip(contests, sizes)):
        h = head_size(n)
        if "ranks" in c:                          # explicit pin (operator)
            r = c["ranks"]
            if (not isinstance(r, list) or len(r) != n or len(set(r)) != n
                    or any(not isinstance(x, int) or isinstance(x, bool) or not 1 <= x <= HEAD_TOP for x in r)):
                raise LayoutError(f"contests.json: {c.get('name')!r} ranks {r!r} must be {n} distinct integers in 1..{HEAD_TOP}")
            out[i] = [x - 1 for x in r]
            continue
        if n <= HEAD_SMALL:                       # the whole contest is head: one head block per group member
            key = n                               # by size, not name: renamed twins must not share rows
            b = seen.get(key, 0)
            seen[key] = b + 1
            if b < HEAD_TOP // n:
                out[i] = list(range(b * n, b * n + n))
            else:
                overflow.append(i)
        else:
            out[i] = list(range(h))
            unique_slots[i] = n - h
    nxt, rnd = HEAD_TOP, 0
    for i in overflow:                            # their own unique rows, the best of the unique pool
        out[i] = list(range(nxt, nxt + sizes[i]))
        nxt += sizes[i]
    order = [i for i in range(len(contests)) if unique_slots[i] > 0]
    while any(unique_slots[i] > 0 for i in order):
        for i in (order if rnd % 2 == 0 else list(reversed(order))):
            if unique_slots[i] > 0:
                out[i].append(nxt)
                nxt += 1
                unique_slots[i] -= 1
        rnd += 1
    return out


def rank_summary(contests: list[dict], layout: str) -> list[str]:
    """One line per contest (preflight print): its entries and the 1-based ranks it takes."""
    return [f"{c.get('name')} [{c.get('contest_id')}] x{int(c['entries'])}: ranks {_ranges(r)}"
            for c, r in zip(contests, assign_ranks(contests, layout))]


def protected_ranks(contests: list[dict], layout: str) -> int:
    """How many leading ranks must hold clean (unflagged) rows: the head, plus under `head` every rank an all-head
    contest takes (its whole entry list is shared or single, with no second lineup to cover a late scratch)."""
    if layout != "head":
        return HEAD_TOP
    ranks = assign_ranks(contests, layout)
    small = [max(r) + 1 for c, r in zip(contests, ranks) if int(c["entries"]) <= HEAD_SMALL and r]
    return max([HEAD_TOP] + small)


def rows_needed(contests: list[dict], layout: str) -> int:
    """Distinct book rows the layout reads (the book must hold at least this many)."""
    ranks = assign_ranks(contests, layout)
    return max((max(r) + 1 for r in ranks if r), default=0)


def _read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(open(path, newline="")))
    if not rows:
        raise LayoutError(f"{path} is empty")
    return rows[0], rows[1:]


def fewest_low_order(book_rows: list[list[str]], low_ids: set[str], flagged: set[int], pin_first: bool,
                     protect: int = HEAD_TOP) -> list[int]:
    """Row order by (LOW count, book rank), a promoted row 1 first; the first `protect` ranks take clean rows only,
    and the flagged rows they skip keep their fewest-LOW place right after them."""
    def key(i: int):
        return (0 if (pin_first and i == 0) else 1, sum(1 for pid in book_rows[i] if pid in low_ids), i)
    ordered = sorted(range(len(book_rows)), key=key)
    head: list[int] = []
    for i in ordered:
        if len(head) >= protect:
            break
        if i not in flagged or (pin_first and i == 0):
            head.append(i)
    taken = set(head)
    return head + [i for i in ordered if i not in taken]


def _injury_flagged(flags: dict | None) -> bool:
    return any(str(t).split(":", 1)[0] in INJURY_TAGS for tags in (flags or {}).values() for t in tags)


def flagged_positions(vetting: Path, n_rows: int) -> set[int]:
    """0-based book positions holding a player with an injury flag (INJURY_TAGS); they stay behind every clean row.

    vetting_final.json (the replacement's final vetting, and the promoted book's) lists flags by book position;
    vetting.json (the plain vetter, when no replacement ran) lists them by source rank, mapped to book position
    through order_source_ranks. Both are read with the SAME tag rule."""
    v = json.loads(Path(vetting).read_text())
    lineups = v.get("lineups")
    if not isinstance(lineups, list) or not lineups:
        raise LayoutError(f"vetting file {vetting} holds no lineups")
    if "position" in lineups[0]:
        if len(lineups) != n_rows:
            raise LayoutError(f"vetting file {vetting} describes {len(lineups)} rows, the book has {n_rows}")
        return {int(x["position"]) - 1 for x in lineups if _injury_flagged(x.get("flags"))}
    order = v.get("order_source_ranks")
    if not isinstance(order, list) or len(order) != n_rows:
        raise LayoutError(f"vetting file {vetting} has no order_source_ranks for the {n_rows}-row book")
    by_rank = {int(x["rank"]): x for x in lineups}
    out = set()
    for pos, src in enumerate(order):
        lu = by_rank.get(int(src))
        if lu is None:
            raise LayoutError(f"vetting file {vetting}: source rank {src} has no lineup record")
        if _injury_flagged(lu.get("flags")):
            out.add(pos)
    return out


LIVE_FLAG_STATUSES = {"Q", "D", "O", "OUT", "IR", "QUESTIONABLE", "DOUBTFUL", "PUP", "NFI", "SUS"}
QB_NOTE_TAGS = ("qb", "backup_qb")


def live_flagged_positions(vetting: Path, n_rows: int, book_rows: list[list[str]], live_status: Path) -> set[int]:
    """Refinement 1 (operator, 2026-09-24; run after the Sunday inactives): a row is flagged when any player's CURRENT
    DraftKings status is Q/D/O/IR, or the vetting gave it a QB-availability note (DK does not carry those). The Friday
    injury-report tag is not used: DK drops Q when a player is declared active, the report never clears.
    `live_status` is a CSV snapshot (id = dk_player_id, status) taken at run time, kept for the audit trail."""
    v = json.loads(Path(vetting).read_text())
    lineups = v.get("lineups")
    if not isinstance(lineups, list) or not lineups or "position" not in lineups[0] or len(lineups) != n_rows:
        raise LayoutError(f"the live flag rule needs the final vetting by position for the {n_rows}-row book")
    with open(live_status, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"id", "status"} <= set(rows[0]):
        raise LayoutError(f"live status snapshot {live_status} lacks id/status")
    status = {str(r["id"]): str(r.get("status") or "").upper() for r in rows}
    missing = {p for row in book_rows for p in row} - set(status)
    if missing:
        raise LayoutError(f"the live status snapshot lacks {len(missing)} of the book's players (wrong draft group?)")
    qb = {int(x["position"]) - 1 for x in lineups
          if any(str(t).split(":", 1)[0] in QB_NOTE_TAGS for tags in (x.get("flags") or {}).values() for t in tags)}
    return qb | {i for i, row in enumerate(book_rows) if any(status[p] in LIVE_FLAG_STATUSES for p in row)}


def check_aligned(book_rows: list[list[str]], upload_rows: list[list[str]]) -> None:
    """The book (dk_player_id) and the upload (draftable ids) must be the same lineups in the same order: every
    player id maps to exactly one draftable id and back, slot for slot. A shifted or foreign upload breaks that."""
    if len(book_rows) != len(upload_rows):
        raise LayoutError(f"book has {len(book_rows)} rows, upload has {len(upload_rows)}")
    fwd: dict[str, str] = {}
    back: dict[str, str] = {}
    for r, (b, u) in enumerate(zip(book_rows, upload_rows)):
        if len(b) != len(u):
            raise LayoutError(f"row {r + 1}: book and upload hold different slot counts")
        for pid, did in zip(b, u):
            if fwd.setdefault(pid, did) != did or back.setdefault(did, pid) != pid:
                raise LayoutError(f"row {r + 1}: book and upload disagree (player {pid} / draftable {did}); "
                                  "they are not the same book in the same order")


def load_order(order: str, n_rows: int, *, book: Path | None, vetting: Path | None, sets: Path | None,
               pin_first: bool, upload_rows: list[list[str]] | None = None,
               protect: int = HEAD_TOP, live_status: Path | None = None) -> tuple[list[int], dict]:
    """The order over upload rows, and a record of how it was made. Fails closed on any missing input."""
    if order not in ORDERS:
        raise LayoutError(f"unknown ENTER_ORDER {order!r}; expected one of {ORDERS}")
    if order == "greedy":
        return list(range(n_rows)), {"order": "greedy"}
    for name, p in (("--book", book), ("--vetting", vetting), ("--sets", sets)):
        if p is None or not Path(p).is_file():
            raise LayoutError(f"ENTER_ORDER=fewest-low needs {name} (got {p!r}); set ENTER_ORDER=greedy to enter in "
                              "the book's own order")
    _, brows = _read_rows(Path(book))
    if len(brows) != n_rows:
        raise LayoutError(f"book {book} has {len(brows)} rows but the upload has {n_rows}; they must be the same book")
    if upload_rows is not None:
        check_aligned(brows, upload_rows)
    _, _brows = _read_rows(Path(book))
    flagged = (live_flagged_positions(Path(vetting), n_rows, _brows, Path(live_status)) if live_status
               else flagged_positions(Path(vetting), n_rows))
    with open(sets, newline="") as f:
        srows = list(csv.DictReader(f))
    if not srows or not {"dk_player_id", "set", "pos"} <= set(srows[0]):
        raise LayoutError(f"sets file {sets} lacks dk_player_id / set / pos")
    known = {str(r["dk_player_id"]) for r in srows}
    low_ids = {str(r["dk_player_id"]) for r in srows if r["set"] == "LOW"}
    skill_known = {str(r["dk_player_id"]) for r in srows if r["pos"] in ("QB", "RB", "WR", "TE")}
    book_ids = {pid for row in brows for pid in row[:8]}            # the eight skill/flex slots; DST is never LOW
    coverage = len(book_ids & known) / max(len(book_ids), 1)
    if coverage < MIN_SETS_COVERAGE:
        raise LayoutError(f"the sets file knows only {coverage:.0%} of the book's players (need "
                          f"{MIN_SETS_COVERAGE:.0%}): wrong week, wrong slate or wrong id form")
    clean = n_rows - len(flagged - ({0} if pin_first else set()))
    if clean < min(protect, n_rows):
        raise LayoutError(f"only {clean} clean rows for {protect} protected ranks; widen the book or relax the layout")
    perm = fewest_low_order(brows, low_ids, flagged, pin_first, protect=protect)
    counts = [sum(1 for pid in brows[i] if pid in low_ids) for i in range(n_rows)]
    return perm, {"order": "fewest-low", "sets": str(sets), "book": str(book), "vetting": str(vetting),
                  "pin_first": pin_first, "flagged_rows": len(flagged), "protected_ranks": protect,
                  "flag_rule": f"live DK status ({live_status})" if live_status else "vetting tags (INJURY_TAGS)", "sets_coverage": round(coverage, 4),
                  "low_players": len(low_ids), "skill_players_known": len(skill_known),
                  "low_count_first_10": [counts[i] for i in perm[:10]]}


def contest_rows(contests: list[dict], n_rows: int, layout: str, perm: list[int]) -> list[list[int]]:
    """Per contest, the UPLOAD row indices its entries take (ranks mapped through the order)."""
    ranks = assign_ranks(contests, layout)
    need = max((max(r) + 1 for r in ranks if r), default=0)
    if need > n_rows:
        raise LayoutError(f"the {layout} layout needs {need} distinct lineups but the book holds {n_rows}")
    return [[perm[r] for r in rs] for rs in ranks]


def frozen_contest_rows(contests: list[dict], bundle: Path, new_rows: list[list[str]],
                        receipt: Path | None = None) -> tuple[list[list[int]], dict]:
    """Swap re-publication (laptop review 2026-09-24, HIGH): a swap changes CELLS, never which book row a contest holds.

    The published bundle records its own upload (ENTER-all-rows-*-KEEPERS.csv, copied at publication); every contest's
    rows are located in it, and the new bundle takes the SAME row indices from the swapped upload. Nothing is re-ordered,
    so no lineup moves between contests (after a lock DraftKings cannot re-assign an entry). The swapped upload may differ
    from the bundle's only in the cells a swap receipt names (apply_swaps.py's <OUT_CSV>.swap.json) -- or, without a
    receipt, in at most one cell per changed row."""
    base_files = sorted(Path(bundle).glob("ENTER-all-rows-*-KEEPERS.csv"))
    if len(base_files) != 1:
        raise LayoutError(f"{bundle} holds {len(base_files)} ENTER-all-rows-*-KEEPERS.csv files; expected exactly one")
    base = _read_rows(base_files[0])[1]
    if len(base) != len(new_rows):
        raise LayoutError(f"the swapped upload has {len(new_rows)} rows, the published bundle's upload {len(base)}")
    index: dict[tuple, int] = {}
    for i, r in enumerate(base):
        if tuple(r) in index:
            raise LayoutError(f"the published upload repeats a lineup (rows {index[tuple(r)] + 1} and {i + 1})")
        index[tuple(r)] = i
    per = []
    for c in contests:
        f = Path(bundle) / enter_filename(c)
        if not f.is_file():
            raise LayoutError(f"the published bundle lacks {f.name}")
        rows = _read_rows(f)[1]
        try:
            per.append([index[tuple(r)] for r in rows])
        except KeyError:
            raise LayoutError(f"{f.name} holds a lineup that is not in the bundle's own upload") from None
        if len(rows) != int(c["entries"]):
            raise LayoutError(f"{f.name} holds {len(rows)} entries, contests.json says {c['entries']}")
    changed = {(i, j) for i, (a, b) in enumerate(zip(base, new_rows)) for j, (x, y) in enumerate(zip(a, b)) if x != y}
    if any(len(a) != len(b) for a, b in zip(base, new_rows)):
        raise LayoutError("the swapped upload changes a row's slot count")
    if receipt is not None and Path(receipt).is_file():
        rec = json.loads(Path(receipt).read_text())
        allowed = set()
        for sw in rec.get("swaps", []):                  # apply_swaps.py v1.1: row (1-based), slot_index, out.dd
            row, j = int(sw["row"]) - 1, int(sw["slot_index"])
            if base[row][j] != str(sw["out"]["dd"]):
                raise LayoutError(f"swap receipt row {row + 1} slot {j}: the published upload does not hold {sw['out']['dd']} there")
            allowed.add((row, j))
        if not changed <= allowed:
            raise LayoutError(f"the swapped upload changes cells the swap receipt does not name: {sorted(changed - allowed)[:5]}")
    else:
        per_row: dict[int, int] = {}
        for i, _ in changed:
            per_row[i] = per_row.get(i, 0) + 1
        if any(v > 1 for v in per_row.values()):
            raise LayoutError("without a swap receipt, a row may change in at most one cell")
    return per, {"order": "frozen (swap re-publication)", "bundle": str(bundle), "changed_cells": len(changed),
                 "rows_changed": sorted({i + 1 for i, _ in changed}), "receipt": str(receipt) if receipt else None}


def label(c: dict) -> str:
    return f"{c['name']}-{c['contest_id']}"


def enter_filename(c: dict) -> str:
    return f"ENTER-{label(c)}-{int(c['entries'])}-entries-KEEP-first-{int(c['keep'])}.csv"


def _ranges(xs: list[int]) -> str:
    xs = [x + 1 for x in xs]
    if not xs:
        return "-"
    out, a, b = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == b + 1:
            b = x
        else:
            out.append(f"{a}" if a == b else f"{a}-{b}"); a = b = x
    out.append(f"{a}" if a == b else f"{a}-{b}")
    return ",".join(out)


def write(contests: list[dict], upload: Path, stage: Path, layout: str, perm_info: tuple[list[int], dict],
          frozen: list[list[int]] | None = None) -> list[str]:
    hdr, body = _read_rows(upload)
    perm, info = perm_info
    per = frozen if frozen is not None else contest_rows(contests, len(body), layout, perm)
    stage.mkdir(parents=True, exist_ok=True)
    lines = [f"layout {layout}; order {info['order']}; {sum(len(r) for r in per)} entries from "
             f"{len(set(x for r in per for x in r))} distinct book rows of {len(body)}"]
    if info["order"] != "greedy":
        lines.append("order record: " + json.dumps(info, sort_keys=True))
    ranks = assign_ranks(contests, layout) if frozen is None else [[] for _ in contests]
    for c, rows, rk in zip(contests, per, ranks):
        with open(stage / enter_filename(c), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            w.writerows(body[i] for i in rows)
        lines.append(f"{label(c)}: {len(rows)} entries = ranks {_ranges(rk) if rk else 'frozen'} (book rows {_ranges(sorted(rows))}; "
                     f"keep {int(c['keep'])}) -> {enter_filename(c)}")
    return lines


def check(contests: list[dict], upload: Path, stage: Path, layout: str, perm_info: tuple[list[int], dict],
          frozen: list[list[int]] | None = None) -> list[str]:
    _, body = _read_rows(upload)
    per = frozen if frozen is not None else contest_rows(contests, len(body), layout, perm_info[0])
    bad = []
    for c, rows in zip(contests, per):
        f = stage / enter_filename(c)
        if not f.is_file():
            bad.append(f"MISSING {f.name}")
            continue
        got = _read_rows(f)[1]
        if got != [body[i] for i in rows]:
            bad.append(f"MISMATCH {label(c)}: staged rows != layout-mapped upload rows ({layout}, {perm_info[1]['order']})")
    return bad


def _contests(path: Path) -> list[dict]:
    c = json.loads(Path(path).read_text())
    c = c if isinstance(c, list) else c.get("contests")
    if not isinstance(c, list) or not c:
        raise LayoutError("contests.json must be a non-empty list")
    return c


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["write", "check", "rows-needed"])
    ap.add_argument("contests", type=Path)
    ap.add_argument("upload", type=Path, nargs="?")
    ap.add_argument("stage", type=Path, nargs="?")
    ap.add_argument("--layout", default=os.environ.get("ENTER_LAYOUT") or "sequential")
    ap.add_argument("--order", default=os.environ.get("ENTER_ORDER") or "greedy")
    ap.add_argument("--book", type=Path)
    ap.add_argument("--vetting", type=Path)
    ap.add_argument("--sets", type=Path, default=Path(os.environ["OWNERSHIP_SETS"]) if os.environ.get("OWNERSHIP_SETS") else None)
    ap.add_argument("--pin-first", action="store_true")
    ap.add_argument("--frozen-bundle", type=Path,
                    default=Path(os.environ["ENTER_FROZEN_BUNDLE"]) if os.environ.get("ENTER_FROZEN_BUNDLE") else None,
                    help="swap re-publication: keep this published bundle's row->contest map, change cells only")
    ap.add_argument("--swap-receipt", type=Path, default=None, help="apply_swaps.py receipt (default: UPLOAD.swap.json)")
    ap.add_argument("--live-status", type=Path,
                    default=Path(os.environ["ENTER_LIVE_STATUS"]) if os.environ.get("ENTER_LIVE_STATUS") else None,
                    help="refinement 1: a DK status snapshot (id,status); flags come from it instead of the report")
    a = ap.parse_args(argv)
    contests = _contests(a.contests)
    if a.cmd == "rows-needed":
        print(rows_needed(contests, a.layout))
        return 0
    if a.upload is None or a.stage is None:
        raise LayoutError(f"{a.cmd} needs UPLOAD_CSV and STAGE_DIR")
    body = _read_rows(a.upload)[1]
    if a.frozen_bundle is not None:
        receipt = a.swap_receipt or Path(str(a.upload) + ".swap.json")
        frozen, info = frozen_contest_rows(contests, a.frozen_bundle, body, receipt if receipt.is_file() else None)
        fz = (list(range(len(body))), info)
        if a.cmd == "write":
            print("\n".join(write(contests, a.upload, a.stage, a.layout, fz, frozen=frozen)))
            return 0
        bad = check(contests, a.upload, a.stage, a.layout, fz, frozen=frozen)
        for b in bad:
            print(b)
        print("staged bundle == the published bundle's row map with the swapped cells:", not bad)
        return 1 if bad else 0
    perm_info = load_order(a.order, len(body), book=a.book, vetting=a.vetting, sets=a.sets, pin_first=a.pin_first,
                           upload_rows=body, protect=protected_ranks(contests, a.layout), live_status=a.live_status)
    if a.cmd == "write":
        print("\n".join(write(contests, a.upload, a.stage, a.layout, perm_info)))
        return 0
    bad = check(contests, a.upload, a.stage, a.layout, perm_info)
    for b in bad:
        print(b)
    print(f"staged bundle == upload rows under the {a.layout} layout and {perm_info[1]['order']} order:", not bad)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LayoutError as exc:
        print(f"enter_layout: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
