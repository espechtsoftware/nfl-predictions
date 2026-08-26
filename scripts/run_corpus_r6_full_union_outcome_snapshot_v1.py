#!/usr/bin/env python3
"""Offline CLI for the R6 post-freeze outcome-snapshot contracts.

The CLI intentionally has no GCS or BigQuery client.  Exact predecessor
objects are supplied through a local content-addressed directory containing
``<sha256>.json`` files.  A production transport can call the pure module with
its own generation-pinned reader after the structural root is complete.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import os
from pathlib import Path
import tempfile
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as snapshot


_JSON_SUFFIX: Final = ".json"


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_components(path: Path, *, label: str) -> None:
    absolute = _absolute_lexical(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} cannot contain a symlink component")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class _LocalExactReader:
    def __init__(self, root: Path) -> None:
        _reject_symlink_components(root, label="--object-store")
        retained = root.resolve(strict=True)
        if not retained.is_dir():
            raise ValueError("--object-store must be a real directory")
        self.root = retained

    def __call__(self, identity: object) -> bytes:
        normalized = batch.normalize_object_identity(
            identity, label="local exact-read identity"
        )
        path = self.root / f"{normalized['sha256']}{_JSON_SUFFIX}"
        if path.is_symlink():
            raise ValueError("content-addressed object path cannot be a symlink")
        resolved = path.resolve(strict=True)
        if resolved.parent != self.root or not resolved.is_file():
            raise ValueError("content-addressed object path differs")
        return resolved.read_bytes()


def _canonical_value(path: Path, *, label: str) -> object:
    raw = path.resolve(strict=True).read_bytes()
    return batch.parse_canonical_json_bytes(raw, label=label)


def _write_create_once(
    path: Path,
    value: object,
    *,
    _link: Callable[..., object] = os.link,
    _after_link: Callable[[], None] | None = None,
) -> None:
    """Durably install canonical bytes without following or replacing links."""
    target = _absolute_lexical(path)
    _reject_symlink_components(target, label="output path")
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError("output parent must already exist")
    if target.exists():
        raise FileExistsError(target)
    raw = snapshot.canonical_json_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor_open = False
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _reject_symlink_components(target, label="output path")
        if target.exists():
            raise FileExistsError(target)
        _link(temporary, target, follow_symlinks=False)
        if _after_link is not None:
            _after_link()
    finally:
        if descriptor_open:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        finally:
            _fsync_directory(parent)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the R6 full-union post-freeze outcome contracts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    project = subparsers.add_parser(
        "project-keys", help="derive the outcome-blind key projection"
    )
    project.add_argument("--object-store", type=Path, required=True)
    project.add_argument("--panel-freeze-identity", type=Path, required=True)
    project.add_argument("--output", type=Path, required=True)

    smoke = subparsers.add_parser(
        "build-smoke-receipt",
        help="prove the explicit actual root/projection without outcomes",
    )
    smoke.add_argument("--object-store", type=Path, required=True)
    smoke.add_argument(
        "--expected-panel-freeze-identity", type=Path, required=True
    )
    smoke.add_argument("--projection", type=Path, required=True)
    smoke.add_argument(
        "--expected-outcome-key-projection-identity", type=Path, required=True
    )
    smoke.add_argument(
        "--expected-reviewed-source-commit-sha", required=True
    )
    smoke.add_argument("--expected-runtime-immutable-image", required=True)
    smoke.add_argument("--snapshot-module-sha256", required=True)
    smoke.add_argument("--snapshot-cli-sha256", required=True)
    smoke.add_argument("--snapshot-test-sha256", required=True)
    smoke.add_argument("--snapshot-cli-test-sha256", required=True)
    smoke.add_argument("--output", type=Path, required=True)

    validate_smoke = subparsers.add_parser(
        "validate-smoke-receipt",
        help="replay a smoke receipt against explicit expected identities",
    )
    validate_smoke.add_argument("--object-store", type=Path, required=True)
    validate_smoke.add_argument("--smoke-receipt", type=Path, required=True)
    validate_smoke.add_argument(
        "--smoke-receipt-identity", type=Path, required=True
    )
    validate_smoke.add_argument(
        "--expected-panel-freeze-identity", type=Path, required=True
    )
    validate_smoke.add_argument("--projection", type=Path, required=True)
    validate_smoke.add_argument(
        "--expected-outcome-key-projection-identity", type=Path, required=True
    )
    validate_smoke.add_argument(
        "--expected-reviewed-source-commit-sha", required=True
    )
    validate_smoke.add_argument(
        "--expected-runtime-immutable-image", required=True
    )
    validate_smoke.add_argument("--snapshot-module-sha256", required=True)
    validate_smoke.add_argument("--snapshot-cli-sha256", required=True)
    validate_smoke.add_argument("--snapshot-test-sha256", required=True)
    validate_smoke.add_argument("--snapshot-cli-test-sha256", required=True)
    validate_smoke.add_argument("--output", type=Path, required=True)

    source = subparsers.add_parser(
        "build-source", help="bind exact integer-micro rows to the projection"
    )
    source.add_argument("--object-store", type=Path, required=True)
    source.add_argument("--projection", type=Path, required=True)
    source.add_argument("--projection-identity", type=Path, required=True)
    source.add_argument(
        "--registered-integer-micro-rows", type=Path, required=True
    )
    source.add_argument("--output", type=Path, required=True)

    build = subparsers.add_parser(
        "build-snapshot", help="derive the reusable snapshot from its source"
    )
    build.add_argument("--object-store", type=Path, required=True)
    build.add_argument("--projection", type=Path, required=True)
    build.add_argument("--projection-identity", type=Path, required=True)
    build.add_argument("--realized-source", type=Path, required=True)
    build.add_argument("--realized-source-identity", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    reader = _LocalExactReader(args.object_store)
    if args.command == "project-keys":
        result = snapshot.project_required_outcome_keys_v1(
            panel_freeze_identity=_canonical_value(
                args.panel_freeze_identity, label="panel-freeze identity"
            ),
            read_exact=reader,
        )
    elif args.command == "build-smoke-receipt":
        result = snapshot.build_actual_root_smoke_receipt_v1(
            panel_freeze_identity=_canonical_value(
                args.expected_panel_freeze_identity,
                label="explicit expected panel-freeze identity",
            ),
            outcome_key_projection=_canonical_value(
                args.projection, label="outcome-key projection"
            ),
            outcome_key_projection_identity=_canonical_value(
                args.expected_outcome_key_projection_identity,
                label="explicit expected projection identity",
            ),
            expected_reviewed_source_commit_sha=(
                args.expected_reviewed_source_commit_sha
            ),
            expected_runtime_immutable_image=(
                args.expected_runtime_immutable_image
            ),
            snapshot_module_sha256=args.snapshot_module_sha256,
            snapshot_cli_sha256=args.snapshot_cli_sha256,
            snapshot_test_sha256=args.snapshot_test_sha256,
            snapshot_cli_test_sha256=args.snapshot_cli_test_sha256,
            read_exact=reader,
        )
    elif args.command == "validate-smoke-receipt":
        result, _ = snapshot.validate_actual_root_smoke_receipt_v1(
            _canonical_value(
                args.smoke_receipt, label="actual-root smoke receipt"
            ),
            identity=_canonical_value(
                args.smoke_receipt_identity,
                label="actual-root smoke receipt identity",
            ),
            expected_panel_freeze_identity=_canonical_value(
                args.expected_panel_freeze_identity,
                label="explicit expected panel-freeze identity",
            ),
            outcome_key_projection=_canonical_value(
                args.projection, label="outcome-key projection"
            ),
            expected_outcome_key_projection_identity=_canonical_value(
                args.expected_outcome_key_projection_identity,
                label="explicit expected projection identity",
            ),
            expected_reviewed_source_commit_sha=(
                args.expected_reviewed_source_commit_sha
            ),
            expected_runtime_immutable_image=(
                args.expected_runtime_immutable_image
            ),
            expected_snapshot_module_sha256=args.snapshot_module_sha256,
            expected_snapshot_cli_sha256=args.snapshot_cli_sha256,
            expected_snapshot_test_sha256=args.snapshot_test_sha256,
            expected_snapshot_cli_test_sha256=args.snapshot_cli_test_sha256,
            read_exact=reader,
        )
    elif args.command == "build-source":
        result = snapshot.build_realized_source_from_registered_rows_v1(
            outcome_key_projection=_canonical_value(
                args.projection, label="outcome-key projection"
            ),
            outcome_key_projection_identity=_canonical_value(
                args.projection_identity, label="outcome-key projection identity"
            ),
            registered_integer_micro_rows=_canonical_value(
                args.registered_integer_micro_rows,
                label="registered integer-micro rows",
            ),
            read_exact=reader,
        )
    elif args.command == "build-snapshot":
        result = snapshot.build_outcome_snapshot_v1(
            outcome_key_projection=_canonical_value(
                args.projection, label="outcome-key projection"
            ),
            outcome_key_projection_identity=_canonical_value(
                args.projection_identity, label="outcome-key projection identity"
            ),
            realized_source=_canonical_value(
                args.realized_source, label="realized source"
            ),
            realized_source_identity=_canonical_value(
                args.realized_source_identity, label="realized source identity"
            ),
            read_exact=reader,
        )
    else:  # pragma: no cover - argparse owns the closed command set
        raise AssertionError("unreachable command")
    _write_create_once(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
