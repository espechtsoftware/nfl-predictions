from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pytest

from nfl_dfs.research.atlas_repair6_proof_transport import (
    EXPECTED_FAILURE,
    FAILED_PROOF_EXECUTION,
    FAILED_PROOF_JOB,
    FAILED_PROOF_URI,
    PROTOCOL_SHA256,
    REPAIR5_CODE_SHA,
    REPAIR5_IMAGE,
    REPAIR6_CODE_SHA,
    REPAIR6_IMAGE,
    REPAIR6_PREFIX,
    REPLACEMENT_PROOF_PREFIX,
    SERVICE_ACCOUNT,
    TARGET_EXECUTION,
    TARGET_JOB,
    TARGET_URI,
    canonical_provenance_prefix,
    classify_failed_legacy_proof,
    compare_opaque_provenance_normalized,
    completed_state,
    opaque_suffix,
    validate_execution_contract,
    validate_object_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from render_atlas_matched_diversity_repair4_command import render  # noqa: E402


def _raw(image: str, code: str, suffix: bytes | None = None) -> bytes:
    suffix = suffix or (
        b'"season":2023,"shard_week":1,"slates":[{"opaque":true}],'
        b'"source_hashes":{"f":"a"},"uses_realized_outcomes":false,'
        b'"version":"atlas-matched-diversity-mvp-v1"}\n'
    )
    return canonical_provenance_prefix(image=image, code_sha=code) + suffix


def _execution(
    *,
    job: str,
    execution: str,
    season: str,
    week: str,
    uri: str,
    command: str,
    state: str,
) -> dict:
    terminal = state != "Unknown"
    return {
        "metadata": {"name": execution},
        "status": {
            "conditions": (
                [] if state == "missing" else
                [{
                    "type": "Completed",
                    "status": state,
                    **({
                        "reason": "NonZeroExitCode",
                        "message": "Task failed with exit code: 1",
                    } if state == "False" else {}),
                }]
            ),
            "succeededCount": 1 if state == "True" else 0,
            "failedCount": 1 if state == "False" else 0,
            "cancelledCount": 0,
            **({"completionTime": "2026-08-18T01:10:39Z"} if terminal else {}),
        },
        "spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": REPAIR6_IMAGE,
                    "command": ["python"],
                    "args": [
                        "-c", command, "--season", season, "--week", week,
                        "--output-uri", uri,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": REPAIR6_CODE_SHA},
                        {"name": "ANALYSIS_IMAGE", "value": REPAIR6_IMAGE},
                    ],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                }],
                "maxRetries": 0,
                "timeoutSeconds": "43200",
                "serviceAccountName": SERVICE_ACCOUNT,
            }},
        },
    }


def test_protocol_is_frozen_and_source_inventory_is_exact() -> None:
    protocol = ROOT / "reports/2026-08-17-atlas-repair6-proof-transport-v1.md"
    assert sha256(protocol.read_bytes()).hexdigest() == PROTOCOL_SHA256
    runner = ROOT / "scripts/run_atlas_matched_diversity_mvp.py"
    renderer = ROOT / "scripts/render_atlas_matched_diversity_repair4_command.py"
    assert sha256(runner.read_bytes()).hexdigest() == (
        "0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740"
    )
    assert sha256(renderer.read_bytes()).hexdigest() == (
        "69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671"
    )


def test_role_specific_commands_are_distinct_and_prefix_bound() -> None:
    target = render(REPAIR6_PREFIX)
    proof = render(REPLACEMENT_PROOF_PREFIX)
    assert target != proof
    assert sha256(target.encode()).hexdigest() != sha256(proof.encode()).hexdigest()

    target_value = _execution(
        job=TARGET_JOB, execution=TARGET_EXECUTION,
        season="2023", week="7", uri=TARGET_URI,
        command=target, state="True",
    )
    validate_execution_contract(
        target_value, job=TARGET_JOB, execution=TARGET_EXECUTION,
        season="2023", week="7", uri=TARGET_URI,
        command=target, expected_state="True",
    )
    with pytest.raises(ValueError, match="execution contract"):
        validate_execution_contract(
            target_value, job=TARGET_JOB, execution=TARGET_EXECUTION,
            season="2023", week="7", uri=TARGET_URI,
            command=proof, expected_state="True",
        )


def test_opaque_equivalence_normalizes_exactly_two_leading_fields() -> None:
    reference = _raw(REPAIR5_IMAGE, REPAIR5_CODE_SHA)
    proof = _raw(REPAIR6_IMAGE, REPAIR6_CODE_SHA)
    result = compare_opaque_provenance_normalized(reference, proof)
    assert result["normalized_fields"] == ["analysis_image", "code_sha"]
    assert result["normalized_suffix_equal"] is True
    assert result["raw_bytes_equal"] is False
    assert result["json_parsed"] is False
    assert result["slate_fields_inspected"] is False


@pytest.mark.parametrize("mutation", [
    lambda raw: raw.replace(b'"opaque":true', b'"opaque":fals', 1),
    lambda raw: raw.replace(b'"source_hashes":{"f":"a"}',
                            b'"source_hashes":{"f":"b"}', 1),
    lambda raw: raw[:-2] + b"x\n",
])
def test_opaque_equivalence_rejects_any_nonprovenance_byte(mutation) -> None:
    reference = _raw(REPAIR5_IMAGE, REPAIR5_CODE_SHA)
    proof = mutation(_raw(REPAIR6_IMAGE, REPAIR6_CODE_SHA))
    with pytest.raises(ValueError, match="normalized opaque bytes differ"):
        compare_opaque_provenance_normalized(reference, proof)


def test_opaque_equivalence_rejects_wrong_provenance_or_framing() -> None:
    good = _raw(REPAIR6_IMAGE, REPAIR6_CODE_SHA)
    wrong = _raw(REPAIR5_IMAGE, REPAIR5_CODE_SHA)
    with pytest.raises(ValueError, match="leading provenance"):
        opaque_suffix(wrong, image=REPAIR6_IMAGE, code_sha=REPAIR6_CODE_SHA)
    with pytest.raises(ValueError, match="framing"):
        opaque_suffix(good[:-1], image=REPAIR6_IMAGE, code_sha=REPAIR6_CODE_SHA)
    reordered = (
        b'{"code_sha":"' + REPAIR6_CODE_SHA.encode() + b'",'
        b'"analysis_image":"x",' + good.split(b",", 2)[2]
    )
    with pytest.raises(ValueError, match="leading provenance"):
        opaque_suffix(reordered, image=REPAIR6_IMAGE, code_sha=REPAIR6_CODE_SHA)


def test_completed_state_maps_absent_and_unknown_to_nonterminal() -> None:
    assert completed_state({"status": {"conditions": []}}) == "Unknown"
    assert completed_state({
        "status": {"conditions": [{"type": "Completed", "status": "Unknown"}]}
    }) == "Unknown"
    with pytest.raises(ValueError, match="population"):
        completed_state({"status": {"conditions": [
            {"type": "Completed", "status": "Unknown"},
            {"type": "Completed", "status": "Unknown"},
        ]}})
    with pytest.raises(ValueError, match="terminal counts"):
        completed_state({"status": {"conditions": [], "failedCount": 1}})
    with pytest.raises(ValueError, match="state differs"):
        completed_state({"status": {
            "conditions": [{"type": "Completed", "status": ""}],
        }})


def test_exact_legacy_failure_classification_is_score_free() -> None:
    command = render(REPAIR6_PREFIX)
    value = _execution(
        job=FAILED_PROOF_JOB, execution=FAILED_PROOF_EXECUTION,
        season="2023", week="1", uri=FAILED_PROOF_URI,
        command=command, state="False",
    )
    log = "Traceback (most recent call last):\n" + EXPECTED_FAILURE + "\n"
    result = classify_failed_legacy_proof(
        value, command=command, error_text=log, legacy_proof_inventory=[],
    )
    assert result["disposition"] == "exact-pre-model-proof-prefix-transport-failure"
    assert result["failed_before_scientific_work"] is True
    assert "error_text" not in result
    with pytest.raises(ValueError, match="failure class"):
        classify_failed_legacy_proof(
            value, command=command, error_text="RuntimeError: other",
            legacy_proof_inventory=[],
        )
    with pytest.raises(ValueError, match="failure class"):
        classify_failed_legacy_proof(
            value, command=command,
            error_text="ATLAS_MVP_SEED_COMPLETE\n" + log,
            legacy_proof_inventory=[],
        )
    wrong_reason = {**value, "status": {**value["status"]}}
    wrong_reason["status"]["conditions"] = [{
        "type": "Completed", "status": "False",
        "reason": "Cancelled", "message": "Task failed with exit code: 1",
    }]
    with pytest.raises(ValueError, match="terminal reason"):
        classify_failed_legacy_proof(
            wrong_reason, command=command, error_text=log,
            legacy_proof_inventory=[],
        )
    with pytest.raises(ValueError, match="not empty"):
        classify_failed_legacy_proof(
            value, command=command, error_text=log,
            legacy_proof_inventory=[FAILED_PROOF_URI],
        )


def test_safe_object_metadata_rejects_body_or_identity_substitutes() -> None:
    value = {
        "uri": TARGET_URI, "generation": "123", "bytes": 10,
        "sha256": "a" * 64,
    }
    assert validate_object_metadata(value, uri=TARGET_URI) == value
    for poison in (
        {**value, "uri": FAILED_PROOF_URI},
        {**value, "generation": ""},
        {**value, "bytes": 0},
        {**value, "sha256": "bad"},
    ):
        with pytest.raises(ValueError, match="object metadata"):
            validate_object_metadata(poison, uri=TARGET_URI)
