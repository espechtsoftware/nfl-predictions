#!/usr/bin/env python3
"""Run the sole licensed A2a outcome-bearing dependence remeasurement.

The historical path is deliberately default-off and contains no lineup,
candidate, optimizer, or portfolio import.  ``--mode smoke`` touches only the
already-locked score-free catalog and one player-world artifact.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Final

from google.cloud import bigquery, storage
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_a2a_rank_factor_split_census as a2a_source  # noqa: E402
from nfl_dfs.analysis import a2a_production_law_dependence as decision  # noqa: E402
from nfl_dfs.analysis.final_served_dependence import evaluate_dependence  # noqa: E402
from nfl_dfs.research import a2a_rank_factor_split as transform  # noqa: E402
from nfl_dfs.research.object_identity import (  # noqa: E402
    content_identity,
    live_object_receipt,
    same_object,
)


PROJECT: Final = "nfl-predictions-503414"
PLAYER_TABLE: Final = f"{PROJECT}.nfl_predictions.slate_player_features"
SOURCE_PANELS: Final = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
RUN_ID: Final = "20260820-a2a-production-law-dependence-remeasurement-v1"
PROTOCOL: Final = ROOT / (
    "reports/2026-08-20-a2a-production-law-dependence-"
    "remeasurement-protocol.md"
)
PROTOCOL_SHA256: Final = (
    "d9e5246b82c010b61fb8a9ef0202873b74e48092d4447c8c68bae1c8fe44389a"
)
TRANSFORM_SOURCE: Final = ROOT / "src/nfl_dfs/research/a2a_rank_factor_split.py"
TRANSFORM_SOURCE_SHA256: Final = (
    "208bcc1707edc53fec7905025572a447d2deef9fbdb725332016f98c60138d02"
)
ESTIMATOR_SOURCE: Final = ROOT / "src/nfl_dfs/analysis/final_served_dependence.py"
ESTIMATOR_SOURCE_SHA256: Final = (
    "85acc05b716fe6d3f39dce46d645c2652e8630a620df8b464dbfb16f2d1e3ffd"
)
DECISION_SOURCE: Final = ROOT / (
    "src/nfl_dfs/analysis/a2a_production_law_dependence.py"
)
DECISION_SOURCE_SHA256: Final = (
    "9bb4cede575bc811abc542e38ec617d7ad5cd822dbe7e1c9c028397af0415978"
)
SOURCE_ADAPTER: Final = ROOT / "scripts/run_a2a_rank_factor_split_census.py"
SOURCE_ADAPTER_SHA256: Final = (
    "24ddb3caceda3d660bed39fcdec84575b3545a2717e75ff944dc86319ef75ad1"
)

A2A_RESULT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    "a2a-rank-factor-split-runs/"
    "20260820-a2a-rank-factor-split-scorefree-v2/result.json"
)
A2A_RESULT_GENERATION: Final = "1787248289501941"
A2A_RESULT_SHA256: Final = (
    "86f72b40b714dd186dd81e698b390eb9e0d5dd3d7b5c96eb42c92f5d213c6774"
)
A2A_RESULT_BYTES: Final = 884_522
A2A_RESULT_LOCAL: Final = ROOT / (
    "reports/a2a-rank-factor-split-runs/"
    "20260820-a2a-rank-factor-split-scorefree-v2/result.json"
)
A2A_PROTOCOL_SHA256: Final = (
    "329379ebd7be5e4a92ee34f8a8dd9ae2f6dca90517a81627800f5756852eeab7"
)

CONTROL_REPORT: Final = ROOT / (
    "reports/production-law-dependence-runs/"
    "20260817-production-law-dependence-remeasurement-v1/report.json"
)
CONTROL_REPORT_SHA256: Final = (
    "5b92339b2a9118727d41a8f4b91e982c5478318029c216652d66b7cdd113e696"
)

OUTPUT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    "a2a-production-law-dependence-runs/"
    f"{RUN_ID}/report.json"
)
OUTCOME_SQL: Final = f"""
SELECT season, week, id AS player_id, actual
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""

EXPECTED_ACCOUNTING: Final = {
    "eligible_team_slate_groups": 1_194,
    "covered_groups": 1_041,
    "skipped_groups": 153,
    "skipped_group_reasons": {
        "zero_eligible_qb": 28,
        "multiple_eligible_qbs": 118,
        "fewer_than_two_eligible_wrs": 7,
    },
    "eligible_rows": 9_469,
    "covered_qb_anchor_rows_unchanged": 1_041,
    "directly_transformed_non_qb_rows": 7_171,
    "skipped_group_eligible_rows_unchanged": 1_257,
}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _validate_static_sources() -> dict[str, Any]:
    expected = {
        PROTOCOL: PROTOCOL_SHA256,
        TRANSFORM_SOURCE: TRANSFORM_SOURCE_SHA256,
        ESTIMATOR_SOURCE: ESTIMATOR_SOURCE_SHA256,
        DECISION_SOURCE: DECISION_SOURCE_SHA256,
        SOURCE_ADAPTER: SOURCE_ADAPTER_SHA256,
        A2A_RESULT_LOCAL: A2A_RESULT_SHA256,
        CONTROL_REPORT: CONTROL_REPORT_SHA256,
    }
    observed = {}
    for path, digest in expected.items():
        if not path.is_file() or _sha(path) != digest:
            raise RuntimeError(f"A2a remeasurement static source differs: {path}")
        observed[str(path.relative_to(ROOT))] = digest
    if transform.GENERIC_ATTENUATION != 0.5 or \
            transform.QB_WR_ALLOCATION != 1.0 or \
            transform.VERSION != "a2a-rank-factor-split-scorefree-v2" or \
            tuple(transform.REGISTERED_BLOCKS) != decision.REGISTERED_BLOCKS:
        raise RuntimeError("A2a remeasurement transform dose or grid differs")
    return observed


def _validate_control_reference() -> dict[str, Any]:
    report = a2a_source._strict_json(CONTROL_REPORT.read_bytes())
    if report.get("run_id") != \
            "20260817-production-law-dependence-remeasurement-v1" or \
            report.get("uses_realized_outcomes") is not True or \
            report.get("candidate_or_lineup_scores_read") is not False or \
            report.get("source_lock", {}).get("sha256") != \
            a2a_source.SOURCE_LOCK_SHA256:
        raise RuntimeError("A2a remeasurement control reference differs")
    reports = [report.get("aggregate"), *[
        report.get("blocks", {}).get(block) for block in decision.REGISTERED_BLOCKS
    ]]
    for item in reports:
        if not isinstance(item, Mapping):
            raise RuntimeError("A2a remeasurement control report grid differs")
        cells = item.get("cells")
        if not isinstance(cells, Mapping) or set(cells) != set(
            decision.REGISTERED_CELLS
        ):
            raise RuntimeError("A2a remeasurement control cells differ")
        for cell in decision.REGISTERED_CELLS:
            row = cells[cell]
            if row.get("realized_estimate") != decision.REALIZED_TARGETS[cell] or \
                    row.get("equivalence_band_abs_log") != \
                    decision.EQUIVALENCE_BANDS[cell]:
                raise RuntimeError("A2a remeasurement realized reference differs")
    aggregate = report["aggregate"]["cells"]
    for cell in decision.REGISTERED_CELLS:
        if aggregate[cell].get("log_simulated_to_realized") != \
                decision.CONTROL_POINT_GAPS[cell] or \
                aggregate[cell].get("classification") != \
                decision.CONTROL_CLASSIFICATIONS[cell]:
            raise RuntimeError("A2a remeasurement control gap differs")
    return {
        "sha256": CONTROL_REPORT_SHA256,
        "run_id": report["run_id"],
        "source_lock_sha256": report["source_lock"]["sha256"],
    }


def _load_a2a_license(gcs: storage.Client) -> dict[str, Any]:
    receipt, raw = live_object_receipt(gcs, A2A_RESULT_URI)
    expected = {
        "uri": A2A_RESULT_URI,
        "generation": A2A_RESULT_GENERATION,
        "sha256": A2A_RESULT_SHA256,
        "bytes": A2A_RESULT_BYTES,
    }
    if not same_object(receipt, expected) or raw != A2A_RESULT_LOCAL.read_bytes():
        raise RuntimeError("A2a remeasurement mechanism-license identity differs")
    result = a2a_source._strict_json(raw)
    fixed = {
        "run_id": "20260820-a2a-rank-factor-split-scorefree-v2",
        "mode": "full",
        "protocol_sha256": A2A_PROTOCOL_SHA256,
        "disposition": "a2a-scorefree-mechanism-passes",
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "historical_remeasurement_licensed": True,
        "exact80_scoring_licensed": False,
        "single_stack_arm_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    if any(result.get(key) != value for key, value in fixed.items()) or \
            result.get("gate", {}).get("passes") is not True or \
            result.get("source_lock", {}).get("sha256") != \
            a2a_source.SOURCE_LOCK_SHA256 or \
            len(result.get("source_artifacts", [])) != 270:
        raise RuntimeError("A2a remeasurement mechanism license differs")
    return {
        **expected,
        "disposition": result["disposition"],
        "historical_remeasurement_licensed": True,
    }


def _query_outcomes(
    client: bigquery.Client,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    parameters = [bigquery.ScalarQueryParameter(
        "r0_panel", "STRING", SOURCE_PANELS[0],
    )]
    job = client.query(
        OUTCOME_SQL,
        job_config=bigquery.QueryJobConfig(query_parameters=parameters),
    )
    result = job.result()
    frame = result.to_dataframe(create_bqstorage_client=False)
    return frame, {
        "job_id": job.job_id,
        "location": job.location,
        "created": job.created.isoformat() if job.created else None,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "query_sha256": sha256(OUTCOME_SQL.encode()).hexdigest(),
        "selected_fields": ["season", "week", "player_id", "actual"],
    }


def _validate_artifact_metadata(
    gcs: storage.Client,
    artifacts: Sequence[Mapping[str, Any]],
) -> None:
    """Validate the complete immutable grid without downloading a body."""
    for index, row in enumerate(artifacts, start=1):
        uri = str(row["uri"])
        bucket_name, marker, object_name = uri[5:].partition("/")
        if not marker or not bucket_name or not object_name:
            raise RuntimeError("A2a remeasurement artifact URI differs")
        blob = gcs.bucket(bucket_name).blob(object_name)
        blob.reload()
        updated = blob.updated.isoformat() if blob.updated else ""
        if str(blob.generation) != str(row["generation"]) or \
                int(blob.size or -1) != int(row["bytes"]) or \
                updated != str(row["updated"]):
            raise RuntimeError("A2a remeasurement artifact metadata changed")
        if index % 25 == 0 or index == len(artifacts):
            print(
                "A2A_REMEASUREMENT_PREFLIGHT_METADATA_COMPLETE",
                index,
                len(artifacts),
                flush=True,
            )


def _actual_maps(
    frame: pd.DataFrame,
) -> dict[tuple[int, int], dict[str, float]]:
    if frame.empty or frame.duplicated(["season", "week", "player_id"]).any():
        raise RuntimeError("A2a remeasurement outcome population differs")
    result = {}
    for (season, week), group in frame.groupby(["season", "week"], sort=True):
        values = pd.to_numeric(group.actual, errors="coerce")
        finite = np.isfinite(values.to_numpy(dtype=float))
        result[(int(season), int(week))] = {
            str(player_id): float(actual)
            for player_id, actual, keep in zip(
                group.player_id, values, finite, strict=True,
            )
            if keep
        }
    expected = {
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    }
    if set(result) != expected:
        raise RuntimeError("A2a remeasurement outcome slate grid differs")
    return result


def _eligible_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    eligible = [
        dict(row) for row in rows
        if row["position"] in {"QB", "RB", "WR", "TE"}
        and float(row["mean_projection"]) >= 4.0
    ]
    eligible.sort(key=lambda row: str(row["player_id"]))
    return eligible


def _build_treatment_population(
    gcs: storage.Client,
    artifacts: Sequence[Mapping[str, Any]],
    catalog: Sequence[Mapping[str, Any]],
    actual: Mapping[tuple[int, int], Mapping[str, float]],
) -> tuple[
    pd.DataFrame,
    dict[str, np.ndarray],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    by_slate = a2a_source._catalog_by_slate(catalog)
    chunks: dict[str, list[np.ndarray]] = {
        block: [] for block in decision.REGISTERED_BLOCKS
    }
    cell_reports: dict[str, list[dict[str, Any]]] = {
        block: [] for block in decision.REGISTERED_BLOCKS
    }
    frame_rows: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []
    slate_universes: dict[tuple[int, int], frozenset[str]] = {}

    for locked in artifacts:
        season = int(locked["season"])
        week = int(locked["week"])
        seed = int(locked["seed"])
        block = decision.REGISTERED_BLOCKS[seed]
        slate = (season, week)
        player_ids, control_draws, receipt = a2a_source._download_player_worlds(
            gcs, locked,
        )
        universe = frozenset(player_ids)
        prior = slate_universes.setdefault(slate, universe)
        if universe != prior:
            raise RuntimeError("A2a remeasurement block player universes differ")
        slate_catalog = a2a_source._catalog_rows_for_artifact(
            by_slate.get(slate, []), player_ids,
        )
        treatment_draws, mechanism = transform.transform_and_measure_slate(
            catalog_rows=slate_catalog,
            player_ids=player_ids,
            control_draws=control_draws,
            expected_worlds=10_000,
        )
        if mechanism.get("mechanics", {}).get("passes") is not True:
            raise RuntimeError("A2a remeasurement mechanical invariant failed")
        cell_reports[block].append(mechanism)

        eligible = _eligible_rows(slate_catalog)
        ids = [str(row["player_id"]) for row in eligible]
        missing = [player_id for player_id in ids if player_id not in actual[slate]]
        if missing:
            raise RuntimeError("A2a remeasurement eligible outcomes are missing")
        artifact_index = {player_id: index for index, player_id in enumerate(player_ids)}
        if set(ids) - set(artifact_index):
            raise RuntimeError("A2a remeasurement eligible universe differs")
        chunks[block].append(treatment_draws[[artifact_index[value] for value in ids]])
        if seed == 0:
            frame_rows.extend({
                "season": season,
                "week": week,
                "gsis_id": player_id,
                "team": str(row["team"]),
                "position": str(row["position"]),
                "actual": float(actual[slate][player_id]),
                "mean_projection": float(row["mean_projection"]),
            } for row, player_id in zip(eligible, ids, strict=True))
        downloads.append({
            "season": season,
            "week": week,
            "block": block,
            "panel_run_id": locked["panel_run_id"],
            **receipt,
        })
        print("A2A_REMEASUREMENT_ARTIFACT_COMPLETE", season, week, block, flush=True)

    frame = pd.DataFrame(frame_rows)
    block_draws = {
        block: np.concatenate(chunks[block], axis=0)
        for block in decision.REGISTERED_BLOCKS
    }
    if len(frame) != 9_469 or frame.duplicated(
        ["season", "week", "gsis_id"]
    ).any() or any(
        values.shape != (9_469, 10_000) for values in block_draws.values()
    ) or len(downloads) != 270:
        raise RuntimeError("A2a remeasurement assembled population differs")
    block_mechanics = {}
    for block in decision.REGISTERED_BLOCKS:
        combined = transform.combine_reports(cell_reports[block])
        if combined.get("mechanics", {}).get("passes") is not True or \
                combined.get("slates") != 54:
            raise RuntimeError("A2a remeasurement block mechanics differ")
        block_mechanics[block] = combined["mechanics"]
    return frame, block_draws, downloads, block_mechanics


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    def normalize(item: Any) -> Any:
        if item is None or isinstance(item, (str, bool)):
            return item
        if isinstance(item, (int, np.integer)) and not isinstance(item, bool):
            return int(item)
        if isinstance(item, (float, np.floating)):
            number = float(item)
            if not math.isfinite(number):
                raise RuntimeError("A2a remeasurement result contains nonfinite data")
            return number
        if isinstance(item, Mapping):
            if not all(isinstance(key, str) for key in item):
                raise RuntimeError("A2a remeasurement result key is non-string")
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        raise RuntimeError(f"A2a remeasurement result type differs: {type(item)!r}")

    return (json.dumps(
        normalize(value), sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ) + "\n").encode()


def _upload_create_only(
    gcs: storage.Client, uri: str, payload: bytes,
) -> dict[str, Any]:
    if uri != OUTPUT_URI:
        raise RuntimeError("A2a remeasurement output URI differs")
    bucket_name, marker, object_name = uri[5:].partition("/")
    if not marker or not bucket_name or not object_name:
        raise RuntimeError("A2a remeasurement output URI is invalid")
    blob = gcs.bucket(bucket_name).blob(object_name)
    blob.upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    receipt = {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "create_only": True,
    }
    content_identity(receipt)
    return receipt


def run_outcome_blind_smoke() -> dict[str, Any]:
    """Exercise the exact new source/transform adapter without actuals."""
    sources = _validate_static_sources()
    control_reference = _validate_control_reference()
    gcs = storage.Client(project=PROJECT)
    license_receipt = _load_a2a_license(gcs)
    lock_receipt, artifacts, catalog = a2a_source._load_source_lock(
        gcs,
        uri=a2a_source.SOURCE_LOCK_URI,
        generation=a2a_source.SOURCE_LOCK_GENERATION,
        digest=a2a_source.SOURCE_LOCK_SHA256,
    )
    locked = artifacts[0]
    player_ids, draws, artifact_receipt = a2a_source._download_player_worlds(
        gcs, locked,
    )
    slate_rows = a2a_source._catalog_by_slate(catalog)[(2023, 1)]
    treatment, report = transform.transform_and_measure_slate(
        slate_rows, player_ids, draws, expected_worlds=10_000,
    )
    if report.get("mechanics", {}).get("passes") is not True or \
            treatment.shape != draws.shape:
        raise RuntimeError("A2a remeasurement outcome-blind smoke failed")
    return {
        "version": "a2a-production-law-dependence-outcome-blind-smoke-v1",
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "static_sources": sources,
        "control_reference": control_reference,
        "mechanism_license": license_receipt,
        "source_lock": lock_receipt,
        "artifact": artifact_receipt,
        "slate": [2023, 1],
        "block": "R0",
        "mechanics": report["mechanics"],
        "coverage": decision.support_accounting(slate_rows),
    }


def run_historical(
    *,
    execute_frozen: bool,
    protocol_sha256: str,
    output_uri: str,
) -> dict[str, Any]:
    # This gate deliberately precedes source validation and all client
    # construction.  Importing the runner or omitting either switch cannot
    # contact storage or BigQuery.
    if not execute_frozen or os.environ.get("A2A_REMEASUREMENT_ENABLED") != "1":
        raise RuntimeError("A2a historical remeasurement is default-off")
    if protocol_sha256 != PROTOCOL_SHA256 or output_uri != OUTPUT_URI:
        raise RuntimeError("A2a historical remeasurement frozen identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image):
        raise RuntimeError("A2a remeasurement immutable code/image is required")

    sources = _validate_static_sources()
    control_reference = _validate_control_reference()
    gcs = storage.Client(project=PROJECT)
    license_receipt = _load_a2a_license(gcs)
    lock_receipt, artifacts, catalog = a2a_source._load_source_lock(
        gcs,
        uri=a2a_source.SOURCE_LOCK_URI,
        generation=a2a_source.SOURCE_LOCK_GENERATION,
        digest=a2a_source.SOURCE_LOCK_SHA256,
    )
    # Complete metadata validation is the final boundary before the sole
    # actual-outcome query.  No artifact body has been read by this path yet.
    _validate_artifact_metadata(gcs, artifacts)

    bq = bigquery.Client(project=PROJECT)
    outcome_frame, query_receipt = _query_outcomes(bq)
    actual = _actual_maps(outcome_frame)
    frame, block_draws, downloads, block_mechanics = _build_treatment_population(
        gcs, artifacts, catalog, actual,
    )
    coverage = decision.support_accounting(catalog)
    for key, value in EXPECTED_ACCOUNTING.items():
        if coverage.get(key) != value:
            raise RuntimeError("A2a remeasurement coverage accounting differs")

    block_reports = {}
    for block in decision.REGISTERED_BLOCKS:
        block_reports[block] = evaluate_dependence(frame, block_draws[block])
        print("A2A_REMEASUREMENT_BLOCK_COMPLETE", block, flush=True)
    aggregate_draws = np.concatenate(
        [block_draws[block] for block in decision.REGISTERED_BLOCKS], axis=1,
    )
    aggregate = evaluate_dependence(frame, aggregate_draws)
    judged = decision.evaluate_remeasurement(block_reports, aggregate)
    result = {
        **judged,
        **judged["licenses"],
        "run_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": code_sha,
        "analysis_image": image,
        "static_source_hashes": sources,
        "mechanism_license": license_receipt,
        "control_reference": control_reference,
        "source_lock": lock_receipt,
        "source_artifacts": downloads,
        "block_mechanics": block_mechanics,
        "coverage_accounting": coverage,
        "outcome_query": query_receipt,
        "outcome_query_issued_after_complete_source_preflight": True,
        "outcome_population": {
            "slates": 54,
            "eligible_player_rows": len(frame),
            "missing_eligible_outcomes": 0,
            "duplicate_eligible_keys": int(frame.duplicated(
                ["season", "week", "gsis_id"]
            ).sum()),
        },
    }
    payload = _canonical_json(result)
    output = _upload_create_only(gcs, output_uri, payload)
    print("A2A_PRODUCTION_LAW_DEPENDENCE_RESULT " + json.dumps({
        "disposition": result["disposition"],
        "output": output,
    }, sort_keys=True), flush=True)
    return {**result, "output": output}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "historical"), required=True)
    parser.add_argument("--execute-frozen", action="store_true")
    parser.add_argument("--protocol-sha256", default="")
    parser.add_argument("--output-uri", default="")
    args = parser.parse_args()
    if args.mode == "smoke":
        if args.execute_frozen or args.output_uri:
            raise SystemExit("outcome-blind smoke cannot carry historical switches")
        print(json.dumps(run_outcome_blind_smoke(), sort_keys=True, allow_nan=False))
        return
    run_historical(
        execute_frozen=args.execute_frozen,
        protocol_sha256=args.protocol_sha256,
        output_uri=args.output_uri,
    )


if __name__ == "__main__":
    main()
