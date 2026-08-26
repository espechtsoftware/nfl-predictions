"""Default-off one-read preparation for corpus realized grading.

The module has no cloud client and performs no I/O at import time.  Exact
reads, create-once publications, lease verification, table metadata, and the
sole query are callbacks owned by a future transport.  Before outcomes are
read it reopens the complete accepted 54-task batch graph, validates all 378
variant populations, and derives the exact player/DST source-key union from
the batch-bound later-source catalog.

After an attempt is durably created, one frozen BigQuery query may return the
union.  The result is converted to exact integer micro-DK, published, graded
through :mod:`corpus_realized_grading`, and independently replayed from the
reopened create-once objects.  This stage neither acquires nor releases the
shared historical-outcome lease and grants no retry, retune, graph mutation,
or production authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_grading as grading
from nfl_dfs.research import lr8_label_fit_adapter as lease_adapter
from nfl_dfs.research import lr8_label_score_map as shared
from nfl_dfs.research import lr8_later_period_source as later_source


SUPPLIER_SCHEMA: Final = "corpus-parametric-realized-outcome-supplier/v1"
ATTEMPT_SCHEMA: Final = "corpus-parametric-realized-read-attempt/v1"
SOURCE_SCHEMA: Final = "corpus-parametric-realized-player-source/v1"
COMPLETION_SCHEMA: Final = "corpus-parametric-realized-completion/v1"
QUERY_CONTRACT_SCHEMA: Final = "corpus-parametric-realized-query-contract/v1"
TRANSPORT_CONTRACT_SCHEMA: Final = "corpus-parametric-transport-contract/v2"
PROJECT: Final = "nfl-predictions-503414"
LOCATION: Final = "US"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = "research/corpus-realized-outcomes"
SKILL_TABLE: Final = shared.SKILL_TABLE
DST_TABLE: Final = shared.DST_TABLE
LEASE_RELEASE_OWNER: Final = "external-launcher-watcher"
SCORE_READ_STAGE: Final = "corpus-54x7-realized-score-read"

QUERY_ROW_FIELDS: Final = (
    "season", "week", "source_kind", "source_key", "realized_score",
)
SOURCE_ROW_FIELDS: Final = (
    "task_index", "season", "week", "slate_id", "source_kind",
    "source_key", "player_id", "realized_score_micro",
)

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")

_TRANSPORT_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "project", "region", "batch_id",
    "output_prefix", "batch_manifest_identity", "batch_manifest_sha256",
    "evidence_contract_identity", "retrieval_task0_prerequisite_identity",
    "foundation_publication_identity", "runtime_iam_evidence_identity",
    "prefix_claim_identity", "build", "service_account", "job",
    "manifest_input_identity_set_sha256", "task_count", "batch_mode",
    "matrix_cell_count", "complete_batch_acceptance_required", "tasks",
    "cloud_run_task_count", "cloud_run_parallelism", "max_retries",
    "task_attempt", "default_command", "default_args",
    "literal_execute_flag_required", "environment_execute_gate_required",
    "producer_and_verifier_separate_executions",
    "automatic_retry_licensed", "create_once", "uses_realized_outcomes",
    "historical_scoring_licensed", "corpus_fill_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "transport_contract_sha256",
})
_ATTEMPT_KEYS: Final = frozenset({
    "schema_version", "supplier_schema", "stage", "run_id",
    "batch_acceptance", "batch_manifest_sha256", "later_source_freeze",
    "task_count", "parameter_set_count", "task_arm_count",
    "generated_unique_membership_count", "distinct_task_roster_count",
    "union_player_dst_count", "union_keys", "union_keys_sha256",
    "query_sql_sha256", "query_spec", "historical_outcome_lease",
    "started_at", "uses_realized_outcomes_at_creation",
    "attempt_precedes_query", "historical_retry_licensed",
    "historical_retune_licensed", "graph_mutation_licensed",
    "production_change_licensed", "decision_authority", "attempt_sha256",
})
_SOURCE_KEYS: Final = frozenset({
    "schema_version", "supplier_schema", "batch_acceptance",
    "batch_manifest_sha256", "later_source_freeze", "attempt",
    "attempt_object", "query_spec", "job_receipt", "table_receipts",
    "source_snapshot_at", "row_fields", "row_count", "rows_sha256", "rows",
    "table_metadata_stable_during_query",
    "historical_outcome_lease_unchanged_during_query", "one_exact_query",
    "full_field_standings_included", "payout_ladder_included",
    "production_change_licensed", "source_sha256",
})
_COMPLETION_KEYS: Final = frozenset({
    "schema_version", "supplier_schema", "run_id", "batch_acceptance",
    "attempt", "attempt_object", "source_object", "outcome_bundle_object",
    "realized_grade", "realized_grade_sha256", "task_count",
    "parameter_set_count", "task_arm_count", "one_historical_outcome_read",
    "independent_replay_complete", "rank_available", "roi_available",
    "rank_roi_unavailable_reason",
    "historical_outcome_lease_release_required", "lease_release_owner",
    "historical_retry_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "completion_sha256",
})


class CorpusRealizedOutcomeError(RuntimeError):
    """The one-read outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class SupplierConfig:
    run_id: str
    job: str
    code_sha: str
    image: str
    expected_batch_acceptance_object_sha256: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return (
            f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"
        )


@dataclass(frozen=True, slots=True)
class PublishedObject:
    receipt: Mapping[str, object]
    reopened_raw: bytes
    created_at: str
    created: bool


@dataclass(frozen=True, slots=True)
class OutcomeKey:
    task_index: int
    season: int
    week: int
    slate_id: str
    player_id: str
    source_kind: str
    source_key: str


@dataclass(frozen=True, slots=True)
class QuerySpec:
    sql: str
    parameters: tuple[shared.QueryParameter, ...]
    job_id: str
    location: str
    sql_sha256: str
    parameters_sha256: str
    union_keys_sha256: str


@dataclass(frozen=True, slots=True)
class AcceptedBatchGraph:
    manifest: Mapping[str, object]
    manifest_identity: Mapping[str, object]
    completion: Mapping[str, object]
    completion_identity: Mapping[str, object]
    acceptance: Mapping[str, object]
    acceptance_identity: Mapping[str, object]
    accepted_tasks: tuple[Mapping[str, object], ...]
    source_freeze: Mapping[str, object]
    source_freeze_identity: Mapping[str, object]
    outcome_keys: tuple[OutcomeKey, ...]
    generated_unique_membership_count: int
    distinct_task_roster_count: int


@dataclass(frozen=True, slots=True)
class RealizedOutcomeSupply:
    attempt: Mapping[str, object]
    attempt_receipt: Mapping[str, object]
    source: Mapping[str, object]
    source_receipt: Mapping[str, object]
    outcome_bundle: Mapping[str, object]
    outcome_bundle_receipt: Mapping[str, object]
    completion: Mapping[str, object]
    completion_receipt: Mapping[str, object]


ExactReader = Callable[[Mapping[str, object]], bytes]
LeaseVerifier = Callable[[], Mapping[str, object]]
MetadataReader = Callable[[str], Mapping[str, object]]
QueryExecutor = Callable[[QuerySpec], shared.QueryResult]
Publisher = Callable[[str, bytes], PublishedObject]
Clock = Callable[[], datetime]


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusRealizedOutcomeError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CorpusRealizedOutcomeError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusRealizedOutcomeError(f"{label} must be a canonical string")
    return value


def _integer(
    value: object, *, label: str, minimum: int | None = 0,
) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise CorpusRealizedOutcomeError(f"{label} must be an exact integer")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CorpusRealizedOutcomeError(f"{label} must be a lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc


def _content_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) not in (
        {"uri", "generation", "sha256", "bytes"},
        {"uri", "generation", "sha256", "bytes", "create_only"},
    ):
        raise CorpusRealizedOutcomeError(f"{label} fields differ")
    if "create_only" in item and item["create_only"] is not True:
        raise CorpusRealizedOutcomeError(f"{label} is not create-only")
    return _identity(
        {key: item[key] for key in ("uri", "generation", "sha256", "bytes")},
        label=label,
    )


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != retained:
        raise CorpusRealizedOutcomeError(f"{label} self-hash differs")
    return retained


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    return dict(_mapping(parsed, label=label))


def _read_json(
    reader: ExactReader, value: object, *, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(value, label=f"{label} identity")
    try:
        raw = reader(identity)
    except Exception as exc:
        raise CorpusRealizedOutcomeError(f"{label} exact read failed") from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        raise CorpusRealizedOutcomeError(f"{label} content identity differs")
    return identity, _parse_json(raw, label=label)


def _validate_config(value: SupplierConfig) -> SupplierConfig:
    if not isinstance(value, SupplierConfig) or (
        _RUN_ID.fullmatch(value.run_id) is None
        or _JOB.fullmatch(value.job) is None
        or _CODE_SHA.fullmatch(value.code_sha) is None
        or _IMAGE.fullmatch(value.image) is None
        or _SHA256.fullmatch(value.expected_batch_acceptance_object_sha256)
        is None
    ):
        raise CorpusRealizedOutcomeError("realized outcome runtime identity differs")
    return value


def _prevalidate_acceptance(value: Mapping[str, object]) -> None:
    _self_hash(
        value, field="batch_acceptance_sha256", label="batch acceptance"
    )
    tasks = _sequence(
        value.get("task_acceptances"), label="batch task acceptances"
    )
    if (
        value.get("schema_version") != grading.BATCH_ACCEPTANCE_SCHEMA
        or value.get("batch_mode") != "complete-54-task"
        or value.get("task_count") != grading.EXPECTED_TASK_COUNT
        or value.get("parameter_set_count")
        != grading.EXPECTED_PARAMETER_SET_COUNT
        or value.get("matrix_cell_count") != grading.EXPECTED_TASK_ARM_COUNT
        or len(tasks) != grading.EXPECTED_TASK_COUNT
        or value.get("complete") is not True
        or value.get("accepted") is not True
        or value.get("partial_result") is not False
        or value.get("independent_verification_complete_for_every_task")
        is not True
        or any(value.get(field) is not False for field in (
            "automatic_retry_licensed", "uses_realized_outcomes",
            "historical_scoring_licensed", "corpus_fill_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        raise CorpusRealizedOutcomeError("batch is not complete accepted coverage")


def _validate_transport_contract(value: Mapping[str, object]) -> None:
    if set(value) != _TRANSPORT_KEYS:
        raise CorpusRealizedOutcomeError("transport contract fields differ")
    _self_hash(
        value, field="transport_contract_sha256", label="transport contract"
    )
    if (
        value.get("schema_version") != TRANSPORT_CONTRACT_SCHEMA
        or value.get("project") != PROJECT
        or value.get("region") != "us-central1"
        or value.get("task_count") != grading.EXPECTED_TASK_COUNT
        or value.get("batch_mode") != "complete-54-task"
        or value.get("matrix_cell_count") != grading.EXPECTED_TASK_ARM_COUNT
        or value.get("complete_batch_acceptance_required") is not True
        or value.get("cloud_run_task_count") != 1
        or value.get("cloud_run_parallelism") != 1
        or value.get("max_retries") != 0
        or value.get("task_attempt") != 0
        or value.get("default_command") != ["python"]
        or value.get("default_args")
        != ["scripts/run_corpus_parametric_transport.py", "parked"]
        or value.get("literal_execute_flag_required") is not True
        or value.get("environment_execute_gate_required") is not True
        or value.get("producer_and_verifier_separate_executions") is not True
        or value.get("create_once") is not True
        or any(value.get(field) is not False for field in (
            "automatic_retry_licensed", "uses_realized_outcomes",
            "historical_scoring_licensed", "corpus_fill_licensed",
            "graph_mutation_licensed", "production_change_licensed",
        ))
    ):
        raise CorpusRealizedOutcomeError("transport contract law differs")
    try:
        shared._utc(value.get("created_at_utc"), label="transport creation")  # noqa: SLF001
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    _digest(
        value.get("batch_manifest_sha256"), label="transport manifest SHA"
    )
    _digest(
        value.get("manifest_input_identity_set_sha256"),
        label="transport input set SHA",
    )
    _identity(value.get("batch_manifest_identity"), label="transport manifest")
    for field in (
        "evidence_contract_identity", "retrieval_task0_prerequisite_identity",
        "foundation_publication_identity", "runtime_iam_evidence_identity",
        "prefix_claim_identity",
    ):
        _identity(value.get(field), label=f"transport {field}")


def _transport_task_projection(task: Mapping[str, object]) -> dict[str, object]:
    prefix = str(task["variant_output_prefix"])
    transport = f"{prefix}transport/"
    result: dict[str, object] = {
        "task_index": task["task_index"],
        "task_sha256": task["task_sha256"],
        "variant_output_prefix": prefix,
        "result_receipt_uri": task["result_receipt_uri"],
        "science_terminal_uri": f"{prefix}task-terminal.json",
        "producer_close_uri": f"{transport}producer-close.json",
        "independent_verification_uri": (
            f"{transport}independent-verification.json"
        ),
        "accepted_terminal_uri": f"{transport}accepted-terminal.json",
    }
    for phase in ("producer", "verifier"):
        result[f"{phase}_launch_intent_uri"] = (
            f"{transport}{phase}-launch-intent.json"
        )
        result[f"{phase}_launch_ledger_uri"] = (
            f"{transport}{phase}-launch-ledger.json"
        )
        result[f"{phase}_execution_name_uri"] = (
            f"{transport}{phase}-execution-name.json"
        )
        result[f"{phase}_worker_completion_uri"] = (
            f"{transport}{phase}-worker-completion.json"
        )
    return result


def _validate_accepted_graph(
    *,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    completion: Mapping[str, object],
    completion_identity: Mapping[str, object],
    acceptance: Mapping[str, object],
    acceptance_identity: Mapping[str, object],
    accepted_tasks: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], int, int]:
    retained_results: list[dict[str, object]] = []
    task_acceptance_identities: list[dict[str, object]] = []
    populations: list[dict[str, object]] = []
    membership_count = 0
    distinct_by_task: dict[int, set[tuple[str, ...]]] = {
        index: set() for index in range(grading.EXPECTED_TASK_COUNT)
    }
    for task_index, (raw, task) in enumerate(
        zip(accepted_tasks, manifest["tasks"], strict=True)
    ):
        retained = _mapping(raw, label=f"accepted task[{task_index}]")
        task_acceptance = _mapping(
            retained.get("task_acceptance"),
            label=f"task[{task_index}] acceptance",
        )
        if (
            task_acceptance.get("transport_contract")
            != acceptance.get("transport_contract")
            or task_acceptance.get("retrieval_task0_prerequisite_identity")
            != acceptance.get("retrieval_task0_prerequisite_identity")
        ):
            raise CorpusRealizedOutcomeError(
                f"task[{task_index}] acceptance authority differs"
            )
        try:
            task_result = batch.validate_task_result_receipt(
                retained["task_result"],
                batch_manifest=manifest,
                batch_manifest_identity=manifest_identity,
            )
            task_result_identity = batch.validate_json_identity(
                task_result,
                retained["task_result_identity"],
                label=f"task[{task_index}] result identity",
            )
        except (KeyError, batch.CorpusParametricBatchError) as exc:
            raise CorpusRealizedOutcomeError(
                f"task[{task_index}] accepted result differs"
            ) from exc
        try:
            _, task_acceptance_identity = grading._validate_task_acceptance(  # noqa: SLF001
                task_acceptance,
                identity=retained["task_acceptance_identity"],
                task=task,
                task_result_identity=task_result_identity,
            )
        except grading.CorpusRealizedGradingError as exc:
            raise CorpusRealizedOutcomeError(
                f"task[{task_index}] acceptance replay differs"
            ) from exc
        task_acceptance_identities.append(task_acceptance_identity)
        retained_results.append({
            "receipt": task_result, "object_identity": task_result_identity,
        })
        raw_variants = _sequence(
            retained.get("variant_results"),
            label=f"task[{task_index}] variants",
        )
        if len(raw_variants) != grading.EXPECTED_PARAMETER_SET_COUNT:
            raise CorpusRealizedOutcomeError("accepted seven-arm coverage differs")
        for ordinal, (raw_variant, parameter_set, result_binding) in enumerate(
            zip(
                raw_variants,
                manifest["parameter_sets"],
                task_result["variant_results"],
                strict=True,
            )
        ):
            variant_row = _mapping(
                raw_variant, label=f"task[{task_index}] variant[{ordinal}]"
            )
            try:
                variant = grading._validate_variant_result(  # noqa: SLF001
                    variant_row["result"],
                    identity=variant_row["object_identity"],
                    expected_identity=result_binding["result_object"],
                    task=task,
                    parameter_set=parameter_set,
                )
            except grading.CorpusRealizedGradingError as exc:
                raise CorpusRealizedOutcomeError(
                    f"task[{task_index}] variant[{ordinal}] replay differs"
                ) from exc
            unique = variant["unique_rosters"]
            membership_count += len(unique)
            distinct_by_task[task_index].update(unique)
            populations.append({
                "task_index": task_index,
                "parameter_set_id": parameter_set["parameter_set_id"],
                "unique_rosters": unique,
            })
    try:
        validated_completion = batch.validate_batch_completion_receipt(
            completion,
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity,
            retained_task_results=retained_results,
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedOutcomeError("batch completion differs") from exc
    if validated_completion != completion:
        raise CorpusRealizedOutcomeError("batch completion replay differs")
    try:
        grading._validate_batch_acceptance(  # noqa: SLF001
            acceptance,
            identity=acceptance_identity,
            completion_identity=completion_identity,
            task_acceptance_identities=task_acceptance_identities,
        )
    except grading.CorpusRealizedGradingError as exc:
        raise CorpusRealizedOutcomeError(
            "batch acceptance replay differs"
        ) from exc
    return populations, membership_count, sum(
        len(rosters) for rosters in distinct_by_task.values()
    )


def _validate_source_freeze_projection(
    value: Mapping[str, object],
    *,
    expected_freeze_sha256: str,
    manifest: Mapping[str, object],
    populations: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], tuple[OutcomeKey, ...]]:
    try:
        frozen = later_source.validate_source_freeze(
            value, expected_freeze_sha256=expected_freeze_sha256
        )
    except later_source.LR8LaterSourceError as exc:
        raise CorpusRealizedOutcomeError(
            "later-source freeze binding differs"
        ) from exc
    slates = _sequence(frozen.get("slates"), label="later-source slates")
    if len(slates) != grading.EXPECTED_TASK_COUNT:
        raise CorpusRealizedOutcomeError("later-source slate coverage differs")
    required_by_task: dict[int, set[str]] = {
        index: set() for index in range(grading.EXPECTED_TASK_COUNT)
    }
    for population in populations:
        task_index = int(population["task_index"])
        required_by_task[task_index].update(
            player
            for roster in population["unique_rosters"]
            for player in roster
        )
    outcome_keys: list[OutcomeKey] = []
    for task_index, (raw_slate, task) in enumerate(
        zip(slates, manifest["tasks"], strict=True)
    ):
        slate = _mapping(raw_slate, label=f"source slate[{task_index}]")
        if (
            slate.get("season") != task["season"]
            or slate.get("week") != task["week"]
            or slate.get("slate_id") != task["slate_id"]
        ):
            raise CorpusRealizedOutcomeError("source/accepted slate identity differs")
        catalog = _sequence(
            slate.get("catalog"), label=f"source slate[{task_index}] catalog"
        )
        if slate.get("catalog_sha256") != later_source.canonical_sha256(catalog):
            raise CorpusRealizedOutcomeError("source catalog self-hash differs")
        catalog_by_id: dict[str, Mapping[str, object]] = {}
        observed_order: list[str] = []
        for raw_player in catalog:
            player = _mapping(raw_player, label="source catalog player")
            player_id = _string(player.get("id"), label="catalog player id")
            position = _string(player.get("pos"), label="catalog player position")
            team = _string(player.get("team"), label="catalog player team")
            observed_order.append(player_id)
            catalog_by_id[player_id] = {
                "position": position.upper(), "team": team.upper(),
            }
        if (
            observed_order != sorted(observed_order)
            or len(catalog_by_id) != len(observed_order)
            or not required_by_task[task_index] <= set(catalog_by_id)
        ):
            raise CorpusRealizedOutcomeError(
                "a generated player is absent from the frozen source catalog"
            )
        for player_id in sorted(required_by_task[task_index]):
            player = catalog_by_id[player_id]
            source_kind = "dst" if player["position"] == "DST" else "skill"
            source_key = player["team"] if source_kind == "dst" else player_id
            outcome_keys.append(OutcomeKey(
                task_index=task_index,
                season=int(task["season"]),
                week=int(task["week"]),
                slate_id=str(task["slate_id"]),
                player_id=player_id,
                source_kind=source_kind,
                source_key=str(source_key),
            ))
    source_keys = [
        (row.season, row.week, row.source_kind, row.source_key)
        for row in outcome_keys
    ]
    if (
        len(source_keys) != len(set(source_keys))
        or not any(row.source_kind == "skill" for row in outcome_keys)
        or not any(row.source_kind == "dst" for row in outcome_keys)
    ):
        raise CorpusRealizedOutcomeError("player/DST source-key union differs")
    ordered = tuple(sorted(
        outcome_keys,
        key=lambda row: (
            row.season, row.week, row.source_kind, row.source_key,
        ),
    ))
    return frozen, ordered


def reopen_accepted_batch(
    *,
    read_exact: ExactReader,
    batch_acceptance_identity: Mapping[str, object],
) -> AcceptedBatchGraph:
    """Reopen and validate the accepted graph before any outcome callback."""
    acceptance_identity, acceptance = _read_json(
        read_exact, batch_acceptance_identity, label="batch acceptance"
    )
    _prevalidate_acceptance(acceptance)
    transport_identity, transport = _read_json(
        read_exact, acceptance["transport_contract"], label="transport contract"
    )
    _validate_transport_contract(transport)
    if transport_identity != acceptance["transport_contract"]:
        raise CorpusRealizedOutcomeError("transport identity changed")
    manifest_identity, raw_manifest = _read_json(
        read_exact, transport["batch_manifest_identity"], label="batch manifest"
    )
    try:
        manifest = batch.validate_batch_manifest(raw_manifest)
        batch.validate_json_identity(
            manifest, manifest_identity, label="batch manifest identity"
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedOutcomeError("batch manifest replay differs") from exc
    if (
        len(manifest["tasks"]) != grading.EXPECTED_TASK_COUNT
        or acceptance_identity["uri"]
        != f"{manifest['output_prefix']}governance/batch-acceptance.json"
        or transport_identity["uri"]
        != (
            f"{manifest['output_prefix']}governance/"
            "parametric-transport-contract.json"
        )
        or transport.get("batch_id") != manifest["batch_id"]
        or transport.get("batch_manifest_sha256")
        != manifest["batch_manifest_sha256"]
        or transport.get("output_prefix") != manifest["output_prefix"]
        or transport.get("tasks") != [
            _transport_task_projection(task) for task in manifest["tasks"]
        ]
    ):
        raise CorpusRealizedOutcomeError("transport/manifest binding differs")
    completion_identity, completion = _read_json(
        read_exact, acceptance["batch_completion"], label="batch completion"
    )
    if completion_identity["uri"] != (
        f"{manifest['output_prefix']}governance/batch-completion.json"
    ):
        raise CorpusRealizedOutcomeError("batch completion URI differs")
    task_acceptance_ids = _sequence(
        acceptance["task_acceptances"], label="task acceptance identities"
    )
    completion_rows = _sequence(
        completion.get("task_results"), label="completion task results"
    )
    if not (
        len(task_acceptance_ids) == len(completion_rows)
        == grading.EXPECTED_TASK_COUNT
    ):
        raise CorpusRealizedOutcomeError("accepted task-result matrix differs")
    accepted_tasks: list[dict[str, object]] = []
    for task_index, (task_acceptance_id, completion_row) in enumerate(
        zip(task_acceptance_ids, completion_rows, strict=True)
    ):
        task_acceptance_identity, task_acceptance = _read_json(
            read_exact,
            task_acceptance_id,
            label=f"task[{task_index}] acceptance",
        )
        row = _mapping(completion_row, label=f"completion task[{task_index}]")
        task_result_identity, task_result = _read_json(
            read_exact,
            row["task_result_object"],
            label=f"task[{task_index}] result",
        )
        variant_results = []
        for ordinal, binding_raw in enumerate(_sequence(
            task_result.get("variant_results"),
            label=f"task[{task_index}] result variants",
        )):
            binding = _mapping(
                binding_raw, label=f"task[{task_index}] binding[{ordinal}]"
            )
            variant_identity, variant = _read_json(
                read_exact,
                binding["result_object"],
                label=f"task[{task_index}] variant[{ordinal}]",
            )
            variant_results.append({
                "result": variant, "object_identity": variant_identity,
            })
        accepted_tasks.append({
            "task_result": task_result,
            "task_result_identity": task_result_identity,
            "task_acceptance": task_acceptance,
            "task_acceptance_identity": task_acceptance_identity,
            "variant_results": variant_results,
        })
    populations, membership_count, distinct_rosters = _validate_accepted_graph(
        manifest=manifest,
        manifest_identity=manifest_identity,
        completion=completion,
        completion_identity=completion_identity,
        acceptance=acceptance,
        acceptance_identity=acceptance_identity,
        accepted_tasks=accepted_tasks,
    )
    source_identity = manifest["common_law"]["source_receipts"][
        "later_source_freeze"
    ]
    retained_source_identity, source = _read_json(
        read_exact, source_identity, label="later-source freeze"
    )
    if retained_source_identity != source_identity:
        raise CorpusRealizedOutcomeError("later-source identity changed")
    source, outcome_keys = _validate_source_freeze_projection(
        source,
        expected_freeze_sha256=manifest["common_law"][
            "later_source_freeze_manifest_sha256"
        ],
        manifest=manifest,
        populations=populations,
    )
    return AcceptedBatchGraph(
        manifest=manifest,
        manifest_identity=manifest_identity,
        completion=completion,
        completion_identity=completion_identity,
        acceptance=acceptance,
        acceptance_identity=acceptance_identity,
        accepted_tasks=tuple(accepted_tasks),
        source_freeze=source,
        source_freeze_identity=retained_source_identity,
        outcome_keys=outcome_keys,
        generated_unique_membership_count=membership_count,
        distinct_task_roster_count=distinct_rosters,
    )


def authoritative_score_sql() -> str:
    sql = f"""WITH skill_scores AS (
  SELECT a.season, a.week, 'skill' AS source_kind,
         CAST(a.gsis_id AS STRING) AS source_key,
         CAST(a.dk_points AS NUMERIC) AS realized_score
  FROM `{SKILL_TABLE}` AS a FOR SYSTEM_TIME AS OF @source_snapshot_at
  WHERE a.season IN UNNEST(@target_seasons)
    AND FORMAT('%d|%02d|%s', a.season, a.week, CAST(a.gsis_id AS STRING))
      IN UNNEST(@skill_keys)
), dst_scores AS (
  SELECT d.season, d.week, 'dst' AS source_kind,
         UPPER(CAST(d.team AS STRING)) AS source_key,
         CAST(d.dst_dk_points AS NUMERIC) AS realized_score
  FROM `{DST_TABLE}` AS d FOR SYSTEM_TIME AS OF @source_snapshot_at
  WHERE d.season IN UNNEST(@target_seasons)
    AND FORMAT('%d|%02d|%s', d.season, d.week, UPPER(CAST(d.team AS STRING)))
      IN UNNEST(@dst_keys)
)
SELECT season, week, source_kind, source_key, realized_score FROM skill_scores
UNION ALL
SELECT season, week, source_kind, source_key, realized_score FROM dst_scores
ORDER BY season, week, source_kind, source_key"""
    compact = f" {sql.lower()} "
    if any(token in compact for token in (
        " contest", " ownership", " payout", " standings", " winner",
        " insert ", " update ", " merge ", " delete ",
    )):
        raise AssertionError("corpus realized SQL exceeded its frozen boundary")
    return sql


AUTHORITATIVE_SCORE_SQL: Final = authoritative_score_sql()
AUTHORITATIVE_SCORE_SQL_SHA256: Final = sha256(
    AUTHORITATIVE_SCORE_SQL.encode("utf-8")
).hexdigest()


def _union_payload(values: Sequence[OutcomeKey]) -> list[dict[str, object]]:
    return [{
        "task_index": row.task_index,
        "season": row.season,
        "week": row.week,
        "slate_id": row.slate_id,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
    } for row in values]


def _parameter_payload(
    parameters: Sequence[shared.QueryParameter],
) -> list[dict[str, object]]:
    return [{
        "name": row.name,
        "type": row.bq_type,
        "array": row.array,
        "value": row.value,
    } for row in parameters]


def build_query_spec(
    *,
    config: SupplierConfig,
    outcome_keys: Sequence[OutcomeKey],
    source_snapshot_at: str,
) -> QuerySpec:
    config = _validate_config(config)
    try:
        snapshot, _ = shared._utc(  # noqa: SLF001
            source_snapshot_at, label="source snapshot"
        )
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    rows = tuple(outcome_keys)
    skill = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in rows if row.source_kind == "skill"
    )
    dst = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in rows if row.source_kind == "dst"
    )
    if (
        not skill
        or not dst
        or len(skill) + len(dst) != len(rows)
        or len(skill) != len(set(skill))
        or len(dst) != len(set(dst))
    ):
        raise CorpusRealizedOutcomeError("query player/DST union differs")
    seasons = sorted({row.season for row in rows})
    parameters = (
        shared.QueryParameter("source_snapshot_at", "TIMESTAMP", snapshot),
        shared.QueryParameter("target_seasons", "INT64", seasons, True),
        shared.QueryParameter("skill_keys", "STRING", skill, True),
        shared.QueryParameter("dst_keys", "STRING", dst, True),
    )
    payload = _parameter_payload(parameters)
    return QuerySpec(
        sql=AUTHORITATIVE_SCORE_SQL,
        parameters=parameters,
        job_id=deterministic_query_job_id(config),
        location=LOCATION,
        sql_sha256=AUTHORITATIVE_SCORE_SQL_SHA256,
        parameters_sha256=canonical_sha256(payload),
        union_keys_sha256=canonical_sha256(_union_payload(rows)),
    )


def deterministic_query_job_id(config: SupplierConfig) -> str:
    """Return the only BigQuery job id licensed for one realized run."""
    config = _validate_config(config)
    return (
        f"corpus_realized_{config.run_id.replace('-', '_')[:42]}_"
        f"{config.expected_batch_acceptance_object_sha256[:12]}"
    )


def _query_contract(spec: QuerySpec) -> dict[str, object]:
    return {
        "schema_version": QUERY_CONTRACT_SCHEMA,
        "job_id": spec.job_id,
        "location": spec.location,
        "sql_sha256": spec.sql_sha256,
        "parameters": _parameter_payload(spec.parameters),
        "parameters_sha256": spec.parameters_sha256,
        "union_keys_sha256": spec.union_keys_sha256,
        "tables": [SKILL_TABLE, DST_TABLE],
        "selected_columns": list(QUERY_ROW_FIELDS),
        "source_snapshot_at": spec.parameters[0].value,
        "query_count": 1,
        "use_query_cache": False,
    }


def _query_rows(
    values: object, *, outcome_keys: Sequence[OutcomeKey],
) -> list[dict[str, object]]:
    rows = _sequence(values, label="authoritative query rows")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in outcome_keys
    }
    result: list[dict[str, object]] = []
    for raw in rows:
        item = _mapping(raw, label="authoritative query row")
        if set(item) != set(QUERY_ROW_FIELDS):
            raise CorpusRealizedOutcomeError("authoritative query row fields differ")
        key = (
            _integer(item["season"], label="query season"),
            _integer(item["week"], label="query week", minimum=1),
            _string(item["source_kind"], label="query source kind"),
            _string(item["source_key"], label="query source key"),
        )
        catalog = expected.get(key)
        if catalog is None:
            raise CorpusRealizedOutcomeError("query returned a non-union key")
        try:
            score = shared._micro_score(item["realized_score"])  # noqa: SLF001
        except shared.LR8ScoreMapError as exc:
            raise CorpusRealizedOutcomeError(str(exc)) from exc
        result.append({
            "task_index": catalog.task_index,
            "season": catalog.season,
            "week": catalog.week,
            "slate_id": catalog.slate_id,
            "source_kind": catalog.source_kind,
            "source_key": catalog.source_key,
            "player_id": catalog.player_id,
            "realized_score_micro": score,
        })
    observed = [
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in result
    ]
    if observed != sorted(expected):
        raise CorpusRealizedOutcomeError(
            "query result is not the exact ordered player/DST union"
        )
    return result


def _retained_source_rows(
    values: object, *, outcome_keys: Sequence[OutcomeKey],
) -> list[dict[str, object]]:
    rows = _sequence(values, label="retained realized source rows")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in outcome_keys
    }
    result: list[dict[str, object]] = []
    for raw in rows:
        item = _mapping(raw, label="retained realized source row")
        if set(item) != set(SOURCE_ROW_FIELDS):
            raise CorpusRealizedOutcomeError(
                "retained realized source row fields differ"
            )
        key = (
            _integer(item["season"], label="source season"),
            _integer(item["week"], label="source week", minimum=1),
            _string(item["source_kind"], label="source kind"),
            _string(item["source_key"], label="source key"),
        )
        catalog = expected.get(key)
        if catalog is None or any((
            item["task_index"] != catalog.task_index,
            item["slate_id"] != catalog.slate_id,
            item["player_id"] != catalog.player_id,
        )):
            raise CorpusRealizedOutcomeError(
                "retained source row is outside the frozen player/DST union"
            )
        score = _integer(
            item["realized_score_micro"],
            label="source realized score micro",
            minimum=None,
        )
        if abs(score) > grading.MAX_ABS_PLAYER_SCORE_MICRO:
            raise CorpusRealizedOutcomeError(
                "source realized score exceeds exact grading bounds"
            )
        result.append(dict(item))
    observed = [
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in result
    ]
    if observed != sorted(expected):
        raise CorpusRealizedOutcomeError(
            "retained source is not the exact ordered player/DST union"
        )
    return result


def _now(clock: Clock, *, label: str) -> tuple[str, datetime]:
    value = clock()
    if not isinstance(value, datetime):
        raise CorpusRealizedOutcomeError(f"{label} clock differs")
    if value.tzinfo is None or value.utcoffset() is None:
        raise CorpusRealizedOutcomeError(f"{label} clock must be aware")
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(), normalized


def _publish(
    publisher: Publisher,
    *,
    uri: str,
    payload: Mapping[str, object],
    earliest: datetime,
    label: str,
) -> tuple[dict[str, object], datetime, dict[str, object]]:
    raw = canonical_json_bytes(payload)
    published = publisher(uri, raw)
    if not isinstance(published, PublishedObject) or published.created is not True:
        raise CorpusRealizedOutcomeError(f"{label} was not create-once")
    receipt = _content_identity(published.receipt, label=f"{label} receipt")
    if _mapping(published.receipt, label=f"{label} receipt").get(
        "create_only"
    ) is not True:
        raise CorpusRealizedOutcomeError(f"{label} receipt is not create-only")
    try:
        created_text, created = shared._utc(  # noqa: SLF001
            published.created_at, label=f"{label} creation"
        )
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    if (
        receipt["uri"] != uri
        or receipt["sha256"] != sha256(raw).hexdigest()
        or receipt["bytes"] != len(raw)
        or published.reopened_raw != raw
        or created < earliest
        or created_text != published.created_at
    ):
        raise CorpusRealizedOutcomeError(f"{label} create-once reopen differs")
    reopened = _parse_json(published.reopened_raw, label=f"reopened {label}")
    if reopened != payload:
        raise CorpusRealizedOutcomeError(f"{label} reopened payload differs")
    return {**receipt, "create_only": True}, created, reopened


def _lease(
    value: object, *, config: SupplierConfig,
) -> dict[str, object]:
    lease_config = shared.SupplierConfig(
        run_id=config.run_id,
        job=config.job,
        code_sha=config.code_sha,
        image=config.image,
        expected_source_manifest_sha256=(
            config.expected_batch_acceptance_object_sha256
        ),
        enabled=True,
    )
    try:
        return shared._validate_lease(value, config=lease_config)  # noqa: SLF001
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc


def _table_receipt(value: object, *, table: str) -> dict[str, object]:
    try:
        return shared._table_receipt(value, table=table)  # noqa: SLF001
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc


def _validate_attempt(
    value: Mapping[str, object],
    *,
    config: SupplierConfig,
    graph: AcceptedBatchGraph,
    lease: Mapping[str, object],
    spec: QuerySpec,
) -> dict[str, object]:
    if set(value) != _ATTEMPT_KEYS:
        raise CorpusRealizedOutcomeError("realized read attempt fields differ")
    _self_hash(value, field="attempt_sha256", label="realized read attempt")
    union = _union_payload(graph.outcome_keys)
    try:
        shared._utc(value.get("started_at"), label="attempt started_at")  # noqa: SLF001
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    if (
        value.get("schema_version") != ATTEMPT_SCHEMA
        or value.get("supplier_schema") != SUPPLIER_SCHEMA
        or value.get("stage") != SCORE_READ_STAGE
        or value.get("run_id") != config.run_id
        or value.get("batch_acceptance") != graph.acceptance_identity
        or value.get("batch_manifest_sha256")
        != graph.manifest["batch_manifest_sha256"]
        or value.get("later_source_freeze") != graph.source_freeze_identity
        or value.get("task_count") != grading.EXPECTED_TASK_COUNT
        or value.get("parameter_set_count")
        != grading.EXPECTED_PARAMETER_SET_COUNT
        or value.get("task_arm_count") != grading.EXPECTED_TASK_ARM_COUNT
        or value.get("generated_unique_membership_count")
        != graph.generated_unique_membership_count
        or value.get("distinct_task_roster_count")
        != graph.distinct_task_roster_count
        or value.get("union_player_dst_count") != len(union)
        or value.get("union_keys") != union
        or value.get("union_keys_sha256") != canonical_sha256(union)
        or value.get("query_sql_sha256") != AUTHORITATIVE_SCORE_SQL_SHA256
        or value.get("query_spec") != _query_contract(spec)
        or value.get("historical_outcome_lease") != lease
        or value.get("uses_realized_outcomes_at_creation") is not False
        or value.get("attempt_precedes_query") is not True
        or any(value.get(field) is not False for field in (
            "historical_retry_licensed", "historical_retune_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        raise CorpusRealizedOutcomeError("realized read attempt replay differs")
    return dict(value)


def _job_receipt(
    value: object, *, spec: QuerySpec, not_before: datetime,
) -> tuple[dict[str, object], datetime]:
    try:
        return shared._job_receipt(  # noqa: SLF001
            value, spec=spec, not_before=not_before
        )
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc


def _validate_source(
    value: Mapping[str, object],
    *,
    graph: AcceptedBatchGraph,
    attempt: Mapping[str, object],
    attempt_receipt: Mapping[str, object],
    spec: QuerySpec,
) -> list[dict[str, object]]:
    if set(value) != _SOURCE_KEYS:
        raise CorpusRealizedOutcomeError("realized player source fields differ")
    _self_hash(value, field="source_sha256", label="realized player source")
    rows = _retained_source_rows(
        value.get("rows"), outcome_keys=graph.outcome_keys
    )
    expected_query_spec = _query_contract(spec)
    try:
        _, attempt_started = shared._utc(  # noqa: SLF001
            attempt.get("started_at"), label="attempt started_at"
        )
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    replayed_job, _ = _job_receipt(
        value.get("job_receipt"), spec=spec, not_before=attempt_started
    )
    raw_tables = _sequence(
        value.get("table_receipts"), label="realized source table receipts"
    )
    tables = [SKILL_TABLE, DST_TABLE]
    if len(raw_tables) != len(tables) or [
        _table_receipt(raw, table=table)
        for raw, table in zip(raw_tables, tables, strict=True)
    ] != list(raw_tables):
        raise CorpusRealizedOutcomeError(
            "realized source table receipt replay differs"
        )
    if (
        value.get("schema_version") != SOURCE_SCHEMA
        or value.get("supplier_schema") != SUPPLIER_SCHEMA
        or value.get("batch_acceptance") != graph.acceptance_identity
        or value.get("batch_manifest_sha256")
        != graph.manifest["batch_manifest_sha256"]
        or value.get("later_source_freeze") != graph.source_freeze_identity
        or value.get("attempt") != attempt
        or value.get("attempt_object") != attempt_receipt
        or attempt.get("query_spec") != expected_query_spec
        or value.get("query_spec") != expected_query_spec
        or value.get("job_receipt") != replayed_job
        or value.get("source_snapshot_at") != spec.parameters[0].value
        or value.get("row_fields") != list(SOURCE_ROW_FIELDS)
        or value.get("row_count") != len(rows)
        or value.get("rows_sha256") != canonical_sha256(rows)
        or value.get("rows") != rows
        or value.get("table_metadata_stable_during_query") is not True
        or value.get("historical_outcome_lease_unchanged_during_query") is not True
        or value.get("one_exact_query") is not True
        or value.get("full_field_standings_included") is not False
        or value.get("payout_ladder_included") is not False
        or value.get("production_change_licensed") is not False
    ):
        raise CorpusRealizedOutcomeError("realized player source replay differs")
    return rows


def _actual_rows(source_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [{
        "task_index": row["task_index"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "player_id": row["player_id"],
        "realized_score_micro": row["realized_score_micro"],
    } for row in source_rows]


def _grade(
    graph: AcceptedBatchGraph,
    *,
    outcome_bundle: Mapping[str, object],
    outcome_identity: Mapping[str, object],
) -> dict[str, object]:
    try:
        return grading.grade_accepted_batch(
            batch_manifest=graph.manifest,
            batch_manifest_identity=graph.manifest_identity,
            batch_completion=graph.completion,
            batch_completion_identity=graph.completion_identity,
            batch_acceptance=graph.acceptance,
            batch_acceptance_identity=graph.acceptance_identity,
            accepted_tasks=graph.accepted_tasks,
            actual_player_outcomes=outcome_bundle,
            actual_player_outcomes_identity=outcome_identity,
        )
    except grading.CorpusRealizedGradingError as exc:
        raise CorpusRealizedOutcomeError("realized grading failed") from exc


def _build_outcome_bundle(
    graph: AcceptedBatchGraph,
    *,
    source_identity: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    try:
        return grading.build_actual_player_outcomes(
            batch_manifest=graph.manifest,
            source_identity=source_identity,
            rows=rows,
        )
    except grading.CorpusRealizedGradingError as exc:
        raise CorpusRealizedOutcomeError(
            "actual player outcome bundle failed"
        ) from exc


def _validate_completion(
    value: Mapping[str, object],
    *,
    config: SupplierConfig,
    graph: AcceptedBatchGraph,
    attempt: Mapping[str, object],
    attempt_receipt: Mapping[str, object],
    source_receipt: Mapping[str, object],
    outcome_receipt: Mapping[str, object],
    grade: Mapping[str, object],
) -> dict[str, object]:
    if set(value) != _COMPLETION_KEYS:
        raise CorpusRealizedOutcomeError("realized completion fields differ")
    _self_hash(value, field="completion_sha256", label="realized completion")
    if (
        value.get("schema_version") != COMPLETION_SCHEMA
        or value.get("supplier_schema") != SUPPLIER_SCHEMA
        or value.get("run_id") != config.run_id
        or value.get("batch_acceptance") != graph.acceptance_identity
        or value.get("attempt") != attempt
        or value.get("attempt_object") != attempt_receipt
        or value.get("source_object") != source_receipt
        or value.get("outcome_bundle_object") != outcome_receipt
        or value.get("realized_grade") != grade
        or value.get("realized_grade_sha256") != grade["realized_grade_sha256"]
        or value.get("task_count") != grading.EXPECTED_TASK_COUNT
        or value.get("parameter_set_count")
        != grading.EXPECTED_PARAMETER_SET_COUNT
        or value.get("task_arm_count") != grading.EXPECTED_TASK_ARM_COUNT
        or value.get("one_historical_outcome_read") is not True
        or value.get("independent_replay_complete") is not True
        or value.get("rank_available") is not False
        or value.get("roi_available") is not False
        or value.get("rank_roi_unavailable_reason")
        != "full_field_standings_and_payout_ladder_not_supplied"
        or value.get("historical_outcome_lease_release_required") is not True
        or value.get("lease_release_owner") != LEASE_RELEASE_OWNER
        or any(value.get(field) is not False for field in (
            "historical_retry_licensed", "historical_retune_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        raise CorpusRealizedOutcomeError("realized completion replay differs")
    return dict(value)


def supply_realized_outcomes(
    *,
    config: SupplierConfig,
    batch_acceptance_identity: Mapping[str, object],
    read_exact: ExactReader,
    verify_lease: LeaseVerifier,
    read_table_metadata: MetadataReader,
    execute_query: QueryExecutor,
    publish: Publisher,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> RealizedOutcomeSupply:
    """Perform the sole callback-driven historical read and exact replay."""
    if not isinstance(config, SupplierConfig) or config.enabled is not True:
        raise CorpusRealizedOutcomeError("corpus realized supplier is default-off")
    config = _validate_config(config)
    supplied_acceptance = _identity(
        batch_acceptance_identity, label="supplied batch acceptance"
    )
    if supplied_acceptance["sha256"] != (
        config.expected_batch_acceptance_object_sha256
    ):
        raise CorpusRealizedOutcomeError("configured batch acceptance differs")
    graph = reopen_accepted_batch(
        read_exact=read_exact,
        batch_acceptance_identity=supplied_acceptance,
    )
    uris = {
        supplied_acceptance["uri"],
        lease_adapter.HISTORICAL_OUTCOME_LEASE_URI,
        f"{config.output_root}/read-attempt.json",
        f"{config.output_root}/player-score-source.json",
        f"{config.output_root}/actual-player-outcomes.json",
        f"{config.output_root}/realized-completion.json",
    }
    if len(uris) != 6 or any(
        str(uri).startswith(graph.manifest["output_prefix"])
        for uri in uris if uri != supplied_acceptance["uri"]
    ):
        raise CorpusRealizedOutcomeError("realized output namespaces alias")

    lease_before = _lease(verify_lease(), config=config)
    started, started_at = _now(clock, label="realized attempt start")
    try:
        _, acquired = shared._utc(  # noqa: SLF001
            lease_before["body"]["acquired_at"], label="lease acquired_at"
        )
    except shared.LR8ScoreMapError as exc:
        raise CorpusRealizedOutcomeError(str(exc)) from exc
    if started_at < acquired:
        raise CorpusRealizedOutcomeError("attempt predates historical lease")
    union_payload = _union_payload(graph.outcome_keys)
    snapshot, snapshot_at = _now(clock, label="realized source snapshot")
    if snapshot_at < started_at:
        raise CorpusRealizedOutcomeError("source snapshot predates attempt start")
    spec = build_query_spec(
        config=config,
        outcome_keys=graph.outcome_keys,
        source_snapshot_at=snapshot,
    )
    query_spec = _query_contract(spec)
    attempt_body: dict[str, object] = {
        "schema_version": ATTEMPT_SCHEMA,
        "supplier_schema": SUPPLIER_SCHEMA,
        "stage": SCORE_READ_STAGE,
        "run_id": config.run_id,
        "batch_acceptance": graph.acceptance_identity,
        "batch_manifest_sha256": graph.manifest["batch_manifest_sha256"],
        "later_source_freeze": graph.source_freeze_identity,
        "task_count": grading.EXPECTED_TASK_COUNT,
        "parameter_set_count": grading.EXPECTED_PARAMETER_SET_COUNT,
        "task_arm_count": grading.EXPECTED_TASK_ARM_COUNT,
        "generated_unique_membership_count": (
            graph.generated_unique_membership_count
        ),
        "distinct_task_roster_count": graph.distinct_task_roster_count,
        "union_player_dst_count": len(graph.outcome_keys),
        "union_keys": union_payload,
        "union_keys_sha256": canonical_sha256(union_payload),
        "query_sql_sha256": AUTHORITATIVE_SCORE_SQL_SHA256,
        "query_spec": query_spec,
        "historical_outcome_lease": lease_before,
        "started_at": started,
        "uses_realized_outcomes_at_creation": False,
        "attempt_precedes_query": True,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    attempt = {
        **attempt_body, "attempt_sha256": canonical_sha256(attempt_body),
    }
    attempt_receipt, attempt_created, reopened_attempt = _publish(
        publish,
        uri=f"{config.output_root}/read-attempt.json",
        payload=attempt,
        earliest=snapshot_at,
        label="realized read attempt",
    )
    attempt = _validate_attempt(
        reopened_attempt,
        config=config,
        graph=graph,
        lease=lease_before,
        spec=spec,
    )

    tables = (SKILL_TABLE, DST_TABLE)
    before = [
        _table_receipt(read_table_metadata(table), table=table)
        for table in tables
    ]
    queried = execute_query(spec)
    if not isinstance(queried, shared.QueryResult):
        raise CorpusRealizedOutcomeError("query executor returned the wrong type")
    job, query_ended = _job_receipt(
        queried.job_receipt, spec=spec, not_before=attempt_created
    )
    if job["cache_hit"] is not False:
        raise CorpusRealizedOutcomeError("realized query used cache")
    source_rows = _query_rows(queried.rows, outcome_keys=graph.outcome_keys)
    after = [
        _table_receipt(read_table_metadata(table), table=table)
        for table in tables
    ]
    if before != after:
        raise CorpusRealizedOutcomeError("outcome table metadata changed during query")
    lease_after = _lease(verify_lease(), config=config)
    if canonical_json_bytes(lease_before) != canonical_json_bytes(lease_after):
        raise CorpusRealizedOutcomeError("historical lease changed during query")
    source_body: dict[str, object] = {
        "schema_version": SOURCE_SCHEMA,
        "supplier_schema": SUPPLIER_SCHEMA,
        "batch_acceptance": graph.acceptance_identity,
        "batch_manifest_sha256": graph.manifest["batch_manifest_sha256"],
        "later_source_freeze": graph.source_freeze_identity,
        "attempt": attempt,
        "attempt_object": attempt_receipt,
        "query_spec": query_spec,
        "job_receipt": job,
        "table_receipts": before,
        "source_snapshot_at": snapshot,
        "row_fields": list(SOURCE_ROW_FIELDS),
        "row_count": len(source_rows),
        "rows_sha256": canonical_sha256(source_rows),
        "rows": source_rows,
        "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True,
        "one_exact_query": True,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
        "production_change_licensed": False,
    }
    source = {
        **source_body, "source_sha256": canonical_sha256(source_body),
    }
    source_receipt, source_created, reopened_source = _publish(
        publish,
        uri=f"{config.output_root}/player-score-source.json",
        payload=source,
        earliest=query_ended,
        label="realized player source",
    )
    replayed_rows = _validate_source(
        reopened_source,
        graph=graph,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        spec=spec,
    )
    outcome_bundle = _build_outcome_bundle(
        graph,
        source_identity=_content_identity(
            source_receipt, label="player source identity"
        ),
        rows=_actual_rows(replayed_rows),
    )
    outcome_receipt, outcome_created, reopened_outcomes = _publish(
        publish,
        uri=f"{config.output_root}/actual-player-outcomes.json",
        payload=outcome_bundle,
        earliest=source_created,
        label="actual player outcomes",
    )
    outcome_identity = _content_identity(
        outcome_receipt, label="actual outcome identity"
    )
    realized_grade = _grade(
        graph,
        outcome_bundle=reopened_outcomes,
        outcome_identity=outcome_identity,
    )
    completion_body: dict[str, object] = {
        "schema_version": COMPLETION_SCHEMA,
        "supplier_schema": SUPPLIER_SCHEMA,
        "run_id": config.run_id,
        "batch_acceptance": graph.acceptance_identity,
        "attempt": attempt,
        "attempt_object": attempt_receipt,
        "source_object": source_receipt,
        "outcome_bundle_object": outcome_receipt,
        "realized_grade": realized_grade,
        "realized_grade_sha256": realized_grade["realized_grade_sha256"],
        "task_count": grading.EXPECTED_TASK_COUNT,
        "parameter_set_count": grading.EXPECTED_PARAMETER_SET_COUNT,
        "task_arm_count": grading.EXPECTED_TASK_ARM_COUNT,
        "one_historical_outcome_read": True,
        "independent_replay_complete": True,
        "rank_available": False,
        "roi_available": False,
        "rank_roi_unavailable_reason": (
            "full_field_standings_and_payout_ladder_not_supplied"
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": LEASE_RELEASE_OWNER,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    completion = {
        **completion_body,
        "completion_sha256": canonical_sha256(completion_body),
    }
    completion_receipt, _, reopened_completion = _publish(
        publish,
        uri=f"{config.output_root}/realized-completion.json",
        payload=completion,
        earliest=outcome_created,
        label="realized completion",
    )

    # Independent replay from the reopened source and outcome publication.
    replayed_outcome = _build_outcome_bundle(
        graph,
        source_identity=_content_identity(
            source_receipt, label="replay source identity"
        ),
        rows=_actual_rows(_validate_source(
            reopened_source,
            graph=graph,
            attempt=attempt,
            attempt_receipt=attempt_receipt,
            spec=spec,
        )),
    )
    if replayed_outcome != reopened_outcomes:
        raise CorpusRealizedOutcomeError("actual outcome replay differs")
    replayed_grade = _grade(
        graph,
        outcome_bundle=replayed_outcome,
        outcome_identity=outcome_identity,
    )
    if replayed_grade != realized_grade:
        raise CorpusRealizedOutcomeError("realized grade replay differs")
    _validate_completion(
        reopened_completion,
        config=config,
        graph=graph,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        source_receipt=source_receipt,
        outcome_receipt=outcome_receipt,
        grade=replayed_grade,
    )
    return RealizedOutcomeSupply(
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        source=source,
        source_receipt=source_receipt,
        outcome_bundle=outcome_bundle,
        outcome_bundle_receipt=outcome_receipt,
        completion=completion,
        completion_receipt=completion_receipt,
    )


__all__ = [
    "AUTHORITATIVE_SCORE_SQL",
    "AUTHORITATIVE_SCORE_SQL_SHA256",
    "AcceptedBatchGraph",
    "COMPLETION_SCHEMA",
    "CorpusRealizedOutcomeError",
    "LEASE_RELEASE_OWNER",
    "OutcomeKey",
    "PROJECT",
    "PublishedObject",
    "QUERY_CONTRACT_SCHEMA",
    "QuerySpec",
    "RealizedOutcomeSupply",
    "SOURCE_SCHEMA",
    "SupplierConfig",
    "build_query_spec",
    "canonical_json_bytes",
    "canonical_sha256",
    "deterministic_query_job_id",
    "reopen_accepted_batch",
    "supply_realized_outcomes",
]
