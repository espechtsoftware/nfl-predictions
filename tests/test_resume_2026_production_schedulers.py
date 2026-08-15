from __future__ import annotations

import importlib.util
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


def test_scheduler_inventory_is_exact_and_unique():
    assert len(resume.SCHEDULERS) == 27
    assert len(set(resume.SCHEDULERS)) == 27
    assert "s-features" in resume.SCHEDULERS
    assert "s-project-su" in resume.SCHEDULERS
    assert "s-shadow-archetype-paired-early" in resume.SCHEDULERS
    assert "s-shadow-archetype-paired-late" in resume.SCHEDULERS
    assert "s-tabpfn-sis-pass-tail-control" in resume.SCHEDULERS
    assert "s-tabpfn-sis-pass-tail-treatment" in resume.SCHEDULERS
    assert "s-shadow-sis-pass-tail-paired" in resume.SCHEDULERS
