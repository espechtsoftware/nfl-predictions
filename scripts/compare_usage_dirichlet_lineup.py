"""Compare the frozen data-fitted K same-image exact-80 books."""

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
    _source_control_reproduction,
    _winner_position_contributions,
)
from nfl_dfs.research import usage_dirichlet_lineup as experiment  # noqa: E402
from nfl_dfs.research.served_tail_lineup import generator_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--historical-source", default=experiment.HISTORICAL_SOURCE_PANEL)
    parser.add_argument(
        "--evaluation-source", default=experiment.EVALUATION_SOURCE_PANEL)
    parser.add_argument("--control", default=experiment.CONTROL_PANEL)
    parser.add_argument("--treatment", default=experiment.TREATMENT_PANEL)
    parser.add_argument("--experiment-code-sha", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    historical_source = _candidates(args.historical_source, promoted=True)
    evaluation_source = _candidates(args.evaluation_source, promoted=True)
    control = _candidates(args.control, promoted=False)
    treatment = _candidates(args.treatment, promoted=False)
    failures = experiment.validate_candidate_panel(
        "historical_source",
        historical_source,
        seasons=experiment.SOURCE_SEASONS,
        promoted=True,
        expected_code_sha=experiment.HISTORICAL_SOURCE_CODE_SHA,
    )
    failures.extend(experiment.validate_candidate_panel(
        "evaluation_source",
        evaluation_source,
        seasons=experiment.EVALUATION_SEASONS,
        promoted=True,
        expected_code_sha=experiment.EVALUATION_SOURCE_CODE_SHA,
    ))
    for name, rows in (("control", control), ("treatment", treatment)):
        failures.extend(experiment.validate_candidate_panel(
            name,
            rows,
            seasons=experiment.EVALUATION_SEASONS,
            promoted=False,
            expected_code_sha=args.experiment_code_sha,
        ))

    audits: dict = {}
    scores: dict = {}
    contributions: dict = {}
    if all(not frame.empty for frame in (
            historical_source, evaluation_source, control, treatment)):
        audits = {
            "source_control_features": _feature_invariance(
                args.evaluation_source,
                args.control,
                left_promoted=True,
                right_promoted=False,
            ),
            "control_treatment_features": _feature_invariance(
                args.control,
                args.treatment,
                left_promoted=False,
                right_promoted=False,
            ),
            "source_control_candidates": _candidate_audit(
                args.evaluation_source,
                args.control,
                left_promoted=True,
                right_promoted=False,
            ),
            "control_treatment_candidates": _candidate_audit(
                args.control,
                args.treatment,
                left_promoted=False,
                right_promoted=False,
            ),
            "source_control_reproduction": _source_control_reproduction(
                evaluation_source, control),
        }
        failures.extend(experiment.mechanism_failures(
            evaluation_source,
            control,
            treatment,
            audits["source_control_features"],
            audits["control_treatment_features"],
            audits["source_control_candidates"],
            audits["control_treatment_candidates"],
            audits["source_control_reproduction"],
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
        "evaluation_source": args.evaluation_source,
        "control": args.control,
        "treatment": args.treatment,
        "mode": "data-fitted-dirichlet-k-same-image-control-treatment",
        "fitted_k": experiment.FITTED_K,
        "k_report_sha256": experiment.K_REPORT_SHA256,
        **audits,
        "historical_source_generator_summary": generator_summary(
            historical_source),
        "evaluation_source_generator_summary": generator_summary(
            evaluation_source),
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
