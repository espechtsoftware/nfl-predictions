import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine, field, payout


def make_slate(seed=41, season=2023, week=5, n_teams=8, proj_quality=1.0):
    """Synthetic slate where projections carry real (imperfect) signal."""
    rng = np.random.default_rng(seed)
    rows = []
    pid = 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        game = f"G{t // 2}"
        for pos, n in (("QB", 2), ("RB", 4), ("WR", 5), ("TE", 3), ("DST", 1)):
            for i in range(n):
                base = {"QB": 19, "RB": 13, "WR": 11, "TE": 8, "DST": 7}[pos]
                mu = max(1.0, base - 2.5 * i + rng.normal(0, 2))
                actual = max(0.0, rng.normal(mu, 6))
                proj = mu + rng.normal(0, 3 / proj_quality)
                rows.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": game,
                    "salary": int(np.clip(2600 + mu * 330 + rng.normal(0, 250),
                                          2500, 9600)),
                    "proj": proj, "actual": actual,
                    "season": season, "week": week,
                })
                pid += 1
    return pd.DataFrame(rows)


def test_payout_curves():
    c = payout.double_up(entry_fee=5, field_size=1000)
    assert c.payout_for_rank(1) == 10
    assert c.payout_for_rank(450) == 10
    assert c.payout_for_rank(451) == 0

    g = payout.gpp(entry_fee=5, field_size=100_000)
    assert g.payout_for_rank(1) == 100_000  # 20000x
    assert g.payout_for_rank(100_000) == 0
    # Payout is monotone non-increasing in rank
    ranks = [1, 10, 100, 1000, 5000, 14_000, 20_000]
    pays = [g.payout_for_rank(r) for r in ranks]
    assert pays == sorted(pays, reverse=True)


def test_roi():
    assert payout.roi(np.array([10.0, 0.0]), entry_fee=5) == 0.0
    assert payout.roi(np.array([0.0, 0.0]), entry_fee=5) == -1.0


def test_naive_ownership_favors_value():
    slate = make_slate()
    own = field.naive_ownership(slate)
    wrs = slate[slate.pos == "WR"]
    w = own[wrs.index.to_numpy()]
    value = (wrs.proj / wrs.salary).to_numpy()
    assert np.corrcoef(w, value)[0, 1] > 0.3
    # Weights normalize within position
    assert w.sum() == pytest.approx(1.0, abs=1e-6)


def test_sample_field_valid_lineups():
    slate = make_slate()
    fld = field.sample_field(slate, n_lineups=300, seed=1)
    assert len(fld) > 250
    salaries = slate.salary.to_numpy()
    positions = slate.pos.to_numpy()
    for lu in fld:
        assert len(lu) == 9
        assert len(set(lu)) == 9
        pos_counts = pd.Series(positions[lu]).value_counts()
        assert pos_counts.get("QB", 0) == 1
        assert pos_counts.get("DST", 0) == 1
        assert 2 <= pos_counts.get("RB", 0) <= 3
        assert salaries[lu].sum() <= field.SALARY_CAP


def test_sample_field_drops_every_infeasible_random_attempt():
    slate = make_slate()
    slate["salary"] = 10_000

    sampled = field.sample_field(slate, n_lineups=25, seed=7)

    assert sampled == []


def test_leakage_guard_rejects_answer_key():
    slate = make_slate()
    slate["proj"] = slate["actual"]
    with pytest.raises(AssertionError):
        engine.leakage_guard(slate)


def test_run_week_and_summary():
    slate = make_slate()
    contest = payout.double_up(entry_fee=5, field_size=1000)
    wk = engine.run_week(slate, contest, n_entries=3, field_size=400, seed=2)
    assert wk is not None
    assert len(wk.lineup_scores) == 3
    assert all(0 <= p <= 1 for p in wk.percentiles)

    result = engine.BacktestResult(weeks=[wk], contest=contest)
    text = result.summary()
    assert "ROI" in text and "2023" in text


def test_good_projections_beat_random_in_percentile():
    """A model with signal should finish better against the field than a
    model projecting pure noise."""
    contest = payout.double_up(entry_fee=5, field_size=1000)

    def median_pct(proj_quality, seed):
        pcts = []
        for wkseed in range(4):
            slate = make_slate(seed=100 + wkseed, week=wkseed + 1,
                               proj_quality=proj_quality)
            if proj_quality < 0.01:  # destroy the signal entirely
                rng = np.random.default_rng(seed + wkseed)
                slate["proj"] = rng.permutation(slate["proj"].to_numpy())
            wk = engine.run_week(slate, contest, n_entries=3, field_size=400,
                                 seed=3)
            pcts.extend(wk.percentiles)
        return float(np.median(pcts))

    sharp = median_pct(proj_quality=2.0, seed=0)
    noise = median_pct(proj_quality=0.001, seed=1)
    assert sharp < noise, f"sharp {sharp:.2f} should finish above noise {noise:.2f}"


def test_sharp_field_entrants():
    from nfl_dfs.backtest import field as field_sim

    slate = make_slate()
    sharp = field_sim.sharp_field(slate, n_lineups=50, n_distinct=6, seed=2)
    assert len(sharp) == 50
    salaries = slate["salary"].to_numpy()
    pos = slate["pos"].to_numpy()
    for lu in sharp[:10]:
        assert len(lu) == 9 and len(set(lu)) == 9
        assert salaries[lu].sum() <= field_sim.SALARY_CAP
        assert (pos[lu] == "QB").sum() == 1 and (pos[lu] == "DST").sum() == 1
    # Duplication is expected: far fewer distinct lineups than entries
    assert len({tuple(sorted(lu)) for lu in sharp}) <= 12


def test_sample_field_sharp_fraction():
    from nfl_dfs.backtest import field as field_sim

    slate = make_slate()
    fld = field_sim.sample_field(slate, n_lineups=100, seed=3, sharp_fraction=0.2)
    assert len(fld) >= 95  # random part may drop a few infeasible attempts


def test_model_ensemble_averages_and_differs(monkeypatch, panel):
    """MODEL_ENSEMBLE=3: members trained on shuffled column orders
    average into predictions that differ from the single model (the
    order-luck dimension is real) while staying finite and same-shape."""
    import numpy as np

    from nfl_dfs.models import components

    season = int(panel.season.max())
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    single = components.train(panel, target_season=season,
                              num_boost_round=20)
    rows = panel[panel.season == season].head(50)
    p1 = single.predict_components(rows)
    monkeypatch.setenv("MODEL_ENSEMBLE", "3")
    ens = components.train(panel, target_season=season,
                           num_boost_round=20)
    p3 = ens.predict_components(rows)
    assert p1.shape == p3.shape
    assert np.isfinite(p3.to_numpy(float)).all()
    assert not np.allclose(p1.targets, p3.targets), \
        "ensemble should differ from the single draw"


def test_registry_roundtrips_ensemble(tmp_path, monkeypatch, panel):
    """MODEL_ENSEMBLE adoption requires the weekly-retrain registry to
    persist and reload K-member ensembles transparently."""
    import numpy as np

    from nfl_dfs.models import components, registry

    monkeypatch.setenv("MODEL_ENSEMBLE", "3")
    season = int(panel.season.max())
    cm = components.train(panel, target_season=season, num_boost_round=15)
    ens = cm.models["targets"]
    meta = registry.ModelMeta(
        scope="test", label="comp_targets", iso_week="2026-W31",
        params={}, features=[], train_seasons=[2020], metrics={})
    registry.save(ens, meta, str(tmp_path))
    loaded, _ = registry.load(str(tmp_path), "test", "comp_targets", "2026-W31")
    rows = panel[panel.season == season].head(30)
    from nfl_dfs.models.featureset import build_X

    X = build_X(rows)
    a = ens.predict(X[ens.feature_name()])
    b = loaded.predict(X[loaded.feature_name()])
    assert np.allclose(a, b), "reloaded ensemble must predict identically"
