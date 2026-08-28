"""Lean process and fold-receipt adapter for grouped current-bank selectors.

The authority wrapper produces three native selector results for each of the
eight broad views.  The active crossed-screen process budget and fold receipt
cannot carry those results: they precharge the control registry, whose fit
lattice is intentionally different.  This module defines a separate,
broad-only 24-fit boundary without changing or weakening the active contract.

The adapter is deliberately transport-free.  It validates and binds the
existing scientific matrix capability, the distinct grouped-successor runtime
observation and a generation-pinned outer run-authorization identity, but it
does not exact-open a Cloud Run task manifest, spawn a process, publish an
object or attest terminal execution.  The companion successor cloud module
performs those operations and keeps this fold receipt nested as non-publishing
scientific child evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_selection_fold_worker_v1 as worker,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_runtime_v1 as successor_runtime,
)


ADAPTER_CONTRACT_ID: Final = (
    "20260828-r6-current-bank-grouped-selector-process-adapter-v1"
)
PROCESS_BUDGET_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-process-budget/v1"
)
MATRIX_CHILD_CAPABILITY_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-matrix-child-capability/v1"
)
OUTER_LAUNCH_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-outer-launch-envelope/v1"
)
FOLD_RECEIPT_SCHEMA: Final = (
    "corpus-r6-current-bank-grouped-selector-fold-receipt/v1"
)
PROCESS_ROLE: Final = "grouped-successor-broad-fold-selector"
EXACT_VIEW_COUNT: Final = authority.EXACT_BROAD_VIEW_COUNT
EXACT_SELECTORS_PER_VIEW: Final = authority.EXACT_SELECTOR_COUNT_PER_VIEW
EXACT_FIT_COUNT: Final = authority.EXACT_BROAD_CELL_COUNT
MAX_BYTES_PER_CELL: Final = 2_000_000
MATRIX_RESPONSE_BYTE_CEILING: Final = EXACT_FIT_COUNT * MAX_BYTES_PER_CELL
FOLD_RECEIPT_BYTE_CEILING: Final = 64_000_000

_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "heldout_artifact_identity_present": False,
    "heldout_artifact_body_present": False,
    "corpus_regeneration_performed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "publication_authority": False,
    "promotion_authority": False,
    "decision_authority": False,
    "terminal_execution_attestation_present": False,
    "dispatcher_wiring_authority_present": False,
}


class CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(ValueError):
    """The isolated 24-fit process or receipt boundary failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            "value is not canonical finite JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} cannot already be present")
    body[field] = _hash(body)
    return body


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    if value.get(field) != _hash({
        key: item for key, item in value.items() if key != field
    }):
        _fail(f"{label} self hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            str(exc)
        ) from exc


def _bind(
    body: Mapping[str, object], identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            body, identity, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            str(exc)
        ) from exc


def _source_authorities_v1(
    *,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    try:
        source_budget = contract.validate_process_budget_v1(
            source_process_budget
        )
        capability = worker.validate_matrix_capability_v1(matrix_capability)
    except (
        contract.CorpusR6CurrentBankCrossedScreenContractV1Error,
        worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error,
    ) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            f"source control authority differs: {exc}"
        ) from exc
    source_identity = _bind(
        source_budget,
        source_process_budget_identity,
        label="source control process budget",
    )
    source_fits = int(source_budget["compute_fit_precharge"])
    if (
        source_budget["process_role"] != "broad-fold-selector"
        or source_budget["phase"] != contract.BROAD_SCREEN_PHASE
        or source_budget["source_ordinal"] != capability["source_ordinal"]
        or source_budget["process_ordinal"] != capability["process_ordinal"]
        or source_budget["write_object_count"] != 0
        or source_budget["write_allowlist"] != []
        or source_budget["child_output_byte_ceiling"]
        < FOLD_RECEIPT_BYTE_CEILING
        or capability["phase"] != contract.BROAD_SCREEN_PHASE
        or capability["fit_count_precharge"] != source_fits
        or source_fits <= EXACT_FIT_COUNT
    ):
        _fail("source control phase/process/fit authority differs")
    return source_budget, source_identity, capability


def _budget_projection_binding_v1(
    *,
    matrix_capability: object | None,
    source_projection: object | None,
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Return the immutable projection facts available before matrix creation."""
    if (matrix_capability is None) == (source_projection is None):
        _fail("exactly one matrix capability or source projection is required")
    if matrix_capability is not None:
        try:
            capability = worker.validate_matrix_capability_v1(matrix_capability)
        except worker.CorpusR6CurrentBankSelectionFoldWorkerV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
                f"source control authority differs: {exc}"
            ) from exc
        scientific = _mapping(
            capability["projection_scientific_binding"],
            label="source scientific projection",
        )
        binding = {
            "source_ordinal": capability["source_ordinal"],
            "fold_ordinal": capability["fold_ordinal"],
            "process_ordinal": capability["process_ordinal"],
            "projection_sha256": scientific["projection_sha256"],
            "slate_id": scientific["slate_id"],
            "fit_scope_id": scientific["fit_scope_id"],
            "training_blocks": list(scientific["training_blocks"]),
            "heldout_block": scientific["heldout_block_label"],
            "training_score_matrix_sha256": scientific[
                "training_score_matrix_sha256"
            ],
        }
        return binding, capability
    try:
        projection = contract.validate_narrow_projection_v1(source_projection)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            f"source projection authority differs: {exc}"
        ) from exc
    heldout = str(projection["heldout_block"])
    fold = list(contract.WORLD_BLOCKS).index(heldout)
    return {
        "source_ordinal": None,
        "fold_ordinal": fold,
        "process_ordinal": None,
        "projection_sha256": projection["projection_sha256"],
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "training_blocks": list(projection["training_blocks"]),
        "heldout_block": heldout,
        "training_score_matrix_sha256": projection[
            "expected_training_score_matrix_sha256"
        ],
    }, None


def compile_successor_process_budget_v1(
    *,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object | None = None,
    source_projection: object | None = None,
) -> dict[str, object]:
    """Adapt exact control reads while replacing its fit charge with 24.

    ``source_projection`` is the preparation-time path: it lets the exact
    budget be published before the score matrix exists.  ``matrix_capability``
    is the execution-time replay path.  Both compile byte-identical budgets.
    """
    binding, capability = _budget_projection_binding_v1(
        matrix_capability=matrix_capability,
        source_projection=source_projection,
    )
    try:
        source_budget = contract.validate_process_budget_v1(
            source_process_budget
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            f"source control authority differs: {exc}"
        ) from exc
    source_identity = _bind(
        source_budget,
        source_process_budget_identity,
        label="source control process budget",
    )
    source = int(source_budget["source_ordinal"])
    process = int(source_budget["process_ordinal"])
    fold = process - source * contract.FOLDS_PER_SLATE
    source_fits = int(source_budget["compute_fit_precharge"])
    if (
        source_budget["process_role"] != "broad-fold-selector"
        or source_budget["phase"] != contract.BROAD_SCREEN_PHASE
        or fold != binding["fold_ordinal"]
        or not 0 <= fold < contract.FOLDS_PER_SLATE
        or binding["source_ordinal"] not in {None, source}
        or binding["process_ordinal"] not in {None, process}
        or source_budget["write_object_count"] != 0
        or source_budget["write_allowlist"] != []
        or source_budget["child_output_byte_ceiling"]
        < FOLD_RECEIPT_BYTE_CEILING
        or source_fits <= EXACT_FIT_COUNT
        or (
            capability is not None
            and (
                capability["phase"] != contract.BROAD_SCREEN_PHASE
                or capability["fit_count_precharge"] != source_fits
            )
        )
    ):
        _fail("source control phase/process/fit authority differs")
    body = {
        "schema_version": PROCESS_BUDGET_SCHEMA,
        "adapter_contract_id": ADAPTER_CONTRACT_ID,
        "source_contract_id": contract.CONTRACT_ID,
        "process_role": PROCESS_ROLE,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": source,
        "fold_ordinal": fold,
        "process_ordinal": process,
        "slate_id": binding["slate_id"],
        "fit_scope_id": binding["fit_scope_id"],
        "training_blocks": binding["training_blocks"],
        "heldout_block": binding["heldout_block"],
        "source_projection_sha256": binding["projection_sha256"],
        "source_training_score_matrix_sha256": binding[
            "training_score_matrix_sha256"
        ],
        "source_control_process_budget_identity": source_identity,
        "source_control_process_budget_sha256": source_budget[
            "process_budget_sha256"
        ],
        "source_control_fit_precharge": source_budget[
            "compute_fit_precharge"
        ],
        "read_allowlist": list(source_budget["read_allowlist"]),
        "read_object_count": source_budget["read_object_count"],
        "read_byte_ceiling": source_budget["read_byte_ceiling"],
        "write_allowlist": [],
        "write_object_count": 0,
        "write_byte_ceiling": 0,
        "matrix_input_transport": "inherited-read-only-local-matrix",
        "matrix_response_byte_ceiling": MATRIX_RESPONSE_BYTE_CEILING,
        "fold_receipt_byte_ceiling": FOLD_RECEIPT_BYTE_CEILING,
        "compute_fit_precharge": EXACT_FIT_COUNT,
        "view_count_precharge": EXACT_VIEW_COUNT,
        "selector_count_per_view_precharge": EXACT_SELECTORS_PER_VIEW,
        "all_block_fit_count": 0,
        "broad_only": True,
        "confirmation_supported": False,
        "source_control_receipt_compatible": False,
        "source_control_fit_parity_claimed": False,
        "current_generation_lookup_allowed": False,
        "endpoint_override_allowed": False,
        "environment_redirect_allowed": False,
        "git_ref_redirect_allowed": False,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="successor_process_budget_sha256")


def validate_successor_process_budget_v1(
    value: object,
    *,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object | None = None,
    source_projection: object | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="successor process budget")
    _self_hash(
        item,
        field="successor_process_budget_sha256",
        label="successor process budget",
    )
    expected = compile_successor_process_budget_v1(
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
        source_projection=source_projection,
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor process budget differs from exact source adaptation")
    return expected


def build_successor_matrix_child_capability_v1(
    *,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    budget = validate_successor_process_budget_v1(
        successor_process_budget,
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
    )
    budget_identity = _bind(
        budget,
        successor_process_budget_identity,
        label="successor process budget",
    )
    _, _, source_capability = _source_authorities_v1(
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
    )
    launch_identity = _identity(
        launch_intent_identity, label="successor outer launch intent"
    )
    projection = source_capability["projection_scientific_binding"]
    wrapper_contract = authority.frozen_authority_wrapper_v1()
    presets = successor.frozen_native_preset_registry_v1()
    body = {
        "schema_version": MATRIX_CHILD_CAPABILITY_SCHEMA,
        "adapter_contract_id": ADAPTER_CONTRACT_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": source_capability["source_ordinal"],
        "fold_ordinal": source_capability["fold_ordinal"],
        "process_ordinal": source_capability["process_ordinal"],
        "slate_id": projection["slate_id"],
        "fit_scope_id": projection["fit_scope_id"],
        "training_blocks": list(projection["training_blocks"]),
        "heldout_block": projection["heldout_block_label"],
        "source_matrix_capability_sha256": source_capability[
            "matrix_capability_sha256"
        ],
        "source_projection_scientific_binding_sha256": source_capability[
            "projection_scientific_binding_sha256"
        ],
        "source_samples_sha256": source_capability["samples_sha256"],
        "source_matrix_descriptor_sha256": source_capability[
            "matrix_descriptor"
        ]["matrix_descriptor_sha256"],
        "successor_process_budget_identity": budget_identity,
        "successor_process_budget_sha256": budget[
            "successor_process_budget_sha256"
        ],
        "launch_intent_identity": launch_identity,
        "outer_launch_authority_binding_required": True,
        "runtime_mode": successor_runtime.RUNTIME_MODE,
        "authority_wrapper_sha256": wrapper_contract[
            "authority_wrapper_sha256"
        ],
        "successor_implementation_sha256": (
            successor.frozen_successor_implementation_v1()[
                "implementation_sha256"
            ]
        ),
        "successor_preset_registry_sha256": _hash(presets),
        "view_count": EXACT_VIEW_COUNT,
        "selector_count_per_view": EXACT_SELECTORS_PER_VIEW,
        "fit_count_precharge": EXACT_FIT_COUNT,
        "source_control_fit_precharge": budget[
            "source_control_fit_precharge"
        ],
        "source_control_receipt_compatible": False,
        "source_control_fit_parity_claimed": False,
        "matrix_bytes_embedded": False,
        "inherited_local_matrix_required": True,
        "heldout_artifact_addressable": False,
        "dispatcher_wiring_authority_required": True,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="successor_matrix_child_capability_sha256")


def validate_successor_matrix_child_capability_v1(
    value: object,
    *,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="successor matrix-child capability")
    _self_hash(
        item,
        field="successor_matrix_child_capability_sha256",
        label="successor matrix-child capability",
    )
    expected = build_successor_matrix_child_capability_v1(
        successor_process_budget=successor_process_budget,
        successor_process_budget_identity=successor_process_budget_identity,
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
        launch_intent_identity=launch_intent_identity,
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor matrix-child capability differs from exact replay")
    return expected


def build_successor_outer_launch_envelope_v1(
    *,
    successor_capability: object,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    runtime_evidence: object,
    authority_response: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    capability = _mapping(
        successor_capability, label="successor matrix-child capability"
    )
    _self_hash(
        capability,
        field="successor_matrix_child_capability_sha256",
        label="successor matrix-child capability",
    )
    budget = _mapping(
        successor_process_budget, label="successor process budget"
    )
    _self_hash(
        budget,
        field="successor_process_budget_sha256",
        label="successor process budget",
    )
    budget_identity = _bind(
        budget,
        successor_process_budget_identity,
        label="successor process budget",
    )
    launch_identity = _identity(
        launch_intent_identity, label="successor outer launch intent"
    )
    try:
        runtime = successor_runtime.validate_runtime_evidence_v1(
            runtime_evidence
        )
    except successor_runtime.CorpusR6CurrentBankSelectorSuccessorRuntimeV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            f"matrix-child runtime authority differs: {exc}"
        ) from exc
    response = _mapping(authority_response, label="successor authority response")
    _self_hash(
        response,
        field="authority_response_sha256",
        label="successor authority response",
    )
    response_bytes = len(_canonical(response))
    response_binding = _mapping(
        response.get("authority_binding"),
        label="successor response authority binding",
    )
    if (
        capability.get("schema_version") != MATRIX_CHILD_CAPABILITY_SCHEMA
        or capability.get("adapter_contract_id") != ADAPTER_CONTRACT_ID
        or capability.get("phase") != contract.BROAD_SCREEN_PHASE
        or capability.get("view_count") != EXACT_VIEW_COUNT
        or capability.get("selector_count_per_view")
        != EXACT_SELECTORS_PER_VIEW
        or capability.get("fit_count_precharge") != EXACT_FIT_COUNT
        or capability.get("source_control_receipt_compatible") is not False
        or capability.get("source_control_fit_parity_claimed") is not False
        or capability.get("dispatcher_wiring_authority_required") is not True
        or capability.get("policy") != _POLICY
        or budget.get("schema_version") != PROCESS_BUDGET_SCHEMA
        or budget.get("adapter_contract_id") != ADAPTER_CONTRACT_ID
        or budget.get("process_role") != PROCESS_ROLE
        or budget.get("phase") != contract.BROAD_SCREEN_PHASE
        or capability.get("successor_process_budget_identity")
        != budget_identity
        or capability.get("successor_process_budget_sha256")
        != budget["successor_process_budget_sha256"]
        or capability.get("launch_intent_identity") != launch_identity
        or budget.get("compute_fit_precharge") != EXACT_FIT_COUNT
        or budget.get("view_count_precharge") != EXACT_VIEW_COUNT
        or budget.get("selector_count_per_view_precharge")
        != EXACT_SELECTORS_PER_VIEW
        or budget.get("matrix_response_byte_ceiling")
        != MATRIX_RESPONSE_BYTE_CEILING
        or budget.get("fold_receipt_byte_ceiling")
        != FOLD_RECEIPT_BYTE_CEILING
        or budget.get("source_control_receipt_compatible") is not False
        or budget.get("source_control_fit_parity_claimed") is not False
        or budget.get("policy") != _POLICY
        or runtime["runtime_mode"] != successor_runtime.RUNTIME_MODE
        or runtime["task_index"] != capability["source_ordinal"]
    ):
        _fail("successor launch capability/budget/runtime binding differs")
    if (
        runtime["process_ordinal"] != capability["process_ordinal"]
        or response.get("phase") != contract.BROAD_SCREEN_PHASE
        or response.get("source_ordinal") != capability["source_ordinal"]
        or response.get("fold_ordinal") != capability["fold_ordinal"]
        or response.get("process_ordinal") != capability["process_ordinal"]
        or response.get("slate_id") != capability["slate_id"]
        or response.get("fit_scope_id") != capability["fit_scope_id"]
        or response.get("runtime_evidence_sha256")
        != runtime["runtime_evidence_sha256"]
        or response.get("authority_wrapper_sha256")
        != capability["authority_wrapper_sha256"]
        or response_binding.get("matrix_capability_sha256")
        != capability["source_matrix_capability_sha256"]
        or response_binding.get("successor_broad_fit_count")
        != EXACT_FIT_COUNT
        or response_binding.get("existing_fold_receipt_compatible") is not False
        or response.get("fit_count") != EXACT_FIT_COUNT
        or response.get("view_count") != EXACT_VIEW_COUNT
        or response.get("selector_count_per_view")
        != EXACT_SELECTORS_PER_VIEW
        or response_bytes < 1
        or response_bytes > budget["matrix_response_byte_ceiling"]
    ):
        _fail("successor response/runtime/capability binding differs")
    body = {
        "schema_version": OUTER_LAUNCH_ENVELOPE_SCHEMA,
        "adapter_contract_id": ADAPTER_CONTRACT_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "launch_intent_identity": launch_identity,
        "outer_launch_authority_identity": launch_identity,
        "outer_launch_authority_binding_required": True,
        "outer_launch_identity_content_pinned": True,
        "successor_process_budget_identity": budget_identity,
        "successor_process_budget_sha256": budget[
            "successor_process_budget_sha256"
        ],
        "successor_matrix_child_capability_sha256": capability[
            "successor_matrix_child_capability_sha256"
        ],
        "source_matrix_capability_sha256": capability[
            "source_matrix_capability_sha256"
        ],
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "runtime_evidence_strength": (
            "process-environment-observation-plus-content-pinned-launch-intent"
        ),
        "runtime_code_commit": runtime["code_commit"],
        "runtime_image_digest": runtime["image_digest"],
        "runtime_job_name": runtime["job_name"],
        "runtime_execution_id": runtime["execution_id"],
        "runtime_task_index": runtime["task_index"],
        "runtime_process_ordinal": runtime["process_ordinal"],
        "authority_response_sha256": response["authority_response_sha256"],
        "authority_response_bytes": response_bytes,
        "fit_count": EXACT_FIT_COUNT,
        "terminal_execution_attestation_required": True,
        "terminal_execution_attestation_present": False,
        "dispatcher_wiring_authority_required": True,
        "dispatcher_wiring_authority_present": False,
        "publication_authority": False,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="outer_launch_envelope_sha256")


def validate_successor_outer_launch_envelope_v1(
    value: object,
    *,
    successor_capability: object,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    runtime_evidence: object,
    authority_response: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="successor outer launch envelope")
    _self_hash(
        item,
        field="outer_launch_envelope_sha256",
        label="successor outer launch envelope",
    )
    expected = build_successor_outer_launch_envelope_v1(
        successor_capability=successor_capability,
        successor_process_budget=successor_process_budget,
        successor_process_budget_identity=successor_process_budget_identity,
        runtime_evidence=runtime_evidence,
        authority_response=authority_response,
        launch_intent_identity=launch_intent_identity,
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor outer launch envelope differs from exact replay")
    return expected


def build_successor_broad_fold_receipt_v1(
    *,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object,
    training_score_matrix: object,
    runtime_evidence: object,
    authority_response: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    """Assemble one non-publishable 24-fit receipt for one slate/fold."""
    budget = validate_successor_process_budget_v1(
        successor_process_budget,
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
    )
    capability = build_successor_matrix_child_capability_v1(
        successor_process_budget=budget,
        successor_process_budget_identity=successor_process_budget_identity,
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
        launch_intent_identity=launch_intent_identity,
    )
    try:
        response = authority.validate_authority_bound_broad_selector_response_v1(
            authority_response,
            matrix_capability=matrix_capability,
            training_score_matrix=training_score_matrix,
            runtime_evidence=runtime_evidence,
        )
    except authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error(
            f"successor authority response differs: {exc}"
        ) from exc
    launch_envelope = build_successor_outer_launch_envelope_v1(
        successor_capability=capability,
        successor_process_budget=budget,
        successor_process_budget_identity=successor_process_budget_identity,
        runtime_evidence=runtime_evidence,
        authority_response=response,
        launch_intent_identity=launch_intent_identity,
    )
    cells = [
        _mapping(row, label=f"successor authority cell[{index}]")
        for index, row in enumerate(
            _sequence(response["cells"], label="successor authority cells")
        )
    ]
    if (
        len(cells) != EXACT_FIT_COUNT
        or response["cell_sha256s"]
        != [row["authority_cell_sha256"] for row in cells]
        or len(set(response["cell_sha256s"])) != EXACT_FIT_COUNT
    ):
        _fail("successor fold cell lattice differs")
    budget_identity = _bind(
        budget,
        successor_process_budget_identity,
        label="successor process budget",
    )
    body = {
        "schema_version": FOLD_RECEIPT_SCHEMA,
        "adapter_contract_id": ADAPTER_CONTRACT_ID,
        "source_contract_id": contract.CONTRACT_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": capability["source_ordinal"],
        "fold_ordinal": capability["fold_ordinal"],
        "process_ordinal": capability["process_ordinal"],
        "slate_id": capability["slate_id"],
        "fit_scope_id": capability["fit_scope_id"],
        "training_blocks": capability["training_blocks"],
        "heldout_block": capability["heldout_block"],
        "successor_matrix_child_capability": capability,
        "successor_matrix_child_capability_sha256": capability[
            "successor_matrix_child_capability_sha256"
        ],
        "successor_process_budget_identity": budget_identity,
        "successor_process_budget_sha256": budget[
            "successor_process_budget_sha256"
        ],
        "source_control_process_budget_identity": budget[
            "source_control_process_budget_identity"
        ],
        "source_control_fit_precharge": budget[
            "source_control_fit_precharge"
        ],
        "source_control_receipt_compatible": False,
        "source_control_fit_parity_claimed": False,
        "outer_launch_envelope": launch_envelope,
        "outer_launch_envelope_sha256": launch_envelope[
            "outer_launch_envelope_sha256"
        ],
        "authority_response": response,
        "authority_response_sha256": response[
            "authority_response_sha256"
        ],
        "authority_response_bytes": len(_canonical(response)),
        "full_candidate_score_row_ledger_sha256": response[
            "full_candidate_score_row_ledger_sha256"
        ],
        "view_count": EXACT_VIEW_COUNT,
        "selector_count_per_view": EXACT_SELECTORS_PER_VIEW,
        "fit_count": EXACT_FIT_COUNT,
        "view_sha256s": list(response["view_sha256s"]),
        "cell_sha256s": list(response["cell_sha256s"]),
        "cells_sha256": _hash(cells),
        "broad_only": True,
        "confirmation_supported": False,
        "folds_assembled": 1,
        "slate_fold_count_required_for_downstream_assembly": (
            contract.FOLDS_PER_SLATE
        ),
        "dispatcher_wiring_authority_required": True,
        "terminal_execution_attestation_required": True,
        "publication_authority": False,
        "policy": dict(_POLICY),
    }
    receipt = _with_hash(body, field="successor_fold_receipt_sha256")
    if len(_canonical(receipt)) > budget["fold_receipt_byte_ceiling"]:
        _fail("successor fold receipt exceeds precharged byte ceiling")
    return receipt


def validate_successor_broad_fold_receipt_v1(
    value: object,
    *,
    successor_process_budget: object,
    successor_process_budget_identity: object,
    source_process_budget: object,
    source_process_budget_identity: object,
    matrix_capability: object,
    training_score_matrix: object,
    runtime_evidence: object,
    authority_response: object,
    launch_intent_identity: object,
) -> dict[str, object]:
    item = _mapping(value, label="successor broad fold receipt")
    _self_hash(
        item,
        field="successor_fold_receipt_sha256",
        label="successor broad fold receipt",
    )
    expected = build_successor_broad_fold_receipt_v1(
        successor_process_budget=successor_process_budget,
        successor_process_budget_identity=successor_process_budget_identity,
        source_process_budget=source_process_budget,
        source_process_budget_identity=source_process_budget_identity,
        matrix_capability=matrix_capability,
        training_score_matrix=training_score_matrix,
        runtime_evidence=runtime_evidence,
        authority_response=authority_response,
        launch_intent_identity=launch_intent_identity,
    )
    if _canonical(item) != _canonical(expected):
        _fail("successor broad fold receipt differs from exact replay")
    return expected


__all__ = [
    "ADAPTER_CONTRACT_ID",
    "EXACT_FIT_COUNT",
    "EXACT_SELECTORS_PER_VIEW",
    "EXACT_VIEW_COUNT",
    "FOLD_RECEIPT_BYTE_CEILING",
    "FOLD_RECEIPT_SCHEMA",
    "MATRIX_CHILD_CAPABILITY_SCHEMA",
    "MATRIX_RESPONSE_BYTE_CEILING",
    "OUTER_LAUNCH_ENVELOPE_SCHEMA",
    "PROCESS_BUDGET_SCHEMA",
    "PROCESS_ROLE",
    "CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error",
    "build_successor_broad_fold_receipt_v1",
    "build_successor_matrix_child_capability_v1",
    "build_successor_outer_launch_envelope_v1",
    "compile_successor_process_budget_v1",
    "validate_successor_broad_fold_receipt_v1",
    "validate_successor_matrix_child_capability_v1",
    "validate_successor_outer_launch_envelope_v1",
    "validate_successor_process_budget_v1",
]
