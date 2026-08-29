from types import SimpleNamespace

import pytest

from nfl_dfs.research import (
    corpus_r6_combined_population_all_block_execution_v1 as e,
)
from nfl_dfs.research import corpus_r6_combined_population_all_block_v1 as combined


def _identity(label: str, ordinal: int = 0) -> dict[str, object]:
    digest = f"{ordinal + 1:064x}"[-64:]
    return {
        "uri": f"gs://synthetic/{label}/{ordinal}",
        "generation": str(ordinal + 1),
        "sha256": digest,
        "bytes": ordinal + 1,
    }


def _manifest_inputs(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    later = _identity("later")
    profile_manifest_identity = _identity("profile-manifest")
    incumbent_rows = []
    descriptors = []
    profile_results = []
    profile_bindings = []
    hard_rows = []
    for ordinal in range(e.TASK_COUNT):
        slate_id = f"2023-w{ordinal + 1:02d}"
        request = {
            "source_ordinal": ordinal,
            "profile_order": list(combined.PROFILE_SOURCE_IDS),
            "projection_bundle_identity": _identity("projection", ordinal),
            "profile_lineup_identities": {
                source_id: _identity(source_id, ordinal)
                for source_id in combined.PROFILE_SOURCE_IDS
            },
            "request_sha256": f"{1000 + ordinal:064x}"[-64:],
        }
        incumbent_rows.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "slate_freeze_identity": _identity("incumbent-leaf", ordinal),
            "slate_freeze_sha256": f"{2000 + ordinal:064x}"[-64:],
            "task_result_sha256": f"{3000 + ordinal:064x}"[-64:],
        })
        descriptor = {
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "task_result_identity": _identity("profile-result", ordinal),
            "task_result_sha256": f"{4000 + ordinal:064x}"[-64:],
        }
        descriptors.append(descriptor)
        profile_results.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "task_request_sha256": request["request_sha256"],
            "slate_result_sha256": descriptor["task_result_sha256"],
        })
        profile_bindings.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "request": request,
            "request_sha256": request["request_sha256"],
        })
        hard_rows.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "later_source_identity": later,
            "slate_result_sha256": f"{5000 + ordinal:064x}"[-64:],
            "source_member_identity": {
                "object_identity": _identity("hard-member", ordinal)
            },
        })
    profile_manifest = {
        "profile_order": list(combined.PROFILE_SOURCE_IDS),
        "task_manifest_sha256": "6" * 64,
        "task_bindings": profile_bindings,
    }
    monkeypatch.setattr(
        e.crossed, "validate_task_manifest_v1", lambda value: value
    )
    monkeypatch.setattr(
        e.crossed, "validate_task_request_v1", lambda value: value
    )
    monkeypatch.setattr(
        e.crossed, "validate_slate_result_v1", lambda value: value
    )
    build_receipt = {
        "build_id": "123e4567-e89b-12d3-a456-426614174000",
        "finish_time": "2026-08-29T00:01:00+00:00",
        "image_digest": f"sha256:{'b' * 64}",
        "image_tag": "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test",
        "project_id": e.FIXED_GCP_PROJECT,
        "region": "us-central1",
        "source_commit": "a" * 40,
        "start_time": "2026-08-29T00:00:00+00:00",
        "status": "SUCCESS",
    }
    build_raw = e._canonical(build_receipt)
    return {
        "incumbent_panel_freeze": {
            "source_slate_count": e.TASK_COUNT,
            "later_source_freeze_identity": later,
            "slate_freezes": incumbent_rows,
            "panel_freeze_sha256": "7" * 64,
        },
        "incumbent_panel_freeze_identity": e.FIXED_INCUMBENT_PANEL_FREEZE_IDENTITY,
        "profile_terminal_root": {
            "source_slate_count": e.TASK_COUNT,
            "adapter_id": e.grader.POPULATION_CROSSED_ADAPTER,
            "task_manifest_identity": profile_manifest_identity,
            "task_manifest_sha256": profile_manifest["task_manifest_sha256"],
            "terminal_experiment_root_sha256": "8" * 64,
        },
        "profile_terminal_identity": e.FIXED_PROFILE_TERMINAL_IDENTITY,
        "profile_task_manifest": profile_manifest,
        "profile_task_result_descriptors": descriptors,
        "profile_task_results": profile_results,
        "hard230_terminal": {
            "source_slate_count": e.TASK_COUNT,
            "later_source_identity": later,
            "terminal_sha256": "9" * 64,
            "slate_results": hard_rows,
        },
        "hard230_terminal_identity": e.FIXED_HARD230_TERMINAL_IDENTITY,
        "terminal_build_receipt": build_receipt,
        "terminal_build_receipt_identity": {
            "uri": "gs://synthetic/build/receipt.json", "generation": "1",
            "sha256": e.sha256(build_raw).hexdigest(), "bytes": len(build_raw),
        },
        "output_prefix": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-combined-population-all-block/test-v1/"
        ),
    }


def _runtime_environment(manifest: dict[str, object], identity: dict[str, object], *, index: int = 0) -> dict[str, str]:
    environment = {
        "CLOUD_RUN_JOB": str(manifest["reused_job_name"]),
        "CLOUD_RUN_EXECUTION": "combined-execution-1",
        "CLOUD_RUN_TASK_INDEX": str(index),
        "CLOUD_RUN_TASK_COUNT": str(e.TASK_COUNT),
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "GOOGLE_CLOUD_PROJECT": e.FIXED_GCP_PROJECT,
        e.ENABLE_ENV: e.ENABLE_VALUE,
        e.MANIFEST_IDENTITY_ENV: e._canonical(identity).decode("utf-8"),
    }
    environment[e.JOB_AUTHORITY_SHA_ENV] = e._hash(
        e.expected_provider_job_observation_v1(
            manifest=manifest, manifest_identity=identity
        )
    )
    return environment


def test_manifest_binds_exact_54_sources_and_known_result_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = e.build_task_manifest_v1(**_manifest_inputs(monkeypatch))

    assert manifest["task_count"] == 54
    assert len(manifest["task_bindings"]) == 54
    assert manifest["source_population_ids"] == list(combined.SOURCE_ORDER)
    assert manifest["common_world_matrix_reconstructed_once_per_slate"] is True
    assert manifest["population_regeneration_performed"] is False
    assert manifest["uses_realized_outcomes"] is False
    assert manifest["historical_finalist_confirmation"] is True
    assert manifest["untouched_confirmatory_inference"] is False
    assert manifest["task_bindings"][0]["result_uri"].endswith(
        "/slates/00/selection-result.json"
    )
    assert manifest["task_bindings"][-1]["result_uri"].endswith(
        "/slates/53/selection-result.json"
    )


def test_manifest_rejects_substituted_finalist_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kwargs = _manifest_inputs(monkeypatch)
    kwargs["hard230_terminal_identity"] = _identity("substituted-hard")
    with pytest.raises(
        e.CorpusR6CombinedPopulationAllBlockExecutionV1Error,
        match="frozen finalists",
    ):
        e.build_task_manifest_v1(**kwargs)


def test_task_result_rejects_a_different_valid_manifest_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    later = _identity("later")
    manifest = {
        "task_manifest_sha256": "1" * 64,
        "later_source_identity": later,
        "code_commit": "a" * 40,
        "image_digest": f"sha256:{'b' * 64}",
        "reused_job_name": e.FIXED_REUSED_JOB_NAME,
        "reused_job_uid": e.FIXED_REUSED_JOB_UID,
        "immutable_image_uri": f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test@sha256:{'b' * 64}",
        "terminal_build_receipt_identity": _identity("build"),
        "terminal_build_receipt_sha256": "c" * 64,
        "task_bindings": [{
            "slate_id": "2023-w01",
            "task_binding_sha256": "2" * 64,
        }],
    }
    identity = _identity("manifest-a")
    science = {
        "result_sha256": "3" * 64,
        "union": {"union_lineup_count": 100},
        "book_count": 8,
        "entry_budget": 80,
    }
    monkeypatch.setattr(e, "validate_task_manifest_v1", lambda value: value)
    monkeypatch.setattr(e, "validate_provider_job_observation_v1", lambda value, **_kwargs: value)
    monkeypatch.setattr(
        e.combined,
        "normalized_slate_for_grader_v1",
        lambda _value, *, source_ordinal: {
            "source_ordinal": source_ordinal,
            "slate_id": "2023-w01",
            "later_source_identity": later,
        },
    )
    runtime = e.build_runtime_authority_v1(
        manifest=manifest,
        manifest_identity=identity,
        environment=_runtime_environment(manifest, identity),
        observed_command=e.DISPATCHER_COMMAND,
        observed_project_id=e.FIXED_GCP_PROJECT,
    )
    result = e.build_task_result_v1(
        manifest=manifest,
        manifest_identity=identity,
        source_ordinal=0,
        runtime_authority=runtime,
        science_result=science,
    )
    assert e.validate_task_result_v1(
        result, manifest=manifest, manifest_identity=identity
    ) == result
    with pytest.raises(
        e.CorpusR6CombinedPopulationAllBlockExecutionV1Error,
        match="reserved Cloud Run runtime|runtime authority canonical replay|fixed law",
    ):
        e.validate_task_result_v1(
            result,
            manifest=manifest,
            manifest_identity=_identity("manifest-b"),
        )


@pytest.mark.parametrize("field", ("CLOUD_RUN_JOB", "CLOUD_RUN_TASK_INDEX", "CLOUD_RUN_TASK_COUNT", "CLOUD_RUN_TASK_ATTEMPT"))
def test_reserved_runtime_must_equal_frozen_job_authority(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    identity = _identity("manifest")
    manifest = {
        "code_commit": "a" * 40,
        "image_digest": f"sha256:{'b' * 64}",
        "reused_job_name": e.FIXED_REUSED_JOB_NAME,
        "reused_job_uid": e.FIXED_REUSED_JOB_UID,
        "immutable_image_uri": f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test@sha256:{'b' * 64}",
        "terminal_build_receipt_identity": _identity("build"),
        "terminal_build_receipt_sha256": "c" * 64,
        "task_manifest_sha256": "d" * 64,
    }
    monkeypatch.setattr(e, "validate_task_manifest_v1", lambda value: value)
    monkeypatch.setattr(e, "validate_provider_job_observation_v1", lambda value, **_kwargs: value)
    environment = _runtime_environment(manifest, identity)
    environment[field] = "forged"
    environment["R6_COMBINED_POPULATION_ALL_BLOCK_CODE_COMMIT"] = manifest["code_commit"]
    with pytest.raises(
        e.CorpusR6CombinedPopulationAllBlockExecutionV1Error,
        match="reserved Cloud Run runtime",
    ):
        e.build_runtime_authority_v1(
            manifest=manifest,
            manifest_identity=identity,
            environment=environment,
            observed_command=e.DISPATCHER_COMMAND,
            observed_project_id=e.FIXED_GCP_PROJECT,
        )


def test_custom_project_env_cannot_forge_observed_client_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity("manifest")
    manifest = {
        "code_commit": "a" * 40, "image_digest": f"sha256:{'b' * 64}",
        "reused_job_name": e.FIXED_REUSED_JOB_NAME,
        "reused_job_uid": e.FIXED_REUSED_JOB_UID,
        "immutable_image_uri": f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test@sha256:{'b' * 64}",
        "terminal_build_receipt_identity": _identity("build"),
        "terminal_build_receipt_sha256": "c" * 64,
        "task_manifest_sha256": "d" * 64,
    }
    monkeypatch.setattr(e, "validate_task_manifest_v1", lambda value: value)
    monkeypatch.setattr(e, "validate_provider_job_observation_v1", lambda value, **_kwargs: value)
    environment = _runtime_environment(manifest, identity)
    environment["GOOGLE_CLOUD_PROJECT"] = e.FIXED_GCP_PROJECT
    with pytest.raises(e.CorpusR6CombinedPopulationAllBlockExecutionV1Error):
        e.build_runtime_authority_v1(
            manifest=manifest, manifest_identity=identity,
            environment=environment, observed_command=e.DISPATCHER_COMMAND,
            observed_project_id="forged-project",
        )


def test_provider_terminal_requires_fixed_uid_image_and_exact_54_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity("manifest")
    manifest = {
        "code_commit": "a" * 40,
        "image_digest": f"sha256:{'b' * 64}",
        "immutable_image_uri": f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test@sha256:{'b' * 64}",
        "reused_job_name": e.FIXED_REUSED_JOB_NAME,
        "reused_job_uid": e.FIXED_REUSED_JOB_UID,
        "terminal_build_receipt_identity": _identity("build"),
        "terminal_build_receipt_sha256": "c" * 64,
        "task_manifest_sha256": "d" * 64,
    }
    monkeypatch.setattr(e, "validate_task_manifest_v1", lambda value: value)
    job = e.expected_provider_job_observation_v1(
        manifest=manifest, manifest_identity=identity
    )
    terminal = {
        "execution_id": "execution-1", "job_name": e.FIXED_REUSED_JOB_NAME,
        "job_uid": e.FIXED_REUSED_JOB_UID, "task_count": 54,
        "succeeded_count": 54, "failed_count": 0, "cancelled_count": 0,
        "running_count": 0, "terminal": True, "provider_observed": True,
        "job_observation": job,
    }
    assert e.validate_provider_terminal_execution_v1(
        terminal, manifest=manifest, manifest_identity=identity
    )["succeeded_count"] == 54
    for field, wrong in (("succeeded_count", 53), ("job_uid", "forged-uid")):
        changed = dict(terminal)
        changed[field] = wrong
        with pytest.raises(e.CorpusR6CombinedPopulationAllBlockExecutionV1Error):
            e.validate_provider_terminal_execution_v1(
                changed, manifest=manifest, manifest_identity=identity
            )
    forged_job = dict(job)
    forged_job["immutable_image_uri"] = forged_job["immutable_image_uri"].replace("b", "e")
    changed = {**terminal, "job_observation": forged_job}
    with pytest.raises(e.CorpusR6CombinedPopulationAllBlockExecutionV1Error):
        e.validate_provider_terminal_execution_v1(
            changed, manifest=manifest, manifest_identity=identity
        )


def test_terminal_rejects_one_task_from_a_different_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_identity = _identity("manifest")
    bindings = [{"slate_id": f"s-{i}", "result_uri": f"gs://synthetic/r/{i}"}
                for i in range(e.TASK_COUNT)]
    manifest = {"task_bindings": bindings}
    monkeypatch.setattr(e, "validate_task_manifest_v1", lambda value: value)
    monkeypatch.setattr(
        e, "validate_provider_terminal_execution_v1", lambda value, **_kwargs: value
    )
    monkeypatch.setattr(e, "normalized_task_result_v1", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(e.grader, "validate_external_normalized_terminal_v1", lambda **_kwargs: None)
    results = []
    for ordinal, binding in enumerate(bindings):
        result = {
            "source_ordinal": ordinal, "slate_id": binding["slate_id"],
            "task_result_sha256": "a" * 64, "science_result_sha256": "b" * 64,
            "union_lineup_count": 100,
            "runtime_authority": {"execution_id": "other" if ordinal == 53 else "execution-1"},
        }
        raw = e._canonical(result)
        results.append((result, {
            "uri": binding["result_uri"], "generation": "1",
            "sha256": e.sha256(raw).hexdigest(), "bytes": len(raw),
        }))
    monkeypatch.setattr(e, "validate_task_result_v1", lambda value, **_kwargs: value)
    with pytest.raises(
        e.CorpusR6CombinedPopulationAllBlockExecutionV1Error,
        match="do not share provider terminal execution",
    ):
        e.build_terminal_v1(
            manifest=manifest, manifest_identity=manifest_identity,
            task_results=results,
            provider_terminal_execution={"execution_id": "execution-1"},
        )
