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


def fill_entries_csv(
    entries_csv: str, lineups: list[Lineup] | list[ShowdownLineup]
) -> str:
    """Fill a downloaded DKEntries.csv with generated lineups for re-upload.

    Entry rows (those with an Entry ID) get lineups in order, cycling if
    there are more entries than lineups; every other cell — entry metadata,
    DK's instruction text, the player-list columns on the right — passes
    through untouched. Raises ValueError if the file isn't a DKEntries
    download or its slot count doesn't match the lineups (e.g. classic
    lineups into a showdown file).
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

    cycle = itertools.cycle(lineups)
    for row in rows[hdr + 1:]:
        if not row or not row[0].strip():
            continue  # player-list / instruction rows, not entries
        players = next(cycle).slot_order()
        if len(row) < first_slot + size:
            row.extend([""] * (first_slot + size - len(row)))
        for j, (p, cpt) in enumerate(zip(players, is_cpt)):
            row[first_slot + j] = _cell(p, captain=cpt)

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
