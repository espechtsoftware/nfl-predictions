from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_combined_population_all_block_v1 as c
from nfl_dfs.research import residual_world_columns as rw


def _identity(label: str) -> dict[str, object]:
    return {
        "uri": f"gs://synthetic/{label}",
        "generation": "1",
        "sha256": (label.encode().hex() + "0" * 64)[:64],
        "bytes": 1,
    }


def _rosters(count: int = 90) -> list[list[str]]:
    return [
        [f"player-{offset:03d}" for offset in range(index, index + 9)]
        for index in range(count)
    ]


def _sources() -> list[dict[str, object]]:
    rosters = _rosters()
    later = _identity("later")
    worlds = {
        key: _identity(key) for key in c.WORLD_IDENTITY_KEYS
    }
    ranges = {
        c.INCUMBENT_SOURCE_ID: range(0, 85),
        c.PROFILE_SOURCE_IDS[0]: range(80, 87),
        c.PROFILE_SOURCE_IDS[1]: range(81, 88),
        c.PROFILE_SOURCE_IDS[2]: range(82, 89),
        c.HARD230_SOURCE_ID: range(83, 90),
    }
    return [
        c.build_population_source_v1(
            source_id=source_id,
            slate_id="2023-w01",
            source_artifact_binding={"artifact": source_id},
            later_source_identity=later,
            world_artifact_identities=worlds,
            lineups=[{
                "source_lineup_id": f"{source_id}:{index}",
                "roster_player_ids": rosters[index],
                "occurrence_count": index + 1,
                "source_detail_ids": [f"detail:{source_id}"],
            } for index in ranges[source_id]],
        )
        for source_id in c.SOURCE_ORDER
    ]


def _scores() -> np.ndarray:
    row = np.arange(90, dtype=np.float64)[:, None]
    column = np.arange(50_000, dtype=np.float64)[None, :]
    scores = 175.0 + row * 0.75 + ((row + column * 7.0) % 23.0)
    return np.ascontiguousarray(scores, dtype=np.float64)


def test_combined_union_dedupes_and_retains_source_overlap() -> None:
    union = c.build_combined_union_v1(
        slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
        sources=_sources(),
    )
    assert union["union_lineup_count"] == 90
    analysis = union["overlap_analysis"]
    assert analysis["source_membership_counts"] == {
        c.INCUMBENT_SOURCE_ID: 85,
        c.PROFILE_SOURCE_IDS[0]: 7,
        c.PROFILE_SOURCE_IDS[1]: 7,
        c.PROFILE_SOURCE_IDS[2]: 7,
        c.HARD230_SOURCE_ID: 7,
    }
    assert analysis["challenger_only_lineup_count"] == 5
    assert analysis["multi_source_lineup_count"] == 9
    shared = next(
        row for row in union["union_lineups"]
        if len(row["source_population_ids"]) == len(c.SOURCE_ORDER)
    )
    assert shared["source_population_count"] == 5
    assert list(shared["source_lineup_ids_by_population"]) == list(c.SOURCE_ORDER)


def test_all_block_runs_frozen_eight_exact_k80_from_one_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_scores = _scores()
    calls: list[tuple[int, int | None]] = []
    strategy_calls: list[str] = []

    def fake_cross_score(
        players: object,
        player_draws: np.ndarray,
        rosters: object,
        *,
        expected_worlds: int | None = None,
    ) -> np.ndarray:
        del players, player_draws
        calls.append((len(rosters), expected_worlds))
        return expected_scores

    monkeypatch.setattr(c, "cross_score_full_union", fake_cross_score)

    def fake_run_book(**kwargs: object) -> dict[str, object]:
        strategy = kwargs["strategy"]
        admitted_ids = kwargs["admitted_ids"]
        admission = kwargs["admission"]
        roster_by_id = kwargs["roster_by_id"]
        assert isinstance(strategy, dict)
        assert isinstance(admitted_ids, list)
        assert isinstance(admission, dict)
        assert isinstance(roster_by_id, dict)
        assert kwargs["training_scores"] is expected_scores
        strategy_id = str(strategy["strategy_id"])
        strategy_calls.append(strategy_id)
        selected = admitted_ids[:80]
        indices = list(range(80))
        body = {
            "schema_version": c.runner.BOOK_SCHEMA,
            "book_id": f"{c.FIT_SCOPE_ID}:{c.ADMISSION_ID}:{strategy_id}",
            "fit_scope_id": c.FIT_SCOPE_ID,
            "reconstruction_sha256": kwargs["reconstruction_sha256"],
            "training_blocks": list(c.rw.WORLD_BLOCKS),
            "heldout_block": None,
            "admission_id": c.ADMISSION_ID,
            "admission_sha256": admission["admission_sha256"],
            "strategy_id": strategy_id,
            "strategy_sha256": strategy["strategy_sha256"],
            "strategy_application_scope": "explicit-all-five-block-final-fit",
            "input_lineup_ids_sha256": c._hash(admitted_ids),
            "training_score_matrix_sha256": kwargs[
                "training_score_matrix_sha256"
            ],
            "training_score_shape": [len(admitted_ids), 50_000],
            "worlds_per_block": 10_000,
            "dose_authority": c.DOSE_AUTHORITY,
            "selected_local_indices": indices,
            "selected_global_indices": indices,
            "selected_lineup_ids": selected,
            "selected_rosters": [roster_by_id[lineup_id] for lineup_id in selected],
            "entry_count": 80,
            "marginal_trace": [{
                "selection_rank": rank,
                "lineup_id": lineup_id,
                "admitted_lineup_index": rank,
                "global_lineup_index": rank,
                "marginal_gain": 0.0,
            } for rank, lineup_id in enumerate(selected)],
            "training_metrics": {"aggregate": {}, "by_block": []},
            "redundancy_diagnostics": {
                "schema_version": "corpus-book-redundancy-diagnostics/v1",
                "pairwise_score_correlation": {
                    "schema_version": "corpus-bounded-pairwise-score-correlation/v1",
                    "uses_realized_outcomes": False,
                },
                "uses_realized_outcomes": False,
            },
            "heldout_metrics_descriptive": None,
            "threshold_semantics": [],
            "uses_realized_outcomes": False,
            "promotion_authority": False,
        }
        return {**body, "book_sha256": c._hash(body)}

    monkeypatch.setattr(c.runner, "_run_book", fake_run_book)
    players = tuple(
        SimpleNamespace(player_id=f"player-{index:03d}")
        for index in range(98)
    )
    draws = np.zeros((len(players), 50_000), dtype=np.float32, order="C")
    result = c.run_combined_population_all_block_v1(
        slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
        sources=_sources(),
        players=players,
        player_draws=draws,
        worlds_per_block=10_000,
        require_authoritative=False,
    )

    assert calls == [(90, 50_000)]
    assert strategy_calls == [
        str(strategy["strategy_id"])
        for strategy in c.lane.frozen_full_union_strategies_v1()
    ]
    assert result["complete"] is True
    assert result["fit_scope_id"] == "all-block-final-fit"
    assert result["book_count"] == 8
    assert len(result["selected_source_contributions"]) == 8
    assert all(book["entry_count"] == 80 for book in result["books"])
    assert all(
        contribution["selected_lineup_count"] == 80
        for contribution in result["selected_source_contributions"]
    )
    assert result["matrix_binding"]["player_world_matrix_read_count"] == 1
    assert result["matrix_binding"]["union_score_matrix_materialization_count"] == 1
    assert result["population_regeneration_performed"] is False
    for contribution in result["selected_source_contributions"]:
        assert (
            contribution["selected_incumbent_member_count"]
            + contribution["selected_challenger_only_lineup_count"]
            == 80
        )
    normalized = c.normalized_slate_for_grader_v1(result, source_ordinal=0)
    assert normalized["source_ordinal"] == 0
    assert len(normalized["populations"]) == 1
    assert len(normalized["populations"][0]["lineups"]) == 90
    assert len(normalized["books"]) == 8
    assert all(
        book["coordinate"]["entry_budget"] == 80
        for book in normalized["books"]
    )

    def rehash_result(value: dict[str, object]) -> dict[str, object]:
        value["books_sha256"] = c._hash(value["books"])
        value["selected_source_contributions_sha256"] = c._hash(
            value["selected_source_contributions"]
        )
        value["result_sha256"] = c._hash({
            key: item for key, item in value.items() if key != "result_sha256"
        })
        return value

    mutations = []
    bad_self_hash = deepcopy(result)
    bad_self_hash["books"][0]["book_sha256"] = "f" * 64
    mutations.append(bad_self_hash)
    for field in (
        "strategy_sha256", "admission_sha256", "reconstruction_sha256",
        "training_score_matrix_sha256",
    ):
        changed = deepcopy(result)
        changed["books"][0][field] = "e" * 64
        changed["books"][0]["book_sha256"] = c._hash({
            key: item for key, item in changed["books"][0].items()
            if key != "book_sha256"
        })
        mutations.append(changed)
    changed_index = deepcopy(result)
    changed_index["books"][0]["selected_local_indices"][0] = 89
    changed_index["books"][0]["book_sha256"] = c._hash({
        key: item for key, item in changed_index["books"][0].items()
        if key != "book_sha256"
    })
    mutations.append(changed_index)
    changed_roster = deepcopy(result)
    changed_roster["books"][0]["selected_rosters"][0][0] = "player-999"
    changed_roster["books"][0]["book_sha256"] = c._hash({
        key: item for key, item in changed_roster["books"][0].items()
        if key != "book_sha256"
    })
    mutations.append(changed_roster)
    changed_contribution = deepcopy(result)
    changed_contribution["selected_source_contributions"][0][
        "selected_incumbent_member_count"
    ] -= 1
    contribution = changed_contribution["selected_source_contributions"][0]
    contribution["contribution_sha256"] = c._hash({
        key: item for key, item in contribution.items()
        if key != "contribution_sha256"
    })
    mutations.append(changed_contribution)
    changed_admission = deepcopy(result)
    changed_admission["admission"]["admitted_lineup_ids"][0] = (
        changed_admission["admission"]["admitted_lineup_ids"][1]
    )
    changed_admission["admission"]["admission_sha256"] = c._hash({
        key: item for key, item in changed_admission["admission"].items()
        if key != "admission_sha256"
    })
    changed_admission["admission_sha256"] = changed_admission["admission"][
        "admission_sha256"
    ]
    for book in changed_admission["books"]:
        book["admission_sha256"] = changed_admission["admission_sha256"]
        book["book_sha256"] = c._hash({
            key: item for key, item in book.items() if key != "book_sha256"
        })
    mutations.append(changed_admission)
    changed_matrix = deepcopy(result)
    changed_matrix["matrix_binding"]["union_sha256"] = "d" * 64
    changed_matrix["matrix_binding"]["matrix_binding_sha256"] = c._hash({
        key: item for key, item in changed_matrix["matrix_binding"].items()
        if key != "matrix_binding_sha256"
    })
    changed_matrix["matrix_binding_sha256"] = changed_matrix["matrix_binding"][
        "matrix_binding_sha256"
    ]
    for book in changed_matrix["books"]:
        book["reconstruction_sha256"] = changed_matrix["matrix_binding_sha256"]
        book["book_sha256"] = c._hash({
            key: item for key, item in book.items() if key != "book_sha256"
        })
    mutations.append(changed_matrix)
    for mutation in mutations:
        with pytest.raises(c.CorpusR6CombinedPopulationAllBlockV1Error):
            c.normalized_slate_for_grader_v1(
                rehash_result(mutation), source_ordinal=0
            )

    # A maliciously coherent book substitution can satisfy every nested hash
    # and structural binding.  Only exact selector replay from the frozen
    # sources/matrix can reject it.
    substituted = deepcopy(result)
    book = substituted["books"][0]
    replacement = substituted["union"]["union_lineups"][89]
    book["selected_local_indices"][0] = 89
    book["selected_global_indices"][0] = 89
    book["selected_lineup_ids"][0] = replacement["lineup_id"]
    book["selected_rosters"][0] = replacement["roster_player_ids"]
    book["marginal_trace"][0]["lineup_id"] = replacement["lineup_id"]
    book["marginal_trace"][0]["admitted_lineup_index"] = 89
    book["marginal_trace"][0]["global_lineup_index"] = 89
    book["book_sha256"] = c._hash({
        key: item for key, item in book.items() if key != "book_sha256"
    })
    union_by_id = {
        row["lineup_id"]: row for row in substituted["union"]["union_lineups"]
    }
    substituted["selected_source_contributions"][0] = c._selected_contribution(
        strategy_id=book["strategy_id"],
        selected_ids=book["selected_lineup_ids"],
        union_by_id=union_by_id,
    )
    rehash_result(substituted)
    c.normalized_slate_for_grader_v1(substituted, source_ordinal=0)
    with pytest.raises(
        c.CorpusR6CombinedPopulationAllBlockV1Error,
        match="exact frozen-source replay",
    ):
        c.validate_exact_science_replay_v1(
            substituted, result, source_ordinal=0
        )


def test_combined_union_rejects_authority_or_source_census_drift() -> None:
    sources = _sources()
    with pytest.raises(
        c.CorpusR6CombinedPopulationAllBlockV1Error,
        match="source order/census",
    ):
        c.build_combined_union_v1(
            slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
            sources=sources[:-1],
        )

    mismatched = deepcopy(sources)
    mismatched[-1] = c.build_population_source_v1(
        source_id=c.HARD230_SOURCE_ID,
        slate_id="2023-w01",
        source_artifact_binding={"artifact": c.HARD230_SOURCE_ID},
        later_source_identity=_identity("different-later"),
        world_artifact_identities={
            key: _identity(key) for key in c.WORLD_IDENTITY_KEYS
        },
        lineups=mismatched[-1]["lineups"],
    )
    with pytest.raises(
        c.CorpusR6CombinedPopulationAllBlockV1Error,
        match="one slate/source/world authority",
    ):
        c.build_combined_union_v1(
            slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
            sources=mismatched,
        )


def test_authoritative_run_rejects_reduced_world_fixture() -> None:
    players = tuple(
        SimpleNamespace(player_id=f"player-{index:03d}")
        for index in range(98)
    )
    draws = np.zeros((len(players), 10), dtype=np.float32, order="C")
    with pytest.raises(
        c.CorpusR6CombinedPopulationAllBlockV1Error,
        match="complete 10,000-world blocks",
    ):
        c.run_combined_population_all_block_v1(
            slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
            sources=_sources(),
            players=players,
            player_draws=draws,
            worlds_per_block=2,
            require_authoritative=True,
        )
