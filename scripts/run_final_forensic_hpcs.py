#!/usr/bin/env python3
"""Run the post-freeze H/P/C/S opportunity decomposition.

This command is outcome-facing and must run only from the immutable image named
by the already-committed freeze manifest.  It first recomputes the outcome-free
prelock summaries and aborts on any drift.  Only then does it read actuals,
reconstruct the full salary-listed universe, rebuild CBWU from its five source
books/artifacts, and solve the registered oracles.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_final_forensic_prelock import capture as capture_prelock  # noqa: E402
from nfl_dfs.research.final_forensic import (
    TAILS,
    WAREHOUSE_TABLE_SCHEMAS,
    decompose_slate,
    validate_freeze_manifest,
)
from nfl_dfs.research.final_forensic_outputs import (
    candidate_scorecard,
    player_capture_slate,
    portfolio_slate,
    registry_outputs,
    warehouse_slate_frames,
)
from nfl_dfs.research.multiseed_candidate_world import (
    reconstruct_fixed_budget_book,
)
from nfl_dfs.research.portfolio_effective_rank import decode_score_artifact


PROJECT = "nfl-predictions-503414"
DATASET = "nfl_predictions"
SCOPES = (
    {
        "id": "component-107",
        "candidate_table": "replay_candidates",
        "panel_ids": ["20260811-pitclean-e80-k1-role12union-a12ab31"],
        "research_only": True,
        "cbwu": False,
    },
    {
        "id": "position-54",
        "candidate_table": "replay_candidates",
        "panel_ids": ["20260812-pitclean-e80-selected-position-scales-v2"],
        "research_only": True,
        "cbwu": False,
    },
    {
        "id": "phase-s-cbwu-54",
        "candidate_table": "replay_candidates_staging",
        "panel_ids": [
            f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
        ],
        "research_only": False,
        "cbwu": True,
    },
)


def _query_df(
    client: bigquery.Client,
    sql: str,
    *,
    params: list[bigquery.ScalarQueryParameter] | None = None,
) -> pd.DataFrame:
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params or []),
        location="US",
    )
    return job.result().to_dataframe(create_bqstorage_client=False)


def _prelock_equal(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> None:
    expected_by_id = {row["id"]: row for row in expected}
    actual_by_id = {row["id"]: row for row in actual}
    if set(expected_by_id) != set(actual_by_id):
        raise RuntimeError("prelock panel scope identities drifted")
    fields = (
        "expected_rows", "expected_player_rows", "expected_slates", "seasons",
        "prelock_row_hash", "prelock_candidate_summary", "prelock_feature_summary",
    )
    for panel_id, expected_row in expected_by_id.items():
        for field in fields:
            if expected_row[field] != actual_by_id[panel_id][field]:
                raise RuntimeError(f"prelock drift: {panel_id}.{field}")


def _load_candidates(
    client: bigquery.Client,
    *,
    table: str,
    panel_ids: list[str],
    research_only: bool,
) -> pd.DataFrame:
    if table not in {"replay_candidates", "replay_candidates_staging"}:
        raise ValueError("unapproved candidate table")
    research = "AND research_eligible" if research_only else ""
    return _query_df(
        client,
        f"""
        SELECT panel_run_id, code_sha, season, week, cand_ix, players,
               selected, selected_rank, salary, actual_score, labels_complete,
               n_entries, n_sims, n_worlds, score_artifact_uri,
               score_artifact_sha256, p_line, sim_mean, sim_q99, tag, all_tags
        FROM `{PROJECT}.{DATASET}.{table}`
        WHERE panel_run_id IN UNNEST(@panel_ids)
          {research}
        ORDER BY panel_run_id, season, week, cand_ix
        """,
        params=[bigquery.ArrayQueryParameter("panel_ids", "STRING", panel_ids)],
    )


def _load_features(
    client: bigquery.Client,
    *,
    panel_id: str,
    research_only: bool,
) -> pd.DataFrame:
    research = "AND research_eligible" if research_only else ""
    return _query_df(
        client,
        f"""
        SELECT season, week, slate_run_id, id, pos, team, opp, game_id,
               salary, actual, mean_projection, proj_p10, proj_p50, proj_p90,
               proj_std, feature_missing
        FROM `{PROJECT}.{DATASET}.slate_player_features`
        WHERE panel_run_id=@panel_id
          {research}
        ORDER BY season, week, id
        """,
        params=[bigquery.ScalarQueryParameter("panel_id", "STRING", panel_id)],
    )


def _authoritative_universe(client: bigquery.Client, seasons: list[int]) -> pd.DataFrame:
    """Load exact main-slate salary membership and authoritative actuals."""
    return _query_df(
        client,
        f"""
        WITH games AS (
          SELECT season, week,
                 CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                      WHEN 'STL' THEN 'LA' ELSE home_team END AS home_team,
                 CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                      WHEN 'STL' THEN 'LA' ELSE away_team END AS away_team
          FROM `{PROJECT}.nfl_raw.schedules`
          WHERE season IN UNNEST(@seasons)
            AND game_type='REG' AND weekday='Sunday'
            AND SAFE.PARSE_TIME('%H:%M', gametime) >= TIME '13:00:00'
            AND SAFE.PARSE_TIME('%H:%M', gametime) < TIME '19:00:00'
        ), pairs AS (
          SELECT season, week, home_team AS team, away_team AS opp,
                 CONCAT(away_team, '@', home_team) AS game_id FROM games
          UNION ALL
          SELECT season, week, away_team, home_team,
                 CONCAT(away_team, '@', home_team) FROM games
        ), skill AS (
          SELECT s.season, s.week, s.gsis_id AS id, UPPER(s.position) AS pos,
                 s.team, p.opp, p.game_id, s.salary,
                 a.dk_points AS authoritative_actual
          FROM `{PROJECT}.nfl_features.dk_salary_week` s
          JOIN pairs p USING (season, week, team)
          JOIN `{PROJECT}.nfl_features.player_week_actuals` a
            USING (gsis_id, season, week)
          WHERE s.season IN UNNEST(@seasons)
            AND UPPER(s.position) IN ('QB','RB','WR','TE')
        ), dst AS (
          SELECT p.season, p.week, CONCAT('DST_', p.team) AS id, 'DST' AS pos,
                 p.team, p.opp, p.game_id, CAST(NULL AS INT64) AS salary,
                 d.dst_dk_points AS authoritative_actual
          FROM pairs p
          JOIN `{PROJECT}.nfl_features.team_defense_week` d
            USING (season, week, team)
        )
        SELECT * FROM skill
        UNION ALL
        SELECT * FROM dst
        """,
        params=[bigquery.ArrayQueryParameter("seasons", "INT64", seasons)],
    )


def _verify_universe(features: pd.DataFrame, authoritative: pd.DataFrame) -> None:
    key = ["season", "week", "id"]
    if features.duplicated(key).any() or authoritative.duplicated(key).any():
        raise RuntimeError("universe contains duplicate season/week/player keys")
    feat = features.copy()
    auth = authoritative[
        authoritative[["season", "week"]].apply(tuple, axis=1).isin(
            set(feat[["season", "week"]].apply(tuple, axis=1))
        )
    ].copy()
    if set(map(tuple, feat[key].to_numpy())) != set(map(tuple, auth[key].to_numpy())):
        missing = set(map(tuple, auth[key].to_numpy())) - set(
            map(tuple, feat[key].to_numpy())
        )
        extra = set(map(tuple, feat[key].to_numpy())) - set(
            map(tuple, auth[key].to_numpy())
        )
        raise RuntimeError(
            f"salary-listed universe differs: missing={len(missing)} extra={len(extra)}"
        )
    joined = feat.merge(auth, on=key, validate="one_to_one", suffixes=("", "_auth"))
    if not np.allclose(
        pd.to_numeric(joined.actual, errors="raise"),
        pd.to_numeric(joined.authoritative_actual, errors="raise"),
        rtol=0.0,
        atol=1e-6,
    ):
        raise RuntimeError("feature actuals differ from authoritative actuals")
    skill = joined[~joined.pos.astype(str).str.upper().eq("DST")]
    if not np.array_equal(
        pd.to_numeric(skill.salary, errors="raise").to_numpy(),
        pd.to_numeric(skill.salary_auth, errors="raise").to_numpy(),
    ):
        raise RuntimeError("salary-listed skill salaries differ")
    pairs = ("team", "opp", "game_id")
    for field in pairs:
        if not joined[field].astype(str).eq(joined[f"{field}_auth"].astype(str)).all():
            raise RuntimeError(f"authoritative universe {field} differs")


def _download_artifact(client: storage.Client, uri: str, digest: str) -> dict:
    bucket, marker, name = str(uri).removeprefix("gs://").partition("/")
    if not marker or not bucket or not name or len(str(digest)) != 64:
        raise RuntimeError("invalid score artifact identity")
    raw = client.bucket(bucket).blob(name).download_as_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("score artifact byte hash differs")
    return decode_score_artifact(raw, digest)


def _read_json_path(client: storage.Client, value: str) -> dict[str, Any]:
    if not value.startswith("gs://"):
        return json.loads(Path(value).read_text(encoding="utf-8"))
    bucket, marker, name = value.removeprefix("gs://").partition("/")
    if not marker or not bucket or not name:
        raise RuntimeError("invalid GCS JSON input path")
    raw = client.bucket(bucket).blob(name).download_as_bytes()
    return json.loads(raw.decode("utf-8"))


def _write_json_path(
    client: storage.Client, value: str, payload: dict[str, Any]
) -> None:
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if not value.startswith("gs://"):
        output = Path(value)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw)
        return
    bucket, marker, name = value.removeprefix("gs://").partition("/")
    if not marker or not bucket or not name:
        raise RuntimeError("invalid GCS JSON output path")
    client.bucket(bucket).blob(name).upload_from_string(
        raw, content_type="application/json", if_generation_match=0
    )


def _write_warehouse_frames(
    client: bigquery.Client,
    manifest: dict[str, Any],
    frames: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    """Load the frozen corpus once and attach an extend-only 90-day expiry."""
    contract = manifest["warehouse_retention"]
    if set(frames) != set(WAREHOUSE_TABLE_SCHEMAS):
        raise RuntimeError("warehouse frames do not match the frozen four-table contract")
    tables = {row["id"]: row for row in contract["tables"]}
    dataset = client.get_dataset(contract["isolation_dataset"])
    expected_expiration_ms = int(contract["retention_days"]) * 86_400_000
    if (
        dataset.default_table_expiration_ms != expected_expiration_ms
        or (dataset.labels or {}).get("production_use") != "forbidden"
    ):
        raise RuntimeError("forensic isolation dataset contract differs")
    expires = datetime.now(timezone.utc) + timedelta(
        days=int(contract["retention_days"])
    )
    materialized = []
    for table_id, frozen_schema in WAREHOUSE_TABLE_SCHEMAS.items():
        table_name = tables[table_id]["table"]
        expected_columns = [field["name"] for field in frozen_schema]
        frame = frames[table_id]
        if list(frame) != expected_columns or frame.empty:
            raise RuntimeError(f"warehouse frame is empty or schema-drifted: {table_id}")
        try:
            existing = client.get_table(table_name)
        except NotFound:
            existing = None
        if existing is not None:
            existing_schema = [
                {"name": field.name, "type": field.field_type, "mode": field.mode}
                for field in existing.schema
            ]
            if (
                existing_schema != frozen_schema
                or existing.num_rows != len(frame)
                or (existing.labels or {}).get("manifest")
                != manifest["manifest_sha256"][:32]
                or existing.expires is None
            ):
                raise RuntimeError(
                    f"unverified write-once forensic destination exists: {table_name}"
                )
            materialized.append({
                "id": table_id,
                "table": table_name,
                "rows": int(existing.num_rows),
                "expires_at": existing.expires.isoformat(),
                "write_disposition": "WRITE_EMPTY",
                "manifest_sha256": manifest["manifest_sha256"],
                "cleanup_deadline": contract["cleanup_deadline"],
                "reused_after_verified_retry": True,
            })
            continue
        schema = [
            bigquery.SchemaField(field["name"], field["type"], mode=field["mode"])
            for field in frozen_schema
        ]
        job = client.load_table_from_dataframe(
            frame,
            table_name,
            job_config=bigquery.LoadJobConfig(
                schema=schema,
                create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
                write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
            ),
        )
        job.result()
        table = client.get_table(table_name)
        if table.num_rows != len(frame):
            raise RuntimeError(f"warehouse row count differs after load: {table_id}")
        table.expires = expires
        table.labels = {
            **(table.labels or {}),
            "purpose": "final_preseason_forensic",
            "manifest": manifest["manifest_sha256"][:32],
        }
        table.description = (
            "Write-once final preseason forensic corpus; extend expiry only. "
            f"Manifest {manifest['manifest_sha256']}."
        )
        table = client.update_table(table, ["expires", "labels", "description"])
        actual_schema = [
            {"name": field.name, "type": field.field_type, "mode": field.mode}
            for field in table.schema
        ]
        if actual_schema != frozen_schema or table.expires is None:
            raise RuntimeError(f"warehouse metadata differs after load: {table_id}")
        materialized.append({
            "id": table_id,
            "table": table_name,
            "rows": int(table.num_rows),
            "expires_at": table.expires.isoformat(),
            "write_disposition": "WRITE_EMPTY",
            "manifest_sha256": manifest["manifest_sha256"],
            "cleanup_deadline": contract["cleanup_deadline"],
        })
    return materialized


def _cbwu_slate(
    frame: pd.DataFrame,
    storage_client: storage.Client,
    season: int,
    week: int,
) -> pd.DataFrame:
    rows: dict[int, pd.DataFrame] = {}
    artifacts: dict[int, dict] = {}
    for seed in range(5):
        panel = f"20260813-sis-asoe-treatment-r{seed}-v1"
        group = frame[
            frame.panel_run_id.astype(str).eq(panel)
            & frame.season.astype(int).eq(season)
            & frame.week.astype(int).eq(week)
        ].copy()
        if group.empty:
            raise RuntimeError(f"CBWU R{seed} is missing {season}w{week}")
        uris = group.score_artifact_uri.astype(str).unique()
        digests = group.score_artifact_sha256.astype(str).unique()
        if len(uris) != 1 or len(digests) != 1:
            raise RuntimeError("CBWU slate lacks one artifact identity")
        rows[seed] = group
        artifacts[seed] = _download_artifact(storage_client, uris[0], digests[0])
    return reconstruct_fixed_budget_book(rows, artifacts, entry_count=80)


def _aggregate(scope_rows: list[dict[str, Any]]) -> dict[str, Any]:
    layer_names = ("H", "P", "C", "S")
    return {
        "slates": len(scope_rows),
        "tail_counts": {
            layer: {
                str(tail): sum(row[layer]["actual_score"] >= tail for row in scope_rows)
                for tail in TAILS
            }
            for layer in layer_names
        },
        "gap_points": {
            gap: {
                "mean": float(np.mean([row["gaps"][gap] for row in scope_rows])),
                "median": float(np.median([row["gaps"][gap] for row in scope_rows])),
                "maximum": float(max(row["gaps"][gap] for row in scope_rows)),
            }
            for gap in ("player_support", "construction", "selection")
        },
        "first_failed_layer_counts": {
            str(tail): {
                layer: sum(
                    row["thresholds"][str(tail)]["first_failed_layer"] == layer
                    for row in scope_rows
                )
                for layer in ("player_support", "construction", "selection", "none")
            }
            for tail in TAILS
        },
    }


def _known_winner_scores(repo_root: Path) -> dict[tuple[int, int], float]:
    scores: dict[tuple[int, int], float] = {}
    older = pd.read_csv(repo_root / "reports/milly-winners-2019-2023-2024.csv")
    grouped = older.groupby(["season", "week"]).fantasy_points.sum()
    scores.update({
        (int(season), int(week)): float(score)
        for (season, week), score in grouped.items()
    })
    current = pd.read_csv(repo_root / "reports/2025-milly-winners.csv")
    scores.update({
        (2025, int(row.week)): float(row.score)
        for row in current.itertuples(index=False)
    })
    return scores


def _portfolio_summary(slates: list[dict[str, Any]]) -> dict[str, Any]:
    known = [
        row["known_first_place"] for row in slates if "known_first_place" in row
    ]
    return {
        "slates": len(slates),
        "prefix_best": {
            prefix: {
                "mean": float(np.mean([
                    row["outcome_blind_selected_prefixes"][prefix]["best"]
                    for row in slates
                ])),
                "tail_counts": {
                    str(tail): sum(
                        row["outcome_blind_selected_prefixes"][prefix]["best"] >= tail
                        for row in slates
                    )
                    for tail in TAILS
                },
            }
            for prefix in ("20", "40", "80")
        },
        "known_first_place": {
            "weeks": len(known),
            "selected_beats": sum(row["selected_beats"] for row in known),
            "within_20": sum(row["selected_gap"] <= 20 for row in known),
            "within_30": sum(row["selected_gap"] <= 30 for row in known),
            "within_40": sum(row["selected_gap"] <= 40 for row in known),
            "mean_gap": (
                float(np.mean([row["selected_gap"] for row in known]))
                if known else None
            ),
        },
    }


def _payout_floor_anchors(slates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    week5 = next(
        (row for row in slates if row["season"] == 2025 and row["week"] == 5),
        None,
    )
    if week5 is None:
        return []
    scores = week5["selected_scores_by_rank"]
    anchors = []
    for contest, fee, cutoff, minimum_payout in (
        ("2025 Week 5 Millionaire", 20.0, 169.34, 30.0),
        ("2025 Week 5 MEGA mini-MAX", 2.0, 171.54, 4.0),
    ):
        cashes = sum(score >= cutoff for score in scores)
        stake = fee * 80
        payout_floor = minimum_payout * cashes
        anchors.append({
            "contest": contest,
            "entries": 80,
            "stake": stake,
            "min_cash_line": cutoff,
            "represented_min_cashes": cashes,
            "represented_payout_floor": payout_floor,
            "payout_floor_roi": payout_floor / stake - 1.0,
            "limitation": (
                "Not realized ROI: exact ranks, upper payout tiers, duplicate "
                "counts and tie splits are unavailable."
            ),
        })
    return anchors


def _capture_summary(slates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "slates": len(slates),
        "threshold_funnel": {
            str(tail): {
                field: sum(row["threshold_funnel"][str(tail)][field] for row in slates)
                for field in (
                    "salary_listed", "served_distribution", "candidate_support",
                    "selected_exposure", "oracle_H", "oracle_P", "oracle_C", "oracle_S",
                )
            }
            for tail in (20, 25, 30, 35)
        },
        "first_failed_stage": dict(Counter(
            player["first_failed_stage"]
            for row in slates for player in row["realized_20_plus_players"]
        )),
    }


def _destination(root: str, contract_path: str) -> str:
    name = Path(contract_path).name
    if root.startswith("gs://"):
        return root.rstrip("/") + "/" + name
    return str(Path(root) / name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--analysis-image", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    storage_client = storage.Client(project=PROJECT)
    manifest = _read_json_path(storage_client, args.manifest)
    validation = validate_freeze_manifest(manifest, repo_root=repo_root)
    if manifest["analysis_image"] != args.analysis_image:
        raise SystemExit("runtime analysis image differs from frozen manifest")
    if manifest["analysis_code_sha"] != args.expected_code_sha:
        raise SystemExit("runtime analysis code SHA differs from frozen manifest")

    client = bigquery.Client(project=PROJECT, location="US")
    current_prelock = capture_prelock(client)
    _prelock_equal(manifest["panels"], current_prelock)

    winner_scores = _known_winner_scores(repo_root)
    output_scopes: list[dict[str, Any]] = []
    portfolio_scopes: list[dict[str, Any]] = []
    capture_scopes: list[dict[str, Any]] = []
    construction_scopes: list[dict[str, Any]] = []
    warehouse_parts: dict[str, list[pd.DataFrame]] = {
        table_id: [] for table_id in WAREHOUSE_TABLE_SCHEMAS
    }
    for scope in SCOPES:
        candidates = _load_candidates(
            client,
            table=scope["candidate_table"],
            panel_ids=scope["panel_ids"],
            research_only=scope["research_only"],
        )
        if not candidates.labels_complete.fillna(False).astype(bool).all():
            raise RuntimeError(f"{scope['id']} labels are incomplete")
        features = _load_features(
            client,
            panel_id=scope["panel_ids"][0],
            research_only=scope["research_only"],
        )
        seasons = sorted(features.season.astype(int).unique().tolist())
        _verify_universe(features, _authoritative_universe(client, seasons))
        slates: list[dict[str, Any]] = []
        portfolio_slates: list[dict[str, Any]] = []
        capture_slates: list[dict[str, Any]] = []
        forensic_candidate_frames: list[pd.DataFrame] = []
        for (season, week), player_group in features.groupby(["season", "week"]):
            season, week = int(season), int(week)
            if scope["cbwu"]:
                candidate_group = _cbwu_slate(
                    candidates, storage_client, season, week
                )
            else:
                candidate_group = candidates[
                    candidates.season.astype(int).eq(season)
                    & candidates.week.astype(int).eq(week)
                ].copy()
            player_frame = player_group.copy()
            result = decompose_slate(
                player_frame[[
                    "id", "pos", "team", "opp", "game_id", "salary", "actual"
                ]],
                candidate_group,
                expected_entries=80,
                min_salary=49_000,
                salary_cap=50_000,
            )
            result.update({"season": season, "week": week, "scope": scope["id"]})
            slates.append(result)
            portfolio = portfolio_slate(
                player_frame,
                candidate_group,
                result,
                known_winner_score=winner_scores.get((season, week)),
            )
            portfolio.update({"season": season, "week": week})
            portfolio_slates.append(portfolio)
            capture = player_capture_slate(player_frame, candidate_group, result)
            capture.update({"season": season, "week": week})
            capture_slates.append(capture)
            labeled_candidates = candidate_group.copy()
            labeled_candidates["season"] = season
            labeled_candidates["week"] = week
            forensic_candidate_frames.append(labeled_candidates)
            slate_warehouse = warehouse_slate_frames(
                player_frame,
                candidate_group,
                result,
                scope=scope["id"],
                season=season,
                week=week,
                manifest_sha256=validation["manifest_sha256"],
                analysis_code_sha=args.expected_code_sha,
                analysis_image=args.analysis_image,
            )
            for table_id, frame in slate_warehouse.items():
                warehouse_parts[table_id].append(frame)
        expected = next(row for row in manifest["panels"] if row["id"] == scope["id"])
        if len(candidates) != expected["expected_rows"]:
            raise RuntimeError(f"{scope['id']} candidate count differs after outcome load")
        if len(slates) != expected["expected_slates"]:
            raise RuntimeError(f"{scope['id']} slate count differs after outcome load")
        output_scopes.append({
            "id": scope["id"],
            "scope_boundary": expected["scope_boundary"],
            "summary": _aggregate(slates),
            "slates": slates,
        })
        portfolio_scopes.append({
            "id": scope["id"],
            "scope_boundary": expected["scope_boundary"],
            "summary": _portfolio_summary(portfolio_slates),
            "payout_floor_anchors": _payout_floor_anchors(portfolio_slates),
            "slates": portfolio_slates,
        })
        capture_scopes.append({
            "id": scope["id"],
            "scope_boundary": expected["scope_boundary"],
            "summary": _capture_summary(capture_slates),
            "slates": capture_slates,
        })
        combined_candidates = pd.concat(forensic_candidate_frames, ignore_index=True)
        construction_scopes.append({
            "id": scope["id"],
            "scope_boundary": expected["scope_boundary"],
            "candidate_scorecard": candidate_scorecard(combined_candidates),
            "data_quality": {
                "prelock_revalidated": True,
                "authoritative_universe_reconciled": True,
                "candidate_rows": len(combined_candidates),
                "player_rows": len(features),
                "feature_missing_rows": int(
                    features.feature_missing.fillna(False).astype(bool).sum()
                ),
            },
        })
    opportunity = {
        "protocol_id": manifest["protocol_id"],
        "manifest_sha256": validation["manifest_sha256"],
        "analysis_image": args.analysis_image,
        "expected_code_sha": args.expected_code_sha,
        "prelock_revalidated_before_outcome_query": True,
        "scopes": output_scopes,
    }
    outputs = registry_outputs(manifest)
    outputs["opportunity_decomposition"] = opportunity
    outputs["portfolio_entry_count_and_money"] = {
        "scope": "evidence scope is explicit per panel",
        "entry_count": 80,
        "portfolio_prefix": [20, 40, 80],
        "contest_assumptions": {
            "historical_complete_standings": False,
            "second_through_fifth_place": "not identifiable",
            "exact_realized_roi": "not identifiable",
            "source": "reports/2026-08-10-contest-placement-roi-audit.md",
        },
        "payout_scenarios": "Only the observed 2025 Week 5 min-cash floor is identified.",
        "duplication_scenarios": "Ownership product is a proxy, not a field-score bound.",
        "roi_bounds": "No defensible multi-season realized ROI bound.",
        "scopes": portfolio_scopes,
    }
    outputs["player_capture_calibration_and_dependence"] = {
        "position": "reported within each scope/slate",
        "tail_bucket": [20, 25, 30, 35],
        "support_capture": capture_scopes,
        "calibration": "mean MAE/rank and p90 interval coverage in each slate record",
        "dependence": {
            "g0": (
                "reports/g0-dependence-runs/"
                "20260812-g0-final-served-dependence-v2/report.json"
            ),
            "g1": (
                "reports/g1-topology-runs/"
                "20260812-g1-archetype-topology-v3/report.json"
            ),
            "warning": "No retrospective dependence refit is licensed.",
        },
        "known_winner_context": (
            "First-place comparisons only where repository data exists; places "
            "2-5 are not present."
        ),
    }
    outputs["construction_selection_regime_and_data_quality"] = {
        "mechanism": "candidate rank skill, generator yield and H/P/C/S gaps",
        "regime": "season/slate records remain disaggregated",
        "construction_gap": "opportunity_decomposition.gaps.construction",
        "selection_gap": "opportunity_decomposition.gaps.selection",
        "distinct_improved_slates": {
            "sis_pass_tail_deciding_220": 2,
            "all_thresholds": 14,
        },
        "distinct_worsened_slates": {
            "sis_pass_tail_deciding_220": 1,
            "all_thresholds": 14,
        },
        "selector_reproducibility": {
            "bootstrap_overlap_of_80": 61.6362,
            "disjoint_half_overlap_of_80": 54.2778,
            "economic_entry_count_inference": "not licensed",
        },
        "data_quality": construction_scopes,
    }
    contract = {
        row["id"]: row["output_path"] for row in manifest["analysis_contract"]
    }
    if set(outputs) != set(contract):
        raise RuntimeError("analyzer did not materialize the exact nine-output contract")
    warehouse_frames = {
        table_id: pd.concat(parts, ignore_index=True)
        for table_id, parts in warehouse_parts.items()
    }
    materialized_tables = _write_warehouse_frames(
        client, manifest, warehouse_frames
    )
    outputs["provenance_and_arm_ledger"]["warehouse_retention"][
        "materialized_tables"
    ] = materialized_tables
    destinations = {}
    for output_id, payload in outputs.items():
        destination = _destination(args.output_root, contract[output_id])
        _write_json_path(storage_client, destination, payload)
        destinations[output_id] = destination
    print(json.dumps({
        "outputs": destinations,
        "warehouse_tables": materialized_tables,
        "manifest_sha256": validation["manifest_sha256"],
        "scopes": {row["id"]: row["summary"] for row in output_scopes},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
