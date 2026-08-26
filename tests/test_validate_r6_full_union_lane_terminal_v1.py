from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_r6_full_union_lane_terminal_v1.py"
SPEC = importlib.util.spec_from_file_location("r6_terminal", PATH)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _envelope(condition: str = "True") -> dict[str, object]:
    return {
        "metadata": {"name": "lane-job-run1", "labels": {"run.googleapis.com/job": "lane-job"}},
        "spec": {"taskCount": 28, "parallelism": 4, "template": {"spec": {
            "maxRetries": 0, "serviceAccountName": "svc@example.invalid",
            "timeoutSeconds": "7200",
            "containers": [{"image": "repo@sha256:" + "a" * 64,
                            "command": ["python"], "args": ["runner", "--offset", "0"],
                            "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                            "env": [
                                {"name": "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED", "value": "1"},
                                {"name": "R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE", "value": "repo@sha256:" + "a" * 64},
                            ]}],
        }}},
        "status": {"completionTime": "2026-08-26T15:00:00Z",
                   "conditions": [{"type": "Completed", "status": condition}],
                   "succeededCount": 28 if condition == "True" else 27,
                   "failedCount": 0 if condition == "True" else 1,
                   "runningCount": 0},
    }


def _build(envelope: dict[str, object]) -> dict[str, object]:
    return cli.build_receipt(
        envelope, lane="lane-a", execution="lane-job-run1", job="lane-job",
        image="repo@sha256:" + "a" * 64, code_sha="b" * 40,
        service_account="svc@example.invalid",
        task_count=28, parallelism=4, expected_args=["runner", "--offset", "0"],
    )


def test_success_and_terminal_failure_are_distinguished_for_repair() -> None:
    assert _build(_envelope())["terminal_success"] is True
    failed = _build(_envelope("False"))
    assert failed["terminal_success"] is False
    assert failed["completed_condition"] == "False"


def test_unknown_or_execution_splice_fails_closed() -> None:
    with pytest.raises(ValueError, match="contract differs"):
        _build(_envelope("Unknown"))
    changed = _envelope()
    changed["spec"]["template"]["spec"]["containers"][0]["args"][-1] = "28"  # type: ignore[index]
    with pytest.raises(ValueError, match="contract differs"):
        _build(changed)
    omitted = _envelope()
    del omitted["status"]["succeededCount"]  # type: ignore[index]
    with pytest.raises(ValueError, match="contract differs"):
        _build(omitted)


def test_atomic_create_equal_collision_partial_symlink_and_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "receipt.json"
    cli._write_equal(target, b"exact")
    cli._write_equal(target, b"exact")
    with pytest.raises(ValueError, match="collision"):
        cli._write_equal(target, b"different")
    partial = tmp_path / "partial.json"
    partial.write_bytes(b"exa")
    with pytest.raises(ValueError, match="collision"):
        cli._write_equal(partial, b"exact")
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(target)
    with pytest.raises(ValueError, match="collision"):
        cli._write_equal(symlink, b"exact")

    raced = tmp_path / "raced.json"
    original_link = cli.os.link
    fired = False

    def race_link(*args: object, **kwargs: object) -> None:
        nonlocal fired
        if not fired and kwargs.get("dir_fd") is not None:
            fired = True
            raced.write_bytes(b"exact")
            raise FileExistsError()
        original_link(*args, **kwargs)

    monkeypatch.setattr(cli.os, "link", race_link)
    cli._write_equal(raced, b"exact")


@pytest.mark.parametrize("failure", ["write", "fsync"])
def test_failed_create_removes_only_partial_and_clean_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    target = tmp_path / f"{failure}.json"
    original = getattr(cli.os, failure)

    def explode(*args: object, **kwargs: object) -> object:
        raise OSError(f"forced {failure}")

    monkeypatch.setattr(cli.os, failure, explode)
    with pytest.raises(OSError, match=f"forced {failure}"):
        cli._write_equal(target, b"complete")
    assert not target.exists()
    monkeypatch.setattr(cli.os, failure, original)
    cli._write_equal(target, b"complete")
    assert target.read_bytes() == b"complete"


def test_existing_compare_rejects_raced_inode_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "receipt.json"
    target.write_bytes(b"exact")
    original_stat = cli.os.stat
    fired = False

    def replacing_stat(*args: object, **kwargs: object) -> object:
        nonlocal fired
        if not fired and kwargs.get("dir_fd") is not None:
            fired = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"exact")
            replacement.replace(target)
        return original_stat(*args, **kwargs)

    monkeypatch.setattr(cli.os, "stat", replacing_stat)
    with pytest.raises(ValueError, match="collision"):
        cli._write_equal(target, b"exact")


def test_directory_is_fsynced_and_require_success_publishes_nothing_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original_fsync = cli.os.fsync

    def observed_fsync(descriptor: int) -> None:
        calls.append(descriptor)
        original_fsync(descriptor)

    monkeypatch.setattr(cli.os, "fsync", observed_fsync)
    target = tmp_path / "durable.json"
    cli._write_equal(target, b"exact")
    assert len(calls) >= 3  # file, directory after link, directory after temp unlink

    envelope = tmp_path / "failed-envelope.json"
    envelope.write_text(__import__("json").dumps(_envelope("False")))
    receipt = tmp_path / "must-not-exist.json"
    argv = [
        "--envelope", str(envelope), "--receipt", str(receipt),
        "--lane", "lane-a", "--execution", "lane-job-run1",
        "--job", "lane-job", "--image", "repo@sha256:" + "a" * 64,
        "--code-sha", "b" * 40, "--service-account", "svc@example.invalid",
        "--task-count", "28", "--parallelism", "4",
        "--expected-args-json", '["runner","--offset","0"]',
        "--require-success",
    ]
    with pytest.raises(ValueError, match="successful terminal"):
        cli.main(argv)
    assert not receipt.exists()
