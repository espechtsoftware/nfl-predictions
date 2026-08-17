"""Immutable, outcome-firewalled source binding for the capacity curve."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import Any

from .same_law_capacity_completion import validate_generation_completion


PROTOCOL_SHA256 = (
    "fbde9ba133ff09bcf7c019bf2232be407e6599397258742392b5501e82047128"
)
SEED_LEDGER_SHA256 = (
    "5838185cb2851a38c139d37959ea655a68dcd1aef534d804285f398586eae6fb"
)
PRELOCK_ROW_HASH = (
    "869a648ade3919b8942d8489795b208484c448ca73873cfcacede84effb13e7e"
)
EXACT_P_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-p-corrected-identities-v1/result.json"
)
EXACT_P_GENERATION = 1786831245271593
EXACT_P_SHA256 = (
    "ff456093841266cba1b0293dd56b0e2d5089588a61518568706900617eff6ad1"
)
EXPECTED_PANELS = tuple(
    f"20260813-sis-asoe-treatment-r{index}-v1" for index in range(5)
)
EXPECTED_PRELOCK_SUMMARY = {
    "row_count": 68493,
    "row_max": 9223349435193716713,
    "row_min": -9222899301205157495,
    "row_sum": "-1488571854430793341898",
    "row_xor": 1771716831806207312,
    "seasons": [2023, 2024, 2025],
    "slate_count": 54,
}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _validate_prelock(
    frozen: Mapping[str, Any], observed_summary: Mapping[str, Any],
) -> None:
    required = {
        "id", "expected_rows", "expected_slates", "panel_ids", "seasons",
        "prelock_row_hash", "prelock_candidate_summary",
        "outcome_columns_excluded",
    }
    if not required <= set(frozen):
        raise ValueError("capacity frozen prelock receipt is incomplete")
    if (
        frozen.get("id") != "phase-s-cbwu-54"
        or int(frozen.get("expected_rows", -1)) != 68493
        or int(frozen.get("expected_slates", -1)) != 54
        or tuple(frozen.get("panel_ids", ())) != EXPECTED_PANELS
        or list(frozen.get("seasons", ())) != [2023, 2024, 2025]
        or frozen.get("prelock_row_hash") != PRELOCK_ROW_HASH
        or frozen.get("prelock_candidate_summary") != EXPECTED_PRELOCK_SUMMARY
        or dict(observed_summary) != EXPECTED_PRELOCK_SUMMARY
        or set(frozen.get("outcome_columns_excluded", ())) != {
            "replay_candidates.actual_score",
            "replay_candidates.actual_rank",
            "slate_player_features.actual",
        }
    ):
        raise ValueError("capacity frozen/current prelock identity differs")


def _validate_exact_p(receipt: Mapping[str, Any]) -> None:
    if set(receipt) != {"uri", "generation", "sha256", "object"}:
        raise ValueError("capacity exact-P source receipt fields differ")
    source = receipt.get("object")
    if not isinstance(source, Mapping):
        raise ValueError("capacity exact-P source object is missing")
    sha = str(receipt.get("sha256", ""))
    if _canonical_sha256(source) != EXACT_P_SHA256:
        raise ValueError("capacity exact-P source bytes differ")
    if (
        receipt.get("uri") != EXACT_P_URI
        or int(receipt.get("generation", -1)) != EXACT_P_GENERATION
        or sha != EXACT_P_SHA256
        or re.fullmatch(r"[0-9a-f]{64}", sha) is None
        or source.get("version") != "exact-p-corrected-identities-v1"
        or source.get("mode") != "full"
        or source.get("scope") != "phase-s-cbwu-54"
        or int(source.get("slates", -1)) != 54
        or int(source.get("roster_slots", -1)) != 486
        or source.get("identity_source_is_outcome_derived") is not True
        or source.get("persisted_outcome_values") is not False
        or source.get("persisted_candidate_scores_or_membership") is not False
        or source.get("all_rosters_independently_legal") is not True
        or source.get("scientific_result_licensed") is not False
        or source.get("production_change_licensed") is not False
        or len(source.get("records", ())) != 54
    ):
        raise ValueError("capacity exact-P source identity differs")
    keys = set()
    for row in source["records"]:
        if not isinstance(row, Mapping) or set(row) != {"season", "week", "players"}:
            raise ValueError("capacity exact-P source record differs")
        players = tuple(map(str, row.get("players", ())))
        key = int(row.get("season", -1)), int(row.get("week", -1))
        if (
            key in keys
            or key[0] not in (2023, 2024, 2025)
            or key[1] not in range(1, 19)
            or len(players) != 9
            or len(set(players)) != 9
        ):
            raise ValueError("capacity exact-P source population differs")
        keys.add(key)
    if keys != {(season, week) for season in (2023, 2024, 2025) for week in range(1, 19)}:
        raise ValueError("capacity exact-P slate grid differs")


def validate_capacity_source_binding(
    manifest: Mapping[str, Any],
    completion: Mapping[str, Any],
    frozen_prelock: Mapping[str, Any],
    observed_prelock_summary: Mapping[str, Any],
    exact_p_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind the complete new generation to the immutable 1x and exact-P sources."""
    if (
        manifest.get("protocol_sha256") != PROTOCOL_SHA256
        or manifest.get("seed_ledger_sha256") != SEED_LEDGER_SHA256
    ):
        raise ValueError("capacity manifest protocol/seed binding differs")
    generation = validate_generation_completion(manifest, completion)
    _validate_prelock(frozen_prelock, observed_prelock_summary)
    _validate_exact_p(exact_p_receipt)
    result = {
        "version": "same-law-capacity-source-binding-v1",
        "run_id": "20260817-same-law-capacity-curve-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "seed_ledger_sha256": SEED_LEDGER_SHA256,
        "generation_validation_sha256": _canonical_sha256(generation),
        "prelock_row_hash": PRELOCK_ROW_HASH,
        "prelock_candidate_rows": 68493,
        "prelock_slates": 54,
        "new_books": 45,
        "new_book_slate_cells": 2430,
        "new_candidate_rows": generation["candidate_rows"],
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
    json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return result


__all__ = [
    "EXACT_P_GENERATION",
    "EXACT_P_SHA256",
    "EXACT_P_URI",
    "EXPECTED_PRELOCK_SUMMARY",
    "PRELOCK_ROW_HASH",
    "PROTOCOL_SHA256",
    "SEED_LEDGER_SHA256",
    "validate_capacity_source_binding",
]
