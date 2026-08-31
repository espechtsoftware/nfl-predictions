from __future__ import annotations

import base64
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from scripts import run_corpus_r6_broad_admission_tournament_v1 as subject


class Store:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}
        self.events: list[str] = []
        self.published: list[str] = []

    def seed(self, uri: str, value: object) -> dict[str, object]:
        raw = subject._document(value)
        identity = {
            "uri": uri, "generation": "1",
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return identity

    def read_exact(self, identity: object) -> bytes:
        return self.objects[identity["uri"]][0]

    def open_known(self, uri: str, maximum_bytes: int):
        self.events.append(f"open:{uri}")
        return self.objects[uri]

    def publish_create_once(self, uri: str, raw: bytes):
        self.published.append(uri)
        identity = {
            "uri": uri, "generation": "1", "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw), "create_once": True,
        }
        if uri in self.objects and self.objects[uri][0] != raw:
            raise RuntimeError("collision")
        self.objects.setdefault(uri, (raw, {key: identity[key] for key in (
            "uri", "generation", "sha256", "bytes"
        )}))
        return identity


def identity(uri: str = "gs://bucket/object.json") -> dict[str, object]:
    return {"uri": uri, "generation": "1", "sha256": "a" * 64, "bytes": 1}


def manifest() -> dict[str, object]:
    return {
        "manifest_sha256": "b" * 64,
        "code_sha": "c" * 40,
        "image_digest": "sha256:" + "d" * 64,
        "immutable_image": "us-central1-docker.pkg.dev/p/r/i@sha256:" + "d" * 64,
        "build_id": "12345678-1234-1234-1234-123456789abc",
        "task_bindings": [{
            "result_uri": f"gs://bucket/slates/{ordinal:02d}/task.json",
            "score_uri": f"gs://bucket/slates/{ordinal:02d}/score.json",
        } for ordinal in range(subject.TASK_COUNT)],
        "terminal_uri": "gs://bucket/full-54/terminal.json",
        "grade_terminal_uri": "gs://bucket/full-54/grade-terminal.json",
    }


def runtime_env(manifest_identity: dict[str, object], *, ordinal: int = 0) -> dict[str, str]:
    retained = manifest()
    return {
        subject.ENABLE_ENV: subject.ENABLE_VALUE,
        subject.OUTCOMES_ALLOWED_ENV: "false",
        subject.CODE_SHA_ENV: str(retained["code_sha"]),
        subject.IMAGE_DIGEST_ENV: str(retained["image_digest"]),
        subject.IMAGE_URI_ENV: str(retained["immutable_image"]),
        subject.BUILD_ID_ENV: str(retained["build_id"]),
        subject.BOUND_IDENTITY_ENV: subject._canonical(manifest_identity).decode(),
        "CLOUD_RUN_JOB": subject.FIXED_REUSED_JOB_NAME,
        "CLOUD_RUN_EXECUTION": "atlas-cbc-32g-full-2023-w8-v1-abcde",
        "CLOUD_RUN_TASK_INDEX": str(ordinal),
        "CLOUD_RUN_TASK_COUNT": str(subject.TASK_COUNT),
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        subject.TASK0_SMOKE_ENV: "false",
    }


def replay_science(ordinal: int = 0):
    slate_id = subject.program.EXPECTED_SLATE_IDS[ordinal]
    package = {"slate_id": slate_id, "package_sha256": "e" * 64}
    lineups = [{
        "lineup_id": "lineup-1", "roster_player_ids": [f"p{i}" for i in range(9)],
        "roster_sha256": subject._hash([f"p{i}" for i in range(9)]),
    }]
    science = {
        "result_sha256": "f" * 64,
        "union": {"union_sha256": "1" * 64},
    }
    return package, identity("gs://bucket/parent.json"), lineups, science


def score_document_fixture():
    roster_a = [f"a{i}" for i in range(9)]
    roster_b = [f"b{i}" for i in range(9)]
    task = {
        "source_ordinal": 0, "slate_id": "2023-w01",
        "task_result_sha256": "1" * 64, "union_lineups_sha256": "2" * 64,
        "union_lineups": [
            {"lineup_id": "lineup-a", "roster_player_ids": roster_a,
             "roster_sha256": subject._hash(roster_a)},
            {"lineup_id": "lineup-b", "roster_player_ids": roster_b,
             "roster_sha256": subject._hash(roster_b)},
        ],
    }
    rows = [
        {"lineup_id": "lineup-a", "roster_sha256": subject._hash(roster_a),
         "realized_score_micro": 200_000_000},
        {"lineup_id": "lineup-b", "roster_sha256": subject._hash(roster_b),
         "realized_score_micro": 190_000_000},
    ]
    grade = subject._with_hash({
        "source_ordinal": 0, "slate_id": "2023-w01",
        "lineup_score_rows": rows, "lineup_score_rows_sha256": subject._hash(rows),
    }, field="slate_grade_sha256")
    completion = identity("gs://bucket/completion.json")
    snapshot = identity("gs://bucket/snapshot.json")
    root = {
        "outcome_completion_identity": completion,
        "outcome_snapshot_identity": snapshot,
    }
    realized = {
        "lineup-a": 200_000_000, "lineup-b": 190_000_000,
    }
    document = subject._with_hash({
        "schema_version": subject.SCORE_SCHEMA,
        "source_ordinal": 0, "slate_id": "2023-w01",
        "task_result_sha256": task["task_result_sha256"],
        "union_lineups_sha256": task["union_lineups_sha256"],
        "outcome_completion_identity": completion,
        "outcome_snapshot_identity": snapshot,
        "slate_grade": grade, "slate_grade_sha256": grade["slate_grade_sha256"],
        "realized_scores_micro": realized,
        "realized_scores_sha256": subject._hash(realized),
        "every_distinct_roster_scored_once": True,
        "uses_realized_outcomes": True, "complete": True,
    }, field="score_document_sha256")
    descriptor = {
        "source_ordinal": 0, "slate_id": "2023-w01",
        "score_identity": identity("gs://bucket/score.json"),
        "score_document_sha256": document["score_document_sha256"],
        "slate_grade_sha256": grade["slate_grade_sha256"],
        "realized_scores_sha256": document["realized_scores_sha256"],
    }
    return document, descriptor, task, root


def test_identity_requires_positive_decimal_generation() -> None:
    for generation in ("", "0", "-1", "abc", "١٢٣"):
        with pytest.raises(subject.BroadAdmissionRunnerV1Error):
            subject._identity({
                "uri": "gs://bucket/x", "generation": generation,
                "sha256": "a" * 64, "bytes": 1,
            }, label="test")


def test_task0_runs_full_science_without_publication_and_normal_task_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store()
    manifest_identity = identity("gs://bucket/manifest.json")
    retained = manifest()
    monkeypatch.setattr(
        subject, "_open_manifest",
        lambda *args, **kwargs: (retained, manifest_identity, {"frontier": True}),
    )
    monkeypatch.setattr(
        subject, "_rebuild_task_science",
        lambda **kwargs: replay_science(int(kwargs["ordinal"])),
    )
    smoke_env = runtime_env(manifest_identity)
    smoke_env[subject.TASK0_SMOKE_ENV] = "true"
    smoke = subject.task_from_request_v1(
        {"manifest_identity": manifest_identity}, store=store,
        environment=smoke_env,
    )
    assert smoke["schema_version"] == subject.SMOKE_SCHEMA
    assert smoke["publication_performed"] is False
    assert store.published == []

    bad_bound = runtime_env(manifest_identity)
    bad_bound[subject.BOUND_IDENTITY_ENV] = subject._canonical(
        identity("gs://bucket/other-manifest.json")
    ).decode()
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="bound identity"):
        subject.task_from_request_v1(
            {"manifest_identity": manifest_identity}, store=store,
            environment=bad_bound,
        )

    normal_env = runtime_env(manifest_identity)
    normal = subject.task_from_request_v1(
        {"manifest_identity": manifest_identity}, store=store,
        environment=normal_env,
    )
    assert normal["publication_performed"] is True
    assert store.published == [retained["task_bindings"][0]["result_uri"]]
    persisted = json.loads(store.objects[store.published[0]][0])
    assert persisted["task0_smoke"] is False
    assert persisted["publication_performed"] is True


def test_task_validator_rejects_self_rehashed_roster_not_in_exact_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store()
    retained = manifest()
    manifest_identity = identity("gs://bucket/manifest.json")
    monkeypatch.setattr(
        subject, "_rebuild_task_science", lambda **kwargs: replay_science(0)
    )
    monkeypatch.setattr(
        subject.program, "validate_score_free_slate_package_v1", lambda value: value
    )
    body = subject._task_body(
        manifest=retained, manifest_identity=manifest_identity,
        frontier={}, ordinal=0, environment=runtime_env(manifest_identity),
        store=store, smoke=False,
    )
    body["union_lineups"][0]["roster_player_ids"][0] = "tampered"
    body["union_lineups"][0]["roster_sha256"] = subject._hash(
        body["union_lineups"][0]["roster_player_ids"]
    )
    body["union_lineups_sha256"] = subject._hash(body["union_lineups"])
    body["task_result_sha256"] = subject._hash({
        key: value for key, value in body.items() if key != "task_result_sha256"
    })
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="replay differs"):
        subject._validate_task_result(
            body, manifest=retained, manifest_identity=manifest_identity,
            frontier={}, ordinal=0, store=store,
        )


def test_collect_proves_terminal_execution_before_opening_task_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store()
    retained = manifest()
    manifest_identity = identity("gs://bucket/manifest.json")
    for ordinal, binding in enumerate(retained["task_bindings"]):
        store.seed(str(binding["result_uri"]), {"ordinal": ordinal})
    monkeypatch.setattr(
        subject, "_open_manifest",
        lambda *args, **kwargs: (retained, manifest_identity, {}),
    )
    monkeypatch.setattr(subject, "_validate_execution_receipt", lambda value, **kwargs: value)
    monkeypatch.setattr(subject, "_validate_task_result", lambda value, **kwargs: {
        "slate_id": subject.program.EXPECTED_SLATE_IDS[kwargs["ordinal"]],
        "runtime_authority": {"execution_id": "job-abcde"},
        "task_result_sha256": "1" * 64, "package_sha256": "2" * 64,
        "union_lineups_sha256": "3" * 64, "runtime_authority_sha256": "4" * 64,
    })

    class Provider:
        def status(self, execution_id, **kwargs):
            store.events.append("provider")
            return {"execution_receipt_sha256": "5" * 64}

    result = subject.collect_from_request_v1(
        {"manifest_identity": manifest_identity, "execution_id": "job-abcde"},
        store=store, provider=Provider(),
    )
    assert result["task_count"] == subject.TASK_COUNT
    assert store.events[0] == "provider"
    assert store.events[1].startswith("open:")


def cloud_execution(
    *, retained: dict[str, object], manifest_identity: dict[str, object],
    memory: str = "32Gi", newline_request: bool = True,
) -> dict[str, object]:
    request = {"manifest_identity": manifest_identity}
    request_raw = subject._document(request) if newline_request else subject._canonical(request)
    env = {
        subject.REQUEST_B64_ENV: base64.b64encode(request_raw).decode(),
        subject.REQUEST_SHA256_ENV: sha256(request_raw).hexdigest(),
        subject.BOUND_IDENTITY_ENV: subject._canonical(manifest_identity).decode(),
        subject.ENABLE_ENV: subject.ENABLE_VALUE,
        subject.OUTCOMES_ALLOWED_ENV: "false",
        subject.CODE_SHA_ENV: retained["code_sha"],
        subject.IMAGE_DIGEST_ENV: retained["image_digest"],
        subject.IMAGE_URI_ENV: retained["immutable_image"],
        subject.BUILD_ID_ENV: retained["build_id"],
        subject.TASK0_SMOKE_ENV: "false",
    }
    return {
        "metadata": {
            "name": "atlas-cbc-32g-full-2023-w8-v1-abcde", "uid": "execution-uid",
            "labels": {
                "run.googleapis.com/job": subject.FIXED_REUSED_JOB_NAME,
                "run.googleapis.com/jobUid": subject.FIXED_REUSED_JOB_UID,
            },
        },
        "spec": {
            "taskCount": 54, "parallelism": 54,
            "template": {"spec": {
                "maxRetries": 0, "timeoutSeconds": "21600",
                "serviceAccountName": "817589974517-compute@developer.gserviceaccount.com",
                "containers": [{
                    "image": retained["immutable_image"], "command": ["/bin/bash"],
                    "args": [
                        "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
                        "container-run", "task",
                    ],
                    "resources": {"limits": {"cpu": "8", "memory": memory}},
                    "env": [{"name": key, "value": value} for key, value in env.items()],
                }],
            }},
        },
        "status": {
            "succeededCount": 54, "failedCount": 0, "cancelledCount": 0,
            "runningCount": 0,
            "conditions": [{"type": "Completed", "status": "True"}],
        },
    }


def test_provider_accepts_newline_request_and_rejects_resource_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retained = manifest()
    manifest_identity = identity("gs://bucket/manifest.json")
    observed = cloud_execution(retained=retained, manifest_identity=manifest_identity)
    monkeypatch.setattr(
        subject.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(observed)),
    )
    receipt = subject.GCloudExecutionStatusV1().status(
        "atlas-cbc-32g-full-2023-w8-v1-abcde", manifest=retained,
        manifest_identity=manifest_identity,
    )
    assert receipt["terminal"] is True
    assert receipt["memory"] == "32Gi"

    drift = cloud_execution(
        retained=retained, manifest_identity=manifest_identity, memory="16Gi"
    )
    monkeypatch.setattr(
        subject.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(drift)),
    )
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="provider observation"):
        subject.GCloudExecutionStatusV1().status(
            "atlas-cbc-32g-full-2023-w8-v1-abcde", manifest=retained,
            manifest_identity=manifest_identity,
        )

    bound_drift = cloud_execution(
        retained=retained, manifest_identity=manifest_identity
    )
    env_rows = bound_drift["spec"]["template"]["spec"]["containers"][0]["env"]
    next(row for row in env_rows if row["name"] == subject.BOUND_IDENTITY_ENV)[
        "value"
    ] = subject._canonical(identity("gs://bucket/other.json")).decode()
    monkeypatch.setattr(
        subject.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(bound_drift)),
    )
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="provider observation"):
        subject.GCloudExecutionStatusV1().status(
            "atlas-cbc-32g-full-2023-w8-v1-abcde", manifest=retained,
            manifest_identity=manifest_identity,
        )


def test_score_document_requires_exact_descriptor_and_unique_roster_coverage() -> None:
    document, descriptor, task, root = score_document_fixture()
    _retained, scores = subject._validate_score_document(
        document, descriptor=descriptor, task=task, root=root, ordinal=0
    )
    assert scores == {"lineup-a": 200_000_000, "lineup-b": 190_000_000}

    extra_descriptor = {**descriptor, "unexpected": True}
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="differs"):
        subject._validate_score_document(
            document, descriptor=extra_descriptor, task=task, root=root, ordinal=0
        )

    duplicate = json.loads(json.dumps(document))
    duplicate["slate_grade"]["lineup_score_rows"][1] = dict(
        duplicate["slate_grade"]["lineup_score_rows"][0]
    )
    duplicate["slate_grade"]["lineup_score_rows_sha256"] = subject._hash(
        duplicate["slate_grade"]["lineup_score_rows"]
    )
    duplicate["slate_grade"]["slate_grade_sha256"] = subject._hash({
        key: value for key, value in duplicate["slate_grade"].items()
        if key != "slate_grade_sha256"
    })
    duplicate["slate_grade_sha256"] = duplicate["slate_grade"][
        "slate_grade_sha256"
    ]
    duplicate["score_document_sha256"] = subject._hash({
        key: value for key, value in duplicate.items()
        if key != "score_document_sha256"
    })
    duplicate_descriptor = {
        **descriptor,
        "score_document_sha256": duplicate["score_document_sha256"],
        "slate_grade_sha256": duplicate["slate_grade_sha256"],
    }
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="row authority"):
        subject._validate_score_document(
            duplicate, descriptor=duplicate_descriptor, task=task, root=root, ordinal=0
        )


@pytest.mark.parametrize("invalid_score", [True, "200000000", 200000000.0])
def test_score_document_rejects_non_exact_integer_scores(invalid_score: object) -> None:
    document, descriptor, task, root = score_document_fixture()
    tampered = json.loads(json.dumps(document))
    tampered["slate_grade"]["lineup_score_rows"][0][
        "realized_score_micro"
    ] = invalid_score
    tampered["slate_grade"]["lineup_score_rows_sha256"] = subject._hash(
        tampered["slate_grade"]["lineup_score_rows"]
    )
    tampered["slate_grade"]["slate_grade_sha256"] = subject._hash({
        key: value for key, value in tampered["slate_grade"].items()
        if key != "slate_grade_sha256"
    })
    tampered["slate_grade_sha256"] = tampered["slate_grade"][
        "slate_grade_sha256"
    ]
    tampered["realized_scores_micro"]["lineup-a"] = invalid_score
    tampered["realized_scores_sha256"] = subject._hash(
        tampered["realized_scores_micro"]
    )
    tampered["score_document_sha256"] = subject._hash({
        key: value for key, value in tampered.items()
        if key != "score_document_sha256"
    })
    tampered_descriptor = {
        **descriptor,
        "score_document_sha256": tampered["score_document_sha256"],
        "slate_grade_sha256": tampered["slate_grade_sha256"],
        "realized_scores_sha256": tampered["realized_scores_sha256"],
    }
    with pytest.raises(subject.BroadAdmissionRunnerV1Error, match="row authority"):
        subject._validate_score_document(
            tampered, descriptor=tampered_descriptor, task=task, root=root, ordinal=0
        )


def test_grade_reopen_never_calls_catalog_and_independently_recomputes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity = identity("gs://bucket/grade-terminal.json")
    terminal_identity = identity("gs://bucket/terminal.json")
    closure_identity = identity("gs://bucket/closure.json")
    score_identity = identity("gs://bucket/score.json")
    grade_identity = identity("gs://bucket/grade.json")
    outcome_identity = identity("gs://bucket/completion.json")
    root = {
        "terminal_identity": terminal_identity, "terminal_sha256": "t",
        "manifest_identity": identity("gs://bucket/manifest.json"),
        "manifest_sha256": "m", "outcome_closure_identity": closure_identity,
        "outcome_closure_sha256": "c", "outcome_completion_identity": outcome_identity,
        "outcome_completion_sha256": "cs", "outcome_snapshot_identity": identity(
            "gs://bucket/snapshot.json"
        ), "outcome_snapshot_sha256": "ss",
        "historical_outcome_lease_identity": identity("gs://bucket/lease.json"),
        "historical_outcome_lease_body_sha256": "ls",
        "score_documents": [{"score_identity": score_identity}],
        "program_grade_identity": grade_identity, "program_grade_sha256": "g",
    }
    terminal = {"manifest_identity": root["manifest_identity"], "terminal_sha256": "t"}
    manifest_value = {"grade_terminal_uri": root_identity["uri"], "manifest_sha256": "m"}
    task = {"slate_id": "2023-w01"}
    closure = {
        "closure_sha256": "c", "outcome_completion_identity": outcome_identity,
        "outcome_completion_sha256": "cs",
        "outcome_snapshot_identity": root["outcome_snapshot_identity"],
        "outcome_snapshot_sha256": "ss",
        "historical_outcome_lease_identity": root["historical_outcome_lease_identity"],
        "historical_outcome_lease_body_sha256": "ls",
    }
    stored_grade = {"program_grade_sha256": "g"}

    def fake_read(value, *, label, **kwargs):
        if label == "grade terminal": return root, root_identity
        if label == "persisted outcome closure": return closure, closure_identity
        if label.startswith("score document"): return {"score": True}, score_identity
        if label == "persisted program grade": return stored_grade, grade_identity
        raise AssertionError(label)

    monkeypatch.setattr(subject, "_read", fake_read)
    monkeypatch.setattr(subject, "_validate_grade_root", lambda value: value)
    monkeypatch.setattr(subject, "_validate_closure", lambda value: value)
    monkeypatch.setattr(
        subject, "_open_score_free_terminal",
        lambda *args, **kwargs: (terminal, terminal_identity, manifest_value, [{}], [task]),
    )
    monkeypatch.setattr(
        subject, "_validate_score_document",
        lambda *args, **kwargs: ({}, {"lineup": 200_000_000}),
    )
    monkeypatch.setattr(subject.program, "_validate_program_grade_v1", lambda value: value)
    monkeypatch.setattr(
        subject.program, "grade_historical_program_v1", lambda **kwargs: stored_grade
    )
    monkeypatch.setattr(
        subject.recognized_outcomes, "open_recognized_outcome_authority_v1",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("catalog reread")),
    )
    result = subject.grade_reopen_from_request_v1(
        {"grade_terminal_identity": root_identity}, store=object()
    )
    assert result["program_grade_independently_recomputed"] is True
    assert result["catalog_reread"] is False
    assert result["outcome_snapshot_reread"] is False
    assert result["historical_outcome_lease_reread"] is False
