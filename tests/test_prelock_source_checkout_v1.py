from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nfl_dfs.inference.prospective_prelock_lineage_shadow_v2 import (
    ProspectivePrelockLineageShadowV2Error,
    _validate_clean_source_checkout_v1,
    _validate_runtime_source_binding_v1,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def test_source_receipt_requires_exact_commit_tracked_and_clean_paths(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "lineage@example.invalid")
    _git(tmp_path, "config", "user.name", "Lineage Test")
    source = tmp_path / "tracked.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.py")
    _git(tmp_path, "commit", "-q", "-m", "fixture")
    head = _git(tmp_path, "rev-parse", "HEAD")

    _validate_clean_source_checkout_v1(
        tmp_path,
        expected_commit=head,
        required_paths=["tracked.py"],
    )

    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="globally clean",
    ):
        _validate_clean_source_checkout_v1(
            tmp_path,
            expected_commit=head,
            required_paths=["tracked.py"],
        )

    source.write_text("VALUE = 1\n", encoding="utf-8")
    untracked = tmp_path / "untracked.py"
    untracked.write_text("VALUE = 3\n", encoding="utf-8")
    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="globally clean",
    ):
        _validate_clean_source_checkout_v1(
            tmp_path,
            expected_commit=head,
            required_paths=["tracked.py"],
        )
    untracked.unlink()

    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="source commit differs",
    ):
        _validate_clean_source_checkout_v1(
            tmp_path,
            expected_commit="f" * 40,
            required_paths=["tracked.py"],
        )


def test_runtime_image_uses_embedded_revision_when_git_is_absent(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "tracked.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    commit = "a" * 40
    monkeypatch.setenv("IMAGE_SOURCE_COMMIT_SHA", commit)

    assert (
        _validate_runtime_source_binding_v1(
            tmp_path,
            expected_commit=commit,
            required_paths=["tracked.py"],
        )
        == "immutable-image-embedded-revision"
    )
    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="image revision differs",
    ):
        _validate_runtime_source_binding_v1(
            tmp_path,
            expected_commit="b" * 40,
            required_paths=["tracked.py"],
        )


def test_runtime_image_does_not_require_git_executable(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "tracked.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    commit = "c" * 40
    monkeypatch.setenv("IMAGE_SOURCE_COMMIT_SHA", commit)

    def _missing_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _missing_git)
    assert (
        _validate_runtime_source_binding_v1(
            tmp_path,
            expected_commit=commit,
            required_paths=["tracked.py"],
        )
        == "immutable-image-embedded-revision"
    )
