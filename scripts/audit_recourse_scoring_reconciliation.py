#!/usr/bin/env python3
"""Create-only full 2023--2025 reconciliation for the PIT skill scorer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.research.recourse_scoring import score_skill_players


PROJECT = "nfl-predictions-503414"
EXPECTED_STAT_PLAYER_WEEKS = 54_419
EXPECTED_SALARY_ZERO_PLAYER_WEEKS = 21_293
EXPECTED_PLAYER_WEEKS = (
    EXPECTED_STAT_PLAYER_WEEKS + EXPECTED_SALARY_ZERO_PLAYER_WEEKS
)


def _query(client: bigquery.Client, sql: str) -> pd.DataFrame:
    return client.query(sql, location="US").result().to_dataframe(
        create_bqstorage_client=False,
    )


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("audit output must name one GCS object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("audit output URI is invalid")
    return bucket, name


def run(output_uri: str) -> dict:
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.search(
        r"@sha256:[0-9a-f]{64}$", image,
    ) is None:
        raise RuntimeError("full CODE_SHA and immutable ANALYSIS_IMAGE are required")
    client = bigquery.Client(project=PROJECT)
    pbp = _query(client, f"""
      SELECT p.game_id, p.season, p.week, p.play_id, p.time_of_day,
             p.`desc`, p.home_team, p.away_team, p.total_home_score,
             p.total_away_score, p.passing_yards, p.pass_touchdown,
             p.interception, p.rushing_yards, p.rush_touchdown,
             p.complete_pass, p.receiving_yards, p.lateral_receiving_yards,
             p.lateral_rushing_yards, p.fumble_lost, p.two_point_attempt,
             p.two_point_conv_result, p.return_touchdown, p.sack, p.safety,
             p.punt_blocked, p.defensive_two_point_conv, p.touchdown,
             p.own_kickoff_recovery_td, p.field_goal_result,
             p.extra_point_result, p.play_type, p.posteam, p.defteam, p.td_team,
             p.fantasy_player_id, p.passer_player_id, p.receiver_player_id,
             p.rusher_player_id, p.lateral_receiver_player_id,
             p.lateral_rusher_player_id, p.td_player_id,
             p.kickoff_returner_player_id,
             p.lateral_kickoff_returner_player_id,
             p.punt_returner_player_id, p.lateral_punt_returner_player_id,
             p.own_kickoff_recovery_player_id, p.fumbled_1_player_id,
             p.fumbled_1_team, p.fumble_recovery_1_team,
             p.fumbled_2_player_id, p.fumbled_2_team,
             p.fumble_recovery_2_team
      FROM `{PROJECT}.nfl_raw.pbp` p
      JOIN `{PROJECT}.nfl_raw.schedules` s USING (game_id)
      WHERE p.season IN (2023, 2024, 2025) AND s.game_type='REG'
      ORDER BY p.season, p.week, p.game_id, p.play_id
    """)
    labels = _query(client, f"""
      SELECT season, week, gsis_id AS player_id, dk_points, has_stat_line
      FROM `{PROJECT}.nfl_features.player_week_actuals`
      WHERE season IN (2023, 2024, 2025)
      ORDER BY season, week, player_id
    """)
    if (
        len(labels) != EXPECTED_PLAYER_WEEKS
        or int(labels.has_stat_line.fillna(False).astype(bool).sum())
        != EXPECTED_STAT_PLAYER_WEEKS
        or int((~labels.has_stat_line.fillna(False).astype(bool)).sum())
        != EXPECTED_SALARY_ZERO_PLAYER_WEEKS
        or labels.duplicated(
        ["season", "week", "player_id"]
        ).any()
    ):
        raise RuntimeError("authoritative reconciliation population differs")
    computed: dict[tuple[int, int, str], float] = {}
    receipts = []
    for (season, week), group in pbp.groupby(["season", "week"], sort=True):
        scored, receipt = score_skill_players(group)
        receipts.append({"season": int(season), "week": int(week), **receipt})
        for row in scored.itertuples(index=False):
            key = (int(season), int(week), str(row.player_id))
            if key in computed:
                raise RuntimeError("computed scorer identity repeats")
            computed[key] = float(row.dk_points)
    differences = []
    label_keys = set()
    for row in labels.itertuples(index=False):
        key = (int(row.season), int(row.week), str(row.player_id))
        label_keys.add(key)
        actual = float(row.dk_points)
        estimate = float(computed.get(key, 0.0))
        delta = estimate - actual
        if not np.isclose(delta, 0.0, rtol=0.0, atol=1e-8):
            differences.append({
                "season": key[0], "week": key[1], "player_id": key[2],
                "computed_minus_authoritative": delta,
            })
    extra = [
        {"season": key[0], "week": key[1], "player_id": key[2], "dk_points": value}
        for key, value in computed.items()
        if key not in label_keys and not np.isclose(value, 0.0, atol=1e-8)
    ]
    if differences or extra:
        raise RuntimeError(
            f"PIT scorer reconciliation differs: labels={len(differences)} "
            f"nonzero_extra={len(extra)} first={(differences or extra)[:3]}"
        )
    result = {
        "protocol": "20260815-pit-skill-scorer-reconciliation-v2",
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pbp_rows": int(len(pbp)),
        "authoritative_player_weeks": int(len(labels)),
        "exact_player_weeks": int(len(labels)),
        "authoritative_stat_player_weeks": EXPECTED_STAT_PLAYER_WEEKS,
        "exact_stat_player_weeks": EXPECTED_STAT_PLAYER_WEEKS,
        "authoritative_salary_zero_player_weeks": (
            EXPECTED_SALARY_ZERO_PLAYER_WEEKS
        ),
        "exact_salary_zero_player_weeks": EXPECTED_SALARY_ZERO_PLAYER_WEEKS,
        "differences": 0,
        "nonzero_computed_identities_outside_labels": 0,
        "multi_lateral_plays_adjusted": int(sum(
            row["multi_lateral_plays_adjusted"] for row in receipts
        )),
        "multi_lateral_players_adjusted": int(sum(
            row["multi_lateral_players_adjusted"] for row in receipts
        )),
        "scoring_relevant_missing_time": int(sum(
            row["scoring_relevant_missing_time"] for row in receipts
        )),
        "slate_receipts": receipts,
        "uses_realized_labels": True,
        "use_restriction": "data-correctness reconciliation only",
    }
    if (
        result["multi_lateral_plays_adjusted"] != 8
        or result["multi_lateral_players_adjusted"] != 12
        or result["scoring_relevant_missing_time"] != 0
    ):
        raise RuntimeError("multi-lateral or timestamp reconciliation counts differ")
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    bucket, name = _parse_gcs(output_uri)
    blob = storage.Client(project=PROJECT).bucket(bucket).blob(name)
    blob.upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    summary = {
        "output_uri": output_uri,
        "generation": str(blob.generation),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "pbp_rows": result["pbp_rows"],
        "exact_player_weeks": result["exact_player_weeks"],
        "exact_stat_player_weeks": result["exact_stat_player_weeks"],
        "exact_salary_zero_player_weeks": (
            result["exact_salary_zero_player_weeks"]
        ),
        "multi_lateral_players_adjusted": 12,
    }
    print("RECOURSE_SCORER_RECONCILIATION " + json.dumps(summary, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.output_uri)


if __name__ == "__main__":
    main()
