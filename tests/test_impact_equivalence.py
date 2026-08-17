from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nfl_dfs.research.impact_equivalence import (
    CHANNELS,
    PROTOCOL_SHA256,
    certify_equivalence,
    impact_closure,
    normalize_context,
)


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports/2026-08-17-impact-equivalence-certificate-protocol.md"


def _hash(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _receipt(logical_id: str, role: str = "shared") -> dict[str, object]:
    return {
        "logical_id": logical_id,
        "role": role,
        "sha256": _hash(logical_id),
        "bytes": len(logical_id) + 1,
    }


def _context() -> dict[str, object]:
    return {
        "version": "impact-equivalence-context-v1",
        "mechanism_id": "example-mechanism-v1",
        "stage": "portfolio_selection",
        "contains_outcome_values": False,
        "candidate_or_lineup_scores_read": False,
        "identities": {
            "terminal_context_sha256": _hash("terminal"),
            "population_sha256": _hash("population"),
            "control_sha256": _hash("control"),
            "treatment_sha256": _hash("treatment"),
            "metric_gate_sha256": _hash("gate"),
        },
        "required_channels": ["candidate_membership", "selected_identities"],
        "channels": {
            "candidate_membership": [
                _receipt("candidate-b", "treatment"),
                _receipt("candidate-a", "control"),
            ],
            "selected_identities": [_receipt("selected")],
        },
    }


def test_protocol_hash_and_impact_closure_are_frozen() -> None:
    assert sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert PROTOCOL_SHA256 == (
        "8175c20840af4351e91806bf33eab58fd3a141e8cea54b34ce6f7796bb67b15c"
    )
    assert impact_closure(["candidate_order"]) == [
        "candidate_order", "selected_identities", "objective_contest",
    ]
    assert impact_closure(["world_masks", "selected_identities"]) == [
        "world_masks", "selected_identities", "objective_contest",
    ]
    assert impact_closure(["player_marginals"]) == list(CHANNELS)
    with pytest.raises(ValueError, match="unknown"):
        impact_closure(["actual_scores"])


def test_receipt_order_is_canonical_and_transfer_equivalent() -> None:
    before = _context()
    after = _context()
    after["channels"]["candidate_membership"].reverse()
    certificate = certify_equivalence(before, after)
    assert certificate["before_manifest_sha256"] == \
        certificate["after_manifest_sha256"]
    assert certificate["changed_channels"] == []
    assert certificate["propagated_impact_channels"] == []
    assert certificate["transfer_equivalent"] is True
    assert certificate["revalidation_required"] is False
    assert certificate["disposition"] == \
        "transfer-equivalent-no-revalidation"
    assert certificate["uses_realized_outcomes"] is False
    assert certificate["scientific_verdict_issued"] is False
    assert certificate["production_change_licensed"] is False


def test_optional_channel_change_is_disclosed_but_does_not_force_rerun() -> None:
    before = _context()
    after = _context()
    before["channels"]["world_masks"] = [_receipt("worlds-before")]
    after["channels"]["world_masks"] = [_receipt("worlds-after")]
    certificate = certify_equivalence(before, after)
    assert certificate["changed_channels"] == ["world_masks"]
    assert certificate["propagated_impact_channels"] == [
        "world_masks", "selected_identities", "objective_contest",
    ]
    assert certificate["channel_comparisons"]["world_masks"][
        "required_before"
    ] is False
    assert certificate["transfer_equivalent"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        "required_receipt",
        "semantic_identity",
        "required_set",
        "mechanism",
        "stage",
    ],
)
def test_any_required_or_semantic_difference_requires_revalidation(
    mutation: str,
) -> None:
    before = _context()
    after = _context()
    if mutation == "required_receipt":
        after["channels"]["selected_identities"][0]["bytes"] += 1
    elif mutation == "semantic_identity":
        after["identities"]["population_sha256"] = _hash("other-population")
    elif mutation == "required_set":
        after["required_channels"] = ["selected_identities"]
    elif mutation == "mechanism":
        after["mechanism_id"] = "other-mechanism"
    elif mutation == "stage":
        after["stage"] = "objective_contest"
    certificate = certify_equivalence(before, after)
    assert certificate["transfer_equivalent"] is False
    assert certificate["revalidation_required"] is True
    assert certificate["disposition"] == "revalidation-required"


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("missing_required", "required channel is absent"),
        ("unknown_channel", "channels are unknown"),
        ("duplicate_receipt", "receipt identity repeats"),
        ("outcome_flag", "outcome-facing"),
        ("malformed_hash", "full lowercase SHA-256"),
        ("unsorted_required", "required channels differ"),
        ("invalid_required_type", "required channels differ"),
    ],
)
def test_invalid_contexts_fail_closed(mutation: str, match: str) -> None:
    context = _context()
    if mutation == "missing_required":
        del context["channels"]["selected_identities"]
    elif mutation == "unknown_channel":
        context["channels"]["actual_scores"] = [_receipt("forbidden")]
    elif mutation == "duplicate_receipt":
        context["channels"]["selected_identities"].append(_receipt("selected"))
    elif mutation == "outcome_flag":
        context["contains_outcome_values"] = True
    elif mutation == "malformed_hash":
        context["identities"]["metric_gate_sha256"] = "A" * 64
    elif mutation == "unsorted_required":
        context["required_channels"].reverse()
    elif mutation == "invalid_required_type":
        context["required_channels"] = ["selected_identities", {}]
    with pytest.raises(ValueError, match=match):
        normalize_context(context)


def test_cli_rejects_duplicate_json_keys_and_is_create_only(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    output = tmp_path / "certificate.json"
    before.write_text(json.dumps(_context()), encoding="utf-8")
    after.write_text(json.dumps(_context()), encoding="utf-8")
    command = [
        sys.executable,
        str(ROOT / "scripts/certify_impact_equivalence.py"),
        "--before", str(before),
        "--after", str(after),
        "--output", str(output),
    ]
    first = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert first.returncode == 0, first.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["disposition"] == "transfer-equivalent-no-revalidation"
    second = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert second.returncode != 0
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"version":"a","version":"b"}', encoding="utf-8")
    duplicate_command = command.copy()
    duplicate_command[duplicate_command.index(str(before))] = str(duplicate)
    duplicate_command[-1] = str(tmp_path / "duplicate-output.json")
    rejected = subprocess.run(
        duplicate_command, cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    assert "duplicate JSON key" in rejected.stderr
