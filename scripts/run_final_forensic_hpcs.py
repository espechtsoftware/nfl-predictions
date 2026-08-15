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
    BETWEEN_ARM_VARIANCE_PANEL_IDS,
    TAILS,
    WAREHOUSE_TABLE_SCHEMAS,
    canonical_game_id,
    decompose_slate,
    recourse_ceiling_slate,
    validate_freeze_manifest,
)
from nfl_dfs.research.final_forensic_outputs import (
    candidate_scorecard,
    player_capture_slate,
    portfolio_slate,
    registry_outputs,
    warehouse_slate_frames,
)
from nfl_dfs.research.final_forensic_diagnostics import (
    aggregate_candidate_diagnostics,
    between_arm_variance_diagnostic,
    candidate_slate_diagnostics,
    feature_missingness_diagnostics,
    paired_scope_diagnostics,
    player_calibration_diagnostics,
    regime_and_drift_diagnostics,
    route_pool_admission_diagnostics,
    winner_benchmark,
)
from nfl_dfs.research.final_forensic_corpus import (  # noqa: E402
    corpus_understanding_diagnostics,
)
from nfl_dfs.research.real_winner_overlap import (
    load_known_winner_rows,
    match_known_winner_players,
)
from nfl_dfs.analysis.fantasy_points_route_share import attach_strict_prior_route
from nfl_dfs.research.multiseed_candidate_world import (
    reconstruct_fixed_budget_book,
)
from nfl_dfs.research.portfolio_effective_rank import decode_score_artifact
from nfl_dfs.names import match_map, norm_name, resolve


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
REFERENCE_REPORTS = {
    "g0_dependence": (
        "reports/g0-dependence-runs/"
        "20260812-g0-final-served-dependence-v2/report.json"
    ),
    "g1_topology": (
        "reports/g1-topology-runs/"
        "20260812-g1-archetype-topology-v3/report.json"
    ),
    "effective_rank": (
        "reports/portfolio-effective-rank-runs/"
        "20260813-incumbent-effective-rank-v2/report.json"
    ),
    "candidate_world_factorial": (
        "reports/multiseed-candidate-world-runs/"
        "20260813-multiseed-candidate-world-v1/report.json"
    ),
    "selector_resampling": (
        "reports/selector-resampling-runs/"
        "20260814-selector-resampling-v1/report.json"
    ),
    "incumbent_seed_variance": (
        "reports/incumbent-seed-variance-runs/"
        "20260813-incumbent-seed-variance-v1/report.json"
    ),
    "sis_pass_tail": (
        "reports/tabpfn-sis-pass-tail-runs/"
        "20260814-sis-pass-tail-exact80-v1/report.json"
    ),
}


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


def _validate_between_arm_prelock(
    client: bigquery.Client,
    contract: dict[str, Any],
) -> None:
    """Revalidate the frozen 14-panel population without reading outcomes."""
    rows = _query_df(
        client,
        f"""
        SELECT panel_run_id, season, week,
               COUNT(*) AS candidate_rows,
               COUNTIF(selected) AS entries,
               LOGICAL_AND(labels_complete) AS labels_complete,
               LOGICAL_AND(research_eligible) AS research_eligible
        FROM `{PROJECT}.{DATASET}.replay_candidates`
        WHERE panel_run_id IN UNNEST(@panel_ids)
        GROUP BY panel_run_id, season, week
        ORDER BY panel_run_id, season, week
        """,
        params=[bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(BETWEEN_ARM_VARIANCE_PANEL_IDS)
        )],
    )
    expected_panels = set(map(str, contract["panel_ids"]))
    actual_panels = set(rows.panel_run_id.astype(str))
    if expected_panels != actual_panels:
        raise RuntimeError("between-arm prelock panel population drifted")
    expected_slates = {
        (int(row[:4]), int(row[5:])) for row in contract["common_slates"]
    }
    if len(rows) != len(expected_panels) * len(expected_slates):
        raise RuntimeError("between-arm prelock panel is not balanced")
    if not rows.labels_complete.fillna(False).astype(bool).all():
        raise RuntimeError("between-arm prelock labels are incomplete")
    if not rows.research_eligible.fillna(False).astype(bool).all():
        raise RuntimeError("between-arm prelock contains non-research rows")
    for panel_id, group in rows.groupby("panel_run_id"):
        actual_slates = set(map(tuple, group[["season", "week"]].astype(int).to_numpy()))
        if actual_slates != expected_slates:
            raise RuntimeError(f"between-arm common slates drifted: {panel_id}")
        expected_entries = int(contract["expected_entries_by_panel"][str(panel_id)])
        if not pd.to_numeric(group.entries, errors="raise").eq(expected_entries).all():
            raise RuntimeError(f"between-arm entry count drifted: {panel_id}")


def _load_between_arm_corpus(
    client: bigquery.Client,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the registered outcome-viewed candidate corpus after prelock parity."""
    candidates = _query_df(
        client,
        f"""
        SELECT panel_run_id, season, week, cand_ix, players, selected,
               selected_rank, salary, tag, all_tags, p_line, sim_mean, sim_sd,
               sim_q50, sim_q90, sim_q99, sim_rank_p_line, actual_score
        FROM `{PROJECT}.{DATASET}.replay_candidates`
        WHERE panel_run_id IN UNNEST(@panel_ids)
          AND labels_complete AND research_eligible
        ORDER BY panel_run_id, season, week, cand_ix
        """,
        params=[bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(BETWEEN_ARM_VARIANCE_PANEL_IDS)
        )],
    )
    if set(candidates.panel_run_id.astype(str)) != set(contract["panel_ids"]):
        raise RuntimeError("between-arm outcome corpus panel population drifted")
    selected = candidates[candidates.selected.fillna(False).astype(bool)]
    weekly = selected.groupby(
        ["panel_run_id", "season", "week"], sort=True
    ).agg(
        weekly_max=("actual_score", "max"),
        entries=("cand_ix", "size"),
    ).reset_index()
    expected_rows = len(contract["panel_ids"]) * len(contract["common_slates"])
    if len(weekly) != expected_rows:
        raise RuntimeError("between-arm outcome corpus is not balanced")
    for panel_id, group in weekly.groupby("panel_run_id"):
        expected_entries = int(contract["expected_entries_by_panel"][str(panel_id)])
        if not group.entries.astype(int).eq(expected_entries).all():
            raise RuntimeError(f"between-arm outcome entry count drifted: {panel_id}")
    return candidates, weekly


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
        SELECT t.*, TO_JSON_STRING(t) AS source_candidate_json
        FROM `{PROJECT}.{DATASET}.{table}` AS t
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
        SELECT t.*, TO_JSON_STRING(t) AS source_features_json
        FROM `{PROJECT}.{DATASET}.slate_player_features` AS t
        WHERE panel_run_id=@panel_id
          {research}
        ORDER BY season, week, id
        """,
        params=[bigquery.ScalarQueryParameter("panel_id", "STRING", panel_id)],
    )


def _load_actual_ownership(
    client: bigquery.Client,
    *,
    seasons: list[int],
) -> pd.DataFrame:
    """Load equal-contest ownership summaries for outcome-only evaluation.

    The source lacks contest field size, so repeated contests cannot be
    field-size weighted. The output retains that limitation explicitly via the
    contest count and never enters selection.
    """
    return _query_df(
        client,
        f"""
        SELECT season, week, display_name,
               AVG(pct_drafted) AS actual_ownership,
               COUNT(DISTINCT contest_id) AS actual_ownership_contests
        FROM `{PROJECT}.nfl_raw.contest_ownership`
        WHERE season IN UNNEST(@seasons)
        GROUP BY season, week, display_name
        ORDER BY season, week, display_name
        """,
        params=[bigquery.ArrayQueryParameter("seasons", "INT64", seasons)],
    )


def _load_route_history(
    client: bigquery.Client,
    *,
    seasons: list[int],
) -> pd.DataFrame:
    """Load the raw resolved route observations used by the strict-prior join."""
    lower = min(seasons) - 1
    upper = max(seasons)
    return _query_df(
        client,
        f"""
        SELECT season, week, gsis_id, route_share
        FROM `{PROJECT}.nfl_raw.fantasy_points_route_share`
        WHERE season BETWEEN @lower AND @upper
          AND gsis_id IS NOT NULL
        ORDER BY gsis_id, season, week
        """,
        params=[
            bigquery.ScalarQueryParameter("lower", "INT64", lower),
            bigquery.ScalarQueryParameter("upper", "INT64", upper),
        ],
    )


def _attach_route_history(
    features: pd.DataFrame,
    route_history: pd.DataFrame,
) -> pd.DataFrame:
    """Reconstruct values omitted from the snapshot and verify source parity."""
    keys = ["season", "week", "id"]
    targets = features[keys].rename(columns={"id": "gsis_id"})
    attached = attach_strict_prior_route(targets, route_history)
    route_columns = [
        "fp_route_source_season", "fp_route_source_week",
        "fp_route_prior_observations", "fp_route_share_last",
        "fp_route_share_l4", "fp_route_share_jump", "fp_route_cross_season",
    ]
    additions = attached[["season", "week", "gsis_id", *route_columns]].rename(
        columns={"gsis_id": "id"}
    )
    frame = features.copy()
    for source in ("fp_route_source_season", "fp_route_source_week"):
        if source not in frame:
            continue
        comparison = frame[keys + [source]].merge(
            additions[keys + [source]],
            on=keys,
            how="left",
            validate="one_to_one",
            suffixes=("_snapshot", "_reconstructed"),
        )
        snapshot = pd.to_numeric(comparison[f"{source}_snapshot"], errors="coerce")
        reconstructed = pd.to_numeric(
            comparison[f"{source}_reconstructed"], errors="coerce"
        )
        supported = snapshot.notna()
        if (
            reconstructed.loc[supported].isna().any()
            or not snapshot.loc[supported].astype(int).eq(
                reconstructed.loc[supported].astype(int)
            ).all()
        ):
            raise RuntimeError(f"strict-prior route reconstruction differs: {source}")
    frame = frame.drop(columns=[
        column for column in route_columns if column in frame
    ])
    return frame.merge(additions, on=keys, how="left", validate="one_to_one")


def _attach_actual_ownership(
    features: pd.DataFrame,
    ownership: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attach name-matched realized ownership without guessing ambiguities."""
    frame = features.copy()
    frame["actual_ownership"] = np.nan
    frame["actual_ownership_contests"] = pd.Series(pd.NA, index=frame.index)
    matched = 0
    eligible = 0
    available_slates = 0
    ambiguous_reference_rows = 0
    total_skill_rows = int(
        (~frame.pos.astype(str).str.upper().eq("DST")).sum()
    )
    for (season, week), group in frame.groupby(["season", "week"]):
        external = ownership[
            ownership.season.astype(int).eq(int(season))
            & ownership.week.astype(int).eq(int(week))
        ]
        if external.empty:
            continue
        available_slates += 1
        skill = group[~group.pos.astype(str).str.upper().eq("DST")]
        eligible += len(skill)
        name_ids: dict[str, set[str]] = {}
        for row in skill[["id", "name"]].itertuples(index=False):
            name_ids.setdefault(norm_name(str(row.name)), set()).add(str(row.id))
        ambiguous_names = {
            name for name, ids in name_ids.items() if len(ids) != 1
        }
        ambiguous_reference_rows += int(sum(
            norm_name(str(row.name)) in ambiguous_names
            for row in skill[["name"]].itertuples(index=False)
        ))
        lookup = match_map({
            str(row.name): str(row.id)
            for row in skill[["id", "name"]].itertuples(index=False)
            if norm_name(str(row.name)) not in ambiguous_names
        })
        by_id: dict[str, list[tuple[float, int]]] = {}
        for row in external.itertuples(index=False):
            player_id = resolve(str(row.display_name), lookup)
            if player_id is None:
                continue
            by_id.setdefault(str(player_id), []).append((
                float(row.actual_ownership),
                int(row.actual_ownership_contests),
            ))
        for player_id, values in by_id.items():
            mask = group.id.astype(str).eq(player_id)
            frame.loc[mask.index[mask], "actual_ownership"] = float(np.mean([
                value[0] for value in values
            ]))
            frame.loc[mask.index[mask], "actual_ownership_contests"] = int(sum(
                value[1] for value in values
            ))
            matched += int(mask.sum())
    return frame, {
        "total_skill_rows": total_skill_rows,
        "available_slate_skill_rows": eligible,
        "matched_player_rows": matched,
        "available_slates": available_slates,
        "ambiguous_reference_rows_excluded": ambiguous_reference_rows,
        "match_rate_when_available": matched / eligible if eligible else None,
        "overall_match_rate": (
            matched / total_skill_rows if total_skill_rows else None
        ),
        "aggregation": "equal-contest mean; contest field size unavailable",
        "selection_use": "forbidden_outcome_only",
    }


def _authoritative_universe(client: bigquery.Client, seasons: list[int]) -> pd.DataFrame:
    """Load exact main-slate salary membership and authoritative actuals."""
    return _query_df(
        client,
        f"""
        WITH games AS (
          SELECT season, week, gametime AS kickoff_time,
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
          SELECT season, week, kickoff_time, home_team AS team, away_team AS opp,
                 CONCAT(away_team, '@', home_team) AS game_id FROM games
          UNION ALL
          SELECT season, week, kickoff_time, away_team, home_team,
                 CONCAT(away_team, '@', home_team) FROM games
        ), skill AS (
          SELECT s.season, s.week, s.gsis_id AS id, UPPER(s.position) AS pos,
                 COALESCE(s.display_name, s.gsis_id) AS name,
                 s.team, p.opp, p.game_id, p.kickoff_time, s.salary,
                 a.dk_points AS authoritative_actual
          FROM `{PROJECT}.nfl_features.dk_salary_week` s
          JOIN pairs p USING (season, week, team)
          JOIN `{PROJECT}.nfl_features.player_week_actuals` a
            USING (gsis_id, season, week)
          WHERE s.season IN UNNEST(@seasons)
            AND UPPER(s.position) IN ('QB','RB','WR','TE')
        ), dst AS (
          SELECT p.season, p.week, CONCAT('DST_', p.team) AS id, 'DST' AS pos,
                 CONCAT(p.team, ' DST') AS name,
                 p.team, p.opp, p.game_id, p.kickoff_time,
                 CAST(NULL AS INT64) AS salary,
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


def _reconcile_universe(
    features: pd.DataFrame,
    authoritative: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Reconcile the frozen served subset to the full hindsight universe.

    ``slate_player_features`` is the exact served/model-supported subset, not
    the complete salary/actual source.  H in the frozen decomposition is the
    full salary-source universe on those same slates, while calibration and
    the served stage must retain NULLs for players absent from the snapshot.
    Every frozen feature row must therefore have an exact authoritative match;
    authoritative-only skill rows are appended with an explicit missing-row
    marker.  DST salary is carried by the frozen feature snapshot because the
    upstream skill salary table has no DST records.
    """
    key = ["season", "week", "id"]
    if features.duplicated(key).any() or authoritative.duplicated(key).any():
        raise RuntimeError("universe contains duplicate season/week/player keys")
    feat = features.copy()
    auth = authoritative[
        authoritative[["season", "week"]].apply(tuple, axis=1).isin(
            set(feat[["season", "week"]].apply(tuple, axis=1))
        )
    ].copy()
    feature_keys = set(map(tuple, feat[key].to_numpy()))
    authoritative_keys = set(map(tuple, auth[key].to_numpy()))
    extra = feature_keys - authoritative_keys
    if extra:
        raise RuntimeError(
            "frozen feature universe contains rows absent from authoritative "
            f"salary/actual sources: extra={len(extra)}"
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
    for field in ("team", "opp"):
        if not joined[field].astype(str).eq(joined[f"{field}_auth"].astype(str)).all():
            raise RuntimeError(f"authoritative universe {field} differs")
    feature_games = [
        canonical_game_id(team, opponent)
        for team, opponent in zip(joined.team, joined.opp, strict=True)
    ]
    authoritative_games = [
        canonical_game_id(team, opponent)
        for team, opponent in zip(
            joined.team_auth, joined.opp_auth, strict=True
        )
    ]
    if feature_games != authoritative_games:
        raise RuntimeError("authoritative universe canonical game differs")

    missing_keys = authoritative_keys - feature_keys
    missing = auth[
        auth[key].apply(tuple, axis=1).isin(missing_keys)
    ].copy()
    if missing.pos.astype(str).str.upper().eq("DST").any():
        raise RuntimeError("authoritative-only DST lacks a frozen salary source")
    if pd.to_numeric(missing.salary, errors="coerce").isna().any():
        raise RuntimeError("authoritative-only skill player lacks salary")
    missing = missing.rename(columns={"authoritative_actual": "actual"})
    missing["feature_missing"] = '["missing_frozen_feature_row"]'
    missing["source_features_json"] = [
        json.dumps({
            "season": int(row.season),
            "week": int(row.week),
            "id": str(row.id),
            "name": str(row.name),
            "pos": str(row.pos),
            "team": str(row.team),
            "opp": str(row.opp),
            "game_id": str(row.game_id),
            "kickoff_time": str(row.kickoff_time),
            "salary": int(row.salary),
            "universe_source": "authoritative_only_no_frozen_feature_row",
        }, sort_keys=True, separators=(",", ":"))
        for row in missing.itertuples(index=False)
    ]

    kickoff = auth[key + ["kickoff_time"]]
    frozen = feat.merge(kickoff, on=key, how="left", validate="one_to_one")
    full = pd.concat([frozen, missing], ignore_index=True, sort=False)
    if full.duplicated(key).any() or len(full) != len(auth):
        raise RuntimeError("reconciled full universe has incomplete/duplicate keys")
    full = full.sort_values(key, kind="stable").reset_index(drop=True)
    return full, {
        "frozen_feature_rows": int(len(feat)),
        "authoritative_rows": int(len(auth)),
        "authoritative_only_rows": int(len(missing)),
        "authoritative_only_by_position": {
            str(position): int(count)
            for position, count in missing.pos.astype(str).value_counts().items()
        },
        "frozen_rows_verified_against_authoritative": True,
        "authoritative_only_selection_use": "hindsight_universe_only",
    }


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


def _json_default(value: object) -> object:
    """Convert NumPy scalars without silently accepting arbitrary objects."""
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(
        f"Object of type {value.__class__.__name__} is not JSON serializable"
    )


def _write_json_path(
    client: storage.Client, value: str, payload: dict[str, Any]
) -> None:
    raw = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        + "\n"
    ).encode("utf-8")
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
    layer_names = ("H_no_salary_floor", "H", "P", "C", "S")
    floor_costs = [
        row["salary_floor_policy"]["realized_score_cost"] for row in scope_rows
    ]
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
        "salary_floor_policy": {
            "mean_realized_score_cost": float(np.mean(floor_costs)),
            "median_realized_score_cost": float(np.median(floor_costs)),
            "maximum_realized_score_cost": float(max(floor_costs)),
            "positive_cost_slates": int(sum(cost > 1e-6 for cost in floor_costs)),
            "newly_reached_threshold_slates": {
                str(tail): int(sum(
                    tail in row["salary_floor_policy"]["newly_reached_thresholds"]
                    for row in scope_rows
                ))
                for tail in TAILS
            },
            "use_restriction": (
                "Outcome-viewed perfect-hindsight bound; any no-floor production "
                "change requires a new prospective outcome-unseen arm."
            ),
        },
        "candidate_support_frequency": {
            "mean_supported_players": float(np.mean([
                row["candidate_support_frequency"]["supported_player_count"]
                for row in scope_rows
            ])),
            "mean_players_appearing_fewer_than_five": float(np.mean([
                row["candidate_support_frequency"][
                    "players_appearing_fewer_than_five_candidates"
                ]
                for row in scope_rows
            ])),
            "mean_fraction_supported_players_appearing_fewer_than_five": float(
                np.mean([
                    row["candidate_support_frequency"][
                        "fraction_supported_players_appearing_fewer_than_five"
                    ]
                    for row in scope_rows
                ])
            ),
            "interpretation": (
                "P is a union-support bound, not proof that every supported "
                "player had material generator propensity."
            ),
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
    recourse_rows = [
        row["recourse_ceiling"] for row in slates
        if "ceiling_gain" in row["recourse_ceiling"]
    ]
    recourse_gains = [row["ceiling_gain"] for row in recourse_rows]
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
        "perfect_information_recourse_ceiling": {
            "slates": int(sum(
                row["recourse_ceiling"].get("status")
                == "computed_perfect_information_upper_bound"
                for row in slates
            )),
            "single_lock_slates": int(sum(
                row["recourse_ceiling"].get("status")
                == "not_identifiable_single_lock_stage"
                for row in slates
            )),
            "mean_gain": (
                float(np.mean(recourse_gains)) if recourse_gains else None
            ),
            "median_gain": (
                float(np.median(recourse_gains)) if recourse_gains else None
            ),
            "maximum_gain": (
                float(max(recourse_gains)) if recourse_gains else None
            ),
            "gain_ge_5_slates": int(sum(
                row["recourse_ceiling"].get("ceiling_gain", -np.inf) >= 5
                for row in slates
            )),
            "gain_ge_10_slates": int(sum(
                row["recourse_ceiling"].get("ceiling_gain", -np.inf) >= 10
                for row in slates
            )),
            "tail_counts": {
                str(tail): int(sum(
                    row["recourse_ceiling"].get(
                        "perfect_information_recourse_ceiling", -np.inf
                    ) >= tail for row in slates
                ))
                for tail in TAILS
            },
            "new_tail_slates": {
                str(tail): int(sum(
                    row["recourse_ceiling"].get("tail_grid", {}).get(
                        str(tail), {}
                    ).get("newly_reached", False)
                    for row in slates
                ))
                for tail in TAILS
            },
            "distinct_improved_slates": int(sum(
                row["recourse_ceiling"].get("ceiling_gain", 0.0) > 1e-6
                for row in slates
            )),
            "realistic_recourse": {
                "status": "unidentifiable_from_frozen_summary_corpus",
                "reason": (
                    "No joint late-player draws conditional on observed early "
                    "results were retained. A prospective world-retention and "
                    "policy freeze is required; no normal/independence proxy is "
                    "fabricated after outcome access."
                ),
            },
            "warning": (
                "Realized late-player scores optimize the bound. It is an upper "
                "bound on incumbent early cores, not policy performance. Actual "
                "kickoff stages, the production latest-kickoff FLEX assignment, "
                "and final salary/position legality are enforced."
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
    funnel_fields = (
        "salary_listed", "served_distribution", "candidate_support",
        "selected_exposure", "oracle_H_no_salary_floor", "oracle_H",
        "oracle_P", "oracle_C", "oracle_S",
    )
    return {
        "slates": len(slates),
        "threshold_funnel": {
            str(tail): {
                field: sum(row["threshold_funnel"][str(tail)][field] for row in slates)
                for field in funnel_fields
            }
            for tail in (20, 25, 30, 35)
        },
        "first_failed_stage": dict(Counter(
            player["first_failed_stage"]
            for row in slates for player in row["realized_20_plus_players"]
        )),
    }


def _reference_reports(repo_root: Path) -> dict[str, Any]:
    return {
        name: {
            "path": path,
            "payload": json.loads((repo_root / path).read_text(encoding="utf-8")),
        }
        for name, path in REFERENCE_REPORTS.items()
    }


def _factor_design_audit(reference_reports: dict[str, Any]) -> dict[str, Any]:
    factorial = reference_reports["candidate_world_factorial"]["payload"]
    cells = ("C0W0", "C0WU", "CUW0", "CUWU")
    observed = set(factorial["result"]["metrics"])
    matrix = np.asarray([
        [1, 0, 0, 0],
        [1, 0, 1, 0],
        [1, 1, 0, 0],
        [1, 1, 1, 1],
    ], dtype=float)
    if observed != set(cells):
        raise RuntimeError("factorial reference lacks the frozen four cells")
    return {
        "candidate_world_2x2": {
            "cells": list(cells),
            "columns": ["intercept", "candidate_union", "world_union", "interaction"],
            "rank": int(np.linalg.matrix_rank(matrix)),
            "columns_count": int(matrix.shape[1]),
            "aliased_columns": [],
            "estimable_contrasts": [
                "candidate_main_at_w0", "candidate_main_at_wu",
                "world_main_at_c0", "world_main_at_cu", "interaction",
            ],
        },
        "fixed_budget_world_contrast": {
            "cells": ["CBW0", "CBWU"],
            "rank": 2,
            "columns_count": 2,
            "estimable_contrasts": ["world_union_at_fixed_candidate_budget"],
        },
        "unidentifiable_in_this_design": [
            "marginal_law main effect", "dependence_law main effect",
            "selector main effect", "candidate_budget main effect",
            "interactions involving those fixed or absent factors",
        ],
        "stage_boundary": (
            "The four-cell factorial and fixed-budget confirmation are the 54-slate "
            "Phase S estimands only; no common-slate effect is attributed to 107 slates."
        ),
    }


def _analysis_completion(
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    dispositions = {
        "contest_payout_roi_cash_drawdown": (
            "partially_identifiable", "03 portfolio report: Week-5 payout floors only"
        ),
        "winner_places_2_through_5_comparison": (
            "unidentifiable", "03 portfolio report: repository contains first place only"
        ),
        "joint_score_and_tail_dependence": (
            "reference_frozen", "04 player/dependence report: pinned G0/G1"
        ),
        "effective_rank_spectral_and_random_controls": (
            "reference_frozen", "05 construction report: pinned effective-rank artifact"
        ),
        "winner_inverse_belief_distance": (
            "unidentifiable", "04 player report: names/feasibility fields insufficient"
        ),
        "cloud_runtime_data_cost_census": (
            "partially_identifiable", "06 arm ledger cost-status fields"
        ),
        "week1_end_to_end_dress_rehearsal": (
            "pending_external_slate", "07 readiness report"
        ),
        "independent_deterministic_reproduction": (
            "post_review_gate", "must be run independently from immutable corpus"
        ),
        "forensic_corpus_cleanup_before_production": (
            "post_review_gate", "manifest-bound cleanup after independent review"
        ),
    }
    rows = []
    for item in manifest["analysis_checklist"]:
        status, evidence = dispositions.get(
            item["id"], ("computed", "materialized in one of outputs 01-09")
        )
        rows.append({**item, "status": status, "evidence": evidence})
    return rows


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
    _validate_between_arm_prelock(client, manifest["between_arm_variance"])

    winner_scores = _known_winner_scores(repo_root)
    winners = winner_benchmark(repo_root)
    references = _reference_reports(repo_root)
    forensic_seasons = sorted({
        int(season)
        for panel in manifest["panels"]
        for season in panel["seasons"]
    })
    actual_ownership = _load_actual_ownership(
        client, seasons=forensic_seasons
    )
    route_history = _load_route_history(
        client, seasons=forensic_seasons
    )
    output_scopes: list[dict[str, Any]] = []
    portfolio_scopes: list[dict[str, Any]] = []
    capture_scopes: list[dict[str, Any]] = []
    construction_scopes: list[dict[str, Any]] = []
    scope_slate_rows: dict[str, list[dict[str, Any]]] = {}
    warehouse_parts: dict[str, list[pd.DataFrame]] = {
        table_id: [] for table_id in WAREHOUSE_TABLE_SCHEMAS
    }
    corpus_player_features: pd.DataFrame | None = None
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
        authoritative = _authoritative_universe(client, seasons)
        features, universe_audit = _reconcile_universe(
            features, authoritative
        )
        features = _attach_route_history(features, route_history)
        features, ownership_audit = _attach_actual_ownership(
            features, actual_ownership
        )
        if features.kickoff_time.isna().any():
            raise RuntimeError("salary-listed player lacks a kickoff time")
        # Preserve every raw source field in source_features_json, while all
        # forensic game grouping and legality use one canonical matchup key.
        features["game_id"] = [
            canonical_game_id(team, opponent)
            for team, opponent in zip(features.team, features.opp, strict=True)
        ]
        if scope["id"] == "component-107":
            corpus_player_features = features.copy()
        slates: list[dict[str, Any]] = []
        portfolio_slates: list[dict[str, Any]] = []
        capture_slates: list[dict[str, Any]] = []
        player_slates: list[pd.DataFrame] = []
        candidate_diagnostic_slates: list[dict[str, Any]] = []
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
            portfolio["recourse_ceiling"] = recourse_ceiling_slate(
                player_frame,
                candidate_group,
                expected_entries=80,
                compute_liveness=scope["id"] == "phase-s-cbwu-54",
            )
            portfolio_slates.append(portfolio)
            capture = player_capture_slate(player_frame, candidate_group, result)
            capture.update({"season": season, "week": week})
            capture_slates.append(capture)
            player_slates.append(player_frame)
            candidate_diagnostic_slates.append({
                "season": season,
                "week": week,
                "diagnostic": candidate_slate_diagnostics(
                    player_frame, candidate_group
                ),
            })
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
        scope_slate_rows[scope["id"]] = slates
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
            "served_calibration": player_calibration_diagnostics(features),
        })
        combined_candidates = pd.concat(forensic_candidate_frames, ignore_index=True)
        winner_source = load_known_winner_rows(repo_root / "reports")
        scope_keys = set(map(tuple, features[["season", "week"]].to_numpy()))
        winner_source = winner_source[
            winner_source[["season", "week"]].apply(tuple, axis=1).isin(scope_keys)
        ]
        winner_players = match_known_winner_players(winner_source, features)
        construction_scopes.append({
            "id": scope["id"],
            "scope_boundary": expected["scope_boundary"],
            "candidate_scorecard": candidate_scorecard(combined_candidates),
            "candidate_diagnostics": aggregate_candidate_diagnostics(
                candidate_diagnostic_slates
            ),
            "regime_and_drift": regime_and_drift_diagnostics(
                slates, player_slates
            ),
            "data_quality": {
                "prelock_revalidated": True,
                "authoritative_universe_reconciled": True,
                "universe_reconciliation": universe_audit,
                "candidate_rows": len(combined_candidates),
                "player_rows": len(features),
                "feature_missing_rows": int(
                    features.feature_missing.fillna("[]").astype(str)
                    .str.strip().str.lower().ne("[]").sum()
                ),
                "actual_ownership_join": ownership_audit,
                "feature_missingness": feature_missingness_diagnostics(features),
            },
            "route_pool_admission_bound": route_pool_admission_diagnostics(
                features, combined_candidates, winner_players
            ),
        })
    if corpus_player_features is None:
        raise RuntimeError("component player corpus was not retained")
    between_candidates, between_weekly = _load_between_arm_corpus(
        client, manifest["between_arm_variance"]
    )
    between_arm = between_arm_variance_diagnostic(
        between_weekly,
        panel_ids=manifest["between_arm_variance"]["panel_ids"],
    )
    corpus_understanding = corpus_understanding_diagnostics(
        between_candidates, corpus_player_features
    )
    paired_evt = paired_scope_diagnostics(scope_slate_rows)
    opportunity = {
        "protocol_id": manifest["protocol_id"],
        "manifest_sha256": validation["manifest_sha256"],
        "analysis_image": args.analysis_image,
        "expected_code_sha": args.expected_code_sha,
        "prelock_revalidated_before_outcome_query": True,
        "scopes": output_scopes,
    }
    outputs = registry_outputs(manifest)
    outputs["provenance_and_arm_ledger"]["analysis_checklist"] = (
        _analysis_completion(manifest)
    )
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
        "winner_roster_benchmark": winners,
        "scopes": portfolio_scopes,
    }
    outputs["player_capture_calibration_and_dependence"] = {
        "position": "reported within each scope/slate",
        "tail_bucket": [20, 25, 30, 35],
        "support_capture": capture_scopes,
        "calibration": {
            "scope_reports": {
                row["id"]: row["served_calibration"] for row in capture_scopes
            },
            "method_warning": (
                "CRPS and tail probabilities use the explicitly labelled normal "
                "approximation from frozen mean/std because player draw arrays are "
                "not retained in slate_player_features."
            ),
        },
        "dependence": {
            "g0": references["g0_dependence"],
            "g1": references["g1_topology"],
            "repaired_allocation_unit_boundary": (
                "The (game, team) allocation-unit repair moved QB-WR aggregate "
                "dependence from the pre-repair 1.053 context to 2.418 and left "
                "no stable repaired-path QB-TE deficit. Pre-repair G-series "
                "targets must not be read as current-path deficiencies."
            ),
            "warning": "No retrospective dependence refit is licensed.",
        },
        "known_winner_context": winners,
    }
    outputs["construction_selection_regime_and_data_quality"] = {
        "mechanism": "candidate rank skill, generator yield and H/P/C/S gaps",
        "regime": {
            row["id"]: row["regime_and_drift"] for row in construction_scopes
        },
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
        "paired_evt": paired_evt,
        "between_arm_variance": between_arm,
        "corpus_understanding_toolkit": corpus_understanding,
        "effective_rank_and_random_controls": references["effective_rank"],
        "selector_resampling_reference": references["selector_resampling"],
        "seed_variance_reference": references["incumbent_seed_variance"],
        "factor_design_and_estimability": _factor_design_audit(references),
        "source_pit_and_backup_readiness": {
            "prelock_panel_revalidated": True,
            "full_source_rows_retained_as_json": True,
            "raw_game_id_normalized_from_team_opponent": True,
            "paid_data_schedule": "README.md weekly operational schedule",
            "backup_contract": "README.md backup/restore checklist",
            "limitation": (
                "Raw source timestamps and live inference joins retain the "
                "dispositions in the pinned report inventory; this run does not "
                "retroactively recreate unavailable vendor publication times."
            ),
        },
        "data_quality": construction_scopes,
    }
    outputs["experiment_meta_analysis_and_kill_list"].update({
        "factor_design_and_estimability": _factor_design_audit(references),
        "candidate_world_factorial_reference": references["candidate_world_factorial"],
        "sis_pass_tail_transfer_boundary": references["sis_pass_tail"],
        "multiple_analysis_disclosure": (
            "Launched arms are a selected sample. This retrospective cannot revive "
            "a rejected arm or reinterpret an immutable gate."
        ),
        "td_wr_closure_precision": (
            "Competitive-WR v4 is invalid/unadjudicated mechanically, but every "
            "frozen disclosed gate moved adversely, including the ungated >=4 "
            "multiplicity diagnostic. It must not be described as promising."
        ),
    })
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
