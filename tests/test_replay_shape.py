

def test_tabpfn_marginals_maps_and_preserves_ranks(monkeypatch):
    """TABPFN_MARGINALS: draws remap onto the cached per-player quantile
    curve; rank order (the correlation carrier) is preserved; uncached
    rows keep their original draws."""
    import numpy as np
    import pandas as pd

    from nfl_dfs.backtest import replay

    rng = np.random.default_rng(3)
    draws = rng.gamma(2.0, 5.0, size=(2, 500)).astype(np.float32)
    keys = pd.DataFrame({"season": [2025, 2025], "week": [1, 1],
                         "gsis_id": ["A", "MISSING"]})
    cache = pd.DataFrame([{
        "season": 2025, "week": 1, "gsis_id": "A", "mean": 12.0,
        "q01": 0.5, "q05": 2.0, "q10": 4.0, "q50": 11.0,
        "q90": 24.0, "q95": 29.0, "q99": 38.0}])
    monkeypatch.setattr(replay, "query_df", None, raising=False)
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df", lambda sql, **kw: cache)
    out = replay._tabpfn_marginals(draws, keys)
    r0, o0 = draws[0], out[0]
    assert (np.argsort(r0) == np.argsort(o0)).all(), "rank order preserved"
    assert abs(np.quantile(o0, 0.5) - 11.0) < 1.5
    assert abs(np.quantile(o0, 0.9) - 24.0) < 2.5
    assert (out[1] == draws[1]).all(), "uncached row untouched"
    assert (out >= 0).all()
