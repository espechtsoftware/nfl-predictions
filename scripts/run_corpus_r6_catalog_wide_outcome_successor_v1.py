#!/usr/bin/env python3
"""Default-off, restart-safe operator for the catalog-wide R6 score snapshot.

``prepare`` exact-opens only the later salary catalog and the predecessor
outcome-key projection.  It publishes the catalog projection and immutable
registered query request before any historical-outcome lease is inspected.

``supply`` requires those exact create-once objects, verifies one live lease,
and submits or recovers one deterministic fixed-ID BigQuery job for the exact
projection-minus-predecessor delta.  Publication order is query evidence,
realized source, outcome snapshot, and completion.  Importing this module and
default CLI invocation perform no cloud I/O or query.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
from typing import Final, Protocol


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_catalog_wide_outcome_successor_v1 as successor,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_full_union_outcome_snapshot_v1 as ordinary,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_full_union_outcome_supply_v1 as base_supply,
)
from nfl_dfs.research import corpus_realized_outcome_transport as registered  # noqa: E402
from scripts import run_corpus_r6_full_union_outcome_supply_v1 as base_runner  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLED_ENV: Final = "R6_CATALOG_WIDE_OUTCOME_ENABLED"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = "research/corpus-r6-catalog-wide-realized"
REQUEST_SCHEMA: Final = "corpus-r6-catalog-wide-registered-request/v1"
COMPLETION_SCHEMA: Final = "corpus-r6-catalog-wide-outcome-completion/v1"
_COMPLETION_FIELDS: Final = frozenset({
    "schema_version", "run_id", "outcome_key_projection_identity",
    "registered_request_identity", "query_evidence_identity",
    "realized_source_identity", "outcome_snapshot_identity",
    "historical_outcome_lease_identity", "source_snapshot_at",
    "source_slate_count", "outcome_key_count", "delta_query_key_count",
    "one_historical_outcome_read", "one_exact_query_job",
    "historical_outcome_lease_release_required", "lease_release_owner",
    "lineup_scoring_performed", "graph_mutation_licensed",
    "production_change_licensed", "decision_authority", "complete",
    "completion_sha256",
})

EXPECTED_SOURCE_SLATE_COUNT: Final = 54
EXPECTED_BASE_KEY_COUNT: Final = 14_247
EXPECTED_CATALOG_KEY_COUNT: Final = 29_605
EXPECTED_DELTA_KEY_COUNT: Final = 15_358
SOURCE_SNAPSHOT_AT: Final = "2026-08-26T23:58:47.451523+00:00"

PREDECESSOR_PROJECTION_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-realized/"
        "20260826-foundry-v12-r6-full-union-realized-v2/"
        "outcome-key-projection.json"
    ),
    "generation": "1787777900321498",
    "sha256": "88d292c31caf2b2f8b14f58fcc9cc7973893e0ea21832e02c85e9bc481083d08",
    "bytes": 2_563_921,
}
PREDECESSOR_PROJECTION_SHA256: Final = (
    "3dcaa715ae33db738c703a3da84846b34d4581a550711f8f35daf3dfce0ba16e"
)
BASE_OUTCOME_SNAPSHOT_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-realized/"
        "20260826-foundry-v12-r6-full-union-realized-v2/outcome-snapshot.json"
    ),
    "generation": "1787813630972164",
    "sha256": "3e03387372bb9326d260d951059f8b6bfb56104207d88656ec4ec158c89d54ce",
    "bytes": 1_735_490,
}
BASE_OUTCOME_SNAPSHOT_SHA256: Final = (
    "f518a4c6f634489e91d5e8fdf615b3ae0f8a497463b8592433a1b020b5e3cae4"
)
LATER_SOURCE_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-source/research/source/"
        "20260821-corpus-artifact-source-authority-v3/source/"
        "later-source-freeze.json"
    ),
    "generation": "1787367678830738",
    "sha256": "c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a",
    "bytes": 4_566_802,
}
LATER_SOURCE_SHA256: Final = (
    "841c9121cb7afa5562e4cc8a607bb96f92a96dbae0388a7e63669a1e7bfb8216"
)

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")


class CatalogWideOutcomeOperatorV1Error(RuntimeError):
    """The bounded catalog-wide outcome operator failed closed."""


class ObjectStoreV1(Protocol):
    def read_exact(self, value: Mapping[str, object]) -> bytes: ...

    def resolve_known(
        self, uri: str, *, absent_ok: bool
    ) -> registered.PublishedObject | None: ...

    def resolve_required(self, uri: str) -> registered.PublishedObject: ...

    def publish(self, uri: str, raw: bytes) -> registered.PublishedObject: ...


LeaseVerifier = Callable[[], Mapping[str, object]]
MetadataReader = Callable[[str], Mapping[str, object]]
QueryGetter = Callable[
    [registered.QuerySpec], base_supply.FullUnionOutcomeQueryResultV1
]


@dataclass(frozen=True, slots=True)
class OperatorConfigV1:
    run_id: str
    job: str
    code_sha: str
    image: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"


@dataclass(frozen=True, slots=True)
class QueryRuntimeV1:
    metadata_reader: MetadataReader
    get_or_create_query: QueryGetter


@dataclass(frozen=True, slots=True)
class PreparedV1:
    projection: Mapping[str, object]
    projection_identity: Mapping[str, object]
    request: Mapping[str, object]
    request_identity: Mapping[str, object]
    delta_keys: tuple[Mapping[str, object], ...]
    query_spec: registered.QuerySpec


@dataclass(frozen=True, slots=True)
class SupplyResultV1:
    completion: Mapping[str, object]
    completion_identity: Mapping[str, object]
    recovered_complete: bool


def _fail(message: str) -> None:
    raise CatalogWideOutcomeOperatorV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CatalogWideOutcomeOperatorV1Error(str(exc)) from exc


def _require_config(config: OperatorConfigV1) -> OperatorConfigV1:
    if (
        not isinstance(config, OperatorConfigV1)
        or config.enabled is not True
        or _RUN_ID.fullmatch(config.run_id) is None
        or _JOB.fullmatch(config.job) is None
        or _CODE_SHA.fullmatch(config.code_sha) is None
        or _IMAGE.fullmatch(config.image) is None
    ):
        _fail("catalog-wide outcome operator is disabled or identity differs")
    return config


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CatalogWideOutcomeOperatorV1Error(str(exc)) from exc
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one JSON object")
    return dict(value)


def _read_exact_json(
    store: ObjectStoreV1, identity: Mapping[str, object], *, label: str
) -> dict[str, object]:
    normalized = _identity(identity, label=f"{label} identity")
    return _parse_json(store.read_exact(normalized), label=label)


def _published_identity(
    value: registered.PublishedObject, *, label: str
) -> dict[str, object]:
    receipt = dict(value.receipt)
    try:
        content = {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")}
    except KeyError as exc:
        raise CatalogWideOutcomeOperatorV1Error(
            f"{label} publication receipt lacks a content identity"
        ) from exc
    return _identity(content, label=f"{label} publication identity")


def _publish_json(
    store: ObjectStoreV1, uri: str, body: Mapping[str, object], *, label: str
) -> tuple[dict[str, object], dict[str, object]]:
    raw = successor.canonical_bytes(body)
    published = store.publish(uri, raw)
    if published.reopened_raw != raw:
        _fail(f"{label} create-once reopen differs")
    return dict(body), _published_identity(published, label=label)


def _known_json(
    store: ObjectStoreV1, uri: str, *, label: str
) -> tuple[dict[str, object], dict[str, object]] | None:
    value = store.resolve_known(uri, absent_ok=True)
    if value is None:
        return None
    return (
        _parse_json(value.reopened_raw, label=label),
        _published_identity(value, label=label),
    )


def _projection_uri(config: OperatorConfigV1) -> str:
    return f"{config.output_root}/outcome-key-projection.json"


def _request_uri(config: OperatorConfigV1) -> str:
    return f"{config.output_root}/registered-request.json"


def _query_evidence_uri(config: OperatorConfigV1) -> str:
    return f"{config.output_root}/query-evidence.json"


def _source_uri(config: OperatorConfigV1) -> str:
    return f"{config.output_root}/realized-source.json"


def _snapshot_uri(config: OperatorConfigV1) -> str:
    return f"{config.output_root}/outcome-snapshot.json"


def _completion_uri(config: OperatorConfigV1) -> str:
    return f"{config.output_root}/completion.json"


def _projection_minus_base_keys_v1(
    projection: Mapping[str, object], predecessor: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    rows = projection.get("outcome_keys")
    base_rows = predecessor.get("outcome_keys")
    if (
        not isinstance(rows, Sequence)
        or isinstance(rows, (str, bytes))
        or not isinstance(base_rows, Sequence)
        or isinstance(base_rows, (str, bytes))
        or projection.get("source_slate_count") != EXPECTED_SOURCE_SLATE_COUNT
        or projection.get("outcome_key_count") != EXPECTED_CATALOG_KEY_COUNT
        or predecessor.get("source_slate_count") != EXPECTED_SOURCE_SLATE_COUNT
        or predecessor.get("outcome_key_count") != EXPECTED_BASE_KEY_COUNT
    ):
        _fail("catalog/base outcome-key census differs")
    base_keys = {
        (row.get("source_ordinal"), row.get("player_id"))
        for row in base_rows
        if isinstance(row, Mapping)
    }
    if len(base_keys) != EXPECTED_BASE_KEY_COUNT:
        _fail("predecessor outcome-key projection contains duplicates")
    projected_keys = {
        (row.get("source_ordinal"), row.get("player_id"))
        for row in rows
        if isinstance(row, Mapping)
    }
    if len(projected_keys) != EXPECTED_CATALOG_KEY_COUNT or not base_keys <= projected_keys:
        _fail("catalog projection does not contain the exact predecessor key set")
    result = tuple(
        {key: row[key] for key in ("season", "week", "source_kind", "source_key")}
        for row in rows
        if isinstance(row, Mapping)
        and (row.get("source_ordinal"), row.get("player_id")) not in base_keys
    )
    query_keys = {
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in result
    }
    if len(result) != EXPECTED_DELTA_KEY_COUNT or len(query_keys) != len(result):
        _fail("projection-minus-base key census is not exactly 15,358")
    return result


def _outcome_keys_for_query(
    projection: Mapping[str, object], predecessor: Mapping[str, object]
) -> tuple[registered.OutcomeKey, ...]:
    base_rows = predecessor["outcome_keys"]
    base_keys = {(row["source_ordinal"], row["player_id"]) for row in base_rows}
    return tuple(
        registered.OutcomeKey(
            task_index=int(row["source_ordinal"]),
            season=int(row["season"]),
            week=int(row["week"]),
            slate_id=str(row["slate_id"]),
            player_id=str(row["player_id"]),
            source_kind=str(row["source_kind"]),
            source_key=str(row["source_key"]),
        )
        for row in projection["outcome_keys"]
        if (row["source_ordinal"], row["player_id"]) not in base_keys
    )


def _query_spec_v1(
    config: OperatorConfigV1,
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    predecessor: Mapping[str, object],
) -> registered.QuerySpec:
    supplier = registered.SupplierConfig(
        run_id=config.run_id,
        job=config.job,
        code_sha=config.code_sha,
        image=config.image,
        expected_batch_acceptance_object_sha256=str(projection_identity["sha256"]),
        enabled=True,
    )
    return registered.build_query_spec(
        config=supplier,
        outcome_keys=_outcome_keys_for_query(projection, predecessor),
        source_snapshot_at=SOURCE_SNAPSHOT_AT,
    )


def _query_contract_v1(spec: registered.QuerySpec) -> dict[str, object]:
    return {
        "job_id": spec.job_id,
        "location": spec.location,
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "union_keys_sha256": spec.union_keys_sha256,
        "tables": [registered.SKILL_TABLE, registered.DST_TABLE],
        "selected_columns": list(registered.QUERY_ROW_FIELDS),
        "source_snapshot_at": SOURCE_SNAPSHOT_AT,
        "query_count": 1,
        "use_query_cache": False,
    }


def _build_registered_request_v1(
    *,
    config: OperatorConfigV1,
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    predecessor: Mapping[str, object],
) -> tuple[dict[str, object], tuple[dict[str, object], ...], registered.QuerySpec]:
    delta = _projection_minus_base_keys_v1(projection, predecessor)
    spec = _query_spec_v1(config, projection, projection_identity, predecessor)
    body: dict[str, object] = {
        "schema_version": REQUEST_SCHEMA,
        "run_id": config.run_id,
        "output_root": config.output_root,
        "job": config.job,
        "code_sha": config.code_sha,
        "image": config.image,
        "outcome_key_projection_identity": dict(projection_identity),
        "outcome_key_projection_sha256": projection["outcome_key_projection_sha256"],
        "predecessor_projection_identity": dict(PREDECESSOR_PROJECTION_IDENTITY),
        "predecessor_projection_sha256": PREDECESSOR_PROJECTION_SHA256,
        "base_outcome_snapshot_identity": dict(BASE_OUTCOME_SNAPSHOT_IDENTITY),
        "base_outcome_snapshot_sha256": BASE_OUTCOME_SNAPSHOT_SHA256,
        "later_source_freeze_identity": dict(LATER_SOURCE_IDENTITY),
        "later_source_freeze_sha256": LATER_SOURCE_SHA256,
        "source_snapshot_at": SOURCE_SNAPSHOT_AT,
        "queried_keys": list(delta),
        "queried_key_count": len(delta),
        "queried_keys_sha256": successor.digest(delta),
        "query_contract": _query_contract_v1(spec),
        "historical_outcome_lease_required": True,
        "query_execution_performed": False,
        "uses_realized_outcomes": False,
        "complete": True,
    }
    body["registered_request_sha256"] = successor.digest(body)
    return body, delta, spec


def _validate_registered_request_v1(
    value: Mapping[str, object], *, expected: Mapping[str, object]
) -> dict[str, object]:
    retained = dict(value)
    if (
        retained != dict(expected)
        or retained.get("registered_request_sha256")
        != successor.digest(
            {key: item for key, item in retained.items() if key != "registered_request_sha256"}
        )
        or retained.get("source_snapshot_at") != SOURCE_SNAPSHOT_AT
        or retained.get("queried_key_count") != EXPECTED_DELTA_KEY_COUNT
        or retained.get("query_execution_performed") is not False
        or retained.get("uses_realized_outcomes") is not False
        or retained.get("complete") is not True
    ):
        _fail("registered catalog-wide query request differs")
    return retained


def _build_outcome_blind_projection_v1(
    *, store: ObjectStoreV1
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    later_source = _read_exact_json(store, LATER_SOURCE_IDENTITY, label="later-source freeze")
    predecessor = _read_exact_json(
        store, PREDECESSOR_PROJECTION_IDENTITY, label="predecessor projection"
    )
    try:
        retained_later = successor.later.validate_source_freeze(
            later_source, expected_freeze_sha256=LATER_SOURCE_SHA256
        )
        parsed_predecessor, predecessor_keys = ordinary._parse_projection_keys(  # noqa: SLF001
            predecessor
        )
    except Exception as exc:
        raise CatalogWideOutcomeOperatorV1Error(str(exc)) from exc
    if (
        parsed_predecessor.get("outcome_key_projection_sha256")
        != PREDECESSOR_PROJECTION_SHA256
        or parsed_predecessor.get("later_source_freeze_identity")
        != dict(LATER_SOURCE_IDENTITY)
        or parsed_predecessor.get("later_source_freeze_sha256") != LATER_SOURCE_SHA256
        or len(predecessor_keys) != EXPECTED_BASE_KEY_COUNT
    ):
        _fail("predecessor projection authority differs")
    rows = successor._catalog_projection(retained_later)  # noqa: SLF001
    body: dict[str, object] = {
        "schema_version": successor.PROJECTION_SCHEMA,
        "later_source_freeze_identity": dict(LATER_SOURCE_IDENTITY),
        "later_source_freeze_sha256": LATER_SOURCE_SHA256,
        "base_outcome_snapshot_identity": dict(BASE_OUTCOME_SNAPSHOT_IDENTITY),
        "base_outcome_snapshot_sha256": BASE_OUTCOME_SNAPSHOT_SHA256,
        "source_slate_count": EXPECTED_SOURCE_SLATE_COUNT,
        "outcome_key_count": len(rows),
        "outcome_keys": rows,
        "outcome_keys_sha256": successor.digest(rows),
        "complete": True,
        "uses_realized_outcomes": False,
    }
    body["outcome_key_projection_sha256"] = successor.digest(body)
    if len(rows) != EXPECTED_CATALOG_KEY_COUNT:
        _fail("catalog projection is not exactly 29,605 keys")
    temporary_identity = batch.object_identity_for_json(
        body, uri="gs://validation/catalog-projection.json", generation="1"
    )
    successor.validate_catalog_wide_projection_v1(
        body,
        identity=temporary_identity,
        later_source=retained_later,
        later_source_identity=LATER_SOURCE_IDENTITY,
        later_source_sha256=LATER_SOURCE_SHA256,
    )
    _projection_minus_base_keys_v1(body, predecessor)
    return body, predecessor, retained_later


def _publish_prepared_v1(
    *,
    config: OperatorConfigV1,
    store: ObjectStoreV1,
    projection: Mapping[str, object],
    predecessor: Mapping[str, object],
) -> PreparedV1:
    projection_body, projection_identity = _publish_json(
        store, _projection_uri(config), projection, label="catalog-wide projection"
    )
    request, delta, spec = _build_registered_request_v1(
        config=config,
        projection=projection_body,
        projection_identity=projection_identity,
        predecessor=predecessor,
    )
    _validate_registered_request_v1(request, expected=request)
    request_body, request_identity = _publish_json(
        store, _request_uri(config), request, label="registered query request"
    )
    return PreparedV1(
        projection=projection_body,
        projection_identity=projection_identity,
        request=request_body,
        request_identity=request_identity,
        delta_keys=delta,
        query_spec=spec,
    )


def prepare_v1(*, config: OperatorConfigV1, store: ObjectStoreV1) -> PreparedV1:
    """Publish projection then request without constructing a lease or query."""
    retained = _require_config(config)
    projection, predecessor, _ = _build_outcome_blind_projection_v1(store=store)
    return _publish_prepared_v1(
        config=retained, store=store, projection=projection, predecessor=predecessor
    )


def _load_prepared_v1(
    *, config: OperatorConfigV1, store: ObjectStoreV1
) -> tuple[PreparedV1, dict[str, object]]:
    expected_projection, predecessor, later_source = _build_outcome_blind_projection_v1(
        store=store
    )
    projection_known = _known_json(
        store, _projection_uri(config), label="catalog-wide projection"
    )
    if projection_known is None:
        _fail("catalog-wide projection must be prepared before lease acquisition")
    projection, projection_identity = projection_known
    if projection != expected_projection:
        _fail("persisted catalog-wide projection differs from outcome-blind replay")
    successor.validate_catalog_wide_projection_v1(
        projection,
        identity=projection_identity,
        later_source=later_source,
        later_source_identity=LATER_SOURCE_IDENTITY,
        later_source_sha256=LATER_SOURCE_SHA256,
    )
    expected_request, delta, spec = _build_registered_request_v1(
        config=config,
        projection=projection,
        projection_identity=projection_identity,
        predecessor=predecessor,
    )
    request_known = _known_json(store, _request_uri(config), label="registered request")
    if request_known is None:
        _fail("registered request must be prepared before lease acquisition")
    request, request_identity = request_known
    _validate_registered_request_v1(request, expected=expected_request)
    return (
        PreparedV1(
            projection=projection,
            projection_identity=projection_identity,
            request=request,
            request_identity=request_identity,
            delta_keys=delta,
            query_spec=spec,
        ),
        later_source,
    )


def _query_outcome_keys(
    prepared: PreparedV1,
) -> tuple[ordinary.OutcomeKeyV1, ...]:
    wanted = {
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in prepared.delta_keys
    }
    rows = [
        ordinary.OutcomeKeyV1(
            source_ordinal=int(row["source_ordinal"]),
            season=int(row["season"]),
            week=int(row["week"]),
            slate_id=str(row["slate_id"]),
            player_id=str(row["player_id"]),
            position=str(row["position"]),
            team=str(row["team"]),
            source_kind=str(row["source_kind"]),
            source_key=str(row["source_key"]),
        )
        for row in prepared.projection["outcome_keys"]
        if (row["season"], row["week"], row["source_kind"], row["source_key"])
        in wanted
    ]
    rows.sort(
        key=lambda row: (row.season, row.week, row.source_kind, row.source_key)
    )
    return tuple(rows)


def _normalize_query_rows_v1(
    rows: object, *, prepared: PreparedV1
) -> tuple[list[dict[str, object]], dict[str, object]]:
    try:
        normalized = base_supply._registered_integer_micro_rows(  # noqa: SLF001
            rows, outcome_keys=_query_outcome_keys(prepared)
        )
    except Exception as exc:
        raise CatalogWideOutcomeOperatorV1Error(str(exc)) from exc
    missing = {
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in normalized.synthesized_skill_keys
    }
    observed = [
        dict(row)
        for row in normalized.rows
        if (row["season"], row["week"], row["source_kind"], row["source_key"])
        not in missing
    ]
    if len(observed) != normalized.observed_integer_micro_row_count:
        _fail("normalized observed query-row census differs")
    zero_evidence = {
        "skill_zero_completion_law": normalized.skill_zero_completion_law,
        "skill_zero_law_source_sha256": normalized.skill_zero_law_source_sha256,
        "salary_catalog_settlement_bridge": normalized.salary_catalog_settlement_bridge,
        "salary_catalog_bridge_source_sha256": (
            normalized.salary_catalog_bridge_source_sha256
        ),
    }
    return observed, zero_evidence


def _validate_query_receipt_v1(
    result: base_supply.FullUnionOutcomeQueryResultV1,
    *, spec: registered.QuerySpec,
) -> None:
    receipt = result.result.job_receipt
    if (
        result.disposition not in {"created", "recovered"}
        or not isinstance(receipt, Mapping)
        or receipt.get("job_id") != spec.job_id
        or receipt.get("location") != spec.location
        or receipt.get("sql_sha256") != spec.sql_sha256
        or receipt.get("parameters_sha256") != spec.parameters_sha256
        or receipt.get("cache_hit") is not False
        or receipt.get("error_result") is not None
    ):
        _fail("fixed-ID BigQuery result receipt differs")


def _query_evidence_body_v1(
    *,
    prepared: PreparedV1,
    rows: Sequence[Mapping[str, object]],
    table_before: Sequence[Mapping[str, object]],
    table_after: Sequence[Mapping[str, object]],
    lease_before: Mapping[str, object],
    lease_after: Mapping[str, object],
) -> dict[str, object]:
    compact_contract = {
        "query_count": 1,
        "use_query_cache": False,
        "source_snapshot_at": SOURCE_SNAPSHOT_AT,
    }
    body: dict[str, object] = {
        "schema_version": successor.QUERY_EVIDENCE_SCHEMA,
        "outcome_key_projection_identity": dict(prepared.projection_identity),
        "outcome_key_projection_sha256": prepared.projection[
            "outcome_key_projection_sha256"
        ],
        "queried_keys": list(prepared.delta_keys),
        "queried_key_count": len(prepared.delta_keys),
        "queried_keys_sha256": successor.digest(prepared.delta_keys),
        "registered_request": {
            "outcome_key_projection_identity": dict(prepared.projection_identity),
            "outcome_key_projection_sha256": prepared.projection[
                "outcome_key_projection_sha256"
            ],
        },
        "query_contract": compact_contract,
        "query_job_receipt": {"cache_hit": False, "complete": True},
        "source_snapshot_at": SOURCE_SNAPSHOT_AT,
        "table_receipts_before_query": [dict(row) for row in table_before],
        "table_receipts_after_query": [dict(row) for row in table_after],
        "table_receipt_set_sha256": successor.digest(table_before),
        "historical_outcome_lease_before_query": dict(lease_before),
        "historical_outcome_lease_after_query": dict(lease_after),
        "historical_outcome_lease_sha256": successor.digest(lease_before),
        "row_fields": sorted(successor._REGISTERED_FIELDS),  # noqa: SLF001
        "row_count": len(rows),
        "rows": [dict(row) for row in rows],
        "rows_sha256": successor.digest(rows),
        "one_exact_query": True,
        "query_cache_used": False,
        "table_metadata_stable_during_query": table_before == table_after,
        "historical_outcome_lease_unchanged_during_query": lease_before == lease_after,
        "complete": True,
    }
    body["query_evidence_sha256"] = successor.digest(body)
    return body


def _lease_identity(value: Mapping[str, object]) -> dict[str, object]:
    receipt = value.get("object_receipt")
    if not isinstance(receipt, Mapping):
        _fail("historical-outcome lease verifier receipt differs")
    return _identity(
        {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
        label="historical-outcome lease",
    )


def _build_completion_v1(
    *,
    config: OperatorConfigV1,
    prepared: PreparedV1,
    query_evidence_identity: Mapping[str, object],
    source_identity: Mapping[str, object],
    snapshot_identity: Mapping[str, object],
    lease_identity: Mapping[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": COMPLETION_SCHEMA,
        "run_id": config.run_id,
        "outcome_key_projection_identity": dict(prepared.projection_identity),
        "registered_request_identity": dict(prepared.request_identity),
        "query_evidence_identity": dict(query_evidence_identity),
        "realized_source_identity": dict(source_identity),
        "outcome_snapshot_identity": dict(snapshot_identity),
        "historical_outcome_lease_identity": dict(lease_identity),
        "source_snapshot_at": SOURCE_SNAPSHOT_AT,
        "source_slate_count": EXPECTED_SOURCE_SLATE_COUNT,
        "outcome_key_count": EXPECTED_CATALOG_KEY_COUNT,
        "delta_query_key_count": EXPECTED_DELTA_KEY_COUNT,
        "one_historical_outcome_read": True,
        "one_exact_query_job": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": registered.LEASE_RELEASE_OWNER,
        "lineup_scoring_performed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
        "complete": True,
    }
    body["completion_sha256"] = successor.digest(body)
    return body


def _validate_completion_v1(
    value: Mapping[str, object], *, config: OperatorConfigV1, prepared: PreparedV1
) -> dict[str, object]:
    retained = dict(value)
    identity_fields = (
        "query_evidence_identity",
        "realized_source_identity",
        "outcome_snapshot_identity",
        "historical_outcome_lease_identity",
    )
    if (
        frozenset(retained) != _COMPLETION_FIELDS
        or retained.get("schema_version") != COMPLETION_SCHEMA
        or retained.get("run_id") != config.run_id
        or retained.get("outcome_key_projection_identity")
        != dict(prepared.projection_identity)
        or retained.get("registered_request_identity") != dict(prepared.request_identity)
        or retained.get("source_snapshot_at") != SOURCE_SNAPSHOT_AT
        or retained.get("source_slate_count") != EXPECTED_SOURCE_SLATE_COUNT
        or retained.get("outcome_key_count") != EXPECTED_CATALOG_KEY_COUNT
        or retained.get("delta_query_key_count") != EXPECTED_DELTA_KEY_COUNT
        or any(not isinstance(retained.get(field), Mapping) for field in identity_fields)
        or retained.get("one_historical_outcome_read") is not True
        or retained.get("one_exact_query_job") is not True
        or retained.get("historical_outcome_lease_release_required") is not True
        or retained.get("lease_release_owner") != registered.LEASE_RELEASE_OWNER
        or any(
            retained.get(field) is not False
            for field in (
                "lineup_scoring_performed",
                "graph_mutation_licensed",
                "production_change_licensed",
                "decision_authority",
            )
        )
        or retained.get("complete") is not True
        or retained.get("completion_sha256")
        != successor.digest(
            {key: item for key, item in retained.items() if key != "completion_sha256"}
        )
    ):
        _fail("catalog-wide completion differs")
    expected_uris = {
        "query_evidence_identity": _query_evidence_uri(config),
        "realized_source_identity": _source_uri(config),
        "outcome_snapshot_identity": _snapshot_uri(config),
    }
    for field, uri in expected_uris.items():
        if _identity(retained[field], label=field)["uri"] != uri:
            _fail(f"{field} URI differs")
    lease_identity = _identity(
        retained["historical_outcome_lease_identity"], label="completion lease"
    )
    if lease_identity["uri"] != base_runner.shared.adapter.HISTORICAL_OUTCOME_LEASE_URI:
        _fail("completion historical-outcome lease URI differs")
    return retained


def _current_exact_json_v1(
    *,
    store: ObjectStoreV1,
    identity: Mapping[str, object],
    expected_uri: str,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    expected_identity = _identity(identity, label=f"{label} completion identity")
    if expected_identity["uri"] != expected_uri:
        _fail(f"{label} completion URI differs")
    current = _known_json(store, expected_uri, label=label)
    if current is None or current[1] != expected_identity:
        _fail(f"{label} completion identity is not the exact current object")
    exact = _read_exact_json(store, expected_identity, label=f"exact {label}")
    if exact != current[0]:
        _fail(f"{label} current/exact generation replay differs")
    return exact, expected_identity


def _expected_snapshot_v1(
    *,
    prepared: PreparedV1,
    later_source: Mapping[str, object],
    base_snapshot: Mapping[str, object],
    evidence: Mapping[str, object],
    evidence_identity: Mapping[str, object],
    source: Mapping[str, object],
    source_identity: Mapping[str, object],
) -> dict[str, object]:
    return successor.build_catalog_wide_snapshot_v1(
        projection=prepared.projection,
        projection_identity=prepared.projection_identity,
        later_source=later_source,
        later_source_identity=LATER_SOURCE_IDENTITY,
        later_source_sha256=LATER_SOURCE_SHA256,
        base_snapshot=base_snapshot,
        base_snapshot_identity=BASE_OUTCOME_SNAPSHOT_IDENTITY,
        base_snapshot_sha256=BASE_OUTCOME_SNAPSHOT_SHA256,
        realized_source=source,
        realized_source_identity=source_identity,
        query_evidence=evidence,
        query_evidence_identity=evidence_identity,
    )


def _replay_completed_chain_v1(
    *,
    config: OperatorConfigV1,
    store: ObjectStoreV1,
    prepared: PreparedV1,
    later_source: Mapping[str, object],
    completion: Mapping[str, object],
) -> None:
    base_snapshot = _read_exact_json(
        store, BASE_OUTCOME_SNAPSHOT_IDENTITY, label="base outcome snapshot"
    )
    if base_snapshot.get("outcome_snapshot_sha256") != BASE_OUTCOME_SNAPSHOT_SHA256:
        _fail("base outcome snapshot internal SHA differs")
    evidence, evidence_identity = _current_exact_json_v1(
        store=store,
        identity=completion["query_evidence_identity"],
        expected_uri=_query_evidence_uri(config),
        label="catalog-wide query evidence",
    )
    successor.validate_catalog_wide_query_evidence_v1(
        evidence,
        identity=evidence_identity,
        projection=prepared.projection,
        projection_identity=prepared.projection_identity,
        base_snapshot=base_snapshot,
    )
    source, source_identity = _current_exact_json_v1(
        store=store,
        identity=completion["realized_source_identity"],
        expected_uri=_source_uri(config),
        label="catalog-wide realized source",
    )
    successor.validate_catalog_wide_realized_source_v1(
        source,
        identity=source_identity,
        projection=prepared.projection,
        projection_identity=prepared.projection_identity,
        base_snapshot=base_snapshot,
        query_evidence=evidence,
        query_evidence_identity=evidence_identity,
    )
    snapshot, snapshot_identity = _current_exact_json_v1(
        store=store,
        identity=completion["outcome_snapshot_identity"],
        expected_uri=_snapshot_uri(config),
        label="catalog-wide outcome snapshot",
    )
    expected_snapshot = _expected_snapshot_v1(
        prepared=prepared,
        later_source=later_source,
        base_snapshot=base_snapshot,
        evidence=evidence,
        evidence_identity=evidence_identity,
        source=source,
        source_identity=source_identity,
    )
    if successor.canonical_bytes(snapshot) != successor.canonical_bytes(expected_snapshot):
        _fail("persisted outcome snapshot differs from exact recovered-chain replay")
    successor.validate_catalog_wide_snapshot_v1(snapshot, identity=snapshot_identity)


def supply_v1(
    *,
    config: OperatorConfigV1,
    store: ObjectStoreV1,
    lease_verifier: LeaseVerifier,
    query_runtime_factory: Callable[[], QueryRuntimeV1],
) -> SupplyResultV1:
    """Finish or recover the one-query chain; never creates a second job ID."""
    retained = _require_config(config)
    prepared, later_source = _load_prepared_v1(config=retained, store=store)

    existing_completion = _known_json(
        store, _completion_uri(retained), label="catalog-wide completion"
    )
    if existing_completion is not None:
        body, identity = existing_completion
        retained_completion = _validate_completion_v1(
            body, config=retained, prepared=prepared
        )
        _replay_completed_chain_v1(
            config=retained,
            store=store,
            prepared=prepared,
            later_source=later_source,
            completion=retained_completion,
        )
        return SupplyResultV1(
            completion=retained_completion,
            completion_identity=identity,
            recovered_complete=True,
        )

    if not callable(lease_verifier) or not callable(query_runtime_factory):
        _fail("lease/query runtime boundary differs")
    lease_before = dict(lease_verifier())
    retained_lease_identity = _lease_identity(lease_before)

    # This is the first outcome-bearing object opened by the operator.
    base_snapshot = _read_exact_json(
        store, BASE_OUTCOME_SNAPSHOT_IDENTITY, label="base outcome snapshot"
    )
    if base_snapshot.get("outcome_snapshot_sha256") != BASE_OUTCOME_SNAPSHOT_SHA256:
        _fail("base outcome snapshot internal SHA differs")

    existing_evidence = _known_json(
        store, _query_evidence_uri(retained), label="catalog-wide query evidence"
    )
    if existing_evidence is None:
        runtime = query_runtime_factory()
        table_before = [
            dict(runtime.metadata_reader(table))
            for table in (registered.SKILL_TABLE, registered.DST_TABLE)
        ]
        result = runtime.get_or_create_query(prepared.query_spec)
        _validate_query_receipt_v1(result, spec=prepared.query_spec)
        lease_after = dict(lease_verifier())
        table_after = [
            dict(runtime.metadata_reader(table))
            for table in (registered.SKILL_TABLE, registered.DST_TABLE)
        ]
        if lease_before != lease_after or table_before != table_after:
            _fail("lease or source table metadata changed during the exact query")
        observed_rows, zero_evidence = _normalize_query_rows_v1(
            result.result.rows, prepared=prepared
        )
        evidence = _query_evidence_body_v1(
            prepared=prepared,
            rows=observed_rows,
            table_before=table_before,
            table_after=table_after,
            lease_before=lease_before,
            lease_after=lease_after,
        )
        temporary_identity = batch.object_identity_for_json(
            evidence, uri=_query_evidence_uri(retained), generation="1"
        )
        successor.validate_catalog_wide_query_evidence_v1(
            evidence,
            identity=temporary_identity,
            projection=prepared.projection,
            projection_identity=prepared.projection_identity,
            base_snapshot=base_snapshot,
        )
        evidence, evidence_identity = _publish_json(
            store,
            _query_evidence_uri(retained),
            evidence,
            label="catalog-wide query evidence",
        )
    else:
        evidence, evidence_identity = existing_evidence
        _, _, observed_rows = successor.validate_catalog_wide_query_evidence_v1(
            evidence,
            identity=evidence_identity,
            projection=prepared.projection,
            projection_identity=prepared.projection_identity,
            base_snapshot=base_snapshot,
        )
        lease_after = dict(lease_verifier())
        if lease_before != lease_after:
            _fail("historical-outcome lease changed while recovering evidence")
        zero_evidence = {
            "skill_zero_completion_law": successor.ZERO_LAW,
            "skill_zero_law_source_sha256": successor.ZERO_LAW_SOURCE_SHA256,
            "salary_catalog_settlement_bridge": successor.ZERO_BRIDGE,
            "salary_catalog_bridge_source_sha256": successor.ZERO_BRIDGE_SOURCE_SHA256,
        }

    query_provenance = {
        "source_snapshot_at": evidence["source_snapshot_at"],
        "query_contract": evidence["query_contract"],
        "query_job_receipt": evidence["query_job_receipt"],
    }
    existing_source = _known_json(
        store, _source_uri(retained), label="catalog-wide realized source"
    )
    if existing_source is None:
        source = successor.build_catalog_wide_realized_source_v1(
            projection=prepared.projection,
            projection_identity=prepared.projection_identity,
            later_source=later_source,
            later_source_identity=LATER_SOURCE_IDENTITY,
            later_source_sha256=LATER_SOURCE_SHA256,
            base_snapshot=base_snapshot,
            base_snapshot_identity=BASE_OUTCOME_SNAPSHOT_IDENTITY,
            base_snapshot_sha256=BASE_OUTCOME_SNAPSHOT_SHA256,
            delta_registered_rows=observed_rows,
            query_evidence=evidence,
            query_evidence_identity=evidence_identity,
            query_provenance=query_provenance,
            zero_evidence=zero_evidence,
        )
        source, source_identity = _publish_json(
            store, _source_uri(retained), source, label="catalog-wide realized source"
        )
    else:
        source, source_identity = existing_source
        successor.validate_catalog_wide_realized_source_v1(
            source,
            identity=source_identity,
            projection=prepared.projection,
            projection_identity=prepared.projection_identity,
            base_snapshot=base_snapshot,
            query_evidence=evidence,
            query_evidence_identity=evidence_identity,
        )

    expected_snapshot = _expected_snapshot_v1(
        prepared=prepared,
        later_source=later_source,
        base_snapshot=base_snapshot,
        evidence=evidence,
        evidence_identity=evidence_identity,
        source=source,
        source_identity=source_identity,
    )
    existing_snapshot = _known_json(
        store, _snapshot_uri(retained), label="catalog-wide outcome snapshot"
    )
    if existing_snapshot is None:
        snapshot = expected_snapshot
        snapshot, snapshot_identity = _publish_json(
            store,
            _snapshot_uri(retained),
            snapshot,
            label="catalog-wide outcome snapshot",
        )
    else:
        snapshot, snapshot_identity = existing_snapshot
        if successor.canonical_bytes(snapshot) != successor.canonical_bytes(
            expected_snapshot
        ):
            _fail("persisted outcome snapshot differs from exact recovered-chain replay")
        successor.validate_catalog_wide_snapshot_v1(snapshot, identity=snapshot_identity)

    completion = _build_completion_v1(
        config=retained,
        prepared=prepared,
        query_evidence_identity=evidence_identity,
        source_identity=source_identity,
        snapshot_identity=snapshot_identity,
        lease_identity=retained_lease_identity,
    )
    completion, completion_identity = _publish_json(
        store,
        _completion_uri(retained),
        completion,
        label="catalog-wide completion",
    )
    _validate_completion_v1(completion, config=retained, prepared=prepared)
    return SupplyResultV1(
        completion=completion,
        completion_identity=completion_identity,
        recovered_complete=False,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "supply"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--lease-generation")
    parser.add_argument("--lease-sha256")
    parser.add_argument("--lease-bytes", type=int)
    return parser


def _cli_config(args: argparse.Namespace) -> OperatorConfigV1:
    config = OperatorConfigV1(
        run_id=args.run_id,
        job=args.job,
        code_sha=args.code_sha,
        image=args.image,
        enabled=args.execute and os.environ.get(ENABLED_ENV) == "1",
    )
    return _require_config(config)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = _cli_config(args)
    from google.cloud import bigquery, storage

    store = base_runner.GenerationPinnedGCSV1(storage.Client(project=PROJECT))
    if args.operation == "prepare":
        prepared = prepare_v1(config=config, store=store)
        output = {
            "operation": "prepare",
            "projection_identity": dict(prepared.projection_identity),
            "registered_request_identity": dict(prepared.request_identity),
            "delta_query_key_count": len(prepared.delta_keys),
            "source_snapshot_at": SOURCE_SNAPSHOT_AT,
            "historical_outcome_lease_inspected": False,
            "query_performed": False,
        }
    else:
        if (
            args.lease_generation is None
            or args.lease_sha256 is None
            or args.lease_bytes is None
        ):
            _fail("supply requires the exact expected historical lease identity")
        expected_lease = {
            "uri": base_runner.shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
            "generation": args.lease_generation,
            "sha256": args.lease_sha256,
            "bytes": args.lease_bytes,
        }
        verifier = base_runner.LiveLeaseVerifierV1(
            store, expected_identity=expected_lease
        )

        def runtime_factory() -> QueryRuntimeV1:
            client = bigquery.Client(project=PROJECT, location=registered.LOCATION)
            return QueryRuntimeV1(
                metadata_reader=lambda table: base_runner._table_metadata(client, table),
                get_or_create_query=lambda spec: base_runner._get_or_create_query(
                    client, spec
                ),
            )

        result = supply_v1(
            config=config,
            store=store,
            lease_verifier=verifier,
            query_runtime_factory=runtime_factory,
        )
        output = {
            "operation": "supply",
            "completion_identity": dict(result.completion_identity),
            "recovered_complete": result.recovered_complete,
            "historical_outcome_lease_release_required": result.completion[
                "historical_outcome_lease_release_required"
            ],
            "lease_release_owner": result.completion["lease_release_owner"],
        }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BASE_OUTCOME_SNAPSHOT_IDENTITY",
    "CatalogWideOutcomeOperatorV1Error",
    "EXPECTED_DELTA_KEY_COUNT",
    "OperatorConfigV1",
    "PreparedV1",
    "QueryRuntimeV1",
    "SOURCE_SNAPSHOT_AT",
    "SupplyResultV1",
    "prepare_v1",
    "supply_v1",
]
