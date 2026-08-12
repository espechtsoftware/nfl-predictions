#!/usr/bin/env python3
"""Mechanism-audited PIT-clean K3/K1 and direct-role comparisons."""

from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.panel_compare import metrics, slate_scores  # noqa: E402


THRESHOLDS = (240, 230, 220, 210, 200, 194, 187)
CACHE_TABLE = "tabpfn_projections_pit_v2"
PREFIX = "PIT_TIER1_JSON="
_DIR = Path(__file__).resolve().parent


def _load(name: str, filename: str):
    spec = spec_from_file_location(name, _DIR / filename)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adoption = _load("_pit_adoption", "compare_adoption_panel.py")
direct = _load("_pit_direct_role", "compare_corrected_k1_direct_role.py")


def lexicographic_decision(source_metrics: dict, treatment_metrics: dict) -> dict:
    deltas = {
        threshold: int(treatment_metrics[f"clear_{threshold}"])
        - int(source_metrics[f"clear_{threshold}"])
        for threshold in THRESHOLDS
    }
    first = next((threshold for threshold in THRESHOLDS if deltas[threshold]), None)
    if first is not None:
        comparison = 1 if deltas[first] > 0 else -1
        tiebreaker = None
    else:
        mean_delta = (
            float(treatment_metrics["mean_best"])
            - float(source_metrics["mean_best"])
        )
        comparison = 1 if mean_delta > 1e-12 else -1 if mean_delta < -1e-12 else 0
        tiebreaker = "mean_best"
    return {
        "threshold_order": list(THRESHOLDS),
        "deltas": {str(key): value for key, value in deltas.items()},
        "first_difference": first,
        "tiebreaker": tiebreaker,
        "comparison": comparison,
        "treatment_selected": comparison > 0,
    }


def _cache_coverage(panel: str) -> dict:
    row = query_df(f"""
        WITH features AS (
          SELECT DISTINCT season, week, gsis_id
          FROM `{settings.predictions}.slate_player_features`
          WHERE panel_run_id = @panel AND pos != 'DST'
        ), cache AS (
          SELECT DISTINCT season, week, gsis_id
          FROM `{settings.features}.{CACHE_TABLE}`
        )
        SELECT COUNT(*) AS player_keys,
               COUNTIF(c.gsis_id IS NOT NULL) AS cache_hits,
               COUNTIF(c.gsis_id IS NULL) AS cache_misses
        FROM features f LEFT JOIN cache c USING (season, week, gsis_id)
    """, params={"panel": panel}).iloc[0]
    return {name: int(row[name] or 0) for name in row.index}


def _season_metrics(source: pd.DataFrame, treatment: pd.DataFrame) -> list[dict]:
    reports = []
    for season in sorted(set(source.season) | set(treatment.season)):
        left = source[source.season.eq(season)]
        right = treatment[treatment.season.eq(season)]
        reports.append({
            "season": int(season),
            "source": metrics(left),
            "treatment": metrics(right),
        })
    return reports


def compare_ensemble(source_id: str, treatment_id: str, code_sha: str) -> dict:
    source = adoption._candidates(source_id, True)
    treatment = adoption._candidates(treatment_id, False)
    failures = adoption._validate_panel("source", source, 80)
    failures += adoption._validate_panel("treatment", treatment, 80)
    mechanism = {}
    if not source.empty and not treatment.empty:
        if not source.code_sha.astype(str).eq(code_sha).all() or not \
                treatment.code_sha.astype(str).eq(code_sha).all():
            failures.append("panel code SHA differs from frozen generation")
        if source.config_hash.iloc[0] != treatment.config_hash.iloc[0]:
            failures.append("source and treatment config hashes differ")
        mechanism, mechanism_failures = adoption._ensemble_mechanism(
            adoption._ensemble_features(source_id, True),
            adoption._ensemble_features(treatment_id, False),
            adoption._candidate_mean_audit(source_id, True),
            adoption._candidate_mean_audit(treatment_id, False),
            str(source.seeds.iloc[0]), str(treatment.seeds.iloc[0]),
        )
        failures.extend(mechanism_failures)
    return _finish(
        source_id, treatment_id, "k3-vs-k1", source, treatment,
        failures, mechanism,
    )


def compare_role(source_id: str, treatment_id: str, code_sha: str) -> dict:
    source = direct._role._candidates(source_id, promoted=True)
    treatment = direct._role._candidates(treatment_id, promoted=False)
    failures = direct._ce._validate_panel("source", source)
    failures += direct._ce._validate_panel("treatment", treatment)
    mechanism: dict = {}
    if not source.empty and not treatment.empty:
        if not source.code_sha.astype(str).eq(code_sha).all() or not \
                treatment.code_sha.astype(str).eq(code_sha).all():
            failures.append("panel code SHA differs from frozen generation")
        feature_audit = direct._ce._feature_invariance(source_id, treatment_id)
        pair_audit = direct._role._candidate_pair_audit(source_id, treatment_id)
        failures.extend(direct._mechanism_failures(
            source, treatment, feature_audit, pair_audit))
        _, frontier = direct._role._role_frontiers(source, treatment)
        mechanism = {
            "feature_invariance": feature_audit,
            "candidate_pair_audit": pair_audit,
            "role_frontier": frontier,
        }
    return _finish(
        source_id, treatment_id, "direct-role-union", source, treatment,
        failures, mechanism,
    )


def _finish(
    source_id: str,
    treatment_id: str,
    mode: str,
    source: pd.DataFrame,
    treatment: pd.DataFrame,
    failures: list[str],
    mechanism: dict,
) -> dict:
    coverage = {
        "source": _cache_coverage(source_id),
        "treatment": _cache_coverage(treatment_id),
    }
    for arm, audit in coverage.items():
        if not audit["player_keys"] or audit["cache_misses"]:
            failures.append(f"{arm} did not use complete PIT-clean TabPFN keys")
    source_slates = slate_scores(source) if not source.empty else pd.DataFrame()
    treatment_slates = (
        slate_scores(treatment) if not treatment.empty else pd.DataFrame()
    )
    source_metrics = metrics(source_slates) if not source_slates.empty else {}
    treatment_metrics = (
        metrics(treatment_slates) if not treatment_slates.empty else {}
    )
    decision = (
        lexicographic_decision(source_metrics, treatment_metrics)
        if source_metrics and treatment_metrics else {}
    )
    selected = (
        treatment_id if decision.get("treatment_selected") else source_id
    )
    return {
        "disposition": "valid" if not failures else "invalid",
        "mode": mode,
        "source": source_id,
        "treatment": treatment_id,
        "selected_panel": selected if not failures else None,
        "source_metrics": source_metrics,
        "treatment_metrics": treatment_metrics,
        "season_metrics": (
            _season_metrics(source_slates, treatment_slates)
            if not source_slates.empty and not treatment_slates.empty else []
        ),
        "decision": decision,
        "cache_table": CACHE_TABLE,
        "cache_coverage": coverage,
        "mechanism": mechanism,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("treatment")
    parser.add_argument("--mechanism", choices=("ensemble", "direct-role"), required=True)
    parser.add_argument("--code-sha", required=True)
    args = parser.parse_args()
    report = (
        compare_ensemble(args.source, args.treatment, args.code_sha)
        if args.mechanism == "ensemble"
        else compare_role(args.source, args.treatment, args.code_sha)
    )
    print(PREFIX + json.dumps(report, sort_keys=True), flush=True)
    return 2 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
