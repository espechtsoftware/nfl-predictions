"""DraftKings classic lineup-upload CSV from slate-specific draftable IDs.

DraftKings' lineup import matches each cell on the slate-specific draftable
ID (the ``ID`` column of the DKSalaries export), not on the stable player ID
(README data-deficiency log, 2026-07-25).  The lab's ``live_week.py`` writes
``book.csv`` with ``dk_player_id`` and the Week-1 publisher records every
book entry's ``slot_dk_draftable_ids``; this module is the one place that
turns either into an importable file, and it fails closed on anything it
cannot prove: an unmapped id, a missing draftable id, a player in a slot its
position cannot fill, a repeated player, a repeated roster, or an output
path that already exists.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import csv
from hashlib import sha256
import json
import numbers
from pathlib import Path
from typing import Final

DK_SLOT_ORDER: Final = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
SLOT_ELIGIBLE: Final = {
    "QB": frozenset({"QB"}),
    "RB": frozenset({"RB"}),
    "WR": frozenset({"WR"}),
    "TE": frozenset({"TE"}),
    "FLEX": frozenset({"RB", "WR", "TE"}),
    "DST": frozenset({"DST"}),
}
ROSTER_SIZE: Final = len(DK_SLOT_ORDER)


class DkUploadCsvError(ValueError):
    """The lineups cannot be turned into a provably importable upload file."""


def _fail(message: str) -> None:
    raise DkUploadCsvError(message)


def _draftable_id(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        _fail(f"{label} is not a draftable id")
    if isinstance(value, numbers.Integral):
        value = int(value)  # numpy / pandas integer scalars
    if isinstance(value, float):
        if not value.is_integer():
            _fail(f"{label} is not an integer draftable id")
        value = int(value)
    if isinstance(value, str):
        if not value.strip().isdigit():
            _fail(f"{label} is not a numeric draftable id: {value!r}")
        value = int(value.strip())
    if type(value) is not int or value <= 0:
        _fail(f"{label} is not a positive draftable id")
    return value


def check_rows(
    rows: Sequence[Sequence[int]],
    *,
    position_by_draftable_id: Mapping[int, str] | None = None,
) -> list[list[int]]:
    """Validate slot rows: nine distinct ids, eligible positions, no repeats."""
    if not rows:
        _fail("no lineups to write")
    checked: list[list[int]] = []
    seen: set[frozenset[int]] = set()
    for ordinal, row in enumerate(rows):
        if len(row) != ROSTER_SIZE:
            _fail(f"lineup {ordinal} does not fill exactly {ROSTER_SIZE} slots")
        ids = [_draftable_id(v, label=f"lineup {ordinal} slot {i}")
               for i, v in enumerate(row)]
        if len(set(ids)) != ROSTER_SIZE:
            _fail(f"lineup {ordinal} repeats a draftable id")
        if position_by_draftable_id is not None:
            for slot, draftable in zip(DK_SLOT_ORDER, ids):
                position = position_by_draftable_id.get(draftable)
                if position is None:
                    _fail(f"lineup {ordinal}: id {draftable} is not on the slate")
                if str(position).upper() not in SLOT_ELIGIBLE[slot]:
                    _fail(
                        f"lineup {ordinal}: {position} cannot fill the {slot} slot"
                    )
        key = frozenset(ids)
        if key in seen:
            _fail(f"lineup {ordinal} repeats an earlier roster")
        seen.add(key)
        checked.append(ids)
    return checked


def rows_from_book_entries(
    entries: Sequence[Mapping[str, object]],
    *,
    position_by_draftable_id: Mapping[int, str] | None = None,
) -> list[list[int]]:
    """Rows from published book entries, in lineup-rank order."""
    if not entries:
        _fail("book has no entries")
    ranked: list[tuple[int, list[int]]] = []
    for ordinal, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or "slot_dk_draftable_ids" not in entry:
            _fail(f"book entry {ordinal} lacks slot_dk_draftable_ids")
        rank = entry.get("lineup_rank")
        if isinstance(rank, bool) or type(rank) is not int:
            _fail(f"book entry {ordinal} lacks an integer lineup_rank")
        slots = entry["slot_dk_draftable_ids"]
        if isinstance(slots, (str, bytes)) or not isinstance(slots, Sequence):
            _fail(f"book entry {ordinal} slot ids are not a sequence")
        ranked.append((rank, list(slots)))
    ranks = sorted(rank for rank, _ in ranked)
    if ranks != list(range(1, len(ranked) + 1)):
        _fail("book lineup ranks are not exactly 1..n")
    ordered = [row for _, row in sorted(ranked, key=lambda item: item[0])]
    return check_rows(ordered, position_by_draftable_id=position_by_draftable_id)


def rows_from_live_week_run(run_dir: Path) -> tuple[list[list[int]], dict]:
    """Rows from a lab ``live_week.py`` run: ``book.csv`` player ids mapped to
    draftable ids through that run's own ``frame.parquet``."""
    import pandas as pd

    book_path = run_dir / "book.csv"
    frame_path = run_dir / "frame.parquet"
    if not book_path.is_file() or not frame_path.is_file():
        _fail(f"{run_dir} lacks book.csv or frame.parquet")
    with book_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.reader(handle))
    if not csv_rows or tuple(csv_rows[0]) != DK_SLOT_ORDER:
        _fail("book.csv header is not the DraftKings classic slot order")
    frame = pd.read_parquet(frame_path)
    for column in ("dk_player_id", "dk_draftable_id", "position", "draft_group_id"):
        if column not in frame.columns:
            _fail(f"frame.parquet lacks {column}")
    groups = set(str(v) for v in frame["draft_group_id"].dropna().unique())
    if len(groups) != 1:
        _fail(f"frame.parquet spans {len(groups)} draft groups, expected one")
    player_ids = frame["dk_player_id"].astype(str)
    if player_ids.duplicated().any():
        _fail("frame.parquet repeats a dk_player_id")
    mapping: dict[str, tuple[int, str]] = {}
    for player_id, draftable, position in zip(
        player_ids, frame["dk_draftable_id"], frame["position"]
    ):
        if pd.isna(draftable):
            _fail(f"frame.parquet has no draftable id for dk_player_id {player_id}")
        mapping[player_id] = (
            _draftable_id(draftable, label=f"dk_player_id {player_id} draftable id"),
            str(position).upper(),
        )
    rows: list[list[int]] = []
    for ordinal, cells in enumerate(csv_rows[1:]):
        if len(cells) != ROSTER_SIZE:
            _fail(f"book.csv row {ordinal} does not have {ROSTER_SIZE} cells")
        row = []
        for cell in cells:
            key = cell.strip()
            if key not in mapping:
                _fail(
                    f"book.csv row {ordinal}: dk_player_id {key!r} is not in the frame"
                )
            row.append(mapping[key][0])
        rows.append(row)
    positions = {draftable: position for draftable, position in mapping.values()}
    checked = check_rows(rows, position_by_draftable_id=positions)
    receipt = {
        "source": "live-week-run-dir",
        "run_dir": str(run_dir),
        "draft_group_id": next(iter(groups)),
        "book_csv_sha256": sha256(book_path.read_bytes()).hexdigest(),
        "frame_parquet_sha256": sha256(frame_path.read_bytes()).hexdigest(),
        "id_form": "dk_player_id -> dk_draftable_id via the run's own frame",
    }
    return checked, receipt


def positions_from_salary_catalog(catalog: Mapping[str, object]) -> dict[int, str]:
    """Draftable id -> position from the published salary catalog's players."""
    rows = catalog.get("players") if isinstance(catalog, Mapping) else None
    if not isinstance(rows, Sequence) or not rows:
        _fail("salary catalog has no players")
    positions: dict[int, str] = {}
    for ordinal, row in enumerate(rows):
        if not isinstance(row, Mapping):
            _fail(f"salary catalog player {ordinal} is not an object")
        draftable = _draftable_id(
            row.get("draftable_id"), label=f"salary catalog player {ordinal} id"
        )
        position = row.get("pos")
        if not isinstance(position, str) or not position:
            _fail(f"salary catalog player {ordinal} lacks a position")
        if draftable in positions:
            _fail(f"salary catalog repeats draftable id {draftable}")
        positions[draftable] = position.upper()
    return positions


def slice_ranks(
    rows: Sequence[Sequence[int]], first: int, last: int
) -> list[list[int]]:
    """Rows for lineup ranks ``first..last`` inclusive (1-based, rank order)."""
    if isinstance(first, bool) or isinstance(last, bool):
        _fail("rank bounds must be integers")
    if type(first) is not int or type(last) is not int or first < 1 or last < first:
        _fail("rank range must satisfy 1 <= first <= last")
    if last > len(rows):
        _fail(f"rank range {first}-{last} exceeds the {len(rows)} available lineups")
    return [list(row) for row in rows[first - 1:last]]


def write_upload_csv(rows: Sequence[Sequence[int]], path: Path) -> dict:
    """Write the upload file create-only and return its receipt."""
    checked = check_rows(rows)
    if path.exists():
        _fail(f"refusing to overwrite {path}")
    lines = [",".join(DK_SLOT_ORDER)] + [",".join(str(v) for v in r) for r in checked]
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
    return {
        "path": str(path),
        "rows": len(checked),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "header": list(DK_SLOT_ORDER),
        "id_form": "dk_draftable_id",
    }


def read_upload_csv(path: Path) -> list[list[int]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or tuple(rows[0]) != DK_SLOT_ORDER:
        _fail("upload csv header is not the DraftKings classic slot order")
    return check_rows([[int(c) for c in r] for r in rows[1:]])


def canonical_receipt_json(receipt: Mapping[str, object]) -> str:
    return json.dumps(receipt, sort_keys=True, separators=(",", ":"))
