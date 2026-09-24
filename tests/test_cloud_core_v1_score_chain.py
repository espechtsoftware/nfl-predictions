from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/cloud_core_v1_score_chain.sh"

PROJECT = "nfl-predictions-503414"
JOB = "atlas-minimal-c-s2023-w1-v1"
SERVICE_ACCOUNT = (
    "corpus-parametric-research@"
    "nfl-predictions-503414.iam.gserviceaccount.com"
)
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    f"foundry/image@sha256:{'a' * 64}"
)
CODE_SHA = "b" * 40
CHAIN_RUN_ID = "core-chain-fixture"
CATALOG_ID = "core-catalog-fixture"
OUTCOME_RUN_ID = "core-outcome-fixture"
GRADE_RUN_ID = "core-grade-fixture"
CATALOG_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    f"corpus-core-v1-catalogs/{CATALOG_ID}/"
)
OUTCOME_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    f"corpus-core-v1-realized/{OUTCOME_RUN_ID}/"
)
GRADE_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    f"corpus-core-v1-grades/{GRADE_RUN_ID}/"
)
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _identity(uri: str, marker: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": marker * 64,
        "bytes": 1,
    }


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    operator = scripts / SOURCE.name
    shutil.copyfile(SOURCE, operator)
    operator.chmod(0o755)

    source_identity = tmp_path / "source-panel-identity.json"
    source_identity.write_bytes(
        _canonical(_identity("gs://fixture/source-panel.json", "c"))
    )
    t230_identity = tmp_path / "t230-panel-release-identity.json"
    t230_identity.write_bytes(
        _canonical(_identity("gs://fixture/t230-panel-release.json", "d"))
    )
    lease = {
        "version": "historical-outcome-active-v1",
        "run_id": OUTCOME_RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-25T16:00:00+00:00",
    }
    lease_raw = _canonical(lease)
    lease_receipt = tmp_path / "historical-outcome-lease-receipt.json"
    lease_receipt.write_bytes(_canonical({
        "lease": lease,
        "object": {
            "uri": LEASE_URI,
            "generation": "71",
            "sha256": sha256(lease_raw).hexdigest(),
            "bytes": len(lease_raw),
            "create_only": True,
        },
    }))
    return operator, source_identity, t230_identity, lease_receipt


def _args(
    *,
    mode: str,
    source_identity: Path,
    t230_identity: Path,
    lease_receipt: Path | None,
    execute: bool = True,
    recover_failed_stage: str | None = None,
) -> list[str]:
    result = [
        "--mode", mode,
        "--chain-run-id", CHAIN_RUN_ID,
        "--project", PROJECT,
        "--region", "us-central1",
        "--job", JOB,
        "--service-account", SERVICE_ACCOUNT,
        "--image", IMAGE,
        "--code-sha", CODE_SHA,
        "--catalog-id", CATALOG_ID,
        "--catalog-output-prefix", CATALOG_PREFIX,
        "--max-logical-catalog-bytes", "100000000",
        "--outcome-run-id", OUTCOME_RUN_ID,
        "--outcome-output-prefix", OUTCOME_PREFIX,
        "--grade-run-id", GRADE_RUN_ID,
        "--grade-output-prefix", GRADE_PREFIX,
        "--max-logical-grade-bytes", "200000000",
        "--source-panel-identity", str(source_identity),
        "--t230-panel-release-identity", str(t230_identity),
        "--poll-seconds", "1",
        "--max-wait-seconds", "10",
    ]
    if execute:
        result.insert(0, "--execute")
    if lease_receipt is not None:
        result.extend(["--lease-receipt", str(lease_receipt)])
    if recover_failed_stage is not None:
        result.extend(["--recover-failed-stage", recover_failed_stage])
    return result


def _fake_gcloud(tmp_path: Path) -> tuple[Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    log = tmp_path / "gcloud-calls.jsonl"
    script = fake_bin / "gcloud"
    script.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

args = sys.argv[1:]
with open(os.environ["FAKE_GCLOUD_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args, separators=(",", ":")) + "\\n")

job = os.environ["FAKE_JOB"]
image = os.environ["FAKE_IMAGE"]
terminal_image = os.environ.get("FAKE_TERMINAL_IMAGE", image)
service_account = os.environ["FAKE_SERVICE_ACCOUNT"]

if args[:3] == ["run", "jobs", "describe"]:
    hold = os.environ.get("FAKE_JOB_DESCRIBE_HOLD")
    if hold:
        hold_path = Path(hold)
        hold_path.mkdir(parents=True, exist_ok=True)
        (hold_path / "ready").write_text("ready\\n", encoding="utf-8")
        deadline = time.monotonic() + 10
        while not (hold_path / "release").exists():
            if time.monotonic() >= deadline:
                raise SystemExit("fake describe hold timed out")
            time.sleep(0.01)
    barrier = os.environ.get("FAKE_JOB_DESCRIBE_BARRIER")
    if barrier:
        barrier_path = Path(barrier)
        barrier_path.mkdir(parents=True, exist_ok=True)
        (barrier_path / str(os.getpid())).write_text("ready\\n", encoding="utf-8")
        deadline = time.monotonic() + 10
        while len(list(barrier_path.iterdir())) < 2:
            if time.monotonic() >= deadline:
                raise SystemExit("fake describe barrier timed out")
            time.sleep(0.01)
    print(json.dumps({
        "metadata": {"name": job},
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": image,
                    "command": ["bash"],
                    "args": [
                        "-ceu",
                        "python scripts/run_corpus_extreme_tail_panel_transport_v1.py parked",
                    ],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                    "env": [],
                    "volumeMounts": [{
                        "name": "foundry-t230-runtime-evidence",
                        "mountPath": "/etc/nfl-dfs",
                    }],
                }],
                "maxRetries": 0,
                "timeoutSeconds": "21600",
                "serviceAccountName": service_account,
                "volumes": [{
                    "name": "foundry-t230-runtime-evidence",
                    "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"},
                }],
            }},
        }}},
    }, sort_keys=True))
elif args[:3] == ["run", "jobs", "execute"]:
    joined = next(value for value in args if value.startswith("--args="))
    if "run_core_v1_catalog_cloud.py" in joined:
        stage = "catalog"
    elif "run_core_v1_outcome_supply.py" in joined:
        stage = "outcome"
    elif "run_core_v1_grade_cloud.py" in joined:
        stage = "grade"
    else:
        raise SystemExit("unknown Core stage")
    if os.environ.get("FAKE_AMBIGUOUS_LAUNCH_STAGE") == stage:
        raise SystemExit(1)
    with open(os.environ["FAKE_GCLOUD_LOG"], encoding="utf-8") as handle:
        prior = [json.loads(line) for line in handle if line.strip()]
    launch_count = sum(
        1 for row in prior
        if row[:3] == ["run", "jobs", "execute"]
        and f"run_core_v1_{stage}" in next(
            value for value in row if value.startswith("--args=")
        )
    )
    print(f"{job}-{stage}-{launch_count:05d}")
elif args[:4] == ["run", "jobs", "executions", "describe"]:
    execution = args[4]
    with open(os.environ["FAKE_GCLOUD_LOG"], encoding="utf-8") as handle:
        prior = [json.loads(line) for line in handle if line.strip()]
    stage = next(value for value in ("catalog", "outcome", "grade") if f"-{value}-" in execution)
    launch = next(
        row for row in reversed(prior)
        if row[:3] == ["run", "jobs", "execute"]
        and f"run_core_v1_{stage}" in next(
            value for value in row if value.startswith("--args=")
        )
    )
    args_override = next(value for value in launch if value.startswith("--args="))
    bash_command = args_override.split(",", 1)[1]
    env_override = next(
        value for value in launch if value.startswith("--update-env-vars=")
    ).removeprefix("--update-env-vars=")
    env_name, env_value = env_override.split("=", 1)
    launch_ordinal = int(execution.rsplit("-", 1)[1])
    fail_stage = os.environ.get("FAKE_FAIL_STAGE")
    fail_count = int(os.environ.get("FAKE_FAIL_COUNT", "0"))
    terminal_status = (
        "False"
        if fail_stage == stage and launch_ordinal <= fail_count
        else "True"
    )
    print(json.dumps({
        "metadata": {
            "name": execution,
            "labels": {"run.googleapis.com/job": job},
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": terminal_image,
                    "command": ["bash"],
                    "args": ["-ceu", bash_command],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                    "env": [{"name": env_name, "value": env_value}],
                    "volumeMounts": [{
                        "name": "foundry-t230-runtime-evidence",
                        "mountPath": "/etc/nfl-dfs",
                    }],
                }],
                "maxRetries": 0,
                "timeoutSeconds": "21600",
                "serviceAccountName": service_account,
                "volumes": [{
                    "name": "foundry-t230-runtime-evidence",
                    "emptyDir": {"medium": "Memory", "sizeLimit": "1Mi"},
                }],
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": terminal_status}],
            "completionTime": "2026-08-25T16:01:00Z",
        },
    }, sort_keys=True))
else:
    raise SystemExit("unexpected gcloud surface: " + repr(args))
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    helper = fake_bin / "core-v1-python"
    helper.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_CORE_MATERIALIZER_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args, separators=(",", ":")) + "\\n")
if len(args) < 2 or args[1] != "materialize-core-v1-completion":
    raise SystemExit("unexpected local Core helper invocation")
output = Path(args[args.index("--output") + 1])
completion_uri = args[args.index("--completion-uri") + 1]
raw = (
    "disposition=core-v1-outcome-snapshot-closed\\n"
    "run_id=core-outcome-fixture\\n"
    "uses_realized_outcomes=true\\n"
).encode()
if output.exists() and output.read_bytes() != raw:
    raise SystemExit("fake materialization differs")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(raw)
print("HISTORICAL_OUTCOME_CORE_V1_COMPLETION_MATERIALIZED " + json.dumps({
    "completion_uri": completion_uri,
    "completion_generation": "73",
    "completion_sha256": "f" * 64,
    "completion_bytes": 3,
    "output": str(output),
}, sort_keys=True, separators=(",", ":")))
""",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    return fake_bin, log


def _environment(fake_bin: Path, log: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
        "CORE_V1_SCORE_CHAIN_ENABLED": "1",
        "FAKE_GCLOUD_LOG": str(log),
        "FAKE_CORE_MATERIALIZER_LOG": str(log.parent / "core-materializer.jsonl"),
        "FAKE_JOB": JOB,
        "FAKE_IMAGE": IMAGE,
        "FAKE_SERVICE_ACCOUNT": SERVICE_ACCOUNT,
        "CORE_V1_SCORE_CHAIN_PYTHON_BIN": str(fake_bin / "core-v1-python"),
    }


def _run(
    operator: Path,
    args: list[str],
    *,
    cwd: Path,
    environ: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(operator), *args],
        cwd=cwd,
        env=environ,
        text=True,
        capture_output=True,
        check=False,
    )


def _calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _wait_for_path(path: Path) -> None:
    deadline = time.monotonic() + 10
    while not path.exists():
        if time.monotonic() >= deadline:
            raise AssertionError(f"timed out waiting for {path}")
        time.sleep(0.01)


def _install_claim_boundary_tr(fake_bin: Path) -> None:
    real_tr = shutil.which("tr")
    assert real_tr is not None
    wrapper = fake_bin / "tr"
    wrapper.write_text(
        f'''#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import time

claim_raw = os.environ.get("FAKE_TR_RECOVERY_CLAIM")
receipt_raw = os.environ.get("FAKE_TR_RECOVERY_RECEIPT")
hold_raw = os.environ.get("FAKE_TR_RECOVERY_HOLD")
if claim_raw and receipt_raw and hold_raw:
    claim = Path(claim_raw)
    receipt = Path(receipt_raw)
    if claim.is_file() and not receipt.exists():
        hold = Path(hold_raw)
        hold.mkdir(parents=True, exist_ok=True)
        (hold / "ready").write_text("ready\\n", encoding="utf-8")
        deadline = time.monotonic() + 10
        while not (hold / "crash").exists():
            if time.monotonic() >= deadline:
                raise SystemExit("fake tr claim-boundary hold timed out")
            time.sleep(0.01)
        raise SystemExit(96)
os.execv({real_tr!r}, [{real_tr!r}, *sys.argv[1:]])
''',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)


def _install_crashing_mv(fake_bin: Path) -> None:
    real_mv = shutil.which("mv")
    assert real_mv is not None
    wrapper = fake_bin / "mv"
    wrapper.write_text(
        f'''#!/usr/bin/env bash
if [[ "${{FAKE_MV_CRASH_BEFORE_ARCHIVE:-}}" == "1" ]]; then
  exit 97
fi
exec "{real_mv}" "$@"
''',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)


def test_operator_is_narrow_default_off_and_has_no_admin_or_inventory_surface() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'gcloud run jobs execute "$JOB"' in source
    assert 'gcloud run jobs executions describe "$execution"' in source
    assert 'gcloud run jobs describe "$JOB"' in source
    assert "--args=\"-ceu,$command\"" in source
    assert "--command" not in source
    assert "CORE_V1_CATALOG_CLOUD_ENABLED" in source
    assert "CORE_V1_OUTCOME_SUPPLY_ENABLED" in source
    assert "CORE_V1_GRADE_CLOUD_ENABLED" in source
    assert "historical_outcome_lease.py" in source
    assert "materialize-core-v1-completion" in source
    assert "--recover-failed-stage" in source
    assert "blind_reinvocation_licensed:false" in source
    assert "automatic_retry_licensed:false" in source
    for forbidden in (
        "gcloud builds",
        "gcloud run jobs deploy",
        "gcloud run jobs update",
        "gcloud run jobs create",
        "get-iam-policy",
        "gcloud storage",
        "gcloud logging",
        "list_blobs",
        "logs read",
    ):
        assert forbidden not in source


def test_default_off_and_missing_lease_fail_before_any_cloud_call(tmp_path: Path) -> None:
    operator, source_identity, t230_identity, lease_receipt = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = _environment(fake_bin, log)

    closed = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
            execute=False,
        ),
        cwd=tmp_path,
        environ={**environ, "CORE_V1_SCORE_CHAIN_ENABLED": "0"},
    )
    assert closed.returncode == 2
    assert "required explicitly" in closed.stderr
    assert _calls(log) == []

    no_lease = _run(
        operator,
        _args(
            mode="outcome",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert no_lease.returncode == 2
    assert "requires one supplied regular lease receipt" in no_lease.stderr
    assert _calls(log) == []

    forged = json.loads(lease_receipt.read_text(encoding="utf-8"))
    forged["object"]["sha256"] = "f" * 64
    lease_receipt.write_bytes(_canonical(forged))
    bad_lease = _run(
        operator,
        _args(
            mode="outcome",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=lease_receipt,
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert bad_lease.returncode == 2
    assert "does not bind its canonical lease bytes" in bad_lease.stderr
    assert _calls(log) == []


def test_all_runs_three_cli_overrides_and_exactly_resumes_local_evidence(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, lease_receipt = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = _environment(fake_bin, log)
    args = _args(
        mode="all",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=lease_receipt,
    )

    first = _run(operator, args, cwd=tmp_path, environ=environ)
    assert first.returncode == 0, first.stderr
    assert first.stdout.count("CORE_V1_STAGE_CLOSED") == 3
    assert "CORE_V1_SCORE_CHAIN_CLOSED mode=all" in first.stdout

    calls = _calls(log)
    job_describes = [row for row in calls if row[:3] == ["run", "jobs", "describe"]]
    executes = [row for row in calls if row[:3] == ["run", "jobs", "execute"]]
    terminal_describes = [
        row for row in calls
        if row[:4] == ["run", "jobs", "executions", "describe"]
    ]
    assert len(job_describes) == 3
    assert len(executes) == 3
    assert len(terminal_describes) == 3
    expected = (
        ("catalog", "scripts/run_core_v1_catalog_cloud.py", "CORE_V1_CATALOG_CLOUD_ENABLED=1"),
        ("outcome", "scripts/run_core_v1_outcome_supply.py", "CORE_V1_OUTCOME_SUPPLY_ENABLED=1"),
        ("grade", "scripts/run_core_v1_grade_cloud.py", "CORE_V1_GRADE_CLOUD_ENABLED=1"),
    )
    for row, (_, cli_path, gate) in zip(executes, expected, strict=True):
        assert row[3] == JOB
        args_override = next(value for value in row if value.startswith("--args="))
        assert args_override.startswith("--args=-ceu,exec python ")
        assert cli_path in args_override
        assert f"--update-env-vars={gate}" in row
        assert "--async" in row
        assert all(not value.startswith("--command") for value in row)
        if cli_path.endswith("run_core_v1_outcome_supply.py"):
            assert f"--expected-lease-uri {LEASE_URI}" in args_override
            assert "--expected-lease-generation 71" in args_override
            assert "--expected-lease-sha256 " in args_override
            assert "--expected-lease-bytes " in args_override

    run_dir = (
        tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    )
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["catalog"]["root_uri"] == CATALOG_PREFIX + "catalog-root.json"
    assert config["outcome"]["completion_uri"] == OUTCOME_PREFIX + "completion.json"
    assert config["grade"]["completion_uri"] == GRADE_PREFIX + "completion.json"
    assert config["cloud_build_or_deploy_licensed"] is False
    retained_lease = json.loads(
        (run_dir / "historical-outcome-lease-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert retained_lease["lease"]["run_id"] == OUTCOME_RUN_ID
    release = json.loads(
        (run_dir / "historical-outcome-lease-release-required.json").read_text(
            encoding="utf-8"
        )
    )
    assert release["status"] == "EXPLICIT_EXTERNAL_RELEASE_REQUIRED"
    assert release["automatic_release_licensed"] is False
    strict_completion = run_dir / "historical-outcome-strict-completion.txt"
    assert release["strict_completion"] == str(strict_completion)
    assert strict_completion.read_text(encoding="utf-8").splitlines() == [
        "disposition=core-v1-outcome-snapshot-closed",
        f"run_id={OUTCOME_RUN_ID}",
        "uses_realized_outcomes=true",
    ]
    materializer_calls = [
        json.loads(line)
        for line in (tmp_path / "core-materializer.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert len(materializer_calls) == 1
    assert materializer_calls[0][1:3] == [
        "materialize-core-v1-completion", "--receipt",
    ]
    assert materializer_calls[0][
        materializer_calls[0].index("--completion-uri") + 1
    ] == OUTCOME_PREFIX + "completion.json"
    for stage, _, _ in expected:
        stage_dir = run_dir / "stages" / stage
        launch = json.loads((stage_dir / "launch.json").read_text(encoding="utf-8"))
        if stage == "outcome":
            assert launch["historical_outcome_lease_object"] == retained_lease[
                "object"
            ]
            assert launch["historical_outcome_lease_receipt_sha256"] == sha256(
                (run_dir / "historical-outcome-lease-receipt.json").read_bytes()
            ).hexdigest()
        else:
            assert launch["historical_outcome_lease_object"] is None
            assert launch["historical_outcome_lease_receipt_sha256"] is None
        execution = (stage_dir / "execution-name.txt").read_text(
            encoding="utf-8"
        ).strip()
        terminal = json.loads(
            (stage_dir / "terminal-execution.json").read_text(encoding="utf-8")
        )
        assert terminal["metadata"]["name"] == execution
        assert terminal["status"]["conditions"] == [
            {"type": "Completed", "status": "True"}
        ]
        assert int(
            (stage_dir / "elapsed-seconds.txt").read_text(encoding="utf-8")
        ) >= 0
        assert (stage_dir / "launch-output.txt").read_text(
            encoding="utf-8"
        ).strip() == execution
        assert (stage_dir / "launch-exit-status.txt").read_text(
            encoding="utf-8"
        ) == "0\n"
        intent = json.loads(
            (stage_dir / "launch-intent.json").read_text(encoding="utf-8")
        )
        assert intent["stage"] == stage
        assert intent["blind_reinvocation_licensed"] is False
        assert intent["automatic_retry_licensed"] is False
        claim = json.loads(
            (stage_dir / "launch-owner-claim.json").read_text(encoding="utf-8")
        )
        assert claim["stage"] == stage
        assert claim["creator_alone_may_launch"] is True
        assert claim["equal_preexisting_claim_licenses_launch"] is False
        assert claim["failed_stage_recovery_binding"] is None
        job = json.loads((stage_dir / "job-config.json").read_text(encoding="utf-8"))
        assert job["image"] == IMAGE
        assert job["service_account"] == SERVICE_ACCOUNT
        assert job["command"] == ["bash"]
        assert job["max_retries"] == 0

    before_replay = log.read_bytes()
    second = _run(operator, args, cwd=tmp_path, environ=environ)
    assert second.returncode == 0, second.stderr
    assert second.stdout.count("CORE_V1_STAGE_RECOVERED") == 3
    assert log.read_bytes() == before_replay
    assert len(
        (tmp_path / "core-materializer.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ) == 2


def test_individual_modes_work_and_create_equal_config_rejects_identity_drift(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, lease_receipt = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = _environment(fake_bin, log)

    catalog = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert catalog.returncode == 0, catalog.stderr
    assert len([row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]]) == 1

    grade = _run(
        operator,
        _args(
            mode="grade",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=lease_receipt,
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert grade.returncode == 0, grade.stderr
    assert len([row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]]) == 2

    drifted = _identity("gs://fixture/source-panel.json", "e")
    source_identity.write_bytes(_canonical(drifted))
    before_drift = log.read_bytes()
    refused = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert refused.returncode == 2
    assert "durable evidence differs" in refused.stderr
    assert log.read_bytes() == before_drift


def test_terminal_execution_envelope_drift_fails_before_terminal_acceptance(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_TERMINAL_IMAGE": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            f"foundry/other@sha256:{'f' * 64}"
        ),
    }

    result = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        ),
        cwd=tmp_path,
        environ=environ,
    )

    assert result.returncode == 2
    assert "terminal execution differs from its exact image-D" in result.stderr
    stage_dir = (
        tmp_path
        / "reports/core-v1-score-chain-runs"
        / CHAIN_RUN_ID
        / "stages/catalog"
    )
    assert (stage_dir / "execution-name.txt").is_file()
    assert not (stage_dir / "terminal-execution.json").exists()


def test_terminal_failure_requires_explicit_recovery_and_retains_every_attempt(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "2",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )

    first = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert first.returncode == 2
    assert "failed or was cancelled" in first.stderr
    calls_after_first = _calls(log)
    assert len(
        [row for row in calls_after_first if row[:3] == ["run", "jobs", "execute"]]
    ) == 1

    refused = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert refused.returncode == 2
    assert "--recover-failed-stage catalog" in refused.stderr
    assert _calls(log) == calls_after_first

    recovery_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
        recover_failed_stage="catalog",
    )
    second = _run(operator, recovery_args, cwd=tmp_path, environ=environ)
    assert second.returncode == 2
    assert "CORE_V1_STAGE_FAILED_ATTEMPT_RETAINED catalog attempt=0" in (
        second.stdout
    )
    assert "failed or was cancelled" in second.stderr

    third = _run(operator, recovery_args, cwd=tmp_path, environ=environ)
    assert third.returncode == 0, third.stderr
    assert "CORE_V1_STAGE_FAILED_ATTEMPT_RETAINED catalog attempt=1" in (
        third.stdout
    )
    executes = [
        row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]
    ]
    assert len(executes) == 3

    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    archive_root = run_dir / "stages/failed-attempts/catalog"
    for ordinal in (0, 1):
        archive = archive_root / f"attempt-{ordinal:04d}"
        receipt = json.loads(
            (archive / "manual-recovery.json").read_text(encoding="utf-8")
        )
        assert receipt["failed_attempt_ordinal"] == ordinal
        assert receipt["failed_execution"].endswith(f"-{ordinal + 1:05d}")
        assert receipt["explicit_manual_recovery"] is True
        assert receipt["command_image_input_output_drift_licensed"] is False
        assert receipt["blind_outcome_reinvocation_licensed"] is False
        assert receipt["automatic_retry_licensed"] is False
        terminal = json.loads(
            (archive / "terminal-execution.json").read_text(encoding="utf-8")
        )
        assert terminal["status"]["conditions"] == [
            {"type": "Completed", "status": "False"}
        ]

    current = run_dir / "stages/catalog"
    current_execution = (current / "execution-name.txt").read_text(
        encoding="utf-8"
    ).strip()
    assert current_execution.endswith("-00003")
    current_terminal = json.loads(
        (current / "terminal-execution.json").read_text(encoding="utf-8")
    )
    assert current_terminal["status"]["conditions"] == [
        {"type": "Completed", "status": "True"}
    ]

    before_replay = log.read_bytes()
    replay = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert replay.returncode == 0, replay.stderr
    assert "CORE_V1_STAGE_RECOVERED catalog" in replay.stdout
    assert log.read_bytes() == before_replay

    recovery_of_success = _run(
        operator, recovery_args, cwd=tmp_path, environ=environ
    )
    assert recovery_of_success.returncode == 2
    assert "already successful stage" in recovery_of_success.stderr
    assert log.read_bytes() == before_replay


def test_recovery_archive_replays_exact_claim_after_interrupted_transaction(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    _install_claim_boundary_tr(fake_bin)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    failed = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert failed.returncode == 2
    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    stage_dir = run_dir / "stages/catalog"
    claim = stage_dir / "manual-recovery-owner-claim.json"
    receipt = stage_dir / "manual-recovery.json"
    hold = tmp_path / "claim-boundary-hold"
    recovery_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
        recover_failed_stage="catalog",
    )
    interruption_environ = {
        **environ,
        "FAKE_TR_RECOVERY_CLAIM": str(claim),
        "FAKE_TR_RECOVERY_RECEIPT": str(receipt),
        "FAKE_TR_RECOVERY_HOLD": str(hold),
    }
    interrupted = subprocess.Popen(
        ["bash", str(operator), *recovery_args],
        cwd=tmp_path,
        env=interruption_environ,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for_path(hold / "ready")
    assert claim.is_file()
    assert not receipt.exists()
    claim_raw = claim.read_bytes()
    calls_at_claim_boundary = _calls(log)

    unflagged = _run(
        operator,
        base_args,
        cwd=tmp_path,
        environ=interruption_environ,
    )
    assert unflagged.returncode == 2
    assert "owns the stage recovery-transition lock" in unflagged.stderr
    assert _calls(log) == calls_at_claim_boundary
    (hold / "crash").write_text("crash\n", encoding="utf-8")
    interrupted_stdout, interrupted_stderr = interrupted.communicate(timeout=20)
    assert interrupted.returncode != 0, interrupted_stdout + interrupted_stderr
    assert claim.read_bytes() == claim_raw
    assert not receipt.exists()
    assert not (run_dir / "stages/failed-attempts/catalog/attempt-0000").exists()
    calls_after_interruption = _calls(log)

    unflagged_after_crash = _run(
        operator, base_args, cwd=tmp_path, environ=environ
    )
    assert unflagged_after_crash.returncode == 2
    assert "--recover-failed-stage catalog" in unflagged_after_crash.stderr
    assert _calls(log) == calls_after_interruption

    recovered = _run(
        operator,
        recovery_args,
        cwd=tmp_path,
        environ=environ,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert "CORE_V1_STAGE_FAILED_ATTEMPT_RETAINED catalog attempt=0" in (
        recovered.stdout
    )
    archive = run_dir / "stages/failed-attempts/catalog/attempt-0000"
    assert (archive / "manual-recovery-owner-claim.json").read_bytes() == claim_raw
    executes = [
        row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]
    ]
    assert len(executes) == 2


def test_recovery_archive_refuses_differing_preexisting_claim(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    _install_claim_boundary_tr(fake_bin)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    failed = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert failed.returncode == 2
    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    stage_dir = run_dir / "stages/catalog"
    claim = stage_dir / "manual-recovery-owner-claim.json"
    receipt = stage_dir / "manual-recovery.json"
    hold = tmp_path / "differing-claim-boundary-hold"
    recovery_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
        recover_failed_stage="catalog",
    )
    interrupted = subprocess.Popen(
        ["bash", str(operator), *recovery_args],
        cwd=tmp_path,
        env={
            **environ,
            "FAKE_TR_RECOVERY_CLAIM": str(claim),
            "FAKE_TR_RECOVERY_RECEIPT": str(receipt),
            "FAKE_TR_RECOVERY_HOLD": str(hold),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for_path(hold / "ready")
    (hold / "crash").write_text("crash\n", encoding="utf-8")
    interrupted.communicate(timeout=20)
    assert interrupted.returncode != 0
    payload = json.loads(claim.read_text(encoding="utf-8"))
    payload["automatic_retry_licensed"] = True
    claim.write_bytes(_canonical(payload))
    calls_before_refusal = _calls(log)

    refused = _run(
        operator,
        recovery_args,
        cwd=tmp_path,
        environ=environ,
    )
    assert refused.returncode == 2
    assert "failed-stage recovery owner claim differs" in refused.stderr
    assert _calls(log) == calls_before_refusal
    assert not (run_dir / "stages/failed-attempts/catalog/attempt-0000").exists()
    assert not receipt.exists()


def test_recovery_archive_replays_exact_receipt_after_interrupted_rename(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    _install_crashing_mv(fake_bin)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    failed = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert failed.returncode == 2
    recovery_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
        recover_failed_stage="catalog",
    )
    interrupted = _run(
        operator,
        recovery_args,
        cwd=tmp_path,
        environ={**environ, "FAKE_MV_CRASH_BEFORE_ARCHIVE": "1"},
    )
    assert interrupted.returncode != 0
    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    stage_dir = run_dir / "stages/catalog"
    claim_raw = (stage_dir / "manual-recovery-owner-claim.json").read_bytes()
    receipt_raw = (stage_dir / "manual-recovery.json").read_bytes()
    archive = run_dir / "stages/failed-attempts/catalog/attempt-0000"
    assert not archive.exists()
    calls_after_interruption = _calls(log)
    assert len(
        [
            row
            for row in calls_after_interruption
            if row[:3] == ["run", "jobs", "execute"]
        ]
    ) == 1

    unflagged = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert unflagged.returncode == 2
    assert "--recover-failed-stage catalog" in unflagged.stderr
    assert _calls(log) == calls_after_interruption

    recovered = _run(
        operator,
        recovery_args,
        cwd=tmp_path,
        environ=environ,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert (archive / "manual-recovery-owner-claim.json").read_bytes() == claim_raw
    assert (archive / "manual-recovery.json").read_bytes() == receipt_raw
    executes = [
        row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]
    ]
    assert len(executes) == 2


def test_recovery_archive_refuses_differing_preexisting_receipt(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    _install_crashing_mv(fake_bin)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    failed = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert failed.returncode == 2
    recovery_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
        recover_failed_stage="catalog",
    )
    interrupted = _run(
        operator,
        recovery_args,
        cwd=tmp_path,
        environ={**environ, "FAKE_MV_CRASH_BEFORE_ARCHIVE": "1"},
    )
    assert interrupted.returncode != 0
    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    stage_dir = run_dir / "stages/catalog"
    receipt = stage_dir / "manual-recovery.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["automatic_retry_licensed"] = True
    receipt.write_bytes(_canonical(payload))
    calls_before_refusal = _calls(log)

    refused = _run(
        operator,
        recovery_args,
        cwd=tmp_path,
        environ=environ,
    )
    assert refused.returncode == 2
    assert "durable evidence differs" in refused.stderr
    assert _calls(log) == calls_before_refusal
    assert not (run_dir / "stages/failed-attempts/catalog/attempt-0000").exists()


def test_recovery_archive_refuses_extra_and_symlink_inventory(
    tmp_path: Path,
) -> None:
    for inventory_kind in ("extra", "symlink"):
        case_root = tmp_path / inventory_kind
        case_root.mkdir()
        operator, source_identity, t230_identity, _ = _workspace(case_root)
        fake_bin, log = _fake_gcloud(case_root)
        _install_crashing_mv(fake_bin)
        environ = {
            **_environment(fake_bin, log),
            "FAKE_FAIL_STAGE": "catalog",
            "FAKE_FAIL_COUNT": "1",
        }
        base_args = _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        )
        failed = _run(operator, base_args, cwd=case_root, environ=environ)
        assert failed.returncode == 2
        recovery_args = _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
            recover_failed_stage="catalog",
        )
        interrupted = _run(
            operator,
            recovery_args,
            cwd=case_root,
            environ={**environ, "FAKE_MV_CRASH_BEFORE_ARCHIVE": "1"},
        )
        assert interrupted.returncode != 0
        run_dir = case_root / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
        stage_dir = run_dir / "stages/catalog"
        if inventory_kind == "extra":
            (stage_dir / "unexpected-extra").write_text(
                "unexpected\n", encoding="utf-8"
            )
        else:
            receipt = stage_dir / "manual-recovery.json"
            receipt_target = case_root / "manual-recovery-target.json"
            receipt_target.write_bytes(receipt.read_bytes())
            receipt.unlink()
            receipt.symlink_to(receipt_target)
        calls_before_refusal = _calls(log)

        refused = _run(
            operator,
            recovery_args,
            cwd=case_root,
            environ=environ,
        )
        assert refused.returncode == 2
        expected_error = (
            "failed-stage archive inventory differs"
            if inventory_kind == "extra"
            else "durable evidence target is not a regular file"
        )
        assert expected_error in refused.stderr
        assert _calls(log) == calls_before_refusal
        assert not (
            run_dir / "stages/failed-attempts/catalog/attempt-0000"
        ).exists()


def test_failed_stage_recovery_refuses_command_receipt_drift(tmp_path: Path) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    first = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert first.returncode == 2

    stage_dir = (
        tmp_path
        / "reports/core-v1-score-chain-runs"
        / CHAIN_RUN_ID
        / "stages/catalog"
    )
    launch_path = stage_dir / "launch.json"
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    launch["execution_args"][1] += " --drift"
    launch_path.write_bytes(_canonical(launch))
    calls_before_recovery = _calls(log)

    refused = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
            recover_failed_stage="catalog",
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert refused.returncode == 2
    assert "durable evidence differs" in refused.stderr
    assert _calls(log) == calls_before_recovery
    assert not (stage_dir.parent / "failed-attempts/catalog/attempt-0000").exists()


def test_outcome_recovery_reuses_exact_command_and_fixed_query_identity(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, lease_receipt = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "outcome",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="outcome",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=lease_receipt,
    )

    first = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert first.returncode == 2
    calls_after_first = _calls(log)
    refused = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert refused.returncode == 2
    assert _calls(log) == calls_after_first

    recovered = _run(
        operator,
        _args(
            mode="outcome",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=lease_receipt,
            recover_failed_stage="outcome",
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert recovered.returncode == 0, recovered.stderr
    executes = [
        row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]
    ]
    assert len(executes) == 2
    commands = [
        next(value for value in row if value.startswith("--args="))
        for row in executes
    ]
    assert commands[0] == commands[1]

    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    receipt = json.loads(
        (
            run_dir
            / "stages/failed-attempts/outcome/attempt-0000/manual-recovery.json"
        ).read_text(encoding="utf-8")
    )
    fixed = receipt["fixed_outcome_recovery"]
    assert fixed["outcome_run_id"] == OUTCOME_RUN_ID
    assert fixed["historical_outcome_lease_object"]["uri"] == LEASE_URI
    assert fixed["same_deterministic_query_job_get_or_create_only"] is True
    assert fixed["duplicate_query_licensed"] is False
    assert receipt["blind_outcome_reinvocation_licensed"] is False


def test_ambiguous_launch_is_never_blindly_reinvoked(tmp_path: Path) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = {
        **_environment(fake_bin, log),
        "FAKE_AMBIGUOUS_LAUNCH_STAGE": "catalog",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )

    first = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert first.returncode == 2
    assert "blind reinvocation is forbidden" in first.stderr
    stage_dir = (
        tmp_path
        / "reports/core-v1-score-chain-runs"
        / CHAIN_RUN_ID
        / "stages/catalog"
    )
    assert (stage_dir / "launch-intent.json").is_file()
    assert (stage_dir / "launch-output.txt").read_bytes() == b""
    assert (stage_dir / "launch-exit-status.txt").read_text(
        encoding="utf-8"
    ) == "1\n"
    assert not (stage_dir / "execution-name.txt").exists()
    calls_after_first = _calls(log)

    second = _run(operator, base_args, cwd=tmp_path, environ=environ)
    assert second.returncode == 2
    assert "blind reinvocation is forbidden" in second.stderr
    assert _calls(log) == calls_after_first

    explicit = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
            recover_failed_stage="catalog",
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert explicit.returncode == 2
    assert "requires one retained terminally failed attempt" in explicit.stderr
    assert _calls(log) == calls_after_first


def test_recovery_flag_must_name_a_stage_in_the_selected_mode(tmp_path: Path) -> None:
    operator, source_identity, t230_identity, lease_receipt = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    result = _run(
        operator,
        _args(
            mode="grade",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=lease_receipt,
            recover_failed_stage="catalog",
        ),
        cwd=tmp_path,
        environ=_environment(fake_bin, log),
    )
    assert result.returncode == 2
    assert "outside the selected mode" in result.stderr
    assert _calls(log) == []


def test_atomic_launch_owner_allows_only_one_concurrent_execution(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    fixed_date = fake_bin / "date"
    fixed_date.write_text("#!/usr/bin/env bash\nprintf '1787691600\\n'\n", encoding="utf-8")
    fixed_date.chmod(0o755)
    hold = tmp_path / "describe-hold"
    environ = {
        **_environment(fake_bin, log),
        "FAKE_JOB_DESCRIBE_HOLD": str(hold),
    }
    command = [
        "bash",
        str(operator),
        *_args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        ),
    ]
    first = subprocess.Popen(
        command,
        cwd=tmp_path,
        env=environ,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for_path(hold / "ready")
    calls_while_locked = _calls(log)
    second = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert second.returncode == 2
    assert "owns the stage recovery-transition lock" in second.stderr
    assert _calls(log) == calls_while_locked
    (hold / "release").write_text("release\n", encoding="utf-8")
    first_stdout, first_stderr = first.communicate(timeout=20)

    assert first.returncode == 0, first_stdout + first_stderr
    executes = [
        row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]
    ]
    assert len(executes) == 1
    claim = (
        tmp_path
        / "reports/core-v1-score-chain-runs"
        / CHAIN_RUN_ID
        / "stages/catalog/launch-owner-claim.json"
    )
    claim_payload = json.loads(claim.read_text(encoding="utf-8"))
    assert claim_payload["creator_alone_may_launch"] is True
    assert claim_payload["failed_stage_recovery_binding"] is None


def test_successful_replay_requires_the_complete_launch_evidence_envelope(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = _environment(fake_bin, log)
    args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    first = _run(operator, args, cwd=tmp_path, environ=environ)
    assert first.returncode == 0, first.stderr
    stage_dir = (
        tmp_path
        / "reports/core-v1-score-chain-runs"
        / CHAIN_RUN_ID
        / "stages/catalog"
    )
    calls_after_success = _calls(log)
    for name in (
        "launch.json",
        "job-config.json",
        "started-at-epoch.txt",
        "launch-intent.json",
        "launch-owner-claim.json",
        "launch-output.txt",
        "launch-exit-status.txt",
    ):
        path = stage_dir / name
        retained = path.read_bytes()
        path.unlink()
        replay = _run(operator, args, cwd=tmp_path, environ=environ)
        assert replay.returncode == 2, (name, replay.stdout, replay.stderr)
        assert "retained stage launch evidence is unsafe" in replay.stderr
        assert _calls(log) == calls_after_success
        path.write_bytes(retained)


def test_interrupted_replay_validates_launch_evidence_before_cloud_poll(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = _environment(fake_bin, log)
    args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    first = _run(operator, args, cwd=tmp_path, environ=environ)
    assert first.returncode == 0, first.stderr
    stage_dir = (
        tmp_path
        / "reports/core-v1-score-chain-runs"
        / CHAIN_RUN_ID
        / "stages/catalog"
    )
    (stage_dir / "terminal-execution.json").unlink()
    (stage_dir / "elapsed-seconds.txt").unlink()
    (stage_dir / "launch-output.txt").write_text(
        f"{JOB}-catalog-corrupt\n", encoding="utf-8"
    )
    calls_before_replay = _calls(log)

    replay = _run(operator, args, cwd=tmp_path, environ=environ)

    assert replay.returncode == 2
    assert "retained launch output differs from its execution name" in replay.stderr
    assert _calls(log) == calls_before_replay


def test_concurrent_unflagged_invocation_cannot_cross_recovery_transition_lock(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, _ = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    failing_environ = {
        **_environment(fake_bin, log),
        "FAKE_FAIL_STAGE": "catalog",
        "FAKE_FAIL_COUNT": "1",
    }
    base_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
    )
    failed = _run(operator, base_args, cwd=tmp_path, environ=failing_environ)
    assert failed.returncode == 2

    hold = tmp_path / "recovery-describe-hold"
    recovery_environ = {
        **failing_environ,
        "FAKE_JOB_DESCRIBE_HOLD": str(hold),
    }
    recovery_args = _args(
        mode="catalog",
        source_identity=source_identity,
        t230_identity=t230_identity,
        lease_receipt=None,
        recover_failed_stage="catalog",
    )
    recovery = subprocess.Popen(
        ["bash", str(operator), *recovery_args],
        cwd=tmp_path,
        env=recovery_environ,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for_path(hold / "ready")
    calls_while_transition_locked = _calls(log)

    unflagged = _run(
        operator,
        base_args,
        cwd=tmp_path,
        environ=recovery_environ,
    )
    assert unflagged.returncode == 2
    assert "owns the stage recovery-transition lock" in unflagged.stderr
    assert _calls(log) == calls_while_transition_locked

    (hold / "release").write_text("release\n", encoding="utf-8")
    recovery_stdout, recovery_stderr = recovery.communicate(timeout=20)
    assert recovery.returncode == 0, recovery_stdout + recovery_stderr
    executes = [
        row for row in _calls(log) if row[:3] == ["run", "jobs", "execute"]
    ]
    assert len(executes) == 2

    run_dir = tmp_path / "reports/core-v1-score-chain-runs" / CHAIN_RUN_ID
    archive = run_dir / "stages/failed-attempts/catalog/attempt-0000"
    archived_recovery_claim = archive / "manual-recovery-owner-claim.json"
    archived_recovery_receipt = archive / "manual-recovery.json"
    replacement_claim = json.loads(
        (run_dir / "stages/catalog/launch-owner-claim.json").read_text(
            encoding="utf-8"
        )
    )
    binding = replacement_claim["failed_stage_recovery_binding"]
    assert binding == {
        "failed_attempt_ordinal": 0,
        "manual_recovery_owner_claim_sha256": sha256(
            archived_recovery_claim.read_bytes()
        ).hexdigest(),
        "manual_recovery_receipt_sha256": sha256(
            archived_recovery_receipt.read_bytes()
        ).hexdigest(),
    }
    assert (run_dir / "stages/recovery-transition-locks/catalog.lock").is_file()


def test_recovery_target_is_preflighted_before_any_stage_or_all_mode_action(
    tmp_path: Path,
) -> None:
    operator, source_identity, t230_identity, lease_receipt = _workspace(tmp_path)
    fake_bin, log = _fake_gcloud(tmp_path)
    environ = _environment(fake_bin, log)

    absent = _run(
        operator,
        _args(
            mode="catalog",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=None,
            recover_failed_stage="catalog",
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert absent.returncode == 2
    assert "requires one retained terminally failed attempt" in absent.stderr
    assert _calls(log) == []

    all_mode = _run(
        operator,
        _args(
            mode="all",
            source_identity=source_identity,
            t230_identity=t230_identity,
            lease_receipt=lease_receipt,
            recover_failed_stage="grade",
        ),
        cwd=tmp_path,
        environ=environ,
    )
    assert all_mode.returncode == 2
    assert "must close in its exact stage mode" in all_mode.stderr
    assert _calls(log) == []
