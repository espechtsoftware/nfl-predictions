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
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_final_forensic_prelock import capture as capture_prelock  # noqa: E402
from nfl_dfs.research.final_forensic import (
    TAILS,
    decompose_slate,
    validate_freeze_manifest,
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
               score_artifact_sha256
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
               salary, actual
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--analysis-image", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = validate_freeze_manifest(manifest, repo_root=repo_root)
    if manifest["analysis_image"] != args.analysis_image:
        raise SystemExit("runtime analysis image differs from frozen manifest")
    if manifest["analysis_code_sha"] != args.expected_code_sha:
        raise SystemExit("runtime analysis code SHA differs from frozen manifest")

    client = bigquery.Client(project=PROJECT, location="US")
    current_prelock = capture_prelock(client)
    _prelock_equal(manifest["panels"], current_prelock)

    storage_client = storage.Client(project=PROJECT)
    output_scopes: list[dict[str, Any]] = []
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
            player_frame = player_group.rename(columns={"id": "id"})[
                ["id", "pos", "team", "opp", "game_id", "salary", "actual"]
            ]
            result = decompose_slate(
                player_frame,
                candidate_group,
                expected_entries=80,
                min_salary=49_000,
                salary_cap=50_000,
            )
            result.update({"season": season, "week": week, "scope": scope["id"]})
            slates.append(result)
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
    report = {
        "protocol_id": manifest["protocol_id"],
        "manifest_sha256": validation["manifest_sha256"],
        "analysis_image": args.analysis_image,
        "expected_code_sha": args.expected_code_sha,
        "prelock_revalidated_before_outcome_query": True,
        "scopes": output_scopes,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(output),
        "manifest_sha256": validation["manifest_sha256"],
        "scopes": {row["id"]: row["summary"] for row in output_scopes},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
