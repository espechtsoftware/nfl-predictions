#!/usr/bin/env python3
"""Run the frozen downstream ATLAS realized-score diagnostic once."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.analysis.atlas_historical_score import (
    aggregate_diagnostic,
    canonical_roster,
    compare_slate,
)
from nfl_dfs.analysis.atlas_matched_diversity import (
    REGISTERED_SEEDS,
    replace_native_boom_book,
)
from nfl_dfs.inference.multiseed_portfolio import (
    combine_cbwu_order_invariant_books,
)
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries

from run_cbwu_seed_order_audit import (
    _candidate_batch,
    _download_artifact,
    _query,
    _upload_create_only,
)
from render_atlas_matched_diversity_repair4_command import render as render_repair4


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
SOURCE_PANELS = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
REPAIR_PANEL = "20260816-atlas-mvp-repair-r3-2025-v1"
UPSTREAM_CODE_SHA = "60f296fdad769b30c0bb7334118698f156e462b9"
UPSTREAM_IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@"
    "sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb"
)
UPSTREAM_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    "20260816-atlas-matched-diversity-mvp-v1-repair4"
)
UPSTREAM_LEDGER = Path(
    "reports/atlas-matched-diversity-runs/"
    "20260816-atlas-matched-diversity-mvp-v1-repair4/executions.txt"
)
UPSTREAM_LEDGER_SHA256 = (
    "0ca2e0635a8cb572912aeb19156a388c9a87ba8bc0f340998a6b39eb2b28c3fd"
)


def _load_upstream_executions() -> dict[tuple[int, int], str]:
    if not UPSTREAM_LEDGER.is_file() or sha256(
        UPSTREAM_LEDGER.read_bytes()
    ).hexdigest() != UPSTREAM_LEDGER_SHA256:
        raise RuntimeError("ATLAS historical repair4 execution ledger differs")
    result: dict[tuple[int, int], str] = {}
    for raw in UPSTREAM_LEDGER.read_text(encoding="utf-8").splitlines():
        fields = raw.split()
        if len(fields) != 5:
            raise RuntimeError("ATLAS historical repair4 ledger row differs")
        season_text, week_text, job, execution, uri = fields
        season, week = int(season_text), int(week_text)
        expected_job = f"atlas-md-s{season}-w{week}-r4"
        expected_uri = f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json"
        if job != expected_job or not execution.startswith(expected_job + "-") or \
                uri != expected_uri or (season, week) in result:
            raise RuntimeError("ATLAS historical repair4 ledger identity differs")
        result[(season, week)] = execution
    expected = {
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    }
    if set(result) != expected or len(set(result.values())) != 54:
        raise RuntimeError("ATLAS historical repair4 ledger grid differs")
    return result


UPSTREAM_EXECUTIONS = _load_upstream_executions()
UPSTREAM_EXECUTION_NAMES = {
    f"{season}-{week}": name
    for (season, week), name in UPSTREAM_EXECUTIONS.items()
}
UPSTREAM_MANIFEST_SHA256 = (
    "083a5e158053cd03f509bfebe518516af695773c029a78a8e80aa6aa336e5df6"
)
UPSTREAM_GRID_COMMAND = render_repair4(UPSTREAM_PREFIX)
PROTOCOL = Path("reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md")
PROTOCOL_SHA256 = "4b618b5f8b8b8ed61dc5518e5b8b1cb8d5941e92f088ddb0a53af05d37f4239e"
PARITY_AMENDMENT = Path(
    "reports/2026-08-16-atlas-historical-score-source-parity-amendment.md"
)
PARITY_AMENDMENT_SHA256 = (
    "6e3997e4e81ffe20063fdf76aff7c3655cdd1424aea350a5e29a681a1cd1832e"
)
SHARDED_UPSTREAM_AMENDMENT = Path(
    "reports/2026-08-16-atlas-historical-score-sharded-upstream-amendment.md"
)
SHARDED_UPSTREAM_AMENDMENT_SHA256 = (
    "ce32274be00678cdef24b3d174578a2e2ce212164166da2a712a9df1562fcd5d"
)
REPAIR4_UPSTREAM_AMENDMENT = Path(
    "reports/2026-08-16-atlas-historical-score-repair4-upstream-amendment.md"
)
REPAIR4_UPSTREAM_AMENDMENT_SHA256 = (
    "32bb95916d53b0a95472adad6d0aebcb6f7fd1631b07b3c29b1cf31950dffd17"
)
HIGH_TAIL_GUARD_AMENDMENT = Path(
    "reports/2026-08-16-atlas-historical-high-tail-guard-amendment.md"
)
HIGH_TAIL_GUARD_AMENDMENT_SHA256 = (
    "b98227830aed550a3f024b85695a3c0bbf7195834320370c41cf3c3e5ca5693d"
)
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/"
    "20260816-atlas-historical-score-diagnostic-v2"
)
UPSTREAM_RECEIPT_URI = f"{OUTPUT_PREFIX}/upstream-receipt.json"
OUTPUT_URI = f"{OUTPUT_PREFIX}/report.json"

SOURCE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256, actual_score
FROM `{SOURCE_TABLE}`
WHERE (
  panel_run_id IN UNNEST(@source_panels)
  AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1)
) OR (
  panel_run_id=@repair_panel AND season=2025 AND week=1
)
ORDER BY panel_run_id, season, week, cand_ix
"""
PLAYER_SQL = f"""
SELECT season, week, id AS player_id, name AS player_name, pos AS position,
       team, opp AS opponent, game_id, salary, proj AS mean_projection,
       actual
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("ATLAS historical GCS URI must name one object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("ATLAS historical GCS URI is invalid")
    return bucket, name


def _download_json(
    client: storage.Client, uri: str,
) -> tuple[dict, dict[str, Any]]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    payload = json.loads(raw)
    return payload, {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }


def _validate_execution(value: dict, season: int, week: int) -> None:
    name = UPSTREAM_EXECUTIONS[(season, week)]
    if value.get("metadata", {}).get("name") != name:
        raise RuntimeError("ATLAS historical upstream execution name differs")
    status = value.get("status", {})
    completed = [row for row in status.get("conditions", [])
                 if row.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0 or \
            not status.get("completionTime"):
        raise RuntimeError("ATLAS historical upstream execution was not successful")
    spec = value.get("spec", {})
    template = spec.get("template", {}).get("spec", {})
    containers = template.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("ATLAS historical upstream task shape differs")
    container = containers[0]
    expected_uri = f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json"
    if container.get("image") != UPSTREAM_IMAGE or \
            container.get("command") != ["python"] or \
            container.get("args") != [
                "-c", UPSTREAM_GRID_COMMAND, "--season", str(season),
                "--week", str(week),
                "--output-uri", expected_uri,
            ]:
        raise RuntimeError("ATLAS historical upstream command/image differs")
    env = {row.get("name"): str(row.get("value", ""))
           for row in container.get("env", [])}
    if env != {"CODE_SHA": UPSTREAM_CODE_SHA, "ANALYSIS_IMAGE": UPSTREAM_IMAGE}:
        raise RuntimeError("ATLAS historical upstream environment differs")
    if container.get("resources", {}).get("limits") != {
        "cpu": "4", "memory": "16Gi",
    } or template.get("maxRetries") != 0 or \
            str(template.get("timeoutSeconds")) != "43200" or \
            template.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("ATLAS historical upstream resources differ")


def _validate_upstream_receipt(receipt: dict) -> dict[str, dict]:
    if receipt.get("version") != "atlas-historical-upstream-receipt-v4" or \
            receipt.get("uses_realized_outcomes") is not False or \
            receipt.get("upstream_code_sha") != UPSTREAM_CODE_SHA or \
            receipt.get("upstream_image") != UPSTREAM_IMAGE or \
            receipt.get("upstream_manifest_sha256") != \
            UPSTREAM_MANIFEST_SHA256 or \
            receipt.get("upstream_execution_ledger_sha256") != \
            UPSTREAM_LEDGER_SHA256 or \
            receipt.get("repair4_upstream_amendment_sha256") != \
            REPAIR4_UPSTREAM_AMENDMENT_SHA256:
        raise RuntimeError("ATLAS historical upstream receipt identity differs")
    forbidden = {
        "upstream_original_execution_ledger_sha256",
        "cbc_retry_protocol_sha256", "failed_execution_sha256",
        "failed_log_sha256", "replacement_receipt_sha256",
        "single_shard_replacement",
    }
    if forbidden.intersection(receipt):
        raise RuntimeError("ATLAS historical repair4 receipt carries repair2 fields")
    strict_harvest = receipt.get("strict_harvest", {})
    expected_harvest = {
        "completion_sha256", "report_sha256", "season_reports_sha256",
        "shards_sha256", "execution_metadata_sha256",
    }
    if set(strict_harvest) != expected_harvest or any(
        not re.fullmatch(r"[0-9a-f]{64}", str(value))
        for value in strict_harvest.values()
    ):
        raise RuntimeError("ATLAS historical repair4 strict harvest differs")
    executions = receipt.get("executions", {})
    if set(executions) != set(UPSTREAM_EXECUTION_NAMES):
        raise RuntimeError("ATLAS historical upstream receipt shard grid differs")
    for season, week in UPSTREAM_EXECUTIONS:
        _validate_execution(executions[f"{season}-{week}"], season, week)
    objects = receipt.get("objects", {})
    expected = {"report", "season-2023", "season-2024", "season-2025"}
    if set(objects) != expected:
        raise RuntimeError("ATLAS historical upstream object receipt differs")
    for key, value in objects.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))) or \
                not str(value.get("generation", "")).isdigit() or \
                int(value.get("bytes") or 0) <= 0:
            raise RuntimeError(f"ATLAS historical upstream {key} receipt differs")
    if strict_harvest["report_sha256"] != objects["report"]["sha256"]:
        raise RuntimeError("ATLAS historical repair4 aggregate hash differs")
    return objects


def _source_params():
    return [
        bigquery.ArrayQueryParameter("source_panels", "STRING", list(SOURCE_PANELS)),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
    ]


def _player_params():
    return [bigquery.ScalarQueryParameter(
        "r0_panel", "STRING", SOURCE_PANELS[0],
    )]


def _canonical_panel(panel: str) -> str:
    return SOURCE_PANELS[3] if panel == REPAIR_PANEL else panel


def _validate_upstream_reports(
    reports: dict[int, dict], aggregate: dict, receipts: dict[str, dict],
) -> None:
    if aggregate.get("version") != "atlas-matched-diversity-mvp-v1" or \
            aggregate.get("uses_realized_outcomes") is not False or \
            aggregate.get("code_sha") != UPSTREAM_CODE_SHA or \
            aggregate.get("analysis_image") != UPSTREAM_IMAGE or \
            aggregate.get("mechanical") != {
                "seasons": [2023, 2024, 2025], "slates": 54,
                "all_valid": True, "all_global_atlas_additions_200": True,
                "all_native_boom_counts_40": True,
            } or len(aggregate.get("slates", [])) != 54:
        raise RuntimeError("ATLAS historical strict upstream aggregate differs")
    expected_hashes = aggregate.get("season_report_sha256", {})
    for season, report in reports.items():
        if expected_hashes.get(str(season)) != receipts[
            f"season-{season}"
        ]["sha256"] or \
                report.get("season") != season or \
                report.get("version") != "atlas-matched-diversity-mvp-v1" or \
                report.get("uses_realized_outcomes") is not False or \
                report.get("code_sha") != UPSTREAM_CODE_SHA or \
                report.get("analysis_image") != UPSTREAM_IMAGE or \
                len(report.get("slates", [])) != 18:
            raise RuntimeError("ATLAS historical upstream season report differs")


def _actual_maps(players: pd.DataFrame) -> dict[tuple[int, int], dict[str, float]]:
    if players.empty or players.duplicated(["season", "week", "player_id"]).any():
        raise RuntimeError("ATLAS historical player outcomes are missing or duplicate")
    if set(players.season.astype(int)) != {2023, 2024, 2025} or \
            any(sorted(group.week.astype(int).unique()) != list(range(1, 19))
                for _, group in players.groupby("season")):
        raise RuntimeError("ATLAS historical player outcome grid differs")
    maps = {}
    for (season, week), group in players.groupby(["season", "week"], sort=True):
        values = pd.to_numeric(group.actual, errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise RuntimeError("ATLAS historical player outcome is non-finite")
        maps[(int(season), int(week))] = {
            str(player_id): float(actual)
            for player_id, actual in zip(group.player_id, values, strict=True)
        }
    if len(maps) != 54:
        raise RuntimeError("ATLAS historical player outcome slate count differs")
    return maps


def _validate_native_actual_parity(
    sources: pd.DataFrame,
    maps: dict[tuple[int, int], dict[str, float]],
) -> dict[str, Any]:
    if len(sources) != 68_199:
        raise RuntimeError("ATLAS historical native parity row count differs")
    missing = 0
    malformed = 0
    differences = []
    for row in sources.itertuples(index=False):
        roster = [value for value in str(row.players).split(",") if value]
        if len(roster) != 9 or len(set(roster)) != 9:
            malformed += 1
            continue
        actual = maps[(int(row.season), int(row.week))]
        absent = [value for value in roster if value not in actual]
        missing += len(absent)
        if absent:
            continue
        reconstructed = float(sum(actual[value] for value in roster))
        registered = float(row.actual_score)
        differences.append(abs(reconstructed - registered))
    maximum = float(max(differences, default=float("inf")))
    tolerance = 1e-9
    if malformed or missing or len(differences) != len(sources) or \
            maximum > tolerance:
        raise RuntimeError("ATLAS historical native actual-score parity differs")
    return {
        "registered_candidate_rows": len(sources),
        "slots_per_roster": 9,
        "malformed_rosters": malformed,
        "missing_player_outcomes": missing,
        "compared_rows": len(differences),
        "maximum_absolute_error": maximum,
        "absolute_tolerance": tolerance,
        "relative_tolerance": 0.0,
        "source_storage_type": "FLOAT",
    }


def _lineup_rosters(batch) -> list[tuple[str, ...]]:
    return [canonical_roster(lineup.ids) for lineup in batch.candidates]


def _selected(batch) -> tuple[list[int], list[tuple[str, ...]]]:
    indices = select_tail_entries(
        np.asarray(batch.candidate_totals, dtype=np.float32),
        80, 194.0, env={"SELECT_LSE": "0"},
    )
    if len(indices) != 80 or len(set(indices)) != 80:
        raise RuntimeError("ATLAS historical exact-80 selector differs")
    return indices, [canonical_roster(batch.candidates[index].ids) for index in indices]


def _atlas_additions(upstream_slate: dict, native) -> list[Lineup]:
    by_id = {str(row["id"]): row for row in native.player_rows}
    additions = []
    seen = set()
    construction = upstream_slate.get("construction", {})
    if set(construction) != set(REGISTERED_SEEDS):
        raise RuntimeError("ATLAS historical upstream construction seeds differ")
    for seed in REGISTERED_SEEDS:
        enumeration = construction[seed].get("enumeration", {})
        proposals = enumeration.get("proposals", [])
        accepted = [row for row in proposals if row.get("accepted") is True]
        if enumeration.get("uses_realized_outcomes") is not False or \
                int(enumeration.get("candidate_count") or 0) != 40 or \
                len(accepted) != 40:
            raise RuntimeError("ATLAS historical accepted proposal count differs")
        for proposal in accepted:
            roster = canonical_roster(proposal.get("roster", []))
            if roster in seen:
                raise RuntimeError("ATLAS historical global addition repeats")
            try:
                additions.append(Lineup(
                    [by_id[player_id] for player_id in roster], tag="atlas",
                ))
            except KeyError as exc:
                raise RuntimeError("ATLAS historical addition leaves universe") from exc
            seen.add(roster)
    if len(additions) != 200:
        raise RuntimeError("ATLAS historical global addition count differs")
    return additions


def _run_slate(
    *, season: int, week: int, source: pd.DataFrame, catalog: pd.DataFrame,
    actual: dict[str, float], upstream: dict, gcs: storage.Client,
) -> tuple[dict, list[dict]]:
    books = {}
    artifact_receipts = []
    for seed, expected_panel in zip(REGISTERED_SEEDS, SOURCE_PANELS, strict=True):
        group = source[
            source.panel_run_id.astype(str).map(_canonical_panel).eq(expected_panel)
        ].copy()
        uris = group.score_artifact_uri.astype(str).unique()
        digests = group.score_artifact_sha256.astype(str).unique()
        if group.empty or len(uris) != 1 or len(digests) != 1:
            raise RuntimeError("ATLAS historical native source identity differs")
        artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
        books[seed] = _candidate_batch(group, artifact, catalog)
        artifact_receipts.append({
            "season": season, "week": week, "seed": seed,
            "source_panel": str(group.panel_run_id.iloc[0]),
            "canonical_panel": expected_panel, "candidate_rows": len(group),
            **receipt,
        })
    p1 = combine_cbwu_order_invariant_books(
        books, REGISTERED_SEEDS, expected_worlds_per_book=10_000,
    )
    additions = _atlas_additions(upstream, books["R0"])
    treatment_books = {}
    by_seed: dict[str, list[Lineup]] = {seed: [] for seed in REGISTERED_SEEDS}
    for index, lineup in enumerate(additions):
        by_seed[REGISTERED_SEEDS[index // 40]].append(lineup)
    for seed in REGISTERED_SEEDS:
        treatment_books[seed] = replace_native_boom_book(books[seed], by_seed[seed])
    p2 = combine_cbwu_order_invariant_books(
        treatment_books, REGISTERED_SEEDS, expected_worlds_per_book=10_000,
    )
    p1_indices, p1_selected = _selected(p1)
    p2_indices, p2_selected = _selected(p2)
    for name, indices, identities in (
        ("P1", p1_indices, p1_selected), ("P2", p2_indices, p2_selected),
    ):
        expected = upstream.get(name, {})
        if indices != expected.get("exact80_indices") or \
                [list(row) for row in identities] != expected.get("exact80_identities"):
            raise RuntimeError(f"ATLAS historical {name} exact-80 identity differs")
        if int(expected.get("candidate_budget") or 0) != len(
            p1.candidates if name == "P1" else p2.candidates
        ):
            raise RuntimeError(f"ATLAS historical {name} budget differs")
    row = compare_slate(
        season=season, week=week,
        p1_candidates=_lineup_rosters(p1),
        p2_candidates=_lineup_rosters(p2),
        p1_selected=p1_selected, p2_selected=p2_selected,
        actual_by_id=actual,
        atlas_rosters=[canonical_roster(lineup.ids) for lineup in additions],
    )
    return row, artifact_receipts


def run(upstream_receipt_uri: str, output_uri: str) -> dict:
    if upstream_receipt_uri != UPSTREAM_RECEIPT_URI or output_uri != OUTPUT_URI:
        raise RuntimeError("ATLAS historical input/output identity differs")
    if not PROTOCOL.is_file() or _file_sha(PROTOCOL) != PROTOCOL_SHA256:
        raise RuntimeError("ATLAS historical frozen protocol differs")
    if not PARITY_AMENDMENT.is_file() or \
            _file_sha(PARITY_AMENDMENT) != PARITY_AMENDMENT_SHA256:
        raise RuntimeError("ATLAS historical source-parity amendment differs")
    if not SHARDED_UPSTREAM_AMENDMENT.is_file() or \
            _file_sha(SHARDED_UPSTREAM_AMENDMENT) != \
            SHARDED_UPSTREAM_AMENDMENT_SHA256:
        raise RuntimeError("ATLAS historical sharded-upstream amendment differs")
    if not REPAIR4_UPSTREAM_AMENDMENT.is_file() or \
            _file_sha(REPAIR4_UPSTREAM_AMENDMENT) != \
            REPAIR4_UPSTREAM_AMENDMENT_SHA256:
        raise RuntimeError("ATLAS historical repair4-upstream amendment differs")
    if not HIGH_TAIL_GUARD_AMENDMENT.is_file() or \
            _file_sha(HIGH_TAIL_GUARD_AMENDMENT) != \
            HIGH_TAIL_GUARD_AMENDMENT_SHA256:
        raise RuntimeError("ATLAS historical high-tail guard amendment differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("ATLAS historical scorer code/image identity is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    receipt, receipt_object = _download_json(gcs, upstream_receipt_uri)
    object_receipts = _validate_upstream_receipt(receipt)
    upstream_reports = {}
    downloaded_receipts = {}
    for season in (2023, 2024, 2025):
        key = f"season-{season}"
        report, object_receipt = _download_json(
            gcs, f"{UPSTREAM_PREFIX}/season-{season}.json",
        )
        if object_receipt != object_receipts[key]:
            raise RuntimeError("ATLAS historical upstream season object changed")
        upstream_reports[season] = report
        downloaded_receipts[key] = object_receipt
    aggregate, aggregate_receipt = _download_json(gcs, f"{UPSTREAM_PREFIX}/report.json")
    if aggregate_receipt != object_receipts["report"]:
        raise RuntimeError("ATLAS historical upstream aggregate object changed")
    downloaded_receipts["report"] = aggregate_receipt
    _validate_upstream_reports(upstream_reports, aggregate, downloaded_receipts)

    sources = _query(bq, SOURCE_SQL, _source_params())
    players = _query(bq, PLAYER_SQL, _player_params())
    actual_maps = _actual_maps(players)
    parity = _validate_native_actual_parity(sources, actual_maps)

    upstream_by_key = {
        (int(row["season"]), int(row["week"])): row
        for report in upstream_reports.values() for row in report["slates"]
    }
    if set(upstream_by_key) != set(actual_maps):
        raise RuntimeError("ATLAS historical upstream/player slate grids differ")
    rows = []
    artifact_receipts = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            source = sources[
                sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            catalog = players[
                players.season.astype(int).eq(season)
                & players.week.astype(int).eq(week)
            ].copy()
            row, slate_receipts = _run_slate(
                season=season, week=week, source=source, catalog=catalog,
                actual=actual_maps[(season, week)],
                upstream=upstream_by_key[(season, week)], gcs=gcs,
            )
            rows.append(row)
            artifact_receipts.extend(slate_receipts)
            print("ATLAS_HISTORICAL_SCORE_SLATE_COMPLETE", season, week, flush=True)

    result = aggregate_diagnostic(rows)
    artifact_raw = json.dumps(
        artifact_receipts, sort_keys=True, separators=(",", ":"),
    ).encode()
    result.update({
        "scorer_code_sha": code_sha,
        "scorer_image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_parity_amendment_sha256": PARITY_AMENDMENT_SHA256,
        "sharded_upstream_amendment_sha256": (
            SHARDED_UPSTREAM_AMENDMENT_SHA256
        ),
        "repair4_upstream_amendment_sha256": (
            REPAIR4_UPSTREAM_AMENDMENT_SHA256
        ),
        "high_tail_guard_amendment_sha256": (
            HIGH_TAIL_GUARD_AMENDMENT_SHA256
        ),
        "upstream": {
            "code_sha": UPSTREAM_CODE_SHA,
            "image": UPSTREAM_IMAGE,
            "receipt_object": receipt_object,
            "objects": downloaded_receipts,
            "executions": UPSTREAM_EXECUTION_NAMES,
            "strict_harvest": receipt["strict_harvest"],
            "scorefree_gate_passed": aggregate.get("gate", {}).get(
                "passes_scorefree_gate"
            ),
        },
        "native_actual_score_parity": parity,
        "source_artifacts": {
            "count": len(artifact_receipts),
            "sha256": sha256(artifact_raw).hexdigest(),
            "receipts": artifact_receipts,
        },
    })
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("ATLAS_HISTORICAL_SCORE_RESULT " + json.dumps({
        "gate": result["gate"], "output": upload,
    }, sort_keys=True))
    return {**result, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-receipt-uri", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.upstream_receipt_uri, args.output_uri)


if __name__ == "__main__":
    main()
