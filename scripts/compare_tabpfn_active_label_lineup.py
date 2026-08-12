"""Compare the frozen TabPFN active-label same-image exact-80 books."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_served_position_lineup import (  # noqa: E402
    _candidate_audit,
    _candidates,
    _feature_invariance,
    _winner_position_contributions,
)
from nfl_dfs.research import tabpfn_active_label_lineup as experiment  # noqa: E402
from nfl_dfs.research.served_tail_lineup import generator_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--historical-source", default=experiment.HISTORICAL_SOURCE_PANEL)
    parser.add_argument("--control", default=experiment.CONTROL_PANEL)
    parser.add_argument("--treatment", default=experiment.TREATMENT_PANEL)
    parser.add_argument("--experiment-code-sha", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    historical_source = _candidates(args.historical_source, promoted=True)
    control = _candidates(args.control, promoted=False)
    treatment = _candidates(args.treatment, promoted=False)
    failures = experiment.validate_candidate_panel(
        "historical_source",
        historical_source,
        seasons=experiment.SOURCE_SEASONS,
        promoted=True,
        expected_code_sha=experiment.HISTORICAL_SOURCE_CODE_SHA,
    )
    for name, rows in (("control", control), ("treatment", treatment)):
        failures.extend(experiment.validate_candidate_panel(
            name,
            rows,
            seasons=experiment.EVALUATION_SEASONS,
            promoted=False,
            expected_code_sha=args.experiment_code_sha,
            allow_season_config=True,
        ))

    audits: dict = {}
    scores: dict = {}
    contributions: dict = {}
    if all(not frame.empty for frame in (
            historical_source, control, treatment)):
        audits = {
            "control_treatment_features": _feature_invariance(
                args.control,
                args.treatment,
                left_promoted=False,
                right_promoted=False,
                ignored_numeric_fields=experiment.DISTRIBUTION_DERIVED_FEATURES,
            ),
            "control_treatment_candidates": _candidate_audit(
                args.control,
                args.treatment,
                left_promoted=False,
                right_promoted=False,
            ),
        }
        failures.extend(experiment.mechanism_failures(
            control,
            treatment,
            audits["control_treatment_features"],
            audits["control_treatment_candidates"],
            experiment_code_sha=args.experiment_code_sha,
        ))
        if not failures:
            scores = experiment.comparison_report(
                historical_source, control, treatment)
            contributions = {
                "control": _winner_position_contributions(args.control),
                "treatment": _winner_position_contributions(args.treatment),
            }

    decision = dict(scores.get("tail_first_decision", {}))
    decision["mechanism_valid"] = not failures
    decision["passes"] = bool(not failures and decision.get("passes"))
    if failures:
        disposition = "invalid"
    elif decision.get("passes"):
        disposition = "pass"
    elif decision.get("neutral"):
        disposition = "neutral"
    else:
        disposition = "reject"
    report = {
        "historical_source": args.historical_source,
        "control": args.control,
        "treatment": args.treatment,
        "mode": "tabpfn-active-label-same-image-exact80",
        "cache_validation_sha256": experiment.CACHE_VALIDATION_SHA256,
        "final_served_report_sha256": experiment.FINAL_SERVED_REPORT_SHA256,
        "control_cache": experiment.CONTROL_TABLE,
        "treatment_cache": experiment.TREATMENT_TABLE,
        "control_position_schedules": experiment.CONTROL_POSITION_SPECS,
        "treatment_position_schedules": experiment.TREATMENT_POSITION_SPECS,
        **audits,
        "historical_source_generator_summary": generator_summary(
            historical_source),
        "control_generator_summary": generator_summary(control),
        "treatment_generator_summary": generator_summary(treatment),
        **scores,
        "winner_position_contributions": contributions,
        "tail_first_decision": decision,
        "disposition": disposition,
        "failures": failures,
    }
    payload = json.dumps(report, separators=(",", ":"), sort_keys=True)
    print(payload)
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
