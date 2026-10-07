"""scripts/o40_dvp_confirmatory.py (O-40's frozen confirmatory rule): the weekly equal-weighted position rank
correlation, the week-resampled pooled lower bound, and the three-part PASS rule. Offline (the training runs need GCP)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import o40_dvp_confirmatory as O  # noqa: E402


def _rows(seed=0, weeks=4, n=12):
    rng = np.random.default_rng(seed)
    out = []
    for w in range(1, weeks + 1):
        for pos in O.POSITIONS:
            y = rng.normal(10, 5, n)
            out += [{"week": w, "position": pos, "y": y[i], "good": y[i] + rng.normal(0, 1), "bad": rng.normal(10, 5)} for i in range(n)]
    return pd.DataFrame(out)


def test_weekly_rank_corr_weights_positions_equally_and_skips_small_groups():
    d = _rows()
    good, bad = O.weekly_rank_corr(d, "good"), O.weekly_rank_corr(d, "bad")
    assert len(good) == 4 and (good > bad).all() and good.between(-1, 1).all()
    one = d[d.week == 1]
    want = np.mean([pd.Series(g.good.values).corr(pd.Series(g.y.values), method="spearman") for _, g in one.groupby("position")])
    assert abs(good.loc[1] - want) < 1e-12
    small = d[~((d.position == "TE") & (d.index % 12 >= 5))]                 # TE groups of 5 < MIN_GROUP drop out
    s = O.weekly_rank_corr(small, "good")
    want3 = np.mean([pd.Series(g.good.values).corr(pd.Series(g.y.values), method="spearman")
                     for p, g in small[small.week == 1].groupby("position") if p != "TE"])
    assert abs(s.loc[1] - want3) < 1e-12


def test_pooled_lower_bound_is_deterministic_and_below_the_mean():
    diffs = {2020: pd.Series([0.01, 0.02, 0.00, 0.03]), 2021: pd.Series([0.02, -0.01, 0.01]), 2022: pd.Series([0.0, 0.01])}
    p1, l1 = O.pooled_lower_bound(diffs, b=2000); p2, l2 = O.pooled_lower_bound(diffs, b=2000)
    assert (p1, l1) == (p2, l2) and abs(p1 - np.mean([0.01, 0.02, 0.0, 0.03, 0.02, -0.01, 0.01, 0.0, 0.01])) < 1e-12 and l1 < p1


def test_the_three_part_rule():
    mae = {2020: (5.0, 5.0), 2021: (5.0, 5.04), 2022: (5.0, 5.0)}
    assert O.decide({2020: 0.01, 2021: 0.02, 2022: -0.01}, 0.001, mae)[0] == "PASS"
    v, why = O.decide({2020: 0.01, 2021: -0.02, 2022: -0.01}, 0.001, mae); assert v == "NOT PASS" and why[0].startswith("(1)")
    v, why = O.decide({2020: 0.01, 2021: 0.02, 2022: 0.01}, -0.0001, mae); assert v == "NOT PASS" and why[0].startswith("(2)")
    v, why = O.decide({2020: 0.01, 2021: 0.02, 2022: 0.01}, 0.001, {**mae, 2022: (5.0, 5.06)})
    assert v == "NOT PASS" and why[0].startswith("(3)") and "2022" in why[0]


def test_an_empty_extra_features_is_exactly_the_base_and_unregistered_extras_never_enter(monkeypatch):
    """The reviewer 10-07: BASE_R runs with EXTRA_FEATURES="" and must be exactly the repaired base."""
    from nfl_dfs.models import featureset as FS
    monkeypatch.delenv("DROP_FEATURES", raising=False)
    monkeypatch.delenv("EXTRA_FEATURES", raising=False); unset = FS._active_numeric_features()
    monkeypatch.setenv("EXTRA_FEATURES", ""); empty = FS._active_numeric_features()
    assert empty == unset == list(FS.NUMERIC_FEATURES)
    monkeypatch.setenv("EXTRA_FEATURES", "not_a_registered_column"); assert FS._active_numeric_features() == list(FS.NUMERIC_FEATURES)


def test_smoke_refuses_decision_seasons_and_drop_features_refuses(monkeypatch, capsys):
    for season in (2020, 2021, 2022, 2026):
        assert O.main(["--smoke-target", str(season)]) == 2
    monkeypatch.setenv("DROP_FEATURES", "x")
    assert O.main([]) == 2 and "DROP_FEATURES" in capsys.readouterr().err


def test_dropped_groups_counts_small_week_position_groups():
    d = _rows(weeks=2, n=12)
    assert O.dropped_groups(d) == 0
    assert O.dropped_groups(d[~((d.week == 1) & (d.position == "TE") & (d.index % 12 >= 3))]) == 1
