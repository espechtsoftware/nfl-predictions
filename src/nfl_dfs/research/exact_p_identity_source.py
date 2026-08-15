"""Reproduce and persist identity-only corrected exact-P oracle rosters."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from .final_forensic import TAILS, _solve_oracle, audit_roster


VERSION = "exact-p-corrected-identities-v1"
SCOPE = "phase-s-cbwu-54"
QB_STACK_MIN = 2
BRING_BACK_MIN = 1


def _require(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    if missing := columns - set(frame):
        raise ValueError(f"{label} lacks columns {sorted(missing)}")


def _roster(value: object) -> tuple[str, ...]:
    players = tuple(item for item in str(value).split(",") if item)
    if len(players) != 9 or len(set(players)) != 9:
        raise ValueError("corrected identity source encountered malformed roster")
    return players


def _source_records(source: dict[str, Any]) -> dict[tuple[int, int], float]:
    records = source.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("exact-stack source records are absent")
    result: dict[tuple[int, int], float] = {}
    for row in records:
        if not isinstance(row, dict) or not {
            "season", "week", "exact_p",
        } <= set(row):
            raise ValueError("exact-stack source record is malformed")
        key = (int(row["season"]), int(row["week"]))
        score = float(row["exact_p"])
        if key in result or not np.isfinite(score):
            raise ValueError("exact-stack source keys/scores are invalid")
        result[key] = score
    return result


def _tail_counts(scores: Sequence[float]) -> dict[str, int]:
    return {
        str(tail): int(sum(float(score) >= tail for score in scores))
        for tail in TAILS
    }


def derive_corrected_p_identities(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    exact_stack_source: dict[str, Any],
    *,
    expected_slates: int,
) -> dict[str, Any]:
    """Re-solve exact P and return a persisted object with identities only.

    Realized player outcomes are required to reproduce the already-published
    oracle, but no realized value is retained in the returned object.
    """
    key_columns = {"season", "week"}
    _require(
        players,
        key_columns
        | {"id", "pos", "team", "opp", "game_id", "salary", "actual"},
        "corrected identity players",
    )
    _require(candidates, key_columns | {"players"}, "corrected identity candidates")
    if any(column in candidates for column in (
        "actual", "actual_score", "actual_rank", "selected", "selected_rank",
        "actual_ownership", "rank", "payout", "winnings", "tag", "all_tags",
    )):
        raise ValueError("corrected identity candidate input is not identity-only")
    source_scores = _source_records(exact_stack_source)
    player_keys = {
        tuple(map(int, row))
        for row in players[["season", "week"]].drop_duplicates().to_numpy()
    }
    candidate_keys = {
        tuple(map(int, row))
        for row in candidates[["season", "week"]].drop_duplicates().to_numpy()
    }
    if player_keys != candidate_keys or player_keys != set(source_scores):
        raise ValueError("corrected identity slate populations differ")
    if len(player_keys) != int(expected_slates):
        raise ValueError(
            f"corrected identity source has {len(player_keys)} slates; "
            f"expected {int(expected_slates)}"
        )

    records: list[dict[str, Any]] = []
    reproduced_scores: list[float] = []
    for season, week in sorted(player_keys):
        pframe = players[
            players.season.eq(season) & players.week.eq(week)
        ].copy()
        support = {
            player
            for value in candidates.loc[
                candidates.season.eq(season) & candidates.week.eq(week),
                "players",
            ]
            for player in _roster(value)
        }
        if not support:
            raise ValueError("corrected identity candidate support is empty")
        solved = _solve_oracle(
            pframe,
            support,
            min_salary=49_000,
            salary_cap=50_000,
            qb_stack_min=QB_STACK_MIN,
            bring_back_min=BRING_BACK_MIN,
        )
        source_score = source_scores[(season, week)]
        if not np.isclose(
            float(solved["actual_score"]), source_score, rtol=0.0, atol=1e-6,
        ):
            raise ValueError("corrected exact-P score does not reproduce")
        roster = tuple(sorted(map(str, solved["players"])))
        audit = audit_roster(
            pframe,
            roster,
            min_salary=49_000,
            salary_cap=50_000,
            qb_stack_min=QB_STACK_MIN,
            bring_back_min=BRING_BACK_MIN,
        )
        if not audit["valid"] or not np.isclose(
            float(audit["actual_score"]), source_score, rtol=0.0, atol=1e-6,
        ):
            raise ValueError("corrected exact-P independent audit failed")
        records.append({
            "season": int(season),
            "week": int(week),
            "players": list(roster),
        })
        reproduced_scores.append(source_score)

    expected_tail = (
        exact_stack_source.get("tail_counts", {}).get("exact_p")
    )
    if expected_tail != _tail_counts(reproduced_scores):
        raise ValueError("corrected exact-P tail counts do not reproduce")
    if sum(len(row["players"]) for row in records) != 9 * int(expected_slates):
        raise ValueError("corrected exact-P slot count differs")
    return {
        "version": VERSION,
        "scope": SCOPE,
        "slates": int(expected_slates),
        "roster_slots": 9 * int(expected_slates),
        "production_stack_contract": {
            "qb_stack_min": QB_STACK_MIN,
            "bring_back_min": BRING_BACK_MIN,
            "min_salary": 49_000,
            "salary_cap": 50_000,
        },
        "identity_source_is_outcome_derived": True,
        "persisted_outcome_values": False,
        "persisted_candidate_scores_or_membership": False,
        "exact_stack_scores_reproduced": True,
        "exact_stack_tail_counts_reproduced": True,
        "all_rosters_independently_legal": True,
        "scientific_result_licensed": False,
        "production_change_licensed": False,
        "records": records,
    }


def preflight_receipt(result: dict[str, Any]) -> dict[str, Any]:
    """Strip every corrected identity from a source-preflight receipt."""
    if result.get("slates") != 18 or len(result.get("records", [])) != 18:
        raise ValueError("corrected identity preflight is not the 2023 panel")
    receipt = {key: value for key, value in result.items() if key != "records"}
    receipt["preflight_season"] = 2023
    receipt["identities_persisted"] = False
    return receipt


__all__ = [
    "BRING_BACK_MIN", "QB_STACK_MIN", "SCOPE", "VERSION",
    "derive_corrected_p_identities", "preflight_receipt",
]
