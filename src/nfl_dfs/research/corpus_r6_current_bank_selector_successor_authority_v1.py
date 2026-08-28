"""Authority adapter for the grouped R6 current-bank selector successor.

The pure successor intentionally accepts caller-shaped arrays and therefore
cannot establish production input authority by itself.  This adapter reuses
the existing crossed-screen scientific matrix capability and exact read-only
matrix descriptor, while requiring a distinct observed runtime authority for
the grouped successor executable.  It never claims to have run through the
frozen 64-fit control matrix-selector command.

Only the broad screen is supported here.  Confirmation remains closed until
its separate rank-only view/sample authority exists.  This module performs no
cloud or object-store I/O and grants no publication, promotion, outcome-read,
or production-mutation authority.  The existing outer launch and fold-envelope
authority must still bind the response before it can enter a durable chain.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as successor_runtime,
)


AUTHORITY_WRAPPER_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-authority-wrapper/v1"
)
AUTHORITY_RESPONSE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-authority-response/v1"
)
AUTHORITY_VIEW_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-authority-view/v1"
)
AUTHORITY_CELL_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-authority-cell/v1"
)
AUTHORITY_WRAPPER_ID: Final = "grouped-three-native-broad-authority-wrapper-v1"
EXPECTED_AUTHORITY_WRAPPER_SHA256: Final = (
    "00b1da72cebc3a20c3c327cb79818dcbeb695204221cc5ca6455649012c63c5e"
)
EXACT_WORLDS_PER_BLOCK: Final = 10_000
EXACT_TRAINING_BLOCK_COUNT: Final = 4
EXACT_BROAD_VIEW_COUNT: Final = 8
EXACT_SELECTOR_COUNT_PER_VIEW: Final = 3
EXACT_BROAD_CELL_COUNT: Final = (
    EXACT_BROAD_VIEW_COUNT * EXACT_SELECTOR_COUNT_PER_VIEW
)
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")

_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "heldout_score_columns_present": False,
    "heldout_artifact_identity_present": False,
    "corpus_regeneration_performed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "scientific_input_authority_validated": True,
    "execution_local_authority_bound": True,
    "outer_launch_authority_binding_required": True,
    "publication_authority": False,
    "promotion_authority": False,
    "decision_authority": False,
}


class CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(ValueError):
    """The successor authority boundary failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            "value is not canonical finite JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    retained = dict(body)
    if field in retained:
        _fail(f"{field} cannot already be present")
    retained[field] = _hash(retained)
    return retained


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _require_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    if value.get(field) != _hash({
        key: item for key, item in value.items() if key != field
    }):
        _fail(f"{label} self hash differs")


def frozen_authority_wrapper_v1() -> dict[str, object]:
    """Return the semantic adapter contract, independent of its file hash."""
    implementation = successor.frozen_successor_implementation_v1()
    registry = successor.frozen_native_preset_registry_v1()
    body: dict[str, object] = {
        "schema_version": AUTHORITY_WRAPPER_SCHEMA,
        "authority_wrapper_id": AUTHORITY_WRAPPER_ID,
        "accepted_phase": contract.BROAD_SCREEN_PHASE,
        "confirmation_supported": False,
        "confirmation_failure_law": (
            "fail-before-matrix-copy-or-grouped-selector-execution"
        ),
        "matrix_capability_schema": worker.MATRIX_CAPABILITY_SCHEMA,
        "runtime_evidence_schema": successor_runtime.RUNTIME_SCHEMA,
        "runtime_mode": successor_runtime.RUNTIME_MODE,
        "runtime_command_authority": (
            "grouped-successor-canonical-matrix-selector-command-v1"
        ),
        "worlds_per_block": EXACT_WORLDS_PER_BLOCK,
        "training_block_count": EXACT_TRAINING_BLOCK_COUNT,
        "broad_view_count": EXACT_BROAD_VIEW_COUNT,
        "selector_count_per_view": EXACT_SELECTOR_COUNT_PER_VIEW,
        "broad_cell_count": EXACT_BROAD_CELL_COUNT,
        "sample_law": (
            "exact-current-bank-deterministic-equal-count-broad-replay"
        ),
        "matrix_law": (
            "exact-read-only-c-contiguous-float64-capability-descriptor-bytes"
        ),
        "score_ledger_law": (
            "derive-full-row-ledger-once-then-exact-sampled-subset-per-view"
        ),
        "execution_law": (
            "one-sampled-matrix-copy-and-one-grouped-three-selector-call-per-view"
        ),
        "existing_fold_receipt_compatible": False,
        "successor_process_budget_required": True,
        "successor_implementation_sha256": implementation[
            "implementation_sha256"
        ],
        "successor_preset_registry_sha256": _hash(registry),
        "outer_authority_law": (
            "successor-launch-and-fold-envelope-binding-remains-required"
        ),
        "policy": dict(_POLICY),
    }
    retained = _with_hash(body, field="authority_wrapper_sha256")
    if (
        retained["authority_wrapper_sha256"]
        != EXPECTED_AUTHORITY_WRAPPER_SHA256
    ):
        _fail("successor authority-wrapper semantic contract drifted")
    return retained


def _validate_candidate_authority_v1(
    projection: Mapping[str, object], *, training_blocks: Sequence[str],
) -> tuple[list[str], list[dict[str, object]]]:
    candidates = [
        _mapping(row, label=f"projection candidate[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(projection.get("candidates"), label="projection candidates")
        )
    ]
    lineup_ids = [str(row.get("lineup_id")) for row in candidates]
    if not successor.ENTRY_BUDGET <= len(candidates) <= (
        contract.MAX_SELECTION_CANDIDATES_PER_FOLD
    ):
        _fail("projection candidate count differs from current-bank authority")
    try:
        normalized = successor._validated_candidates(
            candidates,
            sampled_lineup_ids=lineup_ids,
            training_blocks=training_blocks,
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"projection candidate authority differs: {exc}"
        ) from exc
    rosters = [row["roster_player_ids"] for row in normalized]
    if (
        _canonical(normalized) != _canonical(candidates)
        or projection.get("candidate_lineup_order_sha256") != _hash(lineup_ids)
        or projection.get("candidate_rosters_sha256") != _hash(rosters)
        or projection.get("candidate_rows_sha256") != _hash(normalized)
    ):
        _fail("projection candidate identity/hash authority differs")
    return lineup_ids, normalized


def _validate_sample_authority_v1(
    capability: Mapping[str, object], *, projection: Mapping[str, object],
) -> dict[str, object]:
    try:
        registry = contract._derive_view_registry_fixture_v1(
            projection["candidates"]
        )
        expected = contract._deterministic_equal_count_samples_fixture_v1(
            view_registry=registry,
            slate_id=str(projection["slate_id"]),
            fit_scope_id=str(projection["fit_scope_id"]),
            phase=contract.BROAD_SCREEN_PHASE,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"broad sample authority cannot be replayed: {exc}"
        ) from exc
    if (
        _canonical(capability.get("samples")) != _canonical(expected)
        or capability.get("samples_sha256") != _hash(expected)
        or expected.get("replicate_count") != 1
        or len(expected.get("replicates", [])) != 1
        or len(expected["replicates"][0].get("views", []))
        != EXACT_BROAD_VIEW_COUNT
    ):
        _fail("broad deterministic sample authority differs")
    return expected


def _validate_matrix_authority_v1(
    matrix_value: object,
    *,
    projection: Mapping[str, object],
    descriptor: Mapping[str, object],
) -> tuple[np.ndarray, dict[str, object]]:
    if not isinstance(matrix_value, np.ndarray):
        _fail("training matrix must be one numpy authority object")
    scores = np.asarray(matrix_value)
    expected_shape = [
        len(projection["candidates"]),
        EXACT_TRAINING_BLOCK_COUNT * EXACT_WORLDS_PER_BLOCK,
    ]
    if (
        scores is not matrix_value
        or scores.dtype != np.dtype(np.float64)
        or not scores.dtype.isnative
        or scores.ndim != 2
        or list(scores.shape) != expected_shape
        or not scores.flags.c_contiguous
        or scores.flags.writeable
        or projection.get("training_score_shape") != expected_shape
    ):
        _fail("training matrix read-only dtype/shape authority differs")
    try:
        retained_descriptor = worker._validate_matrix_descriptor_v1(
            descriptor,
            expected_shape=expected_shape,
            expected_matrix_sha256=projection.get(
                "training_score_matrix_sha256"
            ),
        )
        observed_descriptor = worker._matrix_descriptor_v1(
            scores,
            expected_matrix_sha256=str(
                projection["training_score_matrix_sha256"]
            ),
        )
    except worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"training matrix descriptor authority differs: {exc}"
        ) from exc
    if _canonical(retained_descriptor) != _canonical(observed_descriptor):
        _fail("training matrix bytes differ from exact capability descriptor")
    lineup_ids = [str(row["lineup_id"]) for row in projection["candidates"]]
    try:
        ledger = contract._ordered_score_row_ledger_fixture_v1(
            lineup_ids, scores
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"full score-row ledger authority differs: {exc}"
        ) from exc
    if (
        ledger["world_count"]
        != EXACT_TRAINING_BLOCK_COUNT * EXACT_WORLDS_PER_BLOCK
        or ledger["score_matrix_sha256"]
        != projection["training_score_matrix_sha256"]
        or ledger["score_matrix_sha256"] != descriptor["matrix_sha256"]
        or ledger["lineup_ids_sha256"]
        != projection["candidate_lineup_order_sha256"]
    ):
        _fail("score-row ledger does not bind projection and matrix authorities")
    return scores, ledger


def _validate_runtime_authority_v1(
    runtime_value: object, *, capability: Mapping[str, object],
) -> dict[str, object]:
    try:
        runtime = successor_runtime.validate_runtime_evidence_v1(runtime_value)
    except successor_runtime.CorpusR6CurrentBankSelectorSuccessorRuntimeV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"observed runtime authority differs: {exc}"
        ) from exc
    if (
        runtime["runtime_mode"] != successor_runtime.RUNTIME_MODE
        or runtime["command"]
        != successor_runtime.canonical_matrix_selector_command_v1()
        or runtime["process_ordinal"] != capability["process_ordinal"]
        or runtime["task_index"] != capability["source_ordinal"]
        or runtime["pid"] < 1
        or runtime["parent_pid"] < 1
        or runtime["pid"] == runtime["parent_pid"]
        or runtime["outer_launch_authority_binding_required"] is not True
    ):
        _fail("runtime process/task/capability authority differs")
    return runtime


def _validated_authorities_v1(
    *,
    matrix_capability: object,
    training_score_matrix: object,
    runtime_evidence: object,
) -> tuple[
    dict[str, object],
    dict[str, object],
    np.ndarray,
    list[str],
    list[dict[str, object]],
    list[str],
    dict[str, object],
    dict[str, object],
]:
    try:
        capability = worker.validate_matrix_capability_v1(matrix_capability)
    except worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"matrix capability authority differs: {exc}"
        ) from exc
    if capability["phase"] != contract.BROAD_SCREEN_PHASE:
        _fail("confirmation is closed for the grouped successor authority wrapper")
    if contract.WORLDS_PER_BLOCK != EXACT_WORLDS_PER_BLOCK:
        _fail("current-bank worlds-per-block contract drifted")
    projection = _mapping(
        capability["projection_scientific_binding"],
        label="scientific projection binding",
    )
    training_blocks = [str(value) for value in projection["training_blocks"]]
    expected_blocks = [
        block
        for block in contract.WORLD_BLOCKS
        if block != projection["heldout_block_label"]
    ]
    if (
        len(training_blocks) != EXACT_TRAINING_BLOCK_COUNT
        or training_blocks != expected_blocks
        or projection.get("training_world_columns_sha256")
        != contract.canonical_world_columns_sha256_v1(training_blocks)
        or _SHA256_RE.fullmatch(str(projection.get("projection_sha256", "")))
        is None
    ):
        _fail("projection block/world-column authority differs")
    lineup_ids, candidates = _validate_candidate_authority_v1(
        projection, training_blocks=training_blocks
    )
    samples = _validate_sample_authority_v1(
        capability, projection=projection
    )
    scores, full_ledger = _validate_matrix_authority_v1(
        training_score_matrix,
        projection=projection,
        descriptor=_mapping(
            capability["matrix_descriptor"], label="matrix descriptor"
        ),
    )
    runtime = _validate_runtime_authority_v1(
        runtime_evidence, capability=capability
    )
    return (
        capability,
        runtime,
        scores,
        lineup_ids,
        candidates,
        training_blocks,
        samples,
        full_ledger,
    )


def _expected_core_input_binding_v1(
    *,
    sampled_ids: Sequence[str],
    sampled_candidates: Sequence[Mapping[str, object]],
    sampled_scores: np.ndarray,
    training_blocks: Sequence[str],
) -> dict[str, object]:
    heldout = [
        block for block in contract.WORLD_BLOCKS if block not in training_blocks
    ]
    if len(heldout) != 1:
        _fail("training blocks do not imply one held-out label")
    return _with_hash({
        "ordered_sampled_lineup_ids_sha256": _hash(list(sampled_ids)),
        "sampled_candidate_rows_sha256": _hash(list(sampled_candidates)),
        "candidate_count": len(sampled_ids),
        "training_blocks": list(training_blocks),
        "heldout_block_label_only": heldout[0],
        "worlds_per_block": EXACT_WORLDS_PER_BLOCK,
        "training_score_shape": list(sampled_scores.shape),
        "training_score_matrix_sha256": successor._matrix_sha(sampled_scores),
        "input_score_matrix_object_reused": True,
        "no_persistent_full_float64_matrix_clone": True,
        "score_matrix_mutated": False,
        "heldout_score_columns_present": False,
        "uses_realized_outcomes": False,
        "caller_supplied_inputs_only": True,
        "production_authority_validated": False,
    }, field="input_binding_sha256")


def _validate_grouped_result_without_reexecution_v1(
    value: object,
    *,
    sampled_ids: Sequence[str],
    sampled_candidates: Sequence[Mapping[str, object]],
    sampled_scores: np.ndarray,
    training_blocks: Sequence[str],
) -> dict[str, object]:
    """Validate one just-produced pure result without running its kernels twice."""
    item = _mapping(value, label="grouped successor result")
    expected_fields = {
        "schema_version", "implementation", "implementation_sha256",
        "preset_registry", "preset_registry_sha256", "input_binding",
        "input_binding_sha256", "shared_preprocessing",
        "shared_preprocessing_sha256", "selector_count", "selectors",
        "selector_result_sha256s", "entry_budget", "prefix_sizes", "policy",
        "result_sha256",
    }
    if set(item) != expected_fields:
        _fail("grouped successor result fields differ")
    _require_self_hash(item, field="result_sha256", label="grouped result")
    implementation = successor.frozen_successor_implementation_v1()
    presets = successor.frozen_native_preset_registry_v1()
    expected_binding = _expected_core_input_binding_v1(
        sampled_ids=sampled_ids,
        sampled_candidates=sampled_candidates,
        sampled_scores=sampled_scores,
        training_blocks=training_blocks,
    )
    selectors = [
        _mapping(row, label=f"grouped selector[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(item.get("selectors"), label="grouped selectors")
        )
    ]
    if (
        item["schema_version"] != successor.RESULT_SCHEMA
        or _canonical(item["implementation"]) != _canonical(implementation)
        or item["implementation_sha256"]
        != implementation["implementation_sha256"]
        or _canonical(item["preset_registry"]) != _canonical(presets)
        or item["preset_registry_sha256"] != _hash(presets)
        or _canonical(item["input_binding"]) != _canonical(expected_binding)
        or item["input_binding_sha256"]
        != expected_binding["input_binding_sha256"]
        or item["selector_count"] != EXACT_SELECTOR_COUNT_PER_VIEW
        or len(selectors) != EXACT_SELECTOR_COUNT_PER_VIEW
        or item["entry_budget"] != successor.ENTRY_BUDGET
        or item["prefix_sizes"] != list(successor.PREFIX_SIZES)
        or item["policy"] != successor._FALSE_POLICY
    ):
        _fail("grouped successor implementation/input/policy binding differs")
    shared = _mapping(
        item["shared_preprocessing"], label="shared preprocessing"
    )
    if (
        item["shared_preprocessing_sha256"] != _hash(shared)
        or shared.get("no_persistent_full_float64_matrix_clone") is not True
        or shared.get("shared_preprocessing_build_count") != 1
        or shared.get("full_fit_mean_pass_count") != 1
        or shared.get("strict_gt_200_count_pass_count") != 1
        or shared.get("block_partition_build_count") != 1
        or shared.get("dense_candidate_by_world_boolean_retained") is not False
        or shared.get("inclusive_mask_build_count_by_threshold")
        != {
            str(int(threshold)): 1
            for threshold in successor.INCLUSIVE_TAIL_THRESHOLDS
        }
        or shared.get("block_slices")
        != [
            {
                "block_id": block,
                "column_start": ordinal * EXACT_WORLDS_PER_BLOCK,
                "column_stop": (ordinal + 1) * EXACT_WORLDS_PER_BLOCK,
            }
            for ordinal, block in enumerate(training_blocks)
        ]
    ):
        _fail("grouped successor shared-preprocessing evidence differs")
    candidate_by_id = {
        str(row["lineup_id"]): row for row in sampled_candidates
    }
    selector_hashes: list[str] = []
    for ordinal, (row, preset) in enumerate(zip(selectors, presets, strict=True)):
        expected_selector_fields = {
            "ordinal", "preset_id", "preset_sha256", "adapter_id",
            "parameters_sha256", "executable_fingerprint_sha256",
            "selected_canonical_indices", "selected_lineup_ids",
            "selected_lineup_ids_sha256", "selected_rosters_sha256",
            "prefixes", "compact_diagnostics", "compact_diagnostics_sha256",
            "selector_result_sha256",
        }
        if set(row) != expected_selector_fields:
            _fail(f"grouped selector[{ordinal}] fields differ")
        _require_self_hash(
            row,
            field="selector_result_sha256",
            label=f"grouped selector[{ordinal}]",
        )
        raw_indices = _sequence(
            row["selected_canonical_indices"],
            label=f"grouped selector[{ordinal}] selected indices",
        )
        if any(type(value) is not int for value in raw_indices):
            _fail(f"grouped selector[{ordinal}] selected indices differ")
        selected_indices = [int(value) for value in raw_indices]
        selected_ids = [
            str(value)
            for value in _sequence(
                row["selected_lineup_ids"],
                label=f"grouped selector[{ordinal}] selected ids",
            )
        ]
        if (
            len(selected_indices) != successor.ENTRY_BUDGET
            or len(set(selected_indices)) != successor.ENTRY_BUDGET
            or min(selected_indices, default=-1) < 0
            or max(selected_indices, default=len(sampled_ids))
            >= len(sampled_ids)
        ):
            _fail(f"grouped selector[{ordinal}] selected indices differ")
        expected_ids = [sampled_ids[index] for index in selected_indices]
        expected_rosters = [
            candidate_by_id[lineup_id]["roster_player_ids"]
            for lineup_id in selected_ids
        ]
        diagnostics = _mapping(
            row["compact_diagnostics"],
            label=f"grouped selector[{ordinal}] diagnostics",
        )
        if (
            row["ordinal"] != preset["ordinal"]
            or row["preset_id"] != preset["preset_id"]
            or row["preset_sha256"] != preset["preset_sha256"]
            or row["adapter_id"] != preset["adapter_id"]
            or row["parameters_sha256"] != preset["parameters_sha256"]
            or row["executable_fingerprint_sha256"]
            != preset["executable_fingerprint_sha256"]
            or selected_ids != expected_ids
            or row["selected_lineup_ids_sha256"] != _hash(selected_ids)
            or row["selected_rosters_sha256"] != _hash(expected_rosters)
            or row["prefixes"]
            != successor._prefixes(
                selected_ids=selected_ids, candidate_by_id=candidate_by_id
            )
            or row["compact_diagnostics_sha256"] != _hash(diagnostics)
        ):
            _fail(f"grouped selector[{ordinal}] authority binding differs")
        selector_hashes.append(str(row["selector_result_sha256"]))
    if item["selector_result_sha256s"] != selector_hashes:
        _fail("grouped selector result-hash order differs")
    return item


def _authority_cell_v1(
    *,
    view_ordinal: int,
    sample: Mapping[str, object],
    selector_result: Mapping[str, object],
    sampled_ledger: Mapping[str, object],
    candidate_by_id: Mapping[str, Mapping[str, object]],
    grouped_result_sha256: str,
) -> dict[str, object]:
    selected_ids = [str(value) for value in selector_result["selected_lineup_ids"]]
    roster_by_id = {
        lineup_id: list(candidate_by_id[lineup_id]["roster_player_ids"])
        for lineup_id in selected_ids
    }
    try:
        prefixes = contract._selection_prefixes_v1(selected_ids, roster_by_id)
        trace = contract._selection_trace_binding_v1(
            selected_lineup_ids=selected_ids,
            sampled_lineup_ids=sample["sampled_lineup_ids"],
            sampled_score_row_ledger=sampled_ledger,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
            f"authority cell cannot bind exact selected rows: {exc}"
        ) from exc
    body = {
        "schema_version": AUTHORITY_CELL_SCHEMA,
        "replicate": 0,
        "view_ordinal": view_ordinal,
        "view_id": sample["view_id"],
        "sampled_lineup_ids": list(sample["sampled_lineup_ids"]),
        "sampled_lineup_ids_sha256": sample["sampled_lineup_ids_sha256"],
        "rank_seed_sha256": sample["seed_material_sha256"],
        "preset_ordinal": selector_result["ordinal"],
        "preset_id": selector_result["preset_id"],
        "preset_sha256": selector_result["preset_sha256"],
        "adapter_id": selector_result["adapter_id"],
        "parameters_sha256": selector_result["parameters_sha256"],
        "executable_fingerprint_sha256": selector_result[
            "executable_fingerprint_sha256"
        ],
        "successor_selector_result_sha256": selector_result[
            "selector_result_sha256"
        ],
        "grouped_result_sha256": grouped_result_sha256,
        "training_score_row_ledger": dict(sampled_ledger),
        "training_score_row_ledger_sha256": _hash(sampled_ledger),
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _hash(selected_ids),
        "selected_rosters_sha256": _hash([
            roster_by_id[lineup_id] for lineup_id in selected_ids
        ]),
        "prefixes": prefixes,
        "selection_trace": trace,
        "selection_trace_sha256": _hash(trace),
        "compact_diagnostics": dict(selector_result["compact_diagnostics"]),
        "compact_diagnostics_sha256": selector_result[
            "compact_diagnostics_sha256"
        ],
    }
    return _with_hash(body, field="authority_cell_sha256")


def run_authority_bound_broad_selectors_v1(
    *,
    matrix_capability: object,
    training_score_matrix: object,
    runtime_evidence: object,
) -> dict[str, object]:
    """Run the three grouped successors once per authenticated broad view."""
    (
        capability,
        runtime,
        scores,
        lineup_ids,
        candidates,
        training_blocks,
        samples,
        full_ledger,
    ) = _validated_authorities_v1(
        matrix_capability=matrix_capability,
        training_score_matrix=training_score_matrix,
        runtime_evidence=runtime_evidence,
    )
    presets = successor.frozen_native_preset_registry_v1()
    matrix_ordinal = {
        lineup_id: ordinal for ordinal, lineup_id in enumerate(lineup_ids)
    }
    full_candidate_by_id = {
        str(row["lineup_id"]): row for row in candidates
    }
    views: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    broad_samples = samples["replicates"][0]["views"]
    for view_ordinal, sample_value in enumerate(broad_samples):
        sample = _mapping(sample_value, label=f"broad sample[{view_ordinal}]")
        sampled_ids = [str(value) for value in sample["sampled_lineup_ids"]]
        sampled_candidates = [full_candidate_by_id[value] for value in sampled_ids]
        row_ordinals = np.asarray(
            [matrix_ordinal[value] for value in sampled_ids], dtype=np.int64
        )
        # One explicit persistent copy per view.  All three selectors receive
        # this same object through the pure grouped dispatcher.
        sampled_scores = np.empty(
            (len(sampled_ids), scores.shape[1]), dtype=np.float64, order="C"
        )
        np.take(scores, row_ordinals, axis=0, out=sampled_scores)
        sampled_scores.flags.writeable = False
        try:
            grouped_raw = successor.run_grouped_native_selectors_v1(
                sampled_lineup_ids=sampled_ids,
                training_score_matrix=sampled_scores,
                candidate_rows=sampled_candidates,
                training_blocks=training_blocks,
                worlds_per_block=EXACT_WORLDS_PER_BLOCK,
                preset_registry=presets,
            )
            grouped = _validate_grouped_result_without_reexecution_v1(
                grouped_raw,
                sampled_ids=sampled_ids,
                sampled_candidates=sampled_candidates,
                sampled_scores=sampled_scores,
                training_blocks=training_blocks,
            )
        except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
                f"grouped successor execution failed: {exc}"
            ) from exc
        try:
            sampled_ledger = contract._sampled_score_row_ledger_from_full_v1(
                full_ledger, sampled_ids
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
                f"sampled score-row ledger authority differs: {exc}"
            ) from exc
        view_cells = [
            _authority_cell_v1(
                view_ordinal=view_ordinal,
                sample=sample,
                selector_result=selector_result,
                sampled_ledger=sampled_ledger,
                candidate_by_id=full_candidate_by_id,
                grouped_result_sha256=str(grouped["result_sha256"]),
            )
            for selector_result in grouped["selectors"]
        ]
        cells.extend(view_cells)
        view_body = {
            "schema_version": AUTHORITY_VIEW_SCHEMA,
            "replicate": 0,
            "view_ordinal": view_ordinal,
            "view_id": sample["view_id"],
            "source_count": sample["source_count"],
            "target_count": sample["target_count"],
            "sampled_lineup_ids_sha256": sample["sampled_lineup_ids_sha256"],
            "rank_seed_sha256": sample["seed_material_sha256"],
            "sampled_score_matrix_shape": list(sampled_scores.shape),
            "sampled_score_matrix_sha256": contract._float64_matrix_sha256_v1(
                sampled_scores, label="authority sampled matrix"
            ),
            "successor_input_matrix_sha256": grouped["input_binding"][
                "training_score_matrix_sha256"
            ],
            "sampled_score_row_ledger_sha256": _hash(sampled_ledger),
            "sampled_matrix_copy_count": 1,
            "grouped_selector_invocation_count": 1,
            "selector_count": EXACT_SELECTOR_COUNT_PER_VIEW,
            "grouped_result": grouped,
            "grouped_result_sha256": grouped["result_sha256"],
            "cells": view_cells,
            "cell_sha256s": [
                row["authority_cell_sha256"] for row in view_cells
            ],
        }
        views.append(_with_hash(view_body, field="authority_view_sha256"))

    if (
        len(views) != EXACT_BROAD_VIEW_COUNT
        or len(cells) != EXACT_BROAD_CELL_COUNT
    ):
        _fail("broad grouped view/cell lattice differs")
    wrapper_contract = frozen_authority_wrapper_v1()
    descriptor = capability["matrix_descriptor"]
    projection = capability["projection_scientific_binding"]
    authority_binding = _with_hash({
        "matrix_capability_sha256": capability["matrix_capability_sha256"],
        "projection_sha256": projection["projection_sha256"],
        "projection_scientific_binding_sha256": capability[
            "projection_scientific_binding_sha256"
        ],
        "candidate_lineup_order_sha256": projection[
            "candidate_lineup_order_sha256"
        ],
        "candidate_rosters_sha256": projection["candidate_rosters_sha256"],
        "candidate_rows_sha256": projection["candidate_rows_sha256"],
        "training_world_columns_sha256": projection[
            "training_world_columns_sha256"
        ],
        "samples_sha256": capability["samples_sha256"],
        "subsample_sha256": samples["subsample_sha256"],
        "matrix_descriptor_sha256": descriptor["matrix_descriptor_sha256"],
        "training_score_matrix_sha256": projection[
            "training_score_matrix_sha256"
        ],
        "full_score_row_ledger_sha256": _hash(full_ledger),
        "full_score_rows_sha256": full_ledger["rows_sha256"],
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "runtime_command_sha256": runtime["command_sha256"],
        "runtime_entrypoint_sha256": runtime["entrypoint_sha256"],
        "runtime_code_commit": runtime["code_commit"],
        "runtime_image_digest": runtime["image_digest"],
        "runtime_job_name": runtime["job_name"],
        "runtime_execution_id": runtime["execution_id"],
        "runtime_task_index": runtime["task_index"],
        "runtime_process_ordinal": runtime["process_ordinal"],
        "source_capability_strategy_registry_sha256": capability[
            "strategy_registry_sha256"
        ],
        "source_capability_fit_count_precharge": capability[
            "fit_count_precharge"
        ],
        "successor_broad_fit_count": EXACT_BROAD_CELL_COUNT,
        "existing_fold_receipt_compatible": False,
        "successor_process_budget_required": True,
        "authority_wrapper_sha256": wrapper_contract[
            "authority_wrapper_sha256"
        ],
        "successor_implementation_sha256": successor.frozen_successor_implementation_v1()[
            "implementation_sha256"
        ],
        "successor_preset_registry_sha256": _hash(presets),
        "capability_validated_by_existing_worker": True,
        "sample_authority_replayed_from_projection": True,
        "matrix_authority_recomputed_from_read_only_bytes": True,
        "score_row_ledger_rederived_from_matrix": True,
        "runtime_authority_validated_by_successor_runtime": True,
        "source_control_runtime_compatibility_claimed": False,
        "outer_launch_authority_binding_required": True,
    }, field="authority_binding_sha256")
    body = {
        "schema_version": AUTHORITY_RESPONSE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "training_blocks": list(training_blocks),
        "worlds_per_block": EXACT_WORLDS_PER_BLOCK,
        "authority_wrapper": wrapper_contract,
        "authority_wrapper_sha256": wrapper_contract[
            "authority_wrapper_sha256"
        ],
        "authority_binding": authority_binding,
        "authority_binding_sha256": authority_binding[
            "authority_binding_sha256"
        ],
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "full_candidate_score_row_ledger": full_ledger,
        "full_candidate_score_row_ledger_sha256": _hash(full_ledger),
        "view_count": len(views),
        "selector_count_per_view": EXACT_SELECTOR_COUNT_PER_VIEW,
        "fit_count": len(cells),
        "views": views,
        "view_sha256s": [row["authority_view_sha256"] for row in views],
        "cells": cells,
        "cell_sha256s": [row["authority_cell_sha256"] for row in cells],
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="authority_response_sha256")


def validate_authority_bound_broad_selector_response_v1(
    value: object,
    *,
    matrix_capability: object,
    training_score_matrix: object,
    runtime_evidence: object,
) -> dict[str, object]:
    """Replay all pure work and require one byte-exact authority response."""
    item = _mapping(value, label="successor authority response")
    _canonical(item)
    _require_self_hash(
        item,
        field="authority_response_sha256",
        label="successor authority response",
    )
    expected = run_authority_bound_broad_selectors_v1(
        matrix_capability=matrix_capability,
        training_score_matrix=training_score_matrix,
        runtime_evidence=runtime_evidence,
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor authority response differs from exact canonical replay")
    return expected


__all__ = [
    "AUTHORITY_RESPONSE_SCHEMA",
    "AUTHORITY_WRAPPER_ID",
    "AUTHORITY_WRAPPER_SCHEMA",
    "CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error",
    "EXACT_BROAD_CELL_COUNT",
    "EXACT_BROAD_VIEW_COUNT",
    "EXACT_SELECTOR_COUNT_PER_VIEW",
    "EXACT_WORLDS_PER_BLOCK",
    "EXPECTED_AUTHORITY_WRAPPER_SHA256",
    "frozen_authority_wrapper_v1",
    "run_authority_bound_broad_selectors_v1",
    "validate_authority_bound_broad_selector_response_v1",
]
