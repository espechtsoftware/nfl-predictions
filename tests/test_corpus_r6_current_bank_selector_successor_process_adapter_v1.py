from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from tests import (
    test_corpus_r6_current_bank_selector_successor_authority_v1
    as authority_fixtures,
)


def _identity(tag: str, raw: bytes = b"fixture") -> dict[str, object]:
    return {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            f"successor-process-adapter-fixture/{tag}.json"
        ),
        "generation": str(900_000 + len(tag)),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _body_identity(tag: str, value: object) -> dict[str, object]:
    raw = contract.canonical_json_bytes_v1(value)
    return _identity(tag, raw)


def _source_process_budget(
    matrix_capability: dict[str, object],
) -> dict[str, object]:
    source = int(matrix_capability["source_ordinal"])
    fold = int(matrix_capability["fold_ordinal"])
    heldout = contract.WORLD_BLOCKS[fold]
    read_roles = [
        "projection-bundle",
        "later-source",
        *[
            f"training-world-{block}"
            for block in contract.WORLD_BLOCKS
            if block != heldout
        ],
    ]
    reads = [
        {
            "role": role,
            "identity": _identity(f"read-{ordinal}-{role}"),
        }
        for ordinal, role in enumerate(read_roles)
    ]
    body = {
        "schema_version": contract.PROCESS_BUDGET_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "process_role": "broad-fold-selector",
        "phase": contract.BROAD_SCREEN_PHASE,
        "source_ordinal": source,
        "process_ordinal": source * contract.FOLDS_PER_SLATE + fold,
        "child_run_prefix": "successor-process-adapter-fixture",
        "topology_identity": _identity("topology"),
        "projection_bundle_identity": _identity("projection-bundle"),
        "read_allowlist": reads,
        "read_object_count": len(reads),
        "read_byte_ceiling": sum(
            int(row["identity"]["bytes"]) for row in reads
        ),
        "write_allowlist": [],
        "write_object_count": 0,
        "write_byte_ceiling": 0,
        "child_output_byte_ceiling": contract._ROLE_OUTPUT_BYTE_CEILINGS[
            "broad-fold-selector"
        ],
        "compute_fit_precharge": contract.BROAD_FITS_PER_FOLD,
        "all_block_fit_count": 0,
        "current_generation_lookup_allowed": False,
        "endpoint_override_allowed": False,
        "environment_redirect_allowed": False,
        "git_ref_redirect_allowed": False,
        "policy": dict(contract.POLICY_CLAIMS),
    }
    body["process_budget_sha256"] = contract.canonical_sha256_v1(body)
    return contract.validate_process_budget_v1(body)


@pytest.fixture(scope="module")
def adapter_fixture() -> dict[str, object]:
    scores = authority_fixtures._scores()
    matrix_capability = authority_fixtures._capability(scores)
    scores.flags.writeable = False
    runtime = authority_fixtures._runtime()
    candidates = matrix_capability["projection_scientific_binding"][
        "candidates"
    ]
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    grouped = successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=matrix_capability[
            "projection_scientific_binding"
        ]["training_blocks"],
        worlds_per_block=authority.EXACT_WORLDS_PER_BLOCK,
        preset_registry=successor.frozen_native_preset_registry_v1(),
    )

    original_run = successor.run_grouped_native_selectors_v1
    try:
        successor.run_grouped_native_selectors_v1 = (
            lambda **_: deepcopy(grouped)
        )
        response = authority.run_authority_bound_broad_selectors_v1(
            matrix_capability=matrix_capability,
            training_score_matrix=scores,
            runtime_evidence=runtime,
        )
    finally:
        successor.run_grouped_native_selectors_v1 = original_run

    source_budget = _source_process_budget(matrix_capability)
    source_budget_identity = _body_identity("source-budget", source_budget)
    budget = adapter.compile_successor_process_budget_v1(
        source_process_budget=source_budget,
        source_process_budget_identity=source_budget_identity,
        matrix_capability=matrix_capability,
    )
    return {
        "scores": scores,
        "matrix_capability": matrix_capability,
        "runtime": runtime,
        "grouped": grouped,
        "response": response,
        "source_budget": source_budget,
        "source_budget_identity": source_budget_identity,
        "budget": budget,
        "budget_identity": _body_identity("successor-budget", budget),
        "launch_identity": _identity("launch-intent"),
    }


def _install_exact_response_validator(
    monkeypatch: pytest.MonkeyPatch,
    fixture: dict[str, object],
) -> None:
    expected = fixture["response"]

    def validate(value: object, **_: object) -> dict[str, object]:
        if contract.canonical_json_bytes_v1(value) != (
            contract.canonical_json_bytes_v1(expected)
        ):
            raise authority.CorpusR6CurrentBankSelectorSuccessorAuthorityV1Error(
                "fixture response differs"
            )
        return deepcopy(expected)

    monkeypatch.setattr(
        authority,
        "validate_authority_bound_broad_selector_response_v1",
        validate,
    )


def _build_receipt(
    fixture: dict[str, object],
    **changes: object,
) -> dict[str, object]:
    arguments = {
        "successor_process_budget": fixture["budget"],
        "successor_process_budget_identity": fixture["budget_identity"],
        "source_process_budget": fixture["source_budget"],
        "source_process_budget_identity": fixture["source_budget_identity"],
        "matrix_capability": fixture["matrix_capability"],
        "training_score_matrix": fixture["scores"],
        "runtime_evidence": fixture["runtime"],
        "authority_response": fixture["response"],
        "launch_intent_identity": fixture["launch_identity"],
    }
    arguments.update(changes)
    return adapter.build_successor_broad_fold_receipt_v1(**arguments)


def test_exact_24_fit_budget_capability_launch_and_fold_receipt(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_response_validator(monkeypatch, adapter_fixture)
    budget = adapter_fixture["budget"]
    assert budget["compute_fit_precharge"] == 24
    assert budget["view_count_precharge"] == 8
    assert budget["selector_count_per_view_precharge"] == 3
    # Current committed control is 8 views x 8 strategies = 64.  It is a
    # source-read authority only, never a claimed fit-equivalent receipt.
    assert budget["source_control_fit_precharge"] == 64
    assert budget["source_control_fit_parity_claimed"] is False
    assert budget["source_control_receipt_compatible"] is False

    capability = adapter.build_successor_matrix_child_capability_v1(
        successor_process_budget=budget,
        successor_process_budget_identity=adapter_fixture["budget_identity"],
        source_process_budget=adapter_fixture["source_budget"],
        source_process_budget_identity=adapter_fixture[
            "source_budget_identity"
        ],
        matrix_capability=adapter_fixture["matrix_capability"],
        launch_intent_identity=adapter_fixture["launch_identity"],
    )
    assert capability["fit_count_precharge"] == 24
    assert capability["heldout_artifact_addressable"] is False
    assert capability["dispatcher_wiring_authority_required"] is True

    receipt = _build_receipt(adapter_fixture)
    assert receipt["schema_version"] == adapter.FOLD_RECEIPT_SCHEMA
    assert receipt["fit_count"] == 24
    assert len(receipt["cell_sha256s"]) == 24
    assert receipt["source_control_fit_precharge"] == 64
    assert receipt["source_control_fit_parity_claimed"] is False
    assert receipt["source_control_receipt_compatible"] is False
    assert receipt["folds_assembled"] == 1
    assert receipt["slate_fold_count_required_for_downstream_assembly"] == 5
    assert receipt["publication_authority"] is False
    envelope = receipt["outer_launch_envelope"]
    assert envelope["outer_launch_authority_identity"] == adapter_fixture[
        "launch_identity"
    ]
    assert envelope["runtime_evidence_sha256"] == adapter_fixture[
        "runtime"
    ]["runtime_evidence_sha256"]
    assert envelope["terminal_execution_attestation_present"] is False
    assert envelope["dispatcher_wiring_authority_present"] is False

    replay = adapter.validate_successor_broad_fold_receipt_v1(
        receipt,
        successor_process_budget=budget,
        successor_process_budget_identity=adapter_fixture["budget_identity"],
        source_process_budget=adapter_fixture["source_budget"],
        source_process_budget_identity=adapter_fixture[
            "source_budget_identity"
        ],
        matrix_capability=adapter_fixture["matrix_capability"],
        training_score_matrix=adapter_fixture["scores"],
        runtime_evidence=adapter_fixture["runtime"],
        authority_response=adapter_fixture["response"],
        launch_intent_identity=adapter_fixture["launch_identity"],
    )
    assert replay == receipt


def test_real_authority_validator_is_exercised_at_receipt_boundary(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def grouped(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return deepcopy(adapter_fixture["grouped"])

    monkeypatch.setattr(successor, "run_grouped_native_selectors_v1", grouped)
    receipt = _build_receipt(adapter_fixture)
    assert receipt["fit_count"] == 24
    assert len(calls) == 8


def test_rehashed_fit_budget_tamper_cannot_claim_25_cells(
    adapter_fixture: dict[str, object],
) -> None:
    changed = deepcopy(adapter_fixture["budget"])
    changed["compute_fit_precharge"] = 25
    changed["successor_process_budget_sha256"] = (
        contract.canonical_sha256_v1({
            key: value
            for key, value in changed.items()
            if key != "successor_process_budget_sha256"
        })
    )
    with pytest.raises(
        adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        match="differs from exact source adaptation",
    ):
        adapter.validate_successor_process_budget_v1(
            changed,
            source_process_budget=adapter_fixture["source_budget"],
            source_process_budget_identity=adapter_fixture[
                "source_budget_identity"
            ],
            matrix_capability=adapter_fixture["matrix_capability"],
        )


def test_source_control_must_remain_distinct_from_successor_budget(
    adapter_fixture: dict[str, object],
) -> None:
    changed_source = deepcopy(adapter_fixture["source_budget"])
    changed_source["compute_fit_precharge"] = 24
    changed_source["process_budget_sha256"] = contract.canonical_sha256_v1({
        key: value
        for key, value in changed_source.items()
        if key != "process_budget_sha256"
    })
    changed_identity = _body_identity("changed-source-budget", changed_source)
    with pytest.raises(
        adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        match="source control authority differs|phase/process/fit authority differs",
    ):
        adapter.compile_successor_process_budget_v1(
            source_process_budget=changed_source,
            source_process_budget_identity=changed_identity,
            matrix_capability=adapter_fixture["matrix_capability"],
        )


def test_preparation_projection_compiles_same_budget_as_runtime_capability(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scientific = adapter_fixture["matrix_capability"][
        "projection_scientific_binding"
    ]
    narrow_projection = {
        "projection_sha256": scientific["projection_sha256"],
        "slate_id": scientific["slate_id"],
        "fit_scope_id": scientific["fit_scope_id"],
        "training_blocks": scientific["training_blocks"],
        "heldout_block": scientific["heldout_block_label"],
        "expected_training_score_matrix_sha256": scientific[
            "training_score_matrix_sha256"
        ],
    }
    monkeypatch.setattr(
        contract,
        "validate_narrow_projection_v1",
        lambda value: dict(narrow_projection),
    )
    prepared = adapter.compile_successor_process_budget_v1(
        source_process_budget=adapter_fixture["source_budget"],
        source_process_budget_identity=adapter_fixture[
            "source_budget_identity"
        ],
        source_projection={"pre_matrix": True},
    )
    assert prepared == adapter_fixture["budget"]
    assert prepared["compute_fit_precharge"] == 24
    assert "source_matrix_capability_sha256" not in prepared


def test_runtime_task_tamper_fails_outer_launch_binding(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_response_validator(monkeypatch, adapter_fixture)
    changed_runtime = deepcopy(adapter_fixture["runtime"])
    changed_runtime["task_index"] = 1
    changed_runtime["runtime_evidence_sha256"] = contract.canonical_sha256_v1({
        key: value
        for key, value in changed_runtime.items()
        if key != "runtime_evidence_sha256"
    })
    with pytest.raises(
        adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        match="launch capability/budget/runtime binding differs",
    ):
        _build_receipt(adapter_fixture, runtime_evidence=changed_runtime)


def test_response_tamper_is_rejected_before_receipt(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_response_validator(monkeypatch, adapter_fixture)
    changed = deepcopy(adapter_fixture["response"])
    changed["fit_count"] = 25
    changed["authority_response_sha256"] = contract.canonical_sha256_v1({
        key: value
        for key, value in changed.items()
        if key != "authority_response_sha256"
    })
    with pytest.raises(
        adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        match="successor authority response differs",
    ):
        _build_receipt(adapter_fixture, authority_response=changed)


def test_rehashed_launch_envelope_tamper_fails_exact_replay(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_response_validator(monkeypatch, adapter_fixture)
    receipt = _build_receipt(adapter_fixture)
    capability = receipt["successor_matrix_child_capability"]
    envelope = deepcopy(receipt["outer_launch_envelope"])
    envelope["terminal_execution_attestation_present"] = True
    envelope["outer_launch_envelope_sha256"] = contract.canonical_sha256_v1({
        key: value
        for key, value in envelope.items()
        if key != "outer_launch_envelope_sha256"
    })
    with pytest.raises(
        adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        match="differs from exact replay",
    ):
        adapter.validate_successor_outer_launch_envelope_v1(
            envelope,
            successor_capability=capability,
            successor_process_budget=adapter_fixture["budget"],
            successor_process_budget_identity=adapter_fixture[
                "budget_identity"
            ],
            runtime_evidence=adapter_fixture["runtime"],
            authority_response=adapter_fixture["response"],
            launch_intent_identity=adapter_fixture["launch_identity"],
        )


def test_fold_receipt_tamper_fails_even_when_self_hash_is_repaired(
    adapter_fixture: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_response_validator(monkeypatch, adapter_fixture)
    receipt = _build_receipt(adapter_fixture)
    changed = deepcopy(receipt)
    changed["publication_authority"] = True
    changed["successor_fold_receipt_sha256"] = contract.canonical_sha256_v1({
        key: value
        for key, value in changed.items()
        if key != "successor_fold_receipt_sha256"
    })
    with pytest.raises(
        adapter.CorpusR6CurrentBankSelectorSuccessorProcessAdapterV1Error,
        match="differs from exact replay",
    ):
        adapter.validate_successor_broad_fold_receipt_v1(
            changed,
            successor_process_budget=adapter_fixture["budget"],
            successor_process_budget_identity=adapter_fixture[
                "budget_identity"
            ],
            source_process_budget=adapter_fixture["source_budget"],
            source_process_budget_identity=adapter_fixture[
                "source_budget_identity"
            ],
            matrix_capability=adapter_fixture["matrix_capability"],
            training_score_matrix=adapter_fixture["scores"],
            runtime_evidence=adapter_fixture["runtime"],
            authority_response=adapter_fixture["response"],
            launch_intent_identity=adapter_fixture["launch_identity"],
        )
