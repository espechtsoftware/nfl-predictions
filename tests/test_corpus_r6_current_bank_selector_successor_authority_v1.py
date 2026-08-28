from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

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


def _candidates(training_blocks: list[str]) -> list[dict[str, object]]:
    profiles = sorted(value[1] for value in contract.PROFILE_IDENTITIES)
    rows: list[dict[str, object]] = []
    for ordinal in range(successor.ENTRY_BUDGET):
        roster = [f"p-{ordinal:03d}-{slot}" for slot in range(successor.ROSTER_SIZE)]
        rows.append({
            "lineup_id": f"lineup-{ordinal:03d}",
            "roster_player_ids": sorted(roster),
            "training_origin_blocks": list(training_blocks),
            "training_source_arms": profiles,
            "training_occurrence_counts_by_block": {
                block: 1 for block in training_blocks
            },
            "training_source_arms_by_block": {
                block: profiles for block in training_blocks
            },
            "training_occurrence_count": len(training_blocks),
        })
    return rows


def _scores() -> np.ndarray:
    world = np.arange(
        4 * authority.EXACT_WORLDS_PER_BLOCK, dtype=np.float64
    )
    scores = np.empty(
        (successor.ENTRY_BUDGET, world.size), dtype=np.float64, order="C"
    )
    for ordinal in range(successor.ENTRY_BUDGET):
        scores[ordinal] = (
            145.0
            + np.remainder(world * (ordinal + 3) + ordinal * 19, 131.0)
            + (ordinal % 7) * 0.125
        )
    return scores


def _capability(scores: np.ndarray) -> dict[str, object]:
    heldout = contract.WORLD_BLOCKS[0]
    training_blocks = [
        block for block in contract.WORLD_BLOCKS if block != heldout
    ]
    candidates = _candidates(training_blocks)
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    matrix_sha256 = contract._float64_matrix_sha256_v1(
        scores, label="authority fixture matrix"
    )
    projection = {
        "projection_sha256": "1" * 64,
        "slate_id": "2025-w18",
        "fit_scope_id": f"holdout-{heldout}",
        "training_blocks": training_blocks,
        "heldout_block_label": heldout,
        "training_world_columns_sha256": (
            contract.canonical_world_columns_sha256_v1(training_blocks)
        ),
        "candidates": candidates,
        "candidate_lineup_order_sha256": contract.canonical_sha256_v1(
            lineup_ids
        ),
        "candidate_rosters_sha256": contract.canonical_sha256_v1([
            row["roster_player_ids"] for row in candidates
        ]),
        "candidate_rows_sha256": contract.canonical_sha256_v1(candidates),
        "training_score_matrix_sha256": matrix_sha256,
        "training_score_shape": list(scores.shape),
    }
    view_registry = contract._derive_view_registry_fixture_v1(candidates)
    samples = contract._deterministic_equal_count_samples_fixture_v1(
        view_registry=view_registry,
        slate_id=str(projection["slate_id"]),
        fit_scope_id=str(projection["fit_scope_id"]),
        phase=contract.BROAD_SCREEN_PHASE,
    )
    strategies = contract.frozen_strategies_v1()
    descriptor = worker._matrix_descriptor_v1(
        scores, expected_matrix_sha256=matrix_sha256
    )
    body = {
        "schema_version": worker.MATRIX_CAPABILITY_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": 0,
        "fold_ordinal": 0,
        "process_ordinal": 0,
        "projection_scientific_binding": projection,
        "projection_scientific_binding_sha256": (
            contract.canonical_sha256_v1(projection)
        ),
        "samples": samples,
        "samples_sha256": contract.canonical_sha256_v1(samples),
        "strategies": strategies,
        "strategy_registry_sha256": contract.canonical_sha256_v1(strategies),
        "fit_count_precharge": len(strategies) * authority.EXACT_BROAD_VIEW_COUNT,
        "nominee_keys": None,
        "matrix_descriptor": descriptor,
        "matrix_bytes_embedded": False,
        "object_store_transport_capability_exposed": False,
        "inherited_local_matrix_fd_exposed": True,
        "object_identity_exposed": False,
        "heldout_artifact_identity_exposed": False,
        "heldout_artifact_body_exposed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["matrix_capability_sha256"] = contract.canonical_sha256_v1(body)
    return worker.validate_matrix_capability_v1(body)


def _runtime() -> dict[str, object]:
    environment = {
        "GOOGLE_CLOUD_PROJECT": successor_runtime.FIXED_GCP_PROJECT,
        "CODE_SHA": "a" * 40,
        "R6_RUNTIME_IMAGE_DIGEST": "sha256:" + "b" * 64,
        "CLOUD_RUN_JOB": "authority-fixture",
        "CLOUD_RUN_EXECUTION": "authority-fixture-00001",
        "CLOUD_RUN_TASK_INDEX": "0",
        successor_runtime.PROCESS_ORDINAL_ENV: "0",
    }
    command = successor_runtime.canonical_matrix_selector_command_v1()
    return successor_runtime.build_runtime_evidence_v1(
        process_ordinal=0,
        environ=environment,
        observed_command=command,
        pid=211,
        parent_pid=101,
    )


@pytest.fixture(scope="module")
def production_authority_fixture() -> dict[str, object]:
    scores = _scores()
    capability = _capability(scores)
    scores.flags.writeable = False
    candidates = capability["projection_scientific_binding"]["candidates"]
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    # Every broad fixture view contains the same exact 80 rows.  Execute the
    # real grouped implementation once, then use its immutable result to keep
    # authority-boundary tests lean while still exercising production shape.
    grouped = successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=capability["projection_scientific_binding"][
            "training_blocks"
        ],
        worlds_per_block=authority.EXACT_WORLDS_PER_BLOCK,
        preset_registry=successor.frozen_native_preset_registry_v1(),
    )
    return {
        "scores": scores,
        "capability": capability,
        "runtime": _runtime(),
        "grouped": grouped,
    }


def _install_grouped_fixture(
    monkeypatch: pytest.MonkeyPatch,
    fixture: dict[str, object],
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def run(**kwargs: object) -> dict[str, object]:
        matrix = kwargs["training_score_matrix"]
        assert isinstance(matrix, np.ndarray)
        assert matrix.flags.writeable is False
        assert matrix.flags.c_contiguous
        assert matrix is not fixture["scores"]
        assert kwargs["worlds_per_block"] == authority.EXACT_WORLDS_PER_BLOCK
        calls.append(kwargs)
        return deepcopy(fixture["grouped"])

    monkeypatch.setattr(successor, "run_grouped_native_selectors_v1", run)
    return calls


def _rehash_capability(value: dict[str, object]) -> None:
    value["matrix_capability_sha256"] = contract.canonical_sha256_v1({
        key: item for key, item in value.items()
        if key != "matrix_capability_sha256"
    })


def _rehash_runtime(value: dict[str, object]) -> None:
    value["runtime_evidence_sha256"] = contract.canonical_sha256_v1({
        key: item for key, item in value.items()
        if key != "runtime_evidence_sha256"
    })


def test_frozen_authority_contract_is_exact_and_does_not_claim_publication() -> None:
    frozen = authority.frozen_authority_wrapper_v1()
    assert frozen["authority_wrapper_sha256"] == (
        authority.EXPECTED_AUTHORITY_WRAPPER_SHA256
    )
    assert frozen["worlds_per_block"] == 10_000
    assert frozen["broad_view_count"] == 8
    assert frozen["selector_count_per_view"] == 3
    assert frozen["broad_cell_count"] == 24
    assert frozen["confirmation_supported"] is False
    assert frozen["existing_fold_receipt_compatible"] is False
    assert frozen["successor_process_budget_required"] is True
    assert frozen["policy"]["scientific_input_authority_validated"] is True
    assert frozen["policy"]["outer_launch_authority_binding_required"] is True
    assert frozen["policy"]["publication_authority"] is False
    assert frozen["policy"]["promotion_authority"] is False


def test_broad_wrapper_runs_three_once_per_view_and_replays_exactly(
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_grouped_fixture(monkeypatch, production_authority_fixture)
    result = authority.run_authority_bound_broad_selectors_v1(
        matrix_capability=production_authority_fixture["capability"],
        training_score_matrix=production_authority_fixture["scores"],
        runtime_evidence=production_authority_fixture["runtime"],
    )
    assert len(calls) == 8
    assert result["view_count"] == 8
    assert result["selector_count_per_view"] == 3
    assert result["fit_count"] == 24
    assert [row["view_id"] for row in result["views"]] == [
        "U",
        *(contract.isolated_view_id_v1(index) for index in range(7)),
    ]
    expected_presets = [
        row["preset_id"] for row in successor.frozen_native_preset_registry_v1()
    ]
    for view in result["views"]:
        assert view["sampled_matrix_copy_count"] == 1
        assert view["grouped_selector_invocation_count"] == 1
        assert view["selector_count"] == 3
        assert [row["preset_id"] for row in view["cells"]] == expected_presets
        assert all(len(row["selected_lineup_ids"]) == 80 for row in view["cells"])
        assert all(
            row["training_score_row_ledger"]["world_count"] == 40_000
            for row in view["cells"]
        )
    assert result["authority_binding"][
        "matrix_authority_recomputed_from_read_only_bytes"
    ] is True
    assert result["authority_binding"][
        "sample_authority_replayed_from_projection"
    ] is True
    assert result["authority_binding"][
        "score_row_ledger_rederived_from_matrix"
    ] is True
    assert result["authority_binding"]["source_capability_fit_count_precharge"] == (
        len(contract.frozen_strategies_v1()) * 8
    )
    assert result["authority_binding"]["successor_broad_fit_count"] == 24
    assert result["authority_binding"]["existing_fold_receipt_compatible"] is False
    assert result["authority_binding"]["successor_process_budget_required"] is True
    replay = authority.validate_authority_bound_broad_selector_response_v1(
        result,
        matrix_capability=production_authority_fixture["capability"],
        training_score_matrix=production_authority_fixture["scores"],
        runtime_evidence=production_authority_fixture["runtime"],
    )
    assert replay == result
    assert len(calls) == 16


def test_capability_and_projection_authority_tamper_fail_before_selectors(
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_grouped_fixture(monkeypatch, production_authority_fixture)
    capability = deepcopy(production_authority_fixture["capability"])
    capability["matrix_capability_sha256"] = "0" * 64
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match="capability authority differs",
    ):
        authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=capability,
            training_score_matrix=production_authority_fixture["scores"],
            runtime_evidence=production_authority_fixture["runtime"],
        )
    assert not calls

    capability = deepcopy(production_authority_fixture["capability"])
    projection = capability["projection_scientific_binding"]
    projection["candidate_rows_sha256"] = "2" * 64
    capability["projection_scientific_binding_sha256"] = (
        contract.canonical_sha256_v1(projection)
    )
    _rehash_capability(capability)
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match="candidate identity/hash authority differs",
    ):
        authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=capability,
            training_score_matrix=production_authority_fixture["scores"],
            runtime_evidence=production_authority_fixture["runtime"],
        )
    assert not calls


def test_rehashed_sample_tamper_is_rejected_by_deterministic_replay(
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_grouped_fixture(monkeypatch, production_authority_fixture)
    capability = deepcopy(production_authority_fixture["capability"])
    samples = capability["samples"]
    sample = samples["replicates"][0]["views"][0]
    sample["sampled_lineup_ids"][:2] = reversed(
        sample["sampled_lineup_ids"][:2]
    )
    sample["sampled_lineup_ids_sha256"] = contract.canonical_sha256_v1(
        sample["sampled_lineup_ids"]
    )
    samples["subsample_sha256"] = contract.canonical_sha256_v1({
        key: item for key, item in samples.items() if key != "subsample_sha256"
    })
    capability["samples_sha256"] = contract.canonical_sha256_v1(samples)
    _rehash_capability(capability)
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match="sample authority differs",
    ):
        authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=capability,
            training_score_matrix=production_authority_fixture["scores"],
            runtime_evidence=production_authority_fixture["runtime"],
        )
    assert not calls


@pytest.mark.parametrize("kind", ["writeable", "changed-bytes"])
def test_matrix_tamper_fails_before_selectors(
    kind: str,
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_grouped_fixture(monkeypatch, production_authority_fixture)
    matrix = production_authority_fixture["scores"].copy()
    if kind == "changed-bytes":
        matrix[0, 0] += 1.0
        matrix.flags.writeable = False
        pattern = "descriptor authority differs|bytes differ"
    else:
        pattern = "read-only dtype/shape authority differs"
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match=pattern,
    ):
        authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=production_authority_fixture["capability"],
            training_score_matrix=matrix,
            runtime_evidence=production_authority_fixture["runtime"],
        )
    assert not calls


def test_rehashed_runtime_tamper_fails_before_selectors(
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_grouped_fixture(monkeypatch, production_authority_fixture)
    runtime = deepcopy(production_authority_fixture["runtime"])
    runtime["task_index"] = 1
    _rehash_runtime(runtime)
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match="runtime process/task/capability authority differs",
    ):
        authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=production_authority_fixture["capability"],
            training_score_matrix=production_authority_fixture["scores"],
            runtime_evidence=runtime,
        )
    assert not calls


def test_confirmation_fails_closed_before_matrix_copy_or_selectors(
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_grouped_fixture(monkeypatch, production_authority_fixture)
    capability = deepcopy(production_authority_fixture["capability"])
    capability["phase"] = contract.CONFIRMATION_PHASE
    capability["nominee_keys"] = [[
        "U", capability["strategies"][0]["strategy_id"]
    ]]
    capability["fit_count_precharge"] = contract.SUBSAMPLE_REPLICATES
    _rehash_capability(capability)
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match="confirmation is closed",
    ):
        authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=capability,
            training_score_matrix=production_authority_fixture["scores"],
            runtime_evidence=production_authority_fixture["runtime"],
        )
    assert not calls


def test_response_tamper_is_not_replay_validatable(
    production_authority_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_grouped_fixture(monkeypatch, production_authority_fixture)
    result = authority.run_authority_bound_broad_selectors_v1(
        matrix_capability=production_authority_fixture["capability"],
        training_score_matrix=production_authority_fixture["scores"],
        runtime_evidence=production_authority_fixture["runtime"],
    )
    tampered = deepcopy(result)
    tampered["cell_sha256s"][0] = sha256(b"tamper").hexdigest()
    tampered["authority_response_sha256"] = contract.canonical_sha256_v1({
        key: item for key, item in tampered.items()
        if key != "authority_response_sha256"
    })
    with pytest.raises(
        authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error,
        match="differs from exact canonical replay",
    ):
        authority.validate_authority_bound_broad_selector_response_v1(
            tampered,
            matrix_capability=production_authority_fixture["capability"],
            training_score_matrix=production_authority_fixture["scores"],
            runtime_evidence=production_authority_fixture["runtime"],
        )
