#!/usr/bin/env python3
"""Default-off smoke and one-query runner for the R6 full-union panel.

``smoke`` is outcome-blind: it exact-replays the actual 54/54 root, publishes
the root-bound key projection and containment receipt, and never constructs a
BigQuery client or historical-outcome lease verifier.  ``supply`` requires
that exact persisted smoke receipt and replays it before constructing either
boundary.  It then uses known object names only and submits or recovers the
one deterministic fixed-ID query.  Standard output is always a compact
receipt and never contains score rows.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
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

from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_full_union_outcome_snapshot_v1 as snapshot,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_full_union_outcome_supply_v1 as supply,
)
from nfl_dfs.research import corpus_realized_outcome_transport as registered  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as shared  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLED_ENV: Final = "R6_FULL_UNION_OUTCOME_SUPPLY_ENABLED"
SMOKE_ENABLED_ENV: Final = "R6_FULL_UNION_ACTUAL_ROOT_SMOKE_ENABLED"
RECEIPT_SCHEMA: Final = "r6-full-union-outcome-supply-cloud-receipt/v1"
SMOKE_RECEIPT_SCHEMA: Final = "r6-full-union-actual-root-smoke-cloud-receipt/v1"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")


class R6FullUnionOutcomeRunnerV1Error(RuntimeError):
    """The executable R6 full-union outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class SnapshotCodeIdentitiesV1:
    snapshot_module_sha256: str
    snapshot_cli_sha256: str
    snapshot_test_sha256: str
    snapshot_cli_test_sha256: str


@dataclass(frozen=True, slots=True)
class ActualRootSmokeAuthorityV1:
    panel_freeze_identity: Mapping[str, object]
    outcome_key_projection: Mapping[str, object]
    outcome_key_projection_identity: Mapping[str, object]
    actual_root_smoke_receipt: Mapping[str, object]
    actual_root_smoke_receipt_identity: Mapping[str, object]
    code_identities: SnapshotCodeIdentitiesV1


@dataclass(frozen=True, slots=True)
class ActualRootSmokeCloudResultV1:
    authority: ActualRootSmokeAuthorityV1


@dataclass(frozen=True, slots=True)
class FullUnionOutcomeCloudResultV1:
    supply: supply.FullUnionOutcomeSupplyV1
    panel_freeze_identity: Mapping[str, object]
    actual_root_smoke_receipt_identity: Mapping[str, object]
    historical_lease_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ValidatedCliV1:
    operation: str
    config: supply.FullUnionOutcomeSupplyConfigV1
    panel_freeze_identity: Mapping[str, object]
    code_identities: SnapshotCodeIdentitiesV1
    actual_root_smoke_receipt_identity: Mapping[str, object] | None
    expected_lease_identity: Mapping[str, object] | None


def _fail(message: str) -> None:
    raise R6FullUnionOutcomeRunnerV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise R6FullUnionOutcomeRunnerV1Error(str(exc)) from exc


def _gcs_parts(uri: str) -> tuple[str, str]:
    identity = _identity(
        {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
        label="R6 full-union outcome object URI",
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
        raise R6FullUnionOutcomeRunnerV1Error(str(exc)) from exc
    if not isinstance(value, Mapping):
        _fail(f"{label} must be one JSON object")
    return dict(value)


def _lease_json(raw: bytes) -> dict[str, object]:
    """Parse the lease writer's canonical-JSON-plus-newline representation."""
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail("live historical lease bytes differ from the lease writer law")
    return _json(raw[:-1], label="live historical lease")


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _code_identities(
    *,
    snapshot_module_sha256: object,
    snapshot_cli_sha256: object,
    snapshot_test_sha256: object,
    snapshot_cli_test_sha256: object,
) -> SnapshotCodeIdentitiesV1:
    return SnapshotCodeIdentitiesV1(
        snapshot_module_sha256=_digest(
            snapshot_module_sha256, label="snapshot module SHA"
        ),
        snapshot_cli_sha256=_digest(
            snapshot_cli_sha256, label="snapshot CLI SHA"
        ),
        snapshot_test_sha256=_digest(
            snapshot_test_sha256, label="snapshot test SHA"
        ),
        snapshot_cli_test_sha256=_digest(
            snapshot_cli_test_sha256, label="snapshot CLI test SHA"
        ),
    )


def _output_uri(config: supply.FullUnionOutcomeSupplyConfigV1, name: str) -> str:
    return f"{config.output_root}/{name}"


def _content_identity(
    value: registered.PublishedObject, *, label: str,
) -> dict[str, object]:
    receipt = value.receipt
    if not isinstance(receipt, Mapping):
        _fail(f"{label} receipt differs")
    try:
        projected = {
            key: receipt[key]
            for key in ("uri", "generation", "sha256", "bytes")
        }
    except KeyError as exc:
        raise R6FullUnionOutcomeRunnerV1Error(
            f"{label} receipt lacks a content identity"
        ) from exc
    return _identity(projected, label=label)


def _created_at(value: registered.PublishedObject, *, label: str) -> datetime:
    if type(value.created_at) is not str:
        _fail(f"{label} creation timestamp differs")
    try:
        parsed = datetime.fromisoformat(value.created_at)
    except ValueError as exc:
        raise R6FullUnionOutcomeRunnerV1Error(
            f"{label} creation timestamp differs"
        ) from exc
    if parsed.tzinfo is None:
        _fail(f"{label} creation timestamp differs")
    return parsed.astimezone(timezone.utc)


class GenerationPinnedGCSV1:
    """Known-name exact reads and create-or-equal-reopen publication."""

    def __init__(self, client: object):
        self._client = client
        # The pure snapshot validator deliberately replays the complete root
        # at each boundary.  Generation-pinned bytes are immutable, so retain
        # exact verified content in-process and avoid downloading the large
        # 54-slate result graph repeatedly.
        self._exact_cache: dict[tuple[str, str, str, int], bytes] = {}

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label="R6 full-union exact-read identity")
        cache_key = (
            str(identity["uri"]),
            str(identity["generation"]),
            str(identity["sha256"]),
            int(identity["bytes"]),
        )
        cached = self._exact_cache.get(cache_key)
        if cached is not None:
            return cached
        bucket_name, name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise R6FullUnionOutcomeRunnerV1Error(
                "R6 full-union generation-pinned read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation, label="reopened object")
            != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("R6 full-union generation-pinned object differs")
        self._exact_cache[cache_key] = raw
        return raw

    def resolve_known(
        self, uri: str, *, absent_ok: bool,
    ) -> registered.PublishedObject | None:
        bucket_name, name = _gcs_parts(uri)
        try:
            current = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            current.reload()
        except Exception as exc:
            if absent_ok and _is_not_found(exc):
                return None
            raise R6FullUnionOutcomeRunnerV1Error(
                "R6 full-union current-generation resolution failed"
            ) from exc
        generation = _generation(
            current.generation, label="R6 full-union current object"
        )
        try:
            pinned = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise R6FullUnionOutcomeRunnerV1Error(
                "R6 full-union known-generation reopen failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("R6 full-union known object is empty")
        created_at = _iso(
            pinned.time_created, label="R6 full-union object creation"
        )
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
        if resolved is None:  # pragma: no cover - absent_ok=False
            raise AssertionError("required known-name resolution returned None")
        return resolved

    def publish(self, uri: str, raw: bytes) -> registered.PublishedObject:
        if type(raw) is not bytes or not raw:
            _fail("R6 full-union outcome publication payload differs")
        bucket_name, name = _gcs_parts(uri)
        created = False
        try:
            blob = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0
            )
            created = True
        except Exception:
            # Precondition failures and ambiguous successes share one reopen.
            created = False
        reopened = self.resolve_required(uri)
        if reopened.reopened_raw != raw:
            _fail("existing R6 full-union outcome object differs")
        return registered.PublishedObject(
            receipt=reopened.receipt,
            reopened_raw=reopened.reopened_raw,
            created_at=reopened.created_at,
            created=created,
        )


def _runtime_boundary(
    config: supply.FullUnionOutcomeSupplyConfigV1,
    panel_freeze_identity: object,
) -> tuple[supply.FullUnionOutcomeSupplyConfigV1, dict[str, object]]:
    if (
        not isinstance(config, supply.FullUnionOutcomeSupplyConfigV1)
        or config.enabled is not True
        or _RUN_ID.fullmatch(config.run_id) is None
        or _JOB.fullmatch(config.job) is None
        or _CODE_SHA.fullmatch(config.code_sha) is None
        or _IMAGE.fullmatch(config.image) is None
    ):
        _fail("R6 full-union outcome runtime identity differs")
    root_identity = _identity(
        panel_freeze_identity, label="R6 full-union panel-freeze identity"
    )
    root_uri = str(root_identity["uri"])
    if (
        not root_uri.startswith(f"gs://{supply.OUTPUT_BUCKET}/research/")
        or not root_uri.endswith("/panel-freeze.json")
    ):
        _fail("R6 full-union panel-freeze URI differs")
    return config, root_identity


def _snapshot_error(exc: Exception) -> R6FullUnionOutcomeRunnerV1Error:
    return R6FullUnionOutcomeRunnerV1Error(str(exc))


def run_actual_root_smoke_v1(
    *,
    config: supply.FullUnionOutcomeSupplyConfigV1,
    panel_freeze_identity: Mapping[str, object],
    code_identities: SnapshotCodeIdentitiesV1,
    store: GenerationPinnedGCSV1,
) -> ActualRootSmokeCloudResultV1:
    """Create or exactly recover the outcome-blind actual-root smoke gate."""
    retained_config, root_identity = _runtime_boundary(
        config, panel_freeze_identity
    )
    if not isinstance(code_identities, SnapshotCodeIdentitiesV1):
        _fail("snapshot code identities differ")
    code = _code_identities(
        snapshot_module_sha256=code_identities.snapshot_module_sha256,
        snapshot_cli_sha256=code_identities.snapshot_cli_sha256,
        snapshot_test_sha256=code_identities.snapshot_test_sha256,
        snapshot_cli_test_sha256=code_identities.snapshot_cli_test_sha256,
    )
    try:
        expected_projection = snapshot.project_required_outcome_keys_v1(
            panel_freeze_identity=root_identity,
            read_exact=store.read_exact,
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise _snapshot_error(exc) from exc
    projection_object = store.publish(
        _output_uri(retained_config, "outcome-key-projection.json"),
        snapshot.canonical_json_bytes(expected_projection),
    )
    projection_identity = _content_identity(
        projection_object, label="persisted outcome-key projection identity"
    )
    persisted_projection = _json(
        projection_object.reopened_raw,
        label="persisted outcome-key projection",
    )
    try:
        expected_smoke = snapshot.build_actual_root_smoke_receipt_v1(
            panel_freeze_identity=root_identity,
            outcome_key_projection=persisted_projection,
            outcome_key_projection_identity=projection_identity,
            expected_reviewed_source_commit_sha=retained_config.code_sha,
            expected_runtime_immutable_image=retained_config.image,
            snapshot_module_sha256=code.snapshot_module_sha256,
            snapshot_cli_sha256=code.snapshot_cli_sha256,
            snapshot_test_sha256=code.snapshot_test_sha256,
            snapshot_cli_test_sha256=code.snapshot_cli_test_sha256,
            read_exact=store.read_exact,
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise _snapshot_error(exc) from exc
    smoke_object = store.publish(
        _output_uri(retained_config, "actual-root-smoke-receipt.json"),
        snapshot.canonical_json_bytes(expected_smoke),
    )
    smoke_identity = _content_identity(
        smoke_object, label="persisted actual-root smoke identity"
    )
    persisted_smoke = _json(
        smoke_object.reopened_raw, label="persisted actual-root smoke receipt"
    )
    try:
        smoke_receipt, validated_smoke_identity = (
            snapshot.validate_actual_root_smoke_receipt_v1(
                persisted_smoke,
                identity=smoke_identity,
                expected_panel_freeze_identity=root_identity,
                outcome_key_projection=persisted_projection,
                expected_outcome_key_projection_identity=projection_identity,
                expected_reviewed_source_commit_sha=retained_config.code_sha,
                expected_runtime_immutable_image=retained_config.image,
                expected_snapshot_module_sha256=code.snapshot_module_sha256,
                expected_snapshot_cli_sha256=code.snapshot_cli_sha256,
                expected_snapshot_test_sha256=code.snapshot_test_sha256,
                expected_snapshot_cli_test_sha256=(
                    code.snapshot_cli_test_sha256
                ),
                read_exact=store.read_exact,
            )
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise _snapshot_error(exc) from exc
    if (
        validated_smoke_identity != smoke_identity
        or smoke_receipt.get("panel_freeze_identity") != root_identity
        or smoke_receipt.get("outcome_key_projection_identity")
        != projection_identity
        or _created_at(projection_object, label="outcome-key projection")
        > _created_at(smoke_object, label="actual-root smoke receipt")
    ):
        _fail("actual-root smoke durable binding differs")
    return ActualRootSmokeCloudResultV1(authority=ActualRootSmokeAuthorityV1(
        panel_freeze_identity=root_identity,
        outcome_key_projection=persisted_projection,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=smoke_receipt,
        actual_root_smoke_receipt_identity=smoke_identity,
        code_identities=code,
    ))


def preflight_actual_root_smoke_v1(
    *,
    config: supply.FullUnionOutcomeSupplyConfigV1,
    panel_freeze_identity: Mapping[str, object],
    expected_actual_root_smoke_receipt_identity: Mapping[str, object],
    code_identities: SnapshotCodeIdentitiesV1,
    store: GenerationPinnedGCSV1,
) -> ActualRootSmokeAuthorityV1:
    """Validate exact smoke/root/projection using storage and nothing else."""
    retained_config, root_identity = _runtime_boundary(
        config, panel_freeze_identity
    )
    if not isinstance(code_identities, SnapshotCodeIdentitiesV1):
        _fail("snapshot code identities differ")
    code = _code_identities(
        snapshot_module_sha256=code_identities.snapshot_module_sha256,
        snapshot_cli_sha256=code_identities.snapshot_cli_sha256,
        snapshot_test_sha256=code_identities.snapshot_test_sha256,
        snapshot_cli_test_sha256=code_identities.snapshot_cli_test_sha256,
    )
    expected_smoke_identity = _identity(
        expected_actual_root_smoke_receipt_identity,
        label="expected actual-root smoke identity",
    )
    smoke_uri = _output_uri(
        retained_config, "actual-root-smoke-receipt.json"
    )
    if expected_smoke_identity["uri"] != smoke_uri:
        _fail("expected actual-root smoke URI differs")
    smoke_object = store.resolve_required(smoke_uri)
    smoke_identity = _content_identity(
        smoke_object, label="current actual-root smoke identity"
    )
    if smoke_identity != expected_smoke_identity:
        _fail("current actual-root smoke identity differs")
    smoke_value = _json(
        smoke_object.reopened_raw, label="actual-root smoke receipt"
    )
    projection_identity = _identity(
        smoke_value.get("outcome_key_projection_identity"),
        label="smoke-bound outcome-key projection identity",
    )
    projection_uri = _output_uri(
        retained_config, "outcome-key-projection.json"
    )
    if projection_identity["uri"] != projection_uri:
        _fail("smoke-bound outcome-key projection URI differs")
    projection_object = store.resolve_required(projection_uri)
    current_projection_identity = _content_identity(
        projection_object, label="current outcome-key projection identity"
    )
    if current_projection_identity != projection_identity:
        _fail("current outcome-key projection identity differs")
    projection_value = _json(
        projection_object.reopened_raw, label="outcome-key projection"
    )
    try:
        smoke_receipt, validated_smoke_identity = (
            snapshot.validate_actual_root_smoke_receipt_v1(
                smoke_value,
                identity=smoke_identity,
                expected_panel_freeze_identity=root_identity,
                outcome_key_projection=projection_value,
                expected_outcome_key_projection_identity=projection_identity,
                expected_reviewed_source_commit_sha=retained_config.code_sha,
                expected_runtime_immutable_image=retained_config.image,
                expected_snapshot_module_sha256=code.snapshot_module_sha256,
                expected_snapshot_cli_sha256=code.snapshot_cli_sha256,
                expected_snapshot_test_sha256=code.snapshot_test_sha256,
                expected_snapshot_cli_test_sha256=(
                    code.snapshot_cli_test_sha256
                ),
                read_exact=store.read_exact,
            )
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise _snapshot_error(exc) from exc
    if (
        validated_smoke_identity != smoke_identity
        or projection_value.get("panel_freeze_identity") != root_identity
        or smoke_receipt.get("panel_freeze_identity") != root_identity
        or smoke_receipt.get("outcome_key_projection_identity")
        != projection_identity
        or _created_at(projection_object, label="outcome-key projection")
        > _created_at(smoke_object, label="actual-root smoke receipt")
    ):
        _fail("actual-root smoke preflight durable binding differs")
    return ActualRootSmokeAuthorityV1(
        panel_freeze_identity=root_identity,
        outcome_key_projection=projection_value,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=smoke_receipt,
        actual_root_smoke_receipt_identity=smoke_identity,
        code_identities=code,
    )


class LiveLeaseVerifierV1:
    """Resolve and retain the one expected live lease generation lazily."""

    def __init__(
        self,
        store: GenerationPinnedGCSV1,
        *,
        expected_identity: Mapping[str, object],
    ) -> None:
        self._store = store
        self._expected_identity = _identity(
            expected_identity, label="expected historical lease identity"
        )
        if (
            self._expected_identity["uri"]
            != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
        ):
            _fail("expected historical-outcome lease URI differs")
        self._identity: dict[str, object] | None = None
        self._body: dict[str, object] | None = None

    def __call__(self) -> dict[str, object]:
        observed = self._store.resolve_required(
            shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
        )
        receipt = dict(observed.receipt)
        content_identity = _identity(
            {
                key: receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            },
            label="live historical lease identity",
        )
        if content_identity != self._expected_identity:
            _fail("live historical-outcome lease differs from expected identity")
        body = _lease_json(observed.reopened_raw)
        if self._identity is None:
            self._identity = content_identity
            self._body = body
        if content_identity != self._identity or body != self._body:
            _fail("historical-outcome lease generation or bytes changed")
        return {
            "body": dict(body),
            "object_receipt": {**content_identity, "create_only": True},
        }


def _table_metadata(client: object, table_id: str) -> dict[str, object]:
    try:
        table = client.get_table(table_id)  # type: ignore[attr-defined]
    except Exception as exc:
        raise R6FullUnionOutcomeRunnerV1Error(
            "R6 full-union BigQuery table metadata read failed"
        ) from exc

    def field_payload(field: object) -> dict[str, object]:
        return {
            "name": field.name,  # type: ignore[attr-defined]
            "field_type": field.field_type,  # type: ignore[attr-defined]
            "mode": field.mode,  # type: ignore[attr-defined]
            "fields": [
                field_payload(child)
                for child in field.fields  # type: ignore[attr-defined]
            ],
        }

    schema = [field_payload(field) for field in table.schema]
    if type(table.etag) is not str or not table.etag:
        _fail("R6 full-union BigQuery table etag differs")
    return {
        "table_id": table_id,
        "etag": table.etag,
        "modified": _iso(table.modified, label="BigQuery table modified"),
        "num_rows": table.num_rows,
        "schema_sha256": sha256(batch.canonical_json_bytes(schema)).hexdigest(),
    }


def _query_parameters(spec: registered.QuerySpec) -> list[object]:
    from google.cloud import bigquery

    def parameter_value(value: registered.QueryParameter) -> object:
        raw = value.value
        if value.bq_type != "TIMESTAMP":
            return raw

        def timestamp(item: object) -> datetime:
            if isinstance(item, datetime):
                parsed = item
            elif type(item) is str:
                try:
                    parsed = datetime.fromisoformat(item)
                except ValueError as exc:
                    raise R6FullUnionOutcomeRunnerV1Error(
                        "R6 full-union BigQuery TIMESTAMP parameter differs"
                    ) from exc
            else:
                _fail("R6 full-union BigQuery TIMESTAMP parameter differs")
            if parsed.tzinfo is None:
                _fail("R6 full-union BigQuery TIMESTAMP parameter is naive")
            return parsed.astimezone(timezone.utc)

        if value.array:
            if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
                _fail("R6 full-union BigQuery TIMESTAMP array differs")
            return [timestamp(item) for item in raw]
        return timestamp(raw)

    result: list[object] = []
    for value in spec.parameters:
        retained = parameter_value(value)
        if value.array:
            result.append(bigquery.ArrayQueryParameter(
                value.name, value.bq_type, list(retained)  # type: ignore[arg-type]
            ))
        else:
            result.append(bigquery.ScalarQueryParameter(
                value.name, value.bq_type, retained
            ))
    return result


def _parameter_api(values: Sequence[object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for value in values:
        method = getattr(value, "to_api_repr", None)
        if not callable(method):
            _fail("R6 full-union BigQuery parameter representation differs")
        raw = method()
        if not isinstance(raw, Mapping):
            _fail("R6 full-union BigQuery parameter representation differs")
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
        _fail("R6 full-union recovered BigQuery job configuration differs")


def _query_result(
    job: object,
    *,
    spec: registered.QuerySpec,
    parameters: Sequence[object],
    disposition: str,
) -> supply.FullUnionOutcomeQueryResultV1:
    _validate_job(job, spec=spec, parameters=parameters)
    try:
        completed = job.result()  # type: ignore[attr-defined]
        rows = tuple(
            dict(row.items()) if hasattr(row, "items") else dict(row)
            for row in completed
        )
    except Exception as exc:
        raise R6FullUnionOutcomeRunnerV1Error(
            "R6 full-union authoritative BigQuery job failed"
        ) from exc
    cache_hit = getattr(job, "cache_hit", None)
    if type(cache_hit) is not bool:
        _fail("R6 full-union BigQuery cache marker differs")
    total_bytes = getattr(job, "total_bytes_processed", None)
    if type(total_bytes) is not int or total_bytes < 0:
        _fail("R6 full-union BigQuery processed-byte count differs")
    if getattr(job, "error_result", None) is not None:
        _fail("R6 full-union authoritative BigQuery job has an error result")
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
    return supply.FullUnionOutcomeQueryResultV1(
        disposition=disposition,
        result=shared.QueryResult(rows=rows, job_receipt=receipt),
    )


def _get_or_create_query(
    client: object, spec: registered.QuerySpec,
) -> supply.FullUnionOutcomeQueryResultV1:
    from google.cloud import bigquery

    parameters = _query_parameters(spec)
    try:
        existing = client.get_job(  # type: ignore[attr-defined]
            spec.job_id, location=spec.location
        )
    except Exception as exc:
        if not _is_not_found(exc):
            raise R6FullUnionOutcomeRunnerV1Error(
                "R6 full-union fixed-ID BigQuery lookup failed"
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
        # Ambiguous create success may recover this exact ID only.  A failed
        # exact-ID recovery fails closed and never submits another job.
        try:
            job = client.get_job(  # type: ignore[attr-defined]
                spec.job_id, location=spec.location
            )
        except Exception as recovery_exc:
            raise R6FullUnionOutcomeRunnerV1Error(
                "R6 full-union fixed-ID BigQuery create/recovery failed"
            ) from recovery_exc
        disposition = "recovered"
    return _query_result(
        job, spec=spec, parameters=parameters, disposition=disposition
    )


def run_supply_cloud_v1(
    *,
    config: supply.FullUnionOutcomeSupplyConfigV1,
    panel_freeze_identity: Mapping[str, object],
    expected_actual_root_smoke_receipt_identity: Mapping[str, object],
    code_identities: SnapshotCodeIdentitiesV1,
    expected_lease_identity: Mapping[str, object],
    storage_client: object,
    bq_client_factory: Callable[[], object],
    clock: supply.Clock = lambda: datetime.now(timezone.utc),
) -> FullUnionOutcomeCloudResultV1:
    """Validate smoke first, then construct outcome-reading boundaries."""
    retained_config, retained_root_identity = _runtime_boundary(
        config, panel_freeze_identity
    )
    if not callable(bq_client_factory):
        _fail("R6 full-union BigQuery client factory differs")
    retained_lease_identity = _identity(
        expected_lease_identity, label="expected historical lease identity"
    )
    if (
        retained_lease_identity["uri"]
        != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
    ):
        _fail("expected historical-outcome lease URI differs")
    store = GenerationPinnedGCSV1(storage_client)
    authority = preflight_actual_root_smoke_v1(
        config=retained_config,
        panel_freeze_identity=retained_root_identity,
        expected_actual_root_smoke_receipt_identity=(
            expected_actual_root_smoke_receipt_identity
        ),
        code_identities=code_identities,
        store=store,
    )
    try:
        bq_client = bq_client_factory()
    except Exception as exc:
        raise R6FullUnionOutcomeRunnerV1Error(
            "R6 full-union BigQuery client construction failed"
        ) from exc
    if bq_client is None:
        _fail("R6 full-union BigQuery client construction returned None")
    lease_verifier = LiveLeaseVerifierV1(
        store, expected_identity=retained_lease_identity
    )
    supplied = supply.supply_full_union_outcome_snapshot_v1(
        config=retained_config,
        panel_freeze_identity=retained_root_identity,
        outcome_key_projection=authority.outcome_key_projection,
        outcome_key_projection_identity=(
            authority.outcome_key_projection_identity
        ),
        actual_root_smoke_receipt=authority.actual_root_smoke_receipt,
        actual_root_smoke_receipt_identity=(
            authority.actual_root_smoke_receipt_identity
        ),
        snapshot_module_sha256=(
            authority.code_identities.snapshot_module_sha256
        ),
        snapshot_cli_sha256=authority.code_identities.snapshot_cli_sha256,
        snapshot_test_sha256=authority.code_identities.snapshot_test_sha256,
        snapshot_cli_test_sha256=(
            authority.code_identities.snapshot_cli_test_sha256
        ),
        read_exact=store.read_exact,
        verify_lease=lease_verifier,
        read_table_metadata=lambda table: _table_metadata(bq_client, table),
        get_or_create_query=lambda spec: _get_or_create_query(bq_client, spec),
        publish=store.publish,
        read_known=store.read_known,
        clock=clock,
    )
    raw_lease = supplied.attempt.get("historical_outcome_lease")
    if not isinstance(raw_lease, Mapping):
        _fail("persisted historical lease body differs")
    raw_receipt = raw_lease.get("object_receipt")
    if not isinstance(raw_receipt, Mapping):
        _fail("persisted historical lease receipt differs")
    persisted_lease = _identity(
        {
            key: raw_receipt[key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
        label="persisted historical lease identity",
    )
    if persisted_lease != retained_lease_identity:
        _fail("persisted historical lease differs from expected identity")
    return FullUnionOutcomeCloudResultV1(
        supply=supplied,
        panel_freeze_identity=retained_root_identity,
        actual_root_smoke_receipt_identity=(
            authority.actual_root_smoke_receipt_identity
        ),
        historical_lease_identity=persisted_lease,
    )


run_cloud = run_supply_cloud_v1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)

    def common(operation: str) -> argparse.ArgumentParser:
        child = operations.add_parser(operation)
        child.add_argument("--execute", action="store_true")
        child.add_argument("--project", default=PROJECT)
        child.add_argument("--run-id", required=True)
        child.add_argument("--job", required=True)
        child.add_argument("--code-sha", required=True)
        child.add_argument("--image", required=True)
        child.add_argument("--panel-freeze-uri", required=True)
        child.add_argument("--panel-freeze-generation", required=True)
        child.add_argument("--panel-freeze-sha256", required=True)
        child.add_argument("--panel-freeze-bytes", type=int, required=True)
        child.add_argument("--snapshot-module-sha256", required=True)
        child.add_argument("--snapshot-cli-sha256", required=True)
        child.add_argument("--snapshot-test-sha256", required=True)
        child.add_argument("--snapshot-cli-test-sha256", required=True)
        return child

    common("smoke")
    supply_parser = common("supply")
    supply_parser.add_argument("--actual-root-smoke-uri", required=True)
    supply_parser.add_argument(
        "--actual-root-smoke-generation", required=True
    )
    supply_parser.add_argument("--actual-root-smoke-sha256", required=True)
    supply_parser.add_argument(
        "--actual-root-smoke-bytes", type=int, required=True
    )
    supply_parser.add_argument("--expected-lease-uri", required=True)
    supply_parser.add_argument("--expected-lease-generation", required=True)
    supply_parser.add_argument("--expected-lease-sha256", required=True)
    supply_parser.add_argument(
        "--expected-lease-bytes", type=int, required=True
    )
    return parser


def _validated_cli(
    args: argparse.Namespace, *, environ: Mapping[str, str],
) -> ValidatedCliV1:
    if args.operation not in {"smoke", "supply"}:
        _fail("R6 full-union outcome operation differs")
    enabled_env = SMOKE_ENABLED_ENV if args.operation == "smoke" else ENABLED_ENV
    if args.execute is not True or environ.get(enabled_env) != "1":
        _fail(f"--execute and {enabled_env}=1 are required explicitly")
    if args.project != PROJECT:
        _fail("R6 full-union outcome cloud project differs")
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
        _fail("R6 full-union outcome runtime identity differs")
    config = supply.FullUnionOutcomeSupplyConfigV1(
        run_id=args.run_id,
        job=args.job,
        code_sha=args.code_sha,
        image=args.image,
        enabled=True,
    )
    root_identity = _identity({
        "uri": args.panel_freeze_uri,
        "generation": args.panel_freeze_generation,
        "sha256": args.panel_freeze_sha256,
        "bytes": args.panel_freeze_bytes,
    }, label="R6 full-union panel-freeze identity")
    root_uri = str(root_identity["uri"])
    if (
        not root_uri.startswith(f"gs://{supply.OUTPUT_BUCKET}/research/")
        or not root_uri.endswith("/panel-freeze.json")
    ):
        _fail("R6 full-union panel-freeze URI differs")
    code = _code_identities(
        snapshot_module_sha256=args.snapshot_module_sha256,
        snapshot_cli_sha256=args.snapshot_cli_sha256,
        snapshot_test_sha256=args.snapshot_test_sha256,
        snapshot_cli_test_sha256=args.snapshot_cli_test_sha256,
    )
    if args.operation == "smoke":
        return ValidatedCliV1(
            operation="smoke",
            config=config,
            panel_freeze_identity=root_identity,
            code_identities=code,
            actual_root_smoke_receipt_identity=None,
            expected_lease_identity=None,
        )
    smoke_identity = _identity({
        "uri": args.actual_root_smoke_uri,
        "generation": args.actual_root_smoke_generation,
        "sha256": args.actual_root_smoke_sha256,
        "bytes": args.actual_root_smoke_bytes,
    }, label="expected actual-root smoke identity")
    if smoke_identity["uri"] != _output_uri(
        config, "actual-root-smoke-receipt.json"
    ):
        _fail("expected actual-root smoke URI differs")
    expected_lease_identity = _identity({
        "uri": args.expected_lease_uri,
        "generation": args.expected_lease_generation,
        "sha256": args.expected_lease_sha256,
        "bytes": args.expected_lease_bytes,
    }, label="expected historical lease identity")
    if (
        expected_lease_identity["uri"]
        != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
    ):
        _fail("expected historical-outcome lease URI differs")
    return ValidatedCliV1(
        operation="supply",
        config=config,
        panel_freeze_identity=root_identity,
        code_identities=code,
        actual_root_smoke_receipt_identity=smoke_identity,
        expected_lease_identity=expected_lease_identity,
    )


def _smoke_receipt_only(
    cloud: ActualRootSmokeCloudResultV1,
) -> dict[str, object]:
    authority = cloud.authority
    smoke_receipt = authority.actual_root_smoke_receipt
    body: dict[str, object] = {
        "schema_version": SMOKE_RECEIPT_SCHEMA,
        "status": "R6_FULL_UNION_ACTUAL_ROOT_SMOKE_CLOSED",
        "panel_freeze_identity": dict(authority.panel_freeze_identity),
        "outcome_key_projection_identity": dict(
            authority.outcome_key_projection_identity
        ),
        "actual_root_smoke_receipt_identity": dict(
            authority.actual_root_smoke_receipt_identity
        ),
        "later_source_freeze_identity": dict(
            authority.outcome_key_projection["later_source_freeze_identity"]
        ),
        "source_slate_count": smoke_receipt["source_slate_count"],
        "root_leaf_result_replay_count": smoke_receipt[
            "root_leaf_result_replay_count"
        ],
        "r0_r4_book_count": smoke_receipt["r0_r4_book_count"],
        "final_fit_book_count": smoke_receipt["final_fit_book_count"],
        "outcome_key_count": smoke_receipt["outcome_key_count"],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "historical_outcome_lease_acquired": False,
        "bigquery_client_constructed": False,
        "query_executed": False,
        "lineup_scoring_performed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    body["cli_receipt_sha256"] = supply.canonical_sha256(body)
    return body


def _receipt_only(cloud: FullUnionOutcomeCloudResultV1) -> dict[str, object]:
    result = cloud.supply
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "R6_FULL_UNION_OUTCOME_SNAPSHOT_CLOSED",
        "panel_freeze_identity": dict(cloud.panel_freeze_identity),
        "later_source_freeze_identity": dict(
            result.outcome_key_projection["later_source_freeze_identity"]
        ),
        "historical_outcome_lease_identity": dict(
            cloud.historical_lease_identity
        ),
        "outcome_key_projection_identity": dict(
            result.outcome_key_projection_identity
        ),
        "actual_root_smoke_receipt_identity": dict(
            cloud.actual_root_smoke_receipt_identity
        ),
        "attempt_identity": dict(result.attempt_identity),
        "query_evidence_identity": dict(result.query_evidence_identity),
        "realized_source_identity": dict(result.realized_source_identity),
        "outcome_snapshot_identity": dict(result.outcome_snapshot_identity),
        "completion_identity": dict(result.completion_identity),
        "query_job_id": result.completion["query_job_id"],
        "query_job_disposition": result.query_evidence[
            "query_job_disposition"
        ],
        "outcome_key_count": result.completion["outcome_key_count"],
        "one_historical_outcome_read": True,
        "rank_available": False,
        "roi_available": False,
        "graph_mutation_licensed": False,
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
    bq_client_factory: Callable[[], object] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    retained_environ = os.environ if environ is None else environ
    validated = _validated_cli(
        args, environ=retained_environ
    )
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client(project=PROJECT)
    if validated.operation == "smoke":
        smoke_result = run_actual_root_smoke_v1(
            config=validated.config,
            panel_freeze_identity=validated.panel_freeze_identity,
            code_identities=validated.code_identities,
            store=GenerationPinnedGCSV1(storage_client),
        )
        print(
            supply.canonical_json_bytes(
                _smoke_receipt_only(smoke_result)
            ).decode(),
            end="",
        )
        return 0
    if (
        validated.actual_root_smoke_receipt_identity is None
        or validated.expected_lease_identity is None
    ):
        raise AssertionError("validated supply CLI lacks smoke or lease identity")

    if bq_client_factory is None:
        def bq_client_factory() -> object:
            from google.cloud import bigquery

            return bigquery.Client(project=PROJECT)

    result = run_supply_cloud_v1(
        config=validated.config,
        panel_freeze_identity=validated.panel_freeze_identity,
        expected_actual_root_smoke_receipt_identity=(
            validated.actual_root_smoke_receipt_identity
        ),
        code_identities=validated.code_identities,
        expected_lease_identity=validated.expected_lease_identity,
        storage_client=storage_client,
        bq_client_factory=bq_client_factory,
    )
    print(supply.canonical_json_bytes(_receipt_only(result)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        R6FullUnionOutcomeRunnerV1Error,
        supply.CorpusR6FullUnionOutcomeSupplyV1Error,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


__all__ = [
    "ActualRootSmokeAuthorityV1",
    "ActualRootSmokeCloudResultV1",
    "ENABLED_ENV",
    "FullUnionOutcomeCloudResultV1",
    "GenerationPinnedGCSV1",
    "LiveLeaseVerifierV1",
    "PROJECT",
    "R6FullUnionOutcomeRunnerV1Error",
    "RECEIPT_SCHEMA",
    "SMOKE_ENABLED_ENV",
    "SMOKE_RECEIPT_SCHEMA",
    "SnapshotCodeIdentitiesV1",
    "main",
    "preflight_actual_root_smoke_v1",
    "run_actual_root_smoke_v1",
    "run_cloud",
    "run_supply_cloud_v1",
]
