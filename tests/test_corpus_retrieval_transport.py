from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_corpus_retrieval_transport",
    ROOT / "scripts" / "run_corpus_retrieval_transport.py",
)
assert SPEC and SPEC.loader
transport = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = transport
SPEC.loader.exec_module(transport)

CODE_SHA = "a" * 40
BUILD_ID = "12345678-abcd-abcd-abcd-123456789abc"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
)
JOB_UID = "fixture-job-uid"
SERVICE_ACCOUNT = (
    "corpus-retrieval-runtime@nfl-predictions-503414.iam.gserviceaccount.com"
)


def _job(*, generation: int = 7, spec: dict | None = None) -> dict:
    if spec is None:
        spec = {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": {
                            "containers": [{
                                "image": IMAGE,
                                "command": ["python"],
                                "args": [
                                    "scripts/run_corpus_retrieval_transport.py",
                                    "parked",
                                ],
                                "env": [
                                    {
                                        "name": transport.ENABLE_ENV,
                                        "value": "1",
                                    },
                                    {
                                        "name": transport.IMAGE_ENV,
                                        "value": IMAGE,
                                    },
                                    {
                                        "name": transport.BUILD_ENV,
                                        "value": BUILD_ID,
                                    },
                                    {
                                        "name": transport.CODE_ENV,
                                        "value": CODE_SHA,
                                    },
                                ],
                                "resources": {
                                    "limits": {"cpu": "4", "memory": "16Gi"}
                                },
                                "volumeMounts": [],
                            }],
                            "maxRetries": 0,
                            "timeoutSeconds": "21600",
                            "serviceAccountName": SERVICE_ACCOUNT,
                            "volumes": [],
                        },
                    },
                },
            },
        }
    return {
        "metadata": {
            "name": transport.PARKED_JOB,
            "uid": JOB_UID,
            "generation": str(generation),
        },
        "spec": spec,
        "status": {
            "observedGeneration": str(generation),
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _terminal_execution(state: str = "True") -> dict:
    return {
        "metadata": {"name": f"{transport.PARKED_JOB}-abcde"},
        "status": {
            "conditions": [{"type": "Completed", "status": state}],
        },
    }


def _build() -> dict:
    return {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": {
            "revision": CODE_SHA,
            "url": transport.EXPECTED_CODE_REPOSITORY,
        }},
        "sourceProvenance": {
            "resolvedGitSource": {
                "revision": CODE_SHA,
                "url": transport.EXPECTED_CODE_REPOSITORY,
            },
        },
        "results": {"images": [{"digest": IMAGE.rsplit("@", 1)[1]}]},
        "steps": [{
            "status": "SUCCESS",
            "exitCode": 0,
            "args": [
                "python scripts/run_corpus_retrieval_transport.py --help",
                "python -c 'import nfl_dfs.research.corpus_retrieval_engine'",
            ],
        }],
    }


def _identity(uri: str, raw: bytes, generation: str = "7") -> dict:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_execute_gate_precedes_any_enabled_work():
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="literal --execute",
    ):
        transport.require_execute_gate(execute=False, environ={})
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match=transport.ENABLE_ENV,
    ):
        transport.require_execute_gate(execute=True, environ={})
    transport.require_execute_gate(
        execute=True,
        environ={transport.ENABLE_ENV: "1"},
    )


def test_parked_command_is_default_off_and_client_free(capsys):
    assert transport.main(["parked"]) == 0
    output = capsys.readouterr().out
    assert "default_off=true" in output
    assert "client_constructed=false" in output


def test_reuse_preflight_captures_uid_generation_but_rejects_live_state():
    result = transport.validate_reuse_census(
        job=_job(),
        executions=[_terminal_execution()],
        schedulers=[],
    )
    assert result == {
        "name": transport.PARKED_JOB,
        "uid": JOB_UID,
        "generation": "7",
        "observed_generation": "7",
        "spec_sha256": transport.canonical_sha256(_job()["spec"]),
    }

    active = _terminal_execution()
    active["status"] = {"conditions": []}
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="active/nonterminal",
    ):
        transport.validate_reuse_census(
            job=_job(), executions=[active], schedulers=[]
        )

    scheduler = {
        "httpTarget": {
            "uri": (
                "https://run.googleapis.com/v2/projects/p/locations/r/jobs/"
                f"{transport.PARKED_JOB}:run"
            ),
        },
    }
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="scheduler targets",
    ):
        transport.validate_reuse_census(
            job=_job(), executions=[], schedulers=[scheduler]
        )

    stale = _job()
    stale["status"]["observedGeneration"] = "6"
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="observedGeneration differs",
    ):
        transport.validate_reuse_census(
            job=stale, executions=[], schedulers=[]
        )

    not_ready = _job()
    not_ready["status"]["conditions"][0]["status"] = "False"
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="not Ready",
    ):
        transport.validate_reuse_census(
            job=not_ready, executions=[], schedulers=[]
        )


def test_reuse_job_name_is_fixed_but_uid_is_captured_not_hardcoded():
    wrong = _job()
    wrong["metadata"]["name"] = "different-parked-job"
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="job name",
    ):
        transport.validate_reuse_census(
            job=wrong, executions=[], schedulers=[]
        )
    source = (
        ROOT / "scripts" / "run_corpus_retrieval_transport.py"
    ).read_text(encoding="utf-8")
    assert "fixture-job-uid" not in source


def test_build_binds_direct_git_source_digest_and_integration_smokes():
    assert transport.validate_build_metadata(
        _build(), build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
        code_repository=transport.EXPECTED_CODE_REPOSITORY,
    ) == {
        "build_id": BUILD_ID,
        "code_repository": transport.EXPECTED_CODE_REPOSITORY,
        "code_sha": CODE_SHA,
        "image": IMAGE,
    }

    for mutation, match in (
        (lambda row: row.__setitem__("status", "FAILURE"), "identity"),
        (
            lambda row: row["sourceProvenance"]["resolvedGitSource"].__setitem__(
                "revision", "c" * 40
            ),
            "source commit",
        ),
        (
            lambda row: row["source"]["gitSource"].__setitem__(
                "url", "https://example.invalid/wrong.git"
            ),
            "source commit",
        ),
        (
            lambda row: row["results"].__setitem__("images", []),
            "image digest",
        ),
        (
            lambda row: row["steps"][0].__setitem__("args", []),
            "build smokes",
        ),
    ):
        value = _build()
        mutation(value)
        with pytest.raises(transport.CorpusRetrievalTransportError, match=match):
            transport.validate_build_metadata(
                value, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
                code_repository=transport.EXPECTED_CODE_REPOSITORY,
            )


def test_repository_cloudbuild_contains_required_transport_fragments():
    source = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    for fragment in transport.REQUIRED_BUILD_FRAGMENTS:
        assert fragment in source


def test_suite_release_must_equal_the_validated_build():
    suite = {
        "engine_release": {
            "engine_version": "corpus-retrieval-engine-v1",
            "code_repository": transport.EXPECTED_CODE_REPOSITORY,
            "code_commit": CODE_SHA,
            "image_uri": IMAGE,
            "image_digest": IMAGE.rsplit("@", 1)[1],
        },
    }
    build = {
        "build_id": BUILD_ID,
        "code_repository": transport.EXPECTED_CODE_REPOSITORY,
        "code_sha": CODE_SHA,
        "image": IMAGE,
    }
    assert transport.validate_suite_build_binding(
        suite, build,
    )["image_uri"] == IMAGE
    wrong = dict(build)
    wrong["code_sha"] = "c" * 40
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="suite engine release differs",
    ):
        transport.validate_suite_build_binding(suite, wrong)


def test_updated_job_is_one_task_attempt_zero_and_safely_parked():
    result = transport.validate_parked_job(
        _job(),
        expected_uid=JOB_UID,
        expected_image=IMAGE,
        expected_code_sha=CODE_SHA,
        expected_build_id=BUILD_ID,
        expected_service_account=SERVICE_ACCOUNT,
    )
    assert result["uid"] == JOB_UID

    mutators = (
        lambda value: value["spec"]["template"]["spec"].__setitem__(
            "taskCount", 2
        ),
        lambda value: value["spec"]["template"]["spec"]["template"][
            "spec"
        ].__setitem__("maxRetries", 1),
        lambda value: value["spec"]["template"]["spec"]["template"][
            "spec"
        ]["containers"][0].__setitem__("args", ["execute-task"]),
        lambda value: value["spec"]["template"]["spec"]["template"][
            "spec"
        ]["containers"][0]["env"].append({"name": "EXTRA", "value": "1"}),
        lambda value: value["spec"]["template"]["spec"]["template"][
            "spec"
        ].__setitem__("volumes", [{"name": "unsafe"}]),
    )
    for mutate in mutators:
        value = _job()
        mutate(value)
        with pytest.raises(
            transport.CorpusRetrievalTransportError,
            match="parked contract",
        ):
            transport.validate_parked_job(
                value,
                expected_uid=JOB_UID,
                expected_image=IMAGE,
                expected_code_sha=CODE_SHA,
                expected_build_id=BUILD_ID,
                expected_service_account=SERVICE_ACCOUNT,
            )


def test_preacceptance_rollback_is_exact_but_success_keeps_parked_spec():
    before = _job(generation=7)
    rolled_back = _job(generation=9)
    assert transport.validate_preacceptance_rollback(
        before=before, rolled_back=rolled_back,
    )["generation"] == "9"

    wrong = _job(generation=9)
    wrong["spec"]["template"]["spec"]["parallelism"] = 2
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="not rolled back",
    ):
        transport.validate_preacceptance_rollback(
            before=before, rolled_back=wrong
        )

    wrong_uid = _job(generation=9)
    wrong_uid["metadata"]["uid"] = "recreated-resource"
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="not rolled back",
    ):
        transport.validate_preacceptance_rollback(
            before=before, rolled_back=wrong_uid
        )

    deployed = _job(generation=8)
    assert transport.validate_post_terminal_parked_job(
        deployed=deployed, post_terminal=deepcopy(deployed),
    )["generation"] == "8"
    changed = _job(generation=9)
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="changed during execution",
    ):
        transport.validate_post_terminal_parked_job(
            deployed=deployed, post_terminal=changed,
        )


def test_local_identity_reader_reopens_only_exact_body(tmp_path):
    raw = b"real-outcome-blind-artifact"
    path = tmp_path / "R0.npz"
    path.write_bytes(raw)
    identity = _identity("gs://fixture/source/R0.npz", raw)
    reader = transport.LocalIdentityReader([{
        "identity": identity,
        "path": str(path),
    }])
    assert reader.read(identity) == raw

    wrong = dict(identity)
    wrong["generation"] = "8"
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="lacks the exact",
    ):
        reader.read(wrong)
    path.write_bytes(b"changed")
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="body differs",
    ):
        reader.read(identity)


def test_local_publisher_is_create_once_and_prefix_bounded(tmp_path):
    root = tmp_path / "published"
    prefix = "gs://fixture/retrieval/smoke/"
    publisher = transport.LocalCreateOncePublisher(root, allowed_prefix=prefix)
    raw = b'{"schema":"fixture"}'
    receipt = publisher.publish(
        f"{prefix}tasks/0000/result.json", raw, "application/json"
    )
    assert receipt["generation"] == "1"
    assert receipt["sha256"] == sha256(raw).hexdigest()
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="escapes",
    ):
        publisher.publish(
            "gs://fixture/elsewhere/result.json", raw, "application/json"
        )


def test_strict_json_and_object_identity_fail_closed():
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="repeats key",
    ):
        transport.strict_json_bytes(b'{"x":1,"x":1}', label="fixture")
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="not canonical",
    ):
        transport.strict_json_bytes(b'{"x": 1}', label="fixture")
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="canonical GCS",
    ):
        transport.object_identity(
            {
                "uri": "gs://bucket/a/../b",
                "generation": "1",
                "sha256": "a" * 64,
                "bytes": 1,
            },
            label="fixture",
        )


def _iam_evidence(*, project_policy: dict | None = None) -> dict:
    read_prefixes = [
        "gs://fixture-bucket/inputs/2023-w01/",
        "gs://fixture-bucket/retrieval/run-1/",
    ]
    view_targets = [transport._resource_prefix(row) for row in read_prefixes]
    viewer_expression = " || ".join(
        f'resource.name.startsWith("{row}")' for row in view_targets
    )
    creator_expression = (
        'resource.name.startsWith("'
        + transport._resource_prefix(read_prefixes[1])
        + '")'
    )
    member = f"serviceAccount:{SERVICE_ACCOUNT}"
    return transport.build_runtime_iam_evidence(
        captured_at_utc="2026-08-21T18:00:00Z",
        service_account=SERVICE_ACCOUNT,
        read_prefixes=read_prefixes,
        output_prefix=read_prefixes[1],
        project_policy=project_policy or {"bindings": []},
        bucket_policies=[{
            "bucket": "fixture-bucket",
            "policy": {"bindings": [
                {
                    "role": "roles/storage.objectViewer",
                    "members": [member],
                    "condition": {
                        "title": "corpus-retrieval-read-v1",
                        "expression": viewer_expression,
                    },
                },
                {
                    "role": "roles/storage.objectCreator",
                    "members": [member],
                    "condition": {
                        "title": "corpus-retrieval-create-v1",
                        "expression": creator_expression,
                    },
                },
            ]},
        }],
        required_read_uris=[
            "gs://fixture-bucket/inputs/2023-w01/R0.npz",
            "gs://fixture-bucket/retrieval/run-1/governance/suite-manifest.json",
        ],
        bucket_metadata={
            "name": "fixture-bucket",
            "iamConfiguration": {
                "uniformBucketLevelAccess": {"enabled": True},
                "publicAccessPrevention": "enforced",
            },
        },
    )


def test_runtime_iam_is_dedicated_prefix_limited_and_has_no_project_role():
    evidence = _iam_evidence()
    assert evidence["service_account"] == SERVICE_ACCOUNT
    assert evidence["output_prefix"].endswith("/retrieval/run-1/")

    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="forbidden project-level role",
    ):
        _iam_evidence(project_policy={
            "bindings": [{
                "role": "roles/bigquery.dataViewer",
                "members": [f"serviceAccount:{SERVICE_ACCOUNT}"],
            }],
        })

    wrong = deepcopy(evidence)
    wrong["bucket_policies"][0]["policy"]["bindings"][0]["role"] = (
        "roles/storage.objectAdmin"
    )
    wrong.pop("iam_evidence_sha256")
    wrong["iam_evidence_sha256"] = transport.canonical_sha256(wrong)
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="forbidden/repeated bucket role",
    ):
        transport.validate_runtime_iam_evidence(
            wrong,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=[
                "gs://fixture-bucket/inputs/2023-w01/R0.npz",
                "gs://fixture-bucket/retrieval/run-1/governance/suite-manifest.json",
            ],
            output_prefix="gs://fixture-bucket/retrieval/run-1/",
        )

    no_ubla = deepcopy(evidence)
    no_ubla["bucket_metadata"]["iamConfiguration"][
        "uniformBucketLevelAccess"
    ]["enabled"] = False
    no_ubla.pop("iam_evidence_sha256")
    no_ubla["iam_evidence_sha256"] = transport.canonical_sha256(no_ubla)
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="UBLA/PAP enforcement",
    ):
        transport.validate_runtime_iam_evidence(
            no_ubla,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=[
                "gs://fixture-bucket/inputs/2023-w01/R0.npz",
                "gs://fixture-bucket/retrieval/run-1/governance/suite-manifest.json",
            ],
            output_prefix="gs://fixture-bucket/retrieval/run-1/",
        )

    no_pap = deepcopy(evidence)
    no_pap["bucket_metadata"]["iamConfiguration"][
        "publicAccessPrevention"
    ] = "inherited"
    no_pap.pop("iam_evidence_sha256")
    no_pap["iam_evidence_sha256"] = transport.canonical_sha256(no_pap)
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="UBLA/PAP enforcement",
    ):
        transport.validate_runtime_iam_evidence(
            no_pap,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=[
                "gs://fixture-bucket/inputs/2023-w01/R0.npz",
                "gs://fixture-bucket/retrieval/run-1/governance/suite-manifest.json",
            ],
            output_prefix="gs://fixture-bucket/retrieval/run-1/",
        )

    overbroad = deepcopy(evidence)
    overbroad["read_prefixes"].append("gs://fixture-bucket/unrelated/extra/")
    overbroad["read_prefixes"].sort()
    overbroad.pop("iam_evidence_sha256")
    overbroad["iam_evidence_sha256"] = transport.canonical_sha256(overbroad)
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="exact input/output read prefixes",
    ):
        transport.validate_runtime_iam_evidence(
            overbroad,
            service_account=SERVICE_ACCOUNT,
            required_read_uris=[
                "gs://fixture-bucket/inputs/2023-w01/R0.npz",
                "gs://fixture-bucket/retrieval/run-1/governance/suite-manifest.json",
            ],
            output_prefix="gs://fixture-bucket/retrieval/run-1/",
        )


def test_required_read_closure_includes_nested_source_authorities():
    core = transport._core_module()
    source_raw = b'{"source":"candidate-player"}'
    producer_raw = b'{"source":"snapshot-producer"}'
    source_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/source-authority.json",
        source_raw,
    )
    producer_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/producer-authority.json",
        producer_raw,
    )
    player_ids = [f"p{index}" for index in range(9)]
    candidate_rows = [{
        "panel_id": "panel-r0",
        "season": 2023,
        "week": 1,
        "cand_ix": 0,
        "tag": "fixture",
        "all_tags": ["fixture"],
        "players": player_ids,
    }]
    candidate = core.build_candidate_rows_object(
        task_id="s2023-w01",
        source_authority=source_identity,
        source_sql_sha256="c" * 64,
        source_query_receipt={
            "job_id": "fixture-job",
            "project": transport.PROJECT,
            "location": "US",
            "sql_sha256": "c" * 64,
            "snapshot_at_utc": "2026-08-21T18:00:00Z",
            "created": "2026-08-21T18:00:00Z",
            "started": "2026-08-21T18:00:01Z",
            "ended": "2026-08-21T18:00:02Z",
            "total_bytes_processed": 1,
            "cache_hit": False,
            "error_result": None,
            "row_count": 1,
            "rows_sha256": "d" * 64,
            "normalized_rows_sha256": core.canonical_sha256(
                core.normalize_candidate_query_rows(candidate_rows)
            ),
        },
        rows=candidate_rows,
    )
    players = core.build_player_catalog_object(
        task_id="s2023-w01",
        source_authority=source_identity,
        players=[{
            "id": player_id,
            "name": f"Player {index}",
            "pos": "QB" if index == 0 else "WR",
            "team": "AAA",
            "opp": "BBB",
            "game_id": "AAA-BBB",
            "salary": 5000,
            "proj": 10.0,
        } for index, player_id in enumerate(player_ids)],
    )
    candidate_raw = transport.canonical_json_bytes(candidate)
    player_raw = transport.canonical_json_bytes(players)
    candidate_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/candidates.json",
        candidate_raw,
    )
    player_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/players.json",
        player_raw,
    )
    world_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/R0.npz", b"worlds"
    )
    snapshot = {
        "producer": {"producer_authority": producer_identity},
        "tasks": [{
            "candidate_rows_object": candidate_identity,
            "player_catalog_object": player_identity,
            "world_blocks": [{"artifact_object": world_identity}],
        }],
    }
    suite_identity = transport.ObjectIdentity(**_identity(
        "gs://fixture-bucket/retrieval/run-1/governance/suite-manifest.json",
        b"suite",
    ))
    snapshot_identity = transport.ObjectIdentity(**_identity(
        "gs://fixture-bucket/inputs/2023-w01/snapshot.json", b"snapshot"
    ))
    uris = transport._task_required_read_uris(
        suite_identity=suite_identity,
        snapshot_identity=snapshot_identity,
        snapshot=snapshot,
        task_index=0,
        candidate_rows_raw=candidate_raw,
        player_catalog_raw=player_raw,
    )
    assert source_identity["uri"] in uris
    assert producer_identity["uri"] in uris
    assert candidate_identity["uri"] in uris
    assert player_identity["uri"] in uris

    different = core.build_player_catalog_object(
        task_id="s2023-w01",
        source_authority=producer_identity,
        players=players["players"],
    )
    different_raw = transport.canonical_json_bytes(different)
    snapshot["tasks"][0]["player_catalog_object"] = _identity(
        player_identity["uri"], different_raw
    )
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="nested source authorities differ",
    ):
        transport._task_required_read_uris(
            suite_identity=suite_identity,
            snapshot_identity=snapshot_identity,
            snapshot=snapshot,
            task_index=0,
            candidate_rows_raw=candidate_raw,
            player_catalog_raw=different_raw,
        )


def test_cloud_runtime_execution_envelope_is_exact_attempt_zero():
    value = transport._runtime_execution({
        "CLOUD_RUN_JOB": transport.PARKED_JOB,
        "CLOUD_RUN_EXECUTION": f"{transport.PARKED_JOB}-abcde",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        transport.CODE_ENV: CODE_SHA,
        transport.IMAGE_ENV: IMAGE,
    })
    assert value == {
        "execution_id": f"{transport.PARKED_JOB}-abcde",
        "execution_name": f"{transport.PARKED_JOB}-abcde",
        "task_index": 0,
        "attempt": 0,
        "retry_count": 0,
        "mode": "cloud-run-task",
        "code_commit": CODE_SHA,
        "image_uri": IMAGE,
        "image_digest": IMAGE.rsplit("@", 1)[1],
    }
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="attempt-zero identity",
    ):
        transport._runtime_execution({
            "CLOUD_RUN_JOB": transport.PARKED_JOB,
            "CLOUD_RUN_EXECUTION": f"{transport.PARKED_JOB}-abcde",
            "CLOUD_RUN_TASK_INDEX": "0",
            "CLOUD_RUN_TASK_ATTEMPT": "1",
            "CLOUD_RUN_TASK_COUNT": "1",
            transport.CODE_ENV: CODE_SHA,
            transport.IMAGE_ENV: IMAGE,
        })


def test_transport_has_no_outcome_bq_or_live_policy_dependency():
    source = (
        ROOT / "scripts" / "run_corpus_retrieval_transport.py"
    ).read_text(encoding="utf-8")
    assert "from nfl_dfs import bq" not in source
    assert "google.cloud.bigquery" not in source
    assert "production_policy" not in source
    assert "historical_outcome_lease" not in source
    assert "CORPUS_RETRIEVAL_RESEARCH_ENABLED" in source
    assert "CLOUD_RUN_TASK_ATTEMPT" in source


def test_every_mutating_or_score_action_has_its_own_gate(tmp_path):
    identity = transport.ObjectIdentity(
        uri="gs://fixture-bucket/narrow/object.json",
        generation="1",
        sha256="a" * 64,
        bytes=1,
    )
    actions = [
        lambda: transport.run_local_task(
            suite_raw=b"x",
            suite_identity=identity,
            snapshot_raw=b"x",
            snapshot_identity=identity,
            object_rows=[],
            task_index=0,
            output_dir=tmp_path / "out",
            execution_id="local-smoke",
            execute=False,
            environ={transport.ENABLE_ENV: "1"},
        ),
        lambda: transport.execute_cloud_task(
            suite_identity=identity,
            snapshot_identity=identity,
            execution_contract_identity=identity,
            task_index=0,
            execute=False,
            environ={transport.ENABLE_ENV: "1"},
        ),
        lambda: transport.finish_cloud_task(
            execution_contract_identity=identity,
            execution_name="execution-name",
            terminal_metadata={},
            deployed_job={},
            post_terminal_job={},
            executions_after=[],
            schedulers_after=[],
            finished_at_utc="2026-08-21T18:00:00Z",
            execute=False,
            environ={transport.ENABLE_ENV: "1"},
        ),
        lambda: transport.publish_launch_ledger(
            execution_contract_identity=identity,
            job={},
            executions=[],
            schedulers=[],
            created_at_utc="2026-08-21T18:00:00Z",
            execute=False,
            environ={transport.ENABLE_ENV: "1"},
        ),
        lambda: transport.bind_execution_name(
            execution_contract_identity=identity,
            execution_metadata={},
            job={},
            executions=[],
            schedulers=[],
            created_at_utc="2026-08-21T18:00:00Z",
            execute=False,
            environ={transport.ENABLE_ENV: "1"},
        ),
        lambda: transport.publish_transport_governance(
            preflight={},
            execution_contract_raw=b"x",
            runtime_iam_evidence_raw=b"x",
            published_at_utc="2026-08-21T18:00:00Z",
            storage=object(),
            execute=False,
            environ={transport.ENABLE_ENV: "1"},
        ),
    ]
    for action in actions:
        with pytest.raises(
            transport.CorpusRetrievalTransportError,
            match="literal --execute",
        ):
            action()


def test_launch_consumption_ledger_exposes_ambiguous_recovery(monkeypatch):
    raw = b'{"ledger":"exact"}'
    identity = _identity(
        "gs://fixture-bucket/retrieval/run-1/governance/launch.json",
        raw,
        generation="11",
    )
    store = transport.GenerationPinnedStorage.__new__(
        transport.GenerationPinnedStorage
    )
    monkeypatch.setattr(store, "publish", lambda *_args: identity)
    assert store.publish_consumption_ledger(
        identity["uri"], raw, "application/json"
    ) == (identity, True)

    def lost_response(*_args):
        raise RuntimeError("response lost after create")

    monkeypatch.setattr(store, "publish", lost_response)
    monkeypatch.setattr(
        store,
        "resolve_unique",
        lambda _uri: (identity, raw),
    )
    recovered, launch_permitted = store.publish_consumption_ledger(
        identity["uri"], raw, "application/json"
    )
    assert recovered == identity
    assert launch_permitted is False

    monkeypatch.setattr(
        store,
        "resolve_unique",
        lambda _uri: (identity, b"different"),
    )
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="existing launch ledger differs",
    ):
        store.publish_consumption_ledger(
            identity["uri"], raw, "application/json"
        )


def test_exact_current_resolver_uses_get_without_bucket_list():
    raw = b'{"authority":"exact-current"}'
    uri = "gs://fixture-bucket/retrieval/run-1/governance/current.json"

    class Blob:
        def __init__(self, *, generation=None):
            self.generation = generation
            self.size = None
            self.reload_count = 0
            self.download_match = None

        def reload(self):
            self.reload_count += 1
            self.generation = "12"
            self.size = len(raw)

        def download_as_bytes(self, *, if_generation_match):
            self.download_match = if_generation_match
            return raw

    metadata_blob = Blob()
    pinned_blob = Blob(generation=12)

    class Bucket:
        def blob(self, name, generation=None):
            assert name == "retrieval/run-1/governance/current.json"
            if generation is None:
                return metadata_blob
            assert generation == 12
            return pinned_blob

    class Client:
        def bucket(self, name):
            assert name == "fixture-bucket"
            return Bucket()

        def list_blobs(self, *_args, **_kwargs):
            pytest.fail("exact worker resolver must not list the bucket")

    store = transport.GenerationPinnedStorage.__new__(
        transport.GenerationPinnedStorage
    )
    store._client = Client()
    identity, reopened = store.resolve_current(uri)
    assert reopened == raw
    assert identity == _identity(uri, raw, "12")
    assert metadata_blob.reload_count == 1
    assert pinned_blob.download_match == 12


def test_worker_governance_reopens_exact_names_without_list(monkeypatch):
    prefix = "gs://fixture-bucket/retrieval/run-1/governance/"
    uris = {
        "claim": prefix + "claim.json",
        "iam": prefix + "iam.json",
        "intent": prefix + "intent.json",
    }
    raw = {uri: b"{}" for uri in uris.values()}
    identities = {
        uri: _identity(uri, body, str(index + 11))
        for index, (uri, body) in enumerate(raw.items())
    }
    suite_identity = _identity(prefix + "suite.json", b"suite")
    snapshot_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/snapshot.json", b"snapshot"
    )
    candidate_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/candidates.json", b"candidates"
    )
    player_identity = _identity(
        "gs://fixture-bucket/inputs/2023-w01/players.json", b"players"
    )
    suite = {"fixture": "suite"}
    snapshot = {"tasks": [{
        "candidate_rows_object": candidate_identity,
        "player_catalog_object": player_identity,
    }]}
    contract_identity = transport.ObjectIdentity(**_identity(
        prefix + "contract.json", b"contract"
    ))
    contract = {
        "prefix_claim_uri": uris["claim"],
        "runtime_iam_evidence_uri": uris["iam"],
        "runtime_iam_evidence_bytes": len(raw[uris["iam"]]),
        "runtime_iam_evidence_sha256": sha256(raw[uris["iam"]]).hexdigest(),
        "suite_manifest_identity": suite_identity,
        "snapshot_manifest_identity": snapshot_identity,
        "task_index": 0,
        "build": {"fixture": "build"},
        "service_account": SERVICE_ACCOUNT,
        "output_prefix": "gs://fixture-bucket/retrieval/run-1/",
        "launch_intent_uri": uris["intent"],
    }

    class Store:
        def __init__(self):
            self.current_reads = []

        def resolve_current(self, uri):
            self.current_reads.append(uri)
            return identities[uri], raw[uri]

        def resolve_unique(self, _uri):
            pytest.fail("worker governance must not use list resolution")

        def inventory(self, _prefix):
            pytest.fail("worker governance must not inventory the bucket")

        def read(self, identity):
            if identity == suite_identity:
                return b"suite"
            if identity == snapshot_identity:
                return b"snapshot"
            if identity == candidate_identity:
                return b"candidates"
            if identity == player_identity:
                return b"players"
            pytest.fail(f"unexpected identity read: {identity}")

    store = Store()
    monkeypatch.setattr(transport, "_core_module", lambda: object())
    monkeypatch.setattr(
        transport, "_validate_suite_with_core", lambda _core, _raw: suite
    )
    monkeypatch.setattr(
        transport,
        "_validate_snapshot_with_core",
        lambda _core, _raw: snapshot,
    )
    monkeypatch.setattr(
        transport, "_require_one_task_manifests", lambda *_args: None
    )
    monkeypatch.setattr(
        transport, "validate_suite_build_binding", lambda *_args: None
    )
    monkeypatch.setattr(
        transport, "validate_runtime_iam_evidence", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        transport, "_task_required_read_uris", lambda **_kwargs: []
    )
    monkeypatch.setattr(
        transport,
        "validate_prefix_claim",
        lambda *_args, **_kwargs: {"fixture": "claim"},
    )
    monkeypatch.setattr(
        transport,
        "validate_launch_intent",
        lambda *_args, **_kwargs: {
            "prefix_claim": identities[uris["claim"]],
            "runtime_iam_evidence": identities[uris["iam"]],
        },
    )
    reopened = transport._reopen_governance(
        storage=store,
        contract=contract,
        contract_identity=contract_identity,
        exact_name_only=True,
    )
    assert store.current_reads == [uris["claim"], uris["iam"], uris["intent"]]
    assert reopened["launch_intent_identity"] == identities[uris["intent"]]


def test_worker_wait_gate_accepts_only_its_durable_execution_name(monkeypatch):
    contract_identity = transport.ObjectIdentity(
        uri=(
            "gs://fixture-bucket/retrieval/run-1/governance/"
            "task-0000-execution-contract.json"
        ),
        generation="7",
        sha256="a" * 64,
        bytes=10,
    )
    launch_identity = {
        "uri": (
            "gs://fixture-bucket/retrieval/run-1/governance/"
            "task-0000-launch-ledger.json"
        ),
        "generation": "8",
        "sha256": "b" * 64,
        "bytes": 11,
    }
    execution_name = f"{transport.PARKED_JOB}-abcde"
    contract = {
        "execution_name_ledger_uri": (
            "gs://fixture-bucket/retrieval/run-1/governance/"
            "task-0000-execution-name.json"
        ),
        "job_execution": {"uid": JOB_UID, "generation": "8"},
    }
    ledger = transport._self_hash({
        "schema_version": transport.EXECUTION_NAME_LEDGER_SCHEMA,
        "created_at_utc": "2026-08-21T18:00:00Z",
        "execution_contract": contract_identity.as_dict(),
        "launch_ledger": launch_identity,
        "execution_id": execution_name,
        "execution_name": execution_name,
        "execution_uid": "execution-uid",
        "execution_metadata_sha256": "c" * 64,
        "job_uid": JOB_UID,
        "job_generation": "8",
        "exactly_one_new_execution": True,
        "attempt": 0,
        "max_retries": 0,
        "automatic_relaunch_licensed": False,
        "uses_realized_outcomes": False,
    }, field="execution_name_ledger_sha256")
    raw = transport.canonical_json_bytes(ledger)
    identity = _identity(contract["execution_name_ledger_uri"], raw, "9")

    class Store:
        def resolve_current(self, uri):
            assert uri == contract["execution_name_ledger_uri"]
            return identity, raw

        def resolve_unique(self, _uri):
            pytest.fail("worker wait must not use list resolution")

        def inventory(self, _prefix):
            pytest.fail("worker wait must not inventory the bucket")

    runtime = {
        "execution_id": execution_name,
        "execution_name": execution_name,
    }
    bound_identity, bound = transport._wait_for_execution_name_ledger(
        storage=Store(),
        contract=contract,
        contract_identity=contract_identity,
        launch_identity=launch_identity,
        runtime_execution=runtime,
        timeout_seconds=1,
    )
    assert bound_identity == identity
    assert bound["execution_uid"] == "execution-uid"

    wrong = dict(runtime)
    wrong["execution_name"] = f"{transport.PARKED_JOB}-wrong"
    monkeypatch.setattr(
        transport.time,
        "sleep",
        lambda _seconds: pytest.fail("immutable mismatch must fail immediately"),
    )
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="differs from durable execution-name ledger",
    ):
        transport._wait_for_execution_name_ledger(
            storage=Store(),
            contract=contract,
            contract_identity=contract_identity,
            launch_identity=launch_identity,
            runtime_execution=wrong,
            timeout_seconds=1,
        )


def test_result_execution_must_equal_exact_terminal_name_and_id():
    terminal = {
        "execution_id": f"{transport.PARKED_JOB}-abcde",
        "execution_name": f"{transport.PARKED_JOB}-abcde",
    }
    authority = {
        "execution": {
            "execution_id": terminal["execution_id"],
            "execution_name": terminal["execution_name"],
            "attempt": 0,
            "retry_count": 0,
            "mode": "cloud-run-task",
        },
    }
    assert transport.validate_result_execution_binding(
        authority, terminal=terminal,
    )["execution_name"] == terminal["execution_name"]
    wrong = deepcopy(authority)
    wrong["execution"]["execution_name"] = (
        f"projects/{transport.PROJECT}/locations/{transport.REGION}/"
        f"jobs/{transport.PARKED_JOB}/executions/{terminal['execution_id']}"
    )
    with pytest.raises(
        transport.CorpusRetrievalTransportError,
        match="exact terminal execution",
    ):
        transport.validate_result_execution_binding(wrong, terminal=terminal)


def test_cloud_worker_function_has_no_list_or_inventory_path():
    source = (
        ROOT / "scripts" / "run_corpus_retrieval_transport.py"
    ).read_text(encoding="utf-8")
    worker = source.split("def execute_cloud_task(", 1)[1].split(
        "\ndef validate_terminal_execution(", 1
    )[0]
    assert "exact_name_only=True" in worker
    assert ".resolve_current(" in worker
    assert ".resolve_unique(" not in worker
    assert ".inventory(" not in worker
    assert "_require_exact_inventory(" not in worker


def test_reuse_only_launcher_is_gated_parked_and_never_relaunches():
    path = ROOT / "scripts" / "cloud_corpus_retrieval_v1_reuse.sh"
    subprocess.run(["bash", "-n", str(path)], check=True)
    source = path.read_text(encoding="utf-8")
    first_cloud = source.index("gcloud ")
    gate = source.index("CORPUS_RETRIEVAL_RESEARCH_ENABLED")
    assert gate < first_cloud
    assert "gcloud run jobs create" not in source
    assert "gcloud run jobs deploy" not in source
    assert "gcloud run jobs update" in source
    assert "--max-retries=0" in source
    launch = source.split("consume_and_launch() {", 1)[1].split(
        "recover_name() {", 1
    )[0]
    assert launch.index("consume-launch") < launch.index(
        "gcloud run jobs execute"
    )
    assert '[[ "$permitted" == "true" ]]' in launch
    assert "launch already consumed; run recover, never launch" in launch
    recover = source.split("recover_name() {", 1)[1].split(
        "watch_bound() {", 1
    )[0]
    assert "gcloud run jobs execute" not in recover
    assert "accepted -eq 0" in source
    assert "prior A7 export is rollback-only and will not be restored" in source
