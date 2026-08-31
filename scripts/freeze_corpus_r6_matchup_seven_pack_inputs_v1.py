#!/usr/bin/env python3
"""Default-off local freezer for a terminal-bound seven-pack request."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import stat
import sys

from nfl_dfs.research import corpus_r6_matchup_seven_pack_input_freezer_v1 as freezer
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


class SevenPackInputFreezerCliError(RuntimeError):
    """The local freezer CLI failed closed."""


def _fail(message: str) -> None:
    raise SevenPackInputFreezerCliError(message)


def _read_canonical_object(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute():
        _fail(f"{label} path must be absolute")
    try:
        before = path.lstat()
        raw = path.read_bytes()
        after = path.lstat()
    except OSError as exc:
        raise SevenPackInputFreezerCliError(f"{label} file is absent") from exc
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    if (
        path.is_symlink()
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or any(getattr(before, field) != getattr(after, field) for field in stable)
        or not raw
        or len(raw) > 256 * 1024 * 1024
    ):
        _fail(f"{label} must be one stable non-symlink regular file")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SevenPackInputFreezerCliError(f"{label} is not JSON") from exc
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must contain one string-keyed object")
    item = dict(value)
    canonical = source.canonical_json_bytes(item)
    if raw not in (canonical, canonical + b"\n"):
        _fail(f"{label} differs from canonical JSON")
    return item


def _write_create_once(output_directory: Path, files: Mapping[str, bytes]) -> None:
    if not output_directory.is_absolute():
        _fail("output directory must be absolute")
    try:
        parent = output_directory.parent.resolve(strict=True)
        supplied_parent = output_directory.parent.resolve()
    except OSError as exc:
        raise SevenPackInputFreezerCliError("output parent is absent") from exc
    if (
        parent != supplied_parent
        or output_directory != output_directory.resolve()
        or output_directory.exists()
        or output_directory.is_symlink()
    ):
        _fail("output directory must be one absent path under an existing parent")
    output_directory.mkdir(mode=0o700)
    for relative_path, raw in sorted(files.items()):
        path = output_directory / relative_path
        if output_directory not in path.parents or ".." in Path(relative_path).parts:
            _fail("local output path escapes the explicit output directory")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--confirm-freeze", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, object]:
    args = _parser().parse_args(argv)
    if (
        args.confirm_freeze is not True
        or os.environ.get(freezer.FREEZE_ENABLE_ENV) != freezer.ENABLE_VALUE
    ):
        _fail(
            "freeze is disabled; require --confirm-freeze and "
            f"{freezer.FREEZE_ENABLE_ENV}=1"
        )
    result = freezer.freeze_seven_pack_inputs_v1(
        spec_value=_read_canonical_object(args.spec, label="freeze spec"),
    )
    _write_create_once(args.output_directory, result["files"])
    return dict(result["receipt"])


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (
        SevenPackInputFreezerCliError,
        freezer.CorpusR6MatchupSevenPackInputFreezerV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
