from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finish_corpus_r6_broad_admission_tournament_v1.py"
SPEC = importlib.util.spec_from_file_location("broad_admission_finisher", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
finisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finisher)


def _identity(name: str, generation: int) -> dict[str, object]:
    return {
        "uri": f"gs://nfl-predictions-503414-corpus-retrieval/test/{name}.json",
        "generation": str(generation),
        "sha256": f"{generation % 16:x}" * 64,
        "bytes": 100 + generation,
    }


def _build() -> dict[str, object]:
    code_sha = "1" * 40
    digest = "sha256:" + "2" * 64
    root = "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
    return {
        "schema_version": "corpus-r6-broad-admission-cloud-build/v1",
        "code_sha": code_sha,
        "cloud_build_id": "12345678-1234-4234-8234-123456789abc",
        "build_image_tag": f"{root}:broad-admission-{code_sha}",
        "provider_resolved_image": f"{root}@{digest}",
        "image_digest": digest,
        "source_repository": "https://github.com/espechtsoftware/nfl-predictions.git",
        "runtime_build_attestation_identity": _identity("build-attestation", 1),
        "provider_requested_and_resolved_git_source_exact": True,
        "outcome_artifacts_read_by_build_steps": False,
        "outcome_artifacts_in_runtime_image_context": False,
        "complete": True,
    }


def _install(build: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "corpus-r6-broad-admission-cloud-install/v1",
        "code_sha": build["code_sha"],
        "cloud_build_id": build["cloud_build_id"],
        "provider_resolved_image": build["provider_resolved_image"],
        "image_digest": build["image_digest"],
        "reused_job": {
            "name": finisher.JOB,
            "uid": finisher.JOB_UID,
            "generation": 99,
        },
        "prior_terminal_execution": "atlas-cbc-32g-full-2023-w8-v1-old01",
        "install_only": True,
        "execution_launched": False,
        "outcomes_allowed": False,
        "complete": True,
    }


NAMES = {
    "prepare": f"{finisher.JOB}-p0001",
    "task0": f"{finisher.JOB}-t0000",
    "task": f"{finisher.JOB}-t0054",
    "collect": f"{finisher.JOB}-c0001",
    "reopen": f"{finisher.JOB}-r0001",
    "grade": f"{finisher.JOB}-g0001",
    "grade-reopen": f"{finisher.JOB}-x0001",
}
UIDS = {
    phase: f"00000000-0000-4000-8000-{index:012x}"
    for index, phase in enumerate(NAMES, start=1)
}


def _body(phase: str, build: dict[str, object]) -> dict[str, object]:
    manifest = _identity("manifest", 2)
    terminal = _identity("terminal", 3)
    grade_terminal = _identity("grade-terminal", 4)
    digest = "a" * 64
    if phase == "prepare":
        return {
            "schema_version": "corpus-r6-broad-admission-prepare-result/v1",
            "manifest_identity": manifest,
            "manifest_sha256": digest,
            "task_count": 54,
            "build_id": build["cloud_build_id"],
            "all_nonpublication_authorities_validated_before_first_write": True,
            "uses_realized_outcomes": False,
            "execution_launched": False,
            "deployment_mutation_performed": False,
            "complete": True,
            "prepare_result_sha256": digest,
        }
    if phase == "task0":
        return {
            "schema_version": "corpus-r6-broad-admission-task0-smoke/v1",
            "manifest_identity": manifest,
            "source_ordinal": 0,
            "slate_id": "2023-w01",
            "package_sha256": digest,
            "union_lineups_sha256": digest,
            "task_result_sha256": digest,
            "publication_performed": False,
            "uses_realized_outcomes": False,
            "complete": True,
            "smoke_result_sha256": digest,
        }
    if phase == "collect":
        return {
            "schema_version": "corpus-r6-broad-admission-collect-result/v1",
            "terminal_identity": terminal,
            "terminal_sha256": digest,
            "task_count": 54,
            "root_published_last": True,
            "uses_realized_outcomes": False,
            "complete": True,
            "collect_result_sha256": digest,
        }
    if phase == "reopen":
        return {
            "schema_version": "corpus-r6-broad-admission-reopen-result/v1",
            "terminal_identity": terminal,
            "task_count": 54,
            "package_lattice_sha256": digest,
            "all_tasks_and_parents_generation_exact_reopened": True,
            "all_packages_independently_recomputed": True,
            "catalog_reread": False,
            "outcome_reread": False,
            "uses_realized_outcomes": False,
            "complete": True,
            "reopen_result_sha256": digest,
        }
    if phase == "grade":
        return {
            "schema_version": "corpus-r6-broad-admission-grade-result/v1",
            "grade_terminal_identity": grade_terminal,
            "grade_terminal_sha256": digest,
            "program_grade_sha256": digest,
            "grade_root_published_last": True,
            "descriptive_only": True,
            "complete": True,
            "grade_result_sha256": digest,
        }
    return {
        "schema_version": "corpus-r6-broad-admission-grade-reopen-result/v1",
        "grade_terminal_identity": grade_terminal,
        "program_grade_sha256": digest,
        "score_free_lattice_and_parents_replayed": True,
        "persisted_derived_scores_replayed": True,
        "program_grade_independently_recomputed": True,
        "catalog_reread": False,
        "outcome_snapshot_reread": False,
        "historical_outcome_lease_reread": False,
        "uses_realized_outcomes": True,
        "complete": True,
        "grade_reopen_result_sha256": digest,
    }


def _result(phase: str, build: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "corpus-r6-broad-admission-cloud-result/v1",
        "phase": phase,
        "code_sha": build["code_sha"],
        "cloud_build_id": build["cloud_build_id"],
        "provider_resolved_image": build["provider_resolved_image"],
        "execution": {
            "name": NAMES[phase],
            "uid": UIDS[phase],
            "task_count": 1,
            "succeeded_count": 1,
            "failed_count": 0,
            "cancelled_count": 0,
            "completion_time": (
                "2026-09-01T00:00:10Z"
                if phase == "task0"
                else "2026-09-01T01:00:00Z"
            ),
        },
        "operator_receipt": {
            "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
            "command": "task" if phase == "task0" else phase,
            "task0_nonpublishing_smoke": phase == "task0",
            "uses_realized_outcomes": phase in {"grade", "grade-reopen"},
            "result": _body(phase, build),
            "complete": True,
        },
        "exact_execution_stdout_only": True,
        "complete": True,
    }


class FakeRunner:
    def __init__(self, build: dict[str, object]):
        self.build = build
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.results = {
            phase: _result(phase, build) for phase in finisher.ONE_TASK_PHASES
        }

    def run(self, argv, *, cwd=None, env=None):
        args = list(argv)
        self.calls.append((args, dict(env or {})))
        if args[0] == "gcloud":
            assert args[:5] == ["gcloud", "run", "jobs", "executions", "describe"]
            name = args[5]
            phase = next(key for key, value in NAMES.items() if value == name)
            task_count = 54 if phase == "task" else 1
            created = (
                "2026-09-01T00:00:20Z"
                if phase == "task"
                else "2026-09-01T00:00:00Z"
            )
            provider = {
                "metadata": {
                    "name": name,
                    "uid": UIDS[phase],
                    "creationTimestamp": created,
                    "labels": {
                        "run.googleapis.com/job": finisher.JOB,
                        "run.googleapis.com/jobUid": finisher.JOB_UID,
                        "run.googleapis.com/jobGeneration": "99",
                    },
                },
                "spec": {"taskCount": task_count},
                "status": {
                    "conditions": [{"type": "Completed", "status": "True"}],
                    "completionTime": "2026-09-01T02:00:00Z",
                    "succeededCount": task_count,
                    "failedCount": 0,
                    "cancelledCount": 0,
                    "runningCount": 0,
                },
            }
            return finisher.CommandResult(0, json.dumps(provider, indent=2).encode())

        assert args[0] == str(finisher.LAUNCHER)
        action = args[1]
        if action == "install":
            return finisher.CommandResult(0, json.dumps(_install(self.build), indent=2).encode())
        if action == "result":
            name = args[5]
            phase = next(key for key, value in NAMES.items() if value == name)
            return finisher.CommandResult(0, json.dumps(self.results[phase], indent=2).encode())

        phase = action
        request = json.loads(Path(args[5]).read_bytes())
        task_execution = NAMES["task"] if phase == "collect" else None
        launch = {
            "schema_version": "corpus-r6-broad-admission-cloud-launch/v1",
            "phase": phase,
            "code_sha": self.build["code_sha"],
            "cloud_build_id": self.build["cloud_build_id"],
            "provider_resolved_image": self.build["provider_resolved_image"],
            "image_digest": self.build["image_digest"],
            "reused_job": {
                "name": finisher.JOB,
                "uid": finisher.JOB_UID,
                "generation": 99,
            },
            "execution": {
                "name": NAMES[phase],
                "uid": UIDS[phase],
                "task_count": 54 if phase == "task" else 1,
            },
            "bound_input_authority_identity": finisher._phase_bound_identity(
                phase, request
            ),
            "source_task_execution": (
                {"name": NAMES["task"], "uid": UIDS["task"], "task_count": 54}
                if phase == "collect"
                else None
            ),
            "task0_gate_result": self.results["task0"] if phase == "task" else None,
            "request_sha256": finisher._expected_request_sha(
                phase, request, task_execution=task_execution
            ),
            "outcomes_allowed": phase == "grade",
            "task0_nonpublishing_smoke": phase == "task0",
            "execution_provider_reopened": True,
            "complete": True,
        }
        if phase == "collect":
            assert env["R6_BROAD_ADMISSION_TASK_EXECUTION_NAME"] == NAMES["task"]
        return finisher.CommandResult(0, json.dumps(launch, indent=2).encode())


class FailingRunner:
    def __init__(self):
        self.calls = 0

    def run(self, argv, *, cwd=None, env=None):
        self.calls += 1
        return finisher.CommandResult(1, b"", b"ambiguous")


def _make_finisher(tmp_path: Path, monkeypatch, runner, **kwargs):
    state_root = tmp_path / "state"
    state_root.mkdir(exist_ok=True)
    monkeypatch.setattr(finisher, "LOCAL_STATE_ROOT", state_root)
    return finisher.BroadAdmissionFinisher(
        run_dir=state_root / "run",
        build_receipt=_build(),
        output_prefix=finisher.OUTPUT_ROOT + "unit-test-v1/",
        runner=runner,
        already_installed=kwargs.get("already_installed", False),
        resume_executions=kwargs.get("resume_executions", {}),
        poll_interval_seconds=1,
        max_polls=2,
    )


def test_build_receipt_and_prepare_request_pin_exact_parents() -> None:
    build = finisher.validate_build_receipt_v1(_build())
    request = finisher.prepare_request_v1(
        build_receipt=build,
        output_prefix=finisher.OUTPUT_ROOT + "frozen-run-v1/",
    )
    assert request["combined_terminal_identity"] == finisher.FROZEN_COMBINED_TERMINAL_IDENTITY
    assert request["frontier_manifest_identity"] == finisher.FROZEN_FRONTIER_MANIFEST_IDENTITY
    assert request["runtime_build_attestation_identity"] == build[
        "runtime_build_attestation_identity"
    ]
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="output prefix"):
        finisher.prepare_request_v1(build_receipt=build, output_prefix="gs://wrong/run/")
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="output prefix"):
        finisher.prepare_request_v1(
            build_receipt=build, output_prefix=finisher.OUTPUT_ROOT
        )


def test_default_off_fails_before_reading_build_receipt(tmp_path: Path) -> None:
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="default-off"):
        finisher.main(
            [
                "--build-receipt",
                str(tmp_path / "absent.json"),
                "--output-prefix",
                finisher.OUTPUT_ROOT + "default-off/",
            ]
        )


def test_ambiguous_launch_intent_never_relaunches(tmp_path: Path, monkeypatch) -> None:
    runner = FailingRunner()
    worker = _make_finisher(tmp_path, monkeypatch, runner, already_installed=True)
    request = worker.prepare_request
    request_path = worker._request("prepare", request)
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="failed or is ambiguous"):
        worker._launch_or_resume(
            phase="prepare", request=request, request_path=request_path
        )
    assert runner.calls == 1
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="ambiguous launch intent"):
        worker._launch_or_resume(
            phase="prepare", request=request, request_path=request_path
        )
    assert runner.calls == 1


def test_ambiguous_launch_can_resume_only_from_supplied_exact_name(
    tmp_path: Path, monkeypatch
) -> None:
    runner = FailingRunner()
    worker = _make_finisher(tmp_path, monkeypatch, runner, already_installed=True)
    request_path = worker._request("prepare", worker.prepare_request)
    with pytest.raises(finisher.BroadAdmissionFinisherError):
        worker._launch_or_resume(
            phase="prepare", request=worker.prepare_request, request_path=request_path
        )
    recovered = _make_finisher(
        tmp_path,
        monkeypatch,
        runner,
        already_installed=True,
        resume_executions={"prepare": NAMES["prepare"]},
    )
    assert recovered._launch_or_resume(
        phase="prepare",
        request=recovered.prepare_request,
        request_path=request_path,
    ) == NAMES["prepare"]
    assert runner.calls == 1
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="resume execution"):
        _make_finisher(
            tmp_path,
            monkeypatch,
            runner,
            already_installed=True,
            resume_executions={"task": "not-an-execution"},
        )


def test_full_finisher_uses_only_exact_names_and_seals_grade_reopen(
    tmp_path: Path, monkeypatch
) -> None:
    runner = FakeRunner(_build())
    worker = _make_finisher(tmp_path, monkeypatch, runner)
    result = worker.finish()

    assert result["complete"] is True
    assert result["full_task_execution"] == NAMES["task"]
    assert result["manifest_identity"] == _identity("manifest", 2)
    assert result["terminal_identity"] == _identity("terminal", 3)
    assert result["grade_terminal_identity"] == _identity("grade-terminal", 4)
    assert result["phase_execution_names"]["grade-reopen"] == NAMES["grade-reopen"]
    assert (worker.run_dir / "finisher-terminal.json").is_file()

    actions = [
        args[1]
        for args, _ in runner.calls
        if args[0] == str(finisher.LAUNCHER)
    ]
    assert actions == [
        "install",
        "prepare",
        "result",
        "task0",
        "result",
        "task",
        "collect",
        "result",
        "reopen",
        "result",
        "grade",
        "result",
        "grade-reopen",
        "result",
    ]
    for args, _ in runner.calls:
        assert "list" not in args
        if args[0] == "gcloud":
            assert args[:5] == ["gcloud", "run", "jobs", "executions", "describe"]
            assert args[5] in NAMES.values()


def test_full_task_chronology_rejects_pre_gate_execution(
    tmp_path: Path, monkeypatch
) -> None:
    runner = FakeRunner(_build())
    original = runner.run

    def wrong_chronology(argv, *, cwd=None, env=None):
        result = original(argv, cwd=cwd, env=env)
        args = list(argv)
        if args[:5] == ["gcloud", "run", "jobs", "executions", "describe"] and args[5] == NAMES["task"]:
            body = json.loads(result.stdout)
            body["metadata"]["creationTimestamp"] = "2026-09-01T00:00:05Z"
            return finisher.CommandResult(0, json.dumps(body).encode())
        return result

    runner.run = wrong_chronology
    worker = _make_finisher(tmp_path, monkeypatch, runner)
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="strictly after"):
        worker.finish()


def test_grade_reopen_receipt_cannot_claim_catalog_reread() -> None:
    value = _result("grade-reopen", _build())
    value["operator_receipt"]["result"]["catalog_reread"] = True
    with pytest.raises(finisher.BroadAdmissionFinisherError, match="grade independent reopen"):
        finisher.validate_result_receipt_v1(
            value,
            phase="grade-reopen",
            execution_name=NAMES["grade-reopen"],
            build_receipt=_build(),
        )
