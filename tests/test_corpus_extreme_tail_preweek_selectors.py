from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_preweek_selectors as preweek
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as t230
from nfl_dfs.research.corpus_legal_feasibility import canonical_sha256


WIDTH = 32
BLOCKS = ("R0", "R1", "R2", "R3")
MASK_SHA = "a" * 64
LINEAGE_SHA = "b" * 64
SOURCE_MANIFEST = {
    "manifest_id": "factorial-manifest-v1",
    "manifest_sha256": "c" * 64,
    "object_identity": {
        "uri": "gs://fixture/manifests/factorial.json",
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


def _supported_scores(count: int = 90) -> np.ndarray:
    return np.ascontiguousarray(
        np.full((count, len(BLOCKS) * WIDTH), 231.0), dtype=np.float64
    )


def _run(
    *,
    lineup_ids: list[str] | None = None,
    scores: np.ndarray | None = None,
    blocks: tuple[str, ...] = BLOCKS,
    width: int = WIDTH,
    heldout_block: str | None = "R4",
) -> dict[str, object]:
    lineup_ids = _ids() if lineup_ids is None else lineup_ids
    scores = _supported_scores(len(lineup_ids)) if scores is None else scores
    return preweek.run_extreme_tail_preweek_selectors_v1(
        lineup_ids=lineup_ids,
        fit_scores=scores,
        training_blocks=blocks,
        heldout_block=heldout_block,
        worlds_per_block=width,
        candidate_mask_sha256=MASK_SHA,
        occurrence_lineage_sha256=LINEAGE_SHA,
        source_manifest_identity=SOURCE_MANIFEST,
        source_member_identity=SOURCE_MEMBER,
        source_score_matrix_identity=SOURCE_MATRIX,
        require_production_width=False,
    )


def _selector(
    receipt: dict[str, object], selector_id: str
) -> dict[str, object]:
    matches = [
        row for row in receipt["selectors"] if row["selector_id"] == selector_id
    ]
    assert len(matches) == 1
    return matches[0]


def _rehash_output(receipt: dict[str, object]) -> None:
    fit_binding = receipt["input_binding"]["fit_scope_binding"]
    fit_binding["fit_scope_binding_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in fit_binding.items()
            if key != "fit_scope_binding_sha256"
        }
    )
    input_binding = receipt["input_binding"]
    input_binding["fit_scope_binding_sha256"] = fit_binding[
        "fit_scope_binding_sha256"
    ]
    input_binding["input_binding_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in input_binding.items()
            if key != "input_binding_sha256"
        }
    )
    input_hash = input_binding["input_binding_sha256"]
    receipt["fit_scope_binding_sha256"] = fit_binding[
        "fit_scope_binding_sha256"
    ]
    for selector in receipt["selectors"]:
        selector["input_binding_sha256"] = input_hash
        admission = selector["admission"]
        if admission is not None:
            admission["input_binding_sha256"] = input_hash
            admission["admission_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in admission.items()
                    if key != "admission_sha256"
                }
            )
        for raw_ranking in selector["raw_subset_rankings"]:
            raw_ranking["input_binding_sha256"] = input_hash
            raw_ranking["admission_sha256"] = admission["admission_sha256"]
            for raw_book in raw_ranking["books"]:
                raw_book["input_binding_sha256"] = input_hash
                raw_book["admission_sha256"] = admission["admission_sha256"]
                raw_book["raw_book_sha256"] = canonical_sha256(
                    {
                        key: value
                        for key, value in raw_book.items()
                        if key != "raw_book_sha256"
                    }
                )
            raw_ranking["raw_ranking_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in raw_ranking.items()
                    if key != "raw_ranking_sha256"
                }
            )
        selector["raw_subset_rankings_sha256"] = canonical_sha256(
            [
                row["raw_ranking_sha256"]
                for row in selector["raw_subset_rankings"]
            ]
        )
        projection = selector["support_projection"]
        selected_raw = None
        if projection is not None:
            by_strategy = {
                row["raw_strategy_id"]: row
                for row in selector["raw_subset_rankings"]
            }
            projection["raw_ranking_pointers"] = [
                {
                    "raw_strategy_id": row["raw_strategy_id"],
                    "raw_strategy_sha256": row["raw_strategy_sha256"],
                    "raw_ranking_id": row["raw_ranking_id"],
                    "raw_ranking_sha256": row["raw_ranking_sha256"],
                }
                for row in selector["raw_subset_rankings"]
            ]
            selected_raw = by_strategy[projection["selected_raw_strategy_id"]]
            projection["selected_raw_ranking_id"] = selected_raw[
                "raw_ranking_id"
            ]
            projection["selected_raw_ranking_sha256"] = selected_raw[
                "raw_ranking_sha256"
            ]
            projection["selected_raw_book_pointers"] = [
                {
                    "entry_budget": book["entry_budget"],
                    "raw_book_id": book["raw_book_id"],
                    "raw_book_sha256": book["raw_book_sha256"],
                }
                for book in selected_raw["books"]
            ]
            projection["support_projection_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in projection.items()
                    if key != "support_projection_sha256"
                }
            )
        for book in selector["books"]:
            book["input_binding_sha256"] = input_hash
            if selected_raw is not None:
                raw_book = next(
                    row
                    for row in selected_raw["books"]
                    if row["entry_budget"] == book["entry_budget"]
                )
                book["source_raw_subset_book_id"] = raw_book["raw_book_id"]
                book["source_raw_subset_book_sha256"] = raw_book[
                    "raw_book_sha256"
                ]
            book["book_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in book.items()
                    if key != "book_sha256"
                }
            )
        selector["selector_receipt_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in selector.items()
                if key != "selector_receipt_sha256"
            }
        )
    receipt["selector_receipts_sha256"] = canonical_sha256(
        [row["selector_receipt_sha256"] for row in receipt["selectors"]]
    )
    receipt["preweek_selectors_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in receipt.items()
            if key != "preweek_selectors_sha256"
        }
    )


def test_frozen_registry_and_implementation_are_exact() -> None:
    registry = preweek.frozen_preweek_selector_registry_v1()
    assert [row["selector_id"] for row in registry] == [
        "complete-union-inclusive-r194-rank-v1",
        "individual-training-maximum-rank-v1",
        "training-hit-ge-230-admission-v1",
    ]
    assert all(row["entry_budgets"] == [4, 14, 80] for row in registry)
    assert all(row["ranking_depth"] == 80 for row in registry)
    assert all(
        row["strategy_sha256"]
        == canonical_sha256(
            {
                key: value
                for key, value in row.items()
                if key != "strategy_sha256"
            }
        )
        for row in registry
    )
    implementation = preweek.frozen_preweek_selector_implementation_v1()
    assert implementation["candidate_chunk_rows"] == 64
    assert implementation["dense_candidate-by-world_boolean_matrix"] is False
    assert implementation["full_score_matrix_copy"] is False


def test_supported_receipt_has_replayable_exact_prefixes_and_false_authority(
) -> None:
    scores = _supported_scores()
    receipt = _run(scores=scores)
    assert receipt["schema_version"] == preweek.RECEIPT_SCHEMA
    assert receipt["fit_scope_id"] == "holdout-R4"
    assert receipt["selector_count"] == 3
    assert receipt["entry_budgets"] == [4, 14, 80]
    assert receipt["analytical_authority"] is False
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["scope_kind"] == "cross-fit"
    assert receipt["standalone_source_authority"] is False
    assert receipt["outer_exact_source_replay_required"] is True
    assert receipt["publication_status"] == (
        "not-publishable-without-outer-source-replay"
    )
    binding = receipt["input_binding"]["fit_scope_binding"]
    assert binding["world_block_registry"] == ["R0", "R1", "R2", "R3", "R4"]
    assert binding["scope_kind"] == "cross-fit"
    assert binding["heldout_block"] == "R4"
    assert binding["training_blocks"] == ["R0", "R1", "R2", "R3"]
    assert binding["ordered_lineup_ids"] == _ids()
    assert binding["candidate_mask_sha256"] == MASK_SHA
    assert binding["occurrence_lineage_sha256"] == LINEAGE_SHA
    assert binding["source_manifest_identity"] == SOURCE_MANIFEST
    assert binding["source_member_identity"] == SOURCE_MEMBER
    assert binding["score_matrix_binding"][
        "source_score_matrix_identity"
    ] == SOURCE_MATRIX
    for selector in receipt["selectors"]:
        assert selector["status"] == "feasible-exact-rank-80"
        assert selector["book_count"] == 3
        assert selector["promotion_authority"] is False
        rank = selector["rank_80_lineup_ids"]
        for book, budget in zip(selector["books"], (4, 14, 80), strict=True):
            assert book["entry_budget"] == budget
            assert book["selected_lineup_ids"] == rank[:budget]
            assert book["entry_count"] == budget
            assert book["decision_authority"] is False
    admission = _selector(
        receipt, "training-hit-ge-230-admission-v1"
    )
    assert admission["raw_subset_ranking_count"] == 2
    assert [
        row["raw_strategy_id"] for row in admission["raw_subset_rankings"]
    ] == [
        "coverage-ge-230-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
    ]
    assert all(
        row["book_count"] == 3 for row in admission["raw_subset_rankings"]
    )
    assert admission["support_projection"]["support_gate"]["passed"] is True
    assert admission["selected_raw_strategy_id"] == "coverage-ge-230-v1"
    for book, pointer in zip(
        admission["books"],
        admission["support_projection"]["selected_raw_book_pointers"],
        strict=True,
    ):
        assert book["source_raw_subset_book_id"] == pointer["raw_book_id"]
        assert book["source_raw_subset_book_sha256"] == pointer[
            "raw_book_sha256"
        ]
    replay = preweek.validate_extreme_tail_preweek_selectors_v1(
        receipt,
        lineup_ids=_ids(),
        fit_scores=scores,
        training_blocks=BLOCKS,
        heldout_block="R4",
        worlds_per_block=WIDTH,
        candidate_mask_sha256=MASK_SHA,
        occurrence_lineage_sha256=LINEAGE_SHA,
        source_manifest_identity=SOURCE_MANIFEST,
        source_member_identity=SOURCE_MEMBER,
        source_score_matrix_identity=SOURCE_MATRIX,
        require_production_width=False,
    )
    assert replay == receipt


def test_complete_union_r194_ties_and_zero_gain_use_frozen_order() -> None:
    scores = np.ascontiguousarray(
        np.full((90, len(BLOCKS) * WIDTH), 100.0), dtype=np.float64
    )
    scores[0, [0, 1]] = 194.0
    scores[1, :] = 150.0
    scores[1, [0, 1]] = 194.0
    scores[2, [1, 2]] = 194.0
    selector = _selector(
        _run(scores=scores), "complete-union-inclusive-r194-rank-v1"
    )
    assert selector["rank_80_lineup_ids"][:3] == [
        "lineup-001",
        "lineup-002",
        "lineup-000",
    ]
    assert selector["rank_trace"][0]["marginal_new_world_count"] == 2
    assert selector["rank_trace"][1]["marginal_new_world_count"] == 1
    assert selector["rank_trace"][2]["marginal_new_world_count"] == 0
    assert selector["rank_trace"][2][
        "individual_inclusive_194_world_count"
    ] == 2


def test_individual_training_maximum_uses_max_then_mean_then_id() -> None:
    scores = np.ascontiguousarray(
        np.full((90, len(BLOCKS) * WIDTH), 100.0), dtype=np.float64
    )
    scores[0, 0] = 300.0
    scores[1, 0] = 300.0
    scores[1, 1:5] = 200.0
    scores[2] = scores[1]
    selector = _selector(
        _run(scores=scores), "individual-training-maximum-rank-v1"
    )
    assert selector["rank_80_lineup_ids"][:3] == [
        "lineup-001",
        "lineup-002",
        "lineup-000",
    ]
    assert selector["rank_trace"][0]["fit_world_maximum_score"] == 300.0
    assert selector["rank_trace"][0]["fit_world_mean_score"] == selector[
        "rank_trace"
    ][1]["fit_world_mean_score"]


def test_hard_230_admission_below_80_publishes_no_book() -> None:
    scores = np.ascontiguousarray(
        np.full((90, len(BLOCKS) * WIDTH), 180.0), dtype=np.float64
    )
    scores[:79, 0] = 230.0
    selector = _selector(_run(scores=scores), "training-hit-ge-230-admission-v1")
    assert selector["status"] == "mechanically-infeasible-below-exact-80"
    assert selector["admission"]["admitted_candidate_count"] == 79
    assert selector["admission"]["exact_80_feasible"] is False
    assert selector["support_projection"] is None
    assert selector["raw_subset_rankings"] == []
    assert selector["rank_80_lineup_ids"] == []
    assert selector["books"] == []
    assert selector["book_count"] == 0


def test_hard_230_admission_exact_80_is_feasible_without_borrowing() -> None:
    scores = np.ascontiguousarray(
        np.full((90, len(BLOCKS) * WIDTH), 180.0), dtype=np.float64
    )
    scores[:80] = 230.0
    selector = _selector(_run(scores=scores), "training-hit-ge-230-admission-v1")
    assert selector["status"] == "feasible-exact-rank-80"
    assert selector["admission"]["admitted_candidate_count"] == 80
    assert selector["admission"]["exact_80_feasible"] is True
    assert len(selector["rank_80_lineup_ids"]) == 80
    assert set(selector["rank_80_lineup_ids"]) == set(_ids()[:80])


def test_hard_230_support_switch_falls_back_for_zero_block() -> None:
    scores = _supported_scores()
    scores[:, :WIDTH] = 180.0
    selector = _selector(_run(scores=scores), "training-hit-ge-230-admission-v1")
    gate = selector["support_projection"]["support_gate"]
    assert gate["passed"] is False
    assert gate["zero_opportunity_training_blocks"] == ["R0"]
    assert selector["selected_raw_strategy_id"] == (
        "block-robust-bounded-tail-ge-210-250-v1"
    )
    assert selector["book_count"] == 3


def test_hard_230_support_switch_falls_back_below_exact_100() -> None:
    scores = np.ascontiguousarray(
        np.full((90, len(BLOCKS) * WIDTH), 180.0), dtype=np.float64
    )
    for index in range(90):
        block = index % len(BLOCKS)
        world = index // len(BLOCKS)
        scores[index, block * WIDTH + world] = 230.0
    selector = _selector(_run(scores=scores), "training-hit-ge-230-admission-v1")
    gate = selector["support_projection"]["support_gate"]
    assert gate["every_training_block_nonzero"] is True
    assert gate["training_opportunity_world_count"] == 90
    assert gate["minimum_training_opportunity_world_count"] == 100
    assert gate["passed"] is False
    assert selector["selected_raw_strategy_id"] == (
        "block-robust-bounded-tail-ge-210-250-v1"
    )


def test_exact_inclusive_boundaries_are_used_for_194_and_230() -> None:
    scores = np.ascontiguousarray(
        np.full((90, len(BLOCKS) * WIDTH), 193.999), dtype=np.float64
    )
    scores[:, :] = 230.0
    receipt = _run(scores=scores)
    r194 = _selector(receipt, "complete-union-inclusive-r194-rank-v1")
    hard = _selector(receipt, "training-hit-ge-230-admission-v1")
    assert r194["rank_trace"][0]["individual_inclusive_194_world_count"] == 128
    assert hard["admission"]["admitted_candidate_count"] == 90
    assert hard["support_projection"]["support_gate"][
        "training_opportunity_world_count"
    ] == 128


def test_candidate_row_reordering_is_canonically_invariant() -> None:
    lineup_ids = _ids()
    scores = _supported_scores()
    for index in range(len(lineup_ids)):
        scores[index, index % scores.shape[1]] += index / 100.0
    original = _run(lineup_ids=lineup_ids, scores=scores)
    permutation = np.asarray(list(reversed(range(len(lineup_ids)))), dtype=np.int64)
    reordered = _run(
        lineup_ids=[lineup_ids[int(index)] for index in permutation],
        scores=np.ascontiguousarray(scores[permutation]),
    )
    assert reordered == original


@pytest.mark.parametrize("attack", ["schema", "authority", "reorder", "hash"])
def test_replay_rejects_coherently_rehashed_receipt_attacks(attack: str) -> None:
    scores = _supported_scores()
    retained = deepcopy(_run(scores=scores))
    if attack == "schema":
        retained["schema_version"] = "extreme-tail-preweek-selectors/v2"
        _rehash_output(retained)
    elif attack == "authority":
        retained["selectors"][0]["books"][0]["decision_authority"] = True
        _rehash_output(retained)
    elif attack == "reorder":
        book = retained["selectors"][0]["books"][2]
        book["selected_lineup_ids"][0:2] = reversed(
            book["selected_lineup_ids"][0:2]
        )
        book["selected_lineup_ids_sha256"] = canonical_sha256(
            book["selected_lineup_ids"]
        )
        _rehash_output(retained)
    else:
        retained["preweek_selectors_sha256"] = "0" * 64
    with pytest.raises(
        preweek.CorpusExtremeTailPreweekSelectorsError,
        match="canonical replay differs",
    ):
        preweek.validate_extreme_tail_preweek_selectors_v1(
            retained,
            lineup_ids=_ids(),
            fit_scores=scores,
            training_blocks=BLOCKS,
            heldout_block="R4",
            worlds_per_block=WIDTH,
            candidate_mask_sha256=MASK_SHA,
            occurrence_lineage_sha256=LINEAGE_SHA,
            source_manifest_identity=SOURCE_MANIFEST,
            source_member_identity=SOURCE_MEMBER,
            source_score_matrix_identity=SOURCE_MATRIX,
            require_production_width=False,
        )


@pytest.mark.parametrize(
    "splice",
    ["heldout", "candidate-mask", "candidate-ids", "score-matrix"],
)
def test_exact_fit_scope_binding_rejects_coherently_rehashed_splices(
    splice: str,
) -> None:
    scores = _supported_scores()
    retained = deepcopy(_run(scores=scores))
    binding = retained["input_binding"]["fit_scope_binding"]
    if splice == "heldout":
        binding["heldout_block"] = "R3"
        binding["fit_scope_id"] = "holdout-R3"
    elif splice == "candidate-mask":
        binding["candidate_mask_sha256"] = "1" * 64
    elif splice == "candidate-ids":
        binding["ordered_lineup_ids"][0:2] = reversed(
            binding["ordered_lineup_ids"][0:2]
        )
        binding["ordered_lineup_ids_sha256"] = canonical_sha256(
            binding["ordered_lineup_ids"]
        )
    else:
        matrix = binding["score_matrix_binding"]
        matrix["canonical_fit_score_matrix_sha256"] = "2" * 64
        matrix["source_score_matrix_identity"]["matrix_sha256"] = "3" * 64
    _rehash_output(retained)
    with pytest.raises(
        preweek.CorpusExtremeTailPreweekSelectorsError,
        match="canonical replay differs",
    ):
        preweek.validate_extreme_tail_preweek_selectors_v1(
            retained,
            lineup_ids=_ids(),
            fit_scores=scores,
            training_blocks=BLOCKS,
            heldout_block="R4",
            worlds_per_block=WIDTH,
            candidate_mask_sha256=MASK_SHA,
            occurrence_lineage_sha256=LINEAGE_SHA,
            source_manifest_identity=SOURCE_MANIFEST,
            source_member_identity=SOURCE_MEMBER,
            source_score_matrix_identity=SOURCE_MATRIX,
            require_production_width=False,
        )


def test_support_projection_rejects_coherently_rehashed_raw_book_pointer() -> None:
    scores = _supported_scores()
    retained = deepcopy(_run(scores=scores))
    selector = _selector(retained, "training-hit-ge-230-admission-v1")
    fallback = next(
        row
        for row in selector["raw_subset_rankings"]
        if row["raw_strategy_id"]
        == "block-robust-bounded-tail-ge-210-250-v1"
    )
    projection = selector["support_projection"]
    projection["selected_raw_book_pointers"][0] = {
        "entry_budget": 4,
        "raw_book_id": fallback["books"][0]["raw_book_id"],
        "raw_book_sha256": fallback["books"][0]["raw_book_sha256"],
    }
    projection["support_projection_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in projection.items()
            if key != "support_projection_sha256"
        }
    )
    selector["selector_receipt_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in selector.items()
            if key != "selector_receipt_sha256"
        }
    )
    retained["selector_receipts_sha256"] = canonical_sha256(
        [row["selector_receipt_sha256"] for row in retained["selectors"]]
    )
    retained["preweek_selectors_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in retained.items()
            if key != "preweek_selectors_sha256"
        }
    )
    with pytest.raises(
        preweek.CorpusExtremeTailPreweekSelectorsError,
        match="canonical replay differs",
    ):
        preweek.validate_extreme_tail_preweek_selectors_v1(
            retained,
            lineup_ids=_ids(),
            fit_scores=scores,
            training_blocks=BLOCKS,
            heldout_block="R4",
            worlds_per_block=WIDTH,
            candidate_mask_sha256=MASK_SHA,
            occurrence_lineage_sha256=LINEAGE_SHA,
            source_manifest_identity=SOURCE_MANIFEST,
            source_member_identity=SOURCE_MEMBER,
            source_score_matrix_identity=SOURCE_MATRIX,
            require_production_width=False,
        )


def test_fails_closed_on_coherent_imported_constant_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        t230,
        "TAIL_RUNGS",
        (
            (210.0, ">=", 1),
            (220.0, ">=", 2),
            (230.0, ">=", 5),
            (240.0, ">=", 8),
            (250.0, ">=", 16),
        ),
    )
    with pytest.raises(
        preweek.CorpusExtremeTailPreweekSelectorsError,
        match="imported frozen T230 constants differ",
    ):
        _run()


def test_fails_closed_on_coherently_rehashed_upstream_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = deepcopy(t230.frozen_selector_implementation_contract_v1())
    changed["candidate_chunk_rows"] = 65
    changed["selector_implementation_sha256"] = canonical_sha256(
        {
            key: value
            for key, value in changed.items()
            if key != "selector_implementation_sha256"
        }
    )
    monkeypatch.setattr(
        t230,
        "frozen_selector_implementation_contract_v1",
        lambda: deepcopy(changed),
    )
    with pytest.raises(
        preweek.CorpusExtremeTailPreweekSelectorsError,
        match="implementation identity differs",
    ):
        _run()


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("float32", "native float64"),
        ("nonfinite", "non-finite"),
        ("shape", "exact-shape"),
        ("duplicate", "unique nonempty"),
        ("block-order", "canonical R0..R4 subset"),
        ("source-hash", "lowercase SHA-256"),
        ("authority-mode", "exact boolean"),
    ],
)
def test_input_schema_and_finiteness_attacks_fail_closed(
    mutation: str, match: str
) -> None:
    lineup_ids = _ids()
    scores = _supported_scores()
    blocks = BLOCKS
    candidate_mask: object = MASK_SHA
    production: object = False
    if mutation == "float32":
        scores = scores.astype(np.float32)
    elif mutation == "nonfinite":
        scores[0, 0] = np.nan
    elif mutation == "shape":
        scores = np.ascontiguousarray(scores[:, :-1])
    elif mutation == "duplicate":
        lineup_ids[-1] = lineup_ids[0]
    elif mutation == "block-order":
        blocks = ("R1", "R0", "R2", "R3")
    elif mutation == "source-hash":
        candidate_mask = "NOT-A-HASH"
    elif mutation == "authority-mode":
        production = 0
    with pytest.raises(preweek.CorpusExtremeTailPreweekSelectorsError, match=match):
        preweek.run_extreme_tail_preweek_selectors_v1(
            lineup_ids=lineup_ids,
            fit_scores=scores,
            training_blocks=blocks,
            heldout_block="R4",
            worlds_per_block=WIDTH,
            candidate_mask_sha256=candidate_mask,
            occurrence_lineage_sha256=LINEAGE_SHA,
            source_manifest_identity=SOURCE_MANIFEST,
            source_member_identity=SOURCE_MEMBER,
            source_score_matrix_identity=SOURCE_MATRIX,
            require_production_width=production,
        )


def test_final_fit_uses_five_blocks_and_exact_125_gate() -> None:
    blocks = ("R0", "R1", "R2", "R3", "R4")
    scores = np.ascontiguousarray(
        np.full((90, len(blocks) * 25), 230.0), dtype=np.float64
    )
    receipt = _run(
        scores=scores,
        blocks=blocks,
        width=25,
        heldout_block=None,
    )
    selector = _selector(receipt, "training-hit-ge-230-admission-v1")
    assert receipt["fit_scope_id"] == "all-block-final-fit"
    assert receipt["heldout_block"] is None
    assert selector["support_projection"]["support_gate"][
        "minimum_training_opportunity_world_count"
    ] == 125
    assert selector["support_projection"]["support_gate"]["passed"] is True
