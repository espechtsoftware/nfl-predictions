#!/usr/bin/env python3
"""Run the frozen outcome-free CBWU cyclic seed-order audit."""

from __future__ import annotations

import argparse
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.multiseed_portfolio import (
    audit_cbwu_seed_orders,
    combine_cbwu_books,
    combine_cbwu_order_invariant_books,
)
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries
from nfl_dfs.research.portfolio_effective_rank import decode_score_artifact


PROJECT = "nfl-predictions-503414"
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = (
    f"{PROJECT}.nfl_forensic_review."
    "final_forensic_20260814_player_corpus_repair4"
)
FORENSIC_MANIFEST_SHA256 = (
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
)
CBWU_OI_PROTOCOL = (
    "reports/2026-08-15-cbwu-seed-order-result-and-repair-protocol.md"
)
CBWU_OI_PROTOCOL_SHA256 = (
    "0e341130ffbdf66f7ae7ef4b3917e4da4d116df7dbcc54c631d3151c26cbec48"
)
SOURCE_PANEL_IDS = tuple(
    f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
)
SOURCE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256
FROM `{SOURCE_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND labels_complete
ORDER BY panel_run_id, season, week, cand_ix
"""
PLAYER_SQL = f"""
SELECT manifest_sha256, season, week, player_id, player_name, position,
       team, opponent, game_id, salary, mean_projection
FROM `{PLAYER_TABLE}`
WHERE scope = 'phase-s-cbwu-54'
ORDER BY season, week, player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "selected", "payout", "contest_rank",
)


def validate_scorefree_queries() -> None:
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "CBWU score-free query contains forbidden fields: "
            + ", ".join(present)
        )


def validate_repair_protocol() -> None:
    path = Path(CBWU_OI_PROTOCOL)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != (
        CBWU_OI_PROTOCOL_SHA256
    ):
        raise RuntimeError("CBWU-OI frozen protocol identity differs")


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("CBWU GCS URI must name one object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("CBWU GCS URI is invalid")
    return bucket, name


def _download_artifact(
    client: storage.Client, uri: str, digest: str,
) -> tuple[dict[str, np.ndarray], dict[str, str | int]]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    artifact = decode_score_artifact(raw, digest)
    required = {"cand_ix", "totals", "player_ids", "player_draws"}
    if not required <= set(artifact):
        raise ValueError("CBWU source artifact lacks candidate/player worlds")
    return artifact, {
        "uri": uri,
        "sha256": digest,
        "generation": str(blob.generation),
        "updated": blob.updated.isoformat() if blob.updated else "",
        "bytes": len(raw),
    }


def _upload_create_only(
    client: storage.Client, uri: str, payload: bytes,
) -> dict[str, str | int | bool]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    blob.upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "create_only": True,
    }


def _query(client: bigquery.Client, sql: str, params=None) -> pd.DataFrame:
    config = bigquery.QueryJobConfig(query_parameters=params or [])
    return client.query(sql, job_config=config, location="US").result().to_dataframe(
        create_bqstorage_client=False,
    )


def _player_rows(frame: pd.DataFrame, player_ids: np.ndarray) -> tuple[dict, ...]:
    if frame.duplicated("player_id").any():
        raise RuntimeError("CBWU player catalog contains duplicate IDs")
    catalog = frame.set_index(frame.player_id.astype(str), drop=False)
    ids = [str(value) for value in player_ids]
    if len(set(ids)) != len(ids):
        raise RuntimeError("CBWU artifact contains duplicate player IDs")
    if set(ids) - set(catalog.index):
        raise RuntimeError("CBWU artifact players are missing from the catalog")
    rows = []
    for player_id in ids:
        source = catalog.loc[player_id]
        projection = pd.to_numeric(source.mean_projection, errors="coerce")
        rows.append({
            "id": player_id,
            "name": str(source.player_name),
            "pos": str(source.position).upper(),
            "team": str(source.team),
            "opp": str(source.opponent),
            "game_id": str(source.game_id),
            "salary": int(source.salary),
            "proj": float(projection) if np.isfinite(projection) else 0.0,
        })
    return tuple(rows)


def _candidate_batch(
    frame: pd.DataFrame,
    artifact: dict[str, np.ndarray],
    catalog: pd.DataFrame,
) -> CandidateBatch:
    rows = frame.sort_values("cand_ix", kind="stable").reset_index(drop=True)
    indices = pd.to_numeric(rows.cand_ix, errors="raise").astype(int).tolist()
    if indices != list(range(len(rows))):
        raise RuntimeError("CBWU candidate indices are not canonical")
    artifact_indices = np.asarray(artifact["cand_ix"]).astype(int).tolist()
    if artifact_indices != indices:
        raise RuntimeError("CBWU artifact candidate indices differ")
    player_ids = tuple(np.asarray(artifact["player_ids"]).astype(str).tolist())
    player_rows = _player_rows(catalog, np.asarray(player_ids))
    by_id = {row["id"]: row for row in player_rows}
    candidates = []
    all_tags = {}
    for source in rows.itertuples(index=False):
        roster_ids = [value for value in str(source.players).split(",") if value]
        if len(roster_ids) != 9 or len(set(roster_ids)) != 9:
            raise RuntimeError("CBWU candidate roster is malformed")
        try:
            lineup = Lineup([by_id[player_id] for player_id in roster_ids], tag=str(source.tag))
        except KeyError as exc:
            raise RuntimeError("CBWU candidate is outside artifact universe") from exc
        try:
            tags = json.loads(str(source.all_tags))
        except json.JSONDecodeError as exc:
            raise RuntimeError("CBWU candidate tags are not JSON") from exc
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise RuntimeError("CBWU candidate tags are malformed")
        candidates.append(lineup)
        all_tags[lineup.ids] = tuple(tags)
    totals = np.asarray(artifact["totals"], dtype=np.float32)
    draws = np.asarray(artifact["player_draws"], dtype=np.float32)
    if totals.shape != (len(candidates), 10_000):
        raise RuntimeError("CBWU candidate-world shape differs")
    if draws.shape != (len(player_rows), 10_000):
        raise RuntimeError("CBWU player-world shape differs")
    return CandidateBatch(
        candidates=tuple(candidates),
        candidate_totals=totals,
        player_ids=player_ids,
        player_rows=player_rows,
        row_draws=draws,
        all_tags=all_tags,
    )


def _aggregate_audits(audits: list[dict]) -> dict[str, Any]:
    if len(audits) != 54:
        raise ValueError("CBWU aggregate requires exactly 54 slates")
    comparisons = []
    for audit in audits:
        if audit.get("uses_realized_outcomes") is not False:
            raise ValueError("CBWU audit contains outcome-facing data")
        rotations = audit.get("rotations", [])
        if len(rotations) != 5:
            raise ValueError("CBWU audit lacks five cyclic rotations")
        canonical_coverage = float(rotations[0]["selected_world_coverage"])
        for rotation_index, row in enumerate(rotations[1:], start=1):
            comparisons.append({
                "season": int(audit["season"]),
                "week": int(audit["week"]),
                "rotation_index": rotation_index,
                "candidate_jaccard": float(
                    row["candidate_identity_jaccard_vs_canonical"]
                ),
                "selected_jaccard": float(
                    row["selected_identity_jaccard_vs_canonical"]
                ),
                "world_coverage_delta": float(
                    row["selected_world_coverage"] - canonical_coverage
                ),
            })
    candidate = np.asarray([row["candidate_jaccard"] for row in comparisons])
    selected = np.asarray([row["selected_jaccard"] for row in comparisons])
    coverage = np.asarray([row["world_coverage_delta"] for row in comparisons])
    invariant = bool(np.all(candidate == 1.0) and np.all(selected == 1.0))
    return {
        "slates": 54,
        "cyclic_comparisons": len(comparisons),
        "candidate_jaccard": {
            "minimum": float(candidate.min()),
            "mean": float(candidate.mean()),
        },
        "selected_jaccard": {
            "minimum": float(selected.min()),
            "mean": float(selected.mean()),
        },
        "selected_world_coverage_delta": {
            "minimum": float(coverage.min()),
            "mean": float(coverage.mean()),
            "maximum": float(coverage.max()),
        },
        "candidate_changed_comparisons": int(np.sum(candidate < 1.0)),
        "selected_changed_comparisons": int(np.sum(selected < 1.0)),
        "order_invariant": invariant,
        "disposition": (
            "cbwu-order-invariant"
            if invariant else "cbwu-order-sensitive-requires-repair"
        ),
    }


def _tuple_count(lineups: list[Lineup], size: int) -> int:
    found = set()
    for lineup in lineups:
        found.update(combinations(sorted(str(value) for value in lineup.ids), size))
    return len(found)


def _selected_metrics(batch: CandidateBatch, picked: list[int]) -> dict[str, Any]:
    if len(picked) != 80 or len(set(picked)) != 80:
        raise ValueError("CBWU-OI requires exactly 80 selected candidates")
    totals = np.asarray(batch.candidate_totals)
    clears = totals[picked] >= 194.0
    if clears.shape[1] % 5:
        raise ValueError("CBWU-OI world blocks are misaligned")
    block_worlds = clears.shape[1] // 5
    selected = [batch.candidates[index] for index in picked]
    return {
        "identities": [
            sorted(str(value) for value in lineup.ids) for lineup in selected
        ],
        "world_coverage": float(np.mean(np.any(clears, axis=0))),
        "world_coverage_by_block": [
            float(np.mean(np.any(
                clears[:, index * block_worlds:(index + 1) * block_worlds],
                axis=0,
            )))
            for index in range(5)
        ],
        "pair_coverage": _tuple_count(selected, 2),
        "triple_coverage": _tuple_count(selected, 3),
    }


def _repair_slate(books: dict[str, CandidateBatch]) -> dict[str, Any]:
    order = tuple(f"R{index}" for index in range(5))
    control = combine_cbwu_books(
        books, order, expected_worlds_per_book=10_000
    )
    control_picked = select_tail_entries(
        control.candidate_totals, 80, 194.0, env={"SELECT_LSE": "0"}
    )
    control_metrics = _selected_metrics(control, control_picked)

    rotations = tuple(order[offset:] + order[:offset] for offset in range(5))
    rows = []
    canonical_candidates = None
    canonical_selected = None
    canonical_metrics = None
    for rotation in rotations:
        treatment = combine_cbwu_order_invariant_books(
            books,
            rotation,
            tail_line=194.0,
            expected_worlds_per_book=10_000,
        )
        picked = select_tail_entries(
            treatment.candidate_totals, 80, 194.0, env={"SELECT_LSE": "0"}
        )
        metrics = _selected_metrics(treatment, picked)
        candidates = [
            sorted(str(value) for value in lineup.ids)
            for lineup in treatment.candidates
        ]
        if canonical_candidates is None:
            canonical_candidates = candidates
            canonical_selected = metrics["identities"]
            canonical_metrics = metrics
        rows.append({
            "seed_order": list(rotation),
            "candidate_budget": len(treatment.candidates),
            "complete_union_candidates": treatment.metadata[
                "complete_union_candidates"
            ],
            "candidate_identities_exact_vs_canonical": (
                candidates == canonical_candidates
            ),
            "selected_identities_exact_vs_canonical": (
                metrics["identities"] == canonical_selected
            ),
            "selected_metrics": metrics,
        })
    assert canonical_metrics is not None
    candidate_budget = len(control.candidates)
    invariant = bool(all(
        row["candidate_identities_exact_vs_canonical"]
        and row["selected_identities_exact_vs_canonical"]
        and row["candidate_budget"] == candidate_budget
        for row in rows
    ))
    return {
        "version": "cbwu-order-invariant-repair-scorefree-v1",
        "uses_realized_outcomes": False,
        "candidate_budget": candidate_budget,
        "control": control_metrics,
        "treatment": canonical_metrics,
        "world_coverage_delta": (
            canonical_metrics["world_coverage"]
            - control_metrics["world_coverage"]
        ),
        "world_coverage_delta_by_block": [
            treatment - control_value
            for treatment, control_value in zip(
                canonical_metrics["world_coverage_by_block"],
                control_metrics["world_coverage_by_block"],
                strict=True,
            )
        ],
        "pair_coverage_ratio": (
            canonical_metrics["pair_coverage"]
            / max(1, control_metrics["pair_coverage"])
        ),
        "triple_coverage_ratio": (
            canonical_metrics["triple_coverage"]
            / max(1, control_metrics["triple_coverage"])
        ),
        "rotations": rows,
        "order_invariant": invariant,
    }


def _aggregate_repairs(rows: list[dict]) -> dict[str, Any]:
    if len(rows) != 54:
        raise ValueError("CBWU-OI aggregate requires exactly 54 slates")
    if any(row.get("uses_realized_outcomes") is not False for row in rows):
        raise ValueError("CBWU-OI aggregate received outcome-facing rows")
    block_delta = np.asarray([
        row["world_coverage_delta_by_block"] for row in rows
    ], dtype=float)
    conditions = {
        "all_rotations_identity_exact": all(
            row["order_invariant"] for row in rows
        ),
        "aggregate_world_coverage_improves": float(np.mean([
            row["world_coverage_delta"] for row in rows
        ])) > 0.0,
        "at_least_three_blocks_improve": int(np.sum(
            block_delta.mean(axis=0) > 0.0
        )) >= 3,
        "pair_coverage_at_least_90pct": float(np.mean([
            row["pair_coverage_ratio"] for row in rows
        ])) >= 0.90,
        "triple_coverage_at_least_90pct": float(np.mean([
            row["triple_coverage_ratio"] for row in rows
        ])) >= 0.90,
        "exact_candidate_and_entry_counts": all(
            row["candidate_budget"] > 80
            and len(row["treatment"]["identities"]) == 80
            and all(
                rotation["candidate_budget"] == row["candidate_budget"]
                for rotation in row["rotations"]
            )
            for row in rows
        ),
    }
    passes = bool(all(conditions.values()))
    return {
        "slates": 54,
        "cyclic_comparisons": 216,
        "mean_world_coverage_delta": float(np.mean([
            row["world_coverage_delta"] for row in rows
        ])),
        "mean_world_coverage_delta_by_block": block_delta.mean(axis=0).tolist(),
        "mean_pair_coverage_ratio": float(np.mean([
            row["pair_coverage_ratio"] for row in rows
        ])),
        "mean_triple_coverage_ratio": float(np.mean([
            row["triple_coverage_ratio"] for row in rows
        ])),
        "conditions": conditions,
        "passes_scorefree_gate": passes,
        "disposition": (
            "cbwu-oi-scorefree-gate-passes"
            if passes else "cbwu-oi-scorefree-gate-fails"
        ),
    }


def run(output_uri: str, mode: str = "order-audit") -> dict[str, Any]:
    validate_scorefree_queries()
    if mode not in {"order-audit", "order-invariant-repair"}:
        raise ValueError("CBWU score-free mode differs")
    if mode == "order-invariant-repair":
        validate_repair_protocol()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image
    ):
        raise RuntimeError("CBWU exact code SHA and immutable image are required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(
        bq,
        SOURCE_SQL,
        [bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(SOURCE_PANEL_IDS)
        )],
    )
    players = _query(bq, PLAYER_SQL)
    if set(sources.panel_run_id.astype(str)) != set(SOURCE_PANEL_IDS):
        raise RuntimeError("CBWU source panel identities differ")
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("CBWU pre-lock player corpus manifest differs")
    group_keys = sources[["panel_run_id", "season", "week"]].drop_duplicates()
    if len(group_keys) != 270:
        raise RuntimeError(f"CBWU expected 270 seed/slate sources, got {len(group_keys)}")
    slates = sorted({
        (int(row.season), int(row.week)) for row in group_keys.itertuples()
    })
    if len(slates) != 54:
        raise RuntimeError(f"CBWU expected 54 slates, got {len(slates)}")

    audits = []
    receipts = []
    for season, week in slates:
        slate_catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        books = {}
        for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
            group = sources[
                sources.panel_run_id.astype(str).eq(panel_id)
                & sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            if group.empty:
                raise RuntimeError(f"CBWU source is missing {panel_id} {season}w{week}")
            uris = group.score_artifact_uri.astype(str).unique()
            digests = group.score_artifact_sha256.astype(str).unique()
            if len(uris) != 1 or len(digests) != 1:
                raise RuntimeError("CBWU source lacks one artifact identity")
            artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
            books[f"R{seed}"] = _candidate_batch(group, artifact, slate_catalog)
            receipts.append({
                "seed": seed,
                "panel_run_id": panel_id,
                "season": season,
                "week": week,
                "candidate_rows": len(group),
                **receipt,
            })
        if mode == "order-audit":
            audit = audit_cbwu_seed_orders(
                books,
                tuple(books),
                n_entries=80,
                tail_line=194.0,
                expected_worlds_per_book=10_000,
            )
        else:
            audit = _repair_slate(books)
        audits.append({"season": season, "week": week, **audit})

    aggregate = (
        _aggregate_audits(audits)
        if mode == "order-audit" else _aggregate_repairs(audits)
    )
    version = (
        "cbwu-seed-order-scorefree-v1"
        if mode == "order-audit"
        else "cbwu-order-invariant-repair-scorefree-v1"
    )
    report = {
        "version": version,
        "uses_realized_outcomes": False,
        "code_sha": code_sha,
        "image": image,
        "source_table": SOURCE_TABLE,
        "player_table": PLAYER_TABLE,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "repair_protocol_sha256": (
            CBWU_OI_PROTOCOL_SHA256
            if mode == "order-invariant-repair" else None
        ),
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_artifacts": receipts,
        "aggregate": aggregate,
        "slates": audits,
        "consequence": (
            "score-free order audit only; a sensitive result requires an "
            "order-proof or order-invariant repair and cannot select the "
            "historically best order"
            if mode == "order-audit"
            else "score-free repair gate only; a pass licenses a separately "
            "identified pre-lock 2026 shadow and cannot change production"
        ),
    }
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode()
    report["output"] = _upload_create_only(gcs, output_uri, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    parser.add_argument(
        "--mode",
        choices=("order-audit", "order-invariant-repair"),
        default="order-audit",
    )
    args = parser.parse_args()
    result = run(args.output_uri, mode=args.mode)
    print(json.dumps({
        "version": result["version"],
        "aggregate": result["aggregate"],
        "output": result["output"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
