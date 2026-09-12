"""Week tail ledger v1: synthetic build, re-derivation, and mutation checks."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from nfl_dfs.research import week_tail_ledger_v1 as ledger

IDENTITY = {
    "uri": "gs://bucket/week1/terminal.json",
    "generation": "1789080700983712",
    "sha256": "a" * 64,
    "bytes": 1234,
}


def _roster(prefix: str, *ids: str) -> list[str]:
    base = [f"{prefix}-{index}" for index in range(9 - len(ids))]
    return base + list(ids)


def _actuals() -> dict[str, float]:
    actuals = {}
    for prefix in ("a", "b", "c", "d"):
        for index in range(9):
            actuals[f"{prefix}-{index}"] = 20.0
    actuals["star"] = 60.0
    actuals["dud"] = 0.0
    actuals["BUF_DST"] = 12.0
    return actuals


def _pools() -> dict[str, list[list[str]]]:
    # pool p800: 180, 220, 160+... -> rosters a (180), b+star (60+8*20=220), c+dud (160)
    return {
        "p800": [_roster("a"), _roster("b", "star"), _roster("c", "dud")],
        "p400": [_roster("a"), _roster("d", "BUF_DST")],  # 180, 172
    }


def _books() -> dict[str, list[dict]]:
    return {
        "P_CTRL": [
            {"lineup_id": "l1", "lineup_rank": 1,
             "internal_player_ids": _roster("a")},
            {"lineup_id": "l2", "lineup_rank": 2,
             "internal_player_ids": _roster("c", "dud")},
        ],
        "P_MIX": [
            {"lineup_id": "m1", "lineup_rank": 1,
             "internal_player_ids": _roster("b", "star")},
        ],
    }


def _build(**overrides):
    kwargs = dict(
        season=2026,
        week=1,
        slate_id="dk-151307",
        lock_utc="2026-09-13T17:00:00+00:00",
        captured_at="2026-09-15T14:00:00+00:00",
        books=_books(),
        pools=_pools(),
        actual_by_internal_id=_actuals(),
        input_identities={"terminal": dict(IDENTITY)},
        winner={"score": 231.5, "source": "dk standings csv", "contest_id": "1"},
    )
    kwargs.update(overrides)
    return ledger.build_week_tail_ledger_row_v1(**kwargs)


def test_row_scores_pools_books_and_winner_exactly() -> None:
    row = _build()
    pools = {pool["pool_id"]: pool for pool in row["pools"]}
    assert pools["p800"]["max"] == 220.0
    assert pools["p800"]["tail_counts"] == {
        "ge_194": 1, "ge_200": 1, "ge_210": 1, "ge_220": 1, "ge_230": 0, "ge_240": 0,
    }
    assert pools["p400"]["max"] == 180.0
    books = {book["book_id"]: book for book in row["books"]}
    assert books["P_CTRL"]["max"] == 180.0
    assert books["P_CTRL"]["max_lineup_id"] == "l1"
    assert books["P_CTRL"]["against_pools"]["p800"] == {
        "pool_max": 220.0,
        "retrieval_gap": 40.0,
        "pool_max_in_book": False,
        "pool_max_book_rank": None,
        "book_max_rank_in_pool": 2,
        "book_rosters_in_pool": 2,
    }
    assert books["P_MIX"]["against_pools"]["p800"]["pool_max_in_book"] is True
    assert books["P_MIX"]["against_pools"]["p800"]["pool_max_book_rank"] == 1
    assert books["P_MIX"]["against_pools"]["p800"]["retrieval_gap"] == 0.0
    assert row["winner"]["margins"]["books"] == {"P_CTRL": -51.5, "P_MIX": -11.5}
    assert row["winner"]["beaten_by_any_book"] is False
    assert row["winner"]["beaten_by_any_pool"] is False
    assert row["uses_target_week_outcomes"] is True
    assert all(row[field] is False for field in ledger._FALSE_AUTHORITY_FIELDS)
    assert ledger.validate_week_tail_ledger_row_v1(row) == row


def test_build_is_deterministic_and_winner_is_optional() -> None:
    assert _build() == _build()
    row = _build(winner=None)
    assert row["winner"] is None
    ledger.validate_week_tail_ledger_row_v1(row)


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda k: k["actual_by_internal_id"].pop("star"), "no realized actual"),
        (lambda k: k["actual_by_internal_id"].__setitem__("star", float("nan")),
         "not finite"),
        (lambda k: k["books"]["P_CTRL"].__setitem__(
            1, {**k["books"]["P_CTRL"][1], "lineup_id": "l1"}), "repeated"),
        (lambda k: k["books"]["P_CTRL"].__setitem__(
            1, {**k["books"]["P_CTRL"][1], "lineup_rank": 3}), "not exactly 1..n"),
        (lambda k: k["books"]["P_CTRL"][0].pop("internal_player_ids"),
         "lacks required fields"),
        (lambda k: k["pools"]["p800"].append(_roster("a")), "repeats a roster"),
        (lambda k: k["pools"].__setitem__("p800", []), "is empty"),
        (lambda k: k.__setitem__("captured_at", "2026-09-13T16:59:00+00:00"),
         "after slate lock"),
        (lambda k: k.__setitem__("thresholds", (194, 194)), "strictly increasing"),
        (lambda k: k["input_identities"]["terminal"].__setitem__("sha256", "zz"),
         "not lowercase hex"),
        (lambda k: k.__setitem__("winner", {"score": -1, "source": "x",
                                             "contest_id": "1"}), "positive"),
        (lambda k: k["books"]["P_MIX"][0]["internal_player_ids"].append("extra"),
         "exactly 9"),
    ],
)
def test_bad_inputs_fail_closed(mutate: Callable[[dict], object], match: str) -> None:
    kwargs = dict(
        season=2026,
        week=1,
        slate_id="dk-151307",
        lock_utc="2026-09-13T17:00:00+00:00",
        captured_at="2026-09-15T14:00:00+00:00",
        books=_books(),
        pools=_pools(),
        actual_by_internal_id=_actuals(),
        input_identities={"terminal": dict(IDENTITY)},
        winner={"score": 231.5, "source": "dk standings csv", "contest_id": "1"},
    )
    mutate(kwargs)
    with pytest.raises(ledger.WeekTailLedgerError, match=match):
        ledger.build_week_tail_ledger_row_v1(**kwargs)


def _rehash(row: dict) -> None:
    body = {key: row[key] for key in row if key != "row_sha256"}
    row["row_sha256"] = ledger.canonical_sha256(body)


@pytest.mark.parametrize(
    "mutate,rehash,match",
    [
        (lambda r: r.__setitem__("adoption_authority", True), True, "authority"),
        (lambda r: r.__setitem__("uses_target_week_outcomes", False), True,
         "target-week outcomes"),
        (lambda r: r["books"][1]["tail_counts"].__setitem__("ge_194", 0), False,
         "self-hash"),
        (lambda r: r.__setitem__("captured_at", "2026-09-13T16:00:00+00:00"), True,
         "captured before lock"),
        (lambda r: r.pop("winner"), True, "fields differ"),
        (lambda r: r.__setitem__("extra", 1), True, "fields differ"),
    ],
)
def test_tampered_rows_fail_validation(
    mutate: Callable[[dict], object], rehash: bool, match: str
) -> None:
    row = _build()
    mutate(row)
    if rehash:
        _rehash(row)
    with pytest.raises(ledger.WeekTailLedgerError, match=match):
        ledger.validate_week_tail_ledger_row_v1(row)


def test_coherent_rehash_cannot_hide_inconsistency() -> None:
    row = _build()
    row["books"][0]["tail_counts"]["ge_194"] = 0  # P_CTRL max is 180: still coherent
    body = {key: row[key] for key in row if key != "row_sha256"}
    row["row_sha256"] = ledger.canonical_sha256(body)
    ledger.validate_week_tail_ledger_row_v1(row)
    # P_MIX max is 220 but every count says nothing cleared: monotone, yet wrong.
    for key in row["books"][1]["tail_counts"]:
        row["books"][1]["tail_counts"][key] = 0
    body = {key: row[key] for key in row if key != "row_sha256"}
    row["row_sha256"] = ledger.canonical_sha256(body)
    with pytest.raises(ledger.WeekTailLedgerError, match="disagrees"):
        ledger.validate_week_tail_ledger_row_v1(row)
    row = _build()
    row["books"][0]["against_pools"]["p800"]["retrieval_gap"] = 1.0
    body = {key: row[key] for key in row if key != "row_sha256"}
    row["row_sha256"] = ledger.canonical_sha256(body)
    with pytest.raises(ledger.WeekTailLedgerError, match="does not re-derive"):
        ledger.validate_week_tail_ledger_row_v1(row)
