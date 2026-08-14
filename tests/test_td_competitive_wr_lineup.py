import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import td_competitive_wr_lineup as subject


def _frozen_env(season=2024, baseline_seed=0, role_seed=7331):
    return {
        subject.TREATMENT_ENV: "1",
        subject.LICENSE_ENV: "1",
        subject.REFERENCE_REPORT_SHA_ENV: "a" * 64,
        subject.TREATMENT_REPORT_SHA_ENV: "b" * 64,
        subject.PROTOCOL_SHA_ENV: "c" * 64,
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": subject.ACTIVE_CACHE,
        "GAME_SIM_MODE": "possession",
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": str(subject.DIRICHLET_K),
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "REPLACEMENT_SLOTS": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ",".join(subject.ROLE_FEATURES),
        "SERVED_POSITION_SCALES": subject.POSITION_SCHEDULES[season],
        "REPLAY_PROJECTION_SEED": str(baseline_seed),
        "ROLE_BELIEF_SEED": str(role_seed),
    }


def _frame():
    return pd.DataFrame({
        "season": [2024] * 6,
        "week": [1] * 6,
        "game_id": ["A@B"] * 6,
        "team": ["A", "A", "A", "A", "B", "B"],
        "gsis_id": ["q", "w1", "w2", "r", "q2", "w3"],
        "position": ["QB", "WR", "WR", "RB", "QB", "WR"],
        "mean_projection": [20.0, 12.0, 9.0, 14.0, 19.0, 11.0],
    })


def test_treatment_disabled_by_default():
    assert not subject.treatment_enabled({})
    assert subject.treatment_enabled({subject.TREATMENT_ENV: "1"})


def test_frozen_environment_accepts_all_registered_seeds():
    for baseline_seed, role_seed in subject.SEED_PAIRS.items():
        subject.validate_frozen_environment(
            2024, _frozen_env(2024, baseline_seed, role_seed),
        )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (subject.LICENSE_ENV, "0"),
        (subject.REFERENCE_REPORT_SHA_ENV, "short"),
        ("TD_LEDGER_RANK_COUPLING", "1"),
        ("N_BOOM", "41"),
        ("ROLE_BELIEF_SEED", "9"),
    ],
)
def test_frozen_environment_rejects_missing_license_or_drift(name, value):
    env = _frozen_env()
    env[name] = value
    with pytest.raises(ValueError):
        subject.validate_frozen_environment(2024, env)


def test_allocate_final_served_changes_only_supported_competing_wrs():
    control = np.array([
        [1.0, 2.0, 3.0, 4.0],
        [11.0, 14.0, 12.0, 13.0],
        [23.0, 21.0, 24.0, 22.0],
        [31.0, 32.0, 34.0, 33.0],
        [41.0, 42.0, 43.0, 44.0],
        [51.0, 52.0, 53.0, 54.0],
    ])
    source = np.array([
        [4.0, 1.0, 3.0, 2.0],
        [2.0, 4.0, 1.0, 3.0],
        [3.0, 1.0, 4.0, 2.0],
        [4.0, 3.0, 2.0, 1.0],
        [2.0, 1.0, 4.0, 3.0],
        [3.0, 4.0, 1.0, 2.0],
    ])
    treatment, audit = subject.allocate_final_served(
        control, source, source.copy(), _frame(),
    )
    assert np.array_equal(treatment[[0, 3, 4, 5]], control[[0, 3, 4, 5]])
    assert not np.array_equal(treatment[1:3], control[1:3])
    assert np.array_equal(
        np.sort(treatment, axis=1), np.sort(control, axis=1),
    )
    assert audit["eligible_groups"] == 1
    assert audit["eligible_wr_rows"] == 2
    assert audit["changed_rows"] == 2
    assert audit["only_eligible_wr_rows_changed"]
    assert audit["all_ineligible_rows_bit_exact"]


def test_allocate_final_served_rejects_nondeterministic_source():
    control = np.arange(24, dtype=float).reshape(6, 4)
    source = control[:, ::-1]
    repeat = source.copy()
    repeat[1, [0, 1]] = repeat[1, [1, 0]]
    with pytest.raises(ValueError, match="not bit-exact"):
        subject.allocate_final_served(control, source, repeat, _frame())
