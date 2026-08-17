from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models.dst_scoring import (
    DST_COMPONENTS,
    DST_SCORING_LAW_ID,
    points_allowed_points,
    score_dst_components,
)
from nfl_dfs.research.dst_event_frame import (
    DstEventFrameError,
    SCORING_LAW_SOURCE_SHA256,
    census_dst_event_support,
    validate_dst_event_frame,
)


def _event_frame(games=None) -> pd.DataFrame:
    games = games or (
        (2024, 17, "2024_17_B_A", "A", "B", 17, 10),
        (2024, 18, "2024_18_A_B", "B", "A", 20, 13),
        (2025, 1, "2025_01_B_A", "A", "B", 24, 21),
    )
    rows = []
    for game_index, (season, week, game_id, home, away, home_score, away_score) in enumerate(games):
        sides = ((home, away, away_score), (away, home, home_score))
        component_rows = {}
        for side_index, (team, _, _) in enumerate(sides):
            ordinal = game_index * 2 + side_index
            component_rows[team] = {
                "sacks": ordinal % 4,
                "interceptions": ordinal % 2,
                "fumble_recoveries": int(ordinal == 2),
                "safeties": int(ordinal == 3),
                "defensive_safeties": int(ordinal == 3),
                "blocked_kicks": int(ordinal == 4),
                "return_tds": int(ordinal == 5),
                "defensive_return_tds": int(ordinal == 5),
                "defensive_conversions": int(ordinal == 1),
            }
        for side_index, (team, opponent, opponent_score) in enumerate(sides):
            ordinal = game_index * 2 + side_index
            components = component_rows[team]
            opponent_components = component_rows[opponent]
            excluded_td = opponent_components["defensive_return_tds"] * 6
            excluded_safety = opponent_components["defensive_safeties"] * 2
            excluded = excluded_td + excluded_safety
            pa = opponent_score - excluded
            reconstruction = score_dst_components(
                {component: components[component] for component in DST_COMPONENTS},
                points_allowed=pa,
            )
            authoritative = reconstruction if ordinal % 2 == 0 else np.nan
            source = (
                {
                    "authoritative_source_raw_rows": 1,
                    "authoritative_source_matched_rows": 1,
                    "authoritative_source_rejected_rows": 0,
                    "authoritative_distinct_score_count": 1,
                    "authoritative_source_status": "source_match_unique",
                }
                if np.isfinite(authoritative)
                else {
                    "authoritative_source_raw_rows": 0,
                    "authoritative_source_matched_rows": 0,
                    "authoritative_source_rejected_rows": 0,
                    "authoritative_distinct_score_count": 0,
                    "authoritative_source_status": "source_unavailable",
                }
            )
            row = {
                "season": season,
                "week": week,
                "game_id": game_id,
                "team": team,
                "opponent": opponent,
                "opponent_final_score": opponent_score,
                "pa": pa,
                "excluded_defensive_td_points": excluded_td,
                "excluded_safety_points": excluded_safety,
                "excluded_non_dst_points": excluded,
                **components,
                "points_allowed_tier_points": points_allowed_points(pa),
                "reconstructed_dst_dk_points": reconstruction,
                **source,
                "authoritative_dst_dk_points": authoritative,
                "dst_dk_points": reconstruction,
                "score_reconciliation_delta": (
                    0.0 if np.isfinite(authoritative) else np.nan
                ),
                "score_reconciliation_status": (
                    "authoritative_match"
                    if np.isfinite(authoritative)
                    else "reconstruction_only"
                ),
                "event_frame_version": "dst-team-game-event-frame-2026-08-17-v1",
                "scoring_law_id": DST_SCORING_LAW_ID,
                "scoring_law_source_sha256": SCORING_LAW_SOURCE_SHA256,
            }
            payload = {
                "event_frame_version": row["event_frame_version"],
                "scoring_law_id": row["scoring_law_id"],
                "game_id": game_id,
                "season": season,
                "week": week,
                "team": team,
                "opponent": opponent,
                "sacks": components["sacks"],
                "interceptions": components["interceptions"],
                "fumble_recoveries": components["fumble_recoveries"],
                "safeties": components["safeties"],
                "defensive_safeties": components["defensive_safeties"],
                "blocked_kicks": components["blocked_kicks"],
                "return_tds": components["return_tds"],
                "defensive_return_tds": components["defensive_return_tds"],
                "defensive_conversions": components["defensive_conversions"],
                "opponent_final_score": opponent_score,
                "excluded_defensive_td_points": excluded_td,
                "excluded_safety_points": excluded_safety,
                "points_allowed": pa,
                "reconstructed_dst_dk_points": int(reconstruction),
            }
            row["event_vector_payload"] = json.dumps(
                payload, separators=(",", ":"),
            )
            row["event_vector_sha256"] = sha256(
                row["event_vector_payload"].encode(),
            ).hexdigest()
            rows.append(row)
    frame = pd.DataFrame(rows).sort_values(
        ["team", "season", "week", "game_id"], kind="mergesort",
    )
    sources = {"dst_points": "dst_dk_points", **{
        component: component for component in DST_COMPONENTS
    }, "points_allowed": "pa"}
    for suffix, window, groups in (
        ("l4", 4, ["team", "season"]),
        ("l16", 16, ["team"]),
    ):
        for output, source in sources.items():
            column = (
                f"dst_points_{suffix}"
                if output == "dst_points"
                else f"dst_event_{output}_{suffix}"
            )
            frame[column] = frame.groupby(
                groups, sort=False,
            )[source].transform(
                lambda values: values.shift(1).rolling(
                    window, min_periods=1,
                ).mean(),
            )
        frame[f"dst_event_games_prior_{suffix}"] = frame.groupby(
            groups, sort=False,
        )["game_id"].transform(
            lambda values: values.shift(1).rolling(
                window, min_periods=1,
            ).count(),
        ).fillna(0.0)
    return frame.sample(frac=1.0, random_state=17).reset_index(drop=True)


def test_canonical_dst_event_frame_and_prior_windows_validate():
    frame = _event_frame()
    receipt = validate_dst_event_frame(
        frame,
        expected_authoritative_rows_by_season={2024: 2, 2025: 1},
    )
    assert receipt == {
        "version": "dst-team-game-event-frame-2026-08-17-v1",
        "scoring_law_id": DST_SCORING_LAW_ID,
        "rows": 6,
        "games": 3,
        "seasons": [2024, 2025],
        "authoritative_rows": 3,
        "authoritative_mismatches": 0,
        "authoritative_source_failures": 0,
        "authoritative_coverage_contract": {2024: 2, 2025: 1},
        "strict_reconciliation_required": True,
        "prior_windows_validated": True,
    }

    ordered = frame.sort_values(["team", "season", "week"])
    first_2025 = ordered[(ordered.season == 2025) & (ordered.week == 1)]
    assert first_2025.dst_event_games_prior_l4.eq(0).all()
    assert first_2025.dst_points_l4.isna().all()
    assert first_2025.dst_event_games_prior_l16.eq(2).all()
    assert first_2025.dst_points_l16.notna().all()


def test_authoritative_difference_is_diagnosable_but_strictly_unlicensed():
    frame = _event_frame()
    index = frame.authoritative_dst_dk_points.first_valid_index()
    frame.loc[index, "authoritative_dst_dk_points"] += 1
    frame.loc[index, "dst_dk_points"] += 1
    frame.loc[index, "score_reconciliation_delta"] = 1.0
    frame.loc[index, "score_reconciliation_status"] = (
        "authoritative_override_mismatch"
    )

    loose = validate_dst_event_frame(
        frame,
        require_reconciled_authoritative_scores=False,
    )
    assert loose["authoritative_mismatches"] == 1
    census = census_dst_event_support(frame)
    assert sum(
        row["authoritative_mismatches"] for row in census["season_support"]
    ) == 1
    with pytest.raises(DstEventFrameError, match="remain unreconciled"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )


def test_event_frame_rejects_duplicate_keys_and_opponent_mismatch():
    frame = _event_frame()
    with pytest.raises(DstEventFrameError, match="repeats a team-game"):
        validate_dst_event_frame(
            pd.concat([frame, frame.iloc[[0]]]),
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )

    bad = frame.copy()
    bad.loc[0, "opponent"] = "Z"
    with pytest.raises(DstEventFrameError, match="opponent mismatch"):
        validate_dst_event_frame(
            bad,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )


def test_event_frame_rejects_current_week_leakage_in_prior_window():
    frame = _event_frame()
    target = frame[
        (frame.season == 2024) & (frame.week == 18) & (frame.team == "A")
    ].index[0]
    frame.loc[target, "dst_event_sacks_l4"] = frame.loc[target, "sacks"]
    with pytest.raises(DstEventFrameError, match="not strictly prior"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )


def test_prior_windows_truncate_at_exact_four_and_sixteen_games():
    games = tuple(
        (
            2023,
            week,
            f"2023_{week:02d}_A_B",
            "A",
            "B",
            20 + week % 5,
            14 + week % 7,
        )
        for week in range(1, 19)
    )
    frame = _event_frame(games)
    validate_dst_event_frame(
        frame,
        expected_authoritative_rows_by_season={2023: 18},
    )
    team = frame[frame.team.eq("A")].sort_values("week")
    target = team[team.week.eq(18)].iloc[0]
    assert target.dst_event_games_prior_l4 == 4
    assert target.dst_event_games_prior_l16 == 16
    assert target.dst_points_l4 == pytest.approx(
        team[team.week.between(14, 17)].dst_dk_points.mean()
    )
    assert target.dst_points_l16 == pytest.approx(
        team[team.week.between(2, 17)].dst_dk_points.mean()
    )


def test_event_payload_hash_is_recomputed_and_version_is_bound():
    frame = _event_frame()
    frame.loc[0, "event_vector_sha256"] = "0" * 64
    with pytest.raises(DstEventFrameError, match="hash differs"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )
    frame = _event_frame()
    frame.loc[0, "event_frame_version"] = "wrong"
    with pytest.raises(DstEventFrameError, match="version differs"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )


def test_impossible_or_nonreciprocal_pa_exclusions_fail_closed():
    frame = _event_frame()
    index = frame.index[0]
    frame.loc[index, "excluded_defensive_td_points"] += 6
    frame.loc[index, "excluded_non_dst_points"] += 6
    frame.loc[index, "pa"] -= 6
    with pytest.raises(DstEventFrameError, match="not reciprocal"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )
    frame = _event_frame()
    index = frame.index[0]
    frame.loc[index, "opponent_final_score"] = 0
    frame.loc[index, "excluded_defensive_td_points"] = 6
    frame.loc[index, "excluded_non_dst_points"] = 6
    frame.loc[index, "pa"] = 0
    with pytest.raises(DstEventFrameError, match="points allowed reconstruction"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )


def test_source_conflicts_unmatched_rows_and_coverage_fail_closed():
    frame = _event_frame()
    index = frame.authoritative_dst_dk_points.first_valid_index()
    frame.loc[index, "authoritative_source_raw_rows"] = 2
    frame.loc[index, "authoritative_source_matched_rows"] = 2
    frame.loc[index, "authoritative_distinct_score_count"] = 2
    frame.loc[index, "authoritative_source_status"] = "source_conflict"
    frame.loc[index, "authoritative_dst_dk_points"] = np.nan
    frame.loc[index, "score_reconciliation_delta"] = np.nan
    frame.loc[index, "score_reconciliation_status"] = "source_conflict"
    frame.loc[index, "dst_dk_points"] = frame.loc[
        index, "reconstructed_dst_dk_points"
    ]
    with pytest.raises(DstEventFrameError, match="unmatched/conflicted"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 1, 2025: 1},
        )
    frame = _event_frame()
    index = frame.authoritative_dst_dk_points.first_valid_index()
    frame.loc[index, "authoritative_source_matched_rows"] = 0
    frame.loc[index, "authoritative_source_rejected_rows"] = 1
    frame.loc[index, "authoritative_distinct_score_count"] = 0
    frame.loc[index, "authoritative_source_status"] = "source_unmatched"
    frame.loc[index, "authoritative_dst_dk_points"] = np.nan
    frame.loc[index, "score_reconciliation_delta"] = np.nan
    frame.loc[index, "score_reconciliation_status"] = "source_unmatched"
    frame.loc[index, "dst_dk_points"] = frame.loc[
        index, "reconstructed_dst_dk_points"
    ]
    with pytest.raises(DstEventFrameError, match="unmatched/conflicted"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 1, 2025: 1},
        )
    frame = _event_frame()
    index = frame.authoritative_dst_dk_points.first_valid_index()
    frame.loc[index, "authoritative_source_raw_rows"] = 2
    frame.loc[index, "authoritative_source_rejected_rows"] = 1
    frame.loc[index, "authoritative_source_status"] = "source_partial_rejection"
    frame.loc[index, "score_reconciliation_status"] = "source_partial_rejection"
    loose = validate_dst_event_frame(
        frame,
        require_reconciled_authoritative_scores=False,
    )
    assert loose["authoritative_source_failures"] == 1
    with pytest.raises(DstEventFrameError, match="unmatched/conflicted/rejected"):
        validate_dst_event_frame(
            frame,
            expected_authoritative_rows_by_season={2024: 2, 2025: 1},
        )
    with pytest.raises(DstEventFrameError, match="coverage contract"):
        validate_dst_event_frame(_event_frame())
    with pytest.raises(DstEventFrameError, match="coverage counts differ"):
        validate_dst_event_frame(
            _event_frame(),
            expected_authoritative_rows_by_season={2024: 1, 2025: 1},
        )


def test_team_defense_sql_exposes_complete_versioned_event_frame():
    sql = (
        Path(__file__).resolve().parents[1]
        / "sql/features/024_team_defense_week.sql"
    ).read_text()
    for fragment in (
        "e.defensive_safeties, e.blocked_kicks, e.return_tds",
        "e.defensive_return_tds, e.defensive_conversions",
        "AS excluded_non_dst_points",
        "AS points_allowed_tier_points",
        "AS reconstructed_dst_dk_points",
        "AS authoritative_dst_dk_points",
        "AS score_reconciliation_status",
        "AS event_vector_sha256",
        "AS dst_event_games_prior_l4",
        "AS dst_event_defensive_conversions_l4",
        "AS dst_event_defensive_conversions_l16",
        "AS event_vector_payload",
        "AS authoritative_source_status",
        "ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING",
        "ROWS BETWEEN 16 PRECEDING AND 1 PRECEDING",
    ):
        assert fragment in sql
    assert "GREATEST(0" not in sql
    assert "AVG(sacks) OVER w4 AS sacks_l4" not in sql
