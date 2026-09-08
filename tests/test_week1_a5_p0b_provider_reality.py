"""Fail-closed tests for the Week-1 capture-v3 P0-B fact gate."""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from nfl_dfs.inference.generation_exposure import canonical_json_bytes
from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_a5_dk_acquisition as acquisition
from nfl_dfs.ingest import week1_a5_dk_acquisition_pins as live_pins
from nfl_dfs.ingest import week1_a5_governed_capture_v3 as capture_v3
from nfl_dfs.ingest import week1_a5_p0b_provider_reality as subject

SOURCE_BYTES = b"exact reviewed Cloud Build source archive fixture\n"
FIXTURE_LOCATOR = "https://fixture.draftkings.com/account/active?opaque=do-not-retain"
EFFECTIVE_LOCATOR = (
    "https://fixture.draftkings.com/account/entries.csv?signature=also-private"
)
AUDITOR = "user:release-reviewer@example.com"
COLLECTOR = "wk1-a5-capture@nfl-predictions-503414.iam.gserviceaccount.com"
READER = "wk1-a5-reader@nfl-predictions-503414.iam.gserviceaccount.com"
IMAGE_TAG = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/week1/dk-capture:p0b-reviewed"
)
IMAGE = f"{IMAGE_TAG.rsplit(':', 1)[0]}@sha256:{'b' * 64}"
PROJECT_NUMBER = "817589974517"
ORGANIZATION = "123456789012"


def _expected_access() -> dict[str, list[dict[str, object]]]:
    values: dict[str, list[dict[str, object]]] = {}
    for surface, permissions in subject.SURFACE_PERMISSIONS.items():
        principal = AUDITOR
        if surface == "session_secret":
            principal = f"serviceAccount:{COLLECTOR}"
        values[surface] = [
            {"permission": permission, "principals": [principal]}
            for permission in permissions
        ]
    return values


def _intent() -> dict[str, object]:
    return subject._seal(
        {
            "schema_version": subject.INTENT_SCHEMA,
            "created_at_utc": "2026-09-08T18:00:00Z",
            "project": subject.PROJECT,
            "project_number": PROJECT_NUMBER,
            "organization": ORGANIZATION,
            "region": "us-central1",
            "audit_principal": AUDITOR,
            "source_commit": "a" * 40,
            "collector_module_sha256": acquisition._module_sha256(),
            "build_id": "11111111-1111-4111-8111-111111111111",
            "build_region": "global",
            "source_archive": {
                "uri": (
                    "gs://nfl-predictions-503414_cloudbuild/source/p0b-reviewed.tgz"
                ),
                "generation": "101",
                "sha256": hashlib.sha256(SOURCE_BYTES).hexdigest(),
                "bytes": len(SOURCE_BYTES),
            },
            "image_tag": IMAGE_TAG,
            "image": IMAGE,
            "collector_job": {
                "name": "week1-a5-capture-p0b",
                "uid": "22222222-2222-4222-8222-222222222222",
                "generation": "7",
            },
            "collector_service_account": COLLECTOR,
            "authority_reader_service_account": READER,
            "session_secret": {
                "name": "week1-a5-dk-storage-state",
                "version": "3",
                "volume_name": "dk-session-state",
            },
            "contest_role": "milly-5",
            "locator_families": [
                {
                    "scheme": "https",
                    "host": "fixture.draftkings.com",
                    "port": 443,
                    "path_prefix": "/account/",
                }
            ],
            "expected_effective_access": _expected_access(),
            "outcome_data_access_authorized": False,
            "cloud_mutation_authorized": False,
        },
        field="intent_sha256",
    )


def _active_entry_csv(role: str = "milly-5") -> bytes:
    pin = capture.A5_ROLE_TABLE[role]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]
        + list(capture.CLASSIC_SLOTS)
    )
    for ordinal in range(pin.planned_entries):
        first = ordinal * 20 + 1
        writer.writerow(
            [
                str(int(pin.contest_id) * 1_000 + ordinal + 1),
                pin.name,
                pin.contest_id,
                f"${pin.entry_fee_micro // 1_000_000}",
            ]
            + [f"Player {value} ({value})" for value in range(first, first + 9)]
        )
    return output.getvalue().encode()


def _job() -> dict[str, object]:
    return {
        "metadata": {
            "name": "week1-a5-capture-p0b",
            "uid": "22222222-2222-4222-8222-222222222222",
            "generation": 7,
        },
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": {
                            "maxRetries": 0,
                            "serviceAccountName": COLLECTOR,
                            "containers": [
                                {
                                    "image": IMAGE,
                                    "env": [
                                        {"name": "CODE_SHA", "value": "a" * 40},
                                        {
                                            "name": "COLLECTOR_IMAGE_DIGEST",
                                            "value": f"sha256:{'b' * 64}",
                                        },
                                    ],
                                    "volumeMounts": [
                                        {
                                            "name": "dk-session-state",
                                            "mountPath": "/var/run/secrets/nfl-dfs",
                                        }
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "dk-session-state",
                                    "secret": {
                                        "secretName": "week1-a5-dk-storage-state",
                                        "items": [
                                            {
                                                "key": "3",
                                                "path": (
                                                    "draftkings-storage-state.json"
                                                ),
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    },
                }
            }
        },
        "status": {
            "observedGeneration": 7,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _bucket_policy() -> dict[str, object]:
    bindings = [
        {
            "role": "roles/storage.objectCreator",
            "members": [f"serviceAccount:{COLLECTOR}"],
        },
        {
            "role": "roles/storage.objectViewer",
            "members": [
                f"serviceAccount:{COLLECTOR}",
                f"serviceAccount:{READER}",
            ],
        },
    ]
    bindings.sort(key=canonical_json_bytes)
    return {"version": 3, "etag": "Zml4dHVyZS1ldGFn", "bindings": bindings}


def _asset_response(*, surface: str, intent: dict[str, object]) -> dict[str, object]:
    permissions = subject.SURFACE_PERMISSIONS[surface]
    target = subject._asset_target(surface, intent)
    expected = intent["expected_effective_access"][surface]  # type: ignore[index]
    results = []
    for access in expected:
        permission = access["permission"]
        principals = list(access["principals"])
        if not principals:
            continue
        results.append(
            {
                "fullyExplored": True,
                "nonCriticalErrors": [],
                "attachedResourceFullName": (
                    f"//cloudresourcemanager.googleapis.com/organizations/"
                    f"{ORGANIZATION}"
                ),
                "iamBinding": {
                    "role": "roles/p0bFixtureAuthority",
                    "members": principals,
                },
                "identityList": {
                    "identities": [{"name": item} for item in principals],
                    "groupEdges": [],
                },
                "accessControlLists": [
                    {
                        "resources": [{"fullResourceName": target}],
                        "accesses": [
                            {"role": "roles/p0bFixtureAuthority"},
                            {"permission": permission},
                        ],
                        "resourceEdges": [],
                    }
                ],
            }
        )
    return {
        "fullyExplored": True,
        "nonCriticalErrors": [],
        "mainAnalysis": {
            "fullyExplored": True,
            "nonCriticalErrors": [],
            "analysisQuery": {
                "accessSelector": {"permissions": list(permissions)},
                "resourceSelector": {"fullResourceName": target},
                "options": subject._asset_options(surface),
                "scope": f"organizations/{ORGANIZATION}",
            },
            "analysisResults": results,
        },
    }


class FixturePort:
    def __init__(self, intent: dict[str, object]) -> None:
        self.intent = intent
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.overrides: dict[str, object] = {}

    def json(self, *, label: str, argv: list[str]) -> object:
        self.calls.append((label, tuple(argv)))
        if label in self.overrides:
            return copy.deepcopy(self.overrides[label])
        if label == "active-gcloud-principal":
            return [{"account": AUDITOR.split(":", 1)[1], "status": "ACTIVE"}]
        if label == "project-ancestry":
            return [
                {"type": "project", "id": PROJECT_NUMBER},
                {"type": "folder", "id": "444444444444"},
                {"type": "organization", "id": ORGANIZATION},
            ]
        if label == "source-archive-metadata":
            return {
                "bucket": "nfl-predictions-503414_cloudbuild",
                "name": "source/p0b-reviewed.tgz",
                "generation": "101",
                "metageneration": "1",
                "size": str(len(SOURCE_BYTES)),
            }
        if label == "cloud-build":
            storage_source = {
                "bucket": "nfl-predictions-503414_cloudbuild",
                "object": "source/p0b-reviewed.tgz",
                "generation": "101",
            }
            return {
                "id": "11111111-1111-4111-8111-111111111111",
                "status": "SUCCESS",
                "source": {"storageSource": storage_source},
                "sourceProvenance": {"resolvedStorageSource": storage_source},
                "substitutions": {"_CODE_SHA": "a" * 40, "_IMAGE": IMAGE_TAG},
                "results": {
                    "images": [{"name": IMAGE_TAG, "digest": f"sha256:{'b' * 64}"}]
                },
            }
        if label == "artifact-registry-image":
            return {
                "image_summary": {
                    "digest": f"sha256:{'b' * 64}",
                    "fully_qualified_digest": IMAGE,
                }
            }
        if label.startswith("authority-bucket-policy-"):
            return _bucket_policy()
        if label.startswith("authority-bucket-"):
            return {
                "name": acquisition.LIVE_AUTHORITY_BUCKET,
                "projectNumber": PROJECT_NUMBER,
                "metageneration": "9",
                "iamConfiguration": {
                    "uniformBucketLevelAccess": {"enabled": True},
                    "publicAccessPrevention": "enforced",
                },
                "retentionPolicy": {
                    "isLocked": True,
                    "retentionPeriod": "31536000",
                },
                "versioning": {"enabled": True},
            }
        if label.startswith("collector-job-policy-"):
            return {"version": 1, "etag": "am9i", "bindings": []}
        if label.startswith("collector-job-"):
            return _job()
        if "service-account-policy" in label:
            return {"version": 1, "etag": "c2E=", "bindings": []}
        if label.startswith("session-secret-version-"):
            return {
                "name": (
                    f"projects/{PROJECT_NUMBER}/secrets/"
                    "week1-a5-dk-storage-state/versions/3"
                ),
                "state": "ENABLED",
            }
        if label.startswith("session-secret-policy-"):
            return {"version": 1, "etag": "c2VjcmV0", "bindings": []}
        if label.startswith("asset-"):
            surface = label.removeprefix("asset-").rsplit("-", 1)[0]
            return _asset_response(surface=surface, intent=self.intent)
        raise AssertionError(label)

    def raw(self, *, label: str, argv: list[str]) -> bytes:
        self.calls.append((label, tuple(argv)))
        assert label == "source-archive-content-identity"
        return SOURCE_BYTES


@dataclass
class FixtureTransport:
    event: acquisition.TransportEvent
    calls: list[tuple[str, str]]

    def perform(self, *, method: str, locator: str) -> acquisition.TransportEvent:
        self.calls.append((method, locator))
        return self.event


class FixtureTransportFactory:
    def __init__(self, event: acquisition.TransportEvent | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.transport = FixtureTransport(
            event=event
            or acquisition.TransportEvent(
                body=_active_entry_csv(),
                observed_at="2026-09-08T18:01:00Z",
                hops=(
                    acquisition.TransportHop(FIXTURE_LOCATOR, 302, EFFECTIVE_LOCATOR),
                    acquisition.TransportHop(EFFECTIVE_LOCATOR, 200, None),
                ),
                response_content_type="text/csv; charset=utf-8",
                response_content_disposition=('attachment; filename="DKEntries.csv"'),
                session_profile=acquisition.COLLECTOR_SESSION_PROFILE,
            ),
            calls=[],
        )

    def __call__(self, **kwargs: object) -> FixtureTransport:
        self.calls.append(kwargs)
        return self.transport


def _audit(
    *,
    port: FixturePort | None = None,
    transport: FixtureTransportFactory | None = None,
) -> tuple[dict[str, object], FixturePort, FixtureTransportFactory]:
    intent = _intent()
    retained_port = port or FixturePort(intent)
    retained_transport = transport or FixtureTransportFactory()
    receipt = subject.audit_provider_reality_v1(
        intent=intent,
        acceptance_locator=FIXTURE_LOCATOR,
        fact_port=retained_port,
        transport_factory=retained_transport,
        observed_at_utc="2026-09-08T18:02:00Z",
    )
    return receipt, retained_port, retained_transport


def test_default_plan_is_no_contact_and_every_pin_remains_absent(
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    def bomb(*args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    assert subject.main([], fact_port_factory=bomb, transport_factory=bomb) == 0
    assert subject.main(["plan"], fact_port_factory=bomb, transport_factory=bomb) == 0
    output = capsysbinary.readouterr().out
    assert output.count(b'"mode":"no-contact-plan"') == 2
    assert b'"provider_contacted":false' in output
    assert b'"outcome_data_access_authorized":false' in output
    assert capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR is None
    assert {
        value for name, value in vars(live_pins).items() if name.startswith("PINNED_")
    } == {None}


def test_real_fact_fixture_authenticates_release_iam_runtime_and_probe() -> None:
    receipt, port, transport = _audit()

    assert receipt["schema_version"] == subject.RECEIPT_SCHEMA
    assert receipt["release_gate"] == (
        "HOLD_FOR_INDEPENDENT_REVIEW_AND_PIN_ONLY_SUCCESSOR"
    )
    assert receipt["transport_probe"]["capture_v3_schema"] == (
        capture_v3.ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA
    )
    assert receipt["transport_probe"]["legacy_v2_live_fallback_used"] is False
    event = receipt["transport_probe"]["transport_event"]
    assert [hop["status"] for hop in event["redirect_chain"]] == [302, 200]
    assert "do-not-retain" not in str(event)
    assert "also-private" not in str(event)
    assert event["requested_locator"]["query_parameter_names"] == ["opaque"]
    assert event["effective_locator"]["query_parameter_names"] == ["signature"]
    assert receipt["transport_probe"]["response_shape"]["entry_count"] == 57
    assert receipt["transport_probe"]["response_shape"]["body_retained"] is False
    assert transport.transport.calls == [("GET", FIXTURE_LOCATOR)]
    assert transport.calls == [
        {
            "storage_state_path": acquisition.LIVE_SESSION_STATE_PATH,
            "session_profile": acquisition.COLLECTOR_SESSION_PROFILE,
            "locator_families": (
                acquisition.LocatorFamily(
                    "https", "fixture.draftkings.com", "/account/", 443
                ),
            ),
        }
    ]
    labels = [label for label, _ in port.calls]
    assert labels.count("asset-authority_bucket-before") == 1
    assert labels.count("asset-authority_bucket-after") == 1
    assert len([label for label in labels if label.startswith("asset-")]) == 10
    assert labels.index("source-archive-content-identity") < labels.index(
        "authority-bucket-before"
    )
    forbidden = {
        "create",
        "update",
        "delete",
        "execute",
        "submit",
        "add-iam-policy-binding",
    }
    for label, argv in port.calls:
        assert not forbidden.intersection(argv), label
        if label.startswith("asset-"):
            assert argv.count("--expand-groups") == 1
            assert "--expand-roles" in argv
            assert "--expand-resources" in argv
            assert "--output-resource-edges" in argv
            assert "--output-group-edges" in argv
            if "service_account" in label:
                assert "--analyze-service-account-impersonation" in argv
            else:
                assert "--analyze-service-account-impersonation" not in argv


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("image", "mutable:latest", "malformed or mutable"),
        ("outcome_data_access_authorized", True, "must not authorize outcome"),
        ("cloud_mutation_authorized", True, "must not authorize cloud mutation"),
    ],
)
def test_intent_is_canonical_exact_and_authorizes_no_live_action(
    field: str, value: object, message: str
) -> None:
    intent = _intent()
    intent[field] = value
    intent["intent_sha256"] = subject._canonical_sha(
        {key: item for key, item in intent.items() if key != "intent_sha256"}
    )
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match=message):
        subject.validate_intent_v1(intent)


def test_tampered_intent_hash_fails_before_any_fact_or_transport() -> None:
    intent = _intent()
    intent["source_commit"] = "c" * 40
    port = FixturePort(intent)
    transport = FixtureTransportFactory()
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="hash differs"):
        subject.audit_provider_reality_v1(
            intent=intent,
            acceptance_locator=FIXTURE_LOCATOR,
            fact_port=port,
            transport_factory=transport,
        )
    assert port.calls == []
    assert transport.calls == []


def test_unexpected_effective_inherited_principal_fails_before_transport() -> None:
    intent = _intent()
    port = FixturePort(intent)
    response = _asset_response(surface="authority_bucket", intent=intent)
    response["mainAnalysis"]["analysisResults"][0]["identityList"]["identities"].append(
        {"name": "user:unreviewed@example.com"}
    )
    response["mainAnalysis"]["analysisResults"][0]["iamBinding"]["members"].append(
        "user:unreviewed@example.com"
    )
    port.overrides["asset-authority_bucket-before"] = response
    transport = FixtureTransportFactory()
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError,
        match="effective authority differs",
    ):
        subject.audit_provider_reality_v1(
            intent=intent,
            acceptance_locator=FIXTURE_LOCATOR,
            fact_port=port,
            transport_factory=transport,
        )
    assert transport.calls == []


@pytest.mark.parametrize(
    "defect", ["partial", "group-edge", "wrong-query", "outside-ancestry"]
)
def test_incomplete_or_ambiguous_cloud_asset_analysis_fails_closed(
    defect: str,
) -> None:
    intent = _intent()
    port = FixturePort(intent)
    response = _asset_response(surface="collector_job", intent=intent)
    if defect == "partial":
        response["mainAnalysis"]["fullyExplored"] = False
    elif defect == "group-edge":
        response["mainAnalysis"]["analysisResults"][0]["identityList"]["groupEdges"] = [
            {"group": "group:mutable@example.com"}
        ]
    elif defect == "wrong-query":
        response["mainAnalysis"]["analysisQuery"]["scope"] = (
            "organizations/999999999999"
        )
    else:
        response["mainAnalysis"]["analysisResults"][0]["attachedResourceFullName"] = (
            "//cloudresourcemanager.googleapis.com/folders/999999999999"
        )
    port.overrides["asset-collector_job-before"] = response
    with pytest.raises(subject.Week1A5P0BProviderRealityError):
        subject.audit_provider_reality_v1(
            intent=intent,
            acceptance_locator=FIXTURE_LOCATOR,
            fact_port=port,
            transport_factory=FixtureTransportFactory(),
        )


def test_conditioned_effective_binding_is_preserved_for_review() -> None:
    intent = _intent()
    response = _asset_response(surface="authority_bucket", intent=intent)
    result = response["mainAnalysis"]["analysisResults"][0]
    condition = {
        "title": "exact capture prefix",
        "expression": "resource.name.startsWith('projects/_/buckets/exact/')",
    }
    result["iamBinding"]["condition"] = condition
    result["accessControlLists"][0]["conditionEvaluation"] = {
        "evaluationValue": "CONDITIONAL"
    }
    projection = subject._asset_effective_access(
        response,
        scope=f"organizations/{ORGANIZATION}",
        target=subject._asset_target("authority_bucket", intent),
        allowed_attachments=frozenset(
            {f"//cloudresourcemanager.googleapis.com/organizations/{ORGANIZATION}"}
        ),
        options=subject._asset_options("authority_bucket"),
        permissions=subject.AUTHORITY_BUCKET_PERMISSIONS,
        expected=intent["expected_effective_access"]["authority_bucket"],
    )
    conditioned = next(
        item
        for item in projection["binding_provenance"]
        if item["condition"] is not None
    )
    assert conditioned["condition"] == condition
    assert conditioned["condition_evaluations"] == [{"evaluationValue": "CONDITIONAL"}]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda job: job["metadata"].__setitem__("generation", 8),
            "identity/generation differs",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"][
                "containers"
            ][0].__setitem__("image", "mutable:latest"),
            "exact immutable image",
        ),
        (
            lambda job: job["spec"]["template"]["spec"].__setitem__("taskCount", 2),
            "one-task",
        ),
        (
            lambda job: job["spec"]["template"]["spec"]["template"]["spec"]["volumes"][
                0
            ]["secret"]["items"][0].__setitem__("key", "latest"),
            "secret/version/path mount differs",
        ),
    ],
)
def test_mutable_or_cross_wired_runtime_fails_before_transport(
    mutate: object, message: str
) -> None:
    intent = _intent()
    port = FixturePort(intent)
    job = _job()
    mutate(job)  # type: ignore[operator]
    port.overrides["collector-job-before"] = job
    transport = FixtureTransportFactory()
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match=message):
        subject.audit_provider_reality_v1(
            intent=intent,
            acceptance_locator=FIXTURE_LOCATOR,
            fact_port=port,
            transport_factory=transport,
        )
    assert transport.calls == []


@pytest.mark.parametrize(
    ("event_change", "message"),
    [
        (
            {"response_content_type": "text/html"},
            "media type differs",
        ),
        (
            {"response_content_disposition": "inline"},
            "not an attached CSV",
        ),
        (
            {"body": b"login required"},
            "not a DKEntries CSV",
        ),
    ],
)
def test_status_media_disposition_and_response_shape_fail_closed(
    event_change: dict[str, object], message: str
) -> None:
    event = acquisition.TransportEvent(
        body=_active_entry_csv(),
        observed_at="2026-09-08T18:01:00Z",
        hops=(acquisition.TransportHop(FIXTURE_LOCATOR, 200, None),),
        response_content_type="text/csv",
        response_content_disposition='attachment; filename="entries.csv"',
        session_profile=acquisition.COLLECTOR_SESSION_PROFILE,
    )
    event = acquisition.TransportEvent(
        **{**event.__dict__, **event_change}  # type: ignore[arg-type]
    )
    with pytest.raises(Exception, match=message):
        _audit(transport=FixtureTransportFactory(event))


def test_off_family_effective_redirect_is_refused() -> None:
    event = acquisition.TransportEvent(
        body=_active_entry_csv(),
        observed_at="2026-09-08T18:01:00Z",
        hops=(
            acquisition.TransportHop(
                FIXTURE_LOCATOR, 302, "https://evil.example/steal.csv"
            ),
            acquisition.TransportHop("https://evil.example/steal.csv", 200, None),
        ),
        response_content_type="text/csv",
        response_content_disposition='attachment; filename="entries.csv"',
        session_profile=acquisition.COLLECTOR_SESSION_PROFILE,
    )
    with pytest.raises(Exception, match="outside the profile's exact family"):
        _audit(transport=FixtureTransportFactory(event))


def test_provider_fact_drift_after_http_probe_is_a_hold() -> None:
    intent = _intent()
    port = FixturePort(intent)
    changed = _job()
    changed["status"]["conditions"].append({"type": "Reconciling", "status": "False"})
    port.overrides["collector-job-after"] = changed
    transport = FixtureTransportFactory()
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError,
        match="changed during the transport probe",
    ):
        subject.audit_provider_reality_v1(
            intent=intent,
            acceptance_locator=FIXTURE_LOCATOR,
            fact_port=port,
            transport_factory=transport,
        )
    assert transport.transport.calls == [("GET", FIXTURE_LOCATOR)]


def test_cli_requires_separate_confirmation_before_files_or_clients(
    tmp_path: Path,
) -> None:
    def bomb(*args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    evidence = tmp_path / "evidence"
    receipt = tmp_path / "receipt.json"
    assert (
        subject.main(
            [
                "audit",
                "--confirm",
                "wrong",
                "--intent",
                str(tmp_path / "absent.json"),
                "--acceptance-locator-file",
                str(tmp_path / "absent-locator"),
                "--evidence-directory",
                str(evidence),
                "--receipt",
                str(receipt),
            ],
            fact_port_factory=bomb,
            transport_factory=bomb,
        )
        == 2
    )
    assert not evidence.exists()
    assert not receipt.exists()


def test_cli_success_writes_create_once_intent_and_receipt(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    intent = _intent()
    intent_path = tmp_path / "intent.json"
    intent_path.write_bytes(subject._canonical_bytes(intent))
    locator_path = tmp_path / "locator"
    locator_path.write_text(FIXTURE_LOCATOR, encoding="utf-8")
    locator_path.chmod(0o600)
    evidence = tmp_path / "evidence"
    receipt_path = tmp_path / "receipt.json"
    port = FixturePort(intent)
    transport = FixtureTransportFactory()

    assert (
        subject.main(
            [
                "audit",
                "--confirm",
                subject.CONFIRMATION_PHRASE,
                "--intent",
                str(intent_path),
                "--acceptance-locator-file",
                str(locator_path),
                "--evidence-directory",
                str(evidence),
                "--receipt",
                str(receipt_path),
            ],
            fact_port_factory=lambda path: port,
            transport_factory=transport,
        )
        == 0
    )
    assert (evidence / "intent.json").read_bytes() == subject._canonical_bytes(intent)
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["schema_version"] == subject.RECEIPT_SCHEMA
    assert receipt["release_gate"].startswith("HOLD_")
    assert capsysbinary.readouterr().out == receipt_path.read_bytes()

    assert (
        subject.main(
            [
                "audit",
                "--confirm",
                subject.CONFIRMATION_PHRASE,
                "--intent",
                str(intent_path),
                "--acceptance-locator-file",
                str(locator_path),
                "--evidence-directory",
                str(evidence),
                "--receipt",
                str(receipt_path),
            ],
            fact_port_factory=lambda path: (_ for _ in ()).throw(AssertionError(path)),
            transport_factory=lambda **kwargs: (_ for _ in ()).throw(
                AssertionError(kwargs)
            ),
        )
        == 2
    )


def test_private_locator_refuses_symlink_or_readable_mode(tmp_path: Path) -> None:
    locator = tmp_path / "locator"
    locator.write_text(FIXTURE_LOCATOR, encoding="utf-8")
    locator.chmod(0o644)
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="private"):
        subject._private_locator(locator, families=_intent()["locator_families"])
    locator.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(locator)
    with pytest.raises(subject.Week1A5P0BProviderRealityError, match="private"):
        subject._private_locator(link, families=_intent()["locator_families"])


def test_recording_port_rejects_credential_material_before_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Completed:
        stdout = b'{"accessToken":"not-safe"}'

    monkeypatch.setattr(subject.subprocess, "run", lambda *args, **kwargs: Completed())
    port = subject._RecordingGcloudPort(tmp_path)
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError, match="credential material"
    ):
        port.json(label="unsafe", argv=["auth", "list"])
    assert list(tmp_path.iterdir()) == []


def test_recording_port_rejects_secret_named_environment_before_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Completed:
        stdout = b'{"env":[{"name":"API_TOKEN","value":"not-safe"}]}'

    monkeypatch.setattr(subject.subprocess, "run", lambda *args, **kwargs: Completed())
    port = subject._RecordingGcloudPort(tmp_path)
    with pytest.raises(
        subject.Week1A5P0BProviderRealityError, match="credential material"
    ):
        port.json(label="unsafe-env", argv=["run", "jobs", "describe", "job"])
    assert list(tmp_path.iterdir()) == []
