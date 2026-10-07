"""Study 48f's mechanics (offline): the environment classes, the band, the AUC, the frozen week-unit decision rule, and
the fit / score round trip with a missing OWN imputed at the training mean."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import study48f_real_field as S  # noqa: E402


def test_env_classes_follow_the_qbs_game_rank_spread_and_the_top_game_count():
    A = {"pos": np.array(["QB", "RB", "WR", "DST", "QB", "WR"]), "game": np.array(["g1", "g1", "g2", "g2", "g2", "g1"]),
         "spread": np.array([-3.0, 0, 0, 0, 4.0, 0])}
    L = np.array([[0, 1, 2, 3], [4, 5, 2, 3]])
    e = S.env_features(L, A, {"g1": 1, "g2": 2}, "g1", np.array([0, 0, 0, 3200.0, 0, 0]))
    assert e.qb_rank_top.tolist() == [1.0, 0.0] and e.qb_rank_2_3.tolist() == [0.0, 1.0]
    assert e.qb_fav.tolist() == [1.0, 0.0] and e.top_n_1_2.tolist() == [1.0, 1.0] and e.top_n_0.tolist() == [0.0, 0.0]
    assert e.dst_cheap.tolist() == [1.0, 1.0]


def test_band_auc_and_the_week_unit_rule():
    assert S.band_mask(np.arange(10.0)).sum() == 2
    assert S.auc(np.array([1, 2, 3, 4.0]), np.array([0, 0, 1, 1])) == 1.0 and S.auc(np.ones(3), np.zeros(3)) is None
    assert S.decide([0.51, 0.6, 0.52, 0.7]) == "PASS" and S.decide([0.4, 0.45, 0.49, 0.3]) == "WORSE"
    assert S.decide([0.6, 0.6, 0.6, 0.49]) == "NO PASS" and S.decide([0.6, None, 0.6]) == "INCOMPLETE"


def test_fit_and_score_impute_a_missing_own_at_the_training_mean():
    rng = np.random.default_rng(7)
    n = 400
    X = pd.DataFrame({c: rng.normal(size=n) for c in S.FULL})
    X.loc[:199, "own_rank"] = np.nan                                      # two weeks without an ownership source
    y = (X.mates + rng.normal(scale=0.5, size=n) > 1.0).to_numpy()
    m = S.fit_models(X, y)
    assert set(m) == {"SE", "FULL", "SE_NOOWN"} and m["SE"]["features"] == list(S.SE) and "own_rank" not in m["SE_NOOWN"]["features"] and len(m["FULL"]["beta"]) == len(S.FULL) + 1
    own_mu = m["SE"]["mu"][list(S.SE).index("own_rank")]
    assert abs(own_mu - X.own_rank.mean()) < 1e-12
    row = X.iloc[[0]].copy()
    a = S.score(m["SE"], row); row.loc[:, "own_rank"] = own_mu
    assert abs(a[0] - S.score(m["SE"], row)[0]) < 1e-12              # NaN scores as the training mean
    assert m["SE"]["beta"][1 + list(S.SE).index("mates")] > 0


def test_validity_floor_and_the_week_picker():
    good = {"frame_present": True, "fp_proj_present": True, "own_source": "own.csv", "resolved_share": 0.95}
    assert S.week_validity(good, 60) == (True, [])
    ok, why = S.week_validity(dict(good, resolved_share=0.85), 60)
    assert not ok and any("resolved share" in w for w in why)
    ok, why = S.week_validity(dict(good, own_source="none", fp_proj_present=False), 10)
    assert not ok and len(why) == 3
    assert S.pick_weeks({5: True, 6: True, 7: True, 8: True, 9: True}) == [5, 6, 7, 8]          # W9 unused
    assert S.pick_weeks({5: True, 6: False, 7: True, 8: True, 9: True}) == [5, 7, 8, 9]         # W9 replaces W6
    assert S.pick_weeks({5: True, 6: False, 7: False, 8: True, 9: True}) == [5, 8, 9]           # never W10: incomplete
    assert S.decide([0.6, 0.6, 0.6]) == "INCOMPLETE"


def test_the_label_uses_the_whole_field_and_the_band_is_on_the_rows_given():
    ranks = np.array([1, 5, 10, 11, 200])
    assert S.top1_label(ranks, n_all=1000).tolist() == [True, True, True, False, False]     # 1% of 1000 = 10
    assert S.top1_label(ranks, n_all=5).tolist() == [True, False, False, False, False]       # never of the 5 resolved
    proj = np.array([10.0, 9, 8, 7, 6, 5, 4, 3, 2, 1])
    assert S.band_mask(proj).tolist() == [True, True] + [False] * 8
