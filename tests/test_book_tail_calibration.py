from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

import nfl_dfs.research.book_tail_calibration as audit_module

from nfl_dfs.research.book_tail_calibration import (
    AUDIT_PROTOCOL_ID,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    analyze_source_bytes,
    canonical_json_bytes,
    load_source_json,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_book_tail_calibration",
    ROOT / "scripts/analyze_book_tail_calibration.py",
)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)
TEST_BOOTSTRAP_RESAMPLES = 200


@pytest.fixture(autouse=True)
def _bounded_synthetic_bootstrap(monkeypatch):
    assert BOOTSTRAP_RESAMPLES == 10_000
    monkeypatch.setattr(
        audit_module, "BOOTSTRAP_RESAMPLES", TEST_BOOTSTRAP_RESAMPLES,
    )


def _source() -> dict:
    def book(
        selected_best: float,
        coverage: dict[str, float],
        *,
        world_count: int,
        counts: dict[str, int],
        **extra,
    ) -> dict:
        return {
            "candidate_count": 250,
            "world_count": world_count,
            "selected_best": selected_best,
            "oracle_best": selected_best + 7.0,
            "selected_from_seed": counts,
            "simulated_coverage": coverage,
            "simulated_weekly_best_quantile": {
                "0.95": selected_best - 4.0,
                "0.99": selected_best + 5.0,
            },
            **extra,
        }

    slates = []
    for season_offset, season in enumerate((2023, 2024, 2025)):
        for week in range(1, 19):
            ordinal = season_offset * 18 + week
            # Values deliberately vary within every season and put both
            # classes in every calibration threshold's pooled population.
            selected_best = 176.0 + 1.25 * ordinal + ((week % 4) - 1.5) * 3.0
            coverage = {}
            for threshold in (187, 194, 200, 210, 220, 230, 240):
                coverage[str(threshold)] = min(
                    0.99,
                    max(0.01, 0.5 + (selected_best - threshold) / 80.0),
                )
            seed_counts = {
                "R0": 16, "R1": 16, "R2": 16, "R3": 16, "R4": 16,
            }
            base_counts = {
                "R0": 80, "R1": 0, "R2": 0, "R3": 0, "R4": 0,
            }
            arms = {
                arm: book(
                    selected_best,
                    coverage,
                    world_count=50_000 if "WU" in arm else 10_000,
                    counts=base_counts if arm.startswith("C0") else seed_counts,
                    selected_overlap_c0w0=80,
                    selected_delta_c0w0=0.0,
                )
                for arm in ("C0W0", "C0WU", "CUW0", "CUWU")
            }
            slates.append({
                "season": season,
                "week": week,
                "novel_candidates_by_seed": {
                    "R0": 250, "R1": 10, "R2": 9, "R3": 8, "R4": 7,
                },
                "standalone_seed_books": {
                    seed: book(
                        selected_best,
                        coverage,
                        world_count=10_000,
                        counts={key: 80 if key == seed else 0 for key in seed_counts},
                    )
                    for seed in seed_counts
                },
                "fixed_budget_confirmation": {
                    "CBW0": book(
                        selected_best, coverage, world_count=10_000,
                        counts=seed_counts, selected_overlap_c0w0=70,
                    ),
                    "CBWU": book(
                        selected_best, coverage, world_count=50_000,
                        counts=seed_counts, selected_overlap_c0wu=70,
                    ),
                },
                "arms": arms,
            })
    return {
        "protocol": "2026-08-13-multiseed-candidate-world-factorial",
        "source_arm": "treatment",
        "expected_code_sha": "4d6f5cf",
        "mechanical_passes": True,
        "failures": [],
        "result": {
            "metrics": {},
            "selected_arm": "CUWU",
            "ranked_arms": ["CUWU", "C0WU", "CUW0", "C0W0"],
            "production_selected_arm": "C0WU",
            "production_ranked_arms": ["C0WU", "C0W0"],
            "candidate_union_confirmation_required": True,
            "fixed_budget_confirmation": {},
            "final_production_arm": "CBWU",
            "factorial_contrasts": {},
            "weekly_deltas_at_least_10": [],
            "standalone_seed_noise_floor": {},
            "by_season": {},
            "slate_clustered_bootstrap_diagnostic": {},
            "slates": slates,
        },
    }


def _raw(source: dict | None = None) -> bytes:
    return json.dumps(
        _source() if source is None else source,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _analyze(source: dict | None = None) -> dict:
    raw = _raw(source)
    return audit_module._analyze_source_bytes_for_test(
        raw, expected_source_sha256=hashlib.sha256(raw).hexdigest(),
    )


def test_frozen_audit_metrics_design_flags_and_determinism():
    first = _analyze()
    second = _analyze()

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["audit_protocol_id"] == AUDIT_PROTOCOL_ID
    assert first["population"] == {
        "slates": 54,
        "seasons": [2023, 2024, 2025],
        "slates_by_season": {"2023": 18, "2024": 18, "2025": 18},
        "entries_per_selected_book": 80,
        "simulated_worlds_per_selected_book": 50_000,
        "exact80_count_attestation": "transitive_pinned_source",
        "selected_roster_identity_revalidated": False,
    }
    assert BOOTSTRAP_RESAMPLES == 10_000
    assert first["bootstrap_design"]["resamples"] == TEST_BOOTSTRAP_RESAMPLES
    assert first["bootstrap_design"]["seed"] == BOOTSTRAP_SEED
    assert first["bootstrap_design"][
        "within_season_stratified_slate_resampling"
    ] is True

    calibrated = first["thresholds"]["194"]
    assert calibrated["status"] == "calibration"
    assert calibrated["all"]["slates"] == 54
    assert calibrated["all"]["brier_score"] >= 0.0
    assert calibrated["all"]["loso_prevalence_baseline_brier_score"] >= 0.0
    assert calibrated["all"]["roc_auc"] is not None
    assert calibrated["all"]["average_precision"] is not None
    assert calibrated["all"]["bootstrap_roc_auc"]["finite_resamples"] \
        + calibrated["all"]["bootstrap_roc_auc"]["undefined_resamples"] == 200
    assert calibrated["all"]["bootstrap_average_precision"][
        "finite_resamples"
    ] + calibrated["all"]["bootstrap_average_precision"][
        "undefined_resamples"
    ] == 200
    assert calibrated["bootstrap_brier_skill"]["finite_resamples"] == 200
    assert set(calibrated["by_season"]) == {"2023", "2024", "2025"}
    assert calibrated["by_season"]["2023"]["bootstrap_brier_skill"][
        "finite_resamples"
    ] == 200
    assert calibrated["by_season"]["2023"]["bootstrap_roc_auc"][
        "finite_resamples"
    ] + calibrated["by_season"]["2023"]["bootstrap_roc_auc"][
        "undefined_resamples"
    ] == 200

    sparse = first["thresholds"]["230"]
    assert sparse["status"] == "descriptive_only_sparse_tail"
    assert "brier_score" not in sparse["all"]
    assert "bootstrap_brier_skill" not in sparse
    association = first["selected_book_maximum_association"]
    assert association["all"]["q95"]["pearson"] > 0.9
    assert association["all"]["q99"]["spearman"] > 0.9
    assert association["all"]["q95"]["bootstrap"]["pearson"][
        "finite_resamples"
    ] == 200
    assert set(association["by_season"]) == {"2023", "2024", "2025"}
    assert association["by_season"]["2024"]["q99"]["bootstrap"][
        "spearman"
    ]["finite_resamples"] == 200

    assert first["interpretation_flags"] == {
        "retrospective_diagnostic_only": True,
        "absolute_calibration_estimand": True,
        "arm_transport_estimand": False,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_licensed": False,
        "promotion_licensed": False,
        "production_change_licensed": False,
        "permanent_closure_licensed": False,
        "uses_realized_outcomes": True,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda source: source.update(protocol="wrong"), "protocol identity"),
        (lambda source: source.update(source_arm="control"), "source arm"),
        (lambda source: source.update(expected_code_sha="deadbee"), "code SHA"),
        (lambda source: source.update(mechanical_passes=False), "mechanically pass"),
        (
            lambda source: source["result"].update(final_production_arm="C0WU"),
            "final production arm",
        ),
        (lambda source: source["result"]["slates"].pop(), "exactly 54"),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"].update(world_count=10_000),
            "exactly 50000 worlds",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"]["selected_from_seed"].update(R0=15),
            "exact seed counts",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"]["simulated_coverage"].update({"194": 1.01}),
            "probability",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"]["simulated_coverage"].update({"194": 0.0}),
            "tail-monotone",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"]["simulated_weekly_best_quantile"].update({"0.95": 999}),
            "not monotone",
        ),
    ],
)
def test_fail_closed_identity_schema_count_and_probability(mutation, message):
    source = _source()
    mutation(source)
    with pytest.raises(ValueError, match=message):
        _analyze(source)


def test_hash_lock_duplicate_keys_and_nonfinite_json_fail_closed():
    raw = _raw()
    with pytest.raises(ValueError, match="SHA-256 differs"):
        analyze_source_bytes(raw)
    with pytest.raises(TypeError):
        analyze_source_bytes(raw, expected_source_sha256="0" * 64)
    assert "_analyze_source_bytes_for_test" not in audit_module.__all__
    with pytest.raises(ValueError, match="duplicate key"):
        load_source_json(b'{"x":1,"x":2}')
    with pytest.raises(ValueError, match="non-finite"):
        load_source_json(b'{"x":NaN}')


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda source: source["result"]["slates"][0].update(week=99),
            "season/week identity",
        ),
        (lambda source: source.update(extra=True), "root schema differs"),
        (
            lambda source: source["result"].update(extra=True),
            "result schema differs",
        ),
        (
            lambda source: source["result"]["slates"][0].update(extra=True),
            "slate 0 schema differs",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"].update(extra=True),
            "confirmation CBWU schema differs",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"].update(candidate_count=251),
            "CBWU candidate count differs from arms.C0W0",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"].update(selected_rosters=[]),
            "unexpectedly contains selected_rosters",
        ),
        (
            lambda source: source["result"]["slates"][0][
                "fixed_budget_confirmation"
            ]["CBWU"].update(selected_rosters="malformed"),
            "unexpectedly contains selected_rosters",
        ),
    ],
)
def test_generator_schema_and_compact_roster_poison(mutation, message):
    source = _source()
    mutation(source)
    with pytest.raises(ValueError, match=message):
        _analyze(source)


def test_exact_threshold_metrics_and_bootstrap_uncertainty():
    source = _source()
    result = _analyze(source)
    ordered = sorted(
        source["result"]["slates"],
        key=lambda slate: (slate["season"], slate["week"]),
    )
    selected_best = np.asarray([
        slate["fixed_budget_confirmation"]["CBWU"]["selected_best"]
        for slate in ordered
    ])
    labels = (selected_best >= 194).astype(float)
    probabilities = np.asarray([
        slate["fixed_budget_confirmation"]["CBWU"]["simulated_coverage"]["194"]
        for slate in ordered
    ])
    metric = result["thresholds"]["194"]["all"]
    assert metric["brier_score"] == float(
        np.mean(np.square(probabilities - labels))
    )
    assert metric["roc_auc"] == float(roc_auc_score(labels, probabilities))
    assert metric["average_precision"] == float(
        average_precision_score(labels, probabilities)
    )

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    blocks = []
    seasons = np.asarray([slate["season"] for slate in ordered])
    for season in (2023, 2024, 2025):
        indices = np.flatnonzero(seasons == season)
        blocks.append(rng.choice(
            indices, size=(TEST_BOOTSTRAP_RESAMPLES, 18), replace=True,
        ))
    samples = np.concatenate(blocks, axis=1)

    def expected(chosen_rows: np.ndarray) -> tuple[list[float], list[float], int]:
        auc_values = []
        ap_values = []
        undefined = 0
        for chosen in chosen_rows:
            y = labels[chosen]
            if np.unique(y).size != 2:
                undefined += 1
                continue
            q = probabilities[chosen]
            auc_values.append(float(roc_auc_score(y, q)))
            ap_values.append(float(average_precision_score(y, q)))
        return auc_values, ap_values, undefined

    auc_values, ap_values, undefined = expected(samples)
    expected_auc_ci = [
        float(np.quantile(auc_values, 0.025, method="linear")),
        float(np.quantile(auc_values, 0.975, method="linear")),
    ]
    expected_ap_ci = [
        float(np.quantile(ap_values, 0.025, method="linear")),
        float(np.quantile(ap_values, 0.975, method="linear")),
    ]
    assert metric["bootstrap_roc_auc"] == {
        "ci95": expected_auc_ci,
        "finite_resamples": len(auc_values),
        "undefined_resamples": undefined,
    }
    assert metric["bootstrap_average_precision"] == {
        "ci95": expected_ap_ci,
        "finite_resamples": len(ap_values),
        "undefined_resamples": undefined,
    }

    season_metric = result["thresholds"]["194"]["by_season"]["2023"]
    auc_values, ap_values, undefined = expected(blocks[0])
    assert season_metric["bootstrap_roc_auc"] == {
        "ci95": [
            float(np.quantile(auc_values, 0.025, method="linear")),
            float(np.quantile(auc_values, 0.975, method="linear")),
        ],
        "finite_resamples": len(auc_values),
        "undefined_resamples": undefined,
    }
    assert season_metric["bootstrap_average_precision"] == {
        "ci95": [
            float(np.quantile(ap_values, 0.025, method="linear")),
            float(np.quantile(ap_values, 0.975, method="linear")),
        ],
        "finite_resamples": len(ap_values),
        "undefined_resamples": undefined,
    }


def test_undefined_classification_metrics_are_literal_null():
    source = _source()
    for slate in source["result"]["slates"]:
        slate["fixed_budget_confirmation"]["CBWU"]["selected_best"] = 150.0
    result = _analyze(source)
    metric = result["thresholds"]["187"]["all"]
    assert metric["both_classes_present"] is False
    assert metric["roc_auc"] is None
    assert metric["average_precision"] is None


def test_cli_requires_explicit_paths_and_exclusive_create(monkeypatch, tmp_path):
    input_path = tmp_path / "source.json"
    output_path = tmp_path / "result.json"
    input_path.write_bytes(_raw())
    expected = {"ok": True}
    monkeypatch.setattr(cli, "analyze_source_path", lambda path: expected)

    assert cli.main([
        "--input", str(input_path), "--output", str(output_path),
    ]) == 0
    assert output_path.read_bytes() == canonical_json_bytes(expected)
    with pytest.raises(FileExistsError):
        cli.main(["--input", str(input_path), "--output", str(output_path)])
    with pytest.raises(SystemExit):
        cli.main([])
