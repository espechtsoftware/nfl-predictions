from __future__ import annotations

import pandas as pd
import pytest

from nfl_dfs.optimizer.late_swap import (
    DecisionStage,
    RECOURSE_POLICY_VERSION,
    StageBoundaries,
    build_recourse_state,
    classify_entry_reach,
    entry_rosters_from_csv,
    propose_recourse_rosters,
    validate_information_as_of,
    validate_swap_upload,
)


HEADER = "Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n"


def _catalog() -> pd.DataFrame:
    rows = [
        ("1", "QB A", "QB", 6000, "2026-09-13T13:00:00-05:00"),
        ("2", "QB B", "QB", 5900, "2026-09-13T16:05:00-05:00"),
        ("3", "RB A", "RB", 6000, "2026-09-13T13:00:00-05:00"),
        ("4", "RB B", "RB", 5500, "2026-09-13T16:05:00-05:00"),
        ("5", "RB C", "RB", 5000, "2026-09-13T16:05:00-05:00"),
        ("6", "WR A", "WR", 5000, "2026-09-13T16:05:00-05:00"),
        ("7", "WR B", "WR", 5000, "2026-09-13T16:05:00-05:00"),
        ("8", "WR C", "WR", 5000, "2026-09-13T16:05:00-05:00"),
        ("9", "WR D", "WR", 4900, "2026-09-13T16:05:00-05:00"),
        ("10", "TE A", "TE", 4000, "2026-09-13T16:05:00-05:00"),
        ("11", "DST A", "DST", 3000, "2026-09-13T16:05:00-05:00"),
    ]
    return pd.DataFrame(rows, columns=["dk_id", "name", "pos", "salary", "kickoff"])


def _csv(*, qb="QB A (LOCKED)", wr3="WR C (8)", entry="e1") -> str:
    cells = [
        entry,
        "Milly",
        "900",
        "$20",
        qb,
        "RB A (LOCKED)",
        "RB B (4)",
        "WR A (6)",
        "WR B (7)",
        wr3,
        "TE A (10)",
        "RB C (5)",
        "DST A (11)",
    ]
    return HEADER + ",".join(cells) + "\n"


def test_stage_boundaries_and_locked_state_are_time_aware():
    boundaries = StageBoundaries(
        "2026-09-13T13:00:00-05:00",
        "2026-09-13T16:05:00-05:00",
        "2026-09-13T19:20:00-05:00",
    )
    assert boundaries.decision_stage(
        "2026-09-13T12:30:00-05:00"
    ) is DecisionStage.INITIAL_LOCK
    assert boundaries.decision_stage(
        "2026-09-13T14:00:00-05:00"
    ) is DecisionStage.LATE_AFTERNOON
    assert boundaries.decision_stage(
        "2026-09-13T17:00:00-05:00"
    ) is DecisionStage.SUNDAY_NIGHT
    assert boundaries.decision_stage(
        "2026-09-13T20:00:00-05:00"
    ) is DecisionStage.CLOSED
    state = build_recourse_state(
        _catalog(), boundaries, "2026-09-13T14:00:00-05:00"
    )
    assert state["decision_stage"] == "late_afternoon_recourse"
    assert state["locked_player_ids"] == ["1", "3"]
    assert state["next_player_lock"] == "2026-09-13T21:05:00+00:00"


def test_stage_boundaries_reject_naive_or_unordered_times():
    with pytest.raises(ValueError, match="timezone-aware"):
        StageBoundaries(
            "2026-09-13 13:00", "2026-09-13 16:05"
        ).decision_stage("2026-09-13 12:00")
    with pytest.raises(ValueError, match="strictly ordered"):
        StageBoundaries(
            "2026-09-13T16:05:00-05:00",
            "2026-09-13T13:00:00-05:00",
        ).decision_stage("2026-09-13T12:00:00-05:00")


def test_information_gate_rejects_rows_not_yet_available():
    info = pd.DataFrame({
        "source": ["projection", "inactive"],
        "available_at": [
            "2026-09-13T13:30:00-05:00",
            "2026-09-13T14:01:00-05:00",
        ],
    })
    with pytest.raises(ValueError, match="future rows"):
        validate_information_as_of(info, "2026-09-13T14:00:00-05:00")
    receipt = validate_information_as_of(
        info.iloc[[0]], "2026-09-13T14:00:00-05:00"
    )
    assert receipt["rows"] == 1
    assert receipt["future_rows"] == 0
    with pytest.raises(ValueError, match="timezone-naive"):
        validate_information_as_of(
            pd.DataFrame({"available_at": ["2026-09-13 13:30:00"]}),
            "2026-09-13T14:00:00-05:00",
        )


def test_frozen_reach_probability_bands():
    assert classify_entry_reach({
        "alive": 0.05,
        "marginal": 0.005,
        "dead": 0.0049,
    }) == {
        "alive": "alive",
        "marginal": "marginal",
        "dead": "effectively_dead",
    }
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        classify_entry_reach({"bad": 1.1})


def test_filled_entries_resolve_to_roster_ids():
    rosters = entry_rosters_from_csv(_csv(), _catalog())
    assert rosters == {"e1": ["1", "3", "4", "6", "7", "8", "10", "5", "11"]}


def _recourse_fixture(qb_kickoff="2026-09-13T17:00:00Z"):
    players = []
    for pos, count in (("QB", 3), ("RB", 5), ("WR", 7), ("TE", 3), ("DST", 3)):
        for number in range(1, count + 1):
            players.append({
                "dk_id": f"{pos}{number}",
                "pos": pos,
                "salary": 5_000,
                "kickoff": qb_kickoff if pos == "QB" else "2026-09-13T17:00:00Z",
            })
    catalog = pd.DataFrame(players)
    entries = {
        "E1": ["QB1", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "WR4", "DST1"],
        "E2": ["QB2", "RB3", "RB4", "WR5", "WR6", "WR7", "TE2", "RB5", "DST2"],
    }
    boom = ["QB3", "RB1", "RB3", "WR1", "WR5", "WR6", "TE3", "WR2", "DST3"]
    candidates = [*entries.values(), boom]
    worlds = pd.DataFrame(
        1.0,
        index=range(100),
        columns=catalog.dk_id.astype(str),
    )
    worlds["QB3"] = 250.0
    information = pd.DataFrame(
        columns=["dk_id", "points_to_date", "available_at"]
    )
    return catalog, entries, candidates, worlds, information, boom


def test_recourse_policy_improves_tail_book_without_outcomes():
    catalog, entries, candidates, worlds, information, boom = _recourse_fixture()
    result = propose_recourse_rosters(
        entries,
        candidates,
        catalog,
        worlds,
        information,
        as_of="2026-09-13T16:00:00Z",
        worlds_generated_at="2026-09-13T15:59:00Z",
    )
    assert result["policy_version"] == RECOURSE_POLICY_VERSION
    assert result["changed_entries"] == 1
    assert sorted(boom) in [sorted(roster) for roster in result["assignments"].values()]
    assert result["final_book_objective"] > result["initial_book_objective"]
    assert result["uses_points_to_date"] is True
    assert result["uses_post_decision_outcomes"] is False
    assert result["requires_upload_validation"] is True


def test_recourse_policy_keeps_kickoff_locked_players():
    catalog, entries, candidates, worlds, information, _ = _recourse_fixture(
        qb_kickoff="2026-09-13T15:00:00Z"
    )
    result = propose_recourse_rosters(
        entries,
        candidates,
        catalog,
        worlds,
        information,
        as_of="2026-09-13T16:00:00Z",
        worlds_generated_at="2026-09-13T15:59:00Z",
    )
    assert result["changed_entries"] == 0
    assert result["assignments"] == {
        entry: sorted(roster) for entry, roster in entries.items()
    }


def test_recourse_policy_rejects_future_or_prekick_information():
    catalog, entries, candidates, worlds, information, _ = _recourse_fixture()
    with pytest.raises(ValueError, match="generated after"):
        propose_recourse_rosters(
            entries,
            candidates,
            catalog,
            worlds,
            information,
            as_of="2026-09-13T16:00:00Z",
            worlds_generated_at="2026-09-13T16:01:00Z",
        )

    information = pd.DataFrame([{
        "dk_id": "QB3",
        "points_to_date": 10.0,
        "available_at": "2026-09-13T15:59:00Z",
    }])
    with pytest.raises(ValueError, match="before kickoff"):
        propose_recourse_rosters(
            entries,
            candidates,
            catalog,
            worlds,
            information,
            as_of="2026-09-13T16:00:00Z",
            worlds_generated_at="2026-09-13T15:59:00Z",
        )

    information["final_score"] = 10.0
    with pytest.raises(ValueError, match="forbidden outcome columns"):
        propose_recourse_rosters(
            entries,
            candidates,
            catalog,
            worlds,
            information,
            as_of="2026-09-13T16:00:00Z",
            worlds_generated_at="2026-09-13T15:59:00Z",
        )


def test_swap_upload_validator_accepts_legal_unlocked_change():
    original = _csv()
    filled = _csv(wr3="WR D (9)")
    receipt = validate_swap_upload(
        original,
        filled,
        _catalog(),
        as_of="2026-09-13T14:00:00-05:00",
    )
    assert receipt["valid"] is True
    assert receipt["entries"] == 1
    assert receipt["changed_slots"] == 1
    assert receipt["locked_slots"] == 2
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["maximum_salary"] <= 50_000


def test_swap_upload_validator_rejects_locked_position_and_metadata_changes():
    with pytest.raises(ValueError, match="locked player"):
        validate_swap_upload(
            _csv(),
            _csv(qb="QB B (2)"),
            _catalog(),
            as_of="2026-09-13T14:00:00-05:00",
        )
    with pytest.raises(ValueError, match="illegal WR"):
        validate_swap_upload(
            _csv(),
            _csv(wr3="QB B (2)"),
            _catalog(),
            as_of="2026-09-13T12:00:00-05:00",
        )
    changed_meta = _csv().replace("Milly", "Other", 1)
    with pytest.raises(ValueError, match="changed metadata"):
        validate_swap_upload(
            _csv(),
            changed_meta,
            _catalog(),
            as_of="2026-09-13T12:00:00-05:00",
        )


def test_swap_upload_validator_rejects_duplicate_lineups():
    original = _csv(entry="e1") + _csv(entry="e2").split("\n", 1)[1]
    filled = original
    with pytest.raises(ValueError, match="duplicate lineups"):
        validate_swap_upload(
            original,
            filled,
            _catalog(),
            as_of="2026-09-13T12:00:00-05:00",
        )
