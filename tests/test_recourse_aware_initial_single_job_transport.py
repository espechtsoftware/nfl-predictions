from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/run_recourse_aware_initial_single_job_transport.py"
SPEC = importlib.util.spec_from_file_location("recourse_single_job_transport", SOURCE)
assert SPEC is not None and SPEC.loader is not None
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)


def _execution(name: str, status: str = "True") -> dict:
    return {
        "metadata": {
            "name": name,
            "labels": {
                "run.googleapis.com/job": transport.JOB,
                "run.googleapis.com/jobUid": transport.JOB_UID,
            },
            "ownerReferences": [{
                "kind": "Job",
                "name": transport.JOB,
                "uid": transport.JOB_UID,
            }],
        },
        "status": {"conditions": [{"type": "Completed", "status": status}]},
    }


def _execution_snapshot(
    name: str, season: int, week: int, status: str = "True",
) -> dict:
    row = _execution(name, status)
    row["spec"] = {
        "parallelism": 1,
        "taskCount": 1,
        "template": {"spec": {
            "containers": [{
                "image": transport.IMAGE,
                "command": ["python"],
                "args": transport.expected_args(season, week),
                "env": [
                    {"name": "CODE_SHA", "value": transport.CODE_SHA},
                    {"name": "ANALYSIS_IMAGE", "value": transport.IMAGE},
                    {
                        "name": "RECOURSE_TRANSPORT_CELL",
                        "value": transport.cell_token(season, week),
                    },
                ],
                "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
            }],
            "maxRetries": 0,
            "timeoutSeconds": "14400",
            "serviceAccountName": transport.SERVICE_ACCOUNT,
        }},
    }
    if status == "True":
        row["status"].update({
            "succeededCount": 1,
            "failedCount": 0,
            "retriedCount": 0,
            "completionTime": "2026-08-28T00:00:00Z",
        })
    return row


def _job(*, uid: str | None = None) -> dict:
    return {
        "metadata": {"name": transport.JOB, "uid": uid or transport.JOB_UID},
        "spec": {"template": {"spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": transport.IMAGE,
                    "command": ["python"],
                    "args": transport.expected_args(2023, 1),
                    "env": [
                        {"name": "CODE_SHA", "value": transport.CODE_SHA},
                        {"name": "ANALYSIS_IMAGE", "value": transport.IMAGE},
                    ],
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                }],
                "maxRetries": 0,
                "timeoutSeconds": "14400",
                "serviceAccountName": transport.SERVICE_ACCOUNT,
            }},
        }}},
    }


def test_transport_never_creates_deploys_or_deletes_a_job() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    forbidden = (
        '"jobs", "deploy"', '"jobs", "create"', '"jobs", "delete"',
        "gcloud run jobs deploy", "gcloud run jobs delete",
    )
    assert not [token for token in forbidden if token in source]
    command = transport.job_update_command()
    assert command[:5] == [
        "gcloud", "run", "jobs", "update", transport.JOB,
    ]
    assert "--image" in command and transport.IMAGE in command
    for flag in (
        "--clear-secrets", "--clear-volumes", "--clear-volume-mounts",
        "--clear-cloudsql-instances", "--clear-vpc-connector", "--clear-network",
    ):
        assert flag in command


def test_prepare_updates_once_and_submits_only_the_canary() -> None:
    source = inspect.getsource(transport.prepare_canary)
    assert source.count("job_update_command()") == 1
    assert source.count("execution_command(2023, 1)") == 1
    assert "release_cells()" not in source
    assert "validate_job_contract(after)" in source
    assert "inventory_delta(inventory, post_update)" in source


def test_uid_pin_and_exact_job_contract_fail_closed() -> None:
    transport.validate_job_contract(_job())
    with pytest.raises(ValueError, match="UID"):
        transport.validate_job_contract(_job(uid="wrong"))
    changed = _job()
    changed["spec"]["template"]["spec"]["template"]["spec"]["maxRetries"] = 1
    with pytest.raises(ValueError, match="runtime contract"):
        transport.validate_job_contract(changed)


def test_existing_full_runtime_build_and_registry_identity_are_exact() -> None:
    build = {
        "id": transport.BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": {
            "revision": transport.CODE_SHA,
            "url": transport.SOURCE_REPOSITORY,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "revision": transport.CODE_SHA,
            "url": transport.SOURCE_REPOSITORY,
        }},
        "steps": [
            {"id": "full-test-suite", "status": "SUCCESS", "args": []},
            {
                "id": "build-image",
                "status": "SUCCESS",
                "args": ["build", "-t", transport.IMAGE_TAG, "."],
            },
            {
                "id": "smoke-atlas-mvp-runner",
                "status": "SUCCESS",
                "args": [
                    f"python {transport.RUNNER} --help\n"
                    f"python {transport.AGGREGATOR} --help"
                ],
            },
        ],
        "substitutions": {"_IMAGE": transport.IMAGE_TAG},
        "artifacts": {"images": [transport.IMAGE_TAG]},
        "results": {"images": [{
            "name": transport.IMAGE_TAG,
            "digest": transport.IMAGE_DIGEST,
        }]},
    }
    transport.validate_build(build)
    transport.validate_image({"image_summary": {
        "digest": transport.IMAGE_DIGEST,
        "fully_qualified_digest": transport.IMAGE,
    }})
    changed = dict(build)
    changed["status"] = "FAILURE"
    with pytest.raises(ValueError, match="build authority"):
        transport.validate_build(changed)


def test_narrow_v6_authority_is_bound_but_rejected_as_runtime() -> None:
    build = {
        "id": transport.V6_BUILD_ID,
        "status": "SUCCESS",
        "source": {"storageSource": {
            "object": transport.V6_SOURCE_OBJECT,
            "generation": transport.V6_SOURCE_GENERATION,
        }},
        "results": {"images": [{
            "name": transport.V6_IMAGE_TAG,
            "digest": transport.V6_IMAGE_DIGEST,
        }]},
    }
    transport.validate_narrow_v6_build(
        build, "COPY scripts/run_corpus_r6_current_bank_crossed_screen_v1.py",
    )
    with pytest.raises(ValueError, match="incompatibility proof"):
        transport.validate_narrow_v6_build(
            build, f"COPY {transport.RUNNER} /app/scripts/",
        )


def test_inventory_delta_preserves_history_and_rejects_loss_or_duplicates() -> None:
    before = [_execution("old-a"), _execution("old-b", "False")]
    after = [*before, _execution("new-canary")]
    assert transport.inventory_delta(before, after) == {"new-canary"}
    with pytest.raises(ValueError, match="lost"):
        transport.inventory_delta(before, after[1:])
    with pytest.raises(ValueError, match="inventory differs"):
        transport.execution_names([_execution("same"), _execution("same")])


def test_execution_uses_exact_per_cell_override_and_no_job_mutation() -> None:
    command = transport.execution_command(2025, 18)
    assert command[:5] == [
        "gcloud", "run", "jobs", "execute", transport.JOB,
    ]
    args = command[command.index("--args") + 1]
    assert args == ",".join(transport.expected_args(2025, 18))
    assert "--async" in command
    env = command[command.index("--update-env-vars") + 1]
    assert env == "RECOURSE_TRANSPORT_CELL=" + transport.cell_token(2025, 18)
    assert transport.expected_uri(2025, 18) in args
    assert not any(value in command for value in ("deploy", "delete", "create"))


def test_canary_is_excluded_from_explicit_53_cell_release() -> None:
    cells = transport.release_cells()
    assert len(cells) == 53
    assert (2023, 1) not in cells
    assert len(set(cells)) == 53
    assert cells[0] == (2023, 2)
    assert cells[-1] == (2025, 18)


def test_release_fails_before_any_cloud_call_without_validated_canary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport, "OUT", tmp_path)
    monkeypatch.setattr(
        transport, "_run",
        lambda *args, **kwargs: pytest.fail("release reached a cloud command"),
    )
    with pytest.raises(ValueError, match="validated canary receipt is absent"):
        transport.release_grid()


def test_release_requires_exact_outcome_free_canary_receipt() -> None:
    receipt = {
        "version": "recourse-aware-initial-book-single-job-canary-validation-v1",
        "status": True,
        "disposition": "actual-final-path-canary-passes",
        "execution": transport.JOB + "-canary",
        "remaining_cells_released": False,
        "outcome_fields_inspected": False,
        "effect_fields_inspected": False,
    }
    transport.validate_canary_receipt(receipt)
    for key, value in (
        ("status", False),
        ("remaining_cells_released", True),
        ("outcome_fields_inspected", True),
    ):
        changed = dict(receipt)
        changed[key] = value
        with pytest.raises(ValueError, match="receipt differs"):
            transport.validate_canary_receipt(changed)


def test_operator_has_no_historical_outcome_or_log_read_path() -> None:
    source = SOURCE.read_text(encoding="utf-8").lower()
    forbidden = (
        "bigquery", "actual_score", "final_score", "actual_ownership",
        "contest_rank", "payout", "roi", "logging read", "logs read",
    )
    assert not [token for token in forbidden if token in source]
    assert "uses_realized_outcomes" in source
    assert "outcome_fields_inspected" in source


def test_execution_contract_binds_provider_owner_and_cell_token() -> None:
    execution = transport.JOB + "-cell"
    metadata = _execution_snapshot(execution, 2024, 7)
    transport.validate_execution_contract(
        metadata, execution, 2024, 7, require_success=True,
    )
    changed = _execution_snapshot(execution, 2024, 7)
    changed["metadata"]["labels"]["run.googleapis.com/jobUid"] = "wrong"
    with pytest.raises(ValueError, match="owner identity"):
        transport.validate_execution_contract(
            changed, execution, 2024, 7, require_success=False,
        )
    changed = _execution_snapshot(execution, 2024, 7)
    changed["spec"]["template"]["spec"]["containers"][0]["env"][-1][
        "value"
    ] = transport.cell_token(2024, 8)
    with pytest.raises(ValueError, match="snapshot"):
        transport.validate_execution_contract(
            changed, execution, 2024, 7, require_success=False,
        )


def test_inventory_rejects_execution_from_recreated_job() -> None:
    changed = _execution("same-name")
    changed["metadata"]["ownerReferences"][0]["uid"] = "recreated"
    with pytest.raises(ValueError, match="owner"):
        transport.execution_names([changed])


def test_reconcile_recovers_exact_one_unledgered_next_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport, "OUT", tmp_path)
    old = _execution(transport.JOB + "-old")
    canary_name = transport.JOB + "-canary"
    next_name = transport.JOB + "-next"
    (tmp_path / "executions-before.json").write_text(
        json.dumps({"executions": [old]}), encoding="utf-8",
    )
    (tmp_path / "executions.txt").write_text(
        f"2023 1 {transport.JOB} {canary_name} "
        f"{transport.expected_uri(2023, 1)}\n",
        encoding="utf-8",
    )
    current = [
        old,
        _execution_snapshot(canary_name, 2023, 1),
        _execution_snapshot(next_name, 2023, 2, "Unknown"),
    ]
    monkeypatch.setattr(transport, "_inventory", lambda: current)
    rows = transport.reconcile_execution_ledger()
    assert len(rows) == 2
    assert rows[-1][:4] == ["2023", "2", transport.JOB, next_name]


def test_exact_restore_requires_uid_then_replays_captured_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport, "OUT", tmp_path)
    before = _job()
    before["spec"]["template"]["spec"]["template"]["spec"]["containers"][0][
        "image"
    ] = "us-central1-docker.pkg.dev/example/old@sha256:" + "1" * 64
    (tmp_path / "job-before.json").write_text(
        json.dumps(before), encoding="utf-8",
    )
    (tmp_path / "job-before.export.yaml").write_text(
        "apiVersion: run.googleapis.com/v1\nkind: Job\n", encoding="utf-8",
    )
    (tmp_path / "terminal-failure.json").write_text("{}\n", encoding="utf-8")
    responses = iter([_job(), before])
    monkeypatch.setattr(transport, "_gcloud_json", lambda _args: next(responses))
    commands: list[list[str]] = []

    def fake_run(command, *, check=True):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, "{}", "")

    monkeypatch.setattr(transport, "_run", fake_run)
    transport.restore_shared_job("test-failure")
    assert commands[0][:5] == ["gcloud", "run", "jobs", "replace", str(
        tmp_path / "job-before.export.yaml"
    )]
    receipt = json.loads((tmp_path / "job-restoration.json").read_text())
    assert receipt["restored"] is True
    assert receipt["already_restored"] is False


def test_stable_restoration_rejects_spec_drift() -> None:
    before = _job()
    restored = _job()
    restored["spec"]["template"]["spec"]["parallelism"] = 2
    with pytest.raises(ValueError, match="restoration differs"):
        transport.validate_restored_job(before, restored)


def test_terminal_prior_build_cannot_authorize_kickoff_amendment() -> None:
    metadata_path = ROOT / (
        "reports/a7-select-ladder-preflight-runs/"
        "20260820-a7-select-ladder-phase-s-incumbent-v1/smoke/"
        "build-metadata.json"
    )
    with pytest.raises(ValueError, match="full-runtime build authority differs"):
        transport.validate_build(
            json.loads(metadata_path.read_text(encoding="utf-8"))
        )


def test_harvest_terminal_failure_restores_shared_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(transport, "OUT", tmp_path)
    (tmp_path / "grid-release.json").write_text("{}\n", encoding="utf-8")
    rows = [
        [str(season), str(week), transport.JOB, f"{transport.JOB}-{season}-{week}",
         transport.expected_uri(season, week)]
        for season, week in transport.ALL_CELLS
    ]
    monkeypatch.setattr(transport, "_validate_local_sources", lambda: None)
    monkeypatch.setattr(transport, "reconcile_execution_ledger", lambda: rows)

    def describe(execution: str):
        season, week = map(int, execution.rsplit("-", 2)[-2:])
        status = "False" if (season, week) == (2025, 18) else "True"
        return _execution_snapshot(execution, season, week, status)

    monkeypatch.setattr(transport, "_describe_execution", describe)
    restored: list[str] = []
    monkeypatch.setattr(
        transport, "restore_shared_job", lambda reason: restored.append(reason),
    )
    with pytest.raises(ValueError, match="terminal execution failures"):
        transport.harvest_grid()
    assert restored == ["grid-terminal-failure"]
    failure = json.loads((tmp_path / "terminal-failure.json").read_text())
    assert failure["phase"] == "harvest"


def test_successful_harvest_restores_before_terminal_completion() -> None:
    source = inspect.getsource(transport.harvest_grid)
    harvest_receipt = source.index('OUT / "harvest-completion.json"')
    restoration = source.rindex('restore_shared_job("full-harvest-complete")')
    terminal = source.index('OUT / "completion.txt"', restoration)
    assert harvest_receipt < restoration < terminal
    assert "--if-generation-match=0" in inspect.getsource(
        transport._upload_report_create_once
    )
