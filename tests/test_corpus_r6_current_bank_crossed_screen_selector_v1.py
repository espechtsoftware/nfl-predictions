from __future__ import annotations

from hashlib import sha256
import inspect

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_contract_v1 as contract
from nfl_dfs.research import corpus_r6_current_bank_crossed_screen_selector_v1 as selector
import test_corpus_r6_current_bank_crossed_screen_contract_v1 as fixtures


def _identity(uri: str, body: object) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(body)
    return {
        "uri": uri,
        "generation": "7",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_authoritative_signature_accepts_no_caller_selection_facts() -> None:
    parameters = inspect.signature(
        selector.build_selection_fold_receipt_from_matrix_v1
    ).parameters
    assert not {
        "cells", "selected_ids", "selected_lineup_ids", "row_ledger",
        "full_candidate_score_row_ledger", "selection_trace",
    } & set(parameters)


def test_builder_executes_and_replays_live_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = fixtures.authorities.__wrapped__()
    budget = contract.compile_process_budget_v1(
        process_role="broad-fold-selector",
        projection_bundle=authority["bundle"],
        projection_bundle_identity=authority["bundle_identity"],
        topology=authority["topology"],
        topology_identity=authority["topology_identity"],
        source_ordinal=0,
        fold_ordinal=0,
    )
    budget_identity = _identity(
        contract.OUTPUT_NAMESPACE + "fixture-run/process-budgets/broad-000-0.json",
        budget,
    )
    calls: list[tuple[str, tuple[int, int]]] = []

    def fake_run(strategy: object, *, training_scores: np.ndarray, lineup_ids: object):
        calls.append((str(strategy["strategy_id"]), training_scores.shape))
        return list(range(contract.ENTRY_BUDGET)), []

    monkeypatch.setattr(selector.runner, "_run_strategy_v2", fake_run)
    receipt = selector.build_selection_fold_receipt_from_matrix_v1(
        projection_bundle=authority["bundle"],
        projection_bundle_identity=authority["bundle_identity"],
        topology=authority["topology"],
        topology_identity=authority["topology_identity"],
        process_budget=budget,
        process_budget_identity=budget_identity,
        fold_ordinal=0,
        training_score_matrix=authority["training_scores"],
    )
    assert receipt["cell_count"] == contract.BROAD_FITS_PER_FOLD
    assert len(calls) == 2 * contract.BROAD_FITS_PER_FOLD
    assert calls[0][1] == (80, 4 * contract.WORLDS_PER_BLOCK)

    tampered = authority["training_scores"].copy()
    tampered[0, 0] += 1.0
    with pytest.raises(
        selector.CorpusR6CurrentBankCrossedScreenSelectorV1Error,
        match="training matrix differs",
    ):
        selector.build_selection_fold_receipt_from_matrix_v1(
            projection_bundle=authority["bundle"],
            projection_bundle_identity=authority["bundle_identity"],
            topology=authority["topology"],
            topology_identity=authority["topology_identity"],
            process_budget=budget,
            process_budget_identity=budget_identity,
            fold_ordinal=0,
            training_score_matrix=tampered,
        )


def test_live_registry_drift_fails_before_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    live = contract.frozen_strategies_v1()
    live[0]["strategy_sha256"] = "f" * 64
    monkeypatch.setattr(selector.fast_lane, "frozen_full_union_strategies_v1", lambda: live)
    with pytest.raises(
        selector.CorpusR6CurrentBankCrossedScreenSelectorV1Error,
        match="live selector registries differ",
    ):
        selector._verify_live_registries_v1()
