"""Object-store-free matrix selector child for the current-bank crossed screen.

This module has no object-store client and accepts no object identity, URI,
reader, publisher, endpoint, project, source-freeze body, or world-artifact
body. The separate fold broker validates and materializes exactly four
training blocks, then sends this process a bounded scientific capability and
one inherited, read-only anonymous-file descriptor containing the exact finite
score matrix. The held-out artifact identity is absent, not merely marked
unread.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import fcntl
from hashlib import sha256
import mmap
import os
from pathlib import Path
import stat
import sys
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_selection_assembler_v1 as assembler


MATRIX_CAPABILITY_SCHEMA: Final = "corpus-r6-current-bank-four-block-matrix-capability/v1"
MATRIX_RESPONSE_SCHEMA: Final = "corpus-r6-current-bank-registered-selector-response/v1"
MATRIX_CAPABILITY_BYTE_CEILING: Final = 96_000_000
MATRIX_RESPONSE_BYTE_CEILING: Final = 128_000_000
MATRIX_ANONYMOUS_FD: Final = 198
MATRIX_HASH_CHUNK_BYTES: Final = 1024 * 1024
MATRIX_FINITE_CHECK_CHUNK_BYTES: Final = 8 * 1024 * 1024
MATRIX_MEMFD_NAME: Final = "r6-current-bank-score-matrix-v1"
MATRIX_MEMFD_LINK_TARGET: Final = f"/memfd:{MATRIX_MEMFD_NAME} (deleted)"
MATRIX_REQUIRED_SEALS: Final = (
    fcntl.F_SEAL_WRITE
    | fcntl.F_SEAL_GROW
    | fcntl.F_SEAL_SHRINK
    | fcntl.F_SEAL_SEAL
)
MATRIX_DESCRIPTOR_CODEC: Final = "inherited-sealed-memfd-float64-le-v1"
MATRIX_RAW_BYTE_CEILING: Final = (
    contract.MAX_SELECTION_CANDIDATES_PER_FOLD
    * 4
    * contract.WORLDS_PER_BLOCK
    * 8
)


class CorpusR6CurrentBankSelectionFoldWorkerV1Error(ValueError):
    """The object-store-free registered selection process failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = contract.canonical_sha256_v1(result)
    return result


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    if value.get(field) != contract.canonical_sha256_v1({
        key: item for key, item in value.items() if key != field
    }):
        _fail(f"{label} self hash differs")


def _reject_transport_keys(value: object, *, path: str) -> None:
    """Reject transport/addressability keys without inspecting harmless values."""
    if isinstance(value, Mapping):
        forbidden = {
            "uri", "generation", "artifact_identity", "object_identity",
            "read_exact", "read_client", "storage_client", "endpoint",
            "bucket", "object_name",
        }
        for raw_key, child in value.items():
            key = str(raw_key).lower()
            if key in forbidden or key.endswith("_uri") or key.endswith("_generation"):
                _fail(f"scientific projection exposes transport key {path}.{raw_key}")
            _reject_transport_keys(child, path=f"{path}.{raw_key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _reject_transport_keys(child, path=f"{path}[{index}]")


def _sha256_text(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} differs")
    return str(value)


def _matrix_descriptor_v1(
    scores_value: object, *, expected_matrix_sha256: str,
) -> dict[str, object]:
    scores = np.asarray(scores_value)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or not scores.shape[0]
        or not scores.shape[1]
        or not np.isfinite(scores).all()
    ):
        _fail("matrix capability requires a finite nonempty float64 matrix")
    matrix = np.ascontiguousarray(scores, dtype="<f8")
    raw = memoryview(matrix).cast("B")
    raw_digest = sha256()
    scientific_digest = sha256()
    scientific_digest.update(contract.canonical_json_bytes_v1({
        "dtype": "float64-le",
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
    }))
    scientific_digest.update(b"\0")
    for offset in range(0, raw.nbytes, MATRIX_HASH_CHUNK_BYTES):
        chunk = raw[offset:offset + MATRIX_HASH_CHUNK_BYTES]
        raw_digest.update(chunk)
        scientific_digest.update(chunk)
    matrix_sha256 = scientific_digest.hexdigest()
    if matrix_sha256 != _sha256_text(
        expected_matrix_sha256, label="expected matrix SHA-256"
    ):
        _fail("matrix descriptor differs from projection matrix authority")
    body = {
        "codec": MATRIX_DESCRIPTOR_CODEC,
        "dtype": "float64-le",
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "raw_sha256": raw_digest.hexdigest(),
        "raw_bytes": raw.nbytes,
        "matrix_sha256": matrix_sha256,
        "fd_number": MATRIX_ANONYMOUS_FD,
    }
    return _with_hash(body, field="matrix_descriptor_sha256")


def _validate_matrix_descriptor_v1(
    value: object, *, expected_shape: object | None = None,
    expected_matrix_sha256: object | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="matrix descriptor")
    if set(item) != {
        "codec", "dtype", "shape", "raw_sha256", "raw_bytes",
        "matrix_sha256", "fd_number", "matrix_descriptor_sha256",
    }:
        _fail("matrix descriptor fields differ")
    _self_hash(item, field="matrix_descriptor_sha256", label="matrix descriptor")
    shape = _sequence(item.get("shape"), label="matrix descriptor shape")
    if (
        item.get("codec") != MATRIX_DESCRIPTOR_CODEC
        or item.get("dtype") != "float64-le"
        or len(shape) != 2
        or any(type(dimension) is not int or dimension < 1 for dimension in shape)
        or shape[0] > contract.MAX_SELECTION_CANDIDATES_PER_FOLD
        or shape[1] != 4 * contract.WORLDS_PER_BLOCK
        or type(item.get("raw_bytes")) is not int
        or item.get("raw_bytes") != int(shape[0]) * int(shape[1]) * 8
        or item.get("raw_bytes") > MATRIX_RAW_BYTE_CEILING
        or item.get("fd_number") != MATRIX_ANONYMOUS_FD
    ):
        _fail("matrix descriptor shape/byte/FD boundary differs")
    _sha256_text(item.get("raw_sha256"), label="matrix descriptor raw SHA-256")
    matrix_sha256 = _sha256_text(
        item.get("matrix_sha256"), label="matrix descriptor scientific SHA-256"
    )
    if expected_shape is not None and list(shape) != list(
        _sequence(expected_shape, label="expected matrix descriptor shape")
    ):
        _fail("matrix descriptor shape differs from scientific projection")
    if (
        expected_matrix_sha256 is not None
        and matrix_sha256 != expected_matrix_sha256
    ):
        _fail("matrix descriptor hash differs from scientific projection")
    return item


def _stream_inherited_matrix_hashes_v1(
    *, fd_number: int, descriptor: Mapping[str, object],
) -> tuple[str, str]:
    raw_digest = sha256()
    scientific_digest = sha256()
    scientific_digest.update(contract.canonical_json_bytes_v1({
        "dtype": "float64-le",
        "shape": list(descriptor["shape"]),
    }))
    scientific_digest.update(b"\0")
    remaining = int(descriptor["raw_bytes"])
    offset = 0
    while remaining:
        try:
            chunk = os.pread(
                fd_number, min(remaining, MATRIX_HASH_CHUNK_BYTES), offset
            )
        except OSError as exc:
            raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(
                "inherited matrix FD cannot be read"
            ) from exc
        if not chunk:
            _fail("inherited matrix FD is truncated during stream hash")
        raw_digest.update(chunk)
        scientific_digest.update(chunk)
        offset += len(chunk)
        remaining -= len(chunk)
    return raw_digest.hexdigest(), scientific_digest.hexdigest()


def _map_inherited_matrix_readonly_v1(
    descriptor_value: object, *, fd_number: int | None = None,
) -> tuple[np.ndarray, mmap.mmap]:
    """Authenticate and read-only-map the inherited anonymous score matrix."""
    descriptor = _validate_matrix_descriptor_v1(descriptor_value)
    actual_fd = MATRIX_ANONYMOUS_FD if fd_number is None else fd_number
    if type(actual_fd) is not int or actual_fd < 0:
        _fail("inherited matrix FD number differs")
    try:
        os.set_inheritable(actual_fd, False)
        status = os.fstat(actual_fd)
    except OSError as exc:
        raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(
            "inherited matrix FD is absent"
        ) from exc
    if not stat.S_ISREG(status.st_mode) or status.st_nlink != 0:
        _fail("inherited matrix FD is not one regular anonymous memfd")
    if status.st_size != descriptor["raw_bytes"]:
        _fail("inherited matrix FD byte count differs")
    try:
        access_mode = fcntl.fcntl(actual_fd, fcntl.F_GETFL) & os.O_ACCMODE
        observed_seals = fcntl.fcntl(actual_fd, fcntl.F_GET_SEALS)
        link_target = os.readlink(f"/proc/self/fd/{actual_fd}")
    except OSError as exc:
        raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(
            "inherited matrix FD access/anonymity cannot be verified"
        ) from exc
    if access_mode != os.O_RDONLY:
        _fail("inherited matrix FD is not read-only")
    if observed_seals != MATRIX_REQUIRED_SEALS:
        _fail("inherited matrix memfd exact seal set differs")
    if link_target != MATRIX_MEMFD_LINK_TARGET:
        _fail("inherited matrix FD is not the fixed anonymous memfd")
    raw_sha256, matrix_sha256 = _stream_inherited_matrix_hashes_v1(
        fd_number=actual_fd, descriptor=descriptor
    )
    if raw_sha256 != descriptor["raw_sha256"]:
        _fail("inherited matrix FD raw hash differs")
    if matrix_sha256 != descriptor["matrix_sha256"]:
        _fail("inherited matrix FD scientific hash differs")
    try:
        region = mmap.mmap(
            actual_fd, int(descriptor["raw_bytes"]), access=mmap.ACCESS_READ
        )
    except (OSError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(
            "inherited matrix FD cannot be read-only mapped"
        ) from exc
    try:
        os.close(actual_fd)
    except OSError as exc:
        region.close()
        raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(
            "authenticated matrix memfd cannot be closed"
        ) from exc
    scores = np.ndarray(
        tuple(int(value) for value in descriptor["shape"]),
        dtype="<f8",
        buffer=region,
    )
    scores.flags.writeable = False
    rows_per_check = max(
        1,
        MATRIX_FINITE_CHECK_CHUNK_BYTES // (int(scores.shape[1]) * 8),
    )
    for start in range(0, int(scores.shape[0]), rows_per_check):
        if not np.isfinite(scores[start:start + rows_per_check]).all():
            del scores
            region.close()
            _fail("inherited matrix FD contains a non-finite score")
    return scores, region


def build_matrix_capability_v1(
    *,
    phase: str,
    source_ordinal: int,
    fold_ordinal: int,
    projection: Mapping[str, object],
    process_budget: Mapping[str, object],
    training_score_matrix: np.ndarray,
    samples: Mapping[str, object],
    nominee_keys: object | None = None,
) -> dict[str, object]:
    """Strip transport authority and expose only four-block selection facts."""
    try:
        retained_projection = contract.validate_narrow_projection_v1(projection)
        budget = contract.validate_process_budget_v1(process_budget)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectionFoldWorkerV1Error(str(exc)) from exc
    phase_value = str(phase)
    source = int(source_ordinal)
    fold = int(fold_ordinal)
    if (
        type(source_ordinal) is not int
        or type(fold_ordinal) is not int
        or not 0 <= source < contract.PANEL_SLATE_COUNT
        or not 0 <= fold < contract.FOLDS_PER_SLATE
        or retained_projection["heldout_block"] != contract.WORLD_BLOCKS[fold]
        or budget["phase"] != phase_value
        or budget["source_ordinal"] != source
        or budget["process_ordinal"] != source * contract.FOLDS_PER_SLATE + fold
    ):
        _fail("matrix capability phase/source/fold/budget differs")
    scores = np.asarray(training_score_matrix)
    if (
        scores.dtype != np.dtype(np.float64)
        or list(scores.shape) != retained_projection["expected_training_score_shape"]
        or not np.isfinite(scores).all()
        or contract._float64_matrix_sha256_v1(scores, label="capability matrix")
        != retained_projection["expected_training_score_matrix_sha256"]
    ):
        _fail("matrix capability differs from projection matrix authority")
    matrix_descriptor = _matrix_descriptor_v1(
        scores,
        expected_matrix_sha256=retained_projection[
            "expected_training_score_matrix_sha256"
        ],
    )
    candidate_rows = [dict(row) for row in retained_projection["candidates"]]
    sanitized_projection = {
        "projection_sha256": retained_projection["projection_sha256"],
        "slate_id": retained_projection["slate_id"],
        "fit_scope_id": retained_projection["fit_scope_id"],
        "training_blocks": list(retained_projection["training_blocks"]),
        "heldout_block_label": retained_projection["heldout_block"],
        "training_world_columns_sha256": retained_projection["training_world_columns_sha256"],
        "candidates": candidate_rows,
        "candidate_lineup_order_sha256": retained_projection["candidate_lineup_order_sha256"],
        "candidate_rosters_sha256": retained_projection["candidate_rosters_sha256"],
        "candidate_rows_sha256": retained_projection["candidate_rows_sha256"],
        "training_score_matrix_sha256": retained_projection["expected_training_score_matrix_sha256"],
        "training_score_shape": retained_projection["expected_training_score_shape"],
    }
    keys: list[list[str]] | None
    if phase_value == contract.BROAD_SCREEN_PHASE:
        if nominee_keys is not None:
            _fail("broad matrix capability cannot accept nominee keys")
        keys = None
    elif phase_value == contract.CONFIRMATION_PHASE:
        raw_keys = _sequence(nominee_keys, label="confirmation nominee keys")
        keys = []
        for index, raw in enumerate(raw_keys):
            pair = _sequence(raw, label=f"nominee key[{index}]")
            if len(pair) != 2 or any(not isinstance(value, str) or not value for value in pair):
                _fail("confirmation nominee key differs")
            keys.append([str(pair[0]), str(pair[1])])
        if not keys or len(keys) > contract.MAXIMUM_CONFIRMATION_NOMINEES:
            _fail("confirmation nominee count differs")
    else:
        _fail("matrix capability phase differs")
    sample_value = _mapping(samples, label="selection samples")
    strategies = contract.frozen_strategies_v1()
    body = {
        "schema_version": MATRIX_CAPABILITY_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": phase_value,
        "source_ordinal": source,
        "fold_ordinal": fold,
        "process_ordinal": source * contract.FOLDS_PER_SLATE + fold,
        "projection_scientific_binding": sanitized_projection,
        "projection_scientific_binding_sha256": contract.canonical_sha256_v1(sanitized_projection),
        "samples": sample_value,
        "samples_sha256": contract.canonical_sha256_v1(sample_value),
        "strategies": strategies,
        "strategy_registry_sha256": contract.canonical_sha256_v1(strategies),
        "fit_count_precharge": int(budget["compute_fit_precharge"]),
        "nominee_keys": keys,
        "matrix_descriptor": matrix_descriptor,
        "matrix_bytes_embedded": False,
        "object_store_transport_capability_exposed": False,
        "inherited_local_matrix_fd_exposed": True,
        "object_identity_exposed": False,
        "heldout_artifact_identity_exposed": False,
        "heldout_artifact_body_exposed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    result = _with_hash(body, field="matrix_capability_sha256")
    if len(contract.canonical_json_bytes_v1(result)) > MATRIX_CAPABILITY_BYTE_CEILING:
        _fail("matrix capability exceeds frozen input byte ceiling")
    return result


def validate_matrix_capability_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="matrix capability")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "fold_ordinal", "process_ordinal", "projection_scientific_binding",
        "projection_scientific_binding_sha256", "samples", "samples_sha256",
        "strategies", "strategy_registry_sha256", "fit_count_precharge",
        "nominee_keys", "matrix_descriptor", "matrix_bytes_embedded",
        "object_store_transport_capability_exposed",
        "inherited_local_matrix_fd_exposed", "object_identity_exposed",
        "heldout_artifact_identity_exposed", "heldout_artifact_body_exposed",
        "policy", "matrix_capability_sha256",
    }:
        _fail("matrix capability fields differ")
    _self_hash(item, field="matrix_capability_sha256", label="matrix capability")
    if (
        item["schema_version"] != MATRIX_CAPABILITY_SCHEMA
        or item["contract_id"] != contract.CONTRACT_ID
        or item["object_store_transport_capability_exposed"] is not False
        or item["inherited_local_matrix_fd_exposed"] is not True
        or item["matrix_bytes_embedded"] is not False
        or item["object_identity_exposed"] is not False
        or item["heldout_artifact_identity_exposed"] is not False
        or item["heldout_artifact_body_exposed"] is not False
        or item["policy"] != contract.POLICY_CLAIMS
    ):
        _fail("matrix capability fixed boundary differs")
    source = item.get("source_ordinal")
    fold = item.get("fold_ordinal")
    phase = item.get("phase")
    if (
        type(source) is not int
        or type(fold) is not int
        or not 0 <= source < contract.PANEL_SLATE_COUNT
        or not 0 <= fold < contract.FOLDS_PER_SLATE
        or item.get("process_ordinal")
        != source * contract.FOLDS_PER_SLATE + fold
        or phase not in {
            contract.BROAD_SCREEN_PHASE, contract.CONFIRMATION_PHASE,
        }
    ):
        _fail("matrix capability phase/source/fold/process differs")
    projection = _mapping(item["projection_scientific_binding"], label="scientific projection")
    if set(projection) != {
        "projection_sha256", "slate_id", "fit_scope_id", "training_blocks",
        "heldout_block_label", "training_world_columns_sha256", "candidates",
        "candidate_lineup_order_sha256", "candidate_rosters_sha256",
        "candidate_rows_sha256", "training_score_matrix_sha256",
        "training_score_shape",
    }:
        _fail("scientific projection fields differ")
    _reject_transport_keys(projection, path="projection")
    if item["projection_scientific_binding_sha256"] != contract.canonical_sha256_v1(projection):
        _fail("scientific projection hash differs")
    expected_heldout = contract.WORLD_BLOCKS[fold]
    if (
        projection.get("heldout_block_label") != expected_heldout
        or projection.get("fit_scope_id") != f"holdout-{expected_heldout}"
        or projection.get("training_blocks")
        != [block for block in contract.WORLD_BLOCKS if block != expected_heldout]
    ):
        _fail("scientific projection fold isolation differs")
    if item["samples_sha256"] != contract.canonical_sha256_v1(item["samples"]):
        _fail("matrix capability samples hash differs")
    strategies = contract.frozen_strategies_v1()
    if item["strategies"] != strategies or item["strategy_registry_sha256"] != contract.canonical_sha256_v1(strategies):
        _fail("matrix capability strategy registry differs")
    if type(item["fit_count_precharge"]) is not int or item["fit_count_precharge"] < 1:
        _fail("matrix capability fit precharge differs")
    nominee_keys = item.get("nominee_keys")
    expected_fit_count = len(strategies) * 8
    if phase == contract.BROAD_SCREEN_PHASE:
        if nominee_keys is not None:
            _fail("broad matrix capability nominee keys differ")
    else:
        keys = _sequence(nominee_keys, label="confirmation nominee keys")
        if not 1 <= len(keys) <= contract.MAXIMUM_CONFIRMATION_NOMINEES:
            _fail("confirmation matrix capability nominee count differs")
        normalized_keys: list[list[str]] = []
        for index, raw_key in enumerate(keys):
            key = _sequence(raw_key, label=f"confirmation nominee key[{index}]")
            if len(key) != 2 or any(
                not isinstance(value, str) or not value for value in key
            ):
                _fail("confirmation matrix capability nominee key differs")
            normalized_keys.append([str(key[0]), str(key[1])])
        if len({tuple(key) for key in normalized_keys}) != len(normalized_keys):
            _fail("confirmation matrix capability nominee keys repeat")
        expected_fit_count = contract.SUBSAMPLE_REPLICATES * len(normalized_keys)
    if item["fit_count_precharge"] != expected_fit_count:
        _fail("matrix capability fit precharge/replay grid differs")
    shape = _sequence(
        projection.get("training_score_shape"),
        label="scientific projection training score shape",
    )
    if (
        len(shape) != 2
        or any(type(dimension) is not int for dimension in shape)
        or shape[1] != 4 * contract.WORLDS_PER_BLOCK
        or shape[0] != len(projection["candidates"])
    ):
        _fail("scientific projection matrix shape differs")
    _validate_matrix_descriptor_v1(
        item["matrix_descriptor"],
        expected_shape=shape,
        expected_matrix_sha256=projection["training_score_matrix_sha256"],
    )
    return item


def _execute_registered_selection_v1(
    capability_value: object, *, runtime_evidence: object,
    training_score_matrix: np.ndarray,
) -> dict[str, object]:
    """Run the sole registered selection implementation; no fixture seam."""
    capability = validate_matrix_capability_v1(capability_value)
    runtime = assembler.validate_observed_runtime_evidence_v1(runtime_evidence)
    if (
        runtime["mode"] != "matrix-selector"
        or runtime["process_ordinal"] != capability["process_ordinal"]
        or runtime["command"] != assembler.canonical_matrix_selector_command_v1()
    ):
        _fail("matrix-selector observed runtime differs from capability")
    # Lazy import is intentional: only this transport-free process loads the
    # registered executable selection implementation.
    from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_selector_v1 as registered

    strategies = registered._verify_live_registries_v1()
    if strategies != capability["strategies"]:
        _fail("registered selector registry differs from capability")
    projection = capability["projection_scientific_binding"]
    candidates = projection["candidates"]
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    candidate_by_id = {str(row["lineup_id"]): row for row in candidates}
    scores = np.asarray(training_score_matrix)
    descriptor = capability["matrix_descriptor"]
    if (
        scores.dtype != np.dtype(np.float64)
        or list(scores.shape) != descriptor["shape"]
        or scores.flags.writeable
    ):
        _fail("read-only mapped matrix differs from capability descriptor")
    full_ledger = contract._ordered_score_row_ledger_fixture_v1(lineup_ids, scores)
    sample_rows = capability["samples"]
    sample_by_key = {
        (int(replicate["replicate"]), str(view["view_id"])): view
        for replicate in sample_rows["replicates"]
        for view in replicate["views"]
    }
    strategy_by_id = {str(value["strategy_id"]): value for value in strategies}
    if capability["phase"] == contract.BROAD_SCREEN_PHASE:
        keys = [
            (0, view_id, str(strategy["strategy_id"]))
            for view_id in ["U", *(contract.isolated_view_id_v1(index) for index in range(7))]
            for strategy in strategies
        ]
    else:
        keys = [
            (replicate, view_id, strategy_id)
            for replicate in range(contract.SUBSAMPLE_REPLICATES)
            for view_id, strategy_id in capability["nominee_keys"]
        ]
    matrix_ordinal = {lineup_id: index for index, lineup_id in enumerate(lineup_ids)}
    cells: list[dict[str, object]] = []
    for replicate, view_id, strategy_id in keys:
        sample = sample_by_key[(replicate, view_id)]
        sampled_ids = [str(value) for value in sample["sampled_lineup_ids"]]
        sampled_scores = np.ascontiguousarray(
            scores[[matrix_ordinal[value] for value in sampled_ids]], dtype=np.float64
        )
        strategy = strategy_by_id[strategy_id]
        selected, trace = registered.runner._run_strategy_v2(
            strategy, training_scores=sampled_scores, lineup_ids=sampled_ids
        )
        replay_selected, replay_trace = registered.runner._run_strategy_v2(
            strategy, training_scores=sampled_scores, lineup_ids=sampled_ids
        )
        if selected != replay_selected or trace != replay_trace:
            _fail("registered selector replay differs")
        selected_ids = [sampled_ids[int(index)] for index in selected]
        sampled_ledger = contract._sampled_score_row_ledger_from_full_v1(full_ledger, sampled_ids)
        roster_by_id = {
            lineup_id: list(candidate_by_id[lineup_id]["roster_player_ids"])
            for lineup_id in selected_ids
        }
        bound_trace = contract._selection_trace_binding_v1(
            selected_lineup_ids=selected_ids,
            sampled_lineup_ids=sampled_ids,
            sampled_score_row_ledger=sampled_ledger,
        )
        cell = {
            "replicate": replicate,
            "view_id": view_id,
            "sampled_lineup_ids": sampled_ids,
            "sampled_lineup_ids_sha256": sample["sampled_lineup_ids_sha256"],
            "rank_seed_sha256": sample["seed_material_sha256"],
            "strategy_ordinal": strategy["ordinal"],
            "strategy_id": strategy_id,
            "strategy_sha256": strategy["strategy_sha256"],
            "executable_fingerprint_sha256": contract.strategy_executable_fingerprint_v1(strategy),
            "training_score_row_ledger": sampled_ledger,
            "selected_lineup_ids": selected_ids,
            "selected_lineup_ids_sha256": contract.canonical_sha256_v1(selected_ids),
            "selected_rosters_sha256": contract.canonical_sha256_v1(
                [roster_by_id[value] for value in selected_ids]
            ),
            "prefixes": contract._selection_prefixes_v1(selected_ids, roster_by_id),
            "selection_trace": bound_trace,
            "selection_trace_sha256": contract.canonical_sha256_v1(bound_trace),
        }
        cell["selection_cell_sha256"] = contract.canonical_sha256_v1(cell)
        cells.append(cell)
    body = {
        "schema_version": MATRIX_RESPONSE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": capability["phase"],
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "matrix_capability_sha256": capability["matrix_capability_sha256"],
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "full_candidate_score_row_ledger": full_ledger,
        "full_candidate_score_row_ledger_sha256": contract.canonical_sha256_v1(
            full_ledger
        ),
        "cells": cells,
        "cells_sha256": contract.canonical_sha256_v1(cells),
        "fit_count": len(cells),
        "transport_imported": False,
        "raw_read_callable_received": False,
        "heldout_artifact_identity_received": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    result = _with_hash(body, field="matrix_response_sha256")
    if len(contract.canonical_json_bytes_v1(result)) > MATRIX_RESPONSE_BYTE_CEILING:
        _fail("matrix-selector response exceeds byte ceiling")
    return result


def validate_matrix_response_v1(value: object, *, capability: object) -> dict[str, object]:
    item = _mapping(value, label="matrix-selector response")
    if set(item) != {
        "schema_version", "contract_id", "phase", "source_ordinal",
        "fold_ordinal", "process_ordinal", "matrix_capability_sha256",
        "runtime_evidence", "runtime_evidence_sha256",
        "full_candidate_score_row_ledger",
        "full_candidate_score_row_ledger_sha256", "cells", "cells_sha256",
        "fit_count", "transport_imported", "raw_read_callable_received",
        "heldout_artifact_identity_received", "policy",
        "matrix_response_sha256",
    }:
        _fail("matrix-selector response fields differ")
    cap = validate_matrix_capability_v1(capability)
    _self_hash(item, field="matrix_response_sha256", label="matrix response")
    cells = _sequence(item.get("cells"), label="response cells")
    if (
        item.get("schema_version") != MATRIX_RESPONSE_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("phase") != cap["phase"]
        or item.get("source_ordinal") != cap["source_ordinal"]
        or item.get("fold_ordinal") != cap["fold_ordinal"]
        or item.get("process_ordinal") != cap["process_ordinal"]
        or item.get("matrix_capability_sha256") != cap["matrix_capability_sha256"]
        or item.get("full_candidate_score_row_ledger_sha256")
        != contract.canonical_sha256_v1(
            item.get("full_candidate_score_row_ledger")
        )
        or item.get("cells_sha256") != contract.canonical_sha256_v1(cells)
        or item.get("fit_count") != len(cells)
        or item.get("fit_count") != cap["fit_count_precharge"]
        or item.get("transport_imported") is not False
        or item.get("raw_read_callable_received") is not False
        or item.get("heldout_artifact_identity_received") is not False
        or item.get("policy") != contract.POLICY_CLAIMS
    ):
        _fail("matrix-selector response binding/policy differs")
    runtime = assembler.validate_observed_runtime_evidence_v1(item.get("runtime_evidence"))
    if runtime["runtime_evidence_sha256"] != item.get("runtime_evidence_sha256"):
        _fail("matrix-selector runtime evidence hash differs")
    return item


def _read_stdin_bounded(limit: int) -> bytes:
    raw = sys.stdin.buffer.read(limit + 1)
    if len(raw) > limit or sys.stdin.buffer.read(1):
        _fail("matrix capability stdin exceeds byte ceiling")
    return raw


def _execute_with_inherited_matrix_v1(
    capability: Mapping[str, object], *, runtime_evidence: object,
) -> dict[str, object]:
    """Map for one selector call while never masking its original failure."""
    scores, matrix_mapping = _map_inherited_matrix_readonly_v1(
        capability["matrix_descriptor"]
    )
    try:
        response = _execute_registered_selection_v1(
            capability,
            runtime_evidence=runtime_evidence,
            training_score_matrix=scores,
        )
    except BaseException:
        # A failing selector traceback may retain its ndarray argument.  In
        # that case mmap.close() raises BufferError; suppress only that cleanup
        # error so the selector failure remains authoritative.  Process exit
        # then releases the anonymous mapping and inherited descriptor.
        del scores
        try:
            matrix_mapping.close()
        except BufferError:
            pass
        raise
    del scores
    matrix_mapping.close()
    return response


def _main() -> int:
    if sys.argv[1:] != ["matrix-selector"]:
        raise SystemExit("usage: ...selection_fold_worker_v1.py matrix-selector")
    raw = _read_stdin_bounded(MATRIX_CAPABILITY_BYTE_CEILING)
    capability = assembler._strict_json(raw, label="matrix-selector stdin")
    validate_matrix_capability_v1(capability)
    observed_argv = [
        os.path.abspath(sys.executable), str(Path(__file__).resolve()), *sys.argv[1:]
    ]
    runtime = assembler.derive_observed_runtime_evidence_v1(
        mode="matrix-selector",
        process_ordinal=int(capability["process_ordinal"]),
        environ=os.environ,
        argv=observed_argv,
        pid=os.getpid(),
        parent_pid=os.getppid(),
    )
    if runtime["command"] != assembler.canonical_matrix_selector_command_v1():
        _fail("matrix-selector observed command differs")
    response = _execute_with_inherited_matrix_v1(
        capability, runtime_evidence=runtime
    )
    output = contract.canonical_json_bytes_v1(response)
    if len(output) > MATRIX_RESPONSE_BYTE_CEILING:
        _fail("matrix-selector stdout exceeds byte ceiling")
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())


__all__ = [
    "MATRIX_ANONYMOUS_FD",
    "MATRIX_CAPABILITY_BYTE_CEILING",
    "MATRIX_CAPABILITY_SCHEMA",
    "MATRIX_RAW_BYTE_CEILING",
    "MATRIX_MEMFD_LINK_TARGET",
    "MATRIX_MEMFD_NAME",
    "MATRIX_REQUIRED_SEALS",
    "MATRIX_RESPONSE_BYTE_CEILING",
    "MATRIX_RESPONSE_SCHEMA",
    "CorpusR6CurrentBankSelectionFoldWorkerV1Error",
    "build_matrix_capability_v1",
    "validate_matrix_capability_v1",
    "validate_matrix_response_v1",
]
