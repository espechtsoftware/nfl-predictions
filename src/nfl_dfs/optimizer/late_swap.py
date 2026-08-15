"""Fail-closed state and CSV validation for prospective staged late swap.

This module does not choose swaps.  It defines the information boundary and
validates a proposed DraftKings upload before the prospective recourse policy
can expose it to the operator.  Realized final outcomes are not inputs.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import io
import re
from collections.abc import Mapping, Sequence

import pandas as pd

from .export import _entries_layout, _is_locked


RECOURSE_STATE_VERSION = "prospective-recourse-state-v1"
ALIVE_REACH_PROBABILITY = 0.05
MARGINAL_REACH_PROBABILITY = 0.005
SKILL_POSITIONS = {"RB", "WR", "TE"}


class DecisionStage(str, Enum):
    INITIAL_LOCK = "initial_lock"
    LATE_AFTERNOON = "late_afternoon_recourse"
    SUNDAY_NIGHT = "sunday_night_recourse"
    CLOSED = "closed"


def _aware_timestamp(value, label: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return stamp


@dataclass(frozen=True)
class StageBoundaries:
    """Lock boundaries for one slate, fixed before the initial decision."""

    initial_lock: datetime | pd.Timestamp | str
    late_afternoon_lock: datetime | pd.Timestamp | str
    sunday_night_lock: datetime | pd.Timestamp | str | None = None

    def normalized(self) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp | None]:
        initial = _aware_timestamp(self.initial_lock, "initial lock")
        late = _aware_timestamp(self.late_afternoon_lock, "late-afternoon lock")
        night = (
            None
            if self.sunday_night_lock is None
            else _aware_timestamp(self.sunday_night_lock, "Sunday-night lock")
        )
        if late <= initial or (night is not None and night <= late):
            raise ValueError("late-swap stage boundaries must be strictly ordered")
        return initial, late, night

    def decision_stage(self, as_of) -> DecisionStage:
        initial, late, night = self.normalized()
        current = _aware_timestamp(as_of, "late-swap as-of")
        if current < initial:
            return DecisionStage.INITIAL_LOCK
        if current < late:
            return DecisionStage.LATE_AFTERNOON
        if night is not None and current < night:
            return DecisionStage.SUNDAY_NIGHT
        return DecisionStage.CLOSED


def validate_information_as_of(
    information: pd.DataFrame,
    as_of,
) -> dict:
    """Prove that every proposed policy input was available by ``as_of``."""
    if "available_at" not in information.columns:
        raise ValueError("late-swap information lacks available_at")
    current = _aware_timestamp(as_of, "information as-of")
    available = pd.to_datetime(information.available_at, errors="coerce", utc=True)
    if available.isna().any():
        raise ValueError("late-swap information contains invalid available_at")
    current_utc = current.tz_convert("UTC")
    future = available.gt(current_utc)
    if future.any():
        raise ValueError(
            f"late-swap information contains {int(future.sum())} future rows"
        )
    return {
        "state_version": RECOURSE_STATE_VERSION,
        "rows": int(len(information)),
        "as_of": current.isoformat(),
        "latest_available_at": (
            None if information.empty else available.max().isoformat()
        ),
        "future_rows": 0,
    }


def build_recourse_state(
    player_catalog: pd.DataFrame,
    boundaries: StageBoundaries,
    as_of,
) -> dict:
    """Return the deterministic locked/unlocked player state at one decision."""
    required = {"dk_id", "kickoff"}
    missing = required - set(player_catalog.columns)
    if missing:
        raise ValueError(
            "late-swap player catalog missing " + ", ".join(sorted(missing))
        )
    current = _aware_timestamp(as_of, "late-swap as-of")
    catalog = player_catalog.copy()
    catalog["dk_id"] = catalog.dk_id.astype(str)
    if catalog.dk_id.eq("").any() or catalog.dk_id.duplicated().any():
        raise ValueError("late-swap catalog dk_id must be nonempty and unique")
    kickoff = pd.to_datetime(catalog.kickoff, errors="coerce", utc=True)
    if kickoff.isna().any():
        raise ValueError("late-swap player catalog contains invalid kickoff")
    current_utc = current.tz_convert("UTC")
    locked = kickoff.le(current_utc)
    unlocked_times = kickoff[~locked]
    return {
        "state_version": RECOURSE_STATE_VERSION,
        "as_of": current.isoformat(),
        "decision_stage": boundaries.decision_stage(current).value,
        "locked_player_ids": sorted(catalog.loc[locked, "dk_id"].tolist()),
        "unlocked_player_ids": sorted(catalog.loc[~locked, "dk_id"].tolist()),
        "next_player_lock": (
            None if unlocked_times.empty else unlocked_times.min().isoformat()
        ),
    }


def classify_entry_reach(
    reach_probabilities: Mapping[str, float] | Sequence[tuple[str, float]],
) -> dict[str, str]:
    """Classify entries using the frozen pre-outcome conditional reach bands."""
    items = (
        reach_probabilities.items()
        if isinstance(reach_probabilities, Mapping)
        else reach_probabilities
    )
    result: dict[str, str] = {}
    for entry_id, probability in items:
        key = str(entry_id)
        value = float(probability)
        if not 0 <= value <= 1:
            raise ValueError("conditional reach probabilities must be in [0, 1]")
        if key in result:
            raise ValueError("entry reach probabilities repeat an entry id")
        if value >= ALIVE_REACH_PROBABILITY:
            result[key] = "alive"
        elif value >= MARGINAL_REACH_PROBABILITY:
            result[key] = "marginal"
        else:
            result[key] = "effectively_dead"
    return result


_CELL_SUFFIX = re.compile(r"\(([^()]*)\)\s*$")


def _cell_name(cell: str) -> str:
    return _CELL_SUFFIX.sub("", str(cell)).strip().upper()


def _cell_identifier(cell: str) -> str | None:
    match = _CELL_SUFFIX.search(str(cell))
    if not match:
        return None
    value = match.group(1).strip()
    return None if value.upper() == "LOCKED" else value


def _entry_rows(entries_csv: str) -> tuple[list[str], dict[str, list[str]]]:
    rows = list(csv.reader(io.StringIO(entries_csv)))
    header_index, first_slot, slots = _entries_layout(rows)
    entries: dict[str, list[str]] = {}
    for row in rows[header_index + 1:]:
        if not row or not row[0].strip():
            continue
        entry_id = row[0].strip()
        if entry_id in entries:
            raise ValueError(f"DKEntries repeats entry id {entry_id}")
        if len(row) < first_slot + len(slots):
            row = row + [""] * (first_slot + len(slots) - len(row))
        entries[entry_id] = row
    if not entries:
        raise ValueError("DKEntries contains no entry rows")
    return slots, entries


def _catalog_lookups(player_catalog: pd.DataFrame) -> tuple[dict, dict]:
    required = {"dk_id", "name", "pos", "salary", "kickoff"}
    missing = required - set(player_catalog.columns)
    if missing:
        raise ValueError(
            "late-swap validation catalog missing " + ", ".join(sorted(missing))
        )
    catalog = player_catalog.copy()
    catalog["dk_id"] = catalog.dk_id.astype(str)
    catalog["_name"] = catalog.name.astype(str).str.strip().str.upper()
    if catalog.dk_id.eq("").any() or catalog.dk_id.duplicated().any():
        raise ValueError("late-swap validation dk_id must be unique")
    if catalog["_name"].eq("").any() or catalog["_name"].duplicated().any():
        raise ValueError("late-swap validation names must be unique")
    catalog["pos"] = catalog.pos.astype(str).str.upper()
    catalog["salary"] = pd.to_numeric(catalog.salary, errors="coerce")
    catalog["_kickoff"] = pd.to_datetime(
        catalog.kickoff, errors="coerce", utc=True
    )
    if catalog.salary.isna().any() or catalog._kickoff.isna().any():
        raise ValueError("late-swap validation salary/kickoff is incomplete")
    records = catalog.to_dict("records")
    return (
        {str(row["dk_id"]): row for row in records},
        {str(row["_name"]): row for row in records},
    )


def _resolve_cell(cell: str, by_id: dict, by_name: dict) -> dict:
    identifier = _cell_identifier(cell)
    if identifier is not None and identifier in by_id:
        return by_id[identifier]
    name = _cell_name(cell)
    if name in by_name:
        return by_name[name]
    raise ValueError(f"DKEntries player cell is unresolved: {cell!r}")


def _position_fits(position: str, slot: str) -> bool:
    position = str(position).upper()
    slot = str(slot).upper()
    if slot in {"FLEX", "UTIL"}:
        return position in SKILL_POSITIONS
    return position == slot


def validate_swap_upload(
    original_csv: str,
    filled_csv: str,
    player_catalog: pd.DataFrame,
    *,
    as_of,
    allow_duplicate_lineups: bool = False,
) -> dict:
    """Validate a filled classic DKEntries upload against its source file.

    The check is stricter than DraftKings' parser: entry metadata and locked
    players cannot move, every slot must resolve and be position-legal, every
    lineup must be unique by default, and salary must be positive and no more
    than $50,000.  A successful receipt contains no player outcome.
    """
    current = _aware_timestamp(as_of, "swap validation as-of")
    original_slots, original = _entry_rows(original_csv)
    filled_slots, filled = _entry_rows(filled_csv)
    if original_slots != filled_slots or original_slots != [
        "QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"
    ]:
        raise ValueError("late-swap upload does not use classic DK slots")
    if set(original) != set(filled):
        raise ValueError("late-swap upload changed the entry-id population")
    by_id, by_name = _catalog_lookups(player_catalog)
    first_slot = 4
    current_utc = current.tz_convert("UTC")
    roster_keys: set[tuple[str, ...]] = set()
    changed_slots = 0
    locked_slots = 0
    salaries: list[int] = []

    for entry_id in sorted(original):
        before = original[entry_id]
        after = filled[entry_id]
        if before[:first_slot] != after[:first_slot]:
            raise ValueError(f"late-swap upload changed metadata for {entry_id}")
        before_cells = before[first_slot:first_slot + len(original_slots)]
        after_cells = after[first_slot:first_slot + len(original_slots)]
        before_players = [
            _resolve_cell(cell, by_id, by_name) for cell in before_cells
        ]
        after_players = [
            _resolve_cell(cell, by_id, by_name) for cell in after_cells
        ]
        after_ids = [str(player["dk_id"]) for player in after_players]
        if len(set(after_ids)) != len(after_ids):
            raise ValueError(f"late-swap upload repeats a player in {entry_id}")
        for index, (slot, old_cell, new_cell, old_player, new_player) in enumerate(
            zip(
                original_slots,
                before_cells,
                after_cells,
                before_players,
                after_players,
                strict=True,
            )
        ):
            if not _position_fits(new_player["pos"], slot):
                raise ValueError(
                    f"late-swap upload has illegal {slot} player in {entry_id}"
                )
            kickoff_locked = old_player["_kickoff"] <= current_utc
            marker_locked = _is_locked(old_cell)
            if kickoff_locked or marker_locked:
                locked_slots += 1
                if str(old_player["dk_id"]) != str(new_player["dk_id"]):
                    raise ValueError(
                        f"late-swap upload changes locked player in {entry_id} "
                        f"slot {index}"
                    )
                if marker_locked and old_cell != new_cell:
                    raise ValueError(
                        f"late-swap upload rewrites DK locked cell in {entry_id}"
                    )
            if str(old_player["dk_id"]) != str(new_player["dk_id"]):
                changed_slots += 1
        salary = int(sum(int(player["salary"]) for player in after_players))
        if salary <= 0 or salary > 50_000:
            raise ValueError(
                f"late-swap upload salary {salary} is illegal for {entry_id}"
            )
        salaries.append(salary)
        roster_key = tuple(sorted(after_ids))
        if not allow_duplicate_lineups and roster_key in roster_keys:
            raise ValueError("late-swap upload contains duplicate lineups")
        roster_keys.add(roster_key)

    return {
        "state_version": RECOURSE_STATE_VERSION,
        "valid": True,
        "as_of": current.isoformat(),
        "entries": len(original),
        "changed_slots": changed_slots,
        "locked_slots": locked_slots,
        "duplicate_lineups": len(original) - len(roster_keys),
        "minimum_salary": min(salaries),
        "maximum_salary": max(salaries),
        "allow_duplicate_lineups": bool(allow_duplicate_lineups),
        "uses_realized_outcomes": False,
    }


__all__ = [
    "ALIVE_REACH_PROBABILITY",
    "DecisionStage",
    "MARGINAL_REACH_PROBABILITY",
    "RECOURSE_STATE_VERSION",
    "StageBoundaries",
    "build_recourse_state",
    "classify_entry_reach",
    "validate_information_as_of",
    "validate_swap_upload",
]
