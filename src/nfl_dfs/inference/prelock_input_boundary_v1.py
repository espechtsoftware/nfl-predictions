"""Scoped, fail-closed BigQuery boundary for the lineage shadow.

All production query helpers obtain their client through :mod:`nfl_dfs.bq`.
Inside this synchronous boundary that factory returns a query-only proxy.  It
accepts only SELECT/WITH statements whose backtick-qualified table census is a
subset of the frozen pre-lock allowlist and deliberately exposes no load or
write methods.  The effective-policy source inventory and clean-checkout gate
prevent an unreviewed direct-client bypass from entering the executed source.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Final

from .. import bq
from ..config import settings

BIGQUERY_BOUNDARY_SCHEMA: Final = "prelock-bigquery-read-boundary/v1"
INPUT_READ_MANIFEST_SCHEMA: Final = "prelock-input-read-manifest/v1"
ALLOWED_BIGQUERY_TABLE_URIS: Final = frozenset(
    {
        f"{settings.raw}.dk_salaries",
        f"{settings.raw}.prop_lines",
        f"{settings.raw}.schedules",
        f"{settings.raw}.weekly_stats",
        f"{settings.features}.player_id_map",
        f"{settings.features}.player_week_inference",
        f"{settings.features}.team_defense_week",
    }
)
_TABLE = re.compile(r"`([^`]+)`")
_LEADING_QUERY = re.compile(r"^\s*(?:--[^\n]*\n\s*)*(SELECT|WITH)\b", re.IGNORECASE)
_LOCK = threading.Lock()
_ACTIVE = False


class PrelockInputBoundaryError(ValueError):
    """A read or write escaped the frozen pre-lock input boundary."""


def validate_prelock_bigquery_boundary_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise PrelockInputBoundaryError("BigQuery boundary receipt is not a mapping")
    item = dict(value)
    if item != {
        "schema_version": BIGQUERY_BOUNDARY_SCHEMA,
        "allowed_table_uris": sorted(ALLOWED_BIGQUERY_TABLE_URIS),
        "select_or_with_only": True,
        "bigquery_write_methods_exposed": False,
        "scoped_query_only_client": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }:
        raise PrelockInputBoundaryError("BigQuery boundary receipt differs")
    return item


def build_prelock_input_read_manifest_v1(
    *,
    salary_boundary: Mapping[str, object],
    generation_boundary: Mapping[str, object],
) -> dict[str, object]:
    salary = validate_prelock_bigquery_boundary_v1(salary_boundary)
    generation = validate_prelock_bigquery_boundary_v1(generation_boundary)
    if salary != generation:
        raise PrelockInputBoundaryError("BigQuery boundary activations differ")
    return validate_prelock_input_read_manifest_v1(
        {
            "schema_version": INPUT_READ_MANIFEST_SCHEMA,
            "bigquery_boundary": salary,
            "activation_windows": ["salary-authority", "lineup-generation"],
            "allowed_non_bigquery_roles": [
                "component-model-registry",
                "effective-player-feature-snapshot",
                "role-model-registry",
            ],
            "outcome_sources_allowed": [],
            "closed_before_generation": True,
        }
    )


def validate_prelock_input_read_manifest_v1(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise PrelockInputBoundaryError("input read manifest is not a mapping")
    item = dict(value)
    boundary = validate_prelock_bigquery_boundary_v1(item.get("bigquery_boundary"))
    expected = {
        "schema_version": INPUT_READ_MANIFEST_SCHEMA,
        "bigquery_boundary": boundary,
        "activation_windows": ["salary-authority", "lineup-generation"],
        "allowed_non_bigquery_roles": [
            "component-model-registry",
            "effective-player-feature-snapshot",
            "role-model-registry",
        ],
        "outcome_sources_allowed": [],
        "closed_before_generation": True,
    }
    if item != expected:
        raise PrelockInputBoundaryError("input read manifest differs")
    return item


class _QueryOnlyClient:
    __slots__ = ("_delegate", "_violations")

    def __init__(self, delegate: object, violations: list[str]) -> None:
        self._delegate = delegate
        self._violations = violations

    def _reject(self, message: str) -> None:
        self._violations.append(message)
        raise PrelockInputBoundaryError(message)

    def query(self, sql: str, *args: object, **kwargs: object):
        if type(sql) is not str or _LEADING_QUERY.match(sql) is None:
            self._reject("pre-lock BigQuery boundary accepts SELECT/WITH only")
        tables = set(_TABLE.findall(sql))
        if not tables:
            self._reject("pre-lock BigQuery query has no qualified table authority")
        unknown = tables - ALLOWED_BIGQUERY_TABLE_URIS
        if unknown:
            self._reject(
                f"pre-lock BigQuery query reads outside the allowlist: {sorted(unknown)}"
            )
        return self._delegate.query(sql, *args, **kwargs)


@contextmanager
def enforced_prelock_bigquery_boundary_v1() -> Iterator[dict[str, object]]:
    """Install one synchronous query-only boundary and restore it exactly."""

    global _ACTIVE
    if not _LOCK.acquire(blocking=False):
        raise PrelockInputBoundaryError(
            "pre-lock BigQuery boundary does not permit concurrent activation"
        )
    original_client = bq.client
    violations: list[str] = []
    try:
        if _ACTIVE:
            raise PrelockInputBoundaryError(
                "pre-lock BigQuery boundary is already active"
            )
        _ACTIVE = True

        def _client() -> _QueryOnlyClient:
            return _QueryOnlyClient(original_client(), violations)

        bq.client = _client
        yield validate_prelock_bigquery_boundary_v1(
            {
                "schema_version": BIGQUERY_BOUNDARY_SCHEMA,
                "allowed_table_uris": sorted(ALLOWED_BIGQUERY_TABLE_URIS),
                "select_or_with_only": True,
                "bigquery_write_methods_exposed": False,
                "scoped_query_only_client": True,
                "uses_realized_outcomes": False,
                "post_lock_data_read": False,
            }
        )
    finally:
        bq.client = original_client
        _ACTIVE = False
        _LOCK.release()
        if violations:
            raise PrelockInputBoundaryError(
                "pre-lock BigQuery boundary observed a rejected access: "
                + violations[0]
            )


__all__ = [
    "ALLOWED_BIGQUERY_TABLE_URIS",
    "BIGQUERY_BOUNDARY_SCHEMA",
    "INPUT_READ_MANIFEST_SCHEMA",
    "PrelockInputBoundaryError",
    "build_prelock_input_read_manifest_v1",
    "enforced_prelock_bigquery_boundary_v1",
    "validate_prelock_bigquery_boundary_v1",
    "validate_prelock_input_read_manifest_v1",
]
