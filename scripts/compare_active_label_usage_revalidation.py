#!/usr/bin/env python3
"""Compare active-only multinomial control with the finite-K incumbent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.research import active_label_usage_revalidation as experiment  # noqa: E402
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
)


PREFIX = "ACTIVE_LABEL_USAGE_REVALIDATION_JSON="


def _selected_overlap(control, treatment) -> dict:
    left = control.loc[control.selected, ["season", "week", "players"]]
    right = treatment.loc[treatment.selected, ["season", "week", "players"]]
    paired = left.merge(
        right, on=["season", "week", "players"], how="outer",
        indicator=True, validate="one_to_one")
    return {
        "control_selected_rows": int(len(left)),
        "treatment_selected_rows": int(len(right)),
        "common_selected_rows": int(paired._merge.eq("both").sum()),
        "control_only_selected_rows": int(paired._merge.eq("left_only").sum()),
        "treatment_only_selected_rows": int(paired._merge.eq("right_only").sum()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-source", required=True)
    parser.add_argument("--control", default=experiment.CONTROL_PANEL)
    parser.add_argument("--treatment", default=experiment.TREATMENT_PANEL)
    parser.add_argument("--code-sha", required=True)
    args = parser.parse_args()

    historical = _candidates(args.historical_source, promoted=True)
    control = _candidates(args.control, promoted=False)
    treatment = _candidates(args.treatment, promoted=True)
    failures = validate_candidate_panel(
        "historical_source", historical, seasons=SOURCE_SEASONS,
        promoted=True, expected_code_sha=args.code_sha)
    failures.extend(validate_candidate_panel(
        "control", control, seasons=EVALUATION_SEASONS,
        promoted=False, expected_code_sha=args.code_sha))
    failures.extend(validate_candidate_panel(
        "treatment", treatment, seasons=EVALUATION_SEASONS,
        promoted=True, expected_code_sha=args.code_sha))

    audits: dict = {}
    scores: dict = {}
    if all(not frame.empty for frame in (historical, control, treatment)):
        audits = {
            "control_treatment_features": _feature_invariance(
                args.control, args.treatment,
                left_promoted=False, right_promoted=True,
                ignored_numeric_fields=experiment.DISTRIBUTION_DERIVED_FEATURES),
            "control_treatment_candidates": _candidate_audit(
                args.control, args.treatment,
                left_promoted=False, right_promoted=True),
            "selected_overlap": _selected_overlap(control, treatment),
        }
        failures.extend(experiment.mechanism_failures(
            control, treatment,
            audits["control_treatment_features"],
            audits["control_treatment_candidates"],
            expected_code_sha=args.code_sha,
        ))
        if not failures:
            scores = experiment.comparison_report(
                historical, control, treatment)

    decision = dict(scores.get("decision", {}))
    selected = None
    if not failures:
        selected = args.treatment if decision.get("treatment_selected") \
            else args.control
    report = {
        "version": "v1",
        "disposition": "valid" if not failures else "invalid",
        "historical_source": args.historical_source,
        "control": args.control,
        "treatment": args.treatment,
        "selected_panel": selected,
        "code_sha": args.code_sha,
        "cache_table": experiment.CACHE_TABLE,
        "fitted_k": experiment.FITTED_K,
        "known_treatment_before_protocol": True,
        **audits,
        "historical_source_generator_summary": generator_summary(historical),
        "control_generator_summary": generator_summary(control),
        "treatment_generator_summary": generator_summary(treatment),
        **scores,
        "failures": failures,
    }
    print(PREFIX + json.dumps(report, separators=(",", ":"), sort_keys=True),
          flush=True)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
