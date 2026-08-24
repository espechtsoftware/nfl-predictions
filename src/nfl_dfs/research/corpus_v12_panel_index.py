"""Combined, outcome-blind panel index for terminal Foundry v12 lanes.

The v12 generator remains immutable.  This module only exact-reads the two
terminal lane acceptances and their already-authoritative task acceptance /
task-result carriers, verifies the frozen transport bindings, and projects a
small create-once-ready index.  It owns no storage client, publisher, outcome
reader, solver, graph writer, or promotion authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_artifact_source_authority as source_authority
from nfl_dfs.research import corpus_parametric_batch as batch


PANEL_INDEX_SCHEMA: Final = "foundry-v12-combined-panel-index/v1"
LANE_TERMINAL_SCHEMA: Final = "corpus-parametric-batch-acceptance/v1"
TASK_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-task-acceptance/v1"
PUBLICATION_MODE: Final = "create_once"
V12_LANE_LATTICE: Final = (
    {
        "lane_ordinal": 0,
        "lane_id": "v12a",
        "batch_mode": "lane-a-28-task",
        "task_count": 28,
        "source_task_offset": 0,
    },
    {
        "lane_ordinal": 1,
        "lane_id": "v12b",
        "batch_mode": "lane-b-26-task",
        "task_count": 26,
        "source_task_offset": 28,
    },
)
V12_SOURCE_TASK_COUNT: Final = 54

_CANONICAL_ID: Final = re.compile(r"[a-z0-9][a-z0-9._-]*")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")

_LANE_INPUT_KEYS: Final = frozenset({
    "lane_ordinal",
    "lane_id",
    "terminal_receipt_identity",
    "tasks",
})
_TASK_INPUT_KEYS: Final = frozenset({
    "task_ordinal",
    "acceptance_identity",
    "carrier_identity",
})
_LANE_TERMINAL_KEYS: Final = frozenset({
    "schema_version",
    "accepted_at_utc",
    "transport_contract",
    "retrieval_task0_prerequisite_identity",
    "batch_mode",
    "batch_completion",
    "task_acceptances",
    "task_count",
    "parameter_set_count",
    "matrix_cell_count",
    "output_inventory_before_batch_acceptance",
    "output_inventory_before_batch_acceptance_sha256",
    "output_object_count_before_batch_acceptance",
    "complete",
    "accepted",
    "partial_result",
    "independent_verification_complete_for_every_task",
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "batch_acceptance_sha256",
})
_BATCH_COMPLETION_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "batch_manifest_identity",
    "batch_id",
    "batch_manifest_sha256",
    "parameter_schema_sha256",
    "common_law_sha256",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "effective_policy_classified_input_projection_sha256",
    "coverage",
    "task_results",
    "batch_completion_sha256",
})
_COMPLETION_COVERAGE_KEYS: Final = frozenset({
    "task_count",
    "parameter_set_count",
    "matrix_cell_count",
    "complete",
})
_COMPLETION_TASK_KEYS: Final = frozenset({
    "task_index",
    "task_sha256",
    "artifact_source_authority_task_sha256",
    "world_artifact_receipt_set_sha256",
    "task_result_sha256",
    "task_result_object",
})
_TASK_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version",
    "accepted_at_utc",
    "transport_contract",
    "retrieval_task0_prerequisite_identity",
    "task_index",
    "task_sha256",
    "producer_close",
    "science_terminal",
    "task_result",
    "verifier_worker_completion",
    "independent_verification",
    "independent_verification_sha256",
    "verifier_terminal_execution",
    "terminal_governance_census",
    "evidence_object_count",
    "complete_evidence_receipt",
    "independent_verification_complete",
    "strict_verifier_terminal_success",
    "accepted",
    "partial_result",
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "task_acceptance_sha256",
})
_TASK_RESULT_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "batch_manifest_identity",
    "batch_id",
    "batch_manifest_sha256",
    "parameter_schema_sha256",
    "common_law_sha256",
    "task_index",
    "task_sha256",
    "slate_id",
    "world_artifact_receipts",
    "world_artifact_receipt_set_sha256",
    "artifact_source_authority_task_sha256",
    "code_source",
    "immutable_image",
    "source_receipts",
    "source_receipt_set_sha256",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "effective_policy_inventory_identity",
    "effective_policy_inventory_sha256",
    "effective_policy_rule_universe_sha256",
    "effective_policy_inventory_source_set_sha256",
    "effective_policy_classified_input_projection_sha256",
    "world_schedule",
    "world_seed",
    "solver",
    "execution",
    "variant_results",
    "task_result_sha256",
})
_VARIANT_RESULT_KEYS: Final = frozenset({
    "ordinal",
    "parameter_set_id",
    "parameter_set_sha256",
    "effective_policy_receipt",
    "result_object",
})
_INVENTORY_ROW_KEYS: Final = frozenset({"uri", "generation", "bytes"})
_FALSE_TASK_ACCEPTANCE_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
)
_FALSE_LANE_TERMINAL_FIELDS: Final = _FALSE_TASK_ACCEPTANCE_FIELDS
_FALSE_PANEL_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_PANEL_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "panel_id",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "lane_count",
    "lanes",
    "accepted_slate_count",
    "accepted_slates",
    "exclusions",
    "failures",
    "missing_tasks",
    "coverage",
    *_FALSE_PANEL_FIELDS,
    "panel_index_sha256",
})


class CorpusV12PanelIndexError(ValueError):
    """The two-lane v12 panel cannot be indexed without weakening authority."""


ReadExact = Callable[[Mapping[str, object]], bytes]


def _fail(message: str) -> None:
    raise CorpusV12PanelIndexError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    if frozenset(value) != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - frozenset(value))}, "
            f"unknown={sorted(frozenset(value) - expected)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _canonical_id(value: object, *, label: str) -> str:
    if type(value) is not str or _CANONICAL_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical id")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusV12PanelIndexError(f"{label} differs") from exc


def _identity_key(value: Mapping[str, object]) -> tuple[str, str, str, int]:
    return (
        str(value["uri"]),
        str(value["generation"]),
        str(value["sha256"]),
        int(value["bytes"]),
    )


def _transport_json_bytes(value: object) -> bytes:
    """Frozen transport canonical JSON: batch canonical bytes plus newline."""
    return batch.canonical_json_bytes(value) + b"\n"


def _transport_sha256(value: object) -> str:
    return sha256(_transport_json_bytes(value)).hexdigest()


def _parse_transport_json_bytes(raw: bytes, *, label: str) -> object:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail(f"{label} is not newline-canonical transport JSON")

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusV12PanelIndexError(f"{label} is not valid JSON") from exc
    if _transport_json_bytes(value) != raw:
        _fail(f"{label} is not newline-canonical transport JSON")
    return value


def _validate_self_hash(
    value: Mapping[str, object],
    *,
    field: str,
    label: str,
    transport_canonical: bool = False,
) -> None:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    expected = (
        _transport_sha256(body)
        if transport_canonical
        else batch.canonical_sha256(body)
    )
    if expected != retained:
        _fail(f"{label} self-hash differs")


def _exact_read_raw(
    value: object, *, read_exact: ReadExact, label: str
) -> tuple[dict[str, object], bytes]:
    identity = _identity(value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusV12PanelIndexError(f"{label} cannot be exact-read") from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} bytes differ from identity")
    return identity, raw


def _exact_read_json(
    value: object,
    *,
    read_exact: ReadExact,
    label: str,
    transport_canonical: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    identity, raw = _exact_read_raw(value, read_exact=read_exact, label=label)
    try:
        parsed = (
            _parse_transport_json_bytes(raw, label=label)
            if transport_canonical
            else batch.parse_canonical_json_bytes(raw, label=label)
        )
    except Exception as exc:
        raise CorpusV12PanelIndexError(f"{label} is not canonical JSON") from exc
    return identity, dict(_mapping(parsed, label=label))


def _inventory_rows(
    value: object, *, label: str
) -> list[dict[str, object]]:
    rows = _sequence(value, label=label)
    normalized: list[dict[str, object]] = []
    prior: tuple[str, str] | None = None
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"{label}[{ordinal}]")
        _exact_keys(row, _INVENTORY_ROW_KEYS, label=f"{label}[{ordinal}]")
        uri = row["uri"]
        generation = row["generation"]
        size = row["bytes"]
        if (
            type(uri) is not str
            or not uri.startswith("gs://")
            or type(generation) is not str
            or not generation.isdigit()
            or generation.startswith("0")
            or type(size) is not int
            or size <= 0
        ):
            _fail(f"{label}[{ordinal}] values differ")
        key = (uri, generation)
        if prior is not None and key <= prior:
            _fail(f"{label} is not strictly ordered")
        prior = key
        normalized.append({"uri": uri, "generation": generation, "bytes": size})
    return normalized


def _inventory_contains(
    inventory: Sequence[Mapping[str, object]], identity: Mapping[str, object]
) -> bool:
    expected = (identity["uri"], identity["generation"], identity["bytes"])
    return any(
        (row["uri"], row["generation"], row["bytes"]) == expected
        for row in inventory
    )


def _normalize_lane_inputs(
    lane_inputs: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = _sequence(lane_inputs, label="lane inputs")
    if len(rows) != 2:
        _fail("combined v12 panel requires exactly two lanes")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_terminal_objects: set[tuple[str, str, str, int]] = set()
    for lane_ordinal, raw_lane in enumerate(rows):
        lane_law = V12_LANE_LATTICE[lane_ordinal]
        lane = _mapping(raw_lane, label=f"lane input[{lane_ordinal}]")
        _exact_keys(lane, _LANE_INPUT_KEYS, label=f"lane input[{lane_ordinal}]")
        if lane.get("lane_ordinal") != lane_ordinal:
            _fail("lane inputs are not in fixed ordinal order")
        lane_id = _canonical_id(lane.get("lane_id"), label="lane id")
        if lane_id != lane_law["lane_id"]:
            _fail("lane id differs from the frozen v12 lattice")
        if lane_id in seen_ids:
            _fail("lane ids repeat")
        seen_ids.add(lane_id)
        terminal = _identity(
            lane.get("terminal_receipt_identity"),
            label=f"lane[{lane_ordinal}] terminal receipt",
        )
        terminal_key = _identity_key(terminal)
        if terminal_key in seen_terminal_objects:
            _fail("lane terminal receipt identities repeat")
        seen_terminal_objects.add(terminal_key)
        task_values = _sequence(lane.get("tasks"), label=f"lane[{lane_ordinal}] tasks")
        if len(task_values) != lane_law["task_count"]:
            _fail("lane task count differs from the frozen v12 lattice")
        tasks: list[dict[str, object]] = []
        for task_ordinal, raw_task in enumerate(task_values):
            task = _mapping(raw_task, label=f"lane[{lane_ordinal}] task[{task_ordinal}]")
            _exact_keys(
                task,
                _TASK_INPUT_KEYS,
                label=f"lane[{lane_ordinal}] task[{task_ordinal}]",
            )
            if task.get("task_ordinal") != task_ordinal:
                _fail("task inputs are not in fixed ordinal order")
            tasks.append({
                "task_ordinal": task_ordinal,
                "acceptance_identity": _identity(
                    task.get("acceptance_identity"),
                    label=(
                        f"lane[{lane_ordinal}] task[{task_ordinal}] acceptance"
                    ),
                ),
                "carrier_identity": _identity(
                    task.get("carrier_identity"),
                    label=f"lane[{lane_ordinal}] task[{task_ordinal}] carrier",
                ),
            })
        normalized.append({
            "lane_ordinal": lane_ordinal,
            "lane_id": lane_id,
            "terminal_receipt_identity": terminal,
            "tasks": tasks,
        })
    return normalized


def _validate_lane_terminal(
    lane: Mapping[str, object], *, read_exact: ReadExact
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    lane_ordinal = int(lane["lane_ordinal"])
    terminal_identity, terminal = _exact_read_json(
        lane["terminal_receipt_identity"],
        read_exact=read_exact,
        label=f"lane[{lane_ordinal}] terminal receipt",
        transport_canonical=True,
    )
    _exact_keys(terminal, _LANE_TERMINAL_KEYS, label="lane terminal receipt")
    _validate_self_hash(
        terminal,
        field="batch_acceptance_sha256",
        label="lane terminal receipt",
        transport_canonical=True,
    )
    if not 0 <= lane_ordinal < len(V12_LANE_LATTICE):
        _fail("lane ordinal differs from the frozen v12 lattice")
    lane_law = V12_LANE_LATTICE[lane_ordinal]
    task_count = _exact_int(terminal.get("task_count"), label="lane task_count", minimum=1)
    if (
        terminal.get("schema_version") != LANE_TERMINAL_SCHEMA
        or lane.get("lane_id") != lane_law["lane_id"]
        or terminal.get("batch_mode") != lane_law["batch_mode"]
        or task_count != lane_law["task_count"]
        or terminal.get("parameter_set_count") != len(batch.PARAMETER_SET_ORDER)
        or terminal.get("matrix_cell_count")
        != task_count * len(batch.PARAMETER_SET_ORDER)
        or terminal.get("complete") is not True
        or terminal.get("accepted") is not True
        or terminal.get("partial_result") is not False
        or terminal.get("independent_verification_complete_for_every_task")
        is not True
        or any(terminal.get(field) is not False for field in _FALSE_LANE_TERMINAL_FIELDS)
    ):
        _fail(f"lane[{lane_ordinal}] is nonterminal, incomplete, or unauthorized")
    transport_contract = _identity(
        terminal.get("transport_contract"), label="lane transport contract"
    )
    prerequisite = _identity(
        terminal.get("retrieval_task0_prerequisite_identity"),
        label="lane retrieval prerequisite",
    )
    if transport_contract == prerequisite:
        _fail("lane terminal authority identities repeat")
    task_acceptances = [
        _identity(value, label=f"lane terminal task acceptance[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(
                terminal.get("task_acceptances"),
                label="lane terminal task acceptances",
            )
        )
    ]
    if (
        len(task_acceptances) != task_count
        or len({_identity_key(value) for value in task_acceptances}) != task_count
    ):
        _fail("lane terminal task acceptance coverage differs")

    completion_identity, completion = _exact_read_json(
        terminal.get("batch_completion"),
        read_exact=read_exact,
        label=f"lane[{lane_ordinal}] batch completion",
    )
    _exact_keys(completion, _BATCH_COMPLETION_KEYS, label="batch completion")
    _validate_self_hash(
        completion, field="batch_completion_sha256", label="batch completion"
    )
    completion["batch_manifest_identity"] = _identity(
        completion.get("batch_manifest_identity"),
        label="batch completion manifest identity",
    )
    completion["artifact_source_authority_completion"] = _identity(
        completion.get("artifact_source_authority_completion"),
        label="batch completion source-authority identity",
    )
    _canonical_id(completion.get("batch_id"), label="batch completion batch_id")
    for field in (
        "batch_manifest_sha256",
        "parameter_schema_sha256",
        "common_law_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion_sha256",
        "effective_policy_classified_input_projection_sha256",
    ):
        _sha(completion.get(field), label=f"batch completion.{field}")
    coverage = _mapping(completion.get("coverage"), label="batch completion coverage")
    _exact_keys(coverage, _COMPLETION_COVERAGE_KEYS, label="batch completion coverage")
    if (
        completion.get("schema_version") != batch.BATCH_COMPLETION_SCHEMA
        or completion.get("publication_mode") != PUBLICATION_MODE
        or coverage.get("task_count") != task_count
        or coverage.get("parameter_set_count") != len(batch.PARAMETER_SET_ORDER)
        or coverage.get("matrix_cell_count")
        != task_count * len(batch.PARAMETER_SET_ORDER)
        or coverage.get("complete") is not True
    ):
        _fail("lane batch completion coverage differs")
    result_rows = [
        dict(_mapping(value, label=f"batch completion task[{ordinal}]"))
        for ordinal, value in enumerate(
            _sequence(completion.get("task_results"), label="completion task results")
        )
    ]
    if len(result_rows) != task_count:
        _fail("batch completion task count differs")
    seen_carriers: set[tuple[str, str, str, int]] = set()
    for ordinal, result_row in enumerate(result_rows):
        _exact_keys(
            result_row,
            _COMPLETION_TASK_KEYS,
            label=f"batch completion task[{ordinal}]",
        )
        if result_row.get("task_index") != ordinal:
            _fail("batch completion tasks are not in fixed order")
        for field in (
            "task_sha256",
            "artifact_source_authority_task_sha256",
            "world_artifact_receipt_set_sha256",
            "task_result_sha256",
        ):
            _sha(result_row.get(field), label=f"completion task[{ordinal}].{field}")
        carrier = _identity(
            result_row.get("task_result_object"),
            label=f"completion task[{ordinal}] result object",
        )
        if _identity_key(carrier) in seen_carriers:
            _fail("batch completion carrier identities repeat")
        seen_carriers.add(_identity_key(carrier))
        result_row["task_result_object"] = carrier

    inventory = _inventory_rows(
        terminal.get("output_inventory_before_batch_acceptance"),
        label="lane terminal output inventory",
    )
    if (
        terminal.get("output_object_count_before_batch_acceptance") != len(inventory)
        or terminal.get("output_inventory_before_batch_acceptance_sha256")
        != _transport_sha256(inventory)
    ):
        _fail("lane terminal output inventory binding differs")
    required_inventory = [
        completion_identity,
        *task_acceptances,
        *(row["task_result_object"] for row in result_rows),
    ]
    if any(not _inventory_contains(inventory, value) for value in required_inventory):
        _fail("lane terminal inventory omits accepted evidence")
    return (
        terminal_identity,
        terminal,
        completion,
        task_acceptances,
        result_rows,
    )


def _validate_task(
    *,
    lane: Mapping[str, object],
    terminal: Mapping[str, object],
    completion: Mapping[str, object],
    terminal_acceptance_identity: Mapping[str, object],
    result_row: Mapping[str, object],
    task_input: Mapping[str, object],
    source_task: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    lane_ordinal = int(lane["lane_ordinal"])
    task_ordinal = int(task_input["task_ordinal"])
    acceptance_identity = _identity(
        task_input["acceptance_identity"], label="task acceptance input"
    )
    if acceptance_identity != terminal_acceptance_identity:
        _fail("task acceptance input differs from lane terminal order")
    retained_acceptance_identity, acceptance = _exact_read_json(
        acceptance_identity,
        read_exact=read_exact,
        label=f"lane[{lane_ordinal}] task[{task_ordinal}] acceptance",
        transport_canonical=True,
    )
    _exact_keys(acceptance, _TASK_ACCEPTANCE_KEYS, label="task acceptance")
    _validate_self_hash(
        acceptance,
        field="task_acceptance_sha256",
        label="task acceptance",
        transport_canonical=True,
    )
    carrier_identity = _identity(
        task_input["carrier_identity"], label="task carrier input"
    )
    completion_carrier = _identity(
        result_row["task_result_object"], label="completion task carrier"
    )
    if carrier_identity != completion_carrier:
        _fail("task carrier input differs from batch completion")
    if (
        acceptance.get("schema_version") != TASK_ACCEPTANCE_SCHEMA
        or acceptance.get("transport_contract") != terminal.get("transport_contract")
        or acceptance.get("retrieval_task0_prerequisite_identity")
        != terminal.get("retrieval_task0_prerequisite_identity")
        or acceptance.get("task_index") != task_ordinal
        or acceptance.get("task_sha256") != result_row.get("task_sha256")
        or acceptance.get("task_result") != carrier_identity
        or acceptance.get("evidence_object_count") != 140
        or acceptance.get("complete_evidence_receipt") is not True
        or acceptance.get("independent_verification_complete") is not True
        or acceptance.get("strict_verifier_terminal_success") is not True
        or acceptance.get("accepted") is not True
        or acceptance.get("partial_result") is not False
        or any(
            acceptance.get(field) is not False
            for field in _FALSE_TASK_ACCEPTANCE_FIELDS
        )
    ):
        _fail("task acceptance authority or identity differs")
    for field in (
        "producer_close",
        "science_terminal",
        "task_result",
        "verifier_worker_completion",
        "independent_verification",
    ):
        _identity(acceptance.get(field), label=f"task acceptance {field}")
    _sha(
        acceptance.get("independent_verification_sha256"),
        label="task acceptance independent verification sha",
    )

    retained_carrier_identity, carrier = _exact_read_json(
        carrier_identity,
        read_exact=read_exact,
        label=f"lane[{lane_ordinal}] task[{task_ordinal}] carrier",
    )
    _exact_keys(carrier, _TASK_RESULT_KEYS, label="task result carrier")
    _validate_self_hash(carrier, field="task_result_sha256", label="task result carrier")
    carrier["batch_manifest_identity"] = _identity(
        carrier.get("batch_manifest_identity"),
        label="task result carrier manifest identity",
    )
    carrier["artifact_source_authority_completion"] = _identity(
        carrier.get("artifact_source_authority_completion"),
        label="task result carrier source-authority identity",
    )
    carrier["effective_policy_inventory_identity"] = _identity(
        carrier.get("effective_policy_inventory_identity"),
        label="task result carrier policy-inventory identity",
    )
    _canonical_id(carrier.get("batch_id"), label="task result carrier batch_id")
    for field in (
        "batch_manifest_sha256",
        "parameter_schema_sha256",
        "common_law_sha256",
        "source_receipt_set_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion_sha256",
        "effective_policy_inventory_sha256",
        "effective_policy_rule_universe_sha256",
        "effective_policy_inventory_source_set_sha256",
        "effective_policy_classified_input_projection_sha256",
    ):
        _sha(carrier.get(field), label=f"task result carrier.{field}")
    if (
        carrier.get("schema_version") != batch.TASK_RESULT_SCHEMA
        or carrier.get("publication_mode") != PUBLICATION_MODE
        or carrier.get("task_index") != task_ordinal
        or carrier.get("task_sha256") != result_row.get("task_sha256")
        or carrier.get("task_result_sha256") != result_row.get("task_result_sha256")
        or carrier.get("world_artifact_receipt_set_sha256")
        != result_row.get("world_artifact_receipt_set_sha256")
        or carrier.get("artifact_source_authority_task_sha256")
        != result_row.get("artifact_source_authority_task_sha256")
        or carrier.get("batch_manifest_identity")
        != completion.get("batch_manifest_identity")
        or carrier.get("batch_id") != completion.get("batch_id")
        or carrier.get("batch_manifest_sha256")
        != completion.get("batch_manifest_sha256")
        or carrier.get("parameter_schema_sha256")
        != completion.get("parameter_schema_sha256")
        or carrier.get("common_law_sha256") != completion.get("common_law_sha256")
        or carrier.get("later_source_freeze_manifest_sha256")
        != completion.get("later_source_freeze_manifest_sha256")
        or carrier.get("artifact_source_authority_completion")
        != completion.get("artifact_source_authority_completion")
        or carrier.get("artifact_source_authority_completion_sha256")
        != completion.get("artifact_source_authority_completion_sha256")
        or carrier.get("effective_policy_classified_input_projection_sha256")
        != completion.get("effective_policy_classified_input_projection_sha256")
    ):
        _fail("task result carrier differs from accepted completion")
    slate_id = _canonical_id(carrier.get("slate_id"), label="carrier slate_id")
    source_task_ordinal = (
        int(V12_LANE_LATTICE[lane_ordinal]["source_task_offset"])
        + task_ordinal
    )
    if (
        source_task.get("task_index") != source_task_ordinal
        or source_task.get("slate_id") != slate_id
        or source_task.get("task_source_authority_sha256")
        != carrier.get("artifact_source_authority_task_sha256")
        or source_task.get("world_artifact_receipt_set_sha256")
        != carrier.get("world_artifact_receipt_set_sha256")
        or source_task.get("later_source_freeze_manifest_sha256")
        != carrier.get("later_source_freeze_manifest_sha256")
    ):
        _fail("task result carrier differs from the frozen source-authority task")
    variant_rows = _sequence(carrier.get("variant_results"), label="carrier arms")
    if len(variant_rows) != len(batch.PARAMETER_SET_ORDER):
        _fail("task result carrier does not contain exactly seven arms")
    arms: list[dict[str, object]] = []
    seen_arm_objects: set[tuple[str, str, str, int]] = set()
    for arm_ordinal, raw_arm in enumerate(variant_rows):
        arm = _mapping(raw_arm, label=f"carrier arm[{arm_ordinal}]")
        _exact_keys(arm, _VARIANT_RESULT_KEYS, label=f"carrier arm[{arm_ordinal}]")
        if (
            arm.get("ordinal") != arm_ordinal
            or arm.get("parameter_set_id") != batch.PARAMETER_SET_ORDER[arm_ordinal]
        ):
            _fail("carrier arm order or identity differs")
        _sha(
            arm.get("parameter_set_sha256"),
            label=f"carrier arm[{arm_ordinal}] parameter set sha",
        )
        _identity(
            arm.get("effective_policy_receipt"),
            label=f"carrier arm[{arm_ordinal}] policy receipt",
        )
        result_identity, _ = _exact_read_raw(
            arm.get("result_object"),
            read_exact=read_exact,
            label=(
                f"lane[{lane_ordinal}] task[{task_ordinal}] arm[{arm_ordinal}] result"
            ),
        )
        arm_key = _identity_key(result_identity)
        if arm_key in seen_arm_objects:
            _fail("carrier arm result identities repeat")
        seen_arm_objects.add(arm_key)
        arms.append({
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
            "result_identity": result_identity,
        })
    return {
        "slate_id": slate_id,
        "lane_ordinal": lane_ordinal,
        "lane_id": lane["lane_id"],
        "task_ordinal": task_ordinal,
        "source_task_ordinal": source_task_ordinal,
        "source_task_authority_sha256": source_task[
            "task_source_authority_sha256"
        ],
        "task_acceptance_identity": retained_acceptance_identity,
        "carrier_identity": retained_carrier_identity,
        "arms": arms,
    }


def derive_v12_lane_input(
    *,
    lane_ordinal: int,
    lane_id: str,
    terminal_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Derive ordered task inputs from one exact terminal lane acceptance.

    The terminal acceptance supplies the authoritative task-acceptance order;
    its bound batch completion supplies the corresponding task-result carrier
    identities.  Callers therefore never maintain a parallel hand-curated
    per-task list.
    """
    retained_ordinal = _exact_int(
        lane_ordinal, label="derived lane ordinal", minimum=0
    )
    if retained_ordinal >= len(V12_LANE_LATTICE):
        _fail("derived lane ordinal differs from the frozen v12 lattice")
    retained_lane_id = _canonical_id(lane_id, label="derived lane id")
    if retained_lane_id != V12_LANE_LATTICE[retained_ordinal]["lane_id"]:
        _fail("derived lane id differs from the frozen v12 lattice")
    retained_terminal = _identity(
        terminal_receipt_identity, label="derived lane terminal receipt"
    )
    lane = {
        "lane_ordinal": retained_ordinal,
        "lane_id": retained_lane_id,
        "terminal_receipt_identity": retained_terminal,
        "tasks": [],
    }
    (
        terminal_identity,
        _,
        _,
        task_acceptances,
        result_rows,
    ) = _validate_lane_terminal(lane, read_exact=read_exact)
    if len(task_acceptances) != len(result_rows):
        _fail("terminal lane acceptance/completion task coverage differs")
    return {
        "lane_ordinal": retained_ordinal,
        "lane_id": retained_lane_id,
        "terminal_receipt_identity": terminal_identity,
        "tasks": [
            {
                "task_ordinal": task_ordinal,
                "acceptance_identity": acceptance_identity,
                "carrier_identity": result_rows[task_ordinal][
                    "task_result_object"
                ],
            }
            for task_ordinal, acceptance_identity in enumerate(task_acceptances)
        ],
    }


def build_v12_panel_index(
    *,
    lane_inputs: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build the complete two-lane v12 index from exact accepted evidence."""
    lanes = _normalize_lane_inputs(lane_inputs)
    lane_rows: list[dict[str, object]] = []
    accepted_slates: list[dict[str, object]] = []
    seen_slates: set[str] = set()
    seen_acceptances: set[tuple[str, str, str, int]] = set()
    seen_carriers: set[tuple[str, str, str, int]] = set()
    seen_arms: set[tuple[str, str, str, int]] = set()
    retained_source_identity: dict[str, object] | None = None
    retained_source_internal_sha256: str | None = None
    retained_source_completion: dict[str, object] | None = None
    for lane in lanes:
        (
            terminal_identity,
            terminal,
            completion,
            terminal_acceptances,
            result_rows,
        ) = _validate_lane_terminal(lane, read_exact=read_exact)
        lane_source_identity = _identity(
            completion["artifact_source_authority_completion"],
            label="lane source-authority completion identity",
        )
        lane_source_internal_sha256 = _sha(
            completion["artifact_source_authority_completion_sha256"],
            label="lane source-authority completion internal SHA",
        )
        if retained_source_identity is None:
            source_identity, source_raw = _exact_read_raw(
                lane_source_identity,
                read_exact=read_exact,
                label="artifact source-authority completion",
            )
            try:
                source_completion = source_authority.validate_completion_bytes(
                    source_raw
                )
            except Exception as exc:
                raise CorpusV12PanelIndexError(
                    "artifact source-authority completion differs"
                ) from exc
            source_internal_sha256 = _sha(
                source_completion.get("completion_sha256"),
                label="artifact source-authority completion internal SHA",
            )
            if (
                source_internal_sha256 != lane_source_internal_sha256
                or source_completion.get("task_count") != V12_SOURCE_TASK_COUNT
            ):
                _fail("artifact source-authority completion binding differs")
            retained_source_identity = source_identity
            retained_source_internal_sha256 = source_internal_sha256
            retained_source_completion = source_completion
        elif (
            lane_source_identity != retained_source_identity
            or lane_source_internal_sha256 != retained_source_internal_sha256
        ):
            _fail("v12 lanes bind different source-authority completions")
        if retained_source_completion is None:
            _fail("artifact source-authority completion is unavailable")
        if (
            completion.get("later_source_freeze_manifest_sha256")
            != retained_source_completion.get(
                "later_source_freeze_manifest_sha256"
            )
        ):
            _fail("lane completion differs from its source-authority freeze")
        source_tasks = _sequence(
            retained_source_completion.get("tasks"),
            label="artifact source-authority tasks",
        )
        task_inputs = lane["tasks"]
        if len(task_inputs) != len(result_rows):
            _fail("lane task inputs do not cover the complete terminal lane")
        lane_slate_rows: list[dict[str, object]] = []
        for task_ordinal, task_input in enumerate(task_inputs):
            slate_row = _validate_task(
                lane=lane,
                terminal=terminal,
                completion=completion,
                terminal_acceptance_identity=terminal_acceptances[task_ordinal],
                result_row=result_rows[task_ordinal],
                task_input=task_input,
                source_task=_mapping(
                    source_tasks[
                        int(V12_LANE_LATTICE[int(lane["lane_ordinal"])][
                            "source_task_offset"
                        ])
                        + task_ordinal
                    ],
                    label="artifact source-authority task",
                ),
                read_exact=read_exact,
            )
            if slate_row["slate_id"] in seen_slates:
                _fail("accepted slate appears more than once across v12 lanes")
            seen_slates.add(str(slate_row["slate_id"]))
            acceptance_key = _identity_key(slate_row["task_acceptance_identity"])
            carrier_key = _identity_key(slate_row["carrier_identity"])
            if acceptance_key in seen_acceptances or carrier_key in seen_carriers:
                _fail("accepted task identities repeat across v12 lanes")
            seen_acceptances.add(acceptance_key)
            seen_carriers.add(carrier_key)
            for arm in slate_row["arms"]:
                arm_key = _identity_key(arm["result_identity"])
                if arm_key in seen_arms:
                    _fail("arm result identity repeats across accepted tasks")
                seen_arms.add(arm_key)
            accepted_slates.append(slate_row)
            lane_slate_rows.append(slate_row)
        lane_rows.append({
            "lane_ordinal": lane["lane_ordinal"],
            "lane_id": lane["lane_id"],
            "terminal_receipt_identity": terminal_identity,
            "batch_completion_identity": _identity(
                terminal["batch_completion"], label="lane completion identity"
            ),
            "batch_id": completion["batch_id"],
            "batch_mode": terminal["batch_mode"],
            "artifact_source_authority_completion": lane_source_identity,
            "artifact_source_authority_completion_sha256": (
                lane_source_internal_sha256
            ),
            "source_task_offset": V12_LANE_LATTICE[int(lane["lane_ordinal"])][
                "source_task_offset"
            ],
            "expected_task_count": len(result_rows),
            "accepted_task_count": len(lane_slate_rows),
            "accepted_task_ordinals": [
                row["task_ordinal"] for row in lane_slate_rows
            ],
            "task_acceptance_identities_sha256": batch.canonical_sha256([
                row["task_acceptance_identity"] for row in lane_slate_rows
            ]),
            "carrier_identities_sha256": batch.canonical_sha256([
                row["carrier_identity"] for row in lane_slate_rows
            ]),
            "complete": True,
        })

    terminal_identities = [row["terminal_receipt_identity"] for row in lane_rows]
    if (
        retained_source_identity is None
        or retained_source_internal_sha256 is None
    ):
        _fail("combined panel lacks source-authority completion evidence")
    expected_tasks = sum(int(row["expected_task_count"]) for row in lane_rows)
    if (
        expected_tasks != V12_SOURCE_TASK_COUNT
        or [row["source_task_ordinal"] for row in accepted_slates]
        != list(range(V12_SOURCE_TASK_COUNT))
    ):
        _fail("combined panel does not cover the frozen 54-task source lattice")
    body: dict[str, object] = {
        "schema_version": PANEL_INDEX_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "panel_id": f"v12:{batch.canonical_sha256(terminal_identities)}",
        "artifact_source_authority_completion": retained_source_identity,
        "artifact_source_authority_completion_sha256": (
            retained_source_internal_sha256
        ),
        "lane_count": len(lane_rows),
        "lanes": lane_rows,
        "accepted_slate_count": len(accepted_slates),
        "accepted_slates": accepted_slates,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": expected_tasks,
            "accepted_task_count": len(accepted_slates),
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        **{field: False for field in _FALSE_PANEL_FIELDS},
    }
    body["panel_index_sha256"] = batch.canonical_sha256(body)
    return body


def validate_v12_panel_index(
    value: object,
    *,
    lane_inputs: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Validate a panel self-hash and replay it from every exact input."""
    item = dict(_mapping(value, label="v12 panel index"))
    _exact_keys(item, _PANEL_KEYS, label="v12 panel index")
    if (
        item.get("schema_version") != PANEL_INDEX_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or any(item.get(field) is not False for field in _FALSE_PANEL_FIELDS)
    ):
        _fail("v12 panel index schema or authority differs")
    _validate_self_hash(item, field="panel_index_sha256", label="v12 panel index")
    rebuilt = build_v12_panel_index(lane_inputs=lane_inputs, read_exact=read_exact)
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(rebuilt):
        _fail("v12 panel index differs from exact-input replay")
    return rebuilt


def reopen_v12_panel_index(
    *,
    panel_index_identity: Mapping[str, object],
    lane_inputs: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-read one retained index, then replay its complete authority graph."""
    _, raw = _exact_read_raw(
        panel_index_identity, read_exact=read_exact, label="v12 panel index"
    )
    try:
        value = batch.parse_canonical_json_bytes(raw, label="v12 panel index")
    except Exception as exc:
        raise CorpusV12PanelIndexError(
            "v12 panel index is not canonical JSON"
        ) from exc
    return validate_v12_panel_index(
        value, lane_inputs=lane_inputs, read_exact=read_exact
    )


__all__ = [
    "CorpusV12PanelIndexError",
    "LANE_TERMINAL_SCHEMA",
    "PANEL_INDEX_SCHEMA",
    "PUBLICATION_MODE",
    "TASK_ACCEPTANCE_SCHEMA",
    "V12_LANE_LATTICE",
    "V12_SOURCE_TASK_COUNT",
    "build_v12_panel_index",
    "derive_v12_lane_input",
    "reopen_v12_panel_index",
    "validate_v12_panel_index",
]
