"""Pure disposition boundary for the conditional A7 production-law transfer.

The predecessor A7 module owns the selector, clipped-ladder utility, support
census, simultaneous-extremes falsifier, and every score-free threshold.  This
module deliberately adds no science: it verifies the inherited receipt and
projects the one successor license allowed by the frozen transfer protocol.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nfl_dfs.research import a7_select_ladder as a7


PROTOCOL_ID = "20260821-a7-production-law-scorefree-selector-transfer-v1"
VERSION = "a7-production-law-scorefree-selector-transfer-v1"

PASS_DISPOSITION = "production-law-scorefree-transfer-passes-shadow-licensed"
FAIL_DISPOSITION = "production-law-scorefree-transfer-fails-closed"
SMOKE_DISPOSITION = "production-law-scorefree-transfer-smoke-valid"
SUPPORT_DISPOSITION = "production-law-scorefree-transfer-support-valid"
UNSUPPORTED_DISPOSITION = "production-law-scorefree-transfer-unsupported-closed"

LICENSE_FIELDS = (
    "historical_outcome_access_licensed",
    "historical_scoring_licensed",
    "prospective_shadow_licensed",
    "production_change_licensed",
    "historical_retune_licensed",
    "transfer_retry_licensed",
    "automatic_deployment_licensed",
)

EXPECTED_CONDITIONS = frozenset({
    "treatment_nonvacuous",
    "aggregate_ladder_utility_strictly_improves",
    "at_least_four_world_blocks_improve",
    "realism_r3_supported",
    "realism_r3_noninferior",
})
EXPECTED_SUPPORT_CONDITIONS = frozenset({
    "control_r3_events_at_least_100",
    "treatment_r3_events_at_least_100",
    "control_r3_supported_in_every_block",
    "treatment_r3_supported_in_every_block",
})


def licenses(*, prospective_shadow: bool = False) -> dict[str, bool]:
    """Return the complete fail-closed license projection."""
    result = {field: False for field in LICENSE_FIELDS}
    result["prospective_shadow_licensed"] = bool(prospective_shadow)
    return result


def smoke_disposition() -> dict[str, Any]:
    """The real-artifact smoke can license no downstream action."""
    return {
        "version": VERSION,
        "protocol_id": PROTOCOL_ID,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "scorefree_transfer_passed": False,
        "disposition": SMOKE_DISPOSITION,
        "licenses": licenses(),
    }


def support_disposition(support: Mapping[str, Any]) -> dict[str, Any]:
    """Project A7's unchanged support census without exposing arm effects."""
    required = {
        "version", "uses_realized_outcomes", "slates", "definition",
        "minimum_aggregate_events_per_arm",
        "r3_positive_gain_events_by_block", "conditions", "passes",
    }
    conditions = support.get("conditions")
    cells = support.get("r3_positive_gain_events_by_block")
    if set(support) != required or support.get(
        "version"
    ) != "a7-r3-support-census-v1" or support.get(
        "uses_realized_outcomes"
    ) is not False or support.get("slates") != 54 or support.get(
        "definition"
    ) != "positive-ladder-gain-events-with-at-least-3-strict-q99-exceedances" or support.get(
        "minimum_aggregate_events_per_arm"
    ) != a7.R3_SUPPORT_MIN_EVENTS or not isinstance(cells, Mapping) or set(
        cells
    ) != {"control", "treatment"} or any(
        not isinstance(values, list)
        or len(values) != a7.BLOCK_COUNT
        or any(type(value) is not int or value < 0 for value in values)
        for values in cells.values()
    ) or not isinstance(conditions, Mapping) or set(
        conditions
    ) != EXPECTED_SUPPORT_CONDITIONS or any(
        type(value) is not bool for value in conditions.values()
    ) or conditions != {
        "control_r3_events_at_least_100": (
            sum(cells["control"]) >= a7.R3_SUPPORT_MIN_EVENTS
        ),
        "treatment_r3_events_at_least_100": (
            sum(cells["treatment"]) >= a7.R3_SUPPORT_MIN_EVENTS
        ),
        "control_r3_supported_in_every_block": all(
            value > 0 for value in cells["control"]
        ),
        "treatment_r3_supported_in_every_block": all(
            value > 0 for value in cells["treatment"]
        ),
    } or type(support.get("passes")) is not bool or support.get(
        "passes"
    ) is not all(conditions.values()):
        raise ValueError("A7 production-law support census differs")
    passed = support["passes"] is True
    return {
        "version": VERSION,
        "protocol_id": PROTOCOL_ID,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "support_passed": passed,
        "full_execution_freeze_licensed": passed,
        "disposition": SUPPORT_DISPOSITION if passed else UNSUPPORTED_DISPOSITION,
        "licenses": licenses(),
    }


def _validate_inherited_gate(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("A7 production-law inherited gate must be an object")
    required = {
        "protocol_id", "uses_realized_outcomes", "slates", "changed_slates",
        "ladder_utility", "ladder_utility_by_block", "improved_world_blocks",
        "realism", "support", "realism_r3_delta",
        "realism_r3_exact_comparison", "conditions", "mechanics_passes",
        "passes",
    }
    if set(value) != required:
        raise ValueError("A7 production-law inherited gate schema differs")
    if value.get("protocol_id") != a7.PROTOCOL_ID or value.get(
        "uses_realized_outcomes"
    ) is not False or value.get("slates") != 54:
        raise ValueError("A7 production-law inherited gate identity differs")
    conditions = value.get("conditions")
    if not isinstance(conditions, Mapping) or set(conditions) != EXPECTED_CONDITIONS or any(
        type(item) is not bool for item in conditions.values()
    ):
        raise ValueError("A7 production-law inherited conditions differ")
    passes = value.get("passes")
    mechanics = value.get("mechanics_passes")
    if type(passes) is not bool or type(mechanics) is not bool or passes is not all(
        conditions.values()
    ) or mechanics is not all(
        conditions[key]
        for key in (
            "treatment_nonvacuous",
            "aggregate_ladder_utility_strictly_improves",
            "at_least_four_world_blocks_improve",
        )
    ):
        raise ValueError("A7 production-law inherited pass law differs")
    support = value.get("support")
    if not isinstance(support, Mapping) or support.get(
        "uses_realized_outcomes"
    ) is not False or support.get("passes") is not conditions[
        "realism_r3_supported"
    ]:
        raise ValueError("A7 production-law inherited support gate differs")
    exact = value.get("realism_r3_exact_comparison")
    if not isinstance(exact, Mapping) or exact.get("margin_numerator") != (
        a7.REALISM_R3_MARGIN_NUMERATOR
    ) or exact.get("margin_denominator") != (
        a7.REALISM_R3_MARGIN_DENOMINATOR
    ) or exact.get("noninferior") is not conditions["realism_r3_noninferior"]:
        raise ValueError("A7 production-law inherited realism law differs")
    return value


def aggregate_transfer(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Apply A7's score-free gate unchanged and project the transfer result."""
    inherited = _validate_inherited_gate(a7.aggregate_scorefree(rows))
    passed = inherited["passes"] is True
    return {
        "version": VERSION,
        "protocol_id": PROTOCOL_ID,
        "inherited_protocol_id": a7.PROTOCOL_ID,
        "inherited_ladder_spec": a7.LADDER_SPEC,
        "inherited_gate_unchanged": True,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "scorefree_transfer_passed": passed,
        "disposition": PASS_DISPOSITION if passed else FAIL_DISPOSITION,
        "licenses": licenses(prospective_shadow=passed),
        "gate": inherited,
    }


__all__ = [
    "FAIL_DISPOSITION",
    "LICENSE_FIELDS",
    "PASS_DISPOSITION",
    "PROTOCOL_ID",
    "SMOKE_DISPOSITION",
    "SUPPORT_DISPOSITION",
    "UNSUPPORTED_DISPOSITION",
    "VERSION",
    "aggregate_transfer",
    "licenses",
    "smoke_disposition",
    "support_disposition",
]
