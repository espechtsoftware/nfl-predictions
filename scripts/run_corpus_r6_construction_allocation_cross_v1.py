#!/usr/bin/env python3
"""Bounded, default-off runner for the construction x allocation cross.

The runner consumes one exact local manifest whose Parquet members have
already been staged by generation and SHA-256.  It performs no warehouse,
object listing, outcome, graph, deployment, or policy operation.  Generation
is fixed to the registered 54 slates and four cells; output is local
create-once JSON for subsequent root-last publication by the operator module.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

import pandas as pd

from nfl_dfs.research import (
    boom_first_historical_construction_replay_adapter_v1 as adapter,
)
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross


INPUT_SCHEMA = "corpus-r6-construction-allocation-local-input-bundle/v1"
GENERATE_ENABLE_ENV = "CORPUS_R6_CONSTRUCTION_ALLOCATION_GENERATE"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_SELECTION_BYTES = 2 * 1024 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _secure_read(path_value: object, *, maximum: int, label: str) -> bytes:
    if type(path_value) is not str:
        raise ValueError(f"{label} path differs")
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    try:
        before = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} file is absent") from exc
    if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"{label} must be one unaliased regular file")
    if before.st_size <= 0 or before.st_size > maximum:
        raise ValueError(f"{label} exceeds its byte bound")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError(f"{label} requires O_NOFOLLOW support")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags | nofollow)
        opened = os.fstat(descriptor)
        chunks: list[bytes] = []
        retained = 0
        while retained <= maximum:
            chunk = os.read(descriptor, min(8 * 1024 * 1024, maximum + 1 - retained))
            if not chunk:
                break
            chunks.append(chunk)
            retained += len(chunk)
        raw = b"".join(chunks)
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
        or len(raw) != opened.st_size
    ):
        raise ValueError(f"{label} changed during its bounded read")
    return raw


def _json_file(
    path: str, *, label: str, maximum: int = MAX_MANIFEST_BYTES,
) -> dict[str, object]:
    raw = _secure_read(path, maximum=maximum, label=label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must contain JSON") from exc
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise ValueError(f"{label} must contain one string-keyed object")
    return value


def _secure_hash_file(path_value: object, *, maximum: int, label: str) -> tuple[int, str]:
    if type(path_value) is not str:
        raise ValueError(f"{label} path differs")
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    try:
        before = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} file is absent") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size <= 0
        or before.st_size > maximum
    ):
        raise ValueError(f"{label} is not one bounded regular file")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError(f"{label} requires O_NOFOLLOW support")
    descriptor: int | None = None
    digest = hashlib.sha256()
    retained = 0
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_CLOEXEC | nofollow
        )
        opened = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 8 * 1024 * 1024)
            if not chunk:
                break
            retained += len(chunk)
            if retained > maximum:
                raise ValueError(f"{label} exceeds its byte bound")
            digest.update(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ValueError(f"{label} secure hash failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    if (
        any(getattr(before, field) != getattr(opened, field) for field in stable)
        or any(getattr(opened, field) != getattr(after, field) for field in stable)
        or retained != opened.st_size
    ):
        raise ValueError(f"{label} changed during its bounded hash")
    return retained, digest.hexdigest()


def _parquet_member(value: object, *, label: str) -> pd.DataFrame:
    if not isinstance(value, Mapping) or set(value) != {
        "path", "sha256", "bytes", "format",
    }:
        raise ValueError(f"{label} member receipt differs")
    if (
        value.get("format") != "parquet"
        or type(value.get("sha256")) is not str
        or _SHA256.fullmatch(str(value["sha256"])) is None
        or type(value.get("bytes")) is not int
        or not 0 < int(value["bytes"]) <= MAX_MEMBER_BYTES
    ):
        raise ValueError(f"{label} member receipt differs")
    path_value = value.get("path")
    if type(path_value) is not str:
        raise ValueError(f"{label} path differs")
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(f"{label} path must be absolute")
    try:
        before = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} file is absent") from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size != value["bytes"]
    ):
        raise ValueError(f"{label} is not the declared regular file")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError(f"{label} requires O_NOFOLLOW support")
    descriptor: int | None = None
    retained = 0
    digest = hashlib.sha256()
    stable = (
        "st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns",
    )
    try:
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow
        )
        opened = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 8 * 1024 * 1024)
            if not chunk:
                break
            retained += len(chunk)
            if retained > MAX_MEMBER_BYTES:
                raise ValueError(f"{label} exceeds its byte bound")
            digest.update(chunk)
        if retained != value["bytes"] or digest.hexdigest() != value["sha256"]:
            raise ValueError(f"{label} byte identity differs")
        os.lseek(descriptor, 0, os.SEEK_SET)
        # Parse a duplicate of the already verified descriptor.  Replacing the
        # pathname cannot redirect Pandas to different bytes between hashing
        # and parsing.
        with os.fdopen(os.dup(descriptor), "rb") as verified_file:
            frame = pd.read_parquet(verified_file)
        after = os.fstat(descriptor)
    except ValueError:
        raise
    except Exception as exc:  # engine-specific parse failures are data failures
        raise ValueError(f"{label} Parquet parse failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (
        any(getattr(before, field) != getattr(opened, field) for field in stable)
        or any(getattr(opened, field) != getattr(after, field) for field in stable)
    ):
        raise ValueError(f"{label} changed during verified Parquet parse")
    return frame


def _inputs(bundle: Mapping[str, object]) -> tuple[
    list[adapter.ConstructionAllocationSeasonInputs],
    cross.CrossPanelAuthority,
]:
    if bundle.get("schema_version") != INPUT_SCHEMA:
        raise ValueError("input bundle schema differs")
    seasons = bundle.get("seasons")
    if not isinstance(seasons, list) or [
        row.get("season") for row in seasons if isinstance(row, Mapping)
    ] != list(cross.PANEL_SEASONS):
        raise ValueError("input bundle must contain ordered 2023--2025 seasons")
    result: list[adapter.ConstructionAllocationSeasonInputs] = []
    for row in seasons:
        if not isinstance(row, Mapping):
            raise ValueError("season input differs")
        season = row["season"]
        files = row.get("files")
        if not isinstance(files, Mapping) or set(files) != {
            "panel", "dst_prelock", "market_points", "tabpfn_marginals",
        }:
            raise ValueError(f"{season} file grid differs")
        result.append(adapter.ConstructionAllocationSeasonInputs(
            season=season,
            panel=_parquet_member(files["panel"], label=f"{season} panel"),
            dst_prelock=_parquet_member(
                files["dst_prelock"], label=f"{season} prelock DST"
            ),
            market_points=_parquet_member(
                files["market_points"], label=f"{season} market points"
            ),
            tabpfn_marginals=_parquet_member(
                files["tabpfn_marginals"], label=f"{season} TabPFN"
            ),
            source_identity_by_slate=row.get("source_identity_by_slate", {}),
            source_manifest_by_slate=row.get("source_manifest_by_slate", {}),
            lock_identity_by_slate=row.get("lock_identity_by_slate", {}),
            audit_bank_identity_by_slate=row.get("audit_bank_identity_by_slate", {}),
        ))
    raw_authority = bundle.get("panel_authority")
    if not isinstance(raw_authority, Mapping):
        raise ValueError("panel authority differs")
    authority = cross.CrossPanelAuthority(
        panel_id=str(raw_authority.get("panel_id", "")),
        expected_slate_ids=tuple(raw_authority.get("expected_slate_ids", ())),
        identity=raw_authority.get("identity", {}),
    )
    return result, authority


def _create_once_local(path_value: str, raw: bytes) -> None:
    path = Path(path_value)
    if not path.is_absolute() or path.parent.resolve() != path.parent:
        raise ValueError("output selection path must be absolute and normalized")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        written = 0
        while written < len(raw):
            written += os.write(descriptor, raw[written:])
        os.fsync(descriptor)
    except FileExistsError as exc:
        raise ValueError("output selection already exists") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def run(argv: Sequence[str] | None = None) -> dict[str, object]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=(
        "registry", "validate-selection", "generate",
    ))
    parser.add_argument("--input-bundle")
    parser.add_argument("--selection")
    parser.add_argument("--output-selection")
    parser.add_argument("--confirm-generate", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "registry":
        if any((args.input_bundle, args.selection, args.output_selection, args.confirm_generate)):
            raise ValueError("registry accepts no generation arguments")
        return cross.registry_document(code_sha="0000000")
    if args.action == "validate-selection":
        if not args.selection or any((args.input_bundle, args.output_selection, args.confirm_generate)):
            raise ValueError("validate-selection requires only --selection")
        return cross.validate_score_blind_cross_v1(
            _json_file(
                args.selection,
                label="selection",
                maximum=MAX_SELECTION_BYTES,
            )
        )
    if (
        not args.input_bundle
        or not args.output_selection
        or args.selection
        or args.confirm_generate is not True
        or os.environ.get(GENERATE_ENABLE_ENV) != "1"
    ):
        raise ValueError(
            "generate requires --input-bundle, --output-selection, "
            f"--confirm-generate, and {GENERATE_ENABLE_ENV}=1"
        )
    bundle = _json_file(args.input_bundle, label="input bundle")
    inputs, authority = _inputs(bundle)
    selection = adapter.build_score_blind_cross_from_pit_inputs(
        inputs,
        panel_id=str(bundle.get("panel_id", "")),
        code_sha=str(bundle.get("code_sha", "")),
        image_digest=str(bundle.get("image_digest", "")),
        panel_authority=authority,
    )
    raw = cross.canonical_json_bytes(selection) + b"\n"
    _create_once_local(args.output_selection, raw)
    return {
        "schema_version": "corpus-r6-construction-allocation-local-run/v1",
        "selection_path": args.output_selection,
        "selection_sha256": hashlib.sha256(raw).hexdigest(),
        "selection_bytes": len(raw),
        "selection_receipt_sha256": selection["receipt_sha256"],
        "slate_count": selection["slate_count"],
        "cell_count": len(selection["cell_order"]),
        "outcome_data_accessed": False,
        "cloud_mutation_performed": False,
        "complete": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except (ValueError, cross.ConstructionAllocationCrossError, adapter.ConstructionAllocationReplayAdapterError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
