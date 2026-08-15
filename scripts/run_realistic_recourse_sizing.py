#!/usr/bin/env python3
"""Run the frozen 54-slate historical realistic-recourse sizing protocol."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from statistics import median
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.inference.recourse_worlds import derive_remaining_worlds
from nfl_dfs.optimizer.late_swap import propose_recourse_rosters
from nfl_dfs.research.portfolio_effective_rank import decode_score_artifact
from nfl_dfs.research.recourse_scoring import (
    MULTI_LATERAL_ADJUSTMENTS,
    points_information_as_of,
)
from nfl_dfs.research.realistic_recourse_sizing import (
    ENTRY_COUNT,
    PROTOCOL_ID,
    SCOPE,
    TAILS,
    canonical_json_sha256,
    canonical_roster,
    combine_seed_player_worlds,
    decision_instant,
    derive_game_statuses,
    freeze_proposals,
    reconstruct_outcome_blind_cbwu,
    roster_swap_distance,
    validate_forensic_parity,
)


PROJECT = "nfl-predictions-503414"
FORENSIC_DATASET = "nfl_forensic_review"
MANIFEST_SHA256 = "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
PLAYER_TABLE = "final_forensic_20260814_player_corpus_repair4"
CANDIDATE_TABLE = "final_forensic_20260814_candidate_corpus_repair4"
SOURCE_PANEL_IDS = tuple(
    f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
)
EXACT_STACK_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-stack-construction-v1/result.json"
)
EXPECTED_EXACT_STACK_SHA256 = (
    "1d9e6b1f8d4e6174ae4aa717acf62fe657f0f3fbfd9271289a36b4a58664e7f3"
)
SCORER_AUDIT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-realistic-recourse-sizing-v1/scorer-reconciliation.json"
)
LATERAL_RESIDUALS = (
    (2024, 3, "00-0033576"), (2024, 9, "00-0036988"),
    (2025, 18, "00-0036252"), (2024, 4, "00-0036196"),
    (2024, 9, "00-0039915"), (2024, 3, "00-0036261"),
    (2025, 15, "00-0034827"), (2023, 9, "00-0036985"),
    (2024, 3, "00-0039351"), (2023, 16, "00-0033699"),
    (2024, 5, "00-0039896"), (2024, 3, "00-0037525"),
)


def _query(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]
    | None = None,
) -> pd.DataFrame:
    config = bigquery.QueryJobConfig(query_parameters=params or [])
    return client.query(sql, job_config=config, location="US").result().to_dataframe(
        create_bqstorage_client=False,
    )


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("output URI must name one GCS object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("output URI is invalid")
    return bucket, name


def _download_bytes(client: storage.Client, uri: str) -> tuple[bytes, Any]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    return raw, blob


def _upload_create_only(client: storage.Client, uri: str, payload: bytes) -> dict:
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


def _normal_team(value: object) -> str:
    aliases = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
    team = str(value).strip().upper()
    return aliases.get(team, team)


def _pair(left: object, right: object) -> str:
    return "|".join(sorted((_normal_team(left), _normal_team(right))))


def _prepare_schedule(raw: pd.DataFrame, pairs: set[tuple[int, int, str]]) -> pd.DataFrame:
    rows = []
    for game in raw.itertuples(index=False):
        pair = _pair(game.away_team, game.home_team)
        key = (int(game.season), int(game.week), pair)
        if key not in pairs:
            continue
        local = pd.Timestamp(f"{game.gameday} {game.gametime}", tz="America/New_York")
        rows.append({
            "season": int(game.season),
            "week": int(game.week),
            "game_id": str(game.game_id),
            "canonical_game_id": pair,
            "gameday": str(game.gameday),
            "kickoff_utc": local.tz_convert("UTC").isoformat(),
            "away_team": _normal_team(game.away_team),
            "home_team": _normal_team(game.home_team),
        })
    frame = pd.DataFrame(rows)
    if len(frame) != len(pairs) or frame.duplicated(
        ["season", "week", "canonical_game_id"]
    ).any():
        raise RuntimeError("schedule does not exactly map the forensic game pairs")
    return frame.sort_values(["season", "week", "game_id"], kind="stable")


def _json_key_query(
    client: bigquery.Client,
    *,
    keys: list[dict],
    kind: str,
) -> pd.DataFrame:
    encoded = json.dumps(keys, sort_keys=True, separators=(",", ":"))
    target = """
      SELECT CAST(JSON_VALUE(value, '$.season') AS INT64) AS season,
             CAST(JSON_VALUE(value, '$.week') AS INT64) AS week,
             JSON_VALUE(value, '$.game_id') AS game_id
      FROM UNNEST(JSON_QUERY_ARRAY(@keys)) AS value
    """
    if kind == "skill":
        query = f"""
          WITH target AS ({target})
          SELECT DISTINCT p.season, p.week, p.player_id,
                 a.dk_points
          FROM `{PROJECT}.{FORENSIC_DATASET}.{PLAYER_TABLE}` p
          JOIN target USING (season, week, game_id)
          JOIN `{PROJECT}.nfl_features.player_week_actuals` a
            ON a.season=p.season AND a.week=p.week AND a.gsis_id=p.player_id
          WHERE p.scope=@scope AND p.position != 'DST'
          ORDER BY season, week, player_id
        """
    elif kind == "dst":
        query = f"""
          WITH target AS ({target})
          SELECT DISTINCT p.season, p.week, p.team,
                 d.dst_dk_points AS dk_points
          FROM `{PROJECT}.{FORENSIC_DATASET}.{PLAYER_TABLE}` p
          JOIN target USING (season, week, game_id)
          JOIN `{PROJECT}.nfl_features.team_defense_week` d
            ON d.season=p.season AND d.week=p.week AND d.team=p.team
          WHERE p.scope=@scope AND p.position='DST'
          ORDER BY season, week, team
        """
    else:
        raise ValueError("unknown authoritative label kind")
    return _query(client, query, [
        bigquery.ScalarQueryParameter("keys", "STRING", encoded),
        bigquery.ScalarQueryParameter("scope", "STRING", SCOPE),
    ])


def _load_artifact(
    client: storage.Client, uri: str, digest: str,
) -> tuple[dict, dict]:
    raw, blob = _download_bytes(client, uri)
    artifact = decode_score_artifact(raw, digest)
    return artifact, {
        "uri": uri,
        "sha256": digest,
        "generation": str(blob.generation),
        "updated": blob.updated.isoformat() if blob.updated else None,
        "size": int(blob.size),
    }


def _catalog_for_slate(
    players: pd.DataFrame,
    schedule: pd.DataFrame,
    universe: set[str],
) -> pd.DataFrame:
    frame = players[players.player_id.astype(str).isin(universe)].copy()
    if set(frame.player_id.astype(str)) != universe or frame.player_id.duplicated().any():
        raise RuntimeError("forensic player catalog differs from score-world universe")
    game_map = schedule.set_index("canonical_game_id")
    frame["full_game_id"] = frame.game_id.map(game_map.game_id)
    frame["kickoff"] = frame.game_id.map(game_map.kickoff_utc)
    if frame.full_game_id.isna().any() or frame.kickoff.isna().any():
        raise RuntimeError("player catalog has an unmapped schedule game")
    return pd.DataFrame({
        "player_id": frame.player_id.astype(str),
        "dk_id": frame.player_id.astype(str),
        "name": frame.player_name.astype(str),
        "position": frame.position.astype(str),
        "pos": frame.position.astype(str),
        "team": frame.team.astype(str),
        "game_id": frame.full_game_id.astype(str),
        "kickoff_time": frame.kickoff.astype(str),
        "kickoff": frame.kickoff.astype(str),
        "salary": pd.to_numeric(frame.salary, errors="raise").astype(int),
    })


def _audit_lateral_residuals(
    pbp: pd.DataFrame,
    status_by_slate: dict[tuple[int, int], pd.DataFrame],
    universes: dict[tuple[int, int], set[str]],
    decision_by_slate: dict[tuple[int, int], pd.Timestamp],
) -> list[dict]:
    audits = []
    for season, week, player_id in LATERAL_RESIDUALS:
        key = (season, week)
        relevant = player_id in universes.get(key, set())
        if not relevant:
            audits.append({
                "season": season, "week": week, "player_id": player_id,
                "candidate_relevant": False, "disposition": "outside_world_universe",
            })
            continue
        registered = [
            (game_id, play_id, adjustment)
            for (game_id, play_id), adjustment in MULTI_LATERAL_ADJUSTMENTS.items()
            if player_id in adjustment["rec_yards"]
        ]
        if len(registered) != 1:
            raise RuntimeError(
                f"lateral residual lacks one registered description adjustment: "
                f"{key} {player_id}"
            )
        game_id, play_id, adjustment = registered[0]
        matches = pbp[
            pbp.season.astype(int).eq(season) & pbp.week.astype(int).eq(week)
            & pbp.game_id.astype(str).eq(game_id)
            & pd.to_numeric(pbp.play_id, errors="coerce").eq(play_id)
        ].copy()
        if len(matches) != 1:
            raise RuntimeError(
                f"candidate-relevant lateral residual is not identifiable: {key} {player_id}"
            )
        description = str(matches.iloc[0]["desc"])
        if hashlib.sha256(description.encode("utf-8")).hexdigest() != str(
            adjustment["description_sha256"]
        ):
            raise RuntimeError("candidate-relevant lateral description checksum differs")
        matches["event_time"] = pd.to_datetime(
            matches.time_of_day, format="mixed", errors="coerce", utc=True,
        )
        if matches.event_time.isna().any():
            raise RuntimeError("candidate-relevant lateral residual lacks event time")
        statuses = status_by_slate[key].set_index("game_id").game_status.to_dict()
        before = matches.event_time.le(decision_by_slate[key].tz_convert("UTC"))
        game_status = statuses.get(game_id)
        if game_status is None:
            raise RuntimeError("lateral residual game is outside the target slate")
        enters_partial_score = bool(before.iloc[0] and game_status == "in_progress")
        audits.append({
            "season": season, "week": week, "player_id": player_id,
            "candidate_relevant": True,
            "matching_lateral_rows": int(len(matches)),
            "rows_before_decision": int(before.sum()),
            "game_id": game_id,
            "play_id": play_id,
            "game_status": game_status,
            "rec_yards_adjustment": float(adjustment["rec_yards"][player_id]),
            "enters_partial_score": enters_partial_score,
            "description_sha256": str(adjustment["description_sha256"]),
            "disposition": (
                "checksum_bound_description_reconciliation"
                if enters_partial_score else "safe_final_or_post_decision"
            ),
        })
    return audits


def _proposal_record(
    season: int,
    week: int,
    book: pd.DataFrame,
    policy: dict,
    *,
    decision: pd.Timestamp,
    parity: dict,
    source_receipt: dict,
    status_receipt: dict,
    points_receipt: dict,
    world_receipt: dict,
    catalog: pd.DataFrame,
) -> dict:
    initial = book[book.selected.astype(bool)].sort_values(
        "selected_rank", kind="stable",
    )
    initial_assignments = {
        f"entry-{rank:03d}": list(canonical_roster(row.players))
        for rank, row in enumerate(initial.itertuples(index=False))
    }
    kickoff = pd.to_datetime(catalog.kickoff, utc=True)
    locked = int(kickoff.le(decision.tz_convert("UTC")).sum())
    record = {
        "season": season,
        "week": week,
        "decision_instant": decision.isoformat(),
        "candidate_count": int(len(book)),
        "entry_count": ENTRY_COUNT,
        "initial_assignments": initial_assignments,
        "assignments": policy["assignments"],
        "changed_entries": int(policy["changed_entries"]),
        "changes": policy["changes"],
        "alternatives_considered": int(sum(policy["alternatives_considered"].values())),
        "initial_book_objective": policy["initial_book_objective"],
        "final_book_objective": policy["final_book_objective"],
        "simulated_non_decline": tuple(policy["final_book_objective"]) >= tuple(
            policy["initial_book_objective"]
        ),
        "player_status_counts": points_receipt["status_counts"],
        "game_status_counts": status_receipt["status_counts"],
        "locked_players": locked,
        "unlocked_players": int(len(catalog) - locked),
        "candidate_parity_receipt": parity,
        "source_artifact_receipt": source_receipt,
        "game_status_receipt": status_receipt,
        "points_receipt": points_receipt,
        "world_adapter_receipt": world_receipt,
        "uses_post_decision_outcomes": False,
    }
    if not record["simulated_non_decline"]:
        raise RuntimeError("frozen policy declined its simulated book objective")
    record["proposal_sha256"] = canonical_json_sha256(record)
    return record


def _numeric_summary(values: list[float]) -> dict:
    return {
        "mean": float(np.mean(values)),
        "median": float(median(values)),
        "minimum": float(min(values)),
        "maximum": float(max(values)),
    }


def run(output_uri: str, proposal_uri: str) -> dict:
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.search(
        r"@sha256:[0-9a-f]{64}$", image,
    ) is None:
        raise RuntimeError("full CODE_SHA and immutable ANALYSIS_IMAGE are required")
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    scorer_audit_raw, scorer_audit_blob = _download_bytes(gcs, SCORER_AUDIT_URI)
    scorer_audit = json.loads(scorer_audit_raw)
    if (
        scorer_audit.get("analysis_code_sha") != code_sha
        or scorer_audit.get("analysis_image") != image
        or scorer_audit.get("authoritative_player_weeks") != 75_712
        or scorer_audit.get("exact_player_weeks") != 75_712
        or scorer_audit.get("authoritative_stat_player_weeks") != 54_419
        or scorer_audit.get("exact_stat_player_weeks") != 54_419
        or scorer_audit.get("authoritative_salary_zero_player_weeks") != 21_293
        or scorer_audit.get("exact_salary_zero_player_weeks") != 21_293
        or scorer_audit.get("differences") != 0
        or scorer_audit.get("multi_lateral_plays_adjusted") != 8
        or scorer_audit.get("multi_lateral_players_adjusted") != 12
        or scorer_audit.get("scoring_relevant_missing_time") != 0
    ):
        raise RuntimeError("same-image PIT scorer reconciliation receipt differs")
    scorer_audit_receipt = {
        "uri": SCORER_AUDIT_URI,
        "generation": str(scorer_audit_blob.generation),
        "sha256": hashlib.sha256(scorer_audit_raw).hexdigest(),
        "exact_player_weeks": 75_712,
        "exact_stat_player_weeks": 54_419,
        "exact_salary_zero_player_weeks": 21_293,
        "same_code_and_image": True,
    }
    for table_name in (PLAYER_TABLE, CANDIDATE_TABLE):
        table = bq.get_table(f"{PROJECT}.{FORENSIC_DATASET}.{table_name}")
        if (table.labels or {}).get("manifest") != MANIFEST_SHA256[:32]:
            raise RuntimeError(f"forensic table manifest differs: {table_name}")

    source_rows = _query(bq, f"""
      SELECT panel_run_id, season, week, cand_ix, players, selected,
             selected_rank, score_artifact_uri, score_artifact_sha256
      FROM `{PROJECT}.nfl_predictions.replay_candidates_staging`
      WHERE panel_run_id IN UNNEST(@panel_ids)
      ORDER BY panel_run_id, season, week, cand_ix
    """, [bigquery.ArrayQueryParameter("panel_ids", "STRING", list(SOURCE_PANEL_IDS))])
    forensic_candidates = _query(bq, f"""
      SELECT season, week, roster_key, selected, selected_rank
      FROM `{PROJECT}.{FORENSIC_DATASET}.{CANDIDATE_TABLE}`
      WHERE scope=@scope
      ORDER BY season, week, candidate_index
    """, [bigquery.ScalarQueryParameter("scope", "STRING", SCOPE)])
    players = _query(bq, f"""
      SELECT season, week, player_id, player_name, position, team, opponent,
             game_id, kickoff_time, salary
      FROM `{PROJECT}.{FORENSIC_DATASET}.{PLAYER_TABLE}`
      WHERE scope=@scope
      ORDER BY season, week, player_id
    """, [bigquery.ScalarQueryParameter("scope", "STRING", SCOPE)])
    if players.duplicated(["season", "week", "player_id"]).any():
        raise RuntimeError("forensic player corpus repeats a slate player")
    slates = sorted(set(map(tuple, forensic_candidates[["season", "week"]].astype(int).to_numpy())))
    if len(slates) != 54:
        raise RuntimeError("realistic recourse scope does not contain 54 slates")
    forensic_pairs = {
        (int(row.season), int(row.week), str(row.game_id))
        for row in players.itertuples(index=False)
    }
    raw_schedule = _query(bq, f"""
      SELECT game_id, season, week, gameday, gametime, away_team, home_team
      FROM `{PROJECT}.nfl_raw.schedules`
      WHERE game_type='REG' AND season IN (2023, 2024, 2025)
        AND weekday='Sunday'
        AND SAFE.PARSE_TIME('%H:%M', gametime) >= TIME '13:00:00'
        AND SAFE.PARSE_TIME('%H:%M', gametime) < TIME '19:00:00'
      ORDER BY season, week, game_id
    """)
    schedules = _prepare_schedule(raw_schedule, forensic_pairs)
    pbp_columns = """
      game_id, season, week, play_id, time_of_day, qtr, game_seconds_remaining,
      `desc`, home_team, away_team, total_home_score, total_away_score,
      passing_yards, pass_touchdown, interception, rushing_yards, rush_touchdown,
      complete_pass, receiving_yards, lateral_receiving_yards,
      lateral_rushing_yards, fumble_lost, two_point_attempt,
      two_point_conv_result, return_touchdown, sack, safety, punt_blocked,
      defensive_two_point_conv, touchdown, own_kickoff_recovery_td,
      field_goal_result, extra_point_result, play_type, posteam, defteam, td_team,
      fantasy_player_id, passer_player_id, receiver_player_id, rusher_player_id,
      lateral_receiver_player_id, lateral_rusher_player_id, td_player_id,
      kickoff_returner_player_id, lateral_kickoff_returner_player_id,
      punt_returner_player_id, lateral_punt_returner_player_id,
      own_kickoff_recovery_player_id, fumbled_1_player_id, fumbled_1_team,
      fumble_recovery_1_team, fumbled_2_player_id, fumbled_2_team,
      fumble_recovery_2_team
    """
    pbp = _query(bq, f"""
      SELECT {pbp_columns}
      FROM `{PROJECT}.nfl_raw.pbp`
      WHERE season IN (2023, 2024, 2025)
      ORDER BY season, week, game_id, play_id
    """)
    target_game_ids = set(schedules.game_id.astype(str))
    pbp = pbp[pbp.game_id.astype(str).isin(target_game_ids)].copy()

    decision_by_slate: dict[tuple[int, int], pd.Timestamp] = {}
    status_by_slate: dict[tuple[int, int], pd.DataFrame] = {}
    status_receipts: dict[tuple[int, int], dict] = {}
    final_keys: list[dict] = []
    for season, week in slates:
        schedule = schedules[
            schedules.season.astype(int).eq(season)
            & schedules.week.astype(int).eq(week)
        ].copy()
        dates = schedule.gameday.astype(str).unique()
        if len(dates) != 1:
            raise RuntimeError(f"slate has multiple game dates: {season}w{week}")
        decision = decision_instant(dates[0])
        slate_pbp = pbp[
            pbp.season.astype(int).eq(season) & pbp.week.astype(int).eq(week)
        ]
        statuses, receipt = derive_game_statuses(
            schedule[["game_id", "kickoff_utc"]], slate_pbp, as_of=decision,
        )
        decision_by_slate[(season, week)] = decision
        status_by_slate[(season, week)] = statuses
        status_receipts[(season, week)] = receipt
        reverse_pair = schedule.set_index("game_id").canonical_game_id.to_dict()
        for game_id in statuses.loc[
            statuses.game_status.eq("final"), "game_id"
        ].astype(str):
            final_keys.append({
                "season": season, "week": week, "game_id": reverse_pair[game_id],
            })
    audit_universes = {}
    for season, week in slates:
        roster_values = forensic_candidates[
            forensic_candidates.season.astype(int).eq(season)
            & forensic_candidates.week.astype(int).eq(week)
        ].roster_key.astype(str)
        audit_universes[(season, week)] = set().union(*(
            set(canonical_roster(value)) for value in roster_values
        ))
    lateral_audit = _audit_lateral_residuals(
        pbp, status_by_slate, audit_universes, decision_by_slate,
    )
    asof_skill = _json_key_query(bq, keys=final_keys, kind="skill")
    asof_dst = _json_key_query(bq, keys=final_keys, kind="dst")

    proposals: list[dict] = []
    for slate_index, (season, week) in enumerate(slates, start=1):
        seed_frames: dict[int, pd.DataFrame] = {}
        artifacts: dict[int, dict] = {}
        source_receipts: dict[int, dict] = {}
        for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
            rows = source_rows[
                source_rows.panel_run_id.astype(str).eq(panel_id)
                & source_rows.season.astype(int).eq(season)
                & source_rows.week.astype(int).eq(week)
            ].copy()
            if rows.empty:
                raise RuntimeError(f"source R{seed} missing {season}w{week}")
            uris = rows.score_artifact_uri.astype(str).unique()
            digests = rows.score_artifact_sha256.astype(str).unique()
            if len(uris) != 1 or len(digests) != 1:
                raise RuntimeError("source seed/slate lacks one artifact identity")
            artifact, receipt = _load_artifact(gcs, uris[0], digests[0])
            seed_frames[seed] = rows.drop(
                columns=["score_artifact_uri", "score_artifact_sha256"],
            )
            artifacts[seed] = artifact
            source_receipts[seed] = {**receipt, "panel_run_id": panel_id}
        book = reconstruct_outcome_blind_cbwu(seed_frames, artifacts)
        forensic = forensic_candidates[
            forensic_candidates.season.astype(int).eq(season)
            & forensic_candidates.week.astype(int).eq(week)
        ].drop(columns=["season", "week"])
        parity = validate_forensic_parity(book, forensic)
        initial_lock = decision_by_slate[(season, week)].replace(hour=12, minute=55)
        combined, combined_receipt = combine_seed_player_worlds(
            artifacts, source_receipts,
            counterfactual_generated_at=initial_lock,
        )
        universe = set(map(str, combined["player_ids"]))
        slate_players = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ]
        slate_schedule = schedules[
            schedules.season.astype(int).eq(season)
            & schedules.week.astype(int).eq(week)
        ]
        catalog = _catalog_for_slate(slate_players, slate_schedule, universe)
        statuses = status_by_slate[(season, week)]
        final_game_ids = set(statuses.loc[
            statuses.game_status.eq("final"), "game_id"
        ].astype(str))
        slate_pbp = pbp[
            pbp.season.astype(int).eq(season) & pbp.week.astype(int).eq(week)
        ]
        skill = asof_skill[
            asof_skill.season.astype(int).eq(season)
            & asof_skill.week.astype(int).eq(week)
        ][["player_id", "dk_points"]]
        dst = asof_dst[
            asof_dst.season.astype(int).eq(season)
            & asof_dst.week.astype(int).eq(week)
        ][["team", "dk_points"]]
        information, points_receipt = points_information_as_of(
            slate_pbp,
            catalog[[
                "player_id", "dk_id", "position", "team", "game_id", "kickoff_time",
            ]],
            skill,
            dst,
            as_of=decision_by_slate[(season, week)],
            final_game_ids=final_game_ids,
        )
        remaining, points, world_receipt = derive_remaining_worlds(
            combined, catalog, information,
            as_of=decision_by_slate[(season, week)],
        )
        selected = book[book.selected.astype(bool)].sort_values(
            "selected_rank", kind="stable",
        )
        entry_rosters = {
            f"entry-{rank:03d}": list(canonical_roster(row.players))
            for rank, row in enumerate(selected.itertuples(index=False))
        }
        candidates = [
            list(canonical_roster(value)) for value in book.players.astype(str)
        ]
        policy = propose_recourse_rosters(
            entry_rosters,
            candidates,
            catalog,
            remaining,
            points,
            as_of=decision_by_slate[(season, week)],
            worlds_generated_at=combined["generated_at"],
        )
        proposals.append(_proposal_record(
            season, week, book, policy,
            decision=decision_by_slate[(season, week)],
            parity=parity,
            source_receipt=combined_receipt,
            status_receipt=status_receipts[(season, week)],
            points_receipt=points_receipt,
            world_receipt=world_receipt,
            catalog=catalog,
        ))
        print(f"RECOURSE_PROPOSAL {slate_index}/54 {season}w{week}", flush=True)

    frozen = freeze_proposals(proposals)
    frozen.update({
        "manifest_sha256": MANIFEST_SHA256,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "lateral_residual_audit": lateral_audit,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    frozen_payload = json.dumps(
        frozen, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    proposal_receipt = _upload_create_only(gcs, proposal_uri, frozen_payload)

    # Outcome phase begins only after the create-only proposal ledger exists.
    outcomes = _query(bq, f"""
      SELECT season, week, roster_key, actual_score, selected, selected_rank
      FROM `{PROJECT}.{FORENSIC_DATASET}.{CANDIDATE_TABLE}`
      WHERE scope=@scope
      ORDER BY season, week, candidate_index
    """, [bigquery.ScalarQueryParameter("scope", "STRING", SCOPE)])
    exact_raw, exact_blob = _download_bytes(gcs, EXACT_STACK_URI)
    if hashlib.sha256(exact_raw).hexdigest() != EXPECTED_EXACT_STACK_SHA256:
        raise RuntimeError("corrected exact-stack result checksum differs")
    exact = json.loads(exact_raw)
    exact_stack_receipt = {
        "uri": EXACT_STACK_URI,
        "generation": str(exact_blob.generation),
        "sha256": EXPECTED_EXACT_STACK_SHA256,
        "analysis_code_sha": str(exact.get("analysis_code_sha")),
        "analysis_image": str(exact.get("analysis_image")),
    }
    exact_by_slate = {
        (int(row["season"]), int(row["week"])): row for row in exact["records"]
    }
    records = []
    for proposal in proposals:
        season, week = int(proposal["season"]), int(proposal["week"])
        slate = outcomes[
            outcomes.season.astype(int).eq(season)
            & outcomes.week.astype(int).eq(week)
        ].copy()
        slate["roster_key"] = slate.roster_key.map(
            lambda value: ",".join(canonical_roster(value))
        )
        if slate.roster_key.duplicated().any():
            raise RuntimeError("outcome candidate roster identity repeats")
        actual = dict(zip(
            slate.roster_key.astype(str),
            pd.to_numeric(slate.actual_score, errors="raise").astype(float),
            strict=True,
        ))
        initial_items = sorted(proposal["initial_assignments"].items())
        final_items = sorted(proposal["assignments"].items())
        if [key for key, _ in initial_items] != [key for key, _ in final_items]:
            raise RuntimeError("proposal entry identities drifted in outcome phase")
        def lookup(roster: list[str]) -> float:
            key = ",".join(canonical_roster(roster))
            if key not in actual:
                raise RuntimeError("proposed roster is absent from outcome corpus")
            return actual[key]
        initial_scores = {key: lookup(roster) for key, roster in initial_items}
        final_scores = {key: lookup(roster) for key, roster in final_items}
        initial_best_entry = max(initial_scores, key=lambda key: (initial_scores[key], key))
        final_best_entry = max(final_scores, key=lambda key: (final_scores[key], key))
        initial_best = initial_scores[initial_best_entry]
        final_best = final_scores[final_best_entry]
        correction = exact_by_slate[(season, week)]
        p_row = min(
            slate.itertuples(index=False),
            key=lambda row: (-float(row.actual_score), str(row.roster_key)),
        )
        if not np.isclose(float(p_row.actual_score), float(correction["exact_p"])):
            raise RuntimeError("corrected exact-P score differs from outcome corpus")
        p_roster = canonical_roster(p_row.roster_key)
        hindsight_source = canonical_roster(
            correction["corrected_recourse"]["source_roster"]
        )
        hindsight_final = canonical_roster(
            correction["corrected_recourse"]["final_roster"]
        )
        source_entries = [
            entry for entry, roster in initial_items
            if canonical_roster(roster) == hindsight_source
        ]
        if len(source_entries) != 1:
            raise RuntimeError("corrected hindsight source is not one selected entry")
        source_entry = source_entries[0]
        realistic_from_source = canonical_roster(proposal["assignments"][source_entry])
        final_rosters = [canonical_roster(roster) for _, roster in final_items]
        changed = proposal["changes"]
        delta = float(final_best - initial_best)
        pi_gain = float(correction["corrected_recourse"]["ceiling_gain"])
        records.append({
            "season": season,
            "week": week,
            "proposal_sha256": proposal["proposal_sha256"],
            "initial_weekly_max": float(initial_best),
            "final_weekly_max": float(final_best),
            "realized_delta": delta,
            "initial_best_entry": initial_best_entry,
            "final_best_entry": final_best_entry,
            "changed_entries": int(proposal["changed_entries"]),
            "player_replacements": int(sum(len(row["players_out"]) for row in changed)),
            "locked_player_replacements": 0,
            "perfect_information_ceiling_gain": pi_gain,
            "perfect_information_ceiling_score": float(
                correction["corrected_recourse"]["perfect_information_ceiling"]
            ),
            "recovery_fraction": None if pi_gain == 0 else delta / pi_gain,
            "exact_p_score": float(p_row.actual_score),
            "final_best_distance_to_exact_p": roster_swap_distance(
                proposal["assignments"][final_best_entry], p_roster,
            ),
            "closest_final_distance_to_exact_p": min(
                roster_swap_distance(roster, p_roster) for roster in final_rosters
            ),
            "realistic_source_entry_distance_to_hindsight_final": (
                roster_swap_distance(realistic_from_source, hindsight_final)
            ),
            "realistic_source_entry_distance_to_hindsight_source": (
                roster_swap_distance(realistic_from_source, hindsight_source)
            ),
        })

    initial_values = [row["initial_weekly_max"] for row in records]
    final_values = [row["final_weekly_max"] for row in records]
    deltas = [row["realized_delta"] for row in records]
    pi_gains = [row["perfect_information_ceiling_gain"] for row in records]
    result = {
        "protocol_id": PROTOCOL_ID,
        "scope": SCOPE,
        "manifest_sha256": MANIFEST_SHA256,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slates": len(records),
        "expected_entries": ENTRY_COUNT,
        "proposal_ledger": proposal_receipt,
        "scorer_reconciliation": scorer_audit_receipt,
        "corrected_exact_stack_source": exact_stack_receipt,
        "proposal_set_sha256": frozen["proposal_set_sha256"],
        "proposal_frozen_before_outcome_query": True,
        "outcome_phase_opened_after_proposal_generation": proposal_receipt["generation"],
        "realized_weekly_max": {
            "initial": _numeric_summary(initial_values),
            "final": _numeric_summary(final_values),
            "delta": _numeric_summary(deltas),
            "improved_slates": int(sum(value > 1e-8 for value in deltas)),
            "tied_slates": int(sum(abs(value) <= 1e-8 for value in deltas)),
            "worsened_slates": int(sum(value < -1e-8 for value in deltas)),
        },
        "tail_counts": {
            "initial": {
                str(int(tail)): int(sum(value >= tail for value in initial_values))
                for tail in TAILS
            },
            "final": {
                str(int(tail)): int(sum(value >= tail for value in final_values))
                for tail in TAILS
            },
        },
        "season_diagnostics": {
            str(season): {
                "slates": int(sum(row["season"] == season for row in records)),
                "initial_mean": float(np.mean([
                    row["initial_weekly_max"] for row in records if row["season"] == season
                ])),
                "final_mean": float(np.mean([
                    row["final_weekly_max"] for row in records if row["season"] == season
                ])),
                "delta_mean": float(np.mean([
                    row["realized_delta"] for row in records if row["season"] == season
                ])),
            }
            for season in sorted({row["season"] for row in records})
        },
        "perfect_information_recovery": {
            "realized_gain_sum": float(sum(deltas)),
            "perfect_information_gain_sum": float(sum(pi_gains)),
            "aggregate_fraction": float(sum(deltas) / sum(pi_gains)),
        },
        "swap_counts": {
            "entries_changed": int(sum(row["changed_entries"] for row in records)),
            "player_replacements": int(sum(row["player_replacements"] for row in records)),
            "locked_player_replacements": 0,
        },
        "distance_diagnostics": {
            field: _numeric_summary([float(row[field]) for row in records])
            for field in (
                "final_best_distance_to_exact_p",
                "closest_final_distance_to_exact_p",
                "realistic_source_entry_distance_to_hindsight_final",
                "realistic_source_entry_distance_to_hindsight_source",
            )
        },
        "records": records,
        "use_restriction": (
            "Outcome-viewed descriptive sizing only; cannot promote a historical "
            "money policy and is not expected ROI."
        ),
        "uses_realized_outcomes": True,
    }
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    result_receipt = _upload_create_only(gcs, output_uri, payload)
    summary = {
        "protocol_id": PROTOCOL_ID,
        "output": result_receipt,
        "proposal_ledger": proposal_receipt,
        "realized_weekly_max": result["realized_weekly_max"],
        "tail_counts": result["tail_counts"],
        "perfect_information_recovery": result["perfect_information_recovery"],
    }
    print("REALISTIC_RECOURSE_SIZING " + json.dumps(summary, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--proposal-uri", required=True)
    args = parser.parse_args()
    run(args.output_uri, args.proposal_uri)


if __name__ == "__main__":
    main()
