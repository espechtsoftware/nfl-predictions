from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "_game_team_usage_phase_r",
    Path(__file__).parents[1] / "scripts" / "analyze_game_team_usage_phase_r.py",
)
phase_r = module_from_spec(SPEC)
SPEC.loader.exec_module(phase_r)


def _metrics(k_counts, mult_counts, k_mean=170.0, mult_mean=170.0):
    out = {}
    for arm, counts, mean in (
        ("k", k_counts, k_mean), ("mult", mult_counts, mult_mean)
    ):
        for replicate in phase_r.SEEDS:
            out[f"{arm}-R{replicate}"] = {
                "selected_tail": {
                    str(tail): counts.get(tail, 0) for tail in phase_r.TAILS
                },
                "selected_mean": mean,
            }
    return out


def test_frozen_phase_r_decision_uses_first_summed_tail_difference():
    result = phase_r.frozen_decision(_metrics({210: 2}, {210: 1, 194: 9}))
    assert result["selected_arm"] == "k"
    assert result["deciding_threshold"] == 210


def test_frozen_phase_r_ties_tail_counts_then_uses_mean():
    result = phase_r.frozen_decision(_metrics({}, {}, k_mean=169, mult_mean=171))
    assert result["selected_arm"] == "mult"
    assert result["deciding_threshold"] is None


def test_frozen_phase_r_exact_tie_retains_finite_k():
    result = phase_r.frozen_decision(_metrics({}, {}))
    assert result["selected_arm"] == "k"
    assert result["finite_k_retained_on_exact_tie"]
