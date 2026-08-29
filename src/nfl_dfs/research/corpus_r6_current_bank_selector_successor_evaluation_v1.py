"""Held-out evaluation and terminal aggregation for selector successors.

This is deliberately a successor-native contract.  It consumes the five-fold
``grouped-selector-slate-result`` and never adapts that result to the frozen
64-fit crossed-screen selection receipt.  The numerical scoring laws are the
same outcome-blind held-out laws used by the control, which makes the resulting
coordinates comparable without claiming schema or execution parity.

The durable coordinate is ``(view, selector identity, entry budget)``.  Entry
budget is data, not a module constant: the current grouped result supplies the
exact 4/14/80 prefixes, while authority-bound rank continuations and diversity
challengers can supply distinct 80/100/150 books through the same prefix
contract.  Only 80/100/150 books are eligible for the terminal finalist root.

No function in this module can read an object store, invoke a selector, read a
realized outcome, or mutate production state.  Callers must exact-reopen the
selection/projection/world authorities and may publish the returned canonical
objects only with a create-once transport.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from hashlib import sha256
import re
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as selection_cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


EVALUATION_FOLD_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluation-fold/v1"
)
EVALUATION_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluation-result/v1"
)
EVALUATION_EXECUTION_BINDING_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-evaluation-execution-binding/v1"
)
TERMINAL_EXECUTION_BINDING_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-terminal-execution-binding/v1"
)
BOOK_METRIC_ROW_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-book-metric-row/v1"
)
SELECTOR_COORDINATE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-coordinate/v1"
)
PAIRING_COORDINATE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-pairing-coordinate/v1"
)
TERMINAL_AGGREGATE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-terminal-aggregate/v1"
)
AGGREGATE_METRIC_ROW_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-aggregate-metric-row/v1"
)
FINALIST_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-finalist/v1"
)

SUPPORTED_ENTRY_BUDGETS: Final = (4, 14, 80, 100, 150)
FINALIST_ENTRY_BUDGETS: Final = (80, 100, 150)
DECISION_METRIC_STEMS: Final = (
    "mean_heldout_expected_book_max_micro",
    "mean_heldout_p_max_gt_200",
    "mean_heldout_p_max_gt_220",
    "mean_heldout_p_max_gt_230",
    "mean_heldout_participation_ratio_gt_220_micro",
)
EXPECTED_FOLD_CELL_COUNT: Final = adapter.EXACT_FIT_COUNT
EXPECTED_FOLDS_PER_SLATE: Final = contract.FOLDS_PER_SLATE
EXPECTED_PANEL_SLATE_COUNT: Final = contract.PANEL_SLATE_COUNT
EXPECTED_COMPLETE_CELL_COUNT: Final = (
    EXPECTED_PANEL_SLATE_COUNT * EXPECTED_FOLDS_PER_SLATE
)

_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "heldout_simulated_scoring_performed": True,
    "selector_callable_present": False,
    "source_control_receipt_compatibility_claimed": False,
    "source_control_evaluator_compatibility_claimed": False,
    "corpus_regeneration_performed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
}


class CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(ValueError):
    """The successor held-out or terminal authority failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = _hash(body)
    return body


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    digest = _digest(value.get(field), label=f"{label} {field}")
    if digest != _hash({key: item for key, item in value.items() if key != field}):
        _fail(f"{label} self hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return contract._safe_object_identity(value, label=label)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc


def _bind(
    value: Mapping[str, object], identity_value: object, *, label: str,
) -> dict[str, object]:
    try:
        return contract._bind_canonical_body_to_identity_v1(
            value, identity_value, label=label
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc


def _profile_fields(view_id: str) -> tuple[str, int, str]:
    try:
        return contract._view_profile_fields_v1(view_id)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc


def build_evaluation_execution_binding_v1(
    *, source_ordinal: int, slate_id: str, task_manifest_identity: object,
    process_budget_identity: object, runtime_evidence: object,
) -> dict[str, object]:
    """Bind an evaluator result to one separately observed cloud process."""
    runtime = _mapping(runtime_evidence, label="successor evaluator runtime evidence")
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < EXPECTED_PANEL_SLATE_COUNT
        or type(slate_id) is not str
        or not slate_id
        or type(runtime.get("runtime_evidence_sha256")) is not str
    ):
        _fail("successor evaluator execution coordinate differs")
    _self_hash(
        runtime,
        field="runtime_evidence_sha256",
        label="successor evaluator runtime evidence",
    )
    body = {
        "schema_version": EVALUATION_EXECUTION_BINDING_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "task_manifest_identity": _identity(
            task_manifest_identity, label="successor evaluator task manifest"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="successor evaluator process budget"
        ),
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "terminal_cloud_execution_attestation_present": False,
        "publication_authority": True,
        "source_control_evaluator_compatibility_claimed": False,
    }
    return _with_hash(body, field="evaluation_execution_binding_sha256")


def validate_evaluation_execution_binding_v1(value: object) -> dict[str, object]:
    binding = _mapping(value, label="successor evaluation execution binding")
    _self_hash(
        binding,
        field="evaluation_execution_binding_sha256",
        label="successor evaluation execution binding",
    )
    expected = build_evaluation_execution_binding_v1(
        source_ordinal=int(binding.get("source_ordinal", -1)),
        slate_id=str(binding.get("slate_id", "")),
        task_manifest_identity=binding.get("task_manifest_identity"),
        process_budget_identity=binding.get("process_budget_identity"),
        runtime_evidence=binding.get("runtime_evidence"),
    )
    if _canonical(binding) != _canonical(expected):
        _fail("successor evaluation execution binding replay differs")
    return expected


def build_terminal_execution_binding_v1(
    *, terminal_manifest_identity: object, process_budget_identity: object,
    runtime_evidence: object,
) -> dict[str, object]:
    """Bind the terminal bytes to the one observed aggregate process."""
    runtime = _mapping(runtime_evidence, label="successor terminal runtime evidence")
    _self_hash(
        runtime,
        field="runtime_evidence_sha256",
        label="successor terminal runtime evidence",
    )
    return _with_hash({
        "schema_version": TERMINAL_EXECUTION_BINDING_SCHEMA,
        "terminal_manifest_identity": _identity(
            terminal_manifest_identity, label="successor terminal manifest"
        ),
        "process_budget_identity": _identity(
            process_budget_identity, label="successor terminal process budget"
        ),
        "runtime_evidence": runtime,
        "runtime_evidence_sha256": runtime["runtime_evidence_sha256"],
        "terminal_cloud_execution_attestation_present": False,
        "publication_authority": True,
        "source_control_aggregate_compatibility_claimed": False,
    }, field="terminal_execution_binding_sha256")


def validate_terminal_execution_binding_v1(value: object) -> dict[str, object]:
    binding = _mapping(value, label="successor terminal execution binding")
    _self_hash(
        binding,
        field="terminal_execution_binding_sha256",
        label="successor terminal execution binding",
    )
    expected = build_terminal_execution_binding_v1(
        terminal_manifest_identity=binding.get("terminal_manifest_identity"),
        process_budget_identity=binding.get("process_budget_identity"),
        runtime_evidence=binding.get("runtime_evidence"),
    )
    if _canonical(binding) != _canonical(expected):
        _fail("successor terminal execution binding replay differs")
    return expected


def _validate_prefixes_v1(
    *, cell: Mapping[str, object], candidate_by_id: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    selected = [
        str(value) for value in _sequence(
            cell.get("selected_lineup_ids"), label="successor selected lineup IDs"
        )
    ]
    if (
        not selected
        or len(selected) != len(set(selected))
        or not set(selected) <= set(candidate_by_id)
        or cell.get("selected_lineup_ids_sha256") != _hash(selected)
    ):
        _fail("successor selected lineup authority differs")
    rosters = [list(candidate_by_id[lineup_id]["roster_player_ids"]) for lineup_id in selected]
    if cell.get("selected_rosters_sha256") != _hash(rosters):
        _fail("successor selected roster authority differs")
    raw_prefixes = [
        _mapping(row, label=f"successor prefix[{index}]")
        for index, row in enumerate(
            _sequence(cell.get("prefixes"), label="successor prefixes")
        )
    ]
    sizes: list[int] = []
    for index, row in enumerate(raw_prefixes):
        if set(row) != {
            "prefix_size", "selected_lineup_ids_sha256",
            "selected_rosters_sha256", "prefix_payload_sha256",
        }:
            _fail(f"successor prefix[{index}] fields differ")
        size = row.get("prefix_size")
        if type(size) is not int or size not in SUPPORTED_ENTRY_BUDGETS:
            _fail(f"successor prefix[{index}] entry budget differs")
        prefix_ids = selected[:size]
        prefix_rosters = rosters[:size]
        if (
            len(prefix_ids) != size
            or row["selected_lineup_ids_sha256"] != _hash(prefix_ids)
            or row["selected_rosters_sha256"] != _hash(prefix_rosters)
            or row["prefix_payload_sha256"] != _hash({
                "selected_lineup_ids": prefix_ids,
                "selected_rosters": prefix_rosters,
            })
        ):
            _fail(f"successor prefix[{index}] exact payload differs")
        sizes.append(size)
    if not sizes or sizes != sorted(set(sizes)) or sizes[-1] != len(selected):
        _fail("successor prefix lattice must end at the exact ranked depth")
    return raw_prefixes


def _selector_coordinate_v1(cell: Mapping[str, object]) -> dict[str, object]:
    """Normalize current and future authority cells without fixing book size."""
    if cell.get("schema_version") == authority.AUTHORITY_CELL_SCHEMA:
        body = {
            "schema_version": SELECTOR_COORDINATE_SCHEMA,
            "selector_family_id": "grouped-native-current-bank-selectors-v1",
            "selector_ordinal": cell.get("preset_ordinal"),
            "selector_id": cell.get("preset_id"),
            "selector_semantics_sha256": cell.get("preset_sha256"),
            "adapter_id": cell.get("adapter_id"),
            "executable_fingerprint_sha256": cell.get(
                "executable_fingerprint_sha256"
            ),
        }
    else:
        declared = _mapping(
            cell.get("selector_coordinate"),
            label="extended successor selector coordinate",
        )
        body = dict(declared)
        if body.get("schema_version") != SELECTOR_COORDINATE_SCHEMA:
            _fail("extended selector coordinate schema differs")
        body.pop("selector_coordinate_sha256", None)
    if (
        type(body.get("selector_ordinal")) is not int
        or int(body["selector_ordinal"]) < 0
        or type(body.get("selector_family_id")) is not str
        or not body["selector_family_id"]
        or type(body.get("selector_id")) is not str
        or not body["selector_id"]
        or type(body.get("adapter_id")) is not str
        or not body["adapter_id"]
    ):
        _fail("successor selector coordinate identity differs")
    _digest(body.get("selector_semantics_sha256"), label="selector semantics")
    _digest(
        body.get("executable_fingerprint_sha256"),
        label="selector executable fingerprint",
    )
    return _with_hash(body, field="selector_coordinate_sha256")


def _validate_selector_coordinate_v1(value: object) -> dict[str, object]:
    coordinate = _mapping(value, label="successor selector coordinate")
    _self_hash(
        coordinate,
        field="selector_coordinate_sha256",
        label="successor selector coordinate",
    )
    if (
        coordinate.get("schema_version") != SELECTOR_COORDINATE_SCHEMA
        or type(coordinate.get("selector_family_id")) is not str
        or not coordinate["selector_family_id"]
        or type(coordinate.get("selector_id")) is not str
        or not coordinate["selector_id"]
        or type(coordinate.get("selector_ordinal")) is not int
        or int(coordinate["selector_ordinal"]) < 0
        or type(coordinate.get("adapter_id")) is not str
        or not coordinate["adapter_id"]
    ):
        _fail("successor selector coordinate fields differ")
    _digest(
        coordinate.get("selector_semantics_sha256"),
        label="successor selector semantics",
    )
    _digest(
        coordinate.get("executable_fingerprint_sha256"),
        label="successor selector executable",
    )
    return coordinate


def _validate_fold_receipt_v1(
    value: object, *, source_ordinal: int, fold_ordinal: int,
    projection: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    receipt = _mapping(value, label=f"successor fold receipt[{fold_ordinal}]")
    # The exact rank-150/DPP experiment is intentionally not a 24-fit grouped
    # receipt.  Its distinct validator normalizes the same score-free cell
    # surface for this evaluator without weakening the frozen grouped path.
    from nfl_dfs.research import (
        corpus_r6_current_bank_selector_rank150_dpp_mode_v1 as rank150_dpp,
    )

    if receipt.get("schema_version") == rank150_dpp.FOLD_RECEIPT_SCHEMA:
        try:
            return rank150_dpp.validate_evaluation_fold_receipt_v1(
                receipt,
                source_ordinal=source_ordinal,
                fold_ordinal=fold_ordinal,
                projection=projection,
            )
        except rank150_dpp.CorpusR6CurrentBankSelectorRank150DppModeV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
                str(exc)
            ) from exc
    _self_hash(
        receipt,
        field="successor_fold_receipt_sha256",
        label=f"successor fold receipt[{fold_ordinal}]",
    )
    response = _mapping(
        receipt.get("authority_response"), label="successor authority response"
    )
    _self_hash(
        response,
        field="authority_response_sha256",
        label="successor authority response",
    )
    binding = _mapping(
        response.get("authority_binding"), label="successor authority binding"
    )
    _self_hash(
        binding,
        field="authority_binding_sha256",
        label="successor authority binding",
    )
    if (
        receipt.get("schema_version") != adapter.FOLD_RECEIPT_SCHEMA
        or response.get("schema_version") != authority.AUTHORITY_RESPONSE_SCHEMA
        or receipt.get("source_ordinal") != source_ordinal
        or receipt.get("fold_ordinal") != fold_ordinal
        or receipt.get("heldout_block") != contract.WORLD_BLOCKS[fold_ordinal]
        or receipt.get("slate_id") != projection["slate_id"]
        or response.get("source_ordinal") != source_ordinal
        or response.get("fold_ordinal") != fold_ordinal
        or response.get("heldout_block", receipt.get("heldout_block"))
        != contract.WORLD_BLOCKS[fold_ordinal]
        or response.get("fit_scope_id") != projection["fit_scope_id"]
        or binding.get("projection_sha256") != projection["projection_sha256"]
        or binding.get("candidate_lineup_order_sha256")
        != projection["candidate_lineup_order_sha256"]
        or receipt.get("fit_count") != EXPECTED_FOLD_CELL_COUNT
        or response.get("fit_count") != EXPECTED_FOLD_CELL_COUNT
        or receipt.get("source_control_receipt_compatible") is not False
        or receipt.get("source_control_fit_parity_claimed") is not False
    ):
        _fail("successor fold/projection authority differs")
    cells = [
        _mapping(row, label=f"successor authority cell[{index}]")
        for index, row in enumerate(
            _sequence(response.get("cells"), label="successor authority cells")
        )
    ]
    if (
        len(cells) != EXPECTED_FOLD_CELL_COUNT
        or response.get("cell_sha256s")
        != [row.get("authority_cell_sha256") for row in cells]
        or receipt.get("cell_sha256s") != response.get("cell_sha256s")
    ):
        _fail("successor fold cell hash lattice differs")
    candidate_by_id = {
        str(row["lineup_id"]): row for row in projection["candidates"]
    }
    coordinates: list[tuple[int, int]] = []
    for index, cell in enumerate(cells):
        _self_hash(
            cell,
            field="authority_cell_sha256",
            label=f"successor authority cell[{index}]",
        )
        if cell.get("schema_version") != authority.AUTHORITY_CELL_SCHEMA:
            _fail("unregistered extended successor authority cell")
        if (
            cell.get("replicate") != 0
            or type(cell.get("view_ordinal")) is not int
            or type(cell.get("preset_ordinal")) is not int
        ):
            _fail("successor authority cell coordinate differs")
        sampled = [
            str(row) for row in _sequence(
                cell.get("sampled_lineup_ids"), label="sampled lineup IDs"
            )
        ]
        if (
            sampled != sorted(set(sampled))
            or not set(sampled) <= set(candidate_by_id)
            or cell.get("sampled_lineup_ids_sha256") != _hash(sampled)
        ):
            _fail("successor sampled-lineup authority differs")
        _validate_prefixes_v1(cell=cell, candidate_by_id=candidate_by_id)
        _selector_coordinate_v1(cell)
        coordinates.append((int(cell["view_ordinal"]), int(cell["preset_ordinal"])))
    if len(set(coordinates)) != EXPECTED_FOLD_CELL_COUNT:
        _fail("successor authority cell coordinates repeat")
    return receipt, cells


def _selection_fold_receipt_sha256_v1(
    receipt: Mapping[str, object],
) -> str:
    """Return the native receipt hash without relabeling its process mode."""
    if receipt.get("schema_version") == adapter.FOLD_RECEIPT_SCHEMA:
        return _digest(
            receipt.get("successor_fold_receipt_sha256"),
            label="grouped successor fold receipt",
        )
    from nfl_dfs.research import (
        corpus_r6_current_bank_selector_rank150_dpp_mode_v1 as rank150_dpp,
    )

    if receipt.get("schema_version") == rank150_dpp.FOLD_RECEIPT_SCHEMA:
        return _digest(
            receipt.get("rank150_dpp_fold_receipt_sha256"),
            label="rank150/DPP fold receipt",
        )
    _fail("unregistered successor fold receipt hash schema")


def _successor_effective_independent_tail_shots_v1(
    selected_scores_value: object, *, threshold: float,
) -> dict[str, object]:
    """Extend the frozen effective-shot law to exact 100/150-entry books."""
    retained_threshold = contract._finite_float(
        threshold, label="tail threshold"
    )
    if retained_threshold not in contract.EFFECTIVE_SHOT_THRESHOLDS:
        _fail("effective-shot threshold is not registered")
    scores = np.asarray(selected_scores_value)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape[0] not in SUPPORTED_ENTRY_BUDGETS
        or scores.shape[1] < 2
        or not np.isfinite(scores).all()
    ):
        _fail("successor selected held-out score matrix differs")

    events = scores > retained_threshold
    counts = np.count_nonzero(events, axis=1)
    zero_count = int(np.count_nonzero(counts == 0))
    all_count = int(np.count_nonzero(counts == scores.shape[1]))
    active_mask = (counts > 0) & (counts < scores.shape[1])
    active = np.asarray(events[active_mask], dtype=np.float64)
    active_count = int(active.shape[0])

    pairwise_mean: float | None = None
    pairwise_minimum: float | None = None
    pairwise_maximum: float | None = None
    active_pair_count = 0
    if active_count == 0:
        participation_ratio = 0.0
        entropy_effective_rank = 0.0
    elif active_count == 1:
        participation_ratio = 1.0
        entropy_effective_rank = 1.0
    else:
        centered = active - np.mean(
            active, axis=1, keepdims=True, dtype=np.float64
        )
        norms = np.sqrt(
            np.sum(centered * centered, axis=1, dtype=np.float64)
        )
        if not np.isfinite(norms).all() or np.any(norms <= 0.0):
            _fail("active tail rows have invalid variance")
        correlations = (centered @ centered.T) / np.outer(norms, norms)
        correlations = (correlations + correlations.T) / 2.0
        np.fill_diagonal(correlations, 1.0)
        triangle = correlations[np.triu_indices(active_count, k=1)]
        active_pair_count = int(triangle.size)
        pairwise_mean = float(np.mean(triangle, dtype=np.float64))
        pairwise_minimum = float(np.min(triangle))
        pairwise_maximum = float(np.max(triangle))
        raw_eigenvalues = np.linalg.eigvalsh(correlations)
        minimum = float(np.min(raw_eigenvalues))
        if minimum < contract.NUMERICAL_EIGENVALUE_FLOOR:
            _fail("tail-event correlation matrix is not positive semidefinite")
        clipped = np.maximum(raw_eigenvalues, 0.0)
        eigen_sum = float(np.sum(clipped, dtype=np.float64))
        squared_sum = float(np.sum(clipped * clipped, dtype=np.float64))
        if eigen_sum <= 0.0 or squared_sum <= 0.0:
            _fail("tail-event eigenvalue mass differs")
        participation_ratio = (eigen_sum * eigen_sum) / squared_sum
        probabilities = clipped / eigen_sum
        positive = probabilities[probabilities > 0.0]
        entropy_effective_rank = float(
            np.exp(-np.sum(positive * np.log(positive), dtype=np.float64))
        )

    body = {
        "schema_version": contract.TAIL_SHOTS_SCHEMA,
        "threshold": retained_threshold,
        "operator": ">",
        "selected_lineup_count": int(scores.shape[0]),
        "heldout_world_count": int(scores.shape[1]),
        "active_tail_lineup_count": active_count,
        "zero_event_lineup_count": zero_count,
        "all_event_lineup_count": all_count,
        "active_pair_count": active_pair_count,
        "pairwise_active_correlation_mean_micro": (
            None
            if pairwise_mean is None
            else contract.to_micro_v1(
                pairwise_mean, label="pairwise correlation mean"
            )
        ),
        "pairwise_active_correlation_minimum_micro": (
            None
            if pairwise_minimum is None
            else contract.to_micro_v1(
                pairwise_minimum, label="pairwise correlation minimum"
            )
        ),
        "pairwise_active_correlation_maximum_micro": (
            None
            if pairwise_maximum is None
            else contract.to_micro_v1(
                pairwise_maximum, label="pairwise correlation maximum"
            )
        ),
        "participation_ratio_micro": contract.to_micro_v1(
            participation_ratio, label="participation ratio"
        ),
        "entropy_effective_rank_micro": contract.to_micro_v1(
            entropy_effective_rank, label="entropy effective rank"
        ),
        "uses_realized_outcomes": False,
    }
    return contract._with_hash(body, field="tail_shots_sha256")


def _successor_effective_tail_rows_v1(
    scores: np.ndarray,
) -> list[dict[str, object]]:
    """Preserve frozen control bytes while supporting larger successor books."""
    if scores.shape[0] <= contract.ENTRY_BUDGET:
        return contract._effective_tail_rows_v1(scores)
    return [
        _successor_effective_independent_tail_shots_v1(
            scores, threshold=threshold
        )
        for threshold in contract.EFFECTIVE_SHOT_THRESHOLDS
    ]


def _metric_cache_value_v1(
    *, selected_candidates: Sequence[Mapping[str, object]],
    selected_scores: np.ndarray, player_game: Mapping[str, str],
) -> dict[str, object]:
    rosters = [list(row["roster_player_ids"]) for row in selected_candidates]
    try:
        summary = contract._score_summary_v1(
            selected_scores, label="successor heldout book maximum"
        )
        tails = contract._threshold_events_v1(
            selected_scores, include_book_max=True
        )
        effective = _successor_effective_tail_rows_v1(selected_scores)
        return {
            "book_score_summary": summary,
            "tail_metrics": tails,
            "effective_tail_shots": effective,
            "overlap_metrics": contract._overlap_metrics_v1(
                rosters, player_game=player_game
            ),
            "selected_provenance_exposure": contract._provenance_exposure_v1(
                selected_candidates
            ),
            "decision_metrics": contract._aggregate_scalars_from_book_v1(
                summary=summary, tail_rows=tails, effective_rows=effective
            ),
        }
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc


def build_evaluation_fold_v1(
    *, source_ordinal: int, fold_ordinal: int, projection: object,
    selection_fold_receipt: object, heldout_artifact_identity: object,
    heldout_score_matrix: object, later_source_body: object,
) -> dict[str, object]:
    """Score every exact prefix from one successor fold on its fifth block."""
    try:
        retained_projection = contract.validate_narrow_projection_v1(projection)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < EXPECTED_PANEL_SLATE_COUNT
        or type(fold_ordinal) is not int
        or not 0 <= fold_ordinal < EXPECTED_FOLDS_PER_SLATE
        or retained_projection["heldout_block"]
        != contract.WORLD_BLOCKS[fold_ordinal]
    ):
        _fail("successor evaluation fold coordinate differs")
    receipt, cells = _validate_fold_receipt_v1(
        selection_fold_receipt,
        source_ordinal=source_ordinal,
        fold_ordinal=fold_ordinal,
        projection=retained_projection,
    )
    required_players = sorted({
        str(player_id)
        for candidate in retained_projection["candidates"]
        for player_id in candidate["roster_player_ids"]
    })
    try:
        player_game, later_source_sha = contract._later_source_player_game_map_v1(
            later_source_body=later_source_body,
            later_source_identity=retained_projection["later_source_identity"],
            slate_id=str(retained_projection["slate_id"]),
            required_player_ids=required_players,
        )
        heldout_authority, scores = contract._heldout_fold_authority_v1(
            projection=retained_projection,
            heldout_artifact_identity=heldout_artifact_identity,
            heldout_scores=heldout_score_matrix,
        )
        registry = contract.derive_view_registry_from_projection_v1(
            retained_projection
        )
        ids_by_view = contract._view_ids_by_id(registry)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc
    candidates = list(retained_projection["candidates"])
    candidate_by_id = {str(row["lineup_id"]): row for row in candidates}
    index_by_id = {
        str(row["lineup_id"]): index for index, row in enumerate(candidates)
    }
    metric_cache: dict[str, dict[str, object]] = {}
    oracle_cache: dict[str, dict[str, object]] = {}
    rows: list[dict[str, object]] = []
    entry_budgets: set[int] = set()
    for cell_ordinal, cell in enumerate(cells):
        selected_ids = [str(value) for value in cell["selected_lineup_ids"]]
        prefixes = _validate_prefixes_v1(
            cell=cell, candidate_by_id=candidate_by_id
        )
        selector_coordinate = _selector_coordinate_v1(cell)
        view_id = str(cell["view_id"])
        if view_id not in ids_by_view:
            _fail("successor selected view is absent from projection registry")
        view_ids = list(ids_by_view[view_id])
        view_hash = _hash(view_ids)
        if view_hash not in oracle_cache:
            view_scores = scores[[index_by_id[lineup_id] for lineup_id in view_ids], :]
            try:
                oracle_cache[view_hash] = contract._score_summary_v1(
                    view_scores, label="successor simulated corpus oracle"
                )
            except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
                raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
                    str(exc)
                ) from exc
        kind, profile_ordinal, profile_id = _profile_fields(view_id)
        for prefix_ordinal, prefix in enumerate(prefixes):
            entry_budget = int(prefix["prefix_size"])
            entry_budgets.add(entry_budget)
            prefix_ids = selected_ids[:entry_budget]
            prefix_hash = str(prefix["prefix_payload_sha256"])
            if prefix_hash not in metric_cache:
                selected_candidates = [candidate_by_id[lineup_id] for lineup_id in prefix_ids]
                selected_scores = scores[
                    [index_by_id[lineup_id] for lineup_id in prefix_ids], :
                ]
                metric_cache[prefix_hash] = _metric_cache_value_v1(
                    selected_candidates=selected_candidates,
                    selected_scores=selected_scores,
                    player_game=player_game,
                )
            metrics = metric_cache[prefix_hash]
            oracle = oracle_cache[view_hash]
            pairing = _with_hash({
                "schema_version": PAIRING_COORDINATE_SCHEMA,
                "source_ordinal": source_ordinal,
                "slate_id": retained_projection["slate_id"],
                "fold_ordinal": fold_ordinal,
                "heldout_block": retained_projection["heldout_block"],
                "view_id": view_id,
                "replicate": int(cell["replicate"]),
                "entry_budget": entry_budget,
                "sampled_lineup_ids_sha256": cell[
                    "sampled_lineup_ids_sha256"
                ],
            }, field="pairing_coordinate_sha256")
            body = {
                "schema_version": BOOK_METRIC_ROW_SCHEMA,
                "source_ordinal": source_ordinal,
                "slate_id": retained_projection["slate_id"],
                "fold_ordinal": fold_ordinal,
                "heldout_block": retained_projection["heldout_block"],
                "cell_ordinal": cell_ordinal,
                "prefix_ordinal": prefix_ordinal,
                "replicate": int(cell["replicate"]),
                "view_id": view_id,
                "view_kind": kind,
                "profile_ordinal": profile_ordinal,
                "profile_id": profile_id,
                "selector_coordinate": selector_coordinate,
                "selector_coordinate_sha256": selector_coordinate[
                    "selector_coordinate_sha256"
                ],
                "entry_budget": entry_budget,
                "selection_cell_sha256": cell["authority_cell_sha256"],
                "book_payload_sha256": prefix_hash,
                "selected_lineup_ids_sha256": prefix[
                    "selected_lineup_ids_sha256"
                ],
                "selected_rosters_sha256": prefix["selected_rosters_sha256"],
                "pairing_coordinate": pairing,
                "pairing_coordinate_sha256": pairing[
                    "pairing_coordinate_sha256"
                ],
                "retrieval_metrics": {
                    "full_view_candidate_count": len(view_ids),
                    "equal_size_candidate_count": len(
                        cell["sampled_lineup_ids"]
                    ),
                    "selected_lineup_count": entry_budget,
                    "simulated_corpus_oracle_gap_micro": int(oracle["mean_micro"])
                    - int(metrics["book_score_summary"]["mean_micro"]),
                },
                **metrics,
                "paired_control_comparison_ready": entry_budget
                in FINALIST_ENTRY_BUDGETS,
                "policy": dict(_POLICY),
            }
            rows.append(_with_hash(body, field="book_metric_row_sha256"))
    expected_row_count = sum(len(cell["prefixes"]) for cell in cells)
    if len(rows) != expected_row_count:
        _fail("successor evaluation book row lattice differs")
    body = {
        "schema_version": EVALUATION_FOLD_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate_id": retained_projection["slate_id"],
        "fold_ordinal": fold_ordinal,
        "heldout_block": retained_projection["heldout_block"],
        "projection_sha256": retained_projection["projection_sha256"],
        "selection_fold_receipt_sha256": _selection_fold_receipt_sha256_v1(
            receipt
        ),
        "heldout_fold_authority": heldout_authority,
        "heldout_fold_authority_sha256": heldout_authority[
            "heldout_fold_authority_sha256"
        ],
        "later_source_body_sha256": later_source_sha,
        "player_game_map_sha256": _hash(player_game),
        "selection_cell_count": len(cells),
        "entry_budgets": sorted(entry_budgets),
        "book_metric_row_count": len(rows),
        "book_metric_rows": rows,
        "book_metric_rows_sha256": _hash(rows),
        "metric_law": "same-heldout-decision-metrics-as-crossed-screen-control",
        "source_control_evaluator_invoked": False,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="evaluation_fold_sha256")


def _validate_selection_slate_result_v1(
    value: object, *, projection_bundle: Mapping[str, object],
) -> dict[str, object]:
    result = _mapping(value, label="successor selection slate result")
    from nfl_dfs.research import (
        corpus_r6_current_bank_selector_rank150_dpp_mode_v1 as rank150_dpp,
    )

    if result.get("schema_version") == rank150_dpp.SLATE_RESULT_SCHEMA:
        try:
            return rank150_dpp.validate_evaluation_slate_result_v1(
                result, projection_bundle=projection_bundle
            )
        except rank150_dpp.CorpusR6CurrentBankSelectorRank150DppModeV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
                str(exc)
            ) from exc
    _self_hash(
        result,
        field="slate_result_sha256",
        label="successor selection slate result",
    )
    folds = [
        _mapping(row, label=f"successor selection fold[{index}]")
        for index, row in enumerate(
            _sequence(result.get("fold_receipts"), label="selection folds")
        )
    ]
    if (
        result.get("schema_version") != selection_cloud.SLATE_RESULT_SCHEMA
        or result.get("source_control_receipt_compatible") is not False
        or result.get("source_control_fit_parity_claimed") is not False
        or result.get("fold_count") != EXPECTED_FOLDS_PER_SLATE
        or result.get("fold_order") != list(contract.WORLD_BLOCKS)
        or result.get("fit_count")
        != EXPECTED_FOLDS_PER_SLATE * EXPECTED_FOLD_CELL_COUNT
        or len(folds) != EXPECTED_FOLDS_PER_SLATE
        or result.get("fold_receipt_sha256s")
        != [row.get("successor_fold_receipt_sha256") for row in folds]
        or result.get("source_ordinal") != projection_bundle["source_ordinal"]
        or result.get("slate_id") != projection_bundle["slate_id"]
    ):
        _fail("successor selection slate result authority differs")
    for fold, (receipt, projection) in enumerate(
        zip(folds, projection_bundle["fold_projections"], strict=True)
    ):
        _validate_fold_receipt_v1(
            receipt,
            source_ordinal=int(result["source_ordinal"]),
            fold_ordinal=fold,
            projection=projection,
        )
    return result


def build_evaluation_result_v1(
    *, selection_slate_result: object, selection_slate_result_identity: object,
    projection_bundle: object, projection_bundle_identity: object,
    heldout_fold_input_stream: Iterable[object], later_source_body: object,
    execution_binding: object | None = None,
) -> dict[str, object]:
    """Consume R0..R4 once and return one outcome-blind successor result."""
    try:
        bundle = contract.validate_projection_bundle_v1(projection_bundle)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(str(exc)) from exc
    bundle_identity = _bind(
        bundle, projection_bundle_identity, label="successor projection bundle"
    )
    selection = _validate_selection_slate_result_v1(
        selection_slate_result, projection_bundle=bundle
    )
    selection_identity = _bind(
        selection,
        selection_slate_result_identity,
        label="successor selection slate result",
    )
    try:
        stream = iter(heldout_fold_input_stream)
    except TypeError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
            "heldout fold inputs must be a single-pass iterable"
        ) from exc
    folds: list[dict[str, object]] = []
    for fold_ordinal in range(EXPECTED_FOLDS_PER_SLATE):
        try:
            raw = next(stream)
        except StopIteration as exc:
            raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
                "heldout fold stream ended before R4"
            ) from exc
        item = _mapping(raw, label=f"heldout fold input[{fold_ordinal}]")
        if set(item) != {
            "fold_ordinal", "heldout_artifact_identity", "heldout_score_matrix",
        } or item["fold_ordinal"] != fold_ordinal:
            _fail("heldout fold stream order/fields differ")
        folds.append(build_evaluation_fold_v1(
            source_ordinal=int(selection["source_ordinal"]),
            fold_ordinal=fold_ordinal,
            projection=bundle["fold_projections"][fold_ordinal],
            selection_fold_receipt=selection["fold_receipts"][fold_ordinal],
            heldout_artifact_identity=item["heldout_artifact_identity"],
            heldout_score_matrix=item["heldout_score_matrix"],
            later_source_body=later_source_body,
        ))
        del item, raw
    try:
        next(stream)
    except StopIteration:
        pass
    else:
        _fail("heldout fold stream contains more than five folds")
    if (
        len({row["later_source_body_sha256"] for row in folds}) != 1
        or len({row["player_game_map_sha256"] for row in folds}) != 1
    ):
        _fail("successor evaluation folds do not share later-source authority")
    entry_budgets = sorted({
        int(value) for fold in folds for value in fold["entry_budgets"]
    })
    retained_execution_binding = (
        None
        if execution_binding is None
        else validate_evaluation_execution_binding_v1(execution_binding)
    )
    if retained_execution_binding is not None and (
        retained_execution_binding["source_ordinal"] != selection["source_ordinal"]
        or retained_execution_binding["slate_id"] != selection["slate_id"]
    ):
        _fail("successor evaluation execution/result coordinate differs")
    body = {
        "schema_version": EVALUATION_RESULT_SCHEMA,
        "source_ordinal": selection["source_ordinal"],
        "slate_id": selection["slate_id"],
        "selection_slate_result_identity": selection_identity,
        "selection_slate_result_sha256": selection["slate_result_sha256"],
        "projection_bundle_identity": bundle_identity,
        "projection_bundle_sha256": bundle["projection_bundle_sha256"],
        "later_source_identity": bundle["fold_projections"][0][
            "later_source_identity"
        ],
        "fold_count": EXPECTED_FOLDS_PER_SLATE,
        "folds": folds,
        "folds_sha256": _hash(folds),
        "entry_budgets": entry_budgets,
        "book_metric_row_count": sum(
            int(fold["book_metric_row_count"]) for fold in folds
        ),
        "decision_metric_stems": list(DECISION_METRIC_STEMS),
        "paired_control_comparison_ready_entry_budgets": [
            value for value in entry_budgets if value in FINALIST_ENTRY_BUDGETS
        ],
        "execution_binding": retained_execution_binding,
        "execution_binding_sha256": (
            None
            if retained_execution_binding is None
            else retained_execution_binding[
                "evaluation_execution_binding_sha256"
            ]
        ),
        "execution_authority_present": retained_execution_binding is not None,
        "fold_stream_consumption_order": list(range(EXPECTED_FOLDS_PER_SLATE)),
        "selection_code_callable": False,
        "caller_metric_rows_accepted": False,
        "source_control_evaluator_invoked": False,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="evaluation_result_sha256")


def validate_evaluation_result_v1(value: object) -> dict[str, object]:
    """Validate the durable successor transcript without accepting new rows."""
    result = _mapping(value, label="successor evaluation result")
    _self_hash(
        result,
        field="evaluation_result_sha256",
        label="successor evaluation result",
    )
    folds = [
        _mapping(row, label=f"successor evaluation fold[{index}]")
        for index, row in enumerate(
            _sequence(result.get("folds"), label="successor evaluation folds")
        )
    ]
    if (
        result.get("schema_version") != EVALUATION_RESULT_SCHEMA
        or result.get("fold_count") != EXPECTED_FOLDS_PER_SLATE
        or len(folds) != EXPECTED_FOLDS_PER_SLATE
        or result.get("folds_sha256") != _hash(folds)
        or result.get("fold_stream_consumption_order")
        != list(range(EXPECTED_FOLDS_PER_SLATE))
        or result.get("decision_metric_stems") != list(DECISION_METRIC_STEMS)
        or result.get("selection_code_callable") is not False
        or result.get("caller_metric_rows_accepted") is not False
        or result.get("source_control_evaluator_invoked") is not False
        or result.get("policy") != _POLICY
    ):
        _fail("successor evaluation result fixed authority differs")
    total = 0
    budgets: set[int] = set()
    for fold_ordinal, fold in enumerate(folds):
        _self_hash(
            fold,
            field="evaluation_fold_sha256",
            label=f"successor evaluation fold[{fold_ordinal}]",
        )
        rows = [
            _mapping(row, label="successor book metric row")
            for row in _sequence(
                fold.get("book_metric_rows"), label="successor book metric rows"
            )
        ]
        if (
            fold.get("schema_version") != EVALUATION_FOLD_SCHEMA
            or fold.get("source_ordinal") != result.get("source_ordinal")
            or fold.get("slate_id") != result.get("slate_id")
            or fold.get("fold_ordinal") != fold_ordinal
            or fold.get("heldout_block") != contract.WORLD_BLOCKS[fold_ordinal]
            or fold.get("book_metric_row_count") != len(rows)
            or fold.get("book_metric_rows_sha256") != _hash(rows)
            or fold.get("source_control_evaluator_invoked") is not False
            or fold.get("policy") != _POLICY
        ):
            _fail("successor evaluation fold fixed authority differs")
        for row in rows:
            _self_hash(
                row,
                field="book_metric_row_sha256",
                label="successor book metric row",
            )
            selector_coordinate = _mapping(
                row.get("selector_coordinate"), label="selector coordinate"
            )
            selector_coordinate = _validate_selector_coordinate_v1(
                selector_coordinate
            )
            pairing = _mapping(
                row.get("pairing_coordinate"), label="pairing coordinate"
            )
            _self_hash(
                pairing,
                field="pairing_coordinate_sha256",
                label="pairing coordinate",
            )
            metrics = _mapping(
                row.get("decision_metrics"), label="successor decision metrics"
            )
            entry_budget = row.get("entry_budget")
            if (
                row.get("schema_version") != BOOK_METRIC_ROW_SCHEMA
                or row.get("source_ordinal") != result.get("source_ordinal")
                or row.get("fold_ordinal") != fold_ordinal
                or row.get("heldout_block") != contract.WORLD_BLOCKS[fold_ordinal]
                or row.get("selector_coordinate_sha256")
                != selector_coordinate["selector_coordinate_sha256"]
                or row.get("pairing_coordinate_sha256")
                != pairing["pairing_coordinate_sha256"]
                or set(metrics) != set(DECISION_METRIC_STEMS)
                or entry_budget not in SUPPORTED_ENTRY_BUDGETS
                or row.get("policy") != _POLICY
                or pairing.get("schema_version") != PAIRING_COORDINATE_SCHEMA
                or pairing.get("source_ordinal") != result.get("source_ordinal")
                or pairing.get("slate_id") != result.get("slate_id")
                or pairing.get("fold_ordinal") != fold_ordinal
                or pairing.get("heldout_block")
                != contract.WORLD_BLOCKS[fold_ordinal]
                or pairing.get("view_id") != row.get("view_id")
                or pairing.get("replicate") != row.get("replicate")
                or pairing.get("entry_budget") != entry_budget
                or row.get("paired_control_comparison_ready")
                is not (entry_budget in FINALIST_ENTRY_BUDGETS)
            ):
                _fail("successor book metric row authority differs")
            for stem in DECISION_METRIC_STEMS:
                fraction = _mapping(metrics[stem], label=f"decision metric {stem}")
                if (
                    set(fraction) != {"numerator", "denominator"}
                    or type(fraction["numerator"]) is not int
                    or type(fraction["denominator"]) is not int
                    or fraction["numerator"] < 0
                    or fraction["denominator"] < 1
                ):
                    _fail("successor decision metric fraction differs")
            summary = _mapping(
                row.get("book_score_summary"), label="successor book score summary"
            )
            if set(summary) != {
                "mean_micro", "maximum_micro", "q50_micro", "q90_micro",
                "q95_micro", "q99_micro",
            } or any(type(value) is not int for value in summary.values()):
                _fail("successor book score summary differs")
            try:
                tails = contract._validate_tail_rows_v1(
                    row.get("tail_metrics"),
                    selected_count=int(entry_budget),
                    include_book_max=True,
                )
                effective = [
                    contract._validate_effective_tail_row_v1(value)
                    for value in _sequence(
                        row.get("effective_tail_shots"),
                        label="successor effective-tail rows",
                    )
                ]
                expected_metrics = contract._aggregate_scalars_from_book_v1(
                    summary=summary, tail_rows=tails, effective_rows=effective
                )
            except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
                raise CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
                    str(exc)
                ) from exc
            if (
                [value["threshold"] for value in effective]
                != list(contract.EFFECTIVE_SHOT_THRESHOLDS)
                or any(
                    value["selected_lineup_count"] != entry_budget
                    for value in effective
                )
                or metrics != expected_metrics
            ):
                _fail("successor decision metrics differ from heldout transcript")
            overlap = _mapping(
                row.get("overlap_metrics"), label="successor overlap metrics"
            )
            pair_count = int(entry_budget) * (int(entry_budget) - 1) // 2
            retrieval = _mapping(
                row.get("retrieval_metrics"), label="successor retrieval metrics"
            )
            if (
                overlap.get("unordered_lineup_pair_count") != pair_count
                or overlap.get("shared_player_count_denominator") != pair_count
                or retrieval.get("selected_lineup_count") != entry_budget
                or int(retrieval.get("equal_size_candidate_count", -1))
                < int(entry_budget)
                or int(retrieval.get("full_view_candidate_count", -1))
                < int(entry_budget)
            ):
                _fail("successor overlap/retrieval metric invariants differ")
            budgets.add(int(entry_budget))
        total += len(rows)
    if (
        result.get("book_metric_row_count") != total
        or result.get("entry_budgets") != sorted(budgets)
        or result.get("paired_control_comparison_ready_entry_budgets")
        != [value for value in sorted(budgets) if value in FINALIST_ENTRY_BUDGETS]
    ):
        _fail("successor evaluation result row/budget census differs")
    execution_binding = result.get("execution_binding")
    if execution_binding is None:
        if (
            result.get("execution_binding_sha256") is not None
            or result.get("execution_authority_present") is not False
        ):
            _fail("successor absent execution binding differs")
    else:
        retained_execution = validate_evaluation_execution_binding_v1(
            execution_binding
        )
        if (
            result.get("execution_binding_sha256")
            != retained_execution["evaluation_execution_binding_sha256"]
            or result.get("execution_authority_present") is not True
            or retained_execution["source_ordinal"] != result["source_ordinal"]
            or retained_execution["slate_id"] != result["slate_id"]
        ):
            _fail("successor evaluation execution binding differs")
    _identity(
        result.get("selection_slate_result_identity"),
        label="successor selection result identity",
    )
    _identity(
        result.get("projection_bundle_identity"),
        label="successor projection bundle identity",
    )
    return result


def _fraction(row: Mapping[str, object], stem: str) -> Fraction:
    metrics = _mapping(
        row.get("decision_metrics"), label="aggregate source decision metrics"
    )
    value = _mapping(metrics[stem], label=f"aggregate source {stem}")
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def _finalist_order(
    row: Mapping[str, object], *, role: str,
) -> tuple[Fraction, Fraction, Fraction, Fraction, str, str]:
    expected = _fraction(row, "mean_heldout_expected_book_max_micro")
    p220 = _fraction(row, "mean_heldout_p_max_gt_220")
    p230 = _fraction(row, "mean_heldout_p_max_gt_230")
    diversity = _fraction(
        row, "mean_heldout_participation_ratio_gt_220_micro"
    )
    if role == "performance-finalist":
        primary = (expected, p220, p230, diversity)
    elif role == "extreme-tail-finalist":
        primary = (p230, p220, expected, diversity)
    elif role == "independent-shots-finalist":
        primary = (diversity, p230, expected, p220)
    else:  # pragma: no cover - internal-only fixed role registry
        _fail("unknown finalist role")
    return (
        *(-value for value in primary),
        str(row["selector_coordinate"]["selector_id"]),
        str(row["view_id"]),
    )


def build_terminal_aggregate_v1(
    *, evaluation_publications: object, execution_binding: object,
) -> dict[str, object]:
    """Aggregate the complete 54x5 panel and freeze outcome-blind finalists."""
    publications = [
        _mapping(row, label=f"evaluation publication[{index}]")
        for index, row in enumerate(
            _sequence(evaluation_publications, label="evaluation publications")
        )
    ]
    if len(publications) != EXPECTED_PANEL_SLATE_COUNT:
        _fail("terminal aggregate requires the exact 54-slate panel")
    retained: list[tuple[dict[str, object], dict[str, object]]] = []
    for index, publication in enumerate(publications):
        if set(publication) != {"evaluation_result", "evaluation_identity"}:
            _fail(f"evaluation publication[{index}] fields differ")
        result = validate_evaluation_result_v1(publication["evaluation_result"])
        if result["execution_authority_present"] is not True:
            _fail("terminal aggregate requires evaluator execution authority")
        identity = _bind(
            result,
            publication["evaluation_identity"],
            label=f"successor evaluation publication[{index}]",
        )
        retained.append((result, identity))
    retained.sort(key=lambda pair: int(pair[0]["source_ordinal"]))
    if [int(pair[0]["source_ordinal"]) for pair in retained] != list(
        range(EXPECTED_PANEL_SLATE_COUNT)
    ) or len({str(pair[0]["slate_id"]) for pair in retained}) != EXPECTED_PANEL_SLATE_COUNT:
        _fail("terminal aggregate evaluation source/slate panel differs")

    grouped: dict[
        tuple[str, str, int], list[dict[str, object]]
    ] = defaultdict(list)
    selector_by_hash: dict[str, dict[str, object]] = {}
    for result, _ in retained:
        for fold in result["folds"]:
            for row in fold["book_metric_rows"]:
                selector_hash = str(row["selector_coordinate_sha256"])
                selector = dict(row["selector_coordinate"])
                prior = selector_by_hash.setdefault(selector_hash, selector)
                if prior != selector:
                    _fail("selector coordinate hash aliases distinct bodies")
                key = (
                    selector_hash,
                    str(row["view_id"]),
                    int(row["entry_budget"]),
                )
                grouped[key].append(row)
    aggregate_rows: list[dict[str, object]] = []
    for (selector_hash, view_id, entry_budget), rows in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][2],
            str(selector_by_hash[item[0][0]]["selector_id"]),
            item[0][1],
        ),
    ):
        if len(rows) != EXPECTED_COMPLETE_CELL_COUNT:
            _fail("terminal aggregate cell is incomplete")
        pairings = [str(row["pairing_coordinate_sha256"]) for row in rows]
        if len(set(pairings)) != EXPECTED_COMPLETE_CELL_COUNT:
            _fail("terminal aggregate pairing coordinates repeat")
        metric_totals: dict[str, dict[str, int]] = {}
        for stem in DECISION_METRIC_STEMS:
            metric_totals[stem] = {
                "numerator": sum(
                    int(row["decision_metrics"][stem]["numerator"])
                    for row in rows
                ),
                "denominator": sum(
                    int(row["decision_metrics"][stem]["denominator"])
                    for row in rows
                ),
            }
        kind, profile_ordinal, profile_id = _profile_fields(view_id)
        body = {
            "schema_version": AGGREGATE_METRIC_ROW_SCHEMA,
            "view_id": view_id,
            "view_kind": kind,
            "profile_ordinal": profile_ordinal,
            "profile_id": profile_id,
            "selector_coordinate": selector_by_hash[selector_hash],
            "selector_coordinate_sha256": selector_hash,
            "entry_budget": entry_budget,
            "decision_metrics": metric_totals,
            "complete_cell_count": len(rows),
            "slate_count": EXPECTED_PANEL_SLATE_COUNT,
            "fold_count_per_slate": EXPECTED_FOLDS_PER_SLATE,
            "pairing_coordinate_sha256s_sha256": _hash(sorted(pairings)),
            "book_metric_row_sha256s_sha256": _hash(sorted(
                str(row["book_metric_row_sha256"]) for row in rows
            )),
            "paired_control_comparison_ready": entry_budget
            in FINALIST_ENTRY_BUDGETS,
            "policy": dict(_POLICY),
        }
        aggregate_rows.append(_with_hash(body, field="aggregate_metric_row_sha256"))

    finalist_rows: list[dict[str, object]] = []
    for entry_budget in FINALIST_ENTRY_BUDGETS:
        pool = [
            row for row in aggregate_rows if row["entry_budget"] == entry_budget
        ]
        if not pool:
            continue
        roles_by_hash: dict[str, list[str]] = defaultdict(list)
        for role in (
            "performance-finalist",
            "extreme-tail-finalist",
            "independent-shots-finalist",
        ):
            chosen = min(pool, key=lambda row: _finalist_order(row, role=role))
            roles_by_hash[str(chosen["aggregate_metric_row_sha256"])].append(role)
        by_hash = {
            str(row["aggregate_metric_row_sha256"]): row for row in pool
        }
        for aggregate_hash, roles in sorted(
            roles_by_hash.items(),
            key=lambda item: (
                min((
                    "performance-finalist",
                    "extreme-tail-finalist",
                    "independent-shots-finalist",
                ).index(role) for role in item[1]),
                item[0],
            ),
        ):
            row = by_hash[aggregate_hash]
            finalist_rows.append(_with_hash({
                "schema_version": FINALIST_SCHEMA,
                "entry_budget": entry_budget,
                "view_id": row["view_id"],
                "profile_id": row["profile_id"],
                "profile_ordinal": row["profile_ordinal"],
                "selector_coordinate": row["selector_coordinate"],
                "selector_coordinate_sha256": row[
                    "selector_coordinate_sha256"
                ],
                "aggregate_metric_row_sha256": aggregate_hash,
                "roles": roles,
                "selection_law": (
                    "outcome-blind-lexicographic-heldout-performance-tail-diversity"
                ),
                "realized_bridge_eligible_after_terminal_publication": True,
                "historical_scoring_licensed": False,
            }, field="finalist_sha256"))
    if not finalist_rows:
        _fail("terminal aggregate has no exact 80/100/150 finalist cells")
    retained_terminal_execution = validate_terminal_execution_binding_v1(
        execution_binding
    )
    predecessor_rows = [
        {
            "source_ordinal": int(result["source_ordinal"]),
            "slate_id": result["slate_id"],
            "evaluation_identity": identity,
            "evaluation_result_sha256": result["evaluation_result_sha256"],
            "selection_slate_result_identity": result[
                "selection_slate_result_identity"
            ],
        }
        for result, identity in retained
    ]
    body = {
        "schema_version": TERMINAL_AGGREGATE_SCHEMA,
        "evaluation_count": len(retained),
        "predecessors": predecessor_rows,
        "predecessors_sha256": _hash(predecessor_rows),
        "aggregate_metric_row_count": len(aggregate_rows),
        "aggregate_metric_rows": aggregate_rows,
        "aggregate_metric_rows_sha256": _hash(aggregate_rows),
        "finalist_count": len(finalist_rows),
        "finalists": finalist_rows,
        "finalists_sha256": _hash(finalist_rows),
        "decision_metric_stems": list(DECISION_METRIC_STEMS),
        "supported_entry_budgets": list(SUPPORTED_ENTRY_BUDGETS),
        "finalist_entry_budgets": list(FINALIST_ENTRY_BUDGETS),
        "terminal_before_realized_outcome_read": True,
        "realized_outcome_identity_present": False,
        "realized_bridge_must_be_separately_authorized": True,
        "source_control_evaluator_invoked": False,
        "source_control_aggregate_schema_claimed": False,
        "all_evaluation_execution_authority_present": True,
        "terminal_execution_binding": retained_terminal_execution,
        "terminal_execution_binding_sha256": retained_terminal_execution[
            "terminal_execution_binding_sha256"
        ],
        "terminal_execution_authority_present": True,
        "policy": dict(_POLICY),
    }
    return _with_hash(body, field="terminal_aggregate_sha256")


def validate_terminal_aggregate_v1(value: object) -> dict[str, object]:
    root = _mapping(value, label="successor terminal aggregate")
    _self_hash(
        root,
        field="terminal_aggregate_sha256",
        label="successor terminal aggregate",
    )
    rows = [
        _mapping(row, label="successor aggregate metric row")
        for row in _sequence(
            root.get("aggregate_metric_rows"), label="aggregate metric rows"
        )
    ]
    finalists = [
        _mapping(row, label="successor finalist")
        for row in _sequence(root.get("finalists"), label="successor finalists")
    ]
    predecessors = [
        _mapping(row, label="successor aggregate predecessor")
        for row in _sequence(root.get("predecessors"), label="aggregate predecessors")
    ]
    if (
        root.get("schema_version") != TERMINAL_AGGREGATE_SCHEMA
        or root.get("evaluation_count") != EXPECTED_PANEL_SLATE_COUNT
        or len(predecessors) != EXPECTED_PANEL_SLATE_COUNT
        or root.get("predecessors_sha256") != _hash(predecessors)
        or root.get("aggregate_metric_row_count") != len(rows)
        or root.get("aggregate_metric_rows_sha256") != _hash(rows)
        or root.get("finalist_count") != len(finalists)
        or root.get("finalists_sha256") != _hash(finalists)
        or root.get("decision_metric_stems") != list(DECISION_METRIC_STEMS)
        or root.get("supported_entry_budgets") != list(SUPPORTED_ENTRY_BUDGETS)
        or root.get("finalist_entry_budgets") != list(FINALIST_ENTRY_BUDGETS)
        or root.get("terminal_before_realized_outcome_read") is not True
        or root.get("realized_outcome_identity_present") is not False
        or root.get("realized_bridge_must_be_separately_authorized") is not True
        or root.get("source_control_evaluator_invoked") is not False
        or root.get("source_control_aggregate_schema_claimed") is not False
        or root.get("all_evaluation_execution_authority_present") is not True
        or root.get("terminal_execution_authority_present") is not True
        or root.get("policy") != _POLICY
    ):
        _fail("successor terminal aggregate fixed authority differs")
    terminal_execution = validate_terminal_execution_binding_v1(
        root.get("terminal_execution_binding")
    )
    if (
        root.get("terminal_execution_binding_sha256")
        != terminal_execution["terminal_execution_binding_sha256"]
    ):
        _fail("successor terminal execution binding differs")
    for row in rows:
        _self_hash(
            row,
            field="aggregate_metric_row_sha256",
            label="successor aggregate metric row",
        )
        if (
            row.get("schema_version") != AGGREGATE_METRIC_ROW_SCHEMA
            or row.get("complete_cell_count") != EXPECTED_COMPLETE_CELL_COUNT
            or row.get("slate_count") != EXPECTED_PANEL_SLATE_COUNT
            or row.get("fold_count_per_slate") != EXPECTED_FOLDS_PER_SLATE
            or row.get("entry_budget") not in SUPPORTED_ENTRY_BUDGETS
            or set(_mapping(
                row.get("decision_metrics"), label="aggregate decision metrics"
            )) != set(DECISION_METRIC_STEMS)
            or row.get("policy") != _POLICY
        ):
            _fail("successor aggregate metric row authority differs")
    aggregate_hashes = {
        str(row["aggregate_metric_row_sha256"]) for row in rows
    }
    for finalist in finalists:
        _self_hash(
            finalist,
            field="finalist_sha256",
            label="successor finalist",
        )
        if (
            finalist.get("schema_version") != FINALIST_SCHEMA
            or finalist.get("entry_budget") not in FINALIST_ENTRY_BUDGETS
            or finalist.get("aggregate_metric_row_sha256") not in aggregate_hashes
            or finalist.get("historical_scoring_licensed") is not False
            or finalist.get("realized_bridge_eligible_after_terminal_publication")
            is not True
        ):
            _fail("successor finalist authority differs")
    return root


__all__ = [
    "AGGREGATE_METRIC_ROW_SCHEMA",
    "BOOK_METRIC_ROW_SCHEMA",
    "DECISION_METRIC_STEMS",
    "EVALUATION_FOLD_SCHEMA",
    "EVALUATION_EXECUTION_BINDING_SCHEMA",
    "EVALUATION_RESULT_SCHEMA",
    "FINALIST_ENTRY_BUDGETS",
    "FINALIST_SCHEMA",
    "PAIRING_COORDINATE_SCHEMA",
    "SELECTOR_COORDINATE_SCHEMA",
    "SUPPORTED_ENTRY_BUDGETS",
    "TERMINAL_AGGREGATE_SCHEMA",
    "TERMINAL_EXECUTION_BINDING_SCHEMA",
    "CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error",
    "build_evaluation_fold_v1",
    "build_evaluation_execution_binding_v1",
    "build_evaluation_result_v1",
    "build_terminal_aggregate_v1",
    "build_terminal_execution_binding_v1",
    "validate_evaluation_result_v1",
    "validate_evaluation_execution_binding_v1",
    "validate_terminal_aggregate_v1",
    "validate_terminal_execution_binding_v1",
]
