import numpy as np
import pytest

from nfl_dfs.research import td_ledger_rank_lineup as subject


def _frozen_env(season=2024, baseline_seed=0, role_seed=7331):
    return {
        subject.TREATMENT_ENV: "1",
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


def test_treatment_disabled_by_default():
    assert not subject.treatment_enabled({})
    assert not subject.treatment_enabled({subject.TREATMENT_ENV: "off"})
    assert subject.treatment_enabled({subject.TREATMENT_ENV: "1"})


def test_frozen_environment_accepts_each_registered_seed_pair():
    for baseline_seed, role_seed in subject.SEED_PAIRS.items():
        subject.validate_frozen_environment(
            2024, _frozen_env(2024, baseline_seed, role_seed))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TD_LEDGER", "1"),
        ("SIS_ASOE_TARGET_ALLOCATION", "1"),
        ("N_BOOM", "41"),
        ("TABPFN_MARGINAL_TABLE", "tabpfn_projections"),
        ("ROLE_BELIEF_SEED", "9"),
    ],
)
def test_frozen_environment_rejects_composition_or_drift(name, value):
    env = _frozen_env()
    env[name] = value
    with pytest.raises(ValueError):
        subject.validate_frozen_environment(2024, env)


def test_rank_source_environment_restores_mapping():
    env = {"TD_LEDGER": "0"}
    with subject.rank_source_environment(env):
        assert env["TD_LEDGER"] == "1"
    assert env["TD_LEDGER"] == "0"
    with pytest.raises(RuntimeError):
        with subject.rank_source_environment(env):
            raise RuntimeError("boom")
    assert env["TD_LEDGER"] == "0"


def test_rank_coupling_is_exact_deterministic_permutation():
    control = np.array([
        [1.0, 3.0, 2.0, 4.0],
        [10.0, 10.0, 12.0, 11.0],
    ], dtype=np.float64)
    source = np.array([
        [40.0, 10.0, 30.0, 20.0],
        [2.0, 2.0, 1.0, 3.0],
    ], dtype=np.float32)
    treatment, audit = subject.rank_couple_final_served(
        control, source, source.copy())
    assert np.array_equal(
        np.sort(treatment, axis=1), np.sort(control, axis=1))
    assert np.array_equal(treatment, np.array([
        [4.0, 1.0, 3.0, 2.0],
        [10.0, 11.0, 10.0, 12.0],
    ]))
    assert audit["exact_sorted_draw_multisets"]
    assert audit["deterministic_output"]
    assert audit["maximum_mean_delta"] == 0.0
    assert audit["changed_rows"] == 2


def test_rank_coupling_rejects_nondeterministic_source():
    control = np.array([[1.0, 2.0, 3.0]])
    source = np.array([[3.0, 2.0, 1.0]])
    repeat = np.array([[1.0, 2.0, 3.0]])
    with pytest.raises(ValueError, match="not bit-exact"):
        subject.rank_couple_final_served(control, source, repeat)
