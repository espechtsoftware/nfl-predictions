#!/usr/bin/env python3
"""Local-only request and dry-validation CLI for supported-232 generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from nfl_dfs.research import corpus_r6_supported232_generation_v1 as supported


def _read_json(path: str) -> object:
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise supported.CorpusR6Supported232GenerationV1Error(
            f"cannot read JSON input {path!r}: {exc}"
        ) from exc


def _read_draws(path: str) -> np.ndarray:
    try:
        value = np.load(path, allow_pickle=False)
    except Exception as exc:
        raise supported.CorpusR6Supported232GenerationV1Error(
            f"cannot read safe NPY input {path!r}: {exc}"
        ) from exc
    matrix = np.asarray(value)
    if matrix.dtype != np.dtype(np.float32) or matrix.ndim != 2:
        raise supported.CorpusR6Supported232GenerationV1Error(
            "draw input must be one two-dimensional float32 NPY array"
        )
    matrix = np.ascontiguousarray(matrix, dtype=np.float32)
    matrix.flags.writeable = False
    return matrix


def _create_json(path: str, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = supported.canonical_json_bytes_v1(value) + b"\n"
    try:
        with target.open("xb") as stream:
            stream.write(body)
    except FileExistsError as exc:
        raise supported.CorpusR6Supported232GenerationV1Error(
            f"refusing to overwrite {target}"
        ) from exc


def _registry(args: argparse.Namespace) -> None:
    _create_json(args.output, supported.supported232_arm_registry_v1())


def _player_bundle(args: argparse.Namespace) -> None:
    raw = _read_json(args.players)
    players = raw.get("players") if isinstance(raw, dict) else raw
    if not isinstance(players, list):
        raise supported.CorpusR6Supported232GenerationV1Error(
            "players input must be an array or an object containing players"
        )
    bundle = supported.build_player_bundle_v1(
        slate={
            "season": args.season,
            "week": args.week,
            "slate_id": args.slate_id,
        },
        players=players,
    )
    _create_json(args.output, bundle)


def _request(args: argparse.Namespace) -> None:
    bundle = supported.validate_player_bundle_v1(_read_json(args.player_bundle))
    draws = _read_draws(args.draws)
    request = supported.build_local_task_request_v1(
        player_bundle=bundle,
        player_bundle_identity=supported.local_file_identity_v1(args.player_bundle),
        draws_identity=supported.local_file_identity_v1(args.draws),
        draws=draws,
        origin_id=args.origin,
    )
    _create_json(args.output, request)


def _dry_validate(args: argparse.Namespace) -> None:
    request = supported.validate_local_task_request_v1(_read_json(args.request))
    validation, _bundle, _draws = supported.load_and_dry_validate_local_task_v1(
        request
    )
    _create_json(args.output, validation)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build and dry-validate local supported-232 population requests; "
            "this CLI never runs optimizers or reads outcomes"
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    registry = commands.add_parser("registry")
    registry.add_argument("--output", required=True)
    registry.set_defaults(handler=_registry)

    bundle = commands.add_parser("player-bundle")
    bundle.add_argument("--players", required=True)
    bundle.add_argument("--season", required=True, type=int)
    bundle.add_argument("--week", required=True, type=int)
    bundle.add_argument("--slate-id", required=True)
    bundle.add_argument("--output", required=True)
    bundle.set_defaults(handler=_player_bundle)

    request = commands.add_parser("request")
    request.add_argument("--player-bundle", required=True)
    request.add_argument("--draws", required=True)
    request.add_argument("--origin", choices=("R0", "R1", "R2", "R3", "R4"), required=True)
    request.add_argument("--output", required=True)
    request.set_defaults(handler=_request)

    dry = commands.add_parser("dry-validate")
    dry.add_argument("--request", required=True)
    dry.add_argument("--output", required=True)
    dry.set_defaults(handler=_dry_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        args.handler(args)
    except supported.CorpusR6Supported232GenerationV1Error as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
