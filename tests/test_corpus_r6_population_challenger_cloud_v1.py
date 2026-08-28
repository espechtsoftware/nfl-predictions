from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_cloud_v1 as cloud,
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
COMMIT = "b" * 40


def _identity(uri: str, value: object, generation: int = 1) -> dict[str, object]:
    raw = cloud.canonical_bytes_v1(value)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _Store:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, dict[str, object]] = {}
        self.generation = 100

    def seed(self, identity: dict[str, object], value: object) -> None:
        raw = cloud.canonical_bytes_v1(value)
        assert len(raw) == identity["bytes"]
        assert sha256(raw).hexdigest() == identity["sha256"]
        key = (str(identity["uri"]), str(identity["generation"]))
        self.objects[key] = raw
        self.current[str(identity["uri"])] = dict(identity)

    def read_exact(self, identity: dict[str, object]) -> bytes:
        return self.objects[(str(identity["uri"]), str(identity["generation"]))]

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.current:
            identity = self.current[uri]
            assert self.read_exact(identity) == raw
            return identity
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, str(self.generation))] = raw
        self.current[uri] = identity
        return identity

    def open_known(
        self, uri: str, maximum_bytes: int,
    ) -> tuple[bytes, dict[str, object]]:
        identity = self.current[uri]
        assert identity["bytes"] <= maximum_bytes
        return self.read_exact(identity), identity


def _prepare_request() -> dict[str, object]:
    return {
        "schema_version": cloud.PREPARE_REQUEST_SCHEMA,
        "output_prefix": OUTPUT_PREFIX,
        "code_commit": COMMIT,
        "image_uri": IMAGE_URI,
    }


def test_prepare_pins_frozen_source_and_emits_smoke_and_full_job_shapes(
    monkeypatch: pytest.MonkeyPatch,
):
    store = _Store()
    captured: dict[str, object] = {}
    manifest = {
        "task_manifest_sha256": "d" * 64,
        "source_task_manifest_identity": dict(
            cloud.FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY
        ),
        "code_commit": COMMIT,
        "image_digest": "sha256:" + "c" * 64,
        "reused_job_name": cloud.REUSED_JOB_NAME,
    }

    def build(**kwargs):
        captured.update(kwargs)
        return manifest

    monkeypatch.setattr(authority, "build_task_manifest_v1", build)
    result = cloud.prepare_population_manifest_v1(
        request=_prepare_request(),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )

    assert captured["source_task_manifest_identity"] == (
        cloud.FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY
    )
    assert captured["reused_job_name"] == cloud.REUSED_JOB_NAME
    assert captured["image_digest"] == "sha256:" + "c" * 64
    assert result["expected_job_uid"] == cloud.REUSED_JOB_UID
    assert result["population_task_manifest_identity"]["uri"] == (
        OUTPUT_PREFIX + "authorities/task-manifest.json"
    )
    smoke = result["job_configurations"][cloud.TASK0_SCOPE]
    full = result["job_configurations"][cloud.FULL54_SCOPE]
    assert smoke["task_count"] == smoke["parallelism"] == 1
    assert full["task_count"] == full["parallelism"] == 54
    assert smoke["command"] == ["/usr/local/bin/python3.11"]
    assert smoke["args"] == [
        "-I", "/app/scripts/run_corpus_r6_population_challenger_v1.py", "task"
    ]
    assert smoke["max_retries"] == 0
    assert smoke["timeout_seconds"] == 21_600
    assert smoke["new_job_creation_allowed"] is False
    assert set(smoke["environment"]) == {
        "CODE_SHA",
        "GOOGLE_CLOUD_PROJECT",
        "R6_RUNTIME_IMAGE_DIGEST",
        authority.ENABLE_ENV,
        authority.MANIFEST_IDENTITY_ENV,
    }
    assert cloud.validate_preparation_v1(deepcopy(result)) == result


def _manifest_and_preparation() -> tuple[dict[str, object], dict[str, object], _Store]:
    store = _Store()
    bindings = []
    for index in range(authority.TASK_COUNT):
        projection = _identity(
            f"gs://fixture/projection/{index:02d}.json",
            {"projection": index},
            index + 1,
        )
        expected_profile_uris = {
            profile_id: (
                f"{OUTPUT_PREFIX}slates/{index:02d}/{profile_id}/lineups.json"
            )
            for profile_id in profiles.PROFILE_ORDER
        }
        request = {
            "request_sha256": sha256(f"request-{index}".encode()).hexdigest(),
            "projection_bundle_identity": projection,
            "expected_outputs": {
                "profile_lineup_uris": expected_profile_uris,
                "task_result_uri": (
                    f"{OUTPUT_PREFIX}slates/{index:02d}/task-result.json"
                ),
            },
        }
        bindings.append({"request": request})
    manifest = {
        "task_manifest_sha256": "d" * 64,
        "source_task_manifest_identity": dict(
            cloud.FROZEN_BROAD_SELECTION_TASK_MANIFEST_IDENTITY
        ),
        "code_commit": COMMIT,
        "image_digest": "sha256:" + "c" * 64,
        "reused_job_name": cloud.REUSED_JOB_NAME,
        "task_bindings": bindings,
    }
    manifest_identity = _identity(
        OUTPUT_PREFIX + "authorities/task-manifest.json", manifest, 500
    )
    store.seed(manifest_identity, manifest)
    smoke = cloud.build_job_configuration_v1(
        manifest_identity=manifest_identity,
        code_commit=COMMIT,
        image_uri=IMAGE_URI,
        scope=cloud.TASK0_SCOPE,
    )
    full = cloud.build_job_configuration_v1(
        manifest_identity=manifest_identity,
        code_commit=COMMIT,
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
        "code_commit": COMMIT,
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
            cloud.FULL54_SCOPE: full,
        },
        "outcomes_read": False,
    }
    preparation = {
        **body,
        "preparation_sha256": cloud.canonical_sha256_v1(body),
    }
    assert cloud.validate_preparation_v1(preparation) == preparation
    return manifest, preparation, store


def _provider_job(
    preparation: dict[str, object], scope: str,
) -> dict[str, object]:
    config = cloud.job_configuration_v1(preparation, scope=scope)
    return {
        "metadata": {
            "name": cloud.REUSED_JOB_NAME,
            "uid": cloud.REUSED_JOB_UID,
            "generation": "31",
        },
        "spec": {
            "template": {
                "spec": {
                    "taskCount": config["task_count"],
                    "parallelism": config["parallelism"],
                    "template": {
                        "spec": {
                            "maxRetries": 0,
                            "timeoutSeconds": "21600s",
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
                        },
                    },
                },
            },
        },
        "status": {},
    }


def test_exact_job_projection_rejects_wrong_scope_and_preserves_uid():
    _manifest, preparation, _store = _manifest_and_preparation()
    provider = _provider_job(preparation, cloud.TASK0_SCOPE)
    projected = cloud.validate_exact_job_configuration_v1(
        provider, preparation=preparation, scope=cloud.TASK0_SCOPE
    )
    assert projected["job_uid"] == cloud.REUSED_JOB_UID
    assert projected["exact_configuration_validated"] is True
    with pytest.raises(
        cloud.CorpusR6PopulationChallengerCloudV1Error,
        match="requested scope",
    ):
        cloud.validate_exact_job_configuration_v1(
            provider, preparation=preparation, scope=cloud.FULL54_SCOPE
        )
    assert cloud.configure_argv_v1(flags_path="/tmp/population-flags.json")[:5] == [
        "gcloud", "run", "jobs", "update", cloud.REUSED_JOB_NAME
    ]
    assert "create" not in cloud.configure_argv_v1(
        flags_path="/tmp/population-flags.json"
    )


def _provider_execution(
    *, execution: str, count: int, succeeded: int = 0, failed: int = 0,
    complete: bool = False,
) -> dict[str, object]:
    status: dict[str, object] = {
        "succeededCount": succeeded,
        "failedCount": failed,
    }
    if complete:
        status.update({
            "completionTime": "2026-08-29T00:00:00Z",
            "conditions": [{
                "type": "Completed", "state": "CONDITION_SUCCEEDED"
            }],
        })
    return {
        "metadata": {
            "name": execution,
            "uid": "execution-uid-1",
            "generation": "1",
            "labels": {
                "run.googleapis.com/job": cloud.REUSED_JOB_NAME,
                "run.googleapis.com/jobUid": cloud.REUSED_JOB_UID,
            },
        },
        "spec": {"taskCount": count},
        "status": status,
    }


def test_status_distinguishes_active_success_and_failure():
    execution = cloud.REUSED_JOB_NAME + "-abc12"
    active = cloud.build_execution_status_v1(
        _provider_execution(execution=execution, count=1),
        execution_name=execution,
        scope=cloud.TASK0_SCOPE,
    )
    assert active["terminal_state"] == "ACTIVE"
    success = cloud.build_execution_status_v1(
        _provider_execution(
            execution=execution, count=1, succeeded=1, complete=True
        ),
        execution_name=execution,
        scope=cloud.TASK0_SCOPE,
    )
    assert success["terminal_state"] == "SUCCEEDED"
    failed = cloud.build_execution_status_v1(
        _provider_execution(
            execution=execution, count=1, failed=1, complete=True
        ),
        execution_name=execution,
        scope=cloud.TASK0_SCOPE,
    )
    assert failed["terminal_state"] == "FAILED"


def _seed_results(
    manifest: dict[str, object], store: _Store,
) -> None:
    for index, binding in enumerate(manifest["task_bindings"]):
        request = binding["request"]
        profile_rows = []
        for profile_id in profiles.PROFILE_ORDER:
            uri = request["expected_outputs"]["profile_lineup_uris"][profile_id]
            lineup_identity = _identity(
                uri, {"profile": profile_id, "source": index}, 1_000 + index
            )
            profile_rows.append({
                "profile_id": profile_id,
                "lineups_identity": lineup_identity,
            })
        result = {
            "task_index": index,
            "source_ordinal": index,
            "request_sha256": request["request_sha256"],
            "source_authority": {
                "projection_bundle_identity": request[
                    "projection_bundle_identity"
                ],
            },
            "profile_results": profile_rows,
            "task_result_sha256": sha256(f"result-{index}".encode()).hexdigest(),
        }
        identity = _identity(
            request["expected_outputs"]["task_result_uri"],
            result,
            2_000 + index,
        )
        store.seed(identity, result)


def _successful_status(launch: dict[str, object]) -> dict[str, object]:
    count = int(launch["expected_task_count"])
    return cloud.build_execution_status_v1(
        _provider_execution(
            execution=str(launch["execution_name"]),
            count=count,
            succeeded=count,
            complete=True,
        ),
        execution_name=str(launch["execution_name"]),
        scope=str(launch["scope"]),
    )


def test_full_collector_exact_opens_54_known_results_and_emits_crossed_request(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest, preparation, store = _manifest_and_preparation()
    _seed_results(manifest, store)
    monkeypatch.setattr(
        authority, "validate_task_manifest_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        runtime, "validate_task_result_v1", lambda value: dict(value)
    )
    launch = cloud.build_launch_result_v1(
        execution_name=cloud.REUSED_JOB_NAME + "-full1",
        scope=cloud.FULL54_SCOPE,
    )
    collection = cloud.collect_task_results_v1(
        preparation=preparation,
        launch_result=launch,
        execution_status=_successful_status(launch),
        read_exact=store.read_exact,
        open_known=store.open_known,
    )
    assert collection["task_result_count"] == 54
    assert collection["crossed_prepare_ready"] is True
    assert collection["bucket_listing_performed"] is False
    assert [
        row["uri"] for row in collection["population_task_result_identities"]
    ] == [
        f"{OUTPUT_PREFIX}slates/{index:02d}/task-result.json"
        for index in range(54)
    ]
    crossed = cloud.build_crossed_prepare_request_v1(
        preparation=preparation,
        collection=collection,
        output_prefix=(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-current-bank-crossed-screens/"
            "20260828-r6-population-crossed-v1/"
        ),
    )
    assert set(crossed) == {
        "population_task_manifest_identity",
        "population_task_result_identities",
        "output_prefix",
        "code_commit",
        "image_digest",
        "reused_job_name",
    }
    assert len(crossed["population_task_result_identities"]) == 54


def test_task0_collection_is_smoke_only_and_active_collection_is_refused(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest, preparation, store = _manifest_and_preparation()
    _seed_results(manifest, store)
    monkeypatch.setattr(
        authority, "validate_task_manifest_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        runtime, "validate_task_result_v1", lambda value: dict(value)
    )
    launch = cloud.build_launch_result_v1(
        execution_name=cloud.REUSED_JOB_NAME + "-smoke",
        scope=cloud.TASK0_SCOPE,
    )
    collection = cloud.collect_task_results_v1(
        preparation=preparation,
        launch_result=launch,
        execution_status=_successful_status(launch),
        read_exact=store.read_exact,
        open_known=store.open_known,
    )
    assert collection["task_result_count"] == 1
    assert collection["crossed_prepare_ready"] is False
    with pytest.raises(
        cloud.CorpusR6PopulationChallengerCloudV1Error,
        match="not ready for crossed prepare",
    ):
        cloud.build_crossed_prepare_request_v1(
            preparation=preparation,
            collection=collection,
            output_prefix=OUTPUT_PREFIX + "crossed/",
        )

    active = cloud.build_execution_status_v1(
        _provider_execution(
            execution=str(launch["execution_name"]), count=1
        ),
        execution_name=str(launch["execution_name"]),
        scope=cloud.TASK0_SCOPE,
    )
    with pytest.raises(
        cloud.CorpusR6PopulationChallengerCloudV1Error,
        match="before exact execution success",
    ):
        cloud.collect_task_results_v1(
            preparation=preparation,
            launch_result=launch,
            execution_status=active,
            read_exact=store.read_exact,
            open_known=store.open_known,
        )


def _load_task_runner():
    path = Path("scripts/run_corpus_r6_population_challenger_v1.py")
    spec = importlib.util.spec_from_file_location("population_task_runner_cloud", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_task_runner_accepts_only_operator_task0_or_full54_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    runner = _load_task_runner()
    manifest = {
        "code_commit": COMMIT,
        "image_digest": "sha256:" + "c" * 64,
        "reused_job_name": cloud.REUSED_JOB_NAME,
    }
    raw = authority.canonical_bytes_v1(manifest)
    identity = {
        "uri": "gs://fixture/population/task-manifest.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }

    class Store:
        def read_exact(self, observed):
            assert dict(observed) == identity
            return raw

        def publish_create_once(self, uri, body):  # pragma: no cover - injected runtime
            raise AssertionError((uri, body))

    monkeypatch.setattr(
        runner.authority, "validate_task_manifest_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        runner.authority, "task_request_v1",
        lambda value, task_index: {"task_index": task_index},
    )
    monkeypatch.setattr(
        runner.runtime, "execute_task_v1",
        lambda request, **kwargs: {"accepted_task_index": request["task_index"]},
    )
    environment = {
        authority.ENABLE_ENV: "1",
        authority.MANIFEST_IDENTITY_ENV: cloud.canonical_bytes_v1(identity).decode(),
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_JOB": cloud.REUSED_JOB_NAME,
        "GOOGLE_CLOUD_PROJECT": cloud.PROJECT,
        "CODE_SHA": COMMIT,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "c" * 64,
    }
    assert runner.execute_environment_task_v1(
        environment,
        store=Store(),
        observed_command=list(authority.DISPATCHER_COMMAND),
    ) == {"accepted_task_index": 0}

    poisoned = dict(environment)
    poisoned["CLOUD_RUN_TASK_COUNT"] = "2"
    with pytest.raises(
        runner.RunCorpusR6PopulationChallengerV1Error,
        match="task/code/image/job authority",
    ):
        runner.execute_environment_task_v1(
            poisoned,
            store=Store(),
            observed_command=list(authority.DISPATCHER_COMMAND),
        )
