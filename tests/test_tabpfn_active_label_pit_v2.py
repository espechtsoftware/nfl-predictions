from pathlib import Path

import pandas as pd

from nfl_dfs.research import tabpfn_active_label_lineup_v2 as active


K = "28.246898139750336"
CONTROL_SCHEDULES = {
    2023: "QB:0.99,RB:1.0,TE:0.95,WR:1.05",
    2024: "QB:0.98,RB:1.01,TE:0.96,WR:1.04",
    2025: "QB:0.97,RB:1.02,TE:0.97,WR:1.03",
}
TREATMENT_SCHEDULES = {
    2023: "QB:0.98,RB:0.99,TE:0.96,WR:1.04",
    2024: "QB:0.97,RB:1.0,TE:0.97,WR:1.03",
    2025: "QB:0.96,RB:1.01,TE:0.98,WR:1.02",
}


def _rows(*, treatment: bool) -> pd.DataFrame:
    rows = []
    for season in (2023, 2024, 2025):
        values = {
            "GAME_SIM_MODE": "possession",
            "MODEL_ENSEMBLE": "1",
            "N_CE": "0",
            "N_EPISTEMIC": "12",
            "N_GUMBEL": "0",
            "N_BOOM": "40",
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": (
                "target_share_last,carry_share_last,snap_share_last,"
                "target_share_jump,carry_share_jump,snap_share_jump"
            ),
            "ROLE_BELIEF_SEED": "7331",
            "REPLACEMENT_SLOTS": "12",
            "GAME_SIM_USAGE": "dirichlet",
            "DIRICHLET_K": K,
            "TABPFN_MARGINAL_TABLE": (
                active.TREATMENT_TABLE if treatment else active.CONTROL_TABLE),
            "SERVED_POSITION_SCALES": (
                TREATMENT_SCHEDULES if treatment else CONTROL_SCHEDULES)[season],
        }
        rows.append({
            "season": season,
            "code_sha": "a12ab31",
            "seeds": "fixed",
            "lever_env": ",".join(
                f"{key}={value}" for key, value in values.items()),
        })
    return pd.DataFrame(rows)


def test_active_label_v2_mechanism_accepts_cache_and_schedule_only():
    assert active.DISTRIBUTION_DERIVED_FEATURES == (
        "consensus_div", "mean_projection", "model_points_pre", "proj",
        "proj_tourney", "own_est", "proj_p10", "proj_p50", "proj_p90",
        "proj_std",
    )
    features = {
        "left_rows": 10, "right_rows": 10,
        "left_only_rows": 0, "right_only_rows": 0,
        "mismatch_rows": 0, "max_numeric_abs_delta": 0.0,
        "ignored_numeric_fields": list(active.DISTRIBUTION_DERIVED_FEATURES),
    }
    candidates = {
        "paired_slates": 54, "common_rows": 10,
        "left_only_rows": 1, "right_only_rows": 1,
        "common_actual_mismatch": 0, "common_sim_mean_mismatch": 0,
    }
    failures = active.mechanism_failures(
        _rows(treatment=False), _rows(treatment=True), features, candidates,
        expected_code_sha="a12ab31", role_selected=True,
        allocation="dirichlet", selected_k=K,
        control_schedules=CONTROL_SCHEDULES,
        treatment_schedules=TREATMENT_SCHEDULES,
    )
    assert failures == []


def test_active_label_v2_protocol_and_both_terminal_branches_are_tracked():
    root = Path(__file__).parents[1]
    protocol = (root / "reports/2026-08-12-pit-clean-active-label-exact80.md").read_text(
        encoding="utf-8")
    launch = (root / "scripts/prop_lock_tabpfn_active_label_exact80_v2.sh").read_text(
        encoding="utf-8")
    finish = (root / "scripts/cloud_finish_tabpfn_active_label_exact80_v2.sh").read_text(
        encoding="utf-8")
    recompare = (
        root / "scripts/cloud_recompare_tabpfn_active_label_exact80_v2.sh"
    ).read_text(encoding="utf-8")
    fallback = (root / "scripts/resolve_tabpfn_active_label_fallback_v2.sh").read_text(
        encoding="utf-8")
    final_finish = (
        root / "scripts/cloud_finish_tabpfn_active_label_final_served_v2.sh"
    ).read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "240,230,220,210,200,194,187" in protocol
    assert "selected_usage.txt" in launch
    assert "nfl-dfs/nfl-dfs@sha256:ad50fe19" in launch
    assert "wrong generation image package or digest" in launch
    assert 'f"{arm}_schedule"' in launch
    assert "TABPFN_ACTIVE_LABEL_STAGE_B_V2_JSON=" in finish
    assert "compare-tabpfn-active-label-exact80-v2-r1" in recompare
    assert "superseded_invalid_execution" in recompare
    assert "final-served-gate-failed" in fallback
    assert "tabpfn_projections_pit_v2" in fallback
    assert "PIT_ACTIVE_LABEL_FINAL_SERVED_COMPLETE" in final_finish
    assert "COPY scripts/compare_tabpfn_active_label_lineup_v2.py " \
        "./scripts/compare_tabpfn_active_label_lineup_v2.py" in dockerfile
