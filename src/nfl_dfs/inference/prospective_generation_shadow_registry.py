"""Frozen registry for the 2026 prospective generation shadows.

This module is deliberately data-only.  It neither constructs lineups nor
grades them.  The registry preserves the required, exploratory, unequal-
resource, unpassed, and closed roles so that a later runner cannot silently
tune the prospective family or promote a diagnostic contrast.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from types import MappingProxyType
from typing import Final

from .generation_exposure import canonical_sha256


SCHEMA_VERSION: Final = "prospective-generation-shadow-registry/v6"


class ShadowRegistryError(ValueError):
    """The prospective shadow registry differs from its frozen contract."""


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_thaw(v) for v in value]
    return value


_PAYLOAD: Final[dict[str, object]] = {
    "schema_version": SCHEMA_VERSION,
    "registry_id": "2026-prelock-generation-shadows-v1",
    "scope": {
        "universal_construction_law": "draftkings-legality-only",
        "shadow_construction_preset": "incumbent-gpp-construction",
        "shadow_construction_note": (
            "These comparative shadows deliberately retain the incumbent GPP "
            "construction; their house rules are not universal architecture laws."
        ),
        "outcome_free_until_lock": True,
        "report_every_arm_including_losers": True,
        "historical_effects_are_not_live_expectations": True,
        "all_five_arms_required_before_week1": True,
        "arm_omission_allowed": False,
    },
    "shared_protocol": {
        "operational_k": 80,
        "prefixes": [20, 40, 80],
        "coverage_threshold": 194,
        "tail_thresholds": [194, 200, 210, 220, 230, 240],
        "allocation_unit": "per-r0-r4-10000-world-block",
        "generation_blocks_per_slate": 5,
        "requested_core_solves_per_equal-budget-block": 200,
        "requested_role_solves_per_block": 12,
        "shared_simulation_bank": True,
        "shared_selection_bank": True,
        "independent_audit_world_bank_required": True,
        "independent_audit_world_seed": 2_026_083_001,
        "independent_audit_world_count": 10_000,
        "selection_law": "coverage-194",
        "retrieval_crossing": {
            "status": "key-secondary-required",
            "decision_role": "key-secondary-mechanism",
            "primary_efficacy_rule_satisfaction_allowed": False,
            "promotion_equivalent_efficacy_allowed": False,
            "automatic_promotion_allowed": False,
            "populations": ["incumbent-160-40", "boom-first-40-160"],
            "retrievals": [
                "incumbent-coverage-194",
                "cap-4-prefix-then-fill",
            ],
            "same_frozen_pool_per_population": True,
            "adds_candidate_solves": False,
            "historical_crossing_is_descriptive_only": True,
            "prior": (
                "cap-4 was active but slightly adverse on the historical "
                "boom-first population; 2026 decides prospectively"
            ),
        },
        "freeze_before_lock": [
            "book",
            "candidate_pool",
            "solve_exposure_ledger",
            "world_bank_identity",
        ],
        "primary_endpoint": "paired-realized-weekly-maximum-at-k80",
        "secondary_endpoints": [
            "paired-realized-weekly-maximum-at-k20",
            "paired-realized-weekly-maximum-at-k40",
            "weeks-at-least-194",
            "weeks-at-least-200",
            "weeks-at-least-210",
            "weeks-at-least-220",
            "weeks-at-least-230",
            "weeks-at-least-240",
            "pool-oracle",
            "book-regret",
            "field-percentile-rank-duplicates-split-payout",
        ],
        "tail_guard": "predeclared-noninferiority-over-complete-threshold-surface",
        "contest_field_capture_is_prerequisite": True,
        "no_contest_ev_or-spend-allocation-without-complete-field": True,
        "no_within_arm_tuning": True,
        "variants_require_new_preregistration": True,
        "never_add_historical_arm_gains": True,
    },
    "arms": [
        {
            "arm_id": "incumbent-160-40",
            "role": "control",
            "status": "required",
            "scientific_status": "control",
            "decision_role": "primary-control-reference",
            "required_before_week1": True,
            "resource_class": "200-core-solves-per-block",
            "allocation_per_block": {"leverage": 160, "base_boom": 40, "cross_law_boom": 0, "role": 12},
            "allocation_per_slate_five_blocks": {"leverage": 800, "base_boom": 200, "cross_law_boom": 0, "role": 60},
            "world_order": "incumbent",
            "selection_bank": "untouched-base-law",
            "passed_historical_nomination": True,
        },
        {
            "arm_id": "boom-first-40-160",
            "role": "primary-treatment",
            "status": "required",
            "scientific_status": "primary",
            "decision_role": "primary-efficacy-challenger",
            "required_before_week1": True,
            "resource_class": "200-core-solves-per-block",
            "allocation_per_block": {"leverage": 40, "base_boom": 160, "cross_law_boom": 0, "role": 12},
            "allocation_per_slate_five_blocks": {"leverage": 200, "base_boom": 800, "cross_law_boom": 0, "role": 60},
            "world_order": "incumbent",
            "selection_bank": "untouched-base-law",
            "passed_historical_nomination": True,
            "candidate_supply_transported": True,
            "selected_book_effect_established": False,
        },
        {
            "arm_id": "cross-law-40-100-60",
            "role": "exploratory-third-arm",
            "status": "required",
            "scientific_status": "exploratory",
            "decision_role": "diagnostic-only",
            "required_before_week1": True,
            "resource_class": "200-core-solves-per-block",
            "allocation_per_block": {"leverage": 40, "base_boom": 100, "cross_law_boom": 60, "role": 12},
            "allocation_per_slate_five_blocks": {"leverage": 200, "base_boom": 500, "cross_law_boom": 300, "role": 60},
            "world_order": "cross-law-descending-total",
            "selection_bank": "untouched-base-law",
            "discovery_law": {
                "lam_lo": 0.0,
                "lam_hi": 1.0,
                "base": 0.5,
                "slope": 0.0,
                "lam_team": 0.7,
                "marginals_restored_by_rank_transport": True,
                "dst_untouched": True,
            },
            "passed_historical_nomination": True,
            "known_prefix_result": "k20-null",
        },
        {
            "arm_id": "boom-dose-40-360",
            "role": "unequal-resource-dose",
            "status": "required",
            "scientific_status": "unequal-resource",
            "decision_role": "diagnostic-only",
            "required_before_week1": True,
            "resource_class": "400-core-solves-per-block-unequal-resource",
            "allocation_per_block": {"leverage": 40, "base_boom": 360, "cross_law_boom": 0, "role": 12},
            "allocation_per_slate_five_blocks": {"leverage": 200, "base_boom": 1800, "cross_law_boom": 0, "role": 60},
            "world_order": "incumbent",
            "selection_bank": "untouched-base-law",
            "passed_historical_nomination": True,
            "must_not_be_compared_as_equal_compute": True,
        },
        {
            "arm_id": "ceiling-all-boom-0-200",
            "role": "unpassed-near-miss",
            "status": "required",
            "scientific_status": "unpassed",
            "decision_role": "diagnostic-only",
            "required_before_week1": True,
            "resource_class": "200-core-solves-per-block",
            "allocation_per_block": {"leverage": 0, "base_boom": 200, "cross_law_boom": 0, "role": 12},
            "allocation_per_slate_five_blocks": {"leverage": 0, "base_boom": 1000, "cross_law_boom": 0, "role": 60},
            "world_order": "legal-roster-ceiling",
            "selection_bank": "untouched-base-law",
            "passed_historical_nomination": False,
            "failure": "family-wise-lower-bound-minus-0.14",
        },
    ],
    "decision_rules": {
        "interim_horizon_weeks": 8,
        "interim_scope": "integrity-and-severe-harm-only-no-efficacy-promotion",
        "interim_rule": (
            "At exactly eight completed weeks review missing books, source gaps, "
            "illegal lineups, solve failures, extreme exposure or duplication, "
            "and the frozen catastrophic-score guard. Never promote for efficacy."
        ),
        "structural_horizon": "full-regular-season",
        "structural_rule": (
            "The full season is the first prospective efficacy estimate with "
            "uncertainty, not automatic adoption. Structural action executes the "
            "frozen historical-plus-2026 concordance contract below; any incomplete, "
            "unsafe, discordant, or statistically unresolved result continues "
            "accumulation into 2027."
        ),
        "structural_synthesis_contract": {
            "schema_version": (
                "prospective-generation-shadow-structural-synthesis/v1"
            ),
            "frozen_before_week1": True,
            "historical_evidence_role": (
                "already-observed-descriptive-directional-evidence-not-fresh-confirmation"
            ),
            "historical_evidence_identity": {
                "uri": (
                    "gs://nfl-predictions-503414-corpus-retrieval/research/"
                    "corpus-r6-boom-first-allocation/"
                    "20260829-boom-first-68873f42-git-v1/full-54/"
                    "descriptive-realized-grade.json"
                ),
                "generation": 1_788_045_886_595_896,
                "sha256": (
                    "3d92cd0ba1466b52a0bfa883e1c51efddbabf474800ba4516340cc4eb0bff23c"
                ),
                "bytes": 4_002_644,
            },
            "historical_internal_grade_sha256": (
                "eaba50ff60c12552c188a162de9858316967f2dc8d8ba8a430a9b14818a522a4"
            ),
            "historical_metrics": {
                "panel_slate_count": 54,
                "entry_count": 80,
                "control_arm": "incumbent-160-40",
                "challenger_arm": "boom-first-40-160",
                "control_selected_score_sum_micro": 9_613_260_000,
                "challenger_selected_score_sum_micro": 9_681_060_000,
                "selected_paired_delta_sum_micro": 67_800_000,
                "control_pool_oracle_sum_micro": 9_801_020_000,
                "challenger_pool_oracle_sum_micro": 9_983_360_000,
                "pool_oracle_paired_delta_sum_micro": 182_340_000,
                "control_selector_regret_sum_micro": 187_760_000,
                "challenger_selector_regret_sum_micro": 302_300_000,
                "selector_regret_paired_delta_sum_micro": 114_540_000,
                "challenger_win_count": 11,
                "control_win_count": 12,
                "tie_count": 31,
                "selected_threshold_hit_deltas": {
                    "194": None,
                    "200": 2,
                    "210": 2,
                    "220": 2,
                    "230": 0,
                    "240": None,
                },
                "unavailable_historical_thresholds": [194, 240],
                "season_2025_already_informed_descriptive_only": True,
            },
            "synthesis_method": (
                "directional-concordance-without-effect-pooling-or-gain-summing"
            ),
            "required_2026_evidence": {
                "complete_contiguous_regular_season_weeks": 18,
                "week8_integrity_gate_status": "pass",
                "primary_contrast": "boom-first-40-160-vs-incumbent-160-40",
                "entry_count": 80,
                "selected_mean_delta_at_least_preregistered_mpie": True,
                "selected_paired_95pct_interval_lower_strictly_positive": True,
                "selected_effect_direction_matches_historical": True,
                "pool_oracle_effect_direction_matches_historical": True,
                "preregistered_win_rate_194_and_tail_guards_pass": True,
            },
            "concordant_disposition": (
                "human-review-candidate-no-automatic-adoption"
            ),
            "fallback_disposition": (
                "continue-unchanged-accrual-into-2027"
            ),
            "historical_object_reopen_required_before_human_decision": True,
            "historical_object_read_during_weekly_grading": False,
            "effect_pooling_allowed": False,
            "historical_and_prospective_gain_summing_allowed": False,
            "automatic_adoption_allowed": False,
            "automatic_money_policy_change_allowed": False,
        },
        "minimum_practically_important_effect_required_before_week1": True,
        "catastrophic_score_guard_required_before_week1": True,
        "tail_noninferiority_guard_required_before_week1": True,
        "eight_week_efficacy_decision_forbidden": True,
        "full_season_positive_point_estimate_is_not_automatic_adoption": True,
        "week8_safety_contract": {
            "schema_version": (
                "prospective-generation-shadow-weekly-safety-receipt/v2"
            ),
            "receipt_weeks": [1, 2, 3, 4, 5, 6, 7, 8],
            "expected_arm_ids": [
                "incumbent-160-40",
                "boom-first-40-160",
                "cross-law-40-100-60",
                "boom-dose-40-360",
                "ceiling-all-boom-0-200",
            ],
            "expected_book_ids": [
                (
                    "incumbent-160-40::"
                    "incumbent-cbwu-coverage-194-k80"
                ),
                (
                    "incumbent-160-40::"
                    "cap4-production-ladder-prefix-then-fill-k80"
                ),
                (
                    "boom-first-40-160::"
                    "incumbent-cbwu-coverage-194-k80"
                ),
                (
                    "boom-first-40-160::"
                    "cap4-production-ladder-prefix-then-fill-k80"
                ),
                (
                    "cross-law-40-100-60::"
                    "incumbent-cbwu-coverage-194-k80"
                ),
                (
                    "boom-dose-40-360::"
                    "incumbent-cbwu-coverage-194-k80"
                ),
                (
                    "ceiling-all-boom-0-200::"
                    "incumbent-cbwu-coverage-194-k80"
                ),
            ],
            "expected_block_labels": ["R0", "R1", "R2", "R3", "R4"],
            "expected_prefix_sizes": [20, 40, 80],
            "required_source_maximum_age_seconds": {
                "paired-native-effective-construction-source-receipt": 172_800,
                "paired-native-effective-model-source-receipt": 172_800,
                "paired-native-effective-player-input-receipt": 172_800,
                "independent-audit-world-bank": 86_400,
                "shared-simulation-world-bank": 86_400,
                "untouched-selection-world-bank": 86_400,
            },
            "source_age_semantics": (
                "terminal-authority-seal-age-not-raw-upstream-source-age"
            ),
            "raw_upstream_source_freshness_claim_allowed": False,
            "required_evidence_authorities": [
                "book-inventory-audit",
                "source-freshness-audit",
                "lineup-legality-audit",
                "solve-terminal-audit",
                "book-exposure-audit",
                "job-execution-audit",
            ],
            "thresholds": {
                "maximum_missing_terminal_count": 0,
                "maximum_missing_suite_manifest_count": 0,
                "maximum_missing_expected_arm_count": 0,
                "maximum_missing_expected_book_count": 0,
                "maximum_missing_expected_block_count": 0,
                "maximum_missing_expected_prefix_count": 0,
                "maximum_missing_required_source_count": 0,
                "maximum_stale_required_source_count": 0,
                "maximum_missing_evidence_authority_count": 0,
                "maximum_illegal_lineup_count": 0,
                "maximum_solve_failure_count": 0,
                "maximum_solve_request_shortfall_count": 0,
                "maximum_exposure_violation_count": 0,
                "maximum_duplicate_lineup_count": 0,
                "maximum_player_book_exposure_bps": 9_000,
            },
            "solve_failure_statuses": ["error", "exhausted", "infeasible"],
            "duplicate_lineup_scope": "within-each-book",
            "player_exposure_scope": (
                "within-each-book-player-appearances-divided-by-book-size"
            ),
            "terminal_may_be_absent_to_record_failed_run": True,
            "suite_manifest_may_be_absent_to_record_failed_run": True,
            "all_evidence_authorities_exact_reopened": True,
            "missing_receipt_status": "not_evaluated",
            "complete_receipt_set_required_for_pass": True,
            "integrity_pass_required_for_full_season_efficacy_rule": True,
            "efficacy_or_promotion_allowed": False,
        },
        "frozen_hierarchy": [
            "primary-boom-first-vs-incumbent-under-incumbent-retrieval",
            "key-secondary-generation-by-retrieval-crossing",
            "exploratory-cross-law-discovery-vs-boom-first",
            "required-unpassed-ceiling-all-boom-diagnostic-vs-boom-first",
            "required-unequal-resource-boom-dose-diagnostic-vs-boom-first",
        ],
        "all_five_arms_required_before_week1": True,
        "arm_omission_allowed": False,
        "contrast_decision_roles": {
            "boom-first-40-160": {
                "challenger_arm": "boom-first-40-160",
                "comparator_arm": "incumbent-160-40",
                "scientific_status": "primary",
                "decision_role": "primary-efficacy-rule",
                "numeric_diagnostic_criteria_reported": True,
                "primary_efficacy_rule_satisfaction_allowed": True,
                "promotion_equivalent_efficacy_allowed": True,
                "automatic_promotion_allowed": False,
            },
            "cross-law-40-100-60": {
                "challenger_arm": "cross-law-40-100-60",
                "comparator_arm": "boom-first-40-160",
                "scientific_status": "exploratory",
                "decision_role": "diagnostic-only",
                "numeric_diagnostic_criteria_reported": True,
                "primary_efficacy_rule_satisfaction_allowed": False,
                "promotion_equivalent_efficacy_allowed": False,
                "automatic_promotion_allowed": False,
            },
            "boom-dose-40-360": {
                "challenger_arm": "boom-dose-40-360",
                "comparator_arm": "boom-first-40-160",
                "scientific_status": "unequal-resource",
                "decision_role": "diagnostic-only",
                "numeric_diagnostic_criteria_reported": True,
                "primary_efficacy_rule_satisfaction_allowed": False,
                "promotion_equivalent_efficacy_allowed": False,
                "automatic_promotion_allowed": False,
            },
            "ceiling-all-boom-0-200": {
                "challenger_arm": "ceiling-all-boom-0-200",
                "comparator_arm": "boom-first-40-160",
                "scientific_status": "unpassed",
                "decision_role": "diagnostic-only",
                "numeric_diagnostic_criteria_reported": True,
                "primary_efficacy_rule_satisfaction_allowed": False,
                "promotion_equivalent_efficacy_allowed": False,
                "automatic_promotion_allowed": False,
            },
        },
        "nonprimary_contrasts_are_diagnostic_only": True,
        "no_midstream_dose_order_selector_tuning": True,
    },
    # These names exclude only the exact historical implementations that were
    # run.  They are not family-level claims that every future generator or
    # dependence model with a similar label has been disproved.
    "exact_tested_implementation_exclusions": [
        "small-book-selectors-cov210-q97-expected-max-overlay-k-le-40",
        "k80-q98.75-selector",
        "k80-expected-max-selector",
        "factor-stress-robust-selection",
        "historical-gamma-4-first-result-on-boom-first-population-not-live-authority",
        "quality-diverse-second-best-archive",
        "hand-designed-scenario-covering-array",
        "ceiling-or-30k-extreme-retention-without-new-law",
        "shootout-overlays",
        "dst-anticorrelation-law",
        "residual-columns",
        "larger-selection-bank",
        "late-swap-recourse",
        "sleeves",
        "historical-overlap-caps-or-ladders-exact-implementations-other-than-frozen-2026-crossing",
        "breakout-marginals",
        "analog-copulas",
    ],
    "explicit_nonclosures": [
        "gflownet-generators",
        "sequential-monte-carlo-generators",
        "mode-balancing-generators",
        "model-parliament-with-genuinely-disagreeing-candidate-laws",
        "underlying-dependence-deficiency",
    ],
    "findings_and_laws": {
        "market_blend": {
            "directive": "retain-common-lock-prop-market-mean",
            "evidence_scope": "36-covered-slates-2023-2024",
            "historical_drop_cost_at_k100": -2.2,
            "not_paid_data_valuation": True,
        },
        "house_rules": {
            "historical_equal-solve_effect": 3.6,
            "evidence_scope": "lev-first-allocation-reference-cell-only",
            "rules": ["qb-plus-2", "bring-back", "rb-dst-ban", "same-team-rb-ban", "salary-floor-49000"],
            "legality_only_requires_direct_prospective_test": True,
        },
        "calibration": {
            "simulated_tail_overstatement_range": [1.5, 2.0],
            "leverage_roster_tail_overstatement": 2.8,
            "line_194_label": "optimistic-194",
            "simulated_probability_is_not_calibrated": True,
        },
        "cross_seed": {
            "no_repeatable_ensemble_size_advantage": True,
            "required_test": "crossed-fit-seed-by-world-seed",
            "candidate_turnover_matches_reseed": True,
        },
        "population_by_cap": {
            "gamma4_is_population_specific": True,
            "historical_positive-result_only_on-sieved-eight-book-union": True,
            "prospective_cross_on-exact-frozen-control-and-boom-first-pools": True,
            "prefix_exhaustion_does_not-measure-cap-engagement": True,
            "never_add-to-boom-first-gain": True,
        },
        "contest_capture": {
            "allocation_model_not_identified": True,
            "required_fields": [
                "contest-identity", "field-size", "entry-fee", "payout-table",
                "field-rosters", "realized-scores", "ranks", "duplicate-counts",
                "split-payouts", "field-ownership", "participant-strength",
                "shadow-to-entered-lineup-map"
            ],
            "capture_is_mandatory": True,
            "no_spending_decision_before_capture": True,
            "raw-score-only-if-capture-incomplete": True,
        },
        "paid_sources": {
            "publication-is-not-evidence-of-value": True,
            "required_outcome_free_trace": [
                "availability", "staleness", "missingness",
                "served-feature-changes", "marginal-changes",
                "candidate-turnover", "selected-book-turnover"
            ],
            "value_claim_requires-frozen-source-on-off-ablation": True,
        },
        "non_additivity": {
            "historical_gains_must_not_be_summed": True,
            "every_composition_is-a-new-arm": True,
            "cross-law-only-measured-on-top-of-boom-first": True,
            "unequal-resource-dose-is-not-an-equal-budget-effect": True,
        },
    },
}

REGISTRY_SHA256: Final = canonical_sha256(_PAYLOAD)
FROZEN_REGISTRY: Final = _freeze({**_PAYLOAD, "registry_sha256": REGISTRY_SHA256})


def registry_document() -> dict[str, object]:
    """Return an independent JSON-compatible copy of the frozen registry."""

    return deepcopy(_thaw(FROZEN_REGISTRY))  # type: ignore[return-value]


def validate_registry(value: object) -> dict[str, object]:
    """Strictly validate and return a detached canonical registry document."""

    if not isinstance(value, Mapping):
        raise ShadowRegistryError("registry must be a mapping")
    candidate = _thaw(value)
    if not isinstance(candidate, dict):
        raise ShadowRegistryError("registry must be a JSON object")
    expected = registry_document()
    if candidate != expected:
        raise ShadowRegistryError("registry differs from the frozen prospective contract")
    retained = candidate.get("registry_sha256")
    payload = dict(candidate)
    payload.pop("registry_sha256", None)
    if retained != REGISTRY_SHA256 or canonical_sha256(payload) != retained:
        raise ShadowRegistryError("registry hash differs")
    return deepcopy(candidate)


validate_registry(FROZEN_REGISTRY)
