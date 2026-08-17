"""Outcome-free impact and exact transfer-equivalence certificates."""

from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping


PROTOCOL_SHA256 = (
    "8175c20840af4351e91806bf33eab58fd3a141e8cea54b34ce6f7796bb67b15c"
)
CONTEXT_VERSION = "impact-equivalence-context-v1"
CERTIFICATE_VERSION = "impact-equivalence-certificate-v1"

STAGES = (
    "player_marginal",
    "rank_dependence",
    "candidate_generation",
    "portfolio_selection",
    "objective_contest",
)
CHANNELS = (
    "player_marginals",
    "rank_dependence",
    "candidate_membership",
    "candidate_order",
    "world_masks",
    "selected_identities",
    "objective_contest",
)
IDENTITY_KEYS = (
    "terminal_context_sha256",
    "population_sha256",
    "control_sha256",
    "treatment_sha256",
    "metric_gate_sha256",
)
CONTEXT_KEYS = {
    "version",
    "mechanism_id",
    "stage",
    "contains_outcome_values",
    "candidate_or_lineup_scores_read",
    "identities",
    "required_channels",
    "channels",
}
RECEIPT_KEYS = {"logical_id", "role", "sha256", "bytes"}
ROLES = {"shared", "control", "treatment"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")

PROPAGATION = {
    "player_marginals": frozenset(CHANNELS),
    "rank_dependence": frozenset(CHANNELS[1:]),
    "candidate_membership": frozenset(CHANNELS[2:]),
    "candidate_order": frozenset((
        "candidate_order", "selected_identities", "objective_contest",
    )),
    "world_masks": frozenset((
        "world_masks", "selected_identities", "objective_contest",
    )),
    "selected_identities": frozenset((
        "selected_identities", "objective_contest",
    )),
    "objective_contest": frozenset(("objective_contest",)),
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


def _digest(value: object) -> str:
    return sha256(_canonical_json(value).encode()).hexdigest()


def _require_sha(value: object, label: str) -> str:
    text = str(value)
    if not SHA256_RE.fullmatch(text):
        raise ValueError(f"{label} must be a full lowercase SHA-256")
    return text


def normalize_context(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize one outcome-free comparison context."""
    if not isinstance(raw, Mapping) or set(raw) != CONTEXT_KEYS:
        raise ValueError("impact-equivalence context fields differ")
    if raw.get("version") != CONTEXT_VERSION:
        raise ValueError("impact-equivalence context version differs")
    mechanism_id = raw.get("mechanism_id")
    if not isinstance(mechanism_id, str) or not mechanism_id.strip():
        raise ValueError("impact-equivalence mechanism_id is empty")
    stage = raw.get("stage")
    if stage not in STAGES:
        raise ValueError("impact-equivalence stage is unknown")
    if raw.get("contains_outcome_values") is not False or \
            raw.get("candidate_or_lineup_scores_read") is not False:
        raise ValueError("impact-equivalence context is outcome-facing")

    identities_raw = raw.get("identities")
    if not isinstance(identities_raw, Mapping) or \
            set(identities_raw) != set(IDENTITY_KEYS):
        raise ValueError("impact-equivalence semantic identities differ")
    identities = {
        key: _require_sha(identities_raw[key], key)
        for key in IDENTITY_KEYS
    }

    required_raw = raw.get("required_channels")
    if not isinstance(required_raw, list) or not required_raw or \
            any(not isinstance(channel, str) or channel not in CHANNELS
                for channel in required_raw) or \
            required_raw != sorted(required_raw) or \
            len(required_raw) != len(set(required_raw)):
        raise ValueError("impact-equivalence required channels differ")

    channels_raw = raw.get("channels")
    if not isinstance(channels_raw, Mapping) or \
            any(channel not in CHANNELS for channel in channels_raw):
        raise ValueError("impact-equivalence channels are unknown")
    if any(channel not in channels_raw for channel in required_raw):
        raise ValueError("impact-equivalence required channel is absent")

    channels: dict[str, list[dict[str, object]]] = {}
    for channel, receipts_raw in channels_raw.items():
        if not isinstance(receipts_raw, list) or not receipts_raw:
            raise ValueError("impact-equivalence receipt list is empty")
        receipts = []
        identities_seen = set()
        for receipt in receipts_raw:
            if not isinstance(receipt, Mapping) or set(receipt) != RECEIPT_KEYS:
                raise ValueError("impact-equivalence receipt fields differ")
            logical_id = receipt.get("logical_id")
            role = receipt.get("role")
            size = receipt.get("bytes")
            if not isinstance(logical_id, str) or not logical_id.strip() or \
                    role not in ROLES or type(size) is not int or size <= 0:
                raise ValueError("impact-equivalence receipt identity differs")
            key = (logical_id, role)
            if key in identities_seen:
                raise ValueError("impact-equivalence receipt identity repeats")
            identities_seen.add(key)
            receipts.append({
                "logical_id": logical_id,
                "role": role,
                "sha256": _require_sha(receipt.get("sha256"), "receipt sha256"),
                "bytes": size,
            })
        channels[str(channel)] = sorted(
            receipts,
            key=lambda item: (
                str(item["logical_id"]), str(item["role"]),
                str(item["sha256"]), int(item["bytes"]),
            ),
        )

    return {
        "version": CONTEXT_VERSION,
        "mechanism_id": mechanism_id,
        "stage": stage,
        "contains_outcome_values": False,
        "candidate_or_lineup_scores_read": False,
        "identities": identities,
        "required_channels": list(required_raw),
        "channels": {
            channel: channels[channel] for channel in sorted(channels)
        },
    }


def impact_closure(changed_channels: list[str]) -> list[str]:
    """Return the conservative registered downstream impact closure."""
    unknown = set(changed_channels) - set(CHANNELS)
    if unknown:
        raise ValueError("impact-equivalence changed channel is unknown")
    affected: set[str] = set()
    for channel in changed_channels:
        affected.update(PROPAGATION[channel])
    return [channel for channel in CHANNELS if channel in affected]


def certify_equivalence(
    before_raw: Mapping[str, Any], after_raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Issue a fail-closed, outcome-free revalidation decision."""
    before = normalize_context(before_raw)
    after = normalize_context(after_raw)

    identity_comparisons = {
        key: {
            "before": before["identities"][key],
            "after": after["identities"][key],
            "equivalent": before["identities"][key] == after["identities"][key],
        }
        for key in IDENTITY_KEYS
    }
    present_channels = [
        channel for channel in CHANNELS
        if channel in before["channels"] or channel in after["channels"]
    ]
    channel_comparisons = {}
    changed_channels = []
    for channel in present_channels:
        before_receipts = before["channels"].get(channel)
        after_receipts = after["channels"].get(channel)
        equivalent = before_receipts == after_receipts
        if not equivalent:
            changed_channels.append(channel)
        channel_comparisons[channel] = {
            "before_receipt_count": len(before_receipts or []),
            "after_receipt_count": len(after_receipts or []),
            "before_receipts_sha256": (
                _digest(before_receipts) if before_receipts is not None else None
            ),
            "after_receipts_sha256": (
                _digest(after_receipts) if after_receipts is not None else None
            ),
            "equivalent": equivalent,
            "required_before": channel in before["required_channels"],
            "required_after": channel in after["required_channels"],
        }

    required_sets_equal = (
        before["required_channels"] == after["required_channels"]
    )
    required_receipts_equal = required_sets_equal and all(
        channel_comparisons[channel]["equivalent"]
        for channel in before["required_channels"]
    )
    semantic_identity_equal = all(
        comparison["equivalent"]
        for comparison in identity_comparisons.values()
    )
    mechanism_equal = before["mechanism_id"] == after["mechanism_id"]
    stage_equal = before["stage"] == after["stage"]
    transfer_equivalent = all((
        mechanism_equal,
        stage_equal,
        required_sets_equal,
        required_receipts_equal,
        semantic_identity_equal,
    ))

    return {
        "version": CERTIFICATE_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "uses_realized_outcomes": False,
        "scientific_verdict_issued": False,
        "production_change_licensed": False,
        "before_manifest_sha256": _digest(before),
        "after_manifest_sha256": _digest(after),
        "mechanism_comparison": {
            "before": before["mechanism_id"],
            "after": after["mechanism_id"],
            "equivalent": mechanism_equal,
        },
        "stage_comparison": {
            "before": before["stage"],
            "after": after["stage"],
            "equivalent": stage_equal,
        },
        "required_channels_comparison": {
            "before": before["required_channels"],
            "after": after["required_channels"],
            "equivalent": required_sets_equal,
        },
        "identity_comparisons": identity_comparisons,
        "channel_comparisons": channel_comparisons,
        "changed_channels": changed_channels,
        "propagated_impact_channels": impact_closure(changed_channels),
        "required_receipts_equivalent": required_receipts_equal,
        "semantic_identities_equivalent": semantic_identity_equal,
        "transfer_equivalent": transfer_equivalent,
        "revalidation_required": not transfer_equivalent,
        "disposition": (
            "transfer-equivalent-no-revalidation"
            if transfer_equivalent else "revalidation-required"
        ),
    }
