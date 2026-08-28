#!/usr/bin/env python3
"""Calibrate the single prespecified R6 L2b empirical fallback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

from nfl_dfs.research.belief_world_v1 import canonical_json_bytes
from nfl_dfs.research.corpus_r6_belief_evidence_v1 import (
    L2_EVIDENCE_SCHEMA,
    L2_RESIDUAL_COLUMNS,
    _records_sha256,
    local_file_identity,
)
from nfl_dfs.research.corpus_r6_l2_base_rate_v1 import (
    build_l2_base_rate_calibration_release_v1,
)
from nfl_dfs.research.latent_role_state import transition_frame_sha256


class L2BaseRateCliError(ValueError):
    """The evidence directory or create-only output request was not exact."""


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise L2BaseRateCliError(f"cannot read JSON {path}") from exc


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _calibrate(args: argparse.Namespace) -> int:
    evidence_dir = Path(args.evidence_dir).resolve(strict=True)
    role_path = evidence_dir / "l2-role-history.parquet"
    residual_path = evidence_dir / "l2-residual-history.parquet"
    receipt_path = evidence_dir / "l2-evidence-receipt.json"
    for path in (role_path, residual_path, receipt_path):
        if not path.is_file():
            raise L2BaseRateCliError(f"L2 evidence file is absent: {path}")
    receipt = _read_json(receipt_path)
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != L2_EVIDENCE_SCHEMA
        or receipt.get("uses_player_outcomes") is not True
        or receipt.get("uses_lineup_outcomes") is not False
        or receipt.get("historical_lineup_scoring_licensed") is not False
    ):
        raise L2BaseRateCliError("L2 evidence receipt boundary differs")
    roles = pd.read_parquet(role_path)
    residuals = pd.read_parquet(residual_path)
    if receipt.get("role_history_sha256") != transition_frame_sha256(roles):
        raise L2BaseRateCliError("L2 role evidence/receipt hash differs")
    if receipt.get("residual_history_sha256") != _records_sha256(
        residuals, L2_RESIDUAL_COLUMNS
    ):
        raise L2BaseRateCliError("L2 residual evidence/receipt hash differs")
    release = build_l2_base_rate_calibration_release_v1(
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
        raise L2BaseRateCliError(
            "L2b output must be a new file in an existing directory"
        )
    _write_json(output, release)
    summary = {
        "schema": "corpus-r6-l2-base-rate-calibration-summary/v1",
        "calibration_id": release["calibration_id"],
        "release_sha256": release["release_sha256"],
        "candidate_definition": release["candidate_definition"],
        "comparator_definition": release["comparator_definition"],
        "folds": release["folds"],
        "historical_application_registry_sha256": release[
            "historical_application_registry_sha256"
        ],
        "historical_application_registry": {
            fold_id: {
                "target_season": entry["target_season"],
                "role_train_first_season": entry[
                    "role_train_first_season"
                ],
                "role_train_last_season": entry["role_train_last_season"],
                "role_train_row_count": entry["role_train_row_count"],
                "role_training_frame_sha256": entry[
                    "role_training_frame_sha256"
                ],
                "residual_source_fold_ids": entry[
                    "residual_source_fold_ids"
                ],
                "residual_source_seasons": entry["residual_source_seasons"],
                "residual_group_summaries": entry[
                    "residual_group_summaries"
                ],
                "residual_samples_sha256": entry[
                    "residual_samples_sha256"
                ],
                "uses_target_role_labels_for_fit": False,
                "uses_target_player_outcomes_for_fit": False,
                "application_ready": entry["application_ready"],
                "application_sha256": entry["application_sha256"],
            }
            for fold_id, entry in release[
                "historical_application_registry"
            ].items()
        },
        "final_fit_seasons": release["final_fit_seasons"],
        "final_fit_scope": release["final_fit_scope"],
        "residual_group_summaries": release["residual_group_summaries"],
        "gate": release["gate"],
        "prospective_challenger_bank_generation_licensed": release[
            "prospective_challenger_bank_generation_licensed"
        ],
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    sys.stdout.buffer.write(canonical_json_bytes(summary) + b"\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output-file", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    return _calibrate(_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
