from copy import deepcopy

import pytest

from nfl_dfs.inference.generation_exposure import (
    GenerationExposureError,
    SolveExposureLedger,
    canonical_sha256,
    validate_ledger,
)


def _roster(offset: int = 0) -> list[str]:
    return [f"p{offset + index:02d}" for index in range(9)]


def test_ledger_records_new_and_ledger_duplicate() -> None:
    builder = SolveExposureLedger(source_label="seed-101")
    builder.record(
        family="boom",
        requested_ordinal=0,
        world_id=12,
        duration_seconds=0.125,
        status="new",
        roster_ids=_roster(),
    )
    duplicate = builder.record(
        family="boom",
        requested_ordinal=1,
        world_id=19,
        duration_seconds=0.375,
        status="dup",
        roster_ids=reversed(_roster()),
    )
    ledger = builder.finalize(expected_requests_by_family={"boom": 2})

    assert duplicate["duplicate_origin"] == "ledger"
    assert duplicate["duplicate_of_attempt_ordinal"] == 0
    assert ledger["status_counts"]["new"] == 1
    assert ledger["status_counts"]["dup"] == 1
    assert ledger["duration_seconds_by_family"]["boom"] == 0.5
    assert ledger["total_duration_seconds"] == 0.5
    assert validate_ledger(ledger) == ledger


def test_preexisting_duplicate_has_explicit_origin_without_fake_pointer() -> None:
    builder = SolveExposureLedger(
        source_label="seed-101", existing_rosters=[_roster()]
    )
    row = builder.record(
        family="discovery",
        requested_ordinal=0,
        status="dup",
        roster_ids=_roster(),
    )
    ledger = builder.finalize(
        expected_requests_by_family={"discovery": 1}
    )

    assert row["duplicate_origin"] == "preexisting"
    assert row["duplicate_of_attempt_ordinal"] is None
    assert validate_ledger(ledger) == ledger


def test_retry_chain_and_exhausted_requests_are_complete() -> None:
    builder = SolveExposureLedger(source_label="seed-202")
    builder.record(
        family="leverage",
        requested_ordinal=0,
        retry_ordinal=0,
        status="error",
    )
    builder.record(
        family="leverage",
        requested_ordinal=0,
        retry_ordinal=1,
        status="new",
        roster_ids=_roster(20),
    )
    builder.record(
        family="leverage",
        requested_ordinal=1,
        status="exhausted",
    )
    ledger = builder.finalize(
        expected_requests_by_family={"leverage": 2}
    )

    assert ledger["attempt_count"] == 3
    assert ledger["one_record_or_retry_chain_per_requested_solve"] is True


def test_missing_requested_ordinal_is_rejected() -> None:
    builder = SolveExposureLedger(source_label="seed-303")
    builder.record(
        family="boom",
        requested_ordinal=0,
        status="infeasible",
    )
    with pytest.raises(GenerationExposureError, match="census differs"):
        builder.finalize(expected_requests_by_family={"boom": 2})


def test_tamper_and_outcome_fields_fail_closed() -> None:
    builder = SolveExposureLedger(source_label="seed-404")
    builder.record(
        family="boom",
        requested_ordinal=0,
        status="new",
        roster_ids=_roster(),
    )
    ledger = builder.finalize(expected_requests_by_family={"boom": 1})

    tampered = deepcopy(ledger)
    tampered["rows"][0]["world_id"] = 99
    with pytest.raises(GenerationExposureError, match="self-hash differs"):
        validate_ledger(tampered)

    outcome_read = deepcopy(ledger)
    row = outcome_read["rows"][0]
    row["uses_realized_outcomes"] = True
    body = dict(row)
    body.pop("row_sha256")
    row["row_sha256"] = canonical_sha256(body)
    outcome_read["row_manifest_sha256"] = canonical_sha256(
        outcome_read["rows"]
    )
    ledger_body = dict(outcome_read)
    ledger_body.pop("ledger_sha256")
    outcome_read["ledger_sha256"] = canonical_sha256(ledger_body)
    with pytest.raises(GenerationExposureError, match="realized outcomes"):
        validate_ledger(outcome_read)


def test_rosters_must_contain_exactly_nine_unique_ids() -> None:
    builder = SolveExposureLedger(source_label="seed-505")
    with pytest.raises(GenerationExposureError, match="exactly nine"):
        builder.record(
            family="boom",
            requested_ordinal=0,
            status="new",
            roster_ids=_roster()[:8],
        )


@pytest.mark.parametrize("duration", [-0.1, float("inf"), float("nan"), True])
def test_duration_must_be_finite_and_nonnegative(duration) -> None:
    builder = SolveExposureLedger(source_label="seed-606")
    with pytest.raises(GenerationExposureError, match="solve duration"):
        builder.record(
            family="boom",
            requested_ordinal=0,
            duration_seconds=duration,
            status="infeasible",
        )
