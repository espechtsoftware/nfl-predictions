"""Authoritative selector subprocess for the R6 crossed-screen contract.

This is the only module in the slice allowed to import live selector code.  Its
public builder accepts immutable authorities and the reopened finite training
matrix; it derives every ledger, sample, selected ID, prefix, and receipt.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as fast_lane
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract


class CorpusR6CurrentBankCrossedScreenSelectorV1Error(ValueError):
    """The immutable selector subprocess contract cannot be preserved."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankCrossedScreenSelectorV1Error(message)


def _verify_live_registries_v1() -> list[dict[str, object]]:
    profiles = [dict(value) for value in batch.frozen_parameter_sets()]
    strategies = [dict(value) for value in fast_lane.frozen_full_union_strategies_v1()]
    if (
        contract.canonical_sha256_v1(profiles) != contract.PROFILE_REGISTRY_SHA256
        or contract.canonical_sha256_v1(strategies) != contract.STRATEGY_REGISTRY_SHA256
        or profiles != contract.frozen_profiles_v1()
        or strategies != contract.frozen_strategies_v1()
    ):
        _fail("live selector registries differ from the contract-owned literals")
    return strategies


def _published_budget_v1(value: object, identity: object) -> dict[str, object]:
    budget = contract.validate_process_budget_v1(value)
    try:
        retained_identity = contract._bind_canonical_body_to_identity_v1(
            budget, identity, label="selector process budget"
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankCrossedScreenSelectorV1Error(str(exc)) from exc
    if not retained_identity["uri"].startswith(contract.OUTPUT_NAMESPACE):
        _fail("selector process budget is outside the frozen output namespace")
    return budget


def build_selection_fold_receipt_from_matrix_v1(
    *,
    projection_bundle: object,
    projection_bundle_identity: object,
    topology: object,
    topology_identity: object,
    process_budget: object,
    process_budget_identity: object,
    fold_ordinal: int,
    training_score_matrix: np.ndarray,
    nomination: object | None = None,
    nomination_identity: object | None = None,
    broad_phase_authority: object | None = None,
) -> dict[str, object]:
    """Execute and replay every frozen cell; caller supplies no selection facts."""
    budget = _published_budget_v1(process_budget, process_budget_identity)
    bundle = contract.validate_projection_bundle_authority_v1(
        projection_bundle,
        publication_identity=projection_bundle_identity,
        topology=topology,
        topology_identity=topology_identity,
    )
    fold = int(fold_ordinal)
    if type(fold_ordinal) is not int or not 0 <= fold < contract.FOLDS_PER_SLATE:
        _fail("fold ordinal differs")
    expected_role = (
        "broad-fold-selector"
        if budget["phase"] == contract.BROAD_SCREEN_PHASE
        else "confirmation-fold-selector"
    )
    if (
        budget["process_role"] != expected_role
        or budget["source_ordinal"] != bundle["source_ordinal"]
        or budget["process_ordinal"]
        != bundle["source_ordinal"] * contract.FOLDS_PER_SLATE + fold
        or budget["projection_bundle_identity"]
        != contract._safe_object_identity(
            projection_bundle_identity, label="projection bundle identity"
        )
        or budget["topology_identity"]
        != contract._safe_object_identity(topology_identity, label="topology identity")
    ):
        _fail("selector budget does not authorize this exact bundle/fold")
    projection = bundle["fold_projections"][fold]
    lineup_ids = [str(row["lineup_id"]) for row in projection["candidates"]]
    scores = np.asarray(training_score_matrix)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.shape != (len(lineup_ids), 4 * contract.WORLDS_PER_BLOCK)
        or not np.isfinite(scores).all()
        or contract._float64_matrix_sha256_v1(scores, label="training matrix")
        != projection["expected_training_score_matrix_sha256"]
    ):
        _fail("training matrix differs from the exact sealed projection")
    full_ledger = contract._ordered_score_row_ledger_fixture_v1(lineup_ids, scores)
    samples = contract.deterministic_equal_count_samples_from_projection_v1(
        projection, phase=str(budget["phase"])
    )
    sample_by_key = {
        (int(rep["replicate"]), str(view["view_id"])): view
        for rep in samples["replicates"]
        for view in rep["views"]
    }
    strategies = _verify_live_registries_v1()
    strategy_by_id = {str(value["strategy_id"]): value for value in strategies}
    if budget["phase"] == contract.BROAD_SCREEN_PHASE:
        if any(value is not None for value in (
            nomination, nomination_identity, broad_phase_authority,
        )):
            _fail("broad selector cannot accept nomination authority")
        keys = [
            (0, view_id, str(strategy["strategy_id"]))
            for view_id in ["U", *(contract.isolated_view_id_v1(i) for i in range(7))]
            for strategy in strategies
        ]
    else:
        if nomination is None or nomination_identity is None or broad_phase_authority is None:
            _fail("confirmation selector requires exact nomination authority")
        nomination_value, _, _ = contract._validate_confirmation_nomination_authority_v1(
            nomination=nomination,
            nomination_identity=nomination_identity,
            broad_phase_authority=broad_phase_authority,
            topology=topology,
            topology_identity=topology_identity,
        )
        keys = [
            (replicate, view_id, strategy_id)
            for replicate in range(contract.SUBSAMPLE_REPLICATES)
            for view_id, strategy_id in contract._nominee_keys_v1(nomination_value)
        ]
    if budget["compute_fit_precharge"] != len(keys):
        _fail("selector execution lattice differs from its exact fit precharge")
    candidate_by_id = {str(row["lineup_id"]): row for row in projection["candidates"]}
    matrix_ordinal = {lineup_id: index for index, lineup_id in enumerate(lineup_ids)}
    cells: list[dict[str, object]] = []
    for replicate, view_id, strategy_id in keys:
        sample = sample_by_key[(replicate, view_id)]
        sampled_ids = [str(value) for value in sample["sampled_lineup_ids"]]
        sampled_scores = np.ascontiguousarray(
            scores[[matrix_ordinal[value] for value in sampled_ids]], dtype=np.float64
        )
        strategy = strategy_by_id[strategy_id]
        selected, trace = runner._run_strategy_v2(
            strategy, training_scores=sampled_scores, lineup_ids=sampled_ids
        )
        replay_selected, replay_trace = runner._run_strategy_v2(
            strategy, training_scores=sampled_scores, lineup_ids=sampled_ids
        )
        if selected != replay_selected or trace != replay_trace:
            _fail("selector replay differs")
        selected_ids = [sampled_ids[int(index)] for index in selected]
        sampled_ledger = contract._sampled_score_row_ledger_from_full_v1(
            full_ledger, sampled_ids
        )
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
    return contract._build_selection_fold_receipt_structural_v1(
        source_ordinal=int(bundle["source_ordinal"]),
        fold_ordinal=fold,
        projection=projection,
        phase=str(budget["phase"]),
        full_candidate_score_row_ledger=full_ledger,
        cells=cells,
        nomination=nomination,
        broad_phase_authority=broad_phase_authority,
    )


__all__ = [
    "CorpusR6CurrentBankCrossedScreenSelectorV1Error",
    "build_selection_fold_receipt_from_matrix_v1",
]
