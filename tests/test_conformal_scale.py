"""CQR sigma-scale mechanism (external review 3.1): neutral without
data, calibrated with it, clipped at the guardrails."""
import numpy as np
import pandas as pd

from nfl_dfs.models import conformal


def _mock(monkeypatch, frame):
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df", lambda sql, **kw: frame)


def test_neutral_when_thin(monkeypatch):
    _mock(monkeypatch, pd.DataFrame({"proj_points": [10.0] * 5,
                                     "proj_std": [4.0] * 5,
                                     "actual": [11.0] * 5}))
    assert conformal.sigma_scale(2026, 4) == 1.0


def test_calibrates_underdispersed_projections(monkeypatch):
    rng = np.random.default_rng(2)
    n = 400
    mu, sd = 12.0, 5.0
    actual = mu + rng.normal(0, sd * 1.4, n)  # true sigma 40% wider than stated
    _mock(monkeypatch, pd.DataFrame({"proj_points": [mu] * n,
                                     "proj_std": [sd] * n,
                                     "actual": actual}))
    s = conformal.sigma_scale(2026, 4)
    assert 1.15 < s < 1.75


def test_disabled_by_env(monkeypatch):
    monkeypatch.setenv("CQR_CONF", "0")
    assert conformal.sigma_scale(2026, 4) == 1.0
