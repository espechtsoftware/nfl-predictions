import numpy as np
import pytest

from nfl_dfs.models.scoring import StatLine, dk_points


def test_wr_line_with_bonus():
    # 8 rec, 112 yds, 1 TD: 8 + 11.2 + 6 + 3 (100+ bonus) = 28.2
    s = StatLine(receptions=8, rec_yards=112, rec_tds=1)
    assert dk_points(s) == pytest.approx(28.2)


def test_qb_line_with_300_bonus():
    # 320 pass yds, 3 TD, 1 INT: 12.8 + 12 + 3 - 1 = 26.8
    s = StatLine(pass_yards=320, pass_tds=3, interceptions=1)
    assert dk_points(s) == pytest.approx(26.8)


def test_bonus_thresholds_are_inclusive():
    assert dk_points(StatLine(rec_yards=100)) == pytest.approx(13.0)
    assert dk_points(StatLine(rec_yards=99.9)) == pytest.approx(9.99)
    assert dk_points(StatLine(rush_yards=100)) == pytest.approx(13.0)
    assert dk_points(StatLine(pass_yards=300)) == pytest.approx(15.0)


def test_negative_events():
    s = StatLine(fumbles_lost=2, interceptions=1)
    assert dk_points(s) == pytest.approx(-3.0)


def test_vectorized():
    s = StatLine(
        rec_yards=np.array([50.0, 105.0]),
        receptions=np.array([4, 9]),
        rec_tds=np.array([0, 2]),
    )
    pts = dk_points(s)
    assert pts.shape == (2,)
    assert pts[0] == pytest.approx(9.0)
    assert pts[1] == pytest.approx(9 + 10.5 + 12 + 3)
