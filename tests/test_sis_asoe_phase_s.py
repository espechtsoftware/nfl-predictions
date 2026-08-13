from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


SPEC = spec_from_file_location(
    "_sis_asoe_phase_s",
    Path(__file__).parents[1] / "scripts" / "analyze_sis_asoe_phase_s.py",
)
phase_s = module_from_spec(SPEC)
SPEC.loader.exec_module(phase_s)


def _metrics(treatment, control, treatment_mean=170, control_mean=170):
    out = {}
    for arm, counts, mean in (
        ("treatment", treatment, treatment_mean),
        ("control", control, control_mean),
    ):
        for replicate in phase_s.SEEDS:
            out[f"{arm}-R{replicate}"] = {
                "selected_tail": {str(t): counts.get(t, 0) for t in phase_s.TAILS},
                "selected_mean": mean,
            }
    return out


def test_phase_s_uses_first_summed_tail_difference():
    result = phase_s.frozen_decision(_metrics({220: 1}, {220: 0, 194: 9}))
    assert result["selected_arm"] == "treatment"
    assert result["deciding_threshold"] == 220


def test_phase_s_mean_tie_break_can_retain_control():
    result = phase_s.frozen_decision(
        _metrics({}, {}, treatment_mean=169, control_mean=171)
    )
    assert result["selected_arm"] == "control"


def test_phase_s_exact_tie_retains_control():
    result = phase_s.frozen_decision(_metrics({}, {}))
    assert result["selected_arm"] == "control"
    assert result["control_retained_on_exact_tie"]


def test_phase_s_bootstrap_constants_are_frozen():
    assert phase_s.BOOTSTRAP_RESAMPLES == 2_000
    assert phase_s.BOOTSTRAP_SEED == 8_132_026


def test_phase_r_reproduction_checks_complete_candidate_fingerprint(monkeypatch):
    rows = []
    candidates = {}
    for replicate in phase_s.SEEDS:
        row = {
            "season": 2023, "week": 1, "cand_ix": 0,
            "players": "a,b,c,d,e,f,g,h,i", "selected": True,
            "selected_rank": 0, "actual_score": 200.0, "sim_mean": 150.0,
        }
        rows.append(row)
        candidates[("control", replicate)] = pd.DataFrame([row])
    monkeypatch.setattr(
        phase_s, "query_df", lambda *args, **kwargs: pd.DataFrame(rows[:1])
    )
    assert not phase_s.phase_r_reproduction_failures(candidates, "mult")

    candidates[("control", 2)].loc[0, "players"] = "changed"
    failures = phase_s.phase_r_reproduction_failures(candidates, "mult")
    assert failures == ["R2 same-image control players differs from Phase R"]
