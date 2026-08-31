#!/usr/bin/env python3
"""Explicit CLI for the source-v3 one-ordinal worker and verifier."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import stat
import sys

from nfl_dfs.research import corpus_r6_matchup_source_task0_v3 as task0


MAX_JSON_BYTES = 256 * 1024


def _load_json(path_value: str, *, label: str) -> dict[str, object]:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    try:
        before = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} file is absent") from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"{label} path must be one unaliased regular file")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError(f"{label} requires O_NOFOLLOW support")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | nofollow)
        opened = os.fstat(descriptor)
        raw = os.read(descriptor, MAX_JSON_BYTES + 1)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ValueError(f"{label} secure read failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    if (
        any(getattr(before, field) != getattr(opened, field) for field in stable)
        or any(getattr(opened, field) != getattr(after, field) for field in stable)
        or not raw
        or len(raw) > MAX_JSON_BYTES
        or len(raw) != opened.st_size
    ):
        raise ValueError(f"{label} changed or exceeds its byte bound")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} must contain JSON") from exc
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise ValueError(f"{label} must contain one string-keyed object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or independently verify the bounded source-v3 task0 gate"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=(
            "worker", "verify", "validate-provider-receipt", "validate-receipt",
        ),
    )
    parser.add_argument("--run-id")
    parser.add_argument("--worker-result-identity")
    parser.add_argument("--verifier-receipt")
    parser.add_argument("--provider-receipt")
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, object]:
    args = _parser().parse_args(argv)
    provider_arguments = (
        args.provider_receipt,
    )
    if args.action == "worker":
        if (
            not args.run_id
            or args.worker_result_identity
            or args.verifier_receipt
            or any(provider_arguments)
        ):
            raise ValueError("worker requires only --run-id")
        return task0.publish_task0_worker_v3(run_id=args.run_id)
    if args.action == "verify":
        if (
            args.run_id
            or not args.worker_result_identity
            or args.verifier_receipt
            or any(provider_arguments)
        ):
            raise ValueError("verify requires only --worker-result-identity")
        return task0.verify_task0_worker_v3(
            worker_result_identity=_load_json(
                args.worker_result_identity, label="worker result identity"
            )
        )
    if args.action in {"validate-provider-receipt", "validate-receipt"}:
        supplied = args.provider_receipt or args.verifier_receipt
        if (
            args.run_id
            or args.worker_result_identity
            or not supplied
            or (args.provider_receipt and args.verifier_receipt)
        ):
            raise ValueError(
                "validate-provider-receipt requires only --provider-receipt"
            )
        return task0.validate_task0_provider_receipt_v3(
            _load_json(supplied, label="provider receipt")
        )
    raise ValueError("task0 action differs")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (ValueError, task0.CorpusR6MatchupSourceTask0V3Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
