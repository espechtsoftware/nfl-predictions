"""Frozen, score-free registry for incremental paid-source ablations.

This registry deliberately defines source *states*, not source value.  The
Odds experiment isolates the common-lock player-prop override while retaining
the shipping 45/55 model/market blend in both cells.  The Fantasy Points/SIS
experiment is a retrieval-only four-cell crossing on one immutable candidate
population and one immutable world matrix.

Nothing in this module reads a source, an outcome, a cloud object, or a live
policy.  Every object it emits is diagnostic-only and grants no authority to
change generation, retrieval, production, graph, or contest allocation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final


REGISTRY_SCHEMA: Final = "paid-source-ablation-registry/v1"
ODDS_EXPERIMENT_ID: Final = "odds-common-lock-prop-override-v1"
MATCHUP_EXPERIMENT_ID: Final = "fp-sis-retrieval-only-cross-v1"

MODEL_WEIGHT: Final = 0.45
MARKET_WEIGHT: Final = 0.55
ODDS_STALE_REPORTING_AGE_SECONDS: Final = 24 * 60 * 60
ENTRY_BUDGET: Final = 80
MATCHUP_ADMISSION_CAP: Final = 200
MATCHUP_MINIMUM_SUPPORTED_PLAYERS: Final = 2
MATCHUP_MINIMUM_COMPLETENESS: Final = 0.5

ODDS_CELL_ORDER: Final = (
    "odds-prop-override-on-v1",
    "odds-prop-override-off-v1",
)
ODDS_CROSS_ORDER: Final = (
    ("odds-prop-override-on-v1", "odds-prop-override-on-v1"),
    ("odds-prop-override-on-v1", "odds-prop-override-off-v1"),
    ("odds-prop-override-off-v1", "odds-prop-override-on-v1"),
    ("odds-prop-override-off-v1", "odds-prop-override-off-v1"),
)
MATCHUP_CELL_ORDER: Final = (
    "fp-on-sis-on-v1",
    "fp-off-sis-on-v1",
    "fp-on-sis-off-v1",
    "fp-off-sis-off-v1",
)

FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_policy_change_licensed",
    "decision_authority",
    "fill_authority",
    "graph_authority",
    "historical_scoring_authority",
    "live_strategy_authority",
    "outcome_authority",
    "production_authority",
    "promotion_authority",
    "retrieval_authority",
    "scoring_authority",
    "source_value_established",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PaidSourceAblationRegistryV1Error(ValueError):
    """The paid-source registry differs from the frozen incremental tests."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PaidSourceAblationRegistryV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _policy() -> dict[str, object]:
    return {
        "evidence_class": "outcome-blind-source-influence-only",
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "value_claim": "not_evaluated",
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
    }


def _with_self_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    if field in value:
        raise PaidSourceAblationRegistryV1Error(
            f"{field} must not be supplied before hashing"
        )
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _odds_cells() -> list[dict[str, object]]:
    cells = []
    for ordinal, cell_id in enumerate(ODDS_CELL_ORDER):
        prop_override_enabled = ordinal == 0
        body = {
            "ordinal": ordinal,
            "cell_id": cell_id,
            "prop_override_enabled": prop_override_enabled,
            "prop_slice_action": (
                "retain-only-eligible-common-lock-prop-rows"
                if prop_override_enabled
                else "physically-remove-all-odds-prop-rows-before-market-vector"
            ),
            "model_weight": MODEL_WEIGHT,
            "market_weight": MARKET_WEIGHT,
            "market_value_when_prop_eligible": (
                "odds-api-player-prop-market-points"
                if prop_override_enabled
                else "draftkings-ppg-fallback"
            ),
            "market_value_when_prop_ineligible": "draftkings-ppg-fallback",
            "final_projection_law": "0.45-model-plus-0.55-market",
            "model-only-control_forbidden": True,
            "blend_model_weight_one_is_this_control": False,
        }
        cells.append({**body, "cell_sha256": canonical_sha256(body)})
    return cells


def _matchup_cells() -> list[dict[str, object]]:
    settings = ((True, True), (False, True), (True, False), (False, False))
    cells = []
    for ordinal, (cell_id, (fp_enabled, sis_enabled)) in enumerate(
        zip(MATCHUP_CELL_ORDER, settings, strict=True)
    ):
        body = {
            "ordinal": ordinal,
            "cell_id": cell_id,
            "fantasy_points_enabled": fp_enabled,
            "sis_enabled": sis_enabled,
            "fantasy_points_slice_action": (
                "retain-raw-slices"
                if fp_enabled
                else "physically-remove-raw-slices-before-components"
            ),
            "sis_slice_action": (
                "retain-raw-slices"
                if sis_enabled
                else "physically-remove-raw-slices-before-components"
            ),
            "joint_fp_sis_components_available": fp_enabled and sis_enabled,
            "candidate_generation": "not-run-byte-identical-input-authority",
            "candidate_turnover_expected": 0,
            "world_matrix_turnover_expected": 0,
            "retrieval_strategy_id": "coverage-194-v1",
            "admission_cap": MATCHUP_ADMISSION_CAP,
            "entry_budget": ENTRY_BUDGET,
        }
        cells.append({**body, "cell_sha256": canonical_sha256(body)})
    return cells


def frozen_paid_source_ablation_registry_v1() -> dict[str, object]:
    """Return the sole admitted source-state registry."""
    odds_cells = _odds_cells()
    matchup_cells = _matchup_cells()
    body: dict[str, object] = {
        "schema_version": REGISTRY_SCHEMA,
        "registry_id": "incremental-paid-source-ablation-registry-v1",
        "odds_experiment": {
            "experiment_id": ODDS_EXPERIMENT_ID,
            "estimand": "incremental-common-lock-player-prop-override",
            "model_weight": MODEL_WEIGHT,
            "market_weight": MARKET_WEIGHT,
            "staleness_reporting_age_seconds": (
                ODDS_STALE_REPORTING_AGE_SECONDS
            ),
            "staleness_policy": (
                "report-age-but-retain-every-latest-pre-common-lock-row"
            ),
            "historical_execution_gate": (
                "exact-point-in-time-draftkings-ppg-fallback-authority-for-"
                "every-preregistered-slate-and-player"
            ),
            "historical_panel_law": (
                "exact-identity-predeclared-ordered-slate-list-no-omissions"
            ),
            "consumer_parity_gate": (
                "explicit-per-row-prop-else-dk-ppg-market-vector-required-"
                "never-treat-nan-to-model-as-dk-ppg-fallback"
            ),
            "cells": odds_cells,
            "cell_manifest_sha256": canonical_sha256(odds_cells),
            "population_by_selection_world_cross_order": [
                {
                    "population_cell_id": population,
                    "selection_world_cell_id": selection,
                }
                for population, selection in ODDS_CROSS_ORDER
            ],
        },
        "matchup_experiment": {
            "experiment_id": MATCHUP_EXPERIMENT_ID,
            "estimand": "conditional-fantasy-points-sis-retrieval-value",
            "scope": "retrieval-only",
            "candidate_and_world_authority": "byte-identical-in-all-cells",
            "raw_slice_removal_stage": "before-component-calculation",
            "joint_component_law": (
                "unavailable-if-either-fantasy-points-or-sis-is-absent"
            ),
            "additive_vendor_effect_interpretation": (
                "forbidden-report-conditional-effects-and-interaction"
            ),
            "entry_budget": ENTRY_BUDGET,
            "admission_cap": MATCHUP_ADMISSION_CAP,
            "minimum_supported_players": MATCHUP_MINIMUM_SUPPORTED_PLAYERS,
            "minimum_completeness": MATCHUP_MINIMUM_COMPLETENESS,
            "cells": matchup_cells,
            "cell_manifest_sha256": canonical_sha256(matchup_cells),
        },
        "multiplicity_families": [
            "odds-prop-override-two-cell-family",
            "fantasy-points-by-sis-four-cell-family",
        ],
        "automatic_money_policy_change": "forbidden",
        **_policy(),
    }
    return _with_self_hash(body, field="registry_sha256")


def validate_paid_source_ablation_registry_v1(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        raise PaidSourceAblationRegistryV1Error(
            "paid-source registry must be a string-keyed object"
        )
    expected = frozen_paid_source_ablation_registry_v1()
    if canonical_json_bytes(dict(value)) != canonical_json_bytes(expected):
        raise PaidSourceAblationRegistryV1Error(
            "paid-source registry differs from the frozen incremental tests"
        )
    if expected["odds_experiment"]["model_weight"] == 1.0:
        raise PaidSourceAblationRegistryV1Error(
            "model-weight=1.0 is not the incremental prop-override control"
        )
    return expected


def odds_cell_v1(cell_id: str) -> dict[str, object]:
    registry = frozen_paid_source_ablation_registry_v1()
    for value in registry["odds_experiment"]["cells"]:
        if value["cell_id"] == cell_id:
            return dict(value)
    raise PaidSourceAblationRegistryV1Error(f"unknown Odds cell {cell_id!r}")


def matchup_cell_v1(cell_id: str) -> dict[str, object]:
    registry = frozen_paid_source_ablation_registry_v1()
    for value in registry["matchup_experiment"]["cells"]:
        if value["cell_id"] == cell_id:
            return dict(value)
    raise PaidSourceAblationRegistryV1Error(
        f"unknown Fantasy Points/SIS cell {cell_id!r}"
    )


def validate_cell_order_v1(
    values: Sequence[Mapping[str, object]], *, experiment: str,
) -> list[dict[str, object]]:
    expected = (
        [odds_cell_v1(cell_id) for cell_id in ODDS_CELL_ORDER]
        if experiment == "odds"
        else [matchup_cell_v1(cell_id) for cell_id in MATCHUP_CELL_ORDER]
        if experiment == "matchup"
        else None
    )
    if expected is None:
        raise PaidSourceAblationRegistryV1Error(
            f"unknown paid-source experiment {experiment!r}"
        )
    normalized = [dict(value) for value in values]
    if canonical_json_bytes(normalized) != canonical_json_bytes(expected):
        raise PaidSourceAblationRegistryV1Error(
            f"{experiment} cells differ from the frozen order"
        )
    return expected


def is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


__all__ = [
    "ENTRY_BUDGET",
    "FALSE_AUTHORITY_FIELDS",
    "MARKET_WEIGHT",
    "MATCHUP_ADMISSION_CAP",
    "MATCHUP_CELL_ORDER",
    "MATCHUP_MINIMUM_COMPLETENESS",
    "MATCHUP_MINIMUM_SUPPORTED_PLAYERS",
    "MODEL_WEIGHT",
    "ODDS_CELL_ORDER",
    "ODDS_CROSS_ORDER",
    "ODDS_STALE_REPORTING_AGE_SECONDS",
    "PaidSourceAblationRegistryV1Error",
    "canonical_json_bytes",
    "canonical_sha256",
    "frozen_paid_source_ablation_registry_v1",
    "matchup_cell_v1",
    "odds_cell_v1",
    "validate_paid_source_ablation_registry_v1",
]
