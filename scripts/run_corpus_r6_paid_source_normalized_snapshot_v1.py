#!/usr/bin/env python3
"""Default-off producer for immutable normalized FP/SIS source manifests.

``build-request`` and ``validate`` are local-only.  ``task0`` runs exactly the
first fixed time-travel query and cannot publish.  ``publish`` requires that
task0 receipt and creates the twelve nonterminal objects plus root last.
``reopen`` is generation-pinned and read-only.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_paid_source_normalized_snapshot_v1 as snapshot,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source  # noqa: E402
import run_corpus_r6_matchup_seven_pack_capture_v1 as transport  # noqa: E402


TASK0_ENV: Final = "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0"
PUBLISH_ENV: Final = "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PUBLISH"
REOPEN_ENV: Final = "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_REOPEN"
ENABLE_VALUE: Final = "I_UNDERSTAND_RETROSPECTIVE_FP_SIS_SNAPSHOT_V1"
IMAGE_SOURCE_SHA_ENV: Final = "IMAGE_SOURCE_COMMIT_SHA"
MODULE_SHA_ENV: Final = "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_MODULE_SHA256"


class PaidSourceNormalizedSnapshotCliV1Error(RuntimeError):
    """The guarded normalized snapshot CLI failed closed."""


def _fail(message: str) -> None:
    raise PaidSourceNormalizedSnapshotCliV1Error(message)


class Task0ReadOnlyWarehouseViewV1:
    """Expose only one callable query surface to the task-0 core."""

    __slots__ = ("_query",)

    def __init__(self, warehouse: object) -> None:
        if not callable(warehouse):
            _fail("normalized snapshot task0 query runner differs")
        self._query = warehouse

    def __call__(self, spec: Mapping[str, object]) -> object:
        return self._query(spec)


def _require(mode: str, *, execute: bool, environment: Mapping[str, str]) -> None:
    variable = {"task0": TASK0_ENV, "publish": PUBLISH_ENV, "reopen": REOPEN_ENV}.get(
        mode
    )
    if execute is not True or variable is None or environment.get(variable) != ENABLE_VALUE:
        _fail(f"normalized snapshot {mode} is disabled")


def _code_identity(repository_root: Path) -> dict[str, str]:
    commit = transport._git_head(repository_root)
    status = transport._git_status(repository_root, [snapshot.MODULE_PATH])
    blob = transport._git_blob(repository_root, commit, snapshot.MODULE_PATH)
    current = (repository_root / snapshot.MODULE_PATH).read_bytes()
    if status != b"" or not current or current != blob:
        _fail("normalized snapshot projection code is not tracked-clean")
    return {
        "source_commit_sha": commit,
        "module_path": snapshot.MODULE_PATH,
        "module_sha256": sha256(current).hexdigest(),
    }


def _verify_request_code(
    request: Mapping[str, object], *, repository_root: Path,
    environment: Mapping[str, str],
) -> None:
    image_source_sha = environment.get(IMAGE_SOURCE_SHA_ENV)
    image_module_sha = environment.get(MODULE_SHA_ENV)
    if (image_source_sha is None) != (image_module_sha is None):
        _fail("normalized snapshot detached image code binding is incomplete")
    if image_source_sha is None:
        actual = _code_identity(repository_root)
    else:
        source_commit_path = repository_root / "SOURCE_COMMIT"
        try:
            source_commit_raw = source_commit_path.read_bytes()
            module_raw = (repository_root / snapshot.MODULE_PATH).read_bytes()
        except OSError as exc:
            raise PaidSourceNormalizedSnapshotCliV1Error(
                "normalized snapshot detached image code bytes are absent"
            ) from exc
        if (
            len(image_source_sha) != 40
            or any(character not in "0123456789abcdef" for character in image_source_sha)
            or len(image_module_sha) != 64
            or any(character not in "0123456789abcdef" for character in image_module_sha)
            or source_commit_raw != f"{image_source_sha}\n".encode("ascii")
            or sha256(module_raw).hexdigest() != image_module_sha
        ):
            _fail("normalized snapshot detached image code binding differs")
        actual = {
            "source_commit_sha": image_source_sha,
            "module_path": snapshot.MODULE_PATH,
            "module_sha256": image_module_sha,
        }
    if request.get("projection_code_identity") != actual:
        _fail("normalized snapshot request differs from current clean code")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    build = commands.add_parser("build-request")
    build.add_argument("--run-id", required=True)
    build.add_argument("--snapshot-at-utc", required=True)
    build.add_argument("--repository-root", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--request", type=Path, required=True)
    task0 = commands.add_parser("task0")
    task0.add_argument("--request", type=Path, required=True)
    task0.add_argument("--repository-root", required=True)
    task0.add_argument("--execute", action="store_true")
    publish = commands.add_parser("publish")
    publish.add_argument("--request", type=Path, required=True)
    publish.add_argument("--task0-receipt", type=Path, required=True)
    publish.add_argument("--repository-root", required=True)
    publish.add_argument("--execute", action="store_true")
    reopen = commands.add_parser("reopen")
    reopen.add_argument("--terminal-identity", type=Path, required=True)
    reopen.add_argument("--execute", action="store_true")
    return parser


def run(
    argv: Sequence[str] | None = None, *,
    environ: Mapping[str, str] | None = None,
    query_warehouse: object | None = None,
    store: object | None = None,
) -> dict[str, object]:
    args = _parser().parse_args(argv)
    environment = dict(os.environ if environ is None else environ)
    if args.mode == "build-request":
        root = transport._trusted_repository_root(args.repository_root)
        return snapshot.build_snapshot_request_v1(
            run_id=args.run_id,
            snapshot_at_utc=args.snapshot_at_utc,
            projection_code_identity=_code_identity(root),
        )
    if args.mode == "validate":
        return snapshot.validate_snapshot_request_v1(
            transport._read_canonical_json(args.request, label="snapshot request")
        )
    if args.mode in {"task0", "publish"}:
        _require(args.mode, execute=args.execute, environment=environment)
        request = snapshot.validate_snapshot_request_v1(
            transport._read_canonical_json(args.request, label="snapshot request")
        )
        root = transport._trusted_repository_root(args.repository_root)
        _verify_request_code(
            request, repository_root=root, environment=environment
        )
        warehouse = query_warehouse or transport.FixedBigQueryRunnerV1()
        if not callable(warehouse):
            _fail("normalized snapshot query runner differs")
        if args.mode == "task0":
            return snapshot.run_normalized_snapshot_task0_v1(
                request, query_warehouse=Task0ReadOnlyWarehouseViewV1(warehouse)
            )
        task0 = transport._read_canonical_json(
            args.task0_receipt, label="snapshot task0 receipt"
        )
        snapshot.validate_normalized_snapshot_task0_v1(
            task0, request_value=request
        )
        uris = sorted([
            *request["output_inventory"]["nonterminal_uris"],
            request["output_inventory"]["terminal_uri"],
        ])
        retained_store = store or transport._trusted_gcs_transport(
            expected_write_uris=uris
        )
        reader = getattr(retained_store, "read_exact", None)
        writer = getattr(retained_store, "publish_create_once", None)
        if not callable(reader) or not callable(writer):
            _fail("normalized snapshot store differs")
        return snapshot.publish_normalized_snapshot_v1(
            request,
            task0_receipt_value=task0,
            query_warehouse=warehouse,
            publish_create_once=writer,
            read_exact=reader,
        )
    _require("reopen", execute=args.execute, environment=environment)
    terminal_identity = transport._read_canonical_json(
        args.terminal_identity, label="snapshot terminal identity"
    )
    retained_store = store or transport._trusted_gcs_transport(
        expected_write_uris=[]
    )
    reader = getattr(retained_store, "read_exact", None)
    if not callable(reader):
        _fail("normalized snapshot reopen store differs")
    return snapshot.reopen_normalized_snapshot_v1(
        terminal_identity=terminal_identity, read_exact=reader
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (
        PaidSourceNormalizedSnapshotCliV1Error,
        snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error,
        transport.SevenPackCaptureCliError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.buffer.write(source.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
