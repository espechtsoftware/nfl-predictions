#!/usr/bin/env python3
"""Freeze or validate the Git-independent canonical R6-v2 image receipt."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import subprocess
import sys

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_release_v2 as release,
)


_COMMIT = re.compile(r"[0-9a-f]{40}")


class BuildCorpusR6V2RuntimeAuthorityV1Error(RuntimeError):
    """The immutable R6-v2 runtime receipt could not be proven."""


def _fail(message: str) -> None:
    raise BuildCorpusR6V2RuntimeAuthorityV1Error(message)


def _absolute_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        _fail("repository root must be absolute")
    try:
        root = path.resolve(strict=True)
    except OSError as exc:
        raise BuildCorpusR6V2RuntimeAuthorityV1Error(
            "repository root does not exist"
        ) from exc
    if not root.is_dir():
        _fail("repository root must be a directory")
    return root


def _absolute_file(value: str, *, label: str, must_exist: bool) -> Path:
    path = Path(value)
    if not path.is_absolute():
        _fail(f"{label} path must be absolute")
    if must_exist:
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise BuildCorpusR6V2RuntimeAuthorityV1Error(
                f"{label} does not exist"
            ) from exc
        if not resolved.is_file():
            _fail(f"{label} must be a file")
        return resolved
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise BuildCorpusR6V2RuntimeAuthorityV1Error(
            f"{label} parent does not exist"
        ) from exc
    if not parent.is_dir():
        _fail(f"{label} parent must be a directory")
    return parent / path.name


def _commit(value: str) -> str:
    if _COMMIT.fullmatch(value) is None:
        _fail("source commit must be one lowercase full Git commit")
    return value


def _git(
    repository_root: Path, arguments: Sequence[str], *, label: str,
) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BuildCorpusR6V2RuntimeAuthorityV1Error(
            f"build-time Git {label} failed"
        ) from exc
    return completed.stdout


def _git_head(repository_root: Path) -> str:
    try:
        return _git(
            repository_root, ["rev-parse", "--verify", "HEAD"], label="HEAD"
        ).decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise BuildCorpusR6V2RuntimeAuthorityV1Error(
            "build-time Git HEAD is not ASCII"
        ) from exc


def _git_blob(
    repository_root: Path, commit: str, relative_path: str,
) -> bytes:
    return _git(
        repository_root,
        ["show", f"{commit}:{relative_path}"],
        label=f"blob {relative_path}",
    )


def _git_status(
    repository_root: Path, relative_paths: Sequence[str],
) -> bytes:
    return _git(
        repository_root,
        [
            "status", "--porcelain=v1", "--untracked-files=all", "--",
            *relative_paths,
        ],
        label="status",
    )


def _load_receipt(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BuildCorpusR6V2RuntimeAuthorityV1Error(
            "cannot read embedded runtime authority receipt"
        ) from exc
    canonical = raw
    if not canonical:
        _fail("embedded runtime authority receipt framing differs")
    try:
        value = batch.parse_canonical_json_bytes(
            canonical, label="embedded runtime authority receipt"
        )
    except batch.CorpusParametricBatchError as exc:
        raise BuildCorpusR6V2RuntimeAuthorityV1Error(str(exc)) from exc
    if not isinstance(value, Mapping):
        _fail("embedded runtime authority receipt must be an object")
    return release.validate_embedded_runtime_authority_v1(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze a clean tracked source receipt before image build or "
            "validate its on-image bytes without Git"
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--repository-root", required=True)
    freeze.add_argument("--source-commit", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument(
        "--execute", action="store_true",
        help="explicitly authorize create-once local receipt publication",
    )
    validate = commands.add_parser("validate")
    validate.add_argument("--repository-root", required=True)
    validate.add_argument("--source-commit", required=True)
    validate.add_argument("--receipt", required=True)
    return parser


def run(argv: Sequence[str]) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    repository_root = _absolute_root(args.repository_root)
    source_commit = _commit(args.source_commit)
    if args.command == "freeze":
        if args.execute is not True:
            _fail("freeze requires explicit --execute")
        output = _absolute_file(
            args.output, label="receipt output", must_exist=False
        )
        receipt = release.build_embedded_runtime_authority_v1(
            repository_root=repository_root,
            source_commit_sha=source_commit,
            git_head=_git_head,
            git_blob=_git_blob,
            git_status=_git_status,
        )
        raw = batch.canonical_json_bytes(receipt)
        try:
            with output.open("xb") as stream:
                stream.write(raw)
        except FileExistsError as exc:
            raise BuildCorpusR6V2RuntimeAuthorityV1Error(
                "receipt output already exists"
            ) from exc
        except OSError as exc:
            raise BuildCorpusR6V2RuntimeAuthorityV1Error(
                "cannot publish embedded runtime authority receipt"
            ) from exc
        return {
            "command": "freeze",
            "receipt_path": str(output),
            "source_commit_sha": source_commit,
            "runtime_authority_sha256": receipt["runtime_authority_sha256"],
        }
    receipt_path = _absolute_file(
        args.receipt, label="receipt", must_exist=True
    )
    receipt = _load_receipt(receipt_path)
    if receipt["source_commit_sha"] != source_commit:
        _fail("receipt source commit differs from requested image commit")
    release.validate_runtime_files_v1(
        repository_root=repository_root,
        embedded_runtime_authority=receipt,
    )
    return {
        "command": "validate",
        "receipt_path": str(receipt_path),
        "source_commit_sha": source_commit,
        "runtime_authority_sha256": receipt["runtime_authority_sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    result = run(sys.argv[1:] if argv is None else argv)
    sys.stdout.buffer.write(batch.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
