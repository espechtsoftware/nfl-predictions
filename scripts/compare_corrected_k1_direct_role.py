"""Audit the frozen corrected K1 + direct role-belief candidate union."""
from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.research.candidate_union import tail_first_decision  # noqa: E402
from nfl_dfs.research.panel_compare import metrics, slate_scores  # noqa: E402


SOURCE_PANEL = "20260810-lockfix-e80-k1-8677d21"
TREATMENT_PANEL = "20260810-lockfix-e80-k1-role12union-8677d21"
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)

_DIR = Path(__file__).resolve().parent
_CE_SPEC = spec_from_file_location("_direct_role_ce", _DIR / "compare_k1_ce_panel.py")
assert _CE_SPEC and _CE_SPEC.loader
_ce = module_from_spec(_CE_SPEC)
_CE_SPEC.loader.exec_module(_ce)

_ROLE_SPEC = spec_from_file_location(
    "_direct_role_prior", _DIR / "compare_k1_role_belief_panel.py")
assert _ROLE_SPEC and _ROLE_SPEC.loader
_role = module_from_spec(_ROLE_SPEC)
_ROLE_SPEC.loader.exec_module(_role)


def _mechanism_failures(source: pd.DataFrame, treatment: pd.DataFrame,
                        feature_audit: dict, pair_audit: dict) -> list[str]:
    failures: list[str] = []
    if source.empty or treatment.empty:
        return failures
    if source.code_sha.iloc[0] != treatment.code_sha.iloc[0]:
        failures.append("source and treatment code SHA differ")
    if source.config_hash.iloc[0] != treatment.config_hash.iloc[0]:
        failures.append("source and treatment config hashes differ")
    if source.seeds.iloc[0] != treatment.seeds.iloc[0]:
        failures.append("source and treatment seed identities differ")

    source_levers = _role._lever_values(source.lever_env.iloc[0])
    treatment_levers = _role._lever_values(treatment.lever_env.iloc[0])
    for key, value in {"N_CE": "0", "N_EPISTEMIC": "0", "N_BOOM": "40"}.items():
        if source_levers.get(key) != value:
            failures.append(f"source {key} is not {value}")
    for key, value in {"N_CE": "0", "N_EPISTEMIC": "12", "N_BOOM": "40"}.items():
        if treatment_levers.get(key) != value:
            failures.append(f"treatment {key} is not {value}")
    exact_role = {
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
    }
    for key, value in exact_role.items():
        if treatment_levers.get(key) != value:
            failures.append(f"treatment {key} is not the frozen value")
    if "GEN_POOL_CAP_MAP" in treatment_levers:
        failures.append("direct-role union treatment must be uncapped")

    allowed = {
        "N_EPISTEMIC", "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
        "ROLE_BELIEF_SEED", "REPLACEMENT_SLOTS",
    }
    source_other = {k: v for k, v in source_levers.items() if k not in allowed}
    treatment_other = {
        k: v for k, v in treatment_levers.items() if k not in allowed}
    if source_other != treatment_other:
        failures.append("direct-role treatment changes unrelated replay levers")

    if (feature_audit.get("source_rows") != feature_audit.get("treatment_rows")
            or feature_audit.get("source_only_rows")
            or feature_audit.get("treatment_only_rows")
            or feature_audit.get("mismatch_rows")):
        failures.append("source/treatment player snapshots are not invariant")
    if pair_audit.get("paired_slates") != 107:
        failures.append("candidate audit does not cover 107 paired slates")
    if (pair_audit.get("slates_with_role") != 107
            or pair_audit.get("min_role_per_slate") != 12
            or pair_audit.get("max_role_per_slate") != 12):
        failures.append("role generator did not retain exactly 12 candidates per slate")
    if pair_audit.get("novel_role_rows", 0) <= 0:
        failures.append("role generator produced no source-novel roster")
    for field in ("common_actual_mismatch", "common_p_line_mismatch",
                  "common_sim_mean_mismatch", "common_support_mismatch"):
        if pair_audit.get(field):
            failures.append(f"shared candidates differ in {field}")
    if pair_audit.get("source_only_rows"):
        failures.append("direct-role treatment is not a source-roster superset")
    if pair_audit.get("slates_with_larger_treatment") != 107:
        failures.append("direct-role treatment did not expand every slate")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("treatment", nargs="?", default=TREATMENT_PANEL)
    parser.add_argument("--source", default=SOURCE_PANEL)
    parser.add_argument("--output")
    args = parser.parse_args()

    source = _role._candidates(args.source, promoted=True)
    treatment = _role._candidates(args.treatment, promoted=False)
    failures = (_ce._validate_panel("source", source)
                + _ce._validate_panel("treatment", treatment))
    feature_audit: dict = {}
    pair_audit: dict = {}
    role_report: dict = {}
    source_slates = pd.DataFrame()
    treatment_slates = pd.DataFrame()
    if not source.empty and not treatment.empty:
        feature_audit = _ce._feature_invariance(args.source, args.treatment)
        pair_audit = _role._candidate_pair_audit(args.source, args.treatment)
        failures.extend(_mechanism_failures(
            source, treatment, feature_audit, pair_audit))
        _, role_report = _role._role_frontiers(source, treatment)
        source_slates = slate_scores(source)
        treatment_slates = slate_scores(treatment)

    source_metrics = metrics(source_slates) if not source_slates.empty else {}
    treatment_metrics = metrics(treatment_slates) if not treatment_slates.empty else {}
    decision = (tail_first_decision(source_metrics, treatment_metrics)
                if source_metrics and treatment_metrics else {})
    decision["mechanism_valid"] = not failures
    decision["passes"] = bool(
        not failures and decision.get("promotion_candidate"))
    report = {
        "source": args.source,
        "treatment": args.treatment,
        "mode": "direct-role-union",
        "source_metrics": source_metrics,
        "treatment_metrics": treatment_metrics,
        "season_metrics": (
            _ce._season_metrics(source_slates, treatment_slates)
            if not source_slates.empty and not treatment_slates.empty else []),
        "feature_invariance": feature_audit,
        "candidate_pair_audit": pair_audit,
        "role_frontier": role_report,
        "tail_first_operational_gate": decision,
        "disposition": ("pass" if decision.get("passes") else
                        "invalid" if failures else "reject"),
        "failures": failures,
    }
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

