"""Adversarial checks for paid-v3 provider and activation authority."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
    PAID_V3_PROJECT,
    PAID_V3_REGION,
    PAID_V3_SERVICE,
    _sha,
    attest_paid_classic_deployment_v3,
    create_paid_classic_activation_authority_v3,
    paid_classic_activation_identity_from_environment_v3,
    reopen_paid_classic_activation_authority_v3,
    validate_paid_classic_active_traffic_state_v3,
    validate_paid_classic_activation_authority_v3,
    validate_paid_classic_build_evidence_v3,
    validate_paid_classic_deployment_attestation_v3,
)

BUILD_ID = "12345678-1234-1234-1234-123456789abc"
SOURCE_COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE_NAME = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
)
IMAGE = f"{IMAGE_NAME}@{DIGEST}"
TAG = f"{IMAGE_NAME}:paid-v3-{SOURCE_COMMIT}"
SERVICE = PAID_V3_SERVICE
REVISION = "nfl-dfs-app-paidv3-aaaaaaaa-12345678"
STAGING_REVISION = "nfl-dfs-app-paidv3s-aaaaaaaa-12345678"
PREVIOUS_REVISION = "nfl-dfs-app-previous"
ACTIVATION_URI = (
    f"gs://{PAID_V3_PROJECT}-paid-authority/paid-v3/"
    f"{SERVICE}/{REVISION}/activation.json"
)
SERVICE_UID = "11111111-1111-1111-1111-111111111111"
REVISION_UID = "22222222-2222-2222-2222-222222222222"


def _runtime_environment(
    *, activation_identity: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    values = {
        "IMAGE_SOURCE_COMMIT_SHA": SOURCE_COMMIT,
        "IMAGE_DIGEST": DIGEST,
        "IMAGE_URI": IMAGE,
        "PAID_V3_CLOUD_BUILD_ID": BUILD_ID,
        "PAID_V3_SERVICE": SERVICE,
        "PAID_V3_PROJECT": PAID_V3_PROJECT,
        "PAID_V3_REGION": PAID_V3_REGION,
    }
    if activation_identity is not None:
        values.update({
            "PAID_V3_ACTIVATION_URI": str(activation_identity["uri"]),
            "PAID_V3_ACTIVATION_GENERATION": str(
                activation_identity["generation"]
            ),
            "PAID_V3_ACTIVATION_SHA256": str(
                activation_identity["sha256"]
            ),
            "PAID_V3_ACTIVATION_BYTES": str(activation_identity["bytes"]),
        })
    return [{"name": key, "value": value} for key, value in values.items()]


def _provider_records(
    *,
    revision_name: str = REVISION,
    require_traffic: bool = True,
    activation_uri: str | None = None,
    activation_identity: dict[str, object] | None = None,
):
    reviewed = yaml.safe_load(
        Path("cloudbuild.paid-boundary-v3.yaml").read_text(encoding="utf-8")
    )
    # Reproduce the shape returned by gcloud builds describe: declared
    # substitutions are expanded, observations are added, and documented
    # provider defaults are materialized.
    expanded = json.loads(
        json.dumps(reviewed)
        .replace("${_CODE_SHA}", SOURCE_COMMIT)
        .replace("${_BUILD_IMAGE}", TAG)
    )
    build = deepcopy(expanded)
    build.update({
        "id": BUILD_ID,
        "name": (
            "projects/817589974517/locations/global/builds/" + BUILD_ID
        ),
        "projectId": PAID_V3_PROJECT,
        "status": "SUCCESS",
        "createTime": "2026-09-07T12:00:00Z",
        "startTime": "2026-09-07T12:00:05Z",
        "finishTime": "2026-09-07T12:10:00Z",
        "substitutions": {
            "_CODE_SHA": SOURCE_COMMIT,
            "_BUILD_IMAGE": TAG,
        },
        "artifacts": {"images": [TAG]},
        "results": {"images": [{"name": TAG, "digest": DIGEST}]},
    })
    build["options"] = {
        **build.get("options", {}),
        "logging": "LEGACY",
        "pool": {},
    }
    for index, step in enumerate(build["steps"]):
        step.update({
            "status": "SUCCESS",
            "exitCode": 0,
            "timing": {
                "startTime": f"2026-09-07T12:0{index}:00Z",
                "endTime": f"2026-09-07T12:0{index}:30Z",
            },
            "pullTiming": {
                "startTime": f"2026-09-07T12:0{index}:00Z",
                "endTime": f"2026-09-07T12:0{index}:05Z",
            },
        })
    environment = _runtime_environment(
        activation_identity=(
            activation_identity if activation_identity is not None else None
        )
    )
    if activation_uri is not None and activation_identity is None:
        environment.append({"name": "PAID_V3_ACTIVATION_URI", "value": activation_uri})
    service = {
        "metadata": {
            "name": SERVICE,
            "namespace": PAID_V3_PROJECT,
            "uid": SERVICE_UID,
            "selfLink": (
                "/apis/serving.knative.dev/v1/namespaces/"
                f"{PAID_V3_PROJECT}/services/{SERVICE}"
            ),
            "labels": {"cloud.googleapis.com/location": PAID_V3_REGION},
            "generation": 9,
        },
        "spec": {"template": {"spec": {"containers": [{
            "image": IMAGE,
            "env": deepcopy(environment),
        }]}}},
        "status": {
            "observedGeneration": 9,
            "latestReadyRevisionName": revision_name,
            "conditions": [{"type": "Ready", "status": "True"}],
            "traffic": [{
                "revisionName": (
                    revision_name if require_traffic else PREVIOUS_REVISION
                ),
                "percent": 100,
            }],
        },
    }
    revision = {
        "metadata": {
            "name": revision_name,
            "namespace": PAID_V3_PROJECT,
            "uid": REVISION_UID,
            "selfLink": (
                "/apis/serving.knative.dev/v1/namespaces/"
                f"{PAID_V3_PROJECT}/revisions/{revision_name}"
            ),
            "labels": {"cloud.googleapis.com/location": PAID_V3_REGION},
            "generation": 1,
            "creationTimestamp": "2026-09-07T12:11:00Z",
        },
        "spec": {"containers": [{
            "image": IMAGE,
            "env": deepcopy(environment),
        }]},
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }
    return build, service, revision, reviewed


def _attest(
    build,
    service,
    revision,
    reviewed,
    *,
    revision_name: str = REVISION,
    require_traffic: bool = True,
    activation_uri: str | None = None,
    activation_identity: dict[str, object] | None = None,
):
    return attest_paid_classic_deployment_v3(
        build,
        service,
        revision,
        reviewed,
        expected_build_id=BUILD_ID,
        expected_source_commit=SOURCE_COMMIT,
        expected_immutable_image=IMAGE,
        expected_service=SERVICE,
        expected_revision=revision_name,
        require_traffic=require_traffic,
        expected_activation_uri=activation_uri,
        expected_activation_identity=activation_identity,
    )


def _staging_receipt() -> dict[str, object]:
    build, service, revision, reviewed = _provider_records(
        revision_name=STAGING_REVISION,
        require_traffic=False,
        activation_uri=ACTIVATION_URI,
    )
    return _attest(
        build,
        service,
        revision,
        reviewed,
        revision_name=STAGING_REVISION,
        require_traffic=False,
        activation_uri=ACTIVATION_URI,
    )


def _activation_authority() -> dict[str, object]:
    return create_paid_classic_activation_authority_v3(
        _staging_receipt(),
        expected_project=PAID_V3_PROJECT,
        expected_region=PAID_V3_REGION,
        expected_build_id=BUILD_ID,
        expected_source_commit=SOURCE_COMMIT,
        expected_image=IMAGE,
        expected_service=SERVICE,
        authorized_runtime_revision=REVISION,
        activation_uri=ACTIVATION_URI,
    )


def test_provider_realistic_build_and_deployment_attestation_pass() -> None:
    build, service, revision, reviewed = _provider_records()
    receipt = _attest(build, service, revision, reviewed)

    assert receipt["cloud_project"] == PAID_V3_PROJECT
    assert receipt["cloud_region"] == PAID_V3_REGION
    assert receipt["cloud_build_id"] == BUILD_ID
    assert receipt["source_commit_sha"] == SOURCE_COMMIT
    assert receipt["image_digest"] == DIGEST
    assert receipt["immutable_image_uri"] == IMAGE
    assert receipt["cloud_run_revision"] == REVISION
    assert receipt["cloud_run_service_uid"] == SERVICE_UID
    assert validate_paid_classic_deployment_attestation_v3(receipt) == receipt


def test_build_evidence_authenticates_provider_observations_and_defaults() -> None:
    build, _, _, reviewed = _provider_records()
    evidence = validate_paid_classic_build_evidence_v3(
        build,
        reviewed,
        expected_build_id=BUILD_ID,
        expected_source_commit=SOURCE_COMMIT,
        expected_immutable_image=IMAGE,
    )
    assert evidence["cloud_build_id"] == BUILD_ID
    assert evidence["cloud_project"] == PAID_V3_PROJECT
    assert build["name"] and build["startTime"] and build["artifacts"]
    assert build["options"]["logging"] == "LEGACY"
    assert build["options"]["pool"] == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowFailure", True),
        ("allowExitCodes", [0, 1]),
        ("waitFor", ["-"]),
        ("script", "exit 0"),
        ("secretEnv", ["TOKEN"]),
        ("volumes", [{"name": "x", "path": "/x"}]),
        ("timeout", "1s"),
        ("automapSubstitutions", True),
    ],
)
def test_each_provider_step_bypass_field_fails_closed(field, value) -> None:
    build, _, _, reviewed = _provider_records()
    build["steps"][0][field] = value
    with pytest.raises(ValueError, match="reviewed build law"):
        validate_paid_classic_build_evidence_v3(
            build,
            reviewed,
            expected_build_id=BUILD_ID,
            expected_source_commit=SOURCE_COMMIT,
            expected_immutable_image=IMAGE,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout", "1s"),
        ("queueTtl", "1s"),
        ("options", {"machineType": "E2_HIGHCPU_32"}),
        (
            "serviceAccount",
            "projects/nfl-predictions-503414/serviceAccounts/other@example.invalid",
        ),
        ("secrets", [{"kmsKeyName": "projects/other/key", "secretEnv": {}}]),
        (
            "availableSecrets",
            {"secretManager": [{"versionName": "projects/other/secrets/x/versions/1"}]},
        ),
        ("substitutions", {"_CODE_SHA": SOURCE_COMMIT, "_BUILD_IMAGE": TAG, "_X": "1"}),
        ("images", [TAG, f"{IMAGE_NAME}:unreviewed"]),
    ],
)
def test_each_top_level_build_execution_field_fails_closed(field, value) -> None:
    build, _, _, reviewed = _provider_records()
    build[field] = value
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
        (lambda b, s, r: b.update(projectId="other"), "another project"),
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
        (lambda b, s, r: b["steps"].pop(), "reviewed build law"),
        (
            lambda b, s, r: s["metadata"].update(uid="not-a-uid"),
            "provider identity differs",
        ),
        (
            lambda b, s, r: s["metadata"].update(
                selfLink=(
                    "/apis/serving.knative.dev/v1/namespaces/"
                    f"{PAID_V3_PROJECT}/revisions/{SERVICE}"
                )
            ),
            "provider identity differs",
        ),
        (
            lambda b, s, r: r["metadata"].update(
                selfLink="/apis/serving.knative.dev/v1/namespaces/other/revisions/"
                + REVISION
            ),
            "provider identity differs",
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
            "does not total 100",
        ),
        (
            lambda b, s, r: r["status"]["conditions"][0].update(status="False"),
            "not provider-confirmed Ready",
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


def test_activation_authority_is_cross_bound_and_exact_read() -> None:
    authority = _activation_authority()
    raw = json.dumps(authority, sort_keys=True, separators=(",", ":")).encode()
    identity = {
        "uri": ACTIVATION_URI,
        "generation": "987654321",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    environment = {
        "PAID_V3_PROJECT": PAID_V3_PROJECT,
        "PAID_V3_REGION": PAID_V3_REGION,
        "PAID_V3_CLOUD_BUILD_ID": BUILD_ID,
        "IMAGE_SOURCE_COMMIT_SHA": SOURCE_COMMIT,
        "IMAGE_URI": IMAGE,
        "PAID_V3_SERVICE": SERVICE,
        "K_REVISION": REVISION,
        "PAID_V3_ACTIVATION_URI": identity["uri"],
        "PAID_V3_ACTIVATION_GENERATION": identity["generation"],
        "PAID_V3_ACTIVATION_SHA256": identity["sha256"],
        "PAID_V3_ACTIVATION_BYTES": str(identity["bytes"]),
    }
    reopened = reopen_paid_classic_activation_authority_v3(
        environment,
        object_reader=lambda observed: raw if observed == identity else b"",
    )
    assert reopened["authority"] == authority
    assert reopened["object_identity"] == identity


@pytest.mark.parametrize(
    "missing",
    [
        "PAID_V3_ACTIVATION_URI",
        "PAID_V3_ACTIVATION_GENERATION",
        "PAID_V3_ACTIVATION_SHA256",
        "PAID_V3_ACTIVATION_BYTES",
    ],
)
def test_activation_identity_has_no_uri_only_or_partial_mode(missing: str) -> None:
    environment = {
        "PAID_V3_ACTIVATION_URI": ACTIVATION_URI,
        "PAID_V3_ACTIVATION_GENERATION": "123",
        "PAID_V3_ACTIVATION_SHA256": "a" * 64,
        "PAID_V3_ACTIVATION_BYTES": "100",
    }
    environment.pop(missing)
    with pytest.raises(ValueError, match="exact uri/generation/sha256/bytes"):
        paid_classic_activation_identity_from_environment_v3(environment)


def test_exact_activation_read_rejects_non_object_json() -> None:
    raw = b"[]"
    environment = {
        "PAID_V3_ACTIVATION_URI": ACTIVATION_URI,
        "PAID_V3_ACTIVATION_GENERATION": "123",
        "PAID_V3_ACTIVATION_SHA256": hashlib.sha256(raw).hexdigest(),
        "PAID_V3_ACTIVATION_BYTES": str(len(raw)),
        "PAID_V3_PROJECT": PAID_V3_PROJECT,
        "PAID_V3_REGION": PAID_V3_REGION,
        "PAID_V3_CLOUD_BUILD_ID": BUILD_ID,
        "IMAGE_SOURCE_COMMIT_SHA": SOURCE_COMMIT,
        "IMAGE_URI": IMAGE,
        "PAID_V3_SERVICE": SERVICE,
        "K_REVISION": REVISION,
    }
    with pytest.raises(ValueError, match="not an object"):
        reopen_paid_classic_activation_authority_v3(
            environment, object_reader=lambda _identity: raw
        )


def test_activation_authority_rejects_rehashed_unrelated_nested_receipt() -> None:
    authority = _activation_authority()
    nested = authority["staging_pre_activation"]
    nested["cloud_build_id"] = "87654321-4321-4321-4321-cba987654321"
    nested_body = {
        key: value for key, value in nested.items()
        if key != "attestation_sha256"
    }
    nested["attestation_sha256"] = _sha(nested_body)
    authority_body = {
        key: value for key, value in authority.items()
        if key != "authority_sha256"
    }
    authority["authority_sha256"] = _sha(authority_body)
    with pytest.raises(ValueError, match="not cross-bound"):
        validate_paid_classic_activation_authority_v3(
            authority,
            expected_project=PAID_V3_PROJECT,
            expected_region=PAID_V3_REGION,
            expected_build_id=BUILD_ID,
            expected_source_commit=SOURCE_COMMIT,
            expected_image=IMAGE,
            expected_service=SERVICE,
            expected_revision=REVISION,
        )


def test_active_revision_and_attestation_bind_exact_activation_object() -> None:
    identity = {
        "uri": ACTIVATION_URI,
        "generation": "123",
        "sha256": "a" * 64,
        "bytes": 321,
    }
    build, service, revision, reviewed = _provider_records(
        activation_identity=identity
    )
    receipt = _attest(
        build,
        service,
        revision,
        reviewed,
        activation_uri=ACTIVATION_URI,
        activation_identity=identity,
    )
    assert receipt["activation_object_identity"] == identity
    revision["spec"]["containers"][0]["env"][-1]["value"] = "322"
    with pytest.raises(ValueError, match="runtime identity differs"):
        _attest(
            build,
            service,
            revision,
            reviewed,
            activation_uri=ACTIVATION_URI,
            activation_identity=identity,
        )


def test_staging_attestation_refuses_stale_or_inline_activation_authority() -> None:
    build, service, revision, reviewed = _provider_records(
        revision_name=STAGING_REVISION,
        require_traffic=False,
        activation_uri=ACTIVATION_URI,
    )
    for name, value, message in (
        ("PAID_V3_ACTIVATION_GENERATION", "12", "stale exact activation"),
        ("PAID_V3_ACTIVATION_AUTHORITY_JSON", "{}", "forbidden inline"),
    ):
        changed_service = deepcopy(service)
        changed_revision = deepcopy(revision)
        for document in (changed_service, changed_revision):
            containers = (
                document["spec"]["template"]["spec"]["containers"]
                if "template" in document["spec"]
                else document["spec"]["containers"]
            )
            containers[0]["env"].append({"name": name, "value": value})
        with pytest.raises(ValueError, match=message):
            _attest(
                build,
                changed_service,
                changed_revision,
                reviewed,
                revision_name=STAGING_REVISION,
                require_traffic=False,
                activation_uri=ACTIVATION_URI,
            )


def test_reopened_attestation_rejects_rehashed_wrong_project_and_time() -> None:
    build, service, revision, reviewed = _provider_records()
    receipt = _attest(build, service, revision, reviewed)
    for field, value, message in (
        ("cloud_project", "other", "identity is invalid"),
        (
            "provider_revision_create_time",
            "2026-09-07T11:00:00Z",
            "not causally ordered",
        ),
    ):
        mutated = deepcopy(receipt)
        mutated[field] = value
        body = {
            key: item for key, item in mutated.items()
            if key != "attestation_sha256"
        }
        mutated["attestation_sha256"] = _sha(body)
        with pytest.raises(ValueError, match=message):
            validate_paid_classic_deployment_attestation_v3(mutated)


def test_deployer_arms_and_reconciles_before_traffic_mutation() -> None:
    source = Path("scripts/deploy_paid_boundary_v3_image.sh").read_text(
        encoding="utf-8"
    )
    traffic = source.index("gcloud run services update-traffic")
    armed = source.rindex("ROLLBACK_ARMED=1", 0, traffic)
    assert armed < traffic
    assert "service-ambiguous.json" in source
    assert "gcloud run services replace" in source
    assert "trap 'on_signal 130' INT" in source
    assert "trap 'on_signal 143' TERM" in source
    assert "PAID_V3_ACTIVATION_GENERATION" in source
    assert '[[ "$SERVICE" == "nfl-dfs-app" ]]' in source

    app_source = Path("src/nfl_dfs/app/main.py").read_text(encoding="utf-8")
    assert "PAID_V3_ACTIVATION_AUTHORITY_JSON" not in app_source


def test_ambiguous_cutover_reconciliation_is_exact_and_fail_closed() -> None:
    _, service, _, _ = _provider_records()
    reconciled = validate_paid_classic_active_traffic_state_v3(
        service,
        expected_service=SERVICE,
        expected_revision=REVISION,
    )
    assert reconciled["provider_traffic_percent"] == 100
    service["status"]["traffic"] = [
        {"revisionName": REVISION, "percent": 99},
        {"revisionName": PREVIOUS_REVISION, "percent": 1},
    ]
    with pytest.raises(ValueError, match="not wholly"):
        validate_paid_classic_active_traffic_state_v3(
            service,
            expected_service=SERVICE,
            expected_revision=REVISION,
        )


def test_attestor_module_uses_exclusive_output_creation() -> None:
    source = Path(
        "src/nfl_dfs/optimizer/paid_classic_deployment_v3.py"
    ).read_text(encoding="utf-8")
    assert 'args.output.open("x"' in source
