from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess


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
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_GCLOUD_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args, separators=(",", ":")) + "\\n")

job = os.environ["FAKE_JOB"]
image = os.environ["FAKE_IMAGE"]
terminal_image = os.environ.get("FAKE_TERMINAL_IMAGE", image)
service_account = os.environ["FAKE_SERVICE_ACCOUNT"]

if args[:3] == ["run", "jobs", "describe"]:
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
    print(f"{job}-{stage}-00001")
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
            "conditions": [{"type": "Completed", "status": "True"}],
            "completionTime": "2026-08-25T16:01:00Z",
        },
    }, sort_keys=True))
else:
    raise SystemExit("unexpected gcloud surface: " + repr(args))
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return fake_bin, log


def _environment(fake_bin: Path, log: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
        "CORE_V1_SCORE_CHAIN_ENABLED": "1",
        "FAKE_GCLOUD_LOG": str(log),
        "FAKE_JOB": JOB,
        "FAKE_IMAGE": IMAGE,
        "FAKE_SERVICE_ACCOUNT": SERVICE_ACCOUNT,
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
