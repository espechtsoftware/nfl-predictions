from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resume_2026_production_schedulers",
    ROOT / "scripts" / "resume_2026_production_schedulers.py",
)
assert SPEC and SPEC.loader
resume = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resume)


def test_receipt_must_match_committed_copy_and_pushed_head(tmp_path, monkeypatch):
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"pass": true}\n', encoding="utf-8")
    commands = []

    def fake_run(command, *, cwd):
        commands.append(command)
        if command[:2] == ["git", "show"]:
            return SimpleNamespace(stdout=receipt.read_text(encoding="utf-8"))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(resume, "_run", fake_run)
    resume.verify_receipt_in_pushed_main(tmp_path, receipt)
    assert commands == [
        ["git", "show", "HEAD:receipt.json"],
        ["git", "fetch", "origin", "main"],
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"],
        ["git", "show", "origin/main:receipt.json"],
    ]


def test_receipt_byte_drift_fails_before_fetch(tmp_path, monkeypatch):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("local\n", encoding="utf-8")
    commands = []

    def fake_run(command, *, cwd):
        commands.append(command)
        return SimpleNamespace(stdout="committed\n")

    monkeypatch.setattr(resume, "_run", fake_run)
    with pytest.raises(RuntimeError, match="differs"):
        resume.verify_receipt_in_pushed_main(tmp_path, receipt)
    assert len(commands) == 1


def test_receipt_must_match_pushed_origin_main_bytes(tmp_path, monkeypatch):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("local\n", encoding="utf-8")
    commands = []

    def fake_run(command, *, cwd):
        commands.append(command)
        if command[:2] == ["git", "show"]:
            if command[2].startswith("origin/main:"):
                return SimpleNamespace(stdout="changed remotely\n")
            return SimpleNamespace(stdout="local\n")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(resume, "_run", fake_run)
    with pytest.raises(RuntimeError, match="pushed origin/main"):
        resume.verify_receipt_in_pushed_main(tmp_path, receipt)
    assert commands[-1] == ["git", "show", "origin/main:receipt.json"]


def test_scheduler_inventory_is_exact_and_unique():
    assert len(resume.SCHEDULERS) == 27
    assert len(set(resume.SCHEDULERS)) == 27
    assert set(resume.SCHEDULERS) == set(resume.SCHEDULER_CONTRACTS)
    assert "s-features" in resume.SCHEDULERS
    assert "s-project-su" in resume.SCHEDULERS
    assert "s-shadow-archetype-paired-early" in resume.SCHEDULERS
    assert "s-shadow-archetype-paired-late" in resume.SCHEDULERS
    assert "s-tabpfn-sis-pass-tail-control" in resume.SCHEDULERS
    assert "s-tabpfn-sis-pass-tail-treatment" in resume.SCHEDULERS
    assert "s-shadow-sis-pass-tail-paired" in resume.SCHEDULERS


def _description(scheduler):
    job, schedule = resume.SCHEDULER_CONTRACTS[scheduler]
    return {
        "name": (
            f"projects/{resume.PROJECT}/locations/{resume.REGION}/jobs/{scheduler}"
        ),
        "state": "PAUSED",
        "schedule": schedule,
        "timeZone": "America/Chicago",
        "httpTarget": {
            "uri": resume._target_uri(job),
            "httpMethod": "POST",
            "oauthToken": {
                "serviceAccountEmail": resume.SCHEDULER_SERVICE_ACCOUNT,
            },
        },
    }


def test_scheduler_contracts_freeze_tracked_jobs_and_cadences():
    assert resume.SCHEDULER_CONTRACTS == {
        "s-nflverse": ("ingest-nflverse", "0 5 * * *"),
        "s-features": ("build-features", "30 6 * * 2"),
        "s-features-route": ("build-features", "30 6 * * 4"),
        "s-train": ("train-weekly", "30 7 * * 2"),
        "s-train-k1": ("train-weekly-k1", "30 8 * * 2"),
        "s-train-k1-role": ("train-weekly-k1-role", "45 8 * * 2"),
        "s-train-k1-route": ("train-weekly-k1-route", "30 7 * * 4"),
        "s-train-k1-route-role": ("train-weekly-k1-route-role", "0 8 * * 4"),
        "s-project-tu": ("project-slate", "30 9 * * 2"),
        "s-project-su": ("project-slate", "0 6-11 * * 7"),
        "s-shadow-k1-early": ("shadow-k1", "30 10 * * 7"),
        "s-shadow-k1-late": ("shadow-k1", "20 11 * * 7"),
        "s-shadow-k1-nofloor-early": ("shadow-k1-nofloor", "30 10 * * 7"),
        "s-shadow-k1-nofloor-late": ("shadow-k1-nofloor", "20 11 * * 7"),
        "s-shadow-k3-early": ("shadow-k3", "30 10 * * 7"),
        "s-shadow-k3-late": ("shadow-k3", "20 11 * * 7"),
        "s-shadow-k1-roleunion-early": ("shadow-k1-roleunion", "20 10 * * 7"),
        "s-shadow-k1-roleunion-late": ("shadow-k1-roleunion", "10 11 * * 7"),
        "s-shadow-k1-route-roleunion-early": (
            "shadow-k1-route-roleunion", "20 10 * * 7"
        ),
        "s-shadow-k1-route-roleunion-late": (
            "shadow-k1-route-roleunion", "10 11 * * 7"
        ),
        "s-shadow-archetype-paired-early": (
            "shadow-archetype-paired", "15 9 * * 7"
        ),
        "s-shadow-archetype-paired-late": (
            "shadow-archetype-paired", "30 10 * * 7"
        ),
        "s-tabpfn-sis-pass-tail-control": (
            "tabpfn-sis-pass-tail-live-control", "15 9 * * 4"
        ),
        "s-tabpfn-sis-pass-tail-treatment": (
            "tabpfn-sis-pass-tail-live-treatment", "20 9 * * 4"
        ),
        "s-shadow-sis-pass-tail-paired": (
            "shadow-sis-pass-tail-paired", "0 6 * * 7"
        ),
        "s-freeze-tail-early": ("freeze-tail-early", "5 11 * * 7"),
        "s-freeze-tail-late": ("freeze-tail-late", "50 11 * * 7"),
    }


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("name", "projects/p/locations/r/jobs/wrong", "name"),
        ("state", "ENABLED", "state"),
        ("schedule", "0 0 * * *", "schedule"),
        ("timeZone", "UTC", "timeZone"),
        ("uri", "https://example.invalid/run", "uri"),
        ("httpMethod", "GET", "httpMethod"),
        ("oauthServiceAccount", "other@example.com", "oauthServiceAccount"),
    ],
)
def test_scheduler_contract_fails_closed_on_any_drift(field, value, match):
    scheduler = "s-project-su"
    description = _description(scheduler)
    if field in {"uri", "httpMethod"}:
        description["httpTarget"][field] = value
    elif field == "oauthServiceAccount":
        description["httpTarget"]["oauthToken"]["serviceAccountEmail"] = value
    else:
        description[field] = value
    with pytest.raises(RuntimeError, match=match):
        resume.verify_scheduler_contract(scheduler, description)


@pytest.mark.parametrize("body", ["", None, "e30="])
def test_scheduler_contract_rejects_any_present_http_body(body):
    scheduler = "s-project-su"
    description = _description(scheduler)
    description["httpTarget"]["body"] = body
    with pytest.raises(RuntimeError, match="bodyPresent"):
        resume.verify_scheduler_contract(scheduler, description)


def test_preflight_describes_and_validates_all_before_resume(monkeypatch, tmp_path):
    commands = []

    def fake_run(command, *, cwd):
        commands.append(command)
        scheduler = command[4]
        return SimpleNamespace(stdout=json.dumps(_description(scheduler)))

    monkeypatch.setattr(resume, "_run", fake_run)
    resume.preflight_scheduler_contracts(tmp_path)
    assert len(commands) == 27
    assert all(command[3] == "describe" for command in commands)
    assert [command[4] for command in commands] == list(resume.SCHEDULERS)


def test_preflight_drift_fails_without_any_resume_mutation(monkeypatch, tmp_path):
    commands = []

    def fake_run(command, *, cwd):
        commands.append(command)
        scheduler = command[4]
        description = _description(scheduler)
        if scheduler == "s-shadow-k3-late":
            description["state"] = "ENABLED"
        return SimpleNamespace(stdout=json.dumps(description))

    monkeypatch.setattr(resume, "_run", fake_run)
    with pytest.raises(RuntimeError, match="s-shadow-k3-late"):
        resume.preflight_scheduler_contracts(tmp_path)
    assert commands
    assert all("resume" not in command for command in commands)


def test_cleanup_preflight_command_pairs_both_manifests_and_shas(tmp_path):
    cleanup = tmp_path / "cleanup.py"
    manifests = [tmp_path / "original.json", tmp_path / "repair4.json"]
    receipt = tmp_path / "receipt.json"
    command = resume._cleanup_preflight_command(
        cleanup, manifests, ["a" * 64, "b" * 64], receipt
    )
    assert command == [
        resume.sys.executable,
        str(cleanup),
        "--manifest", str(manifests[0]),
        "--confirm-manifest-sha", "a" * 64,
        "--manifest", str(manifests[1]),
        "--confirm-manifest-sha", "b" * 64,
        "--receipt", str(receipt),
        "--verify-only",
    ]


class _SchedulerStateMachine:
    def __init__(
        self,
        *,
        fail_resume_at=None,
        fail_pause_for=None,
        sticky_pause_for=None,
        sticky_resume_for=None,
    ):
        self.states = {scheduler: "PAUSED" for scheduler in resume.SCHEDULERS}
        self.fail_resume_at = fail_resume_at
        self.fail_pause_for = fail_pause_for
        self.sticky_pause_for = sticky_pause_for
        self.sticky_resume_for = sticky_resume_for
        self.resume_calls = []
        self.pause_calls = []
        self.describe_calls = []

    def run(self, command, *, cwd):
        action = command[3]
        scheduler = command[4]
        if action == "describe":
            self.describe_calls.append(scheduler)
            description = _description(scheduler)
            description["state"] = self.states[scheduler]
            return SimpleNamespace(stdout=json.dumps(description))
        if action == "resume":
            call_index = len(self.resume_calls)
            self.resume_calls.append(scheduler)
            if scheduler != self.sticky_resume_for:
                self.states[scheduler] = "ENABLED"
            if call_index == self.fail_resume_at:
                raise resume.subprocess.CalledProcessError(1, command)
            return SimpleNamespace(stdout="")
        if action == "pause":
            self.pause_calls.append(scheduler)
            if scheduler == self.fail_pause_for:
                raise resume.subprocess.CalledProcessError(1, command)
            if scheduler != self.sticky_pause_for:
                self.states[scheduler] = "PAUSED"
            return SimpleNamespace(stdout="")
        raise AssertionError(f"unexpected command: {command}")


def test_mid_loop_resume_failure_rolls_back_attempted_and_verifies_all_paused(
    monkeypatch, tmp_path
):
    failure_index = 6
    cloud = _SchedulerStateMachine(fail_resume_at=failure_index)
    monkeypatch.setattr(resume, "_run", cloud.run)

    with pytest.raises(RuntimeError, match="restored all 27.*PAUSED"):
        resume.resume_scheduler_contracts(tmp_path)

    attempted = list(resume.SCHEDULERS[: failure_index + 1])
    assert cloud.resume_calls == attempted
    assert cloud.pause_calls == list(reversed(attempted))
    assert cloud.describe_calls == list(resume.SCHEDULERS)
    assert set(cloud.states.values()) == {"PAUSED"}


def test_resume_failure_reports_rollback_command_and_postcondition_failure(
    monkeypatch, tmp_path
):
    failure_index = 4
    rollback_failure = resume.SCHEDULERS[2]
    cloud = _SchedulerStateMachine(
        fail_resume_at=failure_index,
        fail_pause_for=rollback_failure,
    )
    monkeypatch.setattr(resume, "_run", cloud.run)

    with pytest.raises(RuntimeError, match="could not prove atomic PAUSED") as exc:
        resume.resume_scheduler_contracts(tmp_path)

    assert f"pause {rollback_failure}" in str(exc.value)
    assert "PAUSED postcondition" in str(exc.value)
    assert cloud.pause_calls == list(
        reversed(resume.SCHEDULERS[: failure_index + 1])
    )
    assert cloud.describe_calls == list(resume.SCHEDULERS)
    assert cloud.states[rollback_failure] == "ENABLED"


def test_resume_failure_rejects_false_successful_rollback_postcondition(
    monkeypatch, tmp_path
):
    failure_index = 3
    sticky = resume.SCHEDULERS[1]
    cloud = _SchedulerStateMachine(
        fail_resume_at=failure_index,
        sticky_pause_for=sticky,
    )
    monkeypatch.setattr(resume, "_run", cloud.run)

    with pytest.raises(RuntimeError, match="PAUSED postcondition"):
        resume.resume_scheduler_contracts(tmp_path)

    assert cloud.describe_calls == list(resume.SCHEDULERS)
    assert cloud.states[sticky] == "ENABLED"


def test_resume_success_requires_all_27_enabled(monkeypatch, tmp_path):
    cloud = _SchedulerStateMachine()
    monkeypatch.setattr(resume, "_run", cloud.run)

    resume.resume_scheduler_contracts(tmp_path)

    assert cloud.resume_calls == list(resume.SCHEDULERS)
    assert cloud.pause_calls == []
    assert cloud.describe_calls == list(resume.SCHEDULERS)
    assert set(cloud.states.values()) == {"ENABLED"}


def test_failed_enabled_postcondition_rolls_every_scheduler_back(
    monkeypatch, tmp_path
):
    sticky = resume.SCHEDULERS[-1]
    cloud = _SchedulerStateMachine(sticky_resume_for=sticky)
    monkeypatch.setattr(resume, "_run", cloud.run)

    with pytest.raises(RuntimeError, match="restored all 27.*PAUSED"):
        resume.resume_scheduler_contracts(tmp_path)

    assert cloud.resume_calls == list(resume.SCHEDULERS)
    assert cloud.pause_calls == list(reversed(resume.SCHEDULERS))
    assert cloud.describe_calls == list(resume.SCHEDULERS) * 2
    assert set(cloud.states.values()) == {"PAUSED"}
