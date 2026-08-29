#!/usr/bin/env python3
"""Derive and grade the 42-cell hard-230 selector confirmation panel."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
import base64
import binascii
import gc
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge
from nfl_dfs.research import (
    corpus_r6_hard230_selector_confirmation_execution_v1 as execution,
)
from nfl_dfs.research import (
    corpus_r6_hard230_selector_confirmation_v1 as confirmation,
)
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as l2b_panel
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader
try:
    from scripts import run_corpus_r6_hard230_selector_bridge_v1 as bridge_operator
except ModuleNotFoundError:  # Direct or isolated ``python scripts/...`` execution.
    _scripts_dir = str(Path(__file__).resolve().parent)
    sys.path.insert(0, _scripts_dir)
    try:
        import run_corpus_r6_hard230_selector_bridge_v1 as bridge_operator
    finally:
        sys.path.remove(_scripts_dir)


MAXIMUM_REQUEST_BYTES = 128_000
MAXIMUM_BRIDGE_TERMINAL_BYTES = bridge_operator.MAXIMUM_TERMINAL_BYTES
MAXIMUM_CONFIRMATION_TERMINAL_BYTES = 60_000_000
MAXIMUM_GRADE_BYTES = 40_000_000
MAXIMUM_SMOKE_OUTPUT_BYTES = 2_000_000
GCS_IO_TIMEOUT_SECONDS = bridge_operator.GCS_IO_TIMEOUT_SECONDS
TASK0_SMOKE_SCHEMA = "corpus-r6-hard230-selector-confirmation-smoke/v1"


class RunCorpusR6Hard230SelectorConfirmationV1Error(RuntimeError):
    """The bounded hard-230 confirmation operator failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6Hard230SelectorConfirmationV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return grader.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str, maximum_bytes: int) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > maximum_bytes:
        _fail(f"{label} byte size differs")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(str(exc)) from exc


GCSExactTransportV1 = bridge_operator.GCSExactTransportV1


def _read_json(
    identity_value: object,
    *,
    store: object,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=label)
    raw = store.read_exact(identity)
    return _strict_json(raw, label=label, maximum_bytes=maximum_bytes), identity


def _publish_json(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    store: object,
) -> dict[str, object]:
    raw = _canonical(value)
    if len(raw) > maximum_bytes:
        _fail("published confirmation object exceeds its byte ceiling")
    identity = _identity(
        store.publish_create_once(uri, raw), label="published confirmation object"
    )
    if store.read_exact(identity) != raw:
        _fail("published confirmation object exact reopen differs")
    return identity


def _read_bridge_terminal(
    identity_value: object,
    *,
    store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    terminal, identity = _read_json(
        identity_value,
        store=store,
        label="hard230 selector bridge terminal",
        maximum_bytes=MAXIMUM_BRIDGE_TERMINAL_BYTES,
    )
    try:
        retained = bridge.validate_hard230_selector_terminal_v1(terminal)
    except bridge.CorpusR6Hard230SelectorBridgeV1Error as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(str(exc)) from exc
    if identity["uri"] != retained["terminal_uri"]:
        _fail("hard230 selector bridge terminal canonical URI differs")
    return retained, identity


def _read_build_authority_v1(
    identity_value: object,
    *,
    source_commit_sha: str,
    immutable_image_digest: str,
    store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        return l2b_panel._read_terminal_build_receipt(
            identity_value,
            source_commit_sha=source_commit_sha,
            immutable_image_digest=immutable_image_digest,
            read_exact=store.read_exact,
            label="hard230 confirmation terminal build receipt",
        )
    except Exception as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(
            "hard230 confirmation terminal build receipt replay failed"
        ) from exc


def _validate_task0_smoke_receipt_v1(value: object) -> dict[str, object]:
    receipt = _mapping(value, label="hard230 confirmation task0 smoke receipt")
    expected_fields = {
        "schema_version",
        "adapter_id",
        "bridge_terminal_identity",
        "bridge_terminal_sha256",
        "terminal_build_receipt_identity",
        "terminal_build_receipt_sha256",
        "source_commit_sha",
        "immutable_image_digest",
        "output_prefix",
        "source_ordinal",
        "slate_id",
        "confirmation_sha256",
        "book_count",
        "complete",
        "outcome_columns_read",
        "uses_realized_outcomes",
        "smoke_sha256",
    }
    source_commit = receipt.get("source_commit_sha")
    image_digest = receipt.get("immutable_image_digest")
    output_prefix = receipt.get("output_prefix")
    if (
        set(receipt) != expected_fields
        or receipt.get("smoke_sha256")
        != _hash({key: item for key, item in receipt.items() if key != "smoke_sha256"})
        or receipt.get("schema_version") != TASK0_SMOKE_SCHEMA
        or receipt.get("adapter_id") != confirmation.ADAPTER_ID
        or type(receipt.get("source_ordinal")) is not int
        or receipt.get("source_ordinal") != 0
        or receipt.get("book_count") != confirmation.BOOK_COUNT
        or receipt.get("complete") is not True
        or receipt.get("outcome_columns_read") != []
        or receipt.get("uses_realized_outcomes") is not False
        or type(source_commit) is not str
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
        or type(image_digest) is not str
        or not image_digest.startswith("sha256:")
        or len(image_digest) != 71
        or type(output_prefix) is not str
        or not output_prefix.endswith("/selector-confirmation-v1/")
    ):
        _fail("hard230 confirmation task0 smoke fixed law differs")
    for field in (
        "bridge_terminal_identity",
        "terminal_build_receipt_identity",
    ):
        _identity(receipt.get(field), label=f"hard230 confirmation smoke {field}")
    for field in (
        "bridge_terminal_sha256",
        "terminal_build_receipt_sha256",
        "confirmation_sha256",
        "smoke_sha256",
    ):
        digest = receipt.get(field)
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            _fail(f"hard230 confirmation smoke {field} differs")
    return receipt


def _read_task0_smoke_receipt_v1(
    identity_value: object,
    *,
    store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    body, identity = _read_json(
        identity_value,
        store=store,
        label="hard230 confirmation task0 smoke receipt",
        maximum_bytes=MAXIMUM_REQUEST_BYTES,
    )
    return _validate_task0_smoke_receipt_v1(body), identity


def _training_score_matrices_v1(
    *,
    bridge_slate: Mapping[str, object],
    player_registry: object,
    player_score_matrix_milli: np.ndarray,
) -> dict[str, np.ndarray]:
    try:
        player_ids = [
            str(_mapping(row, label="hard230 player registry row")["id"])
            for row in player_registry
        ]
    except (KeyError, TypeError) as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(
            "hard230 player registry differs"
        ) from exc
    matrices: dict[str, np.ndarray] = {}
    for population in bridge_slate["population_results"]:
        role = str(population["population_role"])
        matrix = bridge._lineup_score_matrix_dk(
            lineups=population["full_population_lineups"],
            sampled_ids=population["sampled_lineup_ids"],
            player_ids=player_ids,
            player_score_matrix_milli=player_score_matrix_milli,
        )
        matrices[role] = matrix
    if set(matrices) != {spec[0] for spec in bridge.POPULATION_SPECS}:
        _fail("hard230 confirmation training population registry differs")
    return matrices


def _derive_one_confirmation_v1(
    *,
    bridge_slate: Mapping[str, object],
    later_source_identity: Mapping[str, object],
    store: object,
) -> dict[str, object]:
    source_ordinal = int(bridge_slate["source_ordinal"])
    task_result, task_identity = bridge_operator._read_json(
        bridge_slate["task_result_identity"],
        store=store,
        label=f"hard230 task result[{source_ordinal}]",
        maximum_bytes=2_000_000,
    )
    prepared = bridge_operator._replay_source(
        task_result=task_result,
        later_source_identity=later_source_identity,
        store=store,
    )
    if task_identity != bridge_slate.get("task_result_identity"):
        _fail("hard230 confirmation task-result identity differs")
    matrices = _training_score_matrices_v1(
        bridge_slate=bridge_slate,
        player_registry=prepared.player_registry,
        player_score_matrix_milli=prepared.score_matrix,
    )
    try:
        result = confirmation.build_from_sealed_hard230_bridge_v1(
            bridge_slate=bridge_slate,
            training_score_matrices=matrices,
        )
    except (
        confirmation.CorpusR6Hard230SelectorConfirmationV1Error,
        bridge.CorpusR6Hard230SelectorBridgeV1Error,
    ) as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(str(exc)) from exc
    execution.validate_confirmation_slate_structure_v1(
        result, bridge_slate=bridge_slate
    )
    del matrices
    del prepared
    gc.collect()
    return result


def _replay_all_confirmation_results_v1(
    *,
    terminal: Mapping[str, object],
    bridge_terminal: Mapping[str, object],
    store: object,
) -> list[dict[str, object]]:
    persisted = terminal.get("slate_results")
    source_slates = bridge_terminal.get("slate_results")
    if (
        not isinstance(persisted, list)
        or not isinstance(source_slates, list)
        or len(persisted) != grader.SOURCE_SLATE_COUNT
        or len(source_slates) != grader.SOURCE_SLATE_COUNT
    ):
        _fail("hard230 confirmation exact-replay coverage differs")
    replayed: list[dict[str, object]] = []
    for ordinal, (value, bridge_slate) in enumerate(
        zip(persisted, source_slates, strict=True)
    ):
        expected = _derive_one_confirmation_v1(
            bridge_slate=bridge_slate,
            later_source_identity=bridge_terminal["later_source_identity"],
            store=store,
        )
        if _canonical(value) != _canonical(expected):
            _fail(
                f"hard230 confirmation result[{ordinal}] differs from exact replay"
            )
        replayed.append(expected)
    return replayed


def smoke_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    """Publish one exact outcome-blind task-0 reality receipt."""
    item = _mapping(request, label="hard230 confirmation smoke request")
    if set(item) != {
        "bridge_terminal_identity",
        "terminal_build_receipt_identity",
        "source_commit_sha",
        "immutable_image_digest",
        "output_prefix",
        "source_ordinal",
    }:
        _fail("hard230 confirmation smoke request fields differ")
    source_ordinal = item.get("source_ordinal")
    if type(source_ordinal) is not int or source_ordinal != 0:
        _fail("hard230 confirmation smoke source ordinal differs")
    terminal, terminal_identity = _read_bridge_terminal(
        item["bridge_terminal_identity"], store=store
    )
    output_prefix = execution.confirmation_output_prefix_v1(terminal)
    if item.get("output_prefix") != output_prefix:
        _fail("hard230 confirmation smoke output prefix differs")
    build, build_identity = _read_build_authority_v1(
        item["terminal_build_receipt_identity"],
        source_commit_sha=str(item["source_commit_sha"]),
        immutable_image_digest=str(item["immutable_image_digest"]),
        store=store,
    )
    result = _derive_one_confirmation_v1(
        bridge_slate=terminal["slate_results"][source_ordinal],
        later_source_identity=terminal["later_source_identity"],
        store=store,
    )
    body = {
        "schema_version": TASK0_SMOKE_SCHEMA,
        "adapter_id": confirmation.ADAPTER_ID,
        "bridge_terminal_identity": terminal_identity,
        "bridge_terminal_sha256": terminal["terminal_sha256"],
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": _hash(build),
        "source_commit_sha": str(item["source_commit_sha"]),
        "immutable_image_digest": str(item["immutable_image_digest"]),
        "output_prefix": output_prefix,
        "source_ordinal": source_ordinal,
        "slate_id": result["slate_id"],
        "confirmation_sha256": result["confirmation_sha256"],
        "book_count": result["book_count"],
        "complete": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    smoke = {**body, "smoke_sha256": _hash(body)}
    if len(_canonical(smoke)) > MAXIMUM_SMOKE_OUTPUT_BYTES:
        _fail("hard230 confirmation smoke output exceeds its byte ceiling")
    smoke_identity = _publish_json(
        uri=f"{output_prefix}task0-smoke/smoke-receipt.json",
        value=smoke,
        maximum_bytes=MAXIMUM_SMOKE_OUTPUT_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-hard230-selector-confirmation-smoke-cli/v1",
        "smoke_receipt_identity": smoke_identity,
        "smoke_sha256": smoke["smoke_sha256"],
        "confirmation_sha256": result["confirmation_sha256"],
        "book_count": confirmation.BOOK_COUNT,
        "complete": True,
    }


def _validate_smoke_authority_v1(
    *,
    smoke: Mapping[str, object],
    smoke_identity: Mapping[str, object],
    bridge_terminal: Mapping[str, object],
    bridge_terminal_identity: Mapping[str, object],
    build_identity: Mapping[str, object],
    build_sha256: str,
    source_commit_sha: str,
    immutable_image_digest: str,
    output_prefix: str,
) -> None:
    if (
        smoke_identity["uri"]
        != f"{output_prefix}task0-smoke/smoke-receipt.json"
        or smoke.get("bridge_terminal_identity") != bridge_terminal_identity
        or smoke.get("bridge_terminal_sha256")
        != bridge_terminal.get("terminal_sha256")
        or smoke.get("terminal_build_receipt_identity") != build_identity
        or smoke.get("terminal_build_receipt_sha256") != build_sha256
        or smoke.get("source_commit_sha") != source_commit_sha
        or smoke.get("immutable_image_digest") != immutable_image_digest
        or smoke.get("output_prefix") != output_prefix
        or smoke.get("slate_id")
        != bridge_terminal["slate_results"][0].get("slate_id")
    ):
        _fail("hard230 confirmation full54 lacks exact task0 smoke authority")


def derive_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="hard230 confirmation derive request")
    if set(item) != {
        "bridge_terminal_identity",
        "task0_smoke_receipt_identity",
        "terminal_build_receipt_identity",
        "source_commit_sha",
        "immutable_image_digest",
        "output_prefix",
    }:
        _fail("hard230 confirmation derive request fields differ")
    bridge_terminal, bridge_terminal_identity = _read_bridge_terminal(
        item["bridge_terminal_identity"], store=store
    )
    output_prefix = execution.confirmation_output_prefix_v1(bridge_terminal)
    if item.get("output_prefix") != output_prefix:
        _fail("hard230 confirmation output prefix differs")
    source_commit_sha = str(item["source_commit_sha"])
    immutable_image_digest = str(item["immutable_image_digest"])
    build, build_identity = _read_build_authority_v1(
        item["terminal_build_receipt_identity"],
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
        store=store,
    )
    build_sha256 = _hash(build)
    smoke, smoke_identity = _read_task0_smoke_receipt_v1(
        item["task0_smoke_receipt_identity"], store=store
    )
    _validate_smoke_authority_v1(
        smoke=smoke,
        smoke_identity=smoke_identity,
        bridge_terminal=bridge_terminal,
        bridge_terminal_identity=bridge_terminal_identity,
        build_identity=build_identity,
        build_sha256=build_sha256,
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
        output_prefix=output_prefix,
    )
    results: list[dict[str, object]] = []
    for bridge_slate in bridge_terminal["slate_results"]:
        results.append(
            _derive_one_confirmation_v1(
                bridge_slate=bridge_slate,
                later_source_identity=bridge_terminal["later_source_identity"],
                store=store,
            )
        )
    if smoke.get("confirmation_sha256") != results[0]["confirmation_sha256"]:
        _fail("hard230 confirmation full54 task0 replay differs from smoke")
    terminal = execution.build_confirmation_terminal_v1(
        bridge_terminal=bridge_terminal,
        bridge_terminal_identity=bridge_terminal_identity,
        task0_smoke_receipt_identity=smoke_identity,
        task0_smoke_receipt_sha256=str(smoke["smoke_sha256"]),
        terminal_build_receipt_identity=build_identity,
        terminal_build_receipt_sha256=build_sha256,
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
        output_prefix=output_prefix,
        slate_results=results,
    )
    terminal_identity = _publish_json(
        uri=terminal["terminal_uri"],
        value=terminal,
        maximum_bytes=MAXIMUM_CONFIRMATION_TERMINAL_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-hard230-selector-confirmation-cli-result/v1",
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "source_slate_count": grader.SOURCE_SLATE_COUNT,
        "book_count_per_slate": confirmation.BOOK_COUNT,
        "complete": True,
    }


def _validate_outcome_binding(
    *,
    terminal: Mapping[str, object],
    snapshot: Mapping[str, object],
    slate_keys: Mapping[int, tuple[int, int, str]],
) -> None:
    if (
        snapshot.get("later_source_freeze_identity")
        != terminal.get("later_source_identity")
        or set(slate_keys) != set(range(grader.SOURCE_SLATE_COUNT))
        or any(
            slate_keys[ordinal][2]
            != terminal["slate_results"][ordinal].get("slate_id")
            for ordinal in range(grader.SOURCE_SLATE_COUNT)
        )
    ):
        _fail("hard230 confirmation terminal/outcome binding differs")


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="hard230 confirmation grade request")
    if set(item) != {"terminal_identity", "outcome_snapshot_identity"}:
        _fail("hard230 confirmation grade request fields differ")
    terminal, terminal_identity = _read_json(
        item["terminal_identity"],
        store=store,
        label="hard230 confirmation terminal",
        maximum_bytes=MAXIMUM_CONFIRMATION_TERMINAL_BYTES,
    )
    try:
        envelope = execution.validate_terminal_envelope_v1(terminal)
    except execution.CorpusR6Hard230SelectorConfirmationExecutionV1Error as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(str(exc)) from exc
    if terminal_identity["uri"] != envelope["terminal_uri"]:
        _fail("hard230 confirmation terminal canonical URI differs")

    # Complete and validate every score-free predecessor before the first
    # outcome-snapshot read below.
    bridge_terminal, bridge_terminal_identity = _read_bridge_terminal(
        envelope["bridge_terminal_identity"], store=store
    )
    if (
        bridge_terminal_identity != envelope["bridge_terminal_identity"]
        or bridge_terminal["terminal_sha256"]
        != envelope["bridge_terminal_sha256"]
    ):
        _fail("hard230 confirmation bridge terminal binding differs")
    build, build_identity = _read_build_authority_v1(
        envelope["terminal_build_receipt_identity"],
        source_commit_sha=str(envelope["source_commit_sha"]),
        immutable_image_digest=str(envelope["immutable_image_digest"]),
        store=store,
    )
    if (
        build_identity != envelope["terminal_build_receipt_identity"]
        or _hash(build) != envelope["terminal_build_receipt_sha256"]
    ):
        _fail("hard230 confirmation terminal build authority differs")
    smoke, smoke_identity = _read_task0_smoke_receipt_v1(
        envelope["task0_smoke_receipt_identity"], store=store
    )
    if (
        smoke_identity != envelope["task0_smoke_receipt_identity"]
        or smoke["smoke_sha256"] != envelope["task0_smoke_receipt_sha256"]
    ):
        _fail("hard230 confirmation terminal smoke identity differs")
    _validate_smoke_authority_v1(
        smoke=smoke,
        smoke_identity=smoke_identity,
        bridge_terminal=bridge_terminal,
        bridge_terminal_identity=bridge_terminal_identity,
        build_identity=build_identity,
        build_sha256=_hash(build),
        source_commit_sha=str(envelope["source_commit_sha"]),
        immutable_image_digest=str(envelope["immutable_image_digest"]),
        output_prefix=str(envelope["output_prefix"]),
    )
    replayed = _replay_all_confirmation_results_v1(
        terminal=envelope,
        bridge_terminal=bridge_terminal,
        store=store,
    )
    if smoke["confirmation_sha256"] != replayed[0]["confirmation_sha256"]:
        _fail("hard230 confirmation terminal task0 smoke replay differs")
    try:
        normalized = execution.normalized_confirmation_terminal_v1(
            envelope, bridge_terminal=bridge_terminal
        )
    except execution.CorpusR6Hard230SelectorConfirmationExecutionV1Error as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(str(exc)) from exc
    validated = envelope

    snapshot, snapshot_identity, player_scores, slate_keys = (
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            read_outcome_exact=store.read_exact,
        )
    )
    _validate_outcome_binding(
        terminal=validated, snapshot=snapshot, slate_keys=slate_keys
    )
    slate_grades = grader.score_normalized_slates_v1(
        slates=normalized, player_scores=player_scores
    )
    aggregates = grader.aggregate_normalized_slate_grades_v1(slate_grades)
    body = {
        "schema_version": "corpus-r6-hard230-selector-confirmation-realized-grade/v1",
        "adapter_id": confirmation.ADAPTER_ID,
        "terminal_identity": terminal_identity,
        "terminal_sha256": validated["terminal_sha256"],
        "bridge_terminal_identity": bridge_terminal_identity,
        "bridge_terminal_sha256": bridge_terminal["terminal_sha256"],
        "task0_smoke_receipt_identity": smoke_identity,
        "task0_smoke_receipt_sha256": smoke["smoke_sha256"],
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": _hash(build),
        "source_commit_sha": validated["source_commit_sha"],
        "immutable_image_digest": validated["immutable_image_digest"],
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "later_source_identity": validated["later_source_identity"],
        "source_slate_count": grader.SOURCE_SLATE_COUNT,
        "slate_grades": slate_grades,
        "slate_grades_sha256": _hash(slate_grades),
        "aggregate_cells": aggregates,
        "aggregate_cells_sha256": _hash(aggregates),
        "all_score_free_predecessors_validated_before_outcome_open": True,
        "outcome_source_and_slate_identity_bound": True,
        "complete": True,
    }
    grade = {**body, "grade_sha256": _hash(body)}
    grade_identity = _publish_json(
        uri=f"{validated['output_prefix']}full-54/realized-grade.json",
        value=grade,
        maximum_bytes=MAXIMUM_GRADE_BYTES,
        store=store,
    )
    return {
        "schema_version": (
            "corpus-r6-hard230-selector-confirmation-grade-cli-result/v1"
        ),
        "grade_identity": grade_identity,
        "grade_sha256": grade["grade_sha256"],
        "aggregate_cell_count": len(aggregates),
        "complete": True,
    }


def _load_request(path: str) -> dict[str, object]:
    return _strict_json(
        Path(path).read_bytes(),
        label="hard230 confirmation request",
        maximum_bytes=MAXIMUM_REQUEST_BYTES,
    )


def _load_request_base64(value: str) -> dict[str, object]:
    if type(value) is not str or not value or len(value) > MAXIMUM_REQUEST_BYTES * 2:
        _fail("hard230 confirmation base64 request size differs")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise RunCorpusR6Hard230SelectorConfirmationV1Error(
            "hard230 confirmation base64 request differs"
        ) from exc
    return _strict_json(
        raw,
        label="hard230 confirmation request",
        maximum_bytes=MAXIMUM_REQUEST_BYTES,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("smoke", "derive", "grade"):
        child = subparsers.add_parser(command)
        request_group = child.add_mutually_exclusive_group(required=True)
        request_group.add_argument("--request")
        request_group.add_argument("--request-base64")
    args = parser.parse_args(argv)
    store = GCSExactTransportV1()
    request = (
        _load_request(args.request)
        if args.request is not None
        else _load_request_base64(args.request_base64)
    )
    if args.command == "smoke":
        result = smoke_from_request_v1(request, store=store)
    elif args.command == "derive":
        result = derive_from_request_v1(request, store=store)
    else:
        result = grade_from_request_v1(request, store=store)
    sys.stdout.buffer.write(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
