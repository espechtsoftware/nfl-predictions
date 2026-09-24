#!/usr/bin/env python3
"""Local, read-only operator for the sealed 54 x 5 current-bank panel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nfl_dfs.research import corpus_r6_fair_fill_current_bank_authority_v1 as authority
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract


def _json(path: str) -> dict[str, object]:
    value = json.loads(Path(path).read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _emit(value: object) -> None:
    sys.stdout.buffer.write(contract.canonical_json_bytes_v1(value) + b"\n")


def _write_create_once(path: str, value: object) -> None:
    raw = contract.canonical_json_bytes_v1(value)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(raw)


def _header(args: argparse.Namespace) -> None:
    _emit(authority.validate_54x5_manifest_headers_v1(_json(args.manifest)))


def _prepare(args: argparse.Namespace) -> None:
    manifest = _json(args.manifest)
    supplied = [Path(value) for value in args.authority]
    by_sha: dict[str, Path] = {}
    for path in supplied:
        raw = path.read_bytes()
        digest = __import__("hashlib").sha256(raw).hexdigest()
        if digest in by_sha:
            raise ValueError(f"duplicate supplied authority SHA-256: {digest}")
        by_sha[digest] = path

    def read_exact(identity: dict[str, object]) -> bytes:
        digest = str(identity["sha256"])
        path = by_sha.get(digest)
        if path is None:
            raise ValueError(f"required sealed authority was not supplied: {digest}")
        raw = path.read_bytes()
        if len(raw) != identity["bytes"]:
            raise ValueError(f"sealed authority byte count differs: {path}")
        return raw

    _emit(authority.prepare_selection_package_v1(
        manifest, source_ordinal=args.source, fold_ordinal=args.fold,
        read_exact=read_exact,
    ))


def _reader(paths: list[str]):
    by_sha: dict[str, bytes] = {}
    for value in paths:
        raw = Path(value).read_bytes()
        digest = __import__("hashlib").sha256(raw).hexdigest()
        if digest in by_sha:
            raise ValueError(f"duplicate supplied authority SHA-256: {digest}")
        by_sha[digest] = raw

    def read_exact(identity: dict[str, object]) -> bytes:
        raw = by_sha.get(str(identity["sha256"]))
        if raw is None or len(raw) != identity["bytes"]:
            raise ValueError("required exact sealed authority was not supplied")
        return raw
    return read_exact


def _select(args: argparse.Namespace) -> None:
    result = authority.execute_sealed_selection_fold_v1(
        _json(args.manifest), source_ordinal=args.source, fold_ordinal=args.fold,
        read_exact=_reader(args.authority),
    )
    _write_create_once(args.output, result)
    identity = authority.derive_create_once_selection_identity_v1(result)
    _write_create_once(args.output + ".identity.json", identity)
    _emit(identity)


def _evaluate(args: argparse.Namespace) -> None:
    selection = _json(args.selection)
    identity = authority.derive_create_once_selection_identity_v1(selection)
    result = authority.evaluate_sealed_selection_fold_v1(
        _json(args.manifest), selection_result=selection,
        selection_result_identity=identity, read_exact=_reader(args.authority),
    )
    _write_create_once(args.output, result)
    _emit({"evaluation_fold_sha256": result["evaluation_fold_sha256"]})


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    header = commands.add_parser("header")
    header.add_argument("--manifest", required=True)
    header.set_defaults(run=_header)
    prepare = commands.add_parser("prepare-selection")
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--source", type=int, required=True)
    prepare.add_argument("--fold", type=int, required=True)
    prepare.add_argument(
        "--authority", action="append", required=True,
        help="local sealed topology/projection/budget/later-source body",
    )
    prepare.set_defaults(run=_prepare)
    select = commands.add_parser("select")
    select.add_argument("--manifest", required=True)
    select.add_argument("--source", type=int, required=True)
    select.add_argument("--fold", type=int, required=True)
    select.add_argument("--authority", action="append", required=True)
    select.add_argument("--output", required=True)
    select.set_defaults(run=_select)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--manifest", required=True)
    evaluate.add_argument("--selection", required=True)
    evaluate.add_argument("--authority", action="append", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.set_defaults(run=_evaluate)
    args = parser.parse_args()
    args.run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
