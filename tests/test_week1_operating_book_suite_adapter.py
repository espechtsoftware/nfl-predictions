from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference import week1_operating_book_suite_adapter as adapter
from nfl_dfs.inference.week1_operating_book import (
    ALL_BOOM_SOURCE_ID,
    BX60_SOURCE_ID,
    CORE_SOURCE_ID,
)


CAP4_RETRIEVAL_ID = "cap4-production-ladder-prefix-then-fill-k80"


def _lineup(label: str) -> str:
    return f"lineup-v1-{sha256(label.encode('ascii')).hexdigest()}"


def _book(label: str) -> list[str]:
    return [_lineup(f"{label}-{index}") for index in range(80)]


def _authority() -> dict[str, object]:
    memberships = {arm: _book(arm) for arm in shadow.ARM_ORDER}
    return {
        "schema_version": shadow.SUITE_AUTHORITY_SCHEMA,
        "suite_authority_sha256": "a" * 64,
        "complete": True,
        "manifest": {
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        },
        "terminal": {
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        },
        "membership_lineup_ids_by_arm": memberships,
        "retrieval_lineup_ids_by_population": {
            "incumbent-160-40": {
                adapter.BASE_RETRIEVAL_ID: memberships["incumbent-160-40"],
                CAP4_RETRIEVAL_ID: _book("incumbent-cap4"),
            },
            CORE_SOURCE_ID: {
                adapter.BASE_RETRIEVAL_ID: memberships[CORE_SOURCE_ID],
                CAP4_RETRIEVAL_ID: _book("boom-first-cap4"),
            },
        },
    }


@pytest.mark.parametrize(
    ("k", "expected"),
    (
        (80, {CORE_SOURCE_ID: 64, ALL_BOOM_SOURCE_ID: 12, BX60_SOURCE_ID: 4}),
        (100, {CORE_SOURCE_ID: 80, ALL_BOOM_SOURCE_ID: 15, BX60_SOURCE_ID: 5}),
    ),
)
def test_adapter_builds_exact_no_cap4_operating_books(
    monkeypatch: pytest.MonkeyPatch,
    k: int,
    expected: dict[str, int],
) -> None:
    authority = _authority()
    calls: list[object] = []

    def _validate(value: object) -> dict[str, object]:
        calls.append(value)
        return value  # type: ignore[return-value]

    monkeypatch.setattr(shadow, "validate_suite_authority_v1", _validate)
    envelope = adapter.build_week1_operating_book_from_suite_authority_v1(
        authority, k=k
    )

    assert calls == [authority]
    assert envelope["suite_authority_sha256"] == "a" * 64
    assert envelope["base_retrieval_id"] == adapter.BASE_RETRIEVAL_ID
    assert envelope["base_selection_id"] == "coverage-194"
    assert envelope["cap4_used"] is False
    assert envelope["tier3_used"] is False
    assert envelope["uses_realized_outcomes"] is False
    assert envelope["outcome_fields"] == []
    receipt = envelope["compositor_receipt"]
    assert receipt["source_quotas"] == expected
    assert len(receipt["entered_lineups"]) == k
    assert len({row["lineup_id"] for row in receipt["entered_lineups"]}) == k
    assert envelope["compositor_receipt_sha256"] == receipt["receipt_sha256"]

    cap4_ids = set(
        authority["retrieval_lineup_ids_by_population"][CORE_SOURCE_ID][
            CAP4_RETRIEVAL_ID
        ]
    )
    assert not cap4_ids & {
        row["lineup_id"] for row in receipt["source_memberships"]
    }
    assert (
        adapter.validate_week1_operating_book_suite_envelope_v1(envelope)
        == envelope
    )


def test_adapter_binds_each_exact_source_order_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )
    envelope = adapter.build_week1_operating_book_from_suite_authority_v1(
        authority, k=80
    )
    expected_bindings = [
        {
            "source_id": source_id,
            "lineup_count": 80,
            "ordered_lineup_ids_sha256": canonical_sha256(
                authority["membership_lineup_ids_by_arm"][source_id]
            ),
        }
        for source_id in (CORE_SOURCE_ID, ALL_BOOM_SOURCE_ID, BX60_SOURCE_ID)
    ]
    assert envelope["source_book_bindings"] == expected_bindings
    assert envelope["source_book_bindings_sha256"] == canonical_sha256(
        expected_bindings
    )


def test_adapter_preserves_exact_quotas_while_backfilling_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    memberships = authority["membership_lineup_ids_by_arm"]
    core = memberships[CORE_SOURCE_ID]
    all_boom = memberships[ALL_BOOM_SOURCE_ID]
    bx60 = memberships[BX60_SOURCE_ID]
    all_boom[:4] = core[:4]
    bx60[:3] = core[4:7]
    bx60[3] = all_boom[8]
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )

    envelope = adapter.build_week1_operating_book_from_suite_authority_v1(
        authority, k=80
    )
    receipt = envelope["compositor_receipt"]
    assert receipt["source_quotas"] == {
        CORE_SOURCE_ID: 64,
        ALL_BOOM_SOURCE_ID: 12,
        BX60_SOURCE_ID: 4,
    }
    entered = receipt["entered_lineups"]
    assert len({row["lineup_id"] for row in entered}) == 80
    source_receipts = {
        row["source_id"]: row for row in receipt["source_receipts"]
    }
    assert source_receipts[ALL_BOOM_SOURCE_ID]["dedupe_backfill_count"] > 0
    assert source_receipts[BX60_SOURCE_ID]["dedupe_backfill_count"] > 0


@pytest.mark.parametrize("source_id", (ALL_BOOM_SOURCE_ID, BX60_SOURCE_ID))
def test_adapter_binds_optional_base_retrieval_order_for_every_source(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
) -> None:
    authority = _authority()
    authority["retrieval_lineup_ids_by_population"][source_id] = {
        adapter.BASE_RETRIEVAL_ID: list(
            authority["membership_lineup_ids_by_arm"][source_id]
        ),
        CAP4_RETRIEVAL_ID: _book(f"{source_id}-cap4"),
    }
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )
    adapter.build_week1_operating_book_from_suite_authority_v1(
        authority, k=80
    )

    authority["retrieval_lineup_ids_by_population"][source_id][
        adapter.BASE_RETRIEVAL_ID
    ] = _book(f"{source_id}-drift")
    with pytest.raises(
        adapter.Week1OperatingBookSuiteAdapterError,
        match="base-retrieval and membership source orders differ",
    ):
        adapter.build_week1_operating_book_from_suite_authority_v1(
            authority, k=80
        )


def test_adapter_rejects_validator_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _reject(_value: object) -> dict[str, object]:
        raise shadow.ProspectiveGenerationShadowEvaluationError("invalid")

    monkeypatch.setattr(shadow, "validate_suite_authority_v1", _reject)
    with pytest.raises(
        adapter.Week1OperatingBookSuiteAdapterError,
        match="suite authority validation failed",
    ):
        adapter.build_week1_operating_book_from_suite_authority_v1({}, k=80)


@pytest.mark.parametrize("mutation", ("missing-source", "base-drift", "duplicate"))
def test_adapter_rejects_source_mismatch_after_validator_boundary(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )
    if mutation == "missing-source":
        authority["membership_lineup_ids_by_arm"].pop(ALL_BOOM_SOURCE_ID)
    elif mutation == "base-drift":
        authority["retrieval_lineup_ids_by_population"][CORE_SOURCE_ID][
            adapter.BASE_RETRIEVAL_ID
        ] = _book("different-base")
    else:
        book = authority["membership_lineup_ids_by_arm"][BX60_SOURCE_ID]
        book[1] = book[0]

    with pytest.raises(adapter.Week1OperatingBookSuiteAdapterError):
        adapter.build_week1_operating_book_from_suite_authority_v1(
            authority, k=80
        )


def test_adapter_rejects_cap4_and_outcome_bearing_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )
    with pytest.raises(
        adapter.Week1OperatingBookSuiteAdapterError, match="no-cap4"
    ):
        adapter.build_week1_operating_book_from_suite_authority_v1(
            authority, k=80, retrieval_id=CAP4_RETRIEVAL_ID
        )

    authority["terminal"]["uses_realized_outcomes"] = True
    with pytest.raises(
        adapter.Week1OperatingBookSuiteAdapterError, match="not score-blind"
    ):
        adapter.build_week1_operating_book_from_suite_authority_v1(
            authority, k=80
        )


def test_adapter_rejects_rehashed_envelope_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )
    envelope = adapter.build_week1_operating_book_from_suite_authority_v1(
        authority, k=100
    )
    forged = deepcopy(envelope)
    forged["source_book_bindings"][0]["ordered_lineup_ids_sha256"] = "f" * 64
    forged.pop("envelope_sha256")
    forged["envelope_sha256"] = canonical_sha256(forged)
    with pytest.raises(
        adapter.Week1OperatingBookSuiteAdapterError,
        match="source order bindings differ",
    ):
        adapter.validate_week1_operating_book_suite_envelope_v1(forged)


def test_adapter_supports_only_operating_k(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = _authority()
    monkeypatch.setattr(
        shadow, "validate_suite_authority_v1", lambda value: value
    )
    for k in (20, 40, 60, 150):
        with pytest.raises(
            adapter.Week1OperatingBookSuiteAdapterError, match="K must be"
        ):
            adapter.build_week1_operating_book_from_suite_authority_v1(
                authority, k=k
            )
