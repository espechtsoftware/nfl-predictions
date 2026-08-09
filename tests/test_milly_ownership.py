import pandas as pd
import numpy as np

from nfl_dfs.research.milly_ownership import (
    diagnostic_gate,
    join_milly_truth,
    mark_scope_eligibility,
    normalize_name,
    ownership_join_key,
    parse_field_size,
    select_main_milly_contests,
)


def _contest(contest_id: str, name: str, *, season: int = 2025,
             week: int = 5, players: int = 120) -> list[dict]:
    rows = []
    positions = ["QB"] * 10 + ["DST"] * 10 + ["RB"] * (players - 20)
    # 10% per QB/DST -> one roster slot each; remaining ownership brings the
    # total to nine roster slots.
    other = 700.0 / (players - 20)
    for i, pos in enumerate(positions):
        rows.append({
            "season": season,
            "week": week,
            "contest_id": contest_id,
            "contest_name": name,
            "display_name": f"Player {contest_id} {i}",
            "roster_position": pos,
            "pct_drafted": 10.0 if pos in {"QB", "DST"} else other,
        })
    return rows


def test_name_normalization_and_dst_aliases():
    assert normalize_name(None) == ""
    assert normalize_name(float("nan")) == ""
    assert normalize_name("Brian Robinson Jr.") == "BRIANROBINSON"
    assert ownership_join_key("Commanders", "DST") == "DST_WAS"
    assert ownership_join_key("anything", "DST", "LAC") == "DST_LAC"
    assert ownership_join_key("D.J. Moore", "WR") == "PLAYER_WR_DJMOORE"


def test_main_milly_selector_excludes_alternate_and_chooses_largest_field():
    main = "NFL $2.75M Fantasy Football Millionaire [$1M] [161764 entries, $20.0]"
    high = "NFL $2.75M Fantasy Football Millionaire [$1M] [5505 entries, $555.0]"
    thursday = (
        "NFL $2.75M Fantasy Football Millionaire [$1M] (Thu) "
        "[300000 entries, $20.0]")
    rows = _contest("main", main) + _contest("high", high) + _contest("thu", thursday)
    chosen = select_main_milly_contests(pd.DataFrame(rows))
    assert chosen.contest_id.tolist() == ["main"]
    assert parse_field_size(main) == 161764


def test_null_feature_names_are_unmatched_without_key_collision():
    contest_name = (
        "NFL $2M Fantasy Football Millionaire [$1M] [100000 entries, $20.0]")
    contests = pd.DataFrame([{
        "season": 2025, "week": 1, "contest_id": "c",
        "contest_name": contest_name, "field_size": 100000, "own_sum": 10.0,
    }])
    ownership = pd.DataFrame([{
        "season": 2025, "week": 1, "contest_id": "c",
        "contest_name": contest_name, "display_name": "Real Player",
        "roster_position": "WR", "pct_drafted": 10.0,
    }])
    features = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "missing-a", "name": None,
         "pos": "WR", "team": "A"},
        {"season": 2025, "week": 1, "id": "missing-b", "name": None,
         "pos": "WR", "team": "B"},
        {"season": 2025, "week": 1, "id": "real", "name": "Real Player",
         "pos": "WR", "team": "C"},
    ])
    joined, coverage = join_milly_truth(features, ownership, contests)
    assert joined.id.tolist() == ["real"]
    assert coverage.mass_coverage.tolist() == [1.0]


def test_diagnostic_gate_requires_both_comparators_and_two_seasons():
    rows = []
    values = {
        2023: (3.0, .80, 3.2, .79, 3.3, .78),
        2024: (3.0, .80, 3.1, .79, 3.2, .78),
        2025: (3.2, .77, 3.1, .78, 3.3, .76),
        "aggregate": (3.0, .80, 3.2, .78, 3.3, .77),
    }
    for season, vals in values.items():
        for method, mae, spearman in (
            ("contest_aware", vals[0], vals[1]),
            ("all_contest", vals[2], vals[3]),
            ("naive", vals[4], vals[5]),
        ):
            rows.append({
                "season": season, "method": method,
                "mae": mae, "spearman": spearman,
            })
    gate = diagnostic_gate(pd.DataFrame(rows), 0.95)
    assert gate["passes"] is True
    assert gate["season_pass_count"] == 2


def test_diagnostic_gate_rejects_low_mass_coverage():
    rows = []
    for season in (2023, 2024, 2025, "aggregate"):
        rows.extend([
            {"season": season, "method": "contest_aware", "mae": 2.0,
             "spearman": .8},
            {"season": season, "method": "all_contest", "mae": 3.0,
             "spearman": .7},
            {"season": season, "method": "naive", "mae": 4.0,
             "spearman": .6},
        ])
    gate = diagnostic_gate(pd.DataFrame(rows), 0.89)
    assert gate["passes"] is False
    assert gate["ownership_mass_coverage_at_least_90pct"] is False


def test_scope_eligibility_excludes_only_2022_christmas_mismatch():
    coverage = pd.DataFrame([
        {"season": 2022, "week": 15, "mass_coverage": .97},
        {"season": 2022, "week": 16, "mass_coverage": 0.0},
        {"season": 2022, "week": 17, "mass_coverage": .96},
    ])
    marked = mark_scope_eligibility(coverage)
    assert marked.scope_eligible.tolist() == [True, False, True]
    assert "Saturday" in marked.scope_exclusion_reason.iloc[1]


def test_replay_milly_predictions_are_normalized_within_position(monkeypatch):
    from nfl_dfs.backtest import replay
    from nfl_dfs.research import milly_ownership

    frame = pd.DataFrame({
        "season": [2025] * 4,
        "week": [1] * 4,
        "pos": ["QB", "QB", "WR", "WR"],
        "salary": [7000, 6000, 7000, 6000],
        "proj": [20.0, 18.0, 20.0, 18.0],
    })
    monkeypatch.setattr(milly_ownership, "build_features", lambda f: f)
    monkeypatch.setattr(
        milly_ownership, "predict_contest_model",
        lambda model, f: np.array([30.0, 10.0, 20.0, 20.0]))
    out = replay._model_ownership(("milly", object()), frame)
    assert np.allclose(out, [.75, .25, .5, .5])
