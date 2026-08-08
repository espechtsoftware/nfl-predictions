import lightgbm as lgb
import numpy as np
import pandas as pd

from nfl_dfs.models import monitoring, registry


def _tiny_model():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300)})
    y = X.a * 2 + rng.normal(0, 0.1, 300)
    return lgb.train({"objective": "regression", "verbosity": -1},
                     lgb.Dataset(X, y), num_boost_round=10)


def test_registry_roundtrip(tmp_path):
    model = _tiny_model()
    meta = registry.ModelMeta(
        scope="pooled", label="dk_points", iso_week="2025-W10",
        params={"objective": "regression"}, features=["a", "b"],
        train_seasons=[2023, 2024], metrics={"mae": 1.23},
    )
    version = registry.save(model, meta, str(tmp_path))
    assert version == "pooled/dk_points/2025-W10"

    loaded, loaded_meta = registry.load(str(tmp_path), "pooled", "dk_points", "2025-W10")
    assert loaded_meta.metrics["mae"] == 1.23
    X = pd.DataFrame({"a": [1.0], "b": [0.0]})
    np.testing.assert_allclose(loaded.predict(X), model.predict(X))


def test_registry_latest_week(tmp_path):
    model = _tiny_model()
    for wk in ("2025-W09", "2025-W11", "2025-W10"):
        registry.save(model, registry.ModelMeta("pooled", "dk_points", wk), str(tmp_path))
    assert registry.latest_iso_week(str(tmp_path), "pooled", "dk_points") == "2025-W11"


def test_registry_metadata_reads_ensemble_member_params():
    """Weekly training registers the adopted wrapper, not a raw Booster."""
    class _Member:
        def __init__(self, seed):
            self.params = {"objective": "poisson", "seed": seed}

    class _Ensemble:
        members = [_Member(9000), _Member(9001), _Member(9002)]

    params = registry.model_params(_Ensemble())
    assert params["model_type"] == "ensemble"
    assert params["ensemble_size"] == 3
    assert [m["params"]["seed"] for m in params["members"]] == [9000, 9001, 9002]


def test_mae_drift_alarm():
    assert monitoring.check_mae(training_mae=5.0, recent_mae=7.0) is not None
    assert monitoring.check_mae(training_mae=5.0, recent_mae=5.5) is None


def test_coverage_alarms():
    rng = np.random.default_rng(1)
    y = rng.normal(15, 5, 5000)
    good = monitoring.check_coverage(y, np.quantile(y, 0.1) * np.ones(5000),
                                     np.quantile(y, 0.9) * np.ones(5000))
    assert good == []
    bad = monitoring.check_coverage(y, np.quantile(y, 0.3) * np.ones(5000),
                                    np.quantile(y, 0.7) * np.ones(5000))
    assert len(bad) == 2


def test_psi_detects_shift():
    rng = np.random.default_rng(2)
    base = rng.normal(0, 1, 5000)
    assert monitoring.psi(base, rng.normal(0, 1, 5000)) < 0.05
    assert monitoring.psi(base, rng.normal(1.5, 1, 5000)) > 0.2


def test_null_rate_alarm():
    train = pd.DataFrame({"f": np.random.default_rng(3).normal(size=1000)})
    live = pd.DataFrame({"f": [np.nan] * 300 + list(np.random.default_rng(4).normal(size=700))})
    alarms = monitoring.check_feature_drift(train, live, ["f"])
    assert any(a.kind == "null_rate" for a in alarms)
