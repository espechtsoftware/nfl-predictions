"""SBI Workstream B tests (plan §6 + §2.4): prior registry bounds, summary
determinism, the params-injection RNG-parity guarantee, and a fast
truth-recovery smoke.

The golden checksums below were captured from the PRE-params simulate.py
(commit 368a5d4) on the registry's synthetic slate — the byte-identical
proof that adding the ``params`` argument changed nothing when absent.
Same seed, same slate, three env modes. If one of these ever breaks, the
default draw stream moved: that is the 2026-08-05 draw-order regression
class of bug, and the fix is to restore stream order, never to rebase the
hashes without proving the shift is intended.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.models import simulate
from nfl_dfs.research import sbi_params, sbi_summaries

_GOLDEN = {
    # env mode -> sha256 of draws.tobytes(), n_sims=400, seed=123,
    # synthetic_slate(n_games=3, seed=0)
    "default": "98a289de399c532b1ef74e30036f9f65e9149840d56ea36ee71475716a881d62",
    "ledger": "87617d2ae0b6e5ff4a325e4e3fe2161c567cb7e831f264daba3ab7ce7815fa80",
    "ledger+dirichlet": "b8823ccc3b16c2416d4cb57e90c70a696541adb5ff5ed0341e468c75091802da",
}
_ENV_MODES = {
    "default": {},
    "ledger": {"TD_LEDGER": "1"},
    "ledger+dirichlet": {"TD_LEDGER": "1", "GAME_SIM_USAGE": "dirichlet"},
}
_SIM_ENVS = ("TD_LEDGER", "GAME_SIM_USAGE", "GAME_SIM_MODE", "GAME_SIM_PACE")


@pytest.fixture
def slate():
    return sbi_params.synthetic_slate(n_games=3, seed=0)


def _draws(comps, games, teams, monkeypatch, env, **kw):
    for k in _SIM_ENVS:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    res = simulate.simulate(comps, n_sims=400, seed=123, keep_draws=True,
                            game_ids=games, team_ids=teams, **kw)
    return res.draws


# ---------------------------------------------------------------------------
# prior registry
# ---------------------------------------------------------------------------

def test_prior_samples_within_bounds_and_stratified():
    rng = np.random.default_rng(0)
    n = 64
    thetas = sbi_params.sample_prior(rng, n)
    assert thetas.shape == (n, len(sbi_params.REGISTRY))
    for j, spec in enumerate(sbi_params.REGISTRY):
        col = thetas[:, j]
        assert (col >= spec.low).all() and (col <= spec.high).all()
    # Latin-hypercube stratification: exactly one sample per 1/n stratum
    # of the unit cube in every dimension.
    u = sbi_params.to_unit(thetas)
    for j in range(u.shape[1]):
        strata = np.floor(u[:, j] * n).astype(int)
        assert sorted(strata) == list(range(n))


def test_unit_transform_roundtrip():
    rng = np.random.default_rng(1)
    thetas = sbi_params.sample_prior(rng, 16)
    back = sbi_params.from_unit(sbi_params.to_unit(thetas))
    np.testing.assert_allclose(back, thetas, rtol=1e-12)


def test_registry_defaults_match_production_constants():
    by_name = {p.name: p for p in sbi_params.REGISTRY}
    assert by_name["game_factor_sigma"].default == simulate.GAME_FACTOR_SIGMA
    assert by_name["td_alloc_k"].default is None  # exact multinomial
    assert all(p.rationale for p in sbi_params.REGISTRY)


# ---------------------------------------------------------------------------
# RNG parity (plan §2.4 — the CRITICAL guarantee)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", sorted(_GOLDEN))
def test_default_draws_byte_identical_to_pre_params_code(slate, monkeypatch, mode):
    comps, games, teams, _ = slate
    d = _draws(comps, games, teams, monkeypatch, _ENV_MODES[mode])
    assert hashlib.sha256(d.tobytes()).hexdigest() == _GOLDEN[mode]
    # params=None must be indistinguishable from omitting it entirely
    d2 = _draws(comps, games, teams, monkeypatch, _ENV_MODES[mode], params=None)
    assert hashlib.sha256(d2.tobytes()).hexdigest() == _GOLDEN[mode]


def test_params_at_production_values_leave_stream_unchanged(slate, monkeypatch):
    """Overriding with the production values themselves must not shift the
    stream either — same RNG calls, same values."""
    comps, games, teams, _ = slate
    env = _ENV_MODES["ledger+dirichlet"]
    base = _draws(comps, games, teams, monkeypatch, env)
    same = _draws(comps, games, teams, monkeypatch, env,
                  params={"game_factor_sigma": simulate.GAME_FACTOR_SIGMA,
                          "usage_dirichlet_k": 20.0})
    assert np.array_equal(base, same)


def test_each_override_actually_fires(slate, monkeypatch):
    """Vacuity check (validation laws): every registered parameter must
    change the draws when moved off its default under the env mode the
    research harness runs with."""
    comps, games, teams, _ = slate
    env = _ENV_MODES["ledger+dirichlet"]
    base = _draws(comps, games, teams, monkeypatch, env)
    for theta in ({"game_factor_sigma": 0.35},
                  {"usage_dirichlet_k": 5.0},
                  {"td_alloc_k": 4.0}):
        moved = _draws(comps, games, teams, monkeypatch, env, params=theta)
        assert not np.array_equal(base, moved), f"{theta} never fired"


def test_td_alloc_k_preserves_marginal_means(slate, monkeypatch):
    """Dirichlet-multinomial TD allocation must reshape, not shift: each
    player's mean stays put (up to Monte Carlo noise) while realized
    shares get burstier."""
    comps, games, teams, _ = slate
    env = _ENV_MODES["ledger"]
    for k in _SIM_ENVS:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    kw = dict(n_sims=20_000, seed=9, keep_draws=True,
              game_ids=games, team_ids=teams)
    base = simulate.simulate(comps, **kw).draws
    burst = simulate.simulate(comps, params={"td_alloc_k": 4.0}, **kw).draws
    np.testing.assert_allclose(burst.mean(axis=1), base.mean(axis=1),
                               atol=0.5)
    # burstier allocation -> more per-player variance on TD-heavy roles
    assert burst.std(axis=1).mean() > base.std(axis=1).mean()


# ---------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------

def test_summaries_deterministic_given_seed(slate):
    comps, games, teams, roles = slate
    a = sbi_summaries.summarize(
        sbi_params.run_simulator(None, comps, games, teams, n_sims=300, seed=4),
        roles, teams, games)
    b = sbi_summaries.summarize(
        sbi_params.run_simulator(None, comps, games, teams, n_sims=300, seed=4),
        roles, teams, games)
    assert a.equals(b)
    assert not a.isna().any()
    assert (a.index == b.index).all()


def test_summaries_detect_dependence_structure(slate):
    """The joint-structure summaries must sit on the correlated side of
    independence — they are the identifiability channel for the game
    factor and TD ledger. Pair discovery and the tail instrument come
    from research.dependence (instrument #0), so a zero pair count there
    would silently zero these: assert they actually moved."""
    comps, games, teams, roles = slate
    d = sbi_params.run_simulator(None, comps, games, teams, n_sims=4000, seed=6)
    s = sbi_summaries.summarize(d, roles, teams, games)
    assert s["qb_wr1_same_team_corr"] > 0.15  # same-team stack correlation
    assert s["qb_opp_qb_corr"] > 0.05         # shared game environment
    assert s["qb_wr1_tail_lift"] > 1.2        # co-boom above independence
    assert s["team_pass_var_ratio"] > 1.05    # ledger same-event coupling
    # WR1-WR2 sits between the dirichlet usage squeeze (negative) and the
    # shared game factor (positive) — it must at least be weaker than the
    # same-event QB-WR1 coupling.
    assert s["wr1_wr2_same_team_corr"] < s["qb_wr1_same_team_corr"]


# ---------------------------------------------------------------------------
# truth-recovery smoke (2 params, small budget — the full gate is
# scripts/sbi_truth_recovery.py)
# ---------------------------------------------------------------------------

def test_truth_recovery_smoke_two_params():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import sbi_truth_recovery

    results = sbi_truth_recovery.run(
        k_truths=4, n_ref=48, n_sims=250, accept=0.25, n_games=2, seed=3,
        param_names=["game_factor_sigma", "td_alloc_k"], verbose=False)
    assert set(results) == {"game_factor_sigma", "td_alloc_k"}
    for name, r in results.items():
        assert r["verdict"] in ("IDENTIFIABLE", "WEAK", "NOT")
        assert 0.0 <= r["coverage80"] <= 1.0
    # game-factor sigma drives every dispersion/dependence summary; even
    # this tiny budget should show SOME posterior contraction.
    assert results["game_factor_sigma"]["contraction"] < 1.0
