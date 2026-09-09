from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_draftkings_lineups_api_capture as subject

LOCATOR = (
    "https://api.draftkings.com/lineups/v1/users/"
    "11111111-2222-4333-8444-555555555555/lineups?"
    "embed=x&format=json&includeBestBall=false&includeNFT=false&includeSnakeDraft=false"
)


def _fixture() -> dict[str, object]:
    lineup_key = "1000000001"
    entries = []
    ordinal = 0
    for pin in capture.A5_ROLE_TABLE.values():
        for _ in range(pin.planned_entries):
            ordinal += 1
            entries.append(
                {
                    "contestEntryKey": str(2_000_000_000 + ordinal),
                    "contestKey": pin.contest_id,
                    "entryName": "",
                    "lineupKey": lineup_key,
                }
            )
    salaries = [7000, 6000, 5500, 6200, 5800, 5000, 4500, 4900, 4800]
    players = []
    for ordinal, (slot, salary) in enumerate(
        zip(capture.CLASSIC_SLOTS, salaries, strict=True), start=1
    ):
        position = slot if slot != "FLEX" else "RB"
        players.append(
            {
                "DefaultPMR": 60,
                "ExternalRequirements": {},
                "FPPG": 10.0 + ordinal,
                "competitionIds": [str(9000 + ordinal)],
                "displayName": f"Player {ordinal}",
                "draftableId": 100 + ordinal,
                "firstName": "Player",
                "gameKey": str(3000 + ordinal),
                "injury": "",
                "lastName": str(ordinal),
                "playerDkId": 200 + ordinal,
                "playerId": 300 + ordinal,
                "positionId": 400 + ordinal,
                "positionName": position,
                "rosterPositionName": slot,
                "rosterSlotId": 500 + ordinal,
                "salary": salary,
                "shortName": f"P{ordinal}",
                "teamId": 600 + ordinal,
            }
        )
    salary_spent = sum(salaries)
    return {
        "bestBallStartingGameTypes": [],
        "errorStatus": {},
        "gameTypes": [
            {
                "description": "Create an NFL Classic lineup",
                "draftType": "SalaryCap",
                "gameStyle": {
                    "abbreviation": "CLA",
                    "description": "Classic",
                    "gameStyleId": 1,
                    "isEnabled": True,
                    "name": "Classic",
                    "sortOrder": 1,
                    "sportId": 1,
                },
                "gameTypeId": 1,
                "name": "Classic",
                "sportId": 1,
                "tag": "",
            }
        ],
        "lineups": [
            {
                "CreateDate": "2026-09-09T12:00:00Z",
                "contestEntries": 90,
                "contestStartDate": "2026-09-13T17:00:00.0000000Z",
                "contestTypeId": 21,
                "draftGroupId": 151307,
                "draftedPlayers": players,
                "entries": entries,
                "gameTypeId": 1,
                "lineupComparisonValue": "private",
                "lineupKey": lineup_key,
                "salaryCap": 50_000,
                "salaryRemaining": 50_000 - salary_spent,
                "sport": "NFL",
                "status": "Upcoming",
            }
        ],
        "responseStatus": {},
    }


def _raw(value: object | None = None) -> bytes:
    return json.dumps(_fixture() if value is None else value, separators=(",", ":")).encode()


def test_honest_capture_proves_the_exact_90_entry_allocation_without_values() -> None:
    receipt = subject.build_receipt(
        _raw(), captured_at_utc="2026-09-09T21:37:15Z", locator=LOCATOR
    )
    facts = receipt["facts"]
    assert facts["draft_group_id"] == "151307"
    assert facts["entry_count"] == facts["unique_entry_count"] == 90
    assert facts["role_entry_counts"] == {
        role: pin.planned_entries for role, pin in capture.A5_ROLE_TABLE.items()
    }
    assert facts["drafted_player_count"] == facts["unique_draftable_count"] == 9
    assert receipt["standings_or_outcome_opened"] is False
    encoded = subject.canonical(receipt)
    for private_value in (
        "11111111-2222-4333-8444-555555555555",
        "2000000001",
        "1000000001",
        "Player 1",
    ):
        assert private_value.encode() not in encoded


def test_provider_dst_empty_last_name_is_the_only_admitted_empty_last_name() -> None:
    value = _fixture()
    value["lineups"][0]["draftedPlayers"][-1]["lastName"] = ""
    assert subject.inspect_lineups(_raw(value))["drafted_player_count"] == 9
    value["lineups"][0]["draftedPlayers"][0]["lastName"] = ""
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match="only a DST"):
        subject.inspect_lineups(_raw(value))


@pytest.mark.parametrize(
    ("mutate", "token"),
    [
        (lambda v: v.__setitem__("scores", []), "fields differ"),
        (lambda v: v["lineups"][0].__setitem__("draftGroupId", 1), "identity"),
        (lambda v: v["lineups"][0].__setitem__("status", "Complete"), "identity"),
        (lambda v: v["lineups"][0]["entries"].pop(), "entry count"),
        (
            lambda v: v["lineups"][0]["entries"][0].__setitem__(
                "contestEntryKey", v["lineups"][0]["entries"][1]["contestEntryKey"]
            ),
            "repeats an entry key",
        ),
        (
            lambda v: v["lineups"][0]["entries"][0].__setitem__(
                "contestKey", "999999999"
            ),
            "allocation differs",
        ),
        (
            lambda v: v["lineups"][0]["draftedPlayers"][1].__setitem__(
                "draftableId", v["lineups"][0]["draftedPlayers"][0]["draftableId"]
            ),
            "repeats a draftable",
        ),
        (
            lambda v: v["lineups"][0]["draftedPlayers"][0].__setitem__(
                "rosterPositionName", "WR"
            ),
            "slot order differs",
        ),
        (
            lambda v: v["lineups"][0].__setitem__("salaryRemaining", 0),
            "salary does not reconcile",
        ),
    ],
)
def test_identity_allocation_entry_roster_and_salary_mutations_refuse(mutate, token) -> None:
    value = _fixture()
    mutate(value)
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match=token):
        subject.inspect_lineups(_raw(value))


@pytest.mark.parametrize(
    "locator",
    [
        LOCATOR.replace("api.draftkings.com", "example.com"),
        LOCATOR.replace("/lineups?", "/scores?"),
        LOCATOR + "&token=secret",
        LOCATOR.replace("11111111-2222-4333-8444-555555555555", "not-a-guid"),
    ],
)
def test_locator_neighbours_and_extra_query_capabilities_refuse(locator: str) -> None:
    with pytest.raises(subject.DraftKingsLineupsCaptureError):
        subject.admit_locator(locator)


def test_duplicate_and_nonfinite_json_refuse() -> None:
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match="duplicate"):
        subject.parse_strict(b'{"lineups":[],"lineups":[]}')
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match="non-finite"):
        subject.parse_strict(b'{"lineups":NaN}')


def test_wrong_collector_and_postlock_capture_refuse() -> None:
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match="collector differs"):
        subject.build_receipt(
            _raw(),
            captured_at_utc="2026-09-09T21:37:15Z",
            locator=LOCATOR,
            collector_sha256="0" * 64,
        )
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match="not pre-lock"):
        subject.build_receipt(
            _raw(), captured_at_utc="2026-09-13T17:00:00Z", locator=LOCATOR
        )


def _reservation_inputs(monkeypatch) -> tuple[bytes, bytes, bytes]:
    raw = _raw()
    receipt_raw = subject.canonical(
        subject.build_receipt(
            raw, captured_at_utc="2026-09-09T21:37:15Z", locator=LOCATOR
        )
    )
    publication = {
        "bucket": "nfl-predictions-503414-raw",
        "draft_group_id": "151307",
        "objects": {
            "capture_receipt": {
                "bytes": len(receipt_raw),
                "created_at_utc": "2026-09-09T22:20:13Z",
                "generation": subject.RECEIPT_OBJECT_GENERATION,
                "name": subject.RECEIPT_OBJECT_NAME,
                "postpublication_all_generation_census": {
                    "live": 1,
                    "noncurrent": 0,
                    "soft_deleted": 0,
                },
                "prepublication_all_generation_census": {"total": 0},
                "sha256": subject.CAPTURE_RECEIPT_FILE_SHA256,
            },
            "private_raw_response": {
                "bytes": len(raw),
                "created_at_utc": "2026-09-09T22:20:12Z",
                "generation": subject.RAW_OBJECT_GENERATION,
                "name": subject.RAW_OBJECT_NAME,
                "postpublication_all_generation_census": {
                    "live": 1,
                    "noncurrent": 0,
                    "soft_deleted": 0,
                },
                "prepublication_all_generation_census": {"total": 0},
                "sha256": subject.RAW_RESPONSE_SHA256,
            },
        },
        "outcome_or_standings_authority": False,
        "publication_completed_at_utc": "2026-09-09T22:20:13Z",
        "publication_mode": "create-once-if-generation-match-zero",
        "schema_version": "week1-draftkings-lineups-api-publication/v1",
        "season": 2026,
        "week": 1,
    }
    publication_raw = json.dumps(publication, indent=2, sort_keys=True).encode() + b"\n"
    monkeypatch.setattr(subject, "RAW_RESPONSE_BYTES", len(raw))
    monkeypatch.setattr(subject, "RAW_RESPONSE_SHA256", subject.hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(subject, "CAPTURE_RECEIPT_BYTES", len(receipt_raw))
    monkeypatch.setattr(
        subject,
        "CAPTURE_RECEIPT_FILE_SHA256",
        subject.hashlib.sha256(receipt_raw).hexdigest(),
    )
    publication["objects"]["capture_receipt"]["sha256"] = (
        subject.CAPTURE_RECEIPT_FILE_SHA256
    )
    publication["objects"]["private_raw_response"]["sha256"] = (
        subject.RAW_RESPONSE_SHA256
    )
    publication_raw = json.dumps(publication, indent=2, sort_keys=True).encode() + b"\n"
    monkeypatch.setattr(subject, "PUBLICATION_RECORD_BYTES", len(publication_raw))
    monkeypatch.setattr(
        subject,
        "PUBLICATION_RECORD_FILE_SHA256",
        subject.hashlib.sha256(publication_raw).hexdigest(),
    )
    return raw, receipt_raw, publication_raw


def test_api_bridge_proves_reservations_but_not_final_a5_roster_acceptance(
    monkeypatch,
) -> None:
    raw, receipt_raw, publication_raw = _reservation_inputs(monkeypatch)
    bridge = subject.build_a5_reservation_bridge(
        raw,
        capture_receipt_raw=receipt_raw,
        publication_record_raw=publication_raw,
    )
    projection = bridge["a5_projection"]
    assert projection["entry_count"] == projection["unique_entry_count"] == 90
    assert projection["reservation_and_contest_allocation_authority"] is True
    assert projection["final_entry_roster_acceptance_authority"] is False
    assert projection["prepared_filled_book_lineage_present"] is False
    assert bridge["standings_or_outcome_opened"] is False
    encoded = subject.canonical(bridge)
    for private_value in (
        "11111111-2222-4333-8444-555555555555",
        "2000000001",
        "1000000001",
        "Player 1",
    ):
        assert private_value.encode() not in encoded


@pytest.mark.parametrize("target", ["raw", "receipt", "publication"])
def test_api_bridge_refuses_any_unpinned_source_bytes(monkeypatch, target: str) -> None:
    raw, receipt_raw, publication_raw = _reservation_inputs(monkeypatch)
    values = {
        "raw": raw + b" ",
        "receipt": receipt_raw + b" ",
        "publication": publication_raw + b" ",
    }
    with pytest.raises(subject.DraftKingsLineupsCaptureError, match="identity differs"):
        subject.build_a5_reservation_bridge(
            values.get("raw", raw) if target == "raw" else raw,
            capture_receipt_raw=(
                values["receipt"] if target == "receipt" else receipt_raw
            ),
            publication_record_raw=(
                values["publication"] if target == "publication" else publication_raw
            ),
        )


def test_tracked_api_to_a5_bridge_is_redacted_and_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = (
        root
        / "reports/2026-09-09-week1-draftkings-lineups-api-a5-reservation.json"
    ).read_bytes()
    bridge = subject.validate_a5_reservation_bridge(subject.parse_strict(raw))
    assert bridge["a5_projection"]["final_entry_roster_acceptance_authority"] is False
    assert bridge["credentials_or_private_values_retained"] is False
