from types import SimpleNamespace
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_combined_population_all_block_execution_v1 as execution,
)
from scripts import run_corpus_r6_combined_population_all_block_v1 as op


def _identity(uri: str = "gs://synthetic/object") -> dict[str, object]:
    return {"uri": uri, "generation": "1", "sha256": "a" * 64, "bytes": 1}


def test_task_reconstructs_one_common_matrix_then_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    later = _identity("gs://synthetic/later")
    leaf_identity = _identity("gs://synthetic/incumbent-leaf")
    profile_result_identity = _identity("gs://synthetic/profile-result")
    member_object = _identity("gs://synthetic/source-member")
    hard_member_identity = {"object_identity": member_object}
    binding = {
        "slate_id": "2023-w01",
        "incumbent_slate_freeze_identity": leaf_identity,
        "incumbent_slate_freeze_sha256": "1" * 64,
        "incumbent_task_result_sha256": "2" * 64,
        "profile_task_result_identity": profile_result_identity,
        "profile_task_result_sha256": "3" * 64,
        "profile_source_request": {
            "request_sha256": "4" * 64,
            "projection_bundle_identity": _identity("gs://synthetic/projection"),
            "profile_lineup_identities": {"F": _identity("gs://synthetic/F")},
        },
        "profile_source_request_sha256": "4" * 64,
        "hard230_slate_result_sha256": "5" * 64,
        "hard230_source_member_identity": hard_member_identity,
        "task_binding_sha256": "6" * 64,
        "result_uri": "gs://synthetic/output/slates/00/selection-result.json",
    }
    manifest_identity = _identity("gs://synthetic/output/task-manifest.json")
    manifest = {
        "task_bindings": [binding],
        "later_source_identity": later,
        "hard230_terminal_identity": execution.FIXED_HARD230_TERMINAL_IDENTITY,
        "hard230_terminal_sha256": "7" * 64,
    }
    runtime = {"runtime_authority_sha256": "8" * 64, "task_index": 0}
    monkeypatch.setattr(op, "_open_manifest", lambda *_args, **_kwargs: (manifest, manifest_identity))
    monkeypatch.setattr(
        op.execution,
        "validate_runtime_authority_v1",
        lambda value, **_kwargs: value,
    )
    incumbent_result = {"task_result_sha256": "2" * 64}
    monkeypatch.setattr(
        op.full_freeze,
        "reopen_slate_freeze_v1",
        lambda *_args, **_kwargs: (
            {"slate_freeze_sha256": "1" * 64, "source_ordinal": 0, "slate_id": "2023-w01"},
            {"panel_index_identity": _identity("gs://synthetic/panel")},
            {"panel_index_sha256": "8" * 64},
            [{"slate_id": "2023-w01"}],
            incumbent_result,
            leaf_identity,
        ),
    )
    monkeypatch.setattr(op.combined, "project_incumbent_current_r6_source_v1", lambda **_kwargs: "incumbent")
    profile_result = {
        "slate_result_sha256": "3" * 64,
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "task_request_sha256": "4" * 64,
        "projection_bundle_identity": binding["profile_source_request"]["projection_bundle_identity"],
        "profile_lineup_identities": binding["profile_source_request"]["profile_lineup_identities"],
    }

    def fake_read_json(identity: object, **_kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        if identity == profile_result_identity:
            return profile_result, profile_result_identity
        if identity == member_object:
            events.append("source-member-read")
            return {"member": True}, member_object
        raise AssertionError(identity)

    monkeypatch.setattr(op, "_read_json", fake_read_json)
    monkeypatch.setattr(op.crossed, "validate_slate_result_v1", lambda value: value)
    players = tuple(SimpleNamespace(player_id=f"p{i}") for i in range(9))
    draws = np.zeros((9, 50_000), dtype=np.float32)
    prepared = SimpleNamespace(
        season=2023, week=1, slate_id="2023-w01", players=players,
        player_draws=draws,
    )

    def fake_load(*_args: object, **_kwargs: object) -> tuple[object, dict[str, object], dict[str, object]]:
        events.append("common-worlds-reconstructed-once")
        return prepared, {"F": {}}, {"later_source_identity": later}

    monkeypatch.setattr(op.crossed, "_load_task_sources_v1", fake_load)
    monkeypatch.setattr(op.combined, "project_profile_sources_v1", lambda **_kwargs: ("F7", "F8", "F9"))
    hard_slate = {
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "slate_result_sha256": "5" * 64,
        "source_member_identity": hard_member_identity,
    }
    monkeypatch.setattr(
        op,
        "_read_hard_terminal",
        lambda **_kwargs: (
            {"terminal_sha256": "7" * 64, "slate_results": [hard_slate]},
            execution.FIXED_HARD230_TERMINAL_IDENTITY,
        ),
    )
    monkeypatch.setattr(op.combined, "project_hard230_challenger_source_v1", lambda **_kwargs: "hard230")

    def fake_run(**kwargs: object) -> dict[str, object]:
        events.append("science-run")
        assert kwargs["sources"] == ("incumbent", "F7", "F8", "F9", "hard230")
        assert kwargs["player_draws"] is draws
        return {"result_sha256": "9" * 64}

    monkeypatch.setattr(op.combined, "run_combined_population_all_block_v1", fake_run)
    monkeypatch.setattr(
        op.execution,
        "build_task_result_v1",
        lambda **_kwargs: {
            "slate_id": "2023-w01", "task_result_sha256": "b" * 64,
            "union_lineup_count": 100, "book_count": 8, "entry_budget": 80,
        },
    )

    def fake_publish(**kwargs: object) -> dict[str, object]:
        events.append("publish")
        assert kwargs["uri"] == binding["result_uri"]
        return _identity(binding["result_uri"])

    monkeypatch.setattr(op, "_publish_json", fake_publish)
    result = op.execute_task_v1(
        task_manifest_identity=manifest_identity,
        runtime_authority=runtime,
        store=SimpleNamespace(read_exact=lambda _identity_value: b""),
    )

    assert events == [
        "common-worlds-reconstructed-once", "source-member-read",
        "science-run", "publish",
    ]
    assert result["book_count"] == 8
    assert result["uses_realized_outcomes"] is False


def test_isolated_operator_help_import_closure() -> None:
    script = Path(op.__file__).resolve()
    completed = subprocess.run(
        [sys.executable, "-I", str(script), "--help"],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "prepare" in completed.stdout and "task" in completed.stdout


def test_task_environment_is_bound_to_reserved_cloud_run_and_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_identity = _identity("gs://synthetic/output/task-manifest.json")
    manifest = {
        "code_commit": "a" * 40,
        "image_digest": f"sha256:{'b' * 64}",
        "reused_job_name": op.execution.FIXED_REUSED_JOB_NAME,
        "reused_job_uid": op.execution.FIXED_REUSED_JOB_UID,
        "immutable_image_uri": f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test@sha256:{'b' * 64}",
        "terminal_build_receipt_identity": _identity("gs://synthetic/build.json"),
        "terminal_build_receipt_sha256": "c" * 64,
        "task_manifest_sha256": "d" * 64,
    }
    monkeypatch.setattr(
        op, "_open_manifest", lambda *_args, **_kwargs: (manifest, manifest_identity)
    )
    monkeypatch.setattr(
        op.execution, "validate_task_manifest_v1", lambda value: value
    )
    environment = {
        "CLOUD_RUN_JOB": op.execution.FIXED_REUSED_JOB_NAME, "CLOUD_RUN_EXECUTION": "execution-1",
        "CLOUD_RUN_TASK_INDEX": "7", "CLOUD_RUN_TASK_COUNT": "54",
        "CLOUD_RUN_TASK_ATTEMPT": "0", "GOOGLE_CLOUD_PROJECT": op.execution.FIXED_GCP_PROJECT,
        op.ENABLE_ENV: op.ENABLE_VALUE,
        op.MANIFEST_IDENTITY_ENV: op._canonical(manifest_identity).decode("utf-8"),
        "R6_COMBINED_POPULATION_ALL_BLOCK_IMAGE_DIGEST": f"sha256:{'c' * 64}",
    }
    environment[op.execution.JOB_AUTHORITY_SHA_ENV] = op.execution._hash(
        op.execution.expected_provider_job_observation_v1(
            manifest=manifest, manifest_identity=manifest_identity
        )
    )
    monkeypatch.setattr(
        op, "GCloudRunProviderV1",
        lambda: pytest.fail("task runtime must not invoke Cloud SDK/gcloud"),
    )
    authority = op._runtime_authority_from_environment(
        manifest_identity=manifest_identity, store=object(),
        environment=environment, observed_command=list(op.execution.DISPATCHER_COMMAND),
        observed_project_id=op.execution.FIXED_GCP_PROJECT,
    )
    assert authority["task_index"] == 7
    assert authority["job_name"] == manifest["reused_job_name"]

    environment["CLOUD_RUN_JOB"] = "forged-job"
    with pytest.raises(
        op.RunCorpusR6CombinedPopulationAllBlockV1Error,
        match="reserved Cloud Run runtime",
    ):
        op._runtime_authority_from_environment(
            manifest_identity=manifest_identity, store=object(),
            environment=environment, observed_command=list(op.execution.DISPATCHER_COMMAND),
            observed_project_id=op.execution.FIXED_GCP_PROJECT,
        )


def test_task_cli_rejects_request_index_bypass() -> None:
    with pytest.raises(SystemExit):
        op.main(["task", "--request", "/tmp/forged.json"])


def test_configure_refuses_new_or_substituted_job_uid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity("gs://synthetic/output/task-manifest.json")
    monkeypatch.setattr(op, "_open_manifest", lambda *_args, **_kwargs: ({}, identity))
    provider = SimpleNamespace(
        describe_job_identity=lambda _name: {"job_uid": "different-uid"},
        update_existing_job=lambda _desired: pytest.fail("must not update"),
    )
    with pytest.raises(
        op.RunCorpusR6CombinedPopulationAllBlockV1Error,
        match="refuses a different or new",
    ):
        op.configure_existing_job_v1(
            task_manifest_identity=identity, store=object(), provider=provider
        )


def test_configure_transitions_legacy_job_by_identity_then_strict_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity("gs://synthetic/output/task-manifest.json")
    manifest = {"manifest": True}
    desired = {"reused_job_name": op.execution.FIXED_REUSED_JOB_NAME}
    strict = {"strict": True}
    events: list[str] = []
    monkeypatch.setattr(op, "_open_manifest", lambda *_args, **_kwargs: (manifest, identity))
    monkeypatch.setattr(op.execution, "build_job_configuration_v1", lambda **_kwargs: desired)
    monkeypatch.setattr(
        op.execution, "validate_provider_job_observation_v1",
        lambda value, **_kwargs: events.append("strict-post-update") or value,
    )
    provider = SimpleNamespace(
        describe_job_identity=lambda _name: events.append("legacy-metadata-only") or {
            "job_name": op.execution.FIXED_REUSED_JOB_NAME,
            "job_uid": op.execution.FIXED_REUSED_JOB_UID,
        },
        update_existing_job=lambda value: events.append("updated") if value is desired else None,
        describe_job=lambda _name: events.append("full-post-update-describe") or strict,
    )
    result = op.configure_existing_job_v1(
        task_manifest_identity=identity, store=object(), provider=provider
    )
    assert events == [
        "legacy-metadata-only", "updated", "full-post-update-describe",
        "strict-post-update",
    ]
    assert result["job_observation"] is strict


def test_provider_build_attestation_rejects_fabricated_success_receipt() -> None:
    receipt = {
        "build_id": "build-1", "source_commit": "a" * 40,
        "image_tag": "us-central1-docker.pkg.dev/p/r/i:tag",
        "image_digest": f"sha256:{'b' * 64}",
    }
    provider_build = {
        "id": "build-1", "status": "SUCCESS",
        "substitutions": {"_SOURCE_COMMIT": "a" * 40},
        "source": {"repoSource": {
            "commitSha": "a" * 40, "repoName": "github_erich_nfl-predictions"
        }},
        "sourceProvenance": {"resolvedRepoSource": {
            "commitSha": "a" * 40, "repoName": "github_erich_nfl-predictions"
        }},
        "results": {"images": [{
            "name": receipt["image_tag"], "digest": receipt["image_digest"]
        }]},
    }
    op._validate_provider_build_attestation_v1(
        receipt=receipt, provider_build=provider_build
    )
    fabricated = dict(receipt)
    fabricated["source_commit"] = "c" * 40
    with pytest.raises(op.RunCorpusR6CombinedPopulationAllBlockV1Error):
        op._validate_provider_build_attestation_v1(
            receipt=fabricated, provider_build=provider_build
        )
    substitution_only = dict(provider_build)
    substitution_only["sourceProvenance"] = {}
    with pytest.raises(op.RunCorpusR6CombinedPopulationAllBlockV1Error):
        op._validate_provider_build_attestation_v1(
            receipt=receipt, provider_build=substitution_only
        )


def test_provider_build_attestation_accepts_exact_resolved_git_source_only() -> None:
    repository = "https://github.com/espechtsoftware/nfl-predictions.git"
    receipt = {
        "build_id": "build-2", "source_commit": "a" * 40,
        "image_tag": "us-central1-docker.pkg.dev/p/r/i:tag",
        "image_digest": f"sha256:{'b' * 64}",
    }
    provider_build = {
        "id": "build-2", "status": "SUCCESS",
        "substitutions": {"_SOURCE_COMMIT": "a" * 40},
        "source": {"gitSource": {
            "revision": "a" * 40, "url": repository,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "revision": "a" * 40, "url": repository,
        }},
        "results": {"images": [{
            "name": receipt["image_tag"], "digest": receipt["image_digest"],
        }]},
    }
    op._validate_provider_build_attestation_v1(
        receipt=receipt, provider_build=provider_build
    )

    for source_key, value in (
        ("revision", "c" * 40),
        ("url", "https://github.com/example/different.git"),
    ):
        mismatched = {
            **provider_build,
            "source": {"gitSource": {
                **provider_build["source"]["gitSource"], source_key: value,
            }},
        }
        with pytest.raises(op.RunCorpusR6CombinedPopulationAllBlockV1Error):
            op._validate_provider_build_attestation_v1(
                receipt=receipt, provider_build=mismatched
            )

    ambiguous = {
        **provider_build,
        "source": {
            **provider_build["source"],
            "repoSource": {
                "commitSha": "a" * 40, "repoName": "unexpected-second-source",
            },
        },
        "sourceProvenance": {
            **provider_build["sourceProvenance"],
            "resolvedRepoSource": {
                "commitSha": "a" * 40, "repoName": "unexpected-second-source",
            },
        },
    }
    with pytest.raises(op.RunCorpusR6CombinedPopulationAllBlockV1Error):
        op._validate_provider_build_attestation_v1(
            receipt=receipt, provider_build=ambiguous
        )

    conflicting_substitution = {
        **provider_build,
        "substitutions": {"_SOURCE_COMMIT": "c" * 40},
    }
    with pytest.raises(op.RunCorpusR6CombinedPopulationAllBlockV1Error):
        op._validate_provider_build_attestation_v1(
            receipt=receipt, provider_build=conflicting_substitution
        )


def test_execution_parser_uses_provider_job_uid_and_task_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = op.GCloudRunProviderV1()
    image = f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/test@sha256:{'b' * 64}"
    environment = {"CODE_SHA": "a" * 40}
    job = {
        "job_name": op.execution.FIXED_REUSED_JOB_NAME,
        "job_uid": op.execution.FIXED_REUSED_JOB_UID,
        "project_id": op.execution.FIXED_GCP_PROJECT,
        "region": op.execution.FIXED_REGION,
        "image_digest": f"sha256:{'b' * 64}", "immutable_image_uri": image,
        "source_commit": "a" * 40, "container_command": ["python"],
        "container_args": ["task"], "container_environment": environment,
        "task_count": 54, "parallelism": 54, "max_retries": 0,
        "timeout_seconds": 21600, "cpu": "8", "memory": "32Gi",
        "working_directory": "", "volumes": [], "volume_mounts": [],
        "provider_observed": True,
    }
    authority = op._hash(job)
    raw = {
        "metadata": {
            "name": "execution-1",
            "labels": {"run.googleapis.com/job": job["job_name"]},
            "ownerReferences": [{"name": job["job_name"], "uid": job["job_uid"]}],
        },
        "spec": {
            "taskCount": 54, "parallelism": 54,
            "template": {"spec": {
                "maxRetries": 0, "timeoutSeconds": "21600s", "volumes": [],
                "containers": [{
                    "image": image, "command": ["python"], "args": ["task"],
                    "env": [
                        {"name": "CODE_SHA", "value": "a" * 40},
                        {"name": op.execution.JOB_AUTHORITY_SHA_ENV, "value": authority},
                    ],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                    "volumeMounts": [],
                }],
            }},
        },
        "status": {"succeededCount": 54, "completionTime": "now"},
    }
    monkeypatch.setattr(provider, "_json", lambda _argv: raw)
    monkeypatch.setattr(provider, "describe_job", lambda _name: job)
    parsed = provider.describe_execution("execution-1")
    assert parsed["job_uid"] == op.execution.FIXED_REUSED_JOB_UID
    raw["metadata"]["ownerReferences"][0]["uid"] = "forged"
    with pytest.raises(op.RunCorpusR6CombinedPopulationAllBlockV1Error):
        provider.describe_execution("execution-1")


def test_collect_publishes_only_after_all_results_validate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    manifest_identity = _identity("gs://synthetic/output/task-manifest.json")
    manifest = {"terminal_uri": "gs://synthetic/output/full-54/terminal.json"}
    monkeypatch.setattr(op, "_open_manifest", lambda *_args, **_kwargs: (manifest, manifest_identity))
    monkeypatch.setattr(
        op, "status_existing_execution_v1",
        lambda **_kwargs: events.append("provider-54-of-54-terminal") or {"execution_id": "execution-1"},
    )
    monkeypatch.setattr(
        op,
        "_open_known_task_results",
        lambda **_kwargs: events.append("all-54-results-opened") or [(object(), object())] * 54,
    )

    def fake_build(**_kwargs: object) -> dict[str, object]:
        events.append("all-54-results-normalized")
        return {"terminal_uri": manifest["terminal_uri"], "terminal_sha256": "c" * 64}

    monkeypatch.setattr(op.execution, "build_terminal_v1", fake_build)
    monkeypatch.setattr(
        op,
        "_publish_json",
        lambda **kwargs: events.append("terminal-published") or _identity(kwargs["uri"]),
    )
    result = op.collect_from_request_v1(
        {"task_manifest_identity": manifest_identity, "execution_id": "execution-1"},
        store=object(), provider=object(),
    )
    assert events == [
        "provider-54-of-54-terminal", "all-54-results-opened",
        "all-54-results-normalized", "terminal-published"
    ]
    assert result["generic_normalized_terminal_validated_before_terminal"] is True


def test_grade_replays_terminal_before_first_outcome_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    terminal_identity = _identity("gs://synthetic/output/full-54/terminal.json")
    outcome_identity = _identity("gs://synthetic/outcomes")
    later = _identity("gs://synthetic/later")
    normalized = tuple(
        {"source_ordinal": i, "slate_id": f"2023-w{i + 1:02d}"}
        for i in range(54)
    )

    def fake_reopen(*_args: object, **_kwargs: object) -> tuple[object, ...]:
        events.append("score-free-terminal-replayed")
        return (
            {
                "terminal_sha256": "d" * 64, "later_source_identity": later,
                "output_prefix": (
                    "gs://nfl-predictions-503414-corpus-retrieval/research/"
                    "corpus-r6-combined-population-all-block/test-v1/"
                ),
            },
            terminal_identity,
            {},
            normalized,
        )

    monkeypatch.setattr(op, "_reopen_terminal", fake_reopen)

    def fake_outcome(**_kwargs: object) -> tuple[object, ...]:
        events.append("outcome-opened")
        return (
            {"later_source_freeze_identity": later, "outcome_snapshot_sha256": "e" * 64},
            outcome_identity,
            {},
            {i: (2023, i + 1, f"2023-w{i + 1:02d}") for i in range(54)},
        )

    monkeypatch.setattr(op.grader, "open_outcome_snapshot_surface_v1", fake_outcome)
    monkeypatch.setattr(op.grader, "score_normalized_slates_v1", lambda **_kwargs: [])
    monkeypatch.setattr(op.grader, "aggregate_normalized_slate_grades_v1", lambda _rows: [])
    monkeypatch.setattr(
        op,
        "_publish_json",
        lambda **kwargs: events.append("grade-published") or _identity(kwargs["uri"]),
    )
    result = op.grade_from_request_v1(
        {"terminal_identity": terminal_identity, "outcome_snapshot_identity": outcome_identity},
        store=SimpleNamespace(read_exact=lambda _identity_value: b""),
    )
    assert events == [
        "score-free-terminal-replayed", "outcome-opened", "grade-published"
    ]
    assert result["historical_finalist_confirmation"] is True
