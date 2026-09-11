from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/finish_corpus_r6_matchup_source_v3.py"
SPEC = importlib.util.spec_from_file_location("source_v3_finisher", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)

CODE = "1" * 40
BUILD_ID = "12345678-1234-4234-8234-123456789abc"
DIGEST = "sha256:" + "2" * 64
IMAGE_ROOT = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
)
IMAGE = f"{IMAGE_ROOT}@{DIGEST}"
RUN_ID = "20260911-source-v3-driver-test-v1"
OLD_NAME = f"{subject.JOB}-old00"
NEW_NAME = f"{subject.JOB}-new00"
OLD_UID = "00000000-0000-4000-8000-000000000001"
NEW_UID = "00000000-0000-4000-8000-000000000002"


def _raw(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _gnu_gzip_b64(payload: bytes) -> str:
    compressed = subprocess.run(
        ("gzip", "-n", "-9", "-c"),
        input=payload,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout
    return base64.b64encode(compressed).decode("ascii")


def _provider(
    *,
    state: str,
    name: str = NEW_NAME,
    uid: str = NEW_UID,
    phase: str = "worker",
    payload: bytes = b"{}",
    worker: str = "DISABLED",
    verifier: str = "DISABLED",
    publisher: str = "DISABLED",
) -> dict[str, object]:
    env = {
        "BUILD_ID": BUILD_ID,
        "CODE_SHA": CODE,
        "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_DIGEST": DIGEST,
        "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE": IMAGE,
        "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT": CODE,
        subject.PUBLISHER_ENV: publisher,
        subject.VERIFIER_ENV: verifier,
        subject.WORKER_ENV: worker,
        "IMAGE_DIGEST": DIGEST,
        "IMAGE_SOURCE_COMMIT_SHA": CODE,
        "IMAGE_URI": IMAGE,
        subject.MODE_ENV: phase,
        subject.OUTCOMES_ENV: "false",
        subject.PAYLOAD_B64_ENV: _gnu_gzip_b64(payload),
        subject.PAYLOAD_SHA_ENV: sha256(payload).hexdigest(),
        "TASK0_RUN_ID": RUN_ID,
    }
    if state == "True":
        status = {
            "conditions": [{"type": "Completed", "status": "True"}],
            "completionTime": "2026-09-11T17:00:00.123Z",
            "runningCount": 0,
            "succeededCount": 1,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
        }
    elif state == "False":
        status = {
            "conditions": [{"type": "Completed", "status": "False"}],
            "completionTime": "2026-09-11T17:00:00Z",
            "runningCount": 0,
            "succeededCount": 0,
            "failedCount": 1,
            "cancelledCount": 0,
            "retriedCount": 0,
        }
    else:
        status = {
            "conditions": (
                []
                if state == "MISSING"
                else [{"type": "Completed", "status": "Unknown"}]
            ),
            "runningCount": 0 if state == "MISSING" else 1,
            "succeededCount": 0,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
        }
    return {
        "metadata": {
            "name": name,
            "uid": uid,
            "labels": {
                "run.googleapis.com/job": subject.JOB,
                "run.googleapis.com/jobUid": subject.JOB_UID,
                "run.googleapis.com/jobGeneration": "101",
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {
                "spec": {
                    "maxRetries": 0,
                    "timeoutSeconds": "86400",
                    "serviceAccountName": subject.SERVICE_ACCOUNT,
                    "containers": [
                        {
                            "image": IMAGE,
                            "command": ["/bin/bash"],
                            "args": [
                                "/app/scripts/"
                                "cloud_corpus_r6_matchup_source_task0_v3.sh",
                                "container-run",
                                phase,
                            ],
                            "resources": {
                                "limits": {"cpu": "8", "memory": "32Gi"}
                            },
                            "env": [
                                {"name": key, "value": value}
                                for key, value in env.items()
                            ],
                        }
                    ],
                }
            },
        },
        "status": status,
    }


def _prior_terminal() -> dict[str, object]:
    return {
        "metadata": {
            "name": OLD_NAME,
            "uid": OLD_UID,
            "labels": {
                "run.googleapis.com/job": subject.JOB,
                "run.googleapis.com/jobUid": subject.JOB_UID,
            },
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "completionTime": "2026-09-11T16:00:00Z",
            "runningCount": 0,
            "succeededCount": 1,
        },
    }


def _job(latest: str | None) -> dict[str, object]:
    status: dict[str, object] = {}
    if latest is not None:
        status["latestCreatedExecution"] = {"name": latest}
    return {
        "metadata": {"name": subject.JOB, "uid": subject.JOB_UID},
        "status": status,
    }


def _build() -> dict[str, object]:
    tag = f"{IMAGE_ROOT}:matchup-source-v3-{CODE}"
    git_source = {"url": subject.SOURCE_REPOSITORY, "revision": CODE}
    return {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": git_source},
        "sourceProvenance": {"resolvedGitSource": git_source},
        "substitutions": {"_CODE_SHA": CODE, "_BUILD_IMAGE": tag},
        "results": {"images": [{"name": tag, "digest": DIGEST}]},
    }


def _finisher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: object,
    *,
    max_polls: int = 2,
    reconcile_polls: int = 3,
    result_polls: int = 1,
) -> object:
    state_root = tmp_path / "source-v3-state"
    monkeypatch.setattr(subject, "RUN_STATE_ROOT", state_root)
    return subject.SourceV3Finisher(
        run_id=RUN_ID,
        code_sha=CODE,
        build_id=BUILD_ID,
        image=IMAGE,
        run_dir=state_root / RUN_ID,
        runner=runner,
        object_exists=lambda _uri: False,
        provider_receipt_loader=lambda _identity: (_ for _ in ()).throw(
            AssertionError("receipt loader must not run")
        ),
        poll_interval_seconds=1,
        max_polls=max_polls,
        reconcile_polls=reconcile_polls,
        result_polls=result_polls,
        preflight_workers=1,
        sleeper=lambda _seconds: None,
    )


def test_build_provider_requires_requested_and_resolved_direct_git_source() -> None:
    assert subject.validate_build_provider(
        _build(), code_sha=CODE, build_id=BUILD_ID, image=IMAGE
    )["id"] == BUILD_ID
    changed = deepcopy(_build())
    changed["source"] = {"storageSource": {"bucket": "mutable"}}
    with pytest.raises(subject.SourceV3FinisherError):
        subject.validate_build_provider(
            changed, code_sha=CODE, build_id=BUILD_ID, image=IMAGE
        )


@pytest.mark.parametrize("state", ["MISSING", "Unknown", "True", "False"])
def test_provider_validator_classifies_exact_completed_states(state: str) -> None:
    _, observed = subject.validate_provider_execution(
        _provider(state=state),
        phase="worker",
        execution_name=NEW_NAME,
        execution_uid=NEW_UID,
        code_sha=CODE,
        build_id=BUILD_ID,
        image=IMAGE,
        run_id=RUN_ID,
        payload=b"{}",
        worker_execution="DISABLED",
        verifier_execution="DISABLED",
        publisher_execution="DISABLED",
    )
    assert observed == state


def test_provider_validator_tolerates_partial_success_but_rejects_overcount() -> None:
    provider = _provider(state="MISSING")
    provider["status"]["succeededCount"] = 1
    for completion in (None, "2026-09-11T17:00:00Z"):
        if completion is None:
            provider["status"].pop("completionTime", None)
        else:
            provider["status"]["completionTime"] = completion
        _, state = subject.validate_provider_execution(
            provider,
            phase="worker",
            execution_name=NEW_NAME,
            execution_uid=NEW_UID,
            code_sha=CODE,
            build_id=BUILD_ID,
            image=IMAGE,
            run_id=RUN_ID,
            payload=b"{}",
            worker_execution="DISABLED",
            verifier_execution="DISABLED",
            publisher_execution="DISABLED",
        )
        assert state == "MISSING"

    provider["status"]["runningCount"] = 1
    with pytest.raises(subject.SourceV3FinisherError):
        subject.validate_provider_execution(
            provider,
            phase="worker",
            execution_name=NEW_NAME,
            execution_uid=NEW_UID,
            code_sha=CODE,
            build_id=BUILD_ID,
            image=IMAGE,
            run_id=RUN_ID,
            payload=b"{}",
            worker_execution="DISABLED",
            verifier_execution="DISABLED",
            publisher_execution="DISABLED",
        )


class AmbiguousLaunchRunner:
    def __init__(self, run_dir: Path, *, resolves: bool) -> None:
        self.run_dir = run_dir
        self.resolves = resolves
        self.new_state = "MISSING"
        self.launch_count = 0
        self.post_launch_job_reads = 0

    def run(self, argv: object, **_kwargs: object) -> object:
        args = tuple(argv)
        if args[:5] == ("gcloud", "run", "jobs", "executions", "describe"):
            name = args[5]
            value = (
                _prior_terminal()
                if name == OLD_NAME
                else _provider(state=self.new_state)
            )
            return subject.CommandResult(0, _raw(value))
        if args[:4] == ("gcloud", "run", "jobs", "describe"):
            if self.launch_count == 0:
                latest = OLD_NAME
            else:
                self.post_launch_job_reads += 1
                if not self.resolves:
                    latest = OLD_NAME
                elif self.post_launch_job_reads == 1:
                    latest = None
                else:
                    latest = NEW_NAME
            return subject.CommandResult(0, _raw(_job(latest)))
        if args and args[0] == str(subject.LAUNCHER):
            assert (self.run_dir / "phases/worker/launch-intent.json").is_file()
            self.launch_count += 1
            return subject.CommandResult(1, b"", b"network response lost")
        raise AssertionError(f"unexpected command: {args}")


def test_ambiguous_launch_reconciles_latest_once_and_never_relaunches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-v3-state" / RUN_ID
    runner = AmbiguousLaunchRunner(run_dir, resolves=True)
    finisher = _finisher(tmp_path, monkeypatch, runner)
    launch = finisher._launch_or_recover(
        phase="worker",
        prior={},
        payload=b"{}",
        worker="DISABLED",
        verifier="DISABLED",
        publisher="DISABLED",
    )
    assert launch["execution"] == {
        "name": NEW_NAME,
        "uid": NEW_UID,
        "task_count": 1,
    }
    assert launch["provider_attribution_method"] == (
        "provider-latest-after-ambiguous-controller-return"
    )
    assert runner.launch_count == 1

    resumed = finisher._launch_or_recover(
        phase="worker",
        prior={},
        payload=b"{}",
        worker="DISABLED",
        verifier="DISABLED",
        publisher="DISABLED",
    )
    assert resumed == launch
    assert runner.launch_count == 1


def test_consumed_ambiguous_intent_never_relaunches_when_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "source-v3-state" / RUN_ID
    runner = AmbiguousLaunchRunner(run_dir, resolves=False)
    finisher = _finisher(
        tmp_path, monkeypatch, runner, reconcile_polls=1
    )
    for _ in range(2):
        with pytest.raises(subject.SourceV3FinisherError, match="never relaunch"):
            finisher._launch_or_recover(
                phase="worker",
                prior={},
                payload=b"{}",
                worker="DISABLED",
                verifier="DISABLED",
                publisher="DISABLED",
            )
    assert runner.launch_count == 1


def test_post_intent_evidence_without_intent_refuses_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "source-v3-state" / RUN_ID
    runner = AmbiguousLaunchRunner(run_dir, resolves=True)
    finisher = _finisher(tmp_path, monkeypatch, runner)
    attribution = run_dir / "phases/worker/provider-attribution.json"
    subject._publish_once(attribution, _raw(_provider(state="MISSING")))

    with pytest.raises(
        subject.SourceV3FinisherError,
        match="post-intent evidence exists without its launch intent",
    ):
        finisher._launch_or_recover(
            phase="worker",
            prior={},
            payload=b"{}",
            worker="DISABLED",
            verifier="DISABLED",
            publisher="DISABLED",
        )
    assert runner.launch_count == 0


@pytest.mark.parametrize(
    "crash_target",
    ("provider-attribution-receipt.json", "launch.json"),
)
def test_attribution_resume_retains_original_snapshot_across_status_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_target: str,
) -> None:
    run_dir = tmp_path / "source-v3-state" / RUN_ID
    runner = AmbiguousLaunchRunner(run_dir, resolves=True)
    finisher = _finisher(tmp_path, monkeypatch, runner)
    publish_once = subject._publish_once
    crashed = False

    def crash_after_attribution(path: Path, raw: bytes) -> bool:
        nonlocal crashed
        if path.name == crash_target and not crashed:
            crashed = True
            raise RuntimeError("simulated host crash")
        return publish_once(path, raw)

    monkeypatch.setattr(subject, "_publish_once", crash_after_attribution)
    with pytest.raises(RuntimeError, match="simulated host crash"):
        finisher._launch_or_recover(
            phase="worker",
            prior={},
            payload=b"{}",
            worker="DISABLED",
            verifier="DISABLED",
            publisher="DISABLED",
        )

    attribution_path = run_dir / "phases/worker/provider-attribution.json"
    retained_raw = attribution_path.read_bytes()
    retained = json.loads(retained_raw)
    assert retained["status"].get("conditions") == []
    assert not (run_dir / "phases/worker/launch.json").exists()

    monkeypatch.setattr(subject, "_publish_once", publish_once)
    runner.new_state = "True"
    launch = finisher._launch_or_recover(
        phase="worker",
        prior={},
        payload=b"{}",
        worker="DISABLED",
        verifier="DISABLED",
        publisher="DISABLED",
    )

    assert attribution_path.read_bytes() == retained_raw
    assert launch["provider_sha256_at_attribution"] == subject.canonical_sha256(
        retained
    )
    assert launch["provider_attribution_method"] == (
        "provider-latest-after-ambiguous-controller-return"
    )
    assert runner.launch_count == 1


def test_recovery_receipt_resume_revalidates_without_rewriting_status_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "source-v3-state" / RUN_ID
    runner = AmbiguousLaunchRunner(run_dir, resolves=False)
    finisher = _finisher(tmp_path, monkeypatch, runner, reconcile_polls=1)
    with pytest.raises(subject.SourceV3FinisherError, match="never relaunch"):
        finisher._launch_or_recover(
            phase="worker",
            prior={},
            payload=b"{}",
            worker="DISABLED",
            verifier="DISABLED",
            publisher="DISABLED",
        )

    runner.resolves = True
    publish_once = subject._publish_once
    crashed = False

    def crash_before_attribution(path: Path, raw: bytes) -> bool:
        nonlocal crashed
        if path.name == "provider-attribution.json" and not crashed:
            crashed = True
            raise RuntimeError("simulated host crash")
        return publish_once(path, raw)

    monkeypatch.setattr(subject, "_publish_once", crash_before_attribution)
    with pytest.raises(RuntimeError, match="simulated host crash"):
        finisher._launch_or_recover(
            phase="worker",
            prior={},
            payload=b"{}",
            worker="DISABLED",
            verifier="DISABLED",
            publisher="DISABLED",
        )
    recovery_path = run_dir / "phases/worker/launch-recovery.json"
    recovery = json.loads(recovery_path.read_bytes())
    assert not (run_dir / "phases/worker/provider-attribution.json").exists()

    monkeypatch.setattr(subject, "_publish_once", publish_once)
    runner.new_state = "True"
    launch = finisher._launch_or_recover(
        phase="worker",
        prior={},
        payload=b"{}",
        worker="DISABLED",
        verifier="DISABLED",
        publisher="DISABLED",
    )
    attribution = json.loads(
        (run_dir / "phases/worker/provider-attribution.json").read_bytes()
    )
    assert launch["provider_attribution_method"] == (
        "provider-latest-after-consumed-intent"
    )
    assert launch["provider_sha256_at_attribution"] == subject.canonical_sha256(
        attribution
    )
    assert recovery["provider_sha256"] != launch["provider_sha256_at_attribution"]
    assert runner.launch_count == 1


class ExecutionRunner:
    def __init__(self, providers: list[dict[str, object]]) -> None:
        self.providers = list(providers)

    def run(self, argv: object, **_kwargs: object) -> object:
        args = tuple(argv)
        assert args[:5] == ("gcloud", "run", "jobs", "executions", "describe")
        return subject.CommandResult(0, _raw(self.providers.pop(0)))


def test_terminal_poll_resumes_after_transient_missing_without_receipt_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _finisher(
        tmp_path,
        monkeypatch,
        ExecutionRunner([_provider(state="MISSING")]),
        max_polls=1,
    )
    with pytest.raises(subject.SourceV3FinisherError, match="polling exhausted"):
        first._poll_terminal(
            phase="worker",
            name=NEW_NAME,
            uid=NEW_UID,
            payload=b"{}",
            worker="DISABLED",
            verifier="DISABLED",
            publisher="DISABLED",
            intent_sha256="a" * 64,
        )
    second = _finisher(
        tmp_path,
        monkeypatch,
        ExecutionRunner([_provider(state="True")]),
        max_polls=1,
    )
    second._poll_terminal(
        phase="worker",
        name=NEW_NAME,
        uid=NEW_UID,
        payload=b"{}",
        worker="DISABLED",
        verifier="DISABLED",
        publisher="DISABLED",
        intent_sha256="a" * 64,
    )
    poll_dir = second.run_dir / "phases/worker/provider-polls"
    assert sorted(path.name for path in poll_dir.iterdir()) == [
        "000000.json",
        "000001.json",
    ]


class FailedResultRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, argv: object, **_kwargs: object) -> object:
        args = tuple(argv)
        assert args[:2] == (str(subject.LAUNCHER), "result")
        self.calls += 1
        return subject.CommandResult(2, b"", b"not visible yet")


def test_result_collection_uses_restart_safe_create_once_attempt_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = FailedResultRunner()
    finisher = _finisher(tmp_path, monkeypatch, runner, result_polls=1)
    for _ in range(2):
        with pytest.raises(subject.SourceV3FinisherError, match="collection exhausted"):
            finisher._collect_result(phase="worker", name=NEW_NAME, uid=NEW_UID)
    attempts = finisher.run_dir / "phases/worker/result-attempts"
    assert sorted(path.name for path in attempts.iterdir()) == [
        "000000.return.json",
        "000000.stderr.raw",
        "000000.stdout.raw",
        "000001.return.json",
        "000001.stderr.raw",
        "000001.stdout.raw",
    ]
    assert runner.calls == 2


def test_preflight_reads_every_exact_uri_once_and_resumes_from_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[str] = []
    finisher = _finisher(tmp_path, monkeypatch, object())

    def absent(uri: str) -> bool:
        observed.append(uri)
        return False

    finisher.object_exists = absent
    uris = [f"gs://fixture/source-v3/object-{index:04d}.json" for index in range(2_865)]
    freeze = {"schema_version": "test-freeze/v1", "complete": True}
    finisher._preflight(freeze, uris)
    assert observed == uris

    finisher.object_exists = lambda _uri: (_ for _ in ()).throw(
        AssertionError("persisted preflight must not repeat object reads")
    )
    finisher._preflight(freeze, uris)


def _identity(name: str, generation: int) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": str(generation),
        "sha256": f"{generation:x}" * 64,
        "bytes": 100 + generation,
    }


def _terminal_phases() -> dict[str, dict[str, object]]:
    names = {
        phase: f"{subject.JOB}-{letter}0000"
        for phase, letter in zip(subject.PHASES, "wvpr", strict=True)
    }
    source_identity = _identity("source-release-v3", 1)
    batch_identity = _identity("batch-release-v3", 2)
    publish_output = {
        "source_release_v3_identity": source_identity,
        "batch_release_identity": batch_identity,
    }
    reopen_output = {
        **publish_output,
        "task0_worker_execution_name": names["worker"],
        "task0_verifier_execution_name": names["verify"],
        "publisher_execution_name": names["publish"],
        "reopen_execution_name": names["reopen"],
        "write_disabled_public_reopen_complete": True,
        "cloud_mutation_performed": False,
    }
    return {
        "worker": {"execution_name": names["worker"]},
        "verify": {"execution_name": names["verify"]},
        "publish": {
            "execution_name": names["publish"],
            "provider_receipt": {"operator_output": publish_output},
        },
        "reopen": {
            "execution_name": names["reopen"],
            "provider_receipt": {"operator_output": reopen_output},
        },
    }


def test_terminal_extracts_source_identity_from_independent_reopen() -> None:
    phases = _terminal_phases()
    source_identity, batch_identity = subject.validate_final_source_identities(phases)
    assert source_identity["uri"] == "gs://fixture/source-release-v3.json"
    assert batch_identity["uri"] == "gs://fixture/batch-release-v3.json"
    changed = deepcopy(phases)
    changed["reopen"]["provider_receipt"]["operator_output"][
        "source_release_v3_identity"
    ] = _identity("wrong-source", 3)
    with pytest.raises(subject.SourceV3FinisherError):
        subject.validate_final_source_identities(changed)


def _proc_stat(pid: int, parent: int, start_ticks: int) -> str:
    suffix = ["S", str(parent), *("0" for _ in range(17)), str(start_ticks)]
    return f"{pid} (source-v3-test) {' '.join(suffix)}\n"


def test_registry_validation_proves_canonical_continuous_lane_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "production-launcher-registry"
    receipt = state_root / "launchers/source-v3.json"
    receipt.parent.mkdir(parents=True)
    lock_dir = state_root / "launcher-locks"
    lock_dir.mkdir()
    lock_path = lock_dir / (sha256(subject.JOB.encode("ascii")).hexdigest() + ".lock")
    lock_path.touch()
    wrapper_pid = 100
    current_pid = 200
    wrapper_ticks = 777
    value = {
        "schema_version": "shared-launcher-registry/v1",
        "script_path": str(SCRIPT),
        "pid": wrapper_pid,
        "process_start_ticks": wrapper_ticks,
        "owner": "production",
        "lane": subject.JOB,
        "target_run_id_prefixes": [RUN_ID],
        "acquired_at_utc": "2026-09-11T17:00:00Z",
    }
    receipt.write_bytes(subject.canonical_bytes(value))
    receipt.chmod(0o600)
    proc_root = tmp_path / "proc"
    for pid, parent, ticks in (
        (wrapper_pid, 1, wrapper_ticks),
        (current_pid, wrapper_pid, 888),
    ):
        directory = proc_root / str(pid)
        directory.mkdir(parents=True)
        (directory / "stat").write_text(
            _proc_stat(pid, parent, ticks), encoding="ascii"
        )
    monkeypatch.setattr(subject, "REGISTRY_STATE_ROOT", state_root)
    environment = {
        "NFL_LAUNCHER_REGISTRY_RECEIPT": str(receipt),
        "NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256": sha256(receipt.read_bytes()).hexdigest(),
        "NFL_LAUNCHER_REGISTRY_STATE_ROOT": str(state_root),
        "NFL_LAUNCHER_REGISTRY_LANE": subject.JOB,
        "NFL_LAUNCHER_REGISTRY_WRAPPER_PID": str(wrapper_pid),
        "NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS": str(wrapper_ticks),
    }
    subject.verify_launcher_registry_lane(
        run_id=RUN_ID,
        environment=environment,
        proc_root=proc_root,
        current_pid=current_pid,
        lock_probe=lambda path: path == lock_path,
    )
