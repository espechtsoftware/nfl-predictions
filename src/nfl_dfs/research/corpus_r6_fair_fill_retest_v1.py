"""Outcome-blind fair fill/profile/selector historical retest lane.

This module closes the smallest useful execution gap between the existing
population challengers and the frozen R6 selector implementations.  A fill
runner supplies *audited candidate cells* (one fill strategy under one
construction profile); this module then:

* removes the held-out R-block occurrences before candidate admission,
* equalizes retained candidate counts across comparable cells,
* scores only the retained candidates on the four fit blocks,
* runs the three grouped selectors, their three rank-150 continuations, and
  the independent-shots selector, and
* evaluates frozen books on the held-out simulated block.

There is intentionally no object-store client, cloud launcher, realized-score
reader, deployment mutation, or production-default change here.  Missing
generation artifacts remain explicit registry/controller states.  In
particular, tagged incumbent family isolates are diagnostics, not causal
substitutes for regenerating the same family under F7--F9.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_extreme_tail_factorial_manifest as factorial,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as retrieval_runner
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as full_union
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as population_runtime,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as population_authority,
)
from nfl_dfs.research import (
    corpus_r6_population_crossed_cloud_v1 as population_cloud,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import residual_world_columns as rw


FILL_REGISTRY_SCHEMA: Final = "corpus-r6-fair-fill-registry/v1"
PROFILE_REGISTRY_SCHEMA: Final = "corpus-r6-fair-profile-registry/v1"
SELECTOR_REGISTRY_SCHEMA: Final = "corpus-r6-fair-selector-registry/v1"
CANDIDATE_CELL_SCHEMA: Final = "corpus-r6-fair-fill-candidate-cell/v1"
WORK_RECEIPT_SCHEMA: Final = "corpus-r6-fair-fill-work-receipt/v1"
FOLD_PLAN_SCHEMA: Final = "corpus-r6-fair-fill-fold-plan/v1"
CELL_PLAN_SCHEMA: Final = "corpus-r6-fair-fill-cell-plan/v1"
SELECTION_BINDING_SCHEMA: Final = "corpus-r6-fair-fill-selection-input/v1"
EVALUATION_BINDING_SCHEMA: Final = "corpus-r6-fair-fill-evaluation-input/v1"
SELECTOR_RESULT_SCHEMA: Final = "corpus-r6-fair-fill-selector-result/v1"
EVALUATION_RESULT_SCHEMA: Final = "corpus-r6-fair-fill-evaluation-result/v1"
CONTROLLER_SCHEMA: Final = "corpus-r6-fair-fill-retest-controller/v1"
CONTROL_SENSITIVITY_SCHEMA: Final = (
    "corpus-r6-fair-fill-incumbent-control-sensitivity/v1"
)
CONTROL_EVALUATION_SCHEMA: Final = (
    "corpus-r6-fair-fill-incumbent-control-evaluation/v1"
)

INCUMBENT_PROFILE_ID: Final = "F0-incumbent"
PROFILE_ORDER: Final = (INCUMBENT_PROFILE_ID, *profiles.PROFILE_ORDER)
FILL_STRATEGY_ORDER: Final = (
    "legacy-mix-v1",
    "boom-heavy-equal-work-v1",
    "all-boom-equal-work-v1",
    "all-boom-unique-fill-v1",
    "qbvar-expanded-equal-work-v1",
    "role-epistemic-control-v1",
    "game-stack-control-v1",
    "dark-game-control-v1",
    "per-world-exact-v1",
    "no-good-distinct-next-best-v1",
    "quality-diversity-reserve-v1",
)
FAMILY_CONTROL_TAG_BY_STRATEGY: Final = {
    "role-epistemic-control-v1": "epi",
    "game-stack-control-v1": "game",
    "dark-game-control-v1": "dark",
}
NATIVE_EQUAL_WORK_COHORT: Final = "native-tail-select-equal-attempt-v1"
UNIQUE_FILL_COHORT: Final = "native-tail-select-retained-count-only-v1"
PER_WORLD_EXACT_COHORT: Final = "per-world-exact-200-per-block-v1"
MINIMUM_COMMON_COUNT: Final = rank150.RANKING_DEPTH
MAXIMUM_COMMON_COUNT: Final = successor.MAX_CANDIDATES
INCUMBENT_CONTROL_IDS: Final = (
    "coverage-194-v1",
    "strict-200-coverage-v1",
    "tail-ladder-200-210-220-v1",
    "expected-max-v1",
)

_IDENTIFIER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_OCCURRENCE_FIELDS: Final = frozenset({
    "origin_id",
    "candidate_ordinal",
    "lineup_id",
    "roster_player_ids",
    "family_tags",
})
_WORK_FIELDS: Final = frozenset({
    "schema",
    "origin_id",
    "scheduled_optimizer_attempts",
    "attempted_optimizer_calls",
    "optimal_calls",
    "infeasible_calls",
    "error_calls",
    "retained_occurrence_count",
})
_CELL_FIELDS: Final = frozenset({
    "schema",
    "cell_id",
    "slate",
    "fill_strategy_id",
    "fill_strategy_sha256",
    "construction_profile_id",
    "comparison_cohort_id",
    "origin_order",
    "occurrence_count",
    "unique_lineup_count",
    "occurrences",
    "occurrences_sha256",
    "work_receipts",
    "work_receipts_sha256",
    "work_dose_sha256",
    "source_bindings",
    "source_bindings_sha256",
    "source_adapter_id",
    "profile_audit_complete",
    "source_authoritative",
    "comparison_role",
    "diagnostic_only",
    "test_only",
    "score_fields_present",
    "outcome_fields_read",
    "uses_realized_outcomes",
    "promotion_authority",
    "cell_sha256",
})
_FOLD_PLAN_FIELDS: Final = frozenset({
    "schema", "slate", "comparison_cohort_id", "heldout_block",
    "training_blocks", "cell_order", "source_candidate_cells",
    "source_candidate_cell_sha256s", "common_count", "common_count_law",
    "minimum_common_count", "maximum_common_count", "sample_seed_material",
    "sample_seed_material_sha256", "work_dose_sha256", "diagnostic_only",
    "cell_plans", "cell_plan_sha256s", "score_values_read_for_sampling",
    "heldout_score_values_read_for_sampling", "realized_outcomes_read",
    "test_only", "plan_sha256",
})
_CELL_PLAN_FIELDS: Final = frozenset({
    "schema", "cell_id", "cell_sha256", "fill_strategy_id",
    "construction_profile_id", "eligible_lineup_count",
    "eligible_candidate_rows", "eligible_candidate_rows_sha256",
    "sampled_lineup_count", "sampled_lineup_ids", "sampled_candidate_rows",
    "sampled_candidate_rows_sha256", "heldout_occurrences_excluded",
    "uses_realized_outcomes", "cell_plan_sha256",
})


class CorpusR6FairFillRetestV1Error(ValueError):
    """The fair crossed retest contract failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FairFillRetestV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _hash(value: object) -> str:
    return profiles.canonical_sha256_v1(value)


def _with_hash(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    body = dict(value)
    if field_name in body:
        _fail(f"{field_name} is already present")
    return {**body, field_name: _hash(body)}


def _identifier(value: object, *, label: str, maximum: int = 96) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > maximum
        or _IDENTIFIER.fullmatch(value) is None
    ):
        _fail(f"{label} must be one bounded canonical identifier")
    return value


def _strict_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _matrix_hash(value: np.ndarray, *, label: str) -> str:
    matrix = np.asarray(value)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.flags.c_contiguous
    ):
        _fail(f"{label} must be one C-contiguous float64 matrix")
    digest = sha256()
    digest.update(profiles.canonical_json_bytes_v1({
        "dtype": "float64-le",
        "shape": [int(item) for item in matrix.shape],
    }))
    digest.update(b"\0")
    digest.update(memoryview(np.ascontiguousarray(matrix, dtype="<f8")).cast("B"))
    return digest.hexdigest()


def _p0_environment_v1() -> dict[str, str]:
    return factorial.frozen_extreme_tail_factorial_p0_environment_v1()


def fill_generation_environment_v1(strategy_id: str) -> dict[str, str]:
    """Return a complete fill-only engine environment where one exists.

    F7--F9 construction still belongs to the request-local profile model; the
    returned environment must not be mistaken for ownership of those rules.
    """
    strategy = _identifier(strategy_id, label="fill strategy ID")
    environment = _p0_environment_v1()
    overrides: dict[str, str]
    if strategy == "legacy-mix-v1":
        overrides = {}
    elif strategy == "boom-heavy-equal-work-v1":
        overrides = {
            "N_LEV": "40",
            "N_BOOM": "160",
            "BOOM_UNIQUE_FILL": "0",
        }
    elif strategy == "all-boom-equal-work-v1":
        overrides = {"CAND_MULT": "0", "N_BOOM": "200", "BOOM_UNIQUE_FILL": "0"}
    elif strategy == "all-boom-unique-fill-v1":
        overrides = {"CAND_MULT": "0", "N_BOOM": "200", "BOOM_UNIQUE_FILL": "1"}
    elif strategy == "qbvar-expanded-equal-work-v1":
        overrides = {
            "CAND_MULT": "2",
            "N_BOOM": "8",
            "N_QB_VARIANTS": "8",
            "BOOM_UNIQUE_FILL": "0",
        }
    else:
        _fail(f"{strategy} has no standalone generation environment")
    environment.update(overrides)
    return dict(sorted(environment.items()))


def _nominal_slots(environment: Mapping[str, str]) -> dict[str, int]:
    """Describe planned slots; actual optimizer calls remain receipt authority."""
    return {
        "leverage": int(environment.get(
            "N_LEV", str(int(environment["CAND_MULT"]) * 80)
        )),
        "boom": int(environment["N_BOOM"]),
        "role_epistemic": int(environment["N_EPISTEMIC"]),
        "qbvar": 8 * int(environment["N_QB_VARIANTS"]),
        "game_stack": int(environment["N_GAMESTACK"]) * 3,
        "dark_game": int(environment["N_DARKGAME"]),
    }


def fill_strategy_registry_v1() -> dict[str, object]:
    """Return the outcome-blind fill registry and its artifact support limits."""
    rows: list[dict[str, object]] = []
    generation_rows = {
        "legacy-mix-v1": (
            "incumbent native family mix",
            NATIVE_EQUAL_WORK_COHORT,
            "existing-factorial-P0-adapter-for-F0; regeneration-required-for-F7-F9",
        ),
        "boom-heavy-equal-work-v1": (
            "reallocate 120 leverage slots to boom worlds (40/160)",
            NATIVE_EQUAL_WORK_COHORT,
            "generation-required",
        ),
        "all-boom-equal-work-v1": (
            "zero leverage and 200 fixed-attempt boom slots",
            NATIVE_EQUAL_WORK_COHORT,
            "generation-required",
        ),
        "all-boom-unique-fill-v1": (
            "frozen PB unique-fill comparator",
            UNIQUE_FILL_COHORT,
            "existing-factorial-PB-adapter-for-F0; not-equal-work-comparable",
        ),
        "qbvar-expanded-equal-work-v1": (
            "double QB variants and repay slots from boom",
            NATIVE_EQUAL_WORK_COHORT,
            "generation-required",
        ),
    }
    for ordinal, strategy_id in enumerate(FILL_STRATEGY_ORDER):
        if strategy_id in generation_rows:
            hypothesis, cohort, support = generation_rows[strategy_id]
            environment = fill_generation_environment_v1(strategy_id)
            nominal = _nominal_slots(environment)
            row = {
                "ordinal": ordinal,
                "strategy_id": strategy_id,
                "display_name": hypothesis,
                "strategy_kind": "generation-treatment",
                "hypothesis": hypothesis,
                "comparison_cohort_id": cohort,
                "generation_environment_sha256": _hash(environment),
                "environment_overrides_from_p0": {
                    key: value
                    for key, value in environment.items()
                    if _p0_environment_v1().get(key) != value
                },
                "nominal_solve_slots_by_family": nominal,
                "nominal_solve_slot_count": sum(nominal.values()),
                "actual_attempt_receipt_required": True,
                "artifact_support": support,
                "dose_status": (
                    "existing-frozen-law"
                    if strategy_id in {"legacy-mix-v1", "all-boom-unique-fill-v1"}
                    else "provisional-outcome-blind-controller-dose"
                ),
                "diagnostic_only": False,
            }
        elif strategy_id in FAMILY_CONTROL_TAG_BY_STRATEGY:
            tag = FAMILY_CONTROL_TAG_BY_STRATEGY[strategy_id]
            row = {
                "ordinal": ordinal,
                "strategy_id": strategy_id,
                "display_name": f"diagnostic {tag}-tag family isolate",
                "strategy_kind": "tagged-family-isolate",
                "hypothesis": f"diagnose incumbent candidates tagged {tag}",
                "comparison_cohort_id": "diagnostic-family-isolate-v1",
                "family_tag": tag,
                "generation_environment_sha256": None,
                "environment_overrides_from_p0": {},
                "nominal_solve_slots_by_family": {},
                "nominal_solve_slot_count": None,
                "actual_attempt_receipt_required": False,
                "artifact_support": (
                    "existing-tagged-incumbent-adapter-for-F0; relaxed-profile-"
                    "regeneration-required"
                ),
                "dose_status": "existing-tag-diagnostic-only",
                "diagnostic_only": True,
            }
        elif strategy_id == "per-world-exact-v1":
            row = {
                "ordinal": ordinal,
                "strategy_id": strategy_id,
                "display_name": "exact optimum for each scheduled world visit",
                "strategy_kind": "world-optimum-generation-treatment",
                "hypothesis": "one exact legal optimum per scheduled world visit",
                "comparison_cohort_id": PER_WORLD_EXACT_COHORT,
                "generation_environment_sha256": None,
                "environment_overrides_from_p0": {},
                "nominal_solve_slots_by_family": {"world_optimum": 1_000},
                "nominal_solve_slot_count": 1_000,
                "actual_attempt_receipt_required": True,
                "artifact_support": "existing-population-challenger-adapter-for-F7-F9",
                "dose_status": "existing-population-challenger-law",
                "diagnostic_only": False,
            }
        else:
            row = {
                "ordinal": ordinal,
                "strategy_id": strategy_id,
                "display_name": (
                    "complete no-good distinct next-best archive"
                    if strategy_id == "no-good-distinct-next-best-v1"
                    else "pre-lock descriptor quality-diversity reserve"
                ),
                "strategy_kind": "planned-unmaterialized-generation-treatment",
                "hypothesis": (
                    "spend bounded duplicate-world work on a distinct legal successor"
                    if strategy_id == "no-good-distinct-next-best-v1"
                    else "reserve bounded work for underfilled pre-lock quality niches"
                ),
                "comparison_cohort_id": "unassigned-until-generation-law-freezes",
                "generation_environment_sha256": None,
                "environment_overrides_from_p0": {},
                "nominal_solve_slots_by_family": {},
                "nominal_solve_slot_count": None,
                "actual_attempt_receipt_required": True,
                "artifact_support": "none-do-not-run",
                "dose_status": "planned-only-no-candidate-artifact",
                "diagnostic_only": False,
            }
        rows.append(_with_hash(row, field_name="strategy_sha256"))
    body = {
        "schema": FILL_REGISTRY_SCHEMA,
        "strategy_order": list(FILL_STRATEGY_ORDER),
        "strategies": rows,
        "equal-work-native_nominal_slot_count": 266,
        "nominal_slots_are_not_attempt_receipts": True,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="registry_sha256")


def construction_profile_registry_v1() -> dict[str, object]:
    p0_environment = _p0_environment_v1()
    rows = [{
        "ordinal": 0,
        "profile_id": INCUMBENT_PROFILE_ID,
        "display_name": "P0 incumbent ambient production construction law",
        "profile_kind": "frozen-production-environment-with-upstream-stack-owner",
        "profile_sha256": factorial.P0_GENERATION_ENVIRONMENT_SHA256,
        "rule_payload": p0_environment,
        "rule_payload_sha256": _hash(p0_environment),
        "rule_owner": "ClassicProductionPolicy.engine_environment plus upstream stack object",
        "request_local_profile_claimed": False,
        "full_construction_rules_available_here": False,
    }]
    for profile_id in profiles.PROFILE_ORDER:
        profile = profiles.population_profile_v1(profile_id)
        rows.append({
            "ordinal": profile.ordinal,
            "profile_id": profile_id,
            "display_name": profile.hypothesis,
            "profile_kind": "fresh-request-local-model",
            "profile_sha256": profile.fingerprint,
            "rule_payload": profile.payload(),
            "rule_payload_sha256": profile.fingerprint,
            "rule_owner": "PopulationProfile -> fresh legal model",
            "request_local_profile_claimed": True,
            "full_construction_rules_available_here": True,
        })
    body = {
        "schema": PROFILE_REGISTRY_SCHEMA,
        "profile_order": list(PROFILE_ORDER),
        "profiles": rows,
        "inherited_structure_allowed_for_F7_F9": False,
    }
    return _with_hash(body, field_name="registry_sha256")


def selector_registry_v1() -> dict[str, object]:
    presets = successor.frozen_native_preset_registry_v1()
    rows: list[dict[str, object]] = []
    for preset in presets:
        rows.append({
            "selector_id": f"grouped-rank80:{preset['preset_id']}",
            "selector_family": "grouped-rank80",
            "preset_id": preset["preset_id"],
            "prefix_sizes": list(successor.PREFIX_SIZES),
        })
    for preset in presets:
        rows.append({
            "selector_id": f"rank150:{preset['preset_id']}",
            "selector_family": "rank150-continuation",
            "preset_id": preset["preset_id"],
            "prefix_sizes": list(rank150.ENTRY_BUDGETS),
        })
    rows.append({
        "selector_id": "rank150:effective-independent-shots-v1",
        "selector_family": "effective-independent-shots",
        "preset_id": None,
        "prefix_sizes": list(diversity.PREFIX_SIZES),
    })
    rows = [
        _with_hash({"ordinal": ordinal, **row}, field_name="selector_sha256")
        for ordinal, row in enumerate(rows)
    ]
    body = {
        "schema": SELECTOR_REGISTRY_SCHEMA,
        "selector_count": len(rows),
        "selectors": rows,
        "fit_columns_only": True,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="registry_sha256")


def incumbent_control_registry_v1() -> dict[str, object]:
    strategies = full_union.frozen_full_union_strategies_v1()
    by_id = {str(row["strategy_id"]): dict(row) for row in strategies}
    if not set(INCUMBENT_CONTROL_IDS) <= set(by_id):
        _fail("incumbent control registry is incomplete")
    retained = [by_id[strategy_id] for strategy_id in INCUMBENT_CONTROL_IDS]
    body = {
        "schema": "corpus-r6-fair-fill-incumbent-control-registry/v1",
        "strategy_order": list(INCUMBENT_CONTROL_IDS),
        "strategies": retained,
        "sensitivity_views": ["full-corpus", "deterministic-equal-size"],
        "planned_no_good_or_quality_diversity_included": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="registry_sha256")


def _strategy(strategy_id: str) -> dict[str, object]:
    registry = fill_strategy_registry_v1()
    matches = [row for row in registry["strategies"] if row["strategy_id"] == strategy_id]
    if len(matches) != 1:
        _fail("fill strategy is outside the frozen registry")
    return dict(matches[0])


def _cell_id(fill_strategy_id: str, construction_profile_id: str) -> str:
    return _identifier(
        f"{fill_strategy_id}--{construction_profile_id}", label="candidate cell ID"
    )


def _lineup_id(slate_id: str, roster: Sequence[str]) -> str:
    return _hash({
        "schema": "corpus-r6-arm-independent-lineup/v1",
        "slate_id": slate_id,
        "roster_player_ids": list(roster),
    })


def _validate_work_receipts(
    value: object, *, occurrence_counts: Mapping[str, int]
) -> list[dict[str, object]]:
    rows = [
        _mapping(raw, label="work receipt")
        for raw in _sequence(value, label="work receipts")
    ]
    if len(rows) != len(rw.WORLD_BLOCKS):
        _fail("work receipts must cover R0--R4 exactly")
    normalized: list[dict[str, object]] = []
    for block, row in zip(rw.WORLD_BLOCKS, rows, strict=True):
        if set(row) != _WORK_FIELDS or row.get("schema") != WORK_RECEIPT_SCHEMA:
            _fail("work receipt fields/schema differ")
        if row.get("origin_id") != block:
            _fail("work receipt block order differs")
        scheduled = _strict_int(
            row.get("scheduled_optimizer_attempts"), label="scheduled attempts"
        )
        attempted = _strict_int(
            row.get("attempted_optimizer_calls"), label="attempted calls"
        )
        optimal = _strict_int(row.get("optimal_calls"), label="optimal calls")
        infeasible = _strict_int(
            row.get("infeasible_calls"), label="infeasible calls"
        )
        errors = _strict_int(row.get("error_calls"), label="error calls")
        retained = _strict_int(
            row.get("retained_occurrence_count"), label="retained occurrences"
        )
        if (
            scheduled != attempted
            or attempted != optimal + infeasible + errors
            or retained != occurrence_counts.get(block, 0)
            or retained > optimal
        ):
            _fail("work receipt arithmetic differs")
        normalized.append(dict(row))
    return normalized


def build_candidate_cell_from_occurrences_v1(
    *,
    slate: Mapping[str, object],
    fill_strategy_id: str,
    construction_profile_id: str,
    occurrences: Sequence[Mapping[str, object]],
    work_receipts: Sequence[Mapping[str, object]],
    source_bindings: Mapping[str, object],
    profile_audit_complete: bool,
    source_authoritative: bool,
    test_only: bool = False,
    comparison_cohort_id: str | None = None,
    _source_adapter_id: str | None = None,
) -> dict[str, object]:
    """Build one score-free generation cell from occurrence provenance."""
    strategy = _strategy(fill_strategy_id)
    if construction_profile_id not in PROFILE_ORDER:
        _fail("construction profile is outside the frozen registry")
    if (
        fill_strategy_id in {"game-stack-control-v1", "dark-game-control-v1"}
        and construction_profile_id == "F8-game-cap-3"
    ):
        _fail("five-player game family is mechanically incompatible with F8 cap 3")
    for label, value in (
        ("profile audit complete", profile_audit_complete),
        ("source authoritative", source_authoritative),
        ("test only", test_only),
    ):
        if type(value) is not bool:
            _fail(f"{label} must be a literal boolean")
    if source_authoritative and test_only:
        _fail("test-only cells cannot claim authoritative source evidence")
    if _source_adapter_id is None:
        if source_authoritative or not test_only:
            _fail(
                "generic occurrence cells are test-only and cannot self-assert "
                "source authority"
            )
        source_adapter_id = "unvalidated-test-fixture-v1"
    else:
        source_adapter_id = _identifier(
            _source_adapter_id, label="source adapter ID"
        )
        if source_adapter_id not in {
            "population-profile-lineups-exact-v1",
            "population-profile-lineups-unsealed-test-v1",
            "tagged-family-isolate-v1",
        }:
            _fail("source adapter is outside the exact adapter registry")
    retained_slate = _mapping(slate, label="candidate-cell slate")
    if set(retained_slate) != {"season", "week", "slate_id"}:
        _fail("candidate-cell slate fields differ")
    season = _strict_int(retained_slate["season"], label="season", minimum=2000)
    week = _strict_int(retained_slate["week"], label="week", minimum=1)
    slate_id = _identifier(retained_slate["slate_id"], label="slate ID")
    if retained_slate != {"season": season, "week": week, "slate_id": slate_id}:
        _fail("candidate-cell slate values differ")

    normalized_occurrences: list[dict[str, object]] = []
    prior_key: tuple[int, int] | None = None
    ordinals_by_block: dict[str, set[int]] = {block: set() for block in rw.WORLD_BLOCKS}
    for raw in occurrences:
        occurrence = _mapping(raw, label="candidate occurrence")
        if set(occurrence) not in (
            _OCCURRENCE_FIELDS,
            _OCCURRENCE_FIELDS - {"lineup_id"},
        ):
            _fail("candidate occurrence fields differ")
        block = str(occurrence.get("origin_id"))
        if block not in rw.WORLD_BLOCKS:
            _fail("candidate occurrence origin is outside R0--R4")
        ordinal = _strict_int(
            occurrence.get("candidate_ordinal"), label="candidate ordinal"
        )
        if ordinal in ordinals_by_block[block]:
            _fail("candidate ordinals must be unique within an origin")
        ordinals_by_block[block].add(ordinal)
        order_key = (rw.WORLD_BLOCKS.index(block), ordinal)
        if prior_key is not None and order_key <= prior_key:
            _fail("candidate occurrences must be in canonical origin/ordinal order")
        prior_key = order_key
        roster = [
            _identifier(item, label="roster player ID", maximum=160)
            for item in _sequence(
                occurrence.get("roster_player_ids"), label="roster player IDs"
            )
        ]
        if len(roster) != rw.ROSTER_SIZE or roster != sorted(set(roster)):
            _fail("candidate roster must be nine sorted unique player IDs")
        tags = [
            _identifier(item, label="family tag")
            for item in _sequence(occurrence.get("family_tags"), label="family tags")
        ]
        if tags != sorted(set(tags)):
            _fail("family tags must be sorted and unique")
        lineup_id = _lineup_id(slate_id, roster)
        if "lineup_id" in occurrence and occurrence["lineup_id"] != lineup_id:
            _fail("candidate occurrence lineup identity differs")
        normalized_occurrences.append({
            "origin_id": block,
            "candidate_ordinal": ordinal,
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "family_tags": tags,
        })
    if not normalized_occurrences:
        _fail("candidate cell must contain at least one occurrence")
    occurrence_counts = Counter(
        str(row["origin_id"]) for row in normalized_occurrences
    )
    receipts = _validate_work_receipts(
        work_receipts, occurrence_counts=occurrence_counts
    )
    sources = _mapping(source_bindings, label="source bindings")
    if source_adapter_id == "unvalidated-test-fixture-v1":
        if (
            set(sources) != {"schema", "fixture_id"}
            or sources.get("schema") != "corpus-r6-fair-fill-test-source/v1"
            or type(sources.get("fixture_id")) is not str
        ):
            _fail("test source binding fields differ")
    elif source_adapter_id.startswith("population-profile-lineups-"):
        expected = {
            "adapter_id", "profile_lineups_sha256", "source_authority_sha256",
            "work_sha256", "world_schedule_sha256", "outcome_fields_read",
            "uses_realized_outcomes",
        }
        if source_adapter_id == "population-profile-lineups-exact-v1":
            expected.add("exact_lineage")
        if (
            set(sources) != expected
            or sources.get("outcome_fields_read") != []
            or sources.get("uses_realized_outcomes") is not False
        ):
            _fail("population source binding fields differ")
    elif source_adapter_id == "tagged-family-isolate-v1":
        if set(sources) != {
            "adapter_id", "parent_cell_sha256", "parent_candidate_cell",
            "family_tag", "outcome_fields_read", "uses_realized_outcomes",
        } or sources.get("outcome_fields_read") != [] or sources.get(
            "uses_realized_outcomes"
        ) is not False:
            _fail("tagged-family source binding fields differ")
    cohort = comparison_cohort_id or str(strategy["comparison_cohort_id"])
    _identifier(cohort, label="comparison cohort ID")
    cell_id = _cell_id(fill_strategy_id, construction_profile_id)
    roster_by_id: dict[str, list[str]] = {}
    for occurrence in normalized_occurrences:
        lineup_id = str(occurrence["lineup_id"])
        roster = list(occurrence["roster_player_ids"])
        if lineup_id in roster_by_id and roster_by_id[lineup_id] != roster:
            _fail("one lineup identity maps to multiple rosters")
        roster_by_id[lineup_id] = roster
    work_dose = [
        {
            "origin_id": row["origin_id"],
            "scheduled_optimizer_attempts": row["scheduled_optimizer_attempts"],
            "attempted_optimizer_calls": row["attempted_optimizer_calls"],
        }
        for row in receipts
    ]
    body = {
        "schema": CANDIDATE_CELL_SCHEMA,
        "cell_id": cell_id,
        "slate": retained_slate,
        "fill_strategy_id": fill_strategy_id,
        "fill_strategy_sha256": strategy["strategy_sha256"],
        "construction_profile_id": construction_profile_id,
        "comparison_cohort_id": cohort,
        "origin_order": list(rw.WORLD_BLOCKS),
        "occurrence_count": len(normalized_occurrences),
        "unique_lineup_count": len(roster_by_id),
        "occurrences": normalized_occurrences,
        "occurrences_sha256": _hash(normalized_occurrences),
        "work_receipts": receipts,
        "work_receipts_sha256": _hash(receipts),
        "work_dose_sha256": _hash(work_dose),
        "source_bindings": sources,
        "source_bindings_sha256": _hash(sources),
        "source_adapter_id": source_adapter_id,
        "profile_audit_complete": profile_audit_complete,
        "source_authoritative": source_authoritative,
        "comparison_role": (
            "diagnostic-filter" if strategy["diagnostic_only"] else "generation-treatment"
        ),
        "diagnostic_only": strategy["diagnostic_only"],
        "test_only": test_only,
        "score_fields_present": False,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    return validate_candidate_cell_v1(_with_hash(body, field_name="cell_sha256"))


def validate_candidate_cell_v1(value: object) -> dict[str, object]:
    cell = _mapping(value, label="candidate cell")
    digest = cell.get("cell_sha256")
    if set(cell) != _CELL_FIELDS:
        _fail("candidate cell fields differ")
    if cell.get("schema") != CANDIDATE_CELL_SCHEMA or digest != _hash({
        key: item for key, item in cell.items() if key != "cell_sha256"
    }):
        _fail("candidate cell schema/self-hash differs")
    strategy = _strategy(str(cell.get("fill_strategy_id")))
    occurrences = _sequence(cell.get("occurrences"), label="candidate occurrences")
    receipts = _sequence(cell.get("work_receipts"), label="work receipts")
    sources = _mapping(cell.get("source_bindings"), label="source bindings")
    slate = _mapping(cell.get("slate"), label="candidate-cell slate")
    if (
        cell.get("cell_id")
        != _cell_id(str(cell.get("fill_strategy_id")), str(cell.get("construction_profile_id")))
        or cell.get("construction_profile_id") not in PROFILE_ORDER
        or set(slate) != {"season", "week", "slate_id"}
        or type(slate.get("season")) is not int
        or not 2000 <= slate["season"]
        or type(slate.get("week")) is not int
        or slate["week"] < 1
        or _identifier(slate.get("slate_id"), label="slate ID") != slate["slate_id"]
        or cell.get("fill_strategy_sha256") != strategy["strategy_sha256"]
        or cell.get("origin_order") != list(rw.WORLD_BLOCKS)
        or cell.get("occurrence_count") != len(occurrences)
        or cell.get("unique_lineup_count")
        != len({str(_mapping(row, label="occurrence").get("lineup_id")) for row in occurrences})
        or cell.get("occurrences_sha256") != _hash(occurrences)
        or cell.get("work_receipts_sha256") != _hash(receipts)
        or cell.get("source_bindings_sha256") != _hash(sources)
        or cell.get("source_adapter_id") not in {
            "unvalidated-test-fixture-v1",
            "population-profile-lineups-exact-v1",
            "population-profile-lineups-unsealed-test-v1",
            "tagged-family-isolate-v1",
        }
        or cell.get("comparison_role")
        != ("diagnostic-filter" if strategy["diagnostic_only"] else "generation-treatment")
        or cell.get("diagnostic_only") is not strategy["diagnostic_only"]
        or cell.get("score_fields_present") is not False
        or cell.get("outcome_fields_read") != []
        or cell.get("uses_realized_outcomes") is not False
        or cell.get("promotion_authority") is not False
    ):
        _fail("candidate cell fixed contents differ")
    _identifier(cell.get("comparison_cohort_id"), label="comparison cohort ID")
    if (
        cell.get("fill_strategy_id")
        in {"game-stack-control-v1", "dark-game-control-v1"}
        and cell.get("construction_profile_id") == "F8-game-cap-3"
    ):
        _fail("five-player game family is mechanically incompatible with F8 cap 3")
    # Re-run strict component validation without recursively rebuilding a cell.
    normalized_occurrence_counts = Counter(
        str(_mapping(row, label="occurrence").get("origin_id")) for row in occurrences
    )
    _validate_work_receipts(receipts, occurrence_counts=normalized_occurrence_counts)
    work_dose = [
        {
            "origin_id": row["origin_id"],
            "scheduled_optimizer_attempts": row["scheduled_optimizer_attempts"],
            "attempted_optimizer_calls": row["attempted_optimizer_calls"],
        }
        for row in receipts
    ]
    if cell.get("work_dose_sha256") != _hash(work_dose):
        _fail("candidate cell work dose differs")
    # Rebuild each lineup identity and canonical occurrence order.
    slate_id = str(_mapping(cell["slate"], label="slate")["slate_id"])
    prior: tuple[int, int] | None = None
    seen_ordinals: set[tuple[str, int]] = set()
    for raw in occurrences:
        row = _mapping(raw, label="candidate occurrence")
        if set(row) != _OCCURRENCE_FIELDS:
            _fail("candidate occurrence fields differ")
        block = str(row["origin_id"])
        ordinal = row["candidate_ordinal"]
        roster = row["roster_player_ids"]
        tags = row["family_tags"]
        if (
            block not in rw.WORLD_BLOCKS
            or type(ordinal) is not int
            or ordinal < 0
            or (block, ordinal) in seen_ordinals
            or not isinstance(roster, list)
            or len(roster) != rw.ROSTER_SIZE
            or roster != sorted(set(roster))
            or row["lineup_id"] != _lineup_id(slate_id, roster)
            or not isinstance(tags, list)
            or tags != sorted(set(tags))
        ):
            _fail("candidate occurrence contents differ")
        for player_id in roster:
            _identifier(player_id, label="roster player ID", maximum=160)
        for tag in tags:
            _identifier(tag, label="family tag")
        key = (rw.WORLD_BLOCKS.index(block), ordinal)
        if prior is not None and key <= prior:
            _fail("candidate occurrence order differs")
        prior = key
        seen_ordinals.add((block, ordinal))
    if (
        type(cell.get("profile_audit_complete")) is not bool
        or type(cell.get("source_authoritative")) is not bool
        or type(cell.get("test_only")) is not bool
        or (cell.get("source_authoritative") and cell.get("test_only"))
    ):
        _fail("candidate cell authority flags differ")
    if (
        cell["source_authoritative"]
        and cell["source_adapter_id"] == "population-profile-lineups-exact-v1"
    ):
        lineage = _mapping(sources.get("exact_lineage"), label="exact lineage")
        expected_lineage_fields = {
            "task_request",
            "profile_lineups_identity",
            "profile_lineups",
            "player_catalog",
            "player_catalog_sha256",
        }
        if set(lineage) != expected_lineage_fields:
            _fail("exact population lineage fields differ")
        try:
            request = population_cloud.validate_task_request_v1(
                lineage["task_request"]
            )
            identity = population_authority.object_identity_v1(
                lineage["profile_lineups_identity"], label="profile lineups"
            )
            bound = population_authority.bind_body_to_identity_v1(
                lineage["profile_lineups"], identity, label="profile lineups"
            )
            player_rows = _sequence(
                lineage["player_catalog"], label="player catalog"
            )
            players = tuple(rw.PlayerSpec.from_mapping(
                _mapping(row, label="player catalog row")
            ) for row in player_rows)
            retained_lineups = population_runtime.validate_profile_lineups_v1(
                lineage["profile_lineups"], players=players
            )
        except Exception as exc:
            raise CorpusR6FairFillRetestV1Error(
                f"exact population lineage replay failed: {exc}"
            ) from exc
        if (
            bound != identity
            or request["profile_lineup_identities"].get(
                cell["construction_profile_id"]
            ) != identity
            or request["profile_order"] != list(profiles.PROFILE_ORDER)
            or request["code_commit"] is None
            or request["image_digest"] is None
            or retained_lineups["lineups_sha256"]
            != sources.get("profile_lineups_sha256")
            or retained_lineups["source_authority_sha256"]
            != sources.get("source_authority_sha256")
            or retained_lineups["authoritative_solver_proofs_complete"] is not True
            or lineage["player_catalog_sha256"] != _hash(player_rows)
        ):
            _fail("exact population lineage binding differs")
    elif (
        cell["source_authoritative"]
        and cell["source_adapter_id"] == "tagged-family-isolate-v1"
    ):
        parent = validate_candidate_cell_v1(
            sources.get("parent_candidate_cell")
        )
        expected_tag = FAMILY_CONTROL_TAG_BY_STRATEGY.get(
            str(cell["fill_strategy_id"])
        )
        expected_occurrences = [
            row for row in parent["occurrences"]
            if expected_tag in row["family_tags"]
        ]
        if (
            not parent["source_authoritative"]
            or sources.get("parent_cell_sha256") != parent["cell_sha256"]
            or sources.get("family_tag") != expected_tag
            or cell["occurrences"] != expected_occurrences
            or cell["construction_profile_id"]
            != parent["construction_profile_id"]
        ):
            _fail("tagged-family exact parent replay differs")
    elif cell["source_authoritative"]:
        _fail("authoritative cell source adapter differs")
    elif not cell["test_only"]:
        _fail("non-test candidate cells require source-specific exact authority")
    return cell


def candidate_cell_from_population_profile_lineups_v1(
    value: object,
    *,
    players: Sequence[rw.PlayerSpec],
    profile_lineups_identity: object | None = None,
    task_request: object | None = None,
) -> dict[str, object]:
    """Adapt an existing F7/F8/F9 exact-world artifact without reading scores."""
    try:
        lineups = population_runtime.validate_profile_lineups_v1(value, players=players)
    except Exception as exc:
        raise CorpusR6FairFillRetestV1Error(
            f"population profile lineups are invalid: {exc}"
        ) from exc
    profile_id = str(_mapping(lineups["profile"], label="profile")["profile_id"])
    occurrences: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    optimal: Counter[str] = Counter()
    for raw in _sequence(lineups["visit_results"], label="visit results"):
        visit = _mapping(raw, label="visit result")
        world = _mapping(visit["world"], label="visit world")
        lineup = _mapping(visit["lineup_identity"], label="lineup identity")
        block = str(world["block"])
        ordinal = int(world["index"])
        roster = sorted(str(item) for item in lineup["roster"])
        occurrences.append({
            "origin_id": block,
            "candidate_ordinal": ordinal,
            "roster_player_ids": roster,
            "family_tags": ["world-optimum"],
        })
        counts[block] += 1
        optimal[block] += 1
    occurrences.sort(
        key=lambda row: (rw.WORLD_BLOCKS.index(str(row["origin_id"])), int(row["candidate_ordinal"]))
    )
    work = _mapping(lineups["work"], label="shared work")
    attempts = int(work["solve_attempts_per_block"])
    receipts = [
        {
            "schema": WORK_RECEIPT_SCHEMA,
            "origin_id": block,
            "scheduled_optimizer_attempts": attempts,
            "attempted_optimizer_calls": attempts,
            "optimal_calls": optimal[block],
            "infeasible_calls": attempts - optimal[block],
            "error_calls": 0,
            "retained_occurrence_count": counts[block],
        }
        for block in rw.WORLD_BLOCKS
    ]
    authoritative = (
        profile_lineups_identity is not None
        and task_request is not None
        and bool(lineups.get("authoritative_solver_proofs_complete"))
        and not bool(lineups.get("test_only"))
    )
    source: dict[str, object] = {
        "adapter_id": "population-profile-lineups-v1",
        "profile_lineups_sha256": lineups["lineups_sha256"],
        "source_authority_sha256": lineups["source_authority_sha256"],
        "work_sha256": lineups["work_sha256"],
        "world_schedule_sha256": lineups["world_schedule_sha256"],
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
    }
    if authoritative:
        try:
            request = population_cloud.validate_task_request_v1(task_request)
            identity = population_authority.object_identity_v1(
                profile_lineups_identity, label="profile lineups"
            )
            population_authority.bind_body_to_identity_v1(
                lineups, identity, label="profile lineups"
            )
        except Exception as exc:
            raise CorpusR6FairFillRetestV1Error(
                f"population exact source binding failed: {exc}"
            ) from exc
        player_catalog = [
            {
                "id": player.player_id,
                "pos": player.position,
                "team": player.team,
                "opp": player.opponent,
                "game_id": player.game_id,
                "salary": player.salary,
            }
            for player in players
        ]
        source["exact_lineage"] = {
            "task_request": request,
            "profile_lineups_identity": identity,
            "profile_lineups": lineups,
            "player_catalog": player_catalog,
            "player_catalog_sha256": _hash(player_catalog),
        }
    return build_candidate_cell_from_occurrences_v1(
        slate=_mapping(lineups["slate"], label="slate"),
        fill_strategy_id="per-world-exact-v1",
        construction_profile_id=profile_id,
        occurrences=occurrences,
        work_receipts=receipts,
        source_bindings=source,
        profile_audit_complete=True,
        source_authoritative=authoritative,
        test_only=not authoritative,
        comparison_cohort_id=PER_WORLD_EXACT_COHORT,
        _source_adapter_id=(
            "population-profile-lineups-exact-v1"
            if authoritative
            else "population-profile-lineups-unsealed-test-v1"
        ),
    )


def build_tagged_family_control_cell_v1(
    parent_cell: object, *, control_strategy_id: str
) -> dict[str, object]:
    """Create a clearly diagnostic family isolate from tagged candidates."""
    parent = validate_candidate_cell_v1(parent_cell)
    if control_strategy_id not in FAMILY_CONTROL_TAG_BY_STRATEGY:
        _fail("requested control is not a registered tagged-family isolate")
    tag = FAMILY_CONTROL_TAG_BY_STRATEGY[control_strategy_id]
    retained = [
        dict(row) for row in parent["occurrences"] if tag in row["family_tags"]
    ]
    if not retained:
        _fail(f"parent cell contains no {tag}-tagged occurrences")
    counts = Counter(str(row["origin_id"]) for row in retained)
    receipts = []
    for raw in parent["work_receipts"]:
        row = dict(raw)
        row["retained_occurrence_count"] = counts[str(row["origin_id"])]
        receipts.append(row)
    return build_candidate_cell_from_occurrences_v1(
        slate=parent["slate"],
        fill_strategy_id=control_strategy_id,
        construction_profile_id=str(parent["construction_profile_id"]),
        occurrences=retained,
        work_receipts=receipts,
        source_bindings={
            "adapter_id": "tagged-family-isolate-v1",
            "parent_cell_sha256": parent["cell_sha256"],
            "parent_candidate_cell": parent,
            "family_tag": tag,
            "outcome_fields_read": [],
            "uses_realized_outcomes": False,
        },
        profile_audit_complete=bool(parent["profile_audit_complete"]),
        source_authoritative=bool(parent["source_authoritative"]),
        test_only=bool(parent["test_only"]),
        comparison_cohort_id=f"diagnostic-{tag}-family-v1",
        _source_adapter_id="tagged-family-isolate-v1",
    )


def _candidate_rows_for_fit(
    cell: Mapping[str, object], *, heldout_block: str
) -> list[dict[str, object]]:
    training_blocks = tuple(block for block in rw.WORLD_BLOCKS if block != heldout_block)
    cell_id = str(cell["cell_id"])
    roster_by_id: dict[str, list[str]] = {}
    counts_by_id: dict[str, Counter[str]] = {}
    for occurrence in cell["occurrences"]:
        block = str(occurrence["origin_id"])
        lineup_id = str(occurrence["lineup_id"])
        roster = list(occurrence["roster_player_ids"])
        roster_by_id.setdefault(lineup_id, roster)
        if block != heldout_block:
            counts_by_id.setdefault(lineup_id, Counter())[block] += 1
    rows: list[dict[str, object]] = []
    for lineup_id in sorted(counts_by_id):
        counts = counts_by_id[lineup_id]
        by_block = {block: int(counts[block]) for block in training_blocks}
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster_by_id[lineup_id],
            "training_origin_blocks": [
                block for block in training_blocks if by_block[block] > 0
            ],
            "training_source_arms": [cell_id],
            "training_occurrence_counts_by_block": by_block,
            "training_source_arms_by_block": {
                block: ([cell_id] if by_block[block] else [])
                for block in training_blocks
            },
            "training_occurrence_count": sum(by_block.values()),
        })
    try:
        successor._validated_candidates(
            rows,
            sampled_lineup_ids=[str(row["lineup_id"]) for row in rows],
            training_blocks=training_blocks,
            source_arm_registry=[cell_id],
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6FairFillRetestV1Error(str(exc)) from exc
    return rows


def _sample_ids(
    eligible_ids: Sequence[str], *, target: int, seed_material: Mapping[str, object]
) -> list[str]:
    ids = [str(item) for item in eligible_ids]
    if ids != sorted(set(ids)) or len(ids) < target:
        _fail("equal-count sample inputs differ")
    if len(ids) == target:
        return ids
    seed = profiles.canonical_json_bytes_v1(seed_material)
    ranked = sorted(
        ids,
        key=lambda lineup_id: (
            sha256(seed + b"\0" + lineup_id.encode()).digest(), lineup_id
        ),
    )
    return sorted(ranked[:target])


def build_fair_fill_fold_plan_v1(
    *,
    candidate_cells: Sequence[Mapping[str, object]],
    heldout_block: str,
    allow_non_authoritative: bool = False,
    allow_diagnostic: bool = False,
) -> dict[str, object]:
    """Freeze one fair equal-count fold across supplied comparable cells."""
    if heldout_block not in rw.WORLD_BLOCKS:
        _fail("heldout block must be one canonical R block")
    if type(allow_non_authoritative) is not bool or type(allow_diagnostic) is not bool:
        _fail("fold authority switches must be literal booleans")
    cells = [validate_candidate_cell_v1(cell) for cell in candidate_cells]
    if not cells:
        _fail("a fair fold needs at least one candidate cell")
    ids = [str(cell["cell_id"]) for cell in cells]
    if ids != sorted(set(ids)):
        _fail("candidate cells must be sorted by unique cell ID")
    slates = {_hash(cell["slate"]) for cell in cells}
    cohorts = {str(cell["comparison_cohort_id"]) for cell in cells}
    diagnostics = {bool(cell["diagnostic_only"]) for cell in cells}
    if len(slates) != 1 or len(cohorts) != 1 or len(diagnostics) != 1:
        _fail("fair fold cells must share slate, cohort, and comparison role")
    if True in diagnostics and not allow_diagnostic:
        _fail("diagnostic family isolates require explicit diagnostic mode")
    if not allow_non_authoritative and any(
        not cell["source_authoritative"] or cell["test_only"] for cell in cells
    ):
        _fail("non-authoritative/test-only cells require an explicit test seam")
    if any(not cell["profile_audit_complete"] for cell in cells):
        _fail("every crossed cell requires a complete construction-profile audit")
    for cell in cells:
        state, reason = _support_state(
            str(cell["fill_strategy_id"]),
            str(cell["construction_profile_id"]),
        )
        if state != "adapter-available":
            _fail(f"candidate cell is not artifact-supported: {reason}")
    if False in diagnostics and len({cell["work_dose_sha256"] for cell in cells}) != 1:
        _fail("causal crossed cells do not share one attempted-work dose")

    eligible_by_cell = {
        str(cell["cell_id"]): _candidate_rows_for_fit(cell, heldout_block=heldout_block)
        for cell in cells
    }
    common_count = min(
        MAXIMUM_COMMON_COUNT,
        *(len(rows) for rows in eligible_by_cell.values()),
    )
    if common_count < MINIMUM_COMMON_COUNT:
        _fail("at least one fair-fold cell has fewer than 150 fit-eligible lineups")
    seed_material = {
        "schema": FOLD_PLAN_SCHEMA,
        "purpose": "outcome-blind-equal-count-fill-profile-sample",
        "slate": cells[0]["slate"],
        "comparison_cohort_id": cells[0]["comparison_cohort_id"],
        "heldout_block": heldout_block,
    }
    cell_plans: list[dict[str, object]] = []
    for cell in cells:
        cell_id = str(cell["cell_id"])
        eligible = eligible_by_cell[cell_id]
        eligible_ids = [str(row["lineup_id"]) for row in eligible]
        sampled_ids = _sample_ids(
            eligible_ids, target=common_count, seed_material=seed_material
        )
        by_id = {str(row["lineup_id"]): row for row in eligible}
        sampled = [by_id[lineup_id] for lineup_id in sampled_ids]
        cell_plans.append(_with_hash({
            "schema": CELL_PLAN_SCHEMA,
            "cell_id": cell_id,
            "cell_sha256": cell["cell_sha256"],
            "fill_strategy_id": cell["fill_strategy_id"],
            "construction_profile_id": cell["construction_profile_id"],
            "eligible_lineup_count": len(eligible),
            "eligible_candidate_rows": eligible,
            "eligible_candidate_rows_sha256": _hash(eligible),
            "sampled_lineup_count": common_count,
            "sampled_lineup_ids": sampled_ids,
            "sampled_candidate_rows": sampled,
            "sampled_candidate_rows_sha256": _hash(sampled),
            "heldout_occurrences_excluded": True,
            "uses_realized_outcomes": False,
        }, field_name="cell_plan_sha256"))
    body = {
        "schema": FOLD_PLAN_SCHEMA,
        "slate": cells[0]["slate"],
        "comparison_cohort_id": cells[0]["comparison_cohort_id"],
        "heldout_block": heldout_block,
        "training_blocks": [block for block in rw.WORLD_BLOCKS if block != heldout_block],
        "cell_order": ids,
        "source_candidate_cells": cells,
        "source_candidate_cell_sha256s": [cell["cell_sha256"] for cell in cells],
        "common_count": common_count,
        "common_count_law": "min-250-and-smallest-cell-fit-eligible-count",
        "minimum_common_count": MINIMUM_COMMON_COUNT,
        "maximum_common_count": MAXIMUM_COMMON_COUNT,
        "sample_seed_material": seed_material,
        "sample_seed_material_sha256": _hash(seed_material),
        "work_dose_sha256": cells[0]["work_dose_sha256"] if False in diagnostics else None,
        "diagnostic_only": True in diagnostics,
        "cell_plans": cell_plans,
        "cell_plan_sha256s": [row["cell_plan_sha256"] for row in cell_plans],
        "score_values_read_for_sampling": False,
        "heldout_score_values_read_for_sampling": False,
        "realized_outcomes_read": False,
        "test_only": any(bool(cell["test_only"]) for cell in cells),
    }
    return validate_fair_fill_fold_plan_v1(
        _with_hash(body, field_name="plan_sha256")
    )


def validate_fair_fill_fold_plan_v1(value: object) -> dict[str, object]:
    plan = _mapping(value, label="fair fill fold plan")
    if set(plan) != _FOLD_PLAN_FIELDS:
        _fail("fair fill fold plan fields differ")
    if plan.get("schema") != FOLD_PLAN_SCHEMA or plan.get("plan_sha256") != _hash({
        key: item for key, item in plan.items() if key != "plan_sha256"
    }):
        _fail("fair fill fold plan schema/self-hash differs")
    heldout = plan.get("heldout_block")
    training = [block for block in rw.WORLD_BLOCKS if block != heldout]
    cells = [
        _mapping(row, label="cell plan")
        for row in _sequence(plan.get("cell_plans"), label="cell plans")
    ]
    source_cells = [
        validate_candidate_cell_v1(row)
        for row in _sequence(
            plan.get("source_candidate_cells"), label="source candidate cells"
        )
    ]
    if (
        heldout not in rw.WORLD_BLOCKS
        or plan.get("training_blocks") != training
        or plan.get("minimum_common_count") != MINIMUM_COMMON_COUNT
        or plan.get("maximum_common_count") != MAXIMUM_COMMON_COUNT
        or plan.get("cell_order") != [row.get("cell_id") for row in cells]
        or plan.get("cell_order") != [row.get("cell_id") for row in source_cells]
        or plan.get("source_candidate_cell_sha256s")
        != [row.get("cell_sha256") for row in source_cells]
        or plan.get("cell_order") != sorted(set(plan.get("cell_order", [])))
        or plan.get("cell_plan_sha256s") != [row.get("cell_plan_sha256") for row in cells]
        or plan.get("sample_seed_material_sha256") != _hash(plan.get("sample_seed_material"))
        or plan.get("score_values_read_for_sampling") is not False
        or plan.get("heldout_score_values_read_for_sampling") is not False
        or plan.get("realized_outcomes_read") is not False
    ):
        _fail("fair fill fold plan fixed contents differ")
    counts: list[int] = []
    common_count = _strict_int(plan.get("common_count"), label="common count")
    for row, source_cell in zip(cells, source_cells, strict=True):
        if set(row) != _CELL_PLAN_FIELDS:
            _fail("cell plan fields differ")
        if row.get("schema") != CELL_PLAN_SCHEMA or row.get("cell_plan_sha256") != _hash({
            key: item for key, item in row.items() if key != "cell_plan_sha256"
        }):
            _fail("cell plan schema/self-hash differs")
        eligible = _sequence(row.get("eligible_candidate_rows"), label="eligible rows")
        replayed_eligible = _candidate_rows_for_fit(
            source_cell, heldout_block=str(heldout)
        )
        sampled_ids = _sequence(row.get("sampled_lineup_ids"), label="sampled IDs")
        sampled = _sequence(row.get("sampled_candidate_rows"), label="sampled rows")
        eligible_ids = [str(_mapping(item, label="eligible row")["lineup_id"]) for item in eligible]
        expected_ids = _sample_ids(
            eligible_ids,
            target=common_count,
            seed_material=_mapping(plan["sample_seed_material"], label="sample seed"),
        )
        by_id = {str(item["lineup_id"]): item for item in eligible}
        if (
            row.get("eligible_lineup_count") != len(eligible)
            or eligible != replayed_eligible
            or row.get("cell_sha256") != source_cell["cell_sha256"]
            or eligible_ids != sorted(set(eligible_ids))
            or row.get("eligible_candidate_rows_sha256") != _hash(eligible)
            or row.get("sampled_lineup_count") != common_count
            or sampled_ids != expected_ids
            or sampled != [by_id[lineup_id] for lineup_id in sampled_ids]
            or row.get("sampled_candidate_rows_sha256") != _hash(sampled)
            or row.get("heldout_occurrences_excluded") is not True
            or row.get("uses_realized_outcomes") is not False
        ):
            _fail("cell plan contents differ")
        try:
            successor._validated_candidates(
                sampled,
                sampled_lineup_ids=sampled_ids,
                training_blocks=training,
                source_arm_registry=[str(row["cell_id"])],
            )
        except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
            raise CorpusR6FairFillRetestV1Error(str(exc)) from exc
        counts.append(len(eligible))
    if not counts or common_count != min(MAXIMUM_COMMON_COUNT, *counts):
        _fail("fair fold common-count law differs")
    return plan


@dataclass(frozen=True, slots=True)
class FairFillSelectionInputsV1:
    cell_id: str
    heldout_block_label_only: str
    training_blocks: tuple[str, ...]
    worlds_per_block: int
    sampled_lineup_ids: tuple[str, ...]
    candidate_rows: tuple[Mapping[str, object], ...]
    training_score_matrix: np.ndarray = field(compare=False, repr=False)
    binding: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class FairFillEvaluationInputsV1:
    cell_id: str
    heldout_block: str
    worlds_per_block: int
    sampled_lineup_ids: tuple[str, ...]
    roster_player_ids: tuple[tuple[str, ...], ...]
    heldout_score_matrix: np.ndarray = field(compare=False, repr=False)
    binding: Mapping[str, object]


def bind_fair_fill_selection_inputs_v1(
    *,
    plan_sha256: str,
    cell_id: str,
    heldout_block: str,
    training_blocks: Sequence[str],
    worlds_per_block: int,
    sampled_lineup_ids: Sequence[str],
    candidate_rows: Sequence[Mapping[str, object]],
    training_score_matrix: np.ndarray,
) -> FairFillSelectionInputsV1:
    ids = tuple(str(item) for item in sampled_lineup_ids)
    candidates = tuple(dict(row) for row in candidate_rows)
    blocks = tuple(str(item) for item in training_blocks)
    matrix = np.asarray(training_score_matrix)
    if matrix.dtype != np.dtype(np.float64) or not matrix.flags.c_contiguous:
        _fail("training score matrix must be C-contiguous float64")
    matrix.flags.writeable = False
    binding = _with_hash({
        "schema": SELECTION_BINDING_SCHEMA,
        "plan_sha256": plan_sha256,
        "cell_id": cell_id,
        "source_arm_registry": [cell_id],
        "heldout_block_label_only": heldout_block,
        "training_blocks": list(blocks),
        "worlds_per_block": worlds_per_block,
        "sampled_lineup_ids_sha256": _hash(list(ids)),
        "candidate_rows_sha256": _hash(list(candidates)),
        "training_score_shape": list(matrix.shape),
        "training_score_matrix_sha256": _matrix_hash(matrix, label="training matrix"),
        "heldout_score_columns_present": False,
        "realized_outcomes_read": False,
    }, field_name="selection_binding_sha256")
    result = FairFillSelectionInputsV1(
        cell_id=cell_id,
        heldout_block_label_only=heldout_block,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        sampled_lineup_ids=ids,
        candidate_rows=candidates,
        training_score_matrix=matrix,
        binding=binding,
    )
    return validate_fair_fill_selection_inputs_v1(result)


def validate_fair_fill_selection_inputs_v1(
    value: object,
) -> FairFillSelectionInputsV1:
    if not isinstance(value, FairFillSelectionInputsV1):
        _fail("fair fill selection input type differs")
    expected = _with_hash({
        "schema": SELECTION_BINDING_SCHEMA,
        "plan_sha256": value.binding.get("plan_sha256"),
        "cell_id": value.cell_id,
        "source_arm_registry": [value.cell_id],
        "heldout_block_label_only": value.heldout_block_label_only,
        "training_blocks": list(value.training_blocks),
        "worlds_per_block": value.worlds_per_block,
        "sampled_lineup_ids_sha256": _hash(list(value.sampled_lineup_ids)),
        "candidate_rows_sha256": _hash(list(value.candidate_rows)),
        "training_score_shape": list(value.training_score_matrix.shape),
        "training_score_matrix_sha256": _matrix_hash(
            value.training_score_matrix, label="training matrix"
        ),
        "heldout_score_columns_present": False,
        "realized_outcomes_read": False,
    }, field_name="selection_binding_sha256")
    if value.binding != expected or value.training_score_matrix.flags.writeable:
        _fail("fair fill selection binding differs")
    try:
        successor._validated_inputs(
            sampled_lineup_ids=value.sampled_lineup_ids,
            training_score_matrix=value.training_score_matrix,
            candidate_rows=value.candidate_rows,
            training_blocks=value.training_blocks,
            worlds_per_block=value.worlds_per_block,
            source_arm_registry=[value.cell_id],
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6FairFillRetestV1Error(str(exc)) from exc
    return value


def bind_fair_fill_evaluation_inputs_v1(
    *,
    plan_sha256: str,
    cell_id: str,
    heldout_block: str,
    worlds_per_block: int,
    sampled_lineup_ids: Sequence[str],
    rosters: Sequence[Sequence[str]],
    heldout_score_matrix: np.ndarray,
) -> FairFillEvaluationInputsV1:
    ids = tuple(str(item) for item in sampled_lineup_ids)
    retained_rosters = tuple(tuple(str(item) for item in row) for row in rosters)
    scores = np.asarray(heldout_score_matrix)
    if scores.dtype != np.dtype(np.float64) or not scores.flags.c_contiguous:
        _fail("heldout score matrix must be C-contiguous float64")
    scores.flags.writeable = False
    binding = _with_hash({
        "schema": EVALUATION_BINDING_SCHEMA,
        "plan_sha256": plan_sha256,
        "cell_id": cell_id,
        "heldout_block": heldout_block,
        "worlds_per_block": worlds_per_block,
        "sampled_lineup_ids_sha256": _hash(list(ids)),
        "roster_player_ids_sha256": _hash([list(row) for row in retained_rosters]),
        "heldout_score_shape": list(scores.shape),
        "heldout_score_matrix_sha256": _matrix_hash(scores, label="heldout matrix"),
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }, field_name="evaluation_binding_sha256")
    result = FairFillEvaluationInputsV1(
        cell_id=cell_id,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        sampled_lineup_ids=ids,
        roster_player_ids=retained_rosters,
        heldout_score_matrix=scores,
        binding=binding,
    )
    if (
        heldout_block not in rw.WORLD_BLOCKS
        or scores.shape != (len(ids), worlds_per_block)
        or len(retained_rosters) != len(ids)
        or scores.flags.writeable
        or not np.isfinite(scores).all()
    ):
        _fail("fair fill evaluation inputs differ")
    return validate_fair_fill_evaluation_inputs_v1(result)


def validate_fair_fill_evaluation_inputs_v1(
    value: object,
) -> FairFillEvaluationInputsV1:
    if not isinstance(value, FairFillEvaluationInputsV1):
        _fail("fair fill evaluation input type differs")
    expected = _with_hash({
        "schema": EVALUATION_BINDING_SCHEMA,
        "plan_sha256": value.binding.get("plan_sha256"),
        "cell_id": value.cell_id,
        "heldout_block": value.heldout_block,
        "worlds_per_block": value.worlds_per_block,
        "sampled_lineup_ids_sha256": _hash(list(value.sampled_lineup_ids)),
        "roster_player_ids_sha256": _hash([
            list(row) for row in value.roster_player_ids
        ]),
        "heldout_score_shape": list(value.heldout_score_matrix.shape),
        "heldout_score_matrix_sha256": _matrix_hash(
            value.heldout_score_matrix, label="heldout matrix"
        ),
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }, field_name="evaluation_binding_sha256")
    if (
        value.heldout_block not in rw.WORLD_BLOCKS
        or type(value.worlds_per_block) is not int
        or value.worlds_per_block < 1
        or value.sampled_lineup_ids
        != tuple(sorted(set(value.sampled_lineup_ids)))
        or len(value.roster_player_ids) != len(value.sampled_lineup_ids)
        or value.heldout_score_matrix.shape
        != (len(value.sampled_lineup_ids), value.worlds_per_block)
        or value.heldout_score_matrix.dtype != np.dtype(np.float64)
        or not value.heldout_score_matrix.flags.c_contiguous
        or value.heldout_score_matrix.flags.writeable
        or not np.isfinite(value.heldout_score_matrix).all()
        or value.binding != expected
    ):
        _fail("fair fill evaluation binding differs")
    return value


def run_fair_fill_selectors_v1(value: object) -> dict[str, object]:
    selection = validate_fair_fill_selection_inputs_v1(value)
    kwargs = {
        "sampled_lineup_ids": selection.sampled_lineup_ids,
        "training_score_matrix": selection.training_score_matrix,
        "candidate_rows": selection.candidate_rows,
        "training_blocks": selection.training_blocks,
        "worlds_per_block": selection.worlds_per_block,
        "source_arm_registry": [selection.cell_id],
    }
    presets = successor.frozen_native_preset_registry_v1()
    grouped = successor.run_grouped_native_selectors_v1(
        **kwargs, preset_registry=presets
    )
    ranked = rank150.run_exact_rank150_continuation_v1(
        **kwargs, preset_registry=presets
    )
    dpp = diversity.run_effective_independent_shots_selector_v1(**kwargs)
    body = {
        "schema": SELECTOR_RESULT_SCHEMA,
        "cell_id": selection.cell_id,
        "heldout_block_label_only": selection.heldout_block_label_only,
        "selection_binding": dict(selection.binding),
        "selector_registry_sha256": selector_registry_v1()["registry_sha256"],
        "grouped_result": grouped,
        "rank150_result": ranked,
        "dpp_result": dpp,
        "selector_count": 7,
        "heldout_score_columns_present": False,
        "heldout_matrix_or_digest_read": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="selector_result_sha256")


def run_incumbent_control_sensitivity_v1(
    *,
    cell_id: str,
    full_candidate_rows: Sequence[Mapping[str, object]],
    full_training_score_matrix: np.ndarray,
    equal_size_lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    worlds_per_block: int,
) -> dict[str, object]:
    """Run four frozen incumbent controls on full and equal-size views."""
    full_rows = [dict(row) for row in full_candidate_rows]
    full_ids = [str(row.get("lineup_id")) for row in full_rows]
    equal_ids = [str(value) for value in equal_size_lineup_ids]
    blocks = tuple(str(value) for value in training_blocks)
    scores = np.asarray(full_training_score_matrix)
    if (
        len(full_ids) < successor.ENTRY_BUDGET
        or full_ids != sorted(set(full_ids))
        or equal_ids != sorted(set(equal_ids))
        or not set(equal_ids) <= set(full_ids)
        or len(equal_ids) < successor.ENTRY_BUDGET
        or scores.dtype != np.dtype(np.float64)
        or scores.shape != (len(full_ids), len(blocks) * worlds_per_block)
        or not scores.flags.c_contiguous
        or not np.isfinite(scores).all()
    ):
        _fail("incumbent control sensitivity inputs differ")
    try:
        successor._validated_candidates(
            full_rows,
            sampled_lineup_ids=full_ids,
            training_blocks=blocks,
            source_arm_registry=[cell_id],
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6FairFillRetestV1Error(str(exc)) from exc
    registry = incumbent_control_registry_v1()
    full_ordinal = {lineup_id: index for index, lineup_id in enumerate(full_ids)}
    views = [
        ("full-corpus", full_ids, scores),
        (
            "deterministic-equal-size",
            equal_ids,
            np.ascontiguousarray(
                scores[[full_ordinal[lineup_id] for lineup_id in equal_ids]],
                dtype=np.float64,
            ),
        ),
    ]
    results: list[dict[str, object]] = []
    for view_id, lineup_ids, matrix in views:
        for strategy in registry["strategies"]:
            selected, trace = retrieval_runner._run_strategy_v2(
                strategy, training_scores=matrix, lineup_ids=lineup_ids
            )
            replay, replay_trace = retrieval_runner._run_strategy_v2(
                strategy, training_scores=matrix, lineup_ids=lineup_ids
            )
            if selected != replay or trace != replay_trace:
                _fail("incumbent control deterministic replay differs")
            selected_ids = [lineup_ids[int(index)] for index in selected]
            if (
                len(selected_ids) != successor.ENTRY_BUDGET
                or len(set(selected_ids)) != successor.ENTRY_BUDGET
            ):
                _fail("incumbent control did not return exact-80")
            results.append(_with_hash({
                "view_id": view_id,
                "candidate_count": len(lineup_ids),
                "candidate_lineup_ids_sha256": _hash(lineup_ids),
                "strategy_id": strategy["strategy_id"],
                "strategy_sha256": strategy["strategy_sha256"],
                "selected_lineup_ids": selected_ids,
                "selected_lineup_ids_sha256": _hash(selected_ids),
                "selection_trace": trace,
                "selection_trace_sha256": _hash(trace),
            }, field_name="control_result_sha256"))
    body = {
        "schema": CONTROL_SENSITIVITY_SCHEMA,
        "cell_id": cell_id,
        "training_blocks": list(blocks),
        "worlds_per_block": worlds_per_block,
        "full_candidate_count": len(full_ids),
        "equal_size_candidate_count": len(equal_ids),
        "full_candidate_lineup_ids_sha256": _hash(full_ids),
        "equal_size_lineup_ids_sha256": _hash(equal_ids),
        "full_training_score_matrix_sha256": _matrix_hash(
            scores, label="full training score matrix"
        ),
        "control_registry_sha256": registry["registry_sha256"],
        "result_count": len(results),
        "results": results,
        "heldout_score_columns_present": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="sensitivity_result_sha256")


def evaluate_incumbent_control_sensitivity_v1(
    *,
    sensitivity_result: object,
    full_lineup_ids: Sequence[str],
    full_heldout_score_matrix: np.ndarray,
) -> dict[str, object]:
    result = _mapping(sensitivity_result, label="control sensitivity result")
    if (
        result.get("schema") != CONTROL_SENSITIVITY_SCHEMA
        or result.get("sensitivity_result_sha256") != _hash({
            key: value for key, value in result.items()
            if key != "sensitivity_result_sha256"
        })
        or result.get("heldout_score_columns_present") is not False
        or result.get("realized_outcomes_read") is not False
    ):
        _fail("control sensitivity result authority differs")
    lineup_ids = [str(value) for value in full_lineup_ids]
    scores = np.asarray(full_heldout_score_matrix)
    worlds_per_block = int(result["worlds_per_block"])
    if (
        lineup_ids != sorted(set(lineup_ids))
        or _hash(lineup_ids) != result["full_candidate_lineup_ids_sha256"]
        or scores.dtype != np.dtype(np.float64)
        or scores.shape != (len(lineup_ids), worlds_per_block)
        or not scores.flags.c_contiguous
        or not np.isfinite(scores).all()
    ):
        _fail("control heldout evaluation inputs differ")
    ordinal = {lineup_id: index for index, lineup_id in enumerate(lineup_ids)}
    metrics: list[dict[str, object]] = []
    for row in result["results"]:
        selected = [str(value) for value in row["selected_lineup_ids"]]
        maxima = scores[[ordinal[value] for value in selected]].max(axis=0)
        metrics.append(_with_hash({
            "view_id": row["view_id"],
            "strategy_id": row["strategy_id"],
            "selected_lineup_ids_sha256": row["selected_lineup_ids_sha256"],
            "heldout_world_count": worlds_per_block,
            "mean_portfolio_max": float(maxima.mean(dtype=np.float64)),
            "median_portfolio_max": float(np.median(maxima)),
            "maximum_portfolio_max": float(maxima.max()),
            "world_count_ge_200": int(np.count_nonzero(maxima >= 200.0)),
            "world_count_ge_230": int(np.count_nonzero(maxima >= 230.0)),
        }, field_name="metric_sha256"))
    body = {
        "schema": CONTROL_EVALUATION_SCHEMA,
        "cell_id": result["cell_id"],
        "sensitivity_result_sha256": result["sensitivity_result_sha256"],
        "full_heldout_score_matrix_sha256": _matrix_hash(
            scores, label="full heldout score matrix"
        ),
        "metric_count": len(metrics),
        "metrics": metrics,
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="evaluation_result_sha256")


def _selector_books(result: Mapping[str, object]) -> list[dict[str, object]]:
    books: list[dict[str, object]] = []
    grouped = _mapping(result["grouped_result"], label="grouped result")
    for selector in grouped["selectors"]:
        for prefix in selector["prefixes"]:
            books.append({
                "selector_id": f"grouped-rank80:{selector['preset_id']}",
                "prefix_size": prefix["prefix_size"],
                "selected_lineup_ids": prefix["selected_lineup_ids"],
            })
    ranked = _mapping(result["rank150_result"], label="rank150 result")
    for selector in ranked["selectors"]:
        for book in selector["entry_books"]:
            books.append({
                "selector_id": f"rank150:{selector['preset_id']}",
                "prefix_size": book["prefix_size"],
                "selected_lineup_ids": book["selected_lineup_ids"],
            })
    dpp = _mapping(result["dpp_result"], label="DPP result")
    for prefix in dpp["prefixes"]:
        books.append({
            "selector_id": "rank150:effective-independent-shots-v1",
            "prefix_size": prefix["prefix_size"],
            "selected_lineup_ids": prefix["selected_lineup_ids"],
        })
    return books


def evaluate_fair_fill_selector_result_v1(
    evaluation: object, *, selector_result: object
) -> dict[str, object]:
    """Evaluate frozen books on held-out simulated worlds, never outcomes."""
    retained_evaluation = validate_fair_fill_evaluation_inputs_v1(evaluation)
    result = _mapping(selector_result, label="selector result")
    if (
        result.get("schema") != SELECTOR_RESULT_SCHEMA
        or result.get("selector_result_sha256") != _hash({
            key: item for key, item in result.items() if key != "selector_result_sha256"
        })
        or result.get("cell_id") != retained_evaluation.cell_id
        or result.get("heldout_block_label_only") != retained_evaluation.heldout_block
        or _mapping(result.get("selection_binding"), label="selection binding").get(
            "plan_sha256"
        ) != retained_evaluation.binding.get("plan_sha256")
        or result.get("realized_outcomes_read") is not False
    ):
        _fail("selector/evaluation binding differs")
    ordinal = {
        lineup_id: index
        for index, lineup_id in enumerate(retained_evaluation.sampled_lineup_ids)
    }
    metrics: list[dict[str, object]] = []
    for book in _selector_books(result):
        selected = [str(item) for item in book["selected_lineup_ids"]]
        if len(selected) != len(set(selected)) or not set(selected) <= set(ordinal):
            _fail("selector book lies outside heldout evaluation rows")
        maxima = retained_evaluation.heldout_score_matrix[
            [ordinal[item] for item in selected]
        ].max(axis=0)
        metrics.append(_with_hash({
            "selector_id": book["selector_id"],
            "prefix_size": book["prefix_size"],
            "selected_lineup_ids_sha256": _hash(selected),
            "heldout_world_count": retained_evaluation.worlds_per_block,
            "mean_portfolio_max": float(maxima.mean(dtype=np.float64)),
            "median_portfolio_max": float(np.median(maxima)),
            "maximum_portfolio_max": float(maxima.max()),
            "world_count_ge_200": int(np.count_nonzero(maxima >= 200.0)),
            "world_count_ge_230": int(np.count_nonzero(maxima >= 230.0)),
            "simulated_scores_only": True,
        }, field_name="metric_sha256"))
    body = {
        "schema": EVALUATION_RESULT_SCHEMA,
        "cell_id": retained_evaluation.cell_id,
        "heldout_block": retained_evaluation.heldout_block,
        "evaluation_binding": dict(retained_evaluation.binding),
        "selector_result_sha256": result["selector_result_sha256"],
        "metric_count": len(metrics),
        "metrics": metrics,
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="evaluation_result_sha256")


def _support_state(strategy_id: str, profile_id: str) -> tuple[str, str]:
    if strategy_id in {
        "no-good-distinct-next-best-v1", "quality-diversity-reserve-v1"
    }:
        return "not-runnable-no-artifact", (
            "planned arm has no frozen generation law or candidate artifact"
        )
    if strategy_id == "per-world-exact-v1":
        if profile_id in profiles.PROFILE_ORDER:
            return "adapter-available", "existing F7/F8/F9 population lineups"
        return "not-applicable", "per-world challenger does not own F0"
    if strategy_id in {"game-stack-control-v1", "dark-game-control-v1"} and profile_id == "F8-game-cap-3":
        return "mechanically-unsupported", "five-player game lock conflicts with max-from-game 3"
    if strategy_id in FAMILY_CONTROL_TAG_BY_STRATEGY:
        if profile_id == INCUMBENT_PROFILE_ID:
            return "adapter-available", "filter existing tagged incumbent occurrences"
        if strategy_id == "role-epistemic-control-v1":
            return "source-required", "historical role-belief worlds must be regenerated under this profile"
        return "generation-required", "family must be generated under this relaxed profile"
    if strategy_id in {"legacy-mix-v1", "all-boom-unique-fill-v1"} and profile_id == INCUMBENT_PROFILE_ID:
        return "adapter-available", "existing frozen factorial artifact"
    return "generation-required", "no immutable candidate cell currently combines this fill and profile"


def compile_fair_fill_retest_controller_v1(
    *,
    candidate_cells: Sequence[Mapping[str, object]] = (),
    allow_non_authoritative: bool = False,
) -> dict[str, object]:
    """Inventory the requested matrix and compile every runnable fair fold."""
    if type(allow_non_authoritative) is not bool:
        _fail("controller authority switch must be a literal boolean")
    cells = [validate_candidate_cell_v1(cell) for cell in candidate_cells]
    cells.sort(key=lambda cell: str(cell["cell_id"]))
    if len({str(cell["cell_id"]) for cell in cells}) != len(cells):
        _fail("controller candidate cells must be unique")
    if len({_hash(cell["slate"]) for cell in cells}) > 1:
        _fail("one controller invocation may cover only one slate")
    supplied = {str(cell["cell_id"]): cell for cell in cells}
    matrix: list[dict[str, object]] = []
    selectors = selector_registry_v1()
    for strategy_id in FILL_STRATEGY_ORDER:
        for profile_id in PROFILE_ORDER:
            cell_id = _cell_id(strategy_id, profile_id)
            state, reason = _support_state(strategy_id, profile_id)
            if cell_id in supplied:
                if state == "adapter-available":
                    state = "candidate-cell-supplied"
                    reason = (
                        "validated score-free candidate cell is ready for "
                        "fold compilation"
                    )
                else:
                    state = "rejected-unsupported-source"
                    reason = (
                        "caller input cannot override registry support: " + reason
                    )
            matrix.append({
                "fill_strategy_id": strategy_id,
                "construction_profile_id": profile_id,
                "cell_id": cell_id,
                "status": state,
                "reason": reason,
                "candidate_cell_sha256": (
                    supplied[cell_id]["cell_sha256"] if cell_id in supplied else None
                ),
            })
    grouped: dict[tuple[str, bool], list[dict[str, object]]] = {}
    for cell in cells:
        support, _reason = _support_state(
            str(cell["fill_strategy_id"]),
            str(cell["construction_profile_id"]),
        )
        if support != "adapter-available":
            continue
        key = (str(cell["comparison_cohort_id"]), bool(cell["diagnostic_only"]))
        grouped.setdefault(key, []).append(cell)
    fold_compilations: list[dict[str, object]] = []
    work_items: list[dict[str, object]] = []
    for (cohort, diagnostic_only), group in sorted(grouped.items()):
        group.sort(key=lambda cell: str(cell["cell_id"]))
        for heldout in rw.WORLD_BLOCKS:
            try:
                plan = build_fair_fill_fold_plan_v1(
                    candidate_cells=group,
                    heldout_block=heldout,
                    allow_non_authoritative=allow_non_authoritative,
                    allow_diagnostic=diagnostic_only,
                )
            except CorpusR6FairFillRetestV1Error as exc:
                fold_compilations.append({
                    "comparison_cohort_id": cohort,
                    "diagnostic_only": diagnostic_only,
                    "heldout_block": heldout,
                    "cell_ids": [cell["cell_id"] for cell in group],
                    "status": "blocked",
                    "reason": str(exc),
                    "plan_sha256": None,
                    "common_count": None,
                })
                continue
            fold_compilations.append({
                "comparison_cohort_id": cohort,
                "diagnostic_only": diagnostic_only,
                "heldout_block": heldout,
                "cell_ids": list(plan["cell_order"]),
                "status": "ready",
                "reason": None,
                "plan_sha256": plan["plan_sha256"],
                "common_count": plan["common_count"],
            })
            for cell in group:
                for selector in selectors["selectors"]:
                    work_items.append({
                        "plan_sha256": plan["plan_sha256"],
                        "cell_id": cell["cell_id"],
                        "cell_sha256": cell["cell_sha256"],
                        "heldout_block": heldout,
                        "selector_id": selector["selector_id"],
                        "selector_sha256": selector["selector_sha256"],
                    })
    body = {
        "schema": CONTROLLER_SCHEMA,
        "fill_registry_sha256": fill_strategy_registry_v1()["registry_sha256"],
        "profile_registry_sha256": construction_profile_registry_v1()["registry_sha256"],
        "selector_registry_sha256": selectors["registry_sha256"],
        "incumbent_control_registry_sha256": incumbent_control_registry_v1()[
            "registry_sha256"
        ],
        "requested_cell_count": len(FILL_STRATEGY_ORDER) * len(PROFILE_ORDER),
        "slate": cells[0]["slate"] if cells else None,
        "matrix": matrix,
        "supplied_candidate_cell_count": len(cells),
        "supplied_candidate_cell_sha256s": [cell["cell_sha256"] for cell in cells],
        "fold_compilation_count": len(fold_compilations),
        "fold_compilations": fold_compilations,
        "selector_fold_work_item_count": len(work_items),
        "selector_fold_work_items": work_items,
        "incumbent_control_sensitivity_required_per_ready_cell_fold": True,
        "incumbent_control_sensitivity_views": [
            "full-corpus", "deterministic-equal-size"
        ],
        "fold_plan_bodies_rebuilt_deterministically_from_candidate_cells": True,
        "allow_non_authoritative": allow_non_authoritative,
        "cloud_launch_performed": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="controller_sha256")


__all__ = [
    "CANDIDATE_CELL_SCHEMA",
    "CorpusR6FairFillRetestV1Error",
    "FILL_STRATEGY_ORDER",
    "FairFillEvaluationInputsV1",
    "FairFillSelectionInputsV1",
    "INCUMBENT_PROFILE_ID",
    "MAXIMUM_COMMON_COUNT",
    "MINIMUM_COMMON_COUNT",
    "PROFILE_ORDER",
    "WORK_RECEIPT_SCHEMA",
    "bind_fair_fill_evaluation_inputs_v1",
    "bind_fair_fill_selection_inputs_v1",
    "build_candidate_cell_from_occurrences_v1",
    "build_fair_fill_fold_plan_v1",
    "build_tagged_family_control_cell_v1",
    "candidate_cell_from_population_profile_lineups_v1",
    "compile_fair_fill_retest_controller_v1",
    "construction_profile_registry_v1",
    "evaluate_fair_fill_selector_result_v1",
    "evaluate_incumbent_control_sensitivity_v1",
    "fill_generation_environment_v1",
    "fill_strategy_registry_v1",
    "incumbent_control_registry_v1",
    "run_fair_fill_selectors_v1",
    "run_incumbent_control_sensitivity_v1",
    "selector_registry_v1",
    "validate_candidate_cell_v1",
    "validate_fair_fill_fold_plan_v1",
    "validate_fair_fill_evaluation_inputs_v1",
    "validate_fair_fill_selection_inputs_v1",
]
