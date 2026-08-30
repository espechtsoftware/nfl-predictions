"""Prospective generation-shadow freeze, grade, and evaluation contract.

This module is deliberately split at the outcome boundary:

* score-blind builders and validators seal one terminal, create-once,
  pre-lock root for all declared generation arms;
* :func:`grade_realized_week_v1` accepts only that terminal root and one
  independently produced outcome snapshot; and
* :func:`evaluate_prospective_shadow_v1` aggregates the already paired weekly
  grades under the decision rule registered before Week 1.

The contract is intentionally narrow.  It is not a lineup generator, an
outcome supplier, or an adoption switch.  It makes omissions, bank drift,
solve-exposure gaps, prefix rewrites, and post-lock mutation fail closed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from typing import Final

from . import generation_exposure as exposure
from .prospective_boom_first import (
    native_input_source_projection,
    validate_paired_native_input_authority,
)
from .prospective_cross_law_supply_trace import (
    validate_selected_supply_trace,
)
from .prospective_generation_shadow_registry import (
    registry_document,
    validate_registry,
)
from .prospective_generation_shadow_suite import (
    AUDIT_BANK_SCHEMA,
    validate_independent_audit_input_binding,
)


PREREGISTRATION_SCHEMA: Final = (
    "prospective-generation-shadow-preregistration/v6"
)
SEED_CROSSING_SCHEMA: Final = (
    "prospective-generation-shadow-fit-world-crossing/v2"
)
ARM_FREEZE_SCHEMA: Final = "prospective-generation-shadow-arm-freeze/v3"
TERMINAL_PRELOCK_ROOT_SCHEMA: Final = (
    "prospective-generation-shadow-terminal-prelock-root/v2"
)
TERMINAL_PRELOCK_ENVELOPE_SCHEMA: Final = (
    "prospective-generation-shadow-terminal-prelock-envelope/v2"
)
SUITE_AUTHORITY_SCHEMA: Final = (
    "prospective-generation-shadow-suite-authority/v2"
)
SUITE_MANIFEST_SCHEMA: Final = "prospective-generation-shadow-manifest/v2"
SUITE_TERMINAL_SCHEMA: Final = "prospective-generation-shadow-terminal/v2"
SUITE_PRELOCK_RECEIPT_SCHEMA: Final = (
    "prospective-generation-multiarm-prelock/v2"
)
OUTCOME_SNAPSHOT_SCHEMA: Final = (
    "prospective-generation-shadow-independent-outcome-snapshot/v2"
)
REALIZED_SCORE_SOURCE_SCHEMA: Final = (
    "prospective-generation-shadow-independent-lineup-scores/v1"
)
WEEKLY_GRADE_SCHEMA: Final = (
    "prospective-generation-shadow-realized-weekly-grade/v3"
)
EVALUATION_SCHEMA: Final = (
    "prospective-generation-shadow-prospective-evaluation/v6"
)
WEEKLY_SAFETY_RECEIPT_SCHEMA: Final = (
    "prospective-generation-shadow-weekly-safety-receipt/v2"
)
SEASON: Final = 2026
_REGISTRY: Final = validate_registry(registry_document())
_WEEK8_SAFETY_RULE: Final = deepcopy(
    _REGISTRY["decision_rules"]["week8_safety_contract"]
)
_STRUCTURAL_SYNTHESIS_RULE: Final = deepcopy(
    _REGISTRY["decision_rules"]["structural_synthesis_contract"]
)
ARM_ORDER: Final = tuple(
    str(arm["arm_id"]) for arm in _REGISTRY["arms"]
)
_ARM_RELEASE_CONTRACT_BY_ID: Final = {
    str(arm["arm_id"]): {
        "arm_status": str(arm["status"]),
        "scientific_status": str(arm["scientific_status"]),
        "decision_role": str(arm["decision_role"]),
        "required_before_week1": bool(arm["required_before_week1"]),
    }
    for arm in _REGISTRY["arms"]
}
_CONTRAST_DECISION_ROLES: Final = deepcopy(
    _REGISTRY["decision_rules"]["contrast_decision_roles"]
)
_RETRIEVAL_DECISION_ROLE: Final = {
    key: _REGISTRY["shared_protocol"]["retrieval_crossing"][key]
    for key in (
        "decision_role",
        "primary_efficacy_rule_satisfaction_allowed",
        "promotion_equivalent_efficacy_allowed",
        "automatic_promotion_allowed",
    )
}
PREFIX_SIZES: Final = (20, 40, 80)
REALIZED_THRESHOLDS_DK: Final = (194, 200, 210, 220, 230, 240)
CALIBRATION_THRESHOLDS_DK: Final = (194, 210, 220)
INTERIM_WEEK_COUNT: Final = 8
FULL_SEASON_WEEK_COUNT: Final = 18
PROBABILITY_SCALE: Final = 1_000_000

COMPARATOR_BY_ARM: Final = {
    "boom-first-40-160": "incumbent-160-40",
    "cross-law-40-100-60": "boom-first-40-160",
    "boom-dose-40-360": "boom-first-40-160",
    "ceiling-all-boom-0-200": "boom-first-40-160",
}

_BASE_SELECTION_LAW: Final = "untouched-shared-base-law-selection-v1"
_BLOCK_LABELS: Final = ("R0", "R1", "R2", "R3", "R4")
_RETRIEVAL_CROSSING_ARMS: Final = (
    "incumbent-160-40", "boom-first-40-160",
)
_BASE_RETRIEVAL_ID: Final = "incumbent-cbwu-coverage-194-k80"
_CAP4_RETRIEVAL_ID: Final = (
    "cap4-production-ladder-prefix-then-fill-k80"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}\Z")

_POLICY_BY_ARM: Final = {
    "incumbent-160-40": {
        "policy_id": "current-allocation-control-160lev-40boom-v1",
        "required_requests_by_family": {
            "boom": 40,
            "leverage": 160,
            "role_epistemic": 12,
        },
        "core_requested_solve_count": 200,
        "resource_class": "200-solves",
        "arm_status": "required",
        "scientific_status": "control",
        "decision_role": "primary-control-reference",
        "required_before_week1": True,
        "resource_caveat": "equal-resource-control",
        "equal_compute_comparison": True,
        "generation_bank_role": "shared-base-generation-bank",
        "world_visit_order": "production-order",
        "discovery_overlay": None,
        "marginals_restored_by_rank_transport": False,
        "historical_status": "incumbent-control",
    },
    "boom-first-40-160": {
        "policy_id": "boom-first-40lev-160boom-v1",
        "required_requests_by_family": {
            "boom": 160,
            "leverage": 40,
            "role_epistemic": 12,
        },
        "core_requested_solve_count": 200,
        "resource_class": "200-solves",
        "arm_status": "required",
        "scientific_status": "primary",
        "decision_role": "primary-efficacy-challenger",
        "required_before_week1": True,
        "resource_caveat": "equal-resource-primary-treatment",
        "equal_compute_comparison": True,
        "generation_bank_role": "shared-base-generation-bank",
        "world_visit_order": "production-order",
        "discovery_overlay": None,
        "marginals_restored_by_rank_transport": False,
        "historical_status": "primary-prospective-shadow",
    },
    "cross-law-40-100-60": {
        "policy_id": "boom-first-cross-law-discovery-60-of-160-v1",
        "required_requests_by_family": {
            "boom": 100,
            "cross_law_boom": 60,
            "leverage": 40,
            "role_epistemic": 12,
        },
        "core_requested_solve_count": 200,
        "resource_class": "200-solves",
        "arm_status": "required",
        "scientific_status": "exploratory",
        "decision_role": "diagnostic-only",
        "required_before_week1": True,
        "resource_caveat": "equal-resource-nominated-third-arm",
        "equal_compute_comparison": True,
        "generation_bank_role": "generation-only-discovery-overlay",
        "world_visit_order": "descending-total",
        "discovery_overlay": {
            "base": 0.5,
            "lam_hi": 1.0,
            "lam_lo": 0.0,
            "lam_team": 0.7,
            "slope": 0.0,
        },
        "marginals_restored_by_rank_transport": True,
        "historical_status": "nominated-third-arm",
    },
    "boom-dose-40-360": {
        "policy_id": "required-boom-dose-40lev-360boom-v1",
        "required_requests_by_family": {
            "boom": 360,
            "leverage": 40,
            "role_epistemic": 12,
        },
        "core_requested_solve_count": 400,
        "resource_class": "400-solves-unequal-resource",
        "arm_status": "required",
        "scientific_status": "unequal-resource",
        "decision_role": "diagnostic-only",
        "required_before_week1": True,
        "resource_caveat": (
            "required-unequal-resource-dose-not-an-equal-compute-effect"
        ),
        "equal_compute_comparison": False,
        "generation_bank_role": "shared-base-generation-bank",
        "world_visit_order": "production-order",
        "discovery_overlay": None,
        "marginals_restored_by_rank_transport": False,
        "historical_status": "unequal-resource-boom360-diagnostic",
    },
    "ceiling-all-boom-0-200": {
        "policy_id": "all-boom-200-ceiling-ordered-v1",
        "required_requests_by_family": {"boom": 200, "role_epistemic": 12},
        "core_requested_solve_count": 200,
        "resource_class": "200-solves",
        "arm_status": "required",
        "scientific_status": "unpassed",
        "decision_role": "diagnostic-only",
        "required_before_week1": True,
        "resource_caveat": "required-unpassed-near-miss",
        "equal_compute_comparison": True,
        "generation_bank_role": "shared-base-generation-bank",
        "world_visit_order": "legal-roster-ceiling",
        "discovery_overlay": None,
        "marginals_restored_by_rank_transport": False,
        "historical_status": "unpassed-near-miss-diagnostic",
    },
}
if set(_POLICY_BY_ARM) != set(ARM_ORDER) or any(
    {
        key: _POLICY_BY_ARM[arm_id][key]
        for key in _ARM_RELEASE_CONTRACT_BY_ID[arm_id]
    }
    != _ARM_RELEASE_CONTRACT_BY_ID[arm_id]
    for arm_id in ARM_ORDER
):
    raise RuntimeError("generation policy decision roles differ from registry")


class ProspectiveGenerationShadowEvaluationError(ValueError):
    """A prelock freeze, realized grade, or evaluation failed closed."""


def _fail(message: str) -> None:
    raise ProspectiveGenerationShadowEvaluationError(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    """Use the shared exposure-ledger canonical JSON representation."""

    try:
        return exposure.canonical_json_bytes(value)
    except exposure.GenerationExposureError as exc:
        raise ProspectiveGenerationShadowEvaluationError(str(exc)) from exc


def canonical_sha256_v1(value: object) -> str:
    """Use the shared exposure-ledger canonical SHA-256 representation."""

    try:
        return exposure.canonical_sha256(value)
    except exposure.GenerationExposureError as exc:
        raise ProspectiveGenerationShadowEvaluationError(str(exc)) from exc


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, Sequence
    ):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        _fail(f"{label} must be a normalized identifier")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _signed_integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be an exact integer")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _canonical_timestamp(value: object, *, label: str) -> str:
    if isinstance(value, datetime):
        stamp = value
    elif type(value) is str:
        try:
            stamp = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ProspectiveGenerationShadowEvaluationError(
                f"{label} must be an ISO timestamp"
            ) from exc
    else:
        _fail(f"{label} must be an ISO timestamp")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    return stamp.astimezone(timezone.utc).isoformat()


def _parsed_timestamp(value: object, *, label: str) -> datetime:
    canonical = _canonical_timestamp(value, label=label)
    if type(value) is str and value != canonical:
        _fail(f"{label} is not in canonical UTC representation")
    return datetime.fromisoformat(canonical)


def normalize_object_identity_v1(
    value: object, *, label: str = "object identity"
) -> dict[str, object]:
    """Normalize the repository's representation-free content identity."""

    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = _string(item.get("uri"), label=f"{label} URI")
    if not uri.startswith("gs://") or uri.endswith("/") or "/" not in uri[5:]:
        _fail(f"{label} URI must name one exact GCS object")
    generation = _string(
        str(item.get("generation")), label=f"{label} generation"
    )
    if not generation.isdigit() or int(generation) < 1:
        _fail(f"{label} generation must be a positive decimal generation")
    digest = _digest(item.get("sha256"), label=f"{label} SHA-256")
    byte_count = _integer(item.get("bytes"), label=f"{label} bytes", minimum=1)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _reject_prelock_carrier_identity(
    identity: Mapping[str, object], *, label: str
) -> None:
    lowered_uri = str(identity["uri"]).lower()
    if any(
        carrier in lowered_uri
        for carrier in (
            "/actual", "/outcome", "/postlock", "/post-lock",
            "/standings", "/payout", "/settlement",
        )
    ):
        _fail(f"{label} URI is an outcome or post-lock carrier")


def _reject_prelock_carrier_fields(value: object, *, label: str) -> None:
    forbidden = {
        "actual", "actual_score", "realized_score", "realized_scores",
        "final_score", "actual_ownership", "contest_rank", "field_rank",
        "payout", "payouts", "roi", "outcomes", "outcome_rows",
        "postlock_rows", "post_lock_rows", "settlement", "standings",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower().replace("-", "_")
            if lowered in forbidden:
                _fail(f"{label} contains forbidden prelock carrier field {key}")
            _reject_prelock_carrier_fields(
                child, label=f"{label}.{key}"
            )
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for ordinal, child in enumerate(value):
            _reject_prelock_carrier_fields(
                child, label=f"{label}[{ordinal}]"
            )


def build_create_once_artifact_v1(
    *,
    identity: object,
    frozen_at: datetime | str,
    storage_created_at: datetime | str,
) -> dict[str, object]:
    """Build one prelock create-once artifact descriptor."""

    normalized = normalize_object_identity_v1(identity)
    _reject_prelock_carrier_identity(normalized, label="prelock artifact")
    frozen = _canonical_timestamp(frozen_at, label="artifact frozen-at")
    created = _canonical_timestamp(
        storage_created_at, label="artifact storage-created-at"
    )
    if datetime.fromisoformat(created) < datetime.fromisoformat(frozen):
        _fail("artifact storage creation precedes its frozen content")
    return {
        "identity": normalized,
        "create_once": True,
        "frozen_at": frozen,
        "storage_created_at": created,
        "storage_metadata_authority": "google-cloud-storage-object-metadata",
    }


def _validate_artifact(
    value: object, *, label: str, not_after: datetime
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {
        "identity", "create_once", "frozen_at", "storage_created_at",
        "storage_metadata_authority",
    }:
        _fail(f"{label} fields differ")
    frozen = _parsed_timestamp(item.get("frozen_at"), label=f"{label} frozen-at")
    created = _parsed_timestamp(
        item.get("storage_created_at"), label=f"{label} storage-created-at"
    )
    if item.get("create_once") is not True:
        _fail(f"{label} is not create-once")
    if frozen > not_after or created > not_after or created < frozen:
        _fail(f"{label} was frozen after the prelock boundary")
    if item.get("storage_metadata_authority") != (
        "google-cloud-storage-object-metadata"
    ):
        _fail(f"{label} lacks trusted storage metadata")
    identity = normalize_object_identity_v1(
        item.get("identity"), label=f"{label} identity"
    )
    _reject_prelock_carrier_identity(identity, label=label)
    return {
        "identity": identity,
        "create_once": True,
        "frozen_at": frozen.isoformat(),
        "storage_created_at": created.isoformat(),
        "storage_metadata_authority": "google-cloud-storage-object-metadata",
    }


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    body[field] = canonical_sha256_v1(body)
    return body


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _digest(value.get(field), label=f"{label} self-hash")
    body = {key: child for key, child in value.items() if key != field}
    if canonical_sha256_v1(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _validate_structural_synthesis_rule(
    value: object,
) -> dict[str, object]:
    rule = _mapping(value, label="structural synthesis rule")
    if rule != _STRUCTURAL_SYNTHESIS_RULE:
        _fail("structural synthesis rule differs from frozen registry")
    normalize_object_identity_v1(
        rule.get("historical_evidence_identity"),
        label="structural historical evidence identity",
    )
    _digest(
        rule.get("historical_internal_grade_sha256"),
        label="structural historical internal grade SHA",
    )
    metrics = _mapping(
        rule.get("historical_metrics"),
        label="structural historical metrics",
    )
    slate_count = _integer(
        metrics.get("panel_slate_count"),
        label="structural historical slate count",
        minimum=1,
    )
    for prefix in ("selected", "pool_oracle", "selector_regret"):
        control = _signed_integer(
            metrics.get(f"control_{prefix}_score_sum_micro")
            if prefix == "selected"
            else metrics.get(f"control_{prefix}_sum_micro"),
            label=f"historical control {prefix} sum",
        )
        challenger = _signed_integer(
            metrics.get(f"challenger_{prefix}_score_sum_micro")
            if prefix == "selected"
            else metrics.get(f"challenger_{prefix}_sum_micro"),
            label=f"historical challenger {prefix} sum",
        )
        delta = _signed_integer(
            metrics.get(f"{prefix}_paired_delta_sum_micro"),
            label=f"historical {prefix} paired delta sum",
        )
        if challenger - control != delta:
            _fail(f"historical {prefix} synthesis arithmetic differs")
    if sum(
        _integer(metrics.get(field), label=f"historical {field}")
        for field in ("challenger_win_count", "control_win_count", "tie_count")
    ) != slate_count:
        _fail("historical win/tie synthesis counts differ")
    thresholds = _mapping(
        metrics.get("selected_threshold_hit_deltas"),
        label="historical threshold-hit deltas",
    )
    if set(thresholds) != {str(value) for value in REALIZED_THRESHOLDS_DK}:
        _fail("historical synthesis threshold surface differs")
    if (
        metrics.get("unavailable_historical_thresholds") != [194, 240]
        or thresholds.get("194") is not None
        or thresholds.get("240") is not None
        or any(rule.get(field) is not False for field in (
            "historical_object_read_during_weekly_grading",
            "effect_pooling_allowed",
            "historical_and_prospective_gain_summing_allowed",
            "automatic_adoption_allowed",
            "automatic_money_policy_change_allowed",
        ))
    ):
        _fail("structural synthesis non-adoption or missing-data law differs")
    return deepcopy(rule)


def build_preregistration_v1(
    *,
    registered_at: datetime | str,
    week1_lock_at: datetime | str,
    operational_k: int = 80,
    rule_id: str = "prospective-generation-family-rule-v1",
    minimum_paired_mean_delta_micro: int = 2_000_000,
    minimum_win_rate_bps: int = 5_000,
    minimum_194_hit_delta: int = 0,
    catastrophic_paired_delta_micro: int = -20_000_000,
    maximum_tail_hit_deficit: int = 0,
) -> dict[str, object]:
    """Freeze the family rule and both horizons before the Week-1 lock."""

    registered = _canonical_timestamp(registered_at, label="registered-at")
    week1_lock = _canonical_timestamp(week1_lock_at, label="Week-1 lock")
    if datetime.fromisoformat(registered) >= datetime.fromisoformat(week1_lock):
        _fail("preregistration must precede the Week-1 lock")
    k = _integer(operational_k, label="operational K", minimum=80)
    if k != 80:
        _fail("operational K must remain the preregistered production K80")
    mean_delta = _integer(
        minimum_paired_mean_delta_micro,
        label="minimum paired mean delta",
    )
    win_rate = _integer(minimum_win_rate_bps, label="minimum win rate")
    if win_rate > 10_000:
        _fail("minimum win rate exceeds 10,000 basis points")
    hit_delta = _integer(
        minimum_194_hit_delta, label="minimum 194-hit delta"
    )
    catastrophic = _signed_integer(
        catastrophic_paired_delta_micro,
        label="catastrophic paired-delta guard",
    )
    if catastrophic >= 0:
        _fail("catastrophic paired-delta guard must be adverse")
    tail_deficit = _integer(
        maximum_tail_hit_deficit, label="maximum tail-hit deficit"
    )
    reporting = sorted(set(PREFIX_SIZES) | {k})
    body: dict[str, object] = {
        "schema_version": PREREGISTRATION_SCHEMA,
        "season": SEASON,
        "registered_at": registered,
        "week1_lock_at": week1_lock,
        "registered_before_week1": True,
        "required_arm_order": list(ARM_ORDER),
        "all_five_arms_required_before_week1": True,
        "arm_omission_allowed": False,
        "operational_k": k,
        "required_prefix_sizes": list(PREFIX_SIZES),
        "reporting_entry_counts": reporting,
        "primary_endpoint": (
            "paired-realized-weekly-maximum-at-operational-k"
        ),
        "secondary_endpoints": [
            "paired-realized-prefix-maxima-k20-k40-k80",
            "weeks-at-least-194-200-210-220-230-240",
            "per-arm-pool-oracle-and-selector-regret",
            "complete-field-actual-and-counterfactual-rank-duplicates-payout",
            "cap-calibration-p-max-194-210-220",
        ],
        "paired_comparators": dict(COMPARATOR_BY_ARM),
        "arm_decision_roles": deepcopy(_ARM_RELEASE_CONTRACT_BY_ID),
        "contrast_decision_roles": deepcopy(_CONTRAST_DECISION_ROLES),
        "retrieval_decision_role": deepcopy(_RETRIEVAL_DECISION_ROLE),
        "interim_horizon": {
            "completed_weeks": INTERIM_WEEK_COUNT,
            "decision_scope": "integrity-and-severe-harm-only",
            "efficacy_or_promotion_allowed": False,
        },
        "structural_horizon": {
            "completed_weeks": FULL_SEASON_WEEK_COUNT,
            "decision_scope": "first-prospective-efficacy-estimate",
            "uncertainty_required": True,
            "automatic_adoption_allowed": False,
        },
        "structural_synthesis_rule": _validate_structural_synthesis_rule(
            _STRUCTURAL_SYNTHESIS_RULE
        ),
        "inference_unit": "slate-after-block-and-bank-aggregation",
        "generation_block_contract": {
            "shared_block_labels": ["R0", "R1", "R2", "R3", "R4"],
            "worlds_per_block": 10_000,
            "allocation_counts_are_per_block": True,
            "equal_budget_core_solves_per_arm_per_block": 200,
            "equal_budget_core_solves_per_arm_per_slate": 1_000,
            "role_12_and_other_frozen_families_unchanged_per_block": True,
            "selection_world_authority_shared": True,
            "independent_audit_world_bank_required": True,
        },
        "treatment_hierarchy": [
            "primary-boom-first-incumbent-retrieval-vs-incumbent-sentinel",
            "key-secondary-generation-x-retrieval-2x2",
            "exploratory-cross-law-on-boom-first-under-base-selection",
            "required-unpassed-ceiling-all-boom-diagnostic",
            "required-unequal-resource-boom360-diagnostic",
        ],
        "contest_field_capture_rule": {
            "complete-field-capture-required-for-contest-ev": True,
            "otherwise_evidence_scope": "raw-score-only-no-contest-ev",
            "allocation_recommendation_without-complete-field": False,
        },
        "family_level_decision_rule": {
            "rule_id": _identifier(rule_id, label="family rule ID"),
            "minimum_paired_mean_delta_micro": mean_delta,
            "minimum_win_rate_bps": win_rate,
            "minimum_194_hit_delta": hit_delta,
            "minimum_practically_important_effect_micro": mean_delta,
            "catastrophic_paired_delta_micro": catastrophic,
            "tail_noninferiority_thresholds_dk": [230, 240],
            "maximum_tail_hit_deficit": tail_deficit,
            "full_season_uncertainty_method": (
                "slate-level-paired-t-interval-95pct"
            ),
            "same_numeric_criteria_reported_for_every_predeclared_contrast": True,
            "primary_efficacy_rule_challenger_arm": "boom-first-40-160",
            "nonprimary_contrasts_diagnostic_only": True,
        },
        # This entire metric family is fixed in the pre-Week-1 object.  The
        # weekly receipt may truthfully report a missing suite terminal, so a
        # crashed/failed generation run cannot disappear merely because the
        # successful terminal path was never reached.
        "week8_safety_rule": deepcopy(_WEEK8_SAFETY_RULE),
        "one_family_level_rule": True,
        "within_shadow_tuning_allowed": False,
        "variant_requires_new_arm": True,
        "report_every_arm_every_week": True,
        "report_losses": True,
        "historical_gains_may_be_summed": False,
        "all_boom_required_status_disclosed_as_unpassed": True,
        "automatic_adoption": False,
    }
    return _with_hash(body, field="preregistration_sha256")


def validate_preregistration_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="shadow preregistration")
    fields = {
        "schema_version", "season", "registered_at", "week1_lock_at",
        "registered_before_week1", "required_arm_order", "operational_k",
        "all_five_arms_required_before_week1", "arm_omission_allowed",
        "required_prefix_sizes", "reporting_entry_counts",
        "primary_endpoint", "secondary_endpoints", "paired_comparators",
        "arm_decision_roles", "contrast_decision_roles",
        "retrieval_decision_role",
        "interim_horizon", "structural_horizon",
        "structural_synthesis_rule",
        "inference_unit", "generation_block_contract",
        "treatment_hierarchy", "contest_field_capture_rule",
        "family_level_decision_rule", "week8_safety_rule",
        "one_family_level_rule",
        "within_shadow_tuning_allowed", "variant_requires_new_arm",
        "report_every_arm_every_week", "report_losses",
        "historical_gains_may_be_summed",
        "all_boom_required_status_disclosed_as_unpassed",
        "automatic_adoption", "preregistration_sha256",
    }
    if set(item) != fields:
        _fail("shadow preregistration fields differ")
    _validate_self_hash(
        item, field="preregistration_sha256", label="shadow preregistration"
    )
    registered = _parsed_timestamp(item.get("registered_at"), label="registered-at")
    week1_lock = _parsed_timestamp(item.get("week1_lock_at"), label="Week-1 lock")
    k = _integer(item.get("operational_k"), label="operational K", minimum=80)
    if k != 80:
        _fail("operational K must remain the preregistered production K80")
    reporting = sorted(set(PREFIX_SIZES) | {k})
    expected_fixed = {
        "schema_version": PREREGISTRATION_SCHEMA,
        "season": SEASON,
        "registered_before_week1": True,
        "required_arm_order": list(ARM_ORDER),
        "all_five_arms_required_before_week1": True,
        "arm_omission_allowed": False,
        "required_prefix_sizes": list(PREFIX_SIZES),
        "reporting_entry_counts": reporting,
        "primary_endpoint": "paired-realized-weekly-maximum-at-operational-k",
        "paired_comparators": dict(COMPARATOR_BY_ARM),
        "arm_decision_roles": deepcopy(_ARM_RELEASE_CONTRACT_BY_ID),
        "contrast_decision_roles": deepcopy(_CONTRAST_DECISION_ROLES),
        "retrieval_decision_role": deepcopy(_RETRIEVAL_DECISION_ROLE),
        "one_family_level_rule": True,
        "within_shadow_tuning_allowed": False,
        "variant_requires_new_arm": True,
        "report_every_arm_every_week": True,
        "report_losses": True,
        "historical_gains_may_be_summed": False,
        "all_boom_required_status_disclosed_as_unpassed": True,
        "automatic_adoption": False,
        "inference_unit": "slate-after-block-and-bank-aggregation",
        "generation_block_contract": {
            "shared_block_labels": ["R0", "R1", "R2", "R3", "R4"],
            "worlds_per_block": 10_000,
            "allocation_counts_are_per_block": True,
            "equal_budget_core_solves_per_arm_per_block": 200,
            "equal_budget_core_solves_per_arm_per_slate": 1_000,
            "role_12_and_other_frozen_families_unchanged_per_block": True,
            "selection_world_authority_shared": True,
            "independent_audit_world_bank_required": True,
        },
        "treatment_hierarchy": [
            "primary-boom-first-incumbent-retrieval-vs-incumbent-sentinel",
            "key-secondary-generation-x-retrieval-2x2",
            "exploratory-cross-law-on-boom-first-under-base-selection",
            "required-unpassed-ceiling-all-boom-diagnostic",
            "required-unequal-resource-boom360-diagnostic",
        ],
        "contest_field_capture_rule": {
            "complete-field-capture-required-for-contest-ev": True,
            "otherwise_evidence_scope": "raw-score-only-no-contest-ev",
            "allocation_recommendation_without-complete-field": False,
        },
    }
    if any(item.get(key) != expected for key, expected in expected_fixed.items()):
        _fail("shadow preregistration fixed law differs")
    if item.get("week8_safety_rule") != _WEEK8_SAFETY_RULE:
        _fail("shadow preregistration Week-8 safety rule differs")
    _validate_structural_synthesis_rule(item.get("structural_synthesis_rule"))
    if registered >= week1_lock:
        _fail("shadow preregistration was not sealed before Week 1")
    if item.get("secondary_endpoints") != [
        "paired-realized-prefix-maxima-k20-k40-k80",
        "weeks-at-least-194-200-210-220-230-240",
        "per-arm-pool-oracle-and-selector-regret",
        "complete-field-actual-and-counterfactual-rank-duplicates-payout",
        "cap-calibration-p-max-194-210-220",
    ]:
        _fail("shadow preregistration secondary endpoints differ")
    if item.get("interim_horizon") != {
        "completed_weeks": INTERIM_WEEK_COUNT,
        "decision_scope": "integrity-and-severe-harm-only",
        "efficacy_or_promotion_allowed": False,
    } or item.get("structural_horizon") != {
        "completed_weeks": FULL_SEASON_WEEK_COUNT,
        "decision_scope": "first-prospective-efficacy-estimate",
        "uncertainty_required": True,
        "automatic_adoption_allowed": False,
    }:
        _fail("shadow preregistration horizons differ")
    rule = _mapping(
        item.get("family_level_decision_rule"), label="family decision rule"
    )
    if set(rule) != {
        "rule_id", "minimum_paired_mean_delta_micro",
        "minimum_win_rate_bps", "minimum_194_hit_delta",
        "minimum_practically_important_effect_micro",
        "catastrophic_paired_delta_micro",
        "tail_noninferiority_thresholds_dk", "maximum_tail_hit_deficit",
        "full_season_uncertainty_method",
        "same_numeric_criteria_reported_for_every_predeclared_contrast",
        "primary_efficacy_rule_challenger_arm",
        "nonprimary_contrasts_diagnostic_only",
    }:
        _fail("family decision rule fields differ")
    _identifier(rule.get("rule_id"), label="family rule ID")
    _integer(
        rule.get("minimum_paired_mean_delta_micro"),
        label="minimum paired mean delta",
    )
    win_rate = _integer(
        rule.get("minimum_win_rate_bps"), label="minimum win rate"
    )
    _integer(rule.get("minimum_194_hit_delta"), label="minimum 194-hit delta")
    if (
        rule.get("minimum_practically_important_effect_micro")
        != rule.get("minimum_paired_mean_delta_micro")
        or _signed_integer(
            rule.get("catastrophic_paired_delta_micro"),
            label="catastrophic paired-delta guard",
        ) >= 0
        or rule.get("tail_noninferiority_thresholds_dk") != [230, 240]
        or type(rule.get("maximum_tail_hit_deficit")) is not int
        or int(rule["maximum_tail_hit_deficit"]) < 0
        or rule.get("full_season_uncertainty_method")
        != "slate-level-paired-t-interval-95pct"
    ):
        _fail("family decision safety/uncertainty law differs")
    if (
        win_rate > 10_000
        or rule.get(
            "same_numeric_criteria_reported_for_every_predeclared_contrast"
        ) is not True
        or rule.get("primary_efficacy_rule_challenger_arm")
        != "boom-first-40-160"
        or rule.get("nonprimary_contrasts_diagnostic_only") is not True
    ):
        _fail("family decision rule fixed law differs")
    return item


def _safety_ledger_components(value: object, *, label: str) -> list[dict[str, object]]:
    block = _mapping(value, label=label)
    if set(block) == {"native", "transform"}:
        retained = [
            exposure.validate_ledger(block["native"]),
        ]
        if block["transform"] is not None:
            retained.append(exposure.validate_ledger(block["transform"]))
        return retained
    return [exposure.validate_ledger(block)]


def _derived_safety_terminal_authority_v2(
    *,
    root: Mapping[str, object],
    terminal_prelock_envelope_identity: Mapping[str, object],
    rule: Mapping[str, object],
    observed_at: str,
) -> dict[str, object]:
    """Derive every pass-capable safety fact from one validated terminal."""

    suite = _mapping(root["suite_authority"], label="safety suite authority")
    manifest = _mapping(suite["manifest"], label="safety suite manifest")
    prelock = _mapping(
        manifest["prelock_receipt"], label="safety suite prelock receipt"
    )
    expected_arms = [str(value) for value in rule["expected_arm_ids"]]
    expected_books = [str(value) for value in rule["expected_book_ids"]]
    expected_blocks = [str(value) for value in rule["expected_block_labels"]]
    expected_prefixes = [int(value) for value in rule["expected_prefix_sizes"]]
    arms = [
        validate_arm_freeze_v1(value)
        for value in _sequence(root["arms"], label="safety terminal arms")
    ]
    arm_by_id = {str(arm["arm_id"]): arm for arm in arms}

    observed_arm_ids = sorted(arm_by_id)
    block_rows: list[dict[str, object]] = []
    for arm_id in expected_arms:
        arm = arm_by_id.get(arm_id)
        labels = [] if arm is None else sorted(
            _mapping(
                arm["exposure_ledgers_by_block"],
                label=f"safety {arm_id} ledger grid",
            )
        )
        block_rows.append({"arm_id": arm_id, "block_labels": labels})

    memberships = _mapping(
        prelock["memberships"], label="safety frozen memberships"
    )
    base_memberships = _mapping(
        memberships[str(PREFIX_SIZES[-1])],
        label="safety K80 frozen memberships",
    )
    bridge = _sequence(
        suite["player_identity_bridge"],
        label="safety player identity bridge",
    )
    player_by_dk_id: dict[str, dict[str, object]] = {}
    dk_id_by_internal_id: dict[str, str] = {}
    for ordinal, raw_player in enumerate(bridge):
        player = _mapping(raw_player, label=f"safety player bridge[{ordinal}]")
        dk_id = _string(
            player["dk_draftable_id"], label="safety DK draftable ID"
        )
        internal_id = _string(
            player["internal_player_id"], label="safety internal player ID"
        )
        player_by_dk_id[dk_id] = player
        dk_id_by_internal_id[internal_id] = dk_id

    # Candidate IDs are hashes of DK-draftable roster membership.  Native
    # ledgers retain internal IDs, so exact reconstruction goes through the
    # frozen player bridge instead of trusting a caller-supplied roster audit.
    roster_by_lineup_id: dict[str, list[str]] = {}
    solve_status_counts = {
        str(status): 0 for status in rule["solve_failure_statuses"]
    }
    solve_request_shortfall_count = 0
    solve_ledger_projection: list[dict[str, object]] = []
    for arm in arms:
        arm_id = str(arm["arm_id"])
        ledger_grid = _mapping(
            arm["exposure_ledgers_by_block"],
            label=f"safety {arm_id} ledgers",
        )
        for block_label in sorted(ledger_grid):
            components = _safety_ledger_components(
                ledger_grid[block_label],
                label=f"safety {arm_id}/{block_label} ledgers",
            )
            for component_ordinal, ledger in enumerate(components):
                expected_requests = sum(
                    int(value)
                    for value in ledger["expected_requests_by_family"].values()
                )
                request_keys = {
                    (str(row["family"]), int(row["requested_ordinal"]))
                    for row in ledger["rows"]
                }
                solve_request_shortfall_count += max(
                    0, expected_requests - len(request_keys)
                )
                for status in solve_status_counts:
                    solve_status_counts[status] += int(
                        ledger["status_counts"][status]
                    )
                solve_ledger_projection.append({
                    "arm_id": arm_id,
                    "block_label": block_label,
                    "component_ordinal": component_ordinal,
                    "ledger_sha256": ledger["ledger_sha256"],
                    "expected_request_count": expected_requests,
                    "observed_request_count": len(request_keys),
                    "status_counts": dict(ledger["status_counts"]),
                })
                for row in ledger["rows"]:
                    raw_roster = row["player_ids"]
                    if raw_roster is None:
                        continue
                    try:
                        translated = [
                            dk_id_by_internal_id[str(player_id)]
                            for player_id in raw_roster
                        ]
                        roster = list(
                            exposure.roster_identity(translated)["player_ids"]
                        )
                    except (KeyError, exposure.GenerationExposureError):
                        # This cannot validate a selected roster.  The later
                        # membership projection records it as unresolved and
                        # makes legality/exposure fail closed.
                        continue
                    lineup_id = f"lineup-v1-{canonical_sha256_v1(roster)}"
                    prior = roster_by_lineup_id.setdefault(lineup_id, roster)
                    if prior != roster:
                        _fail("safety ledger roster hash collision differs")

    book_by_id: dict[str, dict[str, object]] = {}
    unresolved_lineup_rows: list[dict[str, object]] = []
    for arm_id in expected_arms:
        arm = arm_by_id.get(arm_id)
        if arm is None:
            continue
        base_book_id = f"{arm_id}::{arm['base_retrieval_id']}"
        base_lineup_ids = [str(value) for value in arm["book_lineup_ids"]]
        base_rosters = [
            [str(player_id) for player_id in roster]
            for roster in _sequence(
                base_memberships[arm_id],
                label=f"safety {arm_id} base rosters",
            )
        ]
        if len(base_rosters) != len(base_lineup_ids) or any(
            lineup_id != f"lineup-v1-{canonical_sha256_v1(roster)}"
            for lineup_id, roster in zip(base_lineup_ids, base_rosters)
        ):
            _fail(f"safety {arm_id} base roster binding differs")
        book_by_id[base_book_id] = {
            "book_id": base_book_id,
            "lineup_ids": base_lineup_ids,
            "prefix_sizes": sorted(int(value) for value in arm["prefixes"]),
            "rosters": base_rosters,
            "membership_status": "exact-terminal-derived",
        }
        retrieval = arm["retrieval_interaction"]
        if retrieval is None:
            continue
        cell = _mapping(retrieval, label=f"safety {arm_id} retrieval")
        cap4_book_id = f"{arm_id}::{cell['selector_id']}"
        cap4_lineup_ids = [str(value) for value in cell["book_lineup_ids"]]
        unresolved = [
            lineup_id for lineup_id in cap4_lineup_ids
            if lineup_id not in roster_by_lineup_id
        ]
        cap4_rosters = (
            None
            if unresolved
            else [roster_by_lineup_id[lineup_id] for lineup_id in cap4_lineup_ids]
        )
        if unresolved:
            unresolved_lineup_rows.append({
                "book_id": cap4_book_id,
                "lineup_ids": unresolved,
            })
        book_by_id[cap4_book_id] = {
            "book_id": cap4_book_id,
            "lineup_ids": cap4_lineup_ids,
            "prefix_sizes": sorted(int(value) for value in cell["prefixes"]),
            "rosters": cap4_rosters,
            "membership_status": (
                "unvalidated-missing-frozen-roster"
                if unresolved else "exact-terminal-derived"
            ),
        }

    observed_book_ids = sorted(book_by_id)
    prefix_rows = [
        {
            "book_id": book_id,
            "prefix_sizes": (
                [] if book_id not in book_by_id
                else list(book_by_id[book_id]["prefix_sizes"])
            ),
        }
        for book_id in expected_books
    ]
    book_memberships = [
        book_by_id[book_id] for book_id in expected_books
        if book_id in book_by_id
    ]

    duplicate_lineup_rows: list[dict[str, object]] = []
    for book in book_memberships:
        counts = Counter(str(value) for value in book["lineup_ids"])
        duplicate_lineup_rows.extend(
            {
                "book_id": book["book_id"],
                "lineup_id": lineup_id,
                "occurrence_count": count,
            }
            for lineup_id, count in sorted(counts.items()) if count > 1
        )

    illegal_lineup_rows: list[dict[str, object]] = []
    exposure_violation_rows: list[dict[str, object]] = []
    maximum_exposure_bps = 0
    exposure_threshold = int(
        _mapping(rule["thresholds"], label="safety thresholds")[
            "maximum_player_book_exposure_bps"
        ]
    )
    membership_complete = (
        not unresolved_lineup_rows
        and set(book_by_id) == set(expected_books)
    )
    if membership_complete:
        for book in book_memberships:
            rosters = _sequence(
                book["rosters"], label=f"safety {book['book_id']} rosters"
            )
            player_counts: Counter[str] = Counter()
            for lineup_id, raw_roster in zip(book["lineup_ids"], rosters):
                roster = [str(value) for value in raw_roster]
                reasons: list[str] = []
                if len(roster) != 9 or len(set(roster)) != 9:
                    reasons.append("roster-size-or-uniqueness")
                missing_players = sorted(
                    player_id for player_id in roster
                    if player_id not in player_by_dk_id
                )
                if missing_players:
                    reasons.append("player-missing-from-frozen-bridge")
                else:
                    players = [player_by_dk_id[player_id] for player_id in roster]
                    salary = sum(int(player["salary"]) for player in players)
                    positions = Counter(str(player["position"]) for player in players)
                    teams = {str(player["team"]) for player in players}
                    if salary > 50_000:
                        reasons.append("salary-cap")
                    if not (
                        positions["QB"] == 1
                        and positions["DST"] == 1
                        and 2 <= positions["RB"] <= 3
                        and 3 <= positions["WR"] <= 4
                        and 1 <= positions["TE"] <= 2
                    ):
                        reasons.append("classic-position-slots")
                    if len(teams) < 2:
                        reasons.append("fewer-than-two-teams")
                if reasons:
                    illegal_lineup_rows.append({
                        "book_id": book["book_id"],
                        "lineup_id": lineup_id,
                        "reason_codes": reasons,
                    })
                player_counts.update(roster)
            book_size = len(rosters)
            for player_id, count in sorted(player_counts.items()):
                exposure_bps = (count * 10_000 + book_size - 1) // book_size
                maximum_exposure_bps = max(
                    maximum_exposure_bps, exposure_bps
                )
                if exposure_bps > exposure_threshold:
                    exposure_violation_rows.append({
                        "book_id": book["book_id"],
                        "player_id": player_id,
                        "appearance_count": count,
                        "book_size": book_size,
                        "exposure_bps": exposure_bps,
                    })

    expected_source_ages = {
        str(key): int(value)
        for key, value in _mapping(
            rule["required_source_maximum_age_seconds"],
            label="safety required sources",
        ).items()
    }
    native = _mapping(
        suite["paired_native_input_authority"],
        label="safety paired native input authority",
    )
    source_authorities = {
        "paired-native-effective-player-input-receipt": {
            "authority_kind": "paired-native-effective-input-source",
            "authority_projection": {
                "paired_native_input_authority_sha256": native[
                    "authority_sha256"
                ],
                "effective_player_source_identity": native[
                    "effective_player_source_identity"
                ],
            },
            "authority_sealed_at": suite["manifest_storage_created_at"],
            "age_basis": "manifest-storage-sealed-at",
        },
        "paired-native-effective-model-source-receipt": {
            "authority_kind": "paired-native-effective-input-source",
            "authority_projection": {
                "paired_native_input_authority_sha256": native[
                    "authority_sha256"
                ],
                "effective_model_source_identity": native[
                    "effective_model_source_identity"
                ],
            },
            "authority_sealed_at": suite["manifest_storage_created_at"],
            "age_basis": "manifest-storage-sealed-at",
        },
        "paired-native-effective-construction-source-receipt": {
            "authority_kind": "paired-native-effective-input-source",
            "authority_projection": {
                "paired_native_input_authority_sha256": native[
                    "authority_sha256"
                ],
                "effective_construction_source_identity": native[
                    "effective_construction_source_identity"
                ],
            },
            "authority_sealed_at": suite["manifest_storage_created_at"],
            "age_basis": "manifest-storage-sealed-at",
        },
    }
    source_authorities.update({
        "independent-audit-world-bank": {
            "authority_kind": "terminal-independent-audit-world-artifact",
            "authority_projection": root["independent_audit_world_artifact"],
            "authority_sealed_at": root["independent_audit_world_artifact"][
                "storage_created_at"
            ],
            "age_basis": "object-storage-created-at",
        },
        "shared-simulation-world-bank": {
            "authority_kind": "terminal-shared-simulation-artifact",
            "authority_projection": root["shared_simulation_artifact"],
            "authority_sealed_at": root["shared_simulation_artifact"][
                "storage_created_at"
            ],
            "age_basis": "object-storage-created-at",
        },
        "untouched-selection-world-bank": {
            "authority_kind": "terminal-untouched-selection-artifact",
            "authority_projection": root["untouched_selection_bank_artifact"],
            "authority_sealed_at": root["untouched_selection_bank_artifact"][
                "storage_created_at"
            ],
            "age_basis": "object-storage-created-at",
        },
    })
    if set(source_authorities) != set(expected_source_ages):
        _fail("safety required source labels lack terminal provenance")
    observed_time = datetime.fromisoformat(observed_at)
    source_rows: list[dict[str, object]] = []
    for source_id in sorted(expected_source_ages):
        source = source_authorities[source_id]
        created_at = _canonical_timestamp(
            source["authority_sealed_at"],
            label=f"safety {source_id} authority-sealed-at",
        )
        created_time = datetime.fromisoformat(created_at)
        if created_time > observed_time:
            _fail(f"safety source {source_id} was created after observation")
        age_seconds = math.ceil((observed_time - created_time).total_seconds())
        maximum_age = expected_source_ages[source_id]
        source_rows.append({
            "source_id": source_id,
            "authority_kind": source["authority_kind"],
            "authority_projection_sha256": canonical_sha256_v1(
                source["authority_projection"]
            ),
            "authority_sealed_at": created_at,
            "age_basis": source["age_basis"],
            "age_seconds": age_seconds,
            "maximum_age_seconds": maximum_age,
            "status": "stale" if age_seconds > maximum_age else "available",
        })

    book_membership_sha256 = canonical_sha256_v1(book_memberships)
    evidence_payloads = {
        "book-inventory-audit": {
            "observed_arm_ids": observed_arm_ids,
            "observed_book_ids": observed_book_ids,
            "block_rows": block_rows,
            "prefix_rows": prefix_rows,
        },
        "source-freshness-audit": source_rows,
        "lineup-legality-audit": {
            "book_membership_sha256": book_membership_sha256,
            "illegal_lineup_rows": illegal_lineup_rows,
            "unresolved_lineup_rows": unresolved_lineup_rows,
        },
        "solve-terminal-audit": solve_ledger_projection,
        "book-exposure-audit": {
            "book_membership_sha256": book_membership_sha256,
            "exposure_violation_rows": exposure_violation_rows,
            "maximum_observed_player_exposure_bps": (
                maximum_exposure_bps if membership_complete else None
            ),
            "unresolved_lineup_rows": unresolved_lineup_rows,
        },
        "job-execution-audit": {
            "terminal_prelock_root_sha256": root[
                "terminal_prelock_root_sha256"
            ],
            "terminal_prelock_envelope_identity": (
                terminal_prelock_envelope_identity
            ),
            "suite_manifest_identity": suite["manifest_identity"],
        },
    }
    required_evidence = [
        str(value) for value in rule["required_evidence_authorities"]
    ]
    if set(evidence_payloads) != set(required_evidence):
        _fail("safety derived evidence registry differs")
    evidence_rows = []
    for authority in sorted(required_evidence):
        status = "available"
        if authority in {"lineup-legality-audit", "book-exposure-audit"} and (
            not membership_complete
        ):
            status = "unvalidated"
        evidence_rows.append({
            "authority": authority,
            "derivation": "validated-terminal-prelock-root",
            "authority_sha256": canonical_sha256_v1(
                evidence_payloads[authority]
            ),
            "status": status,
        })

    body: dict[str, object] = {
        "schema_version": (
            "prospective-generation-shadow-terminal-safety-authority/v1"
        ),
        "season": root["season"],
        "week": root["week"],
        "slate_id": root["slate_id"],
        "preregistration_sha256": root["preregistration_sha256"],
        "terminal_prelock_root_sha256": root["terminal_prelock_root_sha256"],
        "terminal_prelock_envelope_identity": (
            terminal_prelock_envelope_identity
        ),
        "suite_manifest_identity": suite["manifest_identity"],
        "observed_arm_ids": observed_arm_ids,
        "observed_book_ids": observed_book_ids,
        "observed_block_labels_by_arm": block_rows,
        "observed_prefix_sizes_by_book": prefix_rows,
        "source_observations": source_rows,
        "evidence_authorities": evidence_rows,
        "book_memberships": book_memberships,
        "book_membership_sha256": book_membership_sha256,
        "unresolved_lineup_rows": unresolved_lineup_rows,
        "illegal_lineup_rows": illegal_lineup_rows,
        "duplicate_lineup_rows": duplicate_lineup_rows,
        "exposure_violation_rows": exposure_violation_rows,
        "solve_ledger_projection": solve_ledger_projection,
        "solve_failure_status_counts": solve_status_counts,
        "solve_request_shortfall_count": solve_request_shortfall_count,
        "maximum_observed_player_exposure_bps": (
            maximum_exposure_bps if membership_complete else None
        ),
        "membership_metrics_exactly_derivable": membership_complete,
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="terminal_safety_authority_sha256")


def build_weekly_safety_receipt_v1(
    *,
    preregistration: Mapping[str, object],
    week: int,
    slate_id: str,
    observed_at: datetime | str | None = None,
    terminal_prelock_envelope: Mapping[str, object] | None = None,
    terminal_prelock_envelope_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a safety receipt from terminal truth, or a durable failure row.

    A terminal-present receipt can pass only after replaying the full validated
    terminal.  A terminal-absent receipt deliberately retains non-derivable
    metrics as ``None`` and always fails; there is no caller-supplied zero path.
    """

    prereg = validate_preregistration_v1(preregistration)
    rule = _mapping(prereg["week8_safety_rule"], label="Week-8 safety rule")
    retained_week = _integer(week, label="safety receipt week", minimum=1)
    if retained_week not in rule["receipt_weeks"]:
        _fail("safety receipt week is outside the frozen Week-8 horizon")
    retained_slate_id = _identifier(slate_id, label="safety receipt slate ID")
    caller_observed_at = (
        None
        if observed_at is None
        else _canonical_timestamp(
            observed_at, label="caller safety receipt observed-at"
        )
    )
    expected_arms = [str(value) for value in rule["expected_arm_ids"]]
    expected_books = [str(value) for value in rule["expected_book_ids"]]
    expected_blocks = [str(value) for value in rule["expected_block_labels"]]
    expected_prefixes = [int(value) for value in rule["expected_prefix_sizes"]]
    expected_sources = sorted(
        str(value)
        for value in _mapping(
            rule["required_source_maximum_age_seconds"],
            label="safety required sources",
        )
    )
    expected_evidence = sorted(
        str(value) for value in rule["required_evidence_authorities"]
    )

    terminal_supplied = terminal_prelock_envelope is not None
    if terminal_supplied != (terminal_prelock_envelope_identity is not None):
        _fail("safety terminal content and object identity must be paired")
    terminal_identity = None
    terminal_value = None
    terminal_authority = None
    manifest_identity = None
    if terminal_supplied:
        terminal_value = _mapping(
            terminal_prelock_envelope, label="safety terminal envelope"
        )
        terminal_identity = normalize_object_identity_v1(
            terminal_prelock_envelope_identity,
            label="safety terminal envelope object identity",
        )
        _reject_prelock_carrier_identity(
            terminal_identity, label="safety terminal envelope"
        )
        if (
            terminal_identity["sha256"] != canonical_sha256_v1(terminal_value)
            or terminal_identity["bytes"]
            != len(canonical_json_bytes_v1(terminal_value))
        ):
            _fail("safety terminal envelope object content identity differs")
        root = validate_terminal_prelock_root_v1(terminal_value)
        if (
            root["week"] != retained_week
            or root["slate_id"] != retained_slate_id
            or root["preregistration_sha256"]
            != prereg["preregistration_sha256"]
        ):
            _fail("safety terminal week, slate, or preregistration differs")
        manifest_identity = root["suite_authority"]["manifest_identity"]
        # The embedded root object's GCS creation time was exact-reopened and
        # bound when the prelock envelope was created.  It is therefore the
        # pass-capable observation clock; request timestamps have no authority.
        retained_observed_at = terminal_value["storage_created_at"]
        if (
            caller_observed_at is not None
            and caller_observed_at != retained_observed_at
        ):
            _fail("caller observation time differs from trusted storage time")
        observed_time = datetime.fromisoformat(retained_observed_at)
        terminal_created = _parsed_timestamp(
            terminal_value["storage_created_at"],
            label="safety terminal root storage-created-at",
        )
        if terminal_created > observed_time:
            _fail("safety terminal was created after observation")
        terminal_authority = _derived_safety_terminal_authority_v2(
            root=root,
            terminal_prelock_envelope_identity=terminal_identity,
            rule=rule,
            observed_at=retained_observed_at,
        )
    else:
        if caller_observed_at is None:
            _fail("terminal-absent safety requires an observed-at time")
        retained_observed_at = caller_observed_at
        observed_time = datetime.fromisoformat(retained_observed_at)

    if terminal_authority is None:
        observed_arm_ids: list[str] = []
        observed_book_ids: list[str] = []
        block_rows = [
            {"arm_id": arm_id, "block_labels": []}
            for arm_id in expected_arms
        ]
        prefix_rows = [
            {"book_id": book_id, "prefix_sizes": []}
            for book_id in expected_books
        ]
        source_rows = [{
            "source_id": source_id,
            "authority_kind": None,
            "authority_projection_sha256": None,
            "authority_sealed_at": None,
            "age_basis": None,
            "age_seconds": None,
            "maximum_age_seconds": int(
                rule["required_source_maximum_age_seconds"][source_id]
            ),
            "status": "missing",
        } for source_id in expected_sources]
        evidence_rows = [{
            "authority": authority,
            "derivation": None,
            "authority_sha256": None,
            "status": "missing",
        } for authority in expected_evidence]
        failure_status_counts: dict[str, int | None] = {
            str(status): None for status in rule["solve_failure_statuses"]
        }
        illegal_lineup_count = None
        solve_failure_count = None
        solve_request_shortfall_count = None
        exposure_violation_count = None
        duplicate_lineup_count = None
        maximum_exposure = None
        unvalidated_metric_ids = [
            "illegal_lineup_count",
            "solve_failure_count",
            "solve_request_shortfall_count",
            "exposure_violation_count",
            "duplicate_lineup_count",
            "maximum_observed_player_exposure_bps",
        ]
    else:
        observed_arm_ids = list(terminal_authority["observed_arm_ids"])
        observed_book_ids = list(terminal_authority["observed_book_ids"])
        block_rows = list(
            terminal_authority["observed_block_labels_by_arm"]
        )
        prefix_rows = list(
            terminal_authority["observed_prefix_sizes_by_book"]
        )
        source_rows = list(terminal_authority["source_observations"])
        evidence_rows = list(terminal_authority["evidence_authorities"])
        failure_status_counts = dict(
            terminal_authority["solve_failure_status_counts"]
        )
        solve_failure_count = sum(
            int(value) for value in failure_status_counts.values()
        )
        solve_request_shortfall_count = int(
            terminal_authority["solve_request_shortfall_count"]
        )
        membership_exact = bool(
            terminal_authority["membership_metrics_exactly_derivable"]
        )
        illegal_lineup_count = (
            len(terminal_authority["illegal_lineup_rows"])
            if membership_exact else None
        )
        exposure_violation_count = (
            len(terminal_authority["exposure_violation_rows"])
            if membership_exact else None
        )
        duplicate_lineup_count = len(
            terminal_authority["duplicate_lineup_rows"]
        )
        maximum_exposure = terminal_authority[
            "maximum_observed_player_exposure_bps"
        ]
        unvalidated_metric_ids = [] if membership_exact else [
            "illegal_lineup_count",
            "exposure_violation_count",
            "maximum_observed_player_exposure_bps",
        ]

    block_by_arm = {
        str(row["arm_id"]): list(row["block_labels"])
        for row in block_rows
    }
    prefix_by_book = {
        str(row["book_id"]): list(row["prefix_sizes"])
        for row in prefix_rows
    }
    missing_arms = sorted(set(expected_arms) - set(observed_arm_ids))
    missing_books = sorted(set(expected_books) - set(observed_book_ids))
    missing_blocks = [
        {"arm_id": arm_id, "block_label": block_label}
        for arm_id in expected_arms for block_label in expected_blocks
        if block_label not in block_by_arm.get(arm_id, [])
    ]
    missing_prefixes = [
        {"book_id": book_id, "prefix_size": prefix_size}
        for book_id in expected_books for prefix_size in expected_prefixes
        if prefix_size not in prefix_by_book.get(book_id, [])
    ]
    missing_sources = [
        str(row["source_id"]) for row in source_rows
        if row["status"] == "missing"
    ]
    stale_sources = [
        str(row["source_id"]) for row in source_rows
        if row["status"] == "stale"
    ]
    missing_evidence = [
        str(row["authority"]) for row in evidence_rows
        if row["status"] != "available"
    ]
    metrics: dict[str, object] = {
        "missing_terminal_count": int(terminal_authority is None),
        "missing_suite_manifest_count": int(manifest_identity is None),
        "missing_expected_arm_count": len(missing_arms),
        "missing_expected_book_count": len(missing_books),
        "missing_expected_block_count": len(missing_blocks),
        "missing_expected_prefix_count": len(missing_prefixes),
        "missing_required_source_count": len(missing_sources),
        "stale_required_source_count": len(stale_sources),
        "missing_evidence_authority_count": len(missing_evidence),
        "illegal_lineup_count": illegal_lineup_count,
        "solve_failure_status_counts": failure_status_counts,
        "solve_failure_count": solve_failure_count,
        "solve_request_shortfall_count": solve_request_shortfall_count,
        "exposure_violation_count": exposure_violation_count,
        "duplicate_lineup_count": duplicate_lineup_count,
        "maximum_observed_player_exposure_bps": maximum_exposure,
    }
    checks = (
        ("missing-terminal", "missing_terminal_count", "maximum_missing_terminal_count"),
        ("missing-suite-manifest", "missing_suite_manifest_count", "maximum_missing_suite_manifest_count"),
        ("missing-expected-arms", "missing_expected_arm_count", "maximum_missing_expected_arm_count"),
        ("missing-expected-books", "missing_expected_book_count", "maximum_missing_expected_book_count"),
        ("missing-expected-blocks", "missing_expected_block_count", "maximum_missing_expected_block_count"),
        ("missing-expected-prefixes", "missing_expected_prefix_count", "maximum_missing_expected_prefix_count"),
        ("missing-required-sources", "missing_required_source_count", "maximum_missing_required_source_count"),
        ("stale-required-sources", "stale_required_source_count", "maximum_stale_required_source_count"),
        ("missing-evidence-authorities", "missing_evidence_authority_count", "maximum_missing_evidence_authority_count"),
        ("illegal-lineups", "illegal_lineup_count", "maximum_illegal_lineup_count"),
        ("solve-failures", "solve_failure_count", "maximum_solve_failure_count"),
        ("solve-request-shortfall", "solve_request_shortfall_count", "maximum_solve_request_shortfall_count"),
        ("exposure-violations", "exposure_violation_count", "maximum_exposure_violation_count"),
        ("duplicate-lineups", "duplicate_lineup_count", "maximum_duplicate_lineup_count"),
        ("extreme-player-exposure", "maximum_observed_player_exposure_bps", "maximum_player_book_exposure_bps"),
    )
    thresholds = _mapping(rule["thresholds"], label="safety thresholds")
    reason_vector: list[str] = []
    for reason, metric, threshold in checks:
        value = metrics[metric]
        if value is None:
            reason_vector.append(f"unvalidated-{reason}")
        elif int(value) > int(thresholds[threshold]):
            reason_vector.append(reason)

    body: dict[str, object] = {
        "schema_version": WEEKLY_SAFETY_RECEIPT_SCHEMA,
        "season": SEASON,
        "week": retained_week,
        "slate_id": retained_slate_id,
        "observed_at": retained_observed_at,
        "preregistration_sha256": prereg["preregistration_sha256"],
        "safety_rule_sha256": canonical_sha256_v1(rule),
        "terminal_prelock_envelope_identity": terminal_identity,
        "terminal_prelock_envelope": terminal_value,
        "suite_manifest_identity": manifest_identity,
        "terminal_safety_authority": terminal_authority,
        "observed_arm_ids": observed_arm_ids,
        "observed_book_ids": observed_book_ids,
        "observed_block_labels_by_arm": block_rows,
        "observed_prefix_sizes_by_book": prefix_rows,
        "source_observations": source_rows,
        "evidence_authorities": evidence_rows,
        "missing_expected_arm_ids": missing_arms,
        "missing_expected_book_ids": missing_books,
        "missing_expected_blocks": missing_blocks,
        "missing_expected_prefixes": missing_prefixes,
        "missing_required_source_ids": missing_sources,
        "stale_required_source_ids": stale_sources,
        "missing_evidence_authorities": missing_evidence,
        "unvalidated_metric_ids": unvalidated_metric_ids,
        "safety_metrics": metrics,
        "reason_vector": reason_vector,
        "integrity_gate_status": "fail" if reason_vector else "pass",
        "receipt_complete": True,
        "uses_realized_outcomes": False,
        "efficacy_or_promotion_allowed": False,
    }
    return _with_hash(body, field="weekly_safety_receipt_sha256")


def validate_weekly_safety_receipt_v1(
    value: object, *, preregistration: Mapping[str, object]
) -> dict[str, object]:
    """Replay a weekly safety receipt from its embedded terminal authority."""

    item = _mapping(value, label="weekly safety receipt")
    fields = {
        "schema_version", "season", "week", "slate_id", "observed_at",
        "preregistration_sha256", "safety_rule_sha256",
        "terminal_prelock_envelope_identity", "terminal_prelock_envelope",
        "suite_manifest_identity", "terminal_safety_authority",
        "observed_arm_ids", "observed_book_ids",
        "observed_block_labels_by_arm", "observed_prefix_sizes_by_book",
        "source_observations", "evidence_authorities",
        "missing_expected_arm_ids", "missing_expected_book_ids",
        "missing_expected_blocks", "missing_expected_prefixes",
        "missing_required_source_ids", "stale_required_source_ids",
        "missing_evidence_authorities", "unvalidated_metric_ids",
        "safety_metrics", "reason_vector", "integrity_gate_status",
        "receipt_complete", "uses_realized_outcomes",
        "efficacy_or_promotion_allowed", "weekly_safety_receipt_sha256",
    }
    if set(item) != fields:
        _fail("weekly safety receipt fields differ")
    _validate_self_hash(
        item,
        field="weekly_safety_receipt_sha256",
        label="weekly safety receipt",
    )
    expected = build_weekly_safety_receipt_v1(
        preregistration=preregistration,
        week=item["week"],
        slate_id=item["slate_id"],
        observed_at=item["observed_at"],
        terminal_prelock_envelope=item["terminal_prelock_envelope"],
        terminal_prelock_envelope_identity=item[
            "terminal_prelock_envelope_identity"
        ],
    )
    if item != expected:
        _fail("weekly safety receipt derived terminal lineage differs")
    return item


def build_seed_crossing_v1(
    *,
    fit_seed_identities: Mapping[str, Mapping[str, object]],
    world_seed_identities: Mapping[str, Mapping[str, object]],
    crossed_slot_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Freeze a complete fit-seed x world-seed content-identity lattice."""

    fit = {
        _identifier(key, label="fit-seed slot"): normalize_object_identity_v1(
            value, label=f"fit-seed {key}"
        )
        for key, value in fit_seed_identities.items()
    }
    world = {
        _identifier(key, label="world-seed slot"): normalize_object_identity_v1(
            value, label=f"world-seed {key}"
        )
        for key, value in world_seed_identities.items()
    }
    if len(fit) != 2 or len(world) != 2:
        _fail("fit/world crossing requires exactly two slots on each axis")
    for axis, identities in (("fit", fit), ("world", world)):
        keys = {
            tuple(identity[field] for field in (
                "uri", "generation", "sha256", "bytes"
            ))
            for identity in identities.values()
        }
        if len(keys) != len(identities):
            _fail(f"{axis}-seed slots do not identify distinct artifacts")
    axis_identity_keys = {
        tuple(identity[field] for field in (
            "uri", "generation", "sha256", "bytes"
        ))
        for identity in (*fit.values(), *world.values())
    }
    if len(axis_identity_keys) != 4:
        _fail("fit/world seed axes do not identify four distinct artifacts")
    for key, identity in (*fit.items(), *world.items()):
        _reject_prelock_carrier_identity(identity, label=f"seed slot {key}")
    expected_slot_ids = {
        f"{fit_id}--{world_id}" for fit_id in fit for world_id in world
    }
    if set(crossed_slot_identities) != expected_slot_ids:
        _fail("fit/world crossed slot lattice is incomplete")
    fit_rows = [
        {"fit_seed_slot": key, "identity": fit[key]} for key in sorted(fit)
    ]
    world_rows = [
        {"world_seed_slot": key, "identity": world[key]}
        for key in sorted(world)
    ]
    crossed_rows = []
    occupied_identity_keys = set(axis_identity_keys)
    for fit_id in sorted(fit):
        for world_id in sorted(world):
            slot_id = f"{fit_id}--{world_id}"
            crossed_identity = normalize_object_identity_v1(
                crossed_slot_identities[slot_id],
                label=f"crossed slot {slot_id}",
            )
            _reject_prelock_carrier_identity(
                crossed_identity, label=f"crossed slot {slot_id}"
            )
            crossed_identity_key = tuple(
                crossed_identity[field] for field in (
                    "uri", "generation", "sha256", "bytes"
                )
            )
            if crossed_identity_key in occupied_identity_keys:
                _fail("fit/world crossing reuses a seed artifact identity")
            occupied_identity_keys.add(crossed_identity_key)
            crossed_rows.append({
                "slot_id": slot_id,
                "fit_seed_slot": fit_id,
                "world_seed_slot": world_id,
                "fit_seed_identity": fit[fit_id],
                "world_seed_identity": world[world_id],
                "crossed_artifact_identity": crossed_identity,
            })
    body: dict[str, object] = {
        "schema_version": SEED_CROSSING_SCHEMA,
        "fit_seed_slots": fit_rows,
        "world_seed_slots": world_rows,
        "crossed_slots": crossed_rows,
        "fit_seed_count": len(fit_rows),
        "world_seed_count": len(world_rows),
        "crossed_slot_count": len(crossed_rows),
        # This object freezes the intended 2 x 2 identity lattice.  Merely
        # reopening four caller-labelled objects cannot prove that the
        # underlying fit/world combinations were actually executed, so the
        # registry must never overstate that fact.
        "crossing_design_complete": True,
        "crossing_execution_status": "not_evaluated",
        "crossed_generation_or_scoring_outputs_semantically_verified": False,
        "crossed_slots_sha256": canonical_sha256_v1(crossed_rows),
    }
    return _with_hash(body, field="seed_crossing_sha256")


def validate_seed_crossing_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="fit/world seed crossing")
    fields = {
        "schema_version", "fit_seed_slots", "world_seed_slots",
        "crossed_slots", "fit_seed_count", "world_seed_count",
        "crossed_slot_count", "crossing_design_complete",
        "crossing_execution_status",
        "crossed_generation_or_scoring_outputs_semantically_verified",
        "crossed_slots_sha256", "seed_crossing_sha256",
    }
    if set(item) != fields:
        _fail("fit/world seed crossing fields differ")
    _validate_self_hash(
        item, field="seed_crossing_sha256", label="fit/world seed crossing"
    )
    fit_rows = _sequence(item.get("fit_seed_slots"), label="fit-seed slots")
    world_rows = _sequence(item.get("world_seed_slots"), label="world-seed slots")
    crossed_rows = _sequence(item.get("crossed_slots"), label="crossed slots")
    fit: dict[str, dict[str, object]] = {}
    world: dict[str, dict[str, object]] = {}
    for raw in fit_rows:
        row = _mapping(raw, label="fit-seed slot")
        if set(row) != {"fit_seed_slot", "identity"}:
            _fail("fit-seed slot fields differ")
        key = _identifier(row.get("fit_seed_slot"), label="fit-seed slot")
        if key in fit:
            _fail("fit-seed slot repeats")
        fit[key] = normalize_object_identity_v1(
            row.get("identity"), label=f"fit-seed {key}"
        )
        _reject_prelock_carrier_identity(fit[key], label=f"fit-seed {key}")
    for raw in world_rows:
        row = _mapping(raw, label="world-seed slot")
        if set(row) != {"world_seed_slot", "identity"}:
            _fail("world-seed slot fields differ")
        key = _identifier(row.get("world_seed_slot"), label="world-seed slot")
        if key in world:
            _fail("world-seed slot repeats")
        world[key] = normalize_object_identity_v1(
            row.get("identity"), label=f"world-seed {key}"
        )
        _reject_prelock_carrier_identity(
            world[key], label=f"world-seed {key}"
        )
    if len(fit) != 2 or len(world) != 2:
        _fail("fit/world seed crossing is not the exact 2x2 design")
    for axis, identities in (("fit", fit), ("world", world)):
        keys = {
            tuple(identity[field] for field in (
                "uri", "generation", "sha256", "bytes"
            ))
            for identity in identities.values()
        }
        if len(keys) != len(identities):
            _fail(f"{axis}-seed slots do not identify distinct artifacts")
    axis_identity_keys = {
        tuple(identity[field] for field in (
            "uri", "generation", "sha256", "bytes"
        ))
        for identity in (*fit.values(), *world.values())
    }
    if len(axis_identity_keys) != 4:
        _fail("fit/world seed axes do not identify four distinct artifacts")
    expected = [
        (fit_id, world_id, f"{fit_id}--{world_id}")
        for fit_id in sorted(fit)
        for world_id in sorted(world)
    ]
    if len(crossed_rows) != len(expected):
        _fail("fit/world crossed slot count differs")
    normalized_crossed = []
    seen_cross_identities: set[tuple[object, ...]] = set(axis_identity_keys)
    for raw, (fit_id, world_id, slot_id) in zip(
        crossed_rows, expected, strict=True
    ):
        row = _mapping(raw, label=f"crossed slot {slot_id}")
        if set(row) != {
            "slot_id", "fit_seed_slot", "world_seed_slot",
            "fit_seed_identity", "world_seed_identity",
            "crossed_artifact_identity",
        }:
            _fail("crossed seed slot fields differ")
        crossed_identity = normalize_object_identity_v1(
            row.get("crossed_artifact_identity"),
            label=f"crossed slot {slot_id}",
        )
        _reject_prelock_carrier_identity(
            crossed_identity, label=f"crossed slot {slot_id}"
        )
        identity_key = tuple(crossed_identity[key] for key in (
            "uri", "generation", "sha256", "bytes"
        ))
        if (
            row.get("slot_id") != slot_id
            or row.get("fit_seed_slot") != fit_id
            or row.get("world_seed_slot") != world_id
            or row.get("fit_seed_identity") != fit[fit_id]
            or row.get("world_seed_identity") != world[world_id]
            or identity_key in seen_cross_identities
        ):
            _fail("crossed seed slot identity differs")
        seen_cross_identities.add(identity_key)
        normalized_crossed.append(row)
    if (
        item.get("schema_version") != SEED_CROSSING_SCHEMA
        or item.get("fit_seed_count") != len(fit)
        or item.get("world_seed_count") != len(world)
        or item.get("crossed_slot_count") != len(expected)
        or item.get("crossing_design_complete") is not True
        or item.get("crossing_execution_status") != "not_evaluated"
        or item.get(
            "crossed_generation_or_scoring_outputs_semantically_verified"
        ) is not False
        or item.get("crossed_slots_sha256")
        != canonical_sha256_v1(normalized_crossed)
    ):
        _fail("fit/world seed crossing fixed law differs")
    return item


def _lineup_ids(value: object, *, label: str, minimum: int = 1) -> list[str]:
    rows = _sequence(value, label=label)
    result = [_identifier(row, label=f"{label} lineup ID") for row in rows]
    if len(result) < minimum or len(set(result)) != len(result):
        _fail(f"{label} must contain at least {minimum} unique lineup IDs")
    return result


def _reporting_counts(operational_k: int) -> list[int]:
    if operational_k != 80:
        _fail("operational K must remain the preregistered production K80")
    return list(PREFIX_SIZES)


def _normalize_modeled_probabilities(
    value: object, *, operational_k: int, label: str
) -> dict[str, dict[str, int]]:
    item = _mapping(value, label=label)
    counts = _reporting_counts(operational_k)
    if set(item) != {str(count) for count in counts}:
        _fail(f"{label} entry-count registry differs")
    normalized: dict[str, dict[str, int]] = {}
    for count in counts:
        raw = _mapping(item[str(count)], label=f"{label} K{count}")
        if set(raw) != {str(threshold) for threshold in CALIBRATION_THRESHOLDS_DK}:
            _fail(f"{label} K{count} threshold registry differs")
        probabilities = {
            str(threshold): _integer(
                raw[str(threshold)],
                label=f"{label} K{count} P(max>={threshold}) ppm",
            )
            for threshold in CALIBRATION_THRESHOLDS_DK
        }
        if any(value > PROBABILITY_SCALE for value in probabilities.values()):
            _fail(f"{label} K{count} probability exceeds one")
        if not (
            probabilities["194"] >= probabilities["210"]
            >= probabilities["220"]
        ):
            _fail(f"{label} K{count} probabilities are not threshold-monotone")
        normalized[str(count)] = probabilities
    for threshold in CALIBRATION_THRESHOLDS_DK:
        trajectory = [normalized[str(count)][str(threshold)] for count in counts]
        if trajectory != sorted(trajectory):
            _fail(f"{label} P(max>={threshold}) is not prefix-monotone")
    return normalized


def _policy(arm_id: str) -> dict[str, object]:
    return {
        key: (
            dict(value) if isinstance(value, Mapping) else value
        )
        for key, value in _POLICY_BY_ARM[arm_id].items()
    }


def _auxiliary_census(
    expected: Mapping[str, object], *, arm_id: str
) -> dict[str, int]:
    required = _POLICY_BY_ARM[arm_id]["required_requests_by_family"]
    assert isinstance(required, Mapping)
    normalized: dict[str, int] = {}
    for raw_family, raw_count in expected.items():
        family = _identifier(raw_family, label=f"{arm_id} ledger family")
        count = _integer(raw_count, label=f"{arm_id} {family} request count")
        normalized[family] = count
    for family, count in required.items():
        if normalized.get(family) != count:
            _fail(f"{arm_id} core requested-solve census differs")
    auxiliary = {
        family: count
        for family, count in normalized.items()
        if family not in required
    }
    # Native generation may carry frozen replacement families beyond the
    # three comparative families.  Their exact census is retained and the
    # terminal validator requires equality across arms; renaming them to a
    # local ``aux_`` namespace would diverge from the canonical ledger.
    return dict(sorted(auxiliary.items()))


def _candidate_roster_digest(value: str, *, label: str) -> str:
    digest = value
    for prefix in ("roster-", "lineup-v1-"):
        if digest.startswith(prefix):
            digest = digest[len(prefix):]
            break
    return _digest(digest, label=label)


def _validate_exact_candidate_provenance(
    ledgers: Sequence[Mapping[str, object]],
    candidate_ids: Sequence[str],
    preexisting_ids: Sequence[str],
    *,
    arm_id: str,
) -> None:
    candidate_digests = {
        _candidate_roster_digest(value, label=f"{arm_id} candidate digest")
        for value in candidate_ids
    }
    preexisting_digests = {
        _candidate_roster_digest(value, label=f"{arm_id} preexisting digest")
        for value in preexisting_ids
    }
    ledger_digests = {
        str(row["roster_sha256"])
        for ledger in ledgers
        for row in ledger["rows"]
        if row["roster_sha256"] is not None
    }
    if not candidate_digests <= ledger_digests | preexisting_digests:
        _fail(f"{arm_id} candidate pool contains unledgered provenance")


def _validate_ledger_grid(
    value: object, *, arm_id: str
) -> tuple[dict[str, object], dict[str, object]]:
    raw = _mapping(value, label=f"{arm_id} exposure-ledger block grid")
    if set(raw) != set(_BLOCK_LABELS):
        _fail(f"{arm_id} exposure-ledger block grid differs")
    ledgers: dict[str, object] = {}
    auxiliary: dict[str, int] | None = None
    hash_by_block: dict[str, object] = {}
    attempts_by_block: dict[str, int] = {}
    requested_by_block: dict[str, int] = {}
    provenance_ledgers: list[dict[str, object]] = []
    mode: str | None = None
    expected_native_core = {
        "incumbent-160-40": {"leverage": 160, "boom": 40},
        "boom-first-40-160": {"leverage": 40, "boom": 160},
        "cross-law-40-100-60": {"leverage": 40, "boom": 100},
        "boom-dose-40-360": {"leverage": 40, "boom": 360},
        "ceiling-all-boom-0-200": {"leverage": 0, "boom": 0},
    }[arm_id]
    expected_transform = (
        {"boom:xlaw": 60}
        if arm_id == "cross-law-40-100-60"
        else {"boom": 200}
        if arm_id == "ceiling-all-boom-0-200"
        else {}
    )
    for block in _BLOCK_LABELS:
        raw_block = _mapping(
            raw[block], label=f"{arm_id}/{block} exposure ledger block"
        )
        nested = set(raw_block) == {"native", "transform"}
        block_mode = (
            "suite-native-plus-transform-ledgers"
            if nested
            else "canonical-composite-ledger"
        )
        if mode is None:
            mode = block_mode
        elif mode != block_mode:
            _fail(f"{arm_id} exposure ledger mode drifts across blocks")
        try:
            native = exposure.validate_ledger(
                raw_block["native"] if nested else raw_block
            )
        except exposure.GenerationExposureError as exc:
            raise ProspectiveGenerationShadowEvaluationError(
                f"{arm_id}/{block} exposure ledger: {exc}"
            ) from exc
        # ``validate_ledger`` is the canonical authority for source-label
        # syntax.  In particular, its v2 grammar deliberately permits the
        # suite's uppercase R0--R4 labels; do not impose a divergent local
        # lowercase-only identifier law here.
        source = _string(
            native.get("source_label"), label=f"{arm_id}/{block} ledger source"
        )
        if block.lower() not in source.lower():
            _fail(f"{arm_id}/{block} exposure ledger source differs")
        native_expected = _mapping(
            native.get("expected_requests_by_family"),
            label=f"{arm_id}/{block} expected solve census",
        )
        if nested:
            for family, count in {
                **expected_native_core, "role_epistemic": 12
            }.items():
                if native_expected.get(family) != count:
                    _fail(f"{arm_id}/{block} native {family} census differs")
            block_auxiliary = {
                str(family): _integer(
                    count, label=f"{arm_id}/{block} {family} request count"
                )
                for family, count in native_expected.items()
                if family not in {"leverage", "boom", "role_epistemic"}
            }
            raw_transform = raw_block["transform"]
            if raw_transform is None:
                transform = None
            else:
                try:
                    transform = exposure.validate_ledger(raw_transform)
                except exposure.GenerationExposureError as exc:
                    raise ProspectiveGenerationShadowEvaluationError(
                        f"{arm_id}/{block} transform exposure ledger: {exc}"
                    ) from exc
            if (transform is None) != (not expected_transform):
                _fail(f"{arm_id}/{block} transform ledger presence differs")
            if transform is not None:
                transform_source = _string(
                    transform.get("source_label"),
                    label=f"{arm_id}/{block} transform ledger source",
                )
                if block.lower() not in transform_source.lower():
                    _fail(f"{arm_id}/{block} transform ledger source differs")
                if transform.get("expected_requests_by_family") != expected_transform:
                    _fail(f"{arm_id}/{block} transform solve census differs")
            ledgers[block] = {"native": native, "transform": transform}
            block_ledgers = [native] + ([] if transform is None else [transform])
            hash_by_block[block] = {
                "native": native["ledger_sha256"],
                "transform": (
                    None if transform is None else transform["ledger_sha256"]
                ),
            }
        else:
            block_auxiliary = _auxiliary_census(
                native_expected, arm_id=arm_id
            )
            ledgers[block] = native
            block_ledgers = [native]
            hash_by_block[block] = native["ledger_sha256"]
        if auxiliary is None:
            auxiliary = dict(sorted(block_auxiliary.items()))
        elif block_auxiliary != auxiliary:
            _fail(f"{arm_id} auxiliary census drifts across blocks")
        provenance_ledgers.extend(block_ledgers)
        attempts_by_block[block] = sum(
            int(ledger["attempt_count"]) for ledger in block_ledgers
        )
        requested_by_block[block] = sum(
            sum(int(count) for count in ledger[
                "expected_requests_by_family"
            ].values())
            for ledger in block_ledgers
        )
    assert auxiliary is not None
    assert mode is not None
    expected_requested = (
        int(_POLICY_BY_ARM[arm_id]["core_requested_solve_count"])
        + 12 + sum(auxiliary.values())
    )
    if any(value != expected_requested for value in requested_by_block.values()):
        _fail(f"{arm_id} requested-solve census differs across ledger components")
    return ledgers, {
        "mode": mode,
        "auxiliary": auxiliary,
        "hash_by_block": hash_by_block,
        "attempts_by_block": attempts_by_block,
        "requested_by_block": requested_by_block,
        "provenance_ledgers": provenance_ledgers,
    }


def build_arm_freeze_v1(
    *,
    arm_id: str,
    population_label: str,
    cap_label: str,
    operational_k: int,
    candidate_lineup_ids: Sequence[str],
    preexisting_candidate_lineup_ids: Sequence[str] = (),
    preexisting_candidate_census_artifact: Mapping[str, object] | None = None,
    book_lineup_ids: Sequence[str],
    modeled_probability_ppm: Mapping[str, Mapping[str, int]],
    exposure_ledgers_by_block: Mapping[str, Mapping[str, object]],
    artifacts: Mapping[str, Mapping[str, object]],
    cap4_book_lineup_ids: Sequence[str] | None = None,
    cap4_modeled_probability_ppm: Mapping[str, Mapping[str, int]] | None = None,
    cap4_book_artifact: Mapping[str, object] | None = None,
    shared_simulation_identity: Mapping[str, object],
    untouched_selection_bank_identity: Mapping[str, object],
    seed_crossing_sha256: str,
) -> dict[str, object]:
    """Build one arm projection after validating its canonical solve ledger."""

    arm = _identifier(arm_id, label="arm ID")
    if arm not in ARM_ORDER:
        _fail("arm ID lies outside the predeclared family")
    k = _integer(operational_k, label="operational K", minimum=80)
    retained_cap_label = _identifier(cap_label, label=f"{arm} cap label")
    if retained_cap_label != _BASE_RETRIEVAL_ID:
        _fail(f"{arm} base retrieval label differs")
    candidates = _lineup_ids(
        candidate_lineup_ids, label=f"{arm} candidate pool", minimum=k
    )
    preexisting = _lineup_ids(
        preexisting_candidate_lineup_ids,
        label=f"{arm} preexisting candidate pool",
        minimum=0,
    ) if preexisting_candidate_lineup_ids else []
    if bool(preexisting) != (preexisting_candidate_census_artifact is not None):
        _fail(f"{arm} preexisting candidates require one frozen census artifact")
    census_artifact: dict[str, object] | None = None
    if preexisting_candidate_census_artifact is not None:
        census_payload = {
            "schema_version": "prospective-generation-preexisting-candidate-census/v1",
            "arm_id": arm,
            "candidate_lineup_ids": preexisting,
            "candidate_lineup_ids_sha256": canonical_sha256_v1(preexisting),
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        }
        descriptor = _mapping(
            preexisting_candidate_census_artifact,
            label=f"{arm} preexisting candidate census artifact",
        )
        if set(descriptor) != {
            "identity", "create_once", "frozen_at", "storage_created_at",
            "storage_metadata_authority",
        }:
            _fail(f"{arm} preexisting candidate census artifact fields differ")
        identity = normalize_object_identity_v1(
            descriptor.get("identity"),
            label=f"{arm} preexisting candidate census identity",
        )
        _reject_prelock_carrier_identity(
            identity, label=f"{arm} preexisting candidate census"
        )
        census_frozen = _canonical_timestamp(
            descriptor.get("frozen_at"),
            label=f"{arm} preexisting census frozen-at",
        )
        census_created = _canonical_timestamp(
            descriptor.get("storage_created_at"),
            label=f"{arm} preexisting census storage-created-at",
        )
        if (
            identity["sha256"] != canonical_sha256_v1(census_payload)
            or identity["bytes"] != len(canonical_json_bytes_v1(census_payload))
            or descriptor.get("create_once") is not True
            or descriptor.get("storage_metadata_authority")
            != "google-cloud-storage-object-metadata"
            or datetime.fromisoformat(census_created)
            < datetime.fromisoformat(census_frozen)
        ):
            _fail(f"{arm} preexisting candidate census content differs")
        census_artifact = {
            "identity": identity,
            "create_once": descriptor.get("create_once"),
            "frozen_at": census_frozen,
            "storage_created_at": census_created,
            "storage_metadata_authority": descriptor.get(
                "storage_metadata_authority"
            ),
        }
    book = _lineup_ids(book_lineup_ids, label=f"{arm} book", minimum=k)
    if len(book) != k or not set(book) <= set(candidates):
        _fail(f"{arm} book is not exact operational K from its candidate pool")
    prefixes = {str(count): book[:count] for count in PREFIX_SIZES}
    modeled = _normalize_modeled_probabilities(
        modeled_probability_ppm, operational_k=k,
        label=f"{arm} modeled probabilities",
    )
    ledgers, ledger_summary = _validate_ledger_grid(
        exposure_ledgers_by_block, arm_id=arm
    )
    auxiliary = ledger_summary["auxiliary"]
    assert isinstance(auxiliary, Mapping)
    _validate_exact_candidate_provenance(
        ledger_summary["provenance_ledgers"],
        candidates,
        preexisting,
        arm_id=arm,
    )
    raw_artifacts = _mapping(artifacts, label=f"{arm} artifacts")
    if set(raw_artifacts) != {
        "book", "candidate_pool", "exposure_ledger", "world"
    }:
        _fail(f"{arm} artifact registry differs")
    # Timestamp/create-once checks occur again at the root, where the exact
    # lock boundary is available.  Here we still require the closed shape.
    normalized_artifacts: dict[str, dict[str, object]] = {}
    for name in sorted(raw_artifacts):
        descriptor = _mapping(
            raw_artifacts[name], label=f"{arm} {name} artifact"
        )
        if set(descriptor) != {
            "identity", "create_once", "frozen_at", "storage_created_at",
            "storage_metadata_authority",
        }:
            _fail(f"{arm} {name} artifact fields differ")
        if descriptor.get("create_once") is not True:
            _fail(f"{arm} {name} artifact is not create-once")
        artifact_identity = normalize_object_identity_v1(
            descriptor.get("identity"), label=f"{arm} {name} artifact"
        )
        _reject_prelock_carrier_identity(
            artifact_identity, label=f"{arm} {name} artifact"
        )
        normalized_artifacts[name] = {
            "identity": artifact_identity,
            "create_once": True,
            "frozen_at": _canonical_timestamp(
                descriptor.get("frozen_at"),
                label=f"{arm} {name} artifact frozen-at",
            ),
            "storage_created_at": _canonical_timestamp(
                descriptor.get("storage_created_at"),
                label=f"{arm} {name} artifact storage-created-at",
            ),
            "storage_metadata_authority": descriptor.get(
                "storage_metadata_authority"
            ),
        }
    crossing_supplied = (
        cap4_book_lineup_ids is not None,
        cap4_modeled_probability_ppm is not None,
        cap4_book_artifact is not None,
    )
    if arm in _RETRIEVAL_CROSSING_ARMS:
        if crossing_supplied != (True, True, True):
            _fail(f"{arm} lacks the preregistered cap-4 retrieval cell")
        cap4_book = _lineup_ids(
            cap4_book_lineup_ids,
            label=f"{arm} cap-4 book",
            minimum=k,
        )
        if len(cap4_book) != k or not set(cap4_book) <= set(candidates):
            _fail(f"{arm} cap-4 book is not exact operational K from its pool")
        cap4_prefixes = {
            str(count): cap4_book[:count] for count in PREFIX_SIZES
        }
        cap4_modeled = _normalize_modeled_probabilities(
            cap4_modeled_probability_ppm,
            operational_k=k,
            label=f"{arm} cap-4 modeled probabilities",
        )
        cap4_descriptor = _mapping(
            cap4_book_artifact, label=f"{arm} cap-4 book artifact"
        )
        if set(cap4_descriptor) != {
            "identity", "create_once", "frozen_at", "storage_created_at",
            "storage_metadata_authority",
        }:
            _fail(f"{arm} cap-4 book artifact fields differ")
        cap4_identity = normalize_object_identity_v1(
            cap4_descriptor.get("identity"),
            label=f"{arm} cap-4 book artifact",
        )
        _reject_prelock_carrier_identity(
            cap4_identity, label=f"{arm} cap-4 book artifact"
        )
        retrieval_interaction: dict[str, object] | None = {
            "selector_id": _CAP4_RETRIEVAL_ID,
            "cap_label": _CAP4_RETRIEVAL_ID,
            "candidate_pool_unchanged": True,
            "book_lineup_ids": cap4_book,
            "book_lineup_ids_sha256": canonical_sha256_v1(cap4_book),
            "prefixes": cap4_prefixes,
            "prefixes_sha256": canonical_sha256_v1(cap4_prefixes),
            "modeled_probability_ppm": cap4_modeled,
            "modeled_probability_sha256": canonical_sha256_v1(cap4_modeled),
            "calibration_probability_source": (
                "independent-score-only-audit-world-bank"
            ),
            "book_artifact": {
                "identity": cap4_identity,
                "create_once": True,
                "frozen_at": _canonical_timestamp(
                    cap4_descriptor.get("frozen_at"),
                    label=f"{arm} cap-4 frozen-at",
                ),
                "storage_created_at": _canonical_timestamp(
                    cap4_descriptor.get("storage_created_at"),
                    label=f"{arm} cap-4 storage-created-at",
                ),
                "storage_metadata_authority": cap4_descriptor.get(
                    "storage_metadata_authority"
                ),
            },
        }
    else:
        if any(crossing_supplied):
            _fail(f"{arm} received an undeclared retrieval interaction")
        retrieval_interaction = None
    body: dict[str, object] = {
        "schema_version": ARM_FREEZE_SCHEMA,
        "arm_id": arm,
        "population_label": _identifier(
            population_label, label=f"{arm} population label"
        ),
        "cap_label": retained_cap_label,
        "generation_contract": _policy(arm),
        "arm_status": _POLICY_BY_ARM[arm]["arm_status"],
        "scientific_status": _POLICY_BY_ARM[arm]["scientific_status"],
        "decision_role": _POLICY_BY_ARM[arm]["decision_role"],
        "required_before_week1": _POLICY_BY_ARM[arm][
            "required_before_week1"
        ],
        "resource_class": _POLICY_BY_ARM[arm]["resource_class"],
        "resource_caveat": _POLICY_BY_ARM[arm]["resource_caveat"],
        "equal_compute_comparison": _POLICY_BY_ARM[arm][
            "equal_compute_comparison"
        ],
        "selection_law": _BASE_SELECTION_LAW,
        "selection_bank_untouched": True,
        "shared_simulation_identity": normalize_object_identity_v1(
            shared_simulation_identity, label=f"{arm} shared simulation"
        ),
        "untouched_selection_bank_identity": normalize_object_identity_v1(
            untouched_selection_bank_identity,
            label=f"{arm} untouched selection bank",
        ),
        "seed_crossing_sha256": _digest(
            seed_crossing_sha256, label=f"{arm} seed crossing SHA-256"
        ),
        "operational_k": k,
        "candidate_lineup_ids": candidates,
        "candidate_lineup_ids_sha256": canonical_sha256_v1(candidates),
        "preexisting_candidate_lineup_ids": preexisting,
        "preexisting_candidate_lineup_ids_sha256": canonical_sha256_v1(
            preexisting
        ),
        "preexisting_candidate_census_artifact": census_artifact,
        "book_lineup_ids": book,
        "book_lineup_ids_sha256": canonical_sha256_v1(book),
        "prefixes": prefixes,
        "prefixes_sha256": canonical_sha256_v1(prefixes),
        "modeled_probability_ppm": modeled,
        "modeled_probability_sha256": canonical_sha256_v1(modeled),
        "calibration_probability_source": (
            "independent-score-only-audit-world-bank"
        ),
        "base_retrieval_id": _BASE_RETRIEVAL_ID,
        "retrieval_interaction": retrieval_interaction,
        "exposure_ledgers_by_block": ledgers,
        "exposure_ledger_mode": ledger_summary["mode"],
        "exposure_ledger_sha256_by_block": ledger_summary["hash_by_block"],
        "allocation_unit": "per-10000-world-block",
        "generation_block_count": len(_BLOCK_LABELS),
        "requested_core_solve_count_per_block": int(
            _POLICY_BY_ARM[arm]["core_requested_solve_count"]
        ),
        "requested_role_solve_count_per_block": 12,
        "requested_auxiliary_solve_count_per_block": sum(auxiliary.values()),
        "requested_solve_count_per_block": ledger_summary[
            "requested_by_block"
        ][_BLOCK_LABELS[0]],
        "requested_solve_count_per_slate": sum(
            ledger_summary["requested_by_block"].values()
        ),
        "solve_attempt_count_per_block": ledger_summary["attempts_by_block"],
        "solve_attempt_count_per_slate": sum(
            ledger_summary["attempts_by_block"].values()
        ),
        "auxiliary_requests_by_family": dict(auxiliary),
        "artifacts": normalized_artifacts,
        "artifact_component_sha256": {
            "book": canonical_sha256_v1(book),
            "candidate_pool": canonical_sha256_v1(candidates),
            "exposure_ledger": canonical_sha256_v1(
                ledger_summary["hash_by_block"]
            ),
            "world": normalized_artifacts["world"]["identity"]["sha256"],
            "cap4_book": (
                None
                if retrieval_interaction is None
                else retrieval_interaction["book_lineup_ids_sha256"]
            ),
            "preexisting_candidate_census": (
                None
                if census_artifact is None
                else census_artifact["identity"]["sha256"]
            ),
        },
        "uses_post_lock_data": False,
        "uses_realized_outcomes": False,
        "complete": True,
    }
    return _with_hash(body, field="arm_freeze_sha256")


def validate_arm_freeze_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="shadow arm freeze")
    fields = {
        "schema_version", "arm_id", "population_label", "cap_label",
        "arm_status", "scientific_status", "decision_role",
        "required_before_week1", "resource_class", "resource_caveat",
        "equal_compute_comparison",
        "generation_contract", "selection_law", "selection_bank_untouched",
        "shared_simulation_identity", "untouched_selection_bank_identity",
        "seed_crossing_sha256", "operational_k", "candidate_lineup_ids",
        "candidate_lineup_ids_sha256", "book_lineup_ids",
        "preexisting_candidate_lineup_ids",
        "preexisting_candidate_lineup_ids_sha256",
        "preexisting_candidate_census_artifact",
        "book_lineup_ids_sha256", "prefixes", "prefixes_sha256",
        "modeled_probability_ppm", "modeled_probability_sha256",
        "calibration_probability_source",
        "base_retrieval_id", "retrieval_interaction",
        "exposure_ledgers_by_block", "exposure_ledger_mode",
        "exposure_ledger_sha256_by_block",
        "allocation_unit", "generation_block_count",
        "requested_core_solve_count_per_block",
        "requested_role_solve_count_per_block",
        "requested_auxiliary_solve_count_per_block",
        "requested_solve_count_per_block", "requested_solve_count_per_slate",
        "solve_attempt_count_per_block", "solve_attempt_count_per_slate",
        "auxiliary_requests_by_family", "artifacts",
        "artifact_component_sha256", "uses_post_lock_data",
        "uses_realized_outcomes", "complete", "arm_freeze_sha256",
    }
    if set(item) != fields:
        _fail("shadow arm freeze fields differ")
    _validate_self_hash(item, field="arm_freeze_sha256", label="shadow arm freeze")
    arm = _identifier(item.get("arm_id"), label="arm ID")
    if arm not in ARM_ORDER:
        _fail("shadow arm is outside the predeclared family")
    k = _integer(item.get("operational_k"), label=f"{arm} operational K", minimum=80)
    candidates = _lineup_ids(
        item.get("candidate_lineup_ids"), label=f"{arm} candidates", minimum=k
    )
    raw_preexisting = _sequence(
        item.get("preexisting_candidate_lineup_ids"),
        label=f"{arm} preexisting candidates",
    )
    preexisting = [
        _identifier(value, label=f"{arm} preexisting candidate")
        for value in raw_preexisting
    ]
    if len(set(preexisting)) != len(preexisting):
        _fail(f"{arm} preexisting candidate list repeats")
    raw_census = item.get("preexisting_candidate_census_artifact")
    if bool(preexisting) != (raw_census is not None):
        _fail(f"{arm} preexisting candidate census presence differs")
    if raw_census is not None:
        census = _mapping(
            raw_census, label=f"{arm} preexisting candidate census artifact"
        )
        if set(census) != {
            "identity", "create_once", "frozen_at", "storage_created_at",
            "storage_metadata_authority",
        }:
            _fail(f"{arm} preexisting candidate census fields differ")
        census_identity = normalize_object_identity_v1(
            census.get("identity"),
            label=f"{arm} preexisting candidate census identity",
        )
        census_payload = {
            "schema_version": "prospective-generation-preexisting-candidate-census/v1",
            "arm_id": arm,
            "candidate_lineup_ids": preexisting,
            "candidate_lineup_ids_sha256": canonical_sha256_v1(preexisting),
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        }
        census_frozen = _parsed_timestamp(
            census.get("frozen_at"), label=f"{arm} census frozen-at"
        )
        census_created = _parsed_timestamp(
            census.get("storage_created_at"),
            label=f"{arm} census storage-created-at",
        )
        if (
            census.get("create_once") is not True
            or census.get("storage_metadata_authority")
            != "google-cloud-storage-object-metadata"
            or census_created < census_frozen
            or census_identity["sha256"]
            != canonical_sha256_v1(census_payload)
            or census_identity["bytes"]
            != len(canonical_json_bytes_v1(census_payload))
        ):
            _fail(f"{arm} preexisting candidate census binding differs")
    book = _lineup_ids(item.get("book_lineup_ids"), label=f"{arm} book", minimum=k)
    prefixes = _mapping(item.get("prefixes"), label=f"{arm} prefixes")
    expected_prefixes = {str(count): book[:count] for count in PREFIX_SIZES}
    modeled = _normalize_modeled_probabilities(
        item.get("modeled_probability_ppm"), operational_k=k,
        label=f"{arm} modeled probabilities",
    )
    retrieval = item.get("retrieval_interaction")
    if arm in _RETRIEVAL_CROSSING_ARMS:
        cell = _mapping(retrieval, label=f"{arm} retrieval interaction")
        if set(cell) != {
            "selector_id", "cap_label", "candidate_pool_unchanged",
            "book_lineup_ids", "book_lineup_ids_sha256", "prefixes",
            "prefixes_sha256", "modeled_probability_ppm",
            "modeled_probability_sha256", "calibration_probability_source",
            "book_artifact",
        }:
            _fail(f"{arm} retrieval-interaction fields differ")
        cap4_book = _lineup_ids(
            cell.get("book_lineup_ids"), label=f"{arm} cap-4 book", minimum=k
        )
        cap4_prefixes = _mapping(
            cell.get("prefixes"), label=f"{arm} cap-4 prefixes"
        )
        cap4_modeled = _normalize_modeled_probabilities(
            cell.get("modeled_probability_ppm"),
            operational_k=k,
            label=f"{arm} cap-4 modeled probabilities",
        )
        if (
            cell.get("selector_id") != _CAP4_RETRIEVAL_ID
            or cell.get("cap_label") != _CAP4_RETRIEVAL_ID
            or cell.get("candidate_pool_unchanged") is not True
            or len(cap4_book) != k
            or not set(cap4_book) <= set(candidates)
            or cell.get("book_lineup_ids_sha256")
            != canonical_sha256_v1(cap4_book)
            or cap4_prefixes
            != {str(count): cap4_book[:count] for count in PREFIX_SIZES}
            or cell.get("prefixes_sha256")
            != canonical_sha256_v1(cap4_prefixes)
            or cell.get("modeled_probability_sha256")
            != canonical_sha256_v1(cap4_modeled)
            or cell.get("calibration_probability_source")
            != "independent-score-only-audit-world-bank"
        ):
            _fail(f"{arm} retrieval-interaction frozen law differs")
        cap4_artifact = _mapping(
            cell.get("book_artifact"), label=f"{arm} cap-4 artifact"
        )
        if set(cap4_artifact) != {
            "identity", "create_once", "frozen_at", "storage_created_at",
            "storage_metadata_authority",
        }:
            _fail(f"{arm} cap-4 artifact fields differ")
        cap4_identity = normalize_object_identity_v1(
            cap4_artifact.get("identity"), label=f"{arm} cap-4 artifact"
        )
        _reject_prelock_carrier_identity(
            cap4_identity, label=f"{arm} cap-4 artifact"
        )
        cap4_frozen = _parsed_timestamp(
            cap4_artifact.get("frozen_at"), label=f"{arm} cap-4 frozen-at"
        )
        cap4_created = _parsed_timestamp(
            cap4_artifact.get("storage_created_at"),
            label=f"{arm} cap-4 storage-created-at",
        )
        if (
            cap4_artifact.get("create_once") is not True
            or cap4_artifact.get("storage_metadata_authority")
            != "google-cloud-storage-object-metadata"
            or cap4_created < cap4_frozen
        ):
            _fail(f"{arm} cap-4 storage metadata differs")
    elif retrieval is not None:
        _fail(f"{arm} has an undeclared retrieval interaction")
    if (
        item.get("schema_version") != ARM_FREEZE_SCHEMA
        or item.get("generation_contract") != _policy(arm)
        or item.get("arm_status") != _POLICY_BY_ARM[arm]["arm_status"]
        or item.get("scientific_status")
        != _POLICY_BY_ARM[arm]["scientific_status"]
        or item.get("decision_role") != _POLICY_BY_ARM[arm]["decision_role"]
        or item.get("required_before_week1")
        is not _POLICY_BY_ARM[arm]["required_before_week1"]
        or item.get("resource_class") != _POLICY_BY_ARM[arm]["resource_class"]
        or item.get("resource_caveat") != _POLICY_BY_ARM[arm]["resource_caveat"]
        or item.get("equal_compute_comparison")
        is not _POLICY_BY_ARM[arm]["equal_compute_comparison"]
        or item.get("selection_law") != _BASE_SELECTION_LAW
        or item.get("selection_bank_untouched") is not True
        or len(book) != k
        or not set(book) <= set(candidates)
        or item.get("candidate_lineup_ids_sha256")
        != canonical_sha256_v1(candidates)
        or item.get("preexisting_candidate_lineup_ids_sha256")
        != canonical_sha256_v1(preexisting)
        or item.get("book_lineup_ids_sha256") != canonical_sha256_v1(book)
        or prefixes != expected_prefixes
        or item.get("prefixes_sha256") != canonical_sha256_v1(prefixes)
        or item.get("modeled_probability_sha256")
        != canonical_sha256_v1(modeled)
        or item.get("calibration_probability_source")
        != "independent-score-only-audit-world-bank"
        or item.get("base_retrieval_id") != _BASE_RETRIEVAL_ID
        or item.get("uses_post_lock_data") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("complete") is not True
    ):
        _fail(f"{arm} frozen book, prefix, or score-blind law differs")
    shared_identity = normalize_object_identity_v1(
        item.get("shared_simulation_identity"), label=f"{arm} simulation"
    )
    selection_identity = normalize_object_identity_v1(
        item.get("untouched_selection_bank_identity"),
        label=f"{arm} selection bank",
    )
    _reject_prelock_carrier_identity(
        shared_identity, label=f"{arm} simulation"
    )
    _reject_prelock_carrier_identity(
        selection_identity, label=f"{arm} selection bank"
    )
    _digest(item.get("seed_crossing_sha256"), label=f"{arm} seed crossing")
    ledgers, ledger_summary = _validate_ledger_grid(
        item.get("exposure_ledgers_by_block"), arm_id=arm
    )
    auxiliary = ledger_summary["auxiliary"]
    assert isinstance(auxiliary, Mapping)
    expected_hashes = ledger_summary["hash_by_block"]
    core_per_block = int(_POLICY_BY_ARM[arm]["core_requested_solve_count"])
    role_per_block = 12
    auxiliary_per_block = sum(auxiliary.values())
    requested_per_block = core_per_block + role_per_block + auxiliary_per_block
    requested_per_slate = requested_per_block * len(_BLOCK_LABELS)
    attempts_by_block = ledger_summary["attempts_by_block"]
    if (
        item.get("exposure_ledger_mode") != ledger_summary["mode"]
        or
        item.get("exposure_ledger_sha256_by_block") != expected_hashes
        or item.get("allocation_unit") != "per-10000-world-block"
        or item.get("generation_block_count") != len(_BLOCK_LABELS)
        or item.get("requested_core_solve_count_per_block") != core_per_block
        or item.get("requested_role_solve_count_per_block") != role_per_block
        or item.get("requested_auxiliary_solve_count_per_block")
        != auxiliary_per_block
        or item.get("requested_solve_count_per_block") != requested_per_block
        or item.get("requested_solve_count_per_slate") != requested_per_slate
        or item.get("solve_attempt_count_per_block") != attempts_by_block
        or item.get("solve_attempt_count_per_slate") != sum(attempts_by_block.values())
        or item.get("auxiliary_requests_by_family") != auxiliary
    ):
        _fail(f"{arm} exposure ledger binding differs")
    _validate_exact_candidate_provenance(
        ledger_summary["provenance_ledgers"],
        candidates,
        preexisting,
        arm_id=arm,
    )
    _identifier(item.get("population_label"), label=f"{arm} population label")
    _identifier(item.get("cap_label"), label=f"{arm} cap label")
    if item.get("cap_label") != _BASE_RETRIEVAL_ID:
        _fail(f"{arm} base retrieval label differs")
    artifacts = _mapping(item.get("artifacts"), label=f"{arm} artifacts")
    if set(artifacts) != {"book", "candidate_pool", "exposure_ledger", "world"}:
        _fail(f"{arm} artifact registry differs")
    for name, raw in artifacts.items():
        descriptor = _mapping(raw, label=f"{arm} {name} artifact")
        if set(descriptor) != {
            "identity", "create_once", "frozen_at", "storage_created_at",
            "storage_metadata_authority",
        }:
            _fail(f"{arm} {name} artifact fields differ")
        artifact_identity = normalize_object_identity_v1(
            descriptor.get("identity"), label=f"{arm} {name} artifact"
        )
        _reject_prelock_carrier_identity(
            artifact_identity, label=f"{arm} {name} artifact"
        )
        frozen = _parsed_timestamp(
            descriptor.get("frozen_at"), label=f"{arm} {name} frozen-at"
        )
        created = _parsed_timestamp(
            descriptor.get("storage_created_at"),
            label=f"{arm} {name} storage-created-at",
        )
        if descriptor.get("create_once") is not True:
            _fail(f"{arm} {name} artifact is not create-once")
        if (
            descriptor.get("storage_metadata_authority")
            != "google-cloud-storage-object-metadata"
            or created < frozen
        ):
            _fail(f"{arm} {name} artifact storage metadata differs")
    expected_component_hashes = {
        "book": canonical_sha256_v1(book),
        "candidate_pool": canonical_sha256_v1(candidates),
        "exposure_ledger": canonical_sha256_v1(expected_hashes),
        "world": artifacts["world"]["identity"]["sha256"],
        "cap4_book": (
            None
            if retrieval is None
            else retrieval["book_lineup_ids_sha256"]
        ),
        "preexisting_candidate_census": (
            None
            if raw_census is None
            else raw_census["identity"]["sha256"]
        ),
    }
    if item.get("artifact_component_sha256") != expected_component_hashes:
        _fail(f"{arm} immutable bundle component binding differs")
    return item


def _suite_object_receipt(
    value: object, *, label: str
) -> dict[str, object]:
    receipt = _mapping(value, label=label)
    if set(receipt) != {
        "uri", "generation", "sha256", "bytes", "gcs_time_created",
        "precedes_slate_lock", "create_only",
    }:
        _fail(f"{label} fields differ")
    if (
        receipt.get("create_only") is not True
        or receipt.get("precedes_slate_lock") is not True
    ):
        _fail(f"{label} is not trusted create-only prelock storage")
    _parsed_timestamp(
        receipt.get("gcs_time_created"), label=f"{label} GCS creation time"
    )
    return normalize_object_identity_v1(
        {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
        label=label,
    )


def _suite_world_identity(value: object, *, label: str) -> dict[str, object]:
    receipt = _mapping(value, label=label)
    if receipt.get("create_only") is not True or not receipt.get(
        "gcs_time_created"
    ):
        _fail(f"{label} is not trusted create-only storage")
    _parsed_timestamp(
        receipt.get("gcs_time_created"), label=f"{label} GCS creation time"
    )
    return normalize_object_identity_v1(
        {key: receipt.get(key) for key in (
            "uri", "generation", "sha256", "bytes"
        )},
        label=label,
    )


def _suite_array_receipt(value: object, *, label: str) -> dict[str, object]:
    receipt = _mapping(value, label=label)
    if set(receipt) != {"sha256", "dtype", "shape", "bytes"}:
        _fail(f"{label} fields differ")
    shape = _sequence(receipt.get("shape"), label=f"{label} shape")
    retained_shape = [
        _integer(dimension, label=f"{label} dimension", minimum=1)
        for dimension in shape
    ]
    return {
        "sha256": _digest(receipt.get("sha256"), label=f"{label} SHA-256"),
        "dtype": _string(receipt.get("dtype"), label=f"{label} dtype"),
        "shape": retained_shape,
        "bytes": _integer(receipt.get("bytes"), label=f"{label} bytes", minimum=1),
    }


def _validated_suite_player_identity_bridge(
    manifest: Mapping[str, object],
    *,
    paired_native_input_authority: Mapping[str, object],
) -> list[dict[str, object]]:
    """Validate the prelock internal-to-DK identity map in player order."""

    raw_rows = _sequence(
        manifest.get("player_identity_bridge"),
        label="suite player identity bridge",
    )
    retained_hash = _digest(
        manifest.get("player_identity_bridge_sha256"),
        label="suite player identity bridge SHA-256",
    )
    if retained_hash != canonical_sha256_v1(raw_rows):
        _fail("suite player identity bridge hash differs")
    expected_player = _mapping(
        paired_native_input_authority.get(
            "effective_player_source_identity"
        ),
        label="paired effective player source identity",
    )
    if len(raw_rows) != expected_player.get("player_count"):
        _fail("suite player identity bridge count differs")
    fields = {
        "internal_player_id", "dk_draftable_id", "gsis_id", "position",
        "team", "dst_team", "salary",
    }
    rows: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(raw_rows):
        row = _mapping(
            raw_row, label=f"suite player identity bridge[{ordinal}]"
        )
        if set(row) != fields:
            _fail("suite player identity bridge fields differ")
        internal_id = _string(
            row.get("internal_player_id"),
            label=f"suite bridge internal player ID {ordinal}",
        )
        dk_id = _string(
            row.get("dk_draftable_id"),
            label=f"suite bridge DK draftable ID {ordinal}",
        )
        position = _string(
            row.get("position"), label=f"suite bridge position {ordinal}"
        )
        team = _string(
            row.get("team"), label=f"suite bridge team {ordinal}"
        )
        if position not in {"QB", "RB", "WR", "TE", "DST"}:
            _fail("suite player identity bridge position differs")
        gsis_id = row.get("gsis_id")
        dst_team = row.get("dst_team")
        if position == "DST":
            if gsis_id is not None or dst_team != team:
                _fail("suite DST identity bridge differs")
        elif (
            type(gsis_id) is not str
            or not gsis_id
            or gsis_id.strip() != gsis_id
            or dst_team is not None
        ):
            _fail("suite player GSIS identity bridge differs")
        rows.append({
            "internal_player_id": internal_id,
            "dk_draftable_id": dk_id,
            "gsis_id": gsis_id,
            "position": position,
            "team": team,
            "dst_team": dst_team,
            "salary": _integer(
                row.get("salary"),
                label=f"suite bridge salary {ordinal}",
                minimum=1,
            ),
        })
    internal_order = [str(row["internal_player_id"]) for row in rows]
    artifact_order = [str(row["dk_draftable_id"]) for row in rows]
    if (
        len(set(internal_order)) != len(internal_order)
        or len(set(artifact_order)) != len(artifact_order)
        or canonical_sha256_v1(internal_order)
        != expected_player.get("internal_player_id_order_sha256")
        or canonical_sha256_v1(artifact_order)
        != expected_player.get("artifact_player_id_order_sha256")
    ):
        _fail("suite player identity bridge order differs")
    return rows


def _probability_to_ppm(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{label} must be a finite probability")
    retained = float(value)
    if not math.isfinite(retained) or not 0.0 <= retained <= 1.0:
        _fail(f"{label} must lie in [0, 1]")
    # Suite simulations are exact proportions over 10,000 or 50,000 worlds,
    # so this conversion is exact at ppm resolution.  Round instead of
    # truncating to avoid binary floating-point representation drift.
    return int(round(retained * PROBABILITY_SCALE))


def _suite_modeled_probability_ppm(
    value: object, *, label: str, nested_prefixes: bool
) -> dict[str, dict[str, int]]:
    diagnostics = _mapping(value, label=label)
    modeled: dict[str, dict[str, int]] = {}
    if nested_prefixes:
        prefixes = _mapping(
            diagnostics.get("prefixes"), label=f"{label} prefixes"
        )
        if set(prefixes) != {str(prefix) for prefix in PREFIX_SIZES}:
            _fail(f"{label} prefix registry differs")
        sources = {}
        for prefix in PREFIX_SIZES:
            cell = _mapping(prefixes[str(prefix)], label=f"{label} K{prefix}")
            sources[str(prefix)] = _mapping(
                cell.get("simulated_p_max_at_least"),
                label=f"{label} K{prefix} probabilities",
            )
    else:
        probabilities = _mapping(
            diagnostics.get("simulated_p_book_max_at_least"),
            label=f"{label} probabilities",
        )
        # The retrieval crossing persists K80 diagnostics.  Prefix-specific
        # calibration for the exact selected order is reconstructed by the
        # decoded-artifact adapter; callers may not copy K80 onto K20/K40.
        sources = {str(PREFIX_SIZES[-1]): probabilities}
    for prefix, probabilities in sources.items():
        if not {str(value) for value in REALIZED_THRESHOLDS_DK} <= set(
            probabilities
        ):
            _fail(f"{label} threshold surface differs")
        modeled[prefix] = {
            str(threshold): _probability_to_ppm(
                probabilities[str(threshold)],
                label=f"{label} K{prefix} P(max>={threshold})",
            )
            for threshold in CALIBRATION_THRESHOLDS_DK
        }
    return modeled


def _artifact_from_suite_receipt(
    value: object, *, frozen_at: datetime | str, label: str
) -> dict[str, object]:
    receipt = _mapping(value, label=label)
    identity = _suite_world_identity(receipt, label=label)
    return build_create_once_artifact_v1(
        identity=identity,
        frozen_at=frozen_at,
        storage_created_at=receipt.get("gcs_time_created"),
    )


def _validate_suite_partial_world_binding(
    value: object, *, expected: Mapping[str, object], label: str
) -> None:
    receipt = _mapping(value, label=label)
    if set(receipt) != {
        "uri", "generation", "sha256", "gcs_time_created", "create_only"
    }:
        _fail(f"{label} fields differ")
    if receipt.get("create_only") is not True:
        _fail(f"{label} is not create-only")
    _parsed_timestamp(
        receipt.get("gcs_time_created"), label=f"{label} GCS creation time"
    )
    normalized_generation = str(receipt.get("generation"))
    if (
        receipt.get("uri") != expected["uri"]
        or normalized_generation != expected["generation"]
        or receipt.get("sha256") != expected["sha256"]
    ):
        _fail(f"{label} content identity differs")


def _suite_memberships(
    value: object,
) -> tuple[dict[str, dict[str, list[list[str]]]], dict[str, list[str]]]:
    memberships = _mapping(value, label="suite memberships")
    if set(memberships) != {str(value) for value in PREFIX_SIZES}:
        _fail("suite membership prefix registry differs")
    normalized: dict[str, dict[str, list[list[str]]]] = {}
    lineup_ids: dict[str, list[str]] = {arm: [] for arm in ARM_ORDER}
    for prefix in PREFIX_SIZES:
        by_arm = _mapping(
            memberships[str(prefix)], label=f"suite K{prefix} memberships"
        )
        if set(by_arm) != set(ARM_ORDER):
            _fail("suite membership arm order differs")
        normalized[str(prefix)] = {}
        for arm in ARM_ORDER:
            rosters = _sequence(
                by_arm[arm], label=f"suite {arm} K{prefix} memberships"
            )
            if len(rosters) != prefix:
                _fail(f"suite {arm} K{prefix} membership count differs")
            retained: list[list[str]] = []
            for raw_roster in rosters:
                roster = _sequence(raw_roster, label=f"suite {arm} roster")
                ids = [_string(value, label="suite roster player ID") for value in roster]
                if len(ids) != 9 or ids != sorted(ids) or len(set(ids)) != 9:
                    _fail(f"suite {arm} roster identity differs")
                retained.append(ids)
            normalized[str(prefix)][arm] = retained
            if prefix == PREFIX_SIZES[-1]:
                lineup_ids[arm] = [
                    f"lineup-v1-{canonical_sha256_v1(roster)}"
                    for roster in retained
                ]
    for arm in ARM_ORDER:
        if (
            normalized["20"][arm] != normalized["40"][arm][:20]
            or normalized["40"][arm] != normalized["80"][arm][:40]
        ):
            _fail(f"suite {arm} memberships are not exact nested prefixes")
    return normalized, lineup_ids


def build_suite_authority_v1(
    *,
    manifest: Mapping[str, object],
    terminal: Mapping[str, object],
    terminal_receipt: Mapping[str, object],
    manifest_storage_created_at: datetime | str | None = None,
    terminal_storage_created_at: datetime | str | None = None,
    world_storage_created_at_by_arm: Mapping[str, datetime | str] | None = None,
) -> dict[str, object]:
    """Bind the runner's manifest/terminal schemas and trusted GCS metadata."""

    manifest_doc = _mapping(manifest, label="suite manifest")
    terminal_doc = _mapping(terminal, label="suite terminal")
    _reject_prelock_carrier_fields(manifest_doc, label="suite manifest")
    _reject_prelock_carrier_fields(terminal_doc, label="suite terminal")
    if manifest_doc.get("schema_version") != SUITE_MANIFEST_SCHEMA:
        _fail("suite manifest schema differs")
    if terminal_doc.get("schema_version") != SUITE_TERMINAL_SCHEMA:
        _fail("suite terminal schema differs")
    _validate_self_hash(
        terminal_doc,
        field="terminal_receipt_sha256",
        label="suite terminal",
    )
    manifest_identity = _suite_object_receipt(
        terminal_doc.get("manifest"), label="suite manifest receipt"
    )
    terminal_identity = _suite_object_receipt(
        terminal_receipt, label="suite terminal receipt"
    )
    if (
        manifest_identity["sha256"] != canonical_sha256_v1(manifest_doc)
        or manifest_identity["bytes"]
        != len(canonical_json_bytes_v1(manifest_doc))
        or terminal_identity["sha256"] != canonical_sha256_v1(terminal_doc)
        or terminal_identity["bytes"]
        != len(canonical_json_bytes_v1(terminal_doc))
    ):
        _fail("suite terminal/manifest object content identity differs")
    prelock = _mapping(
        manifest_doc.get("prelock_receipt"), label="suite prelock receipt"
    )
    _validate_self_hash(
        prelock, field="receipt_sha256", label="suite prelock receipt"
    )
    registry = validate_registry(prelock.get("registry"))
    if (
        prelock.get("schema_version") != SUITE_PRELOCK_RECEIPT_SCHEMA
        or prelock.get("entries") != 80
        or prelock.get("prefixes") != list(PREFIX_SIZES)
        or prelock.get("thresholds") != list(REALIZED_THRESHOLDS_DK)
        or prelock.get("player_worlds_identical_across_all_arms") is not True
        or prelock.get("uses_realized_outcomes") is not False
        or prelock.get("post_lock_data_read") is not False
        or prelock.get("production_enabled") is not False
        or manifest_doc.get("registry_sha256") != registry["registry_sha256"]
    ):
        _fail("suite prelock fixed law differs")
    try:
        paired_native_input_authority = validate_paired_native_input_authority(
            prelock.get("paired_native_input_authority"),
            expected_arm_order=ARM_ORDER,
            expected_block_labels=_BLOCK_LABELS,
        )
    except ValueError as exc:
        raise ProspectiveGenerationShadowEvaluationError(
            "suite paired native input/source authority differs"
        ) from exc
    if (
        prelock.get("paired_native_input_authority_sha256")
        != paired_native_input_authority["authority_sha256"]
        or terminal_doc.get("paired_native_input_authority")
        != paired_native_input_authority
        or terminal_doc.get("paired_native_input_authority_sha256")
        != paired_native_input_authority["authority_sha256"]
    ):
        _fail("suite terminal paired native input/source binding differs")
    player_identity_bridge = _validated_suite_player_identity_bridge(
        manifest_doc,
        paired_native_input_authority=paired_native_input_authority,
    )
    try:
        audit_input_binding = validate_independent_audit_input_binding(
            prelock.get("independent_audit_input_binding"),
            paired_native_input_authority=paired_native_input_authority,
            expected_internal_player_ids=[
                row["internal_player_id"] for row in player_identity_bridge
            ],
        )
    except ValueError as exc:
        raise ProspectiveGenerationShadowEvaluationError(
            "suite independent audit input/source binding differs"
        ) from exc
    if (
        prelock.get("independent_audit_input_binding_sha256")
        != audit_input_binding["binding_sha256"]
        or manifest_doc.get("independent_audit_input_binding")
        != audit_input_binding
        or manifest_doc.get("independent_audit_input_binding_sha256")
        != audit_input_binding["binding_sha256"]
        or terminal_doc.get("independent_audit_input_binding")
        != audit_input_binding
        or terminal_doc.get("independent_audit_input_binding_sha256")
        != audit_input_binding["binding_sha256"]
    ):
        _fail("suite audit input binding carrier differs")
    shared_player_worlds_receipt = _suite_array_receipt(
        prelock.get("player_worlds_receipt"),
        label="suite shared player-world bank",
    )
    if (
        len(shared_player_worlds_receipt["shape"]) != 2
        or shared_player_worlds_receipt["shape"][1] != 50_000
    ):
        _fail("suite shared player-world bank is not exact five-by-10k")
    raw_audit_bank = _mapping(
        prelock.get("independent_audit_world_bank"),
        label="suite independent audit-bank receipt",
    )
    _validate_self_hash(
        raw_audit_bank,
        field="receipt_sha256",
        label="suite independent audit-bank receipt",
    )
    audit_world_bank_receipt = _suite_array_receipt(
        raw_audit_bank.get("world_bank_receipt"),
        label="suite independent audit world bank",
    )
    if (
        raw_audit_bank.get("schema_version") != AUDIT_BANK_SCHEMA
        or raw_audit_bank.get("world_seed") != 2_026_083_001
        or raw_audit_bank.get("world_count") != 10_000
        or audit_world_bank_receipt["shape"]
        != [shared_player_worlds_receipt["shape"][0], 10_000]
        or not _string(
            raw_audit_bank.get("model_version"),
            label="suite independent audit model version",
        )
        or not _digest(
            raw_audit_bank.get("player_order_sha256"),
            label="suite independent audit player order hash",
        )
        or raw_audit_bank.get("player_order_sha256")
        != paired_native_input_authority["effective_player_source_identity"][
            "internal_player_id_order_sha256"
        ]
        or raw_audit_bank.get("model_version")
        != paired_native_input_authority["effective_model_source_identity"][
            "model_version"
        ]
        or raw_audit_bank.get("input_binding") != audit_input_binding
        or raw_audit_bank.get("input_binding_sha256")
        != audit_input_binding["binding_sha256"]
        or raw_audit_bank.get("candidate_solves_run") != 0
        or raw_audit_bank.get("used_for_selection") is not False
        or raw_audit_bank.get("uses_realized_outcomes") is not False
        or raw_audit_bank.get("post_lock_data_read") is not False
        or prelock.get(
            "audit_world_bank_distinct_from_all_five_selection_blocks"
        ) is not True
        or prelock.get("audit_world_bank_used_for_selection") is not False
    ):
        _fail("suite independent audit-bank law differs")
    memberships, lineup_ids = _suite_memberships(prelock.get("memberships"))
    if prelock.get("memberships_sha256") != canonical_sha256_v1(memberships):
        _fail("suite membership hash differs")
    arm_receipts = _mapping(
        prelock.get("arm_receipts"), label="suite arm receipts"
    )
    if set(arm_receipts) != set(ARM_ORDER):
        _fail("suite arm receipt order differs")
    per_block_requested_work_by_arm: dict[str, object] = {}
    native_ledger_sha256_by_arm: dict[str, object] = {}
    native_transform_sha256_by_arm: dict[str, object] = {}
    base_modeled_probability_ppm_by_arm: dict[str, object] = {}
    reference_auxiliary_by_block: dict[str, dict[str, int]] = {}
    for arm in ARM_ORDER:
        receipt = _mapping(arm_receipts[arm], label=f"suite {arm} receipt")
        ledger_hashes = _mapping(
            receipt.get("native_exposure_ledger_sha256"),
            label=f"suite {arm} ledger hash grid",
        )
        candidate_matrix = _suite_array_receipt(
            receipt.get("candidate_matrix_receipt"),
            label=f"suite {arm} candidate score matrix",
        )
        candidate_count = _integer(
            receipt.get("candidate_count"),
            label=f"suite {arm} candidate count",
            minimum=80,
        )
        transform_hashes = _mapping(
            receipt.get("native_transform_receipt_sha256"),
            label=f"suite {arm} transform hash grid",
        )
        if (
            receipt.get("selected_count") != 80
            or candidate_count < 80
            or not _digest(
                receipt.get("candidate_order_sha256"),
                label=f"suite {arm} candidate order hash",
            )
            or receipt.get("selected_order_sha256")
            != canonical_sha256_v1(memberships["80"][arm])
            or candidate_matrix["shape"] != [candidate_count, 50_000]
            or set(ledger_hashes) != {"R0", "R1", "R2", "R3", "R4"}
            or set(transform_hashes) != {"R0", "R1", "R2", "R3", "R4"}
        ):
            _fail(f"suite {arm} book or ledger receipt differs")
        for seed_label, digest in ledger_hashes.items():
            _digest(digest, label=f"suite {arm}/{seed_label} ledger hash")
        work = _mapping(
            receipt.get("per_block_requested_work"),
            label=f"suite {arm} per-block work",
        )
        if set(work) != set(_BLOCK_LABELS):
            _fail(f"suite {arm} per-block work grid differs")
        native_ledger_sha256_by_arm[arm] = dict(ledger_hashes)
        native_transform_sha256_by_arm[arm] = {}
        expected_core = 400 if arm == "boom-dose-40-360" else 200
        expected_native_core = {
            "incumbent-160-40": {"leverage": 160, "boom": 40},
            "boom-first-40-160": {"leverage": 40, "boom": 160},
            "cross-law-40-100-60": {"leverage": 40, "boom": 100},
            "boom-dose-40-360": {"leverage": 40, "boom": 360},
            "ceiling-all-boom-0-200": {"leverage": 0, "boom": 0},
        }[arm]
        for block in _BLOCK_LABELS:
            block_work = _mapping(
                work[block], label=f"suite {arm}/{block} work"
            )
            if set(block_work) != {
                "unit", "native_ledger_sha256",
                "native_expected_requests_by_family", "native_status_counts",
                "native_duration_seconds_by_family",
                "native_total_duration_seconds", "transform_ledger_sha256",
                "transform_expected_requests_by_family",
                "transform_status_counts",
                "transform_duration_seconds_by_family",
                "requested_composite_core", "requested_role",
                "natural_uniqueness_collisions_failures_and_runtime_receipted",
            }:
                _fail(f"suite {arm}/{block} work fields differ")
            native_expected = {
                _string(family, label=f"suite {arm}/{block} native family"):
                _integer(
                    count,
                    label=f"suite {arm}/{block} native family request count",
                )
                for family, count in _mapping(
                    block_work.get("native_expected_requests_by_family"),
                    label=f"suite {arm}/{block} native request census",
                ).items()
            }
            for family, count in {
                **expected_native_core, "role_epistemic": 12
            }.items():
                if native_expected.get(family) != count:
                    _fail(f"suite {arm}/{block} native {family} census differs")
            auxiliary = {
                family: count for family, count in native_expected.items()
                if family not in {"leverage", "boom", "role_epistemic"}
            }
            if arm == ARM_ORDER[0]:
                reference_auxiliary_by_block[block] = auxiliary
            elif auxiliary != reference_auxiliary_by_block[block]:
                _fail(f"suite {arm}/{block} auxiliary census differs")
            native_status = _mapping(
                block_work.get("native_status_counts"),
                label=f"suite {arm}/{block} native status counts",
            )
            native_durations = _mapping(
                block_work.get("native_duration_seconds_by_family"),
                label=f"suite {arm}/{block} native family durations",
            )
            if any(
                type(count) is not int or count < 0
                for count in native_status.values()
            ) or set(native_durations) != set(native_expected) or any(
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(float(duration))
                or float(duration) < 0.0
                for duration in native_durations.values()
            ):
                _fail(f"suite {arm}/{block} native status/runtime differs")
            native_total = block_work.get("native_total_duration_seconds")
            if (
                isinstance(native_total, bool)
                or not isinstance(native_total, (int, float))
                or not math.isfinite(float(native_total))
                or float(native_total) < 0.0
                or not math.isclose(
                    float(native_total),
                    sum(float(value) for value in native_durations.values()),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            ):
                _fail(f"suite {arm}/{block} native total runtime differs")
            _digest(
                block_work.get("native_ledger_sha256"),
                label=f"suite {arm}/{block} native ledger hash",
            )
            transform_hash = block_work.get("transform_ledger_sha256")
            if transform_hash is not None:
                _digest(
                    transform_hash,
                    label=f"suite {arm}/{block} transform ledger hash",
                )
            if (
                block_work.get("unit")
                != "one-10000-world-generation-block"
                or block_work.get("requested_composite_core") != expected_core
                or block_work.get("requested_role") != 12
                or block_work.get(
                    "natural_uniqueness_collisions_failures_and_runtime_receipted"
                ) is not True
            ):
                _fail(f"suite {arm}/{block} work census differs")
            if block_work.get("native_ledger_sha256") != ledger_hashes[block]:
                _fail(f"suite {arm}/{block} native ledger authorities differ")
            raw_transform_hashes = _mapping(
                transform_hashes[block],
                label=f"suite {arm}/{block} transform receipt hashes",
            )
            expected_transform_key = (
                "cross_law_discovery"
                if arm == "cross-law-40-100-60"
                else "all_boom_ceiling"
                if arm == "ceiling-all-boom-0-200"
                else None
            )
            if set(raw_transform_hashes) != (
                {expected_transform_key} if expected_transform_key else set()
            ):
                _fail(f"suite {arm}/{block} transform receipt registry differs")
            if expected_transform_key is None:
                if transform_hash is not None:
                    _fail(f"suite {arm}/{block} has an undeclared transform ledger")
            elif transform_hash is None:
                _fail(f"suite {arm}/{block} transform ledger authority is absent")
            else:
                _digest(
                raw_transform_hashes[expected_transform_key],
                label=f"suite {arm}/{block} transform receipt hash",
                )
            transform_expected = _mapping(
                block_work.get("transform_expected_requests_by_family"),
                label=f"suite {arm}/{block} transform request census",
            )
            expected_transform_census = (
                {"boom:xlaw": 60}
                if arm == "cross-law-40-100-60"
                else {"boom": 200}
                if arm == "ceiling-all-boom-0-200"
                else {}
            )
            if transform_expected != expected_transform_census:
                _fail(f"suite {arm}/{block} transform request census differs")
            transform_status = _mapping(
                block_work.get("transform_status_counts"),
                label=f"suite {arm}/{block} transform status counts",
            )
            transform_durations = _mapping(
                block_work.get("transform_duration_seconds_by_family"),
                label=f"suite {arm}/{block} transform family durations",
            )
            if (
                any(
                    type(count) is not int or count < 0
                    for count in transform_status.values()
                )
                or set(transform_durations) != {
                    family for family, count in transform_expected.items()
                    if count > 0
                }
                or any(
                    isinstance(duration, bool)
                    or not isinstance(duration, (int, float))
                    or not math.isfinite(float(duration))
                    or float(duration) < 0.0
                    for duration in transform_durations.values()
                )
            ):
                _fail(f"suite {arm}/{block} transform status/runtime differs")
            native_transform_sha256_by_arm[arm][block] = dict(
                raw_transform_hashes
            )
        per_block_requested_work_by_arm[arm] = work
        # Calibration is scored only on the distinct audit bank.  The
        # selection-bank surface remains a mechanism diagnostic and is never
        # promoted into a calibration input.
        _suite_modeled_probability_ppm(
            receipt.get("simulated_diagnostics"),
            label=f"suite {arm} base-selection diagnostics",
            nested_prefixes=True,
        )
        base_modeled_probability_ppm_by_arm[arm] = (
            _suite_modeled_probability_ppm(
                receipt.get("independent_audit_diagnostics"),
                label=f"suite {arm} independent-audit diagnostics",
                nested_prefixes=True,
            )
        )
    selected_supply_trace = _mapping(
        prelock.get("cross_law_selected_supply_trace"),
        label="suite cross-law selected-supply trace",
    )
    _validate_self_hash(
        selected_supply_trace,
        field="trace_sha256",
        label="suite cross-law selected-supply trace",
    )
    selected_supply_trace_sha256 = selected_supply_trace["trace_sha256"]
    if (
        prelock.get("cross_law_selected_supply_trace_sha256")
        != selected_supply_trace_sha256
        or terminal_doc.get("cross_law_selected_supply_trace")
        != selected_supply_trace
        or terminal_doc.get("cross_law_selected_supply_trace_sha256")
        != selected_supply_trace_sha256
        or any(
            _mapping(
                arm_receipts[arm], label=f"suite {arm} receipt"
            ).get("cross_law_selected_supply_trace_sha256")
            != (
                selected_supply_trace_sha256
                if arm == "cross-law-40-100-60"
                else None
            )
            for arm in ARM_ORDER
        )
    ):
        _fail("suite cross-law selected-supply binding differs")
    world_manifest = _mapping(
        manifest_doc.get("world_artifacts"), label="suite manifest worlds"
    )
    world_terminal = _mapping(
        terminal_doc.get("world_artifacts"), label="suite terminal worlds"
    )
    if set(world_manifest) != set(ARM_ORDER) or set(world_terminal) != set(
        ARM_ORDER
    ):
        _fail("suite world-artifact arm order differs")
    world_identities: dict[str, dict[str, object]] = {}
    for arm in ARM_ORDER:
        manifest_world = _suite_world_identity(
            world_manifest[arm], label=f"suite manifest {arm} world"
        )
        terminal_world = _suite_world_identity(
            world_terminal[arm], label=f"suite terminal {arm} world"
        )
        if manifest_world != terminal_world:
            _fail(f"suite {arm} terminal world binding differs")
        _reject_prelock_carrier_identity(
            manifest_world, label=f"suite {arm} world"
        )
        world_identities[arm] = manifest_world
    if len({_identity_key(identity) for identity in world_identities.values()}) != len(
        ARM_ORDER
    ):
        _fail("suite arm bundle identities are not unique")
    for field in (
        "run_id", "season", "week", "draft_group_id", "code_sha",
        "image_source_commit_sha", "image_uri", "registry_sha256",
        "slate_lock_at",
    ):
        if terminal_doc.get(field) != manifest_doc.get(field):
            _fail(f"suite terminal/manifest context differs at {field}")
    if (
        terminal_doc.get("complete") is not True
        or terminal_doc.get("memberships_sha256")
        != prelock.get("memberships_sha256")
        or any(document.get("uses_realized_outcomes") is not False for document in (
            manifest_doc, terminal_doc
        ))
        or any(document.get("post_lock_data_read") is not False for document in (
            manifest_doc, terminal_doc
        ))
        or any(document.get("production_enabled") is not False for document in (
            manifest_doc, terminal_doc
        ))
    ):
        _fail("suite terminal score-blind completion law differs")
    crossing = _mapping(
        prelock.get("generation_retrieval_crossing"),
        label="suite generation x retrieval crossing",
    )
    _validate_self_hash(
        crossing, field="receipt_sha256",
        label="suite generation x retrieval crossing",
    )
    crossing_audit = _mapping(
        crossing.get("independent_score_only_audit_bank"),
        label="suite retrieval-crossing independent audit bank",
    )
    crossing_audit_receipt = _suite_array_receipt(
        crossing_audit.get("player_world_matrix_receipt"),
        label="suite retrieval-crossing audit matrix",
    )
    if (
        crossing.get("schema_version")
        != "prospective-generation-retrieval-crossing/v1"
        or crossing.get("population_order") != list(_RETRIEVAL_CROSSING_ARMS)
        or crossing.get("retrieval_order")
        != [_BASE_RETRIEVAL_ID, _CAP4_RETRIEVAL_ID]
        or crossing.get("entry_budget") != 80
        or crossing.get("report_thresholds") != list(REALIZED_THRESHOLDS_DK)
        or crossing.get("candidate_solves_requested_by_crossing") != 0
        or crossing.get("shared_generation_exposure_ledger_modified") is not False
        or crossing.get("uses_realized_outcomes") is not False
        or crossing.get("post_lock_data_read") is not False
        or crossing_audit_receipt != audit_world_bank_receipt
        or crossing_audit.get("world_count") != 10_000
        or crossing_audit.get("used_for_selection") is not False
        or crossing_audit.get("distinct_from_every_selection_block") is not True
    ):
        _fail("suite generation x retrieval fixed law differs")
    crossing_populations = _mapping(
        crossing.get("populations"), label="suite retrieval populations"
    )
    if set(crossing_populations) != set(_RETRIEVAL_CROSSING_ARMS):
        _fail("suite retrieval population order differs")
    retrieval_lineup_ids: dict[str, dict[str, list[str]]] = {}
    candidate_lineup_ids: dict[str, list[str]] = {}
    cap4_modeled_probability_ppm_by_population: dict[str, object] = {}
    for population in _RETRIEVAL_CROSSING_ARMS:
        population_receipt = _mapping(
            crossing_populations[population],
            label=f"suite retrieval population {population}",
        )
        candidates = _lineup_ids(
            population_receipt.get("candidate_lineup_ids"),
            label=f"suite {population} retrieval candidates",
            minimum=80,
        )
        if (
            population_receipt.get("candidate_lineup_ids_sha256")
            != canonical_sha256_v1(candidates)
            or population_receipt.get("candidate_count") != len(candidates)
            or population_receipt.get("candidate_solves_requested_by_crossing") != 0
            or population_receipt.get(
                "same_candidate_pool_for_both_official_retrievals"
            ) is not True
        ):
            _fail(f"suite {population} retrieval population differs")
        retrievals = _mapping(
            population_receipt.get("retrievals"),
            label=f"suite {population} retrieval books",
        )
        if set(retrievals) != {_BASE_RETRIEVAL_ID, _CAP4_RETRIEVAL_ID}:
            _fail(f"suite {population} retrieval order differs")
        retrieval_lineup_ids[population] = {}
        for retrieval_id in (_BASE_RETRIEVAL_ID, _CAP4_RETRIEVAL_ID):
            book = _mapping(
                retrievals[retrieval_id],
                label=f"suite {population}/{retrieval_id} book",
            )
            selected_ids = _lineup_ids(
                book.get("selected_lineup_ids"),
                label=f"suite {population}/{retrieval_id} selected IDs",
                minimum=80,
            )
            if (
                len(selected_ids) != 80
                or not set(selected_ids) <= set(candidates)
                or book.get("selected_lineup_ids_sha256")
                != canonical_sha256_v1(selected_ids)
                or book.get("uses_realized_outcomes") is not False
                or book.get("post_lock_data_read") is not False
            ):
                _fail(f"suite {population}/{retrieval_id} book differs")
            retrieval_lineup_ids[population][retrieval_id] = selected_ids
            _suite_modeled_probability_ppm(
                book.get("simulated_diagnostics"),
                label=f"suite {population}/{retrieval_id} diagnostics",
                nested_prefixes=False,
            )
            audit_modeled = _suite_modeled_probability_ppm(
                book.get("independent_audit_diagnostics"),
                label=(
                    f"suite {population}/{retrieval_id} independent-audit "
                    "diagnostics"
                ),
                nested_prefixes=True,
            )
            if retrieval_id == _BASE_RETRIEVAL_ID and audit_modeled != (
                base_modeled_probability_ppm_by_arm[population]
            ):
                _fail(f"suite {population} base audit diagnostics differ")
            if retrieval_id == _CAP4_RETRIEVAL_ID:
                cap4_modeled_probability_ppm_by_population[population] = (
                    audit_modeled
                )
        if retrieval_lineup_ids[population][_BASE_RETRIEVAL_ID] != lineup_ids[
            population
        ]:
            _fail(f"suite {population} incumbent book authorities differ")
        candidate_lineup_ids[population] = candidates
    if (
        prelock.get("generation_retrieval_crossing_sha256")
        != crossing["receipt_sha256"]
        or terminal_doc.get("generation_retrieval_crossing_sha256")
        != crossing["receipt_sha256"]
    ):
        _fail("suite generation x retrieval authority differs")
    generated = _canonical_timestamp(
        manifest_doc.get("generated_at"), label="suite generated-at"
    )
    lock = _canonical_timestamp(
        manifest_doc.get("slate_lock_at"), label="suite slate lock"
    )
    manifest_created = _canonical_timestamp(
        terminal_doc["manifest"]["gcs_time_created"],
        label="suite manifest storage-created-at",
    )
    terminal_created = _canonical_timestamp(
        terminal_receipt["gcs_time_created"],
        label="suite terminal storage-created-at",
    )
    world_created = {
        arm: _canonical_timestamp(
            world_terminal[arm]["gcs_time_created"],
            label=f"suite {arm} world storage-created-at",
        )
        for arm in ARM_ORDER
    }
    generated_dt = datetime.fromisoformat(generated)
    manifest_created_dt = datetime.fromisoformat(manifest_created)
    terminal_created_dt = datetime.fromisoformat(terminal_created)
    lock_dt = datetime.fromisoformat(lock)
    if (
        any(datetime.fromisoformat(value) < generated_dt for value in world_created.values())
        or manifest_created_dt < generated_dt
        or terminal_created_dt < manifest_created_dt
        or terminal_created_dt >= lock_dt
        or any(datetime.fromisoformat(value) >= lock_dt for value in world_created.values())
    ):
        _fail("suite storage creation chronology differs")
    if manifest_storage_created_at is not None and _canonical_timestamp(
        manifest_storage_created_at, label="supplied manifest creation time"
    ) != manifest_created:
        _fail("supplied manifest storage metadata differs")
    if terminal_storage_created_at is not None and _canonical_timestamp(
        terminal_storage_created_at, label="supplied terminal creation time"
    ) != terminal_created:
        _fail("supplied terminal storage metadata differs")
    if world_storage_created_at_by_arm is not None and {
        arm: _canonical_timestamp(
            world_storage_created_at_by_arm[arm],
            label=f"supplied {arm} world creation time",
        ) for arm in ARM_ORDER
    } != world_created:
        _fail("supplied world storage metadata differs")
    audit_manifest = _mapping(
        manifest_doc.get("independent_audit_world_artifact"),
        label="suite manifest audit world artifact",
    )
    audit_terminal = _mapping(
        terminal_doc.get("independent_audit_world_artifact"),
        label="suite terminal audit world artifact",
    )
    audit_identity = _suite_world_identity(
        audit_manifest, label="suite independent audit world artifact"
    )
    if audit_identity != _suite_world_identity(
        audit_terminal, label="suite terminal audit world artifact"
    ) or audit_identity in world_identities.values():
        _fail("suite independent audit-world identity differs")
    audit_created = _canonical_timestamp(
        audit_terminal.get("gcs_time_created"),
        label="suite audit world storage-created-at",
    )
    if not generated_dt <= datetime.fromisoformat(audit_created) < lock_dt:
        _fail("suite audit world was not created prelock")
    if (
        audit_identity["sha256"] != audit_manifest.get("sha256")
        or audit_world_bank_receipt["sha256"]
        == shared_player_worlds_receipt["sha256"]
    ):
        _fail("suite independent audit bank/artifact binding differs")

    discovery_manifest = _mapping(
        manifest_doc.get("cross_law_discovery_world_artifacts"),
        label="suite cross-law discovery artifacts",
    )
    discovery_terminal = _mapping(
        terminal_doc.get("cross_law_discovery_world_artifacts"),
        label="suite terminal cross-law discovery artifacts",
    )
    if set(discovery_manifest) != set(_BLOCK_LABELS) or set(
        discovery_terminal
    ) != set(_BLOCK_LABELS):
        _fail("suite cross-law discovery artifact grid differs")
    discovery_identities: dict[str, dict[str, object]] = {}
    discovery_created: dict[str, str] = {}
    occupied_identities = {
        _identity_key(identity) for identity in world_identities.values()
    } | {_identity_key(audit_identity)}
    for block in _BLOCK_LABELS:
        manifest_identity_for_block = _suite_world_identity(
            discovery_manifest[block],
            label=f"suite cross-law {block} discovery artifact",
        )
        terminal_identity_for_block = _suite_world_identity(
            discovery_terminal[block],
            label=f"suite terminal cross-law {block} discovery artifact",
        )
        if manifest_identity_for_block != terminal_identity_for_block:
            _fail(f"suite cross-law {block} discovery binding differs")
        key = _identity_key(manifest_identity_for_block)
        if key in occupied_identities:
            _fail("suite discovery/audit/selection artifact identity is reused")
        occupied_identities.add(key)
        created = _canonical_timestamp(
            _mapping(
                discovery_terminal[block],
                label=f"suite terminal cross-law {block} discovery receipt",
            ).get("gcs_time_created"),
            label=f"suite cross-law {block} discovery storage-created-at",
        )
        if not generated_dt <= datetime.fromisoformat(created) < lock_dt:
            _fail(f"suite cross-law {block} discovery artifact is not prelock")
        discovery_identities[block] = manifest_identity_for_block
        discovery_created[block] = created

    persistence = _mapping(
        manifest_doc.get("cross_law_persistence_binding"),
        label="suite cross-law persistence binding",
    )
    terminal_persistence = _mapping(
        terminal_doc.get("cross_law_persistence_binding"),
        label="suite terminal cross-law persistence binding",
    )
    if terminal_persistence != persistence:
        _fail("suite cross-law persistence terminal binding differs")
    _validate_self_hash(
        persistence,
        field="binding_sha256",
        label="suite cross-law persistence binding",
    )
    influence = _mapping(
        persistence.get("per_block_influence_trace_sha256"),
        label="suite cross-law influence trace grid",
    )
    if (
        persistence.get("schema_version")
        != "prospective-cross-law-persisted-world-binding/v1"
        or set(influence) != set(_BLOCK_LABELS)
        or persistence.get("selected_supply_trace_sha256")
        != selected_supply_trace_sha256
        or any(
            persistence.get(field) is not expected
            for field, expected in {
                "discovery_worlds_used_for_generation_only": True,
                "all_selection_scores_from_untouched_base_bank": True,
                "audit_worlds_used_for_selection": False,
                "all_objects_create_only_and_prelock": True,
                "uses_realized_outcomes": False,
            }.items()
        )
    ):
        _fail("suite cross-law persistence law differs")
    for block in _BLOCK_LABELS:
        _digest(
            influence[block],
            label=f"suite cross-law {block} influence trace hash",
        )
    _validate_suite_partial_world_binding(
        persistence.get("base_selection_world_artifact"),
        expected=world_identities["cross-law-40-100-60"],
        label="suite cross-law persisted base-selection artifact",
    )
    _validate_suite_partial_world_binding(
        persistence.get("independent_audit_world_artifact"),
        expected=audit_identity,
        label="suite cross-law persisted audit artifact",
    )
    persistence_discovery = _mapping(
        persistence.get("discovery_generation_world_artifacts"),
        label="suite persisted discovery artifacts",
    )
    if set(persistence_discovery) != set(_BLOCK_LABELS):
        _fail("suite cross-law persistence object binding differs")
    for block in _BLOCK_LABELS:
        _validate_suite_partial_world_binding(
            persistence_discovery[block],
            expected=discovery_identities[block],
            label=f"suite persisted cross-law {block} discovery artifact",
        )
    body: dict[str, object] = {
        "schema_version": SUITE_AUTHORITY_SCHEMA,
        "manifest": manifest_doc,
        "terminal": terminal_doc,
        "manifest_identity": manifest_identity,
        "terminal_identity": terminal_identity,
        "generated_at": generated,
        "slate_lock_at": lock,
        "manifest_storage_created_at": manifest_created,
        "terminal_storage_created_at": terminal_created,
        "world_artifact_identities": world_identities,
        "world_storage_created_at_by_arm": world_created,
        "shared_player_worlds_receipt": shared_player_worlds_receipt,
        "per_block_requested_work_by_arm": per_block_requested_work_by_arm,
        "native_exposure_ledger_sha256_by_arm": native_ledger_sha256_by_arm,
        "native_transform_receipt_sha256_by_arm": (
            native_transform_sha256_by_arm
        ),
        "paired_native_input_authority": paired_native_input_authority,
        "player_identity_bridge": player_identity_bridge,
        "cross_law_selected_supply_trace": selected_supply_trace,
        "base_modeled_probability_ppm_by_arm": (
            base_modeled_probability_ppm_by_arm
        ),
        "calibration_probability_source": (
            "independent-score-only-audit-world-bank"
        ),
        "independent_audit_world_artifact_identity": audit_identity,
        "independent_audit_world_storage_created_at": audit_created,
        "independent_audit_world_bank_receipt": raw_audit_bank,
        "independent_audit_input_binding": audit_input_binding,
        "cross_law_discovery_world_artifact_identities": (
            discovery_identities
        ),
        "cross_law_discovery_world_storage_created_at": discovery_created,
        "cross_law_persistence_binding": persistence,
        "membership_lineup_ids_by_arm": lineup_ids,
        "candidate_lineup_ids_by_retrieval_population": candidate_lineup_ids,
        "retrieval_lineup_ids_by_population": retrieval_lineup_ids,
        "cap4_modeled_probability_ppm_by_population": (
            cap4_modeled_probability_ppm_by_population
        ),
        "storage_metadata_authority": "google-cloud-storage-object-metadata",
        "complete": True,
    }
    return _with_hash(body, field="suite_authority_sha256")


def validate_suite_authority_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="suite authority")
    fields = {
        "schema_version", "manifest", "terminal", "manifest_identity",
        "terminal_identity", "generated_at", "manifest_storage_created_at",
        "terminal_storage_created_at", "slate_lock_at", "world_artifact_identities",
        "world_storage_created_at_by_arm", "shared_player_worlds_receipt",
        "per_block_requested_work_by_arm",
        "native_exposure_ledger_sha256_by_arm",
        "native_transform_receipt_sha256_by_arm",
        "paired_native_input_authority",
        "player_identity_bridge",
        "cross_law_selected_supply_trace",
        "base_modeled_probability_ppm_by_arm",
        "calibration_probability_source",
        "membership_lineup_ids_by_arm",
        "independent_audit_world_artifact_identity",
        "independent_audit_world_storage_created_at",
        "independent_audit_world_bank_receipt",
        "independent_audit_input_binding",
        "cross_law_discovery_world_artifact_identities",
        "cross_law_discovery_world_storage_created_at",
        "cross_law_persistence_binding",
        "candidate_lineup_ids_by_retrieval_population",
        "retrieval_lineup_ids_by_population",
        "cap4_modeled_probability_ppm_by_population",
        "storage_metadata_authority", "complete", "suite_authority_sha256",
    }
    if set(item) != fields:
        _fail("suite authority fields differ")
    _validate_self_hash(item, field="suite_authority_sha256", label="suite authority")
    terminal = _mapping(item.get("terminal"), label="suite terminal")
    receipt = {
        **normalize_object_identity_v1(
            item.get("terminal_identity"), label="suite terminal identity"
        ),
        "gcs_time_created": item.get("terminal_storage_created_at"),
        "precedes_slate_lock": True,
        "create_only": True,
    }
    rebuilt = build_suite_authority_v1(
        manifest=_mapping(item.get("manifest"), label="suite manifest"),
        terminal=terminal,
        terminal_receipt=receipt,
    )
    if rebuilt != item:
        _fail("suite authority normalized projection differs")
    return item


def _decoded_lineup_ids_and_scores(
    decoded: Mapping[str, object], *, arm_id: str
) -> tuple[list[str], dict[str, object]]:
    """Validate decoder output and retain only score-blind roster/world data."""

    try:
        import numpy as np
        from .prospective_boom_first import _array_receipt
    except ImportError as exc:  # pragma: no cover - project runtime dependency
        raise ProspectiveGenerationShadowEvaluationError(
            "decoded suite artifacts require numpy"
        ) from exc
    metadata = _mapping(
        decoded.get("metadata"), label=f"decoded {arm_id} metadata"
    )
    _reject_prelock_carrier_fields(
        metadata, label=f"decoded {arm_id} metadata"
    )
    if (
        metadata.get("artifact_version") != "prospective-recourse-worlds-v1"
        or metadata.get("uses_post_decision_outcomes") is not False
    ):
        _fail(f"decoded {arm_id} artifact contract differs")
    player_ids_array = np.asarray(decoded.get("player_ids")).astype(str)
    draws = np.asarray(decoded.get("player_draws"), dtype=np.float32)
    if (
        player_ids_array.ndim != 1
        or len(set(player_ids_array.tolist())) != len(player_ids_array)
        or draws.ndim != 2
        or draws.shape[0] != len(player_ids_array)
        or draws.shape[1] != 50_000
        or not np.isfinite(draws).all()
    ):
        _fail(f"decoded {arm_id} player-world bank differs")
    raw_rosters = _sequence(
        decoded.get("candidate_rosters"),
        label=f"decoded {arm_id} candidate rosters",
    )
    rosters: list[list[str]] = []
    player_universe = set(player_ids_array.tolist())
    for ordinal, raw_roster in enumerate(raw_rosters):
        roster = [
            _string(value, label=f"decoded {arm_id} roster player ID")
            for value in _sequence(
                raw_roster, label=f"decoded {arm_id} roster[{ordinal}]"
            )
        ]
        if (
            len(roster) != 9
            or roster != sorted(roster)
            or len(set(roster)) != 9
            or not set(roster) <= player_universe
        ):
            _fail(f"decoded {arm_id} candidate roster differs")
        rosters.append(roster)
    lineup_ids = [
        f"lineup-v1-{canonical_sha256_v1(roster)}" for roster in rosters
    ]
    if len(set(lineup_ids)) != len(lineup_ids):
        _fail(f"decoded {arm_id} candidate pool repeats")
    return lineup_ids, {
        "metadata": metadata,
        "player_ids": player_ids_array,
        "player_draws": draws,
        "candidate_rosters": rosters,
        "world_receipt": _array_receipt(draws),
    }


def _decoded_modeled_probability_ppm(
    decoded_projection: Mapping[str, object],
    lineup_ids: Sequence[str],
    *,
    arm_id: str,
    label: str,
    score_world_projection: Mapping[str, object] | None = None,
) -> dict[str, dict[str, int]]:
    import numpy as np

    rosters = decoded_projection["candidate_rosters"]
    world_projection = (
        decoded_projection
        if score_world_projection is None
        else score_world_projection
    )
    player_ids = np.asarray(world_projection["player_ids"]).astype(str)
    draws = np.asarray(world_projection["player_draws"], dtype=np.float32)
    roster_by_id = {
        f"lineup-v1-{canonical_sha256_v1(roster)}": roster
        for roster in rosters
    }
    row_by_player = {
        player_id: ordinal for ordinal, player_id in enumerate(player_ids)
    }
    try:
        score_rows = np.stack([
            draws[[row_by_player[player_id] for player_id in roster_by_id[lineup_id]]]
            .sum(axis=0, dtype=np.float32)
            for lineup_id in lineup_ids
        ])
    except KeyError as exc:
        raise ProspectiveGenerationShadowEvaluationError(
            f"{arm_id} {label} escapes its decoded candidate/player bank"
        ) from exc
    modeled: dict[str, dict[str, int]] = {}
    for prefix in PREFIX_SIZES:
        maxima = score_rows[:prefix].max(axis=0)
        modeled[str(prefix)] = {
            str(threshold): int(
                np.count_nonzero(maxima >= float(threshold))
                * PROBABILITY_SCALE // maxima.size
            )
            for threshold in CALIBRATION_THRESHOLDS_DK
        }
    return _normalize_modeled_probabilities(
        modeled, operational_k=80, label=f"{arm_id} {label} probabilities"
    )


def _decoded_independent_audit_projection_v1(
    *,
    suite: Mapping[str, object],
    decoded_audit_artifact: Mapping[str, object],
) -> dict[str, object]:
    """Validate and project the exact score-only audit world artifact."""

    import numpy as np
    from .prospective_boom_first import _array_receipt

    decoded = _mapping(
        decoded_audit_artifact, label="decoded independent-audit artifact"
    )
    if _digest(
        decoded.get("sha256"), label="decoded independent-audit SHA-256"
    ) != suite["independent_audit_world_artifact_identity"]["sha256"]:
        _fail("decoded independent-audit artifact differs from suite authority")
    metadata = _mapping(
        decoded.get("metadata"), label="decoded independent-audit metadata"
    )
    _reject_prelock_carrier_fields(
        metadata, label="decoded independent-audit metadata"
    )
    context = _mapping(
        metadata.get("context"), label="decoded independent-audit context"
    )
    manifest = _mapping(suite.get("manifest"), label="suite manifest")
    if (
        metadata.get("artifact_version") != "prospective-recourse-worlds-v1"
        or metadata.get("uses_post_decision_outcomes") is not False
        or context.get("arm") != "independent-audit-world-bank"
        or any(
            context.get(field) != manifest.get(field)
            for field in (
                "season", "week", "draft_group_id", "run_id", "code_sha",
                "slate_lock_at",
            )
        )
    ):
        _fail("decoded independent-audit artifact context differs")
    batch_metadata = _mapping(
        metadata.get("candidate_batch_metadata"),
        label="decoded independent-audit candidate-batch metadata",
    )
    audit_receipt = _mapping(
        batch_metadata.get("audit_bank_receipt"),
        label="decoded independent-audit bank receipt",
    )
    _validate_self_hash(
        audit_receipt,
        field="receipt_sha256",
        label="decoded independent-audit bank receipt",
    )
    audit_input_binding = suite["independent_audit_input_binding"]
    if (
        audit_receipt != suite["independent_audit_world_bank_receipt"]
        or batch_metadata.get("artifact_role")
        != "independent-score-only-audit-world-bank"
        or batch_metadata.get("independent_audit_input_binding")
        != audit_input_binding
        or batch_metadata.get("independent_audit_input_binding_sha256")
        != audit_input_binding["binding_sha256"]
        or batch_metadata.get("candidate_solves_run") != 0
        or batch_metadata.get("used_for_selection") is not False
        or batch_metadata.get("uses_realized_outcomes") is not False
        or batch_metadata.get("post_lock_data_read") is not False
    ):
        _fail("decoded independent-audit input/source receipt differs")
    player_ids = np.asarray(decoded.get("player_ids")).astype(str)
    draws = np.asarray(decoded.get("player_draws"), dtype=np.float32)
    expected_receipt = suite["independent_audit_world_bank_receipt"][
        "world_bank_receipt"
    ]
    if (
        player_ids.ndim != 1
        or len(set(player_ids.tolist())) != len(player_ids)
        or draws.shape != (len(player_ids), 10_000)
        or not np.isfinite(draws).all()
        or _array_receipt(draws) != expected_receipt
        or canonical_sha256_v1(player_ids.tolist())
        != suite["paired_native_input_authority"][
            "effective_player_source_identity"
        ]["artifact_player_id_order_sha256"]
    ):
        _fail("decoded independent-audit world matrix differs")
    return {"player_ids": player_ids, "player_draws": draws}


def _decoded_suite_arm_freezes_v2(
    *,
    suite: Mapping[str, object],
    decoded_arm_artifacts: Mapping[str, Mapping[str, object]],
    decoded_audit_artifact: Mapping[str, object],
    seed_crossing_sha256: str,
) -> list[dict[str, object]]:
    import numpy as np

    if set(decoded_arm_artifacts) != set(ARM_ORDER):
        _fail("decoded suite arm-artifact grid differs")
    manifest = _mapping(suite.get("manifest"), label="suite manifest")
    prelock = _mapping(
        manifest.get("prelock_receipt"), label="suite prelock receipt"
    )
    manifest_worlds = _mapping(
        manifest.get("world_artifacts"), label="suite manifest worlds"
    )
    arm_receipts = _mapping(
        prelock.get("arm_receipts"), label="suite arm receipts"
    )
    audit_projection = _decoded_independent_audit_projection_v1(
        suite=suite, decoded_audit_artifact=decoded_audit_artifact
    )
    try:
        paired_native_input_authority = validate_paired_native_input_authority(
            suite.get("paired_native_input_authority"),
            expected_arm_order=ARM_ORDER,
            expected_block_labels=_BLOCK_LABELS,
        )
    except ValueError as exc:
        raise ProspectiveGenerationShadowEvaluationError(
            "suite paired native input/source authority differs"
        ) from exc
    player_identity_bridge = _validated_suite_player_identity_bridge(
        manifest,
        paired_native_input_authority=paired_native_input_authority,
    )
    if suite.get("player_identity_bridge") != player_identity_bridge:
        _fail("suite player identity bridge authority differs")
    internal_player_id_by_dk_id = {
        str(row["dk_draftable_id"]): str(row["internal_player_id"])
        for row in player_identity_bridge
    }
    artifact_player_order = [
        str(row["dk_draftable_id"]) for row in player_identity_bridge
    ]
    reference_native_source = paired_native_input_authority[
        "native_source_projection"
    ]
    expected_artifact_player_order_sha256 = paired_native_input_authority[
        "effective_player_source_identity"
    ]["artifact_player_id_order_sha256"]
    shared_identity = suite["world_artifact_identities"][ARM_ORDER[0]]
    arms: list[dict[str, object]] = []
    for arm in ARM_ORDER:
        decoded = _mapping(
            decoded_arm_artifacts[arm], label=f"decoded {arm} artifact"
        )
        decoded_sha = _digest(
            decoded.get("sha256"), label=f"decoded {arm} artifact SHA-256"
        )
        expected_identity = suite["world_artifact_identities"][arm]
        if decoded_sha != expected_identity["sha256"]:
            _fail(f"decoded {arm} artifact differs from suite authority")
        candidate_ids, projection = _decoded_lineup_ids_and_scores(
            decoded, arm_id=arm
        )
        receipt = _mapping(arm_receipts[arm], label=f"suite {arm} receipt")
        if (
            len(candidate_ids) != receipt["candidate_count"]
            or canonical_sha256_v1(projection["candidate_rosters"])
            != receipt["candidate_order_sha256"]
            or projection["world_receipt"]
            != suite["shared_player_worlds_receipt"]
        ):
            _fail(f"decoded {arm} pool/world projection differs from suite")
        decoded_player_order = np.asarray(
            decoded.get("player_ids")
        ).astype(str).tolist()
        if (
            decoded_player_order != artifact_player_order
            or canonical_sha256_v1(decoded_player_order)
            != expected_artifact_player_order_sha256
        ):
            _fail(f"decoded {arm} effective player source order differs")
        metadata = projection["metadata"]
        context = _mapping(
            metadata.get("context"), label=f"decoded {arm} artifact context"
        )
        if any(
            context.get(field) != manifest.get(field)
            for field in (
                "season", "week", "draft_group_id", "run_id", "code_sha",
                "slate_lock_at",
            )
        ) or context.get("arm") != arm:
            _fail(f"decoded {arm} artifact context differs from suite")
        batch_metadata = _mapping(
            metadata.get("candidate_batch_metadata"),
            label=f"decoded {arm} candidate-batch metadata",
        )
        if (
            batch_metadata.get("portfolio") != "CBWU"
            or batch_metadata.get("world_blocks") != 5
            or batch_metadata.get("worlds_per_block") != [10_000] * 5
            or batch_metadata.get("uses_realized_outcomes", False) is not False
        ):
            _fail(f"decoded {arm} CBWU metadata differs")
        native_input_receipts = _mapping(
            batch_metadata.get("native_generation_receipts"),
            label=f"decoded {arm} native input/source receipt grid",
        )
        if set(native_input_receipts) != set(_BLOCK_LABELS):
            _fail(f"decoded {arm} native input/source block grid differs")
        for block in _BLOCK_LABELS:
            try:
                source_projection = native_input_source_projection(
                    native_input_receipts[block],
                    label=f"decoded {arm}/{block} native generation receipt",
                )
            except ValueError as exc:
                raise ProspectiveGenerationShadowEvaluationError(
                    f"decoded {arm}/{block} native input/source differs"
                ) from exc
            if (
                source_projection != reference_native_source
                or canonical_sha256_v1(source_projection)
                != paired_native_input_authority[
                    "native_source_projection_sha256_by_arm"
                ][arm][block]
            ):
                _fail(f"decoded {arm}/{block} native input/source drift")
        native_grid = _mapping(
            batch_metadata.get("native_generation_exposure_ledgers"),
            label=f"decoded {arm} native ledger grid",
        )
        transform_receipts = _mapping(
            batch_metadata.get("native_generation_transform_receipts"),
            label=f"decoded {arm} transform receipt grid",
        )
        if set(native_grid) != set(_BLOCK_LABELS) or set(
            transform_receipts
        ) != set(_BLOCK_LABELS):
            _fail(f"decoded {arm} ledger/transform block grid differs")
        ledger_grid: dict[str, object] = {}
        for block in _BLOCK_LABELS:
            native = exposure.validate_ledger(native_grid[block])
            suite_work = suite["per_block_requested_work_by_arm"][arm][block]
            if native["ledger_sha256"] != suite[
                "native_exposure_ledger_sha256_by_arm"
            ][arm][block]:
                _fail(f"decoded {arm}/{block} native ledger binding differs")
            if (
                native["expected_requests_by_family"]
                != suite_work["native_expected_requests_by_family"]
                or native["status_counts"] != suite_work["native_status_counts"]
                or native["duration_seconds_by_family"]
                != suite_work["native_duration_seconds_by_family"]
                or native["total_duration_seconds"]
                != suite_work["native_total_duration_seconds"]
            ):
                _fail(f"decoded {arm}/{block} native work/runtime differs")
            block_transforms = _mapping(
                transform_receipts[block],
                label=f"decoded {arm}/{block} transform receipts",
            )
            expected_transform_key = (
                "cross_law_discovery"
                if arm == "cross-law-40-100-60"
                else "all_boom_ceiling"
                if arm == "ceiling-all-boom-0-200"
                else None
            )
            if set(block_transforms) != (
                {expected_transform_key} if expected_transform_key else set()
            ):
                _fail(f"decoded {arm}/{block} transform registry differs")
            transform_ledger = None
            if expected_transform_key is not None:
                transform_receipt = _mapping(
                    block_transforms[expected_transform_key],
                    label=f"decoded {arm}/{block} transform receipt",
                )
                _validate_self_hash(
                    transform_receipt,
                    field="receipt_sha256",
                    label=f"decoded {arm}/{block} transform receipt",
                )
                expected_transform_receipt_hash = suite[
                    "native_transform_receipt_sha256_by_arm"
                ][arm][block][expected_transform_key]
                if (
                    transform_receipt["receipt_sha256"]
                    != expected_transform_receipt_hash
                ):
                    _fail(f"decoded {arm}/{block} transform receipt differs")
                ledger_field = (
                    "exposure_ledger"
                    if expected_transform_key == "cross_law_discovery"
                    else "solve_exposure_ledger"
                )
                transform_ledger = exposure.validate_ledger(
                    transform_receipt.get(ledger_field)
                )
                if transform_ledger["ledger_sha256"] != suite[
                    "per_block_requested_work_by_arm"
                ][arm][block]["transform_ledger_sha256"]:
                    _fail(f"decoded {arm}/{block} transform ledger differs")
                if (
                    transform_ledger["expected_requests_by_family"]
                    != suite_work["transform_expected_requests_by_family"]
                    or transform_ledger["status_counts"]
                    != suite_work["transform_status_counts"]
                    or transform_ledger["duration_seconds_by_family"]
                    != suite_work["transform_duration_seconds_by_family"]
                ):
                    _fail(f"decoded {arm}/{block} transform work/runtime differs")
                if expected_transform_key == "cross_law_discovery" and (
                    transform_receipt.get("production_influence_trace_sha256")
                    != suite["cross_law_persistence_binding"][
                        "per_block_influence_trace_sha256"
                    ][block]
                ):
                    _fail(f"decoded {arm}/{block} discovery trace differs")
            ledger_grid[block] = {
                "native": native,
                "transform": transform_ledger,
            }
        base_book = suite["membership_lineup_ids_by_arm"][arm]
        if not set(base_book) <= set(candidate_ids):
            _fail(f"decoded {arm} suite book escapes its candidate pool")
        if arm == "cross-law-40-100-60":
            candidate_source_blocks = [
                _string(
                    value,
                    label="decoded cross-law candidate source block",
                )
                for value in _sequence(
                    batch_metadata.get("candidate_source_blocks"),
                    label="decoded cross-law candidate source blocks",
                )
            ]
            candidate_internal_roster_sha256s: list[str] = []
            try:
                for roster in projection["candidate_rosters"]:
                    internal_roster = [
                        internal_player_id_by_dk_id[str(player_id)]
                        for player_id in roster
                    ]
                    candidate_internal_roster_sha256s.append(str(
                        exposure.roster_identity(internal_roster)[
                            "roster_sha256"
                        ]
                    ))
            except (KeyError, exposure.GenerationExposureError) as exc:
                raise ProspectiveGenerationShadowEvaluationError(
                    "decoded cross-law candidate identity bridge differs"
                ) from exc
            try:
                reopened_supply_trace = validate_selected_supply_trace(
                    suite.get("cross_law_selected_supply_trace"),
                    candidate_lineup_ids=candidate_ids,
                    candidate_internal_roster_sha256s=(
                        candidate_internal_roster_sha256s
                    ),
                    selected_lineup_ids=base_book,
                    candidate_source_blocks=candidate_source_blocks,
                    transform_receipts_by_block=transform_receipts,
                    block_labels=_BLOCK_LABELS,
                )
            except ValueError as exc:
                raise ProspectiveGenerationShadowEvaluationError(
                    "decoded cross-law selected-supply trace differs"
                ) from exc
            if reopened_supply_trace != suite[
                "cross_law_selected_supply_trace"
            ]:
                _fail("decoded cross-law selected-supply authority differs")
        base_modeled = _decoded_modeled_probability_ppm(
            projection,
            base_book,
            arm_id=arm,
            label="base retrieval independent audit",
            score_world_projection=audit_projection,
        )
        if base_modeled != suite["base_modeled_probability_ppm_by_arm"][arm]:
            _fail(f"decoded {arm} modeled base diagnostics differ")
        bundle_artifact = _artifact_from_suite_receipt(
            manifest_worlds[arm],
            frozen_at=suite["generated_at"],
            label=f"suite {arm} immutable bundle",
        )
        extra: dict[str, object] = {}
        if arm in _RETRIEVAL_CROSSING_ARMS:
            cap4_book = suite["retrieval_lineup_ids_by_population"][arm][
                _CAP4_RETRIEVAL_ID
            ]
            cap4_modeled = _decoded_modeled_probability_ppm(
                projection,
                cap4_book,
                arm_id=arm,
                label="cap-4 retrieval independent audit",
                score_world_projection=audit_projection,
            )
            if cap4_modeled != suite[
                "cap4_modeled_probability_ppm_by_population"
            ][arm]:
                _fail(f"decoded {arm} cap-4 audit diagnostics differ")
            extra = {
                "cap4_book_lineup_ids": cap4_book,
                "cap4_modeled_probability_ppm": cap4_modeled,
                "cap4_book_artifact": bundle_artifact,
            }
        arms.append(build_arm_freeze_v1(
            arm_id=arm,
            population_label=f"population:{arm}",
            cap_label=_BASE_RETRIEVAL_ID,
            operational_k=80,
            candidate_lineup_ids=candidate_ids,
            book_lineup_ids=base_book,
            modeled_probability_ppm=base_modeled,
            exposure_ledgers_by_block=ledger_grid,
            artifacts={
                component: bundle_artifact
                for component in (
                    "book", "candidate_pool", "exposure_ledger", "world"
                )
            },
            shared_simulation_identity=shared_identity,
            untouched_selection_bank_identity=shared_identity,
            seed_crossing_sha256=seed_crossing_sha256,
            **extra,
        ))
    return arms


def build_terminal_prelock_root_from_suite_v2(
    *,
    preregistration: Mapping[str, object],
    seed_crossing: Mapping[str, object],
    suite_authority: Mapping[str, object],
    decoded_arm_artifacts: Mapping[str, Mapping[str, object]],
    decoded_audit_artifact: Mapping[str, object],
    frozen_at: datetime | str | None = None,
    slate_id: str | None = None,
) -> dict[str, object]:
    """Build a runnable terminal root from the suite's real immutable bundles.

    Callers provide the already decoded, checksum-verified outputs of
    :func:`recourse_worlds.decode_recourse_world_artifact`; no synthetic
    component objects or hand-built arm freezes are accepted.
    """

    suite = validate_suite_authority_v1(suite_authority)
    seed = validate_seed_crossing_v1(seed_crossing)
    manifest = _mapping(suite["manifest"], label="suite manifest")
    arms = _decoded_suite_arm_freezes_v2(
        suite=suite,
        decoded_arm_artifacts=decoded_arm_artifacts,
        decoded_audit_artifact=decoded_audit_artifact,
        seed_crossing_sha256=seed["seed_crossing_sha256"],
    )
    retained_frozen_at = (
        suite["terminal_storage_created_at"]
        if frozen_at is None
        else frozen_at
    )
    retained_slate_id = (
        f"dk-{manifest['draft_group_id']}" if slate_id is None else slate_id
    )
    return build_terminal_prelock_root_v1(
        preregistration=preregistration,
        season=int(manifest["season"]),
        week=int(manifest["week"]),
        slate_id=retained_slate_id,
        frozen_at=retained_frozen_at,
        lock_at=suite["slate_lock_at"],
        seed_crossing=seed,
        suite_authority=suite,
        arms=arms,
    )


def build_terminal_prelock_root_v1(
    *,
    preregistration: Mapping[str, object],
    season: int,
    week: int,
    slate_id: str,
    frozen_at: datetime | str,
    lock_at: datetime | str,
    shared_simulation_artifact: Mapping[str, object] | None = None,
    untouched_selection_bank_artifact: Mapping[str, object] | None = None,
    independent_audit_world_artifact: Mapping[str, object] | None = None,
    seed_crossing: Mapping[str, object],
    suite_authority: Mapping[str, object],
    arms: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Seal all arms into one terminal score-blind root before slate lock."""

    prereg = validate_preregistration_v1(preregistration)
    if season != SEASON:
        _fail("terminal prelock root season differs")
    week_value = _integer(week, label="week", minimum=1)
    if week_value > FULL_SEASON_WEEK_COUNT:
        _fail("terminal prelock root week lies outside the regular season")
    frozen = _canonical_timestamp(frozen_at, label="root frozen-at")
    lock = _canonical_timestamp(lock_at, label="slate lock")
    if datetime.fromisoformat(frozen) >= datetime.fromisoformat(lock):
        _fail("terminal root was not frozen before slate lock")
    if week_value == 1 and lock != prereg["week1_lock_at"]:
        _fail("Week-1 root lock differs from the preregistered lock")
    seed = validate_seed_crossing_v1(seed_crossing)
    suite = validate_suite_authority_v1(suite_authority)
    normalized_arms = [validate_arm_freeze_v1(arm) for arm in arms]
    suite_manifest = suite["manifest"]
    assert isinstance(suite_manifest, Mapping)
    suite_worlds = _mapping(
        suite_manifest.get("world_artifacts"), label="suite manifest worlds"
    )
    suite_frozen_at = suite["generated_at"]
    if shared_simulation_artifact is None:
        shared_simulation_artifact = _artifact_from_suite_receipt(
            suite_worlds[ARM_ORDER[0]],
            frozen_at=suite_frozen_at,
            label="suite shared simulation bundle",
        )
    if untouched_selection_bank_artifact is None:
        untouched_selection_bank_artifact = _artifact_from_suite_receipt(
            suite_worlds[ARM_ORDER[0]],
            frozen_at=suite_frozen_at,
            label="suite untouched selection-bank bundle",
        )
    if independent_audit_world_artifact is None:
        independent_audit_world_artifact = _artifact_from_suite_receipt(
            suite_manifest.get("independent_audit_world_artifact"),
            frozen_at=suite_frozen_at,
            label="suite independent audit-world artifact",
        )
    body: dict[str, object] = {
        "schema_version": TERMINAL_PRELOCK_ROOT_SCHEMA,
        "complete": True,
        "season": SEASON,
        "week": week_value,
        "slate_id": _identifier(slate_id, label="slate ID"),
        "frozen_at": frozen,
        "lock_at": lock,
        "preregistration": prereg,
        "preregistration_sha256": prereg["preregistration_sha256"],
        "operational_k": prereg["operational_k"],
        "reporting_entry_counts": prereg["reporting_entry_counts"],
        "shared_simulation_artifact": dict(shared_simulation_artifact),
        "untouched_selection_bank_artifact": dict(
            untouched_selection_bank_artifact
        ),
        "independent_audit_world_artifact": dict(
            independent_audit_world_artifact
        ),
        "seed_crossing": seed,
        "seed_crossing_sha256": seed["seed_crossing_sha256"],
        "suite_authority": suite,
        "suite_authority_sha256": suite["suite_authority_sha256"],
        "arm_order": list(ARM_ORDER),
        "arms": normalized_arms,
        "arms_sha256": canonical_sha256_v1(normalized_arms),
        "one_shared_simulation": True,
        "one_untouched_selection_bank": True,
        "all_artifacts_create_once": True,
        "selection_completed_before_lock": True,
        "outcome_carrier_fields": [],
        "outcome_access_performed": False,
        "uses_post_lock_data": False,
        "production_change_licensed": False,
    }
    root = _with_hash(body, field="terminal_prelock_root_sha256")
    return validate_terminal_prelock_root_body_v1(root)


def validate_terminal_prelock_root_body_v1(value: object) -> dict[str, object]:
    root = _mapping(value, label="terminal prelock root")
    fields = {
        "schema_version", "complete", "season", "week", "slate_id",
        "frozen_at", "lock_at", "preregistration",
        "preregistration_sha256", "operational_k",
        "reporting_entry_counts", "shared_simulation_artifact",
        "untouched_selection_bank_artifact", "independent_audit_world_artifact",
        "seed_crossing",
        "seed_crossing_sha256", "suite_authority",
        "suite_authority_sha256", "arm_order", "arms", "arms_sha256",
        "one_shared_simulation", "one_untouched_selection_bank",
        "all_artifacts_create_once", "selection_completed_before_lock",
        "outcome_carrier_fields", "outcome_access_performed",
        "uses_post_lock_data", "production_change_licensed",
        "terminal_prelock_root_sha256",
    }
    if set(root) != fields:
        _fail("terminal prelock root fields differ")
    _validate_self_hash(
        root, field="terminal_prelock_root_sha256", label="terminal prelock root"
    )
    if (
        root.get("schema_version") != TERMINAL_PRELOCK_ROOT_SCHEMA
        or root.get("complete") is not True
        or root.get("season") != SEASON
        or root.get("arm_order") != list(ARM_ORDER)
        or any(root.get(field) is not True for field in (
            "one_shared_simulation", "one_untouched_selection_bank",
            "all_artifacts_create_once", "selection_completed_before_lock",
        ))
        or root.get("outcome_carrier_fields") != []
        or root.get("outcome_access_performed") is not False
        or root.get("uses_post_lock_data") is not False
        or root.get("production_change_licensed") is not False
    ):
        _fail("terminal prelock root fixed score-blind law differs")
    week = _integer(root.get("week"), label="root week", minimum=1)
    if week > FULL_SEASON_WEEK_COUNT:
        _fail("terminal prelock root week differs")
    _identifier(root.get("slate_id"), label="root slate ID")
    frozen = _parsed_timestamp(root.get("frozen_at"), label="root frozen-at")
    lock = _parsed_timestamp(root.get("lock_at"), label="root lock")
    if frozen >= lock:
        _fail("terminal prelock root was sealed at or after lock")
    prereg = validate_preregistration_v1(root.get("preregistration"))
    if (
        root.get("preregistration_sha256") != prereg["preregistration_sha256"]
        or root.get("operational_k") != prereg["operational_k"]
        or root.get("reporting_entry_counts") != prereg["reporting_entry_counts"]
        or (week == 1 and root.get("lock_at") != prereg["week1_lock_at"])
    ):
        _fail("terminal root preregistration binding differs")
    shared = _validate_artifact(
        root.get("shared_simulation_artifact"),
        label="shared simulation artifact", not_after=frozen,
    )
    selection = _validate_artifact(
        root.get("untouched_selection_bank_artifact"),
        label="untouched selection-bank artifact", not_after=frozen,
    )
    audit = _validate_artifact(
        root.get("independent_audit_world_artifact"),
        label="independent audit-world artifact", not_after=frozen,
    )
    if audit["identity"] in (shared["identity"], selection["identity"]):
        _fail("independent audit-world authority is not distinct")
    seed = validate_seed_crossing_v1(root.get("seed_crossing"))
    if root.get("seed_crossing_sha256") != seed["seed_crossing_sha256"]:
        _fail("terminal root seed-crossing binding differs")
    suite = validate_suite_authority_v1(root.get("suite_authority"))
    if (
        root.get("suite_authority_sha256") != suite["suite_authority_sha256"]
        or suite["manifest"].get("season") != root["season"]
        or suite["manifest"].get("week") != root["week"]
        or suite["slate_lock_at"] != root["lock_at"]
        or suite["independent_audit_world_artifact_identity"]
        != audit["identity"]
        or suite["independent_audit_world_storage_created_at"]
        != audit["storage_created_at"]
        or shared["identity"]
        != suite["world_artifact_identities"][ARM_ORDER[0]]
        or selection["identity"]
        != suite["world_artifact_identities"][ARM_ORDER[0]]
        or shared["storage_created_at"]
        != suite["world_storage_created_at_by_arm"][ARM_ORDER[0]]
        or selection["storage_created_at"]
        != suite["world_storage_created_at_by_arm"][ARM_ORDER[0]]
        or _parsed_timestamp(
            suite["terminal_storage_created_at"],
            label="suite terminal storage-created-at",
        ) > frozen
    ):
        _fail("terminal root suite authority binding differs")
    raw_arms = _sequence(root.get("arms"), label="terminal root arms")
    arms = [validate_arm_freeze_v1(arm) for arm in raw_arms]
    if (
        [arm["arm_id"] for arm in arms] != list(ARM_ORDER)
        or root.get("arms_sha256") != canonical_sha256_v1(arms)
    ):
        _fail("terminal root arm lattice is incomplete or reordered")
    population_cap = [
        (arm["population_label"], arm["cap_label"]) for arm in arms
    ]
    if len(set(population_cap)) != len(ARM_ORDER):
        _fail("terminal root repeats a population x cap label")
    auxiliary = arms[0]["auxiliary_requests_by_family"]
    for arm in arms:
        contract = _POLICY_BY_ARM[str(arm["arm_id"])]
        expected_per_block = (
            int(contract["core_requested_solve_count"])
            + 12
            + sum(int(value) for value in auxiliary.values())
        )
        if (
            arm["operational_k"] != prereg["operational_k"]
            or arm["shared_simulation_identity"] != shared["identity"]
            or arm["untouched_selection_bank_identity"] != selection["identity"]
            or arm["seed_crossing_sha256"] != seed["seed_crossing_sha256"]
            or arm["auxiliary_requests_by_family"] != auxiliary
            or arm["requested_solve_count_per_block"] != expected_per_block
            or arm["requested_solve_count_per_slate"]
            != expected_per_block * len(_BLOCK_LABELS)
        ):
            _fail("arm bank, seed, resource, or shared-auxiliary binding differs")
        if (
            arm["book_lineup_ids"]
            != suite["membership_lineup_ids_by_arm"][arm["arm_id"]]
            or arm["modeled_probability_ppm"]
            != suite["base_modeled_probability_ppm_by_arm"][arm["arm_id"]]
            or arm["calibration_probability_source"]
            != suite["calibration_probability_source"]
            or arm["artifacts"]["world"]["identity"]
            != suite["world_artifact_identities"][arm["arm_id"]]
            or arm["artifacts"]["world"]["storage_created_at"]
            != suite["world_storage_created_at_by_arm"][arm["arm_id"]]
        ):
            _fail("arm book/world projection differs from suite authority")
        if arm["arm_id"] in _RETRIEVAL_CROSSING_ARMS and (
            arm["candidate_lineup_ids"]
            != suite["candidate_lineup_ids_by_retrieval_population"][
                arm["arm_id"]
            ]
            or arm["retrieval_interaction"]["book_lineup_ids"]
            != suite["retrieval_lineup_ids_by_population"][arm["arm_id"]][
                _CAP4_RETRIEVAL_ID
            ]
            or arm["retrieval_interaction"]["modeled_probability_ppm"]
            != suite["cap4_modeled_probability_ppm_by_population"][
                arm["arm_id"]
            ]
        ):
            _fail("arm candidate/retrieval projection differs from suite authority")
        suite_work = suite["manifest"]["prelock_receipt"]["arm_receipts"][
            arm["arm_id"]
        ]["per_block_requested_work"]
        for block in _BLOCK_LABELS:
            work = suite_work[block]
            if (
                work["requested_composite_core"]
                != arm["requested_core_solve_count_per_block"]
                or work["requested_role"]
                != arm["requested_role_solve_count_per_block"]
                or work[
                    "natural_uniqueness_collisions_failures_and_runtime_receipted"
                ] is not True
            ):
                _fail("arm per-block work differs from suite authority")
        expected_bundle_identity = suite["world_artifact_identities"][
            arm["arm_id"]
        ]
        expected_bundle_created = suite["world_storage_created_at_by_arm"][
            arm["arm_id"]
        ]
        for name, descriptor in arm["artifacts"].items():
            artifact = _validate_artifact(
                descriptor, label=f"{arm['arm_id']} {name} artifact",
                not_after=frozen,
            )
            if (
                artifact["identity"] != expected_bundle_identity
                or artifact["storage_created_at"] != expected_bundle_created
            ):
                _fail(
                    f"{arm['arm_id']} {name} does not bind its immutable suite bundle"
                )
        retrieval = arm["retrieval_interaction"]
        if retrieval is not None:
            cap4_artifact = _validate_artifact(
                retrieval["book_artifact"],
                label=f"{arm['arm_id']} cap-4 book artifact",
                not_after=frozen,
            )
            if (
                cap4_artifact["identity"] != expected_bundle_identity
                or cap4_artifact["storage_created_at"]
                != expected_bundle_created
            ):
                _fail("retrieval book does not bind its immutable arm bundle")
        census_artifact = arm["preexisting_candidate_census_artifact"]
        if census_artifact is not None:
            census = _validate_artifact(
                census_artifact,
                label=f"{arm['arm_id']} preexisting candidate census",
                not_after=frozen,
            )
            if census["identity"] in (
                expected_bundle_identity,
                audit["identity"],
            ):
                _fail("preexisting candidate census reuses a suite authority")
    return root


def bind_terminal_prelock_root_v1(
    *,
    root: Mapping[str, object],
    uri: str,
    generation: str | int,
    storage_created_at: datetime | str,
) -> dict[str, object]:
    """Bind a canonical terminal body to its create-once object identity."""

    retained = validate_terminal_prelock_root_body_v1(root)
    raw = canonical_json_bytes_v1(retained)
    identity = normalize_object_identity_v1({
        "uri": uri,
        "generation": str(generation),
        "sha256": canonical_sha256_v1(retained),
        "bytes": len(raw),
    }, label="terminal prelock root identity")
    _reject_prelock_carrier_identity(identity, label="terminal prelock root")
    created = _canonical_timestamp(
        storage_created_at, label="terminal root storage-created-at"
    )
    frozen = _parsed_timestamp(retained["frozen_at"], label="root frozen-at")
    lock = _parsed_timestamp(retained["lock_at"], label="root lock")
    created_dt = datetime.fromisoformat(created)
    if not frozen <= created_dt < lock:
        _fail("terminal root storage creation is not inside the prelock window")
    body: dict[str, object] = {
        "schema_version": TERMINAL_PRELOCK_ENVELOPE_SCHEMA,
        "identity": identity,
        "create_once": True,
        "storage_created_at": created,
        "storage_metadata_authority": "google-cloud-storage-object-metadata",
        "terminal_prelock_root": retained,
        "terminal_prelock_root_sha256": retained[
            "terminal_prelock_root_sha256"
        ],
    }
    return _with_hash(body, field="terminal_prelock_envelope_sha256")


def validate_terminal_prelock_root_v1(value: object) -> dict[str, object]:
    """Validate the terminal envelope and return its normalized root body."""

    envelope = _mapping(value, label="terminal prelock envelope")
    if set(envelope) != {
        "schema_version", "identity", "create_once",
        "storage_created_at", "storage_metadata_authority",
        "terminal_prelock_root", "terminal_prelock_root_sha256",
        "terminal_prelock_envelope_sha256",
    }:
        _fail("terminal prelock envelope fields differ")
    _validate_self_hash(
        envelope, field="terminal_prelock_envelope_sha256",
        label="terminal prelock envelope",
    )
    root = validate_terminal_prelock_root_body_v1(
        envelope.get("terminal_prelock_root")
    )
    identity = normalize_object_identity_v1(
        envelope.get("identity"), label="terminal prelock root identity"
    )
    _reject_prelock_carrier_identity(identity, label="terminal prelock root")
    raw = canonical_json_bytes_v1(root)
    created = _parsed_timestamp(
        envelope.get("storage_created_at"),
        label="terminal root storage-created-at",
    )
    frozen = _parsed_timestamp(root["frozen_at"], label="root frozen-at")
    lock = _parsed_timestamp(root["lock_at"], label="root lock")
    if (
        envelope.get("schema_version") != TERMINAL_PRELOCK_ENVELOPE_SCHEMA
        or envelope.get("create_once") is not True
        or envelope.get("terminal_prelock_root_sha256")
        != root["terminal_prelock_root_sha256"]
        or identity["sha256"] != canonical_sha256_v1(root)
        or identity["bytes"] != len(raw)
        or envelope.get("storage_metadata_authority")
        != "google-cloud-storage-object-metadata"
        or not frozen <= created < lock
    ):
        _fail("terminal prelock envelope content identity differs")
    return root


def _normalize_contest_field_capture(value: object) -> dict[str, object]:
    capture = _mapping(value, label="contest field capture")
    identity_fields = (
        "payout_table_identity", "field_rosters_identity",
        "field_ownership_identity", "participant_strength_identity",
        "shadow_entry_mapping_identity",
    )
    base_fields = {
        "contest_id", "field_size", "entry_fee_micro", *identity_fields,
        "complete",
    }
    normalized_fields = base_fields | {
        "status", "evidence_scope", "contest_ev_claim_allowed",
        "complete_field_rank_claim_allowed",
        "allocation_recommendation_allowed",
    }
    if set(capture) not in (base_fields, normalized_fields):
        _fail("contest field-capture fields differ")
    normalized: dict[str, object] = {
        "contest_id": _identifier(
            capture.get("contest_id"), label="contest ID"
        ),
        "field_size": _integer(
            capture.get("field_size"), label="contest field size", minimum=2
        ),
        "entry_fee_micro": _integer(
            capture.get("entry_fee_micro"), label="contest entry fee"
        ),
    }
    identity_keys: set[tuple[object, ...]] = set()
    for field in identity_fields:
        identity = normalize_object_identity_v1(
            capture.get(field), label=field.replace("_", " ")
        )
        key = _identity_key(identity)
        if key in identity_keys:
            _fail("contest field capture reuses an authority identity")
        identity_keys.add(key)
        normalized[field] = identity
    if capture.get("complete") is not True:
        _fail("contest field capture is incomplete")
    contest_ev_allowed = (
        capture.get("contest_ev_claim_allowed") is True
        if set(capture) == normalized_fields
        else False
    )
    normalized.update({
        "complete": True,
        "status": "complete-contest-field-capture",
        "evidence_scope": (
            "raw-score-complete-field-ranks-and-entered-contest-ev"
            if contest_ev_allowed
            else "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
        ),
        "complete_field_rank_claim_allowed": True,
        "contest_ev_claim_allowed": contest_ev_allowed,
        "allocation_recommendation_allowed": False,
    })
    if set(capture) == normalized_fields and capture != normalized:
        _fail("contest field-capture evidence labels differ")
    return normalized


def build_outcome_snapshot_v1(
    *,
    season: int,
    week: int,
    slate_id: str,
    captured_at: datetime | str,
    outcome_source_identity: Mapping[str, object],
    realized_score_source_identity: Mapping[str, object],
    lineup_rows: Sequence[Mapping[str, object]],
    field_metrics_available: bool,
    contest_field_capture: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build an independent, post-event score snapshot for the grader.

    The snapshot deliberately has no prelock-root identity or arm field.  It
    can be produced without knowing which generation treatments will consume
    it.  When field data are unavailable, rank/duplicates/payout are absent,
    rather than silently filled.
    """

    if season != SEASON:
        _fail("outcome snapshot season differs")
    week_value = _integer(week, label="outcome week", minimum=1)
    if week_value > FULL_SEASON_WEEK_COUNT:
        _fail("outcome snapshot week differs")
    if type(field_metrics_available) is not bool:
        _fail("field-metrics availability must be explicit boolean")
    if field_metrics_available:
        if contest_field_capture is None:
            _fail("field metrics require complete contest-field capture")
        field_capture = _normalize_contest_field_capture(contest_field_capture)
    else:
        if contest_field_capture is not None:
            _fail("raw-score-only snapshot cannot carry contest-field capture")
        field_capture = {
            "status": "unavailable-raw-score-only",
            "evidence_scope": "raw-score-only-no-contest-ev",
            "complete_field_rank_claim_allowed": False,
            "contest_ev_claim_allowed": False,
            "allocation_recommendation_allowed": False,
            "complete": False,
        }
    captured = _canonical_timestamp(captured_at, label="outcome captured-at")
    slate = _identifier(slate_id, label="outcome slate ID")
    rows = []
    seen: set[str] = set()
    for ordinal, raw in enumerate(lineup_rows):
        row = _mapping(raw, label=f"outcome lineup[{ordinal}]")
        expected = {"lineup_id", "realized_score_micro"}
        if field_metrics_available:
            expected |= {
                "actual_field_rank", "actual_field_percentile_ppm",
                "counterfactual_field_rank",
                "counterfactual_field_percentile_ppm", "duplicates",
                "split_payout_micro", "entered_in_contest",
                "matching_entry_ids", "actual_split_payout_applicable",
            }
        if set(row) != expected:
            _fail("outcome lineup fields differ from availability declaration")
        lineup_id = _identifier(row.get("lineup_id"), label="outcome lineup ID")
        if lineup_id in seen:
            _fail("outcome snapshot repeats a lineup ID")
        seen.add(lineup_id)
        normalized: dict[str, object] = {
            "lineup_id": lineup_id,
            "realized_score_micro": _integer(
                row.get("realized_score_micro"),
                label=f"{lineup_id} realized score micro",
                minimum=-100_000_000,
            ),
        }
        if field_metrics_available:
            field_size = int(field_capture["field_size"])
            entered = row.get("entered_in_contest")
            applicable = row.get("actual_split_payout_applicable")
            if type(entered) is not bool or type(applicable) is not bool:
                _fail(f"{lineup_id} entered/payout applicability differs")
            counterfactual_rank = _integer(
                row.get("counterfactual_field_rank"),
                label=f"{lineup_id} counterfactual field rank",
                minimum=1,
            )
            if counterfactual_rank > field_size + 1:
                _fail(f"{lineup_id} counterfactual field rank exceeds insertion range")
            counterfactual_percentile = max(
                0,
                (field_size - counterfactual_rank) * PROBABILITY_SCALE
                // (field_size - 1),
            )
            retained_counterfactual_percentile = _integer(
                row.get("counterfactual_field_percentile_ppm"),
                label=f"{lineup_id} counterfactual field percentile",
            )
            matching_entry_ids = [
                _string(value, label=f"{lineup_id} matching entry ID")
                for value in _sequence(
                    row.get("matching_entry_ids"),
                    label=f"{lineup_id} matching entry IDs",
                )
            ]
            if (
                matching_entry_ids != sorted(matching_entry_ids)
                or len(set(matching_entry_ids)) != len(matching_entry_ids)
                or retained_counterfactual_percentile
                != counterfactual_percentile
            ):
                _fail(f"{lineup_id} counterfactual field mapping differs")
            duplicates = _integer(
                row.get("duplicates"), label=f"{lineup_id} duplicates"
            )
            payout = _integer(
                row.get("split_payout_micro"),
                label=f"{lineup_id} split payout micro",
            )
            actual_rank = row.get("actual_field_rank")
            actual_percentile = row.get("actual_field_percentile_ppm")
            if entered:
                retained_actual_rank = _integer(
                    actual_rank, label=f"{lineup_id} actual field rank", minimum=1
                )
                retained_actual_percentile = _integer(
                    actual_percentile,
                    label=f"{lineup_id} actual field percentile",
                )
                if (
                    retained_actual_rank > field_size
                    or retained_actual_rank != counterfactual_rank
                    or retained_actual_percentile != counterfactual_percentile
                    or duplicates < 1
                    or duplicates != len(matching_entry_ids)
                    or applicable is not True
                ):
                    _fail(f"{lineup_id} actual contest mapping differs")
            else:
                retained_actual_rank = None
                retained_actual_percentile = None
                if (
                    actual_rank is not None
                    or actual_percentile is not None
                    or duplicates != 0
                    or payout != 0
                    or matching_entry_ids
                    or applicable is not False
                ):
                    _fail(f"{lineup_id} unentered contest facts were imputed")
            normalized.update({
                "actual_field_rank": retained_actual_rank,
                "actual_field_percentile_ppm": retained_actual_percentile,
                "counterfactual_field_rank": counterfactual_rank,
                "counterfactual_field_percentile_ppm": (
                    retained_counterfactual_percentile
                ),
                "duplicates": duplicates,
                "split_payout_micro": payout,
                "entered_in_contest": entered,
                "matching_entry_ids": matching_entry_ids,
                "actual_split_payout_applicable": applicable,
            })
        rows.append(normalized)
    if not rows:
        _fail("outcome snapshot is empty")
    rows.sort(key=lambda row: str(row["lineup_id"]))
    if field_metrics_available and field_capture["contest_ev_claim_allowed"]:
        if not all(
            bool(row["entered_in_contest"])
            and bool(row["actual_split_payout_applicable"])
            and int(row["duplicates"]) >= 1
            for row in rows
        ):
            _fail("contest EV cannot use counterfactual or unentered lineups")
    score_rows = [{
        "lineup_id": row["lineup_id"],
        "realized_score_micro": row["realized_score_micro"],
    } for row in rows]
    score_source_payload = {
        "schema_version": REALIZED_SCORE_SOURCE_SCHEMA,
        "season": SEASON,
        "week": week_value,
        "slate_id": slate,
        "captured_at": captured,
        "producer_class": "independent-realized-lineup-score-source",
        "independent_from_generation": True,
        "terminal_prelock_root_binding_present": False,
        "lineup_count": len(score_rows),
        "lineup_rows": score_rows,
        "lineup_rows_sha256": canonical_sha256_v1(score_rows),
    }
    score_source_identity = normalize_object_identity_v1(
        realized_score_source_identity,
        label="independent realized-score source",
    )
    if (
        score_source_identity["sha256"]
        != canonical_sha256_v1(score_source_payload)
        or score_source_identity["bytes"]
        != len(canonical_json_bytes_v1(score_source_payload))
    ):
        _fail("independent realized-score identity does not bind exact scores")
    source_payload = {
        "schema_version": (
            "prospective-generation-shadow-outcome-source-content/v2"
        ),
        "season": SEASON,
        "week": week_value,
        "slate_id": slate,
        "captured_at": captured,
        "field_metrics_available": field_metrics_available,
        "realized_score_source_identity": score_source_identity,
        "contest_field_capture": field_capture,
        "lineup_rows": rows,
    }
    source_identity = normalize_object_identity_v1(
        outcome_source_identity, label="independent outcome source"
    )
    if (
        source_identity["sha256"] != canonical_sha256_v1(source_payload)
        or source_identity["bytes"]
        != len(canonical_json_bytes_v1(source_payload))
    ):
        _fail("independent outcome source identity does not bind snapshot rows")
    if _identity_key(source_identity) == _identity_key(score_source_identity):
        _fail("outcome snapshot and realized-score source identities are reused")
    body: dict[str, object] = {
        "schema_version": OUTCOME_SNAPSHOT_SCHEMA,
        "season": SEASON,
        "week": week_value,
        "slate_id": slate,
        "captured_at": captured,
        "outcome_source_identity": source_identity,
        "realized_score_source_identity": score_source_identity,
        "producer_class": "independent-outcome-snapshot",
        "independent_from_generation": True,
        "field_metrics_available": field_metrics_available,
        "contest_field_capture": field_capture,
        "lineup_count": len(rows),
        "lineup_rows": rows,
        "lineup_rows_sha256": canonical_sha256_v1(rows),
        "prelock_root_binding_present": False,
        "complete": True,
    }
    return _with_hash(body, field="outcome_snapshot_sha256")


def validate_outcome_snapshot_v1(value: object) -> dict[str, object]:
    snapshot = _mapping(value, label="independent outcome snapshot")
    fields = {
        "schema_version", "season", "week", "slate_id", "captured_at",
        "outcome_source_identity", "realized_score_source_identity",
        "producer_class",
        "independent_from_generation", "field_metrics_available",
        "contest_field_capture",
        "lineup_count", "lineup_rows", "lineup_rows_sha256",
        "prelock_root_binding_present", "complete", "outcome_snapshot_sha256",
    }
    if set(snapshot) != fields:
        _fail("independent outcome snapshot fields differ")
    _validate_self_hash(
        snapshot, field="outcome_snapshot_sha256",
        label="independent outcome snapshot",
    )
    rebuilt = build_outcome_snapshot_v1(
        season=snapshot.get("season"),
        week=snapshot.get("week"),
        slate_id=snapshot.get("slate_id"),
        captured_at=snapshot.get("captured_at"),
        outcome_source_identity=_mapping(
            snapshot.get("outcome_source_identity"),
            label="independent outcome source identity",
        ),
        realized_score_source_identity=_mapping(
            snapshot.get("realized_score_source_identity"),
            label="independent realized-score source identity",
        ),
        lineup_rows=_sequence(
            snapshot.get("lineup_rows"), label="outcome lineup rows"
        ),
        field_metrics_available=snapshot.get("field_metrics_available"),
        contest_field_capture=(
            snapshot.get("contest_field_capture")
            if snapshot.get("field_metrics_available") is True
            else None
        ),
    )
    if rebuilt != snapshot:
        _fail("independent outcome snapshot normalized projection differs")
    return snapshot


def _validated_field_bridge_projection_v1(
    *,
    terminal_prelock_root: Mapping[str, object],
    field_bridge: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], bool]:
    from .prospective_generation_shadow_field_bridge import (
        validate_contest_field_bridge_v1,
    )

    root = validate_terminal_prelock_root_v1(terminal_prelock_root)
    bridge = validate_contest_field_bridge_v1(field_bridge)
    envelope_identity = normalize_object_identity_v1(
        terminal_prelock_root.get("identity"),
        label="terminal prelock envelope identity",
    )
    bridge_root_identity = normalize_object_identity_v1(
        bridge.get("terminal_prelock_root_identity"),
        label="field-bridge terminal identity",
    )
    if (
        bridge_root_identity != envelope_identity
        or bridge.get("terminal_prelock_root_sha256")
        != root["terminal_prelock_root_sha256"]
        or bridge.get("season") != root["season"]
        or bridge.get("week") != root["week"]
        or bridge.get("slate_id") != root["slate_id"]
    ):
        _fail("contest-field bridge does not bind the terminal prelock root")
    complete = bridge.get("complete_contest_field_capture") is True
    if complete != (bridge.get("status") == "complete-contest-field-capture"):
        _fail("contest-field bridge completeness labels differ")
    prelock_keys = _prelock_identity_keys(root, terminal_prelock_root)
    score_identity = normalize_object_identity_v1(
        bridge.get("realized_score_source_identity"),
        label="field-bridge realized-score source",
    )
    if _identity_key(score_identity) in prelock_keys:
        _fail("field-bridge realized-score source collides with prelock")
    if complete:
        capture = _mapping(
            bridge.get("evaluator_contest_field_capture"),
            label="field-bridge evaluator contest capture",
        )
        for field in (
            "payout_table_identity", "field_rosters_identity",
            "field_ownership_identity", "participant_strength_identity",
            "shadow_entry_mapping_identity",
        ):
            if _identity_key(capture[field]) in prelock_keys:
                _fail("field-bridge component authority collides with prelock")
    return root, bridge, complete


def build_outcome_source_payload_from_field_bridge_v1(
    *,
    terminal_prelock_root: Mapping[str, object],
    field_bridge: Mapping[str, object],
) -> dict[str, object]:
    """Prepare the canonical independent snapshot payload for publication."""

    _root, bridge, complete = _validated_field_bridge_projection_v1(
        terminal_prelock_root=terminal_prelock_root,
        field_bridge=field_bridge,
    )
    rows = [
        dict(_mapping(row, label="field-bridge evaluator lineup row"))
        for row in _sequence(
            bridge.get("evaluator_lineup_rows"),
            label="field-bridge evaluator lineup rows",
        )
    ]
    capture = (
        _normalize_contest_field_capture(
            bridge.get("evaluator_contest_field_capture")
        )
        if complete
        else {
            "status": "unavailable-raw-score-only",
            "evidence_scope": "raw-score-only-no-contest-ev",
            "complete_field_rank_claim_allowed": False,
            "contest_ev_claim_allowed": False,
            "allocation_recommendation_allowed": False,
            "complete": False,
        }
    )
    return {
        "schema_version": (
            "prospective-generation-shadow-outcome-source-content/v2"
        ),
        "season": bridge["season"],
        "week": bridge["week"],
        "slate_id": bridge["slate_id"],
        "captured_at": bridge["captured_at"],
        "field_metrics_available": complete,
        "realized_score_source_identity": normalize_object_identity_v1(
            bridge.get("realized_score_source_identity"),
            label="field-bridge realized-score source",
        ),
        "contest_field_capture": capture,
        "lineup_rows": rows,
    }


def build_outcome_snapshot_from_field_bridge_v1(
    *,
    terminal_prelock_root: Mapping[str, object],
    field_bridge: Mapping[str, object],
    outcome_source_identity: Mapping[str, object],
) -> dict[str, object]:
    """Adapt the validated field bridge without collapsing its authorities."""

    _root, bridge, complete = _validated_field_bridge_projection_v1(
        terminal_prelock_root=terminal_prelock_root,
        field_bridge=field_bridge,
    )
    expected_payload = build_outcome_source_payload_from_field_bridge_v1(
        terminal_prelock_root=terminal_prelock_root,
        field_bridge=bridge,
    )
    identity = normalize_object_identity_v1(
        outcome_source_identity, label="independent outcome snapshot source"
    )
    if (
        identity["sha256"] != canonical_sha256_v1(expected_payload)
        or identity["bytes"] != len(canonical_json_bytes_v1(expected_payload))
    ):
        _fail("independent outcome identity does not bind the field bridge projection")
    return build_outcome_snapshot_v1(
        season=int(bridge["season"]),
        week=int(bridge["week"]),
        slate_id=str(bridge["slate_id"]),
        captured_at=str(bridge["captured_at"]),
        outcome_source_identity=identity,
        realized_score_source_identity=_mapping(
            bridge.get("realized_score_source_identity"),
            label="field-bridge realized-score source identity",
        ),
        lineup_rows=_sequence(
            bridge.get("evaluator_lineup_rows"),
            label="field-bridge evaluator lineup rows",
        ),
        field_metrics_available=complete,
        contest_field_capture=(
            _mapping(
                bridge.get("evaluator_contest_field_capture"),
                label="field-bridge evaluator contest-field capture",
            )
            if complete else None
        ),
    )


def _identity_key(value: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(value[field] for field in (
        "uri", "generation", "sha256", "bytes"
    ))


def _prelock_identity_keys(
    root: Mapping[str, object], envelope: Mapping[str, object]
) -> set[tuple[object, ...]]:
    identities = [
        normalize_object_identity_v1(
            envelope["identity"], label="terminal root identity"
        ),
        normalize_object_identity_v1(
            root["shared_simulation_artifact"]["identity"],
            label="shared simulation identity",
        ),
        normalize_object_identity_v1(
            root["untouched_selection_bank_artifact"]["identity"],
            label="selection bank identity",
        ),
        normalize_object_identity_v1(
            root["independent_audit_world_artifact"]["identity"],
            label="independent audit-world identity",
        ),
    ]
    seed = root["seed_crossing"]
    identities.extend(row["identity"] for row in seed["fit_seed_slots"])
    identities.extend(row["identity"] for row in seed["world_seed_slots"])
    identities.extend(
        row["crossed_artifact_identity"] for row in seed["crossed_slots"]
    )
    for arm in root["arms"]:
        identities.extend(
            descriptor["identity"] for descriptor in arm["artifacts"].values()
        )
        if arm["retrieval_interaction"] is not None:
            identities.append(
                arm["retrieval_interaction"]["book_artifact"]["identity"]
            )
        if arm["preexisting_candidate_census_artifact"] is not None:
            identities.append(
                arm["preexisting_candidate_census_artifact"]["identity"]
            )
    suite = root.get("suite_authority")
    if isinstance(suite, Mapping):
        identities.extend((suite["manifest_identity"], suite["terminal_identity"]))
        identities.extend(suite["world_artifact_identities"].values())
        identities.append(suite["independent_audit_world_artifact_identity"])
        identities.extend(
            suite["cross_law_discovery_world_artifact_identities"].values()
        )
    return {_identity_key(identity) for identity in identities}


def _best_lineup(
    lineup_ids: Sequence[str], score_by_id: Mapping[str, int]
) -> tuple[str, int]:
    # Stable book/pool order is the predeclared tie break.
    best_id = lineup_ids[0]
    best_score = score_by_id[best_id]
    for lineup_id in lineup_ids[1:]:
        score = score_by_id[lineup_id]
        if score > best_score:
            best_id, best_score = lineup_id, score
    return best_id, best_score


def _threshold_rows(score_micro: int) -> list[dict[str, object]]:
    return [{
        "threshold_dk": threshold,
        "threshold_micro": threshold * PROBABILITY_SCALE,
        "realized_hit": score_micro >= threshold * PROBABILITY_SCALE,
    } for threshold in REALIZED_THRESHOLDS_DK]


def _calibration_rows(
    score_micro: int, modeled: Mapping[str, int]
) -> list[dict[str, object]]:
    rows = []
    for threshold in CALIBRATION_THRESHOLDS_DK:
        probability = int(modeled[str(threshold)])
        indicator = int(score_micro >= threshold * PROBABILITY_SCALE)
        residual = indicator * PROBABILITY_SCALE - probability
        rows.append({
            "threshold_dk": threshold,
            "modeled_probability_ppm": probability,
            "realized_indicator": indicator,
            "calibration_residual_ppm": residual,
            "brier_loss_ppm_squared": residual * residual,
        })
    return rows


def _field_metrics(
    lineup_ids: Sequence[str], best_id: str,
    outcome_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    rows = [outcome_by_id[lineup_id] for lineup_id in lineup_ids]
    best_row = outcome_by_id[best_id]
    entered_rows = [row for row in rows if row["entered_in_contest"]]
    return {
        "best_realized_lineup_entered_in_contest": bool(
            best_row["entered_in_contest"]
        ),
        "best_realized_lineup_actual_field_rank": (
            None
            if best_row["actual_field_rank"] is None
            else int(best_row["actual_field_rank"])
        ),
        "best_realized_lineup_actual_field_percentile_ppm": (
            None
            if best_row["actual_field_percentile_ppm"] is None
            else int(best_row["actual_field_percentile_ppm"])
        ),
        "best_realized_lineup_counterfactual_field_rank": int(
            best_row["counterfactual_field_rank"]
        ),
        "best_realized_lineup_counterfactual_field_percentile_ppm": int(
            best_row["counterfactual_field_percentile_ppm"]
        ),
        "best_realized_lineup_duplicates": int(best_row["duplicates"]),
        "best_realized_lineup_split_payout_micro": int(
            best_row["split_payout_micro"]
        ),
        "best_realized_lineup_actual_split_payout_applicable": bool(
            best_row["actual_split_payout_applicable"]
        ),
        "best_realized_lineup_matching_entry_ids": list(
            best_row["matching_entry_ids"]
        ),
        "entered_lineup_count_in_prefix": len(entered_rows),
        "best_actual_field_rank_in_prefix": (
            None
            if not entered_rows
            else min(int(row["actual_field_rank"]) for row in entered_rows)
        ),
        "best_actual_field_percentile_ppm_in_prefix": (
            None
            if not entered_rows
            else max(
                int(row["actual_field_percentile_ppm"])
                for row in entered_rows
            )
        ),
        "best_counterfactual_field_rank_in_prefix": min(
            int(row["counterfactual_field_rank"]) for row in rows
        ),
        "best_counterfactual_field_percentile_ppm_in_prefix": max(
            int(row["counterfactual_field_percentile_ppm"]) for row in rows
        ),
        "total_actual_prefix_split_payout_micro": sum(
            int(row["split_payout_micro"]) for row in rows
        ),
    }


def grade_realized_week_v1(
    *, terminal_prelock_root: Mapping[str, object],
    outcome_snapshot: Mapping[str, object],
) -> dict[str, object]:
    """Grade one week from exactly two separated authorities.

    The terminal root is fully validated before the outcome mapping is
    inspected.  No caller-supplied book, candidate pool, score map, prefix,
    arm list, or decision rule is accepted by this API.
    """

    root = validate_terminal_prelock_root_v1(terminal_prelock_root)
    # Outcome access starts only after the terminal root returned above.
    snapshot = validate_outcome_snapshot_v1(outcome_snapshot)
    if (
        snapshot["season"] != root["season"]
        or snapshot["week"] != root["week"]
        or snapshot["slate_id"] != root["slate_id"]
        or _parsed_timestamp(snapshot["captured_at"], label="outcome captured-at")
        <= _parsed_timestamp(root["lock_at"], label="root lock")
    ):
        _fail("outcome snapshot does not match the completed prelock slate")
    outcome_source = normalize_object_identity_v1(
        snapshot["outcome_source_identity"], label="outcome source"
    )
    score_source = normalize_object_identity_v1(
        snapshot["realized_score_source_identity"],
        label="realized-score source",
    )
    prelock_identity = normalize_object_identity_v1(
        terminal_prelock_root["identity"], label="terminal root identity"
    )
    prelock_identities = _prelock_identity_keys(root, terminal_prelock_root)
    if (
        _identity_key(outcome_source) in prelock_identities
        or _identity_key(score_source) in prelock_identities
        or _identity_key(outcome_source) == _identity_key(score_source)
    ):
        _fail("outcome/score source is not independent of prelock authorities")
    capture = snapshot["contest_field_capture"]
    if snapshot["field_metrics_available"]:
        for field in (
            "payout_table_identity", "field_rosters_identity",
            "field_ownership_identity", "participant_strength_identity",
            "shadow_entry_mapping_identity",
        ):
            if (
                _identity_key(capture[field]) in prelock_identities
                or _identity_key(capture[field])
                in {_identity_key(outcome_source), _identity_key(score_source)}
            ):
                _fail("contest-field source is not independent of prelock authorities")
    outcome_rows = {
        str(row["lineup_id"]): row for row in snapshot["lineup_rows"]
    }
    score_by_id = {
        lineup_id: int(row["realized_score_micro"])
        for lineup_id, row in outcome_rows.items()
    }
    required_lineups = {
        lineup_id
        for arm in root["arms"]
        for lineup_id in arm["candidate_lineup_ids"]
    }
    if set(score_by_id) != required_lineups:
        _fail("outcome snapshot is not the exact frozen candidate union")
    field_available = bool(snapshot["field_metrics_available"])
    reporting_counts = [int(value) for value in root["reporting_entry_counts"]]
    arm_results: list[dict[str, object]] = []
    for arm in root["arms"]:
        arm_id = str(arm["arm_id"])
        pool_ids = [str(value) for value in arm["candidate_lineup_ids"]]
        book_ids = [str(value) for value in arm["book_lineup_ids"]]
        oracle_id, oracle_score = _best_lineup(pool_ids, score_by_id)
        prefix_results = []
        for count in reporting_counts:
            selected_ids = book_ids[:count]
            best_id, best_score = _best_lineup(selected_ids, score_by_id)
            prefix_results.append({
                "entry_count": count,
                "selected_weekly_maximum_micro": best_score,
                "selected_weekly_maximum_lineup_id": best_id,
                "pool_oracle_micro": oracle_score,
                "pool_oracle_lineup_id": oracle_id,
                "selector_regret_micro": oracle_score - best_score,
                "thresholds": _threshold_rows(best_score),
                "cap_calibration": _calibration_rows(
                    best_score, arm["modeled_probability_ppm"][str(count)]
                ),
                "field_metrics": (
                    _field_metrics(selected_ids, best_id, outcome_rows)
                    if field_available else None
                ),
            })
        operational = next(
            row for row in prefix_results
            if row["entry_count"] == root["operational_k"]
        )
        arm_results.append({
            "arm_id": arm_id,
            "population_label": arm["population_label"],
            "cap_label": arm["cap_label"],
            "arm_status": arm["arm_status"],
            "scientific_status": arm["scientific_status"],
            "decision_role": arm["decision_role"],
            "required_before_week1": arm["required_before_week1"],
            "resource_class": arm["resource_class"],
            "resource_caveat": arm["resource_caveat"],
            "equal_compute_comparison": arm["equal_compute_comparison"],
            "candidate_count": len(pool_ids),
            "operational_k": root["operational_k"],
            "operational_weekly_maximum_micro": operational[
                "selected_weekly_maximum_micro"
            ],
            "pool_oracle_micro": oracle_score,
            "operational_selector_regret_micro": operational[
                "selector_regret_micro"
            ],
            "prefix_results": prefix_results,
        })
    result_by_arm = {str(row["arm_id"]): row for row in arm_results}
    root_by_arm = {str(row["arm_id"]): row for row in root["arms"]}
    retrieval_crossing_cells: list[dict[str, object]] = []
    for generation_arm in _RETRIEVAL_CROSSING_ARMS:
        base_result = result_by_arm[generation_arm]
        retrieval_crossing_cells.append({
            "generation_arm": generation_arm,
            "retrieval_id": _BASE_RETRIEVAL_ID,
            "population_label": base_result["population_label"],
            "cap_label": _BASE_RETRIEVAL_ID,
            "operational_weekly_maximum_micro": base_result[
                "operational_weekly_maximum_micro"
            ],
            "prefix_results": base_result["prefix_results"],
        })
        frozen = root_by_arm[generation_arm]
        interaction = frozen["retrieval_interaction"]
        pool_ids = [str(value) for value in frozen["candidate_lineup_ids"]]
        cap4_ids = [str(value) for value in interaction["book_lineup_ids"]]
        oracle_id, oracle_score = _best_lineup(pool_ids, score_by_id)
        cap4_prefix_results = []
        for count in reporting_counts:
            selected_ids = cap4_ids[:count]
            best_id, best_score = _best_lineup(selected_ids, score_by_id)
            cap4_prefix_results.append({
                "entry_count": count,
                "selected_weekly_maximum_micro": best_score,
                "selected_weekly_maximum_lineup_id": best_id,
                "pool_oracle_micro": oracle_score,
                "pool_oracle_lineup_id": oracle_id,
                "selector_regret_micro": oracle_score - best_score,
                "thresholds": _threshold_rows(best_score),
                "cap_calibration": _calibration_rows(
                    best_score,
                    interaction["modeled_probability_ppm"][str(count)],
                ),
                "field_metrics": (
                    _field_metrics(selected_ids, best_id, outcome_rows)
                    if field_available else None
                ),
            })
        cap4_operational = next(
            row for row in cap4_prefix_results
            if row["entry_count"] == root["operational_k"]
        )
        retrieval_crossing_cells.append({
            "generation_arm": generation_arm,
            "retrieval_id": _CAP4_RETRIEVAL_ID,
            "population_label": frozen["population_label"],
            "cap_label": interaction["cap_label"],
            "operational_weekly_maximum_micro": cap4_operational[
                "selected_weekly_maximum_micro"
            ],
            "prefix_results": cap4_prefix_results,
        })
    crossing_by_key = {
        (row["generation_arm"], row["retrieval_id"]): row
        for row in retrieval_crossing_cells
    }
    incumbent_arm, boom_arm = _RETRIEVAL_CROSSING_ARMS
    inc_base = int(crossing_by_key[(incumbent_arm, _BASE_RETRIEVAL_ID)][
        "operational_weekly_maximum_micro"
    ])
    inc_cap4 = int(crossing_by_key[(incumbent_arm, _CAP4_RETRIEVAL_ID)][
        "operational_weekly_maximum_micro"
    ])
    boom_base = int(crossing_by_key[(boom_arm, _BASE_RETRIEVAL_ID)][
        "operational_weekly_maximum_micro"
    ])
    boom_cap4 = int(crossing_by_key[(boom_arm, _CAP4_RETRIEVAL_ID)][
        "operational_weekly_maximum_micro"
    ])
    retrieval_interaction = {
        "generation_effect_under_incumbent_retrieval_micro": boom_base - inc_base,
        "generation_effect_under_cap4_retrieval_micro": boom_cap4 - inc_cap4,
        "retrieval_effect_on_incumbent_generation_micro": inc_cap4 - inc_base,
        "retrieval_effect_on_boom_first_generation_micro": boom_cap4 - boom_base,
        "difference_in_differences_micro": (
            (boom_cap4 - boom_base) - (inc_cap4 - inc_base)
        ),
        "key_secondary_not_primary": True,
        **deepcopy(_RETRIEVAL_DECISION_ROLE),
    }
    paired_rows = []
    for challenger in ARM_ORDER[1:]:
        comparator = COMPARATOR_BY_ARM[challenger]
        contrast_role = _CONTRAST_DECISION_ROLES[challenger]
        challenger_score = int(
            result_by_arm[challenger]["operational_weekly_maximum_micro"]
        )
        comparator_score = int(
            result_by_arm[comparator]["operational_weekly_maximum_micro"]
        )
        challenger_thresholds = {
            int(row["threshold_dk"]): bool(row["realized_hit"])
            for row in next(
                row for row in result_by_arm[challenger]["prefix_results"]
                if row["entry_count"] == root["operational_k"]
            )["thresholds"]
        }
        comparator_thresholds = {
            int(row["threshold_dk"]): bool(row["realized_hit"])
            for row in next(
                row for row in result_by_arm[comparator]["prefix_results"]
                if row["entry_count"] == root["operational_k"]
            )["thresholds"]
        }
        delta = challenger_score - comparator_score
        paired_rows.append({
            "challenger_arm": challenger,
            "comparator_arm": comparator,
            "scientific_status": contrast_role["scientific_status"],
            "decision_role": contrast_role["decision_role"],
            "primary_efficacy_rule_satisfaction_allowed": contrast_role[
                "primary_efficacy_rule_satisfaction_allowed"
            ],
            "promotion_equivalent_efficacy_allowed": contrast_role[
                "promotion_equivalent_efficacy_allowed"
            ],
            "comparison_resource_class": (
                "equal-compute" if _POLICY_BY_ARM[challenger][
                    "equal_compute_comparison"
                ] else "unequal-resource-dose-not-equal-compute"
            ),
            "challenger_weekly_maximum_micro": challenger_score,
            "comparator_weekly_maximum_micro": comparator_score,
            "paired_delta_micro": delta,
            "sign": "win" if delta > 0 else "loss" if delta < 0 else "tie",
            "threshold_hit_deltas": {
                str(threshold): int(challenger_thresholds[threshold])
                - int(comparator_thresholds[threshold])
                for threshold in REALIZED_THRESHOLDS_DK
            },
        })
    prefix_pairs = []
    for count in reporting_counts:
        for challenger in ARM_ORDER[1:]:
            comparator = COMPARATOR_BY_ARM[challenger]
            contrast_role = _CONTRAST_DECISION_ROLES[challenger]
            challenger_row = next(
                row for row in result_by_arm[challenger]["prefix_results"]
                if row["entry_count"] == count
            )
            comparator_row = next(
                row for row in result_by_arm[comparator]["prefix_results"]
                if row["entry_count"] == count
            )
            prefix_pairs.append({
                "entry_count": count,
                "challenger_arm": challenger,
                "comparator_arm": comparator,
                "scientific_status": contrast_role["scientific_status"],
                "decision_role": contrast_role["decision_role"],
                "primary_efficacy_rule_satisfaction_allowed": contrast_role[
                    "primary_efficacy_rule_satisfaction_allowed"
                ],
                "promotion_equivalent_efficacy_allowed": contrast_role[
                    "promotion_equivalent_efficacy_allowed"
                ],
                "comparison_resource_class": (
                    "equal-compute" if _POLICY_BY_ARM[challenger][
                        "equal_compute_comparison"
                    ] else "unequal-resource-dose-not-equal-compute"
                ),
                "paired_delta_micro": int(
                    challenger_row["selected_weekly_maximum_micro"]
                ) - int(comparator_row["selected_weekly_maximum_micro"]),
            })
    body: dict[str, object] = {
        "schema_version": WEEKLY_GRADE_SCHEMA,
        "season": root["season"],
        "week": root["week"],
        "slate_id": root["slate_id"],
        "terminal_prelock_root_identity": prelock_identity,
        "terminal_prelock_root_sha256": root["terminal_prelock_root_sha256"],
        "preregistration_sha256": root["preregistration_sha256"],
        "seed_crossing_sha256": root["seed_crossing_sha256"],
        "outcome_source_identity": outcome_source,
        "realized_score_source_identity": score_source,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "operational_k": root["operational_k"],
        "reporting_entry_counts": reporting_counts,
        "arm_order": list(ARM_ORDER),
        "contrast_decision_roles": deepcopy(_CONTRAST_DECISION_ROLES),
        "retrieval_decision_role": deepcopy(_RETRIEVAL_DECISION_ROLE),
        "arm_results": arm_results,
        "arm_results_sha256": canonical_sha256_v1(arm_results),
        "paired_operational_contrasts": paired_rows,
        "paired_prefix_contrasts": prefix_pairs,
        "retrieval_crossing_cells": retrieval_crossing_cells,
        "retrieval_crossing_cells_sha256": canonical_sha256_v1(
            retrieval_crossing_cells
        ),
        "retrieval_interaction": retrieval_interaction,
        "field_metrics_available": field_available,
        "contest_field_evidence_scope": capture["evidence_scope"],
        "complete_field_rank_claim_allowed": capture[
            "complete_field_rank_claim_allowed"
        ],
        "contest_ev_claim_allowed": capture["contest_ev_claim_allowed"],
        "allocation_recommendation_allowed": False,
        "inference_unit": "slate-after-block-and-bank-aggregation",
        "terminal_freeze_validated_before_outcome_consumed": True,
        "grader_inputs_exactly_terminal_plus_independent_snapshot": True,
        "all_arms_reported_including_losses": True,
        "uses_realized_outcomes": True,
        "historical_gain_inputs_consumed": False,
        "automatic_adoption": False,
        "complete": True,
    }
    grade = _with_hash(body, field="weekly_grade_sha256")
    return validate_realized_week_grade_v1(grade)


def _validate_prefix_grade(
    value: object, *, arm_id: str, field_available: bool,
) -> dict[str, object]:
    row = _mapping(value, label=f"{arm_id} prefix grade")
    if set(row) != {
        "entry_count", "selected_weekly_maximum_micro",
        "selected_weekly_maximum_lineup_id", "pool_oracle_micro",
        "pool_oracle_lineup_id", "selector_regret_micro", "thresholds",
        "cap_calibration", "field_metrics",
    }:
        _fail(f"{arm_id} prefix-grade fields differ")
    _integer(row.get("entry_count"), label=f"{arm_id} prefix count", minimum=1)
    selected = _integer(
        row.get("selected_weekly_maximum_micro"),
        label=f"{arm_id} weekly maximum", minimum=-100_000_000,
    )
    oracle = _integer(
        row.get("pool_oracle_micro"), label=f"{arm_id} pool oracle",
        minimum=-100_000_000,
    )
    _identifier(
        row.get("selected_weekly_maximum_lineup_id"),
        label=f"{arm_id} maximum lineup ID",
    )
    _identifier(row.get("pool_oracle_lineup_id"), label=f"{arm_id} oracle ID")
    if (
        oracle < selected
        or row.get("selector_regret_micro") != oracle - selected
    ):
        _fail(f"{arm_id} pool oracle/regret differs")
    thresholds = _sequence(row.get("thresholds"), label=f"{arm_id} thresholds")
    if len(thresholds) != len(REALIZED_THRESHOLDS_DK):
        _fail(f"{arm_id} threshold registry differs")
    for raw, threshold in zip(thresholds, REALIZED_THRESHOLDS_DK, strict=True):
        threshold_row = _mapping(raw, label=f"{arm_id} threshold {threshold}")
        if (
            set(threshold_row) != {
                "threshold_dk", "threshold_micro", "realized_hit"
            }
            or threshold_row.get("threshold_dk") != threshold
            or threshold_row.get("threshold_micro")
            != threshold * PROBABILITY_SCALE
            or threshold_row.get("realized_hit")
            is not (selected >= threshold * PROBABILITY_SCALE)
        ):
            _fail(f"{arm_id} threshold realization differs")
    calibration = _sequence(
        row.get("cap_calibration"), label=f"{arm_id} cap calibration"
    )
    if len(calibration) != len(CALIBRATION_THRESHOLDS_DK):
        _fail(f"{arm_id} cap-calibration threshold registry differs")
    for raw, threshold in zip(
        calibration, CALIBRATION_THRESHOLDS_DK, strict=True
    ):
        cell = _mapping(raw, label=f"{arm_id} cap calibration {threshold}")
        if set(cell) != {
            "threshold_dk", "modeled_probability_ppm", "realized_indicator",
            "calibration_residual_ppm", "brier_loss_ppm_squared",
        }:
            _fail(f"{arm_id} cap-calibration fields differ")
        probability = _integer(
            cell.get("modeled_probability_ppm"),
            label=f"{arm_id} modeled probability",
        )
        if probability > PROBABILITY_SCALE:
            _fail(f"{arm_id} modeled probability exceeds one")
        indicator = int(selected >= threshold * PROBABILITY_SCALE)
        residual = indicator * PROBABILITY_SCALE - probability
        if (
            cell.get("threshold_dk") != threshold
            or cell.get("realized_indicator") != indicator
            or cell.get("calibration_residual_ppm") != residual
            or cell.get("brier_loss_ppm_squared") != residual * residual
        ):
            _fail(f"{arm_id} cap-calibration arithmetic differs")
    field = row.get("field_metrics")
    if field_available:
        metric = _mapping(field, label=f"{arm_id} field metrics")
        if set(metric) != {
            "best_realized_lineup_entered_in_contest",
            "best_realized_lineup_actual_field_rank",
            "best_realized_lineup_actual_field_percentile_ppm",
            "best_realized_lineup_counterfactual_field_rank",
            "best_realized_lineup_counterfactual_field_percentile_ppm",
            "best_realized_lineup_duplicates",
            "best_realized_lineup_split_payout_micro",
            "best_realized_lineup_actual_split_payout_applicable",
            "best_realized_lineup_matching_entry_ids",
            "entered_lineup_count_in_prefix",
            "best_actual_field_rank_in_prefix",
            "best_actual_field_percentile_ppm_in_prefix",
            "best_counterfactual_field_rank_in_prefix",
            "best_counterfactual_field_percentile_ppm_in_prefix",
            "total_actual_prefix_split_payout_micro",
        }:
            _fail(f"{arm_id} field metric fields differ")
        entered = metric.get("best_realized_lineup_entered_in_contest")
        applicable = metric.get(
            "best_realized_lineup_actual_split_payout_applicable"
        )
        if type(entered) is not bool or type(applicable) is not bool:
            _fail(f"{arm_id} best-lineup actual contest labels differ")
        counterfactual_rank = _integer(
            metric.get("best_realized_lineup_counterfactual_field_rank"),
            label="best realized lineup counterfactual rank", minimum=1,
        )
        counterfactual_percentile = _integer(
            metric.get(
                "best_realized_lineup_counterfactual_field_percentile_ppm"
            ),
            label="best realized lineup counterfactual percentile",
        )
        duplicates = _integer(
            metric.get("best_realized_lineup_duplicates"),
            label="best realized lineup duplicates",
        )
        payout = _integer(
            metric.get("best_realized_lineup_split_payout_micro"),
            label="best realized lineup split payout",
        )
        matching = [
            _string(value, label="best realized lineup matching entry ID")
            for value in _sequence(
                metric.get("best_realized_lineup_matching_entry_ids"),
                label="best realized lineup matching entry IDs",
            )
        ]
        if matching != sorted(matching) or len(set(matching)) != len(matching):
            _fail(f"{arm_id} best-lineup matching entries differ")
        actual_rank = metric.get("best_realized_lineup_actual_field_rank")
        actual_percentile = metric.get(
            "best_realized_lineup_actual_field_percentile_ppm"
        )
        if entered:
            _integer(actual_rank, label="best realized actual rank", minimum=1)
            _integer(
                actual_percentile,
                label="best realized actual field percentile",
            )
            if (
                duplicates < 1
                or duplicates != len(matching)
                or applicable is not True
                or actual_rank != counterfactual_rank
                or actual_percentile != counterfactual_percentile
            ):
                _fail(f"{arm_id} best-lineup actual mapping differs")
        elif (
            actual_rank is not None
            or actual_percentile is not None
            or duplicates != 0
            or payout != 0
            or matching
            or applicable is not False
        ):
            _fail(f"{arm_id} unentered best-lineup facts were imputed")
        entered_count = _integer(
            metric.get("entered_lineup_count_in_prefix"),
            label="entered lineup count in prefix",
        )
        best_counterfactual_rank = _integer(
            metric.get("best_counterfactual_field_rank_in_prefix"),
            label="best counterfactual field rank", minimum=1,
        )
        if best_counterfactual_rank > counterfactual_rank:
            _fail(f"{arm_id} best counterfactual rank summary differs")
        _integer(
            metric.get("best_counterfactual_field_percentile_ppm_in_prefix"),
            label="best counterfactual field percentile",
        )
        best_actual_rank = metric.get("best_actual_field_rank_in_prefix")
        best_actual_percentile = metric.get(
            "best_actual_field_percentile_ppm_in_prefix"
        )
        if entered_count:
            _integer(best_actual_rank, label="best actual field rank", minimum=1)
            _integer(
                best_actual_percentile,
                label="best actual field percentile",
            )
        elif best_actual_rank is not None or best_actual_percentile is not None:
            _fail(f"{arm_id} prefix actual field facts were imputed")
        _integer(
            metric.get("total_actual_prefix_split_payout_micro"),
            label="prefix actual split payout",
        )
    elif field is not None:
        _fail(f"{arm_id} reports field metrics when unavailable")
    return row


def validate_realized_week_grade_v1(value: object) -> dict[str, object]:
    grade = _mapping(value, label="prospective weekly grade")
    fields = {
        "schema_version", "season", "week", "slate_id",
        "terminal_prelock_root_identity", "terminal_prelock_root_sha256",
        "preregistration_sha256", "seed_crossing_sha256",
        "outcome_source_identity", "realized_score_source_identity",
        "outcome_snapshot_sha256",
        "operational_k", "reporting_entry_counts", "arm_order",
        "contrast_decision_roles", "retrieval_decision_role",
        "arm_results", "arm_results_sha256", "paired_operational_contrasts",
        "paired_prefix_contrasts", "retrieval_crossing_cells",
        "retrieval_crossing_cells_sha256", "retrieval_interaction",
        "field_metrics_available", "contest_field_evidence_scope",
        "complete_field_rank_claim_allowed",
        "contest_ev_claim_allowed", "allocation_recommendation_allowed",
        "inference_unit",
        "terminal_freeze_validated_before_outcome_consumed",
        "grader_inputs_exactly_terminal_plus_independent_snapshot",
        "all_arms_reported_including_losses", "uses_realized_outcomes",
        "historical_gain_inputs_consumed", "automatic_adoption", "complete",
        "weekly_grade_sha256",
    }
    if set(grade) != fields:
        _fail("prospective weekly grade fields differ")
    _validate_self_hash(
        grade, field="weekly_grade_sha256", label="prospective weekly grade"
    )
    week = _integer(grade.get("week"), label="grade week", minimum=1)
    k = _integer(grade.get("operational_k"), label="grade K", minimum=80)
    reporting = _reporting_counts(k)
    field_available = grade.get("field_metrics_available")
    if (
        grade.get("schema_version") != WEEKLY_GRADE_SCHEMA
        or grade.get("season") != SEASON
        or week > FULL_SEASON_WEEK_COUNT
        or grade.get("reporting_entry_counts") != reporting
        or grade.get("arm_order") != list(ARM_ORDER)
        or grade.get("contrast_decision_roles")
        != _CONTRAST_DECISION_ROLES
        or grade.get("retrieval_decision_role")
        != _RETRIEVAL_DECISION_ROLE
        or type(field_available) is not bool
        or grade.get("inference_unit")
        != "slate-after-block-and-bank-aggregation"
        or grade.get("complete_field_rank_claim_allowed") is not bool(
            field_available
        )
        or grade.get("contest_field_evidence_scope") not in (
            (
                "raw-score-complete-field-ranks-and-entered-contest-ev",
                "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev",
            ) if field_available else ("raw-score-only-no-contest-ev",)
        )
        or type(grade.get("contest_ev_claim_allowed")) is not bool
        or grade.get("contest_ev_claim_allowed") is not (
            grade.get("contest_field_evidence_scope")
            == "raw-score-complete-field-ranks-and-entered-contest-ev"
        )
        or grade.get("allocation_recommendation_allowed") is not False
        or any(grade.get(field) is not True for field in (
            "terminal_freeze_validated_before_outcome_consumed",
            "grader_inputs_exactly_terminal_plus_independent_snapshot",
            "all_arms_reported_including_losses", "uses_realized_outcomes",
            "complete",
        ))
        or grade.get("historical_gain_inputs_consumed") is not False
        or grade.get("automatic_adoption") is not False
    ):
        _fail("prospective weekly grade fixed law differs")
    _identifier(grade.get("slate_id"), label="grade slate ID")
    normalize_object_identity_v1(
        grade.get("terminal_prelock_root_identity"),
        label="grade terminal-root identity",
    )
    normalize_object_identity_v1(
        grade.get("outcome_source_identity"), label="grade outcome source"
    )
    normalize_object_identity_v1(
        grade.get("realized_score_source_identity"),
        label="grade realized-score source",
    )
    for field in (
        "terminal_prelock_root_sha256", "preregistration_sha256",
        "seed_crossing_sha256", "outcome_snapshot_sha256",
    ):
        _digest(grade.get(field), label=f"grade {field}")
    raw_arms = _sequence(grade.get("arm_results"), label="grade arm results")
    if len(raw_arms) != len(ARM_ORDER):
        _fail("weekly grade omits a predeclared arm")
    arms: list[dict[str, object]] = []
    for raw, arm_id in zip(raw_arms, ARM_ORDER, strict=True):
        arm = _mapping(raw, label=f"grade {arm_id}")
        if set(arm) != {
            "arm_id", "population_label", "cap_label", "arm_status",
            "scientific_status", "decision_role", "required_before_week1",
            "resource_class", "resource_caveat", "equal_compute_comparison",
            "candidate_count",
            "operational_k", "operational_weekly_maximum_micro",
            "pool_oracle_micro", "operational_selector_regret_micro",
            "prefix_results",
        }:
            _fail(f"grade {arm_id} fields differ")
        if (
            arm.get("arm_id") != arm_id
            or arm.get("operational_k") != k
            or arm.get("arm_status") != _POLICY_BY_ARM[arm_id]["arm_status"]
            or arm.get("scientific_status")
            != _POLICY_BY_ARM[arm_id]["scientific_status"]
            or arm.get("decision_role")
            != _POLICY_BY_ARM[arm_id]["decision_role"]
            or arm.get("required_before_week1")
            is not _POLICY_BY_ARM[arm_id]["required_before_week1"]
            or arm.get("resource_class")
            != _POLICY_BY_ARM[arm_id]["resource_class"]
            or arm.get("resource_caveat")
            != _POLICY_BY_ARM[arm_id]["resource_caveat"]
            or arm.get("equal_compute_comparison")
            is not _POLICY_BY_ARM[arm_id]["equal_compute_comparison"]
        ):
            _fail("weekly grade arm order/K differs")
        _identifier(arm.get("population_label"), label="population label")
        _identifier(arm.get("cap_label"), label="cap label")
        _integer(
            arm.get("candidate_count"), label=f"{arm_id} candidate count",
            minimum=k,
        )
        prefixes = [
            _validate_prefix_grade(
                row, arm_id=arm_id, field_available=bool(field_available)
            )
            for row in _sequence(
                arm.get("prefix_results"), label=f"{arm_id} prefix results"
            )
        ]
        if [row["entry_count"] for row in prefixes] != reporting:
            _fail(f"{arm_id} grade prefix registry differs")
        operational = next(row for row in prefixes if row["entry_count"] == k)
        if (
            arm.get("operational_weekly_maximum_micro")
            != operational["selected_weekly_maximum_micro"]
            or arm.get("pool_oracle_micro") != operational["pool_oracle_micro"]
            or arm.get("operational_selector_regret_micro")
            != operational["selector_regret_micro"]
        ):
            _fail(f"{arm_id} operational projection differs")
        arms.append(arm)
    if grade.get("arm_results_sha256") != canonical_sha256_v1(arms):
        _fail("weekly grade arm-results hash differs")
    by_arm = {str(arm["arm_id"]): arm for arm in arms}
    paired = _sequence(
        grade.get("paired_operational_contrasts"),
        label="paired operational contrasts",
    )
    if len(paired) != len(ARM_ORDER) - 1:
        _fail("paired operational contrast family differs")
    for raw, challenger in zip(paired, ARM_ORDER[1:], strict=True):
        row = _mapping(raw, label=f"paired contrast {challenger}")
        comparator = COMPARATOR_BY_ARM[challenger]
        contrast_role = _CONTRAST_DECISION_ROLES[challenger]
        if set(row) != {
            "challenger_arm", "comparator_arm",
            "scientific_status", "decision_role",
            "primary_efficacy_rule_satisfaction_allowed",
            "promotion_equivalent_efficacy_allowed",
            "comparison_resource_class",
            "challenger_weekly_maximum_micro",
            "comparator_weekly_maximum_micro", "paired_delta_micro", "sign",
            "threshold_hit_deltas",
        }:
            _fail("paired operational contrast fields differ")
        challenger_score = int(by_arm[challenger]["operational_weekly_maximum_micro"])
        comparator_score = int(by_arm[comparator]["operational_weekly_maximum_micro"])
        delta = challenger_score - comparator_score
        expected_sign = "win" if delta > 0 else "loss" if delta < 0 else "tie"
        challenger_thresholds = {
            str(cell["threshold_dk"]): int(bool(cell["realized_hit"]))
            for cell in next(
                prefix for prefix in by_arm[challenger]["prefix_results"]
                if prefix["entry_count"] == k
            )["thresholds"]
        }
        comparator_thresholds = {
            str(cell["threshold_dk"]): int(bool(cell["realized_hit"]))
            for cell in next(
                prefix for prefix in by_arm[comparator]["prefix_results"]
                if prefix["entry_count"] == k
            )["thresholds"]
        }
        expected_thresholds = {
            str(threshold): challenger_thresholds[str(threshold)]
            - comparator_thresholds[str(threshold)]
            for threshold in REALIZED_THRESHOLDS_DK
        }
        if (
            row.get("challenger_arm") != challenger
            or row.get("comparator_arm") != comparator
            or row.get("scientific_status")
            != contrast_role["scientific_status"]
            or row.get("decision_role") != contrast_role["decision_role"]
            or row.get("primary_efficacy_rule_satisfaction_allowed")
            is not contrast_role[
                "primary_efficacy_rule_satisfaction_allowed"
            ]
            or row.get("promotion_equivalent_efficacy_allowed")
            is not contrast_role["promotion_equivalent_efficacy_allowed"]
            or row.get("comparison_resource_class") != (
                "equal-compute" if _POLICY_BY_ARM[challenger][
                    "equal_compute_comparison"
                ] else "unequal-resource-dose-not-equal-compute"
            )
            or row.get("challenger_weekly_maximum_micro") != challenger_score
            or row.get("comparator_weekly_maximum_micro") != comparator_score
            or row.get("paired_delta_micro") != delta
            or row.get("sign") != expected_sign
            or row.get("threshold_hit_deltas") != expected_thresholds
        ):
            _fail("paired operational contrast arithmetic differs")
    prefix_pairs = _sequence(
        grade.get("paired_prefix_contrasts"), label="paired prefix contrasts"
    )
    expected_pairs = []
    for count in reporting:
        for challenger in ARM_ORDER[1:]:
            comparator = COMPARATOR_BY_ARM[challenger]
            contrast_role = _CONTRAST_DECISION_ROLES[challenger]
            challenger_score = int(next(
                row for row in by_arm[challenger]["prefix_results"]
                if row["entry_count"] == count
            )["selected_weekly_maximum_micro"])
            comparator_score = int(next(
                row for row in by_arm[comparator]["prefix_results"]
                if row["entry_count"] == count
            )["selected_weekly_maximum_micro"])
            expected_pairs.append({
                "entry_count": count,
                "challenger_arm": challenger,
                "comparator_arm": comparator,
                "scientific_status": contrast_role["scientific_status"],
                "decision_role": contrast_role["decision_role"],
                "primary_efficacy_rule_satisfaction_allowed": contrast_role[
                    "primary_efficacy_rule_satisfaction_allowed"
                ],
                "promotion_equivalent_efficacy_allowed": contrast_role[
                    "promotion_equivalent_efficacy_allowed"
                ],
                "comparison_resource_class": (
                    "equal-compute" if _POLICY_BY_ARM[challenger][
                        "equal_compute_comparison"
                    ] else "unequal-resource-dose-not-equal-compute"
                ),
                "paired_delta_micro": challenger_score - comparator_score,
            })
    if prefix_pairs != expected_pairs:
        _fail("paired prefix contrasts differ")
    raw_cells = _sequence(
        grade.get("retrieval_crossing_cells"),
        label="generation x retrieval crossing cells",
    )
    expected_keys = [
        (arm, retrieval)
        for arm in _RETRIEVAL_CROSSING_ARMS
        for retrieval in (_BASE_RETRIEVAL_ID, _CAP4_RETRIEVAL_ID)
    ]
    cells: list[dict[str, object]] = []
    for raw, (generation_arm, retrieval_id) in zip(
        raw_cells, expected_keys, strict=True
    ):
        cell = _mapping(raw, label="generation x retrieval cell")
        if set(cell) != {
            "generation_arm", "retrieval_id", "population_label", "cap_label",
            "operational_weekly_maximum_micro", "prefix_results",
        }:
            _fail("generation x retrieval cell fields differ")
        prefixes = [
            _validate_prefix_grade(
                row,
                arm_id=f"{generation_arm}/{retrieval_id}",
                field_available=bool(field_available),
            )
            for row in _sequence(
                cell.get("prefix_results"), label="retrieval cell prefixes"
            )
        ]
        operational = next(
            (row for row in prefixes if row["entry_count"] == k), None
        )
        if (
            cell.get("generation_arm") != generation_arm
            or cell.get("retrieval_id") != retrieval_id
            or cell.get("cap_label") != retrieval_id
            or [row["entry_count"] for row in prefixes] != reporting
            or operational is None
            or cell.get("operational_weekly_maximum_micro")
            != operational["selected_weekly_maximum_micro"]
        ):
            _fail("generation x retrieval cell arithmetic differs")
        _identifier(cell.get("population_label"), label="retrieval population")
        cells.append(cell)
    if (
        len(raw_cells) != len(expected_keys)
        or grade.get("retrieval_crossing_cells_sha256")
        != canonical_sha256_v1(cells)
    ):
        _fail("generation x retrieval crossing lattice differs")
    cell_by_key = {
        (cell["generation_arm"], cell["retrieval_id"]): int(
            cell["operational_weekly_maximum_micro"]
        )
        for cell in cells
    }
    incumbent_arm, boom_arm = _RETRIEVAL_CROSSING_ARMS
    inc_base = cell_by_key[(incumbent_arm, _BASE_RETRIEVAL_ID)]
    inc_cap4 = cell_by_key[(incumbent_arm, _CAP4_RETRIEVAL_ID)]
    boom_base = cell_by_key[(boom_arm, _BASE_RETRIEVAL_ID)]
    boom_cap4 = cell_by_key[(boom_arm, _CAP4_RETRIEVAL_ID)]
    expected_interaction = {
        "generation_effect_under_incumbent_retrieval_micro": boom_base - inc_base,
        "generation_effect_under_cap4_retrieval_micro": boom_cap4 - inc_cap4,
        "retrieval_effect_on_incumbent_generation_micro": inc_cap4 - inc_base,
        "retrieval_effect_on_boom_first_generation_micro": boom_cap4 - boom_base,
        "difference_in_differences_micro": (
            (boom_cap4 - boom_base) - (inc_cap4 - inc_base)
        ),
        "key_secondary_not_primary": True,
        **deepcopy(_RETRIEVAL_DECISION_ROLE),
    }
    if grade.get("retrieval_interaction") != expected_interaction:
        _fail("generation x retrieval interaction arithmetic differs")
    return grade


_T_975_BY_DF: Final = {
    1: 12.706205, 2: 4.302653, 3: 3.182446, 4: 2.776445,
    5: 2.570582, 6: 2.446912, 7: 2.364624, 8: 2.306004,
    9: 2.262157, 10: 2.228139, 11: 2.200985, 12: 2.178813,
    13: 2.160369, 14: 2.144787, 15: 2.131450, 16: 2.119905,
    17: 2.109816,
}


def _paired_interval_95pct(values: Sequence[int]) -> dict[str, object] | None:
    """Return the frozen slate-paired t interval for one effect vector."""

    n = len(values)
    if n < 2:
        return None
    if n - 1 not in _T_975_BY_DF:
        _fail("paired interval exceeds the frozen 18-week season horizon")
    value_sum = sum(values)
    sum_squares = sum(value * value for value in values)
    variance_of_mean = (
        (n * sum_squares - value_sum * value_sum) / (n * n * (n - 1))
    )
    half_width = math.ceil(
        _T_975_BY_DF[n - 1] * math.sqrt(max(0.0, variance_of_mean))
    )
    point = value_sum / n
    return {
        "method": (
            "slate-level-paired-t-interval-95pct"
            if n == FULL_SEASON_WEEK_COUNT
            else "descriptive-slate-level-paired-t-interval-95pct-not-a-decision"
        ),
        "point_estimate_micro": {
            "numerator": value_sum,
            "denominator": n,
        },
        "lower_micro": math.floor(point - half_width),
        "upper_micro": math.ceil(point + half_width),
        "half_width_micro": half_width,
    }


def _effect_summary(values: Sequence[int]) -> dict[str, object]:
    return {
        "mean_micro": {
            "numerator": sum(values),
            "denominator": len(values),
        },
        "slate_level_values_micro": list(values),
        "uncertainty_95pct": _paired_interval_95pct(values),
    }


def _aggregate_retrieval_prefix_rows(
    rows: Sequence[Mapping[str, object]], *, entry_count: int,
) -> dict[str, object]:
    scores = [int(row["selected_weekly_maximum_micro"]) for row in rows]
    oracles = [int(row["pool_oracle_micro"]) for row in rows]
    regrets = [int(row["selector_regret_micro"]) for row in rows]
    field_rows = [row["field_metrics"] for row in rows if row["field_metrics"]]
    field_count = len(field_rows)
    return {
        "entry_count": entry_count,
        "week_count": len(rows),
        "mean_weekly_maximum_micro": {
            "numerator": sum(scores), "denominator": len(rows),
        },
        "mean_pool_oracle_micro": {
            "numerator": sum(oracles), "denominator": len(rows),
        },
        "mean_selector_regret_micro": {
            "numerator": sum(regrets), "denominator": len(rows),
        },
        "threshold_hit_counts": {
            str(threshold): sum(
                bool(next(
                    cell for cell in row["thresholds"]
                    if cell["threshold_dk"] == threshold
                )["realized_hit"])
                for row in rows
            )
            for threshold in REALIZED_THRESHOLDS_DK
        },
        "field_availability": {
            "complete_field_capture_week_count": field_count,
            "missing_field_capture_week_count": len(rows) - field_count,
            "complete_for_every_week": field_count == len(rows),
            "evidence_scope": (
                "complete-field-every-week"
                if field_count == len(rows)
                else "partial-complete-field"
                if field_count
                else "raw-score-only-no-complete-field"
            ),
        },
        "complete_field_metrics": (
            {
                "best_counterfactual_field_rank": min(
                    int(row["best_counterfactual_field_rank_in_prefix"])
                    for row in field_rows
                ),
                "best_counterfactual_field_percentile_ppm": max(
                    int(row[
                        "best_counterfactual_field_percentile_ppm_in_prefix"
                    ])
                    for row in field_rows
                ),
                "best_actual_field_rank": (
                    min(
                        int(row["best_actual_field_rank_in_prefix"])
                        for row in field_rows
                        if row["best_actual_field_rank_in_prefix"] is not None
                    )
                    if any(
                        row["best_actual_field_rank_in_prefix"] is not None
                        for row in field_rows
                    ) else None
                ),
                "best_actual_field_percentile_ppm": (
                    max(
                        int(row["best_actual_field_percentile_ppm_in_prefix"])
                        for row in field_rows
                        if row[
                            "best_actual_field_percentile_ppm_in_prefix"
                        ] is not None
                    )
                    if any(
                        row["best_actual_field_percentile_ppm_in_prefix"]
                        is not None
                        for row in field_rows
                    ) else None
                ),
                "entered_lineup_observation_count": sum(
                    int(row["entered_lineup_count_in_prefix"])
                    for row in field_rows
                ),
                "total_actual_split_payout_micro": sum(
                    int(row["total_actual_prefix_split_payout_micro"])
                    for row in field_rows
                ),
                "best_lineup_duplicate_observation_count": len(field_rows),
                "best_lineup_duplicate_sum": sum(
                    int(row["best_realized_lineup_duplicates"])
                    for row in field_rows
                ),
                "actual_entered_best_lineup_week_count": sum(
                    bool(row["best_realized_lineup_entered_in_contest"])
                    for row in field_rows
                ),
                "contest_ev_imputed": False,
            }
            if field_rows else None
        ),
    }


def _aggregate_arm_results(
    grades: Sequence[Mapping[str, object]], *, arm_id: str,
) -> dict[str, object]:
    first = next(
        row for row in grades[0]["arm_results"] if row["arm_id"] == arm_id
    )
    reporting = [int(value) for value in grades[0]["reporting_entry_counts"]]
    prefix_aggregates = []
    for count in reporting:
        rows = [next(
            prefix
            for arm in grade["arm_results"] if arm["arm_id"] == arm_id
            for prefix in arm["prefix_results"] if prefix["entry_count"] == count
        ) for grade in grades]
        scores = [int(row["selected_weekly_maximum_micro"]) for row in rows]
        oracles = [int(row["pool_oracle_micro"]) for row in rows]
        regrets = [int(row["selector_regret_micro"]) for row in rows]
        threshold_counts = {
            str(threshold): sum(
                bool(next(
                    cell for cell in row["thresholds"]
                    if cell["threshold_dk"] == threshold
                )["realized_hit"])
                for row in rows
            )
            for threshold in REALIZED_THRESHOLDS_DK
        }
        field_rows = [row["field_metrics"] for row in rows if row["field_metrics"]]
        prefix_aggregates.append({
            "entry_count": count,
            "week_count": len(rows),
            "mean_weekly_maximum_micro": {
                "numerator": sum(scores), "denominator": len(scores),
            },
            "mean_pool_oracle_micro": {
                "numerator": sum(oracles), "denominator": len(oracles),
            },
            "mean_selector_regret_micro": {
                "numerator": sum(regrets), "denominator": len(regrets),
            },
            "threshold_hit_counts": threshold_counts,
            "complete_field_capture_week_count": len(field_rows),
            "complete_field_metrics": (
                {
                    "best_counterfactual_field_rank": min(
                        int(row["best_counterfactual_field_rank_in_prefix"])
                        for row in field_rows
                    ),
                    "best_counterfactual_field_percentile_ppm": max(
                        int(row[
                            "best_counterfactual_field_percentile_ppm_in_prefix"
                        ])
                        for row in field_rows
                    ),
                    "best_actual_field_rank": (
                        min(
                            int(row["best_actual_field_rank_in_prefix"])
                            for row in field_rows
                            if row["best_actual_field_rank_in_prefix"] is not None
                        )
                        if any(
                            row["best_actual_field_rank_in_prefix"] is not None
                            for row in field_rows
                        ) else None
                    ),
                    "best_actual_field_percentile_ppm": (
                        max(
                            int(row[
                                "best_actual_field_percentile_ppm_in_prefix"
                            ])
                            for row in field_rows
                            if row[
                                "best_actual_field_percentile_ppm_in_prefix"
                            ] is not None
                        )
                        if any(
                            row[
                                "best_actual_field_percentile_ppm_in_prefix"
                            ] is not None
                            for row in field_rows
                        ) else None
                    ),
                    "entered_lineup_observation_count": sum(
                        int(row["entered_lineup_count_in_prefix"])
                        for row in field_rows
                    ),
                    "total_actual_payout_micro": sum(
                        int(row["total_actual_prefix_split_payout_micro"])
                        for row in field_rows
                    ),
                    "mean_best_lineup_duplicates": {
                        "numerator": sum(
                            int(row["best_realized_lineup_duplicates"])
                            for row in field_rows
                        ),
                        "denominator": len(field_rows),
                    },
                } if field_rows else None
            ),
        })
    return {
        "arm_id": arm_id,
        "population_label": first["population_label"],
        "cap_label": first["cap_label"],
        "arm_status": first["arm_status"],
        "scientific_status": first["scientific_status"],
        "decision_role": first["decision_role"],
        "required_before_week1": first["required_before_week1"],
        "resource_class": first["resource_class"],
        "resource_caveat": first["resource_caveat"],
        "equal_compute_comparison": first["equal_compute_comparison"],
        "prefix_aggregates": prefix_aggregates,
    }


def _calibration_cells(
    grades: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    cells = []
    reporting = [int(value) for value in grades[0]["reporting_entry_counts"]]
    for arm_id in ARM_ORDER:
        first_arm = next(
            row for row in grades[0]["arm_results"] if row["arm_id"] == arm_id
        )
        for count in reporting:
            for threshold in CALIBRATION_THRESHOLDS_DK:
                rows = [next(
                    cell
                    for arm in grade["arm_results"] if arm["arm_id"] == arm_id
                    for prefix in arm["prefix_results"]
                    if prefix["entry_count"] == count
                    for cell in prefix["cap_calibration"]
                    if cell["threshold_dk"] == threshold
                ) for grade in grades]
                modeled_sum = sum(
                    int(row["modeled_probability_ppm"]) for row in rows
                )
                realized_hits = sum(int(row["realized_indicator"]) for row in rows)
                cells.append({
                    "arm_id": arm_id,
                    "population_label": first_arm["population_label"],
                    "cap_label": first_arm["cap_label"],
                    "population_cap_label": (
                        f"{first_arm['population_label']}x{first_arm['cap_label']}"
                    ),
                    "entry_count": count,
                    "threshold_dk": threshold,
                    "week_count": len(rows),
                    "modeled_probability_mean_ppm": {
                        "numerator": modeled_sum,
                        "denominator": len(rows),
                    },
                    "realized_hit_rate": {
                        "numerator": realized_hits,
                        "denominator": len(rows),
                    },
                    "calibration_residual_mean_ppm": {
                        "numerator": realized_hits * PROBABILITY_SCALE
                        - modeled_sum,
                        "denominator": len(rows),
                    },
                    "brier_loss_sum_ppm_squared": sum(
                        int(row["brier_loss_ppm_squared"]) for row in rows
                    ),
                })
    for arm_id in _RETRIEVAL_CROSSING_ARMS:
        first_cell = next(
            cell for cell in grades[0]["retrieval_crossing_cells"]
            if cell["generation_arm"] == arm_id
            and cell["retrieval_id"] == _CAP4_RETRIEVAL_ID
        )
        for count in reporting:
            for threshold in CALIBRATION_THRESHOLDS_DK:
                rows = [next(
                    calibration
                    for cell in grade["retrieval_crossing_cells"]
                    if cell["generation_arm"] == arm_id
                    and cell["retrieval_id"] == _CAP4_RETRIEVAL_ID
                    for prefix in cell["prefix_results"]
                    if prefix["entry_count"] == count
                    for calibration in prefix["cap_calibration"]
                    if calibration["threshold_dk"] == threshold
                ) for grade in grades]
                modeled_sum = sum(
                    int(row["modeled_probability_ppm"]) for row in rows
                )
                realized_hits = sum(int(row["realized_indicator"]) for row in rows)
                cells.append({
                    "arm_id": arm_id,
                    "population_label": first_cell["population_label"],
                    "cap_label": first_cell["cap_label"],
                    "population_cap_label": (
                        f"{first_cell['population_label']}x{first_cell['cap_label']}"
                    ),
                    "entry_count": count,
                    "threshold_dk": threshold,
                    "week_count": len(rows),
                    "modeled_probability_mean_ppm": {
                        "numerator": modeled_sum, "denominator": len(rows),
                    },
                    "realized_hit_rate": {
                        "numerator": realized_hits, "denominator": len(rows),
                    },
                    "calibration_residual_mean_ppm": {
                        "numerator": realized_hits * PROBABILITY_SCALE - modeled_sum,
                        "denominator": len(rows),
                    },
                    "brier_loss_sum_ppm_squared": sum(
                        int(row["brier_loss_ppm_squared"]) for row in rows
                    ),
                })
    return cells


def _build_prospective_shadow_evaluation_v1(
    *, preregistration: Mapping[str, object],
    weekly_grades: Sequence[Mapping[str, object]],
    weekly_safety_receipts: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Evaluate only paired prospective weeks under the pre-Week-1 rule."""

    prereg = validate_preregistration_v1(preregistration)
    grades = [validate_realized_week_grade_v1(grade) for grade in weekly_grades]
    safety_receipts = [
        validate_weekly_safety_receipt_v1(
            receipt, preregistration=prereg
        )
        for receipt in weekly_safety_receipts
    ]
    if not grades and not safety_receipts:
        _fail("prospective evaluation requires a weekly grade or safety receipt")
    grades.sort(key=lambda grade: int(grade["week"]))
    weeks = [int(grade["week"]) for grade in grades]
    if len(weeks) != len(set(weeks)):
        _fail("prospective weekly grades contain a duplicate week")
    if len(grades) > FULL_SEASON_WEEK_COUNT:
        _fail("prospective evaluation exceeds the frozen season horizon")
    safety_receipts.sort(key=lambda receipt: int(receipt["week"]))
    safety_weeks = [int(receipt["week"]) for receipt in safety_receipts]
    if len(safety_weeks) != len(set(safety_weeks)):
        _fail("prospective safety receipts contain a duplicate week")
    represented_weeks = sorted(set(weeks) | set(safety_weeks))
    completed = max(represented_weeks)
    if completed > FULL_SEASON_WEEK_COUNT:
        _fail("prospective evaluation exceeds the frozen season horizon")
    if represented_weeks != list(range(1, completed + 1)):
        _fail("prospective weekly evidence is not complete and contiguous")
    missing_grade_weeks = sorted(set(represented_weeks) - set(weeks))
    if any(week > INTERIM_WEEK_COUNT for week in missing_grade_weeks):
        _fail("post-interim missing weekly grades lack a frozen safety receipt law")
    if len({str(grade["seed_crossing_sha256"]) for grade in grades}) != len(
        grades
    ):
        _fail("weekly fit-seed x world-seed crossing authorities are reused")
    first_labels = (
        [
            (arm["arm_id"], arm["population_label"], arm["cap_label"])
            for arm in grades[0]["arm_results"]
        ]
        if grades
        else []
    )
    for grade in grades:
        labels = [
            (arm["arm_id"], arm["population_label"], arm["cap_label"])
            for arm in grade["arm_results"]
        ]
        if (
            grade["preregistration_sha256"] != prereg["preregistration_sha256"]
            or grade["operational_k"] != prereg["operational_k"]
            or grade["reporting_entry_counts"]
            != prereg["reporting_entry_counts"]
            or labels != first_labels
        ):
            _fail("weekly grade preregistration or population x cap labels drift")
    grade_by_week = {int(grade["week"]): grade for grade in grades}
    for receipt in safety_receipts:
        grade = grade_by_week.get(int(receipt["week"]))
        if grade is None:
            continue
        if grade["slate_id"] != receipt["slate_id"]:
            _fail("weekly grade and safety receipt slate identities differ")
        terminal_authority = receipt["terminal_safety_authority"]
        terminal_envelope = receipt["terminal_prelock_envelope"]
        if terminal_authority is None or terminal_envelope is None:
            _fail("weekly grade lacks a terminal-present safety lineage")
        safety_root_identity = normalize_object_identity_v1(
            _mapping(
                terminal_envelope,
                label="weekly safety terminal envelope",
            )["identity"],
            label="weekly safety terminal root identity",
        )
        if (
            grade["terminal_prelock_root_identity"] != safety_root_identity
            or grade["terminal_prelock_root_sha256"]
            != terminal_authority["terminal_prelock_root_sha256"]
        ):
            _fail("weekly grade and safety receipt root lineages differ")
    arm_aggregates = (
        [
            _aggregate_arm_results(grades, arm_id=arm_id)
            for arm_id in ARM_ORDER
        ]
        if grades
        else []
    )
    paired_aggregates = []
    for challenger in ARM_ORDER[1:] if grades else ():
        comparator = COMPARATOR_BY_ARM[challenger]
        contrast_role = _CONTRAST_DECISION_ROLES[challenger]
        rows = [next(
            row for row in grade["paired_operational_contrasts"]
            if row["challenger_arm"] == challenger
        ) for grade in grades]
        deltas = [int(row["paired_delta_micro"]) for row in rows]
        threshold_hit_deltas = {
            str(threshold): sum(
                int(row["threshold_hit_deltas"][str(threshold)]) for row in rows
            )
            for threshold in REALIZED_THRESHOLDS_DK
        }
        uncertainty = _paired_interval_95pct(deltas)
        paired_aggregates.append({
            "challenger_arm": challenger,
            "comparator_arm": comparator,
            "scientific_status": contrast_role["scientific_status"],
            "decision_role": contrast_role["decision_role"],
            "primary_efficacy_rule_satisfaction_allowed": contrast_role[
                "primary_efficacy_rule_satisfaction_allowed"
            ],
            "promotion_equivalent_efficacy_allowed": contrast_role[
                "promotion_equivalent_efficacy_allowed"
            ],
            "comparison_resource_class": (
                "equal-compute" if _POLICY_BY_ARM[challenger][
                    "equal_compute_comparison"
                ] else "unequal-resource-dose-not-equal-compute"
            ),
            "week_count": len(rows),
            "paired_mean_delta_micro": {
                "numerator": sum(deltas), "denominator": len(deltas),
            },
            "win_count": sum(delta > 0 for delta in deltas),
            "tie_count": sum(delta == 0 for delta in deltas),
            "loss_count": sum(delta < 0 for delta in deltas),
            "threshold_hit_deltas": threshold_hit_deltas,
            "slate_level_delta_values_micro": deltas,
            "uncertainty_95pct": uncertainty,
        })
    calibration = _calibration_cells(grades) if grades else []

    safety_rule = _mapping(
        prereg["week8_safety_rule"], label="evaluation Week-8 safety rule"
    )
    expected_safety_weeks = [
        int(value) for value in safety_rule["receipt_weeks"]
    ]
    missing_safety_weeks = sorted(
        set(expected_safety_weeks) - set(safety_weeks)
    )
    safety_metric_fields = tuple(
        str(key)
        for key in (
            "missing_terminal_count",
            "missing_suite_manifest_count",
            "missing_expected_arm_count",
            "missing_expected_book_count",
            "missing_expected_block_count",
            "missing_expected_prefix_count",
            "missing_required_source_count",
            "stale_required_source_count",
            "missing_evidence_authority_count",
            "illegal_lineup_count",
            "solve_failure_count",
            "solve_request_shortfall_count",
            "exposure_violation_count",
            "duplicate_lineup_count",
        )
    )
    def optional_metric_total(field: str) -> int | None:
        values = [
            _mapping(
                receipt["safety_metrics"], label="weekly safety metrics"
            )[field]
            for receipt in safety_receipts
        ]
        if any(value is None for value in values):
            return None
        return sum(int(value) for value in values)

    metric_totals = {
        field: optional_metric_total(field) for field in safety_metric_fields
    }
    solve_failure_status_count_totals = {
        status: (
            None
            if any(
                _mapping(
                    _mapping(
                        receipt["safety_metrics"],
                        label="weekly safety metrics",
                    )["solve_failure_status_counts"],
                    label="weekly solve failure status counts",
                )[status] is None
                for receipt in safety_receipts
            )
            else sum(
                int(_mapping(
                    _mapping(
                        receipt["safety_metrics"],
                        label="weekly safety metrics",
                    )["solve_failure_status_counts"],
                    label="weekly solve failure status counts",
                )[status])
                for receipt in safety_receipts
            )
        )
        for status in safety_rule["solve_failure_statuses"]
    }
    raw_maximum_exposures = [
        _mapping(
                receipt["safety_metrics"], label="weekly safety metrics"
        )["maximum_observed_player_exposure_bps"]
        for receipt in safety_receipts
    ]
    maximum_exposure_bps = (
        None
        if not raw_maximum_exposures
        or any(value is None for value in raw_maximum_exposures)
        else max(int(value) for value in raw_maximum_exposures)
    )
    failed_week_reasons = [
        {
            "week": receipt["week"],
            "slate_id": receipt["slate_id"],
            "reason_vector": receipt["reason_vector"],
        }
        for receipt in safety_receipts
        if receipt["integrity_gate_status"] == "fail"
    ]
    if failed_week_reasons:
        integrity_status = "fail"
    elif not missing_safety_weeks:
        integrity_status = "pass"
    else:
        integrity_status = str(safety_rule["missing_receipt_status"])
    integrity_reasons = [
        f"week-{row['week']}:{reason}"
        for row in failed_week_reasons
        for reason in row["reason_vector"]
    ]
    if missing_safety_weeks:
        integrity_reasons.append("missing-weekly-safety-receipts")
    integrity_gate = {
        "receipt_schema_version": WEEKLY_SAFETY_RECEIPT_SCHEMA,
        "expected_receipt_weeks": expected_safety_weeks,
        "received_receipt_weeks": safety_weeks,
        "missing_receipt_weeks": missing_safety_weeks,
        "receipt_count": len(safety_receipts),
        "pass_count": sum(
            receipt["integrity_gate_status"] == "pass"
            for receipt in safety_receipts
        ),
        "fail_count": len(failed_week_reasons),
        "complete_receipt_set": not missing_safety_weeks,
        "metric_totals": metric_totals,
        "solve_failure_status_count_totals": (
            solve_failure_status_count_totals
        ),
        "maximum_observed_player_exposure_bps": maximum_exposure_bps,
        "failed_week_reasons": failed_week_reasons,
        "reason_vector": integrity_reasons,
        "integrity_gate_status": integrity_status,
        "safety_receipt_set_sha256": canonical_sha256_v1(safety_receipts),
        "efficacy_or_promotion_allowed": False,
    }
    if completed < INTERIM_WEEK_COUNT:
        horizon = "accrual-before-eight-week-interim"
        decision_scope = "not-yet-eligible"
    elif completed == INTERIM_WEEK_COUNT:
        horizon = "eight-week-integrity-severe-harm-only"
        decision_scope = "integrity-and-severe-harm-only"
    elif completed < FULL_SEASON_WEEK_COUNT:
        horizon = "post-interim-accrual-no-decision"
        decision_scope = "not-eligible-between-frozen-checkpoints"
    else:
        horizon = "full-season-first-efficacy-estimate"
        decision_scope = "efficacy-estimate-with-uncertainty-no-auto-adoption"
    rule = prereg["family_level_decision_rule"]
    decisions = []
    for aggregate in paired_aggregates:
        challenger = str(aggregate["challenger_arm"])
        contrast_role = _CONTRAST_DECISION_ROLES[challenger]
        n = int(aggregate["week_count"])
        delta_sum = int(aggregate["paired_mean_delta_micro"]["numerator"])
        mean_ok = delta_sum >= int(
            rule["minimum_paired_mean_delta_micro"]
        ) * n
        wins_ok = int(aggregate["win_count"]) * 10_000 >= int(
            rule["minimum_win_rate_bps"]
        ) * n
        hit_ok = int(aggregate["threshold_hit_deltas"]["194"]) >= int(
            rule["minimum_194_hit_delta"]
        )
        tail_ok = all(
            int(aggregate["threshold_hit_deltas"][str(threshold)])
            >= -int(rule["maximum_tail_hit_deficit"])
            for threshold in rule["tail_noninferiority_thresholds_dk"]
        )
        checkpoint = completed in {INTERIM_WEEK_COUNT, FULL_SEASON_WEEK_COUNT}
        full_season_integrity_eligible = (
            completed == FULL_SEASON_WEEK_COUNT
            and weeks == list(range(1, FULL_SEASON_WEEK_COUNT + 1))
            and integrity_status == "pass"
        )
        primary_rule_allowed = bool(
            contrast_role["primary_efficacy_rule_satisfaction_allowed"]
        )
        efficacy_eligible = (
            full_season_integrity_eligible and primary_rule_allowed
        )
        diagnostic_criteria_satisfied = (
            mean_ok and wins_ok and hit_ok and tail_ok
        )
        primary_efficacy_rule_satisfied = (
            efficacy_eligible and diagnostic_criteria_satisfied
        )
        severe_harm = any(
            delta <= int(rule["catastrophic_paired_delta_micro"])
            for delta in aggregate["slate_level_delta_values_micro"]
        )
        decisions.append({
            "challenger_arm": challenger,
            "comparator_arm": aggregate["comparator_arm"],
            "scientific_status": contrast_role["scientific_status"],
            "decision_role": contrast_role["decision_role"],
            "numeric_diagnostic_criteria_reported": contrast_role[
                "numeric_diagnostic_criteria_reported"
            ],
            "primary_efficacy_rule_satisfaction_allowed": primary_rule_allowed,
            "promotion_equivalent_efficacy_allowed": contrast_role[
                "promotion_equivalent_efficacy_allowed"
            ],
            "automatic_promotion_allowed": contrast_role[
                "automatic_promotion_allowed"
            ],
            "checkpoint_eligible": checkpoint,
            "interim_integrity_only": completed == INTERIM_WEEK_COUNT,
            "full_season_integrity_eligible": full_season_integrity_eligible,
            "efficacy_eligible": efficacy_eligible,
            "integrity_gate_status": integrity_status,
            "severe_harm_gate_triggered": severe_harm,
            "mean_delta_criterion_met": mean_ok,
            "win_rate_criterion_met": wins_ok,
            "threshold_194_criterion_met": hit_ok,
            "tail_noninferiority_criterion_met": tail_ok,
            "diagnostic_criteria_satisfied": diagnostic_criteria_satisfied,
            "primary_efficacy_rule_satisfied": (
                primary_efficacy_rule_satisfied
            ),
            "efficacy_rule_satisfied": primary_efficacy_rule_satisfied,
            "efficacy_promotion_authorized": False,
        })
    reporting_counts = [int(value) for value in prereg["reporting_entry_counts"]]

    def retrieval_cell(
        grade: Mapping[str, object], *, generation_arm: str, retrieval_id: str,
    ) -> Mapping[str, object]:
        return next(
            cell for cell in grade["retrieval_crossing_cells"]
            if cell["generation_arm"] == generation_arm
            and cell["retrieval_id"] == retrieval_id
        )

    def retrieval_prefix(
        grade: Mapping[str, object], *, generation_arm: str,
        retrieval_id: str, entry_count: int,
    ) -> Mapping[str, object]:
        cell = retrieval_cell(
            grade, generation_arm=generation_arm, retrieval_id=retrieval_id
        )
        return next(
            row for row in cell["prefix_results"]
            if row["entry_count"] == entry_count
        )

    retrieval_cells = []
    if grades:
        for generation_arm in _RETRIEVAL_CROSSING_ARMS:
            for retrieval_id in (_BASE_RETRIEVAL_ID, _CAP4_RETRIEVAL_ID):
                cells = [
                    retrieval_cell(
                        grade,
                        generation_arm=generation_arm,
                        retrieval_id=retrieval_id,
                    )
                    for grade in grades
                ]
                prefix_aggregates = []
                for count in reporting_counts:
                    rows = [
                        retrieval_prefix(
                            grade,
                            generation_arm=generation_arm,
                            retrieval_id=retrieval_id,
                            entry_count=count,
                        )
                        for grade in grades
                    ]
                    prefix_aggregates.append(
                        _aggregate_retrieval_prefix_rows(
                            rows, entry_count=count
                        )
                    )
                operational = next(
                    row for row in prefix_aggregates
                    if row["entry_count"] == prereg["operational_k"]
                )
                retrieval_cells.append({
                    "generation_arm": generation_arm,
                    "retrieval_id": retrieval_id,
                    "population_label": cells[0]["population_label"],
                    "cap_label": cells[0]["cap_label"],
                    "week_count": len(grades),
                    "mean_weekly_maximum_micro": operational[
                        "mean_weekly_maximum_micro"
                    ],
                    "prefix_aggregates": prefix_aggregates,
                })

    retrieval_effect_aggregates = []
    retrieval_interaction_prefixes = []
    metric_fields = (
        ("selected_weekly_maximum", "selected_weekly_maximum_micro"),
        ("pool_oracle", "pool_oracle_micro"),
        ("selector_regret", "selector_regret_micro"),
    )
    for count in reporting_counts if grades else ():
        rows_by_cell = {
            (generation_arm, retrieval_id): [
                retrieval_prefix(
                    grade,
                    generation_arm=generation_arm,
                    retrieval_id=retrieval_id,
                    entry_count=count,
                )
                for grade in grades
            ]
            for generation_arm in _RETRIEVAL_CROSSING_ARMS
            for retrieval_id in (_BASE_RETRIEVAL_ID, _CAP4_RETRIEVAL_ID)
        }
        for generation_arm in _RETRIEVAL_CROSSING_ARMS:
            base_rows = rows_by_cell[(generation_arm, _BASE_RETRIEVAL_ID)]
            cap_rows = rows_by_cell[(generation_arm, _CAP4_RETRIEVAL_ID)]
            metric_effects = {
                f"{label}_effect": _effect_summary([
                    int(cap[field]) - int(base[field])
                    for base, cap in zip(base_rows, cap_rows, strict=True)
                ])
                for label, field in metric_fields
            }
            threshold_deltas = {
                str(threshold): sum(
                    int(next(
                        cell for cell in cap["thresholds"]
                        if cell["threshold_dk"] == threshold
                    )["realized_hit"])
                    - int(next(
                        cell for cell in base["thresholds"]
                        if cell["threshold_dk"] == threshold
                    )["realized_hit"])
                    for base, cap in zip(base_rows, cap_rows, strict=True)
                )
                for threshold in REALIZED_THRESHOLDS_DK
            }
            field_pair_count = sum(
                base["field_metrics"] is not None
                and cap["field_metrics"] is not None
                for base, cap in zip(base_rows, cap_rows, strict=True)
            )
            retrieval_effect_aggregates.append({
                "generation_arm": generation_arm,
                "entry_count": count,
                "week_count": len(grades),
                "retrieval_contrast": (
                    f"{_CAP4_RETRIEVAL_ID}-minus-{_BASE_RETRIEVAL_ID}"
                ),
                **metric_effects,
                "threshold_hit_deltas": threshold_deltas,
                "field_availability": {
                    "paired_complete_field_week_count": field_pair_count,
                    "paired_missing_field_week_count": (
                        len(grades) - field_pair_count
                    ),
                    "complete_for_every_paired_week": (
                        field_pair_count == len(grades)
                    ),
                },
            })

        effect_families: dict[str, object] = {}
        for label, field in metric_fields:
            inc_base = rows_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[0], _BASE_RETRIEVAL_ID)
            ]
            inc_cap = rows_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[0], _CAP4_RETRIEVAL_ID)
            ]
            boom_base = rows_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[1], _BASE_RETRIEVAL_ID)
            ]
            boom_cap = rows_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[1], _CAP4_RETRIEVAL_ID)
            ]
            vectors = {
                "generation_effect_under_incumbent_retrieval": [
                    int(boom[field]) - int(inc[field])
                    for inc, boom in zip(inc_base, boom_base, strict=True)
                ],
                "generation_effect_under_cap4_retrieval": [
                    int(boom[field]) - int(inc[field])
                    for inc, boom in zip(inc_cap, boom_cap, strict=True)
                ],
                "retrieval_effect_on_incumbent_generation": [
                    int(cap[field]) - int(base[field])
                    for base, cap in zip(inc_base, inc_cap, strict=True)
                ],
                "retrieval_effect_on_boom_first_generation": [
                    int(cap[field]) - int(base[field])
                    for base, cap in zip(boom_base, boom_cap, strict=True)
                ],
            }
            vectors["difference_in_differences"] = [
                boom - incumbent
                for incumbent, boom in zip(
                    vectors["retrieval_effect_on_incumbent_generation"],
                    vectors["retrieval_effect_on_boom_first_generation"],
                    strict=True,
                )
            ]
            effect_families[label] = {
                name: _effect_summary(values)
                for name, values in vectors.items()
            }

        threshold_effects = {}
        for threshold in REALIZED_THRESHOLDS_DK:
            indicator_by_cell = {
                key: [
                    int(next(
                        cell for cell in row["thresholds"]
                        if cell["threshold_dk"] == threshold
                    )["realized_hit"])
                    for row in rows
                ]
                for key, rows in rows_by_cell.items()
            }
            inc_base_values = indicator_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[0], _BASE_RETRIEVAL_ID)
            ]
            inc_cap_values = indicator_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[0], _CAP4_RETRIEVAL_ID)
            ]
            boom_base_values = indicator_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[1], _BASE_RETRIEVAL_ID)
            ]
            boom_cap_values = indicator_by_cell[
                (_RETRIEVAL_CROSSING_ARMS[1], _CAP4_RETRIEVAL_ID)
            ]
            incumbent_retrieval_delta = [
                cap - base for base, cap in zip(
                    inc_base_values, inc_cap_values, strict=True
                )
            ]
            boom_retrieval_delta = [
                cap - base for base, cap in zip(
                    boom_base_values, boom_cap_values, strict=True
                )
            ]
            threshold_effects[str(threshold)] = {
                "generation_effect_under_incumbent_retrieval": sum(
                    boom - incumbent for incumbent, boom in zip(
                        inc_base_values, boom_base_values, strict=True
                    )
                ),
                "generation_effect_under_cap4_retrieval": sum(
                    boom - incumbent for incumbent, boom in zip(
                        inc_cap_values, boom_cap_values, strict=True
                    )
                ),
                "retrieval_effect_on_incumbent_generation": sum(
                    incumbent_retrieval_delta
                ),
                "retrieval_effect_on_boom_first_generation": sum(
                    boom_retrieval_delta
                ),
                "difference_in_differences": sum(
                    boom - incumbent for incumbent, boom in zip(
                        incumbent_retrieval_delta,
                        boom_retrieval_delta,
                        strict=True,
                    )
                ),
            }
        field_week_count = sum(
            bool(grade["field_metrics_available"]) for grade in grades
        )
        retrieval_interaction_prefixes.append({
            "entry_count": count,
            "week_count": len(grades),
            "effect_families": effect_families,
            "threshold_hit_effects": threshold_effects,
            "field_availability": {
                "complete_field_capture_week_count": field_week_count,
                "missing_field_capture_week_count": len(grades) - field_week_count,
                "complete_for_every_week": field_week_count == len(grades),
            },
        })

    operational_interaction = next(
        (
            row for row in retrieval_interaction_prefixes
            if row["entry_count"] == prereg["operational_k"]
        ),
        None,
    )
    operational_did = (
        operational_interaction["effect_families"]
        ["selected_weekly_maximum"]["difference_in_differences"]
        if operational_interaction is not None
        else None
    )
    retrieval_interaction_aggregate = {
        "week_count": len(grades),
        "difference_in_differences_mean_micro": (
            operational_did["mean_micro"] if operational_did else None
        ),
        "slate_level_values_micro": (
            operational_did["slate_level_values_micro"]
            if operational_did else []
        ),
        "uncertainty_95pct": (
            operational_did["uncertainty_95pct"] if operational_did else None
        ),
        "reporting_entry_counts": reporting_counts,
        "prefix_aggregates": retrieval_interaction_prefixes,
        "hierarchy": "key-secondary-mechanism-not-primary",
        **deepcopy(_RETRIEVAL_DECISION_ROLE),
    }

    synthesis_rule = _mapping(
        prereg["structural_synthesis_rule"],
        label="structural synthesis rule",
    )
    historical_metrics = _mapping(
        synthesis_rule["historical_metrics"],
        label="structural historical metrics",
    )
    full_season_complete = (
        weeks == list(range(1, FULL_SEASON_WEEK_COUNT + 1))
    )
    primary_aggregate = next(
        (
            row for row in paired_aggregates
            if row["challenger_arm"] == "boom-first-40-160"
        ),
        None,
    )
    primary_decision = next(
        (
            row for row in decisions
            if row["challenger_arm"] == "boom-first-40-160"
        ),
        None,
    )
    historical_selected_positive = (
        int(historical_metrics["selected_paired_delta_sum_micro"]) > 0
    )
    historical_oracle_positive = (
        int(historical_metrics["pool_oracle_paired_delta_sum_micro"]) > 0
    )
    prospective_selected_positive: bool | None = None
    prospective_oracle_positive: bool | None = None
    prospective_interval_lower_positive: bool | None = None
    prospective_guard_set_passed: bool | None = None
    if full_season_complete and primary_aggregate is not None:
        prospective_selected_positive = (
            int(primary_aggregate["paired_mean_delta_micro"]["numerator"]) > 0
        )
        interval = _mapping(
            primary_aggregate["uncertainty_95pct"],
            label="full-season primary paired interval",
        )
        prospective_interval_lower_positive = int(interval["lower_micro"]) > 0
        control_aggregate = next(
            row for row in arm_aggregates
            if row["arm_id"] == "incumbent-160-40"
        )
        boom_aggregate = next(
            row for row in arm_aggregates
            if row["arm_id"] == "boom-first-40-160"
        )
        control_k80 = next(
            row for row in control_aggregate["prefix_aggregates"]
            if row["entry_count"] == prereg["operational_k"]
        )
        boom_k80 = next(
            row for row in boom_aggregate["prefix_aggregates"]
            if row["entry_count"] == prereg["operational_k"]
        )
        prospective_oracle_positive = (
            int(boom_k80["mean_pool_oracle_micro"]["numerator"])
            * int(control_k80["mean_pool_oracle_micro"]["denominator"])
            > int(control_k80["mean_pool_oracle_micro"]["numerator"])
            * int(boom_k80["mean_pool_oracle_micro"]["denominator"])
        )
        prospective_guard_set_passed = bool(
            primary_decision
            and primary_decision["diagnostic_criteria_satisfied"]
            and primary_decision["full_season_integrity_eligible"]
        )
    condition_vector = {
        "historical_selected_effect_positive": historical_selected_positive,
        "historical_pool_oracle_effect_positive": historical_oracle_positive,
        "complete_contiguous_2026_regular_season": full_season_complete,
        "week8_integrity_gate_passed": (
            integrity_status == "pass" if full_season_complete else None
        ),
        "2026_selected_effect_direction_matches_historical": (
            prospective_selected_positive == historical_selected_positive
            if prospective_selected_positive is not None else None
        ),
        "2026_pool_oracle_effect_direction_matches_historical": (
            prospective_oracle_positive == historical_oracle_positive
            if prospective_oracle_positive is not None else None
        ),
        "2026_selected_paired_interval_lower_strictly_positive": (
            prospective_interval_lower_positive
        ),
        "2026_preregistered_mpie_win_194_tail_guard_set_passed": (
            prospective_guard_set_passed
        ),
    }
    prospective_conditions = [
        value for key, value in condition_vector.items()
        if key.startswith("2026_") or key in {
            "complete_contiguous_2026_regular_season",
            "week8_integrity_gate_passed",
        }
    ]
    synthesis_concordant = (
        full_season_complete
        and all(value is True for value in condition_vector.values())
    )
    if not full_season_complete:
        synthesis_status = "pending-2026-accrual"
        synthesis_disposition = "no-structural-decision-before-full-season"
    elif synthesis_concordant:
        synthesis_status = "concordant"
        synthesis_disposition = synthesis_rule["concordant_disposition"]
    else:
        synthesis_status = "not-concordant-or-not-resolved"
        synthesis_disposition = synthesis_rule["fallback_disposition"]
    structural_synthesis = {
        "schema_version": synthesis_rule["schema_version"],
        "synthesis_rule_sha256": canonical_sha256_v1(synthesis_rule),
        "historical_evidence_identity": deepcopy(
            synthesis_rule["historical_evidence_identity"]
        ),
        "historical_internal_grade_sha256": synthesis_rule[
            "historical_internal_grade_sha256"
        ],
        "historical_metrics": deepcopy(historical_metrics),
        "historical_metrics_sha256": canonical_sha256_v1(historical_metrics),
        "historical_evidence_role": synthesis_rule[
            "historical_evidence_role"
        ],
        "synthesis_method": synthesis_rule["synthesis_method"],
        "condition_vector": condition_vector,
        "prospective_condition_count": len(prospective_conditions),
        "prospective_conditions_satisfied_count": sum(
            value is True for value in prospective_conditions
        ),
        "concordance_status": synthesis_status,
        "disposition": synthesis_disposition,
        "historical_object_read_during_evaluation": False,
        "historical_object_reopen_required_before_human_decision": True,
        "effect_pooling_performed": False,
        "historical_and_prospective_gain_summing_performed": False,
        "automatic_adoption": False,
        "automatic_money_policy_change": False,
    }
    weekly_rows = [{
        "week": grade["week"],
        "slate_id": grade["slate_id"],
        "weekly_grade_sha256": grade["weekly_grade_sha256"],
        "terminal_prelock_root_sha256": grade["terminal_prelock_root_sha256"],
        "outcome_snapshot_sha256": grade["outcome_snapshot_sha256"],
        "seed_crossing_sha256": grade["seed_crossing_sha256"],
        "all_arms_reported": True,
    } for grade in grades]
    body: dict[str, object] = {
        "schema_version": EVALUATION_SCHEMA,
        "season": SEASON,
        "preregistration": prereg,
        "preregistration_sha256": prereg["preregistration_sha256"],
        "weekly_grades": grades,
        "weekly_grades_sha256": canonical_sha256_v1(grades),
        "weekly_safety_receipts": safety_receipts,
        "weekly_safety_receipts_sha256": canonical_sha256_v1(
            safety_receipts
        ),
        "completed_week_count": completed,
        "completed_weeks": represented_weeks,
        "graded_week_count": len(grades),
        "graded_weeks": weeks,
        "horizon": horizon,
        "decision_scope": decision_scope,
        "operational_k": prereg["operational_k"],
        "reporting_entry_counts": prereg["reporting_entry_counts"],
        "arm_order": list(ARM_ORDER),
        "all_five_arms_required_before_week1": True,
        "arm_omission_allowed": False,
        "arm_decision_roles": deepcopy(_ARM_RELEASE_CONTRACT_BY_ID),
        "contrast_decision_roles": deepcopy(_CONTRAST_DECISION_ROLES),
        "retrieval_decision_role": deepcopy(_RETRIEVAL_DECISION_ROLE),
        "only_primary_contrast_may_satisfy_efficacy_rule": True,
        "weekly_reports": weekly_rows,
        "weekly_reports_sha256": canonical_sha256_v1(weekly_rows),
        "arm_aggregates": arm_aggregates,
        "paired_aggregates": paired_aggregates,
        "retrieval_crossing_aggregates": retrieval_cells,
        "retrieval_effect_aggregates": retrieval_effect_aggregates,
        "retrieval_interaction_aggregate": retrieval_interaction_aggregate,
        "structural_synthesis": structural_synthesis,
        "population_cap_calibration": calibration,
        "family_level_decision_rule": rule,
        "week8_safety_rule": safety_rule,
        "week8_integrity_gate": integrity_gate,
        "family_rule_decisions": decisions,
        "one_family_level_rule_applied": True,
        "all_arms_reported_including_losses": (
            bool(grades) and not missing_grade_weeks
        ),
        "fit_world_crossing_designs_retained_by_week": (
            bool(grades) and not missing_grade_weeks
        ),
        "fit_world_crossing_execution_status": "not_evaluated",
        "historical_gain_inputs_consumed": full_season_complete,
        "historical_gains_summed_across_arms": False,
        "automatic_adoption": False,
        "human_decision_required": True,
        "inference_unit": "slate-after-block-and-bank-aggregation",
        "full_season_uncertainty_reported": (
            weeks == list(range(1, FULL_SEASON_WEEK_COUNT + 1))
        ),
        "eight_week_efficacy_or_promotion_performed": False,
        "complete_field_capture_week_count": sum(
            bool(grade["field_metrics_available"]) for grade in grades
        ),
        "contest_evidence_scope": (
            "no-realized-grade-evidence"
            if not grades
            else "raw-score-complete-field-ranks-and-entered-contest-ev"
            if grades and all(
                bool(grade["contest_ev_claim_allowed"]) for grade in grades
            )
            else "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
            if grades and all(
                bool(grade["field_metrics_available"]) for grade in grades
            )
            else "raw-score-only-no-contest-ev"
        ),
        "contest_ev_claim_allowed": all(
            bool(grade["contest_ev_claim_allowed"]) for grade in grades
        ) if grades else False,
        "allocation_recommendation_allowed": False,
        "complete": True,
    }
    result = _with_hash(body, field="evaluation_sha256")
    return result


def evaluate_prospective_shadow_v1(
    *, preregistration: Mapping[str, object],
    weekly_grades: Sequence[Mapping[str, object]],
    weekly_safety_receipts: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    result = _build_prospective_shadow_evaluation_v1(
        preregistration=preregistration,
        weekly_grades=weekly_grades,
        weekly_safety_receipts=weekly_safety_receipts,
    )
    return validate_prospective_shadow_evaluation_v1(result)


def validate_prospective_shadow_evaluation_v1(
    value: object,
) -> dict[str, object]:
    result = _mapping(value, label="prospective shadow evaluation")
    fields = {
        "schema_version", "season", "preregistration",
        "preregistration_sha256", "weekly_grades", "weekly_grades_sha256",
        "weekly_safety_receipts", "weekly_safety_receipts_sha256",
        "completed_week_count", "completed_weeks",
        "graded_week_count", "graded_weeks", "horizon",
        "decision_scope", "operational_k", "reporting_entry_counts",
        "arm_order", "all_five_arms_required_before_week1",
        "arm_omission_allowed", "arm_decision_roles",
        "contrast_decision_roles", "retrieval_decision_role",
        "only_primary_contrast_may_satisfy_efficacy_rule",
        "weekly_reports", "weekly_reports_sha256",
        "arm_aggregates", "paired_aggregates", "retrieval_crossing_aggregates",
        "retrieval_effect_aggregates",
        "retrieval_interaction_aggregate",
        "structural_synthesis",
        "population_cap_calibration", "family_level_decision_rule",
        "week8_safety_rule", "week8_integrity_gate",
        "family_rule_decisions", "one_family_level_rule_applied",
        "all_arms_reported_including_losses",
        "fit_world_crossing_designs_retained_by_week",
        "fit_world_crossing_execution_status",
        "historical_gain_inputs_consumed",
        "historical_gains_summed_across_arms", "automatic_adoption",
        "human_decision_required", "inference_unit",
        "full_season_uncertainty_reported",
        "eight_week_efficacy_or_promotion_performed",
        "complete_field_capture_week_count", "contest_evidence_scope",
        "contest_ev_claim_allowed", "allocation_recommendation_allowed",
        "complete", "evaluation_sha256",
    }
    if set(result) != fields:
        _fail("prospective shadow evaluation fields differ")
    _validate_self_hash(
        result, field="evaluation_sha256", label="prospective shadow evaluation"
    )
    prereg = validate_preregistration_v1(result.get("preregistration"))
    grades = [
        validate_realized_week_grade_v1(grade)
        for grade in _sequence(
            result.get("weekly_grades"), label="evaluation weekly grades"
        )
    ]
    if result.get("weekly_grades_sha256") != canonical_sha256_v1(grades):
        _fail("evaluation weekly-grade manifest differs")
    safety_receipts = [
        validate_weekly_safety_receipt_v1(
            receipt, preregistration=prereg
        )
        for receipt in _sequence(
            result.get("weekly_safety_receipts"),
            label="evaluation weekly safety receipts",
        )
    ]
    if result.get("weekly_safety_receipts_sha256") != canonical_sha256_v1(
        safety_receipts
    ):
        _fail("evaluation weekly safety-receipt manifest differs")
    expected = _build_prospective_shadow_evaluation_v1(
        preregistration=prereg,
        weekly_grades=grades,
        weekly_safety_receipts=safety_receipts,
    )
    if result != expected:
        _fail("prospective shadow evaluation arithmetic or lineage differs")
    return result


# Explicit names at the two security boundaries, plus concise compatibility
# aliases for callers that describe the same contract in domain terms.
validate_score_blind_freeze_v1 = validate_terminal_prelock_root_v1
grade_realized_v1 = grade_realized_week_v1
evaluate_season_v1 = evaluate_prospective_shadow_v1


__all__ = [
    "ARM_FREEZE_SCHEMA", "ARM_ORDER", "AUDIT_BANK_SCHEMA",
    "CALIBRATION_THRESHOLDS_DK",
    "COMPARATOR_BY_ARM", "EVALUATION_SCHEMA", "FULL_SEASON_WEEK_COUNT",
    "INTERIM_WEEK_COUNT", "OUTCOME_SNAPSHOT_SCHEMA", "PREFIX_SIZES",
    "PREREGISTRATION_SCHEMA", "PROBABILITY_SCALE", "REALIZED_SCORE_SOURCE_SCHEMA",
    "ProspectiveGenerationShadowEvaluationError", "REALIZED_THRESHOLDS_DK",
    "SEASON", "SEED_CROSSING_SCHEMA", "TERMINAL_PRELOCK_ENVELOPE_SCHEMA",
    "TERMINAL_PRELOCK_ROOT_SCHEMA", "SUITE_AUTHORITY_SCHEMA",
    "SUITE_MANIFEST_SCHEMA", "SUITE_PRELOCK_RECEIPT_SCHEMA",
    "SUITE_TERMINAL_SCHEMA", "WEEKLY_GRADE_SCHEMA",
    "WEEKLY_SAFETY_RECEIPT_SCHEMA",
    "bind_terminal_prelock_root_v1", "build_arm_freeze_v1",
    "build_create_once_artifact_v1", "build_outcome_snapshot_v1",
    "build_outcome_snapshot_from_field_bridge_v1",
    "build_outcome_source_payload_from_field_bridge_v1",
    "build_preregistration_v1", "build_seed_crossing_v1",
    "build_weekly_safety_receipt_v1",
    "build_suite_authority_v1", "build_terminal_prelock_root_from_suite_v2",
    "build_terminal_prelock_root_v1", "canonical_json_bytes_v1",
    "canonical_sha256_v1", "evaluate_prospective_shadow_v1",
    "evaluate_season_v1", "grade_realized_v1", "grade_realized_week_v1",
    "normalize_object_identity_v1", "validate_arm_freeze_v1",
    "validate_outcome_snapshot_v1", "validate_preregistration_v1",
    "validate_prospective_shadow_evaluation_v1",
    "validate_realized_week_grade_v1", "validate_score_blind_freeze_v1",
    "validate_seed_crossing_v1", "validate_suite_authority_v1",
    "validate_terminal_prelock_root_body_v1", "validate_terminal_prelock_root_v1",
    "validate_weekly_safety_receipt_v1",
]
