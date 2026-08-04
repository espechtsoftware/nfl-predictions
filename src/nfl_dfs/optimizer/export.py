"""DK upload CSV export, DKEntries filling, and exposure reporting.

DraftKings imports lineups two ways, both driven by draftable IDs — the
slate-specific "ID" column of DKSalaries.csv, not the stable playerId:

* draftkings.com/lineup/upload — a CSV with a slot header row and one
  lineup per row (`to_dk_csv` / `to_dk_showdown_csv`);
* Lineups -> Edit Entries — download DKEntries.csv for contests you've
  already entered, fill the slot cells, re-upload (`fill_entries_csv`).

On showdown slates the CPT slot only accepts the CPT-specific draftable
ID, which is why players carry a separate `cpt_dk_id`.
"""

from __future__ import annotations

import csv
import io
import itertools
from collections import Counter

from .lineup import Lineup
from .showdown import ShowdownLineup

DK_HEADER = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
DK_SHOWDOWN_HEADER = ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]

ENTRY_META_HEADER = ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]


def _cell(p: dict, captain: bool = False) -> str:
    """'Name (draftable_id)' as DK's upload parser expects. Falls back to
    the stable player ID for rows ingested before draftable IDs existed —
    DK rejects those, but a wrong-ID row beats a crash and the store layer
    warns when the fallback is in play."""
    if captain:
        pid = p.get("cpt_dk_id") or p.get("dk_id") or p["id"]
    else:
        pid = p.get("dk_id") or p["id"]
    return f"{p['name']} ({pid})"


def to_dk_csv(lineups: list[Lineup]) -> str:
    """DraftKings bulk-upload format: one row per lineup, players as
    'Name (draftable_id)' in slot order."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DK_HEADER)
    for lu in lineups:
        writer.writerow([_cell(p) for p in lu.slot_order()])
    return buf.getvalue()


def to_dk_showdown_csv(lineups: list[ShowdownLineup]) -> str:
    """DraftKings Showdown bulk-upload format: CPT first, then five FLEX.
    The CPT cell must carry the CPT-slot draftable ID."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DK_SHOWDOWN_HEADER)
    for lu in lineups:
        players = lu.slot_order()
        writer.writerow(
            [_cell(players[0], captain=True)] + [_cell(p) for p in players[1:]]
        )
    return buf.getvalue()


def _entries_layout(rows: list[list[str]]) -> tuple[int, int, list[str]]:
    """Locate the header row and slot columns of a DKEntries.csv.

    Returns (header_row_index, first_slot_column, slot_names). The slot
    names are the contiguous non-empty headers after 'Entry Fee' — DK pads
    the file to the right with instructions and the slate's player list,
    which the upload parser (and we) leave untouched.
    """
    for i, row in enumerate(rows):
        cells = [c.strip().lstrip("\ufeff") for c in row]  # DK files ship a BOM
        if cells[: len(ENTRY_META_HEADER)] == ENTRY_META_HEADER:
            slots = list(itertools.takewhile(
                lambda c: c, cells[len(ENTRY_META_HEADER):]
            ))
            if not slots:
                break
            return i, len(ENTRY_META_HEADER), slots
    raise ValueError(
        "Not a DKEntries.csv: no 'Entry ID,Contest Name,Contest ID,Entry Fee,"
        "<slots...>' header row found. Download it from DraftKings via "
        "Lineups -> Edit Entries."
    )


def entry_count(entries_csv: str) -> int:
    """Number of contest entries in a DKEntries.csv download."""
    rows = list(csv.reader(io.StringIO(entries_csv)))
    hdr, _, _ = _entries_layout(rows)
    return sum(1 for r in rows[hdr + 1:] if r and r[0].strip())


def _cell_name(cell: str) -> str:
    """'Justin Jefferson (12345678)' / 'X (LOCKED)' -> normalized name."""
    import re as _re

    return _re.sub(r"\s*\(.*\)\s*$", "", str(cell)).strip().upper()


def _is_locked(cell: str) -> bool:
    return "LOCKED" in str(cell).upper()


def assign_min_churn(current: list[list[str]],
                     lineups: list,
                     locked: list[set] | None = None) -> list[int]:
    """Assign generated lineups to entry rows MINIMIZING total player
    changes (2026-08-03, Thursday-entry workflow): the upload replaces
    by Entry ID either way, but a churn-minimizing assignment makes the
    Sunday diff reviewable and keeps locked players matched where
    possible. current[i] = normalized player names now in entry i.
    Returns lineup index per entry (lineups cycled if fewer)."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    n = len(current)
    pool = [lineups[i % len(lineups)] for i in range(n)]
    names = [{str(p.get("name", "")).strip().upper() for p in lu.players}
             for lu in pool]
    overlap = np.zeros((n, len(pool)))
    for i, cur in enumerate(current):
        cs = set(cur)
        for j, ns in enumerate(names):
            overlap[i, j] = len(cs & ns)
            # Lock-aware (2026-08-04 audit): a lineup missing an entry's
            # locked players can't be uploaded to that row — make such
            # pairs prohibitively costly so a compatible lineup isn't
            # assigned elsewhere while this row goes untouched and the
            # compatible lineup's coverage slot is silently stranded.
            if locked and locked[i] and not locked[i] <= ns:
                overlap[i, j] = -1e6
    r, c = linear_sum_assignment(-overlap)
    out = [0] * n
    for i, j in zip(r, c):
        out[i] = j % len(lineups)
    return out


def fill_entries_csv(
    entries_csv: str, lineups: list[Lineup] | list[ShowdownLineup],
    diff_out: list | None = None,
) -> str:
    """Fill a downloaded DKEntries.csv with generated lineups for re-upload.

    Assignment is churn-minimizing (see assign_min_churn): each entry
    gets the generated lineup most similar to what it already holds, so
    the Sunday late-swap diff is as small as the new set allows. Rows
    with LOCKED players (games already kicked off) are handled safely:
    if the assigned lineup contains every locked player, locked cells
    keep their original text and the rest fill around them; otherwise
    the ROW IS LEFT UNTOUCHED (DK would reject a locked-slot change) and
    flagged in the diff. Pass diff_out=[] to receive per-entry dicts:
    {entry_id, changed, out, in, locked, untouched}.
    """
    if not lineups:
        raise ValueError("No lineups to fill entries with")
    rows = list(csv.reader(io.StringIO(entries_csv)))
    hdr, first_slot, slots = _entries_layout(rows)
    size = len(lineups[0].slot_order())
    if len(slots) != size:
        raise ValueError(
            f"Entries file has {len(slots)} roster slots {slots} but lineups "
            f"have {size} players — classic vs showdown mismatch?"
        )
    is_cpt = [s.strip().upper() == "CPT" for s in slots]

    entry_rows = [r for r in rows[hdr + 1:] if r and r[0].strip()]
    current = [[_cell_name(c) for c in
                (r[first_slot:first_slot + size] + [""] * size)[:size]]
               for r in entry_rows]
    locked_by_row = []
    for r in entry_rows:
        cells = (r[first_slot:first_slot + size] + [""] * size)[:size]
        locked_by_row.append({_cell_name(c) for c in cells if _is_locked(c)})
    try:
        order = assign_min_churn(current, lineups, locked=locked_by_row)
    except Exception:  # scipy unavailable etc. — order-fill still correct
        order = [i % len(lineups) for i in range(len(entry_rows))]

    for i, row in enumerate(entry_rows):
        lu = lineups[order[i]]
        players = lu.slot_order()
        if len(row) < first_slot + size:
            row.extend([""] * (first_slot + size - len(row)))
        cells = row[first_slot:first_slot + size]
        locked_idx = [j for j, c in enumerate(cells) if _is_locked(c)]
        locked_names = {_cell_name(cells[j]) for j in locked_idx}
        new_names = {str(p.get("name", "")).strip().upper()
                     for p in players}
        d = {"entry_id": row[0], "locked": sorted(locked_names),
             "untouched": False, "out": [], "in": []}
        if locked_names and not locked_names <= new_names:
            d["untouched"] = True  # DK would reject; keep as entered
            if diff_out is not None:
                diff_out.append(d)
            continue
        if locked_idx:
            # keep locked cells verbatim; fill the open slots POSITION-
            # AWARE (2026-08-04 audit): sequential fill misaligned slots
            # whenever the locked player sat in a different slot index in
            # the new lineup's slot_order (e.g. locked FLEX cell, lineup
            # hard-slots him at RB) — every later cell shifted one slot
            # and DK would reject the row. Specific slots fill first,
            # FLEX/CPT take leftovers; if no eligible player remains for
            # a slot, the row is left untouched rather than invalid.
            rest = [p for p in players
                    if str(p.get("name", "")).strip().upper()
                    not in locked_names]

            def _fits(p, slot):
                s = str(slot).strip().upper()
                pos = str(p.get("pos", "")).upper()
                if s in ("FLEX", "UTIL"):
                    return pos in ("RB", "WR", "TE")
                if s == "CPT":
                    return True
                return pos == s

            open_slots = [j for j in range(size) if j not in locked_idx]
            fill: dict[int, dict] = {}
            feasible = True
            for j in sorted(open_slots, key=lambda j: str(slots[j]).strip()
                            .upper() in ("FLEX", "UTIL", "CPT")):
                pick = next((p for p in rest if _fits(p, slots[j])), None)
                if pick is None:
                    feasible = False
                    break
                rest.remove(pick)
                fill[j] = pick
            if not feasible:
                d["untouched"] = True
                if diff_out is not None:
                    diff_out.append(d)
                continue
            for j, p in fill.items():
                row[first_slot + j] = _cell(p, captain=is_cpt[j])
        else:
            for j, (p, cpt) in enumerate(zip(players, is_cpt)):
                row[first_slot + j] = _cell(p, captain=cpt)
        if diff_out is not None:
            cur_set = {c for c in current[i] if c}
            d["out"] = sorted(cur_set - new_names)
            d["in"] = sorted(new_names - cur_set)
            diff_out.append(d)

    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def showdown_exposure_summary(lineups: list[ShowdownLineup]) -> list[dict]:
    """Classic exposure plus how often each player is the captain."""
    exp = exposure_summary(lineups)
    cpt_counts = Counter(lu.captain["id"] for lu in lineups)
    n = len(lineups)
    for row in exp:
        row["cpt_lineups"] = cpt_counts.get(row["id"], 0)
        row["cpt_exposure"] = cpt_counts.get(row["id"], 0) / n
    return exp


def exposure_summary(lineups: list[Lineup]) -> list[dict]:
    """Player exposure across a lineup set, sorted by exposure descending."""
    if not lineups:
        return []
    counts: Counter[str] = Counter()
    meta: dict[str, dict] = {}
    for lu in lineups:
        for p in lu.players:
            counts[p["id"]] += 1
            meta[p["id"]] = p
    n = len(lineups)
    return [
        {
            "id": pid,
            "name": meta[pid]["name"],
            "pos": meta[pid]["pos"],
            "team": meta[pid]["team"],
            "salary": meta[pid]["salary"],
            "exposure": count / n,
            "lineups": count,
        }
        for pid, count in counts.most_common()
    ]
