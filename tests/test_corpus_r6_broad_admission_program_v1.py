from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_broad_admission_program_v1 as subject


def _real_candidates(count: int = 520) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    source_count = len(subject.core.SOURCE_ORDER)
    for index in range(count):
        primary = (index // 80) % source_count
        source_ordinals = {primary}
        if index % 11 == 0:
            source_ordinals.add((primary + 1) % source_count)
        sources = [
            source for ordinal, source in enumerate(subject.core.SOURCE_ORDER)
            if ordinal in source_ordinals
        ]
        rows.append({
            "lineup_id": f"L{index:04d}",
            "roster_player_ids": [f"P{index:04d}-{slot}" for slot in range(9)],
            "source_population_ids": sources,
            "source_population_count": len(sources),
            "source_lineup_ids_by_population": {
                source: f"{source}-L{index:04d}" for source in sources
            },
            "source_occurrence_counts_by_population": {
                source: 1 + index % 3 for source in sources
            },
            "source_detail_ids_by_population": {
                source: sorted({
                    f"family-{subject.core.SOURCE_ORDER.index(source)}",
                    f"law-{index % 37:02d}",
                })
                for source in sources
            },
        })
    return rows


def _real_freeze() -> dict[str, object]:
    count = 520
    base = 100.0 + np.arange(count, dtype=np.float64) * 0.25
    offsets = np.linspace(-3.0, 3.0, 12, dtype=np.float64)
    matrix = np.ascontiguousarray(base[:, None] + offsets[None, :])
    return subject.core.freeze_slate_inputs_v1(
        slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
        candidates=_real_candidates(count),
        modeled_score_matrix=matrix,
        source_binding={"artifact": "real-package-fixture", "source_ordinal": 0},
    )


def test_real_score_free_package_replays_both_fixed_budgets():
    freeze = _real_freeze()
    package = subject.build_score_free_slate_package_v1(
        freeze, source_ordinal=0
    )
    assert package == subject.build_score_free_slate_package_v1(
        freeze, source_ordinal=0
    )
    assert subject.validate_score_free_slate_package_v1(package) == package
    assert package["uses_realized_outcomes"] is False
    assert package["direct_admission_included"] is False
    assert package["automatic_policy_promotion"] is False
    assert [
        row["admission_budget"] for row in package["budget_packages"]
    ] == [250, 500]
    for row in package["budget_packages"]:
        budget = row["admission_budget"]
        assert len(row["reference_admission"]["selected_lineup_ids"]) == budget
        assert len(row["quota_admission"]["selected_lineup_ids"]) == budget
        assert len(row["quota_blend"]["selected_lineup_ids"]) == budget
        assert row["total_admission_budget_held_fixed"] is True

    tampered = deepcopy(package)
    tampered["budget_packages"][0]["uses_realized_outcomes"] = True
    tampered["budget_packages"][0]["budget_package_sha256"] = subject._hash({
        key: value for key, value in tampered["budget_packages"][0].items()
        if key != "budget_package_sha256"
    })
    tampered["budget_packages_sha256"] = subject._hash(
        tampered["budget_packages"]
    )
    tampered["package_sha256"] = subject._hash({
        key: value for key, value in tampered.items()
        if key != "package_sha256"
    })
    with pytest.raises(
        subject.CorpusR6BroadAdmissionProgramV1Error,
        match="outcome authority",
    ):
        subject.validate_score_free_slate_package_v1(tampered)

    with pytest.raises(
        subject.CorpusR6BroadAdmissionProgramV1Error,
        match="slate/ordinal binding differs",
    ):
        subject.build_score_free_slate_package_v1(freeze, source_ordinal=1)


def _stub_package(source_ordinal: int) -> dict[str, object]:
    slate_id = subject.EXPECTED_SLATE_IDS[source_ordinal]
    season, week = slate_id.split("-w")
    slate = {"season": int(season), "week": int(week), "slate_id": slate_id}
    budget_packages = []
    for budget in subject.core.ADMISSION_BUDGETS:
        budget_packages.append({
            "admission_budget": budget,
            "reference_admission": {
                "admission_id": subject.core.REFERENCE_ADMISSION_ID,
                "admission_budget": budget,
            },
            "quota_admission": {
                "admission_id": subject.core.QUOTA_ADMISSION_ID,
                "admission_budget": budget,
            },
            "quota_blend": {
                "challenger_admission_id": subject.core.QUOTA_ADMISSION_ID,
                "admission_budget": budget,
            },
        })
    return {
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "slate": slate,
        "slate_freeze": {
            "slate": slate,
            "candidate_features": [
                {"lineup_id": f"{slate_id}-A"},
                {"lineup_id": f"{slate_id}-B"},
            ],
        },
        "slate_freeze_sha256": format(source_ordinal + 1, "064x"),
        "package_sha256": format(source_ordinal + 101, "064x"),
        "budget_packages": budget_packages,
    }


def _threshold_rows(retained: int) -> list[dict[str, object]]:
    return [{
        "threshold": threshold,
        "fixed_corpus_candidate_count": 2,
        "retained_candidate_count": retained,
        "retained_fraction_ppm": retained * 500_000,
        "fixed_corpus_has_opportunity": True,
        "slate_opportunity_retained": retained > 0,
    } for threshold in subject.core.THRESHOLDS]


def test_exact_54_slate_program_is_walk_forward_and_descriptive(monkeypatch):
    packages = [_stub_package(index) for index in range(54)]
    realized = {
        package["slate_id"]: {
            f"{package['slate_id']}-A": 190_000_000,
            f"{package['slate_id']}-B": 210_000_000,
        }
        for package in packages
    }
    fit_calls: list[tuple[int, int, list[str]]] = []
    grade_calls: list[tuple[str, int, tuple[str, ...]]] = []

    monkeypatch.setattr(
        subject,
        "validate_score_free_slate_package_v1",
        lambda value: value,
    )

    def fake_fit(*, training, target_season, expected_training_slate_ids):
        fit_calls.append((
            target_season, len(training), list(expected_training_slate_ids)
        ))
        return {
            "target_season": target_season,
            "ranker_sha256": format(target_season, "064x"),
        }

    def fake_direct(slate_freeze, *, ranker, budget):
        assert slate_freeze["slate"]["season"] == ranker["target_season"]
        return {
            "admission_id": subject.core.DIRECT_ADMISSION_ID,
            "admission_budget": budget,
        }

    def fake_blend(*, slate_freeze, reference_admission, challenger_admission):
        del slate_freeze, reference_admission
        return {
            "challenger_admission_id": challenger_admission["admission_id"],
            "admission_budget": challenger_admission["admission_budget"],
        }

    arm_lift = {
        subject.core.REFERENCE_ADMISSION_ID: 0,
        subject.core.QUOTA_ADMISSION_ID: 1_000_000,
        subject.core.DIRECT_ADMISSION_ID: 3_000_000,
    }

    def fake_grade(
        *, slate_freeze, admissions, blends, realized_scores_micro,
        outcome_identity,
    ):
        del realized_scores_micro, outcome_identity
        slate_id = slate_freeze["slate"]["slate_id"]
        budget = admissions[0]["admission_budget"]
        admission_ids = tuple(item["admission_id"] for item in admissions)
        grade_calls.append((slate_id, budget, admission_ids))
        reference_max = 180_000_000 + budget
        admission_rows = [{
            "admission_id": admission_id,
            "realized_max_micro": reference_max + arm_lift[admission_id],
            "fixed_corpus_max_retained": (
                admission_id == subject.core.DIRECT_ADMISSION_ID
            ),
            "fixed_corpus_max_gap_micro": (
                0 if admission_id == subject.core.DIRECT_ADMISSION_ID
                else 3_000_000 - arm_lift[admission_id]
            ),
            "threshold_retention": _threshold_rows(
                2 if admission_id == subject.core.DIRECT_ADMISSION_ID else 1
            ),
        } for admission_id in admission_ids]
        blend_rows = []
        for blend in blends:
            challenger = blend["challenger_admission_id"]
            lift = (
                4_000_000
                if challenger == subject.core.DIRECT_ADMISSION_ID
                else 2_000_000
            )
            blend_rows.append({
                "challenger_admission_id": challenger,
                "realized_max_micro": reference_max + lift,
                "fixed_corpus_max_retained": (
                    challenger == subject.core.DIRECT_ADMISSION_ID
                ),
                "fixed_corpus_max_gap_micro": (
                    0 if challenger == subject.core.DIRECT_ADMISSION_ID
                    else 1_000_000
                ),
                "threshold_retention": _threshold_rows(
                    2 if challenger == subject.core.DIRECT_ADMISSION_ID else 1
                ),
            })
        return {
            "grade_sha256": subject._hash({
                "slate_id": slate_id, "budget": budget,
            }),
            "admission_grades": admission_rows,
            "fixed_total_budget_blend_grades": blend_rows,
        }

    monkeypatch.setattr(
        subject.core, "fit_past_season_direct_ranker_v1", fake_fit
    )
    monkeypatch.setattr(
        subject.core, "build_direct_ranker_admission_v1", fake_direct
    )
    monkeypatch.setattr(
        subject.core,
        "build_fixed_budget_reference_challenger_blend_v1",
        fake_blend,
    )
    monkeypatch.setattr(
        subject.core, "grade_fixed_budget_admissions_v1", fake_grade
    )
    identity = {
        "uri": "gs://example/exact-historical-outcomes.json",
        "generation": "123",
        "sha256": "a" * 64,
        "bytes": 42,
    }
    result = subject.grade_historical_program_v1(
        packages=packages,
        realized_scores_by_slate=realized,
        outcome_identity=identity,
    )
    replay = subject.grade_historical_program_v1(
        packages=packages,
        realized_scores_by_slate=realized,
        outcome_identity=identity,
    )
    assert result == replay
    assert fit_calls[:2] == [
        (2024, 18, list(subject.EXPECTED_SLATE_IDS[:18])),
        (2025, 36, list(subject.EXPECTED_SLATE_IDS[:36])),
    ]
    assert len(result["slate_budget_grades"]) == 108
    assert len(result["per_slate_arm_deltas"]) == 468
    assert result["descriptive_only"] is True
    assert result["automatic_policy_promotion"] is False
    assert result["hindsight_union_gap_is_not_a_recovery_target"] is True
    assert all(
        subject.core.DIRECT_ADMISSION_ID not in admission_ids
        for slate_id, _budget, admission_ids in grade_calls[:36]
        if slate_id.startswith("2023-")
    )
    summaries = {
        (row["admission_budget"], row["arm_key"]): row
        for row in result["arm_summaries"]
    }
    assert summaries[(250, "admission::past-season-direct-ridge")][
        "paired_slate_count"
    ] == 36
    assert summaries[(250, "admission::past-season-direct-ridge")][
        "paired_max_lift_sum_micro"
    ] == 36 * 3_000_000
    assert summaries[(500, "blend::source-quota-disagreement")][
        "paired_slate_count"
    ] == 54
    assert summaries[(500, "blend::source-quota-disagreement")][
        "threshold_retention"
    ][0]["retained_candidate_count"] == 54


def test_lattice_gate_precedes_outcome_identity_and_realized_maps(monkeypatch):
    packages = [_stub_package(index) for index in range(53)]
    monkeypatch.setattr(
        subject,
        "validate_score_free_slate_package_v1",
        lambda value: value,
    )
    with pytest.raises(
        subject.CorpusR6BroadAdmissionProgramV1Error,
        match="exact 54-slate lattice",
    ):
        subject.grade_historical_program_v1(
            packages=packages,
            realized_scores_by_slate=None,
            outcome_identity=None,
        )


def test_expected_lattice_is_exact_and_ordinal():
    assert len(subject.EXPECTED_SLATE_IDS) == 54
    assert subject.EXPECTED_SLATE_IDS[:2] == ("2023-w01", "2023-w02")
    assert subject.EXPECTED_SLATE_IDS[17:19] == ("2023-w18", "2024-w01")
    assert subject.EXPECTED_SLATE_IDS[-1] == "2025-w18"
