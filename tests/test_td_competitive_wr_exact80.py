import pandas as pd

from nfl_dfs.research import td_competitive_wr_exact80 as subject
from nfl_dfs.research import td_competitive_wr_lineup as treatment
from nfl_dfs.research.tabpfn_active_label_lineup_v2 import (
    DISTRIBUTION_DERIVED_FEATURES,
)


REFERENCE_SHA = "a" * 64
TREATMENT_SHA = "b" * 64
PROTOCOL_SHA = "c" * 64
CODE_SHA = "d" * 40


def _lever(season: int, replicate: int, arm: str) -> str:
    base_seed, role_seed = subject.SEEDS[replicate]
    values = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": treatment.ACTIVE_CACHE,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"
        ),
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": subject.FITTED_K,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "SERVED_POSITION_SCALES": subject.SCHEDULES[season],
    }
    if arm == "treatment":
        values.update({
            treatment.TREATMENT_ENV: "1",
            treatment.LICENSE_ENV: "1",
            treatment.REFERENCE_REPORT_SHA_ENV: REFERENCE_SHA,
            treatment.TREATMENT_REPORT_SHA_ENV: TREATMENT_SHA,
            treatment.PROTOCOL_SHA_ENV: PROTOCOL_SHA,
        })
    return ",".join(f"{key}={value}" for key, value in sorted(values.items()))


def _candidates(arm: str, replicate: int) -> pd.DataFrame:
    base_seed, role_seed = subject.SEEDS[replicate]
    rows = []
    for season in subject.SEASONS:
        for week in range(1, 19):
            rows.append({
                "season": season,
                "week": week,
                "players": f"p-{season}-{week}",
                "code_sha": CODE_SHA,
                "seeds": (
                    f"REPLAY_PROJECTION_SEED={base_seed};"
                    f"ROLE_BELIEF_SEED={role_seed}"
                ),
                "lever_env": _lever(season, replicate, arm),
                "actual_score": 200.0 + week,
                "sim_mean": 150.0,
                "p_line": 0.1 if arm == "control" else 0.11,
                "score_artifact_sha256": (
                    ("e" if arm == "control" else "f") * 64
                ),
            })
    return pd.DataFrame(rows)


def _feature_audit() -> dict:
    return {
        "left_rows": 100,
        "right_rows": 100,
        "left_only_rows": 0,
        "right_only_rows": 0,
        "invariant_mismatch_rows": 0,
        "ignored_fields": sorted(DISTRIBUTION_DERIVED_FEATURES),
        "missing_ignored_fields": [],
    }


def test_panel_ids_are_frozen():
    assert subject.panel_id("control", 0) == (
        "20260814-td-comp-wr-control-r0-v1"
    )
    assert subject.panel_id("treatment", 4) == (
        "20260814-td-comp-wr-treatment-r4-v1"
    )


def test_dependence_candidate_audit_requires_scores_not_means_to_change():
    control = _candidates("control", 0)
    treated = _candidates("treatment", 0)
    audit = subject.candidate_audit(control, treated)
    assert audit["paired_slates"] == 54
    assert audit["common_actual_mismatch"] == 0
    assert audit["common_sim_mean_mismatch"] == 0
    assert audit["common_p_line_mismatch"] == 54
    assert audit["common_artifact_sha_mismatch"] == 54


def test_registered_mechanism_passes_exact_provenance_audit():
    control = _candidates("control", 2)
    treated = _candidates("treatment", 2)
    failures = subject.mechanism_failures(
        control,
        treated,
        _feature_audit(),
        subject.candidate_audit(control, treated),
        expected_code_sha=CODE_SHA,
        replicate=2,
        reference_report_sha=REFERENCE_SHA,
        treatment_report_sha=TREATMENT_SHA,
        protocol_sha=PROTOCOL_SHA,
    )
    assert failures == []


def test_provenance_audit_rejects_unregistered_composition():
    control = _candidates("control", 1)
    treated = _candidates("treatment", 1)
    treated["lever_env"] += ",SIS_ASOE_TARGET_ALLOCATION=1"
    failures = subject.mechanism_failures(
        control,
        treated,
        _feature_audit(),
        subject.candidate_audit(control, treated),
        expected_code_sha=CODE_SHA,
        replicate=1,
        reference_report_sha=REFERENCE_SHA,
        treatment_report_sha=TREATMENT_SHA,
        protocol_sha=PROTOCOL_SHA,
    )
    assert any("prohibited levers" in failure for failure in failures)
