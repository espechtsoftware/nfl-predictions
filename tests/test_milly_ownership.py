import pandas as pd

from nfl_dfs.research.milly_ownership import (
    diagnostic_gate,
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
    assert normalize_name("Brian Robinson Jr.") == "BRIANROBINSON"
    assert ownership_join_key("Commanders", "DST") == "DST_WAS"
    assert ownership_join_key("anything", "DST", "LAC") == "DST_LAC"
    assert ownership_join_key("D.J. Moore", "WR") == "PLAYER_DJMOORE"


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
