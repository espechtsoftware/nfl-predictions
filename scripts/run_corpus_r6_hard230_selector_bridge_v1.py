#!/usr/bin/env python3
"""Derive and grade selected books from a terminal hard-230 population root."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
import gc
from hashlib import sha256
import json
from pathlib import Path
import sys

from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_run_controller_v1 as controller,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_source_decoder_v1 as decoder,
)
from nfl_dfs.research import (
    corpus_r6_hard230_selector_bridge_v1 as bridge,
)
from nfl_dfs.research import (
    corpus_r6_novel_roster_realized_grader_v1 as grader,
)


MAXIMUM_REQUEST_BYTES = 128_000
MAXIMUM_TERMINAL_BYTES = 80_000_000
MAXIMUM_SLATE_RESULT_BYTES = 2_000_000
MAXIMUM_GRADE_BYTES = 30_000_000
GCS_IO_TIMEOUT_SECONDS = 900
TASK0_SMOKE_SCHEMA = "corpus-r6-hard230-selector-bridge-task0-smoke/v1"


class RunCorpusR6Hard230SelectorBridgeV1Error(RuntimeError):
    """The hard-230 selector bridge operator failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6Hard230SelectorBridgeV1Error(message)


def _canonical(value: object) -> bytes:
    return grader.canonical_json_bytes_v1(value)


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(
    value: Mapping[str, object], *, field: str
) -> dict[str, object]:
    result = dict(value)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _hash(result)
    return result


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
        raise RunCorpusR6Hard230SelectorBridgeV1Error(
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
        raise RunCorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc


def _selector_output_prefix(source_manifest: Mapping[str, object]) -> str:
    source_prefix = source_manifest.get("output_prefix")
    if (
        type(source_prefix) is not str
        or not source_prefix.startswith("gs://")
        or not source_prefix.endswith("/")
        or "//" in source_prefix[5:]
    ):
        _fail("hard230 source output prefix differs")
    return f"{source_prefix}selector-bridge/"


def _scope_output_uri(*, output_prefix: str, mode: str) -> str:
    if mode == "task0-smoke":
        return f"{output_prefix}task0-smoke/slate-result.json"
    if mode == "full-54":
        return f"{output_prefix}full-54/terminal.json"
    _fail("hard230 selector output scope differs")


def _grade_output_uri(*, terminal: Mapping[str, object]) -> str:
    prefix = terminal.get("output_prefix")
    terminal_uri = terminal.get("terminal_uri")
    if (
        type(prefix) is not str
        or type(terminal_uri) is not str
        or terminal_uri != _scope_output_uri(output_prefix=prefix, mode="full-54")
    ):
        _fail("hard230 selector terminal output topology differs")
    return f"{prefix}full-54/realized-grade.json"


class GCSExactTransportV1:
    """Generation-exact, no-listing transport with no large-object cache."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
            from google.cloud.storage.retry import DEFAULT_RETRY
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RunCorpusR6Hard230SelectorBridgeV1Error(
                "google-cloud-storage is required"
            ) from exc
        self._client = storage.Client(
            project=grader.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=grader.FIXED_STORAGE_ENDPOINT
            ),
        )
        # These terminal objects can approach 80 MB.  A single 60-second
        # socket timeout discarded an otherwise complete 54-slate derivation.
        # Generation preconditions make retrying these exact reads/creates
        # idempotent; retain a bounded retry window long enough for a slow
        # resumable transfer to finish.
        self._retry = DEFAULT_RETRY.with_timeout(GCS_IO_TIMEOUT_SECONDS)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if type(uri) is not str or not uri.startswith("gs://"):
            _fail("GCS URI must use gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name or "//" in name:
            _fail("GCS URI is malformed")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="GCS exact read")
        bucket_name, object_name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(
            if_generation_match=generation,
            timeout=GCS_IO_TIMEOUT_SECONDS,
            retry=self._retry,
        )
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-exact GCS bytes differ")
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                timeout=GCS_IO_TIMEOUT_SECONDS,
                retry=self._retry,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            current = self._client.bucket(bucket_name).blob(object_name)
            current.reload(
                timeout=GCS_IO_TIMEOUT_SECONDS,
                retry=self._retry,
            )
            if current.generation is None:
                _fail("create-once collision lacks an existing generation")
            identity = {
                "uri": uri,
                "generation": str(current.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once publication lacks a generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity


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
    *, uri: str, value: Mapping[str, object], maximum_bytes: int, store: object,
) -> dict[str, object]:
    raw = _canonical(value)
    if len(raw) > maximum_bytes:
        _fail("published bridge object exceeds its byte ceiling")
    identity = _identity(
        store.publish_create_once(uri, raw), label="published bridge object"
    )
    if store.read_exact(identity) != raw:
        _fail("published bridge object exact reopen differs")
    return identity


def _open_final_root(
    identity_value: object, *, store: object
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    root, root_identity = _read_json(
        identity_value,
        store=store,
        label="hard230 final root",
        maximum_bytes=controller.MAXIMUM_FINAL_ROOT_BYTES,
    )
    manifest, manifest_identity, source_manifest = (
        controller.open_controller_manifest_v1(
            controller_manifest_identity=root.get("controller_manifest_identity"),
            read_exact=store.read_exact,
        )
    )
    try:
        validated = controller.validate_final_root_v1(
            root,
            controller_manifest=manifest,
            controller_manifest_identity=manifest_identity,
        )
    except controller.Hard230R6RunControllerV1Error as exc:
        raise RunCorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc
    if (
        validated.get("complete") is not True
        or root_identity["uri"] != manifest.get("final_root_uri")
        or validated.get("source_task_manifest_identity")
        != manifest.get("source_task_manifest_identity")
    ):
        _fail("hard230 final root terminal URI/manifest binding differs")
    return validated, root_identity, source_manifest


def _replay_source(
    *, task_result: Mapping[str, object], later_source_identity: Mapping[str, object],
    store: object,
) -> decoder.PreparedHard230R6SourceV1:
    source_member_identity = _mapping(
        task_result.get("source_member_identity"), label="source member identity"
    )
    source_member_object = _identity(
        source_member_identity.get("object_identity"),
        label="source member object",
    )
    score_identity = _mapping(
        task_result.get("score_matrix_identity"), label="score matrix identity"
    )
    matrix_object = _identity(
        score_identity.get("artifact_identity"), label="matrix authority object"
    )
    proof_identity = _mapping(
        score_identity.get("derivation_proof_identity"),
        label="matrix derivation proof identity",
    )
    proof_object = _identity(
        proof_identity.get("proof_object_identity"), label="derivation proof object"
    )
    if not str(source_member_object["uri"]).endswith("/source-member.json"):
        _fail("source-member URI suffix differs")
    output_prefix = str(source_member_object["uri"])[: -len("/source-member.json")]
    expected_by_uri = {
        str(source_member_object["uri"]): source_member_object,
        str(matrix_object["uri"]): matrix_object,
        str(proof_object["uri"]): proof_object,
    }

    def reopen_published(uri: str, payload: bytes) -> Mapping[str, object]:
        expected = expected_by_uri.get(uri)
        if expected is None or store.read_exact(expected) != payload:
            _fail("decoder replay publication differs from frozen bytes")
        return expected

    try:
        prepared = decoder.materialize_hard230_r6_source_v1(
            later_source_freeze_identity=later_source_identity,
            slate_id=str(task_result["slate_id"]),
            heldout_block=None,
            output_prefix=output_prefix,
            read_exact=store.read_exact,
            publish_create_once=reopen_published,
        )
    except decoder.Hard230R6SourceDecoderV1Error as exc:
        raise RunCorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc
    if (
        prepared.source_member_identity != source_member_identity
        or prepared.score_matrix_identity != score_identity
    ):
        _fail("decoder read-only replay differs from task result")
    return prepared


def _derive_slate_results(
    *, root: Mapping[str, object], source_manifest: Mapping[str, object],
    store: object,
) -> list[dict[str, object]]:
    later_identity = _identity(
        source_manifest.get("later_source_freeze_identity"),
        label="hard230 later-source freeze",
    )
    results: list[dict[str, object]] = []
    for source_ordinal, raw_record in enumerate(root["task_records"]):
        record = _mapping(raw_record, label=f"hard230 task record[{source_ordinal}]")
        task_result, task_identity = _read_json(
            record["task_result_identity"],
            store=store,
            label=f"hard230 task result[{source_ordinal}]",
            maximum_bytes=2_000_000,
        )
        process_receipt, process_identity = _read_json(
            record["process_receipt_identity"],
            store=store,
            label=f"hard230 process receipt[{source_ordinal}]",
            maximum_bytes=hard_process_maximum_root_bytes(),
        )
        prepared = _replay_source(
            task_result=task_result,
            later_source_identity=later_identity,
            store=store,
        )
        result = bridge.run_hard230_selector_slate_v1(
            source_ordinal=source_ordinal,
            later_source_identity=later_identity,
            task_result_identity=task_identity,
            task_result=task_result,
            process_receipt_identity=process_identity,
            process_receipt=process_receipt,
            player_registry=prepared.player_registry,
            score_matrix=prepared.score_matrix,
            score_matrix_identity=prepared.score_matrix_identity,
        )
        if len(_canonical(result)) > MAXIMUM_SLATE_RESULT_BYTES:
            _fail("hard230 selector slate result exceeds its byte ceiling")
        results.append(result)
        del prepared
        gc.collect()
    return results


def _build_task0_smoke_receipt(
    *,
    output_prefix: str,
    hard230_task0_root: Mapping[str, object],
    hard230_task0_root_identity: Mapping[str, object],
    source_manifest: Mapping[str, object],
    slate_result: Mapping[str, object],
    slate_result_identity: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": TASK0_SMOKE_SCHEMA,
        "contract_id": bridge.CONTRACT_ID,
        "adapter_id": bridge.ADAPTER_ID,
        "execution_scope": controller.TASK0_SMOKE_SCOPE,
        "output_prefix": output_prefix,
        "hard230_task0_final_root_identity": _identity(
            hard230_task0_root_identity, label="smoke hard230 task0 root"
        ),
        "hard230_task0_final_root_sha256": hard230_task0_root[
            "final_root_sha256"
        ],
        "source_task_manifest_identity": hard230_task0_root[
            "source_task_manifest_identity"
        ],
        "source_task_manifest_sha256": hard230_task0_root[
            "source_task_manifest_sha256"
        ],
        "later_source_identity": _identity(
            source_manifest.get("later_source_freeze_identity"),
            label="smoke later source",
        ),
        "slate_result_identity": _identity(
            slate_result_identity, label="smoke slate result"
        ),
        "slate_result_sha256": slate_result["slate_result_sha256"],
        "source_slate_count": 1,
        "complete": True,
        "outcome_columns_read": [],
        **bridge._false_authorities(),
    }
    return _with_hash(body, field="smoke_receipt_sha256")


def _validate_task0_smoke_receipt(
    value: object,
) -> dict[str, object]:
    receipt = _mapping(value, label="hard230 selector task0 smoke receipt")
    expected_fields = {
        "schema_version", "contract_id", "adapter_id", "execution_scope",
        "output_prefix", "hard230_task0_final_root_identity",
        "hard230_task0_final_root_sha256", "source_task_manifest_identity",
        "source_task_manifest_sha256", "later_source_identity",
        "slate_result_identity", "slate_result_sha256", "source_slate_count",
        "complete", "outcome_columns_read", *bridge._FALSE_AUTHORITY_FIELDS,
        "smoke_receipt_sha256",
    }
    if (
        set(receipt) != expected_fields
        or receipt.get("smoke_receipt_sha256")
        != _hash({
            key: item for key, item in receipt.items()
            if key != "smoke_receipt_sha256"
        })
        or receipt.get("schema_version") != TASK0_SMOKE_SCHEMA
        or receipt.get("contract_id") != bridge.CONTRACT_ID
        or receipt.get("adapter_id") != bridge.ADAPTER_ID
        or receipt.get("execution_scope") != controller.TASK0_SMOKE_SCOPE
        or receipt.get("source_slate_count") != 1
        or receipt.get("complete") is not True
        or receipt.get("outcome_columns_read") != []
        or any(
            receipt.get(field) is not False
            for field in bridge._FALSE_AUTHORITY_FIELDS
        )
    ):
        _fail("hard230 selector task0 smoke fixed law differs")
    for field in (
        "hard230_task0_final_root_identity", "source_task_manifest_identity",
        "later_source_identity", "slate_result_identity",
    ):
        _identity(receipt.get(field), label=f"task0 smoke {field}")
    for field in (
        "hard230_task0_final_root_sha256", "source_task_manifest_sha256",
        "slate_result_sha256", "smoke_receipt_sha256",
    ):
        digest = receipt.get(field)
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            _fail(f"hard230 selector task0 smoke {field} differs")
    output_prefix = receipt.get("output_prefix")
    if (
        type(output_prefix) is not str
        or not output_prefix.startswith("gs://")
        or not output_prefix.endswith("/selector-bridge/")
        or "//" in output_prefix[5:]
    ):
        _fail("hard230 selector task0 smoke output prefix differs")
    if receipt.get("slate_result_identity", {}).get("uri") != _scope_output_uri(
        output_prefix=output_prefix,
        mode="task0-smoke",
    ):
        _fail("hard230 selector task0 smoke result URI differs")
    return receipt


def _replay_task0_smoke_authority(
    *, smoke_receipt_identity: object, store: object,
) -> tuple[dict[str, object], dict[str, object]]:
    receipt_value, retained_receipt_identity = _read_json(
        smoke_receipt_identity,
        store=store,
        label="hard230 selector task0 smoke receipt",
        maximum_bytes=MAXIMUM_REQUEST_BYTES,
    )
    receipt = _validate_task0_smoke_receipt(receipt_value)
    task0_root, task0_root_identity, source_manifest = _open_final_root(
        receipt["hard230_task0_final_root_identity"], store=store
    )
    if (
        task0_root.get("scope_id") != controller.TASK0_SMOKE_SCOPE
        or task0_root.get("scientific_task_count") != 1
        or task0_root_identity != receipt["hard230_task0_final_root_identity"]
        or task0_root.get("final_root_sha256")
        != receipt["hard230_task0_final_root_sha256"]
        or task0_root.get("source_task_manifest_identity")
        != receipt["source_task_manifest_identity"]
        or task0_root.get("source_task_manifest_sha256")
        != receipt["source_task_manifest_sha256"]
        or source_manifest.get("later_source_freeze_identity")
        != receipt["later_source_identity"]
        or _selector_output_prefix(source_manifest) != receipt["output_prefix"]
    ):
        _fail("hard230 selector task0 smoke source authority differs")
    replayed = _derive_slate_results(
        root=task0_root, source_manifest=source_manifest, store=store
    )
    if len(replayed) != 1:
        _fail("hard230 selector task0 smoke replay coverage differs")
    bridge.normalized_slate_for_grader_v1(replayed[0])
    persisted, persisted_identity = _read_json(
        receipt["slate_result_identity"],
        store=store,
        label="hard230 selector task0 slate result",
        maximum_bytes=MAXIMUM_SLATE_RESULT_BYTES,
    )
    if (
        persisted_identity != receipt["slate_result_identity"]
        or persisted.get("slate_result_sha256")
        != receipt["slate_result_sha256"]
        or _canonical(persisted) != _canonical(replayed[0])
    ):
        _fail("hard230 selector task0 smoke pure replay differs")
    return receipt, retained_receipt_identity


def hard_process_maximum_root_bytes() -> int:
    # Local import keeps the operator's public surface small while using the
    # exact upstream ceiling rather than a second magic number.
    from nfl_dfs.research import (
        corpus_extreme_tail_hard230_population_process_v1 as hard_process,
    )

    return int(hard_process.MAX_ROOT_BYTES)


def derive_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="hard230 selector derive request")
    if set(item) != {
        "mode", "hard230_final_root_identity", "task0_smoke_receipt_identity",
        "output_prefix",
    }:
        _fail("hard230 selector derive request fields differ")
    mode = item.get("mode")
    if mode not in {"task0-smoke", "full-54"}:
        _fail("hard230 selector derive mode differs")
    root, root_identity, source_manifest = _open_final_root(
        item["hard230_final_root_identity"], store=store
    )
    output_prefix = _selector_output_prefix(source_manifest)
    if item.get("output_prefix") != output_prefix:
        _fail("hard230 selector derive output prefix differs")
    expected_count = 1 if mode == "task0-smoke" else grader.SOURCE_SLATE_COUNT
    expected_scope = (
        controller.TASK0_SMOKE_SCOPE
        if mode == "task0-smoke"
        else controller.FULL_54_SCOPE
    )
    if (
        root.get("scope_id") != expected_scope
        or root.get("scientific_task_count") != expected_count
    ):
        _fail("hard230 selector derive root scope differs")
    smoke_receipt: dict[str, object] | None = None
    smoke_receipt_identity: dict[str, object] | None = None
    if mode == "task0-smoke":
        if item.get("task0_smoke_receipt_identity") is not None:
            _fail("hard230 selector task0 cannot consume a prior smoke")
    else:
        smoke_receipt, smoke_receipt_identity = _replay_task0_smoke_authority(
            smoke_receipt_identity=item.get("task0_smoke_receipt_identity"),
            store=store,
        )
        if (
            smoke_receipt["source_task_manifest_identity"]
            != root.get("source_task_manifest_identity")
            or smoke_receipt["source_task_manifest_sha256"]
            != root.get("source_task_manifest_sha256")
            or smoke_receipt["hard230_task0_final_root_identity"]
            != root.get("required_smoke_final_root_identity")
            or smoke_receipt["hard230_task0_final_root_sha256"]
            != root.get("required_smoke_final_root_sha256")
            or smoke_receipt["later_source_identity"]
            != source_manifest.get("later_source_freeze_identity")
            or smoke_receipt["output_prefix"] != output_prefix
        ):
            _fail("hard230 selector full54 lacks its exact task0 smoke authority")
    results = _derive_slate_results(
        root=root, source_manifest=source_manifest, store=store
    )
    if mode == "task0-smoke":
        result = results[0]
        bridge.normalized_slate_for_grader_v1(result)
        identity = _publish_json(
            uri=_scope_output_uri(output_prefix=output_prefix, mode=mode),
            value=result,
            maximum_bytes=MAXIMUM_SLATE_RESULT_BYTES,
            store=store,
        )
        smoke = _build_task0_smoke_receipt(
            output_prefix=output_prefix,
            hard230_task0_root=root,
            hard230_task0_root_identity=root_identity,
            source_manifest=source_manifest,
            slate_result=result,
            slate_result_identity=identity,
        )
        retained_smoke_identity = _publish_json(
            uri=f"{output_prefix}task0-smoke/smoke-receipt.json",
            value=smoke,
            maximum_bytes=MAXIMUM_REQUEST_BYTES,
            store=store,
        )
        return {
            "schema_version": "corpus-r6-hard230-selector-bridge-cli-result/v1",
            "mode": mode,
            "source_slate_count": 1,
            "slate_result_identity": identity,
            "slate_result_sha256": result["slate_result_sha256"],
            "task0_smoke_receipt_identity": retained_smoke_identity,
            "task0_smoke_receipt_sha256": smoke["smoke_receipt_sha256"],
            "complete": True,
        }
    if smoke_receipt is None or smoke_receipt_identity is None:
        _fail("hard230 selector full54 smoke authority is absent")
    terminal = bridge.build_hard230_selector_terminal_v1(
        hard230_final_root_identity=root_identity,
        hard230_final_root_sha256=str(root["final_root_sha256"]),
        hard230_source_task_manifest_identity=root[
            "source_task_manifest_identity"
        ],
        hard230_source_task_manifest_sha256=str(
            root["source_task_manifest_sha256"]
        ),
        task0_smoke_receipt_identity=smoke_receipt_identity,
        task0_smoke_receipt_sha256=str(
            smoke_receipt["smoke_receipt_sha256"]
        ),
        later_source_identity=source_manifest["later_source_freeze_identity"],
        output_prefix=output_prefix,
        slate_results=results,
    )
    terminal_identity = _publish_json(
        uri=_scope_output_uri(output_prefix=output_prefix, mode=mode),
        value=terminal,
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-hard230-selector-bridge-cli-result/v1",
        "mode": mode,
        "source_slate_count": grader.SOURCE_SLATE_COUNT,
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "complete": True,
    }


def _validate_outcome_terminal_binding(
    *,
    terminal: Mapping[str, object],
    snapshot: Mapping[str, object],
    slate_keys: Mapping[int, tuple[int, int, str]],
) -> None:
    slate_results = [
        _mapping(row, label=f"hard230 terminal slate[{ordinal}]")
        for ordinal, row in enumerate(terminal.get("slate_results", []))
    ]
    if (
        snapshot.get("later_source_freeze_identity")
        != terminal.get("later_source_identity")
        or len(slate_results) != grader.SOURCE_SLATE_COUNT
        or set(slate_keys) != set(range(grader.SOURCE_SLATE_COUNT))
        or any(
            slate_keys[ordinal][2] != slate_results[ordinal].get("slate_id")
            for ordinal in range(grader.SOURCE_SLATE_COUNT)
        )
    ):
        _fail("hard230 selector terminal/outcome source or slate binding differs")


def grade_from_request_v1(request: object, *, store: object) -> dict[str, object]:
    item = _mapping(request, label="hard230 selector grade request")
    if set(item) != {"terminal_identity", "outcome_snapshot_identity"}:
        _fail("hard230 selector grade request fields differ")
    terminal, terminal_identity = _read_json(
        item["terminal_identity"],
        store=store,
        label="hard230 selector terminal",
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
    )
    validated = bridge.validate_hard230_selector_terminal_v1(terminal)
    if terminal_identity["uri"] != validated["terminal_uri"]:
        _fail("hard230 selector terminal canonical URI differs")

    # The create-last terminal was produced only after exact replay of all 54
    # score-free predecessors.  Reopen and bind its immutable source authority
    # here, but do not recompute the same selector lattice a second time before
    # grading.  Terminal validation above checks every nested self-hash,
    # coordinate, prefix, and complete 54-slate surface; the checks below bind
    # that surface back to the exact final root and task-0 smoke authority.
    root, root_identity, source_manifest = _open_final_root(
        validated["hard230_final_root_identity"], store=store
    )
    if (
        root_identity != validated["hard230_final_root_identity"]
        or root.get("final_root_sha256")
        != validated["hard230_final_root_sha256"]
        or root.get("scope_id") != controller.FULL_54_SCOPE
        or root.get("scientific_task_count") != grader.SOURCE_SLATE_COUNT
        or root.get("source_task_manifest_identity")
        != validated["hard230_source_task_manifest_identity"]
        or root.get("source_task_manifest_sha256")
        != validated["hard230_source_task_manifest_sha256"]
        or source_manifest.get("later_source_freeze_identity")
        != validated["later_source_identity"]
        or _selector_output_prefix(source_manifest) != validated["output_prefix"]
    ):
        _fail("hard230 selector terminal/full54 source authority differs")
    smoke_receipt, smoke_receipt_identity = _replay_task0_smoke_authority(
        smoke_receipt_identity=validated["task0_smoke_receipt_identity"],
        store=store,
    )
    if (
        smoke_receipt_identity != validated["task0_smoke_receipt_identity"]
        or smoke_receipt.get("smoke_receipt_sha256")
        != validated["task0_smoke_receipt_sha256"]
        or smoke_receipt.get("source_task_manifest_identity")
        != root.get("source_task_manifest_identity")
        or smoke_receipt.get("source_task_manifest_sha256")
        != root.get("source_task_manifest_sha256")
        or smoke_receipt.get("hard230_task0_final_root_identity")
        != root.get("required_smoke_final_root_identity")
        or smoke_receipt.get("hard230_task0_final_root_sha256")
        != root.get("required_smoke_final_root_sha256")
    ):
        _fail("hard230 selector terminal task0 smoke authority differs")
    normalized = bridge.normalized_terminal_for_grader_v1(validated)
    snapshot, snapshot_identity, player_scores, slate_keys = (
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=item["outcome_snapshot_identity"],
            read_outcome_exact=store.read_exact,
        )
    )
    _validate_outcome_terminal_binding(
        terminal=validated, snapshot=snapshot, slate_keys=slate_keys
    )
    slate_grades = grader.score_normalized_slates_v1(
        slates=normalized, player_scores=player_scores
    )
    aggregates = grader.aggregate_normalized_slate_grades_v1(slate_grades)
    body = {
        "schema_version": "corpus-r6-hard230-selector-bridge-realized-grade/v1",
        "adapter_id": bridge.ADAPTER_ID,
        "terminal_identity": terminal_identity,
        "terminal_sha256": validated["terminal_sha256"],
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "later_source_identity": validated["later_source_identity"],
        "source_slate_count": grader.SOURCE_SLATE_COUNT,
        "slate_grades": slate_grades,
        "slate_grades_sha256": _hash(slate_grades),
        "aggregate_cells": aggregates,
        "aggregate_cells_sha256": _hash(aggregates),
        "all_score_free_predecessors_replayed_before_outcome_open": True,
        "outcome_source_and_slate_identity_bound": True,
        "complete": True,
    }
    grade = {**body, "grade_sha256": _hash(body)}
    grade_identity = _publish_json(
        uri=_grade_output_uri(terminal=validated),
        value=grade,
        maximum_bytes=MAXIMUM_GRADE_BYTES,
        store=store,
    )
    return {
        "schema_version": "corpus-r6-hard230-selector-bridge-grade-cli-result/v1",
        "grade_identity": grade_identity,
        "grade_sha256": grade["grade_sha256"],
        "aggregate_cell_count": len(aggregates),
        "complete": True,
    }


def _load_request(path: str) -> dict[str, object]:
    raw = Path(path).read_bytes()
    return _strict_json(
        raw, label="hard230 selector request", maximum_bytes=MAXIMUM_REQUEST_BYTES
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("derive", "grade"):
        child = subparsers.add_parser(command)
        child.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    store = GCSExactTransportV1()
    request = _load_request(args.request)
    result = (
        derive_from_request_v1(request, store=store)
        if args.command == "derive"
        else grade_from_request_v1(request, store=store)
    )
    sys.stdout.buffer.write(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
