#!/usr/bin/env python3
"""Compare the PIT-clean SCHED same-image exact-80 evaluation books."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.research import tabpfn_sched_lineup_v1 as experiment  # noqa: E402
from nfl_dfs.research.served_tail_lineup import (  # noqa: E402
    EVALUATION_SEASONS,
    SOURCE_SEASONS,
    generator_summary,
    validate_candidate_panel,
)
from compare_served_position_lineup import (  # noqa: E402
    _candidate_audit,
    _candidates,
    _feature_invariance,
    _winner_position_contributions,
)


PREFIX = "TABPFN_SCHED_STAGE_B_V1_JSON="


def _schedules(encoded: str) -> dict[int, str]:
    value = json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))
    return {int(season): str(spec) for season, spec in value.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-source", required=True)
    parser.add_argument("--historical-code-sha", default="a12ab31")
    parser.add_argument("--control", default=experiment.CONTROL_PANEL)
    parser.add_argument("--treatment", default=experiment.TREATMENT_PANEL)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--role-selected", choices=("true", "false"), required=True)
    parser.add_argument("--allocation", choices=("multinomial", "dirichlet"),
                        required=True)
    parser.add_argument("--selected-k", required=True)
    parser.add_argument("--control-schedules-b64", required=True)
    parser.add_argument("--treatment-schedules-b64", required=True)
    parser.add_argument("--cache-validation-sha", required=True)
    parser.add_argument("--final-served-sha", required=True)
    args = parser.parse_args()
    role_selected = args.role_selected == "true"
    control_schedules = _schedules(args.control_schedules_b64)
    treatment_schedules = _schedules(args.treatment_schedules_b64)

    historical_source = _candidates(args.historical_source, promoted=True)
    control = _candidates(args.control, promoted=False)
    treatment = _candidates(args.treatment, promoted=False)
    failures = validate_candidate_panel(
        "historical_source", historical_source, seasons=SOURCE_SEASONS,
        promoted=True, expected_code_sha=args.historical_code_sha)
    for name, rows in (("control", control), ("treatment", treatment)):
        failures.extend(validate_candidate_panel(
            name, rows, seasons=EVALUATION_SEASONS, promoted=False,
            expected_code_sha=args.code_sha, allow_season_config=True))
    audits: dict = {}
    scores: dict = {}
    contributions: dict = {}
    if all(not frame.empty for frame in (historical_source, control, treatment)):
        audits = {
            "control_treatment_features": _feature_invariance(
                args.control, args.treatment,
                left_promoted=False, right_promoted=False,
                ignored_numeric_fields=experiment.DISTRIBUTION_DERIVED_FEATURES),
            "control_treatment_candidates": _candidate_audit(
                args.control, args.treatment,
                left_promoted=False, right_promoted=False),
        }
        failures.extend(experiment.mechanism_failures(
            control, treatment,
            audits["control_treatment_features"],
            audits["control_treatment_candidates"],
            expected_code_sha=args.code_sha,
            role_selected=role_selected,
            allocation=args.allocation,
            selected_k=args.selected_k,
            control_schedules=control_schedules,
            treatment_schedules=treatment_schedules,
        ))
        if not failures:
            scores = experiment.comparison_report(
                historical_source, control, treatment)
            contributions = {
                "control": _winner_position_contributions(args.control),
                "treatment": _winner_position_contributions(args.treatment),
            }
    decision = dict(scores.get("decision", {}))
    selected = (
        args.treatment if decision.get("treatment_selected") else args.control
    ) if not failures else None
    report = {
        "disposition": "valid" if not failures else "invalid",
        "historical_source": args.historical_source,
        "historical_code_sha": args.historical_code_sha,
        "control": args.control,
        "treatment": args.treatment,
        "selected_panel": selected,
        "role_selected": role_selected,
        "allocation": args.allocation,
        "selected_k": args.selected_k,
        "code_sha": args.code_sha,
        "control_cache": experiment.CONTROL_TABLE,
        "treatment_cache": experiment.TREATMENT_TABLE,
        "control_position_schedules": control_schedules,
        "treatment_position_schedules": treatment_schedules,
        "cache_validation_sha256": args.cache_validation_sha,
        "final_served_report_sha256": args.final_served_sha,
        "mode": "pit-clean-tabpfn-sched-v1",
        **audits,
        "historical_source_generator_summary": generator_summary(
            historical_source),
        "control_generator_summary": generator_summary(control),
        "treatment_generator_summary": generator_summary(treatment),
        **scores,
        "winner_position_contributions": contributions,
        "failures": failures,
    }
    print(PREFIX + json.dumps(report, separators=(",", ":"), sort_keys=True),
          flush=True)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
