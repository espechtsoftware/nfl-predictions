from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import ownership_import
from nfl_dfs.inference import prospective_generation_shadow_field_bridge as bridge
from nfl_dfs.inference.generation_exposure import (
    canonical_json_bytes,
    canonical_sha256,
)


LOCK_AT = "2026-09-13T17:00:00+00:00"
CAPTURED_AT = "2026-09-14T04:00:00+00:00"


def _players(roster: int) -> list[tuple[str, str]]:
    return [
        ("QB", f"Quarter {roster}"),
        ("RB", f"Runner {roster} A"),
        ("RB", f"Runner {roster} B"),
        ("WR", f"Wide {roster} A"),
        ("WR", f"Wide {roster} B"),
        ("WR", f"Wide {roster} C"),
        ("TE", f"Tight {roster}"),
        ("FLEX", f"Flex {roster}"),
        ("DST", f"Defense {roster}"),
    ]


def _lineup(players: list[tuple[str, str]]) -> str:
    return " ".join(f"{slot} {name}" for slot, name in players)


def _write_field(path: Path, *, duplicate_top: bool = False) -> tuple[
    dict[str, str], list[list[str]]
]:
    player_rosters = [_players(index) for index in range(4)]
    if duplicate_top:
        player_rosters[1] = player_rosters[0]
    names = sorted({name for roster in player_rosters for _, name in roster})
    player_ids = {name: f"player-{ordinal:02d}" for ordinal, name in enumerate(names)}
    normalized_rosters = [
        sorted(player_ids[name] for _, name in roster) for roster in player_rosters
    ]
    if duplicate_top:
        points = [200.0, 200.0, 180.0, 170.0]
        ranks = [1, 1, 3, 4]
        payouts = [550.0, 550.0, 50.0, 0.0]
    else:
        points = [200.0, 190.0, 180.0, 170.0]
        ranks = [1, 2, 3, 4]
        payouts = [1000.0, 100.0, 50.0, 0.0]
    appearances: dict[str, int] = {name: 0 for name in names}
    for roster in player_rosters:
        for _, name in roster:
            appearances[name] += 1
    row_count = max(4, len(names))
    data: dict[str, list[object | None]] = {
        "Rank": ranks + [None] * (row_count - 4),
        "EntryId": ["0001", "0002", "0003", "0004"] + [None] * (row_count - 4),
        "EntryName": ["alpha", "beta", "gamma", "delta"] + [None] * (row_count - 4),
        "TimeRemaining": ["0"] * 4 + [None] * (row_count - 4),
        "Points": points + [None] * (row_count - 4),
        "Lineup": [_lineup(roster) for roster in player_rosters]
        + [None] * (row_count - 4),
        "Winnings": [f"${value:.2f}" for value in payouts]
        + [None] * (row_count - 4),
        "Player": names + [None] * (row_count - len(names)),
        "Roster Position": ["FLEX"] * len(names)
        + [None] * (row_count - len(names)),
        "%Drafted": [
            f"{appearances[name] * 25:.2f}%" for name in names
        ] + [None] * (row_count - len(names)),
        "FPTS": ["10.0"] * len(names) + [None] * (row_count - len(names)),
    }
    pd.DataFrame(data).to_csv(path, index=False)
    return player_ids, normalized_rosters


def _lineup_id(roster: list[str]) -> str:
    return f"lineup-v1-{canonical_sha256(sorted(roster))}"


def _identity(label: str, payload: object | None = None) -> dict[str, object]:
    if payload is None:
        payload = {"label": label}
    return {
        "uri": f"gs://fixture-postsettlement/{label}.json",
        "generation": "1",
        "sha256": canonical_sha256(payload),
        "bytes": len(canonical_json_bytes(payload)),
    }


def _projection(lineup_ids: list[str]) -> dict[str, object]:
    groups = [{
        "membership_id": "arm:incumbent-160-40:candidate-pool",
        "lineup_count": len(lineup_ids),
        "lineup_ids": lineup_ids,
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
    }, {
        "membership_id": "arm:incumbent-160-40:incumbent-retrieval",
        "lineup_count": 2,
        "lineup_ids": lineup_ids[:2],
        "lineup_ids_sha256": canonical_sha256(lineup_ids[:2]),
    }]
    memberships = [{
        "lineup_id": lineup_id,
        "membership_ids": [groups[0]["membership_id"]]
        + ([groups[1]["membership_id"]] if ordinal < 2 else []),
    } for ordinal, lineup_id in enumerate(sorted(lineup_ids))]
    body: dict[str, object] = {
        "schema_version": bridge.MEMBERSHIP_SCHEMA,
        "season": 2026,
        "week": 1,
        "slate_id": "2026-w01",
        "lock_at": LOCK_AT,
        "terminal_prelock_root_identity": _identity("terminal-root"),
        "terminal_prelock_root_sha256": "a" * 64,
        "membership_groups": groups,
        "membership_groups_sha256": canonical_sha256(groups),
        "lineup_memberships": memberships,
        "lineup_memberships_sha256": canonical_sha256(memberships),
        "required_lineup_count": len(lineup_ids),
    }
    return bridge._self_hashed(body, field="membership_projection_sha256")


def _capture_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    duplicate_top: bool = False,
) -> dict[str, object]:
    source = tmp_path / "contest-standings-12345.csv"
    player_by_name, rosters = _write_field(source, duplicate_top=duplicate_top)
    validated = ownership_import.validate_full_field_capture(
        source, expected_entries=4
    )
    source_raw = source.read_bytes()
    source_uri = "gs://fixture-postsettlement/full-field-source.csv"
    capture_source = {
        "uri": source_uri,
        "generation": "7",
        "sha256": validated["source_sha256"],
        "bytes": validated["source_bytes"],
    }
    captured_ids = [_lineup_id(roster) for roster in rosters]
    # Recombine salary-slate players into one legal-identity roster absent
    # from the captured field. The bridge does not invent an entry for it.
    absent_roster = sorted(rosters[0][1:] + [rosters[2][0]])
    absent_id = _lineup_id(absent_roster)
    frozen_ids = sorted(set([captured_ids[0], captured_ids[2], absent_id]))
    projection = _projection(frozen_ids)
    monkeypatch.setattr(
        bridge, "_project_terminal_prelock_root", lambda value: projection
    )
    capture_manifest = {
        "schema_version": 1,
        "capture_version": "dk-full-field-v1",
        "capture_id": "capture-fixture",
        "status": "applied",
        "evidence_timing": "post_settlement",
        "source": {
            "uri": source_uri,
            "sha256": validated["source_sha256"],
            "bytes": validated["source_bytes"],
            "captured_at": CAPTURED_AT,
        },
        "contest": {
            "season": 2026,
            "week": 1,
            "contest_id": "12345",
            "contest_name": "Millionaire Maker",
            "expected_entries": 4,
            "observed_entries": 4,
            "roster_format": "classic",
        },
        "validation": {
            "operator_confirmed_settled": True,
            "operator_confirmed_full_field": True,
            "operator_confirmed_contest_metadata": True,
            "settled_points_complete": True,
            "entry_ids_unique": True,
            "competition_ranks_reproduced": True,
            "ownership_reproduced_from_entries": True,
        },
    }
    score_by_id = {}
    captured_score = {
        captured_ids[0]: 200_000_000,
        captured_ids[2]: 180_000_000,
    }
    for lineup_id in frozen_ids:
        score_by_id[lineup_id] = captured_score.get(lineup_id, 185_000_000)
    payout_rows = [
        {
            "rank_start": rank,
            "rank_end": rank,
            "payout_micro": payout,
            "award_label": "cash",
        }
        for rank, payout in enumerate(
            [1_000_000_000, 100_000_000, 50_000_000, 0], start=1
        )
    ]
    participant_rows = [{
        "entry_id": entry_id,
        "participant_id": f"participant-{entry_id}",
        "strength_percentile_ppm": ordinal * 100_000,
        "as_of_at": "2026-09-13T16:00:00+00:00",
    } for ordinal, entry_id in enumerate(("0001", "0002", "0003", "0004"), 1)]
    terminal = {"ignored": True}
    score_payload = bridge.build_independent_realized_score_source_payload_v1(
        terminal_prelock_root=terminal,
        captured_at=CAPTURED_AT,
        realized_score_micro_by_lineup_id=score_by_id,
    )
    return {
        "terminal_prelock_root": terminal,
        "captured_at": CAPTURED_AT,
        "realized_score_micro_by_lineup_id": score_by_id,
        "realized_score_source_identity": _identity(
            "independent-realized-scores", score_payload
        ),
        "capture_manifest": capture_manifest,
        "validated_capture": validated,
        "capture_source_identity": capture_source,
        "entry_fee_micro": 20_000_000,
        "payout_table_rows": payout_rows,
        "participant_strength_rows": participant_rows,
        "player_identity_rows": [
            {"display_name": name, "player_id": player_id}
            for name, player_id in player_by_name.items()
        ],
        "captured_ids": captured_ids,
        "absent_id": absent_id,
    }


def _prepare(case: dict[str, object]) -> dict[str, object]:
    return bridge.prepare_contest_field_bridge_v1(**{
        key: value for key, value in case.items()
        if key not in {"captured_ids", "absent_id"}
    })


def _component_identities(preparation: dict[str, object]) -> dict[str, object]:
    return {
        name: _identity(f"component-{name}", payload)
        for name, payload in preparation["component_payloads"].items()
    }


def _refresh_score_identity(case: dict[str, object]) -> None:
    payload = bridge.build_independent_realized_score_source_payload_v1(
        terminal_prelock_root=case["terminal_prelock_root"],
        captured_at=case["captured_at"],
        realized_score_micro_by_lineup_id=case[
            "realized_score_micro_by_lineup_id"
        ],
    )
    case["realized_score_source_identity"] = _identity(
        "independent-realized-scores-refreshed", payload
    )


def test_complete_bridge_binds_field_and_marks_unentered_without_actual_facts(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    preparation = _prepare(case)
    assert preparation["status"] == "ready-for-create-once-component-binding"
    assert preparation["contest_ev_claim_allowed"] is False

    result = bridge.bind_contest_field_bridge_v1(
        preparation=preparation,
        component_identities=_component_identities(preparation),
    )
    assert bridge.validate_contest_field_bridge_v1(result) == result
    assert result["complete_contest_field_capture"] is True
    assert result["complete_field_rank_claim_allowed"] is True
    assert result["contest_ev_claim_allowed"] is False
    assert result["evidence_scope"] == (
        "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
    )
    assert result["allocation_recommendation_allowed"] is False
    by_id = {row["lineup_id"]: row for row in result["evaluator_lineup_rows"]}

    absent = by_id[case["absent_id"]]
    assert absent["entered_in_contest"] is False
    assert absent["matching_entry_ids"] == []
    assert absent["duplicates"] == 0
    assert absent["actual_field_rank"] is None
    assert absent["actual_field_percentile_ppm"] is None
    assert absent["counterfactual_field_rank"] == 3
    assert absent["actual_split_payout_applicable"] is False
    assert absent["split_payout_micro"] == 0

    entered = by_id[case["captured_ids"][0]]
    assert entered["entered_in_contest"] is True
    assert entered["matching_entry_ids"] == ["0001"]
    assert entered["duplicates"] == 1
    assert entered["actual_field_rank"] == 1
    assert entered["actual_field_rank"] == entered["counterfactual_field_rank"]
    assert entered["split_payout_micro"] == 1_000_000_000


def test_duplicate_tie_uses_complete_field_and_actual_split_payout(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch, duplicate_top=True)
    preparation = _prepare(case)
    result = bridge.bind_contest_field_bridge_v1(
        preparation=preparation,
        component_identities=_component_identities(preparation),
    )
    top_id = case["captured_ids"][0]
    row = next(
        value for value in result["evaluator_lineup_rows"]
        if value["lineup_id"] == top_id
    )
    assert row["matching_entry_ids"] == ["0001", "0002"]
    assert row["duplicates"] == 2
    assert row["actual_field_rank"] == 1
    assert row["split_payout_micro"] == 550_000_000


def test_missing_participant_strength_fails_closed_to_raw_score_only(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    case["participant_strength_rows"] = None
    result = _prepare(case)
    assert bridge.validate_contest_field_bridge_v1(result) == result
    assert result["status"] == "raw-score-only-no-contest-ev"
    assert result["contest_ev_claim_allowed"] is False
    assert result["evaluator_contest_field_capture"] is None
    assert result["component_identities"] is None
    assert "participant_strength_missing" in result["deficiencies"]
    assert all(set(row) == {"lineup_id", "realized_score_micro"}
               for row in result["evaluator_lineup_rows"])


def test_unentered_lineup_below_entire_field_has_insertion_rank_n_plus_one(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    case["realized_score_micro_by_lineup_id"][case["absent_id"]] = 100_000_000
    _refresh_score_identity(case)
    preparation = _prepare(case)
    result = bridge.bind_contest_field_bridge_v1(
        preparation=preparation,
        component_identities=_component_identities(preparation),
    )
    absent = next(
        row for row in result["evaluator_lineup_rows"]
        if row["lineup_id"] == case["absent_id"]
    )
    assert absent["counterfactual_field_rank"] == 5
    assert absent["counterfactual_field_percentile_ppm"] == 0
    assert bridge.validate_contest_field_bridge_v1(result) == result


def test_validation_only_capture_or_missing_payout_stays_raw_score_only(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    pending = deepcopy(case)
    pending["capture_manifest"]["status"] = "validated-only"
    pending["capture_manifest"]["evidence_timing"] = (
        "settlement_pending_operator_confirmation"
    )
    pending["capture_manifest"]["validation"][
        "operator_confirmed_full_field"
    ] = False
    result = _prepare(pending)
    assert result["status"] == "raw-score-only-no-contest-ev"
    assert result["deficiencies"] == [
        "full_field_capture_not_applied_or_confirmed"
    ]

    no_payout = deepcopy(case)
    no_payout["validated_capture"]["entries"].loc[0, "payout"] = float("nan")
    result = _prepare(no_payout)
    assert result["status"] == "raw-score-only-no-contest-ev"
    assert result["deficiencies"] == ["actual_split_payout_missing"]


def test_unreconciled_payout_table_downgrades_instead_of_claiming_ev(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    case["validated_capture"] = deepcopy(case["validated_capture"])
    case["validated_capture"]["entries"].loc[0, "payout"] = 999.0
    result = _prepare(case)
    assert result["status"] == "raw-score-only-no-contest-ev"
    assert result["contest_ev_claim_allowed"] is False
    assert result["deficiencies"] == ["split_payout_not_reconciled_at_rank_1"]


def test_capture_identity_or_component_identity_mismatch_fails(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    broken = deepcopy(case)
    broken["capture_source_identity"]["sha256"] = "f" * 64
    with pytest.raises(
        bridge.ProspectiveContestFieldBridgeError,
        match="source identity differs",
    ):
        _prepare(broken)

    preparation = _prepare(case)
    identities = _component_identities(preparation)
    identities["field_rosters"]["bytes"] += 1
    with pytest.raises(
        bridge.ProspectiveContestFieldBridgeError,
        match="does not bind",
    ):
        bridge.bind_contest_field_bridge_v1(
            preparation=preparation, component_identities=identities
        )


def test_realized_score_mutation_without_new_immutable_identity_fails(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    lineup_id = next(iter(case["realized_score_micro_by_lineup_id"]))
    case["realized_score_micro_by_lineup_id"][lineup_id] += 1
    with pytest.raises(
        bridge.ProspectiveContestFieldBridgeError,
        match="realized-score source identity.*does not bind",
    ):
        _prepare(case)

    raw_case = _capture_case(tmp_path, monkeypatch)
    raw_case["participant_strength_rows"] = None
    raw_bridge = _prepare(raw_case)
    raw_bridge["evaluator_lineup_rows"][0]["realized_score_micro"] += 1
    raw_bridge.pop("field_bridge_sha256")
    raw_bridge["field_bridge_sha256"] = canonical_sha256(raw_bridge)
    with pytest.raises(
        bridge.ProspectiveContestFieldBridgeError,
        match="realized-score source identity.*does not bind",
    ):
        bridge.validate_contest_field_bridge_v1(raw_bridge)


def test_score_registry_must_exactly_cover_frozen_memberships(
    tmp_path, monkeypatch
):
    case = _capture_case(tmp_path, monkeypatch)
    case["realized_score_micro_by_lineup_id"].pop(next(iter(
        case["realized_score_micro_by_lineup_id"]
    )))
    with pytest.raises(
        bridge.ProspectiveContestFieldBridgeError,
        match="exactly cover frozen lineups",
    ):
        _prepare(case)
