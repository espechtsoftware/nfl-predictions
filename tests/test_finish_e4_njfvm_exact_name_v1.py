from __future__ import annotations

import base64
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/finish_e4_njfvm_exact_name_v1.py"
SPEC = importlib.util.spec_from_file_location("e4_njfvm_continuation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
subject = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = subject
SPEC.loader.exec_module(subject)

FROZEN_PATH = ROOT / "scripts/finish_corpus_r6_broad_admission_tournament_v1.py"
FROZEN_SPEC = importlib.util.spec_from_file_location("e4_njfvm_test_frozen", FROZEN_PATH)
assert FROZEN_SPEC is not None and FROZEN_SPEC.loader is not None
frozen = importlib.util.module_from_spec(FROZEN_SPEC)
sys.modules[FROZEN_SPEC.name] = frozen
FROZEN_SPEC.loader.exec_module(frozen)


GRADE_REOPEN_NAME = f"{subject.JOB}-gr001"
GRADE_REOPEN_UID = "30000000-0000-4000-8000-000000000001"


def _identity(name: str, generation: int) -> dict[str, object]:
    return {
        "uri": f"gs://nfl-predictions-503414-corpus-retrieval/test/{name}.json",
        "generation": str(generation),
        "sha256": f"{generation % 16:x}" * 64,
        "bytes": 100 + generation,
    }


def _env(request: dict[str, object], phase: str) -> list[dict[str, str]]:
    request_bytes = subject.canonical_bytes(request)
    bound = request[
        "terminal_identity" if phase == "grade" else "grade_terminal_identity"
    ]
    values = {
        "CODE_SHA": subject.CODE_SHA,
        "IMAGE_DIGEST": subject.IMAGE_DIGEST,
        "BUILD_ID": subject.BUILD_ID,
        "IMAGE_URI": subject.IMAGE,
        "R6_BROAD_ADMISSION_ENABLE": (
            "I_UNDERSTAND_FIXED_CORPUS_ADMISSION_TOURNAMENT_V1"
        ),
        "R6_BROAD_ADMISSION_REQUEST_SHA256": sha256(request_bytes).hexdigest(),
        "R6_BROAD_ADMISSION_REQUEST_B64": base64.b64encode(request_bytes).decode(),
        "R6_BROAD_ADMISSION_BOUND_IDENTITY": json.dumps(
            bound, sort_keys=True, separators=(",", ":")
        ),
        "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED": (
            "true" if phase == "grade" else "false"
        ),
        "R6_BROAD_ADMISSION_TASK0_SMOKE": "false",
    }
    if phase == "grade":
        values["R6_BROAD_ADMISSION_TIMEOUT_RECOVERY_FROM"] = (
            subject.FAILED_EXECUTION
        )
    return [{"name": key, "value": value} for key, value in values.items()]


def _provider(
    *,
    phase: str,
    name: str,
    uid: str,
    request: dict[str, object],
    completed: str,
    generation: str = "50",
) -> dict[str, object]:
    terminal = completed == "True"
    return {
        "metadata": {
            "name": name,
            "uid": uid,
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": subject.JOB,
                "run.googleapis.com/jobUid": subject.JOB_UID,
                "run.googleapis.com/jobGeneration": generation,
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 54,
            "template": {
                "spec": {
                    "maxRetries": 0,
                    "timeoutSeconds": "43200" if phase == "grade" else "21600",
                    "serviceAccountName": subject.SERVICE_ACCOUNT,
                    "containers": [
                        {
                            "image": subject.IMAGE,
                            "command": ["/bin/bash"],
                            "args": [
                                "/app/scripts/"
                                "cloud_corpus_r6_broad_admission_tournament_v1.sh",
                                "container-run",
                                phase,
                            ],
                            "resources": {
                                "limits": {"cpu": "8", "memory": "32Gi"}
                            },
                            "env": _env(request, phase),
                        }
                    ],
                }
            },
        },
        "status": {
            "conditions": [{"type": "Completed", "status": completed}],
            **({"completionTime": "2026-09-01T18:00:00Z"} if terminal else {}),
            "runningCount": 0 if terminal else 1,
            "succeededCount": 1 if terminal else 0,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
        },
    }


def _grade_body(grade_terminal: dict[str, object]) -> dict[str, object]:
    digest = "a" * 64
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


def _grade_reopen_body(grade_terminal: dict[str, object]) -> dict[str, object]:
    digest = "b" * 64
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


def _result(
    *,
    phase: str,
    name: str,
    uid: str,
    grade_terminal: dict[str, object],
) -> dict[str, object]:
    body = (
        _grade_body(grade_terminal)
        if phase == "grade"
        else _grade_reopen_body(grade_terminal)
    )
    return {
        "schema_version": "corpus-r6-broad-admission-cloud-result/v1",
        "phase": phase,
        "code_sha": subject.CODE_SHA,
        "cloud_build_id": subject.BUILD_ID,
        "provider_resolved_image": subject.IMAGE,
        "execution": {
            "name": name,
            "uid": uid,
            "task_count": 1,
            "succeeded_count": 1,
            "failed_count": 0,
            "cancelled_count": 0,
            "completion_time": "2026-09-01T18:00:00Z",
        },
        "operator_receipt": {
            "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
            "command": phase,
            "task0_nonpublishing_smoke": False,
            "uses_realized_outcomes": True,
            "result": body,
            "complete": True,
        },
        "exact_execution_stdout_only": True,
        "complete": True,
    }


def _launch(request: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "corpus-r6-broad-admission-cloud-launch/v1",
        "phase": "grade-reopen",
        "code_sha": subject.CODE_SHA,
        "cloud_build_id": subject.BUILD_ID,
        "provider_resolved_image": subject.IMAGE,
        "image_digest": subject.IMAGE_DIGEST,
        "reused_job": {
            "name": subject.JOB,
            "uid": subject.JOB_UID,
            "generation": 50,
        },
        "execution": {
            "name": GRADE_REOPEN_NAME,
            "uid": GRADE_REOPEN_UID,
            "task_count": 1,
        },
        "bound_input_authority_identity": request["grade_terminal_identity"],
        "source_task_execution": None,
        "task0_gate_result": None,
        "request_sha256": subject.canonical_sha256(request),
        "outcomes_allowed": False,
        "task0_nonpublishing_smoke": False,
        "execution_provider_reopened": True,
        "complete": True,
    }


class FakeRunner:
    def __init__(
        self,
        paths: subject.ContinuationPaths,
        *,
        recovery_states: list[str] | None = None,
        recovery_uid: str = subject.RECOVERY_UID,
        launch_returncode: int = 0,
    ) -> None:
        self.paths = paths
        self.recovery_states = list(recovery_states or ["Unknown", "True"])
        self.recovery_uid = recovery_uid
        self.launch_returncode = launch_returncode
        self.calls: list[list[str]] = []
        self.grade_terminal = _identity("grade-terminal", 9)
        self.reopen_request: dict[str, object] | None = None

    def run(self, argv, *, cwd=None):
        args = list(argv)
        self.calls.append(args)
        if args[:5] == ["gcloud", "run", "jobs", "executions", "describe"]:
            name = args[5]
            assert args == [
                "gcloud",
                "run",
                "jobs",
                "executions",
                "describe",
                name,
                "--project",
                subject.PROJECT,
                "--region",
                subject.REGION,
                "--format=json",
            ]
            if name == subject.RECOVERY_EXECUTION:
                state = self.recovery_states.pop(0)
                value = _provider(
                    phase="grade",
                    name=name,
                    uid=self.recovery_uid,
                    request=dict(subject.GRADE_REQUEST),
                    completed=state,
                )
            else:
                assert name == GRADE_REOPEN_NAME
                assert self.reopen_request is not None
                value = _provider(
                    phase="grade-reopen",
                    name=name,
                    uid=GRADE_REOPEN_UID,
                    request=self.reopen_request,
                    completed="True",
                )
            return subject.CommandResult(0, subject.canonical_bytes(value))
        if args[0] == str(self.paths.host_launcher):
            assert args[1:] == [
                "result",
                subject.IMAGE,
                subject.CODE_SHA,
                subject.BUILD_ID,
                subject.RECOVERY_EXECUTION,
            ]
            value = _result(
                phase="grade",
                name=subject.RECOVERY_EXECUTION,
                uid=subject.RECOVERY_UID,
                grade_terminal=self.grade_terminal,
            )
            return subject.CommandResult(0, subject.canonical_bytes(value))
        assert args[0] == str(self.paths.exact_launcher)
        if args[1] == "grade-reopen":
            self.reopen_request = json.loads(Path(args[-1]).read_bytes())
            if self.launch_returncode:
                return subject.CommandResult(self.launch_returncode)
            return subject.CommandResult(
                0, subject.canonical_bytes(_launch(self.reopen_request))
            )
        assert args[1:] == [
            "result",
            subject.IMAGE,
            subject.CODE_SHA,
            subject.BUILD_ID,
            GRADE_REOPEN_NAME,
        ]
        value = _result(
            phase="grade-reopen",
            name=GRADE_REOPEN_NAME,
            uid=GRADE_REOPEN_UID,
            grade_terminal=self.grade_terminal,
        )
        return subject.CommandResult(0, subject.canonical_bytes(value))


def _paths(tmp_path: Path) -> subject.ContinuationPaths:
    root = tmp_path / "repo"
    host = root / "scripts/cloud.sh"
    exact_root = root / ".build-contexts/exact/source"
    exact = exact_root / "scripts/cloud.sh"
    host.parent.mkdir(parents=True)
    exact.parent.mkdir(parents=True)
    host.write_text("host\n")
    exact.write_text("exact\n")
    return subject.ContinuationPaths(
        root=root,
        host_launcher=host,
        exact_root=exact_root,
        exact_launcher=exact,
        run_dir=root / ".tmp/e4-test",
    )


def _continuation(
    paths: subject.ContinuationPaths,
    runner: FakeRunner,
    *,
    max_polls: int = 5,
) -> subject.E4ExactNameContinuation:
    return subject.E4ExactNameContinuation(
        paths=paths,
        frozen=frozen,
        runner=runner,
        poll_interval_seconds=1,
        max_polls=max_polls,
        sleeper=lambda _: None,
    )


def test_default_invocation_is_inert() -> None:
    with pytest.raises(subject.E4ContinuationError, match="default-off"):
        subject.main([])


def test_exact_name_chain_reaches_grade_reopen_without_listing_or_recovery_launch(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    runner = FakeRunner(paths)
    result = _continuation(paths, runner).finish()

    assert result["recovery_execution"] == {
        "name": subject.RECOVERY_EXECUTION,
        "uid": subject.RECOVERY_UID,
    }
    assert result["grade_reopen_execution"] == {
        "name": GRADE_REOPEN_NAME,
        "uid": GRADE_REOPEN_UID,
    }
    assert result["new_grade_recovery_launched"] is False
    assert result["execution_listing_used"] is False
    assert result["complete"] is True
    flattened = [part for call in runner.calls for part in call]
    assert "list" not in flattened
    assert "grade-timeout-recovery" not in flattened
    recovery_describes = [
        call
        for call in runner.calls
        if call[:5] == ["gcloud", "run", "jobs", "executions", "describe"]
        and call[5] == subject.RECOVERY_EXECUTION
    ]
    assert len(recovery_describes) == 2


def test_recovery_uid_mismatch_stops_before_result_or_launch(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    runner = FakeRunner(paths, recovery_uid="40000000-0000-4000-8000-000000000001")
    with pytest.raises(subject.E4ContinuationError, match="provider envelope"):
        _continuation(paths, runner).finish()
    assert len(runner.calls) == 1


def test_nonterminal_poll_exhaustion_does_not_collect_or_launch(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    runner = FakeRunner(paths, recovery_states=["Unknown"])
    with pytest.raises(subject.E4ContinuationError, match="polling exhausted"):
        _continuation(paths, runner, max_polls=1).finish()
    assert len(runner.calls) == 1
    assert runner.calls[0][5] == subject.RECOVERY_EXECUTION


def test_ambiguous_grade_reopen_launch_intent_never_relaunches(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    first = FakeRunner(paths, recovery_states=["True"], launch_returncode=1)
    with pytest.raises(subject.E4ContinuationError, match="provider-ambiguous"):
        _continuation(paths, first).finish()

    second = FakeRunner(paths, recovery_states=["True"])
    with pytest.raises(subject.E4ContinuationError, match="exact name and UID required"):
        _continuation(paths, second).finish()
    assert all(call[1] != "grade-reopen" for call in second.calls if len(call) > 1)


def test_ambiguous_launch_can_resume_only_with_exact_name_and_uid(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    first = FakeRunner(paths, recovery_states=["True"], launch_returncode=1)
    with pytest.raises(subject.E4ContinuationError, match="provider-ambiguous"):
        _continuation(paths, first).finish()

    resumed = FakeRunner(paths, recovery_states=["True"])
    resumed.grade_terminal = first.grade_terminal
    resumed.reopen_request = {"grade_terminal_identity": first.grade_terminal}
    continuation = subject.E4ExactNameContinuation(
        paths=paths,
        frozen=frozen,
        runner=resumed,
        poll_interval_seconds=1,
        max_polls=5,
        sleeper=lambda _: None,
        resume_execution=GRADE_REOPEN_NAME,
        resume_uid=GRADE_REOPEN_UID,
    )
    result = continuation.finish()
    assert result["complete"] is True
    assert all(call[1] != "grade-reopen" for call in resumed.calls if len(call) > 1)
    assert [call[5] for call in resumed.calls if call[0] == "gcloud"] == [
        GRADE_REOPEN_NAME,
        GRADE_REOPEN_NAME,
    ]


def _stat(pid: int, parent: int, ticks: int) -> str:
    suffix = ["S", str(parent), *("0" for _ in range(17)), str(ticks)]
    return f"{pid} (fixture) " + " ".join(suffix) + "\n"


def test_launcher_registry_attestation_binds_lane_owner_process_and_prefixes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    script = root / "scripts/finisher.py"
    script.parent.mkdir(parents=True)
    script.write_text("pass\n")
    receipt = root / ".tmp/launchers/finisher-100.json"
    receipt.parent.mkdir(parents=True)
    value = {
        "schema_version": "shared-launcher-registry/v1",
        "script_path": str(script.resolve()),
        "pid": 100,
        "process_start_ticks": 900,
        "owner": "production",
        "lane": subject.JOB,
        "target_run_id_prefixes": subject.TARGET_PREFIXES,
        "acquired_at_utc": "2026-09-01T17:00:00Z",
    }
    receipt.write_bytes(subject.canonical_bytes(value))
    lock = root / ".tmp/launcher-locks" / (
        sha256(subject.JOB.encode()).hexdigest() + ".lock"
    )
    lock.parent.mkdir(parents=True)
    lock.touch()
    proc = tmp_path / "proc"
    (proc / "100").mkdir(parents=True)
    (proc / "200").mkdir(parents=True)
    (proc / "100/stat").write_text(_stat(100, 1, 900))
    (proc / "200/stat").write_text(_stat(200, 100, 901))
    environment = {
        "NFL_LAUNCHER_REGISTRY_RECEIPT": str(receipt),
        "NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256": sha256(receipt.read_bytes()).hexdigest(),
        "NFL_LAUNCHER_REGISTRY_LANE": subject.JOB,
        "NFL_LAUNCHER_REGISTRY_WRAPPER_PID": "100",
        "NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS": "900",
    }
    subject.verify_launcher_registry_lane(
        root=root,
        script_path=script,
        environment=environment,
        proc_root=proc,
        current_pid=200,
        lock_probe=lambda _: True,
    )

    value["target_run_id_prefixes"] = [subject.RECOVERY_EXECUTION]
    receipt.write_bytes(subject.canonical_bytes(value))
    environment["NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256"] = sha256(
        receipt.read_bytes()
    ).hexdigest()
    with pytest.raises(subject.E4ContinuationError, match="receipt authority"):
        subject.verify_launcher_registry_lane(
            root=root,
            script_path=script,
            environment=environment,
            proc_root=proc,
            current_pid=200,
            lock_probe=lambda _: True,
        )
