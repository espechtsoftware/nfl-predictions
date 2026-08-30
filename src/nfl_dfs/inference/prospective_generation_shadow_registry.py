"""Frozen registry for the 2026 prospective generation shadows.

This module is deliberately data-only.  It neither constructs lineups nor
grades them.  The registry preserves the nominated, optional, and closed arms
so that a later runner cannot silently tune the prospective family.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from types import MappingProxyType
from typing import Final

from .generation_exposure import canonical_sha256


SCHEMA_VERSION: Final = "prospective-generation-shadow-registry/v2"


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
            "role": "nominated-third-arm",
            "status": "required",
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
            "role": "optional-dose",
            "status": "optional-resource-permitting",
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
            "role": "optional-near-miss",
            "status": "optional-frozen-before-week1-or-omitted",
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
            "uncertainty, not automatic adoption. Structural action uses a "
            "predeclared synthesis with the historical matched result or continues "
            "accumulation into 2027."
        ),
        "minimum_practically_important_effect_required_before_week1": True,
        "catastrophic_score_guard_required_before_week1": True,
        "tail_noninferiority_guard_required_before_week1": True,
        "eight_week_efficacy_decision_forbidden": True,
        "full_season_positive_point_estimate_is_not_automatic_adoption": True,
        "frozen_hierarchy": [
            "primary-boom-first-vs-incumbent-under-incumbent-retrieval",
            "key-secondary-generation-by-retrieval-crossing",
            "exploratory-cross-law-discovery-vs-boom-first",
            "optional-unpassed-ceiling-all-boom-vs-boom-first",
            "lower-separate-unequal-compute-boom-dose",
        ],
        "optional_arms_are_separate_contrasts": True,
        "no_midstream_dose_order_selector_tuning": True,
    },
    "closed_arm_exclusions": [
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
