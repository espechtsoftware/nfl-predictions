#!/usr/bin/env python3
"""Default-off CLI for the canonical candidate-v2 -> source-v3 batch.

No action is implicit.  ``validate`` performs only clean Git, tracked-plan,
runtime, and declared-image checks.  ``task0`` adds a prerequisite-only,
read-only real-artifact smoke and never runs a component/source worker,
publishes a source object, verifies from a distinct process, or constructs a
write-capable transport.
Full publication is intentionally absent from this public CLI.  The exact-name
Cloud Run controller is the sole executable publication boundary; it derives
provider state rather than accepting a caller-authored receipt.  ``reopen``
accepts one local generation-pinned
terminal batch-root identity and exposes no write callback; external
orchestration must attest that a later invocation used a distinct process.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import stat
import sys

from nfl_dfs.research import (
    corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch,
)
MAX_LOCAL_JSON_BYTES = 256 * 1024


def _load_root_identity(path_value: str) -> dict[str, object]:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError("reopen identity path must be absolute")
    try:
        before = path.lstat()
    except OSError as exc:
        raise ValueError("reopen identity file is absent") from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("reopen identity path must be one unaliased regular file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError("reopen identity file requires O_NOFOLLOW support")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags | nofollow)
        opened = os.fstat(descriptor)
        chunks: list[bytes] = []
        retained = 0
        while retained <= MAX_LOCAL_JSON_BYTES:
            chunk = os.read(
                descriptor,
                min(16 * 1024, MAX_LOCAL_JSON_BYTES + 1 - retained),
            )
            if not chunk:
                break
            chunks.append(chunk)
            retained += len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ValueError("reopen identity file secure read failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    if (
        any(getattr(before, field) != getattr(opened, field) for field in stable)
        or any(getattr(opened, field) != getattr(after, field) for field in stable)
        or not raw
        or len(raw) > MAX_LOCAL_JSON_BYTES
        or len(raw) != opened.st_size
    ):
        raise ValueError("reopen identity file changed or exceeds its byte bound")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("reopen identity file must contain JSON") from exc
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise ValueError("reopen identity file must contain one string-keyed object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate, prerequisite-only task-0 smoke, "
            "or write-disabled reopen the canonical R6 matchup source-v3 batch"
        )
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=("validate", "task0", "reopen"),
        help="Choose exactly one explicit operation; no action is implicit.",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--batch-root-identity")
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, object]:
    args = _parser().parse_args(argv)
    if args.action == "validate":
        if (
            args.run_id or args.batch_root_identity
        ):
            raise ValueError("validate accepts no publication or reopen arguments")
        return batch.validate_matchup_source_batch_outer_candidate_authority_v3()
    if args.action == "task0":
        if (
            args.run_id or args.batch_root_identity
        ):
            raise ValueError("task0 accepts no publication or reopen arguments")
        return batch.validate_matchup_source_batch_task0_readiness_v3()
    if args.action == "reopen":
        if (
            args.run_id or not args.batch_root_identity
        ):
            raise ValueError("reopen requires only --batch-root-identity")
        return batch.reopen_matchup_source_batch_outer_candidate_authority_v3(
            batch_release_identity=_load_root_identity(args.batch_root_identity)
        )
    raise ValueError("source-v3 action differs")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (
        ValueError,
        batch.CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
