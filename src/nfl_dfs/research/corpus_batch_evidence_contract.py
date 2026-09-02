"""Pre-outcome evidence contract for the seven-arm corpus parameter batch.

This module is a pure preregistration layer.  It binds one already-valid
``corpus_parametric_batch`` manifest to immutable endpoint, gate,
multiplicity, license-transition, reporting, and evidence-graph topology
definitions.  It owns no solver, outcome reader, object-store client, graph
writer, lease, deployment path, or mutable process environment.

The contract itself always has ``decision_authority=False``.  A separately
governed realized-outcome completion may decide only whether one of the six
frozen challengers is allowed to become one fresh, default-off 2026
prospective shadow.  It can never authorize production, adoption, default-on
behavior, money entries, historical retuning, or a second historical look.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Final

from .corpus_parametric_batch import (
    MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
    PARAMETER_ORDER,
    PARAMETER_SCHEMA_SHA256,
    PARAMETER_SET_ORDER,
    PUBLICATION_MODE,
    SELECTED_ENTRY_BUDGET,
    SOLVE_ATTEMPTS_PER_BLOCK,
    TASK_WORLD_SOURCE_ROLES,
    canonical_json_bytes,
    canonical_sha256,
    normalize_object_identity,
    parse_canonical_json_bytes,
    validate_batch_manifest,
    validate_json_identity,
)


SCHEMA: Final = "corpus-parametric-batch-evidence-contract/v1"
V2_SCHEMA: Final = "corpus-parametric-batch-evidence-contract/v2"
CONTRACT_PHASE: Final = "pre_run_outcome_blind"
KNOWLEDGE_CLASS: Final = "outcome_blind"
INCUMBENT_PARAMETER_SET_ID: Final = "incumbent"
CHALLENGER_PARAMETER_SET_IDS: Final = PARAMETER_SET_ORDER[1:]
THRESHOLDS_DK: Final = (187, 194, 200, 210, 220, 230, 240)
MICRO_DK_PER_POINT: Final = 1_000_000

EXPECTED_INVENTORY_SCHEMA: Final = "nfl-dfs-effective-policy-rule-inventory/v2"
EXPECTED_INVENTORY_SHA256: Final = (
    "865eb259079f2151fb92f26eab33c8cdab353ec60a89766d1a934861fdc1bd70"
)
EXPECTED_RULE_UNIVERSE_SHA256: Final = (
    "1c0da0299bb6295711389208035907f11dbf28fe32d53771bb98546f740fefea"
)
EXPECTED_INVENTORY_SOURCE_SET_SHA256: Final = (
    "a498dea7796276f84e13c86a8db034fb5ddd295666ba34b71bb7942f44a2e8b1"
)
EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256: Final = (
    "3ddef13eade46dd3198bc86acdb7f16f56ea8fc30a81c2f421c5c3e72b8ddd99"
)
V2_EXPECTED_INVENTORY_SHA256: Final = (
    "830dcfbde6cd3e2a6ac629cfbf6a7f8acd2b237f8951f9c050d40a6e1f30ad54"
)
V2_EXPECTED_RULE_UNIVERSE_SHA256: Final = (
    "c8d51dbca4090b342d7979c3bb425d7c79cdd79e4d03d1159acc1c934f7c8cc4"
)
V2_EXPECTED_INVENTORY_SOURCE_SET_SHA256: Final = (
    "7061e2cc6657101a9a3f36855926b8523550ca697d0f022c12143e8a28fde791"
)
V2_EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256: Final = (
    "d3ad2c67c3e57e6199c83a3e4de8c3c6ef07fde44a4c289d1f85464f9c52a779"
)


@dataclass(frozen=True)
class _EvidenceContractVersion:
    schema: str
    contract_suffix: str
    inventory_sha256: str
    rule_universe_sha256: str
    inventory_source_set_sha256: str
    classified_input_projection_sha256: str


_V1_CONTRACT: Final = _EvidenceContractVersion(
    schema=SCHEMA,
    contract_suffix="v1",
    inventory_sha256=EXPECTED_INVENTORY_SHA256,
    rule_universe_sha256=EXPECTED_RULE_UNIVERSE_SHA256,
    inventory_source_set_sha256=EXPECTED_INVENTORY_SOURCE_SET_SHA256,
    classified_input_projection_sha256=(
        EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256
    ),
)
_V2_CONTRACT: Final = _EvidenceContractVersion(
    schema=V2_SCHEMA,
    contract_suffix="v2",
    inventory_sha256=V2_EXPECTED_INVENTORY_SHA256,
    rule_universe_sha256=V2_EXPECTED_RULE_UNIVERSE_SHA256,
    inventory_source_set_sha256=V2_EXPECTED_INVENTORY_SOURCE_SET_SHA256,
    classified_input_projection_sha256=(
        V2_EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256
    ),
)

PARENT_GRAPH: Final = {
    "builder_sha256": (
        "f70e5b1667107201808756c8737d23fac6cb47e35c80f47bef05177cec3b2d59"
    ),
    "decision_authority": False,
    "graph_id": "graph:generated-corpus-tail-20260821-v1",
    "manifest_sha256": (
        "dcfbe866414f6b011eda14659931217168bcc5371cc6caade9c596a4df8fe9ca"
    ),
    "registry_sha256": (
        "388d9645a34a29abff0bf22f50ee352531e9b0264fb27013b374fb21efe95751"
    ),
    "schema": "nfl-dfs-research-evidence-graph/v1",
}

PAIRED_TEST_LAW: Final = {
    "add_one_correction_above_exact_limit": True,
    "algorithm": "paired-weekly-max-mean-and-wilcoxon-sign-flip",
    "exact_enumeration_nonzero_pair_limit": 20,
    "inclusive_comparison_epsilon": 1e-12,
    "monte_carlo_chunk_size": 65_536,
    "monte_carlo_resamples": 200_000,
    "monte_carlo_rng_call": (
        "rng.choice((-1.0,1.0),size=(take,n_nonzero))"
    ),
    "monte_carlo_rng_lifecycle": (
        "fresh-default_rng-seed-for-each-challenger-and-endpoint"
    ),
    "monte_carlo_seed": 20_260_818,
    "p_value_sidedness": "two_sided",
    "protocol_id": "20260818-paired-max-coprimary-v1",
    "same_sign_matrix_for_mean_and_signed_rank": True,
    "signed_rank_ties": "average-rank-stable-absolute-nonzero-differences",
    "zero_differences": "excluded_from_inference_and_reported_as_ties",
}

_PARAMETER_RULE_IDS: Final = {
    "bring_back_min": "rule:bring-back-min-one",
    "forbid_rb_vs_dst": "rule:forbid-rb-vs-dst",
    "forbid_two_rb_same_team": "rule:forbid-two-rb-same-team",
    "min_lineup_salary": "rule:salary-floor-49000",
    "qb_stack_min": "rule:qb-stack-min-two",
}


class CorpusBatchEvidenceContractError(ValueError):
    """A fail-closed preregistration or evidence-binding violation."""


def _score_free_endpoints() -> list[dict[str, object]]:
    endpoints: list[dict[str, object]] = [
        {
            "direction": "higher_is_better",
            "formula": (
                "primary_optimum_micro(task,parameter_set,visit); exact signed "
                "integer from the retained optimal-solver proof"
            ),
            "gate_role": "paired_relaxation_monotonicity",
            "grain": "task_parameter_set_visit",
            "id": "endpoint:corpus:visit-primary-optimum-micro",
            "label": "Visit primary optimum in exact integer objective units",
            "phase": "score_free",
            "population_stage": "visit_output",
            "thresholds_micro": [],
        },
        {
            "direction": "nonnegative_required",
            "formula": (
                "primary_optimum_micro(task,challenger,visit) - "
                "primary_optimum_micro(task,incumbent,visit), aligned on the "
                "same task, world block, world index, objective, and visit ordinal"
            ),
            "gate_role": "paired_relaxation_monotonicity",
            "grain": "task_challenger_visit",
            "id": "endpoint:corpus:paired-primary-optimum-delta-micro",
            "label": "Relaxed-minus-incumbent paired visit optimum",
            "phase": "score_free",
            "population_stage": "visit_output",
            "thresholds_micro": [],
        },
        {
            "direction": "at_least_80_required",
            "formula": (
                "cardinality(first_occurrence_unique(ordered_visit_rosters"
                "(task,parameter_set)))"
            ),
            "gate_role": "candidate_support",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:generated-unique-lineup-count",
            "label": "First-occurrence unique generated lineups",
            "phase": "score_free",
            "population_stage": "generated_unique",
            "thresholds_micro": [],
        },
        {
            "direction": "exact_generated_unique_by_50000_required",
            "formula": (
                "for each exact task/slate and parameter set, every canonical "
                "generated-unique roster identity has exactly one float64 score "
                "row over the common ordered 50000 source worlds; score-matrix "
                "roster-row identity set equals the complete frozen generated-"
                "unique roster identity set and world columns equal the complete "
                "ordered R0..R4 x 0..9999 source-world lattice"
            ),
            "gate_role": "score_free_score_matrix_coverage",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:simulated-scored-generated-unique-count",
            "label": "Generated-unique rosters with complete simulated scores",
            "phase": "score_free",
            "population_stage": "generated_unique",
            "thresholds_micro": [],
        },
        {
            "direction": "zero_for_incumbent_positive_for_every_challenger",
            "formula": (
                "sum over generated-unique rosters of I[at least one of the "
                "five incumbent house constraints is violated]"
            ),
            "gate_role": "outside_incumbent_law_nonvacuity",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:outside-incumbent-law-unique-count",
            "label": "Generated unique lineups outside the incumbent five-rule law",
            "phase": "score_free",
            "population_stage": "generated_unique",
            "thresholds_micro": [],
        },
        {
            "direction": "exact_zero_required",
            "formula": (
                "sum over generated-unique rosters of I[independent DK Classic "
                "legality audit fails]"
            ),
            "gate_role": "dk_legality",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:dk-invalid-generated-unique-count",
            "label": "DK-invalid generated unique lineups",
            "phase": "score_free",
            "population_stage": "generated_unique",
            "thresholds_micro": [],
        },
        {
            "direction": "exact_80_required",
            "formula": "cardinality(selected_exact80(task,parameter_set))",
            "gate_role": "exact80",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:selected-exact80-count",
            "label": "Selected unique exact-80 entries",
            "phase": "score_free",
            "population_stage": "selected_exact80",
            "thresholds_micro": [],
        },
        {
            "direction": "higher_is_better_descriptive_only",
            "formula": (
                "mean over the common ordered 50000 source worlds of max "
                "simulated_score(task,parameter_set,generated_unique,world)"
            ),
            "gate_role": "outcome_blind_diagnostic",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:simulated-candidate-ceiling-c",
            "label": "Outcome-blind simulated candidate ceiling C",
            "phase": "score_free",
            "population_stage": "generated_unique",
            "thresholds_micro": [],
        },
        {
            "direction": "higher_is_better_descriptive_only",
            "formula": (
                "mean over the common ordered 50000 source worlds of max "
                "simulated_score(task,parameter_set,selected_exact80,world)"
            ),
            "gate_role": "outcome_blind_diagnostic",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:simulated-exact80-maximum-s",
            "label": "Outcome-blind simulated exact-80 maximum S",
            "phase": "score_free",
            "population_stage": "selected_exact80",
            "thresholds_micro": [],
        },
        {
            "direction": "lower_is_better_descriptive_only",
            "formula": (
                "simulated_candidate_ceiling_c(task,parameter_set) - "
                "simulated_exact80_maximum_s(task,parameter_set)"
            ),
            "gate_role": "outcome_blind_diagnostic",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:simulated-conversion-gap-c-minus-s",
            "label": "Outcome-blind simulated C-minus-S conversion gap",
            "phase": "score_free",
            "population_stage": "selected_exact80",
            "thresholds_micro": [],
        },
    ]
    for stage, population_stage in (
        ("generated-unique", "generated_unique"),
        ("selected-exact80", "selected_exact80"),
    ):
        for field in PARAMETER_ORDER:
            endpoints.append({
                "direction": "descriptive_mechanism_not_quality",
                "formula": (
                    f"sum over {population_stage}(task,parameter_set) of "
                    f"I[{_PARAMETER_RULE_IDS[field]} is violated]"
                ),
                "gate_role": "effective_rule_dose",
                "grain": "task_parameter_set",
                "id": f"endpoint:corpus:{stage}-{field.replace('_', '-')}-violations",
                "label": f"{stage} violations of {_PARAMETER_RULE_IDS[field]}",
                "phase": "score_free",
                "population_stage": population_stage,
                "thresholds_micro": [],
            })
    return endpoints


def _realized_endpoints() -> list[dict[str, object]]:
    thresholds = [value * MICRO_DK_PER_POINT for value in THRESHOLDS_DK]
    return [
        {
            "direction": "exact_generated_unique_count_required",
            "formula": (
                "cardinality of exact (task_index,season,week,slate_id,canonical "
                "generated-unique roster identity) keys with one exactly "
                "reconstructed actual-score micro-DK value; the scored keyed "
                "roster set must equal the complete frozen keyed generated-unique "
                "roster set for the exact task/slate and parameter set"
            ),
            "gate_role": "historical_score_coverage",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:realized-scored-generated-unique-count",
            "label": "Historically scored generated-unique lineups",
            "phase": "realized_historical",
            "population_stage": "generated_unique",
            "thresholds_micro": [],
        },
        {
            "direction": "higher_is_better",
            "formula": (
                "C[task,parameter_set] = max exact actual_score_micro over the "
                "complete generated-unique population"
            ),
            "gate_role": "historical_co_primary",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:realized-candidate-ceiling-c",
            "label": "Realized generated-candidate ceiling C",
            "phase": "realized_historical",
            "population_stage": "generated_unique",
            "thresholds_micro": thresholds,
        },
        {
            "direction": "higher_is_better",
            "formula": (
                "S[task,parameter_set] = max exact actual_score_micro over the "
                "frozen selected exact-80 population"
            ),
            "gate_role": "historical_co_primary",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:realized-exact80-maximum-s",
            "label": "Realized selected exact-80 maximum S",
            "phase": "realized_historical",
            "population_stage": "selected_exact80",
            "thresholds_micro": thresholds,
        },
        {
            "direction": "lower_is_better_diagnostic_only",
            "formula": (
                "realized_candidate_ceiling_c(task,parameter_set) - "
                "realized_exact80_maximum_s(task,parameter_set)"
            ),
            "gate_role": "mandatory_conversion_diagnostic",
            "grain": "task_parameter_set",
            "id": "endpoint:corpus:realized-conversion-gap-c-minus-s",
            "label": "Realized C-minus-S conversion gap",
            "phase": "realized_historical",
            "population_stage": "selected_exact80",
            "thresholds_micro": [],
        },
    ]


def endpoint_registry() -> list[dict[str, object]]:
    """Return the closed, ordered endpoint registry."""
    rows = [*_score_free_endpoints(), *_realized_endpoints()]
    ids = [str(row["id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise CorpusBatchEvidenceContractError("endpoint ids repeat")
    return deepcopy(rows)


def _pre_outcome_gates() -> list[dict[str, object]]:
    return [
        {
            "failure_disposition": "invalid-pre-run-contract",
            "id": "gate:corpus:evidence-contract-frozen",
            "phase": "before_score_free_execution",
            "predicate": (
                "canonical create-once contract bytes and generation-pinned "
                "identity are bound by the outer execution freeze before task zero"
            ),
            "required_evidence_roles": [
                "evidence_contract_object", "outer_execution_freeze"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-batch-identity",
            "id": "gate:corpus:batch-manifest-seven-set-identity",
            "phase": "before_score_free_execution",
            "predicate": (
                "exact canonical batch manifest identity, five-field schema, "
                "incumbent, and all six challengers validate in fixed order"
            ),
            "required_evidence_roles": [
                "batch_manifest_object", "parameter_set_rows"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-source-world-pairing",
            "id": "gate:corpus:source-world-compute-pairing",
            "phase": "before_score_free_execution",
            "predicate": (
                "all seven arms share exact source bytes, top-200 R0-R4 world "
                "schedule, objective, solver authority, 1000 visits, 50000 "
                "selector worlds, deadline, deduplication, and exact-80 law"
            ),
            "required_evidence_roles": [
                "raw_source_freeze", "raw_world_artifacts",
                "world_schedule_authority", "registered_common_law"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-effective-policy",
            "id": "gate:corpus:effective-policy-runtime-replay",
            "phase": "after_score_free_execution",
            "predicate": (
                "regenerated inventory v2, classified-input projection, all "
                "ambient absences, every rule row, and every arm's exact applied "
                "dose independently replay from raw authorities"
            ),
            "required_evidence_roles": [
                "inventory_raw_bytes", "runtime_policy_rows",
                "classified_input_runtime_absence_proof"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-solver-or-retry-law",
            "id": "gate:corpus:solver-terminal-zero-retry-proof",
            "phase": "after_score_free_execution",
            "predicate": (
                "every task-by-arm-by-visit has one terminal proven-optimal "
                "solver witness under one total deadline; attempts=1 and retries=0"
            ),
            "required_evidence_roles": [
                "attempt_ledger", "solver_stage_proofs", "terminal_receipts"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-relaxation-monotonicity",
            "id": "gate:corpus:paired-objective-relaxation-monotonicity",
            "phase": "after_score_free_execution",
            "predicate": (
                "for every task, challenger, and aligned visit, exact integer "
                "challenger primary optimum minus incumbent primary optimum is "
                ">= 0; all 6 * task_count * 1000 pairs are retained and replayed"
            ),
            "required_evidence_roles": [
                "exact_primary_optimum_matrix", "independent_monotonicity_replay"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "score-free-arm-vacuity",
            "id": "gate:corpus:outside-incumbent-law-nonvacuity",
            "phase": "after_score_free_execution",
            "predicate": (
                "incumbent has zero outside-incumbent-law unique rosters; every "
                "single-removal arm has at least one unique roster violating its "
                "removed rule while satisfying the other four; the all-five arm "
                "has at least one unique roster violating at least one of the five"
            ),
            "required_evidence_roles": [
                "generated_unique_rosters", "independent_five_rule_census"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-legality-or-entry-budget",
            "id": "gate:corpus:dk-legality-and-exact80",
            "phase": "after_score_free_execution",
            "predicate": (
                "every generated and selected roster independently passes DK "
                "Classic hard legality and every task-by-arm book is 80 unique "
                "members of its own generated-unique population"
            ),
            "required_evidence_roles": [
                "generated_unique_rosters", "selected_rosters",
                "independent_dk_audit"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "invalid-scorefree-replay",
            "id": "gate:corpus:independent-scorefree-replay",
            "phase": "after_score_free_execution",
            "predicate": (
                "an independent verifier reloads raw sources and canonical bodies "
                "and reproduces source binding, policies, schedules, attempts, "
                "first occurrence, score matrices, selector, and all endpoints"
            ),
            "required_evidence_roles": [
                "independent_scorefree_verifier", "raw_authority_inventory"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "incomplete-simulated-score-coverage",
            "id": "gate:corpus:simulated-score-matrix-exact-roster-world-coverage",
            "phase": "after_score_free_execution",
            "predicate": (
                "for every exact task/slate and parameter set, every frozen "
                "generated-unique roster has exactly one float64 score row with "
                "exactly 50000 ordered values; the score-matrix roster-row set "
                "equals the complete generated-unique roster set and its columns "
                "equal the ordered R0..R4 x 0..9999 source-world lattice, with no "
                "missing, extra, partial, selected-only, or reordered coverage"
            ),
            "required_evidence_roles": [
                "generated_unique_rosters", "candidate_score_matrices",
                "ordered_source_world_lattice", "independent_scorefree_verifier",
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "incomplete-seven-arm-matrix",
            "id": "gate:corpus:complete-scorefree-result-matrix",
            "phase": "after_score_free_execution",
            "predicate": (
                "every manifest task has all seven ordered terminal result and "
                "effective-policy bodies; failed, losing, tied, or vacuous arms "
                "cannot be omitted, reordered, replaced, or rerun"
            ),
            "required_evidence_roles": [
                "task_result_bodies", "batch_completion_body"
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "missing-historical-authority",
            "id": "gate:corpus:historical-authorities-bound",
            "phase": "before_historical_outcome_read",
            "predicate": (
                "generation-pinned paired-statistics implementation, independent "
                "paired verifier, one-read actual-score query contract, realized "
                "completion schema, and unseen-2026 shadow gate are bound before "
                "the outcome lease is acquired"
            ),
            "required_evidence_roles": [
                "paired_statistics_implementation",
                "independent_paired_statistics_verifier",
                "historical_score_query_contract",
                "realized_completion_schema",
                "unseen_2026_shadow_gate_protocol",
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "incomplete-historical-score-coverage-law",
            "id": "gate:corpus:historical-exact-roster-coverage-contract",
            "phase": "before_historical_outcome_read",
            "predicate": (
                "the pinned one-read contract derives the exact distinct "
                "(task_index,season,week,slate_id,player-or-DST-id) source union "
                "from every frozen generated-unique roster across all tasks and "
                "arms, reconstructs one exact micro-DK score for every exact "
                "(task_index,season,week,slate_id,canonical-roster-identity) key, "
                "and requires per-task-arm keyed scored-roster set equality with "
                "no cross-slate aliasing and no missing, extra, partial, winner-"
                "only, or exact80-only rows"
            ),
            "required_evidence_roles": [
                "historical_score_query_contract",
                "generated_unique_roster_union_manifest",
                "realized_completion_schema",
            ],
            "required_for_outcome_read": True,
        },
        {
            "failure_disposition": "historical-read-not-licensed",
            "id": "gate:corpus:one-read-lease-ready",
            "phase": "immediately_before_historical_outcome_read",
            "predicate": (
                "all earlier gates are true, immutable score-free populations are "
                "complete, output prefix is create-once empty, the shared outcome "
                "lease is acquired once, and exactly one full seven-arm query is "
                "permitted with no partial-result inspection"
            ),
            "required_evidence_roles": [
                "pre_outcome_gate_completion", "historical_outcome_lease",
                "create_once_query_attempt"
            ],
            "required_for_outcome_read": True,
        },
    ]


def _historical_decision_law(task_count: int) -> dict[str, object]:
    return {
        "aligned_task_count": task_count,
        "challenger_comparisons": [{
            "challenger_parameter_set_id": parameter_set_id,
            "control_parameter_set_id": INCUMBENT_PARAMETER_SET_ID,
            "ordinal": ordinal,
        } for ordinal, parameter_set_id in enumerate(
            CHALLENGER_PARAMETER_SET_IDS, start=1
        )],
        "co_primary_endpoint_ids": [
            "endpoint:corpus:realized-candidate-ceiling-c",
            "endpoint:corpus:realized-exact80-maximum-s",
        ],
        "comparison_count": len(CHALLENGER_PARAMETER_SET_IDS),
        "historical_pass_predicates": [
            "all_pre_outcome_gates_true",
            "mean_delta_c_strictly_positive",
            "mean_delta_s_strictly_positive",
            "signed_rank_direction_c_positive",
            "signed_rank_direction_s_positive",
            "holm_adjusted_joint_p_le_0.05",
            "selected_s_194_count_delta_ge_minus_1",
            "selected_s_200_count_delta_ge_minus_1",
        ],
        "incumbent_parameter_set_id": INCUMBENT_PARAMETER_SET_ID,
        "joint_p_formula": (
            "max(p_C_mean_two_sided,p_C_signed_rank_two_sided,"
            "p_S_mean_two_sided,p_S_signed_rank_two_sided)"
        ),
        "multiplicity": {
            "alpha": 0.05,
            "family": "six-frozen-challengers-vs-common-incumbent",
            "holm_formula": (
                "sort (joint_p,challenger_ordinal); at zero-based position j "
                "compute min(1,(6-j)*joint_p); take the capped running maximum; "
                "map back to challenger ordinal"
            ),
            "hypothesis_count": 6,
            "method": "holm_step_down",
            "missing_or_invalid_comparison": "invalidate_entire_completion",
            "rounded_values_may_decide": False,
        },
        "nominee_order": [
            "smallest_holm_adjusted_joint_p",
            "largest_mean_delta_s",
            "largest_mean_delta_c",
            "largest_selected_s_200_count_delta",
            "smallest_fixed_parameter_set_ordinal",
        ],
        "nominee_pool": "historical_pass_true_only",
        "paired_test_law": deepcopy(PAIRED_TEST_LAW),
        "score_input_law": {
            "actual_score_input": "finite_nonboolean_json_integer_or_float",
            "cent_conversion": "python_round_nearest_even(score*100)",
            "cent_tolerance": 1e-9,
            "exact_internal_unit": "integer_micro_dk",
            "micro_dk_per_cent": 10_000,
            "micro_dk_per_point": MICRO_DK_PER_POINT,
            "outcomes_may_change_population": False,
            "thresholds_dk": list(THRESHOLDS_DK),
        },
        "winner_loser_reporting": {
            "all_parameter_set_order": list(PARAMETER_SET_ORDER),
            "better_tied_worse_formula": (
                "compare exact task-level micro-DK endpoint values against "
                "incumbent; counts must sum to aligned_task_count"
            ),
            "favorable_sorting_forbidden": True,
            "incumbent_row": "better=0,tied=aligned_task_count,worse=0",
            "losing_tied_failed_or_ineligible_rows_may_be_omitted": False,
            "rank_order": (
                "descending mean S, descending S count at 200, descending mean "
                "C, then fixed parameter-set ordinal"
            ),
            "realized_result_rows_required": 7,
        },
    }


def _license_state_machine() -> dict[str, object]:
    immutable_false = [
        "adoption_licensed",
        "default_on_licensed",
        "historical_retry_licensed",
        "historical_retune_licensed",
        "money_entry_licensed",
        "production_change_licensed",
    ]
    initial = {
        "adoption_licensed": False,
        "default_on_licensed": False,
        "historical_outcome_read_consumed": False,
        "historical_outcome_read_once_licensed": False,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "money_entry_licensed": False,
        "production_change_licensed": False,
        "prospective_shadow_create_licensed": False,
        "prospective_shadow_deploy_default_off_licensed": False,
        "prospective_shadow_freeze_licensed": False,
        "prospective_shadow_passed": False,
    }
    return {
        "initial_state": initial,
        "invariants": {
            "at_most_one_shadow_parameter_set": True,
            "contract_decision_authority": False,
            "immutable_false_fields": immutable_false,
            "shadow_default_off": True,
            "shadow_is_not_prospectively_passing_before_unseen_gate": True,
        },
        "transitions": [
            {
                "event": "all_pre_outcome_gates_pass",
                "result": {
                    **initial,
                    "historical_outcome_read_once_licensed": True,
                },
                "scope": "one_complete_seven-arm-historical-read",
            },
            {
                "event": "historical_outcome_read_launched_once",
                "result": {
                    **initial,
                    "historical_outcome_read_consumed": True,
                },
                "scope": "read-consumed-no-retry",
            },
            {
                "event": "separately_governed_realized_completion_no_pass",
                "result": {
                    **initial,
                    "historical_outcome_read_consumed": True,
                },
                "scope": "historical-shadow-nomination-only-no-nominee",
            },
            {
                "event": "separately_governed_realized_completion_with_nominee",
                "result": {
                    **initial,
                    "historical_outcome_read_consumed": True,
                    "prospective_shadow_create_licensed": True,
                    "prospective_shadow_deploy_default_off_licensed": True,
                    "prospective_shadow_freeze_licensed": True,
                },
                "scope": (
                    "exactly-one-fixed-parameter-set-fresh-unseen-2026-default-off-shadow"
                ),
            },
        ],
        "unseen_2026_transition": {
            "inside_this_contract": False,
            "predicate": (
                "a separately frozen prospective protocol grades only unseen "
                "2026 slates and passes its preregistered gate"
            ),
            "prospective_shadow_passed_before_transition": False,
        },
    }


def _missing_pre_run_artifacts() -> list[dict[str, str]]:
    return [
        {
            "blocks": "historical_outcome_read",
            "reason": (
                "the batch common law has no direct generation-pinned identity "
                "for the standing paired C/S statistics implementation"
            ),
            "role": "paired_statistics_implementation",
        },
        {
            "blocks": "historical_outcome_read",
            "reason": (
                "no source-independent exact-vector C/S paired-statistics verifier "
                "is bound by the batch foundation"
            ),
            "role": "independent_paired_statistics_verifier",
        },
        {
            "blocks": "historical_outcome_read",
            "reason": (
                "the exact one-read actual-score source/query/order/precision "
                "contract is outside the score-free batch foundation"
            ),
            "role": "historical_score_query_contract",
        },
        {
            "blocks": "historical_outcome_read",
            "reason": (
                "the canonical realized seven-row completion and authority schema "
                "does not yet exist"
            ),
            "role": "realized_completion_schema",
        },
        {
            "blocks": "prospective_shadow_deployment",
            "reason": (
                "historical evidence cannot define a passing prospective shadow; "
                "the unseen-2026 gate and default-off firewall need their own freeze"
            ),
            "role": "unseen_2026_shadow_gate_protocol",
        },
    ]


def _graph_topology(task_count: int, endpoint_rows: Sequence[object],
                    gate_rows: Sequence[object]) -> dict[str, object]:
    score_free_task_parameter_set_count = sum(
        isinstance(row, Mapping)
        and row.get("phase") == "score_free"
        and row.get("grain") == "task_parameter_set"
        for row in endpoint_rows
    )
    score_free_task_parameter_set_visit_count = sum(
        isinstance(row, Mapping)
        and row.get("phase") == "score_free"
        and row.get("grain") == "task_parameter_set_visit"
        for row in endpoint_rows
    )
    score_free_task_challenger_visit_count = sum(
        isinstance(row, Mapping)
        and row.get("phase") == "score_free"
        and row.get("grain") == "task_challenger_visit"
        for row in endpoint_rows
    )
    realized_endpoint_count = sum(
        isinstance(row, Mapping) and row.get("phase") == "realized_historical"
        for row in endpoint_rows
    )
    parameter_set_count = len(PARAMETER_SET_ORDER)
    challenger_count = len(CHALLENGER_PARAMETER_SET_IDS)
    visit_count = MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
    score_free_task_parameter_set_measurements = (
        task_count * parameter_set_count * score_free_task_parameter_set_count
    )
    score_free_task_parameter_set_visit_measurements = (
        task_count * parameter_set_count * visit_count
        * score_free_task_parameter_set_visit_count
    )
    score_free_task_challenger_visit_measurements = (
        task_count * challenger_count * visit_count
        * score_free_task_challenger_visit_count
    )
    score_free_measurement_count = (
        score_free_task_parameter_set_measurements
        + score_free_task_parameter_set_visit_measurements
        + score_free_task_challenger_visit_measurements
    )
    realized_measurement_count = (
        task_count * parameter_set_count * realized_endpoint_count
    )
    license_count = 12
    return {
        "adapter_law": {
            "append_only_new_graph_version": True,
            "decision_authority_before_realized_completion": False,
            "graph_is_run_controller": False,
            "independent_adapter_required": True,
            "outcome_blind_worker_graph_mutation": False,
            "parent_graph_immutable": True,
            "realized_decision_authority_scope": (
                "historical-shadow-nomination-only"
            ),
        },
        "edge_families": [
            {
                "cardinality": parameter_set_count,
                "from": "batch:{batch_id}",
                "kind": "USES_PARAMETER_SET",
                "to": "parameter-set:{batch_id}:{parameter_set_id}",
            },
            {
                "cardinality": parameter_set_count * len(PARAMETER_ORDER),
                "from": "parameter-set:{batch_id}:{parameter_set_id}",
                "kind": "SETS_PARAMETER",
                "properties": "exact typed control/treatment value",
                "to": "parameter:corpus:{parameter_name}",
            },
            {
                "cardinality": task_count + 1,
                "from": "batch:{batch_id}",
                "kind": "BOUND_TO_EXECUTION",
                "to": "task executions plus one independent finisher execution",
            },
            {
                "cardinality": parameter_set_count * task_count,
                "from": "execution:{batch_id}:task-{task_index_04d}",
                "kind": "PRODUCES",
                "to": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:visit-output"
                ),
            },
            {
                "cardinality": parameter_set_count * task_count,
                "from": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:visit-output"
                ),
                "kind": "PRODUCES",
                "to": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:generated-unique"
                ),
            },
            {
                "cardinality": parameter_set_count * task_count,
                "from": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:generated-unique"
                ),
                "kind": "PRODUCES",
                "to": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:selected-exact80"
                ),
            },
            {
                "cardinality": score_free_task_parameter_set_measurements,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:{endpoint_slug}"
                ),
                "kind": "MEASURES",
                "to": "score-free task-parameter-set endpoint",
            },
            {
                "cardinality": score_free_task_parameter_set_measurements,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:{endpoint_slug}"
                ),
                "kind": "OBSERVED_ON",
                "to": "truthful endpoint population stage",
            },
            {
                "cardinality": score_free_task_parameter_set_visit_measurements,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:visit-{visit_ordinal_04d}:"
                    "{endpoint_slug}"
                ),
                "kind": "MEASURES",
                "to": "score-free task-parameter-set-visit endpoint",
            },
            {
                "cardinality": score_free_task_parameter_set_visit_measurements,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:visit-{visit_ordinal_04d}:"
                    "{endpoint_slug}"
                ),
                "kind": "OBSERVED_ON",
                "to": "truthful endpoint population stage",
            },
            {
                "cardinality": score_free_task_challenger_visit_measurements,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{challenger_parameter_set_id}:visit-{visit_ordinal_04d}:"
                    "{endpoint_slug}"
                ),
                "kind": "MEASURES",
                "to": "score-free task-challenger-visit endpoint",
            },
            {
                "cardinality": score_free_task_challenger_visit_measurements,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{challenger_parameter_set_id}:visit-{visit_ordinal_04d}:"
                    "{endpoint_slug}"
                ),
                "kind": "OBSERVED_ON",
                "to": "paired incumbent/challenger visit population",
            },
            {
                "cardinality": realized_measurement_count,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:{endpoint_slug}"
                ),
                "kind": "MEASURES",
                "to": "realized endpoint; governed completion only",
            },
            {
                "cardinality": realized_measurement_count,
                "from": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:{endpoint_slug}"
                ),
                "kind": "OBSERVED_ON",
                "to": "truthful endpoint population stage",
            },
            {
                "cardinality": len(gate_rows),
                "from": "batch:{batch_id}",
                "kind": "EVALUATES_GATE",
                "to": "gate:corpus:{gate_slug}",
            },
            {
                "cardinality": "explicit-many; exact mapping from license transitions",
                "from": "gate:corpus:{gate_slug}",
                "kind": "DECIDES_LICENSE",
                "to": "license:corpus:{license_slug}",
            },
        ],
        "node_families": [
            {"cardinality": 1, "id": "batch:{batch_id}", "kind": "batch"},
            {
                "cardinality": 5,
                "id": "parameter:corpus:{parameter_name}",
                "kind": "parameter",
            },
            {
                "cardinality": parameter_set_count,
                "id": "parameter-set:{batch_id}:{parameter_set_id}",
                "kind": "parameter_set",
            },
            {
                "cardinality": task_count,
                "id": "execution:{batch_id}:task-{task_index_04d}",
                "kind": "execution",
            },
            {
                "cardinality": 1,
                "id": "execution:{batch_id}:independent-finisher",
                "kind": "execution",
            },
            {
                "cardinality": task_count * parameter_set_count,
                "id": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:visit-output"
                ),
                "kind": "population",
            },
            {
                "cardinality": task_count * parameter_set_count,
                "id": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:generated-unique"
                ),
                "kind": "population",
            },
            {
                "cardinality": task_count * parameter_set_count,
                "id": (
                    "population:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:selected-exact80"
                ),
                "kind": "population",
            },
            {
                "cardinality": len(endpoint_rows),
                "id": "literal endpoint registry id",
                "kind": "endpoint",
            },
            {
                "cardinality": score_free_task_parameter_set_measurements,
                "grain": "task_parameter_set",
                "id": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:{endpoint_slug}"
                ),
                "kind": "measurement",
                "materialization_phase": "score_free_completion",
            },
            {
                "cardinality": score_free_task_parameter_set_visit_measurements,
                "grain": "task_parameter_set_visit",
                "id": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:visit-{visit_ordinal_04d}:"
                    "{endpoint_slug}"
                ),
                "kind": "measurement",
                "materialization_phase": "score_free_completion",
            },
            {
                "cardinality": score_free_task_challenger_visit_measurements,
                "grain": "task_challenger_visit",
                "id": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{challenger_parameter_set_id}:visit-{visit_ordinal_04d}:"
                    "{endpoint_slug}"
                ),
                "kind": "measurement",
                "materialization_phase": "score_free_completion",
            },
            {
                "cardinality": realized_measurement_count,
                "grain": "task_parameter_set",
                "id": (
                    "measurement:{batch_id}:task-{task_index_04d}:"
                    "{parameter_set_id}:{endpoint_slug}"
                ),
                "kind": "measurement",
                "materialization_phase": "realized_completion_only",
            },
            {
                "cardinality": len(gate_rows),
                "id": "literal gate registry id",
                "kind": "gate",
            },
            {
                "cardinality": license_count,
                "id": "license:corpus:{license_slug}",
                "kind": "license",
            },
        ],
        "parent_graph": deepcopy(PARENT_GRAPH),
        "storage_plane": {
            "application_operational_datastore_shared": False,
            "authoritative_artifacts": (
                "canonical-create-once-json-and-generation-pinned-object-bodies"
            ),
            "dedicated_logical_database_required": True,
            "graph_can_authorize_execution_or_policy": False,
            "graph_payload_scope": (
                "identities-relations-rule-states-measurements-and-object-pointers"
            ),
            "large_world_matrices_or_raw_score_bodies_in_graph": False,
            "projection_is_append_only": True,
            "projection_is_rebuildable_from_authorities": True,
            "recommended_query_projection": "dedicated-neo4j-or-equivalent",
        },
        "population_stage_law": {
            "admission_label": "first-occurrence-generated-unique-union",
            "cbwu_admission_claim_permitted": False,
            "selected_population": "selected-exact80",
            "visit_population": "visit-output",
        },
        "resolved_cardinalities": {
            "endpoint_count": len(endpoint_rows),
            "gate_count": len(gate_rows),
            "license_count": license_count,
            "parameter_count": len(PARAMETER_ORDER),
            "parameter_set_count": parameter_set_count,
            "population_count": 3 * task_count * parameter_set_count,
            "realized_measurement_count_if_completed": realized_measurement_count,
            "score_free_measurement_count": score_free_measurement_count,
            "task_execution_count": task_count,
        },
    }


def _validate_foundation_identity(
    manifest: Mapping[str, object], version: _EvidenceContractVersion
) -> None:
    common = manifest["common_law"]
    expected = {
        "effective_policy_classified_input_projection_sha256": (
            version.classified_input_projection_sha256
        ),
        "effective_policy_inventory_sha256": version.inventory_sha256,
        "effective_policy_inventory_source_set_sha256": (
            version.inventory_source_set_sha256
        ),
        "effective_policy_rule_universe_sha256": version.rule_universe_sha256,
    }
    for key, value in expected.items():
        if common[key] != value:
            raise CorpusBatchEvidenceContractError(
                f"batch manifest {key} differs from {version.schema}"
            )
    budget = common["solve_budget"]
    if (
        budget["solve_attempts_per_seed"] != SOLVE_ATTEMPTS_PER_BLOCK
        or budget["candidate_entry_budget"]
        != MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
        or budget["selected_entry_budget"] != SELECTED_ENTRY_BUDGET
        or tuple(common["source_receipts"]) != ("later_source_freeze",)
    ):
        raise CorpusBatchEvidenceContractError(
            f"batch dose/source roles differ from {version.schema}"
        )
    if tuple(TASK_WORLD_SOURCE_ROLES) != (
        "world_artifact_r0", "world_artifact_r1", "world_artifact_r2",
        "world_artifact_r3", "world_artifact_r4",
    ):
        raise CorpusBatchEvidenceContractError("world source roles differ")


def _batch_binding(
    manifest: Mapping[str, object], identity: Mapping[str, object]
) -> dict[str, object]:
    common = manifest["common_law"]
    return {
        "batch_id": manifest["batch_id"],
        "batch_manifest_identity": dict(identity),
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "challenger_parameter_set_ids": list(CHALLENGER_PARAMETER_SET_IDS),
        "common_law_sha256": manifest["common_law_sha256"],
        "effective_policy_classified_input_projection_sha256": common[
            "effective_policy_classified_input_projection_sha256"
        ],
        "effective_policy_inventory_identity": common[
            "effective_policy_inventory_identity"
        ],
        "effective_policy_inventory_schema": EXPECTED_INVENTORY_SCHEMA,
        "effective_policy_inventory_sha256": common[
            "effective_policy_inventory_sha256"
        ],
        "effective_policy_inventory_source_set_sha256": common[
            "effective_policy_inventory_source_set_sha256"
        ],
        "effective_policy_rule_universe_sha256": common[
            "effective_policy_rule_universe_sha256"
        ],
        "incumbent_parameter_set_id": INCUMBENT_PARAMETER_SET_ID,
        "parameter_schema_sha256": PARAMETER_SCHEMA_SHA256,
        "parameter_sets": [{
            "ordinal": row["ordinal"],
            "parameter_set_id": row["parameter_set_id"],
            "parameter_set_sha256": row["parameter_set_sha256"],
            "values": row["values"],
        } for row in manifest["parameter_sets"]],
        "task_lattice": [{
            "season": task["season"],
            "slate_id": task["slate_id"],
            "task_index": task["task_index"],
            "task_sha256": task["task_sha256"],
            "week": task["week"],
            "world_artifact_receipt_set_sha256": task[
                "world_artifact_receipt_set_sha256"
            ],
        } for task in manifest["tasks"]],
    }


def _build_corpus_batch_evidence_contract(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
    version: _EvidenceContractVersion,
) -> dict[str, object]:
    """Build the deterministic create-once preregistration for one batch."""
    manifest = validate_batch_manifest(batch_manifest)
    _validate_foundation_identity(manifest, version)
    identity = validate_json_identity(
        manifest,
        batch_manifest_identity,
        label="evidence contract batch manifest identity",
    )
    if identity["uri"] != manifest["manifest_uri"]:
        raise CorpusBatchEvidenceContractError(
            "batch manifest identity URI differs from manifest URI"
        )
    endpoints = endpoint_registry()
    gates = _pre_outcome_gates()
    task_count = len(manifest["tasks"])
    contract_uri = (
        f"{manifest['output_prefix']}governance/pre-run-evidence-contract.json"
    )
    body: dict[str, object] = {
        "authority_transition_law": {
            "contract_decision_authority": False,
            "outcome_blind_completion_decision_authority": False,
            "realized_completion_may_set_decision_authority": True,
            "realized_decision_authority_scope": (
                "select-zero-or-one-default-off-2026-shadow-nominee-only"
            ),
            "separately_governed_realized_completion_required": True,
        },
        "batch_binding": _batch_binding(manifest, identity),
        "contract_id": (
            f"contract:corpus-parametric:{manifest['batch_id']}:"
            f"{version.contract_suffix}"
        ),
        "contract_phase": CONTRACT_PHASE,
        "contract_uri": contract_uri,
        "decision_authority": False,
        "endpoint_registry": endpoints,
        "graph_extension_topology": _graph_topology(
            task_count, endpoints, gates
        ),
        "historical_decision_law": _historical_decision_law(task_count),
        "knowledge_class": KNOWLEDGE_CLASS,
        "license_state_machine": _license_state_machine(),
        "missing_pre_run_artifacts": _missing_pre_run_artifacts(),
        "mutation_law": {
            "endpoint_addition_after_freeze": "forbidden",
            "endpoint_formula_or_direction_change_after_freeze": "forbidden",
            "gate_addition_removal_or_threshold_change_after_freeze": "forbidden",
            "losing_or_failed_arm_removal": "forbidden",
            "post_outcome_rehash_or_replacement": "forbidden",
            "repair_after_partial_outcome_body": "new_protocol_and_new_outcomes_required",
            "worker_graph_mutation": "forbidden",
        },
        "pre_outcome_gate_registry": gates,
        "pre_run_artifact_readiness": {
            "historical_outcome_read_ready": False,
            "missing_role_count": len(_missing_pre_run_artifacts()),
            "reason": (
                "the score-free batch foundation does not yet bind every "
                "historical decision and prospective-shadow authority"
            ),
        },
        "publication_mode": PUBLICATION_MODE,
        "reporting_law": {
            "all_seven_outcome_blind_rows_required": True,
            "all_seven_realized_rows_required_if_outcomes_are_read": True,
            "challenger_comparison_count": 6,
            "common_control": INCUMBENT_PARAMETER_SET_ID,
            "complete_winner_loser_table_required": True,
            "failed_tied_losing_or_ineligible_arms_reported": True,
            "parameter_set_order": list(PARAMETER_SET_ORDER),
            "partial_result_inspection": "forbidden",
            "winner_or_nominee_only_output": "forbidden",
        },
        "schema_version": version.schema,
        "uses_realized_outcomes": False,
    }
    body["evidence_contract_sha256"] = canonical_sha256(body)
    return body


def build_corpus_batch_evidence_contract(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build the immutable historical v1 evidence contract."""
    return _build_corpus_batch_evidence_contract(
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
        version=_V1_CONTRACT,
    )


def build_corpus_batch_evidence_contract_v2(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build the future v2 contract bound to source inventory v6."""
    return _build_corpus_batch_evidence_contract(
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
        version=_V2_CONTRACT,
    )


def validate_corpus_batch_evidence_contract(
    value: object,
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Rebuild from the batch and require exact type-sensitive equality."""
    if not isinstance(value, Mapping):
        raise CorpusBatchEvidenceContractError("evidence contract must be an object")
    schema = value.get("schema_version")
    if schema == SCHEMA:
        builder = build_corpus_batch_evidence_contract
    elif schema == V2_SCHEMA:
        builder = build_corpus_batch_evidence_contract_v2
    else:
        raise CorpusBatchEvidenceContractError(
            "evidence contract schema version is unsupported"
        )
    expected = builder(
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
    )
    if set(value) != set(expected):
        raise CorpusBatchEvidenceContractError(
            "evidence contract top-level keys differ"
        )
    retained_hash = value.get("evidence_contract_sha256")
    if type(retained_hash) is not str:
        raise CorpusBatchEvidenceContractError(
            "evidence contract SHA-256 must be a string"
        )
    unhashed = {
        key: value[key] for key in value if key != "evidence_contract_sha256"
    }
    if canonical_sha256(unhashed) != retained_hash:
        raise CorpusBatchEvidenceContractError(
            "evidence contract self-hash differs"
        )
    try:
        actual_bytes = canonical_json_bytes(dict(value))
        expected_bytes = canonical_json_bytes(expected)
    except Exception as exc:
        raise CorpusBatchEvidenceContractError(
            "evidence contract is not canonical JSON"
        ) from exc
    if actual_bytes != expected_bytes:
        raise CorpusBatchEvidenceContractError(
            "evidence contract differs from the frozen preregistration"
        )
    return expected


def validate_corpus_batch_evidence_contract_bytes(
    raw: bytes,
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Strict-load canonical retained bytes and replay the full contract."""
    try:
        parsed = parse_canonical_json_bytes(raw, label="batch evidence contract")
    except Exception as exc:
        raise CorpusBatchEvidenceContractError(
            "retained evidence contract bytes are invalid"
        ) from exc
    return validate_corpus_batch_evidence_contract(
        parsed,
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
    )


def validate_corpus_batch_evidence_contract_identity(
    value: object,
    identity: object,
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Validate the body plus its deterministic generation-pinned object URI."""
    contract = validate_corpus_batch_evidence_contract(
        value,
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
    )
    normalized = normalize_object_identity(
        identity, label="batch evidence contract identity"
    )
    validate_json_identity(
        contract, normalized, label="batch evidence contract identity"
    )
    if normalized["uri"] != contract["contract_uri"]:
        raise CorpusBatchEvidenceContractError(
            "evidence contract object URI differs from deterministic path"
        )
    return normalized


__all__ = [
    "CHALLENGER_PARAMETER_SET_IDS",
    "CorpusBatchEvidenceContractError",
    "INCUMBENT_PARAMETER_SET_ID",
    "PAIRED_TEST_LAW",
    "SCHEMA",
    "V2_SCHEMA",
    "THRESHOLDS_DK",
    "build_corpus_batch_evidence_contract",
    "build_corpus_batch_evidence_contract_v2",
    "endpoint_registry",
    "validate_corpus_batch_evidence_contract",
    "validate_corpus_batch_evidence_contract_bytes",
    "validate_corpus_batch_evidence_contract_identity",
]
