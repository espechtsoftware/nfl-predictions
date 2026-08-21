#!/usr/bin/env python3
"""Default-off LR8 earlier-period authoritative score-map transport.
Verify an external live lease, use one pinned source, and emit only receipts.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Final


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import lr8_label_fit_adapter as adapter  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as supplier  # noqa: E402
from nfl_dfs.research.object_identity import same_object  # noqa: E402


ENABLED_ENV: Final = "LR8_LABEL_SCORE_MAP_ENABLED"
PROJECT: Final = "nfl-predictions-503414"
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,127}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")


class LR8ScoreMapRunnerError(RuntimeError):
    """The executable score-map boundary failed closed."""


@dataclass(frozen=True, slots=True)
class SourcePin:
    uri: str
    generation: str
    sha256: str
    manifest_sha256: str


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LR8ScoreMapRunnerError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise LR8ScoreMapRunnerError(f"{label} must be a JSON object")
    return value


def _gcs_parts(uri: object, *, label: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise LR8ScoreMapRunnerError(f"{label} URI must use gs://")
    bucket, separator, name = uri.removeprefix("gs://").partition("/")
    if not bucket or not separator or not name or ".." in name.split("/"):
        raise LR8ScoreMapRunnerError(f"{label} URI must name one GCS object")
    return bucket, name


def _generation(value: object, *, label: str) -> str:
    text = value if isinstance(value, str) else ""
    if _GENERATION.fullmatch(text) is None:
        raise LR8ScoreMapRunnerError(f"{label} generation must be canonical")
    return text


def _digest(value: object, *, label: str) -> str:
    text = value if isinstance(value, str) else ""
    if _SHA256.fullmatch(text) is None:
        raise LR8ScoreMapRunnerError(f"{label} must be a lowercase SHA-256")
    return text


def _iso(value: object, *, label: str) -> str:
    if not isinstance(value, datetime):
        raise LR8ScoreMapRunnerError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LR8ScoreMapRunnerError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _read_lease_contract(path: Path) -> dict[str, object]:
    try:
        value = _strict_json(path.read_bytes(), label="historical lease receipt")
    except OSError as exc:
        raise LR8ScoreMapRunnerError("historical lease receipt is unreadable") from exc
    if set(value) != {"lease", "object"}:
        raise LR8ScoreMapRunnerError("historical lease receipt fields differ")
    try:
        body = dict(value["lease"])  # type: ignore[arg-type]
        receipt = dict(value["object"])  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise LR8ScoreMapRunnerError("historical lease contract differs")
    return {"body": body, "object_receipt": receipt}


class _LiveLeaseVerifier:
    def __init__(self, client: object, contract: Mapping[str, object]):
        self._client = client
        self._body = dict(contract["body"])  # type: ignore[arg-type]
        self._receipt = dict(contract["object_receipt"])  # type: ignore[arg-type]

    def __call__(self) -> dict[str, object]:
        receipt = self._receipt
        uri = receipt.get("uri")
        generation = _generation(receipt.get("generation"), label="historical lease")
        _digest(receipt.get("sha256"), label="historical lease digest")
        if uri != adapter.HISTORICAL_OUTCOME_LEASE_URI:
            raise LR8ScoreMapRunnerError("historical lease URI differs")
        bucket_name, name = _gcs_parts(uri, label="historical lease")
        generation_int = int(generation)
        try:
            bucket = self._client.bucket(bucket_name)  # type: ignore[attr-defined]
            live = bucket.blob(name)
            live.reload(if_generation_match=generation_int)
            if str(live.generation) != generation:
                raise LR8ScoreMapRunnerError("historical lease is not current")
            pinned = bucket.blob(name, generation=generation_int)
            raw = pinned.download_as_bytes(if_generation_match=generation_int)
        except LR8ScoreMapRunnerError:
            raise
        except Exception as exc:
            raise LR8ScoreMapRunnerError(
                "historical lease live-generation verification failed"
            ) from exc
        observed = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        expected = {
            key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
        }
        if (
            receipt.get("create_only") is not True
            or not same_object(expected, observed)
            or _strict_json(raw, label="live historical lease") != self._body
        ):
            raise LR8ScoreMapRunnerError("historical lease content differs")
        return {"body": dict(self._body), "object_receipt": dict(receipt)}


def _load_source(
    client: object, pin: SourcePin,
) -> tuple[dict[str, object], dict[str, object]]:
    bucket_name, name = _gcs_parts(pin.uri, label="training source")
    generation = _generation(pin.generation, label="training source")
    _digest(pin.sha256, label="training source digest")
    _digest(pin.manifest_sha256, label="training source manifest digest")
    generation_int = int(generation)
    try:
        blob = client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
            name, generation=generation_int
        )
        blob.reload(if_generation_match=generation_int)
        raw = blob.download_as_bytes(if_generation_match=generation_int)
    except Exception as exc:
        raise LR8ScoreMapRunnerError(
            "training source generation-pinned read failed"
        ) from exc
    observed = {
        "uri": pin.uri,
        "generation": str(blob.generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    expected = {**observed, "generation": generation, "sha256": pin.sha256}
    if not same_object(expected, observed):
        raise LR8ScoreMapRunnerError("training source object identity differs")
    return _strict_json(raw, label="training source freeze"), observed


def _table_metadata(client: object, table_id: str) -> dict[str, object]:
    try:
        table = client.get_table(table_id)  # type: ignore[attr-defined]
    except Exception as exc:
        raise LR8ScoreMapRunnerError("BigQuery table metadata read failed") from exc

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
    etag = table.etag
    if not isinstance(etag, str) or not etag:
        raise LR8ScoreMapRunnerError("BigQuery table etag differs")
    return {
        "table_id": table_id,
        "etag": etag,
        "modified": _iso(table.modified, label="BigQuery table modified"),
        "num_rows": table.num_rows,
        "schema_sha256": sha256(supplier.canonical_json(schema)).hexdigest(),
    }


def _execute_query(client: object, spec: supplier.QuerySpec) -> supplier.QueryResult:
    from google.cloud import bigquery

    parameters = []
    for value in spec.parameters:
        if value.array:
            parameters.append(bigquery.ArrayQueryParameter(
                value.name, value.bq_type, list(value.value)  # type: ignore[arg-type]
            ))
        else:
            parameters.append(bigquery.ScalarQueryParameter(
                value.name, value.bq_type, value.value
            ))
    job_config = bigquery.QueryJobConfig(
        query_parameters=parameters, use_query_cache=False
    )
    try:
        job = client.query(  # type: ignore[attr-defined]
            spec.sql,
            job_config=job_config,
            job_id=spec.job_id,
            location=spec.location,
            job_retry=None,
        )
        result = job.result()
        rows = tuple(
            dict(row.items()) if hasattr(row, "items") else dict(row)
            for row in result
        )
    except Exception as exc:
        raise LR8ScoreMapRunnerError("authoritative BigQuery query failed") from exc
    cache_hit = job.cache_hit
    if not isinstance(cache_hit, bool):
        raise LR8ScoreMapRunnerError("authoritative query cache marker differs")
    receipt = {
        "job_id": job.job_id,
        "location": job.location,
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "created": _iso(job.created, label="query created"),
        "started": _iso(job.started, label="query started"),
        "ended": _iso(job.ended, label="query ended"),
        "total_bytes_processed": job.total_bytes_processed,
        "cache_hit": cache_hit,
        "error_result": job.error_result,
    }
    return supplier.QueryResult(rows=rows, job_receipt=receipt)


class _CreateOncePublisher:
    def __init__(self, client: object):
        self._client = client

    def __call__(self, uri: str, raw: bytes) -> supplier.PublishedObject:
        bucket_name, name = _gcs_parts(uri, label="score-map output")
        bucket = self._client.bucket(bucket_name)  # type: ignore[attr-defined]
        blob = bucket.blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            if type(exc).__name__ == "PreconditionFailed":
                raise LR8ScoreMapRunnerError(
                    "score-map output already exists; create-once refused"
                ) from exc
            raise LR8ScoreMapRunnerError("score-map output upload failed") from exc
        try:
            generation = int(blob.generation)
        except (TypeError, ValueError) as exc:
            raise LR8ScoreMapRunnerError(
                "created score-map generation is absent"
            ) from exc
        if generation <= 0:
            raise LR8ScoreMapRunnerError("created score-map generation differs")
        try:
            pinned = bucket.blob(name, generation=generation)
            pinned.reload(if_generation_match=generation)
            reopened = pinned.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise LR8ScoreMapRunnerError(
                "created score-map generation reopen failed"
            ) from exc
        if reopened != raw or str(pinned.generation) != str(generation):
            raise LR8ScoreMapRunnerError("created score-map bytes differ")
        return supplier.PublishedObject(
            receipt={
                "uri": uri,
                "generation": str(generation),
                "sha256": sha256(reopened).hexdigest(),
                "bytes": len(reopened),
                "create_only": True,
            },
            reopened_raw=reopened,
            created_at=_iso(pinned.time_created, label="object creation"),
            created=True,
        )


def run_cloud(
    *,
    config: supplier.SupplierConfig,
    source_pin: SourcePin,
    lease_contract: Mapping[str, object],
    bq_client: object,
    storage_client: object,
    clock: supplier.Clock = lambda: datetime.now(timezone.utc),
) -> supplier.ScoreMapSupply:
    if not isinstance(config.enabled, bool) or config.enabled is not True:
        raise LR8ScoreMapRunnerError("LR8 score-map runner is default-off")
    training_source, source_receipt = _load_source(storage_client, source_pin)
    lease_verifier = _LiveLeaseVerifier(storage_client, lease_contract)
    return supplier.supply_authoritative_score_map(
        config=config,
        training_source_freeze=training_source,
        training_source_receipt=source_receipt,
        verify_lease=lease_verifier,
        read_table_metadata=lambda table: _table_metadata(bq_client, table),
        execute_query=lambda spec: _execute_query(bq_client, spec),
        publish=_CreateOncePublisher(storage_client),
        clock=clock,
    )


def _receipt_only(result: supplier.ScoreMapSupply) -> dict[str, object]:
    return {
        "status": "LR8_LABEL_SCORE_MAP_CLOSED",
        "attempt_object": dict(result.attempt_receipt),
        "source_extract_object": dict(result.source_extract_receipt),
        "score_map_object": dict(result.score_map_receipt),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--training-source-uri", required=True)
    parser.add_argument("--training-source-generation", required=True)
    parser.add_argument("--training-source-sha256", required=True)
    parser.add_argument("--training-source-manifest-sha256", required=True)
    parser.add_argument("--historical-lease-receipt", type=Path, required=True)
    return parser


def _validated_cli(
    args: argparse.Namespace,
) -> tuple[supplier.SupplierConfig, SourcePin, dict[str, object]]:
    if not args.execute or os.environ.get(ENABLED_ENV) != "1":
        raise LR8ScoreMapRunnerError(
            f"--execute and {ENABLED_ENV}=1 are required explicitly"
        )
    if args.project != PROJECT:
        raise LR8ScoreMapRunnerError("LR8 score-map project differs")
    if (
        _RUN_ID.fullmatch(args.run_id) is None
        or _JOB.fullmatch(args.job) is None
        or _CODE_SHA.fullmatch(args.code_sha) is None
        or _IMAGE.fullmatch(args.image) is None
    ):
        raise LR8ScoreMapRunnerError("LR8 score-map runtime identity differs")
    _gcs_parts(args.training_source_uri, label="training source")
    source_pin = SourcePin(
        uri=args.training_source_uri,
        generation=_generation(
            args.training_source_generation, label="training source"
        ),
        sha256=_digest(
            args.training_source_sha256, label="training source digest"
        ),
        manifest_sha256=_digest(
            args.training_source_manifest_sha256,
            label="training source manifest digest",
        ),
    )
    config = supplier.SupplierConfig(
        run_id=args.run_id,
        job=args.job,
        code_sha=args.code_sha,
        image=args.image,
        expected_source_manifest_sha256=source_pin.manifest_sha256,
        enabled=True,
    )
    output_uris = {
        adapter.HISTORICAL_OUTCOME_LEASE_URI,
        source_pin.uri,
        f"{config.output_root}/label-read-attempt.json",
        f"{config.output_root}/authoritative-score-source.json",
        f"{config.output_root}/authoritative-score-map.json",
    }
    if len(output_uris) != 5:
        raise LR8ScoreMapRunnerError("LR8 score-map object URIs alias")
    lease = _read_lease_contract(args.historical_lease_receipt)
    validated = supplier._validate_lease(lease, config=config)  # noqa: SLF001
    return config, source_pin, validated


def main(argv: Sequence[str] | None = None) -> int:
    config, source_pin, lease_contract = _validated_cli(_parser().parse_args(argv))
    from google.cloud import bigquery, storage

    result = run_cloud(
        config=config,
        source_pin=source_pin,
        lease_contract=lease_contract,
        bq_client=bigquery.Client(project=PROJECT),
        storage_client=storage.Client(project=PROJECT),
    )
    print(supplier.canonical_json(_receipt_only(result)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LR8ScoreMapRunnerError, supplier.LR8ScoreMapError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
