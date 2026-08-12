#!/usr/bin/env python3
"""Audit the PIT-clean same-image position-scale control and treatment."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.research import served_position_lineup_v2 as experiment  # noqa: E402
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
    _source_control_reproduction,
    _winner_position_contributions,
)


PREFIX = "SERVED_POSITION_STAGE_B_V2_JSON="


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--control", default=experiment.CONTROL_PANEL)
    parser.add_argument("--treatment", default=experiment.TREATMENT_PANEL)
    parser.add_argument("--code-sha", required=True)
    position = parser.add_mutually_exclusive_group(required=True)
    position.add_argument("--position-spec")
    position.add_argument("--position-spec-b64")
    parser.add_argument("--base", choices=("k1", "k3"), required=True)
    parser.add_argument("--role-selected", choices=("true", "false"), required=True)
    args = parser.parse_args()
    role_selected = args.role_selected == "true"
    position_spec = args.position_spec or base64.b64decode(
        args.position_spec_b64, validate=True).decode("ascii")

    source = _candidates(args.source, promoted=True)
    control = _candidates(args.control, promoted=False)
    treatment = _candidates(args.treatment, promoted=False)
    source_eval = source[source.season.isin(EVALUATION_SEASONS)]
    failures = validate_candidate_panel(
        "source", source, seasons=SOURCE_SEASONS, promoted=True,
        expected_code_sha=args.code_sha)
    for name, rows in (("control", control), ("treatment", treatment)):
        failures.extend(validate_candidate_panel(
            name, rows, seasons=EVALUATION_SEASONS, promoted=False,
            expected_code_sha=args.code_sha))

    audits: dict = {}
    scores: dict = {}
    contributions: dict = {}
    if not source.empty and not control.empty and not treatment.empty:
        audits = {
            "source_control_features": _feature_invariance(
                args.source, args.control,
                left_promoted=True, right_promoted=False),
            "control_treatment_features": _feature_invariance(
                args.control, args.treatment,
                left_promoted=False, right_promoted=False),
            "source_control_candidates": _candidate_audit(
                args.source, args.control,
                left_promoted=True, right_promoted=False),
            "control_treatment_candidates": _candidate_audit(
                args.control, args.treatment,
                left_promoted=False, right_promoted=False),
            "source_control_reproduction": _source_control_reproduction(
                source_eval, control),
        }
        failures.extend(experiment.mechanism_failures(
            source_eval, control, treatment,
            audits["source_control_features"],
            audits["control_treatment_features"],
            audits["source_control_candidates"],
            audits["control_treatment_candidates"],
            audits["source_control_reproduction"],
            expected_code_sha=args.code_sha,
            position_spec=position_spec,
            base=args.base,
            role_selected=role_selected,
        ))
        if not failures:
            scores = experiment.comparison_report(source, control, treatment)
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
        "source": args.source,
        "control": args.control,
        "treatment": args.treatment,
        "selected_panel": selected,
        "base": args.base,
        "role_selected": role_selected,
        "code_sha": args.code_sha,
        "position_spec": position_spec,
        "cache_table": experiment.CACHE_TABLE,
        "mode": "pit-clean-served-position-scales-v2",
        **audits,
        "source_generator_summary": generator_summary(source),
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
