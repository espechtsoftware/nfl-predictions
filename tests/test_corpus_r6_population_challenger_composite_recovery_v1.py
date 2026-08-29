from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_cloud_v1 as cloud,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_composite_recovery_v1 as recovery,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as runtime,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles


IMAGE_URI = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/research@sha256:" + "c" * 64
)
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-current-bank-crossed-screens/"
    "20260828-r6-population-f7-f9-v1/"
)
CROSSED_OUTPUT_PREFIX = OUTPUT_PREFIX + "crossed-v1/"
SCIENCE_COMMIT = "b" * 40
RECOVERY_COMMIT = "e" * 40


def _identity(uri: str, value: object, generation: int) -> dict[str, object]:
    raw = recovery.canonical_bytes_v1(value)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _self_hashed(
    body: dict[str, object], *, field: str
) -> dict[str, object]:
    return {**body, field: recovery.canonical_sha256_v1(body)}


class _Store:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, dict[str, object]] = {}
        self.events: list[tuple[str, str]] = []
        self.generation = 10_000

    def seed(self, identity: dict[str, object], value: object) -> None:
        raw = recovery.canonical_bytes_v1(value)
        assert len(raw) == identity["bytes"]
        assert sha256(raw).hexdigest() == identity["sha256"]
        key = (str(identity["uri"]), str(identity["generation"]))
        self.objects[key] = raw
        self.current[str(identity["uri"])] = dict(identity)

    def read_exact(self, identity: dict[str, object]) -> bytes:
        uri = str(identity["uri"])
        self.events.append(("read_exact", uri))
        return self.objects[(uri, str(identity["generation"]))]

    def open_known(
        self, uri: str, maximum_bytes: int
    ) -> tuple[bytes, dict[str, object]]:
        self.events.append(("open_known", uri))
        identity = self.current[uri]
        assert int(identity["bytes"]) <= maximum_bytes
        key = (uri, str(identity["generation"]))
        return self.objects[key], dict(identity)

    def publish_create_once(
        self, uri: str, value: object
    ) -> dict[str, object]:
        raw = (
            value
            if type(value) is bytes
            else recovery.canonical_bytes_v1(value)
        )
        self.events.append(("publish_create_once", uri))
        if uri in self.current:
            identity = self.current[uri]
            assert self.objects[(uri, str(identity["generation"]))] == raw
            return dict(identity)
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, str(self.generation))] = raw
        self.current[uri] = identity
        return dict(identity)


def _manifest_preparation_store(
) -> tuple[dict[str, object], dict[str, object], _Store]:
    store = _Store()
    task_bindings: list[dict[str, object]] = []
    for index in range(authority.TASK_COUNT):
        projection = _identity(
            f"gs://fixture/projections/{index:02d}.json",
            {"projection": index},
            100 + index,
        )
        expected_outputs = {
            "profile_lineup_uris": {
                profile_id: (
                    f"{OUTPUT_PREFIX}slates/{index:02d}/"
                    f"{profile_id}/lineups.json"
                )
                for profile_id in profiles.PROFILE_ORDER
            },
            "task_result_uri": (
                f"{OUTPUT_PREFIX}slates/{index:02d}/task-result.json"
            ),
        }
        request = {
            "request_sha256": sha256(f"request-{index}".encode()).hexdigest(),
            "projection_bundle_identity": projection,
            "expected_outputs": expected_outputs,
        }
        task_bindings.append({
            "task_binding_sha256": sha256(
                f"binding-{index}".encode()
            ).hexdigest(),
            "request": request,
        })
    manifest = {
        "task_manifest_sha256": "d" * 64,
        "source_task_manifest_identity": dict(
            cloud.FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY
        ),
        "code_commit": SCIENCE_COMMIT,
        "image_digest": "sha256:" + "c" * 64,
        "reused_job_name": cloud.REUSED_JOB_NAME,
        "task_bindings": task_bindings,
    }
    manifest_identity = _identity(
        OUTPUT_PREFIX + "authorities/task-manifest.json", manifest, 500
    )
    store.seed(manifest_identity, manifest)
    smoke = cloud.build_job_configuration_v1(
        manifest_identity=manifest_identity,
        code_commit=SCIENCE_COMMIT,
        image_uri=IMAGE_URI,
        scope=cloud.TASK0_SCOPE,
    )
    full54 = cloud.build_job_configuration_v1(
        manifest_identity=manifest_identity,
        code_commit=SCIENCE_COMMIT,
        image_uri=IMAGE_URI,
        scope=cloud.FULL54_SCOPE,
    )
    body = {
        "schema_version": cloud.PREPARATION_SCHEMA,
        "source_task_manifest_identity": dict(
            cloud.FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY
        ),
        "population_task_manifest_identity": manifest_identity,
        "population_task_manifest_sha256": manifest["task_manifest_sha256"],
        "output_prefix": OUTPUT_PREFIX,
        "code_commit": SCIENCE_COMMIT,
        "image_uri": IMAGE_URI,
        "image_digest": "sha256:" + "c" * 64,
        "project_id": cloud.PROJECT,
        "location": cloud.REGION,
        "reused_job_name": cloud.REUSED_JOB_NAME,
        "expected_job_uid": cloud.REUSED_JOB_UID,
        "task_count": authority.TASK_COUNT,
        "profile_order": list(profiles.PROFILE_ORDER),
        "solves_per_task": authority.SOLVES_PER_TASK,
        "job_configurations": {
            cloud.TASK0_SCOPE: smoke,
            cloud.FULL54_SCOPE: full54,
        },
        "outcomes_read": False,
    }
    preparation = _self_hashed(body, field="preparation_sha256")
    assert cloud.validate_preparation_v1(preparation) == preparation
    return manifest, preparation, store


def _provider_execution(
    *, execution_name: str, task_count: int, succeeded: int, failed: int
) -> dict[str, object]:
    return {
        "metadata": {
            "name": execution_name,
            "uid": f"{execution_name}-uid",
            "generation": "7",
            "labels": {
                "run.googleapis.com/job": cloud.REUSED_JOB_NAME,
                "run.googleapis.com/jobUid": cloud.REUSED_JOB_UID,
            },
        },
        "spec": {"taskCount": task_count},
        "status": {
            "succeededCount": succeeded,
            "failedCount": failed,
            "completionTime": "2026-08-29T05:18:34.184120Z",
            "conditions": [{
                "type": "Completed",
                "state": "CONDITION_SUCCEEDED",
            }],
        },
    }


def _launch_and_status(
    *, scope: str, suffix: str, succeeded: int, failed: int
) -> tuple[dict[str, object], dict[str, object]]:
    execution_name = f"{cloud.REUSED_JOB_NAME}-{suffix}"
    launch = cloud.build_launch_result_v1(
        execution_name=execution_name, scope=scope
    )
    status = cloud.build_execution_status_v1(
        _provider_execution(
            execution_name=execution_name,
            task_count=int(launch["expected_task_count"]),
            succeeded=succeeded,
            failed=failed,
        ),
        execution_name=execution_name,
        scope=scope,
    )
    return launch, status


def _task_description(
    *,
    preparation: dict[str, object],
    launch: dict[str, object],
    failed: bool,
) -> dict[str, object]:
    config = cloud.job_configuration_v1(
        preparation, scope=str(launch["scope"])
    )
    execution_name = str(launch["execution_name"])
    labels = {
        "run.googleapis.com/execution": execution_name,
        "run.googleapis.com/job": cloud.REUSED_JOB_NAME,
        "run.googleapis.com/runningState": "Failed" if failed else "Succeeded",
    }
    completed = {
        "type": "Completed",
        "status": "False" if failed else "True",
    }
    if failed:
        completed["reason"] = "NonZeroExitCode"
    last_attempt: dict[str, object] = {"status": {}}
    if failed:
        last_attempt = {"exitCode": 1, "status": {"code": 10}}
    return {
        "metadata": {
            "name": f"{execution_name}-task0",
            "labels": labels,
            "ownerReferences": [
                {
                    "kind": "Job",
                    "name": cloud.REUSED_JOB_NAME,
                    "uid": cloud.REUSED_JOB_UID,
                },
                {
                    "kind": "Execution",
                    "name": execution_name,
                    "uid": f"{execution_name}-uid",
                },
            ],
        },
        "spec": {
            "containers": [{
                "image": config["image_uri"],
                "command": config["command"],
                "args": config["args"],
                "env": [
                    {"name": key, "value": value}
                    for key, value in config["environment"].items()
                ],
                "resources": {"limits": config["resources"]},
            }],
            "maxRetries": config["max_retries"],
            "timeoutSeconds": str(config["timeout_seconds"]),
            "serviceAccountName": "fixture-service-account@example.invalid",
        },
        "status": {
            "startTime": "2026-08-29T03:18:52.854487Z",
            "completionTime": "2026-08-29T05:18:34.184120Z",
            "conditions": [
                {"type": "Started", "status": "True"},
                completed,
            ],
            "lastAttemptResult": last_attempt,
        },
    }


def _seed_results(
    manifest: dict[str, object], store: _Store
) -> list[dict[str, object]]:
    identities: list[dict[str, object]] = []
    for index, binding_value in enumerate(manifest["task_bindings"]):
        binding = dict(binding_value)
        request = dict(binding["request"])
        expected_outputs = dict(request["expected_outputs"])
        lineups = dict(expected_outputs["profile_lineup_uris"])
        result = {
            "task_index": index,
            "source_ordinal": index,
            "request_sha256": request["request_sha256"],
            "source_authority": {
                "projection_bundle_identity": request[
                    "projection_bundle_identity"
                ],
            },
            "profile_results": [
                {
                    "profile_id": profile_id,
                    "lineups_identity": {
                        "uri": lineups[profile_id],
                        "generation": "1",
                        "sha256": "a" * 64,
                        "bytes": 1,
                    },
                }
                for profile_id in profiles.PROFILE_ORDER
            ],
            "task_result_sha256": sha256(
                f"result-self-hash-{index}".encode()
            ).hexdigest(),
        }
        identity = _identity(
            str(expected_outputs["task_result_uri"]),
            result,
            2_000 + index,
        )
        store.seed(identity, result)
        identities.append(identity)
    return identities


def _smoke_collection(
    *,
    preparation: dict[str, object],
    smoke_launch: dict[str, object],
    task0_identity: dict[str, object],
    task0_result_sha: str,
) -> dict[str, object]:
    body = {
        "schema_version": cloud.COLLECTION_SCHEMA,
        "scope": cloud.TASK0_SCOPE,
        "execution_name": smoke_launch["execution_name"],
        "population_task_manifest_identity": preparation[
            "population_task_manifest_identity"
        ],
        "population_task_manifest_sha256": preparation[
            "population_task_manifest_sha256"
        ],
        "task_result_count": 1,
        "population_task_result_identities": [task0_identity],
        "population_task_result_sha256s": [task0_result_sha],
        "crossed_prepare_ready": False,
        "bucket_listing_performed": False,
        "outcomes_read": False,
    }
    return _self_hashed(body, field="collection_sha256")


def _context(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    manifest, preparation, store = _manifest_preparation_store()
    monkeypatch.setattr(
        authority, "validate_task_manifest_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        runtime, "validate_task_result_v1", lambda value: dict(value)
    )
    result_identities = _seed_results(manifest, store)
    smoke_launch, smoke_status = _launch_and_status(
        scope=cloud.TASK0_SCOPE,
        suffix="smoke1",
        succeeded=1,
        failed=0,
    )
    full_launch, full_status = _launch_and_status(
        scope=cloud.FULL54_SCOPE,
        suffix="full54",
        succeeded=53,
        failed=1,
    )
    task0_raw = store.objects[
        (
            str(result_identities[0]["uri"]),
            str(result_identities[0]["generation"]),
        )
    ]
    task0_result = recovery.strict_json_bytes_v1(
        task0_raw, label="fixture task0 result"
    )
    smoke_collection = _smoke_collection(
        preparation=preparation,
        smoke_launch=smoke_launch,
        task0_identity=result_identities[0],
        task0_result_sha=str(task0_result["task_result_sha256"]),
    )
    return {
        "manifest": manifest,
        "preparation": preparation,
        "store": store,
        "result_identities": result_identities,
        "smoke_launch": smoke_launch,
        "smoke_status": smoke_status,
        "smoke_collection": smoke_collection,
        "full_launch": full_launch,
        "full_status": full_status,
        "smoke_task": _task_description(
            preparation=preparation,
            launch=smoke_launch,
            failed=False,
        ),
        "failed_task": _task_description(
            preparation=preparation,
            launch=full_launch,
            failed=True,
        ),
    }


def _build_intent(context: dict[str, object]) -> dict[str, object]:
    return recovery.build_recovery_intent_v1(
        preparation=context["preparation"],
        population_manifest=context["manifest"],
        smoke_launch_result=context["smoke_launch"],
        smoke_status=context["smoke_status"],
        smoke_collection=context["smoke_collection"],
        full54_launch_result=context["full_launch"],
        full54_status=context["full_status"],
        smoke_task_description=context["smoke_task"],
        failed_task_description=context["failed_task"],
        crossed_output_prefix=CROSSED_OUTPUT_PREFIX,
        recovery_code_commit=RECOVERY_COMMIT,
        recovery_source_sha256s={"core": "1" * 64, "operator": "2" * 64},
        amendment_report_sha256="3" * 64,
    )


def _publish_intent(
    context: dict[str, object], intent: dict[str, object]
) -> dict[str, object]:
    store = context["store"]
    assert isinstance(store, _Store)
    return store.publish_create_once(str(intent["outputs"]["intent_uri"]), intent)


def test_composite_recovery_is_no_recompute_and_emits_ordinary_request(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    store = context["store"]
    assert isinstance(store, _Store)
    events_before_intent = list(store.events)
    intent = _build_intent(context)
    assert store.events == events_before_intent
    intent_identity = _publish_intent(context, intent)
    collection, crossed_request = recovery.collect_composite_results_v1(
        recovery_intent=intent,
        recovery_intent_identity=intent_identity,
        read_exact=store.read_exact,
        open_known=store.open_known,
    )

    assert collection["task_result_count"] == 54
    assert collection["population_task_result_identities"][0] == intent[
        "task0_smoke_result_identity"
    ]
    assert [row["task_index"] for row in collection["task_result_provenance"]] == (
        list(range(54))
    )
    assert collection["task_result_provenance"][0]["source"] == (
        "successful-same-science-task0-smoke"
    )
    assert {
        row["source"] for row in collection["task_result_provenance"][1:]
    } == {"successful-complement-of-full54-execution"}
    assert set(crossed_request) == {
        "population_task_manifest_identity",
        "population_task_result_identities",
        "output_prefix",
        "code_commit",
        "image_digest",
        "reused_job_name",
    }
    assert len(crossed_request["population_task_result_identities"]) == 54

    intent_publish = store.events.index(
        ("publish_create_once", str(intent["outputs"]["intent_uri"]))
    )
    first_new_result_open = store.events.index(
        (
            "open_known",
            f"{OUTPUT_PREFIX}slates/01/task-result.json",
        )
    )
    assert intent_publish < first_new_result_open
    assert sum(event[0] == "open_known" for event in store.events) == 53

    collection_identity = store.publish_create_once(
        str(intent["outputs"]["collection_uri"]), collection
    )
    crossed_identity = store.publish_create_once(
        str(intent["outputs"]["crossed_prepare_request_uri"]), crossed_request
    )
    receipt = recovery.build_recovery_receipt_v1(
        recovery_intent=intent,
        recovery_intent_identity=intent_identity,
        composite_collection=collection,
        composite_collection_identity=collection_identity,
        crossed_prepare_request=crossed_request,
        crossed_prepare_request_identity=crossed_identity,
    )
    assert receipt["new_execution_launched"] is False
    assert receipt["task_recomputed"] is False
    assert receipt["bucket_listing_performed"] is False
    assert receipt["logs_read"] is False
    assert receipt["outcomes_read"] is False


def test_intent_rejects_failed_index_other_than_zero(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    failed_task = deepcopy(context["failed_task"])
    failed_task["metadata"]["name"] = (
        str(context["full_launch"]["execution_name"]) + "-task1"
    )
    failed_task["status"]["index"] = 1
    context["failed_task"] = failed_task
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="exact task 0",
    ):
        _build_intent(context)


def test_intent_rejects_smoke_full_science_surface_drift(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    failed_task = deepcopy(context["failed_task"])
    failed_task["spec"]["containers"][0]["image"] = (
        "us-central1-docker.pkg.dev/example/wrong@sha256:" + "9" * 64
    )
    context["failed_task"] = failed_task
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="spec differs from frozen preparation",
    ):
        _build_intent(context)


def test_intent_rejects_any_full54_terminal_shape_except_53_plus_1(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    _launch, status = _launch_and_status(
        scope=cloud.FULL54_SCOPE,
        suffix="full54",
        succeeded=52,
        failed=2,
    )
    context["full_status"] = status
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="outside the fixed recovery state",
    ):
        _build_intent(context)


def test_collection_rejects_manifest_bytes_changed_after_intent(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    intent = _build_intent(context)
    intent_identity = _publish_intent(context, intent)
    store = context["store"]
    assert isinstance(store, _Store)
    manifest_identity = intent["population_task_manifest_identity"]
    key = (
        str(manifest_identity["uri"]),
        str(manifest_identity["generation"]),
    )
    changed = deepcopy(context["manifest"])
    changed["code_commit"] = "9" * 40
    store.objects[key] = recovery.canonical_bytes_v1(changed)
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="identity differs|bytes differ",
    ):
        recovery.collect_composite_results_v1(
            recovery_intent=intent,
            recovery_intent_identity=intent_identity,
            read_exact=store.read_exact,
            open_known=store.open_known,
        )


def test_collection_rejects_out_of_order_task_result(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    intent = _build_intent(context)
    intent_identity = _publish_intent(context, intent)
    store = context["store"]
    assert isinstance(store, _Store)
    manifest = context["manifest"]
    uri = manifest["task_bindings"][7]["request"]["expected_outputs"][
        "task_result_uri"
    ]
    wrong_result = deepcopy(
        recovery.strict_json_bytes_v1(
            store.open_known(uri, authority.MAXIMUM_TASK_RESULT_BYTES)[0],
            label="fixture result 7",
        )
    )
    wrong_result["task_index"] = 8
    wrong_identity = _identity(uri, wrong_result, 30_007)
    store.seed(wrong_identity, wrong_result)
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="deterministic manifest request",
    ):
        recovery.collect_composite_results_v1(
            recovery_intent=intent,
            recovery_intent_identity=intent_identity,
            read_exact=store.read_exact,
            open_known=store.open_known,
        )


def test_rehashed_intent_cannot_relax_outcome_blind_policy(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    intent = deepcopy(_build_intent(context))
    intent.pop("recovery_intent_sha256")
    intent["policy"]["uses_realized_outcomes"] = True
    intent = _self_hashed(intent, field="recovery_intent_sha256")
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="intent contract differs",
    ):
        recovery.validate_recovery_intent_v1(intent)


def test_collection_requires_exact_published_intent_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    context = _context(monkeypatch)
    intent = _build_intent(context)
    intent_identity = _publish_intent(context, intent)
    changed_identity = dict(intent_identity)
    changed_identity["generation"] = "999999"
    store = context["store"]
    assert isinstance(store, _Store)
    with pytest.raises(
        recovery.CorpusR6PopulationChallengerCompositeRecoveryV1Error,
        match="published recovery intent generation",
    ):
        recovery.collect_composite_results_v1(
            recovery_intent=intent,
            recovery_intent_identity=changed_identity,
            read_exact=store.read_exact,
            open_known=store.open_known,
        )
