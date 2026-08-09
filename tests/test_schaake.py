import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.schaake import (apply_schaake, apply_schaake_game,
                                      build_game_bank)
from nfl_dfs.research.conditional_schaake import (
    FOREST_ROLES, cloud_smoke as conditional_cloud_smoke,
    evaluate_dependence_panel, fit_conditional_template_forest)
from nfl_dfs.research import schaake_diag
from nfl_dfs.research.schaake_diag import realized_dependence_scores


def test_game_shuffle_is_an_exact_marginal_permutation():
    n = 1000
    draws = np.vstack([np.arange(n, dtype=float),
                       np.arange(n, dtype=float) + 10_000])
    templates = pd.DataFrame({
        "QB_a": [0.1, 0.2, 0.3, 0.4],
        "WR1_a": [0.2, 0.3, 0.4, 0.5],
    })
    out = apply_schaake_game(
        draws, pd.Series(["QB", "WR1"]), np.array(["A", "A"]),
        templates, seed=1,
    )
    for before, after in zip(draws, out):
        assert np.array_equal(np.sort(before), np.sort(after))
        assert len(np.unique(after)) == n


def test_weighted_game_shuffle_is_an_exact_marginal_permutation():
    rng = np.random.default_rng(101)
    draws = rng.normal(size=(4, 1001))
    templates = pd.DataFrame({
        "QB_fav": [0.1, 0.4, 0.8],
        "WR1_fav": [0.2, 0.5, 0.9],
        "QB_dog": [0.2, 0.6, 0.7],
        "WR1_dog": [0.1, 0.3, 0.8],
    })
    out = apply_schaake_game(
        draws, pd.Series(["QB", "WR1", "QB", "WR1"]),
        np.array(["A", "A", "B", "B"]), templates, seed=11,
        team_values=np.array([25.0, 25.0, 20.0, 20.0]),
        template_probabilities=np.array([0.05, 0.15, 0.8]))
    assert all(np.array_equal(np.sort(a), np.sort(b))
               for a, b in zip(draws, out))


def test_default_game_shuffle_keeps_legacy_integer_sampling():
    draws = np.vstack([np.arange(101, dtype=float),
                       np.arange(101, dtype=float) + 1000])
    templates = pd.DataFrame({
        "QB_a": [0.1, 0.5, 0.9],
        "WR1_a": [0.2, 0.6, 0.8],
    })
    seed = 29
    actual = apply_schaake_game(
        draws, pd.Series(["QB", "WR1"]), np.array(["A", "A"]),
        templates, seed=seed)

    rng = np.random.default_rng(seed)
    picked = rng.integers(0, len(templates), size=draws.shape[1])
    tie_break = rng.permutation(draws.shape[1])
    expected = draws.copy()
    for row, column in enumerate(("QB_a", "WR1_a")):
        ranks = templates[column].to_numpy()[picked]
        order = np.lexsort((tie_break, ranks))
        quantiles = np.empty(draws.shape[1], dtype=int)
        quantiles[order] = np.arange(draws.shape[1])
        expected[row] = np.sort(draws[row])[quantiles]
    assert np.array_equal(actual, expected)


def test_conditional_forest_favors_matching_context_without_leakage():
    rng = np.random.default_rng(31)
    rows = []
    for season, group in ((2023, 0), (2024, 1), (2025, 1)):
        for index in range(60):
            row = {
                "season": season,
                "game_total": 40.0 + 12.0 * group + rng.normal(0, 0.2),
                "spread_abs": 2.0 + group,
            }
            for role_index, role in enumerate(FOREST_ROLES):
                row[role] = np.clip(
                    0.15 + 0.7 * group + 0.002 * role_index
                    + rng.normal(0, 0.01), 0.001, 0.999)
            rows.append(row)
    fitted = fit_conditional_template_forest(
        pd.DataFrame(rows), target_season=2025, seed=41,
        n_estimators=60, min_samples_leaf=5, rff_dim=24)
    # The target season is never allowed into the fitted template support.
    assert fitted.templates.season.max() == 2024
    weights = fitted.weights({"game_total": 52.0, "spread_abs": 3.0})
    assert np.isclose(weights.sum(), 1.0)
    assert weights[fitted.templates.season.eq(2024)].sum() > 0.8
    assert fitted.diagnostics(weights)["effective_templates"] > 1


def _dependence_report(season, production=(0.20, 0.030),
                       forest=(0.19, 0.029)):
    return {
        "season": season,
        "template_mode": "forest",
        "marginal_exact": True,
        "required_pairs_complete": True,
        "production": {
            "n_pairs": 100, "variogram": production[0],
            "tail_brier": production[1],
        },
        "schaake": {
            "n_pairs": 100, "variogram": forest[0],
            "tail_brier": forest[1],
        },
    }


def test_dependence_panel_gate_enforces_aggregate_and_season_stability():
    reports = [_dependence_report(season)
               for season in (2023, 2024, 2025)]
    passing = evaluate_dependence_panel(reports)
    assert passing["checks"]["passes"]
    assert passing["disposition"] == "dependence-gate-passes"

    unstable = reports[:2] + [_dependence_report(
        2025, production=(0.20, 0.030), forest=(0.25, 0.040))]
    failed = evaluate_dependence_panel(unstable)
    assert not failed["checks"]["no_season_worsens_both"]
    assert not failed["checks"]["passes"]


def test_dependence_panel_gate_requires_frozen_seasons():
    with pytest.raises(ValueError, match="seasons mismatch"):
        evaluate_dependence_panel([
            _dependence_report(2023), _dependence_report(2024),
        ])


def test_legacy_shuffle_is_an_exact_marginal_permutation():
    rng = np.random.default_rng(2)
    draws = rng.normal(size=(2, 401))
    templates = pd.DataFrame({"QB": [0.1, 0.5, 0.9],
                              "WR1": [0.2, 0.6, 0.8]})
    out = apply_schaake(draws, pd.Series(["QB", "WR1"]),
                        pd.Series(["A", "A"]), templates, seed=3)
    assert all(np.array_equal(np.sort(x), np.sort(y))
               for x, y in zip(draws, out))


def test_realized_scores_prefer_matching_dependence():
    rng = np.random.default_rng(4)
    n = 5000
    common = rng.normal(size=n)
    matched = np.vstack([common, common + rng.normal(0, 0.1, n)])
    independent = rng.normal(size=(2, n))
    meta = pd.DataFrame({"game_id": ["g", "g"], "team": ["A", "A"],
                         "role": ["QB", "WR1"]})
    # A jointly high realization should receive a better tail forecast from
    # the positively dependent arm.
    actual = np.array([2.0, 2.0])
    good = realized_dependence_scores(matched, actual, meta)
    bad = realized_dependence_scores(independent, actual, meta)
    assert good["tail_brier"] < bad["tail_brier"]


def test_game_bank_orients_sides_by_implied_total():
    rows = []
    for team, implied, qb in (("ZZZ", 27.0, 30.0), ("AAA", 20.0, 12.0)):
        rows.append({"season": 2024, "week": 1, "game_id": "g",
                     "team": team, "role": "QB", "dk_points": qb,
                     "implied_team_total": implied})
    bank = build_game_bank(pd.DataFrame(rows))
    # ZZZ is alphabetically last but is still the semantic favorite side.
    assert bank.QB_fav.iloc[0] > bank.QB_dog.iloc[0]


def test_whole_season_gate_emits_each_week_and_uses_all_role_pairs(
        monkeypatch, caplog):
    rows = []
    for week in (1, 2):
        for team in ("A", "B"):
            for pos, salary, actual in (("QB", 7000, 20.0),
                                        ("WR", 6500, 16.0),
                                        ("WR", 5200, 11.0)):
                rows.append({"season": 2025, "week": week,
                             "game_id": f"g{week}", "team": team,
                             "position": pos, "salary": salary,
                             "y_dk_points": actual,
                             "game_total": 47.0, "spread": 3.0,
                             "implied_team_total": (25.0 if team == "A"
                                                    else 22.0)})
    frame = pd.DataFrame(rows)
    rng = np.random.default_rng(9)
    draws = rng.normal(15, 5, size=(len(frame), 500))
    bank = pd.DataFrame({
        "season": [2024] * 4, "week": [1, 2, 3, 4],
        "game_id": ["h1", "h2", "h3", "h4"],
        "game_total": [44.0, 46.0, 48.0, 50.0],
        "spread_abs": [2.0, 3.0, 4.0, 5.0],
        "QB_fav": [0.2, 0.4, 0.6, 0.8],
        "WR1_fav": [0.3, 0.5, 0.7, 0.9],
        "WR2_fav": [0.1, 0.4, 0.6, 0.9],
        "QB_dog": [0.1, 0.3, 0.7, 0.9],
        "WR1_dog": [0.2, 0.4, 0.8, 0.9],
        "WR2_dog": [0.1, 0.5, 0.7, 0.8],
    })
    monkeypatch.setattr(schaake_diag, "_BANK", bank)
    monkeypatch.setenv("SCHAAKE_DIAG_STRICT", "1")
    caplog.set_level("INFO")
    report = schaake_diag.log_dependence_ab(frame, draws)
    assert report["weeks"] == 2
    assert report["required_pairs_complete"]
    assert report["marginal_exact"]
    assert all(report["production"]["by_pair"][key]["n"] > 0
               for key in schaake_diag.REQUIRED_PAIR_KEYS)
    assert sum("schaake-week " in r.message for r in caplog.records) == 2


def test_whole_season_gate_supports_conditional_forest_mode(monkeypatch):
    rows = []
    for week in (1, 2):
        for team in ("A", "B"):
            for pos, salary, actual in (("QB", 7000, 20.0),
                                        ("RB", 6800, 17.0),
                                        ("RB", 5100, 10.0),
                                        ("WR", 6500, 16.0),
                                        ("WR", 5200, 11.0),
                                        ("WR", 4100, 8.0),
                                        ("TE", 3900, 9.0)):
                rows.append({
                    "season": 2025, "week": week,
                    "game_id": f"g{week}", "team": team,
                    "position": pos, "salary": salary,
                    "y_dk_points": actual,
                    "game_total": 47.0, "spread": 3.0,
                    "pace_env_l6": 64.0,
                    "neutral_pass_rate_l6": 0.58,
                    "team_top2_target_share_l6": 0.43,
                    "implied_team_total": (25.0 if team == "A" else 22.0),
                })
    frame = pd.DataFrame(rows)
    rng = np.random.default_rng(91)
    draws = rng.normal(15, 5, size=(len(frame), 300))
    bank_rows = []
    for index in range(80):
        record = {
            "season": 2024, "week": index % 18 + 1,
            "game_id": f"h{index}",
            "game_total": 40.0 + index % 12,
            "spread_abs": 1.0 + index % 6,
            "pace_env_l6": 61.0 + index % 8,
            "neutral_pass_rate_l6": 0.5 + (index % 10) / 100,
            "team_top2_target_share_l6": 0.35 + (index % 9) / 100,
        }
        for role_index, role in enumerate(FOREST_ROLES):
            record[role] = (
                (index + 2 * role_index) % 79 + 1) / 80.0
        bank_rows.append(record)
    monkeypatch.setattr(schaake_diag, "_BANK", pd.DataFrame(bank_rows))
    monkeypatch.setenv("SCHAAKE_TEMPLATE_MODE", "forest")
    report = schaake_diag.log_dependence_ab(frame, draws)
    assert report["template_mode"] == "forest"
    assert report["marginal_exact"]
    assert report["forest"]["templates"] == 80
    assert report["forest"]["seed"] == 8162
    assert report["forest"]["mean_effective_templates"] > 1


def test_game_seeds_are_distinct_and_image_smoke_passes():
    assert (schaake_diag._stable_game_seed(2025, 1, "g1")
            != schaake_diag._stable_game_seed(2025, 1, "g2"))
    assert schaake_diag.cloud_smoke()["status"] == "PASS"
    assert conditional_cloud_smoke()["status"] == "PASS"
