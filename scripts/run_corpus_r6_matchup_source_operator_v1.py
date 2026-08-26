#!/usr/bin/env python3
"""Validate or execute one corrected, outcome-blind R6 source bundle.

``--validate-only`` constructs no cloud client and grants no trusted
mechanical authority. ``--execute`` is intentionally unavailable until the
separate pinned 54-entry authority catalog exists; no caller-supplied carrier
can bypass that source block. The script does not execute SQL or access
BigQuery.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_matchup_source_operator_v1 as operator,
)
from nfl_dfs.research import corpus_r6_matchup_source_v1 as source  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="absolute path to the local canonical input-bundle JSON",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--validate-only",
        action="store_true",
        help="run the complete source contract in memory without authority",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help=(
            "reserved and fail-closed until the frozen 54-entry authority "
            "catalog is implemented"
        ),
    )
    return parser


def _read_bounded_regular_file(
    path: Path, *, maximum_bytes: int, label: str,
) -> bytes:
    """No-follow bounded descriptor read with stable pre/post metadata."""
    if (
        not path.is_absolute()
        or path.name in {"", ".", ".."}
        or any(component in {".", ".."} for component in path.parts[1:])
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise operator.CorpusR6MatchupSourceOperatorV1Error(
            f"{label} path must be one absolute no-follow file"
        )
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open("/", directory_flags)
        for component in path.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(path.name, file_flags, dir_fd=directory_fd)
        before = os.fstat(file_fd)
        entry = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(entry.st_mode)
            or (before.st_dev, before.st_ino) != (entry.st_dev, entry.st_ino)
            or before.st_nlink != 1
            or entry.st_nlink != 1
            or not 0 < before.st_size <= maximum_bytes
        ):
            raise operator.CorpusR6MatchupSourceOperatorV1Error(
                f"{label} regular-file/link/size checks failed"
            )
        chunks: list[bytes] = []
        size = 0
        while True:
            remaining = maximum_bytes + 1 - size
            if remaining <= 0:
                raise operator.CorpusR6MatchupSourceOperatorV1Error(
                    f"{label} exceeds the byte bound"
                )
            chunk = os.read(file_fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(file_fd)
        if (
            not raw
            or len(raw) != before.st_size
            or (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_nlink,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
        ):
            raise operator.CorpusR6MatchupSourceOperatorV1Error(
                f"{label} changed during its bounded no-follow read"
            )
        return raw
    except operator.CorpusR6MatchupSourceOperatorV1Error:
        raise
    except OSError as exc:
        raise operator.CorpusR6MatchupSourceOperatorV1Error(
            f"{label} could not be read safely"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def main(
    argv: Sequence[str] | None = None,
) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        raw = _read_bounded_regular_file(
            args.bundle,
            maximum_bytes=operator.MAX_INPUT_BUNDLE_BYTES,
            label="bundle",
        )
        operator.parse_input_bundle_v1(raw)
        if args.validate_only:
            result = operator.run_matchup_source_operator_v1(
                input_bundle_raw=raw,
                validate_only=True,
            )
        else:
            result = operator.run_matchup_source_operator_v1(
                input_bundle_raw=raw,
                validate_only=False,
            )
        sys.stdout.buffer.write(source.canonical_json_bytes(result) + b"\n")
        return 0
    except (
        operator.CorpusR6MatchupSourceOperatorV1Error,
        source.CorpusR6MatchupSourceV1Error,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
