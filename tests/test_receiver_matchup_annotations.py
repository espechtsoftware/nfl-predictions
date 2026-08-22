from __future__ import annotations

from hashlib import sha256

import pytest

from nfl_dfs.research import receiver_matchup_annotations as annotations
from nfl_dfs.research import receiver_matchup_contract as contract


def _inputs() -> annotations.SlateMatchupInputs:
    roles = [
        {"gsis_id": pid, "team": "AAA", "role_label": label,
         "role_consensus_score": score, "role_component_count": 3,
         "role_supported": True}
        for pid, label, score in (
            ("00-0000001", "WR1", 0.9),
            ("00-0000002", "WR2", 0.7),
            ("00-0000003", "WR3+", 0.5),
            ("00-0000004", "TE1", 0.8),
        )
    ]
    concessions = [
        {"defense": "BBB", "role_label": label,
         "receiving_dk_allowed_per_game_l8": value,
         "concession_supported": True}
        for label, value in (
            ("WR1", 4.0), ("WR2", 6.0), ("WR3+", 8.0), ("TE1", 10.0),
        )
    ]
    defenders = [
        {"defense": "BBB", "alignment": "wide",
         "defender_exposure_weight": 0.5,
         "dk_per_target_allowed_shrunk_l8": 2.0,
         "workload_rank": rank, "defender_supported": True}
        for rank in (1, 2)
    ] + [
        {"defense": "BBB", "alignment": "slot",
         "defender_exposure_weight": 1.0,
         "dk_per_target_allowed_shrunk_l8": 1.0,
         "workload_rank": 1, "defender_supported": True},
    ]
    alignments = [
        {"gsis_id": pid, "player_wide_share": share,
         "alignment_supported": True}
        for pid, share in (
            ("00-0000001", 0.0), ("00-0000002", 0.25),
            ("00-0000003", 0.75), ("00-0000004", 1.0),
        )
    ]
    shell_receivers = [
        {"gsis_id": pid, "man_fprr": man, "zone_fprr": 0.30}
        for pid, man in (
            ("00-0000001", 0.32), ("00-0000002", 0.36),
            ("00-0000003", 0.40), ("00-0000004", 0.44),
        )
    ]
    shell_defenses = [
        {"team": "BBB", "def_man_rate": 0.6},
        {"team": "DDD", "def_man_rate": 0.4},
    ]
    return annotations.SlateMatchupInputs(
        season=2023,
        week=1,
        role_rows=tuple(roles),
        concession_rows=tuple(concessions),
        defender_rows=tuple(defenders),
        alignment_rows=tuple(alignments),
        shell_receiver_rows=tuple(shell_receivers),
        shell_defense_rows=tuple(shell_defenses),
        opponent_by_team={"AAA": "BBB", "BBB": "AAA"},
    )


def _catalog() -> list[dict[str, object]]:
    players = [
        {"id": f"00-000000{index}", "pos": "WR" if index < 4 else "TE",
         "team": "AAA"}
        for index in (1, 2, 3, 4)
    ]
    players.append({"id": "00-0000005", "pos": "WR", "team": "CCC"})
    players.append({"id": "00-0000009", "pos": "QB", "team": "AAA"})
    return players


def test_percentiles_match_percent_rank_convention():
    values = {"a": 1.0, "b": 2.0, "c": 2.0, "d": 4.0}
    result = annotations._percentiles(values)
    assert result == {"a": 0.0, "b": 1 / 3, "c": 1 / 3, "d": 1.0}
    assert annotations._percentiles({"only": 5.0}) == {"only": 0.0}
    assert annotations._percentiles({}) == {}


def test_component_laws_and_easy_coverage_thresholds():
    rows = {
        row["player_id"]: row
        for row in annotations.build_matchup_rows(_inputs(), _catalog())
    }
    assert set(rows) == {
        "00-0000001", "00-0000002", "00-0000003", "00-0000004",
        "00-0000005",
    }
    first = rows["00-0000001"]["values"]
    fourth = rows["00-0000004"]["values"]
    third = rows["00-0000003"]["values"]
    assert first["matchup_component_count"] == 4
    assert first["matchup_edge_score"] == pytest.approx(0.0)
    assert first["easy_coverage_v1"] is False
    # Component percentiles for the top receiver: concession 1.0,
    # alignment 1.0, top-defender 2/3 (tied wide pair), shell 1.0.
    assert fourth["matchup_edge_score"] == pytest.approx(11 / 12)
    assert fourth["easy_coverage_v1"] is True
    assert third["matchup_edge_score"] == pytest.approx(2 / 3)
    assert third["easy_coverage_v1"] is False
    assert fourth["opponent_role_concession_l8"] == pytest.approx(10.0)
    assert fourth["defense_wide_vulnerability_l8"] == pytest.approx(2.0)
    assert fourth["defense_slot_vulnerability_l8"] == pytest.approx(1.0)
    assert fourth["defender_workload_quality_l8"] == pytest.approx(2.0)
    assert fourth["defender_evidence_grain"] == "sis-defender-alignment"
    assert fourth["wide_route_share_l4"] == pytest.approx(1.0)
    assert fourth["slot_route_share_l4"] == pytest.approx(0.0)

    orphan = rows["00-0000005"]
    assert orphan["values"]["matchup_edge_score"] is None
    assert orphan["values"]["easy_coverage_v1"] is None
    assert orphan["values"]["matchup_component_count"] == 0
    assert orphan["missing"]["matchup_edge_score"] == (
        "below-support-threshold"
    )
    assert orphan["missing"]["opponent_role_concession_l8"] == (
        "source-absent"
    )
    for row in rows.values():
        for name, value in row["values"].items():
            if value is None:
                assert row["missing"][name] in contract.MISSING_REASON_CODES


def test_slate_annotation_object_roundtrips_through_contract(tmp_path):
    family = annotations.receiver_matchup_family_v1()
    body = annotations.build_slate_annotation_object(
        inputs=_inputs(),
        catalog_players=_catalog(),
        task_id="task-0000-2023-w01",
        slate_id="2023-w01",
        lock_time_utc="2023-09-10T17:00:00Z",
        maximum_source_time_utc="2023-09-10T13:00:00Z",
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
        created_at_utc="2026-08-22T19:00:00Z",
    )
    raw = contract.canonical_json_bytes(body)
    validated = contract.validate_annotation_bytes(
        raw,
        expected_family=family,
        require_analysis_grade=False,
    )
    assert validated["row_count"] == 5
    assert validated["analysis_grade"] is False
    assert validated["slate_id"] == "2023-w01"


def test_duplicate_catalog_receiver_fails_closed():
    catalog = _catalog() + [{"id": "00-0000001", "pos": "WR", "team": "AAA"}]
    with pytest.raises(
        annotations.ReceiverMatchupAnnotationError, match="repeats receiver"
    ):
        annotations.build_matchup_rows(_inputs(), catalog)
