from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_preweek_additions as additions
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research.corpus_legal_feasibility import canonical_sha256


WIDTH = 8
BLOCKS = ("R0", "R1", "R2", "R3")
MASK_SHA = "a" * 64
LINEAGE_SHA = "b" * 64
SOURCE_MANIFEST = {
    "manifest_id": "preweek-additions-fixture-v1",
    "manifest_sha256": "c" * 64,
    "object_identity": {
        "uri": "gs://fixture/manifests/preweek-additions.json",
        "generation": "101",
        "sha256": "d" * 64,
        "bytes": 1234,
    },
}
SOURCE_MEMBER = {
    "member_id": "member-2023-w01",
    "member_ordinal": 0,
    "member_sha256": "e" * 64,
    "slate_id": "2023-w01",
}
SOURCE_MATRIX = {
    "matrix_id": "matrix-2023-w01",
    "matrix_sha256": "f" * 64,
    "object_identity": {
        "uri": "gs://fixture/matrices/2023-w01.npz",
        "generation": "202",
        "sha256": "0" * 64,
        "bytes": 5678,
    },
}


def _ids(count: int = 90) -> list[str]:
    return [f"lineup-{index:03d}" for index in range(count)]


def _scores(value: float = 231.0, count: int = 90) -> np.ndarray:
    return np.ascontiguousarray(
        np.full((count, len(BLOCKS) * WIDTH), value), dtype=np.float64
    )


def _kwargs(
    *,
    lineup_ids: list[str] | None = None,
    scores: np.ndarray | None = None,
    blocks: tuple[str, ...] = BLOCKS,
    heldout: str | None = "R4",
    width: int = WIDTH,
    candidate_mask_sha256: str = MASK_SHA,
    occurrence_lineage_sha256: str = LINEAGE_SHA,
    source_manifest_identity: dict[str, object] = SOURCE_MANIFEST,
    source_member_identity: dict[str, object] = SOURCE_MEMBER,
    source_score_matrix_identity: dict[str, object] = SOURCE_MATRIX,
) -> dict[str, object]:
    ids = _ids() if lineup_ids is None else lineup_ids
    matrix = _scores(count=len(ids)) if scores is None else scores
    return {
        "lineup_ids": ids,
        "fit_scores": matrix,
        "training_blocks": blocks,
        "heldout_block": heldout,
        "worlds_per_block": width,
        "candidate_mask_sha256": candidate_mask_sha256,
        "occurrence_lineage_sha256": occurrence_lineage_sha256,
        "source_manifest_identity": source_manifest_identity,
        "source_member_identity": source_member_identity,
        "source_score_matrix_identity": source_score_matrix_identity,
        "require_production_width": False,
    }


def _run(**overrides: object) -> dict[str, object]:
    return additions.run_extreme_tail_preweek_additions_v1(
        **_kwargs(**overrides)
    )


def _selector(
    receipt: dict[str, object], strategy_id: str
) -> dict[str, object]:
    matches = [
        row for row in receipt["selectors"] if row["strategy_id"] == strategy_id
    ]
    assert len(matches) == 1
    return matches[0]


def _rehash_book(book: dict[str, object]) -> None:
    book["book_sha256"] = canonical_sha256(
        {key: value for key, value in book.items() if key != "book_sha256"}
    )


def _rehash_selector(selector: dict[str, object]) -> None:
    for book in selector["books"]:
        _rehash_book(book)
    selector["selector_receipt_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in selector.items()
            if key != "selector_receipt_sha256"
        }
    )


def _rehash_oracle(oracle: dict[str, object]) -> None:
    for row in oracle["rows"]:
        row["oracle_row_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in row.items()
                if key != "oracle_row_sha256"
            }
        )
    oracle["rows_sha256"] = canonical_sha256(
        [row["oracle_row_sha256"] for row in oracle["rows"]]
    )
    oracle["solver_proof_sha256s"] = [
        row["solver_proof_sha256"] for row in oracle["rows"]
    ]
    oracle["solver_proof_sha256s_sha256"] = canonical_sha256(
        oracle["solver_proof_sha256s"]
    )
    oracle["oracle_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in oracle.items()
            if key != "oracle_sha256"
        }
    )


def _rehash_receipt(receipt: dict[str, object]) -> None:
    for selector in receipt["selectors"]:
        _rehash_selector(selector)
    _rehash_oracle(receipt["oracle"])
    receipt["selectors_sha256"] = canonical_sha256(
        [row["selector_receipt_sha256"] for row in receipt["selectors"]]
    )
    receipt["oracle_sha256"] = receipt["oracle"]["oracle_sha256"]
    receipt["receipt_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_sha256"
        }
    )


def _model_identity(
    *, receipt: dict[str, object], row: dict[str, object]
) -> str:
    oracle = receipt["oracle"]
    return canonical_sha256(
        {
            "input_binding_sha256": receipt["input_binding_sha256"],
            "event_incidence_sha256": oracle["event_incidence_sha256"],
            "entry_budget": row["entry_budget"],
            "candidate_count": row["candidate_count"],
            "opportunity_world_count": row["opportunity_world_count"],
            "event_edge_count": row["event_edge_count"],
            "objective": "maximize-distinct-inclusive-230-covered-worlds",
            "candidate_constraint": (
                "sum-binary-candidate-selection-equals-budget"
            ),
            "coverage_constraint": (
                "binary-world-covered-le-sum-selected-hitters"
            ),
        }
    )


def _refresh_runtime_and_input_pointers(receipt: dict[str, object]) -> None:
    input_binding = receipt["input_binding"]
    input_hash = input_binding["input_binding_sha256"]
    receipt["input_binding_sha256"] = input_hash
    for selector in receipt["selectors"]:
        selector["input_binding_sha256"] = input_hash
        for book in selector["books"]:
            book["input_binding_sha256"] = input_hash
    oracle = receipt["oracle"]
    oracle["input_binding_sha256"] = input_hash
    backend = oracle["backend"]
    backend_hash = canonical_sha256(backend)
    for row in oracle["rows"]:
        model_hash = _model_identity(receipt=receipt, row=row)
        row["model_identity_sha256"] = model_hash
        row["threads"] = backend["threads"]
        row["seed_options"] = backend["seed_options"]
        row["gap_relative"] = backend["gap_relative"]
        row["gap_absolute"] = backend["gap_absolute"]
        row["presolve"] = backend["presolve"]
        row["cuts"] = backend["cuts"]
        row["strong"] = backend["strong"]
        row["warm_start"] = backend["warm_start"]
        row["time_mode"] = backend["time_mode"]
        row["time_limit_seconds"] = backend["time_limit_seconds"]
        row["wall_clock_telemetry_in_identity"] = backend[
            "wall_clock_fields_in_identity"
        ]
        row["deterministic_work_limit_law"] = backend[
            "deterministic_work_limit_law"
        ]
        row["node_limit"] = backend["node_limits"][str(row["entry_budget"])]
        proof = row["solver_proof"]
        proof["model_identity_sha256"] = model_hash
        proof["backend_identity_sha256"] = backend_hash
        options = proof["execution_options"]
        options["gap_relative"] = backend["gap_relative"]
        options["gap_absolute"] = backend["gap_absolute"]
        options["presolve"] = backend["presolve"]
        options["cuts"] = backend["cuts"]
        options["strong"] = backend["strong"]
        options["warm_start"] = backend["warm_start"]
        options["threads"] = backend["threads"]
        options["seed_options"] = backend["seed_options"]
        options["node_limit"] = row["node_limit"]
        options["time_mode"] = backend["time_mode"]
        options["time_limit_seconds"] = backend["time_limit_seconds"]
        options["work_limit_law"] = backend["deterministic_work_limit_law"]
        proof["wall_clock_telemetry_in_identity"] = backend[
            "wall_clock_fields_in_identity"
        ]
        proof["solver_proof_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in proof.items()
                if key != "solver_proof_sha256"
            }
        )
        row["solver_proof_sha256"] = proof["solver_proof_sha256"]
    _rehash_receipt(receipt)


def _coherently_splice_input_binding(
    receipt: dict[str, object], *, field: str, value: object
) -> None:
    input_binding = receipt["input_binding"]
    fit_scope = input_binding["fit_scope_binding"]
    fit_scope[field] = value
    fit_scope["fit_scope_binding_sha256"] = canonical_sha256(
        {
            key: item
            for key, item in fit_scope.items()
            if key != "fit_scope_binding_sha256"
        }
    )
    input_binding[field] = value
    input_binding["fit_scope_binding_sha256"] = fit_scope[
        "fit_scope_binding_sha256"
    ]
    input_binding["input_binding_sha256"] = canonical_sha256(
        {
            key: item
            for key, item in input_binding.items()
            if key != "input_binding_sha256"
        }
    )
    input_hash = input_binding["input_binding_sha256"]
    receipt["fit_scope_binding_sha256"] = fit_scope[
        "fit_scope_binding_sha256"
    ]
    receipt["input_binding_sha256"] = input_hash
    for selector in receipt["selectors"]:
        selector["input_binding_sha256"] = input_hash
        for book in selector["books"]:
            book["input_binding_sha256"] = input_hash
    oracle = receipt["oracle"]
    oracle["fit_scope_binding_sha256"] = fit_scope[
        "fit_scope_binding_sha256"
    ]
    _refresh_runtime_and_input_pointers(receipt)


def _coherently_mutate_backend(
    receipt: dict[str, object], *, path: tuple[object, ...], value: object
) -> None:
    for backend in (
        receipt["input_binding"]["oracle_backend"],
        receipt["oracle"]["backend"],
    ):
        target = backend
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    input_binding = receipt["input_binding"]
    input_binding["input_binding_sha256"] = canonical_sha256(
        {
            key: item
            for key, item in input_binding.items()
            if key != "input_binding_sha256"
        }
    )
    _refresh_runtime_and_input_pointers(receipt)


@pytest.fixture(scope="module")
def tied_receipt() -> dict[str, object]:
    return _run()


def test_frozen_contracts_have_literal_identities() -> None:
    implementation = additions.frozen_preweek_additions_implementation_v1()
    assert implementation["implementation_id"] == (
        "packed-convex-block-support-cbc-oracle-v1"
    )
    assert implementation["implementation_sha256"] == (
        "1c94e9635d6038f629c40ce81cc2b3b3ed4fcad600e4832a0f231c5c9c19403d"
    )
    registry = additions.frozen_preweek_additions_registry_v1()
    assert [row["strategy_id"] for row in registry] == [
        "convex-excess-expected-max-ge-200-v1",
        "block-supported-bounded-tail-ge-210-250-v1",
        "maximum-coverage-ge-230-oracle-diagnostic-v1",
    ]
    assert [row["strategy_sha256"] for row in registry] == [
        "189dc6986c7d70b8315f9e41cb1fe5c6fce35c54f2756729254a0e1614dd1082",
        "a2070561cfb0a2c2c049b27d5e5ff71682a87d3568254b09ebf987a58d775954",
        "b40a7ed84af58f62ba1c4d814bcaf6f360ffb09e286963d348790f9f007b6b6e",
    ]
    assert registry[0]["parameters"] == {
        "utility": "max(0,s-200)^2",
        "pivot": 200.0,
        "exponent": 2,
        "parameter_sweep": False,
    }
    assert registry[1]["parameters"]["rungs"] == [
        {"threshold": 210.0, "operator": ">=", "weight": 1},
        {"threshold": 220.0, "operator": ">=", "weight": 2},
        {"threshold": 230.0, "operator": ">=", "weight": 4},
        {"threshold": 240.0, "operator": ">=", "weight": 8},
        {"threshold": 250.0, "operator": ">=", "weight": 16},
    ]


def test_ties_zero_gains_and_exact_prefix_identity(
    tied_receipt: dict[str, object],
) -> None:
    expected_ids = _ids()[:80]
    for strategy_id in (
        "convex-excess-expected-max-ge-200-v1",
        "block-supported-bounded-tail-ge-210-250-v1",
    ):
        selector = _selector(tied_receipt, strategy_id)
        assert selector["rank_80_lineup_ids"] == expected_ids
        assert [book["entry_budget"] for book in selector["books"]] == [
            4,
            14,
            80,
        ]
        for book in selector["books"]:
            budget = book["entry_budget"]
            assert book["selected_lineup_ids"] == expected_ids[:budget]
            assert book["marginal_trace"] == selector["rank_trace"][:budget]
    convex = _selector(
        tied_receipt, "convex-excess-expected-max-ge-200-v1"
    )
    ladder = _selector(
        tied_receipt, "block-supported-bounded-tail-ge-210-250-v1"
    )
    assert convex["rank_trace"][1][
        "marginal_mean_convex_excess_expected_max_gain"
    ] == 0.0
    assert ladder["rank_trace"][1][
        "marginal_block_supported_rung_utility"
    ] == 0


def test_distinct_block_support_changes_the_first_ladder_choice() -> None:
    scores = _scores(190.0)
    # lineup-000 has four 251 events in only R0.  lineup-001 has the same
    # four events split across R0/R1, so every rung's marginal coverage is
    # multiplied by two distinct blocks rather than one.
    scores[0, 0:4] = 251.0
    scores[1, 0:2] = 251.0
    scores[1, WIDTH : WIDTH + 2] = 251.0
    receipt = _run(scores=scores)
    ladder = _selector(
        receipt, "block-supported-bounded-tail-ge-210-250-v1"
    )
    assert ladder["rank_80_lineup_ids"][0] == "lineup-001"
    assert ladder["rank_trace"][0]["distinct_block_support_by_rung"] == [
        2,
        2,
        2,
        2,
        2,
    ]


def test_oracle_is_exact_on_fixture_and_retains_bounds_and_no_authority(
    tied_receipt: dict[str, object],
) -> None:
    oracle = tied_receipt["oracle"]
    backend = oracle["backend"]
    assert backend == tied_receipt["input_binding"]["oracle_backend"]
    assert backend["pulp_version"] == "3.3.2"
    assert backend["cbc_version"] == "2.10.3"
    assert backend["cbc_build_date"] == "Dec 15 2019"
    assert backend["executable_content_sha256"] == (
        "2e17077752aa52b06385ad248c9e90bb4f1ce34038c34c94e1012ca6adea5cc7"
    )
    assert backend["executable_bytes"] == 7_178_823
    assert backend["gap_relative"] == 0.0
    assert backend["gap_absolute"] == 0.0
    assert backend["presolve"] is True
    assert backend["cuts"] is True
    assert backend["strong"] == 0
    assert backend["warm_start"] is True
    assert backend["threads"] == 1
    assert backend["seed_options"] == ["randomSeed 1", "randomCbcSeed 1"]
    assert backend["time_mode"] == "cpu"
    assert backend["time_limit_seconds"] is None
    assert backend["wall_clock_fields_in_identity"] is False
    assert oracle["threshold"] == 230.0
    assert oracle["operator"] == ">="
    assert oracle["not_a_post_result_book_selector"] is True
    assert oracle["outcome_authority"] is False
    assert oracle["publication_authority"] is False
    assert oracle["opportunity_world_count"] == len(BLOCKS) * WIDTH
    for row, budget in zip(oracle["rows"], (4, 14, 80), strict=True):
        assert row["entry_budget"] == budget
        assert row["status"] == "exact-optimum-proven"
        assert row["terminal_reason"] == "optimal-proven"
        assert row["lower_bound_world_count"] == len(BLOCKS) * WIDTH
        assert row["upper_bound_world_count"] == len(BLOCKS) * WIDTH
        assert row["absolute_gap_world_count"] == 0
        assert row["relative_gap"] == 0.0
        assert row["time_limit_seconds"] is None
        assert row["time_mode"] == "cpu"
        assert row["wall_clock_telemetry_in_identity"] is False
        assert row["node_limit"] in {100_000, 250_000, 500_000}
        assert len(row["witness_selected_lineup_ids"]) == budget
        assert row["oracle_book_selection_authority"] is False
        assert row["solver_proof_sha256"] == row["solver_proof"][
            "solver_proof_sha256"
        ]
        assert row["solver_proof"]["wall_clock_telemetry_in_identity"] is False
        assert all(
            "Time (" not in line
            for line in row["solver_proof"]["canonical_solver_log"]
        )
        assert row["solver_proof"]["canonical_solver_log"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("pulp_version",), "3.3.3"),
        (("solver",), "different-solver"),
        (("cbc_version",), "2.10.4"),
        (("cbc_build_date",), "different-build"),
        (("executable_path",), "/tmp/coherently-spliced-cbc"),
        (("executable_content_sha256",), "8" * 64),
        (("executable_bytes",), 7_178_824),
        (("gap_relative",), 0.01),
        (("gap_absolute",), 1.0),
        (("presolve",), False),
        (("cuts",), False),
        (("strong",), 1),
        (("warm_start",), False),
        (("threads",), 2),
        (("seed_options", 0), "randomSeed 2"),
        (("seed_options", 1), "randomCbcSeed 2"),
        (("node_limits", "4"), 99_999),
        (("deterministic_work_limit_law",), "different-work-law"),
        (("time_mode",), "elapsed"),
        (("time_limit_seconds",), 1),
        (("wall_clock_fields_in_identity",), True),
    ],
)
def test_every_coherently_rehashed_solver_or_binary_drift_fails_replay(
    tied_receipt: dict[str, object], path: tuple[object, ...], value: object
) -> None:
    attacked = deepcopy(tied_receipt)
    _coherently_mutate_backend(attacked, path=path, value=value)
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            attacked, **_kwargs()
        )


def test_equivalent_input_row_reordering_is_receipt_identical(
    tied_receipt: dict[str, object],
) -> None:
    ids = _ids()
    scores = _scores()
    order = np.asarray(list(reversed(range(len(ids)))), dtype=np.int64)
    reordered = _run(
        lineup_ids=[ids[int(index)] for index in order],
        scores=np.ascontiguousarray(scores[order]),
    )
    assert reordered == tied_receipt


@pytest.mark.parametrize(
    ("blocks", "heldout"),
    [
        (("R0", "R1", "R2", "R3"), "R3"),
        (("R1", "R0", "R2", "R3"), "R4"),
        (("R0", "R1", "R2", "R4"), "R4"),
    ],
)
def test_fit_scope_substitution_fails_before_selection(
    blocks: tuple[str, ...], heldout: str
) -> None:
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="heldout|canonical|registry",
    ):
        _run(blocks=blocks, heldout=heldout)


def test_final_scope_is_exact_all_five_blocks() -> None:
    blocks = ("R0", "R1", "R2", "R3", "R4")
    scores = np.ascontiguousarray(
        np.full((90, len(blocks) * WIDTH), 231.0), dtype=np.float64
    )
    receipt = _run(
        blocks=blocks, heldout=None, scores=scores, width=WIDTH
    )
    binding = receipt["input_binding"]["fit_scope_binding"]
    assert binding["scope_kind"] == "final-fit"
    assert binding["heldout_block"] is None
    assert binding["training_blocks"] == list(blocks)


def test_nonfinite_and_non_float64_inputs_fail_closed() -> None:
    nonfinite = _scores()
    nonfinite[0, 0] = np.nan
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="non-finite",
    ):
        _run(scores=nonfinite)
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="float64",
    ):
        _run(scores=_scores().astype(np.float32))


def test_coherent_imported_neighbor_contract_drift_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = retrieval.frozen_retrieval_strategies_v2

    def drifted(entry_budget: int = 80) -> list[dict[str, object]]:
        registry = deepcopy(original(entry_budget))
        target = next(
            row for row in registry if row["strategy_id"] == "expected-max-v1"
        )
        target["description"] = "coherently altered"
        target["strategy_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in target.items()
                if key != "strategy_sha256"
            }
        )
        return registry

    monkeypatch.setattr(retrieval, "frozen_retrieval_strategies_v2", drifted)
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="neighbor expected-max",
    ):
        _run()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_mask_sha256", "9" * 64),
        ("occurrence_lineage_sha256", "7" * 64),
    ],
)
def test_coherent_mask_or_occurrence_lineage_splice_fails_replay(
    tied_receipt: dict[str, object], field: str, value: str
) -> None:
    attacked = deepcopy(tied_receipt)
    _coherently_splice_input_binding(
        attacked, field=field, value=value
    )
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            attacked, **_kwargs()
        )


def test_lineup_id_and_matrix_lineage_splices_fail_replay(
    tied_receipt: dict[str, object],
) -> None:
    changed_ids = _ids()
    changed_ids[0] = "lineup-altered"
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            tied_receipt, **_kwargs(lineup_ids=changed_ids)
        )
    changed_scores = _scores()
    changed_scores[0, 0] = 232.0
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            tied_receipt, **_kwargs(scores=changed_scores)
        )


@pytest.mark.parametrize("lineage", ["manifest", "member", "matrix-object"])
def test_source_manifest_member_and_matrix_object_splices_fail_replay(
    tied_receipt: dict[str, object], lineage: str
) -> None:
    overrides: dict[str, object] = {}
    if lineage == "manifest":
        manifest = deepcopy(SOURCE_MANIFEST)
        manifest["object_identity"]["sha256"] = "1" * 64
        overrides["source_manifest_identity"] = manifest
    elif lineage == "member":
        member = deepcopy(SOURCE_MEMBER)
        member["member_sha256"] = "2" * 64
        overrides["source_member_identity"] = member
    else:
        matrix = deepcopy(SOURCE_MATRIX)
        matrix["object_identity"]["sha256"] = "3" * 64
        overrides["source_score_matrix_identity"] = matrix
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            tied_receipt, **_kwargs(**overrides)
        )


@pytest.mark.parametrize("location", ["book", "selector", "oracle-row"])
def test_nested_false_authority_flip_fails_canonical_replay(
    tied_receipt: dict[str, object], location: str
) -> None:
    attacked = deepcopy(tied_receipt)
    if location == "book":
        attacked["selectors"][0]["books"][0]["publication_authority"] = True
    elif location == "selector":
        attacked["selectors"][1]["uses_realized_outcomes"] = True
    else:
        attacked["oracle"]["rows"][0]["outcome_authority"] = True
    _rehash_receipt(attacked)
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            attacked, **_kwargs()
        )


def test_coherent_oracle_bound_pointer_attack_fails_replay(
    tied_receipt: dict[str, object],
) -> None:
    attacked = deepcopy(tied_receipt)
    attacked["oracle"]["rows"][0]["upper_bound_world_count"] += 1
    attacked["oracle"]["rows"][0]["absolute_gap_world_count"] += 1
    attacked["oracle"]["rows"][0]["relative_gap_rational"]["numerator"] += 1
    attacked["oracle"]["rows"][0]["relative_gap"] = 1 / 33
    proof = attacked["oracle"]["rows"][0]["solver_proof"]
    proof["upper_bound_world_count"] += 1
    proof["solver_proof_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in proof.items()
            if key != "solver_proof_sha256"
        }
    )
    attacked["oracle"]["rows"][0]["solver_proof_sha256"] = proof[
        "solver_proof_sha256"
    ]
    _rehash_receipt(attacked)
    with pytest.raises(
        additions.CorpusExtremeTailPreweekAdditionsError,
        match="canonical replay",
    ):
        additions.validate_extreme_tail_preweek_additions_v1(
            attacked, **_kwargs()
        )


def test_sparse_envelope_fallback_retains_safe_explicit_gap() -> None:
    row = additions._solve_oracle_budget(  # noqa: SLF001
        budget=4,
        sparse_incidence=None,
        candidate_count=90,
        opportunity_count=20,
        event_edge_count=2_000_001,
        analytical_upper_bound=18,
        greedy_indices=list(range(80)),
        lineup_ids=_ids(),
        greedy_coverage=12,
        backend=additions._cbc_runtime_identity(),  # noqa: SLF001
        input_binding_sha256="1" * 64,
        event_incidence_sha256="2" * 64,
    )
    assert row["status"] == "required-exact-not-proven"
    assert row["terminal_reason"] == "sparse-model-envelope-bounded"
    assert row["solver_attempted"] is False
    assert row["lower_bound_world_count"] == 12
    assert row["upper_bound_world_count"] == 18
    assert row["absolute_gap_world_count"] == 6
    assert row["relative_gap_rational"] == {"numerator": 6, "denominator": 18}
