"""Contract tests for the versioned paid Classic export boundary."""

from __future__ import annotations

import csv
import hashlib
import io
from copy import deepcopy

import pandas as pd
import pytest
from fastapi import HTTPException

from nfl_dfs.app import main as app_main
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.optimizer.paid_classic_book_v2 import (
    PAID_CLASSIC_CATALOG_MAX_AGE,
    PAID_CLASSIC_BOUNDARY_ID,
    assert_exact_unique_classic_book_v2,
    assert_paid_candidate_supply_v2,
    build_paid_classic_catalog_v2,
    fill_paid_entries_csv_v2,
    paid_entry_count_v2,
    to_paid_dk_csv_v2,
    validate_paid_classic_book_v2,
)

_PULLED_AT = pd.Timestamp("2026-09-01T15:00:00Z")
_VALIDATED_AT = pd.Timestamp("2026-09-01T16:00:00Z")


@pytest.fixture(autouse=True)
def _fixed_paid_server_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app_main, "_paid_classic_now_v2", lambda: _VALIDATED_AT.to_pydatetime()
    )


def _salary_rows() -> pd.DataFrame:
    specs = [
        (101, "QB", "A", 7000),
        (102, "QB", "B", 7000),
        (201, "RB", "A", 6500),
        (202, "RB", "B", 6000),
        (203, "RB", "C", 5000),
        (301, "WR", "A", 6000),
        (302, "WR", "B", 5500),
        (303, "WR", "C", 5000),
        (304, "WR", "D", 4500),
        (401, "TE", "B", 4000),
        (402, "TE", "D", 3500),
        (501, "DST", "C", 3000),
        (502, "DST", "D", 3000),
    ]
    return pd.DataFrame(
        [
            {
                "pulled_at": _PULLED_AT,
                "draft_group_id": 9001,
                "dk_player_id": player_id,
                "dk_draftable_id": player_id + 50_000_000,
                "display_name": f"Player {player_id}",
                "team_abbr": team,
                "position": position,
                "salary": salary,
                "status": "",
            }
            for player_id, position, team, salary in specs
        ]
    )


def _catalog(rows: pd.DataFrame | None = None):
    return build_paid_classic_catalog_v2(
        _salary_rows() if rows is None else rows,
        draft_group_id=9001,
        validated_at=_VALIDATED_AT,
    )


def _lineup(ids: list[int], rows: pd.DataFrame | None = None) -> Lineup:
    rows = _salary_rows() if rows is None else rows
    by_id = rows.set_index("dk_player_id").to_dict("index")
    players = []
    for player_id in ids:
        row = by_id[player_id]
        players.append(
            {
                "id": player_id,
                "dk_id": int(row["dk_draftable_id"]),
                "name": row["display_name"],
                "pos": row["position"],
                "team": row["team_abbr"],
                "salary": int(row["salary"]),
                "proj": 10.0,
            }
        )
    return Lineup(players=players)


def _book(rows: pd.DataFrame | None = None) -> list[Lineup]:
    rows = _salary_rows() if rows is None else rows
    return [
        _lineup([101, 201, 202, 301, 302, 303, 401, 304, 501], rows),
        _lineup([102, 201, 203, 301, 302, 304, 402, 303, 502], rows),
    ]


def _ranked(book: list[Lineup]) -> list[dict]:
    return [
        {
            "lineup": lineup,
            "confidence": 1.0,
            "proj_mean": round(lineup.proj, 1),
        }
        for lineup in book
    ]


def _entries(*, locked: bool = False) -> str:
    first = "Old QB (LOCKED)" if locked else ""
    return (
        "Entry ID,Contest Name,Contest ID,Entry Fee,"
        "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
        f"1,Milly,77,$20,{first},,,,,,,,,,Keep this\n"
        "2,Milly,77,$20\n"
    )


def test_paid_upload_is_exact_unique_legal_and_receipted() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    book = _book(rows)

    exported = to_paid_dk_csv_v2(book, expected_entries=2, catalog=catalog)

    reopened = list(csv.reader(io.StringIO(exported.csv_text)))
    assert len(reopened) == 3
    assert reopened[0] == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(set(reopened[1])) == 9
    assert len(set(reopened[2])) == 9
    assert reopened[1] != reopened[2]
    receipt = exported.receipt
    assert receipt["boundary_id"] == PAID_CLASSIC_BOUNDARY_ID
    assert receipt["expected_entries"] == 2
    assert receipt["actual_entries"] == 2
    assert receipt["unique_rosters"] == 2
    assert receipt["draftkings_legal"] is True
    assert receipt["active_eligible"] is True
    assert receipt["salary_catalog_pulled_at"] == _PULLED_AT.isoformat()
    assert receipt["salary_catalog_validated_at"] == _VALIDATED_AT.isoformat()
    assert receipt["salary_catalog_age_seconds"] == 3600.0
    assert receipt["salary_catalog_max_age_seconds"] == 7200
    assert receipt["salary_catalog_fresh"] is True
    assert len(receipt["salary_catalog_sha256"]) == 64
    assert len(receipt["csv_sha256"]) == 64


def test_paid_catalog_accepts_the_documented_two_hour_boundary() -> None:
    assert PAID_CLASSIC_CATALOG_MAX_AGE.total_seconds() == 7200
    validated_at = _PULLED_AT + pd.Timedelta(hours=2)
    catalog = build_paid_classic_catalog_v2(
        _salary_rows(), draft_group_id=9001, validated_at=validated_at
    )
    assert catalog.age_seconds == 7200.0
    assert catalog.max_age_seconds == 7200


def test_paid_catalog_rejects_stale_future_naive_and_mixed_pulls() -> None:
    rows = _salary_rows()
    with pytest.raises(ValueError, match="catalog is stale"):
        build_paid_classic_catalog_v2(
            rows,
            draft_group_id=9001,
            validated_at=_PULLED_AT + pd.Timedelta(hours=2, seconds=1),
        )
    with pytest.raises(ValueError, match="is in the future"):
        build_paid_classic_catalog_v2(
            rows,
            draft_group_id=9001,
            validated_at=_PULLED_AT - pd.Timedelta(seconds=1),
        )

    naive = rows.copy()
    naive["pulled_at"] = _PULLED_AT.tz_localize(None)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_paid_classic_catalog_v2(
            naive, draft_group_id=9001, validated_at=_VALIDATED_AT
        )

    mixed = rows.copy()
    mixed.loc[mixed.index[-1], "pulled_at"] = _PULLED_AT + pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match="mixes multiple pulled_at"):
        build_paid_classic_catalog_v2(
            mixed, draft_group_id=9001, validated_at=_VALIDATED_AT
        )


def test_terminal_and_candidate_counts_fail_closed() -> None:
    book = _book()
    with pytest.raises(ValueError, match="candidate supply is short"):
        assert_paid_candidate_supply_v2(
            available_candidates=1, requested_entries=2
        )
    with pytest.raises(ValueError, match="book is short"):
        assert_exact_unique_classic_book_v2(book[:1], expected_entries=2)
    with pytest.raises(ValueError, match="duplicate canonical rosters"):
        assert_exact_unique_classic_book_v2(
            [book[0], deepcopy(book[0])], expected_entries=2
        )


@pytest.mark.parametrize("inactive", ["O", "OUT", "IR", "out"])
def test_current_inactive_player_is_rejected(inactive: str) -> None:
    rows = _salary_rows()
    rows.loc[rows.dk_player_id == 101, "status"] = inactive
    catalog = _catalog(rows)
    with pytest.raises(ValueError, match="contains inactive player"):
        validate_paid_classic_book_v2(
            _book(rows), expected_entries=2, catalog=catalog
        )


def test_stale_draftable_id_and_catalog_drift_are_rejected() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    book = _book(rows)
    book[0].players[0]["dk_id"] += 1
    with pytest.raises(ValueError, match="stale draftable ID"):
        validate_paid_classic_book_v2(book, expected_entries=2, catalog=catalog)

    book = _book(rows)
    book[0].players[0]["salary"] += 100
    with pytest.raises(ValueError, match="current salary catalog"):
        validate_paid_classic_book_v2(book, expected_entries=2, catalog=catalog)


def test_complete_draftkings_legality_is_reopened() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    invalid_shape = _lineup(
        [101, 102, 201, 202, 301, 302, 401, 304, 501], rows
    )
    with pytest.raises(ValueError, match="Classic positions"):
        validate_paid_classic_book_v2(
            [invalid_shape], expected_entries=1, catalog=catalog
        )

    expensive = rows.copy()
    expensive.loc[expensive.dk_player_id == 101, "salary"] = 10_000
    expensive_catalog = _catalog(expensive)
    with pytest.raises(ValueError, match="salary cap"):
        validate_paid_classic_book_v2(
            [_lineup([101, 201, 202, 301, 302, 303, 401, 304, 501], expensive)],
            expected_entries=1,
            catalog=expensive_catalog,
        )


def test_catalog_refuses_duplicate_or_missing_upload_identity() -> None:
    rows = _salary_rows()
    duplicated = pd.concat([rows, rows.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate stable player IDs"):
        _catalog(duplicated)

    missing = rows.copy()
    missing.loc[0, "dk_draftable_id"] = None
    with pytest.raises(ValueError, match="dk_draftable_id must be an integer"):
        _catalog(missing)


def test_paid_entry_fill_never_cycles_a_short_book() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    with pytest.raises(ValueError, match="book is short"):
        fill_paid_entries_csv_v2(
            _entries(), _book(rows)[:1], catalog=catalog, contest_id="77"
        )


def test_paid_entry_fill_reopens_exact_output_book() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    exported = fill_paid_entries_csv_v2(
        _entries(), _book(rows), catalog=catalog, contest_id="77"
    )
    reopened = list(csv.reader(io.StringIO(exported.csv_text)))
    assert reopened[1][0] == "1"
    assert reopened[2][0] == "2"
    assert reopened[1][4:13] != reopened[2][4:13]
    assert all(cell.endswith(")") for cell in reopened[1][4:13])
    assert all(cell.endswith(")") for cell in reopened[2][4:13])
    assert exported.receipt["targeted_entries"] == 2
    assert exported.receipt["contest_id"] == "77"
    assert len(exported.receipt["entry_id_order_sha256"]) == 64


def test_paid_entry_capture_is_exact_and_csv_identical() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    book = _book(rows)
    ordinary = fill_paid_entries_csv_v2(
        _entries(), book, catalog=catalog, contest_id="77"
    )
    events = []
    traced = fill_paid_entries_csv_v2(
        _entries(),
        book,
        catalog=catalog,
        contest_id="77",
        prepared_entry_capture=events.append,
    )

    assert traced.csv_text.encode() == ordinary.csv_text.encode()
    assert traced.receipt == ordinary.receipt
    assert len(events) == 1
    event = events[0]
    assert event["csv_sha256"] == traced.receipt["csv_sha256"]
    assert event["paid_export_receipt_sha256"] == traced.receipt[
        "export_receipt_sha256"
    ]
    assert [row["export_ordinal"] for row in event["entries"]] == [0, 1]
    assert sorted(
        row["paid_input_book_ordinal"] for row in event["entries"]
    ) == [0, 1]
    assert [row["entry_id"] for row in event["entries"]] == ["1", "2"]
    assert all(len(row["internal_player_ids"]) == 9
               for row in event["entries"])
    assert all(len(row["slot_dk_draftable_ids"]) == 9
               for row in event["entries"])


def test_paid_entry_target_requires_an_explicit_unambiguous_contest() -> None:
    with pytest.raises(ValueError, match="requires an explicit contest_id"):
        paid_entry_count_v2(_entries(), contest_id=None)
    with pytest.raises(ValueError, match="requires an explicit contest_id"):
        paid_entry_count_v2(_entries(), contest_id="   ")
    with pytest.raises(ValueError, match="no entry rows for contest_id 88"):
        paid_entry_count_v2(_entries(), contest_id="88")

    missing_contest = _entries() + "3,Unknown,,$20\n"
    with pytest.raises(ValueError, match="selection is ambiguous"):
        paid_entry_count_v2(missing_contest, contest_id="77")

    cross_contest_duplicate = _entries() + "1,Other,88,$20\n"
    with pytest.raises(ValueError, match="ambiguous across contests"):
        paid_entry_count_v2(cross_contest_duplicate, contest_id="77")


def test_paid_entry_target_rejects_blank_and_duplicate_entry_ids() -> None:
    duplicate = _entries().replace("2,Milly,77", "1,Milly,77")
    with pytest.raises(ValueError, match="duplicate Entry IDs"):
        paid_entry_count_v2(duplicate, contest_id="77")

    blank = _entries().replace("2,Milly,77", ",Milly,77")
    with pytest.raises(ValueError, match="nonblank Entry IDs"):
        paid_entry_count_v2(blank, contest_id="77")


def test_ordinary_paid_fill_refuses_locked_rows() -> None:
    rows = _salary_rows()
    catalog = _catalog(rows)
    with pytest.raises(ValueError, match="refuses locked rows"):
        fill_paid_entries_csv_v2(
            _entries(locked=True), _book(rows), catalog=catalog, contest_id="77"
        )


class _SalaryStore:
    def __init__(self, rows: pd.DataFrame):
        self.rows = rows

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        return self.rows[self.rows.draft_group_id == draft_group_id].copy()


def test_paid_v2_api_routes_bind_the_current_slate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _salary_rows()
    book = _book(rows)
    store = _SalaryStore(rows)
    build_calls = []

    def build_once(req, selected_store):
        build_calls.append((req, selected_store))
        return book, _ranked(book)

    monkeypatch.setattr(
        app_main,
        "_build_classic",
        build_once,
    )
    monkeypatch.setattr(
        "nfl_dfs.notes.record_entered_lineups", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(app_main, "_with_watch_notes", lambda players: players)

    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
    )
    preview = app_main.build_paid_lineups_v2(request, store=store)
    assert len(build_calls) == 1
    assert len(preview["lineups"]) == 2
    assert preview["paid_export"]["actual_entries"] == 2
    assert preview["paid_export"]["unique_rosters"] == 2
    assert preview["paid_export"]["draftkings_legal"] is True
    assert preview["paid_export"]["active_eligible"] is True
    csv_bytes = preview["dk_csv"].encode("utf-8")
    assert preview["paid_export"]["csv_sha256"] == hashlib.sha256(
        csv_bytes
    ).hexdigest()
    assert len(list(csv.reader(io.StringIO(preview["dk_csv"])))) == 3

    response = app_main.build_paid_lineups_csv_v2(request, store=store)
    assert response.status_code == 200
    assert response.headers["x-paid-book-boundary"] == PAID_CLASSIC_BOUNDARY_ID
    assert response.headers["x-paid-book-entries"] == "2"
    assert response.headers["x-paid-book-exact-k"] == "true"
    assert response.headers["x-paid-book-catalog-pulled-at"] == (
        _PULLED_AT.isoformat()
    )
    assert response.headers["x-paid-book-catalog-age-seconds"] == "3600.0"
    assert len(response.headers["x-paid-book-receipt-sha256"]) == 64

    entries_request = app_main.FillEntriesRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        entries_csv=_entries(),
        contest_id="77",
        sim=False,
    )
    entries_response = app_main.fill_paid_classic_entries_v2(
        entries_request, store=store
    )
    assert entries_response.status_code == 200
    assert entries_response.headers["x-paid-book-boundary"] == (
        PAID_CLASSIC_BOUNDARY_ID
    )
    assert entries_response.headers["x-paid-book-entries"] == "2"


def test_paid_v2_api_refuses_implicit_whole_week_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = _book()
    monkeypatch.setattr(
        app_main,
        "_build_classic",
        lambda req, store: (book, _ranked(book)),
    )
    request = app_main.LineupRequest(
        season=2026, week=1, n_lineups=2, sim=False
    )
    with pytest.raises(HTTPException, match="requires draft_group_id"):
        app_main.build_paid_lineups_csv_v2(
            request, store=_SalaryStore(_salary_rows())
        )


def test_both_paid_v2_api_routes_reject_a_partial_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _salary_rows()
    short_book = _book(rows)[:1]
    monkeypatch.setattr(
        app_main,
        "_build_classic",
        lambda req, store: (short_book, _ranked(short_book)),
    )
    request = app_main.LineupRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        n_lineups=2,
        sim=False,
    )
    with pytest.raises(HTTPException, match="book is short"):
        app_main.build_paid_lineups_v2(request, store=_SalaryStore(rows))
    with pytest.raises(HTTPException, match="book is short"):
        app_main.build_paid_lineups_csv_v2(
            request, store=_SalaryStore(rows)
        )

    entries_request = app_main.FillEntriesRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        entries_csv=_entries(),
        contest_id="77",
        sim=False,
    )
    with pytest.raises(HTTPException, match="book is short"):
        app_main.fill_paid_classic_entries_v2(
            entries_request, store=_SalaryStore(rows)
        )


def test_paid_entries_api_requires_contest_before_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_calls = []
    monkeypatch.setattr(
        app_main,
        "_build_classic",
        lambda req, store: build_calls.append(req),
    )
    request = app_main.FillEntriesRequest(
        season=2026,
        week=1,
        draft_group_id=9001,
        entries_csv=_entries(),
        sim=False,
    )
    with pytest.raises(HTTPException, match="requires an explicit contest_id"):
        app_main.fill_paid_classic_entries_v2(
            request, store=_SalaryStore(_salary_rows())
        )
    assert build_calls == []


def test_classic_web_ui_uses_the_single_build_paid_preview() -> None:
    html = app_main.lineups_page()
    assert "sd?'/showdown/lineups':'/lineups/paid-v2'" in html
    assert "paid v2 exact K" in html
    assert "lastBuild.payload.dk_csv" in html
    assert "CSV always downloads that exact preview" in html


def test_classic_salary_store_exposes_the_exact_pull_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nfl_dfs.app.store import CLASSIC_COLUMNS, BigQueryStore

    calls = []

    def query(sql, *, params):
        calls.append((sql, params))
        return pd.DataFrame()

    monkeypatch.setattr("nfl_dfs.bq.query_df", query)
    BigQueryStore().classic_salaries(9001)
    assert "pulled_at" in CLASSIC_COLUMNS
    assert "SELECT DISTINCT s.pulled_at, s.draft_group_id" in calls[0][0]
    assert calls[0][1] == {"gid": 9001}
