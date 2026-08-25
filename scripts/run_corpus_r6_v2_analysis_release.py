#!/usr/bin/env python3
"""Prepare, run, verify, and finish the outcome-blind R6-v2 mechanics panel.

The command performs exact-name object reads and create-once publications only.
It has no object-listing path and imports no realized-outcome reader.  With the
currently available simple 017r matchup snapshot, every successfully executed
slate and the 54-slate terminal are explicitly ``complete-source-blocked``.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
import sys
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_analysis_release as release
from nfl_dfs.research.corpus_neo4j_transport import (
    ExactObjectStore,
    GoogleCloudObjectStore,
)


COMMANDS: Final = ("prepare", "run-slate", "verify-slate", "finish-panel")


class CorpusR6V2AnalysisReleaseCLIError(RuntimeError):
    """The CLI cannot continue without weakening exact publication."""


def _load_identity(
    path: Path, *, label: str, carrier_field: str | None = None
) -> dict[str, object]:
    if not path.is_absolute():
        raise CorpusR6V2AnalysisReleaseCLIError(
            f"{label} path must be absolute"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusR6V2AnalysisReleaseCLIError(
            f"cannot read {label} file"
        ) from exc
    canonical_raw = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical_raw or raw not in {canonical_raw, canonical_raw + b"\n"}:
        raise CorpusR6V2AnalysisReleaseCLIError(
            f"{label} file must be canonical JSON with at most one newline"
        )
    try:
        parsed = batch.parse_canonical_json_bytes(canonical_raw, label=label)
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseCLIError(
            f"{label} file is not canonical JSON"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise CorpusR6V2AnalysisReleaseCLIError(f"{label} must be an object")
    candidate: object = parsed
    if carrier_field is not None and carrier_field in parsed:
        candidate = parsed[carrier_field]
    try:
        return batch.normalize_object_identity(candidate, label=label)
    except Exception as exc:
        raise CorpusR6V2AnalysisReleaseCLIError(
            f"{label} does not carry one exact object identity"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Outcome-blind R6-v2 prepare/run-slate/verify-slate/finish-panel seam"
        )
    )
    parser.add_argument(
        "--project",
        help="optional Google Cloud project used only to construct the GCS client",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare", help="exact-replay the 54-slate panel and publish its manifest"
    )
    prepare.add_argument(
        "--panel-index-identity", required=True, type=Path,
        help="absolute canonical JSON identity for the published combined panel",
    )
    prepare.add_argument(
        "--lane-terminal-identity", required=True, action="append", type=Path,
        help="absolute lane terminal identity file; provide exactly twice in A/B order",
    )
    prepare.add_argument("--source-commit-sha", required=True)
    prepare.add_argument("--immutable-image", required=True)
    prepare.add_argument("--output-prefix", required=True)

    run_slate = subparsers.add_parser(
        "run-slate", help="worker: run and publish mechanics only"
    )
    run_slate.add_argument(
        "--manifest-identity", required=True, type=Path,
        help="absolute canonical JSON identity (or prepare receipt carrier)",
    )

    verify_slate = subparsers.add_parser(
        "verify-slate",
        help="independent process: exact-rerun mechanics and publish source block",
    )
    verify_slate.add_argument(
        "--manifest-identity", required=True, type=Path,
        help="absolute canonical JSON identity (or prepare receipt carrier)",
    )
    verify_slate.add_argument(
        "--mechanics-result-identity", required=True, type=Path,
        help="absolute worker mechanics identity (or run receipt carrier)",
    )
    run_slate.add_argument("--source-ordinal", required=True, type=int)
    run_slate.add_argument(
        "--matchup-source-snapshot-identity", required=True, type=Path,
        help="absolute canonical JSON identity for the simple matchup snapshot",
    )

    finish = subparsers.add_parser(
        "finish-panel", help="exact-reopen 54 acceptances and publish the terminal"
    )
    finish.add_argument(
        "--manifest-identity", required=True, type=Path,
        help="absolute canonical JSON identity (or prepare receipt carrier)",
    )
    finish.add_argument(
        "--slate-acceptance-identity", required=True, action="append", type=Path,
        help=(
            "absolute canonical JSON identity (or verify receipt carrier); provide "
            "exactly 54 in source-ordinal order"
        ),
    )
    return parser


def run(argv: Sequence[str], *, storage: ExactObjectStore) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    if args.command == "prepare":
        if len(args.lane_terminal_identity) != 2:
            raise CorpusR6V2AnalysisReleaseCLIError(
                "prepare requires exactly two lane terminal identities"
            )
        return release.prepare_r6_v2_analysis_release_v1(
            storage=storage,
            panel_index_identity=_load_identity(
                args.panel_index_identity,
                label="panel index identity",
                carrier_field="panel_object_identity",
            ),
            lane_terminal_identities=[
                _load_identity(
                    path,
                    label=f"lane terminal identity[{ordinal}]",
                    carrier_field="terminal_receipt_identity",
                )
                for ordinal, path in enumerate(args.lane_terminal_identity)
            ],
            source_commit_sha=args.source_commit_sha,
            immutable_image=args.immutable_image,
            output_prefix=args.output_prefix,
        )
    if args.command == "run-slate":
        return release.run_r6_v2_analysis_slate_v1(
            storage=storage,
            manifest_identity=_load_identity(
                args.manifest_identity,
                label="manifest identity",
                carrier_field="manifest_identity",
            ),
            source_ordinal=args.source_ordinal,
            matchup_source_snapshot_identity=_load_identity(
                args.matchup_source_snapshot_identity,
                label="matchup source snapshot identity",
                carrier_field="matchup_source_snapshot_identity",
            ),
        )
    if args.command == "verify-slate":
        return release.verify_r6_v2_analysis_slate_v1(
            storage=storage,
            manifest_identity=_load_identity(
                args.manifest_identity,
                label="manifest identity",
                carrier_field="manifest_identity",
            ),
            mechanics_result_identity=_load_identity(
                args.mechanics_result_identity,
                label="mechanics result identity",
                carrier_field="mechanics_result_identity",
            ),
        )
    if args.command == "finish-panel":
        if len(args.slate_acceptance_identity) != release.AUTHORITATIVE_SLATE_COUNT:
            raise CorpusR6V2AnalysisReleaseCLIError(
                "finish-panel requires exactly 54 acceptance identities"
            )
        return release.finish_r6_v2_analysis_panel_v1(
            storage=storage,
            manifest_identity=_load_identity(
                args.manifest_identity,
                label="manifest identity",
                carrier_field="manifest_identity",
            ),
            ordered_acceptance_identities=[
                _load_identity(
                    path,
                    label=f"slate acceptance identity[{ordinal}]",
                    carrier_field="slate_acceptance_identity",
                )
                for ordinal, path in enumerate(args.slate_acceptance_identity)
            ],
        )
    raise CorpusR6V2AnalysisReleaseCLIError(
        f"unregistered command {args.command!r}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parsed_argv = list(sys.argv[1:] if argv is None else argv)
    # Parse once to obtain the optional project without constructing any client
    # during module import or test collection.
    args = _parser().parse_args(parsed_argv)
    storage = GoogleCloudObjectStore(project=args.project)
    result = run(parsed_argv, storage=storage)
    sys.stdout.buffer.write(batch.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
