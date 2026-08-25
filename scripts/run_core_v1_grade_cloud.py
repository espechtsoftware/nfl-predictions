#!/usr/bin/env python3
"""Default-off cloud adapter for one completed Core v1 realized grade.

``grade`` exact-reopens the sharded catalog authority from its pinned root,
exact-reopens the completed outcome snapshot and all of its pinned
predecessors, invokes the established score-once grade publisher, and then
exact-reopens the published grade root before printing one compact receipt.
``reopen`` independently replays an already-published grade root.

The runner has no BigQuery, IAM, selector, graph, or object-list interface.
Google Cloud Storage is imported and constructed only after both explicit
execution gates pass.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research import (  # noqa: E402
    corpus_core_v1_catalog_materializer as catalog_store,
)
from nfl_dfs.research import corpus_core_v1_grade_publisher as grade_store  # noqa: E402
from nfl_dfs.research import corpus_core_v1_outcome_snapshot as outcome  # noqa: E402
from nfl_dfs.research import corpus_core_v1_outcome_supply as supply  # noqa: E402
from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLED_ENV: Final = "CORE_V1_GRADE_CLOUD_ENABLED"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = "research/corpus-core-v1-grades"
GRADE_RECEIPT_SCHEMA: Final = "core-v1-grade-cloud-publication-receipt/v1"
REOPEN_RECEIPT_SCHEMA: Final = "core-v1-grade-cloud-reopen-receipt/v1"
GRADE_COMPLETION_SCHEMA: Final = "core-v1-grade-cloud-completion/v1"
GRADE_COMPLETION_FILENAME: Final = "completion.json"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_OUTCOME_KEY_FIELDS: Final = frozenset({
    "source_ordinal",
    "season",
    "week",
    "slate_id",
    "source_kind",
    "source_key",
    "player_id",
})
_GRADE_COMPLETION_KEYS: Final = frozenset({
    "schema_version",
    "grade_run_id",
    "catalog_root_identity",
    "catalog_identity",
    "outcome_completion_identity",
    "player_source_identity",
    "outcome_snapshot_identity",
    "grade_root_identity",
    "realized_grade_sha256",
    "catalog_sha256",
    "outcome_snapshot_sha256",
    "slate_grade_shard_count",
    "coverage",
    "contest_metrics",
    "one_historical_outcome_read",
    "uses_realized_outcomes",
    "historical_retune_licensed",
    "historical_retry_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "grade_completion_sha256",
})


class CoreV1GradeCloudError(RuntimeError):
    """The default-off Core v1 grade boundary failed closed."""


@dataclass(frozen=True, slots=True)
class ReopenedCompletedOutcomes:
    completion: Mapping[str, object]
    completion_identity: Mapping[str, object]
    attempt_identity: Mapping[str, object]
    player_source: Mapping[str, object]
    player_source_identity: Mapping[str, object]
    outcome_snapshot: Mapping[str, object]
    outcome_snapshot_identity: Mapping[str, object]
    outcome_keys: tuple[outcome.CoreOutcomeKey, ...]


@dataclass(frozen=True, slots=True)
class PublishedGradeCompletion:
    completion: Mapping[str, object]
    completion_identity: Mapping[str, object]
    created: bool


def _fail(message: str) -> None:
    raise CoreV1GradeCloudError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1GradeCloudError(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1GradeCloudError(str(exc)) from exc


def _parse_json(raw: bytes, *, label: str) -> object:
    try:
        return batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1GradeCloudError(str(exc)) from exc


def _gcs_parts(uri: str) -> tuple[str, str]:
    identity = _identity(
        {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
        label="Core v1 grade cloud object URI",
    )
    bucket, name = str(identity["uri"]).removeprefix("gs://").split("/", 1)
    return bucket, name


def _generation(value: object, *, label: str) -> str:
    if type(value) is int and value >= 1:
        return str(value)
    if type(value) is str and value.isdigit() and not value.startswith("0"):
        return value
    _fail(f"{label} must be one positive generation")


class GenerationPinnedGCS:
    """Known-name generation GET and equal-content create-once publication."""

    def __init__(self, client: object):
        self._client = client

    def read_exact(self, value: Mapping[str, object]) -> bytes:
        identity = _identity(value, label="Core v1 grade exact-read identity")
        bucket_name, name = _gcs_parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise CoreV1GradeCloudError(
                "Core v1 grade generation-pinned read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or _generation(blob.generation, label="reopened object generation")
            != identity["generation"]
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("Core v1 grade generation-pinned object differs")
        return raw

    def resolve_current_exact(
        self, uri: str,
    ) -> tuple[dict[str, object], bytes]:
        bucket_name, name = _gcs_parts(uri)
        try:
            bucket = self._client.bucket(bucket_name)  # type: ignore[attr-defined]
            current = bucket.blob(name)
            current.reload()
            generation = _generation(
                current.generation,
                label="grade create-once recovered generation",
            )
        except Exception as exc:
            raise CoreV1GradeCloudError(
                "Core v1 grade create-once current resolution failed"
            ) from exc
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name, generation=int(generation)
            )
            blob.reload(if_generation_match=int(generation))
            raw = blob.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise CoreV1GradeCloudError(
                "Core v1 grade create-once recovery read failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail("Core v1 recovered grade object is empty")
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("Core v1 recovered grade bytes differ")
        return identity, raw

    def publish_create_once(
        self, uri: str, raw: bytes,
    ) -> grade_store.CreateOncePublication:
        _gcs_parts(uri)
        if type(raw) is not bytes or not raw:
            _fail("Core v1 grade create-once payload must be nonempty bytes")
        bucket_name, name = _gcs_parts(uri)
        created = False
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                name
            )
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
            created = True
        except Exception:
            created = False
        identity, reopened = self.resolve_current_exact(uri)
        if reopened != raw:
            _fail("existing Core v1 grade create-once object differs")
        return grade_store.CreateOncePublication(
            identity=identity, created=created
        )


def _read_json_exact(
    identity: Mapping[str, object],
    *,
    store: GenerationPinnedGCS,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained_identity = _identity(identity, label=f"{label} identity")
    raw = store.read_exact(retained_identity)
    value = dict(_mapping(_parse_json(raw, label=label), label=label))
    _json_identity(value, retained_identity, label=f"{label} identity")
    return retained_identity, value


def _add_gate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    grade = commands.add_parser(
        "grade", help="grade one completed Core v1 catalog/outcome pair"
    )
    _add_gate(grade)
    grade.add_argument("--grade-run-id", required=True)
    grade.add_argument("--max-logical-grade-bytes", type=int, required=True)
    grade.add_argument("--catalog-root-uri", required=True)
    grade.add_argument("--outcome-completion-uri", required=True)

    reopen = commands.add_parser(
        "reopen", help="known-name reopen one completed Core v1 grade"
    )
    _add_gate(reopen)
    reopen.add_argument("--grade-run-id", required=True)
    return parser


def _require_gate(
    args: argparse.Namespace, *, environ: Mapping[str, str],
) -> None:
    if args.execute is not True or environ.get(ENABLED_ENV) != "1":
        _fail(f"--execute and {ENABLED_ENV}=1 are required explicitly")
    if args.project != PROJECT:
        _fail("Core v1 grade cloud project differs")


def _grade_output_prefix(run_id: object) -> str:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("Core v1 grade run ID differs")
    return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{run_id}/"


def _grade_completion_uri(run_id: object) -> str:
    return _grade_output_prefix(run_id) + GRADE_COMPLETION_FILENAME


def _outcome_keys_from_attempt(
    attempt: Mapping[str, object],
) -> tuple[outcome.CoreOutcomeKey, ...]:
    raw_rows = _sequence(
        attempt.get("outcome_keys"), label="completed outcome keys"
    )
    rows: list[outcome.CoreOutcomeKey] = []
    for ordinal, raw in enumerate(raw_rows):
        row = _mapping(raw, label=f"completed outcome key[{ordinal}]")
        if frozenset(row) != _OUTCOME_KEY_FIELDS:
            _fail("completed outcome key fields differ")
        source_ordinal = row.get("source_ordinal")
        season = row.get("season")
        week = row.get("week")
        strings = {
            field: row.get(field)
            for field in ("slate_id", "source_kind", "source_key", "player_id")
        }
        if (
            type(source_ordinal) is not int
            or source_ordinal < 0
            or type(season) is not int
            or season < 2000
            or type(week) is not int
            or week < 1
            or any(
                type(value) is not str
                or not value
                or value.strip() != value
                for value in strings.values()
            )
        ):
            _fail("completed outcome key value differs")
        rows.append(outcome.CoreOutcomeKey(
            source_ordinal=source_ordinal,
            season=season,
            week=week,
            slate_id=str(strings["slate_id"]),
            source_kind=str(strings["source_kind"]),
            source_key=str(strings["source_key"]),
            player_id=str(strings["player_id"]),
        ))
    if not rows:
        _fail("completed outcome key union is empty")
    return tuple(rows)


def _reopen_completed_outcomes(
    *,
    completion_identity: Mapping[str, object],
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    store: GenerationPinnedGCS,
) -> ReopenedCompletedOutcomes:
    retained_completion_identity, completion = _read_json_exact(
        completion_identity,
        store=store,
        label="Core v1 outcome completion",
    )
    run_id = completion.get("run_id")
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("Core v1 outcome completion run ID differs")
    outcome_root = (
        f"gs://{supply.OUTPUT_BUCKET}/{supply.OUTPUT_NAMESPACE}/{run_id}"
    )
    if retained_completion_identity["uri"] != f"{outcome_root}/completion.json":
        _fail("Core v1 outcome completion URI differs from its known-name law")

    attempt_identity = _identity(
        completion.get("attempt_identity"), label="outcome attempt identity"
    )
    player_source_identity = _identity(
        completion.get("player_source_identity"),
        label="outcome player-source identity",
    )
    outcome_snapshot_identity = _identity(
        completion.get("outcome_snapshot_identity"),
        label="outcome snapshot identity",
    )
    expected_uris = {
        "attempt": f"{outcome_root}/read-attempt.json",
        "source": f"{outcome_root}/player-score-source.json",
        "snapshot": f"{outcome_root}/player-outcome-snapshot.json",
    }
    if (
        attempt_identity["uri"] != expected_uris["attempt"]
        or player_source_identity["uri"] != expected_uris["source"]
        or outcome_snapshot_identity["uri"] != expected_uris["snapshot"]
    ):
        _fail("Core v1 outcome predecessor URI differs from its known-name law")

    reopened_attempt_identity, attempt = _read_json_exact(
        attempt_identity, store=store, label="Core v1 outcome read attempt"
    )
    reopened_source_identity, player_source = _read_json_exact(
        player_source_identity,
        store=store,
        label="Core v1 realized player source",
    )
    reopened_snapshot_identity, outcome_snapshot = _read_json_exact(
        outcome_snapshot_identity,
        store=store,
        label="Core v1 player outcome snapshot",
    )
    if (
        player_source.get("attempt") != attempt
        or player_source.get("attempt_identity") != reopened_attempt_identity
    ):
        _fail("Core v1 completed player source differs from its exact attempt")
    outcome_keys = _outcome_keys_from_attempt(attempt)
    try:
        retained_source, source_identity, _ = outcome.validate_core_player_source(
            player_source,
            identity=reopened_source_identity,
            catalog=catalog,
            catalog_identity=catalog_identity,
            outcome_keys=outcome_keys,
        )
        retained_snapshot, snapshot_identity, _ = (
            outcome.validate_core_outcome_snapshot(
                outcome_snapshot,
                identity=reopened_snapshot_identity,
                catalog=catalog,
                catalog_identity=catalog_identity,
                player_source=retained_source,
                player_source_identity=source_identity,
                outcome_keys=outcome_keys,
            )
        )
        historical_lease = _mapping(
            attempt.get("historical_outcome_lease"),
            label="completed attempt historical lease",
        )
        lease_body = _mapping(
            historical_lease.get("body"),
            label="completed attempt historical lease body",
        )
        replay_config = supply.CoreOutcomeSupplyConfig(
            run_id=run_id,
            job=str(lease_body.get("job")),
            code_sha=str(lease_body.get("code_sha")),
            image=str(lease_body.get("image")),
            enabled=False,
        )
        retained_completion = supply.validate_core_outcome_completion(
            completion,
            config=replay_config,
            catalog_identity=catalog_identity,
            catalog_sha256=str(catalog["catalog_sha256"]),
            attempt_identity=reopened_attempt_identity,
            player_source_identity=source_identity,
            outcome_snapshot_identity=snapshot_identity,
            outcome_key_count=len(outcome_keys),
        )
    except (
        outcome.CorpusCoreV1OutcomeSnapshotError,
        supply.CorpusCoreV1OutcomeSupplyError,
    ) as exc:
        raise CoreV1GradeCloudError(str(exc)) from exc
    return ReopenedCompletedOutcomes(
        completion=retained_completion,
        completion_identity=retained_completion_identity,
        attempt_identity=reopened_attempt_identity,
        player_source=retained_source,
        player_source_identity=source_identity,
        outcome_snapshot=retained_snapshot,
        outcome_snapshot_identity=snapshot_identity,
        outcome_keys=outcome_keys,
    )


def _receipt(value: Mapping[str, object]) -> dict[str, object]:
    body = dict(value)
    body["cli_receipt_sha256"] = grade_store.canonical_sha256(body)
    return body


def _coverage_receipt(grade: Mapping[str, object]) -> dict[str, object]:
    coverage = _mapping(grade.get("coverage"), label="reopened grade coverage")
    return {
        key: coverage[key]
        for key in (
            "source_slate_count",
            "book_cell_count",
            "weekly_contrast_cell_count",
            "contrast_summary_count",
            "unique_union_roster_membership_count",
            "union_roster_sum_operation_count",
            "actual_player_outcome_row_count",
            "every_unique_union_roster_scored_exactly_once_per_slate",
            "all_registered_contrasts_reported_regardless_of_sign",
            "complete",
        )
    }


def _with_self_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    result = dict(value)
    result[field] = grade_store.canonical_sha256(result)
    return result


def _grade_completion_body(
    *,
    grade_run_id: str,
    catalog_authority: catalog_store.ReopenedShardedCoreV1Catalog,
    completed: ReopenedCompletedOutcomes,
    published: grade_store.PublishedShardedCoreV1Grade,
    reopened_grade: Mapping[str, object],
) -> dict[str, object]:
    return _with_self_hash({
        "schema_version": GRADE_COMPLETION_SCHEMA,
        "grade_run_id": grade_run_id,
        "catalog_root_identity": dict(catalog_authority.root_identity),
        "catalog_identity": dict(catalog_authority.catalog_identity),
        "outcome_completion_identity": dict(completed.completion_identity),
        "player_source_identity": dict(completed.player_source_identity),
        "outcome_snapshot_identity": dict(completed.outcome_snapshot_identity),
        "grade_root_identity": dict(published.root_identity),
        "realized_grade_sha256": reopened_grade["realized_grade_sha256"],
        "catalog_sha256": reopened_grade["catalog_authority"]["catalog_sha256"],
        "outcome_snapshot_sha256": reopened_grade[
            "actual_player_outcome_authority"
        ]["outcome_snapshot_sha256"],
        "slate_grade_shard_count": len(published.slate_shard_identities),
        "coverage": _coverage_receipt(reopened_grade),
        "contest_metrics": reopened_grade["contest_metrics"],
        "one_historical_outcome_read": completed.completion[
            "one_historical_outcome_read"
        ],
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, field="grade_completion_sha256")


def _validate_grade_completion(
    value: object,
    *,
    completion_identity: Mapping[str, object],
    reopened_grade: Mapping[str, object],
    catalog_authority: catalog_store.ReopenedShardedCoreV1Catalog,
    completed: ReopenedCompletedOutcomes,
) -> dict[str, object]:
    completion = dict(_mapping(value, label="Core v1 grade completion"))
    if frozenset(completion) != _GRADE_COMPLETION_KEYS:
        _fail("Core v1 grade completion fields differ")
    retained_hash = completion.get("grade_completion_sha256")
    body = {
        key: item
        for key, item in completion.items()
        if key != "grade_completion_sha256"
    }
    if (
        type(retained_hash) is not str
        or retained_hash != grade_store.canonical_sha256(body)
    ):
        _fail("Core v1 grade completion self-hash differs")
    run_id = completion.get("grade_run_id")
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("Core v1 grade completion run ID differs")
    retained_completion_identity = _identity(
        completion_identity, label="Core v1 grade completion identity"
    )
    catalog_root_identity = _identity(
        completion.get("catalog_root_identity"), label="catalog root identity"
    )
    catalog_identity = _identity(
        completion.get("catalog_identity"), label="catalog identity"
    )
    outcome_completion_identity = _identity(
        completion.get("outcome_completion_identity"),
        label="outcome completion identity",
    )
    player_source_identity = _identity(
        completion.get("player_source_identity"), label="player source identity"
    )
    outcome_snapshot_identity = _identity(
        completion.get("outcome_snapshot_identity"),
        label="outcome snapshot identity",
    )
    grade_root_identity = _identity(
        completion.get("grade_root_identity"), label="grade root identity"
    )
    grade_catalog_authority = _mapping(
        reopened_grade.get("catalog_authority"),
        label="reopened grade catalog authority",
    )
    grade_outcome_authority = _mapping(
        reopened_grade.get("actual_player_outcome_authority"),
        label="reopened grade outcome authority",
    )
    if (
        retained_completion_identity["uri"] != _grade_completion_uri(run_id)
        or grade_root_identity["uri"]
        != _grade_output_prefix(run_id) + grade_store.ROOT_FILENAME
        or completion.get("schema_version") != GRADE_COMPLETION_SCHEMA
        or completion.get("catalog_root_identity") != catalog_root_identity
        or completion.get("catalog_identity") != catalog_identity
        or completion.get("outcome_completion_identity")
        != outcome_completion_identity
        or completion.get("player_source_identity") != player_source_identity
        or completion.get("outcome_snapshot_identity")
        != outcome_snapshot_identity
        or completion.get("grade_root_identity") != grade_root_identity
        or catalog_root_identity != catalog_authority.root_identity
        or catalog_identity != catalog_authority.catalog_identity
        or outcome_completion_identity != completed.completion_identity
        or player_source_identity != completed.player_source_identity
        or outcome_snapshot_identity != completed.outcome_snapshot_identity
        or catalog_identity != grade_catalog_authority.get("catalog_identity")
        or player_source_identity != grade_outcome_authority.get(
            "source_identity"
        )
        or outcome_snapshot_identity != grade_outcome_authority.get(
            "outcome_snapshot_identity"
        )
        or completion.get("realized_grade_sha256")
        != reopened_grade["realized_grade_sha256"]
        or completion.get("catalog_sha256")
        != reopened_grade["catalog_authority"]["catalog_sha256"]
        or completion.get("catalog_sha256")
        != catalog_authority.logical_catalog.get("catalog_sha256")
        or completion.get("outcome_snapshot_sha256")
        != reopened_grade["actual_player_outcome_authority"][
            "outcome_snapshot_sha256"
        ]
        or completion.get("slate_grade_shard_count") != 54
        or completion.get("coverage") != _coverage_receipt(reopened_grade)
        or completion.get("contest_metrics") != reopened_grade["contest_metrics"]
        or completion.get("one_historical_outcome_read")
        != completed.completion.get("one_historical_outcome_read")
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("uses_realized_outcomes") is not True
        or any(completion.get(field) is not False for field in (
            "historical_retune_licensed",
            "historical_retry_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("Core v1 grade completion law differs")
    return completion


def _publish_grade_completion(
    *,
    grade_run_id: str,
    catalog_authority: catalog_store.ReopenedShardedCoreV1Catalog,
    completed: ReopenedCompletedOutcomes,
    published: grade_store.PublishedShardedCoreV1Grade,
    reopened_grade: Mapping[str, object],
    store: GenerationPinnedGCS,
) -> PublishedGradeCompletion:
    completion = _grade_completion_body(
        grade_run_id=grade_run_id,
        catalog_authority=catalog_authority,
        completed=completed,
        published=published,
        reopened_grade=reopened_grade,
    )
    raw = grade_store.canonical_json_bytes(completion)
    publication = store.publish_create_once(
        _grade_completion_uri(grade_run_id), raw
    )
    completion_identity, reopened = _read_json_exact(
        publication.identity,
        store=store,
        label="Core v1 grade completion",
    )
    if reopened != completion:
        _fail("Core v1 grade completion exact recovery differs")
    _validate_grade_completion(
        reopened,
        completion_identity=completion_identity,
        reopened_grade=reopened_grade,
        catalog_authority=catalog_authority,
        completed=completed,
    )
    return PublishedGradeCompletion(
        completion=completion,
        completion_identity=completion_identity,
        created=publication.created,
    )


def _reopen_grade_completion(
    *, grade_run_id: str, store: GenerationPinnedGCS,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    completion_identity, _ = store.resolve_current_exact(
        _grade_completion_uri(grade_run_id)
    )
    retained_identity, completion = _read_json_exact(
        completion_identity,
        store=store,
        label="Core v1 grade completion",
    )
    grade_root_identity = _identity(
        completion.get("grade_root_identity"), label="grade root identity"
    )
    catalog_root_identity = _identity(
        completion.get("catalog_root_identity"), label="catalog root identity"
    )
    outcome_completion_identity = _identity(
        completion.get("outcome_completion_identity"),
        label="outcome completion identity",
    )
    catalog_authority = catalog_store.reopen_sharded_core_v1_catalog_authority(
        root_identity=catalog_root_identity,
        read_exact=store.read_exact,
    )
    completed = _reopen_completed_outcomes(
        completion_identity=outcome_completion_identity,
        catalog=catalog_authority.logical_catalog,
        catalog_identity=catalog_authority.catalog_identity,
        store=store,
    )
    reopened_grade = grade_store.reopen_sharded_core_v1_realized_grade(
        root_identity=grade_root_identity,
        read_exact=store.read_exact,
    )
    retained_completion = _validate_grade_completion(
        completion,
        completion_identity=retained_identity,
        reopened_grade=reopened_grade,
        catalog_authority=catalog_authority,
        completed=completed,
    )
    return retained_completion, retained_identity, reopened_grade


def _grade_receipt(
    *,
    catalog_authority: catalog_store.ReopenedShardedCoreV1Catalog,
    completed: ReopenedCompletedOutcomes,
    published: grade_store.PublishedShardedCoreV1Grade,
    grade_completion: PublishedGradeCompletion,
    reopened_grade: Mapping[str, object],
) -> dict[str, object]:
    return _receipt({
        "schema_version": GRADE_RECEIPT_SCHEMA,
        "status": "CORE_V1_SHARDED_REALIZED_GRADE_CLOSED",
        "catalog_root_identity": dict(catalog_authority.root_identity),
        "catalog_identity": dict(catalog_authority.catalog_identity),
        "outcome_completion_identity": dict(completed.completion_identity),
        "player_source_identity": dict(completed.player_source_identity),
        "outcome_snapshot_identity": dict(completed.outcome_snapshot_identity),
        "grade_root_identity": dict(published.root_identity),
        "grade_completion_identity": dict(
            grade_completion.completion_identity
        ),
        "realized_grade_sha256": reopened_grade["realized_grade_sha256"],
        "catalog_sha256": reopened_grade["catalog_authority"]["catalog_sha256"],
        "outcome_snapshot_sha256": reopened_grade[
            "actual_player_outcome_authority"
        ]["outcome_snapshot_sha256"],
        "slate_grade_shard_count": len(published.slate_shard_identities),
        "summary_identity": dict(published.summary_identity),
        "created_slate_shard_count": published.created_slate_shard_count,
        "recovered_slate_shard_count": published.recovered_slate_shard_count,
        "summary_created": published.summary_created,
        "root_created": published.root_created,
        "grade_completion_created": grade_completion.created,
        "coverage": _coverage_receipt(reopened_grade),
        "contest_metrics": reopened_grade["contest_metrics"],
        "one_historical_outcome_read": completed.completion[
            "one_historical_outcome_read"
        ],
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    })


def _reopen_receipt(
    *,
    completion_identity: Mapping[str, object],
    completion: Mapping[str, object],
    reopened_grade: Mapping[str, object],
) -> dict[str, object]:
    return _receipt({
        "schema_version": REOPEN_RECEIPT_SCHEMA,
        "status": "CORE_V1_SHARDED_REALIZED_GRADE_REOPENED",
        "grade_completion_identity": dict(completion_identity),
        "grade_root_identity": dict(completion["grade_root_identity"]),
        "realized_grade_sha256": reopened_grade["realized_grade_sha256"],
        "catalog_sha256": reopened_grade["catalog_authority"]["catalog_sha256"],
        "outcome_snapshot_sha256": reopened_grade[
            "actual_player_outcome_authority"
        ]["outcome_snapshot_sha256"],
        "coverage": _coverage_receipt(reopened_grade),
        "contest_metrics": reopened_grade["contest_metrics"],
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    })


def _execute(
    args: argparse.Namespace, *, store: GenerationPinnedGCS,
) -> dict[str, object]:
    if args.command == "grade":
        output_prefix = _grade_output_prefix(args.grade_run_id)
        catalog_root_identity, _ = store.resolve_current_exact(
            args.catalog_root_uri
        )
        outcome_completion_identity, _ = store.resolve_current_exact(
            args.outcome_completion_uri
        )
        catalog_authority = catalog_store.reopen_sharded_core_v1_catalog_authority(
            root_identity=catalog_root_identity,
            read_exact=store.read_exact,
        )
        completed = _reopen_completed_outcomes(
            completion_identity=outcome_completion_identity,
            catalog=catalog_authority.logical_catalog,
            catalog_identity=catalog_authority.catalog_identity,
            store=store,
        )
        published = grade_store.grade_and_publish_sharded_core_v1(
            catalog=catalog_authority.logical_catalog,
            catalog_identity=catalog_authority.catalog_identity,
            outcome_snapshot=completed.outcome_snapshot,
            outcome_snapshot_identity=completed.outcome_snapshot_identity,
            player_source=completed.player_source,
            player_source_identity=completed.player_source_identity,
            outcome_keys=completed.outcome_keys,
            output_prefix=output_prefix,
            max_logical_grade_bytes=args.max_logical_grade_bytes,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
        reopened_grade = grade_store.reopen_sharded_core_v1_realized_grade(
            root_identity=published.root_identity,
            read_exact=store.read_exact,
        )
        grade_completion = _publish_grade_completion(
            grade_run_id=args.grade_run_id,
            catalog_authority=catalog_authority,
            completed=completed,
            published=published,
            reopened_grade=reopened_grade,
            store=store,
        )
        return _grade_receipt(
            catalog_authority=catalog_authority,
            completed=completed,
            published=published,
            grade_completion=grade_completion,
            reopened_grade=reopened_grade,
        )
    if args.command == "reopen":
        grade_run_id = args.grade_run_id
        _grade_output_prefix(grade_run_id)
        completion, completion_identity, reopened_grade = (
            _reopen_grade_completion(
                grade_run_id=grade_run_id,
                store=store,
            )
        )
        return _reopen_receipt(
            completion_identity=completion_identity,
            completion=completion,
            reopened_grade=reopened_grade,
        )
    raise AssertionError("argparse admitted an unknown Core v1 grade command")


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    retained_environ = os.environ if environ is None else environ
    _require_gate(args, environ=retained_environ)
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client(project=PROJECT)
    receipt = _execute(args, store=GenerationPinnedGCS(storage_client))
    print(grade_store.canonical_json_bytes(receipt).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CoreV1GradeCloudError,
        catalog_store.CorpusCoreV1CatalogMaterializerError,
        grade_store.CorpusCoreV1GradePublisherError,
        outcome.CorpusCoreV1OutcomeSnapshotError,
        supply.CorpusCoreV1OutcomeSupplyError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


__all__ = [
    "CoreV1GradeCloudError",
    "ENABLED_ENV",
    "GenerationPinnedGCS",
    "PROJECT",
    "ReopenedCompletedOutcomes",
    "main",
]
