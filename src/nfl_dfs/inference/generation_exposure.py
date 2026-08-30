"""Canonical prelock exposure ledger for prospective generation shadows.

The ledger records requested optimizer work, including work that yields no
candidate.  It contains no realized score, contest, rank, payout, ownership,
or post-lock field.  A separate grader may join a frozen ledger only after the
terminal prelock root exists.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from hashlib import sha256
import json
import math
import re
from typing import Final


LEDGER_SCHEMA: Final = "prospective-generation-solve-exposure-ledger/v2"
ROW_SCHEMA: Final = "prospective-generation-solve-exposure-row/v2"
ALLOWED_STATUSES: Final = frozenset({
    "new",
    "dup",
    "infeasible",
    "error",
    "exhausted",
})
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GenerationExposureError(ValueError):
    """A solve-exposure ledger violated the frozen prelock contract."""


def _fail(message: str) -> None:
    raise GenerationExposureError(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GenerationExposureError(
            "exposure value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def roster_identity(player_ids: Iterable[object]) -> dict[str, object]:
    roster = sorted(str(value) for value in player_ids)
    if len(roster) != 9 or any(not value for value in roster):
        _fail("solve roster must contain exactly nine nonempty player IDs")
    if len(set(roster)) != 9:
        _fail("solve roster repeats a player ID")
    return {
        "player_ids": roster,
        "roster_sha256": canonical_sha256(roster),
    }


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} must be a normalized identifier")
    return value


def _nonnegative(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a nonnegative integer")
    return value


def _optional_nonnegative(value: object, *, label: str) -> int | None:
    if value is None:
        return None
    return _nonnegative(value, label=label)


def _duration(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("solve duration must be a finite nonnegative number")
    retained = float(value)
    if not math.isfinite(retained) or retained < 0.0:
        _fail("solve duration must be a finite nonnegative number")
    return retained


def _validate_row(value: object) -> dict[str, object]:
    fields = {
        "schema_version",
        "attempt_ordinal",
        "source_label",
        "family",
        "requested_ordinal",
        "retry_ordinal",
        "world_id",
        "duration_seconds",
        "status",
        "player_ids",
        "roster_sha256",
        "duplicate_origin",
        "duplicate_of_attempt_ordinal",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "row_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("solve-exposure row fields differ")
    item = dict(value)
    retained = item.pop("row_sha256")
    if type(retained) is not str or _SHA256.fullmatch(retained) is None:
        _fail("solve-exposure row hash differs")
    if canonical_sha256(item) != retained:
        _fail("solve-exposure row self-hash differs")
    attempt = _nonnegative(item["attempt_ordinal"], label="attempt ordinal")
    requested = _nonnegative(
        item["requested_ordinal"], label="requested ordinal"
    )
    retry = _nonnegative(item["retry_ordinal"], label="retry ordinal")
    world = _optional_nonnegative(item["world_id"], label="world ID")
    duration_seconds = _duration(item["duration_seconds"])
    duplicate = _optional_nonnegative(
        item["duplicate_of_attempt_ordinal"],
        label="duplicate attempt ordinal",
    )
    duplicate_origin = item["duplicate_origin"]
    if duplicate_origin not in {None, "ledger", "preexisting"}:
        _fail("duplicate origin differs")
    status = item["status"]
    if item["schema_version"] != ROW_SCHEMA or status not in ALLOWED_STATUSES:
        _fail("solve-exposure row fixed law differs")
    source = _identifier(item["source_label"], label="source label")
    family = _identifier(item["family"], label="family")
    player_ids = item["player_ids"]
    roster_hash = item["roster_sha256"]
    if status in {"new", "dup"}:
        if not isinstance(player_ids, Sequence) or isinstance(
            player_ids, (str, bytes)
        ):
            _fail("successful solve lacks a roster")
        roster = roster_identity(player_ids)
        if list(player_ids) != roster["player_ids"] or roster_hash != roster[
            "roster_sha256"
        ]:
            _fail("successful solve roster identity differs")
        if status == "new" and (
            duplicate is not None or duplicate_origin is not None
        ):
            _fail("new solve carries duplicate provenance")
        if status == "dup" and duplicate_origin is None:
            _fail("duplicate solve lacks duplicate provenance")
        if status == "dup" and duplicate_origin == "ledger" and (
            duplicate is None or duplicate >= attempt
        ):
            _fail("ledger duplicate lacks an earlier roster pointer")
        if status == "dup" and duplicate_origin == "preexisting" and (
            duplicate is not None
        ):
            _fail("preexisting duplicate carries a ledger pointer")
    else:
        if (
            player_ids is not None
            or roster_hash is not None
            or duplicate is not None
            or duplicate_origin is not None
        ):
            _fail("unsuccessful solve carries a roster")
    if item["uses_realized_outcomes"] is not False:
        _fail("solve-exposure row reads realized outcomes")
    if item["post_lock_data_read"] is not False:
        _fail("solve-exposure row reads post-lock data")
    return {
        **item,
        "attempt_ordinal": attempt,
        "source_label": source,
        "family": family,
        "requested_ordinal": requested,
        "retry_ordinal": retry,
        "world_id": world,
        "duration_seconds": duration_seconds,
        "status": status,
        "duplicate_origin": duplicate_origin,
        "duplicate_of_attempt_ordinal": duplicate,
        "row_sha256": retained,
    }


class SolveExposureLedger:
    """Append-only in-memory builder for one native generation book."""

    def __init__(
        self,
        *,
        source_label: str,
        existing_rosters: Iterable[Iterable[object]] = (),
    ) -> None:
        self.source_label = _identifier(source_label, label="source label")
        self._rows: list[dict[str, object]] = []
        self._first_attempt_by_roster: dict[str, int | None] = {}
        for roster in existing_rosters:
            identity = roster_identity(roster)
            self._first_attempt_by_roster.setdefault(
                str(identity["roster_sha256"]), None
            )

    @property
    def rows(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(row) for row in self._rows)

    def record(
        self,
        *,
        family: str,
        requested_ordinal: int,
        retry_ordinal: int = 0,
        world_id: int | None = None,
        duration_seconds: float = 0.0,
        status: str,
        roster_ids: Iterable[object] | None = None,
    ) -> dict[str, object]:
        retained_family = _identifier(family, label="family")
        requested = _nonnegative(
            requested_ordinal, label="requested ordinal"
        )
        retry = _nonnegative(retry_ordinal, label="retry ordinal")
        world = _optional_nonnegative(world_id, label="world ID")
        duration = _duration(duration_seconds)
        if status not in ALLOWED_STATUSES:
            _fail("solve status differs")
        attempt = len(self._rows)
        roster: dict[str, object] | None = None
        duplicate: int | None = None
        duplicate_origin: str | None = None
        if status in {"new", "dup"}:
            if roster_ids is None:
                _fail("successful solve requires roster IDs")
            roster = roster_identity(roster_ids)
            digest = str(roster["roster_sha256"])
            was_seen = digest in self._first_attempt_by_roster
            prior = self._first_attempt_by_roster.get(digest)
            derived_status = "dup" if was_seen else "new"
            if status != derived_status:
                _fail("solve status disagrees with roster history")
            if prior is None:
                if digest in self._first_attempt_by_roster:
                    duplicate_origin = "preexisting"
                else:
                    self._first_attempt_by_roster[digest] = attempt
            else:
                duplicate = prior
                duplicate_origin = "ledger"
        elif roster_ids is not None:
            _fail("unsuccessful solve must not carry roster IDs")
        body: dict[str, object] = {
            "schema_version": ROW_SCHEMA,
            "attempt_ordinal": attempt,
            "source_label": self.source_label,
            "family": retained_family,
            "requested_ordinal": requested,
            "retry_ordinal": retry,
            "world_id": world,
            "duration_seconds": duration,
            "status": status,
            "player_ids": None if roster is None else roster["player_ids"],
            "roster_sha256": None if roster is None else roster["roster_sha256"],
            "duplicate_origin": duplicate_origin,
            "duplicate_of_attempt_ordinal": duplicate,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
        }
        body["row_sha256"] = canonical_sha256(body)
        normalized = _validate_row(body)
        self._rows.append(normalized)
        return dict(normalized)

    def finalize(
        self,
        *,
        expected_requests_by_family: Mapping[str, int],
    ) -> dict[str, object]:
        return build_ledger(
            self._rows,
            source_label=self.source_label,
            expected_requests_by_family=expected_requests_by_family,
        )


def build_ledger(
    rows: Sequence[Mapping[str, object]],
    *,
    source_label: str,
    expected_requests_by_family: Mapping[str, int],
) -> dict[str, object]:
    source = _identifier(source_label, label="source label")
    expected = {
        _identifier(key, label="expected family"): _nonnegative(
            value, label=f"{key} expected requests"
        )
        for key, value in expected_requests_by_family.items()
    }
    if not expected:
        _fail("solve-exposure ledger requires an expected family census")
    normalized = [_validate_row(row) for row in rows]
    if any(
        row["attempt_ordinal"] != ordinal or row["source_label"] != source
        for ordinal, row in enumerate(normalized)
    ):
        _fail("solve-exposure row order/source differs")
    observed_requests: dict[str, set[int]] = {key: set() for key in expected}
    status_counts: dict[str, int] = {key: 0 for key in ALLOWED_STATUSES}
    duration_by_family: dict[str, float] = {key: 0.0 for key in expected}
    duration_by_status: dict[str, float] = {
        key: 0.0 for key in ALLOWED_STATUSES
    }
    for row in normalized:
        family = str(row["family"])
        if family not in expected:
            _fail("solve-exposure row family is outside the frozen census")
        observed_requests[family].add(int(row["requested_ordinal"]))
        status_counts[str(row["status"])] += 1
        duration = float(row["duration_seconds"])
        duration_by_family[family] += duration
        duration_by_status[str(row["status"])] += duration
        if row["status"] == "dup" and row["duplicate_origin"] == "ledger":
            prior = int(row["duplicate_of_attempt_ordinal"])
            if normalized[prior]["roster_sha256"] != row["roster_sha256"]:
                _fail("duplicate pointer roster differs")
    chains: dict[tuple[str, int], list[dict[str, object]]] = {}
    for row in normalized:
        chains.setdefault(
            (str(row["family"]), int(row["requested_ordinal"])), []
        ).append(row)
    for (family, requested), chain in chains.items():
        retries = [int(row["retry_ordinal"]) for row in chain]
        if retries != list(range(len(chain))):
            _fail(f"{family} request {requested} retry chain differs")
        if any(
            row["status"] not in {"error", "dup", "infeasible"}
            for row in chain[:-1]
        ):
            _fail(f"{family} request {requested} continued after a terminal result")
    for family, count in expected.items():
        if observed_requests[family] != set(range(count)):
            _fail(f"{family} requested-solve census differs")
    body: dict[str, object] = {
        "schema_version": LEDGER_SCHEMA,
        "source_label": source,
        "expected_requests_by_family": dict(sorted(expected.items())),
        "attempt_count": len(normalized),
        "status_counts": dict(sorted(status_counts.items())),
        "duration_seconds_by_family": {
            key: duration_by_family[key] for key in sorted(duration_by_family)
        },
        "duration_seconds_by_status": {
            key: duration_by_status[key] for key in sorted(duration_by_status)
        },
        "total_duration_seconds": float(sum(duration_by_family.values())),
        "rows": normalized,
        "row_manifest_sha256": canonical_sha256(normalized),
        "one_record_or_retry_chain_per_requested_solve": True,
        "hashed_prelock": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["ledger_sha256"] = canonical_sha256(body)
    return body


def validate_ledger(value: object) -> dict[str, object]:
    fields = {
        "schema_version",
        "source_label",
        "expected_requests_by_family",
        "attempt_count",
        "status_counts",
        "duration_seconds_by_family",
        "duration_seconds_by_status",
        "total_duration_seconds",
        "rows",
        "row_manifest_sha256",
        "one_record_or_retry_chain_per_requested_solve",
        "hashed_prelock",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "ledger_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("solve-exposure ledger fields differ")
    item = dict(value)
    retained = item.pop("ledger_sha256")
    if type(retained) is not str or _SHA256.fullmatch(retained) is None:
        _fail("solve-exposure ledger hash differs")
    if canonical_sha256(item) != retained:
        _fail("solve-exposure ledger self-hash differs")
    rows = item["rows"]
    expected = item["expected_requests_by_family"]
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        _fail("solve-exposure ledger rows differ")
    if not isinstance(expected, Mapping):
        _fail("solve-exposure expected census differs")
    rebuilt = build_ledger(
        list(rows),
        source_label=_identifier(item["source_label"], label="source label"),
        expected_requests_by_family={
            str(key): value for key, value in expected.items()
        },
    )
    if rebuilt["ledger_sha256"] != retained or rebuilt != {
        **item,
        "ledger_sha256": retained,
    }:
        _fail("solve-exposure ledger canonical replay differs")
    return rebuilt


__all__ = [
    "ALLOWED_STATUSES",
    "GenerationExposureError",
    "LEDGER_SCHEMA",
    "ROW_SCHEMA",
    "SolveExposureLedger",
    "build_ledger",
    "canonical_json_bytes",
    "canonical_sha256",
    "roster_identity",
    "validate_ledger",
]
