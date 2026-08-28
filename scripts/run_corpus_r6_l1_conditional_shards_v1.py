#!/usr/bin/env python3
"""Preflight or materialize R6 L1 CAL19/WF21/HOLD22 bank shards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

from nfl_dfs.research.belief_world_v1 import canonical_json_bytes
from nfl_dfs.research.corpus_r6_l1_conditional_shards_v1 import (
    COMPONENT_COLUMNS,
    component_surface_preflight_v1,
    local_file_identity,
    materialize_l1_conditional_shards_v1,
)


class L1ConditionalShardCliError(ValueError):
    """The local component-surface request was not exact."""


_BASE_COLUMNS = (
    "gsis_id", "season", "week", "pos", "team", "opp", "game_id",
    "game_total", *COMPONENT_COLUMNS,
)


def _read_json(path: str) -> dict[str, object]:
    source = Path(path).resolve(strict=True)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise L1ConditionalShardCliError(
            f"cannot read source identity JSON {source}"
        ) from exc
    if not isinstance(value, dict):
        raise L1ConditionalShardCliError(
            "source identity JSON must contain one object"
        )
    return value


def _surface(path: Path) -> pd.DataFrame:
    try:
        import pyarrow.parquet as parquet

        available = set(parquet.ParquetFile(path).schema_arrow.names)
        return pd.read_parquet(
            path,
            columns=[name for name in _BASE_COLUMNS if name in available],
        )
    except Exception as exc:
        raise L1ConditionalShardCliError(
            f"cannot read exact component surface {path}"
        ) from exc


def _identity(path: Path, identity_path: str | None) -> dict[str, object]:
    return (
        local_file_identity(path)
        if identity_path is None
        else _read_json(identity_path)
    )


def _preflight(args: argparse.Namespace) -> int:
    source = Path(args.component_surface).resolve(strict=True)
    receipt = component_surface_preflight_v1(
        _surface(source),
        source_identity=_identity(source, args.component_surface_identity),
    )
    sys.stdout.buffer.write(canonical_json_bytes(receipt) + b"\n")
    return 0 if receipt["ready"] else 2


def _materialize(args: argparse.Namespace) -> int:
    source = Path(args.component_surface).resolve(strict=True)
    result = materialize_l1_conditional_shards_v1(
        component_surface=_surface(source),
        component_surface_identity=_identity(
            source, args.component_surface_identity
        ),
        output_dir=args.output_dir,
        n_sims=args.n_sims,
        base_seed=args.base_seed,
        usage_dirichlet_k=args.usage_dirichlet_k,
        td_allocation_k=args.td_allocation_k,
    )
    sys.stdout.buffer.write(canonical_json_bytes(result.receipt) + b"\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, func in (("preflight", _preflight), ("materialize", _materialize)):
        command = subparsers.add_parser(name)
        command.add_argument("--component-surface", required=True)
        command.add_argument("--component-surface-identity")
        command.set_defaults(func=func)
        if name == "materialize":
            command.add_argument("--output-dir", required=True)
            command.add_argument("--n-sims", type=int, default=10_000)
            command.add_argument("--base-seed", type=int, default=20260828)
            command.add_argument(
                "--usage-dirichlet-k", type=float, default=20.0
            )
            command.add_argument("--td-allocation-k", type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
