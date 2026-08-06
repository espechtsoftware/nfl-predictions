"""Ensemble-member disagreement exposure (scoring plan §5.2, §11.4).

Epistemic spread is disagreement about the MEAN — distinct from the
aleatoric outcome variance the simulator samples. It must be exposed
without changing the averaged prediction, and its ABSENCE must be
visible (empty), never silently zero.
"""
import numpy as np
import pandas as pd

from nfl_dfs.models.components import _EnsembleBooster


class _Stub:
    def __init__(self, offset):
        self.offset = offset

    def feature_name(self):
        return ["a", "b"]

    def predict(self, X):
        return X["a"].to_numpy() + self.offset


def test_members_exposed_without_changing_average():
    ens = _EnsembleBooster([_Stub(-1.0), _Stub(0.0), _Stub(1.0)])
    X = pd.DataFrame({"a": [10.0, 20.0], "b": [0.0, 0.0]})
    avg = ens.predict(X)
    assert np.allclose(avg, [10.0, 20.0]), "averaging changed"
    P = ens.predict_members(X)
    assert P.shape == (3, 2)
    assert np.allclose(P.mean(axis=0), avg)


def test_spread_measures_disagreement_not_level():
    tight = _EnsembleBooster([_Stub(0.0), _Stub(0.0), _Stub(0.0)])
    loose = _EnsembleBooster([_Stub(-4.0), _Stub(0.0), _Stub(4.0)])
    X = pd.DataFrame({"a": [10.0], "b": [0.0]})
    sd_t, rg_t = tight.predict_spread(X)
    sd_l, rg_l = loose.predict_spread(X)
    assert sd_t[0] == 0.0 and rg_t[0] == 0.0
    assert sd_l[0] > 3.0 and rg_l[0] == 8.0
    # identical means, different disagreement — the whole point
    assert tight.predict(X)[0] == loose.predict(X)[0]


def test_single_model_reports_unavailable_not_zero():
    """A non-ensemble booster has no spread; component_spread must omit
    the columns so callers see 'unavailable' rather than 0.0."""
    class _Single(_Stub):
        pass

    m = _Single(0.0)
    assert not hasattr(m, "predict_spread")
