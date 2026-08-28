#!/usr/bin/env python3
"""Four-block read broker and selector-free five-fold assembler entrypoint."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any, Final

from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_selection_assembler_v1 as assembler
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest


STDIN_REQUEST_BYTE_CEILING: Final = 16_000_000
ASSEMBLER_STDOUT_BYTE_CEILING: Final = 4_000_000
ASSEMBLER_STDOUT_SPOOL_MEMORY_BYTES: Final = 64_000
DISPATCHER_RSS_BUDGET_BYTES: Final = 512 * 1024 * 1024
# The dispatcher captures into a bytearray and then materializes terminal
# bytes.  Reserve another 32 raw-output equivalents for strict JSON decode,
# schema validation, and Python container overhead.  This is deliberately
# conservative for the fixed-field assembler envelope.
ASSEMBLER_STDOUT_DUPLICATE_CAPTURE_BYTES: Final = (
    2 * ASSEMBLER_STDOUT_BYTE_CEILING + 1
)
ASSEMBLER_STDOUT_JSON_VALIDATION_RESERVE_BYTES: Final = (
    32 * ASSEMBLER_STDOUT_BYTE_CEILING
)
ASSEMBLER_STDOUT_DERIVED_WORST_CASE_RSS_BYTES: Final = (
    ASSEMBLER_STDOUT_SPOOL_MEMORY_BYTES
    + ASSEMBLER_STDOUT_DUPLICATE_CAPTURE_BYTES
    + ASSEMBLER_STDOUT_JSON_VALIDATION_RESERVE_BYTES
)
# The controller's terminal proof may retain at most one exact publication
# body at a time.  These terms make the 512 MiB selection-task boundary
# reproducible; a transport that creates a second full publication copy does
# not satisfy this accounting law.
DISPATCHER_PREOUTPUT_RSS_CEILING_BYTES: Final = 256 * 1024 * 1024
DISPATCHER_SELECTION_RECEIPT_SINGLE_COPY_BYTES: Final = max(
    contract.BROAD_SELECTION_RECEIPT_MAX_BYTES,
    contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES,
)
DISPATCHER_CHILD_STDERR_DUPLICATE_CAPTURE_BYTES: Final = (
    2 * task_manifest.MAXIMUM_CHILD_STDERR_BYTES + 1
)
DISPATCHER_TERMINAL_EVIDENCE_DUPLICATE_BYTES: Final = (
    2 * task_manifest.MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES + 1
)
DISPATCHER_EXACT_READ_CHUNK_BYTES: Final = 64 * 1024
DISPATCHER_TRANSIENT_RESERVE_BYTES: Final = 64 * 1024 * 1024
DISPATCHER_SELECTION_TERMINAL_WORST_CASE_RSS_BYTES: Final = (
    DISPATCHER_PREOUTPUT_RSS_CEILING_BYTES
    + DISPATCHER_SELECTION_RECEIPT_SINGLE_COPY_BYTES
    + ASSEMBLER_STDOUT_DUPLICATE_CAPTURE_BYTES
    + DISPATCHER_CHILD_STDERR_DUPLICATE_CAPTURE_BYTES
    + DISPATCHER_TERMINAL_EVIDENCE_DUPLICATE_BYTES
    + DISPATCHER_EXACT_READ_CHUNK_BYTES
    + DISPATCHER_TRANSIENT_RESERVE_BYTES
)
MAXIMUM_PROCESS_COMMAND_BYTES: Final = 4_096


class SelectionExecutionV1Error(ValueError):
    """The broker/assembler executable boundary failed closed."""


def _fail(message: str) -> None:
    raise SelectionExecutionV1Error(message)


def observed_process_command_v1(
    *, mode: str, raw_cmdline: bytes | None = None,
) -> list[str]:
    """Return only the bounded kernel-observed canonical process command."""
    try:
        if raw_cmdline is None:
            with Path("/proc/self/cmdline").open("rb") as command_stream:
                raw = command_stream.read(MAXIMUM_PROCESS_COMMAND_BYTES + 1)
                trailing = command_stream.read(1)
            if len(raw) > MAXIMUM_PROCESS_COMMAND_BYTES or trailing:
                _fail("kernel process command exceeds byte ceiling")
        else:
            raw = raw_cmdline
    except OSError as exc:
        raise SelectionExecutionV1Error(
            "kernel process command is unavailable"
        ) from exc
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > MAXIMUM_PROCESS_COMMAND_BYTES
        or not raw.endswith(b"\0")
    ):
        _fail("kernel process command differs")
    encoded = raw[:-1].split(b"\0")
    if len(encoded) != 3 or any(not field for field in encoded):
        _fail("kernel process command shape differs")
    try:
        observed = [field.decode("utf-8", errors="strict") for field in encoded]
    except UnicodeDecodeError as exc:
        raise SelectionExecutionV1Error(
            "kernel process command is not UTF-8"
        ) from exc
    retained = [
        str(Path(observed[0]).resolve()),
        str(Path(observed[1]).resolve()),
        observed[2],
    ]
    expected = (
        assembler.canonical_fold_broker_command_v1()
        if mode == "fold-broker"
        else assembler.canonical_slate_assembler_command_v1()
        if mode == "slate-assembler"
        else None
    )
    if expected is None or retained != expected:
        _fail("kernel process command is not the canonical selection entrypoint")
    return retained


def bind_task_evidence_to_assembler_envelope_v1(
    envelope_value: Mapping[str, object],
    binding_evidence_value: Mapping[str, object],
    *,
    request: Mapping[str, object],
    raw_request: bytes,
) -> dict[str, object]:
    """Self-hash the exact controller task binding into one slate envelope."""
    envelope = dict(envelope_value)
    if "task_binding_evidence" in envelope:
        _fail("assembler envelope already contains task binding evidence")
    prior_hash = envelope.pop("assembler_envelope_sha256", None)
    if (
        type(prior_hash) is not str
        or prior_hash != contract.canonical_sha256_v1(envelope)
    ):
        _fail("unbound assembler envelope self-hash differs")
    evidence = dict(binding_evidence_value)
    expected_evidence_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "task_manifest_sha256", "layer_id", "phase", "process_role",
        "task_index", "source_ordinal", "process_ordinal",
        "task_binding_sha256", "request_sha256", "request_bytes",
        "expected_outputs_sha256", "child_command_sha256",
        "manifest_generation_exact_reopen_required",
        "caller_request_or_command_accepted", "policy",
        "child_task_binding_evidence_sha256",
    }
    request_sha256 = sha256(raw_request).hexdigest()
    expected_role = (
        "broad-slate-assembler"
        if request.get("phase") == contract.BROAD_SCREEN_PHASE
        else "confirmation-slate-assembler"
    )
    expected_layer = (
        "broad-selection-receipt"
        if request.get("phase") == contract.BROAD_SCREEN_PHASE
        else "confirmation-selection-receipt"
    )
    hash_fields = (
        "task_manifest_sha256", "task_binding_sha256", "request_sha256",
        "expected_outputs_sha256", "child_command_sha256",
        "child_task_binding_evidence_sha256",
    )
    if (
        set(evidence) != expected_evidence_fields
        or evidence.get("child_task_binding_evidence_sha256")
        != contract.canonical_sha256_v1({
            key: value for key, value in evidence.items()
            if key != "child_task_binding_evidence_sha256"
        })
        or evidence.get("schema_version")
        != task_manifest.CHILD_TASK_BINDING_EVIDENCE_SCHEMA
        or evidence.get("contract_id") != contract.CONTRACT_ID
        or any(
            type(evidence.get(field)) is not str
            or len(str(evidence.get(field))) != 64
            or any(character not in "0123456789abcdef"
                   for character in str(evidence.get(field)))
            for field in hash_fields
        )
        or contract._safe_object_identity(
            evidence.get("manifest_identity"),
            label="assembler binding manifest identity",
        ) != evidence.get("manifest_identity")
        or evidence.get("layer_id") != expected_layer
        or evidence.get("request_sha256") != request_sha256
        or evidence.get("request_bytes") != len(raw_request)
        or envelope.get("assembler_request_sha256")
        != request.get("assembler_request_sha256")
        or evidence.get("phase") != request.get("phase")
        or evidence.get("process_role") != expected_role
        or evidence.get("task_index") != request.get("source_ordinal")
        or evidence.get("source_ordinal") != request.get("source_ordinal")
        or evidence.get("process_ordinal") != request.get("source_ordinal")
        or evidence.get("manifest_generation_exact_reopen_required") is not True
        or evidence.get("caller_request_or_command_accepted") is not False
        or evidence.get("policy") != contract.POLICY_CLAIMS
        or envelope.get("phase") != request.get("phase")
        or envelope.get("source_ordinal") != request.get("source_ordinal")
    ):
        _fail("assembler task binding evidence differs from its result envelope")
    envelope["task_binding_evidence"] = evidence
    envelope["assembler_envelope_sha256"] = contract.canonical_sha256_v1(
        envelope
    )
    return envelope


def reopen_controller_task_after_client_v1(
    *,
    parsed_binding: Mapping[str, object],
    environ: Mapping[str, str],
    raw_request: bytes,
    observed_command: list[str],
    read_exact: Callable[[Mapping[str, object]], bytes],
    expected_process_role: str,
    expected_phase: str,
    expected_source_ordinal: int,
    expected_process_ordinal: int,
) -> dict[str, object]:
    """Validate the selected task before any non-manifest authority read."""
    manifest_identity = contract._safe_object_identity(
        parsed_binding.get("manifest_identity"),
        label="controller selection task manifest identity",
    )
    if int(manifest_identity["bytes"]) > task_manifest.MAXIMUM_MANIFEST_BYTES:
        _fail("controller selection task manifest exceeds byte ceiling")
    manifest_raw = read_exact(manifest_identity)
    manifest = task_manifest.strict_json_v1(
        manifest_raw, label="controller selection task manifest"
    )
    immediate = task_manifest.validate_child_task_binding_v1(
        manifest,
        manifest_identity=manifest_identity,
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        expected_process_role=expected_process_role,
        expected_phase=expected_phase,
        expected_source_ordinal=expected_source_ordinal,
        expected_process_ordinal=expected_process_ordinal,
    )
    cached_manifest_replays = 0

    def read_with_manifest_cache(identity_value: Mapping[str, object]) -> bytes:
        nonlocal cached_manifest_replays
        retained = contract._safe_object_identity(
            identity_value, label="controller selection authority identity"
        )
        if retained == manifest_identity:
            cached_manifest_replays += 1
            if cached_manifest_replays != 1:
                _fail("controller task manifest cache replay count differs")
            return manifest_raw
        return read_exact(retained)

    replayed = task_manifest.reopen_child_task_binding_v1(
        environ=environ,
        raw_request=raw_request,
        observed_command=observed_command,
        read_exact=read_with_manifest_cache,
        expected_process_role=expected_process_role,
        expected_phase=expected_phase,
        expected_source_ordinal=expected_source_ordinal,
        expected_process_ordinal=expected_process_ordinal,
    )
    if (
        cached_manifest_replays != 1
        or contract.canonical_json_bytes_v1(replayed)
        != contract.canonical_json_bytes_v1(immediate)
    ):
        _fail("controller task binding authority replay differs")
    return immediate


class GCSExactCreateOnceTransportV1:
    """Fixed-project, fixed-endpoint generation reads and create-once writes."""

    def __init__(self, *, validated_environment: Mapping[str, object]) -> None:
        if (
            validated_environment.get("project_id") != assembler.FIXED_GCP_PROJECT
            or validated_environment.get("storage_endpoint")
            != "https://storage.googleapis.com"
            or validated_environment.get("redirect_environment_present") is not False
        ):
            _fail("GCS client construction lacks validated fixed environment")
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud-only dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=assembler.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint="https://storage.googleapis.com"
            ),
        )

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("object URI must be gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name:
            _fail("object URI is malformed")
        return bucket, name

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        retained = contract._safe_object_identity(identity, label="GCS exact read")
        bucket_name, object_name = self._parts(str(retained["uri"]))
        generation = int(str(retained["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(
            if_generation_match=generation, retry=None
        )
        if (
            not isinstance(raw, bytes)
            or len(raw) != retained["bytes"]
            or sha256(raw).hexdigest() != retained["sha256"]
        ):
            _fail("generation-pinned GCS body differs from exact identity")
        return raw

    def publish_create_once(
        self, uri: str, raw: bytes,
        prior_identity: Mapping[str, object] | None,
    ) -> dict[str, object]:
        if not isinstance(raw, bytes):
            _fail("publication body must be bytes")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            if prior_identity is None:
                _fail("selection receipt collision lacks exact prior authority")
            prior = contract._safe_object_identity(
                prior_identity, label="prior selection receipt authority"
            )
            if (
                prior["uri"] != uri
                or prior["bytes"] != len(raw)
                or prior["sha256"] != sha256(raw).hexdigest()
                or self.read_exact(prior) != raw
            ):
                _fail("selection receipt collision differs from exact prior")
            return prior
        if blob.generation is None:
            _fail("create-once upload did not return its generation")
        created = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(created) != raw:
            _fail("selection receipt exact reopen differs after create")
        return created


@dataclass(slots=True)
class _ExactFourBlockBodyBrokerV1:
    allowed_by_role: Mapping[str, Mapping[str, object]]
    read_exact: assembler.ReadExact
    starting_ordinal: int
    _observed: list[dict[str, object]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.allowed_by_role = {
            str(role): assembler._identity(identity, label=f"{role} identity")
            for role, identity in self.allowed_by_role.items()
        }
        if (
            list(self.allowed_by_role)[0:1] != ["later-source"]
            or len(self.allowed_by_role) != 5
            or len({value["uri"] for value in self.allowed_by_role.values()}) != 5
        ):
            _fail("four-block broker allowlist differs")
        self._observed = []

    def read(self, role: str, identity_value: object) -> bytes:
        if role not in self.allowed_by_role:
            _fail(f"raw body role {role!r} is not addressable")
        identity = assembler._identity(identity_value, label=f"{role} identity")
        if identity != self.allowed_by_role[role]:
            _fail(f"raw body identity for {role!r} differs")
        if any(row["role"] == role for row in self._observed):
            _fail(f"raw body role {role!r} repeats")
        raw, retained = assembler._read_identity_bytes(
            identity, read_exact=self.read_exact, label=role
        )
        self._observed.append(assembler._read_row(
            ordinal=self.starting_ordinal + len(self._observed),
            channel="process-budget",
            role=role,
            identity=retained,
        ))
        return raw

    @property
    def ledger(self) -> list[dict[str, object]]:
        if [row["role"] for row in self._observed] != list(self.allowed_by_role):
            _fail("four-block broker read ledger is incomplete or reordered")
        return [dict(row) for row in self._observed]


def _validate_later_source(value: Mapping[str, object]) -> dict[str, object]:
    from nfl_dfs.research import lr8_later_period_source as later

    expected = value.get("freeze_sha256")
    if not isinstance(expected, str):
        _fail("later source lacks frozen SHA-256")
    return later.validate_source_freeze(value, expected_freeze_sha256=expected)


def _players(values: object) -> tuple[object, ...]:
    from nfl_dfs.research import residual_world_columns as worlds

    if not isinstance(values, list) or not values:
        _fail("later-source catalog differs")
    rows = tuple(worlds.PlayerSpec.from_mapping(value) for value in values)
    if tuple(player.player_id for player in rows) != tuple(
        sorted(player.player_id for player in rows)
    ):
        _fail("later-source catalog order differs")
    return rows


def _artifact_identity(receipt_value: object) -> dict[str, object]:
    row = assembler._mapping(receipt_value, label="artifact receipt")
    return assembler._identity({
        "uri": row.get("uri"),
        "generation": row.get("generation"),
        "sha256": row.get("sha256"),
        "bytes": row.get("bytes"),
    }, label="artifact receipt identity")


def _bounded_subprocess(
    *, command: list[str], input_bytes: bytes, output_ceiling: int,
    environment: Mapping[str, str],
) -> bytes:
    if output_ceiling < 1:
        _fail("subprocess output ceiling differs")
    with tempfile.TemporaryFile() as stdin_file:
        stdin_file.write(input_bytes)
        stdin_file.seek(0)
        process = subprocess.Popen(
            command,
            stdin=stdin_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=dict(environment),
        )
        assert process.stdout is not None
        output = process.stdout.read(output_ceiling + 1)
        if len(output) > output_ceiling:
            process.kill()
            process.wait()
            _fail("subprocess stdout exceeded precharged byte ceiling")
        return_code = process.wait()
    if return_code != 0:
        _fail(f"subprocess exited {return_code}")
    return output


def _spawn_matrix_official(
    capability: Mapping[str, object], *, process_ordinal: int,
) -> tuple[dict[str, object], int]:
    from nfl_dfs.research import (
        corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1
        as matrix_worker,
    )

    raw = contract.canonical_json_bytes_v1(capability)
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("R6_TASK_")
    }
    environment["R6_SELECTOR_PROCESS_ORDINAL"] = str(process_ordinal)
    output = _bounded_subprocess(
        command=assembler.canonical_matrix_selector_command_v1(),
        input_bytes=raw,
        output_ceiling=matrix_worker.MATRIX_RESPONSE_BYTE_CEILING,
        environment=environment,
    )
    return assembler._strict_json(output, label="matrix-selector stdout"), len(output)


def _run_fold_broker_core_v1(
    request_value: object,
    *,
    broker_runtime_evidence: object,
    read_exact: assembler.ReadExact,
    validate_later_source: Callable[[Mapping[str, object]], Mapping[str, object]],
    players_from_catalog: Callable[[object], tuple[object, ...]],
    load_artifact_worlds: Callable[[Mapping[str, object], bytes], Any],
    cross_score: Callable[..., object],
    score_matrix_sha256: Callable[[object], str],
    spawn_matrix: Callable[[Mapping[str, object], int], tuple[Mapping[str, object], int]],
) -> dict[str, object]:
    import numpy as np
    from nfl_dfs.research import (
        corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1
        as matrix_worker,
    )

    request = assembler.validate_fold_worker_request_v1(request_value)
    broker_runtime = assembler.validate_observed_runtime_evidence_v1(
        broker_runtime_evidence
    )
    if (
        broker_runtime["mode"] != "fold-broker"
        or broker_runtime["process_ordinal"] != request["process_ordinal"]
    ):
        _fail("fold broker observed runtime differs")
    (
        design, topology, bundle, _nomination_publication, nomination,
        embedded_broad_authority, ledger,
    ) = assembler._reopen_common_authorities(request, read_exact=read_exact)
    bootstrap_manifest = assembler._mapping(
        design.get("bootstrap_manifest"), label="design bootstrap manifest"
    )
    bootstrap_manifest_identity = assembler._identity(
        design.get("bootstrap_manifest_identity"),
        label="design bootstrap manifest identity",
    )
    fold = int(request["fold_ordinal"])
    projection = bundle["fold_projections"][fold]
    internal = dict(request)
    internal["_reopened_nomination_publication"] = (
        _nomination_publication
    )
    internal["_reopened_nomination"] = nomination
    internal["_embedded_broad_phase_authority"] = embedded_broad_authority
    role = (
        "broad-fold-selector"
        if request["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-fold-selector"
    )
    bootstrap_process_chain = assembler._bootstrap_process_chain_v1(
        bootstrap_manifest, process_role=role
    )
    if (
        bootstrap_process_chain != assembler.canonical_fold_process_chain_v1()
        or broker_runtime["code_commit"] != bootstrap_manifest["code_commit"]
        or broker_runtime["image_digest"] != bootstrap_manifest["image_digest"]
    ):
        _fail("fold broker runtime differs from exact bootstrap manifest")
    expected_budget = assembler._compile_budget(
        role=role, request=internal, topology=topology, bundle=bundle,
        fold_ordinal=fold,
    )
    budget, budget_identity = assembler._exact_budget(
        identity=request["process_budget_identity"], expected=expected_budget,
        read_exact=read_exact, label="fold process budget",
    )
    ledger.append(assembler._read_row(
        ordinal=len(ledger), channel="bootstrap-authority",
        role="process-budget", identity=budget_identity,
    ))
    budget_reads = {
        str(row["role"]): row["identity"] for row in budget["read_allowlist"]
    }
    training_roles = [
        f"training-world-{block}" for block in projection["training_blocks"]
    ]
    heldout_role = f"training-world-{projection['heldout_block']}"
    allowed = {
        "later-source": budget_reads["later-source"],
        **{role_name: budget_reads[role_name] for role_name in training_roles},
    }
    if heldout_role in allowed:
        _fail("held-out fifth block entered broker capability")
    broker = _ExactFourBlockBodyBrokerV1(
        allowed_by_role=allowed, read_exact=read_exact,
        starting_ordinal=len(ledger),
    )
    source_raw = broker.read("later-source", projection["later_source_identity"])
    source_json = assembler._strict_json(source_raw, label="later-source")
    assembler._bind(source_json, projection["later_source_identity"], label="later-source")
    source = dict(validate_later_source(source_json))
    matches = [
        row for row in source.get("slates", [])
        if isinstance(row, Mapping) and row.get("slate_id") == projection["slate_id"]
    ]
    if len(matches) != 1:
        _fail("projection slate is absent or repeated in later source")
    slate = dict(matches[0])
    players = players_from_catalog(slate.get("catalog"))
    player_ids = tuple(player.player_id for player in players)
    receipts_raw = slate.get("artifact_receipts")
    if not isinstance(receipts_raw, list) or len(receipts_raw) != 5:
        _fail("source artifact receipt lattice differs")
    receipts = {str(row["block"]): dict(row) for row in receipts_raw}
    if list(receipts) != list(contract.WORLD_BLOCKS):
        _fail("source artifact receipt order differs")
    for block in contract.WORLD_BLOCKS:
        if _artifact_identity(receipts[block]) != projection["world_artifact_identities"][f"world_artifact_{block.lower()}"]:
            _fail("source/projection artifact identity differs")
    aligned = []
    for block in projection["training_blocks"]:
        receipt = receipts[block]
        raw = broker.read(f"training-world-{block}", _artifact_identity(receipt))
        loaded = load_artifact_worlds(receipt, raw)
        loaded_ids = tuple(str(value) for value in loaded.player_ids)
        draws = np.asarray(loaded.player_draws)
        if (
            loaded.block != block
            or set(loaded_ids) != set(player_ids)
            or len(set(loaded_ids)) != len(loaded_ids)
            or draws.dtype != np.dtype(np.float32)
            or draws.shape != (len(loaded_ids), contract.WORLDS_PER_BLOCK)
            or not np.isfinite(draws).all()
        ):
            _fail("training artifact player/matrix binding differs")
        index = {player_id: ordinal for ordinal, player_id in enumerate(loaded_ids)}
        aligned.append(draws[[index[player_id] for player_id in player_ids]])
    player_draws = np.ascontiguousarray(np.concatenate(aligned, axis=1), dtype=np.float32)
    rosters = [tuple(row["roster_player_ids"]) for row in projection["candidates"]]
    scores = np.asarray(cross_score(
        players, player_draws, rosters,
        expected_worlds=4 * contract.WORLDS_PER_BLOCK,
    ))
    if (
        scores.dtype != np.dtype(np.float64)
        or list(scores.shape) != projection["expected_training_score_shape"]
        or not np.isfinite(scores).all()
        or score_matrix_sha256(scores)
        != projection["expected_training_score_matrix_sha256"]
        or contract._float64_matrix_sha256_v1(scores, label="broker score matrix")
        != projection["expected_training_score_matrix_sha256"]
    ):
        _fail("four-block cross-scored matrix differs")
    samples = contract.deterministic_equal_count_samples_from_projection_v1(
        projection, phase=request["phase"]
    )
    nominee_keys = (
        None if nomination is None
        else [list(value) for value in contract._nominee_keys_v1(nomination)]
    )
    capability = matrix_worker.build_matrix_capability_v1(
        phase=request["phase"], source_ordinal=request["source_ordinal"],
        fold_ordinal=fold, projection=projection, process_budget=budget,
        training_score_matrix=scores, samples=samples,
        nominee_keys=nominee_keys,
    )
    response_raw, response_bytes = spawn_matrix(
        capability, int(request["process_ordinal"])
    )
    response = matrix_worker.validate_matrix_response_v1(
        response_raw, capability=capability
    )
    if (
        response["runtime_evidence"]["code_commit"]
        != bootstrap_manifest["code_commit"]
        or response["runtime_evidence"]["image_digest"]
        != bootstrap_manifest["image_digest"]
    ):
        _fail("matrix-selector runtime differs from exact bootstrap manifest")
    try:
        fold_receipt = contract._build_selection_fold_receipt_structural_v1(
            source_ordinal=int(request["source_ordinal"]),
            fold_ordinal=fold,
            projection=projection,
            phase=str(request["phase"]),
            full_candidate_score_row_ledger=response[
                "full_candidate_score_row_ledger"
            ],
            cells=response["cells"],
            nomination=nomination,
            broad_phase_authority=embedded_broad_authority,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise SelectionExecutionV1Error(str(exc)) from exc
    complete_ledger = [*ledger, *broker.ledger]
    if complete_ledger != assembler.expected_worker_read_ledger_v1(
        request=request, process_budget=budget
    ):
        _fail("broker reads differ from exact canonical ledger")
    return assembler.build_fold_child_envelope_v1(
        request=request,
        process_budget=budget,
        read_ledger=complete_ledger,
        selection_fold_receipt=fold_receipt,
        broker_runtime_evidence=broker_runtime,
        matrix_runtime_evidence=response["runtime_evidence"],
        matrix_capability_sha256=capability["matrix_capability_sha256"],
        matrix_response_sha256=response["matrix_response_sha256"],
        matrix_response_bytes=response_bytes,
        bootstrap_manifest_identity=bootstrap_manifest_identity,
        bootstrap_manifest_sha256=bootstrap_manifest[
            "bootstrap_manifest_sha256"
        ],
        bootstrap_process_chain=bootstrap_process_chain,
        launch_intent_identity=bootstrap_manifest["run_identity"],
    )


def run_fold_broker_v1(
    request_value: object, *, broker_runtime_evidence: object,
    read_exact: assembler.ReadExact,
) -> dict[str, object]:
    """Official broker: no executable selection injection is accepted."""
    from nfl_dfs.research import corpus_legal_feasibility as legal
    from nfl_dfs.research import lr8_later_period_source as later

    return _run_fold_broker_core_v1(
        request_value,
        broker_runtime_evidence=broker_runtime_evidence,
        read_exact=read_exact,
        validate_later_source=_validate_later_source,
        players_from_catalog=_players,
        load_artifact_worlds=later.load_artifact_worlds,
        cross_score=legal.cross_score_full_union,
        score_matrix_sha256=legal._score_matrix_sha256,
        spawn_matrix=lambda capability, ordinal: _spawn_matrix_official(
            capability, process_ordinal=ordinal
        ),
    )


def _run_fold_broker_fixture_v1(
    request_value: object, **fixture_hooks: object,
) -> dict[str, object]:
    """Private non-authoritative synthetic seam; never called by the CLI."""
    return _run_fold_broker_core_v1(request_value, **fixture_hooks)


def _spawn_fold_broker(
    request: Mapping[str, object], output_ceiling: int,
) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(request)
    # The controller capability belongs only to the externally dispatched
    # slate assembler.  Its scientific children receive their exact fold
    # request/process budget, never the manifest identity or binding scalars.
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("R6_TASK_")
    }
    environment["R6_SELECTOR_PROCESS_ORDINAL"] = str(request["process_ordinal"])
    output = _bounded_subprocess(
        command=assembler.canonical_fold_broker_command_v1(),
        input_bytes=raw,
        output_ceiling=output_ceiling,
        environment=environment,
    )
    child = assembler._strict_json(output, label="fold-broker stdout")
    evidence = assembler._mapping(
        child.get("child_execution_evidence"), label="child evidence"
    )
    if evidence.get("child_output_bytes") != len(output):
        _fail("fold-broker stdout byte evidence differs")
    return child


def _read_stdin_bounded(limit: int) -> bytes:
    raw = sys.stdin.buffer.read(limit + 1)
    if len(raw) > limit or sys.stdin.buffer.read(1):
        _fail("stdin request exceeds byte ceiling")
    return raw


def _emit_bounded(value: object, *, ceiling: int) -> None:
    if type(ceiling) is not int or ceiling < 1:
        _fail("stdout envelope byte ceiling differs")
    encoder = json.JSONEncoder(
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    byte_count = 0
    try:
        with tempfile.SpooledTemporaryFile(
            max_size=ASSEMBLER_STDOUT_SPOOL_MEMORY_BYTES,
            mode="w+b",
        ) as spool:
            for text_chunk in encoder.iterencode(value):
                raw_chunk = text_chunk.encode("utf-8")
                byte_count += len(raw_chunk)
                if byte_count > ceiling:
                    _fail("stdout envelope exceeds byte ceiling")
                spool.write(raw_chunk)
            spool.seek(0)
            while True:
                raw_chunk = spool.read(64 * 1024)
                if not raw_chunk:
                    break
                written = sys.stdout.buffer.write(raw_chunk)
                if written is not None and written != len(raw_chunk):
                    _fail("stdout envelope write was partial")
    except SelectionExecutionV1Error:
        raise
    except (TypeError, ValueError) as exc:
        raise SelectionExecutionV1Error(
            "stdout envelope is not canonical JSON"
        ) from exc
    sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in (["fold-broker"], ["slate-assembler"]):
        raise SystemExit("usage: ...selection_v1.py {fold-broker|slate-assembler}")
    raw_request = _read_stdin_bounded(STDIN_REQUEST_BYTE_CEILING)
    mode = args[0]
    # The externally dispatched slate assembler must establish the bounded
    # scalar controller binding before it can construct a cloud client.  Fold
    # brokers are private assembler children and are instead closed by the
    # fold process budget and exact subprocess command.
    parsed_binding = (
        task_manifest.parse_child_task_binding_environment_v1(os.environ)
        if mode == "slate-assembler"
        else None
    )
    observed_command = observed_process_command_v1(mode=mode)
    request = assembler._strict_json(raw_request, label="stdin request")
    if mode == "fold-broker":
        validated_request = assembler.validate_fold_worker_request_v1(request)
        process_ordinal = int(validated_request["process_ordinal"])
    else:
        validated_request = assembler.validate_slate_assembler_request_v1(request)
        process_ordinal = int(validated_request["source_ordinal"])
        expected_layer = (
            "broad-selection-receipt"
            if validated_request["phase"] == contract.BROAD_SCREEN_PHASE
            else "confirmation-selection-receipt"
        )
        if (
            parsed_binding is None
            or parsed_binding["layer_id"] != expected_layer
            or parsed_binding["task_index"] != process_ordinal
        ):
            _fail("preclient assembler task layer/index binding differs")
        observed_child_command_sha256 = contract.canonical_sha256_v1({
            "command": observed_command,
            "entrypoint_sha256": sha256(
                Path(observed_command[1]).read_bytes()
            ).hexdigest(),
        })
        if (
            parsed_binding["request_sha256"]
            != sha256(raw_request).hexdigest()
            or parsed_binding["child_command_sha256"]
            != observed_child_command_sha256
        ):
            _fail("preclient assembler request/command scalar binding differs")
    # Every semantic/request/environment gate precedes client construction.
    environment = assembler.validate_execution_environment_v1(
        os.environ, mode=mode
    )
    runtime = assembler.derive_observed_runtime_evidence_v1(
        mode=mode, process_ordinal=process_ordinal, environ=os.environ,
        argv=observed_command, pid=os.getpid(), parent_pid=os.getppid(),
    )
    transport = GCSExactCreateOnceTransportV1(validated_environment=environment)
    if mode == "fold-broker":
        envelope = run_fold_broker_v1(
            validated_request,
            broker_runtime_evidence=runtime,
            read_exact=transport.read_exact,
        )
        ceiling = int(envelope["child_execution_evidence"]["child_output_byte_ceiling"])
    else:
        binding_evidence = reopen_controller_task_after_client_v1(
            parsed_binding=parsed_binding,
            environ=os.environ,
            raw_request=raw_request,
            observed_command=observed_command,
            read_exact=transport.read_exact,
            expected_process_role=(
                "broad-slate-assembler"
                if validated_request["phase"] == contract.BROAD_SCREEN_PHASE
                else "confirmation-slate-assembler"
            ),
            expected_phase=str(validated_request["phase"]),
            expected_source_ordinal=process_ordinal,
            expected_process_ordinal=process_ordinal,
        )
        envelope = assembler.run_slate_assembler_v1(
            validated_request,
            read_exact=transport.read_exact,
            publish_create_once=transport.publish_create_once,
            assembler_runtime_evidence=runtime,
            spawn_child=_spawn_fold_broker,
        )
        envelope = bind_task_evidence_to_assembler_envelope_v1(
            envelope,
            binding_evidence,
            request=validated_request,
            raw_request=raw_request,
        )
        ceiling = ASSEMBLER_STDOUT_BYTE_CEILING
    _emit_bounded(envelope, ceiling=ceiling)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "GCSExactCreateOnceTransportV1",
    "SelectionExecutionV1Error",
    "main",
    "run_fold_broker_v1",
]
