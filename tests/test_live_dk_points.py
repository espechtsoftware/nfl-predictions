"""Offline tests for scripts/live_dk_points.py (ESPN box score -> DraftKings points)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from live_dk_points import game_points, pa_points, scoring_extras  # noqa: E402


def _summary():
    def cat(name, labels, rows):
        return {"name": name, "labels": labels,
                "athletes": [{"athlete": {"displayName": n, "id": str(i)}, "stats": s} for i, (n, s) in enumerate(rows)]}
    home = {"team": {"abbreviation": "AAA"}, "statistics": [
        cat("passing", ["C/ATT", "YDS", "AVG", "TD", "INT"], [("Qb One", ["20/30", "310", "10.3", "2", "1"])]),
        cat("receiving", ["REC", "YDS", "AVG", "TD", "LONG", "TGTS"], [("Wr One", ["8", "104", "13.0", "1", "40", "10"])]),
        cat("fumbles", ["FUM", "LOST", "REC"], [("Wr One", ["1", "1", "0"])]),
        cat("defensive", ["TOT", "SOLO", "SACKS", "TFL", "PD", "QB HTS", "TD"], [("Lb One", ["5", "3", "2", "1", "0", "2", "1"])]),
        cat("interceptions", ["INT", "YDS", "TD"], [("Cb One", ["1", "50", "1"])])]}
    away = {"team": {"abbreviation": "BBB"}, "statistics": [
        cat("rushing", ["CAR", "YDS", "AVG", "TD", "LONG"], [("Rb Two", ["20", "100", "5.0", "0", "20"])]),
        cat("defensive", ["TOT", "SOLO", "SACKS", "TFL", "PD", "QB HTS", "TD"], [("De Two", ["4", "4", "1.5", "1", "0", "1", "0"])])]}
    return {"header": {"competitions": [{"competitors": [{"team": {"abbreviation": "AAA"}, "score": "27"},
                                                          {"team": {"abbreviation": "BBB"}, "score": "9"}],
                                         "status": {"type": {"name": "STATUS_FINAL"}, "period": 4, "displayClock": "0:00"}}]},
            "boxscore": {"players": [home, away]},
            "scoringPlays": [
                {"team": {"abbreviation": "AAA"}, "type": {"text": "Passing Touchdown"},
                 "text": "Wr One 10 Yd pass from Qb One (Qb One Pass to Wr One for Two-Point Conversion)"},
                {"team": {"abbreviation": "AAA"}, "type": {"text": "Interception Return Touchdown"},
                 "text": "Cb One 50 Yd Interception Return (Kicker Kick)"},
                {"team": {"abbreviation": "BBB"}, "type": {"text": "Safety"}, "text": "Qb One sacked in end zone, SAFETY"},
                {"team": {"abbreviation": "BBB"}, "type": {"text": "Rushing Touchdown"},
                 "text": "Rb Two 1 Yd Rush (Rb Two Run for Two-Point Conversion)"}]}


def test_scoring_extras_counts_return_tds_safeties_and_two_point_conversions():
    tds, saf, two = scoring_extras(_summary())
    assert tds == {"AAA": 1} and saf == {"BBB": 1}
    assert two == {"Qb One": 1, "Wr One": 1, "Rb Two": 1}


def test_game_points_players_and_dst():
    rows, state = game_points(_summary())
    pts = {r["name"]: r["dk_points"] for r in rows}
    # QB: 310*0.04 + 2*4 - 1 + 3 (300 bonus) + 2 (2pt) = 24.4
    assert abs(pts["Qb One"] - 24.4) < 1e-9
    # WR: 8 + 10.4 + 6 + 3 (100 bonus) - 1 (fumble lost) + 2 (2pt) = 28.4
    assert abs(pts["Wr One"] - 28.4) < 1e-9
    # RB: 10 + 3 (100 bonus) + 2 (2pt) = 15
    assert abs(pts["Rb Two"] - 15.0) < 1e-9
    # AAA DST: sacks 2 + INT 2 + 0 opp fumbles + one return TD (counted once, from the scoring plays) 6 + PA 9 -> 4 = 14
    assert pts["AAA DST"] == 14.0
    # BBB DST: sacks 1.5 + opp fumbles lost 1 x 2 + safety 2 + PA 27 -> 0 = 5.5
    assert pts["BBB DST"] == 5.5
    assert state["status"] == "STATUS_FINAL"


def test_points_allowed_tiers():
    assert [pa_points(x) for x in (0, 3, 7, 14, 21, 28, 35)] == [10.0, 7.0, 4.0, 1.0, 0.0, -1.0, -4.0]
