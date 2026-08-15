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

import numpy as np
import pandas as pd

from .export import _entries_layout, _is_locked


RECOURSE_STATE_VERSION = "prospective-recourse-state-v1"
RECOURSE_POLICY_VERSION = "prospective-recourse-policy-v1"
ALIVE_REACH_PROBABILITY = 0.05
MARGINAL_REACH_PROBABILITY = 0.005
SKILL_POSITIONS = {"RB", "WR", "TE"}
RECOURSE_TAIL_GRID = (240.0, 230.0, 220.0, 210.0, 200.0, 194.0, 187.0)
MAX_RECOURSE_ALTERNATIVES = 24


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
    normalized = []
    for value in information.available_at.tolist():
        try:
            normalized.append(
                _aware_timestamp(value, "information available_at")
                .tz_convert("UTC")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "late-swap information contains invalid or timezone-naive "
                "available_at"
            ) from exc
    available = pd.Series(
        pd.to_datetime(normalized, utc=True), index=information.index,
        dtype="datetime64[ns, UTC]",
    )
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


def _recourse_catalog(player_catalog: pd.DataFrame) -> pd.DataFrame:
    required = {"dk_id", "pos", "salary", "kickoff"}
    missing = required - set(player_catalog.columns)
    if missing:
        raise ValueError(
            "recourse player catalog missing " + ", ".join(sorted(missing))
        )
    catalog = player_catalog.copy()
    catalog["dk_id"] = catalog.dk_id.astype(str)
    if catalog.dk_id.eq("").any() or catalog.dk_id.duplicated().any():
        raise ValueError("recourse catalog dk_id must be nonempty and unique")
    catalog["pos"] = catalog.pos.astype(str).str.upper()
    catalog["salary"] = pd.to_numeric(catalog.salary, errors="coerce")
    catalog["_kickoff"] = pd.to_datetime(
        catalog.kickoff, errors="coerce", utc=True
    )
    if catalog.salary.isna().any() or catalog._kickoff.isna().any():
        raise ValueError("recourse catalog salary/kickoff is incomplete")
    return catalog.set_index("dk_id", drop=False)


def _normalize_classic_roster(
    roster: Sequence[str | int], catalog: pd.DataFrame, label: str,
) -> tuple[str, ...]:
    ids = tuple(str(value) for value in roster)
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError(f"{label} must contain nine unique players")
    unknown = set(ids) - set(catalog.index)
    if unknown:
        raise ValueError(f"{label} contains unknown players: {sorted(unknown)}")
    rows = catalog.loc[list(ids)]
    counts = rows.pos.value_counts().to_dict()
    legal = (
        counts.get("QB", 0) == 1
        and counts.get("DST", 0) == 1
        and counts.get("RB", 0) >= 2
        and counts.get("WR", 0) >= 3
        and counts.get("TE", 0) >= 1
        and sum(counts.get(pos, 0) for pos in SKILL_POSITIONS) == 7
    )
    if not legal:
        raise ValueError(f"{label} is not a legal classic position roster")
    salary = float(rows.salary.sum())
    if not 0 < salary <= 50_000:
        raise ValueError(f"{label} has illegal salary {salary:g}")
    return tuple(sorted(ids))


def _simulated_book_objective(book_max: np.ndarray) -> tuple:
    return (
        *(int(np.count_nonzero(book_max >= line))
          for line in RECOURSE_TAIL_GRID),
        float(np.quantile(book_max, 0.99)),
        float(np.mean(book_max)),
    )


def propose_recourse_rosters(
    entry_rosters: Mapping[str, Sequence[str | int]],
    candidate_rosters: Sequence[Sequence[str | int]],
    player_catalog: pd.DataFrame,
    remaining_world_scores: pd.DataFrame,
    points_information: pd.DataFrame,
    *,
    as_of,
    worlds_generated_at,
    score_kind: str = "remaining_after_as_of",
) -> dict:
    """Propose PIT-safe roster identities under the frozen recourse policy.

    ``remaining_world_scores`` must contain simulated *additional* fantasy
    points after ``as_of``. ``points_information`` supplies observed
    points-to-date, with columns ``dk_id``, ``points_to_date`` and
    ``available_at``. The function returns roster identities only; the
    DKEntries filler and :func:`validate_swap_upload` remain mandatory before
    an upload can be exposed.
    """
    if score_kind != "remaining_after_as_of":
        raise ValueError(
            "recourse v1 requires remaining_after_as_of simulated scores"
        )
    current = _aware_timestamp(as_of, "recourse policy as-of")
    generated = _aware_timestamp(
        worlds_generated_at, "recourse worlds generated-at"
    )
    if generated.tz_convert("UTC") > current.tz_convert("UTC"):
        raise ValueError("recourse worlds were generated after the decision")
    if not entry_rosters:
        raise ValueError("recourse policy requires at least one entry")

    catalog = _recourse_catalog(player_catalog)
    originals: dict[str, tuple[str, ...]] = {}
    for raw_entry_id, roster in entry_rosters.items():
        entry_id = str(raw_entry_id)
        if not entry_id or entry_id in originals:
            raise ValueError("recourse entries require unique nonempty ids")
        originals[entry_id] = _normalize_classic_roster(
            roster, catalog, f"entry {entry_id}"
        )
    if len(set(originals.values())) != len(originals):
        raise ValueError("recourse original book contains duplicate lineups")

    candidates: dict[tuple[str, ...], tuple[str, ...]] = {}
    for index, roster in enumerate(candidate_rosters):
        normalized = _normalize_classic_roster(
            roster, catalog, f"candidate {index}"
        )
        candidates.setdefault(normalized, normalized)
    if not candidates:
        raise ValueError("recourse policy requires candidate rosters")

    worlds = remaining_world_scores.copy()
    worlds.columns = [str(column) for column in worlds.columns]
    if worlds.empty or worlds.shape[1] == 0:
        raise ValueError("recourse remaining-world matrix is empty")
    if len(set(worlds.columns)) != len(worlds.columns):
        raise ValueError("recourse remaining-world columns repeat player ids")
    required_ids = set().union(*originals.values(), *candidates.values())
    missing_worlds = required_ids - set(worlds.columns)
    if missing_worlds:
        raise ValueError(
            "recourse remaining worlds omit players: "
            + ", ".join(sorted(missing_worlds))
        )
    worlds = worlds.loc[:, sorted(required_ids)].apply(
        pd.to_numeric, errors="coerce"
    )
    world_values = worlds.to_numpy(dtype=float)
    if not np.isfinite(world_values).all():
        raise ValueError("recourse remaining worlds contain nonfinite scores")

    info_required = {"dk_id", "points_to_date", "available_at"}
    missing_info = info_required - set(points_information.columns)
    if missing_info:
        raise ValueError(
            "recourse points information missing "
            + ", ".join(sorted(missing_info))
        )
    forbidden_info = {
        "actual_score", "final_score", "actual_ownership", "contest_rank",
        "payout", "roi",
    } & set(points_information.columns)
    if forbidden_info:
        raise ValueError(
            "recourse points information contains forbidden outcome columns: "
            + ", ".join(sorted(forbidden_info))
        )
    information_receipt = validate_information_as_of(
        points_information, current
    )
    info = points_information.copy()
    info["dk_id"] = info.dk_id.astype(str)
    if info.dk_id.eq("").any() or info.dk_id.duplicated().any():
        raise ValueError("recourse points information repeats a player")
    unknown_info = set(info.dk_id) - set(catalog.index)
    if unknown_info:
        raise ValueError(
            "recourse points information has unknown players: "
            + ", ".join(sorted(unknown_info))
        )
    info["points_to_date"] = pd.to_numeric(
        info.points_to_date, errors="coerce"
    )
    if not np.isfinite(info.points_to_date.to_numpy(dtype=float)).all():
        raise ValueError("recourse points-to-date contains nonfinite scores")
    kickoff_locked = catalog._kickoff.le(current.tz_convert("UTC"))
    unlocked_info = info.dk_id.map(~kickoff_locked).fillna(False)
    if info.loc[unlocked_info & info.points_to_date.ne(0)].shape[0]:
        raise ValueError("recourse points exist for a player before kickoff")
    observed = info.set_index("dk_id").points_to_date.to_dict()

    column_index = {player_id: i for i, player_id in enumerate(worlds.columns)}
    score_cache: dict[tuple[str, ...], np.ndarray] = {}

    def roster_scores(roster: tuple[str, ...]) -> np.ndarray:
        if roster not in score_cache:
            indexes = [column_index[player_id] for player_id in roster]
            points = sum(float(observed.get(player_id, 0.0)) for player_id in roster)
            score_cache[roster] = world_values[:, indexes].sum(axis=1) + points
        return score_cache[roster]

    original_scores = {key: roster_scores(value) for key, value in originals.items()}
    reach = {
        entry_id: float(np.mean(scores >= 194.0))
        for entry_id, scores in original_scores.items()
    }
    reach_labels = classify_entry_reach(reach)
    entry_order = sorted(originals, key=lambda key: (reach[key], key))
    assignments = dict(originals)
    current_scores = dict(original_scores)
    changes: list[dict] = []
    alternatives_considered: dict[str, int] = {}

    def individual_order(roster: tuple[str, ...]) -> tuple:
        scores = roster_scores(roster)
        return (
            *(-int(np.count_nonzero(scores >= line))
              for line in RECOURSE_TAIL_GRID),
            -float(np.quantile(scores, 0.99)),
            -float(np.mean(scores)),
            roster,
        )

    for entry_id in entry_order:
        original = assignments[entry_id]
        locked = {
            player_id for player_id in original
            if bool(kickoff_locked.loc[player_id])
        }
        occupied = set(assignments.values()) - {original}
        compatible = [
            roster for roster in candidates
            if roster not in occupied and locked <= set(roster)
        ]
        compatible = sorted(compatible, key=individual_order)[
            :MAX_RECOURSE_ALTERNATIVES
        ]
        alternatives_considered[entry_id] = len(compatible)
        others = [
            scores for other_id, scores in current_scores.items()
            if other_id != entry_id
        ]
        base_other = (
            np.maximum.reduce(others)
            if others
            else np.full(len(worlds), -np.inf, dtype=float)
        )
        baseline_max = np.maximum(base_other, current_scores[entry_id])
        baseline_objective = _simulated_book_objective(baseline_max)
        choices: list[tuple[tuple, int, tuple[str, ...], np.ndarray]] = []
        for roster in compatible:
            scores = roster_scores(roster)
            objective = _simulated_book_objective(np.maximum(base_other, scores))
            overlap = len(set(original) & set(roster))
            choices.append((objective, overlap, roster, scores))
        if not choices:
            continue
        # Objective first, then minimum churn, then ascending canonical roster.
        choices.sort(key=lambda row: row[2])
        choices.sort(key=lambda row: row[1], reverse=True)
        choices.sort(key=lambda row: row[0], reverse=True)
        objective, overlap, replacement, replacement_scores = choices[0]
        if objective <= baseline_objective or replacement == original:
            continue
        assignments[entry_id] = replacement
        current_scores[entry_id] = replacement_scores
        changes.append({
            "entry_id": entry_id,
            "reach_class": reach_labels[entry_id],
            "players_out": sorted(set(original) - set(replacement)),
            "players_in": sorted(set(replacement) - set(original)),
            "overlap": overlap,
            "before_objective": list(baseline_objective),
            "after_objective": list(objective),
        })

    final_matrix = np.vstack([current_scores[key] for key in sorted(current_scores)])
    final_objective = _simulated_book_objective(final_matrix.max(axis=0))
    initial_matrix = np.vstack([original_scores[key] for key in sorted(original_scores)])
    initial_objective = _simulated_book_objective(initial_matrix.max(axis=0))
    return {
        "policy_version": RECOURSE_POLICY_VERSION,
        "state_version": RECOURSE_STATE_VERSION,
        "as_of": current.isoformat(),
        "worlds_generated_at": generated.isoformat(),
        "score_kind": score_kind,
        "tail_grid": list(RECOURSE_TAIL_GRID),
        "worlds": int(len(worlds)),
        "entries": len(originals),
        "unique_candidates": len(candidates),
        "max_alternatives_per_entry": MAX_RECOURSE_ALTERNATIVES,
        "entry_order": entry_order,
        "reach_probabilities": reach,
        "reach_classes": reach_labels,
        "alternatives_considered": alternatives_considered,
        "initial_book_objective": list(initial_objective),
        "final_book_objective": list(final_objective),
        "assignments": {key: list(value) for key, value in assignments.items()},
        "changes": changes,
        "changed_entries": len(changes),
        "information_receipt": information_receipt,
        "uses_points_to_date": True,
        "uses_post_decision_outcomes": False,
        "requires_upload_validation": True,
    }


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


def entry_rosters_from_csv(
    entries_csv: str, player_catalog: pd.DataFrame,
) -> dict[str, list[str]]:
    """Resolve an already-filled classic DKEntries file to DK roster ids."""
    slots, entries = _entry_rows(entries_csv)
    if slots != ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]:
        raise ValueError("recourse entries do not use classic DK slots")
    by_id, by_name = _catalog_lookups(player_catalog)
    rosters = {}
    for entry_id, row in entries.items():
        cells = row[4:4 + len(slots)]
        players = [_resolve_cell(cell, by_id, by_name) for cell in cells]
        ids = [str(player["dk_id"]) for player in players]
        if len(set(ids)) != 9:
            raise ValueError(f"recourse entry {entry_id} repeats a player")
        rosters[entry_id] = ids
    return rosters


def fill_entry_assignments_csv(
    entries_csv: str,
    assignments: Mapping[str, Sequence[str | int]],
    player_catalog: pd.DataFrame,
    *,
    as_of,
) -> tuple[str, dict]:
    """Fill exact entry-id assignments, then run the strict upload validator.

    Unlike the ordinary lineup exporter, this function never reassigns one
    proposed roster to another entry to minimize churn. The recourse policy's
    entry-specific locks and objective therefore remain bound to the exact DK
    Entry ID for which they were evaluated.
    """
    current = _aware_timestamp(as_of, "recourse assignment as-of")
    rows = list(csv.reader(io.StringIO(entries_csv)))
    header_index, first_slot, slots = _entries_layout(rows)
    if slots != ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]:
        raise ValueError("recourse assignments do not use classic DK slots")
    entry_rows: dict[str, list[str]] = {}
    for row in rows[header_index + 1:]:
        if not row or not row[0].strip():
            continue
        entry_id = row[0].strip()
        if entry_id in entry_rows:
            raise ValueError(f"DKEntries repeats entry id {entry_id}")
        if len(row) < first_slot + len(slots):
            row.extend([""] * (first_slot + len(slots) - len(row)))
        entry_rows[entry_id] = row
    normalized_assignments = {
        str(entry_id): [str(player_id) for player_id in roster]
        for entry_id, roster in assignments.items()
    }
    if set(normalized_assignments) != set(entry_rows):
        raise ValueError("recourse assignments differ from DK entry ids")

    catalog = _recourse_catalog(player_catalog)
    by_id, by_name = _catalog_lookups(player_catalog)
    current_utc = current.tz_convert("UTC")
    for entry_id, row in entry_rows.items():
        assigned = _normalize_classic_roster(
            normalized_assignments[entry_id],
            catalog,
            f"recourse assignment {entry_id}",
        )
        remaining = {player_id: by_id[player_id] for player_id in assigned}
        before_cells = row[first_slot:first_slot + len(slots)]
        before_players = [
            _resolve_cell(cell, by_id, by_name) for cell in before_cells
        ]
        locked_indexes = []
        for index, (cell, player) in enumerate(
            zip(before_cells, before_players, strict=True)
        ):
            locked = _is_locked(cell) or player["_kickoff"] <= current_utc
            if not locked:
                continue
            player_id = str(player["dk_id"])
            if player_id not in remaining:
                raise ValueError(
                    f"recourse assignment changes locked player in {entry_id}"
                )
            locked_indexes.append(index)
            remaining.pop(player_id)

        open_indexes = [
            index for index in range(len(slots)) if index not in locked_indexes
        ]
        # Hard position slots first, FLEX last. Within a slot, retain the
        # current player when possible, then use stable DK-id order.
        for index in sorted(
            open_indexes,
            key=lambda value: slots[value].upper() in {"FLEX", "UTIL"},
        ):
            slot = slots[index]
            before_id = str(before_players[index]["dk_id"])
            eligible = [
                player for player in remaining.values()
                if _position_fits(player["pos"], slot)
            ]
            if not eligible:
                raise ValueError(
                    f"recourse assignment cannot fill {slot} in {entry_id}"
                )
            player = next(
                (candidate for candidate in eligible
                 if str(candidate["dk_id"]) == before_id),
                min(eligible, key=lambda candidate: str(candidate["dk_id"])),
            )
            player_id = str(player["dk_id"])
            row[first_slot + index] = f"{player['name']} ({player_id})"
            remaining.pop(player_id)
        if remaining:
            raise ValueError(f"recourse assignment left players in {entry_id}")

    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    filled_csv = buffer.getvalue()
    receipt = validate_swap_upload(
        entries_csv,
        filled_csv,
        player_catalog,
        as_of=current,
    )
    return filled_csv, receipt


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
    "MAX_RECOURSE_ALTERNATIVES",
    "MARGINAL_REACH_PROBABILITY",
    "RECOURSE_POLICY_VERSION",
    "RECOURSE_STATE_VERSION",
    "RECOURSE_TAIL_GRID",
    "StageBoundaries",
    "build_recourse_state",
    "classify_entry_reach",
    "entry_rosters_from_csv",
    "fill_entry_assignments_csv",
    "propose_recourse_rosters",
    "validate_information_as_of",
    "validate_swap_upload",
]
