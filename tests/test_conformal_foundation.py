"""Offline tests for Workstream E (online conformal) and Workstream F
(foundation shadow harness). Synthetic data only; no network — the
chronos challenger path is never exercised here."""
import importlib.util
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.online_conformal import (
    CalibrationState,
    OnlineConformalCalibrator,
    conformal_risk_control,
    interval_score,
    scale_knob_tail_losses,
    tail_overstatement_loss,
)

_FS_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "foundation_shadow.py"
_spec = importlib.util.spec_from_file_location("foundation_shadow", _FS_PATH)
fs = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("foundation_shadow", fs)
_spec.loader.exec_module(fs)


# ---------------------------------------------------------------------------
# Workstream E: append-only state
# ---------------------------------------------------------------------------

def test_append_only_invariant():
    st = CalibrationState()
    for i in range(10):
        st.append(f"2026w{i:02d}", {"position": "WR"}, float(i))
    before = st.fingerprint(10)
    for i in range(10, 20):
        st.append(f"2026w{i:02d}", {"position": "RB"}, float(i))
    # Earlier prefix is byte-identical after further appends.
    assert st.fingerprint(10) == before
    assert len(st) == 20
    # The exposed view is immutable and there is no mutation surface.
    recs = st.records
    with pytest.raises(TypeError):
        recs[0] = None
    assert not hasattr(st, "remove")


def test_timestamps_must_not_go_backwards():
    st = CalibrationState()
    st.append("2026w05", {"position": "WR"}, 1.0)
    with pytest.raises(ValueError):
        st.append("2026w04", {"position": "WR"}, 2.0)
    st.append("2026w05", {"position": "TE"}, 3.0)  # equal is fine (same slate)


def test_state_json_round_trip():
    st = CalibrationState()
    st.append("2026w01", {"position": "WR", "role_class": "starter"}, -0.4)
    st.append("2026w02", {"position": "RB"}, 1.7)
    st2 = CalibrationState.from_json(st.to_json())
    assert st2.fingerprint() == st.fingerprint()


# ---------------------------------------------------------------------------
# Workstream E: coverage and adaptation
# ---------------------------------------------------------------------------

def _run_stream(cal, sigmas, rng, q_raw=1.0):
    """Feed y ~ N(0, sigma_t) with fixed raw quantiles (+-q_raw). Returns
    per-step coverage indicators."""
    covered = []
    for t, s in enumerate(sigmas):
        y = rng.normal(0, s)
        _, cov = cal.update(
            {"position": "WR"}, y, -q_raw, 0.0, q_raw, timestamp=f"t{t:06d}"
        )
        covered.append(cov)
    return np.asarray(covered, dtype=float)


def test_iid_coverage_hits_target():
    # Raw +-1 interval on N(0,1) covers only ~68%; conformal must lift it
    # to the 90% target.
    rng = np.random.default_rng(3)
    cal = OnlineConformalCalibrator(target_coverage=0.9, learning_rate=0.02,
                                    min_group_size=30, max_window=1000)
    cov = _run_stream(cal, np.ones(3000), rng)
    assert abs(cov[1000:].mean() - 0.9) < 0.025


def test_adapts_after_distribution_shift():
    # Variance doubles mid-stream. The adaptive calibrator (windowed
    # scores + ACI feedback) must restore near-target coverage; a frozen
    # control (no feedback, unwindowed) under-covers in the new regime.
    sigmas = np.concatenate([np.ones(1500), 2.0 * np.ones(1500)])
    adaptive = OnlineConformalCalibrator(target_coverage=0.9, learning_rate=0.05,
                                         min_group_size=30, max_window=300)
    control = OnlineConformalCalibrator(target_coverage=0.9, learning_rate=0.0,
                                        min_group_size=30, max_window=None)
    cov_a = _run_stream(adaptive, sigmas, np.random.default_rng(11))
    cov_c = _run_stream(control, sigmas, np.random.default_rng(11))
    tail_a, tail_c = cov_a[-500:].mean(), cov_c[-500:].mean()
    assert abs(tail_a - 0.9) < 0.04, f"adaptive post-shift coverage {tail_a}"
    assert abs(tail_a - 0.9) < abs(tail_c - 0.9), (tail_a, tail_c)


def test_fallback_hierarchy():
    cal = OnlineConformalCalibrator(min_group_size=30)
    # 50 WR-starter scores, 40 TE-starter scores, nothing else.
    for i in range(50):
        cal.state.append("2026w01", {"position": "WR", "role_class": "starter"}, i / 50)
    for i in range(40):
        cal.state.append("2026w01", {"position": "TE", "role_class": "starter"}, i / 40)
    # Position has enough data -> most specific level wins.
    level, value, scores = cal.resolve({"position": "WR", "role_class": "starter"})
    assert (level, value, len(scores)) == ("position", "WR", 50)
    # RB has no position data but the shared role class qualifies.
    level, value, scores = cal.resolve({"position": "RB", "role_class": "starter"})
    assert (level, value, len(scores)) == ("role_class", "starter", 90)
    # Unknown role falls through to global (90 total >= 30).
    level, value, scores = cal.resolve({"position": "RB", "role_class": "backup"})
    assert (level, len(scores)) == ("global", 90)
    # With a higher floor nothing qualifies: raw quantiles pass through.
    strict = OnlineConformalCalibrator(min_group_size=1000, state=cal.state)
    out = strict.interval({"position": "RB", "role_class": "backup"}, 1.0, 2.0, 3.0)
    assert (out.level, out.delta, out.lo, out.hi) == ("none", 0.0, 1.0, 3.0)


def test_correction_is_order_preserving():
    cal = OnlineConformalCalibrator(min_group_size=10)
    # Strongly negative scores => the correction wants to narrow hard.
    for i in range(50):
        cal.state.append("2026w01", {"position": "WR"}, -100.0)
    out = cal.interval({"position": "WR"}, q_lo=5.0, q_mid=8.0, q_hi=12.0)
    assert out.lo <= out.mid <= out.hi
    assert out.mid == 8.0  # median untouched
    with pytest.raises(ValueError):
        cal.interval({"position": "WR"}, 3.0, 2.0, 1.0)  # unordered input


def test_interval_score_sign():
    assert interval_score(5.0, -1.0, 1.0) == 4.0   # above the interval
    assert interval_score(0.0, -1.0, 1.0) == -1.0  # inside: negative


# ---------------------------------------------------------------------------
# Workstream E: conformal risk control
# ---------------------------------------------------------------------------

def test_risk_control_scale_knob():
    # Claimed upper-tail probability under Normal(0, scale); true tail
    # P(y > 1.2816) = 0.10. Shrinking the scale shrinks the claim, so the
    # overstatement loss is monotone along the descending-scale grid.
    rng = np.random.default_rng(5)
    n = 4000
    y = rng.normal(0, 1, n)
    scales = [2.0, 1.5, 1.2, 1.0, 0.8, 0.6]
    losses = scale_knob_tail_losses(np.zeros(n), np.ones(n), 1.2816, y, scales)
    res = conformal_risk_control(scales, losses, target_risk=0.06)
    assert res.satisfied
    assert res.achieved_bound <= 0.06
    # Must not jump straight to the most conservative knob.
    assert 0 < res.chosen_index < len(scales) - 1
    # Risks really are non-increasing.
    assert all(a >= b - 1e-12 for a, b in zip(res.risks, res.risks[1:]))


def test_risk_control_rejects_non_monotone_loss():
    losses = np.array([[0.1, 0.5], [0.1, 0.5]])  # risk increases with lambda
    with pytest.raises(ValueError, match="monotone"):
        conformal_risk_control([1.0, 2.0], losses, target_risk=0.5)


def test_risk_control_unsatisfiable_flagged():
    losses = np.full((100, 2), 0.9)
    res = conformal_risk_control([1.0, 0.5], losses, target_risk=0.1)
    assert not res.satisfied


def test_tail_overstatement_loss_bounds():
    loss = tail_overstatement_loss([0.3, 0.3, 0.0], [0.0, 1.0, 0.0])
    assert loss.tolist() == [0.3, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Workstream F: harness (baselines only — no network, chronos untouched)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synth_preds():
    df = fs.synthetic_usage_sequences(n_players=15, n_weeks=20, seed=3)
    preds, notes = fs.run_walk_forward(df, challengers=())
    return df, preds, notes


def test_synthetic_generator_shape():
    df = fs.synthetic_usage_sequences(n_players=6, n_weeks=10, seed=1)
    assert set(df.columns) == {"player_id", "t", "y"}
    assert len(df) == 60
    assert (df.y >= 0).all()
    assert df.groupby("player_id").t.is_monotonic_increasing.all()


def test_walk_forward_no_lookahead(synth_preds):
    # The last-value forecaster's median at time t must equal y_{t-1}
    # exactly — proof the history slice excludes the target week.
    df, preds, _ = synth_preds
    last = preds[preds.method == "last"]
    y_by = {(r.player_id, r.t): r.y for r in df.itertuples()}
    for r in last.itertuples():
        assert r.q50 == y_by[(r.player_id, r.t - 1)]


def test_all_baselines_and_monotone_quantiles(synth_preds):
    _, preds, _ = synth_preds
    assert set(preds.method) == {"last", "roll4", "ewm", "kalman"}
    assert (preds.q10 <= preds.q50).all() and (preds.q50 <= preds.q90).all()
    assert (preds.q10 >= 0).all()
    assert np.isfinite(preds[["q10", "q50", "q90"]].to_numpy()).all()


def test_summary_table_buckets(synth_preds):
    _, preds, _ = synth_preds
    table = fs.summarize(preds)
    assert {"all", "h1-2", "h3-5", "h6-10", "h11-+"} <= set(table.bucket)
    assert (table.n > 0).all()
    assert np.isfinite(table[["mae", "pinball10", "pinball50", "pinball90"]].to_numpy()).all()
    assert (table[["pinball10", "pinball50", "pinball90"]].to_numpy() >= 0).all()


def test_chronos_never_imported_without_request(synth_preds):
    _, _, notes = synth_preds
    assert notes["chronos"].startswith("not requested")
    assert "chronos" not in sys.modules  # guarded import held
    assert "tabfm" in notes  # access status always reported


def test_csv_mode_round_trip(tmp_path):
    df = fs.synthetic_usage_sequences(n_players=4, n_weeks=6, seed=2)
    # Season/week ordering variant.
    df2 = df.rename(columns={"t": "week"}).assign(season=2026)
    p = tmp_path / "seq.csv"
    df2[["player_id", "season", "week", "y"]].to_csv(p, index=False)
    loaded = fs.load_csv_sequences(str(p))
    assert set(loaded.columns) == {"player_id", "t", "y"}
    assert len(loaded) == len(df)
    preds, _ = fs.run_walk_forward(loaded)
    assert len(preds) > 0
