"""TD event ledger (TD_LEDGER=1, review #5): Sol's validation gates.
Gate 1: player marginal TD means unchanged (mean-preserving).
Gate 2: QB pass-TDs and teammate rec-TDs positively correlated under
the ledger, ~zero without.
Gate 3: joint QB+catcher boom frequency rises.
Only after these does the six-season panel arbitrate."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models.simulate import _td_event_ledger, simulate


def _mk_comps():
    # one game, two teams: QB + 3 receivers each (+ a RB with no rec)
    rows = []
    for team in ("A", "B"):
        rows.append(dict(team=team, pos="QB", targets=0.0, catch_rate=0.0,
                         ypr=0.0, rec_tds=0.0, carries=3.0, ypc=4.0,
                         rush_tds=0.05, pass_attempts=34.0, ypa=7.2,
                         pass_tds=1.8, interceptions=0.8))
        for k, (tg, td) in enumerate(((9.0, 0.55), (7.0, 0.45), (5.0, 0.3))):
            rows.append(dict(team=team, pos=f"WR{k}", targets=tg,
                             catch_rate=0.65, ypr=11.0, rec_tds=td,
                             carries=0.0, ypc=0.0, rush_tds=0.0,
                             pass_attempts=0.0, ypa=0.0, pass_tds=0.0,
                             interceptions=0.0))
    return pd.DataFrame(rows)


def test_ledger_preserves_marginal_means():
    comps = _mk_comps()
    rng = np.random.default_rng(0)
    team_codes = pd.factorize(comps.team)[0]
    gm = np.ones((len(comps), 40_000))
    rec, pas = _td_event_ledger(
        rng, comps.rec_tds.to_numpy(), comps.pass_tds.to_numpy(),
        team_codes, gm, 40_000)
    for i in range(len(comps)):
        if comps.rec_tds[i] > 0:
            assert rec[i].mean() == pytest.approx(comps.rec_tds[i], rel=0.05)
        if comps.pass_tds[i] > 0:
            assert pas[i].mean() == pytest.approx(comps.pass_tds[i], rel=0.05)


def test_ledger_creates_qb_receiver_covariance(monkeypatch):
    comps = _mk_comps()
    team_codes = pd.factorize(comps.team)[0]
    gm = np.ones((len(comps), 30_000))
    rng = np.random.default_rng(1)
    rec_l, pas_l = _td_event_ledger(
        rng, comps.rec_tds.to_numpy(), comps.pass_tds.to_numpy(),
        team_codes, gm, 30_000)
    # ledger: QB row 0, his WR1 row 1 — same-event coupling
    corr_l = np.corrcoef(pas_l[0], rec_l[1])[0, 1]
    # independent baseline
    rng2 = np.random.default_rng(2)
    pas_i = rng2.poisson(comps.pass_tds[0], 30_000)
    rec_i = rng2.poisson(comps.rec_tds[1], 30_000)
    corr_i = np.corrcoef(pas_i, rec_i)[0, 1]
    assert corr_l > 0.25, f"ledger corr too weak: {corr_l:.3f}"
    assert abs(corr_i) < 0.05


def test_ledger_raises_joint_boom_rate():
    comps = _mk_comps()
    team_codes = pd.factorize(comps.team)[0]
    gm = np.ones((len(comps), 30_000))
    rec_l, pas_l = _td_event_ledger(
        np.random.default_rng(3), comps.rec_tds.to_numpy(),
        comps.pass_tds.to_numpy(), team_codes, gm, 30_000)
    joint_l = np.mean((pas_l[0] >= 3) & (rec_l[1] >= 2))
    rng = np.random.default_rng(4)
    joint_i = np.mean((rng.poisson(comps.pass_tds[0], 30_000) >= 3)
                      & (rng.poisson(comps.rec_tds[1], 30_000) >= 2))
    assert joint_l > joint_i * 1.5, f"{joint_l:.4f} vs {joint_i:.4f}"


def test_simulate_env_gate_and_mean_parity(monkeypatch):
    comps = _mk_comps()
    kw = dict(n_sims=25_000, seed=5, keep_draws=True,
              game_ids=pd.Series(["g1"] * len(comps)),
              team_ids=comps.team)
    base = simulate(comps.drop(columns=["team", "pos"]), **kw)
    monkeypatch.setenv("TD_LEDGER", "1")
    led = simulate(comps.drop(columns=["team", "pos"]), **kw)
    # DK-point means must agree (mean-preserving surgery)
    mb = base.summary["proj_points"].to_numpy()
    ml = led.summary["proj_points"].to_numpy()
    assert np.allclose(mb, ml, rtol=0.06, atol=0.35), f"{mb} vs {ml}"
    # and the QB/WR1 joint p95 tail must be fatter under the ledger
    qb_wr_base = base.draws[0] + base.draws[1]
    qb_wr_led = led.draws[0] + led.draws[1]
    assert np.percentile(qb_wr_led, 99) >= np.percentile(qb_wr_base, 99)
