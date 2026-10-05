"""Study 22a frozen reader (scripts/study22a_report.py): synthetic smokes required before freezing (prereg §7)."""
import importlib.util
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("study22a_report", ROOT / "scripts" / "study22a_report.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
PREREG = ROOT / "reports" / "2026-10-05-prereg-study22a-residual-calibration.md"


def _panel(rng, *, h1_effect=0.0, h5_effect=0.0, n_weeks=17):
    """An analysis-ready frame (eligible rows with predictors) with planted effects on the miss."""
    rows = []
    for s in R.SEASONS:
        for w in range(1, n_weeks + 1):
            for pos, n in R.TOP_N.items():
                for i in range(n):
                    rows.append((s, w, f"{s}-{pos}-{i}", pos))
    d = pd.DataFrame(rows, columns=["season", "week", "gsis_id", "pos"])
    d["salary"] = rng.integers(3000, 9000, len(d))
    d["mean_projection"] = rng.normal(12, 4, len(d)).clip(1)
    d["model_points_pre"] = d.mean_projection + rng.normal(0, 1, len(d))
    for h in ("h1", "h2", "h3", "h4"):
        d[h] = rng.normal(0, 1, len(d))
    d.loc[~d.week.isin(R.H2_WEEKS), "h2"] = np.nan
    v = d.mean_projection / (d.salary / 1000)
    q = v.groupby([d.season, d.week, d.pos]).transform(lambda x: x.quantile(0.9))
    d["h5"] = (v >= q).astype(float); d["h5_model"] = d.h5
    noise = rng.normal(0, 6, len(d))
    d["actual"] = d.mean_projection + noise + h1_effect * 6 * d.h1 + h5_effect * d.h5
    return d


def test_printed_level_matches_the_prereg_sentence():
    text = PREREG.read_text()
    assert "1 − 0.05/5, i.e. a **99% interval**" in text
    assert R.LEVEL_TEXT == "99% interval" and abs(R.ALPHA - 0.01) < 1e-12
    assert (R.B_FROZEN, R.SEED) == (20_000, 20261005) and "B = 20,000, seed 20261005" in text
    assert R.TOP_N == {"QB": 24, "RB": 48, "WR": 72, "TE": 24} and "(QB 24, RB 48, WR 72, TE 24)" in text
    assert R.H2_WEEKS == (2, 3, 4, 5) and R.SUPPORT_FLOOR == 500


def test_planted_effects_are_recovered_and_a_null_is_not_confirmed():
    rng = np.random.default_rng(1)
    d = _panel(rng, h1_effect=0.25, h5_effect=-2.0)
    support = {h: True for h in ("h1", "h2", "h3", "h4", "h5")}
    out = R.analyse(d, support, B=200, seed=7)
    assert re.search(r"H1 last season's defence vs position: estimate \+0\.\d+.*-> CONFIRMED", out)
    assert re.search(r"H5 top value decile.*-> CONFIRMED", out)
    assert re.search(r"H3 most recent played game's DK points: .*-> NOT CONFIRMED", out)
    assert "two-sided 99% interval (alpha 0.010 = 0.05/5)" in out
    null = R.analyse(_panel(np.random.default_rng(2)), support, B=200, seed=7)
    assert "CONFIRMED" not in null.replace("NOT CONFIRMED", "")


def test_the_opposite_sign_reads_opposite_and_unsupported_is_never_tested():
    d = _panel(np.random.default_rng(3), h1_effect=-0.25)
    out = R.analyse(d, {"h1": True, "h2": False, "h3": True, "h4": True, "h5": True}, B=200, seed=7)
    assert re.search(r"H1 .*-> OPPOSITE", out)
    assert "H2 early-season defence vs position (weeks 2-5): UNSUPPORTED (census) -- not tested" in out


def test_fingerprint_is_deterministic_and_the_read_is_reproducible():
    d = _panel(np.random.default_rng(4))
    s = {h: True for h in ("h1", "h2", "h3", "h4", "h5")}
    assert R.analyse(d, s, B=100, seed=7) == R.analyse(d.sample(frac=1, random_state=1), s, B=100, seed=7)


def test_eligibility_takes_top_n_by_projection_and_fails_closed_on_duplicates():
    rows = [(2023, 3, f"q{i}", "QB", "KC", "LAR", 6000, 30 - i, 25.0, True) for i in range(30)]
    panel = pd.DataFrame(rows, columns=["season", "week", "gsis_id", "pos", "team", "opp", "salary",
                                        "mean_projection", "model_points_pre", "has_actual"])
    d = R.eligible(panel)
    assert len(d) == 24 and set(d.gsis_id) == {f"q{i}" for i in range(24)} and set(d.opp) == {"LA"}
    with pytest.raises(SystemExit, match="FAIL-CLOSED"):
        R.eligible(pd.concat([panel, panel.iloc[:1]]))


def test_predictors_are_point_in_time():
    d = pd.DataFrame({"season": [2023, 2023, 2023], "week": [2, 6, 9], "gsis_id": ["p1", "p1", "p1"],
                      "pos": ["WR"] * 3, "team": ["KC"] * 3, "opp": ["BUF", "BUF", "BUF"], "salary": [6000] * 3,
                      "mean_projection": [15.0] * 3, "model_points_pre": [14.0] * 3})
    ws = pd.DataFrame([  # (season, week, player_id, pos, team, opp, dk)
        (2022, 5, "x", "WR", "MIA", "BUF", 30.0), (2022, 6, "y", "WR", "NE", "BUF", 10.0),   # BUF 2022: 20 per game
        (2023, 1, "z", "WR", "NYJ", "BUF", 40.0),                                              # BUF 2023 wk1: 40
        (2023, 5, "w", "WR", "NYJ", "BUF", 4.0),                                               # after week 2
        (2023, 1, "p1", "WR", "KC", "DET", 11.0), (2023, 7, "p1", "WR", "KC", "DEN", 22.0),    # p1: byes 2-6, 8
    ], columns=["season", "week", "player_id", "pos", "team", "opp", "dk"])
    sal = pd.DataFrame({"season": [2023], "week": [6], "gsis_id": ["p1"], "salary_delta_wow": [300]})
    out = R.add_predictors(d, ws, sal)
    assert list(out.h1) == [20.0, 20.0, 20.0]                       # last season only
    assert out.h2.iloc[0] == 40.0 and np.isnan(out.h2.iloc[1])     # weeks < W of this season; W 6 is outside 2-5
    assert list(out.h3) == [11.0, 11.0, 22.0]                      # the most recent PLAYED game, across byes
    assert out.h4.iloc[1] == 300 and np.isnan(out.h4.iloc[0])
