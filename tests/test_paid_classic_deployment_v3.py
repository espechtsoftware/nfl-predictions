"""Adversarial checks for paid-v3 provider deployment attestation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
    attest_paid_classic_deployment_v3,
    validate_paid_classic_build_evidence_v3,
    validate_paid_classic_deployment_attestation_v3,
)

BUILD_ID = "12345678-1234-1234-1234-123456789abc"
SOURCE_COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE_NAME = "us-central1-docker.pkg.dev/project/repo/nfl-dfs"
IMAGE = f"{IMAGE_NAME}@{DIGEST}"
TAG = f"{IMAGE_NAME}:paid-v3-{SOURCE_COMMIT}"
SERVICE = "nfl-dfs-app"
REVISION = "nfl-dfs-app-paidv3-aaaaaaaa-12345678"


def _provider_records():
    environment = [
        {"name": "IMAGE_SOURCE_COMMIT_SHA", "value": SOURCE_COMMIT},
        {"name": "IMAGE_DIGEST", "value": DIGEST},
        {"name": "IMAGE_URI", "value": IMAGE},
        {"name": "PAID_V3_CLOUD_BUILD_ID", "value": BUILD_ID},
    ]
    reviewed = yaml.safe_load(
        Path("cloudbuild.paid-boundary-v3.yaml").read_text(encoding="utf-8")
    )
    build = {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "createTime": "2026-09-07T12:00:00Z",
        "finishTime": "2026-09-07T12:10:00Z",
        "substitutions": {
            "_CODE_SHA": SOURCE_COMMIT,
            "_BUILD_IMAGE": TAG,
        },
        "images": [TAG],
        "steps": deepcopy(reviewed["steps"]),
        "results": {"images": [{"name": TAG, "digest": DIGEST}]},
    }
    service = {
        "metadata": {"name": SERVICE, "generation": 9},
        "spec": {"template": {"spec": {"containers": [{
            "image": IMAGE, "env": deepcopy(environment),
        }]}}},
        "status": {
            "observedGeneration": 9,
            "latestReadyRevisionName": REVISION,
            "conditions": [{"type": "Ready", "status": "True"}],
            "traffic": [{"revisionName": REVISION, "percent": 100}],
        },
    }
    revision = {
        "metadata": {
            "name": REVISION,
            "generation": 1,
            "creationTimestamp": "2026-09-07T12:11:00Z",
        },
        "spec": {"containers": [{
            "image": IMAGE, "env": deepcopy(environment),
        }]},
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }
    return build, service, revision, reviewed


def _attest(build, service, revision, reviewed):
    return attest_paid_classic_deployment_v3(
        build,
        service,
        revision,
        reviewed,
        expected_build_id=BUILD_ID,
        expected_source_commit=SOURCE_COMMIT,
        expected_immutable_image=IMAGE,
        expected_service=SERVICE,
        expected_revision=REVISION,
    )


def test_attestation_binds_provider_build_image_service_and_revision() -> None:
    build, service, revision, reviewed = _provider_records()
    receipt = _attest(build, service, revision, reviewed)

    assert receipt["cloud_build_id"] == BUILD_ID
    assert receipt["source_commit_sha"] == SOURCE_COMMIT
    assert receipt["image_digest"] == DIGEST
    assert receipt["immutable_image_uri"] == IMAGE
    assert receipt["cloud_run_revision"] == REVISION
    assert validate_paid_classic_deployment_attestation_v3(receipt) == receipt
    assert all(
        len(receipt[field]) == 64
        for field in (
            "provider_build_record_sha256",
            "provider_service_record_sha256",
            "provider_revision_record_sha256",
            "reviewed_build_contract_sha256",
            "attestation_sha256",
        )
    )


def test_build_evidence_is_authenticated_before_deployment() -> None:
    build, _, _, reviewed = _provider_records()
    evidence = validate_paid_classic_build_evidence_v3(
        build,
        reviewed,
        expected_build_id=BUILD_ID,
        expected_source_commit=SOURCE_COMMIT,
        expected_immutable_image=IMAGE,
    )
    assert evidence["cloud_build_id"] == BUILD_ID
    assert evidence["source_commit_sha"] == SOURCE_COMMIT
    build["steps"][0]["args"].append("echo bypass")
    with pytest.raises(ValueError, match="reviewed build law"):
        validate_paid_classic_build_evidence_v3(
            build,
            reviewed,
            expected_build_id=BUILD_ID,
            expected_source_commit=SOURCE_COMMIT,
            expected_immutable_image=IMAGE,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda b, s, r: b.update(status="FAILURE"), "successful expected build"),
        (
            lambda b, s, r: b["substitutions"].update(_CODE_SHA="c" * 40),
            "bind the source commit",
        ),
        (
            lambda b, s, r: b["results"]["images"][0].update(
                digest="sha256:" + "d" * 64
            ),
            "digest differs",
        ),
        (
            lambda b, s, r: b["steps"].pop(),
            "reviewed build law",
        ),
        (
            lambda b, s, r: b["steps"][0]["args"].append("echo bypass"),
            "reviewed build law",
        ),
        (
            lambda b, s, r: b["substitutions"].update(
                _BUILD_IMAGE="registry.example/other:latest"
            ),
            "reviewed image tag",
        ),
        (
            lambda b, s, r: s["status"].update(
                latestReadyRevisionName="another-revision"
            ),
            "latest ready revision differs",
        ),
        (
            lambda b, s, r: s["status"].update(
                traffic=[{"revisionName": REVISION, "percent": 99}]
            ),
            "traffic is not wholly",
        ),
        (
            lambda b, s, r: r["status"]["conditions"][0].update(status="False"),
            "not provider-confirmed Ready",
        ),
        (
            lambda b, s, r: r["metadata"].pop("generation"),
            "generation evidence is missing",
        ),
        (
            lambda b, s, r: r["metadata"].pop("creationTimestamp"),
            "lacks a creation timestamp",
        ),
        (
            lambda b, s, r: r["spec"]["containers"][0].update(image=TAG),
            "does not use the immutable image",
        ),
        (
            lambda b, s, r: r["spec"]["containers"][0]["env"][0].update(
                value="c" * 40
            ),
            "runtime identity differs",
        ),
    ],
)
def test_provider_or_runtime_drift_fails_closed(mutation, message: str) -> None:
    build, service, revision, reviewed = _provider_records()
    mutation(build, service, revision)
    with pytest.raises(ValueError, match=message):
        _attest(build, service, revision, reviewed)


def test_reopened_attestation_rejects_rehashed_arbitrary_fields() -> None:
    build, service, revision, reviewed = _provider_records()
    receipt = _attest(build, service, revision, reviewed)
    receipt["cloud_run_revision"] = "another-revision"
    with pytest.raises(ValueError, match="attestation hash differs"):
        validate_paid_classic_deployment_attestation_v3(receipt)


def test_attestor_module_uses_exclusive_output_creation() -> None:
    source = Path(
        "src/nfl_dfs/optimizer/paid_classic_deployment_v3.py"
    ).read_text(encoding="utf-8")
    assert 'args.output.open("x"' in source
