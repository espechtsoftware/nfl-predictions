"""Pure guards for the conditional SIS RB run-defense exact-80 comparison."""

from __future__ import annotations

import pandas as pd

from .served_position_lineup_v2 import comparison_report, tail_first_decision
from .tabpfn_active_label_lineup_v2 import DISTRIBUTION_DERIVED_FEATURES
from .tabpfn_sched_lineup_v1 import mechanism_failures as _mechanism_failures


CONTROL_PANEL = "20260813-pitclean-e80-selected-tabpfn-sis-rb-rdef-control-v1"
TREATMENT_PANEL = "20260813-pitclean-e80-selected-tabpfn-sis-rb-rdef-treatment-v1"
CONTROL_TABLE = "tabpfn_sis_rb_rdef_control_v1"
TREATMENT_TABLE = "tabpfn_sis_rb_rdef_treatment_v1"


def mechanism_failures(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    feature_audit: dict,
    candidate_audit: dict,
    **kwargs,
) -> list[str]:
    return _mechanism_failures(
        control,
        treatment,
        feature_audit,
        candidate_audit,
        control_table=CONTROL_TABLE,
        treatment_table=TREATMENT_TABLE,
        mechanism_name="SIS RB run-defense",
        **kwargs,
    )


__all__ = [
    "CONTROL_PANEL", "CONTROL_TABLE", "DISTRIBUTION_DERIVED_FEATURES",
    "TREATMENT_PANEL", "TREATMENT_TABLE", "comparison_report",
    "mechanism_failures", "tail_first_decision",
]

