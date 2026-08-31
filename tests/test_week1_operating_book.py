from __future__ import annotations

from hashlib import sha256

import pytest

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference.week1_operating_book import (
    ALL_BOOM_SOURCE_ID,
    BALANCED_SOURCE_SCHEDULE_20,
    BX60_SOURCE_ID,
    CONTRACT_ID,
    CORE_SOURCE_ID,
    DECISION_DATE,
    INTERNAL_FREEZE_UTC,
    TIER3_READ_ID,
    WEEK1_DEADLINE_UTC,
    Tier3Amendment,
    Week1OperatingBookError,
    compose_week1_operating_book,
    operating_book_contract,
)


TIER3_SOURCE = "direct-generator-g1"


def _lineup(label: str) -> str:
    return f"lineup-v1-{sha256(label.encode('ascii')).hexdigest()}"


def _ids(source: str, count: int = 120) -> list[str]:
    return [_lineup(f"{source}-{index}") for index in range(count)]


def _base_sources(count: int = 120) -> dict[str, list[str]]:
    return {
        CORE_SOURCE_ID: _ids("core", count),
        ALL_BOOM_SOURCE_ID: _ids("all-boom", count),
        BX60_SOURCE_ID: _ids("bx60", count),
    }


def _amendment(
    *,
    slots_by_k: tuple[tuple[int, int], ...] = (
        (20, 1),
        (40, 2),
        (80, 4),
        (100, 5),
    ),
    source_id: str = TIER3_SOURCE,
    selection_id: str = "phenotype-set-selector",
    positive: bool = True,
    orthogonal: bool = True,
    read_id: str = TIER3_READ_ID,
    issued_at: str = "2026-08-31T18:00:00Z",
) -> Tier3Amendment:
    return Tier3Amendment(
        amendment_id="week1-tier3-054-owner-amendment-v1",
        issued_at_utc=issued_at,
        source_id=source_id,
        selection_id=selection_id,
        slots_by_k=slots_by_k,
        evidence_receipt_sha256="a" * 64,
        read_id=read_id,
        positive=positive,
        orthogonal_to_core=orthogonal,
    )


def test_contract_freezes_owner_dates_laws_and_exact_prefix_quotas() -> None:
    contract = operating_book_contract()

    assert contract["contract_id"] == CONTRACT_ID
    assert contract["decision_date"] == DECISION_DATE == "2026-08-30"
    assert contract["week1_main_slate_deadline_utc"] == (
        WEEK1_DEADLINE_UTC
    ) == "2026-09-13T17:00:00Z"
    assert contract["internal_book_freeze_utc"] == (
        INTERNAL_FREEZE_UTC
    ) == "2026-09-11T17:00:00Z"
    assert contract["operating_k"] == [80, 100]
    assert contract["core"] == {
        "source_id": CORE_SOURCE_ID,
        "generation_id": "boom-first",
        "leverage_solves_per_block": 40,
        "boom_solves_per_block": 160,
        "optimizer_k": 1,
        "centering": "corrected-mean-centering",
        "market_blend": "props-first-with-dk-ppg-fallback",
        "selection_id": "coverage-194",
    }
    assert contract["cap4"]["allowed_in_entered_book"] is False
    assert contract["tier3"]["default_entered_slots"] == 0
    assert contract["tier3"]["required_read_id"] == "PREREG-026/054"
    assert contract["prefix_quotas_before_tier3"] == {
        "20": {
            CORE_SOURCE_ID: 16,
            ALL_BOOM_SOURCE_ID: 3,
            BX60_SOURCE_ID: 1,
        },
        "40": {
            CORE_SOURCE_ID: 32,
            ALL_BOOM_SOURCE_ID: 6,
            BX60_SOURCE_ID: 2,
        },
        "80": {
            CORE_SOURCE_ID: 64,
            ALL_BOOM_SOURCE_ID: 12,
            BX60_SOURCE_ID: 4,
        },
        "100": {
            CORE_SOURCE_ID: 80,
            ALL_BOOM_SOURCE_ID: 15,
            BX60_SOURCE_ID: 5,
        },
    }
    without_hash = dict(contract)
    observed_hash = without_hash.pop("contract_sha256")
    assert observed_hash == canonical_sha256(without_hash)


def test_balanced_20_slot_schedule_has_80_15_5_mix() -> None:
    assert len(BALANCED_SOURCE_SCHEDULE_20) == 20
    assert BALANCED_SOURCE_SCHEDULE_20.count(CORE_SOURCE_ID) == 16
    assert BALANCED_SOURCE_SCHEDULE_20.count(ALL_BOOM_SOURCE_ID) == 3
    assert BALANCED_SOURCE_SCHEDULE_20.count(BX60_SOURCE_ID) == 1


def test_composition_is_exact_deterministic_and_prefix_stable() -> None:
    sources = _base_sources()
    book100 = compose_week1_operating_book(sources, k=100)

    assert len(book100["entered_lineups"]) == 100
    assert len({row["lineup_id"] for row in book100["entered_lineups"]}) == 100
    assert book100["source_quotas"] == {
        CORE_SOURCE_ID: 80,
        ALL_BOOM_SOURCE_ID: 15,
        BX60_SOURCE_ID: 5,
    }
    assert book100["cap4_used"] is False
    assert book100["uses_realized_outcomes"] is False

    ids100 = [row["lineup_id"] for row in book100["entered_lineups"]]
    for k in (20, 40, 80):
        prefix = compose_week1_operating_book(sources, k=k)
        assert [row["lineup_id"] for row in prefix["entered_lineups"]] == (
            ids100[:k]
        )
    assert compose_week1_operating_book(sources, k=100) == book100


def test_global_dedupe_backfills_within_the_scheduled_source() -> None:
    shared = _lineup("shared")
    all_zero = _lineup("all-zero")
    sources = {
        CORE_SOURCE_ID: [shared, *_ids("core", 90)],
        ALL_BOOM_SOURCE_ID: [
            shared,
            all_zero,
            all_zero,
            *_ids("all-boom", 90),
        ],
        BX60_SOURCE_ID: [shared, *_ids("bx60", 90)],
    }

    receipt = compose_week1_operating_book(sources, k=20)
    source_receipts = {
        row["source_id"]: row for row in receipt["source_receipts"]
    }
    assert source_receipts[ALL_BOOM_SOURCE_ID]["dedupe_backfill_count"] == 2
    assert source_receipts[BX60_SOURCE_ID]["dedupe_backfill_count"] == 1
    assert source_receipts[ALL_BOOM_SOURCE_ID]["entered_count"] == 3
    assert source_receipts[BX60_SOURCE_ID]["entered_count"] == 1
    assert next(
        row
        for row in receipt["source_memberships"]
        if row["source_id"] == ALL_BOOM_SOURCE_ID and row["source_rank"] == 1
    )["status"] == "duplicate-of-entered-lineup"
    assert any(
        row["entered"] is False
        and row["status"] == "unentered-source-remainder"
        for row in receipt["unentered_lineups"]
    )
    assert all(row["entered"] is True for row in receipt["entered_lineups"])
    assert all(row["entered"] is False for row in receipt["unentered_lineups"])

    without_hash = dict(receipt)
    observed_hash = without_hash.pop("receipt_sha256")
    assert observed_hash == canonical_sha256(without_hash)
    assert receipt["entered_lineup_ids_sha256"] == canonical_sha256([
        row["lineup_id"] for row in receipt["entered_lineups"]
    ])


def test_core_evidence_order_has_dedupe_precedence_over_sleeves() -> None:
    shared = _lineup("core-rank-five-and-all-boom-rank-one")
    sources = _base_sources()
    sources[CORE_SOURCE_ID][4] = shared
    sources[ALL_BOOM_SOURCE_ID][0] = shared

    receipt = compose_week1_operating_book(sources, k=20)
    shared_entries = [
        row for row in receipt["entered_lineups"] if row["lineup_id"] == shared
    ]
    assert shared_entries == [{
        "entry_rank": 6,
        "lineup_id": shared,
        "source_id": CORE_SOURCE_ID,
        "source_rank": 5,
        "source_role": "tier1-core",
        "entered": True,
    }]
    all_boom_receipt = next(
        row
        for row in receipt["source_receipts"]
        if row["source_id"] == ALL_BOOM_SOURCE_ID
    )
    assert all_boom_receipt["dedupe_backfill_count"] == 1
    assert all_boom_receipt["entered_count"] == 3


def test_overlapping_source_books_remain_prefix_stable_through_k100() -> None:
    shared = _lineup("core-rank-seventy-and-all-boom-rank-one")
    sources = _base_sources()
    sources[CORE_SOURCE_ID][69] = shared
    sources[ALL_BOOM_SOURCE_ID][0] = shared

    book100 = compose_week1_operating_book(sources, k=100)
    ids100 = [row["lineup_id"] for row in book100["entered_lineups"]]
    shared_row = next(
        row for row in book100["entered_lineups"] if row["lineup_id"] == shared
    )
    assert shared_row["source_id"] == CORE_SOURCE_ID
    assert shared_row["source_rank"] == 70
    for k in (20, 40, 80):
        prefix = compose_week1_operating_book(sources, k=k)
        assert [row["lineup_id"] for row in prefix["entered_lineups"]] == (
            ids100[:k]
        )


def test_composition_fails_closed_when_a_source_cannot_meet_its_quota() -> None:
    shared = _lineup("shared-shortfall")
    sources = _base_sources()
    sources[ALL_BOOM_SOURCE_ID] = [shared, shared, _lineup("only-unique")]
    sources[CORE_SOURCE_ID][0] = shared

    with pytest.raises(Week1OperatingBookError, match="cannot fill its exact quota"):
        compose_week1_operating_book(sources, k=20)


def test_no_tier3_source_is_accepted_without_an_explicit_amendment() -> None:
    sources = _base_sources()
    sources[TIER3_SOURCE] = _ids("tier3")
    with pytest.raises(Week1OperatingBookError, match="frozen source set"):
        compose_week1_operating_book(sources, k=80)

    with pytest.raises(Week1OperatingBookError, match="explicit Tier3Amendment"):
        compose_week1_operating_book(
            _base_sources(), k=80, tier3_amendment={"source_id": TIER3_SOURCE}
        )


def test_valid_tier3_amendment_replaces_only_core_and_preserves_prefixes() -> None:
    amendment = _amendment()
    sources = _base_sources()
    sources[TIER3_SOURCE] = _ids("tier3")
    book100 = compose_week1_operating_book(
        sources, k=100, tier3_amendment=amendment
    )

    assert book100["source_quotas"] == {
        CORE_SOURCE_ID: 75,
        ALL_BOOM_SOURCE_ID: 15,
        BX60_SOURCE_ID: 5,
        TIER3_SOURCE: 5,
    }
    assert book100["tier3_amendment"]["read_id"] == TIER3_READ_ID
    assert book100["tier3_amendment"]["changes_tier2_counts"] is False
    amendment_without_hash = dict(book100["tier3_amendment"])
    amendment_hash = amendment_without_hash.pop("amendment_sha256")
    assert amendment_hash == canonical_sha256(amendment_without_hash)

    ids100 = [row["lineup_id"] for row in book100["entered_lineups"]]
    expected = {
        20: (15, 3, 1, 1),
        40: (30, 6, 2, 2),
        80: (60, 12, 4, 4),
    }
    for k, counts in expected.items():
        prefix = compose_week1_operating_book(
            sources, k=k, tier3_amendment=amendment
        )
        assert [row["lineup_id"] for row in prefix["entered_lineups"]] == (
            ids100[:k]
        )
        assert tuple(prefix["source_quotas"][source_id] for source_id in (
            CORE_SOURCE_ID,
            ALL_BOOM_SOURCE_ID,
            BX60_SOURCE_ID,
            TIER3_SOURCE,
        )) == counts


@pytest.mark.parametrize(
    "amendment,match",
    [
        (_amendment(slots_by_k=((20, 2), (40, 2), (80, 4), (100, 5))), "5%"),
        (_amendment(slots_by_k=((20, 1), (40, 0), (80, 4), (100, 5))), "5%"),
        (_amendment(read_id="PREREG-026/053"), "PREREG-026/054"),
        (_amendment(positive=False), "positive and orthogonal"),
        (_amendment(orthogonal=False), "positive and orthogonal"),
        (_amendment(selection_id="cap-4-prefix-then-fill"), "cap-4"),
        (_amendment(issued_at="2026-09-12T00:00:00Z"), "decision window"),
    ],
)
def test_tier3_amendment_fails_closed(
    amendment: Tier3Amendment, match: str
) -> None:
    sources = _base_sources()
    sources[amendment.source_id] = _ids("tier3")
    with pytest.raises(Week1OperatingBookError, match=match):
        compose_week1_operating_book(
            sources, k=100, tier3_amendment=amendment
        )


def test_rejects_unsupported_k_noncanonical_ids_and_unknown_sources() -> None:
    with pytest.raises(Week1OperatingBookError, match="K must be"):
        compose_week1_operating_book(_base_sources(), k=60)

    sources = _base_sources()
    sources[CORE_SOURCE_ID][0] = "not-a-canonical-lineup-id"
    with pytest.raises(Week1OperatingBookError, match="noncanonical"):
        compose_week1_operating_book(sources, k=20)

    sources = _base_sources()
    sources["cap-4-prefix-then-fill"] = _ids("cap4")
    with pytest.raises(Week1OperatingBookError, match="frozen source set"):
        compose_week1_operating_book(sources, k=20)
