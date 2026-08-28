#!/usr/bin/env python3
"""Materialize real-player L1/L2 evidence without reading lineup outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from nfl_dfs.research.belief_world_v1 import canonical_json_bytes
from nfl_dfs.research.belief_world_v1 import canonical_sha256
from nfl_dfs.research.corpus_r6_belief_evidence_v1 import (
    L1_BANK_MANIFEST_SCHEMA,
    L1ConditionalBankShard,
    build_l1_real_player_evidence_v1,
    build_l2_real_player_evidence_v1,
    load_pre2023_sunday_main_role_history_v1,
    local_file_identity,
    snapshot_schema_smoke_v1,
)
from nfl_dfs.research.corpus_r6_belief_calibration_v1 import (
    build_l2_role_jump_calibration_release_v1,
)
from nfl_dfs.research.latent_role_state import transition_frame_sha256
from nfl_dfs.research import corpus_r6_belief_evidence_v1 as evidence_contract


class BeliefEvidenceCliError(ValueError):
    """The local evidence materialization request was not exact."""


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BeliefEvidenceCliError(f"cannot read JSON {path}") from exc


def _identity(path: Path, identity_path: str | None) -> dict[str, object]:
    if identity_path is None:
        return local_file_identity(path)
    value = _read_json(Path(identity_path))
    if not isinstance(value, dict):
        raise BeliefEvidenceCliError("source identity JSON must be an object")
    return value


def _output_dir(path: str) -> Path:
    result = Path(path).resolve()
    result.mkdir(parents=True, exist_ok=False)
    return result


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _schema_smoke(args: argparse.Namespace) -> int:
    import pyarrow.parquet as parquet

    source = Path(args.snapshot).resolve(strict=True)
    columns = parquet.ParquetFile(source).schema_arrow.names
    smoke = snapshot_schema_smoke_v1(columns)
    result: dict[str, object] = {
        "schema": "corpus-r6-belief-evidence-real-source-smoke/v1",
        "smoke": smoke,
        "source_identity": _identity(source, args.snapshot_identity),
    }
    result["receipt_sha256"] = canonical_sha256(result)
    sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
    return 0


def _load_shards(manifest_path: Path) -> list[L1ConditionalBankShard]:
    value = _read_json(manifest_path)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "shards"}
        or value.get("schema") != L1_BANK_MANIFEST_SCHEMA
        or not isinstance(value.get("shards"), list)
        or not value["shards"]
    ):
        raise BeliefEvidenceCliError("L1 bank manifest schema differs")
    shards: list[L1ConditionalBankShard] = []
    for item in value["shards"]:
        if not isinstance(item, dict) or set(item) not in (
            {"season", "week", "path"},
            {"season", "week", "path", "source_identity"},
        ):
            raise BeliefEvidenceCliError("L1 bank manifest shard differs")
        path = Path(str(item["path"])).resolve(strict=True)
        with np.load(path, allow_pickle=False) as bank:
            if set(bank.files) != {
                "player_ids", "ordinary_draws", "shootout_draws"
            }:
                raise BeliefEvidenceCliError(f"L1 NPZ keys differ for {path}")
            players = tuple(str(value) for value in bank["player_ids"].tolist())
            ordinary = np.asarray(bank["ordinary_draws"], dtype=np.float64)
            shootout = np.asarray(bank["shootout_draws"], dtype=np.float64)
        identity = item.get("source_identity") or local_file_identity(path)
        shards.append(L1ConditionalBankShard(
            season=int(item["season"]),
            week=int(item["week"]),
            player_ids=players,
            ordinary_draws=ordinary,
            shootout_draws=shootout,
            source_identity=identity,
        ))
    return shards


def _extract_l1(args: argparse.Namespace) -> int:
    snapshot_path = Path(args.snapshot).resolve(strict=True)
    snapshot = pd.read_parquet(
        snapshot_path,
        columns=[
            "gsis_id", "season", "week", "pos", "team", "opp",
            "game_id", "mean_projection", "actual",
        ],
    )
    evidence = build_l1_real_player_evidence_v1(
        player_snapshot=snapshot,
        bank_shards=_load_shards(Path(args.bank_manifest).resolve(strict=True)),
        snapshot_source_identity=_identity(
            snapshot_path, args.snapshot_identity
        ),
    )
    output = _output_dir(args.output_dir)
    evidence.event_rows.to_parquet(output / "l1-event-evidence.parquet", index=False)
    evidence.opposing_wr1_moment_rows.to_parquet(
        output / "l1-opposing-wr1-moments.parquet", index=False
    )
    _write_json(output / "l1-evidence-receipt.json", evidence.receipt)
    sys.stdout.buffer.write(canonical_json_bytes(evidence.receipt) + b"\n")
    return 0


def _extract_l2(args: argparse.Namespace) -> int:
    snapshot_path = Path(args.snapshot).resolve(strict=True)
    snapshot = pd.read_parquet(
        snapshot_path,
        columns=[
            "gsis_id", "season", "week", "pos", "team", "opp",
            "game_id", "mean_projection", "actual",
        ],
    )
    output = _output_dir(args.output_dir)
    if args.role_history:
        source_role_path = Path(args.role_history).resolve(strict=True)
        roles = pd.read_parquet(source_role_path)
        role_identity = _identity(source_role_path, args.role_source_identity)
    else:
        if args.role_source_identity:
            raise BeliefEvidenceCliError(
                "role source identity cannot precede a live materialization"
            )
        roles = load_pre2023_sunday_main_role_history_v1()
        source_role_path = output / "l2-role-history.source.parquet"
        roles.to_parquet(source_role_path, index=False)
        role_identity = local_file_identity(source_role_path)
    evidence = build_l2_real_player_evidence_v1(
        role_history=roles,
        player_snapshot=snapshot,
        snapshot_source_identity=_identity(
            snapshot_path, args.snapshot_identity
        ),
        role_source_identity=role_identity,
    )
    evidence.role_history.to_parquet(
        output / "l2-role-history.parquet", index=False
    )
    evidence.residual_history.to_parquet(
        output / "l2-residual-history.parquet", index=False
    )
    _write_json(output / "l2-evidence-receipt.json", evidence.receipt)
    sys.stdout.buffer.write(canonical_json_bytes(evidence.receipt) + b"\n")
    return 0


def _calibrate_l2(args: argparse.Namespace) -> int:
    evidence_dir = Path(args.evidence_dir).resolve(strict=True)
    role_path = evidence_dir / "l2-role-history.parquet"
    residual_path = evidence_dir / "l2-residual-history.parquet"
    receipt_path = evidence_dir / "l2-evidence-receipt.json"
    for path in (role_path, residual_path, receipt_path):
        if not path.is_file():
            raise BeliefEvidenceCliError(f"L2 evidence file is absent: {path}")
    receipt = _read_json(receipt_path)
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != evidence_contract.L2_EVIDENCE_SCHEMA
        or receipt.get("uses_player_outcomes") is not True
        or receipt.get("uses_lineup_outcomes") is not False
        or receipt.get("historical_lineup_scoring_licensed") is not False
    ):
        raise BeliefEvidenceCliError("L2 evidence receipt boundary differs")
    roles = pd.read_parquet(role_path)
    residuals = pd.read_parquet(residual_path)
    if receipt.get("role_history_sha256") != transition_frame_sha256(roles):
        raise BeliefEvidenceCliError("L2 role evidence/receipt hash differs")
    if receipt.get("residual_history_sha256") != evidence_contract._records_sha256(
        residuals, evidence_contract.L2_RESIDUAL_COLUMNS
    ):
        raise BeliefEvidenceCliError("L2 residual evidence/receipt hash differs")
    release = build_l2_role_jump_calibration_release_v1(
        role_history=roles,
        residual_history=residuals,
        source_identities={
            "evidence_receipt": local_file_identity(receipt_path),
            "role_history": local_file_identity(role_path),
            "residual_history": local_file_identity(residual_path),
        },
        code_sha=str(args.code_sha),
    )
    output = Path(args.output_file).resolve()
    if output.exists() or not output.parent.is_dir():
        raise BeliefEvidenceCliError(
            "L2 calibration output must be a new file in an existing directory"
        )
    _write_json(output, release)
    sys.stdout.buffer.write(canonical_json_bytes(release) + b"\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke = subparsers.add_parser("schema-smoke")
    smoke.add_argument("--snapshot", required=True)
    smoke.add_argument("--snapshot-identity")
    smoke.set_defaults(func=_schema_smoke)

    l1 = subparsers.add_parser("extract-l1")
    l1.add_argument("--snapshot", required=True)
    l1.add_argument("--snapshot-identity")
    l1.add_argument("--bank-manifest", required=True)
    l1.add_argument("--output-dir", required=True)
    l1.set_defaults(func=_extract_l1)

    l2 = subparsers.add_parser("extract-l2")
    l2.add_argument("--snapshot", required=True)
    l2.add_argument("--snapshot-identity")
    l2.add_argument("--role-history")
    l2.add_argument("--role-source-identity")
    l2.add_argument("--output-dir", required=True)
    l2.set_defaults(func=_extract_l2)

    calibrate_l2 = subparsers.add_parser("calibrate-l2")
    calibrate_l2.add_argument("--evidence-dir", required=True)
    calibrate_l2.add_argument("--code-sha", required=True)
    calibrate_l2.add_argument("--output-file", required=True)
    calibrate_l2.set_defaults(func=_calibrate_l2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
