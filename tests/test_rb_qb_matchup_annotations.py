from __future__ import annotations

from hashlib import sha256

import pytest

from nfl_dfs.research import rb_qb_matchup_annotations as builders
from nfl_dfs.research import receiver_matchup_contract as contract


def _inputs() -> builders.RbQbSlateInputs:
    rb_roles = [
        {"gsis_id": pid, "team": "AAA", "role_label": label,
         "role_consensus_score": score, "role_component_count": 3,
         "role_supported": True}
        for pid, label, score in (
            ("00-0000011", "RB1", 0.9),
            ("00-0000012", "RB2", 0.6),
            ("00-0000013", "RB3+", 0.3),
        )
    ]
    rb_concessions = [
        {"defense": "BBB", "role_label": label,
         "rushing_dk_allowed_per_game_l8": rush,
         "receiving_dk_allowed_per_game_l8": recv,
         "concession_supported": True}
        for label, rush, recv in (
            ("RB1", 15.0, 8.0), ("RB2", 9.0, 5.0), ("RB3+", 4.0, 2.0),
        )
    ]
    defense_context = [{
        "defense": "BBB",
        "rdef_epa_per_attempt_l8": 0.05,
        "rdef_boom_rate_l8": 0.11,
        "run_context_supported": True,
        "pressures_per_game_l8": 12.0,
        "sacks_per_game_l8": 2.5,
        "pass_rush_supported": True,
        "qb_dk_allowed_per_game_l8": 21.0,
        "qb_concession_supported": True,
    }, {
        "defense": "DDD",
        "rdef_epa_per_attempt_l8": -0.10,
        "rdef_boom_rate_l8": 0.07,
        "run_context_supported": True,
        "pressures_per_game_l8": 18.0,
        "sacks_per_game_l8": 3.5,
        "pass_rush_supported": True,
        "qb_dk_allowed_per_game_l8": 14.0,
        "qb_concession_supported": True,
    }]
    secondary = [
        {"team": "BBB", "db_ypt_allowed_l6": 8.4},
        {"team": "DDD", "db_ypt_allowed_l6": 6.1},
    ]
    return builders.RbQbSlateInputs(
        season=2023,
        week=1,
        rb_role_rows=tuple(rb_roles),
        rb_concession_rows=tuple(rb_concessions),
        defense_context_rows=tuple(defense_context),
        secondary_rows=tuple(secondary),
        opponent_by_team={
            "AAA": "BBB", "BBB": "AAA", "CCC": "DDD", "DDD": "CCC",
        },
    )


def _catalog() -> list[dict[str, object]]:
    return [
        {"id": "00-0000011", "pos": "RB", "team": "AAA"},
        {"id": "00-0000012", "pos": "RB", "team": "AAA"},
        {"id": "00-0000013", "pos": "RB", "team": "AAA"},
        {"id": "00-0000014", "pos": "RB", "team": "EEE"},
        {"id": "00-0000021", "pos": "QB", "team": "AAA"},
        {"id": "00-0000022", "pos": "QB", "team": "CCC"},
        {"id": "00-0000031", "pos": "WR", "team": "AAA"},
    ]


def test_rb_components_edge_and_orphan_reasons():
    rows = {
        row["player_id"]: row
        for row in builders.build_rb_matchup_rows(_inputs(), _catalog())
    }
    assert set(rows) == {
        "00-0000011", "00-0000012", "00-0000013", "00-0000014",
    }
    rb1 = rows["00-0000011"]["values"]
    assert rb1["role_label"] == "RB1"
    assert rb1["opponent_rushing_concession_l8"] == pytest.approx(15.0)
    assert rb1["opponent_receiving_concession_l8"] == pytest.approx(8.0)
    assert rb1["opponent_rdef_epa_per_attempt_l8"] == pytest.approx(0.05)
    # Three AAA backs share the run-context value (percentile 0 for all);
    # concession percentiles order RB1 > RB2 > RB3+.
    assert rb1["matchup_component_count"] == 3
    assert rb1["matchup_edge_score"] == pytest.approx((1.0 + 1.0 + 0.0) / 3)
    assert rb1["easy_ground_matchup_v1"] is False
    rb3 = rows["00-0000013"]["values"]
    assert rb3["matchup_edge_score"] == pytest.approx(0.0)
    orphan = rows["00-0000014"]
    assert orphan["values"]["matchup_component_count"] == 0
    assert orphan["missing"]["opponent_rushing_concession_l8"] == (
        "source-absent"
    )
    for row in rows.values():
        for name, value in row["values"].items():
            if value is None:
                assert row["missing"][name] in contract.MISSING_REASON_CODES


def test_qb_components_invert_pressure_orientation():
    rows = {
        row["player_id"]: row
        for row in builders.build_qb_matchup_rows(_inputs(), _catalog())
    }
    assert set(rows) == {"00-0000021", "00-0000022"}
    aaa_qb = rows["00-0000021"]["values"]
    ccc_qb = rows["00-0000022"]["values"]
    # AAA faces BBB: higher concession (21 > 14), FEWER pressures
    # (12 < 18, inverted -> favorable), weaker secondary (8.4 > 6.1):
    # every component percentile 1.0 -> easy pass matchup.
    assert aaa_qb["matchup_edge_score"] == pytest.approx(1.0)
    assert aaa_qb["easy_pass_matchup_v1"] is True
    assert aaa_qb["opponent_pressures_per_game_l8"] == pytest.approx(12.0)
    assert ccc_qb["matchup_edge_score"] == pytest.approx(0.0)
    assert ccc_qb["easy_pass_matchup_v1"] is False


def test_both_families_roundtrip_through_contract():
    for family, build in (
        (builders.rb_matchup_family_v1(), builders.build_rb_matchup_rows),
        (builders.qb_matchup_family_v1(), builders.build_qb_matchup_rows),
    ):
        rows = build(_inputs(), _catalog())
        body = builders.build_family_annotation_object(
            family=family,
            rows=rows,
            task_id="task-0000-2023-w01",
            slate_id="2023-w01",
            lock_time_utc="2023-09-10T17:00:00Z",
            maximum_source_time_utc="2023-09-10T16:00:00Z",
            player_catalog_identity={
                "uri": "gs://fixture/catalog.json",
                "generation": "1",
                "sha256": sha256(b"catalog").hexdigest(),
                "bytes": 7,
            },
            source_identities={
                role: {
                    "uri": f"gs://fixture/{role}.json",
                    "generation": "1",
                    "sha256": "a" * 64,
                    "bytes": 10,
                }
                for role in family.source_roles
            },
            created_at_utc="2026-08-22T20:00:00Z",
        )
        raw = contract.canonical_json_bytes(body)
        validated = contract.validate_annotation_bytes(
            raw, expected_family=family, require_analysis_grade=False
        )
        assert validated["row_count"] == len(rows)
        assert validated["family"]["family_id"] == family.family_id
