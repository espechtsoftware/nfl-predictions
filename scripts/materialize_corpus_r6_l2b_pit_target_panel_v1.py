#!/usr/bin/env python3
"""Materialize one local, catalog-spined R6 L2b PIT target panel."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys

import pandas as pd

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as cloud
from nfl_dfs.research import corpus_r6_l2b_pit_target_panel_v1 as materializer


class MaterializeCorpusR6L2BPITTargetPanelV1Error(RuntimeError):
    """The local exact-input or create-once boundary failed."""


def _fail(message: str) -> None:
    raise MaterializeCorpusR6L2BPITTargetPanelV1Error(message)


def _json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaterializeCorpusR6L2BPITTargetPanelV1Error(
            f"{label} is not readable JSON"
        ) from exc
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _identity(path: Path, *, label: str) -> dict[str, object]:
    value = _json_object(path, label=f"{label} identity")
    try:
        return cloud._identity(value, label=label)
    except cloud.CorpusR6L2BPanelCloudV1Error as exc:
        raise MaterializeCorpusR6L2BPITTargetPanelV1Error(str(exc)) from exc


def _exact_local_bytes(
    path: Path, identity: Mapping[str, object], *, label: str,
) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise MaterializeCorpusR6L2BPITTargetPanelV1Error(
            f"{label} local copy is unreadable"
        ) from exc
    if (
        not raw
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} local copy differs from its immutable identity")
    return raw


def _write_create_once(path: Path, raw: bytes) -> None:
    if not path.is_absolute() or not path.parent.is_dir():
        _fail("output must be an absolute new file in an existing directory")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise MaterializeCorpusR6L2BPITTargetPanelV1Error(
            "output already exists; create-once publication refused"
        ) from exc
    except OSError as exc:
        raise MaterializeCorpusR6L2BPITTargetPanelV1Error(
            "create-once local publication failed"
        ) from exc


def materialize(args: argparse.Namespace) -> dict[str, object]:
    source_identity = _identity(
        args.later_source_identity, label="later-source freeze"
    )
    frame_identity = _identity(
        args.source_frame_identity, label="score-free source frame"
    )
    source_raw = _exact_local_bytes(
        args.later_source, source_identity, label="later-source freeze"
    )
    frame_raw = _exact_local_bytes(
        args.source_frame, frame_identity, label="score-free source frame"
    )
    try:
        source = json.loads(source_raw.decode("utf-8"))
        if not isinstance(source, Mapping):
            _fail("later-source freeze must be one JSON object")
        frame = pd.read_parquet(BytesIO(frame_raw))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
        raise MaterializeCorpusR6L2BPITTargetPanelV1Error(
            "immutable source inputs could not be decoded"
        ) from exc
    panel = materializer.materialize_catalog_spined_pit_target_panel_v1(
        later_source_freeze=dict(source),
        later_source_freeze_identity=source_identity,
        score_free_source=frame,
        score_free_source_identity=frame_identity,
    )
    raw = legal.canonical_json_bytes(panel)
    _write_create_once(args.output, raw)
    return {
        "schema_version": "corpus-r6-l2b-pit-target-local-publication/v1",
        "output": str(args.output),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "target_panel_sha256": panel["target_panel_sha256"],
        "slate_count": panel["slate_count"],
        "cloud_mutation_performed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--later-source", type=Path, required=True)
    parser.add_argument("--later-source-identity", type=Path, required=True)
    parser.add_argument("--source-frame", type=Path, required=True)
    parser.add_argument("--source-frame-identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    result = materialize(_parser().parse_args(argv))
    sys.stdout.buffer.write(legal.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        MaterializeCorpusR6L2BPITTargetPanelV1Error,
        materializer.CorpusR6L2BPITTargetPanelV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
