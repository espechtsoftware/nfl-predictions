"""Bounded create-once operator for the two paid-source ablations.

The scientific builders remain storage agnostic.  This module accepts only a
complete validated panel and its complete score-blind slate evidence, expands
all nested population/world/book or physically stripped source-view bodies
into independently reopenable documents, publishes every child create-once,
and publishes the terminal root last.  It has no outcome API and performs no
cloud operation at import time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from typing import Final

import numpy as np

from . import corpus_r6_paid_source_ablation_v1 as matchup
from . import corpus_r6_matchup_source_v2 as source
from . import odds_prop_override_ablation_v1 as odds
from . import paid_source_ablation_registry_v1 as registry
from . import paid_source_odds_execution_adapter_v1 as odds_execution


READY_SCHEMA: Final = "paid-source-ablation-ready-bundle/v1"
TERMINAL_SCHEMA: Final = "paid-source-ablation-terminal/v1"
TERMINAL_ENVELOPE_SCHEMA: Final = "paid-source-ablation-terminal-envelope/v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_POSITIONS: Final = ("QB", "RB", "WR", "TE", "DST")


class PaidSourceAblationOperatorV1Error(ValueError):
    """The bounded publication/reopen contract differs."""


PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
ReadExact = Callable[[Mapping[str, object]], bytes]


@dataclass(frozen=True)
class _OddsExecutionRecord:
    """In-process witness emitted only by the genuine staged runner."""

    execution_receipt: Mapping[str, object]
    execution_receipt_identity: Mapping[str, object]
    runtime_attestation: Mapping[str, object]
    player_input: Mapping[str, object]
    player_input_identity: Mapping[str, object]
    candidate_input: Mapping[str, object]
    candidate_input_identity: Mapping[str, object]
    centered_world_bytes: bytes
    centered_world_identity: Mapping[str, object]


def _fail(message: str) -> None:
    raise PaidSourceAblationOperatorV1Error(message)


def _document(value: Mapping[str, object]) -> bytes:
    return registry.canonical_json_bytes(dict(value)) + b"\n"


def _parse_document(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail(f"{label} is not canonical newline-terminated JSON")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PaidSourceAblationOperatorV1Error(f"{label} JSON differs") from exc
    if not isinstance(value, Mapping) or _document(value) != raw:
        _fail(f"{label} canonical replay differs")
    return dict(value)


def _parse_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse an identity-bound canonical JSON input (without a newline)."""
    if type(raw) is not bytes or not raw or raw.endswith(b"\n"):
        _fail(f"{label} is not canonical JSON")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PaidSourceAblationOperatorV1Error(f"{label} JSON differs") from exc
    if (
        not isinstance(value, Mapping)
        or registry.canonical_json_bytes(dict(value)) != raw
    ):
        _fail(f"{label} canonical replay differs")
    return dict(value)


def _timestamp(value: str, *, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        _fail(f"{label} must be an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise PaidSourceAblationOperatorV1Error(f"{label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{label} is not UTC")
    return value


def _identity(
    value: object,
    *,
    label: str,
    expected_uri: str | None = None,
    expected_raw: bytes | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a create-once identity")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    if (
        type(uri) is not str
        or not uri
        or type(generation) not in {str, int}
        or not str(generation)
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        or type(size) is not int
        or size <= 0
        or value.get("create_once") is not True
    ):
        _fail(f"{label} create-once identity differs")
    if expected_uri is not None and uri != expected_uri:
        _fail(f"{label} URI differs")
    if expected_raw is not None and (
        size != len(expected_raw) or digest != sha256(expected_raw).hexdigest()
    ):
        _fail(f"{label} byte identity differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": size,
        "create_once": True,
    }


def _read(identity: Mapping[str, object], *, read_exact: ReadExact, label: str) -> bytes:
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    return raw


def _source_identity(value: object, *, label: str) -> dict[str, object]:
    """Normalize an immutable input identity without inventing create-once."""
    if not isinstance(value, Mapping):
        _fail(f"{label} is not an exact object identity")
    try:
        normalized = source.normalize_object_identity_v2(value, label=label)
    except ValueError as exc:
        raise PaidSourceAblationOperatorV1Error(str(exc)) from exc
    return dict(normalized)


def _read_source_exact(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> bytes:
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise PaidSourceAblationOperatorV1Error(
            f"{label} generation-exact read failed: {exc}"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact content differs")
    return raw


def _validated_panel(
    *,
    experiment_id: str,
    panel_support: Mapping[str, object],
    slate_evidence: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if experiment_id == registry.ODDS_EXPERIMENT_ID:
        panel = odds.validate_odds_prop_override_panel_support_census_v1(
            panel_support
        )
        evidence = [
            odds.validate_odds_prop_override_influence_trace_v1(value)
            for value in slate_evidence
        ]
        if (
            len(evidence) != panel["slate_count"]
            or [value["slate"] for value in evidence] != panel["slates"]
            or [value["support_census_sha256"] for value in evidence]
            != panel["slate_support_census_sha256s"]
            or panel["historical_execution_status"] != "support-gate-passed"
        ):
            _fail("Odds operator lacks the complete preregistered support panel")
        return panel, evidence
    if experiment_id == registry.MATCHUP_EXPERIMENT_ID:
        panel = matchup.validate_fp_sis_panel_support_census_v1(panel_support)
        evidence = [
            matchup.validate_fp_sis_retrieval_support_census_v1(value)
            for value in slate_evidence
        ]
        if (
            len(evidence) != panel["slate_count"]
            or [value["source_task_ordinal"] for value in evidence]
            != list(range(panel["slate_count"]))
            or [value["slate_support_census_sha256"] for value in evidence]
            != panel["slate_census_sha256s"]
            or panel["support_gate_status"] != "passed"
        ):
            _fail("FP/SIS operator lacks the complete feasible 54-slate panel")
        return panel, evidence
    _fail(f"unknown paid-source experiment {experiment_id!r}")


def _child_bodies(
    *,
    experiment_id: str,
    panel: Mapping[str, object],
    evidence: Sequence[Mapping[str, object]],
) -> list[tuple[str, str, dict[str, object]]]:
    result: list[tuple[str, str, dict[str, object]]] = [
        ("panel-support", "panel-support", dict(panel))
    ]
    seen_body_sha: dict[tuple[str, str], str] = {}

    def add(name: str, kind: str, body: Mapping[str, object]) -> None:
        key = (name, kind)
        digest = registry.canonical_sha256(body)
        if key in seen_body_sha:
            if seen_body_sha[key] != digest:
                _fail(f"paid-source child {name!r} has conflicting bodies")
            return
        seen_body_sha[key] = digest
        result.append((name, kind, dict(body)))

    for ordinal, slate in enumerate(evidence):
        slate_name = f"slates/{ordinal:04d}"
        add(f"{slate_name}/evidence", "slate-evidence", slate)
        if experiment_id == registry.ODDS_EXPERIMENT_ID:
            add(
                f"{slate_name}/support-census",
                "odds-support-census",
                slate["support_census_body"],
            )
            add(
                f"{slate_name}/fallback-authority",
                "odds-dk-ppg-fallback-authority",
                slate["support_census_body"]["fallback_authority_body"],
            )
            add(
                f"{slate_name}/prop-authority",
                "odds-prop-snapshot-authority",
                slate["support_census_body"]["prop_authority_body"],
            )
            for output in slate["cell_outputs"]:
                population_id = str(output["population_cell_id"])
                world_id = str(output["selection_world_cell_id"])
                add(
                    f"{slate_name}/populations/{population_id}",
                    "odds-candidate-population",
                    output["candidate_population_body"],
                )
                add(
                    f"{slate_name}/selection-worlds/{world_id}",
                    "odds-selection-world",
                    output["selection_world_body"],
                )
                add(
                    f"{slate_name}/books/{population_id}--{world_id}",
                    "odds-selected-book",
                    output["selected_book_body"],
                )
        else:
            add(
                f"{slate_name}/structural-catalog",
                "matchup-structural-catalog",
                slate["structural_catalog_body"],
            )
            add(
                f"{slate_name}/candidate-authority",
                "matchup-candidate-authority",
                slate["accepted_candidate_artifact_body"],
            )
            add(
                f"{slate_name}/catalog-join-authority",
                "matchup-catalog-join-authority",
                slate["catalog_join_authority"],
            )
            add(
                f"{slate_name}/world-binding",
                "matchup-world-binding",
                slate["world_matrix_binding"],
            )
            add(
                f"{slate_name}/upstream-source-release",
                "matchup-upstream-source-release",
                slate["upstream_source_release_body"],
            )
            for pack_ordinal, pack_body in enumerate(
                slate["upstream_pack_row_objects"]
            ):
                add(
                    f"{slate_name}/upstream-packs/{pack_ordinal:02d}",
                    "matchup-upstream-pack",
                    pack_body,
                )
            for cell in slate["cells"]:
                add(
                    f"{slate_name}/source-views/{cell['cell']['cell_id']}",
                    "matchup-derived-source-view",
                    cell["source_view"],
                )
    return result


def _matrix_document_requirements(
    *, experiment_id: str, evidence: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    requirements: dict[str, dict[str, object]] = {}
    if experiment_id == registry.ODDS_EXPERIMENT_ID:
        for ordinal, slate in enumerate(evidence):
            seen_worlds: set[str] = set()
            for output in slate["cell_outputs"]:
                world_id = str(output["selection_world_cell_id"])
                if world_id in seen_worlds:
                    continue
                seen_worlds.add(world_id)
                body = output["selection_world_body"]
                requirements[
                    f"slates/{ordinal:04d}/selection-world-matrices/{world_id}"
                ] = {
                    "sha256": str(body["world_matrix_sha256"]),
                    "bytes": int(body["world_matrix_bytes"]),
                    "kind": "odds-world-matrix",
                }
    else:
        for ordinal, slate in enumerate(evidence):
            identity = slate["world_matrix_binding"]["world_matrix_identity"]
            requirements[f"slates/{ordinal:04d}/world-matrix"] = {
                "sha256": str(identity["sha256"]),
                "bytes": int(identity["bytes"]),
                "kind": "matchup-world-matrix",
            }
    return requirements


def _odds_execution_documents(
    *,
    evidence: Sequence[Mapping[str, object]],
    execution_records: Sequence[object] | None,
) -> list[tuple[str, str, str, bytes]]:
    """Materialize the genuine-execution proof carried by an Odds terminal."""
    if (
        execution_records is None
        or isinstance(execution_records, (str, bytes))
        or not isinstance(execution_records, Sequence)
        or len(execution_records) != len(evidence)
    ):
        _fail("Odds ready bundle requires one genuine execution record per slate")
    result: list[tuple[str, str, str, bytes]] = []
    for ordinal, (raw_record, trace) in enumerate(
        zip(execution_records, evidence, strict=True)
    ):
        if type(raw_record) is not _OddsExecutionRecord:
            _fail(
                f"Odds execution record[{ordinal}] was not emitted by the "
                "genuine staged runner"
            )
        record = raw_record
        receipt = record.execution_receipt
        runtime = record.runtime_attestation
        player_input = record.player_input
        candidate_input = record.candidate_input
        centered_raw = record.centered_world_bytes
        if (
            not isinstance(receipt, Mapping)
            or not isinstance(runtime, Mapping)
            or not isinstance(player_input, Mapping)
            or not isinstance(candidate_input, Mapping)
            or type(centered_raw) is not bytes
            or receipt.get("schema_version")
            != odds_execution.EXECUTION_RECEIPT_SCHEMA
            or receipt.get("influence_trace_sha256")
            != trace["influence_trace_sha256"]
            or receipt.get("slate") != trace["slate"]
            or receipt.get("support_census_sha256")
            != trace["support_census_sha256"]
        ):
            _fail(f"Odds execution record[{ordinal}] differs from trace")
        receipt_raw = registry.canonical_json_bytes(dict(receipt))
        receipt_identity = _identity(
            record.execution_receipt_identity,
            label=f"Odds execution receipt[{ordinal}] identity",
            expected_raw=receipt_raw,
        )
        for name, body, identity in (
            ("player input", player_input, record.player_input_identity),
            ("candidate input", candidate_input, record.candidate_input_identity),
        ):
            raw = registry.canonical_json_bytes(dict(body))
            normalized = _source_identity(
                identity, label=f"Odds execution {name}[{ordinal}] identity"
            )
            if (
                normalized["sha256"] != sha256(raw).hexdigest()
                or normalized["bytes"] != len(raw)
            ):
                _fail(f"Odds execution {name}[{ordinal}] byte identity differs")
        centered_identity = _source_identity(
            record.centered_world_identity,
            label=f"Odds centered worlds[{ordinal}] identity",
        )
        if (
            centered_identity["sha256"] != sha256(centered_raw).hexdigest()
            or centered_identity["bytes"] != len(centered_raw)
        ):
            _fail(f"Odds centered worlds[{ordinal}] byte identity differs")
        prefix = f"slates/{ordinal:04d}/execution"
        result.extend((
            (
                f"{prefix}/receipt",
                "odds-genuine-execution-receipt",
                "canonical-json",
                receipt_raw,
            ),
            (
                f"{prefix}/runtime-attestation",
                "odds-runtime-attestation",
                "canonical-json",
                registry.canonical_json_bytes(dict(runtime)),
            ),
            (
                f"{prefix}/player-input",
                "odds-player-input",
                "canonical-json",
                registry.canonical_json_bytes(dict(player_input)),
            ),
            (
                f"{prefix}/candidate-input",
                "odds-candidate-input",
                "canonical-json",
                registry.canonical_json_bytes(dict(candidate_input)),
            ),
            (
                f"{prefix}/centered-player-worlds",
                "odds-centered-player-worlds",
                "raw-binary",
                centered_raw,
            ),
        ))
    return result


def _validate_matrix_document(
    *,
    name: str,
    raw: bytes,
    experiment_id: str,
    evidence: Sequence[Mapping[str, object]],
    requirement: Mapping[str, object],
) -> None:
    if (
        type(raw) is not bytes
        or len(raw) != requirement["bytes"]
        or sha256(raw).hexdigest() != requirement["sha256"]
    ):
        _fail("world-matrix bytes differ from frozen matrix authority")
    if experiment_id != registry.MATCHUP_EXPERIMENT_ID:
        return
    try:
        ordinal = int(name.split("/", 2)[1])
        header_raw, matrix_raw = raw.split(b"\n", 1)
        header = json.loads(header_raw)
    except (IndexError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise PaidSourceAblationOperatorV1Error(
            "FP/SIS world matrix canonical bytes differ"
        ) from exc
    if (
        not isinstance(header, Mapping)
        or registry.canonical_json_bytes(header) != header_raw
        or set(header) != {"schema_version", "candidate_ids", "dtype", "shape"}
        or header.get("schema_version")
        != "r6-paid-source-world-matrix-bytes/v1"
        or ordinal < 0
        or ordinal >= len(evidence)
    ):
        _fail("FP/SIS world matrix canonical header differs")
    slate = evidence[ordinal]
    candidate_ids = [
        str(row["candidate_id"])
        for row in slate["accepted_candidate_artifact_body"]["rows"]
    ]
    try:
        dtype = np.dtype(header["dtype"])
        shape = tuple(int(value) for value in header["shape"])
    except (TypeError, ValueError) as exc:
        raise PaidSourceAblationOperatorV1Error(
            "FP/SIS world matrix dtype/shape differs"
        ) from exc
    if (
        header.get("candidate_ids") != candidate_ids
        or len(shape) != 2
        or shape[0] != len(candidate_ids)
        or shape[1] <= 0
        or dtype.kind != "f"
        or len(matrix_raw) != math.prod(shape) * dtype.itemsize
    ):
        _fail("FP/SIS world matrix canonical body dimensions differ")
    values = np.frombuffer(matrix_raw, dtype=dtype).reshape(shape)
    rebuilt = matchup.build_world_matrix_binding_v1(
        world_matrix_identity=slate["world_matrix_binding"][
            "world_matrix_identity"
        ],
        candidate_ids=candidate_ids,
        world_scores=values,
    )
    if rebuilt != slate["world_matrix_binding"]:
        _fail("FP/SIS world matrix bytes differ from binding")


def _odds_execution_names(ordinal: int) -> dict[str, str]:
    prefix = f"slates/{ordinal:04d}/execution"
    return {
        "receipt": f"{prefix}/receipt",
        "runtime": f"{prefix}/runtime-attestation",
        "player": f"{prefix}/player-input",
        "candidate": f"{prefix}/candidate-input",
        "centered": f"{prefix}/centered-player-worlds",
    }


def _assert_dk_legal_population(
    *, population: Mapping[str, object], player_input: Mapping[str, object],
) -> None:
    by_id = {str(row["gsis_id"]): row for row in player_input["player_rows"]}
    for row in population["candidate_rows"]:
        try:
            players = [by_id[str(player_id)] for player_id in row["player_ids"]]
        except KeyError as exc:
            raise PaidSourceAblationOperatorV1Error(
                "Odds generated roster leaves exact player input"
            ) from exc
        positions = [str(player["position"]) for player in players]
        teams = [str(player["team"]) for player in players]
        salary = sum(int(player["salary"]) for player in players)
        counts = {position: positions.count(position) for position in _POSITIONS}
        if (
            len(players) != 9
            or len({str(player["gsis_id"]) for player in players}) != 9
            or counts != {
                "QB": 1,
                "RB": counts["RB"],
                "WR": counts["WR"],
                "TE": counts["TE"],
                "DST": 1,
            }
            or not 2 <= counts["RB"] <= 3
            or not 3 <= counts["WR"] <= 4
            or not 1 <= counts["TE"] <= 2
            or salary > 50_000
            or len(set(teams)) < 2
            or max((teams.count(team) for team in set(teams)), default=0) > 4
        ):
            _fail("Odds generated candidate is not DK Classic legal")


def _validate_odds_execution_replay(
    *,
    evidence: Sequence[Mapping[str, object]],
    documents: Mapping[str, object],
    read_exact: ReadExact | None,
) -> None:
    """Rebuild source shifts and all four selectors from terminal bytes."""

    def exact(identity: object, expected: bytes, *, label: str) -> None:
        normalized = _source_identity(identity, label=f"{label} identity")
        if (
            normalized["sha256"] != sha256(expected).hexdigest()
            or normalized["bytes"] != len(expected)
        ):
            _fail(f"{label} byte identity differs")
        if read_exact is not None and _read_source_exact(
            normalized, read_exact=read_exact, label=label
        ) != expected:
            _fail(f"{label} exact reopen differs")

    for ordinal, trace in enumerate(evidence):
        names = _odds_execution_names(ordinal)
        receipt = documents.get(names["receipt"])
        runtime = documents.get(names["runtime"])
        player_input = documents.get(names["player"])
        candidate_input = documents.get(names["candidate"])
        centered_raw = documents.get(names["centered"])
        if (
            not isinstance(receipt, Mapping)
            or not isinstance(runtime, Mapping)
            or not isinstance(player_input, Mapping)
            or not isinstance(candidate_input, Mapping)
            or type(centered_raw) is not bytes
        ):
            _fail(f"Odds execution proof[{ordinal}] is incomplete")
        receipt = dict(receipt)
        retained_receipt_hash = receipt.get("execution_receipt_sha256")
        receipt_body = dict(receipt)
        receipt_body.pop("execution_receipt_sha256", None)
        if (
            receipt.get("schema_version") != odds_execution.EXECUTION_RECEIPT_SCHEMA
            or retained_receipt_hash != registry.canonical_sha256(receipt_body)
            or receipt.get("experiment_id") != registry.ODDS_EXPERIMENT_ID
            or receipt.get("slate") != trace["slate"]
            or receipt.get("support_census_sha256")
            != trace["support_census_sha256"]
            or receipt.get("influence_trace_sha256")
            != trace["influence_trace_sha256"]
            or receipt.get("runtime_attestation") != runtime
            or receipt.get("exact_k80_all_crossing_cells") is not True
            or receipt.get("uses_realized_outcomes") is not False
            or receipt.get("outcome_columns_read") != []
        ):
            _fail(f"Odds execution receipt[{ordinal}] differs")
        try:
            runtime_validated = odds_execution._runtime_attestation(runtime)
        except odds_execution.PaidSourceOddsExecutionAdapterV1Error as exc:
            raise PaidSourceAblationOperatorV1Error(str(exc)) from exc
        if runtime_validated != runtime:
            _fail(f"Odds runtime attestation[{ordinal}] differs")
        census = trace["support_census_body"]
        input_identities = receipt.get("exact_input_identities")
        if not isinstance(input_identities, Mapping) or set(input_identities) != {
            "player_input", "candidate_generation_input", "centered_player_worlds"
        }:
            _fail(f"Odds execution input manifest[{ordinal}] differs")
        player_raw = registry.canonical_json_bytes(dict(player_input))
        candidate_raw = registry.canonical_json_bytes(dict(candidate_input))
        exact(input_identities["player_input"], player_raw, label=f"Odds player input[{ordinal}]")
        exact(
            input_identities["candidate_generation_input"], candidate_raw,
            label=f"Odds candidate input[{ordinal}]",
        )
        exact(
            input_identities["centered_player_worlds"], centered_raw,
            label=f"Odds centered worlds[{ordinal}]",
        )
        try:
            players, _ = odds_execution.validate_odds_execution_player_input_v1(
                player_input,
                support_census=census,
                identity=input_identities["player_input"],
            )
            candidate_plan, _ = (
                odds_execution.validate_odds_execution_candidate_input_v1(
                    candidate_input,
                    support_census=census,
                    identity=input_identities["candidate_generation_input"],
                )
            )
            world_header, centered, _ = odds_execution._open_centered_worlds(
                raw=centered_raw,
                identity=input_identities["centered_player_worlds"],
                support_census=census,
            )
        except odds_execution.PaidSourceOddsExecutionAdapterV1Error as exc:
            raise PaidSourceAblationOperatorV1Error(str(exc)) from exc
        implementation = receipt.get("implementation")
        if (
            not isinstance(implementation, Mapping)
            or implementation.get("generation_family")
            != odds_execution.GENERATION_FAMILY
            or implementation.get("selection_law") != odds_execution.SELECTION_LAW
            or implementation.get("tail_line") != odds_execution.TAIL_LINE
            or implementation.get("entry_budget") != registry.ENTRY_BUDGET
            or implementation.get("construction_preset_receipt")
            != candidate_plan["construction_preset_receipt"]
        ):
            _fail(f"Odds execution implementation[{ordinal}] differs")
        player_ids = [str(value) for value in world_header["player_ids"]]
        generation_receipts = receipt.get("generation_receipts")
        selection_receipts = receipt.get("selection_receipts")
        if (
            not isinstance(generation_receipts, Sequence)
            or isinstance(generation_receipts, (str, bytes))
            or len(generation_receipts) != 2
            or not isinstance(selection_receipts, Sequence)
            or isinstance(selection_receipts, (str, bytes))
            or len(selection_receipts) != 4
        ):
            _fail(f"Odds execution work receipts[{ordinal}] differ")
        worlds_by_cell: dict[str, np.ndarray] = {}
        population_by_cell: dict[str, Mapping[str, object]] = {}
        output_by_cross = {
            (row["population_cell_id"], row["selection_world_cell_id"]): row
            for row in trace["cell_outputs"]
        }
        for cell_index, cell_id in enumerate(registry.ODDS_CELL_ORDER):
            output = output_by_cross[(cell_id, registry.ODDS_CELL_ORDER[0])]
            selection_output = output_by_cross[(registry.ODDS_CELL_ORDER[0], cell_id)]
            matrix_name = (
                f"slates/{ordinal:04d}/selection-world-matrices/{cell_id}"
            )
            matrix_raw = documents.get(matrix_name)
            if type(matrix_raw) is not bytes:
                _fail(f"Odds shifted world matrix[{ordinal}] is absent")
            try:
                header_raw, values_raw = matrix_raw.split(b"\n", 1)
                header = json.loads(header_raw)
                if (
                    not isinstance(header, Mapping)
                    or registry.canonical_json_bytes(dict(header)) != header_raw
                    or header.get("schema_version") != odds_execution.SHIFTED_WORLD_SCHEMA
                    or header.get("selection_world_cell_id") != cell_id
                    or header.get("player_ids") != player_ids
                    or header.get("dtype") != "<f8"
                ):
                    _fail(f"Odds shifted world header[{ordinal}] differs")
                shape = tuple(int(value) for value in header["shape"])
                shifted = np.frombuffer(values_raw, dtype="<f8").reshape(shape)
            except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
                raise PaidSourceAblationOperatorV1Error(
                    f"Odds shifted world matrix[{ordinal}] differs"
                ) from exc
            projection_rows = odds_execution._cell_projection_rows(census, cell_id)
            means = np.asarray(
                [float(row["blended_mean"]) for row in projection_rows],
                dtype=np.float64,
            )
            if (
                shifted.shape != centered.shape
                or not np.array_equal(shifted, centered + means[:, None])
                or selection_output["selection_world_body"]["world_matrix_sha256"]
                != sha256(matrix_raw).hexdigest()
                or selection_output["selection_world_body"]["world_matrix_bytes"]
                != len(matrix_raw)
            ):
                _fail(f"Odds shifted world replay[{ordinal}] differs")
            worlds_by_cell[cell_id] = shifted
            population = output["candidate_population_body"]
            _assert_dk_legal_population(population=population, player_input=players)
            population_by_cell[cell_id] = population
            generation_receipt = generation_receipts[cell_index]
            if (
                generation_receipt.get("cell_id") != cell_id
                or generation_receipt.get("unique_candidate_count")
                != len(population["candidate_rows"])
                or generation_receipt.get("candidate_population_identity")
                != output["candidate_population_identity"]
                or generation_receipt.get("selection_world_body_identity")
                != selection_output["selection_world_identity"]
            ):
                _fail(f"Odds generation receipt[{ordinal}] differs")
            exact(
                generation_receipt["candidate_population_identity"],
                registry.canonical_json_bytes(dict(population)),
                label=f"Odds candidate population[{ordinal}:{cell_id}]",
            )
            exact(
                generation_receipt["selection_world_body_identity"],
                registry.canonical_json_bytes(dict(selection_output["selection_world_body"])),
                label=f"Odds selection world body[{ordinal}:{cell_id}]",
            )
            exact(
                generation_receipt["selection_world_matrix_identity"], matrix_raw,
                label=f"Odds shifted world matrix[{ordinal}:{cell_id}]",
            )
        for cross_index, (population_cell, selection_cell) in enumerate(
            registry.ODDS_CROSS_ORDER
        ):
            output = output_by_cross[(population_cell, selection_cell)]
            rows = population_by_cell[population_cell]["candidate_rows"]
            totals = odds_execution._candidate_totals(
                rows, player_ids=player_ids, worlds=worlds_by_cell[selection_cell]
            )
            selected_indices = odds_execution.select_tail_entries(
                totals, registry.ENTRY_BUDGET, odds_execution.TAIL_LINE, env={}
            )
            expected_selected = [
                str(rows[index]["candidate_id"]) for index in selected_indices
            ]
            selection_receipt = selection_receipts[cross_index]
            if (
                len(selected_indices) != registry.ENTRY_BUDGET
                or expected_selected != output["selected_lineup_ids"]
                or selection_receipt.get("population_cell_id") != population_cell
                or selection_receipt.get("selection_world_cell_id") != selection_cell
                or selection_receipt.get("candidate_count") != len(rows)
                or selection_receipt.get("entry_budget") != registry.ENTRY_BUDGET
                or selection_receipt.get("selected_book_identity")
                != output["selected_book_identity"]
            ):
                _fail(f"Odds exact K80 selection replay[{ordinal}] differs")
            exact(
                selection_receipt["selected_book_identity"],
                registry.canonical_json_bytes(dict(output["selected_book_body"])),
                label=(
                    f"Odds selected book[{ordinal}:{population_cell}--{selection_cell}]"
                ),
            )
        exact(
            receipt["influence_trace_identity"],
            registry.canonical_json_bytes(dict(trace)),
            label=f"Odds influence trace[{ordinal}]",
        )


def prepare_paid_source_bundle_v1(
    *,
    experiment_id: str,
    panel_support: Mapping[str, object],
    slate_evidence: Sequence[Mapping[str, object]],
    run_id: str,
    output_prefix: str,
    frozen_at: str,
    world_matrix_bytes_by_sha256: Mapping[str, bytes],
    odds_execution_records: Sequence[object] | None = None,
) -> dict[str, object]:
    """Prepare a bounded, score-blind publication bundle without mutation."""

    panel, evidence = _validated_panel(
        experiment_id=experiment_id,
        panel_support=panel_support,
        slate_evidence=slate_evidence,
    )
    retained_run_id = str(run_id).strip()
    if _ID.fullmatch(retained_run_id) is None:
        _fail("run ID differs")
    prefix = str(output_prefix).strip().rstrip("/")
    if not prefix.startswith("gs://") or "//" in prefix[5:]:
        _fail("output prefix must be one normalized GCS prefix")
    retained_frozen_at = _timestamp(frozen_at, label="frozen_at")
    run_prefix = f"{prefix}/{retained_run_id}"
    documents: dict[str, bytes] = {}
    manifest: list[dict[str, object]] = []
    for name, kind, body in _child_bodies(
        experiment_id=experiment_id, panel=panel, evidence=evidence
    ):
        raw = _document(body)
        uri = f"{run_prefix}/{name}.json"
        if name in documents or any(row["uri"] == uri for row in manifest):
            _fail("paid-source publication repeats a child document")
        documents[name] = raw
        manifest.append({
            "name": name,
            "kind": kind,
            "encoding": "canonical-json-newline",
            "uri": uri,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    execution_documents: list[tuple[str, str, str, bytes]] = []
    if experiment_id == registry.ODDS_EXPERIMENT_ID:
        execution_documents = _odds_execution_documents(
            evidence=evidence, execution_records=odds_execution_records
        )
    elif odds_execution_records is not None:
        _fail("FP/SIS ready bundle cannot carry Odds execution records")
    for name, kind, encoding, raw in execution_documents:
        uri = f"{run_prefix}/{name}" + (
            ".json" if encoding.startswith("canonical-json") else ".bin"
        )
        if name in documents or any(row["uri"] == uri for row in manifest):
            _fail("paid-source publication repeats an execution document")
        documents[name] = raw
        manifest.append({
            "name": name,
            "kind": kind,
            "encoding": encoding,
            "uri": uri,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    if not isinstance(world_matrix_bytes_by_sha256, Mapping):
        _fail("world-matrix byte authority is not a mapping")
    matrix_requirements = _matrix_document_requirements(
        experiment_id=experiment_id, evidence=evidence
    )
    required_digests = {
        str(requirement["sha256"]) for requirement in matrix_requirements.values()
    }
    if set(world_matrix_bytes_by_sha256) != required_digests:
        _fail("world-matrix byte authority does not exactly cover the panel")
    for name, requirement in matrix_requirements.items():
        digest = str(requirement["sha256"])
        raw = world_matrix_bytes_by_sha256[digest]
        _validate_matrix_document(
            name=name,
            raw=raw,
            experiment_id=experiment_id,
            evidence=evidence,
            requirement=requirement,
        )
        uri = f"{run_prefix}/{name}.bin"
        if name in documents or any(row["uri"] == uri for row in manifest):
            _fail("paid-source publication repeats a matrix document")
        documents[name] = raw
        manifest.append({
            "name": name,
            "kind": requirement["kind"],
            "encoding": "raw-binary",
            "uri": uri,
            "sha256": digest,
            "bytes": len(raw),
        })
    body: dict[str, object] = {
        "schema_version": READY_SCHEMA,
        "experiment_id": experiment_id,
        "registry_sha256": registry.frozen_paid_source_ablation_registry_v1()[
            "registry_sha256"
        ],
        "run_id": retained_run_id,
        "frozen_at": retained_frozen_at,
        "panel_support_sha256": (
            panel["panel_support_census_sha256"]
            if experiment_id == registry.ODDS_EXPERIMENT_ID
            else panel["panel_support_census_sha256"]
        ),
        "slate_count": len(evidence),
        "document_manifest": manifest,
        "document_manifest_sha256": registry.canonical_sha256(manifest),
        "terminal_uri": f"{run_prefix}/terminal.json",
        "publication_order": ["all-child-documents", "terminal-root-last"],
        "status": "ready-for-create-once-publication",
        "all_cells_complete": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "scoring_value_claim": "not-evaluated-by-publication",
        "source_value_established": False,
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    return {
        **body,
        "ready_sha256": registry.canonical_sha256(body),
        "documents_raw_by_name": documents,
    }


def run_odds_panel_to_ready_v1(
    *,
    slate_inputs: Sequence[Mapping[str, object]],
    preregistered_slates: Sequence[Mapping[str, object]],
    preregistered_panel_identity: Mapping[str, object],
    run_id: str,
    output_prefix: str,
    frozen_at: str,
    publish_execution_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Stage genuine Odds execution, then return its publishable terminal.

    The solver-emitted objects are necessarily create-once staged before the
    terminal bundle can bind their real storage generations.  A failure may
    therefore leave unreferenced immutable staging objects, but can never
    produce a ready bundle or terminal.  Caller-prebuilt populations/books are
    not accepted by this API.
    """

    if not slate_inputs:
        _fail("Odds runner requires a nonempty exact preregistered panel")
    retained_run_id = str(run_id).strip()
    prefix = str(output_prefix).strip().rstrip("/")
    if (
        _ID.fullmatch(retained_run_id) is None
        or not prefix.startswith("gs://")
        or "//" in prefix[5:]
        or not callable(publish_execution_create_once)
        or not callable(read_exact)
    ):
        _fail("Odds staged execution publication contract differs")
    _timestamp(frozen_at, label="frozen_at")
    run_prefix = f"{prefix}/{retained_run_id}"
    support: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    execution_records: list[_OddsExecutionRecord] = []
    generated_worlds: dict[str, bytes] = {}
    expected_fields = {
        "slate",
        "model_rows",
        "fallback_authority",
        "fallback_authority_identity",
        "prop_authority",
        "prop_authority_identity",
        "player_input_identity",
        "candidate_input_identity",
        "centered_world_identity",
        "runtime_attestation",
    }
    for ordinal, raw in enumerate(slate_inputs):
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            _fail(f"Odds runner input[{ordinal}] fields differ")
        census = odds.build_odds_prop_override_support_census_v1(
            slate=raw["slate"],
            model_rows=raw["model_rows"],
            fallback_authority=raw["fallback_authority"],
            fallback_authority_identity=raw["fallback_authority_identity"],
            prop_authority=raw["prop_authority"],
            prop_authority_identity=raw["prop_authority_identity"],
        )
        support.append(census)
        player_identity = _source_identity(
            raw["player_input_identity"],
            label=f"Odds player input[{ordinal}] identity",
        )
        candidate_identity = _source_identity(
            raw["candidate_input_identity"],
            label=f"Odds candidate input[{ordinal}] identity",
        )
        centered_identity = _source_identity(
            raw["centered_world_identity"],
            label=f"Odds centered worlds[{ordinal}] identity",
        )
        player_raw = _read_source_exact(
            player_identity, read_exact=read_exact,
            label=f"Odds player input[{ordinal}]",
        )
        candidate_raw = _read_source_exact(
            candidate_identity, read_exact=read_exact,
            label=f"Odds candidate input[{ordinal}]",
        )
        centered_raw = _read_source_exact(
            centered_identity, read_exact=read_exact,
            label=f"Odds centered worlds[{ordinal}]",
        )
        player_input = _parse_canonical_json(
            player_raw, label=f"Odds player input[{ordinal}]"
        )
        candidate_input = _parse_canonical_json(
            candidate_raw, label=f"Odds candidate input[{ordinal}]"
        )

        def bind_execution_output(name: str, output_raw: bytes) -> dict[str, object]:
            uri = f"{run_prefix}/staging/slates/{ordinal:04d}/{name}"
            identity = _identity(
                publish_execution_create_once(uri, output_raw),
                label=f"Odds staged output[{ordinal}] {name}",
                expected_uri=uri,
                expected_raw=output_raw,
            )
            if _read(
                identity, read_exact=read_exact,
                label=f"Odds staged output[{ordinal}] {name}",
            ) != output_raw:
                _fail(f"Odds staged output[{ordinal}] {name} reopen differs")
            # The scientific execution contract uses the generic four-field
            # generation-exact identity; create-once is separately proven by
            # this staging operator and its publication callback.
            return {
                key: identity[key]
                for key in ("uri", "generation", "sha256", "bytes")
            }

        try:
            executed = odds_execution.execute_odds_prop_override_cross_v1(
                support_census=census,
                player_input=player_input,
                player_input_identity=player_identity,
                candidate_input=candidate_input,
                candidate_input_identity=candidate_identity,
                centered_world_bytes=centered_raw,
                centered_world_identity=centered_identity,
                runtime_attestation=raw["runtime_attestation"],
                bind_output=bind_execution_output,
            )
        except odds_execution.PaidSourceOddsExecutionAdapterV1Error as exc:
            raise PaidSourceAblationOperatorV1Error(
                f"Odds genuine execution[{ordinal}] failed: {exc}"
            ) from exc
        receipt = dict(executed["execution_receipt"])
        receipt_raw = registry.canonical_json_bytes(receipt)
        receipt_uri = (
            f"{run_prefix}/staging/slates/{ordinal:04d}/execution-receipt.json"
        )
        receipt_identity = _identity(
            publish_execution_create_once(receipt_uri, receipt_raw),
            label=f"Odds execution receipt[{ordinal}]",
            expected_uri=receipt_uri,
            expected_raw=receipt_raw,
        )
        if _read(
            receipt_identity, read_exact=read_exact,
            label=f"Odds execution receipt[{ordinal}]",
        ) != receipt_raw:
            _fail(f"Odds execution receipt[{ordinal}] reopen differs")
        trace = dict(executed["influence_trace"])
        evidence.append(trace)
        for digest, matrix_raw in executed["world_matrix_bytes_by_sha256"].items():
            if digest in generated_worlds and generated_worlds[digest] != matrix_raw:
                _fail("Odds execution repeated a matrix digest with different bytes")
            generated_worlds[str(digest)] = matrix_raw
        execution_records.append(_OddsExecutionRecord(
            execution_receipt=receipt,
            execution_receipt_identity=receipt_identity,
            runtime_attestation=dict(raw["runtime_attestation"]),
            player_input=player_input,
            player_input_identity=player_identity,
            candidate_input=candidate_input,
            candidate_input_identity=candidate_identity,
            centered_world_bytes=centered_raw,
            centered_world_identity=centered_identity,
        ))
    panel = odds.build_odds_prop_override_panel_support_census_v1(
        support,
        preregistered_slates=preregistered_slates,
        preregistered_panel_identity=preregistered_panel_identity,
    )
    return prepare_paid_source_bundle_v1(
        experiment_id=registry.ODDS_EXPERIMENT_ID,
        panel_support=panel,
        slate_evidence=evidence,
        run_id=run_id,
        output_prefix=output_prefix,
        frozen_at=frozen_at,
        world_matrix_bytes_by_sha256=generated_worlds,
        odds_execution_records=execution_records,
    )


def run_fp_sis_panel_to_ready_v1(
    *,
    slate_inputs: Sequence[Mapping[str, object]],
    run_id: str,
    output_prefix: str,
    frozen_at: str,
    world_matrix_bytes_by_sha256: Mapping[str, bytes],
    canonical_source_v3_reopen_by_ordinal: Callable[[int], Mapping[str, object]],
) -> dict[str, object]:
    """Bounded 54-slate runner for the physical-removal retrieval cross."""

    if len(slate_inputs) != 54:
        _fail("FP/SIS runner requires exactly 54 immutable slate inputs")
    if not callable(canonical_source_v3_reopen_by_ordinal):
        _fail("FP/SIS runner requires the canonical source-v3 deep reopener")
    expected_fields = {
        "structural_catalog",
        "structural_catalog_identity",
        "accepted_candidate_artifact",
        "accepted_candidate_artifact_identity",
        "upstream_source_release",
        "upstream_source_release_identity",
        "upstream_pack_row_objects",
        "world_matrix_binding",
        "world_scores",
    }
    evidence: list[dict[str, object]] = []
    for ordinal, raw in enumerate(slate_inputs):
        if not isinstance(raw, Mapping) or set(raw) != expected_fields:
            _fail(f"FP/SIS runner input[{ordinal}] fields differ")
        try:
            reopened = canonical_source_v3_reopen_by_ordinal(ordinal)
        except Exception as exc:
            raise PaidSourceAblationOperatorV1Error(
                f"FP/SIS source-v3 deep reopen[{ordinal}] failed: {exc}"
            ) from exc
        if not isinstance(reopened, Mapping):
            _fail(f"FP/SIS source-v3 deep reopen[{ordinal}] differs")
        release = reopened.get("release")
        member = reopened.get("member")
        candidate_binding = reopened.get("candidate_authority_binding")
        if (
            not isinstance(release, Mapping)
            or not isinstance(member, Mapping)
            or not isinstance(candidate_binding, Mapping)
            or reopened.get("structural_catalog") != raw["structural_catalog"]
            or reopened.get("candidate_artifact")
            != raw["accepted_candidate_artifact"]
            or release.get("upstream_source_release_identity")
            != raw["upstream_source_release_identity"]
            or candidate_binding.get("candidate_artifact_identity")
            != raw["accepted_candidate_artifact_identity"]
            or member.get("source_task_ordinal") != ordinal
            or not registry.is_sha256(
                release.get("matchup_source_release_candidate_authority_sha256")
            )
            or not registry.is_sha256(
                member.get("matchup_source_member_candidate_authority_sha256")
            )
        ):
            _fail(
                f"FP/SIS source-v3 deep reopen[{ordinal}] differs from runner input"
            )
        census = matchup.run_fp_sis_retrieval_support_census_v1(
            structural_catalog=raw["structural_catalog"],
            structural_catalog_identity=raw["structural_catalog_identity"],
            accepted_candidate_artifact=raw["accepted_candidate_artifact"],
            accepted_candidate_artifact_identity=raw[
                "accepted_candidate_artifact_identity"
            ],
            upstream_source_release=raw["upstream_source_release"],
            upstream_source_release_identity=raw[
                "upstream_source_release_identity"
            ],
            upstream_pack_row_objects=raw["upstream_pack_row_objects"],
            world_matrix_binding=raw["world_matrix_binding"],
            world_scores=raw["world_scores"],
        )
        if census["source_task_ordinal"] != ordinal:
            _fail("FP/SIS runner inputs differ from fixed 54-slate order")
        evidence.append(census)
    panel = matchup.build_fp_sis_panel_support_census_v1(evidence)
    return prepare_paid_source_bundle_v1(
        experiment_id=registry.MATCHUP_EXPERIMENT_ID,
        panel_support=panel,
        slate_evidence=evidence,
        run_id=run_id,
        output_prefix=output_prefix,
        frozen_at=frozen_at,
        world_matrix_bytes_by_sha256=world_matrix_bytes_by_sha256,
    )


def validate_ready_bundle_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("ready bundle is not a mapping")
    item = dict(value)
    documents = item.pop("documents_raw_by_name", None)
    retained_hash = item.pop("ready_sha256", None)
    if (
        not isinstance(documents, Mapping)
        or set(item) != {
            "schema_version",
            "experiment_id",
            "registry_sha256",
            "run_id",
            "frozen_at",
            "panel_support_sha256",
            "slate_count",
            "document_manifest",
            "document_manifest_sha256",
            "terminal_uri",
            "publication_order",
            "status",
            "all_cells_complete",
            "outcome_columns_read",
            "uses_realized_outcomes",
            "scoring_value_claim",
            "source_value_established",
            "automatic_policy_promotion",
            "production_policy_authority",
        }
        or type(retained_hash) is not str
        or _SHA256.fullmatch(retained_hash) is None
        or registry.canonical_sha256(item) != retained_hash
        or item.get("schema_version") != READY_SCHEMA
        or item.get("status") != "ready-for-create-once-publication"
        or item.get("publication_order")
        != ["all-child-documents", "terminal-root-last"]
        or item.get("uses_realized_outcomes") is not False
        or item.get("outcome_columns_read") != []
        or item.get("scoring_value_claim") != "not-evaluated-by-publication"
        or item.get("source_value_established") is not False
        or item.get("automatic_policy_promotion") is not False
        or item.get("production_policy_authority") is not False
    ):
        _fail("ready bundle differs")
    manifest = item.get("document_manifest")
    if not isinstance(manifest, Sequence) or isinstance(manifest, (str, bytes)):
        _fail("ready document manifest differs")
    if (
        item.get("document_manifest_sha256")
        != registry.canonical_sha256(manifest)
        or {row.get("name") for row in manifest if isinstance(row, Mapping)}
        != set(documents)
    ):
        _fail("ready document manifest binding differs")
    parsed_documents: dict[str, dict[str, object]] = {}
    manifest_by_name: dict[str, dict[str, object]] = {}
    for raw_row in manifest:
        if not isinstance(raw_row, Mapping):
            _fail("ready document manifest row differs")
        row = dict(raw_row)
        raw = documents.get(row.get("name"))
        if (
            set(row) != {
                "name", "kind", "encoding", "uri", "sha256", "bytes"
            }
            or type(raw) is not bytes
            or row.get("sha256") != sha256(raw).hexdigest()
            or row.get("bytes") != len(raw)
        ):
            _fail("ready child document binding differs")
        manifest_by_name[str(row["name"])] = row
        if row.get("encoding") == "canonical-json-newline":
            parsed_documents[str(row["name"])] = _parse_document(
                raw, label=f"ready child {row.get('name')}"
            )
        elif row.get("encoding") == "canonical-json":
            parsed_documents[str(row["name"])] = _parse_canonical_json(
                raw, label=f"ready child {row.get('name')}"
            )
        elif row.get("encoding") != "raw-binary":
            _fail("ready child document encoding differs")
    panel = parsed_documents.get("panel-support")
    evidence_names = sorted(
        name for name in parsed_documents if name.endswith("/evidence")
    )
    if panel is None:
        _fail("ready bundle lacks panel support")
    try:
        validated_panel, validated_evidence = _validated_panel(
            experiment_id=str(item.get("experiment_id")),
            panel_support=panel,
            slate_evidence=[parsed_documents[name] for name in evidence_names],
        )
    except (odds.OddsPropOverrideAblationV1Error, matchup.CorpusR6PaidSourceAblationV1Error) as exc:
        raise PaidSourceAblationOperatorV1Error(str(exc)) from exc
    expected_json = {
        name: body
        for name, _, body in _child_bodies(
            experiment_id=str(item["experiment_id"]),
            panel=validated_panel,
            evidence=validated_evidence,
        )
    }
    expected_matrices = _matrix_document_requirements(
        experiment_id=str(item["experiment_id"]), evidence=validated_evidence
    )
    expected_execution_names: set[str] = set()
    if item["experiment_id"] == registry.ODDS_EXPERIMENT_ID:
        expected_execution_names = {
            name
            for ordinal in range(len(validated_evidence))
            for name in _odds_execution_names(ordinal).values()
        }
    if (
        item.get("registry_sha256")
        != registry.frozen_paid_source_ablation_registry_v1()["registry_sha256"]
        or item.get("panel_support_sha256")
        != validated_panel["panel_support_census_sha256"]
        or item.get("slate_count") != len(validated_evidence)
        or item.get("all_cells_complete") is not True
        or set(documents)
        != set(expected_json) | set(expected_matrices) | expected_execution_names
    ):
        _fail("ready bundle child set differs from the complete experiment")
    for name, body in expected_json.items():
        if (
            parsed_documents.get(name) != body
            or manifest_by_name[name]["encoding"] != "canonical-json-newline"
        ):
            _fail("ready JSON child differs from exact experiment body")
    for name, requirement in expected_matrices.items():
        raw = documents[name]
        row = manifest_by_name[name]
        _validate_matrix_document(
            name=name,
            raw=raw,
            experiment_id=str(item["experiment_id"]),
            evidence=validated_evidence,
            requirement=requirement,
        )
        if (
            row["encoding"] != "raw-binary"
            or row["kind"] != requirement["kind"]
            or row["sha256"] != requirement["sha256"]
            or row["bytes"] != requirement["bytes"]
        ):
            _fail("ready world-matrix child differs from exact authority")
    if item["experiment_id"] == registry.ODDS_EXPERIMENT_ID:
        _validate_odds_execution_replay(
            evidence=validated_evidence,
            documents={**parsed_documents, **{
                name: raw for name, raw in documents.items()
                if name not in parsed_documents
            }},
            read_exact=None,
        )
    return {**item, "ready_sha256": retained_hash, "documents_raw_by_name": dict(documents)}


def publish_paid_source_bundle_v1(
    ready_bundle: Mapping[str, object],
    *,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Publish every child, exact-reopen it, then publish terminal root last."""

    ready = validate_ready_bundle_v1(ready_bundle)
    if not callable(publish_create_once) or not callable(read_exact):
        _fail("publication callbacks are not callable")
    child_identities: list[dict[str, object]] = []
    for row in ready["document_manifest"]:
        raw = ready["documents_raw_by_name"][row["name"]]
        identity = _identity(
            publish_create_once(str(row["uri"]), raw),
            label=f"published {row['name']}",
            expected_uri=str(row["uri"]),
            expected_raw=raw,
        )
        if _read(identity, read_exact=read_exact, label=str(row["name"])) != raw:
            _fail(f"published {row['name']} exact reopen differs")
        child_identities.append({
            "name": row["name"],
            "kind": row["kind"],
            "encoding": row["encoding"],
            "identity": identity,
        })
    terminal_body: dict[str, object] = {
        "schema_version": TERMINAL_SCHEMA,
        "experiment_id": ready["experiment_id"],
        "registry_sha256": ready["registry_sha256"],
        "run_id": ready["run_id"],
        "frozen_at": ready["frozen_at"],
        "ready_sha256": ready["ready_sha256"],
        "panel_support_sha256": ready["panel_support_sha256"],
        "slate_count": ready["slate_count"],
        "child_identities": child_identities,
        "child_identity_manifest_sha256": registry.canonical_sha256(
            child_identities
        ),
        "all_outputs_create_once": True,
        "all_outputs_exact_reopened": True,
        "terminal_published_last": True,
        "score_blind_evidence_frozen_before_outcome_join": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
        "historical_evidence_status": "awaiting-independent-grade",
        "scoring_value_claim": "not-evaluated-by-publication",
        "source_value_established": False,
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    terminal_body["terminal_sha256"] = registry.canonical_sha256(terminal_body)
    terminal_raw = _document(terminal_body)
    terminal_identity = _identity(
        publish_create_once(str(ready["terminal_uri"]), terminal_raw),
        label="published paid-source terminal",
        expected_uri=str(ready["terminal_uri"]),
        expected_raw=terminal_raw,
    )
    if _read(terminal_identity, read_exact=read_exact, label="terminal") != terminal_raw:
        _fail("published terminal exact reopen differs")
    envelope: dict[str, object] = {
        "schema_version": TERMINAL_ENVELOPE_SCHEMA,
        "experiment_id": ready["experiment_id"],
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal_body["terminal_sha256"],
        "complete": True,
        "create_once": True,
        "uses_realized_outcomes": False,
    }
    envelope["envelope_sha256"] = registry.canonical_sha256(envelope)
    return envelope


def reopen_paid_source_terminal_v1(
    terminal_envelope: Mapping[str, object], *, read_exact: ReadExact,
) -> dict[str, object]:
    """Reopen terminal and every child by its exact generation."""

    if not isinstance(terminal_envelope, Mapping):
        _fail("terminal envelope is not a mapping")
    envelope = dict(terminal_envelope)
    retained = envelope.pop("envelope_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or registry.canonical_sha256(envelope) != retained
        or envelope.get("schema_version") != TERMINAL_ENVELOPE_SCHEMA
        or envelope.get("complete") is not True
        or envelope.get("create_once") is not True
        or envelope.get("uses_realized_outcomes") is not False
        or set(envelope) != {
            "schema_version",
            "experiment_id",
            "terminal_identity",
            "terminal_sha256",
            "complete",
            "create_once",
            "uses_realized_outcomes",
        }
    ):
        _fail("terminal envelope differs")
    terminal_identity = _identity(
        envelope.get("terminal_identity"), label="paid-source terminal identity"
    )
    terminal = _parse_document(
        _read(terminal_identity, read_exact=read_exact, label="terminal"),
        label="terminal",
    )
    terminal_hash = terminal.get("terminal_sha256")
    terminal_body = dict(terminal)
    terminal_body.pop("terminal_sha256", None)
    children = terminal.get("child_identities")
    if (
        set(terminal) != {
            "schema_version",
            "experiment_id",
            "registry_sha256",
            "run_id",
            "frozen_at",
            "ready_sha256",
            "panel_support_sha256",
            "slate_count",
            "child_identities",
            "child_identity_manifest_sha256",
            "all_outputs_create_once",
            "all_outputs_exact_reopened",
            "terminal_published_last",
            "score_blind_evidence_frozen_before_outcome_join",
            "outcome_columns_read",
            "uses_realized_outcomes",
            "complete",
            "historical_evidence_status",
            "scoring_value_claim",
            "source_value_established",
            "automatic_policy_promotion",
            "production_policy_authority",
            "terminal_sha256",
        }
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("experiment_id") != envelope.get("experiment_id")
        or terminal_hash != envelope.get("terminal_sha256")
        or registry.canonical_sha256(terminal_body) != terminal_hash
        or terminal.get("complete") is not True
        or terminal.get("all_outputs_create_once") is not True
        or terminal.get("all_outputs_exact_reopened") is not True
        or terminal.get("terminal_published_last") is not True
        or terminal.get("score_blind_evidence_frozen_before_outcome_join") is not True
        or terminal.get("outcome_columns_read") != []
        or terminal.get("uses_realized_outcomes") is not False
        or terminal.get("historical_evidence_status")
        != "awaiting-independent-grade"
        or terminal.get("scoring_value_claim")
        != "not-evaluated-by-publication"
        or terminal.get("source_value_established") is not False
        or terminal.get("automatic_policy_promotion") is not False
        or terminal.get("production_policy_authority") is not False
        or terminal.get("registry_sha256")
        != registry.frozen_paid_source_ablation_registry_v1()["registry_sha256"]
        or not isinstance(children, Sequence)
        or isinstance(children, (str, bytes))
        or terminal.get("child_identity_manifest_sha256")
        != registry.canonical_sha256(children)
    ):
        _fail("paid-source terminal differs")
    documents: dict[str, object] = {}
    for raw_row in children:
        if not isinstance(raw_row, Mapping) or set(raw_row) != {
            "name", "kind", "encoding", "identity"
        }:
            _fail("paid-source terminal child row differs")
        name = raw_row["name"]
        if type(name) is not str or not name or name in documents:
            _fail("paid-source terminal repeats a child name")
        identity = _identity(raw_row["identity"], label=f"{name} identity")
        raw = _read(identity, read_exact=read_exact, label=name)
        if raw_row["encoding"] == "canonical-json-newline":
            documents[name] = _parse_document(raw, label=name)
        elif raw_row["encoding"] == "canonical-json":
            documents[name] = _parse_canonical_json(raw, label=name)
        elif raw_row["encoding"] == "raw-binary":
            documents[name] = raw
        else:
            _fail("paid-source terminal child encoding differs")
    panel = documents.get("panel-support")
    evidence_names = sorted(
        name for name in documents if name.endswith("/evidence")
    )
    if panel is None:
        _fail("paid-source terminal lacks panel support")
    validated_panel, validated_evidence = _validated_panel(
        experiment_id=str(terminal["experiment_id"]),
        panel_support=panel,
        slate_evidence=[documents[name] for name in evidence_names],
    )
    expected_json = {
        name: body
        for name, _, body in _child_bodies(
            experiment_id=str(terminal["experiment_id"]),
            panel=validated_panel,
            evidence=validated_evidence,
        )
    }
    expected_matrices = _matrix_document_requirements(
        experiment_id=str(terminal["experiment_id"]),
        evidence=validated_evidence,
    )
    expected_execution_names: set[str] = set()
    if terminal["experiment_id"] == registry.ODDS_EXPERIMENT_ID:
        expected_execution_names = {
            name
            for ordinal in range(len(validated_evidence))
            for name in _odds_execution_names(ordinal).values()
        }
    for name, requirement in expected_matrices.items():
        raw = documents.get(name)
        if type(raw) is not bytes:
            _fail("paid-source terminal lacks a world-matrix body")
        _validate_matrix_document(
            name=name,
            raw=raw,
            experiment_id=str(terminal["experiment_id"]),
            evidence=validated_evidence,
            requirement=requirement,
        )
    if (
        len(validated_evidence) != terminal["slate_count"]
        or terminal.get("panel_support_sha256")
        != validated_panel["panel_support_census_sha256"]
        or set(documents)
        != set(expected_json) | set(expected_matrices) | expected_execution_names
        or any(documents.get(name) != body for name, body in expected_json.items())
    ):
        _fail("paid-source terminal slate count differs")
    if terminal["experiment_id"] == registry.ODDS_EXPERIMENT_ID:
        _validate_odds_execution_replay(
            evidence=validated_evidence,
            documents=documents,
            read_exact=read_exact,
        )
    return {
        "schema_version": "paid-source-ablation-terminal-reopen/v1",
        "terminal_envelope": {**envelope, "envelope_sha256": retained},
        "terminal": terminal,
        "panel_support": validated_panel,
        "slate_evidence": validated_evidence,
        "documents_by_name": documents,
        "complete": True,
        "outcome_data_accessed": False,
    }


__all__ = [
    "PaidSourceAblationOperatorV1Error",
    "READY_SCHEMA",
    "TERMINAL_ENVELOPE_SCHEMA",
    "TERMINAL_SCHEMA",
    "prepare_paid_source_bundle_v1",
    "publish_paid_source_bundle_v1",
    "reopen_paid_source_terminal_v1",
    "run_fp_sis_panel_to_ready_v1",
    "run_odds_panel_to_ready_v1",
    "validate_ready_bundle_v1",
]
