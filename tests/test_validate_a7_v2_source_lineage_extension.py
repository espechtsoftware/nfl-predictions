from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_a7_select_ladder as a7_transport  # noqa: E402
import finish_lr8_training_source_smoke as lr8_transport  # noqa: E402
import validate_a7_v2_source_lineage_extension as lineage  # noqa: E402


def _evidence() -> dict[str, object]:
    path = ROOT / lineage.LINEAGE_EVIDENCE_PATH
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == lineage.LINEAGE_EVIDENCE_SHA256
    value = json.loads(raw)
    assert raw == lineage._canonical_json(value) + b"\n"
    return value


def _fixture_blob(root: Path, commit: str, relative: str) -> bytes | None:
    evidence = _evidence()
    assert commit in {lineage.BASE_CODE_SHA, lineage.TARGET_CODE_SHA}
    row = evidence["sources"][relative]  # type: ignore[index]
    field = (
        "base_sha256" if commit == lineage.BASE_CODE_SHA else "target_sha256"
    )
    expected = row[field]  # type: ignore[index]
    if expected is None:
        return None
    if commit == lineage.BASE_CODE_SHA and relative == lineage.ARCHIVE_TEST_PATH:
        raw = lineage._registered_base_test(root)
    else:
        raw = (root / relative).read_bytes()
    assert sha256(raw).hexdigest() == expected
    return raw


def _fixture_diff(
    _root: Path, base: str, target: str,
) -> list[dict[str, str]]:
    evidence = _evidence()
    assert (base, target) == (lineage.BASE_CODE_SHA, lineage.TARGET_CODE_SHA)
    return [dict(row) for row in evidence["complete_delta"]]  # type: ignore[union-attr]


def _fixture_resolve(_root: Path, commit: str) -> None:
    evidence = _evidence()
    assert commit in {
        evidence["base_code_sha"], evidence["target_code_sha"],
    }


def _fixture_ancestry(_root: Path, base: str, target: str) -> None:
    evidence = _evidence()
    assert evidence["base_is_ancestor_of_target"] is True
    assert (base, target) == (
        evidence["base_code_sha"], evidence["target_code_sha"],
    )


def _fixture_validate(**overrides: object) -> dict[str, object]:
    options = {
        "blob_loader": _fixture_blob,
        "diff_loader": _fixture_diff,
        "commit_resolver": _fixture_resolve,
        "ancestry_checker": _fixture_ancestry,
    }
    options.update(overrides)
    return lineage._validate(**options)


def test_registered_source_lineage_is_exact_and_narrow() -> None:
    receipt = _fixture_validate()

    assert receipt["base_code_sha"] == lineage.BASE_CODE_SHA
    assert receipt["target_code_sha"] == lineage.TARGET_CODE_SHA
    assert receipt["shared_image_tag"] == (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        "nfl-dfs:lr8-smoke-2bec296"
    )
    assert receipt["equal_source_count"] == 37
    assert receipt["lineage_evidence"] == {
        "path": lineage.LINEAGE_EVIDENCE_PATH,
        "sha256": lineage.LINEAGE_EVIDENCE_SHA256,
        "source_count": 43,
    }
    assert receipt["complete_delta"] == {
        "path_count": 61,
        "sha256": lineage.EXPECTED_DIFF_SHA256,
        "category_counts": {
            "archive-hermetic-repair": 2,
            "retained-administrative-state": 14,
            "unrelated-lr8-state": 45,
        },
        "status_counts": {"A": 50, "M": 11},
    }
    assert receipt["licenses"] == {
        "a7_first_preflight_prepare_claim_with_exact_shared_build": True,
        "a7_smoke_or_later_authority_changed": False,
        "historical_scoring_licensed": False,
        "lr8_authority_granted": False,
        "old_build_or_image_reuse_licensed": False,
        "preflight_retry_licensed": False,
        "production_change_licensed": False,
        "repair_override_licensed": False,
    }


def test_synthetic_lr8_tagged_build_is_compatible_with_both_build_gates() -> None:
    image = f"{lineage.IMAGE_REPOSITORY}@sha256:{'a' * 64}"
    build_id = "shared-build-12345678"
    cloudbuild = (ROOT / "cloudbuild.yaml").read_bytes()
    evidence = _evidence()
    assert sha256(cloudbuild).hexdigest() == evidence["sources"][  # type: ignore[index]
        "cloudbuild.yaml"
    ]["target_sha256"]
    source = {
        "url": a7_transport.GIT_SOURCE_URL,
        "revision": lineage.TARGET_CODE_SHA,
    }
    build = {
        "id": build_id,
        "status": "SUCCESS",
        "substitutions": {
            "_CODE_SHA": lineage.TARGET_CODE_SHA,
            "_IMAGE": lineage.SHARED_IMAGE_TAG,
        },
        "steps": a7_transport._expected_cloud_build_steps(
            lineage.SHARED_IMAGE_TAG, cloudbuild_raw=cloudbuild,
        ),
        "options": {"machineType": "E2_HIGHCPU_8"},
        "timeout": "10800s",
        "images": [lineage.SHARED_IMAGE_TAG],
        "serviceAccount": a7_transport.BUILD_SERVICE_ACCOUNT,
        "logsBucket": a7_transport.BUILD_LOGS_BUCKET,
        "secrets": None,
        "availableSecrets": None,
        "artifacts": {"images": [lineage.SHARED_IMAGE_TAG]},
        "results": {"images": [{
            "name": lineage.SHARED_IMAGE_TAG,
            "digest": image.rsplit("@", 1)[1],
        }]},
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
    }

    a7_transport._validate_build_metadata(
        build, build_id=build_id, image=image,
        code_sha=lineage.TARGET_CODE_SHA,
        git_source_loader=lambda _root, commit, relative: (
            cloudbuild
            if (commit, relative) == (
                lineage.TARGET_CODE_SHA, "cloudbuild.yaml",
            ) else None
        ),
    )
    assert lr8_transport._validate_build_metadata(
        build, build_id=build_id, image=image,
        code_sha=lineage.TARGET_CODE_SHA,
        git_source_loader=lambda commit, relative: (
            cloudbuild
            if (commit, relative) == (
                lineage.TARGET_CODE_SHA, "cloudbuild.yaml",
            ) else None
        ),
    ) == lineage.SHARED_IMAGE_TAG


def test_real_retained_recovery_body_and_fixture_are_pinned() -> None:
    receipt = _fixture_validate()

    assert receipt["recovery"] == {
        "recovery_json_sha256": lineage.RECOVERY_FILES[
            f"{lineage.RECOVERY_ROOT}/recovery.json"
        ],
        "recovery_ledger_sha256": lineage.RECOVERY_FILES[
            f"{lineage.RECOVERY_ROOT}/recovery.sha256"
        ],
        "incident_sha256": lineage.RECOVERY_FILES[
            f"{lineage.RECOVERY_ROOT}/incident.json"
        ],
        "fresh_code_sha": lineage.BASE_CODE_SHA,
    }
    assert receipt["archive_repair"]["historical_finisher_bytes"] == 229_783
    assert receipt["archive_repair"]["historical_finisher_sha256"] == (
        lineage.HISTORICAL_FINISHER_SHA256
    )


def test_public_authority_entrypoint_exposes_no_evidence_injection() -> None:
    assert set(inspect.signature(lineage.validate).parameters) == {
        "root", "retained_root",
    }


def test_protocol_drift_fails_before_authority(tmp_path: Path) -> None:
    target = tmp_path / lineage.PROTOCOL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT / lineage.PROTOCOL_PATH).read_bytes() + b"drift\n")

    with pytest.raises(lineage.SourceLineageError, match="protocol differs"):
        lineage._validate_protocol(tmp_path)


def test_lineage_evidence_drift_fails_before_authority(tmp_path: Path) -> None:
    target = tmp_path / lineage.LINEAGE_EVIDENCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        (ROOT / lineage.LINEAGE_EVIDENCE_PATH).read_bytes() + b"drift\n"
    )

    with pytest.raises(lineage.SourceLineageError, match="evidence fixture differs"):
        lineage._registered_evidence(tmp_path)


def test_base_test_evidence_drift_fails_before_authority(tmp_path: Path) -> None:
    target = tmp_path / lineage.BASE_TEST_FIXTURE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        (ROOT / lineage.BASE_TEST_FIXTURE_PATH).read_bytes() + b"drift\n"
    )

    with pytest.raises(lineage.SourceLineageError, match="base-test fixture differs"):
        lineage._registered_base_test(tmp_path)


def test_recovery_body_drift_fails_before_authority(tmp_path: Path) -> None:
    for relative in lineage.RECOVERY_FILES:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    recovery = tmp_path / lineage.RECOVERY_ROOT / "recovery.json"
    value = json.loads(recovery.read_text(encoding="utf-8"))
    value["fresh_code_sha"] = lineage.TARGET_CODE_SHA
    recovery.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(lineage.SourceLineageError, match="retained recovery differs"):
        _fixture_validate(retained_root=tmp_path)


def test_a7_governed_source_drift_fails() -> None:
    target = lineage.A7_SOURCE_PATHS[1]

    def poisoned(root: Path, commit: str, relative: str) -> bytes | None:
        raw = _fixture_blob(root, commit, relative)
        if commit == lineage.TARGET_CODE_SHA and relative == target:
            assert raw is not None
            return raw + b"drift\n"
        return raw

    with pytest.raises(lineage.SourceLineageError, match="evidence source differs"):
        _fixture_validate(blob_loader=poisoned)


def test_archive_fixture_drift_fails() -> None:
    def poisoned(root: Path, commit: str, relative: str) -> bytes | None:
        raw = _fixture_blob(root, commit, relative)
        if commit == lineage.TARGET_CODE_SHA and relative == (
            lineage.ARCHIVE_FIXTURE_PATH
        ):
            assert raw is not None
            return raw + b"drift\n"
        return raw

    with pytest.raises(
        lineage.SourceLineageError, match="evidence source differs",
    ):
        _fixture_validate(blob_loader=poisoned)


def test_unclassified_complete_delta_path_fails() -> None:
    def poisoned(root: Path, base: str, target: str) -> list[dict[str, str]]:
        rows = _fixture_diff(root, base, target)
        rows[-1] = {"path": "src/nfl_dfs/research/a7_new_science.py", "status": "A"}
        return rows

    with pytest.raises(lineage.SourceLineageError, match="unclassified change"):
        _fixture_validate(diff_loader=poisoned)


def test_complete_delta_content_or_status_drift_fails() -> None:
    def poisoned(root: Path, base: str, target: str) -> list[dict[str, str]]:
        rows = _fixture_diff(root, base, target)
        rows[0] = {**rows[0], "status": "A"}
        return rows

    with pytest.raises(
        lineage.SourceLineageError, match="complete-delta receipt differs",
    ):
        _fixture_validate(diff_loader=poisoned)
