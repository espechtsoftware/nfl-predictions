from pathlib import Path

import pytest

from nfl_dfs.models.dst_scoring import (
    DST_COMPONENTS,
    DST_SCORING_LAW,
    DST_SCORING_LAW_ID,
    points_allowed_points,
    score_dst_components,
)


ROOT = Path(__file__).resolve().parents[1]


def test_versioned_manifest_freezes_current_official_classic_dst_law():
    manifest = DST_SCORING_LAW.manifest()
    assert DST_SCORING_LAW_ID == "draftkings-nfl-classic-dst-2026-08-17-v1"
    assert manifest["product"] == "DraftKings NFL Classic"
    assert manifest["game_type_id"] == 1
    assert manifest["event_points"] == {
        "sacks": 1.0,
        "interceptions": 2.0,
        "fumble_recoveries": 2.0,
        "safeties": 2.0,
        "blocked_kicks": 2.0,
        "return_tds": 6.0,
        "defensive_conversions": 2.0,
    }
    assert manifest["points_allowed_tiers"] == [
        {"maximum": 0, "points": 10.0},
        {"maximum": 6, "points": 7.0},
        {"maximum": 13, "points": 4.0},
        {"maximum": 20, "points": 1.0},
        {"maximum": 27, "points": 0.0},
        {"maximum": 34, "points": -1.0},
        {"maximum": None, "points": -4.0},
    ]
    assert manifest["reciprocal_defensive_conversion_return_counts_as_pa"] is True
    assert manifest["yards_allowed_fantasy_component_present"] is False
    assert manifest["sources"][0]["content_sha256"] == (
        "fb0ac704f9bbc5d8fd96727280ad8ef7760b1a9d2456474dd760904543d7bbe5"
    )


@pytest.mark.parametrize(
    ("points_allowed", "fantasy_points"),
    [
        (0, 10.0),
        (1, 7.0),
        (6, 7.0),
        (7, 4.0),
        (13, 4.0),
        (14, 1.0),
        (20, 1.0),
        (21, 0.0),
        (27, 0.0),
        (28, -1.0),
        (34, -1.0),
        (35, -4.0),
    ],
)
def test_points_allowed_tier_boundaries(points_allowed, fantasy_points):
    assert points_allowed_points(points_allowed) == fantasy_points


def test_canonical_scorer_requires_exact_event_vector_and_no_yards_component():
    components = dict.fromkeys(DST_COMPONENTS, 0.0)
    components.update({
        "sacks": 3,
        "interceptions": 1,
        "fumble_recoveries": 1,
        "safeties": 1,
        "blocked_kicks": 1,
        "return_tds": 1,
        "defensive_conversions": 1,
    })
    assert score_dst_components(components, points_allowed=14) == 20.0

    with pytest.raises(ValueError, match="extra=\\['yards_allowed'\\]"):
        score_dst_components(
            {**components, "yards_allowed": 199},
            points_allowed=14,
        )


def test_warehouse_sql_is_pinned_to_the_same_scoring_contract():
    sql = (ROOT / "sql/features/024_team_defense_week.sql").read_text()
    assert f"Scoring-law contract: {DST_SCORING_LAW_ID}" in sql
    assert "e.sacks * 1 + e.interceptions * 2 + e.fumble_recoveries * 2" in sql
    assert "+ e.safeties * 2 + e.blocked_kicks * 2 + e.return_tds * 6" in sql
    assert "+ e.defensive_conversions * 2" in sql
    for fragment in (
        "WHEN p.pa = 0 THEN 10",
        "WHEN p.pa <= 6 THEN 7",
        "WHEN p.pa <= 13 THEN 4",
        "WHEN p.pa <= 20 THEN 1",
        "WHEN p.pa <= 27 THEN 0",
        "WHEN p.pa <= 34 THEN -1",
        "ELSE -4",
    ):
        assert fragment in sql
    assert "yards_allowed" not in sql.lower()

    not_allowed_cte = sql.split(
        "offense_points_not_allowed_raw AS (", 1,
    )[1].split("offense_points_not_allowed AS (", 1)[0]
    # Current DK rules charge a conversion return to the reciprocal DST's PA,
    # so it must not be removed with points surrendered by the offense.
    assert "defensive_two_point_conv" not in not_allowed_cte
