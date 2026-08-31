from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_broad_admission_tournament_v1 as subject


def _candidates(count: int = 600) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    source_count = len(subject.SOURCE_ORDER)
    group_size = max(1, count // source_count)
    for index in range(count):
        primary = min(source_count - 1, index // group_size)
        source_indices = {primary}
        if index % 13 == 0:
            source_indices.add((primary + 1) % source_count)
        if index % 29 == 0:
            source_indices.add((primary + 2) % source_count)
        sources = [
            source for ordinal, source in enumerate(subject.SOURCE_ORDER)
            if ordinal in source_indices
        ]
        details = {
            source: sorted({
                f"family-{subject.SOURCE_ORDER.index(source)}",
                f"law-{index % 31:02d}",
            })
            for source in sources
        }
        rows.append({
            "lineup_id": f"L{index:04d}",
            "roster_player_ids": [f"P{index:04d}-{slot}" for slot in range(9)],
            "source_population_ids": sources,
            "source_population_count": len(sources),
            "source_lineup_ids_by_population": {
                source: f"{source}-L{index:04d}" for source in sources
            },
            "source_occurrence_counts_by_population": {
                source: 1 + (index % 3) for source in sources
            },
            "source_detail_ids_by_population": details,
        })
    return rows


def _scores(count: int = 600, worlds: int = 32) -> np.ndarray:
    base = 105.0 + np.arange(count, dtype=np.float64) * 0.24
    offsets = np.linspace(-4.0, 4.0, worlds, dtype=np.float64)
    return np.ascontiguousarray(base[:, None] + offsets[None, :])


def _freeze(*, season: int = 2023, week: int = 1, count: int = 600):
    return subject.freeze_slate_inputs_v1(
        slate={
            "season": season,
            "week": week,
            "slate_id": f"{season}-w{week:02d}",
        },
        candidates=_candidates(count),
        modeled_score_matrix=_scores(count),
        source_binding={"uri": f"gs://example/{season}-w{week:02d}", "generation": "1"},
    )


def _realized_scores(freeze: dict[str, object]) -> dict[str, int]:
    rows = freeze["candidate_features"]
    assert isinstance(rows, list)
    return {
        str(row["lineup_id"]): 300_000_000 - ordinal * 100_000
        for ordinal, row in enumerate(rows)
    }


def _identity(uri: str, generation: int, digest: str = "a") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest * 64,
        "bytes": 100,
    }


def test_fixed_budget_reference_and_quota_are_outcome_blind_and_deterministic():
    freeze = _freeze()
    assert freeze["uses_realized_outcomes"] is False
    assert freeze["full_union_oracle_is_training_target"] is False
    assert freeze["parent_a250_reference_law"] == subject.frontier.SIEVE_LAW
    scores = _scores()
    expected_indices = sorted(
        range(len(scores)),
        key=lambda index: (
            -int(np.count_nonzero(scores[index] > 230.0)),
            -int(np.count_nonzero(scores[index] > 220.0)),
            -int(np.count_nonzero(scores[index] > 210.0)),
            -int(np.count_nonzero(scores[index] > 200.0)),
            -float(scores[index].mean(dtype=np.float64)),
            f"L{index:04d}",
        ),
    )
    expected_a250 = {f"L{index:04d}" for index in expected_indices[:250]}
    assert set(subject.build_reference_admission_v1(
        freeze, budget=250
    )["selected_lineup_ids"]) == expected_a250

    for budget in subject.ADMISSION_BUDGETS:
        reference = subject.build_reference_admission_v1(freeze, budget=budget)
        quota = subject.build_quota_admission_v1(freeze, budget=budget)
        assert len(reference["selected_lineup_ids"]) == budget
        assert len(quota["selected_lineup_ids"]) == budget
        assert len(set(reference["selected_lineup_ids"])) == budget
        assert len(set(quota["selected_lineup_ids"])) == budget
        assert reference["uses_realized_outcomes"] is False
        assert quota["uses_realized_outcomes"] is False
        assert quota == subject.build_quota_admission_v1(freeze, budget=budget)
        census = quota["quota_policy"]["availability_census"]
        assert census[-1]["selection_stratum"] == "modeled-tail-reference-fill"
        assert all(row["shortfall"] >= 0 for row in census)

    reference_250 = subject.build_reference_admission_v1(freeze, budget=250)
    quota_250 = subject.build_quota_admission_v1(freeze, budget=250)
    assert quota_250["selected_lineup_ids"] != reference_250["selected_lineup_ids"]
    assert any(
        "new_detail_rarity_micro" in row
        for row in quota_250["selection_trace"]
        if row["selection_stratum"] == "rare-source-detail"
    )


def test_reference_uses_exact_float64_mean_at_a500_cutoff():
    candidates = _candidates(501)
    scores = np.ascontiguousarray(
        np.full((501, 8), 100.00000035), dtype=np.float64
    )
    scores[0, :] = 100.0000003
    scores[500, :] = 100.0000004
    freeze = subject.freeze_slate_inputs_v1(
        slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
        candidates=candidates,
        modeled_score_matrix=scores,
        source_binding={"artifact": "exact-mean-test"},
    )
    by_id = {row["lineup_id"]: row for row in freeze["candidate_features"]}
    assert by_id["L0000"]["modeled_mean_micro"] == by_id["L0500"][
        "modeled_mean_micro"
    ]
    selected = subject.build_reference_admission_v1(
        freeze, budget=500
    )["selected_lineup_ids"]
    assert "L0500" in selected
    assert "L0000" not in selected


def test_freeze_rejects_matrix_and_rehashed_semantic_tamper():
    candidates = _candidates()
    matrix = _scores()
    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="modeled score matrix differs",
    ):
        subject.freeze_slate_inputs_v1(
            slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
            candidates=candidates,
            modeled_score_matrix=np.asfortranarray(matrix),
            source_binding={"artifact": "matrix-test"},
        )
    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="carries outcome authority",
    ):
        subject.freeze_slate_inputs_v1(
            slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
            candidates=candidates,
            modeled_score_matrix=matrix,
            source_binding={"realized_outcomes": "forbidden"},
        )

    freeze = _freeze()
    tampered = deepcopy(freeze)
    tampered["realized_score_micro"] = 999_000_000
    tampered["slate_freeze_sha256"] = subject._hash({
        key: value for key, value in tampered.items()
        if key != "slate_freeze_sha256"
    })
    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="authority differs",
    ):
        subject.build_reference_admission_v1(tampered, budget=250)

    tampered = deepcopy(freeze)
    tampered["candidate_features"][0]["strict_gt_240_world_count"] = 999
    tampered["candidate_features_sha256"] = subject._hash(
        tampered["candidate_features"]
    )
    tampered["slate_freeze_sha256"] = subject._hash({
        key: value for key, value in tampered.items()
        if key != "slate_freeze_sha256"
    })
    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="feature values differ",
    ):
        subject.build_reference_admission_v1(tampered, budget=250)

    tampered = deepcopy(freeze)
    first = tampered["candidate_features"][0]
    second = tampered["candidate_features"][1]
    first["reference_rank"], second["reference_rank"] = (
        second["reference_rank"], first["reference_rank"]
    )
    tampered["candidate_features_sha256"] = subject._hash(
        tampered["candidate_features"]
    )
    tampered["slate_freeze_sha256"] = subject._hash({
        key: value for key, value in tampered.items()
        if key != "slate_freeze_sha256"
    })
    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="reference rank differs",
    ):
        subject.build_reference_admission_v1(tampered, budget=250)


def test_direct_ranker_is_past_only_order_invariant_and_exact_budget():
    freeze_2024 = _freeze(season=2024, week=1)
    expected_slates = [f"2023-w{week:02d}" for week in range(1, 19)]
    entries = []
    for week in range(1, 19):
        freeze = _freeze(season=2023, week=week, count=600 + week)
        entries.append((
            freeze,
            _realized_scores(freeze),
            _identity(
                f"gs://example/outcomes/2023-w{week:02d}",
                100 + week,
                format(week % 16, "x"),
            ),
        ))
    ranker = subject.fit_past_season_direct_ranker_v1(
        training=list(reversed(entries)),
        target_season=2024,
        expected_training_slate_ids=expected_slates,
    )
    replay = subject.fit_past_season_direct_ranker_v1(
        training=entries,
        target_season=2024,
        expected_training_slate_ids=expected_slates,
    )
    assert ranker == replay
    assert ranker["training_slates"] == expected_slates
    assert ranker["future_or_target_season_rows_used"] is False
    assert ranker["feature_standardization"] == (
        "equal-slate-sample-weighted-mean-variance"
    )
    assert all(
        np.isclose(
            float.fromhex(binding["sample_weight_sum_hex"]),
            subject.SLATE_TOTAL_SAMPLE_WEIGHT,
        )
        for binding in ranker["training_bindings"]
    )
    for budget in subject.ADMISSION_BUDGETS:
        admission = subject.build_direct_ranker_admission_v1(
            freeze_2024, ranker=ranker, budget=budget
        )
        assert len(admission["selected_lineup_ids"]) == budget
        assert admission["past_season_only"] is True
        assert admission["uses_realized_outcomes"] is True
        assert admission["past_season_labels_used"] is True
        assert admission["target_slate_labels_used"] is False

    reference_2024 = subject.build_reference_admission_v1(
        freeze_2024, budget=250
    )
    quota_2024 = subject.build_quota_admission_v1(freeze_2024, budget=250)
    direct_2024 = subject.build_direct_ranker_admission_v1(
        freeze_2024, ranker=ranker, budget=250
    )
    quota_blend = subject.build_fixed_budget_reference_challenger_blend_v1(
        slate_freeze=freeze_2024,
        reference_admission=reference_2024,
        challenger_admission=quota_2024,
    )
    direct_blend = subject.build_fixed_budget_reference_challenger_blend_v1(
        slate_freeze=freeze_2024,
        reference_admission=reference_2024,
        challenger_admission=direct_2024,
    )
    assert direct_blend["uses_realized_outcomes"] is True
    assert direct_blend["past_season_labels_used"] is True
    assert direct_blend["target_slate_labels_used"] is False
    grade = subject.grade_fixed_budget_admissions_v1(
        slate_freeze=freeze_2024,
        admissions=[direct_2024, reference_2024, quota_2024],
        blends=[direct_blend, quota_blend],
        realized_scores_micro=_realized_scores(freeze_2024),
        outcome_identity=_identity(
            "gs://example/outcomes/2024-w01", 209, "e"
        ),
    )
    assert len(grade["admission_grades"]) == 3
    assert len(grade["fixed_total_budget_blend_grades"]) == 2

    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="past-season slates only",
    ):
        subject.fit_past_season_direct_ranker_v1(
            training=[*entries[:-1], (
                freeze_2024,
                _realized_scores(freeze_2024),
                _identity("gs://example/outcomes/2024-w01", 9, "c"),
            )],
            target_season=2024,
            expected_training_slate_ids=expected_slates,
        )
    with pytest.raises(
        subject.CorpusR6BroadAdmissionTournamentV1Error,
        match="target season differs",
    ):
        subject.fit_past_season_direct_ranker_v1(
            training=entries,
            target_season=2024,
            expected_training_slate_ids=["2023-w01"],
        )


def test_fixed_total_budget_blend_and_retention_grade_use_one_frozen_corpus():
    freeze = _freeze(season=2023, week=1)
    reference = subject.build_reference_admission_v1(freeze, budget=250)
    quota = subject.build_quota_admission_v1(freeze, budget=250)
    blend = subject.build_fixed_budget_reference_challenger_blend_v1(
        slate_freeze=freeze,
        reference_admission=reference,
        challenger_admission=quota,
    )
    assert len(blend["selected_lineup_ids"]) == 250
    assert blend["total_admission_budget_held_fixed"] is True
    assert blend == subject.build_fixed_budget_reference_challenger_blend_v1(
        slate_freeze=freeze,
        reference_admission=reference,
        challenger_admission=quota,
    )
    novel = sorted(
        set(blend["selected_lineup_ids"])
        - set(reference["selected_lineup_ids"])
    )
    assert novel
    all_ids = [row["lineup_id"] for row in freeze["candidate_features"]]
    scores = {
        lineup_id: 150_000_000 + ordinal
        for ordinal, lineup_id in enumerate(all_ids)
    }
    scores[novel[0]] = 241_000_000
    grade = subject.grade_fixed_budget_admissions_v1(
        slate_freeze=freeze,
        admissions=[quota, reference],
        blends=[blend],
        realized_scores_micro=scores,
        outcome_identity=_identity(
            "gs://example/catalog-outcomes/2023-w01", 11, "d"
        ),
    )
    assert grade["fixed_corpus_hindsight_max_is_diagnostic_only"] is True
    assert grade["hindsight_union_gap_is_not_a_recovery_target"] is True
    assert grade["fixed_corpus_realized_max_lineup_id"] == novel[0]
    by_arm = {
        row["admission_id"]: row for row in grade["admission_grades"]
    }
    assert by_arm[subject.REFERENCE_ADMISSION_ID][
        "fixed_corpus_max_retained"
    ] is False
    assert by_arm[subject.QUOTA_ADMISSION_ID][
        "fixed_corpus_max_retained"
    ] is True
    assert grade["fixed_total_budget_blend_grades"][0][
        "incremental_realized_max_vs_reference_micro"
    ] > 0
    assert grade["k80_selection_is_secondary_and_not_performed"] is True


def test_realized_score_ties_receive_the_same_training_target():
    scores = {"A": 100, "B": 100, "C": 200}
    percentiles = subject._rank_percentiles(scores, lineup_ids=["A", "B", "C"])
    assert percentiles["A"] == percentiles["B"] == 0.25
    assert percentiles["C"] == 1.0
