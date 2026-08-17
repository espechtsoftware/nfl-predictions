"""Strict identity-only frame preparation for the same-law capacity curve."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import pandas as pd

from .exact_p_generator_census import BASE_FAMILIES, _base_tags, canonical_roster
from .same_law_capacity_curve import BOOK_ORDER
from .same_law_capacity_generation import NEW_BOOKS, panel_id
from .same_law_capacity_sources import (
    EXACT_P_GENERATION,
    EXACT_P_SHA256,
    EXACT_P_URI,
    PRELOCK_ROW_HASH,
    PROTOCOL_SHA256,
    SEED_LEDGER_SHA256,
)


PLAYER_COLUMNS = {
    "season", "week", "id", "pos", "team", "opp", "game_id", "salary",
}
CANDIDATE_COLUMNS = {
    "panel_run_id", "season", "week", "cand_ix", "players", "tag", "all_tags",
}
EXACT_P_COLUMNS = {"season", "week", "players"}
EXISTING_PANELS = {
    f"20260813-sis-asoe-treatment-r{index}-v1": f"R{index}"
    for index in range(5)
}
NEW_PANELS = {panel_id(replicate): replicate for replicate in NEW_BOOKS}
PANEL_TO_BOOK = {**EXISTING_PANELS, **NEW_PANELS}
SLATE_GRID = {
    (season, week)
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
}


def _strict_columns(frame: pd.DataFrame, expected: set[str], label: str) -> None:
    if set(frame) != expected:
        raise ValueError(f"capacity {label} columns differ")


def _validate_source_binding(binding: Mapping[str, Any]) -> None:
    fixed = {
        "version": "same-law-capacity-source-binding-v1",
        "run_id": "20260817-same-law-capacity-curve-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "seed_ledger_sha256": SEED_LEDGER_SHA256,
        "prelock_row_hash": PRELOCK_ROW_HASH,
        "prelock_candidate_rows": 68493,
        "prelock_slates": 54,
        "new_books": 45,
        "new_book_slate_cells": 2430,
        "exact_p_uri": EXACT_P_URI,
        "exact_p_generation": EXACT_P_GENERATION,
        "exact_p_sha256": EXACT_P_SHA256,
        "exact_p_slates": 54,
        "uses_realized_outcome_values": False,
        "uses_outcome_derived_exact_p_identity": True,
        "candidate_scores_inspected": False,
        "capacity_statistics_computed": False,
        "production_change_licensed": False,
        "disposition": "valid-immutable-capacity-sources",
    }
    if any(binding.get(key) != value for key, value in fixed.items()):
        raise ValueError("capacity immutable source binding differs")
    if (
        set(binding) != set(fixed) | {
            "generation_validation_sha256", "new_candidate_rows",
        }
        or not isinstance(binding.get("new_candidate_rows"), int)
        or int(binding["new_candidate_rows"]) <= 0
        or not isinstance(binding.get("generation_validation_sha256"), str)
        or re.fullmatch(
            r"[0-9a-f]{64}", binding["generation_validation_sha256"],
        ) is None
    ):
        raise ValueError("capacity immutable source binding fields differ")


def _slates(frame: pd.DataFrame) -> set[tuple[int, int]]:
    return {
        (int(season), int(week))
        for season, week in frame[["season", "week"]].drop_duplicates().itertuples(
            index=False, name=None,
        )
    }


def _mechanics(completion: Mapping[str, Any]) -> dict[tuple[str, int, int], dict]:
    rows = completion.get("candidate_mechanics")
    if not isinstance(rows, list) or len(rows) != 2430:
        raise ValueError("capacity candidate mechanics population differs")
    result = {}
    expected_fields = {
        "replicate", "season", "week", "panel_run_id", "candidate_rows",
        "minimum_cand_ix", "maximum_cand_ix", "distinct_cand_ix",
        "families_present", "all_rosters_nine_unique", "all_rosters_legal",
    }
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != expected_fields:
            raise ValueError("capacity candidate mechanics fields differ")
        key = str(row["replicate"]), int(row["season"]), int(row["week"])
        if key in result:
            raise ValueError("capacity candidate mechanics cell repeats")
        if (
            key[0] not in NEW_BOOKS
            or (key[1], key[2]) not in SLATE_GRID
            or row["panel_run_id"] != panel_id(key[0])
            or int(row["candidate_rows"]) <= 0
            or int(row["minimum_cand_ix"]) != 0
            or int(row["maximum_cand_ix"]) != int(row["candidate_rows"]) - 1
            or int(row["distinct_cand_ix"]) != int(row["candidate_rows"])
            or tuple(sorted(map(str, row["families_present"])))
            != tuple(sorted(BASE_FAMILIES))
            or row["all_rosters_nine_unique"] is not True
            or row["all_rosters_legal"] is not True
        ):
            raise ValueError("capacity candidate mechanics identity differs")
        result[key] = dict(row)
    expected = {
        (replicate, season, week)
        for replicate in NEW_BOOKS
        for season, week in SLATE_GRID
    }
    if set(result) != expected:
        raise ValueError("capacity candidate mechanics grid differs")
    return result


def prepare_capacity_frames(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    exact_p: pd.DataFrame,
    source_binding: Mapping[str, Any],
    generation_completion: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Validate and normalize the complete frozen 50-book input population."""
    _validate_source_binding(source_binding)
    _strict_columns(players, PLAYER_COLUMNS, "player")
    _strict_columns(candidates, CANDIDATE_COLUMNS, "candidate")
    _strict_columns(exact_p, EXACT_P_COLUMNS, "exact-P")
    if players.empty or candidates.empty or exact_p.empty:
        raise ValueError("capacity frame population is empty")
    if _slates(players) != SLATE_GRID or _slates(candidates) != SLATE_GRID or \
            _slates(exact_p) != SLATE_GRID:
        raise ValueError("capacity frame slate grid differs")
    if len(exact_p) != 54 or exact_p.duplicated(["season", "week"]).any():
        raise ValueError("capacity exact-P frame population differs")
    if players.duplicated(["season", "week", "id"]).any():
        raise ValueError("capacity player identity repeats")
    salary = pd.to_numeric(players["salary"], errors="coerce")
    if salary.isna().any() or (salary <= 0).any():
        raise ValueError("capacity player salary differs")
    for value in exact_p["players"]:
        canonical_roster(value)

    panels = set(candidates["panel_run_id"].astype(str))
    if panels != set(PANEL_TO_BOOK):
        raise ValueError("capacity candidate panel population differs")
    normalized = candidates.copy()
    normalized["replicate"] = normalized["panel_run_id"].astype(str).map(
        PANEL_TO_BOOK
    )
    normalized["season"] = pd.to_numeric(normalized["season"], errors="raise").astype(int)
    normalized["week"] = pd.to_numeric(normalized["week"], errors="raise").astype(int)
    normalized["cand_ix"] = pd.to_numeric(
        normalized["cand_ix"], errors="raise",
    ).astype(int)
    if normalized.duplicated(
        ["replicate", "season", "week", "cand_ix"]
    ).any():
        raise ValueError("capacity candidate identity repeats")

    mechanics = _mechanics(generation_completion)
    book_order = {book: index for index, book in enumerate(BOOK_ORDER)}
    normalized["_book_order"] = normalized["replicate"].map(book_order)
    normalized = normalized.sort_values(
        ["_book_order", "season", "week", "cand_ix"], kind="stable",
    )
    observed_cells = set()
    for (replicate, season, week), group in normalized.groupby(
        ["replicate", "season", "week"], sort=False,
    ):
        key = str(replicate), int(season), int(week)
        observed_cells.add(key)
        indices = group["cand_ix"].tolist()
        if indices != list(range(len(group))):
            raise ValueError("capacity candidate indices are not contiguous")
        families = set()
        rosters = set()
        for row in group.itertuples(index=False):
            rosters.add(canonical_roster(row.players))
            families.update(_base_tags(row.all_tags, row.tag))
        if families != set(BASE_FAMILIES):
            raise ValueError("capacity candidate family population differs")
        if key[0] in NEW_BOOKS:
            expected = mechanics[key]
            if len(group) != int(expected["candidate_rows"]) or \
                    len(rosters) != len(group):
                raise ValueError("capacity candidate/mechanics row count differs")
    expected_cells = {
        (replicate, season, week)
        for replicate in BOOK_ORDER
        for season, week in SLATE_GRID
    }
    if observed_cells != expected_cells:
        raise ValueError("capacity candidate book/slate grid differs")

    existing_rows = int(normalized["replicate"].isin(BOOK_ORDER[:5]).sum())
    new_rows = len(normalized) - existing_rows
    if existing_rows != 68493 or new_rows != source_binding["new_candidate_rows"]:
        raise ValueError("capacity candidate source row count differs")
    expected_new_rows = sum(int(row["candidate_rows"]) for row in mechanics.values())
    if new_rows != expected_new_rows:
        raise ValueError("capacity candidate mechanics total differs")

    normalized = normalized.drop(columns=["panel_run_id", "_book_order"])[[
        "replicate", "season", "week", "cand_ix", "players", "tag", "all_tags",
    ]].reset_index(drop=True)
    prepared_players = players.sort_values(
        ["season", "week", "id"], kind="stable",
    ).reset_index(drop=True)
    prepared_exact_p = exact_p.sort_values(
        ["season", "week"], kind="stable",
    ).reset_index(drop=True)
    receipt = {
        "version": "same-law-capacity-frame-receipt-v1",
        "run_id": "20260817-same-law-capacity-curve-v1",
        "slates": 54,
        "books": 50,
        "book_slate_cells": 2700,
        "candidate_rows": len(normalized),
        "prelock_candidate_rows": existing_rows,
        "new_candidate_rows": new_rows,
        "player_rows": len(prepared_players),
        "exact_p_rows": len(prepared_exact_p),
        "uses_realized_outcome_values": False,
        "candidate_scores_inspected": False,
        "capacity_statistics_computed": False,
        "production_change_licensed": False,
        "disposition": "valid-identity-only-capacity-frames",
    }
    return prepared_players, normalized, prepared_exact_p, receipt


__all__ = [
    "CANDIDATE_COLUMNS",
    "EXACT_P_COLUMNS",
    "EXISTING_PANELS",
    "NEW_PANELS",
    "PANEL_TO_BOOK",
    "PLAYER_COLUMNS",
    "prepare_capacity_frames",
]
