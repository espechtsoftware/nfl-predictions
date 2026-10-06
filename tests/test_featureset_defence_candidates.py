"""O-22 co-run arm D: the seven as-of opponent-defence columns are registered candidates, so EXTRA_FEATURES adds them
(a name EXTRA_FEATURES does not recognise is silently dropped -- the arm would train the control's model). Offline."""
import pandas as pd

from nfl_dfs.models import featureset as F

DEFENCE = ["epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6", "rz_td_rate_allowed_l6", "qb_fp_allowed_adj_l6",
           "rb_fp_allowed_adj_l6", "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6"]


def test_the_default_model_is_unchanged(monkeypatch):
    monkeypatch.delenv("EXTRA_FEATURES", raising=False); monkeypatch.delenv("DROP_FEATURES", raising=False)
    assert F._active_numeric_features() == list(F.NUMERIC_FEATURES)
    assert not set(DEFENCE) & set(F.NUMERIC_FEATURES)


def test_arm_d_adds_exactly_the_seven_columns(monkeypatch):
    monkeypatch.delenv("DROP_FEATURES", raising=False)
    monkeypatch.setenv("EXTRA_FEATURES", ",".join(DEFENCE))
    active = F._active_numeric_features()
    assert active == list(F.NUMERIC_FEATURES) + DEFENCE
    X = F.build_X(pd.DataFrame({"position": ["WR"], **{c: [1.0] for c in DEFENCE}}))
    assert set(DEFENCE) <= set(X.columns) and list(X.columns[:-1]) == sorted(active)    # sorted (Addendum 34)


def test_arm_b_drops_the_two_leaky_features(monkeypatch):
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    monkeypatch.setenv("DROP_FEATURES", "qb_cpoe_l6,neutral_pass_rate_l6")
    active = F._active_numeric_features()
    assert "qb_cpoe_l6" not in active and "neutral_pass_rate_l6" not in active
    assert len(active) == len(F.NUMERIC_FEATURES) - 2
