#!/usr/bin/env python3
"""Default-off root-last runner for the R6 full-union realized grade.

The runner accepts only generation/SHA/byte-pinned upstream identities.  It
replays the complete one-query supply lineage and confirms the same live
historical-outcome lease before and after grading.  The reviewed grader then
publishes 54 create-once shards and its root last; this runner exact-reopens
and canonically regrades all of them before publishing a terminal completion.

No BigQuery, query, graph, IAM, production, promotion, or decision client is
constructed here.  Standard output contains identities and census counts
only, never player rows, lineup rows, scores, or aggregate score metrics.
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

from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release  # noqa: E402
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as outcomes  # noqa: E402
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as supply  # noqa: E402
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze  # noqa: E402
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading  # noqa: E402
from nfl_dfs.research import corpus_realized_outcome_transport as registered  # noqa: E402
from nfl_dfs.research import lr8_label_score_map as shared  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLED_ENV: Final = "R6_FULL_UNION_REALIZED_GRADE_ENABLED"
CODE_SHA_ENV: Final = "R6_FULL_UNION_REVIEWED_CODE_SHA"
IMAGE_ENV: Final = "R6_FULL_UNION_RUNTIME_IMAGE"
RECEIPT_SCHEMA: Final = "r6-full-union-realized-grade-cloud-receipt/v1"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")


class R6FullUnionRealizedGradeRunnerV1Error(RuntimeError):
    """The operational R6 score-once grade boundary failed closed."""


@dataclass(frozen=True, slots=True)
class ValidatedCliV1:
    config: release.FullUnionGradeReleaseConfigV1
    panel_freeze_identity: Mapping[str, object]
    outcome_supply_completion_identity: Mapping[str, object]
    outcome_key_projection_identity: Mapping[str, object]
    realized_source_identity: Mapping[str, object]
    outcome_snapshot_identity: Mapping[str, object]
    expected_lease_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class GradeBlindPreflightV1:
    """Only structural/outcome-blind objects opened before the live lease."""

    config: release.FullUnionGradeReleaseConfigV1
    panel_freeze: Mapping[str, object]
    panel_freeze_identity: Mapping[str, object]
    outcome_supply_completion: Mapping[str, object]
    outcome_supply_completion_identity: Mapping[str, object]
    outcome_key_projection: Mapping[str, object]
    outcome_key_projection_identity: Mapping[str, object]
    actual_root_smoke_receipt: Mapping[str, object]
    actual_root_smoke_receipt_identity: Mapping[str, object]
    supply_attempt: Mapping[str, object]
    supply_attempt_identity: Mapping[str, object]
    supply_attempt_created_at: datetime
    supply_query_evidence_identity: Mapping[str, object]
    realized_source_identity: Mapping[str, object]
    outcome_snapshot_identity: Mapping[str, object]
    historical_lease_binding: Mapping[str, object]
    supply_config: supply.FullUnionOutcomeSupplyConfigV1
    outcome_keys: Sequence[outcomes.OutcomeKeyV1]
    query_spec: registered.QuerySpec
    query_contract: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class GradePreflightAuthorityV1:
    panel_freeze: Mapping[str, object]
    panel_freeze_identity: Mapping[str, object]
    outcome_supply_completion: Mapping[str, object]
    outcome_supply_completion_identity: Mapping[str, object]
    actual_root_smoke_receipt: Mapping[str, object]
    actual_root_smoke_receipt_identity: Mapping[str, object]
    outcome_key_projection: Mapping[str, object]
    outcome_key_projection_identity: Mapping[str, object]
    realized_source: Mapping[str, object]
    realized_source_identity: Mapping[str, object]
    outcome_snapshot: Mapping[str, object]
    outcome_snapshot_identity: Mapping[str, object]
    supply_attempt: Mapping[str, object]
    supply_attempt_identity: Mapping[str, object]
    supply_query_evidence: Mapping[str, object]
    supply_query_evidence_identity: Mapping[str, object]
    historical_lease_binding: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class FullUnionRealizedGradeCloudResultV1:
    authority: GradePreflightAuthorityV1
    persisted_grade_root: Mapping[str, object]
    persisted_grade_root_identity: Mapping[str, object]
    grade_completion: Mapping[str, object]
    grade_completion_identity: Mapping[str, object]
    historical_lease_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StoredObjectV1:
    identity: Mapping[str, object]
    raw: bytes
    created_at: datetime


def _fail(message: str) -> None:
    raise R6FullUnionRealizedGradeRunnerV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _generation(value: object, *, label: str) -> str:
    if type(value) is int and value >= 1:
        return str(value)
    if type(value) is str and value.isdigit() and not value.startswith("0"):
        return value
    _fail(f"{label} generation differs")


def _aware_utc(value: object, *, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        _fail(f"{label} timestamp differs")
    return value.astimezone(timezone.utc)


def _parse_utc_text(value: object, *, label: str) -> datetime:
    if type(value) is not str:
        _fail(f"{label} timestamp differs")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(
            f"{label} timestamp differs"
        ) from exc
    if parsed.tzinfo is None:
        _fail(f"{label} timestamp differs")
    return parsed.astimezone(timezone.utc)


def _is_not_found(exc: Exception) -> bool:
    try:
        from google.api_core.exceptions import NotFound
    except ImportError:
        return type(exc).__name__ == "NotFound"
    return isinstance(exc, NotFound) or type(exc).__name__ == "NotFound"


def _gcs_parts(uri: str) -> tuple[str, str]:
    retained = _identity(
        {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
        label="R6 realized-grade GCS URI",
    )
    bucket, name = str(retained["uri"]).removeprefix("gs://").split("/", 1)
    return bucket, name


def _json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    return _mapping(value, label=label)


def _lease_json(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail("live historical-outcome lease bytes differ from writer law")
    return _json(raw[:-1], label="live historical-outcome lease")


class GenerationPinnedGCSV1:
    """Generation-pinned reads plus create-or-exact-equal recovery."""

    def __init__(self, client: object):
        self._client = client
        self._cache: dict[tuple[str, str, str, int], StoredObjectV1] = {}

    @staticmethod
    def _key(identity: Mapping[str, object]) -> tuple[str, str, str, int]:
        return (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )

    def resolve_exact(self, value: Mapping[str, object]) -> StoredObjectV1:
        identity = _identity(value, label="R6 realized-grade exact identity")
        key = self._key(identity)
        cached = self._cache.get(key)
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
            raise R6FullUnionRealizedGradeRunnerV1Error(
                "R6 realized-grade generation-pinned read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation, label="reopened object")
            != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("R6 realized-grade generation-pinned object differs")
        stored = StoredObjectV1(
            identity=identity,
            raw=raw,
            created_at=_aware_utc(
                blob.time_created, label="R6 realized-grade object creation"
            ),
        )
        self._cache[key] = stored
        return stored

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        return self.resolve_exact(value).raw

    def resolve_current(self, uri: str, *, absent_ok: bool) -> StoredObjectV1 | None:
        bucket_name, name = _gcs_parts(uri)
        try:
            current = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            current.reload()
        except Exception as exc:
            if absent_ok and _is_not_found(exc):
                return None
            raise R6FullUnionRealizedGradeRunnerV1Error(
                "R6 realized-grade current object resolution failed"
            ) from exc
        generation = _generation(
            current.generation, label="R6 realized-grade current object"
        )
        try:
            pinned = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise R6FullUnionRealizedGradeRunnerV1Error(
                "R6 realized-grade current generation reopen failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("R6 realized-grade current object is empty")
        identity = _identity({
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="R6 realized-grade current identity")
        stored = StoredObjectV1(
            identity=identity,
            raw=raw,
            created_at=_aware_utc(
                pinned.time_created, label="R6 realized-grade object creation"
            ),
        )
        self._cache[self._key(identity)] = stored
        return stored

    def resolve_required_current(self, uri: str) -> StoredObjectV1:
        retained = self.resolve_current(uri, absent_ok=False)
        if retained is None:  # pragma: no cover - absent_ok=False
            raise AssertionError("required current object resolved absent")
        return retained

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("R6 realized-grade publication payload differs")
        bucket_name, name = _gcs_parts(uri)
        try:
            blob = self._client.bucket(bucket_name).blob(name)  # type: ignore[attr-defined]
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0
            )
        except Exception:
            # Both a real collision and an ambiguous successful write are
            # resolved by one exact current-generation reopen below.
            pass
        reopened = self.resolve_required_current(uri)
        if reopened.raw != raw:
            _fail("existing R6 realized-grade object differs")
        return dict(reopened.identity)


class StableHistoricalLeaseV1:
    """Require one expected live lease generation and byte-identical body."""

    def __init__(
        self,
        store: GenerationPinnedGCSV1,
        *,
        expected_identity: Mapping[str, object],
        expected_binding: Mapping[str, object],
    ) -> None:
        self._store = store
        self._expected_identity = _identity(
            expected_identity, label="expected historical-outcome lease identity"
        )
        self._expected_binding = _mapping(
            expected_binding, label="supply-bound historical-outcome lease"
        )
        if self._expected_identity["uri"] != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI:
            _fail("expected historical-outcome lease URI differs")
        receipt = _mapping(
            self._expected_binding.get("object_receipt"),
            label="supply-bound historical-outcome lease receipt",
        )
        binding_identity = _identity(
            {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
            label="supply-bound historical-outcome lease identity",
        )
        if binding_identity != self._expected_identity:
            _fail("supply-bound historical-outcome lease identity differs")
        self._first_body: dict[str, object] | None = None

    def verify(self) -> dict[str, object]:
        current = self._store.resolve_required_current(
            shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
        )
        if dict(current.identity) != self._expected_identity:
            _fail("live historical-outcome lease identity changed")
        body = _lease_json(current.raw)
        if body != self._expected_binding.get("body"):
            _fail("live historical-outcome lease body differs from supply")
        if self._first_body is None:
            self._first_body = body
        elif body != self._first_body:
            _fail("historical-outcome lease body changed during grading")
        return {
            "body": dict(body),
            "object_receipt": {**self._expected_identity, "create_only": True},
        }


def _exact_json(
    store: GenerationPinnedGCSV1,
    identity: Mapping[str, object],
    *,
    label: str,
) -> tuple[dict[str, object], StoredObjectV1]:
    stored = store.resolve_exact(identity)
    return _json(stored.raw, label=label), stored


def _supply_config_from_attempt(
    *,
    config: release.FullUnionGradeReleaseConfigV1,
    completion: Mapping[str, object],
    attempt: Mapping[str, object],
) -> supply.FullUnionOutcomeSupplyConfigV1:
    lease = _mapping(
        attempt.get("historical_outcome_lease"), label="supply attempt lease"
    )
    body = _mapping(lease.get("body"), label="supply attempt lease body")
    if (
        completion.get("run_id") != config.expected_supply_run_id
        or body.get("run_id") != config.expected_supply_run_id
        or body.get("job") != config.expected_supply_job
        or body.get("code_sha") != config.expected_supply_code_sha
        or body.get("image") != config.expected_supply_image
    ):
        _fail("supply completion/lease runtime identity differs")
    return supply.FullUnionOutcomeSupplyConfigV1(
        run_id=config.expected_supply_run_id,
        job=config.expected_supply_job,
        code_sha=config.expected_supply_code_sha,
        image=config.expected_supply_image,
        enabled=True,
    )


def preflight_grade_authority_v1(
    *,
    config: release.FullUnionGradeReleaseConfigV1,
    panel_freeze_identity: Mapping[str, object],
    outcome_supply_completion_identity: Mapping[str, object],
    outcome_key_projection_identity: Mapping[str, object],
    realized_source_identity: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    store: GenerationPinnedGCSV1,
) -> GradeBlindPreflightV1:
    """Open only outcome-blind supply objects before live-lease proof."""
    retained_config = release.validate_grade_release_config_v1(config)
    panel_identity = _identity(panel_freeze_identity, label="panel-freeze identity")
    completion_identity = _identity(
        outcome_supply_completion_identity,
        label="outcome-supply completion identity",
    )
    projection_identity = _identity(
        outcome_key_projection_identity, label="outcome-key projection identity"
    )
    source_identity = _identity(
        realized_source_identity, label="realized source identity"
    )
    snapshot_identity = _identity(
        outcome_snapshot_identity, label="outcome snapshot identity"
    )

    panel, _ = _exact_json(store, panel_identity, label="panel-freeze root")
    completion, _ = _exact_json(
        store, completion_identity, label="outcome-supply completion"
    )
    projection, _ = _exact_json(
        store, projection_identity, label="outcome-key projection"
    )
    if (
        completion.get("run_id") != retained_config.expected_supply_run_id
        or completion.get("panel_freeze_identity") != panel_identity
        or completion.get("outcome_key_projection_identity") != projection_identity
        or completion.get("realized_source_identity") != source_identity
        or completion.get("outcome_snapshot_identity") != snapshot_identity
        or completion.get("historical_outcome_lease_release_required") is not True
        or completion.get("lease_release_owner") != supply.LEASE_RELEASE_OWNER
    ):
        _fail("outcome-supply completion/upstream identity binding differs")
    try:
        reopened_panel, reopened_panel_identity = freeze.reopen_panel_freeze_v1(
            panel_identity, read_exact=store.read_exact
        )
        projection_value, reopened_projection_identity, outcome_keys = (
            outcomes.validate_outcome_key_projection_v1(
                projection,
                identity=projection_identity,
                read_exact=store.read_exact,
            )
        )
    except (
        freeze.CorpusR6FullUnionPanelFreezeV1Error,
        outcomes.CorpusR6FullUnionOutcomeSnapshotV1Error,
    ) as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    if (
        reopened_panel_identity != panel_identity
        or reopened_projection_identity != projection_identity
        or panel != reopened_panel
    ):
        _fail("canonical outcome-blind upstream replay differs")

    smoke_identity = _identity(
        completion.get("actual_root_smoke_receipt_identity"),
        label="supply-bound actual-root smoke identity",
    )
    smoke_receipt, _ = _exact_json(
        store, smoke_identity, label="actual-root smoke receipt"
    )
    try:
        validated_smoke, validated_smoke_identity = (
            outcomes.validate_actual_root_smoke_receipt_v1(
                smoke_receipt,
                identity=smoke_identity,
                expected_panel_freeze_identity=panel_identity,
                outcome_key_projection=projection_value,
                expected_outcome_key_projection_identity=projection_identity,
                expected_reviewed_source_commit_sha=(
                    retained_config.expected_supply_code_sha
                ),
                expected_runtime_immutable_image=(
                    retained_config.expected_supply_image
                ),
                expected_snapshot_module_sha256=(
                    retained_config.snapshot_module_sha256
                ),
                expected_snapshot_cli_sha256=(
                    retained_config.snapshot_cli_sha256
                ),
                expected_snapshot_test_sha256=(
                    retained_config.snapshot_test_sha256
                ),
                expected_snapshot_cli_test_sha256=(
                    retained_config.snapshot_cli_test_sha256
                ),
                read_exact=store.read_exact,
            )
        )
    except outcomes.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    if validated_smoke_identity != smoke_identity:
        _fail("actual-root smoke pinned-provenance replay differs")

    attempt_identity = _identity(
        completion.get("attempt_identity"), label="supply attempt identity"
    )
    query_evidence_identity = _identity(
        completion.get("query_evidence_identity"),
        label="supply query-evidence identity",
    )
    attempt, attempt_stored = _exact_json(
        store, attempt_identity, label="outcome-supply attempt"
    )
    supply_config = _supply_config_from_attempt(
        config=retained_config, completion=completion, attempt=attempt
    )
    lease_binding = _mapping(
        attempt.get("historical_outcome_lease"),
        label="supply-bound historical-outcome lease",
    )
    query_contract = _mapping(
        attempt.get("query_contract"), label="supply query contract"
    )
    table_receipts_raw = attempt.get("table_receipts_before_query")
    if (
        isinstance(table_receipts_raw, (str, bytes))
        or not isinstance(table_receipts_raw, Sequence)
    ):
        _fail("supply table receipts differ")
    table_receipts = [
        _mapping(value, label=f"supply table receipt[{index}]")
        for index, value in enumerate(table_receipts_raw)
    ]
    try:
        legacy_config = supply._legacy_config(  # noqa: SLF001
            supply_config,
            panel_freeze_object_sha256=str(panel_identity["sha256"]),
        )
        spec, retained_query_contract = supply._query_spec_from_contract(  # noqa: SLF001
            query_contract,
            config=supply_config,
            legacy_config=legacy_config,
            outcome_keys=outcome_keys,
            panel_freeze_object_sha256=str(panel_identity["sha256"]),
        )
        validated_attempt = supply.validate_outcome_attempt_v1(
            attempt,
            config=supply_config,
            object_uri=str(attempt_identity["uri"]),
            panel_freeze_identity=panel_identity,
            projection=projection_value,
            projection_identity=projection_identity,
            smoke_receipt=validated_smoke,
            smoke_receipt_identity=smoke_identity,
            query_contract=retained_query_contract,
            table_receipts=table_receipts,
            lease=lease_binding,
        )
    except supply.CorpusR6FullUnionOutcomeSupplyV1Error as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    if (
        validated_attempt != attempt
        or completion.get("query_job_id") != spec.job_id
        or retained_config.output_root
        == str(completion_identity["uri"]).rsplit("/", 1)[0]
    ):
        _fail("outcome-blind supply lineage replay differs")

    return GradeBlindPreflightV1(
        config=retained_config,
        panel_freeze=reopened_panel,
        panel_freeze_identity=panel_identity,
        outcome_supply_completion=completion,
        outcome_supply_completion_identity=completion_identity,
        outcome_key_projection=projection_value,
        outcome_key_projection_identity=projection_identity,
        actual_root_smoke_receipt=validated_smoke,
        actual_root_smoke_receipt_identity=smoke_identity,
        supply_attempt=validated_attempt,
        supply_attempt_identity=attempt_identity,
        supply_attempt_created_at=attempt_stored.created_at,
        supply_query_evidence_identity=query_evidence_identity,
        realized_source_identity=source_identity,
        outcome_snapshot_identity=snapshot_identity,
        historical_lease_binding=lease_binding,
        supply_config=supply_config,
        outcome_keys=outcome_keys,
        query_spec=spec,
        query_contract=retained_query_contract,
    )


def open_outcome_grade_authority_v1(
    *,
    blind: GradeBlindPreflightV1,
    store: GenerationPinnedGCSV1,
) -> GradePreflightAuthorityV1:
    """Open score-bearing supply artifacts only after live-lease proof."""
    evidence, _ = _exact_json(
        store,
        blind.supply_query_evidence_identity,
        label="outcome-supply query evidence",
    )
    source, _ = _exact_json(
        store, blind.realized_source_identity, label="realized source"
    )
    outcome_snapshot, _ = _exact_json(
        store, blind.outcome_snapshot_identity, label="outcome snapshot"
    )
    try:
        source_value, reopened_source_identity, _ = (
            outcomes.validate_realized_source_v1(
                source,
                identity=blind.realized_source_identity,
                outcome_key_projection=blind.outcome_key_projection,
                outcome_key_projection_identity=(
                    blind.outcome_key_projection_identity
                ),
                read_exact=store.read_exact,
            )
        )
        snapshot_value, reopened_snapshot_identity, _ = (
            outcomes.validate_outcome_snapshot_v1(
                outcome_snapshot,
                identity=blind.outcome_snapshot_identity,
                outcome_key_projection=blind.outcome_key_projection,
                outcome_key_projection_identity=(
                    blind.outcome_key_projection_identity
                ),
                realized_source=source_value,
                realized_source_identity=blind.realized_source_identity,
                read_exact=store.read_exact,
            )
        )
        validated_evidence, registered_rows, _ = supply.validate_query_evidence_v1(
            evidence,
            config=blind.supply_config,
            object_uri=str(blind.supply_query_evidence_identity["uri"]),
            panel_freeze_identity=blind.panel_freeze_identity,
            projection=blind.outcome_key_projection,
            projection_identity=blind.outcome_key_projection_identity,
            smoke_receipt=blind.actual_root_smoke_receipt,
            smoke_receipt_identity=blind.actual_root_smoke_receipt_identity,
            attempt=blind.supply_attempt,
            attempt_identity=blind.supply_attempt_identity,
            attempt_created_at=blind.supply_attempt_created_at,
            spec=blind.query_spec,
            query_contract=blind.query_contract,
            outcome_keys=blind.outcome_keys,
        )
        expected_source = outcomes.build_realized_source_from_registered_rows_v1(
            outcome_key_projection=blind.outcome_key_projection,
            outcome_key_projection_identity=blind.outcome_key_projection_identity,
            registered_integer_micro_rows=registered_rows,
            read_exact=store.read_exact,
        )
        validated_completion = supply.validate_outcome_completion_v1(
            blind.outcome_supply_completion,
            config=blind.supply_config,
            object_uri=str(blind.outcome_supply_completion_identity["uri"]),
            panel_freeze_identity=blind.panel_freeze_identity,
            projection=blind.outcome_key_projection,
            projection_identity=blind.outcome_key_projection_identity,
            smoke_receipt=blind.actual_root_smoke_receipt,
            smoke_receipt_identity=blind.actual_root_smoke_receipt_identity,
            attempt_identity=blind.supply_attempt_identity,
            query_evidence_identity=blind.supply_query_evidence_identity,
            realized_source_identity=blind.realized_source_identity,
            outcome_snapshot_identity=blind.outcome_snapshot_identity,
            query_job_id=blind.query_spec.job_id,
        )
    except (
        supply.CorpusR6FullUnionOutcomeSupplyV1Error,
        outcomes.CorpusR6FullUnionOutcomeSnapshotV1Error,
    ) as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    if (
        reopened_source_identity != blind.realized_source_identity
        or reopened_snapshot_identity != blind.outcome_snapshot_identity
        or validated_evidence != evidence
        or validated_completion != blind.outcome_supply_completion
        or outcomes.canonical_json_bytes(expected_source)
        != outcomes.canonical_json_bytes(source_value)
    ):
        _fail("outcome-supply canonical lineage replay differs")
    return GradePreflightAuthorityV1(
        panel_freeze=blind.panel_freeze,
        panel_freeze_identity=blind.panel_freeze_identity,
        outcome_supply_completion=validated_completion,
        outcome_supply_completion_identity=(
            blind.outcome_supply_completion_identity
        ),
        actual_root_smoke_receipt=blind.actual_root_smoke_receipt,
        actual_root_smoke_receipt_identity=(
            blind.actual_root_smoke_receipt_identity
        ),
        outcome_key_projection=blind.outcome_key_projection,
        outcome_key_projection_identity=blind.outcome_key_projection_identity,
        realized_source=source_value,
        realized_source_identity=blind.realized_source_identity,
        outcome_snapshot=snapshot_value,
        outcome_snapshot_identity=blind.outcome_snapshot_identity,
        supply_attempt=blind.supply_attempt,
        supply_attempt_identity=blind.supply_attempt_identity,
        supply_query_evidence=validated_evidence,
        supply_query_evidence_identity=blind.supply_query_evidence_identity,
        historical_lease_binding=blind.historical_lease_binding,
    )


def run_grade_cloud_v1(
    *,
    config: release.FullUnionGradeReleaseConfigV1,
    panel_freeze_identity: Mapping[str, object],
    outcome_supply_completion_identity: Mapping[str, object],
    outcome_key_projection_identity: Mapping[str, object],
    realized_source_identity: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    expected_lease_identity: Mapping[str, object],
    storage_client: object,
) -> FullUnionRealizedGradeCloudResultV1:
    """Preflight, grade root-last, replay, recheck lease, then complete."""
    retained_config = release.validate_grade_release_config_v1(config)
    store = GenerationPinnedGCSV1(storage_client)
    blind = preflight_grade_authority_v1(
        config=retained_config,
        panel_freeze_identity=panel_freeze_identity,
        outcome_supply_completion_identity=outcome_supply_completion_identity,
        outcome_key_projection_identity=outcome_key_projection_identity,
        realized_source_identity=realized_source_identity,
        outcome_snapshot_identity=outcome_snapshot_identity,
        store=store,
    )
    lease = StableHistoricalLeaseV1(
        store,
        expected_identity=expected_lease_identity,
        expected_binding=blind.historical_lease_binding,
    )
    before = lease.verify()
    authority = open_outcome_grade_authority_v1(blind=blind, store=store)
    try:
        persisted_root, persisted_identity = (
            grading.grade_and_publish_r6_full_union_realized_v1(
                panel_freeze_identity=authority.panel_freeze_identity,
                outcome_key_projection=authority.outcome_key_projection,
                outcome_key_projection_identity=(
                    authority.outcome_key_projection_identity
                ),
                realized_source=authority.realized_source,
                realized_source_identity=authority.realized_source_identity,
                outcome_snapshot=authority.outcome_snapshot,
                outcome_snapshot_identity=authority.outcome_snapshot_identity,
                output_prefix=retained_config.output_root,
                read_exact=store.read_exact,
                publish_create_once=store.publish_create_once,
            )
        )
        (
            replayed_root,
            replayed_identity,
            _logical_root,
            replayed_shards,
        ) = grading.validate_persisted_realized_grade_v1(
            persisted_root,
            identity=persisted_identity,
            panel_freeze_identity=authority.panel_freeze_identity,
            outcome_key_projection=authority.outcome_key_projection,
            outcome_key_projection_identity=(
                authority.outcome_key_projection_identity
            ),
            realized_source=authority.realized_source,
            realized_source_identity=authority.realized_source_identity,
            outcome_snapshot=authority.outcome_snapshot,
            outcome_snapshot_identity=authority.outcome_snapshot_identity,
            read_exact=store.read_exact,
        )
    except grading.CorpusR6FullUnionRealizedGradingV1Error as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    if (
        replayed_identity != persisted_identity
        or grading.canonical_json_bytes(replayed_root)
        != grading.canonical_json_bytes(persisted_root)
        or len(replayed_shards) != grading.SOURCE_SLATE_COUNT
    ):
        _fail("persisted realized-grade canonical replay differs")
    after = lease.verify()
    if before != after:
        _fail("historical-outcome lease changed across grading")

    completion = release.build_grade_completion_v1(
        config=retained_config,
        panel_freeze_identity=authority.panel_freeze_identity,
        outcome_supply_completion=authority.outcome_supply_completion,
        outcome_supply_completion_identity=(
            authority.outcome_supply_completion_identity
        ),
        actual_root_smoke_receipt=authority.actual_root_smoke_receipt,
        actual_root_smoke_receipt_identity=(
            authority.actual_root_smoke_receipt_identity
        ),
        historical_outcome_lease=authority.historical_lease_binding,
        outcome_key_projection=authority.outcome_key_projection,
        outcome_key_projection_identity=authority.outcome_key_projection_identity,
        realized_source=authority.realized_source,
        realized_source_identity=authority.realized_source_identity,
        outcome_snapshot=authority.outcome_snapshot,
        outcome_snapshot_identity=authority.outcome_snapshot_identity,
        persisted_grade_root=replayed_root,
        persisted_grade_root_identity=replayed_identity,
    )
    completion_raw = release.canonical_json_bytes(completion)
    completion_identity = store.publish_create_once(
        retained_config.completion_uri, completion_raw
    )
    reopened_completion, _ = _exact_json(
        store, completion_identity, label="realized-grade completion"
    )
    try:
        validated_completion, validated_completion_identity = (
            release.validate_grade_completion_v1(
                reopened_completion,
                identity=completion_identity,
                config=retained_config,
                panel_freeze_identity=authority.panel_freeze_identity,
                outcome_supply_completion=authority.outcome_supply_completion,
                outcome_supply_completion_identity=(
                    authority.outcome_supply_completion_identity
                ),
                actual_root_smoke_receipt=authority.actual_root_smoke_receipt,
                actual_root_smoke_receipt_identity=(
                    authority.actual_root_smoke_receipt_identity
                ),
                historical_outcome_lease=authority.historical_lease_binding,
                outcome_key_projection=authority.outcome_key_projection,
                outcome_key_projection_identity=(
                    authority.outcome_key_projection_identity
                ),
                realized_source=authority.realized_source,
                realized_source_identity=authority.realized_source_identity,
                outcome_snapshot=authority.outcome_snapshot,
                outcome_snapshot_identity=authority.outcome_snapshot_identity,
                persisted_grade_root=replayed_root,
                persisted_grade_root_identity=replayed_identity,
            )
        )
    except release.CorpusR6FullUnionGradeReleaseV1Error as exc:
        raise R6FullUnionRealizedGradeRunnerV1Error(str(exc)) from exc
    if (
        validated_completion_identity != completion_identity
        or release.canonical_json_bytes(validated_completion) != completion_raw
    ):
        _fail("realized-grade completion exact recovery differs")
    return FullUnionRealizedGradeCloudResultV1(
        authority=authority,
        persisted_grade_root=replayed_root,
        persisted_grade_root_identity=replayed_identity,
        grade_completion=validated_completion,
        grade_completion_identity=validated_completion_identity,
        historical_lease_identity=_identity(
            expected_lease_identity, label="expected historical lease identity"
        ),
    )


run_cloud = run_grade_cloud_v1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-supply-run-id", required=True)
    parser.add_argument("--expected-supply-job", required=True)
    parser.add_argument("--expected-supply-code-sha", required=True)
    parser.add_argument("--expected-supply-image", required=True)
    parser.add_argument("--snapshot-module-sha256", required=True)
    parser.add_argument("--snapshot-cli-sha256", required=True)
    parser.add_argument("--snapshot-test-sha256", required=True)
    parser.add_argument("--snapshot-cli-test-sha256", required=True)

    def identity(prefix: str) -> None:
        parser.add_argument(f"--{prefix}-uri", required=True)
        parser.add_argument(f"--{prefix}-generation", required=True)
        parser.add_argument(f"--{prefix}-sha256", required=True)
        parser.add_argument(f"--{prefix}-bytes", type=int, required=True)

    identity("panel-freeze")
    identity("outcome-supply-completion")
    identity("outcome-key-projection")
    identity("realized-source")
    identity("outcome-snapshot")
    identity("expected-lease")
    return parser


def _arg_identity(
    args: argparse.Namespace, prefix: str, *, label: str,
) -> dict[str, object]:
    attr = prefix.replace("-", "_")
    return _identity({
        "uri": getattr(args, f"{attr}_uri"),
        "generation": getattr(args, f"{attr}_generation"),
        "sha256": getattr(args, f"{attr}_sha256"),
        "bytes": getattr(args, f"{attr}_bytes"),
    }, label=label)


def _validated_cli(
    args: argparse.Namespace, *, environ: Mapping[str, str],
) -> ValidatedCliV1:
    if args.execute is not True or environ.get(ENABLED_ENV) != "1":
        _fail(f"--execute and {ENABLED_ENV}=1 are required explicitly")
    if args.project != PROJECT:
        _fail("R6 realized-grade cloud project differs")
    runtime_job = environ.get("CLOUD_RUN_JOB")
    runtime_execution = environ.get("CLOUD_RUN_EXECUTION")
    if (
        type(args.run_id) is not str
        or _RUN_ID.fullmatch(args.run_id) is None
        or type(runtime_job) is not str
        or _JOB.fullmatch(runtime_job) is None
        or type(runtime_execution) is not str
        or _JOB.fullmatch(runtime_execution) is None
        or type(args.code_sha) is not str
        or _CODE_SHA.fullmatch(args.code_sha) is None
        or type(args.image) is not str
        or _IMAGE.fullmatch(args.image) is None
        or type(args.expected_supply_run_id) is not str
        or _RUN_ID.fullmatch(args.expected_supply_run_id) is None
        or type(args.expected_supply_job) is not str
        or _JOB.fullmatch(args.expected_supply_job) is None
        or type(args.expected_supply_code_sha) is not str
        or _CODE_SHA.fullmatch(args.expected_supply_code_sha) is None
        or type(args.expected_supply_image) is not str
        or _IMAGE.fullmatch(args.expected_supply_image) is None
        or any(_SHA256.fullmatch(value) is None for value in (
            args.snapshot_module_sha256,
            args.snapshot_cli_sha256,
            args.snapshot_test_sha256,
            args.snapshot_cli_test_sha256,
        ))
    ):
        _fail("R6 realized-grade runtime identity differs")
    if (
        environ.get("CLOUD_RUN_TASK_INDEX") != "0"
        or environ.get("CLOUD_RUN_TASK_COUNT") != "1"
        or environ.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
        or environ.get(CODE_SHA_ENV) != args.code_sha
        or environ.get(IMAGE_ENV) != args.image
    ):
        _fail("R6 realized-grade Cloud Run task/runtime envelope differs")
    config = release.FullUnionGradeReleaseConfigV1(
        run_id=args.run_id,
        job=runtime_job,
        execution=runtime_execution,
        code_sha=args.code_sha,
        image=args.image,
        expected_supply_run_id=args.expected_supply_run_id,
        expected_supply_job=args.expected_supply_job,
        expected_supply_code_sha=args.expected_supply_code_sha,
        expected_supply_image=args.expected_supply_image,
        snapshot_module_sha256=args.snapshot_module_sha256,
        snapshot_cli_sha256=args.snapshot_cli_sha256,
        snapshot_test_sha256=args.snapshot_test_sha256,
        snapshot_cli_test_sha256=args.snapshot_cli_test_sha256,
        enabled=True,
    )
    release.validate_grade_release_config_v1(config)
    panel_identity = _arg_identity(
        args, "panel-freeze", label="panel-freeze identity"
    )
    completion_identity = _arg_identity(
        args,
        "outcome-supply-completion",
        label="outcome-supply completion identity",
    )
    projection_identity = _arg_identity(
        args, "outcome-key-projection", label="outcome-key projection identity"
    )
    source_identity = _arg_identity(
        args, "realized-source", label="realized source identity"
    )
    snapshot_identity = _arg_identity(
        args, "outcome-snapshot", label="outcome snapshot identity"
    )
    lease_identity = _arg_identity(
        args, "expected-lease", label="expected historical lease identity"
    )
    panel_uri = str(panel_identity["uri"])
    supply_root = str(completion_identity["uri"]).removesuffix("/completion.json")
    if (
        not panel_uri.startswith(f"gs://{release.OUTPUT_BUCKET}/research/")
        or not panel_uri.endswith("/panel-freeze.json")
        or not str(completion_identity["uri"]).startswith(
            f"gs://{supply.OUTPUT_BUCKET}/{supply.OUTPUT_NAMESPACE}/"
        )
        or not str(completion_identity["uri"]).endswith("/completion.json")
        or projection_identity["uri"]
        != f"{supply_root}/outcome-key-projection.json"
        or source_identity["uri"] != f"{supply_root}/realized-source.json"
        or snapshot_identity["uri"] != f"{supply_root}/outcome-snapshot.json"
        or lease_identity["uri"] != shared.adapter.HISTORICAL_OUTCOME_LEASE_URI
    ):
        _fail("R6 realized-grade upstream URI law differs")
    return ValidatedCliV1(
        config=config,
        panel_freeze_identity=panel_identity,
        outcome_supply_completion_identity=completion_identity,
        outcome_key_projection_identity=projection_identity,
        realized_source_identity=source_identity,
        outcome_snapshot_identity=snapshot_identity,
        expected_lease_identity=lease_identity,
    )


def _receipt_only(
    result: FullUnionRealizedGradeCloudResultV1,
) -> dict[str, object]:
    completion = result.grade_completion
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "R6_FULL_UNION_REALIZED_GRADE_REPLAYED",
        "run_id": completion["run_id"],
        "job": completion["job"],
        "execution": completion["execution"],
        "code_sha": completion["code_sha"],
        "image": completion["image"],
        "expected_supply_run_id": completion["expected_supply_run_id"],
        "expected_supply_job": completion["expected_supply_job"],
        "expected_supply_code_sha": completion["expected_supply_code_sha"],
        "expected_supply_image": completion["expected_supply_image"],
        "actual_root_smoke_receipt_identity": dict(
            completion["actual_root_smoke_receipt_identity"]
        ),
        "historical_outcome_lease_identity": dict(
            completion["historical_outcome_lease_identity"]
        ),
        "panel_freeze_identity": dict(
            result.authority.panel_freeze_identity
        ),
        "outcome_supply_completion_identity": dict(
            result.authority.outcome_supply_completion_identity
        ),
        "outcome_key_projection_identity": dict(
            result.authority.outcome_key_projection_identity
        ),
        "realized_source_identity": dict(
            result.authority.realized_source_identity
        ),
        "outcome_snapshot_identity": dict(
            result.authority.outcome_snapshot_identity
        ),
        "persisted_grade_root_identity": dict(
            result.persisted_grade_root_identity
        ),
        "grade_completion_identity": dict(result.grade_completion_identity),
        "source_slate_count": completion["source_slate_count"],
        "slate_grade_object_count": completion["slate_grade_object_count"],
        "rank_80_book_count": completion["rank_80_book_count"],
        "prefix_grade_count": completion["prefix_grade_count"],
        "aggregate_cell_count": completion["aggregate_cell_count"],
        "canonical_persisted_grade_replay_complete": True,
        "contest_metrics_availability": "unavailable",
        "contest_rank_available": False,
        "contest_roi_available": False,
        "historical_outcome_lease_release_required": True,
        "runtime_task_index": 0,
        "runtime_task_count": 1,
        "runtime_task_attempt": 0,
        "terminal_execution_envelope_validated": False,
        "terminal_execution_envelope_validation_owner": (
            release.LEASE_RELEASE_OWNER
        ),
        "additional_historical_outcome_read": False,
        "bigquery_client_constructed": False,
        "outcome_query_executed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    body["cli_receipt_sha256"] = release.canonical_sha256(body)
    return body


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    retained_environ = os.environ if environ is None else environ
    validated = _validated_cli(args, environ=retained_environ)
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client(project=PROJECT)
    result = run_grade_cloud_v1(
        config=validated.config,
        panel_freeze_identity=validated.panel_freeze_identity,
        outcome_supply_completion_identity=(
            validated.outcome_supply_completion_identity
        ),
        outcome_key_projection_identity=(
            validated.outcome_key_projection_identity
        ),
        realized_source_identity=validated.realized_source_identity,
        outcome_snapshot_identity=validated.outcome_snapshot_identity,
        expected_lease_identity=validated.expected_lease_identity,
        storage_client=storage_client,
    )
    print(release.canonical_json_bytes(_receipt_only(result)).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        R6FullUnionRealizedGradeRunnerV1Error,
        release.CorpusR6FullUnionGradeReleaseV1Error,
        grading.CorpusR6FullUnionRealizedGradingV1Error,
        outcomes.CorpusR6FullUnionOutcomeSnapshotV1Error,
        supply.CorpusR6FullUnionOutcomeSupplyV1Error,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


__all__ = [
    "CODE_SHA_ENV",
    "ENABLED_ENV",
    "FullUnionRealizedGradeCloudResultV1",
    "GenerationPinnedGCSV1",
    "GradeBlindPreflightV1",
    "GradePreflightAuthorityV1",
    "IMAGE_ENV",
    "PROJECT",
    "R6FullUnionRealizedGradeRunnerV1Error",
    "RECEIPT_SCHEMA",
    "StableHistoricalLeaseV1",
    "ValidatedCliV1",
    "main",
    "open_outcome_grade_authority_v1",
    "preflight_grade_authority_v1",
    "run_cloud",
    "run_grade_cloud_v1",
]
