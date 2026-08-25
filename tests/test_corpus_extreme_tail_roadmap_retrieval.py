from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect

import numpy as np
import pytest
from scipy.special import betaincinv

from nfl_dfs.research import corpus_extreme_tail_roadmap_retrieval as target


def _hash(character: str) -> str:
    return character * 64


def _object_identity(name: str, character: str) -> dict[str, object]:
    return {
        "uri": f"gs://test-bucket/{name}.json",
        "generation": "123456789",
        "sha256": _hash(character),
        "bytes": 1000 + ord(character),
    }


def _source_identities() -> dict[str, object]:
    return {
        "source_manifest_identity": {
            "manifest_id": "accepted-panel-v12-test",
            "manifest_sha256": _hash("a"),
            "object_identity": _object_identity("manifest", "b"),
        },
        "source_member_identity": {
            "member_id": "accepted-panel-v12-test-member-00",
            "member_ordinal": 0,
            "member_sha256": _hash("c"),
            "slate_id": "2023-w01-main",
        },
        "source_score_matrix_identity": {
            "matrix_id": "ordinary-r-fit-matrix-test",
            "matrix_sha256": _hash("d"),
            "object_identity": _object_identity("matrix", "e"),
        },
    }


def _canonical_fixture() -> tuple[list[str], np.ndarray]:
    lineup_ids = [f"lineup-{index:03d}" for index in range(80)]
    scores = np.empty((80, 40), dtype=np.float64)
    for index in range(80):
        scores[index] = 90.0 + float(index) / 100.0

    # A is the highest-mean tail candidate and therefore the deterministic
    # first choice for both laws.  B carries the same event signature at a
    # lower score.  C carries an equally broad but disjoint signature.
    scores[0] = 100.0
    scores[1] = 100.0
    scores[2] = 100.0
    for block in range(4):
        start = block * 10
        scores[0, start : start + 2] = 240.0
        scores[1, start : start + 2] = 238.0
        scores[2, start + 2 : start + 4] = 235.0
    return lineup_ids, np.ascontiguousarray(scores)


def _attach_calibration_origin_lineage(
    kwargs: dict[str, object],
    *,
    counts_by_lineup: dict[str, dict[str, int]] | None = None,
) -> None:
    canonical_ids = sorted(kwargs["lineup_ids"])
    blocks = list(kwargs["training_blocks"])
    calibration_block = blocks[-1]
    fit_scope = target.preweek.build_extreme_tail_preweek_fit_scope_binding_v1(
        lineup_ids=kwargs["lineup_ids"],
        fit_scores=kwargs["fit_scores"],
        training_blocks=kwargs["training_blocks"],
        heldout_block=kwargs["heldout_block"],
        worlds_per_block=kwargs["worlds_per_block"],
        candidate_mask_sha256=kwargs["candidate_mask_sha256"],
        occurrence_lineage_sha256=kwargs["occurrence_lineage_sha256"],
        source_manifest_identity=kwargs["source_manifest_identity"],
        source_member_identity=kwargs["source_member_identity"],
        source_score_matrix_identity=kwargs["source_score_matrix_identity"],
        require_production_width=kwargs["require_production_width"],
    )
    rows: list[dict[str, object]] = []
    for ordinal, lineup_id in enumerate(canonical_ids):
        counts = {block: 0 for block in target.WORLD_BLOCKS}
        if counts_by_lineup is None:
            counts[blocks[0]] = 1
        else:
            counts.update(counts_by_lineup[lineup_id])
        origin_blocks = [
            block for block in target.WORLD_BLOCKS if counts[block] > 0
        ]
        rows.append({
            "candidate_ordinal": ordinal,
            "lineup_id": lineup_id,
            "origin_blocks": origin_blocks,
            "occurrence_counts_by_block": counts,
            "occurrence_count": sum(counts.values()),
        })
    body: dict[str, object] = {
        "schema_version": target.CALIBRATION_ORIGIN_LINEAGE_SCHEMA,
        "lineage_law": target.LCB_CALIBRATION_ORIGIN_INPUT_LAW,
        "fit_scope_id": fit_scope["fit_scope_id"],
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "training_blocks": blocks,
        "calibration_block": calibration_block,
        "source_manifest_identity_sha256": target._sha(
            fit_scope["source_manifest_identity"], label="test source manifest"
        ),
        "source_member_identity_sha256": target._sha(
            fit_scope["source_member_identity"], label="test source member"
        ),
        "source_manifest_member_binding_sha256": fit_scope[
            "source_manifest_member_binding_sha256"
        ],
        "score_matrix_binding_sha256": target._sha(
            fit_scope["score_matrix_binding"], label="test score matrix binding"
        ),
        "candidate_mask_sha256": fit_scope["candidate_mask_sha256"],
        "occurrence_lineage_sha256": fit_scope["occurrence_lineage_sha256"],
        "ordered_lineup_count": len(canonical_ids),
        "ordered_lineup_ids_sha256": target._sha(
            canonical_ids, label="test calibration-origin lineup IDs"
        ),
        "candidate_origin_rows": rows,
        "candidate_origin_rows_sha256": target._sha(
            rows, label="test calibration-origin rows"
        ),
        "occurrence_count": sum(int(row["occurrence_count"]) for row in rows),
        "uses_realized_outcomes": False,
        "heldout_score_columns_present": False,
        "outer_exact_source_replay_required": True,
    }
    artifact = dict(body)
    artifact["lineage_artifact_sha256"] = target._sha(
        artifact, label="test calibration-origin artifact"
    )
    payload = target._canonical(
        artifact, label="test calibration-origin artifact"
    )
    kwargs["calibration_origin_lineage_artifact"] = artifact
    kwargs["calibration_origin_lineage_artifact_identity"] = {
        "uri": "gs://test-bucket/calibration-origin-lineage.json",
        "generation": "987654321",
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _kwargs(*, canonical_order: bool = False) -> dict[str, object]:
    lineup_ids, scores = _canonical_fixture()
    if not canonical_order:
        lineup_ids = list(reversed(lineup_ids))
        scores = np.ascontiguousarray(scores[::-1])
    kwargs: dict[str, object] = {
        "lineup_ids": lineup_ids,
        "fit_scores": scores,
        "training_blocks": ("R0", "R1", "R2", "R3"),
        "heldout_block": "R4",
        "worlds_per_block": 10,
        "candidate_mask_sha256": _hash("f"),
        "occurrence_lineage_sha256": _hash("1"),
        **_source_identities(),
        "require_production_width": False,
    }
    _attach_calibration_origin_lineage(kwargs)
    return kwargs


def _derived_calibration_origin_binding(
    kwargs: dict[str, object],
) -> tuple[np.ndarray, dict[str, object]]:
    canonical_ids, _, _, blocks, fit_scope = target._validated_scope(
        lineup_ids=kwargs["lineup_ids"],
        fit_scores=kwargs["fit_scores"],
        training_blocks=kwargs["training_blocks"],
        heldout_block=kwargs["heldout_block"],
        worlds_per_block=kwargs["worlds_per_block"],
        candidate_mask_sha256=kwargs["candidate_mask_sha256"],
        occurrence_lineage_sha256=kwargs["occurrence_lineage_sha256"],
        source_manifest_identity=kwargs["source_manifest_identity"],
        source_member_identity=kwargs["source_member_identity"],
        source_score_matrix_identity=kwargs["source_score_matrix_identity"],
        require_production_width=kwargs["require_production_width"],
    )
    return target._calibration_origin_eligibility(
        lineage_artifact=kwargs["calibration_origin_lineage_artifact"],
        lineage_artifact_identity=kwargs[
            "calibration_origin_lineage_artifact_identity"
        ],
        canonical_ids=canonical_ids,
        training_blocks=blocks,
        calibration_block=blocks[-1],
        fit_scope=fit_scope,
    )


def _rehash_calibration_origin_artifact(kwargs: dict[str, object]) -> None:
    artifact = kwargs["calibration_origin_lineage_artifact"]
    rows = artifact["candidate_origin_rows"]
    artifact["candidate_origin_rows_sha256"] = target._sha(
        rows, label="test coherently changed calibration-origin rows"
    )
    artifact["occurrence_count"] = sum(
        int(row["occurrence_count"]) for row in rows
    )
    artifact.pop("lineage_artifact_sha256", None)
    artifact["lineage_artifact_sha256"] = target._sha(
        artifact, label="test coherently changed calibration-origin artifact"
    )
    payload = target._canonical(
        artifact, label="test coherently changed calibration-origin artifact"
    )
    identity = kwargs["calibration_origin_lineage_artifact_identity"]
    identity["sha256"] = sha256(payload).hexdigest()
    identity["bytes"] = len(payload)


@pytest.fixture(scope="module")
def built() -> tuple[dict[str, object], dict[str, object]]:
    kwargs = _kwargs()
    receipt = target.run_extreme_tail_roadmap_retrieval_v1(**kwargs)
    return kwargs, receipt


def _selector(
    receipt: dict[str, object], strategy_id: str
) -> dict[str, object]:
    return next(
        row for row in receipt["selectors"] if row["strategy_id"] == strategy_id
    )


def _assert_false_authorities(value: dict[str, object]) -> None:
    for field in target._FALSE_AUTHORITY_FIELDS:
        assert value[field] is False


def test_literal_contracts_freeze_formulas_hashes_and_ties() -> None:
    implementation = target.frozen_roadmap_retrieval_implementation_v1()
    registry = target.frozen_roadmap_retrieval_registry_v1()
    assert implementation["implementation_sha256"] == (
        "59f75200be251763126b5a556d8e324d787c7d22890fefadb9fce08dc0dcfdb4"
    )
    assert target._sha(
        target._implementation_body(), label="test implementation"
    ) == target.EXPECTED_IMPLEMENTATION_SHA256
    assert [row["strategy_id"] for row in registry] == [
        "tail-lcb-ge-230-v1",
        "correlation-aware-expected-max-ge-230-v1",
    ]
    assert [row["strategy_sha256"] for row in registry] == [
        "36ddf8187e726f665d47936fe89750157720591dc005af73b0bd8d243cf86af1",
        "e2e7245e784b5d047b7f89fc77c3647b0d1c51747bf31625ccdab14caa70dc31",
    ]
    lcb = registry[0]
    assert lcb["parameters"] == {
        "threshold": 230.0,
        "operator": ">=",
        "bound": "one-sided-exact-clopper-pearson",
        "total_alpha_numerator": 1,
        "total_alpha_denominator": 20,
        "confidence_level": 0.95,
        "multiplicity_law": "bonferroni-alpha-divided-by-exact-rank-catalog",
        "calibration_block_law": "highest-ordinal-fit-r-block",
        "calibration_origin_law": (
            "strip-calibration-origin-occurrences-retain-candidate-iff-other-"
            "origin-remains"
        ),
        "calibration_origin_input_law": (
            "generation-pinned-exact-origin-count-lineage-artifact"
        ),
        "rank_catalog_ids": [
            "cp-transformed-training-utility-rank-v1",
            "correlation-aware-expected-max-training-rank-v1",
        ],
        "catalog_size": 2,
        "rank_training_scope": "fit-blocks-minus-calibration-block",
        "bound_scope": "selected-exact-rank80-book-only",
        "prefix_confidence_claim": False,
        "confidence_parameter_sweep": False,
    }
    assert lcb["tie_law"] == [
        "largest-bonferroni-adjusted-calibration-cp-lower",
        "largest-calibration-inclusive-230-book-hit-count",
        "ascending-frozen-rank-catalog-ordinal",
    ]
    heuristic = implementation["cp_transformed_training_catalog_law"]
    assert heuristic["adaptive_candidate_and_rank_search"] is True
    assert heuristic["frequentist_confidence_claim"] is False
    assert heuristic["coverage_claim"] is False
    assert heuristic["selection_adjustment"] == "none-not-a-bound"
    assert implementation["tail_lcb_law"][
        "selection_calibration_independence_required"
    ] is True
    assert implementation["tail_lcb_law"][
        "calibration_origin_exclusion_required"
    ] is True
    assert implementation["tail_lcb_law"][
        "caller_supplied_eligibility_mask_allowed"
    ] is False
    assert implementation["tail_lcb_law"]["bound_scope"] == (
        "selected-exact-rank80-book-only"
    )
    correlation = registry[1]
    assert correlation["parameters"]["penalty_dk_per_unit_overlap"] == 230.0
    assert correlation["parameters"]["penalty_unit"] == (
        "draftkings-points-per-fit-world"
    )
    assert correlation["parameters"]["coefficient_sweep"] is False
    assert len(set(target.EXPECTED_STRATEGY_SHA256S.values())) == 2
    assert target.EXPECTED_IMPLEMENTATION_SHA256 not in set(
        target.EXPECTED_STRATEGY_SHA256S.values()
    )


def test_clopper_pearson_lookup_is_exact_one_sided_and_monotone() -> None:
    table = target._clopper_pearson_lower_table(
        worlds_per_block=10, tail_probability=0.025
    )
    assert table[0] == 0.0
    for count in range(1, 11):
        expected = betaincinv(count, 10 - count + 1, 0.025)
        assert table[count] == pytest.approx(expected, abs=1e-15)
    assert np.all(np.diff(table) >= 0.0)


def test_tail_lcb_uses_independent_calibration_and_training_transform_is_honest(
    built: tuple[dict[str, object], dict[str, object]],
) -> None:
    _, receipt = built
    selector = _selector(receipt, target.TAIL_LCB_STRATEGY_ID)
    assert selector["ordered_lineup_ids"][:3] == [
        "lineup-000",
        "lineup-002",
        "lineup-001",
    ]
    calibration = selector["independent_calibration_receipt"]
    assert calibration["rank_training_blocks"] == ["R0", "R1", "R2"]
    assert calibration["calibration_block"] == "R3"
    assert calibration["alpha_per_catalog_member"] == 0.025
    assert calibration["catalog_ids"] == list(target.LCB_CATALOG_IDS)
    assert calibration["catalog_ranks_frozen_before_calibration"] is True
    assert calibration["calibration_excluded_from_every_rank_search"] is True
    assert calibration[
        "calibration_origin_excluded_from_every_rank_search"
    ] is True
    assert calibration["calibration_origin_eligible_count"] == 80
    assert calibration["bound_scope"] == "chosen-exact-rank80-book-only"
    assert calibration["prefix_confidence_claim"] is False
    _assert_false_authorities(calibration)
    for catalog_row in calibration["catalog"]:
        assert catalog_row["rank_training_blocks"] == ["R0", "R1", "R2"]
        assert catalog_row["calibration_block"] == "R3"
        assert catalog_row["rank_training_uses_calibration_block"] is False
        assert catalog_row["candidate_origin_uses_calibration_block"] is False
        assert catalog_row["rank_frozen_before_calibration"] is True
        count = catalog_row["calibration_inclusive_230_book_hit_count"]
        expected = 0.0 if count == 0 else betaincinv(count, 11 - count, 0.025)
        assert catalog_row["calibration_cp_lower"] == pytest.approx(
            expected, abs=1e-15
        )
    table = target._clopper_pearson_lower_table(
        worlds_per_block=10, tail_probability=0.05 / 3.0
    )
    prior_counts = np.zeros(3, dtype=np.int64)
    prior_objective = 0.0
    for rank, row in enumerate(selector["trace"]):
        assert row["selection_rank"] == rank
        assert row["meta_catalog_source_id"] == target.LCB_CATALOG_IDS[0]
        assert row["meta_rank_trained_without_calibration"] is True
        assert row["frequentist_confidence_claim"] is False
        assert row["coverage_claim"] is False
        assert row["pre_block_union_hit_counts"] == prior_counts.tolist()
        post_counts = np.asarray(row["post_block_union_hit_counts"], dtype=np.int64)
        expected_lowers = table[post_counts]
        assert row["post_block_cp_training_transforms"] == pytest.approx(
            expected_lowers.tolist(), abs=1e-15
        )
        expected_objective = float(expected_lowers.mean(dtype=np.float64))
        assert row["pre_mean_block_cp_training_utility"] == pytest.approx(
            prior_objective, abs=1e-15
        )
        assert row["post_mean_block_cp_training_utility"] == pytest.approx(
            expected_objective, abs=1e-15
        )
        assert row["marginal_mean_block_cp_training_utility"] == pytest.approx(
            expected_objective - prior_objective, abs=1e-15
        )
        assert row["post_minimum_block_cp_training_transform"] == pytest.approx(
            float(expected_lowers.min()), abs=1e-15
        )
        prior_counts = post_counts
        prior_objective = expected_objective
    assert len(selector["trace"]) == 80


def test_correlation_aware_trace_replays_dk_unit_penalty(
    built: tuple[dict[str, object], dict[str, object]],
) -> None:
    _, receipt = built
    selector = _selector(receipt, target.CORRELATION_AWARE_STRATEGY_ID)
    assert selector["ordered_lineup_ids"][:2] == ["lineup-000", "lineup-002"]
    # The lower-scoring duplicate of lineup-000 is deliberately last.
    assert selector["ordered_lineup_ids"][-1] == "lineup-001"
    canonical_ids, canonical_scores = _canonical_fixture()
    row_by_id = {
        lineup_id: canonical_scores[index]
        for index, lineup_id in enumerate(canonical_ids)
    }
    current_max: np.ndarray | None = None
    union = np.zeros(canonical_scores.shape[1], dtype=bool)
    for rank, row in enumerate(selector["trace"]):
        values = row_by_id[row["lineup_id"]]
        before = 0.0 if current_max is None else float(current_max.mean())
        base_gain = (
            float(values.mean())
            if current_max is None
            else float(np.maximum(values - current_max, 0.0).mean())
        )
        event = values >= 230.0
        overlap = int(np.count_nonzero(event & union))
        penalty = 230.0 * float(overlap) / 40.0
        current_max = (
            values.copy()
            if current_max is None
            else np.maximum(current_max, values)
        )
        union |= event
        assert row["selection_rank"] == rank
        assert row["book_expected_max_before_dk"] == pytest.approx(before)
        assert row["base_marginal_expected_max_gain_dk"] == pytest.approx(
            base_gain
        )
        assert row["redundant_inclusive_230_event_count"] == overlap
        assert row["redundant_inclusive_230_event_rate"] == pytest.approx(
            overlap / 40.0
        )
        assert row["redundancy_penalty_dk"] == pytest.approx(penalty)
        assert row["penalized_marginal_expected_max_gain_dk"] == pytest.approx(
            base_gain - penalty
        )
        assert row["book_expected_max_after_dk"] == pytest.approx(
            float(current_max.mean())
        )
        assert row["book_inclusive_230_union_count_after"] == int(union.sum())
    duplicate = selector["trace"][-1]
    assert duplicate["redundant_inclusive_230_event_count"] == 8
    assert duplicate["redundancy_penalty_dk"] == pytest.approx(46.0)
    assert duplicate["penalized_marginal_expected_max_gain_dk"] == pytest.approx(
        -46.0
    )


def test_independent_calibration_meta_selector_chooses_one_whole_frozen_rank() -> None:
    lineup_ids = [f"candidate-{index:03d}" for index in range(82)]
    scores = np.full((82, 40), 100.0, dtype=np.float64)
    scores[80, 30:36] = 240.0
    scores[81, 30:36] = 235.0
    first_rank = list(range(80))
    second_rank = list(range(2, 82))
    first_trace = [{"selection_rank": rank} for rank in range(80)]
    second_trace = [{"selection_rank": rank} for rank in range(80)]
    meta_kwargs: dict[str, object] = {
        "lineup_ids": lineup_ids,
        "fit_scores": np.ascontiguousarray(scores),
        "training_blocks": ("R0", "R1", "R2", "R3"),
        "heldout_block": "R4",
        "worlds_per_block": 10,
        "candidate_mask_sha256": _hash("f"),
        "occurrence_lineage_sha256": _hash("1"),
        **_source_identities(),
        "require_production_width": False,
    }
    _attach_calibration_origin_lineage(meta_kwargs)
    eligible_indices, origin_binding = _derived_calibration_origin_binding(
        meta_kwargs
    )
    selected, trace, calibration = target._select_independent_calibration_meta_rank(
        catalog=(
            (target.LCB_CATALOG_IDS[0], first_rank, first_trace),
            (target.LCB_CATALOG_IDS[1], second_rank, second_trace),
        ),
        lineup_ids=lineup_ids,
        scores=scores,
        canonical_source_rows=np.arange(82, dtype=np.int64),
        rank_training_blocks=("R0", "R1", "R2"),
        calibration_block="R3",
        worlds_per_block=10,
        rank_training_matrix_sha256=_hash("6"),
        calibration_matrix_sha256=_hash("7"),
        eligible_canonical_indices=eligible_indices,
        calibration_origin_binding=origin_binding,
    )
    assert selected == second_rank
    assert calibration["chosen_catalog_ordinal"] == 1
    assert calibration["chosen_catalog_id"] == target.LCB_CATALOG_IDS[1]
    assert calibration["calibration_origin_eligible_count"] == 82
    assert calibration[
        "calibration_origin_excluded_from_every_rank_search"
    ] is True
    assert calibration["catalog"][0][
        "calibration_inclusive_230_book_hit_count"
    ] == 0
    assert calibration["catalog"][1][
        "calibration_inclusive_230_book_hit_count"
    ] == 6
    assert calibration["chosen_exact_rank80_calibration_cp_lower"] == (
        pytest.approx(betaincinv(6, 5, 0.025), abs=1e-15)
    )
    assert all(
        row["meta_catalog_source_id"] == target.LCB_CATALOG_IDS[1]
        for row in trace
    )
    stripped_counts = {
        lineup_id: ({"R3": 1} if index < 2 else {"R0": 1})
        for index, lineup_id in enumerate(lineup_ids)
    }
    _attach_calibration_origin_lineage(
        meta_kwargs, counts_by_lineup=stripped_counts
    )
    stripped_indices, stripped_binding = _derived_calibration_origin_binding(
        meta_kwargs
    )
    assert stripped_indices.tolist() == list(range(2, 82))
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="candidate rank differs",
    ):
        target._select_independent_calibration_meta_rank(
            catalog=(
                (target.LCB_CATALOG_IDS[0], first_rank, first_trace),
                (target.LCB_CATALOG_IDS[1], second_rank, second_trace),
            ),
            lineup_ids=lineup_ids,
            scores=scores,
            canonical_source_rows=np.arange(82, dtype=np.int64),
            rank_training_blocks=("R0", "R1", "R2"),
            calibration_block="R3",
            worlds_per_block=10,
            rank_training_matrix_sha256=_hash("6"),
            calibration_matrix_sha256=_hash("7"),
            eligible_canonical_indices=stripped_indices,
            calibration_origin_binding=stripped_binding,
        )


def test_runtime_score_scans_are_candidate_chunk_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_widths: list[int] = []
    observed_cp_scopes: list[tuple[str, ...]] = []
    observed_correlation_scopes: list[tuple[str, ...]] = []
    original_score_rows = target._score_rows
    original_cp = target._select_cp_transformed_training_utility
    original_correlation = target._select_correlation_aware_expected_max

    def checked_score_rows(
        scores: np.ndarray,
        canonical_source_rows: np.ndarray,
        start: int,
        stop: int,
        *,
        column_start: int | None = None,
        column_stop: int | None = None,
    ) -> np.ndarray:
        observed_widths.append(stop - start)
        assert 1 <= stop - start <= target.CANDIDATE_CHUNK_ROWS
        return original_score_rows(
            scores,
            canonical_source_rows,
            start,
            stop,
            column_start=column_start,
            column_stop=column_stop,
        )

    def checked_cp(**kwargs: object):
        observed_cp_scopes.append(tuple(kwargs["training_blocks"]))
        return original_cp(**kwargs)

    def checked_correlation(**kwargs: object):
        observed_correlation_scopes.append(tuple(kwargs["training_blocks"]))
        return original_correlation(**kwargs)

    monkeypatch.setattr(target, "_score_rows", checked_score_rows)
    monkeypatch.setattr(
        target, "_select_cp_transformed_training_utility", checked_cp
    )
    monkeypatch.setattr(
        target, "_select_correlation_aware_expected_max", checked_correlation
    )
    target.run_extreme_tail_roadmap_retrieval_v1(**_kwargs())
    assert max(observed_widths) == target.CANDIDATE_CHUNK_ROWS
    assert observed_cp_scopes == [("R0", "R1", "R2")]
    assert observed_correlation_scopes == [
        ("R0", "R1", "R2"),
        ("R0", "R1", "R2", "R3"),
    ]
    implementation = target.frozen_roadmap_retrieval_implementation_v1()
    assert implementation["dense_candidate_by_world_boolean_matrix"] is False
    assert implementation["full_score_matrix_copy"] is False


def test_exact_rank80_prefix_books_lineage_and_false_authority(
    built: tuple[dict[str, object], dict[str, object]],
) -> None:
    kwargs, receipt = built
    assert receipt["selector_count"] == 2
    assert receipt["ranking_depth"] == 80
    assert receipt["input_binding"]["training_blocks"] == [
        "R0",
        "R1",
        "R2",
        "R3",
    ]
    assert receipt["input_binding"]["heldout_block_identifier_only"] == "R4"
    assert receipt["input_binding"]["heldout_score_columns_present"] is False
    assert receipt["input_binding"]["realized_outcomes_present"] is False
    assert receipt["input_binding"]["candidate_mask_sha256"] == kwargs[
        "candidate_mask_sha256"
    ]
    assert receipt["input_binding"]["occurrence_lineage_sha256"] == kwargs[
        "occurrence_lineage_sha256"
    ]
    assert receipt["input_binding"]["source_manifest_identity"] == kwargs[
        "source_manifest_identity"
    ]
    assert receipt["input_binding"]["source_member_identity"] == kwargs[
        "source_member_identity"
    ]
    _assert_false_authorities(receipt)
    _assert_false_authorities(receipt["input_binding"])
    assert receipt["standalone_source_authority"] is False
    assert receipt["outer_exact_source_replay_required"] is True
    for selector in receipt["selectors"]:
        assert selector["selected_count"] == 80
        assert selector["trace_count"] == 80
        assert selector["entry_budgets"] == [4, 14, 80]
        _assert_false_authorities(selector)
        for budget, book in zip((4, 14, 80), selector["books"], strict=True):
            assert book["entry_budget"] == budget
            assert book["selected_count"] == budget
            assert book["ordered_lineup_ids"] == selector[
                "ordered_lineup_ids"
            ][:budget]
            assert book["ordered_canonical_lineup_indices"] == selector[
                "ordered_canonical_lineup_indices"
            ][:budget]
            assert book["prefix_replay_exact"] is True
            _assert_false_authorities(book)


def test_input_row_permutation_is_canonical_and_validator_replays(
    built: tuple[dict[str, object], dict[str, object]],
) -> None:
    kwargs, receipt = built
    canonical_kwargs = _kwargs(canonical_order=True)
    canonical_receipt = target.run_extreme_tail_roadmap_retrieval_v1(
        **canonical_kwargs
    )
    assert canonical_receipt == receipt
    assert target.validate_extreme_tail_roadmap_retrieval_v1(
        receipt, **kwargs
    ) == receipt
    assert target.validate_extreme_tail_roadmap_retrieval_v1(
        receipt, **canonical_kwargs
    ) == receipt


def test_public_runner_has_no_heldout_or_realized_score_argument() -> None:
    parameters = inspect.signature(
        target.run_extreme_tail_roadmap_retrieval_v1
    ).parameters
    assert "heldout_scores" not in parameters
    assert "realized_scores" not in parameters
    assert "outcomes" not in parameters
    assert set(parameters) == {
        "lineup_ids",
        "fit_scores",
        "training_blocks",
        "heldout_block",
        "worlds_per_block",
        "candidate_mask_sha256",
        "occurrence_lineage_sha256",
        "calibration_origin_lineage_artifact",
        "calibration_origin_lineage_artifact_identity",
        "source_manifest_identity",
        "source_member_identity",
        "source_score_matrix_identity",
        "require_production_width",
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("TAIL_THRESHOLD_DK", 229.0),
        ("LCB_TOTAL_ALPHA", 0.10),
        ("LCB_CONFIDENCE_LEVEL", 0.90),
        ("CP_TRAINING_TRANSFORM_ALPHA", 0.10),
        ("LCB_CATALOG_IDS", ("forged-rank", "other-forged-rank")),
        ("LCB_CALIBRATION_ORIGIN_LAW", "forged-origin-law"),
        ("REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP", 229.0),
        ("CANDIDATE_CHUNK_ROWS", 32),
    ],
)
def test_literal_formula_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch, field: str, replacement: object
) -> None:
    monkeypatch.setattr(target, field, replacement)
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="literal roadmap retrieval constants drifted",
    ):
        target.run_extreme_tail_roadmap_retrieval_v1(**_kwargs())


def test_literal_hash_and_numerical_runtime_drift_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "EXPECTED_IMPLEMENTATION_SHA256", _hash("9"))
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="implementation hash differs",
    ):
        target.frozen_roadmap_retrieval_registry_v1()

    monkeypatch.undo()
    monkeypatch.setattr(target.scipy, "__version__", "0.0.0")
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="numerical runtime differs",
    ):
        target.frozen_roadmap_retrieval_registry_v1()


def test_upstream_fit_scope_or_expected_max_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target.preweek, "RANKING_DEPTH", 79)
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="imported world, budget, or fit-scope constants drifted",
    ):
        target.run_extreme_tail_roadmap_retrieval_v1(**_kwargs())


@pytest.mark.parametrize(
    "attack",
    [
        "heldout-column-append",
        "wrong-block-membership",
        "duplicate-lineup-id",
        "too-few-candidates",
        "float32-matrix",
        "nonfinite-matrix",
        "calibration-origin-shortfall",
        "calibration-origin-row-splice",
        "calibration-origin-object-identity",
    ],
)
def test_invalid_fit_inputs_fail_before_selection(attack: str) -> None:
    kwargs = _kwargs()
    scores = np.asarray(kwargs["fit_scores"])
    lineup_ids = list(kwargs["lineup_ids"])
    if attack == "heldout-column-append":
        kwargs["fit_scores"] = np.ascontiguousarray(
            np.column_stack([scores, np.zeros((80, 10), dtype=np.float64)])
        )
    elif attack == "wrong-block-membership":
        kwargs["training_blocks"] = ("R0", "R1", "R2", "R4")
    elif attack == "duplicate-lineup-id":
        lineup_ids[-1] = lineup_ids[0]
        kwargs["lineup_ids"] = lineup_ids
    elif attack == "too-few-candidates":
        kwargs["lineup_ids"] = lineup_ids[:79]
        kwargs["fit_scores"] = np.ascontiguousarray(scores[:79])
    elif attack == "float32-matrix":
        kwargs["fit_scores"] = np.ascontiguousarray(scores, dtype=np.float32)
    elif attack == "nonfinite-matrix":
        changed = scores.copy()
        changed[0, 0] = np.nan
        kwargs["fit_scores"] = changed
    elif attack == "calibration-origin-shortfall":
        canonical_ids = sorted(lineup_ids)
        counts = {
            lineup_id: (
                {"R3": 1}
                if lineup_id == canonical_ids[-1]
                else {"R0": 1}
            )
            for lineup_id in canonical_ids
        }
        _attach_calibration_origin_lineage(
            kwargs, counts_by_lineup=counts
        )
    elif attack == "calibration-origin-row-splice":
        artifact = deepcopy(kwargs["calibration_origin_lineage_artifact"])
        artifact["candidate_origin_rows"][0]["occurrence_counts_by_block"][
            "R0"
        ] = 2
        kwargs["calibration_origin_lineage_artifact"] = artifact
    elif attack == "calibration-origin-object-identity":
        identity = deepcopy(
            kwargs["calibration_origin_lineage_artifact_identity"]
        )
        identity["sha256"] = _hash("9")
        kwargs["calibration_origin_lineage_artifact_identity"] = identity
    with pytest.raises(target.CorpusExtremeTailRoadmapRetrievalError):
        target.run_extreme_tail_roadmap_retrieval_v1(**kwargs)


@pytest.mark.parametrize(
    "splice",
    ["matrix", "candidate-mask", "occurrence-lineage", "manifest", "member"],
)
def test_validator_rejects_exact_lineage_and_matrix_splices(
    built: tuple[dict[str, object], dict[str, object]], splice: str
) -> None:
    kwargs, receipt = built
    changed = deepcopy(kwargs)
    if splice == "matrix":
        scores = np.asarray(changed["fit_scores"]).copy()
        scores[0, 0] += 1.0
        changed["fit_scores"] = scores
    elif splice == "candidate-mask":
        changed["candidate_mask_sha256"] = _hash("2")
    elif splice == "occurrence-lineage":
        changed["occurrence_lineage_sha256"] = _hash("3")
    elif splice == "manifest":
        manifest = deepcopy(changed["source_manifest_identity"])
        manifest["manifest_sha256"] = _hash("4")
        changed["source_manifest_identity"] = manifest
    elif splice == "member":
        member = deepcopy(changed["source_member_identity"])
        member["member_sha256"] = _hash("5")
        changed["source_member_identity"] = member
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="differs from canonical replay",
    ):
        target.validate_extreme_tail_roadmap_retrieval_v1(
            receipt, **changed
        )


def test_coherently_rehashed_calibration_origin_artifact_splice_fails_replay(
    built: tuple[dict[str, object], dict[str, object]],
) -> None:
    kwargs, receipt = built
    generation_changed = deepcopy(kwargs)
    generation_changed["calibration_origin_lineage_artifact_identity"][
        "generation"
    ] = "987654322"
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="differs from canonical replay",
    ):
        target.validate_extreme_tail_roadmap_retrieval_v1(
            receipt, **generation_changed
        )

    changed = deepcopy(kwargs)
    artifact = changed["calibration_origin_lineage_artifact"]
    row = artifact["candidate_origin_rows"][0]
    row["occurrence_counts_by_block"]["R0"] = 0
    row["occurrence_counts_by_block"]["R1"] = 1
    row["origin_blocks"] = ["R1"]
    _rehash_calibration_origin_artifact(changed)

    changed_receipt = target.run_extreme_tail_roadmap_retrieval_v1(**changed)
    assert changed_receipt["input_binding_sha256"] != receipt[
        "input_binding_sha256"
    ]
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="differs from canonical replay",
    ):
        target.validate_extreme_tail_roadmap_retrieval_v1(
            receipt, **changed
        )


def test_coherently_rehashed_nested_ranking_splice_still_fails_replay(
    built: tuple[dict[str, object], dict[str, object]],
) -> None:
    kwargs, receipt = built
    changed = deepcopy(receipt)
    selector = changed["selectors"][0]
    selector["ordered_lineup_ids"][0] = "lineup-forged"
    selector_body = {
        key: value
        for key, value in selector.items()
        if key != "selector_receipt_sha256"
    }
    selector["selector_receipt_sha256"] = target._sha(
        selector_body, label="forged selector"
    )
    changed["selector_receipt_sha256s"][0] = selector[
        "selector_receipt_sha256"
    ]
    changed["selector_receipt_sha256s_sha256"] = target._sha(
        changed["selector_receipt_sha256s"], label="forged selector hashes"
    )
    receipt_body = {
        key: value for key, value in changed.items() if key != "receipt_sha256"
    }
    changed["receipt_sha256"] = target._sha(
        receipt_body, label="forged receipt"
    )
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="differs from canonical replay",
    ):
        target.validate_extreme_tail_roadmap_retrieval_v1(
            changed, **kwargs
        )


def test_final_fit_requires_all_five_r_blocks() -> None:
    lineup_ids, four_block_scores = _canonical_fixture()
    fifth = np.full((80, 10), 90.0, dtype=np.float64)
    scores = np.ascontiguousarray(np.column_stack([four_block_scores, fifth]))
    kwargs = {
        **_kwargs(canonical_order=True),
        "lineup_ids": lineup_ids,
        "fit_scores": scores,
        "training_blocks": ("R0", "R1", "R2", "R3", "R4"),
        "heldout_block": None,
    }
    _attach_calibration_origin_lineage(kwargs)
    receipt = target.run_extreme_tail_roadmap_retrieval_v1(**kwargs)
    assert receipt["fit_scope_id"] == "all-block-final-fit"
    assert receipt["input_binding"]["training_blocks"] == [
        "R0",
        "R1",
        "R2",
        "R3",
        "R4",
    ]
    assert receipt["input_binding"]["lcb_rank_training_blocks"] == [
        "R0",
        "R1",
        "R2",
        "R3",
    ]
    assert receipt["input_binding"]["lcb_calibration_block"] == "R4"
    assert receipt["input_binding"][
        "cp_training_transform_probability_per_block"
    ] == pytest.approx(0.0125)
    assert receipt["input_binding"][
        "lcb_alpha_per_catalog_member"
    ] == pytest.approx(0.025)
    calibration = _selector(
        receipt, target.TAIL_LCB_STRATEGY_ID
    )["independent_calibration_receipt"]
    assert calibration["rank_training_blocks"] == ["R0", "R1", "R2", "R3"]
    assert calibration["calibration_block"] == "R4"
    assert calibration["alpha_per_catalog_member"] == pytest.approx(
        0.025
    )


def test_production_width_is_literal_10000() -> None:
    with pytest.raises(
        target.CorpusExtremeTailRoadmapRetrievalError,
        match="exactly 10,000",
    ):
        target.run_extreme_tail_roadmap_retrieval_v1(
            **{**_kwargs(), "require_production_width": True}
        )
