"""September machinery, pre-built: entry import + dupe-calibration math.

All offline — synthetic fixtures stand in for the standings exports that
only exist in-season (and purge from DK in ~4 days)."""

import numpy as np
import pandas as pd

from nfl_dfs.ingest.ownership_import import parse_entries_csv, parse_standings_csv
from nfl_dfs.ops import field_calibration as fc


def _standings_csv(tmp_path):
    # DK's shape: entry block left, player summary right (same file)
    df = pd.DataFrame({
        "Rank": [1, 2, 3, 4],
        "EntryId": ["e1", "e2", "e3", "e4"],
        "EntryName": ["a", "b", "c", "d"],
        "TimeRemaining": [0] * 4,
        "Points": [180.2, 175.0, 175.0, 160.1],
        "Lineup": [
            "QB Jalen Hurts RB Bijan Robinson WR AJ Brown TE Dallas Goedert DST Eagles WR X One WR Y Two RB Z Three FLEX W Four",
            "QB Jalen Hurts RB Bijan Robinson WR AJ Brown TE Dallas Goedert DST Eagles WR X One WR Y Two RB Z Three FLEX W Four",
            "QB Josh Allen RB James Cook WR Khalil Shakir TE Dalton Kincaid DST Bills WR X One WR Y Two RB Z Three FLEX W Four",
            "QB Josh Allen RB James Cook WR Khalil Shakir TE Dalton Kincaid DST Bills WR A Five WR Y Two RB Z Three FLEX W Four",
        ],
        "Player": ["Jalen Hurts", "Josh Allen", "AJ Brown", None],
        "Roster Position": ["QB", "QB", "WR", None],
        "%Drafted": ["50%", "50%", "25%", None],
        "FPTS": [30.0, 28.0, 20.0, None],
    })
    p = tmp_path / "contest-standings-123.csv"
    df.to_csv(p, index=False)
    return p


def test_entries_parsed_and_keyed(tmp_path):
    p = _standings_csv(tmp_path)
    e = parse_entries_csv(p)
    assert len(e) == 4
    # dupes: rows 1&2 identical lineups -> same players_key
    dupes = e.groupby("players_key").size().sort_values(ascending=False)
    assert dupes.iloc[0] == 2 and len(dupes) == 3
    # slot tokens stripped, names sorted
    assert "QB" not in dupes.index[0] and "FLEX" not in dupes.index[0]
    assert e.n_players.eq(9).all()
    assert e.is_top20.all()
    assert e.lineup_slots_json.str.contains('"slot": "QB"').all()
    # ownership block still parses from the same file
    own = parse_standings_csv(p)
    assert len(own) == 3 and own.pct_drafted.max() == 50.0


def test_dupe_correlation_math():
    real = pd.DataFrame({"players_key": ["a", "b", "c"],
                         "count": [10, 5, 1], "best_rank": [1, 2, 3]})
    sim = pd.DataFrame({"players_key": ["a", "b"], "sim_count": [200, 100]})
    res = fc.dupe_correlation(real, sim, n_entries=1000, n_sims=20_000)
    # rescale: 200*(1000/20000)=10, 100*..=5, missing->0; corr([10,5,1],[10,5,0])
    assert res["match_rate"] == 2 / 3
    assert res["dupe_corr"] > 0.95


def test_independence_baseline():
    entries = pd.DataFrame({"players_key": ["A|B", "A|B", "C|D"],
                            "rank": [1, 2, 3]})
    own = pd.Series({"A": 0.5, "B": 0.4, "C": 0.1, "D": 0.02})
    b = fc.independence_baseline(entries, own)
    ab = b[b.players_key == "A|B"].iloc[0]
    assert ab["count"] == 2 and abs(ab.indep_expected - 0.5 * 0.4 * 3) < 1e-9


def test_salary_leftover_skips_unpriced():
    entries = pd.DataFrame({"players_key": ["A|B", "A|Z"]})
    left = fc.salary_leftover(entries, {"A": 30_000, "B": 19_500}, cap=50_000)
    assert list(left) == [500.0]
