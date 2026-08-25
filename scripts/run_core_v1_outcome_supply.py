#!/usr/bin/env python3
"""Default-off cloud runner for the recoverable Core v1 outcome snapshot.

The runner resolves one deterministic sharded-catalog root by known name,
exact-replays its logical catalog and later-source freeze, and lazily verifies
the live historical-outcome lease only if the durable transaction still needs
its one query.  It uses no object listing. Standard output contains one compact
receipt and never score rows.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import corpus_core_v1_outcome_supply as supply  # noqa: E402
from nfl_dfs.research import corpus_core_v1_catalog_materializer as catalog_store  # noqa: E402
from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import corpus_realized_outcome_transport as registered  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as shared  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLED_ENV: Final = "CORE_V1_OUTCOME_SUPPLY_ENABLED"
RECEIPT_SCHEMA: Final = "core-v1-outcome-supply-cloud-receipt/v1"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")


class CoreV1OutcomeRunnerError(RuntimeError):
    """The executable Core v1 historical-outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class CoreOutcomeCloudResult:
    supply: supply.CoreOutcomeSupply
    catalog_root_identity: Mapping[str, object]
    catalog_identity: Mapping[str, object]
    source_freeze_identity: Mapping[str, object]
    historical_lease_identity: Mapping[str, object]


def _fail(message: str) -> None:
    raise CoreV1OutcomeRunnerError(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1OutcomeRunnerError(str(exc)) from exc


def _gcs_parts(uri: str) -> tuple[str, str]:
    identity = _identity(
        {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
        label="Core v1 outcome object URI",
    )
    bucket, name = str(identity["uri"]).removeprefix("gs://").split("/", 1)
    return bucket, name


def _generation(value: object, *, label: str) -> str:
    if type(value) is int and value >= 1:
        return str(value)
    if type(value) is str and value.isdigit() and not value.startswith("0"):
        return value
    _fail(f"{label} generation differs")


def _iso(value: object, *, label: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        _fail(f"{label} timestamp differs")
    return value.astimezone(timezone.utc).isoformat()


def _is_not_found(exc: Exception) -> bool:
    try:
        from google.api_core.exceptions import NotFound
    except ImportError:
        return type(exc).__name__ == "NotFound"
    return isinstance(exc, NotFound) or type(exc).__name__ == "NotFound"


def _json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1OutcomeRunnerError(str(exc)) from exc
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one JSON object")
    return dict(value)


class GenerationPinnedGCS:
    """Known-name GCS reads and exact create-or-equal-reopen publication."""

    def __init__(self, client: object):
        self._client = client

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label="Core v1 outcome exact-read identity")
        bucket_name, name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise CoreV1OutcomeRunnerError(
                "Core v1 outcome generation-pinned read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation, label="reopened object")
            != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("Core v1 outcome generation-pinned object differs")
        return raw

    def resolve_known(
        self,
        uri: str,
        *,
        absent_ok: bool,
    ) -> registered.PublishedObject | None:
        bucket_name, name = _gcs_parts(uri)
        try:
            current = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            current.reload()
        except Exception as exc:
            if absent_ok and _is_not_found(exc):
                return None
            raise CoreV1OutcomeRunnerError(
                "Core v1 outcome current-generation resolution failed"
            ) from exc
        generation = _generation(
            current.generation, label="Core v1 outcome current object"
        )
        try:
            pinned = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise CoreV1OutcomeRunnerError(
                "Core v1 outcome known-generation reopen failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("Core v1 outcome known object is empty")
        created_at = _iso(pinned.time_created, label="Core v1 outcome object creation")
        return registered.PublishedObject(
            receipt={
                "uri": uri,
                "generation": generation,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_only": True,
            },
            reopened_raw=raw,
            created_at=created_at,
            created=False,
        )

    def read_known(self, uri: str) -> registered.PublishedObject | None:
        return self.resolve_known(uri, absent_ok=True)

    def resolve_required(self, uri: str) -> registered.PublishedObject:
        resolved = self.resolve_known(uri, absent_ok=False)
        if resolved is None:
            raise AssertionError("required known-name resolution returned None")
        return resolved

    def publish(self, uri: str, raw: bytes) -> registered.PublishedObject:
        if type(raw) is not bytes or not raw:
            _fail("Core v1 outcome publication payload differs")
        bucket_name, name = _gcs_parts(uri)
        created = False
        try:
            blob = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
            created = True
        except Exception:
            # Precondition failures and ambiguous successes use one exact law.
            created = False
        reopened = self.resolve_required(uri)
        if reopened.reopened_raw != raw:
            _fail("existing Core v1 outcome object differs")
        return registered.PublishedObject(
            receipt=reopened.receipt,
            reopened_raw=reopened.reopened_raw,
            created_at=reopened.created_at,
            created=created,
        )


class LiveLeaseVerifier:
    """Resolve the fixed live lease lazily, then require that exact generation."""

    def __init__(self, store: GenerationPinnedGCS) -> None:
        self._store = store
        self._identity: dict[str, object] | None = None
        self._body: dict[str, object] | None = None

    def __call__(self) -> dict[str, object]:
        observed = self._store.resolve_required(
            shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
        )
        receipt = dict(observed.receipt)
        content_identity = _identity(
            {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
            label="live historical lease identity",
        )
        body = _json(observed.reopened_raw, label="live historical lease")
        if self._identity is None:
            self._identity = content_identity
            self._body = body
        if content_identity != self._identity:
            _fail("historical-outcome lease current generation differs")
        if body != self._body:
            _fail("historical-outcome lease bytes differ")
        return {
            "body": dict(body),
            "object_receipt": {**content_identity, "create_only": True},
        }


def _table_metadata(client: object, table_id: str) -> dict[str, object]:
    try:
        table = client.get_table(table_id)  # type: ignore[attr-defined]
    except Exception as exc:
        raise CoreV1OutcomeRunnerError(
            "Core v1 BigQuery table metadata read failed"
        ) from exc

    def field_payload(field: object) -> dict[str, object]:
        return {
            "name": field.name,  # type: ignore[attr-defined]
            "field_type": field.field_type,  # type: ignore[attr-defined]
            "mode": field.mode,  # type: ignore[attr-defined]
            "fields": [
                field_payload(child) for child in field.fields  # type: ignore[attr-defined]
            ],
        }

    schema = [field_payload(field) for field in table.schema]
    if type(table.etag) is not str or not table.etag:
        _fail("Core v1 BigQuery table etag differs")
    return {
        "table_id": table_id,
        "etag": table.etag,
        "modified": _iso(table.modified, label="BigQuery table modified"),
        "num_rows": table.num_rows,
        "schema_sha256": sha256(batch.canonical_json_bytes(schema)).hexdigest(),
    }


def _query_parameters(spec: registered.QuerySpec) -> list[object]:
    from google.cloud import bigquery

    result: list[object] = []
    for value in spec.parameters:
        if value.array:
            result.append(bigquery.ArrayQueryParameter(
                value.name, value.bq_type, list(value.value)  # type: ignore[arg-type]
            ))
        else:
            result.append(bigquery.ScalarQueryParameter(
                value.name, value.bq_type, value.value
            ))
    return result


def _parameter_api(values: Sequence[object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for value in values:
        method = getattr(value, "to_api_repr", None)
        if not callable(method):
            _fail("Core v1 BigQuery parameter representation differs")
        raw = method()
        if not isinstance(raw, Mapping):
            _fail("Core v1 BigQuery parameter representation differs")
        result.append(dict(raw))
    return result


def _validate_job(
    job: object,
    *,
    spec: registered.QuerySpec,
    parameters: Sequence[object],
) -> None:
    actual_parameters = getattr(job, "query_parameters", None)
    if (
        getattr(job, "job_id", None) != spec.job_id
        or getattr(job, "location", None) != spec.location
        or getattr(job, "query", None) != spec.sql
        or getattr(job, "use_legacy_sql", None) is not False
        or getattr(job, "use_query_cache", None) is not False
        or not isinstance(actual_parameters, Sequence)
        or isinstance(actual_parameters, (str, bytes))
        or _parameter_api(actual_parameters) != _parameter_api(parameters)
    ):
        _fail("Core v1 recovered BigQuery job configuration differs")


def _query_result(
    job: object,
    *,
    spec: registered.QuerySpec,
    parameters: Sequence[object],
    disposition: str,
) -> supply.CoreOutcomeQueryResult:
    _validate_job(job, spec=spec, parameters=parameters)
    try:
        completed = job.result()  # type: ignore[attr-defined]
        rows = tuple(
            dict(row.items()) if hasattr(row, "items") else dict(row)
            for row in completed
        )
    except Exception as exc:
        raise CoreV1OutcomeRunnerError(
            "Core v1 authoritative BigQuery job failed"
        ) from exc
    cache_hit = getattr(job, "cache_hit", None)
    if type(cache_hit) is not bool:
        _fail("Core v1 BigQuery cache marker differs")
    total_bytes = getattr(job, "total_bytes_processed", None)
    if type(total_bytes) is not int or total_bytes < 0:
        _fail("Core v1 BigQuery processed-byte count differs")
    if getattr(job, "error_result", None) is not None:
        _fail("Core v1 authoritative BigQuery job has an error result")
    receipt = {
        "job_id": job.job_id,  # type: ignore[attr-defined]
        "location": job.location,  # type: ignore[attr-defined]
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "created": _iso(job.created, label="BigQuery job created"),  # type: ignore[attr-defined]
        "started": _iso(job.started, label="BigQuery job started"),  # type: ignore[attr-defined]
        "ended": _iso(job.ended, label="BigQuery job ended"),  # type: ignore[attr-defined]
        "total_bytes_processed": total_bytes,
        "cache_hit": cache_hit,
        "error_result": job.error_result,  # type: ignore[attr-defined]
    }
    return supply.CoreOutcomeQueryResult(
        disposition=disposition,
        result=shared.QueryResult(rows=rows, job_receipt=receipt),
    )


def _get_or_create_query(
    client: object, spec: registered.QuerySpec,
) -> supply.CoreOutcomeQueryResult:
    from google.cloud import bigquery

    parameters = _query_parameters(spec)
    try:
        existing = client.get_job(  # type: ignore[attr-defined]
            spec.job_id, location=spec.location
        )
    except Exception as exc:
        if not _is_not_found(exc):
            raise CoreV1OutcomeRunnerError(
                "Core v1 fixed-ID BigQuery job lookup failed"
            ) from exc
        existing = None
    if existing is not None:
        return _query_result(
            existing,
            spec=spec,
            parameters=parameters,
            disposition="recovered",
        )
    job_config = bigquery.QueryJobConfig(
        query_parameters=parameters,
        use_query_cache=False,
        use_legacy_sql=False,
    )
    try:
        job = client.query(  # type: ignore[attr-defined]
            spec.sql,
            job_config=job_config,
            job_id=spec.job_id,
            location=spec.location,
            job_retry=None,
        )
        disposition = "created"
    except Exception as exc:
        # A create can succeed server-side before the response is lost. Resolve
        # that single fixed ID; never submit another query.
        try:
            job = client.get_job(  # type: ignore[attr-defined]
                spec.job_id, location=spec.location
            )
        except Exception as recovery_exc:
            raise CoreV1OutcomeRunnerError(
                "Core v1 fixed-ID BigQuery create/recovery failed"
            ) from recovery_exc
        disposition = "recovered"
    return _query_result(
        job,
        spec=spec,
        parameters=parameters,
        disposition=disposition,
    )


def run_cloud(
    *,
    config: supply.CoreOutcomeSupplyConfig,
    catalog_root_uri: str,
    storage_client: object,
    bq_client: object,
    clock: supply.Clock = lambda: datetime.now(timezone.utc),
) -> CoreOutcomeCloudResult:
    if not isinstance(config, supply.CoreOutcomeSupplyConfig) or config.enabled is not True:
        _fail("Core v1 outcome cloud runner is default-off")
    expected_catalog_prefix = f"gs://{supply.OUTPUT_BUCKET}/"
    if (
        type(catalog_root_uri) is not str
        or not catalog_root_uri.startswith(expected_catalog_prefix)
        or not catalog_root_uri.endswith(catalog_store.ROOT_FILENAME)
    ):
        _fail("Core v1 catalog root URI differs from its deterministic law")
    store = GenerationPinnedGCS(storage_client)
    catalog_root = store.resolve_required(catalog_root_uri)
    catalog_root_identity = _identity(
        {
            key: catalog_root.receipt[key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
        label="Core v1 catalog root identity",
    )
    try:
        catalog_authority = (
            catalog_store.reopen_sharded_core_v1_catalog_authority(
                root_identity=catalog_root_identity,
                read_exact=store.read_exact,
            )
        )
    except catalog_store.CorpusCoreV1CatalogMaterializerError as exc:
        raise CoreV1OutcomeRunnerError(str(exc)) from exc
    catalog = dict(catalog_authority.logical_catalog)
    catalog_identity = dict(catalog_authority.catalog_identity)
    source_freeze_identity = _identity(
        catalog.get("later_source_freeze_identity"),
        label="catalog later-source freeze identity",
    )
    source_freeze = _json(
        store.read_exact(source_freeze_identity), label="later-source freeze"
    )
    output_uris = {
        f"{config.output_root}/read-attempt.json",
        f"{config.output_root}/player-score-source.json",
        f"{config.output_root}/player-outcome-snapshot.json",
        f"{config.output_root}/completion.json",
    }
    if len({
        catalog_root_uri,
        str(catalog_identity["uri"]),
        str(source_freeze_identity["uri"]),
        shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
        *output_uris,
    }) != 8:
        _fail("Core v1 outcome input/output object URIs alias")
    supplied = supply.supply_core_v1_outcome_snapshot(
        config=config,
        catalog=catalog,
        catalog_identity=catalog_identity,
        source_freeze=source_freeze,
        source_freeze_identity=source_freeze_identity,
        verify_lease=LiveLeaseVerifier(store),
        read_table_metadata=lambda table: _table_metadata(bq_client, table),
        get_or_create_query=lambda spec: _get_or_create_query(bq_client, spec),
        publish=store.publish,
        read_known=store.read_known,
        clock=clock,
    )
    raw_lease = supplied.attempt.get("historical_outcome_lease")
    if not isinstance(raw_lease, Mapping):
        _fail("persisted historical lease body differs")
    raw_lease_receipt = raw_lease.get("object_receipt")
    if not isinstance(raw_lease_receipt, Mapping):
        _fail("persisted historical lease receipt differs")
    persisted_lease = _identity(
        {
            key: raw_lease_receipt[key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
        label="persisted historical lease identity",
    )
    if persisted_lease["uri"] != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI:
        _fail("persisted historical lease URI differs")
    return CoreOutcomeCloudResult(
        supply=supplied,
        catalog_root_identity=catalog_root_identity,
        catalog_identity=catalog_identity,
        source_freeze_identity=source_freeze_identity,
        historical_lease_identity=persisted_lease,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--catalog-root-uri", required=True)
    return parser


def _validated_cli(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str],
) -> tuple[supply.CoreOutcomeSupplyConfig, str]:
    if args.execute is not True or environ.get(ENABLED_ENV) != "1":
        _fail(f"--execute and {ENABLED_ENV}=1 are required explicitly")
    if args.project != PROJECT:
        _fail("Core v1 outcome cloud project differs")
    if (
        type(args.run_id) is not str
        or _RUN_ID.fullmatch(args.run_id) is None
        or type(args.job) is not str
        or _JOB.fullmatch(args.job) is None
        or type(args.code_sha) is not str
        or _CODE_SHA.fullmatch(args.code_sha) is None
        or type(args.image) is not str
        or _IMAGE.fullmatch(args.image) is None
    ):
        _fail("Core v1 outcome runtime identity differs")
    config = supply.CoreOutcomeSupplyConfig(
        run_id=args.run_id,
        job=args.job,
        code_sha=args.code_sha,
        image=args.image,
        enabled=True,
    )
    catalog_root_uri = str(args.catalog_root_uri)
    expected_prefix = f"gs://{supply.OUTPUT_BUCKET}/"
    if (
        not catalog_root_uri.startswith(expected_prefix)
        or not catalog_root_uri.endswith(catalog_store.ROOT_FILENAME)
    ):
        _fail("Core v1 catalog root URI differs from its deterministic law")
    _gcs_parts(catalog_root_uri)
    return config, catalog_root_uri


def _receipt_only(cloud: CoreOutcomeCloudResult) -> dict[str, object]:
    result = cloud.supply
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "CORE_V1_OUTCOME_SNAPSHOT_CLOSED",
        "catalog_root_identity": dict(cloud.catalog_root_identity),
        "catalog_identity": dict(cloud.catalog_identity),
        "later_source_freeze_identity": dict(cloud.source_freeze_identity),
        "historical_outcome_lease_identity": dict(
            cloud.historical_lease_identity
        ),
        "attempt_identity": dict(result.attempt_identity),
        "player_source_identity": dict(result.player_source_identity),
        "outcome_snapshot_identity": dict(result.outcome_snapshot_identity),
        "completion_identity": dict(result.completion_identity),
        "query_job_id": result.player_source["query_job_id"],
        "query_job_disposition": result.player_source["query_job_disposition"],
        "outcome_key_count": result.completion["outcome_key_count"],
        "one_historical_outcome_read": True,
        "rank_available": False,
        "roi_available": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    body["cli_receipt_sha256"] = supply.canonical_sha256(body)
    return body


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
    bq_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    retained_environ = os.environ if environ is None else environ
    config, catalog_root_uri = _validated_cli(
        args, environ=retained_environ
    )
    if storage_client is None or bq_client is None:
        # Cloud imports and clients are unreachable while either gate is closed.
        from google.cloud import bigquery, storage

        if storage_client is None:
            storage_client = storage.Client(project=PROJECT)
        if bq_client is None:
            bq_client = bigquery.Client(project=PROJECT)
    result = run_cloud(
        config=config,
        catalog_root_uri=catalog_root_uri,
        storage_client=storage_client,
        bq_client=bq_client,
    )
    print(supply.canonical_json_bytes(_receipt_only(result)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CoreV1OutcomeRunnerError,
        supply.CorpusCoreV1OutcomeSupplyError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


__all__ = [
    "CoreV1OutcomeRunnerError",
    "CoreOutcomeCloudResult",
    "ENABLED_ENV",
    "GenerationPinnedGCS",
    "LiveLeaseVerifier",
    "PROJECT",
    "RECEIPT_SCHEMA",
    "main",
    "run_cloud",
]
