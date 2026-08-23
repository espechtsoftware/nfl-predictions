from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_a7_corpus_rank_fusions",
    ROOT / "scripts/analyze_a7_corpus_rank_fusions.py",
)
assert SPEC is not None and SPEC.loader is not None
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def _identity(index: int) -> list[str]:
    return sorted(f"player-{index:03d}-{slot}" for slot in range(9))


def _threshold_counts(values: list[int]) -> dict[str, int]:
    return {
        str(threshold): sum(
            value >= threshold * analysis.MICRO_DK_SCALE for value in values
        )
        for threshold in analysis.THRESHOLDS
    }


def _synthetic_report() -> dict:
    rows = []
    control_maxima: list[int] = []
    treatment_maxima: list[int] = []
    control = list(range(80))
    treatment = [*range(70), *range(80, 90)]
    identities = [_identity(index) for index in range(100)]
    for slate_index, (season, week) in enumerate(analysis.EXPECTED_SLATES):
        scores = [150.0 + (index % 7) for index in range(100)]
        scores[0] = 190.0
        if slate_index < 5:
            scores[79] = 195.0
            scores[80] = 205.0 + slate_index
        else:
            scores[79] = 180.0
            scores[80] = 181.0
        control_scores = [scores[index] for index in control]
        treatment_scores = [scores[index] for index in treatment]
        control_maxima.append(analysis._score_to_micro(max(control_scores)))
        treatment_maxima.append(analysis._score_to_micro(max(treatment_scores)))
        rows.append({
            "season": season,
            "week": week,
            "candidate_identities": identities,
            "candidate_actual_scores": scores,
            "control": {
                "indices": control,
                "identities": [identities[index] for index in control],
                "scorefree": {"selection_order": control},
                "realized": {
                    "identities": [identities[index] for index in control],
                    "scores": control_scores,
                    "prefix_maxima": {
                        "4": max(control_scores[:4]),
                        "14": max(control_scores[:14]),
                        "80": max(control_scores),
                    },
                },
            },
            "treatment": {
                "indices": treatment,
                "identities": [identities[index] for index in treatment],
                "scorefree": {"selection_order": treatment},
                "realized": {
                    "identities": [identities[index] for index in treatment],
                    "scores": treatment_scores,
                    "prefix_maxima": {
                        "4": max(treatment_scores[:4]),
                        "14": max(treatment_scores[:14]),
                        "80": max(treatment_scores),
                    },
                },
            },
        })
    return {
        "run_id": analysis.SOURCE_RUN_ID,
        "uses_realized_outcomes": True,
        "actual_score_query_executed": True,
        "slates": rows,
        "outcome": {"cuts": {"80": {
            "control_mean": sum(control_maxima) / (
                len(control_maxima) * analysis.MICRO_DK_SCALE
            ),
            "treatment_mean": sum(treatment_maxima) / (
                len(treatment_maxima) * analysis.MICRO_DK_SCALE
            ),
            "control_threshold_counts": _threshold_counts(control_maxima),
            "treatment_threshold_counts": _threshold_counts(treatment_maxima),
        }}},
    }


class _ScorePoisonRow(dict):
    def get(self, key, default=None):
        if key == "candidate_actual_scores":
            raise AssertionError("selection phase accessed candidate scores")
        return super().get(key, default)


def test_selection_phase_never_dereferences_score_field():
    report = _synthetic_report()
    report["slates"] = [_ScorePoisonRow(row) for row in report["slates"]]
    manifest = analysis._selection_manifest(
        report, implementation_sha256="1" * 64
    )
    assert manifest["score_field_semantically_accessed"] is False
    assert len(manifest["slates"]) == 54


def test_frozen_directional_and_rank_blend_books_are_exact_and_nonvacuous():
    control = tuple(range(80))
    treatment = (*range(70), *range(80, 90))
    variants = analysis._variant_sets(control, treatment)
    assert tuple(variants) == analysis.VARIANT_ORDER
    assert variants["DS25"] == tuple(sorted({*range(77), 80, 81, 82}))
    assert variants["DS50"] == tuple(sorted({*range(75), *range(80, 85)}))
    assert variants["DS75"] == tuple(sorted({*range(72), *range(80, 88)}))
    assert variants["A7-100"] == tuple(sorted(treatment))
    assert all(len(book) == len(set(book)) == 80 for book in variants.values())
    assert all(set(book) != set(control) for book in variants.values())
    assert [80 - len(set(variants[name]) & set(control)) for name in (
        "RB25", "RB50", "RB75",
    )] == sorted(80 - len(set(variants[name]) & set(control)) for name in (
        "RB25", "RB50", "RB75",
    ))


def test_variant_input_poisons_fail_closed():
    control = tuple(range(80))
    with pytest.raises(analysis.VariationError, match="empty or asymmetric"):
        analysis._variant_sets(control, control)
    report = _synthetic_report()
    report["slates"][0]["control"]["indices"][0] = True
    report["slates"][0]["control"]["scorefree"]["selection_order"][0] = True
    with pytest.raises(analysis.VariationError, match="exact in-range"):
        analysis._selection_manifest(report, implementation_sha256="1" * 64)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (178.53999999999996, 178_540_000),
        (205, 205_000_000),
        (0.04, 40_000),
    ],
)
def test_score_conversion_is_exact_cent_to_micro(value, expected):
    assert analysis._score_to_micro(value) == expected


@pytest.mark.parametrize("value", [True, None, "178.54", float("nan"), 1.001])
def test_score_conversion_rejects_wrong_type_nonfinite_and_subcent(value):
    with pytest.raises(analysis.VariationError):
        analysis._score_to_micro(value)


def test_all_variants_are_scored_holm_adjusted_and_never_license_adoption():
    report = _synthetic_report()
    manifest = analysis._selection_manifest(
        report, implementation_sha256=analysis._implementation_sha256()
    )
    result = analysis._score_result(report, manifest)
    assert result["variant_order"] == list(analysis.VARIANT_ORDER)
    assert [row["variant"] for row in result["variants"]] == list(
        analysis.VARIANT_ORDER
    )
    assert all(0.0 <= row["holm_adjusted_p_joint"] <= 1.0 for row in result[
        "variants"
    ])
    raw_order = sorted(
        result["variants"], key=lambda row: (
            row["p_joint"], analysis.VARIANT_ORDER.index(row["variant"])
        )
    )
    assert [row["holm_adjusted_p_joint"] for row in raw_order] == sorted(
        row["holm_adjusted_p_joint"] for row in raw_order
    )
    assert result["retrospective_post_outcome_exploratory"] is True
    for key in (
        "new_outcome_query_executed",
        "historical_adoption_licensed",
        "production_change_licensed",
        "deployment_licensed",
        "prospective_shadow_licensed",
        "followup_corpus_variation_licensed",
    ):
        assert result[key] is False
    assert set(result["eligible_variants"]) <= set(analysis.VARIANT_ORDER)
    assert result["future_prospective_nominee"] in (
        *analysis.VARIANT_ORDER, None,
    )


def test_score_reconstruction_and_manifest_drift_fail_closed():
    report = _synthetic_report()
    manifest = analysis._selection_manifest(
        report, implementation_sha256=analysis._implementation_sha256()
    )
    drifted_report = deepcopy(report)
    drifted_report["slates"][0]["control"]["realized"]["scores"][0] += 1
    with pytest.raises(analysis.VariationError, match="ordered realization"):
        analysis._score_result(drifted_report, manifest)
    drifted_manifest = deepcopy(manifest)
    drifted_manifest["slates"][0]["variants"]["DS25"]["indices"][0] = 999
    with pytest.raises((analysis.VariationError, IndexError)):
        analysis._score_result(report, drifted_manifest)


def test_holm_uses_step_down_running_maximum():
    rows = [{"p_joint": value} for value in (0.01, 0.04, 0.03, 0.2)]
    analysis._holm(rows)
    assert [row["holm_adjusted_p_joint"] for row in rows] == pytest.approx(
        [0.04, 0.09, 0.09, 0.2]
    )


def test_create_once_pair_reopens_identical_and_rejects_collision(tmp_path):
    value = {"a": 1, "b": False}
    analysis._write_pair(tmp_path, "body.json", "body.sha256", value)
    analysis._write_pair(tmp_path, "body.json", "body.sha256", value)
    (tmp_path / "body.json").write_text('{"a":2}\n', encoding="utf-8")
    with pytest.raises(analysis.VariationError, match="collision"):
        analysis._write_pair(tmp_path, "body.json", "body.sha256", value)


def test_selection_commit_requires_exact_tracked_pushed_bytes(tmp_path, monkeypatch):
    manifest = tmp_path / "selection-manifest.json"
    manifest.write_bytes(analysis._canonical({"x": 1}))
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    calls = []

    def fake_git(args):
        calls.append(args)
        if args[0] == "show":
            return manifest.read_bytes()
        return b""

    monkeypatch.setattr(analysis, "_git", fake_git)
    analysis._validate_selection_commit(
        manifest, "a" * 40, analysis._sha(manifest)
    )
    assert calls == [
        ["show", f"{'a' * 40}:selection-manifest.json"],
        ["merge-base", "--is-ancestor", "a" * 40, "origin/main"],
    ]
    with pytest.raises(analysis.VariationError, match="external hash"):
        analysis._validate_selection_commit(manifest, "a" * 40, "0" * 64)
