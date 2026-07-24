"""Walk-forward hyperparameter tuning with Optuna (guide §7.5).

Optional: requires the `tuning` extra. 150 trials on 40k rows runs in a
few minutes on a laptop — every fold is walk-forward, so the tuned params
are honest by construction.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from .featureset import LGB_THREADS, build_X
from .validation import walk_forward_folds
from .weights import sample_weights


def tune(
    panel: pd.DataFrame,
    label: str,
    objective: str = "tweedie",
    n_trials: int = 150,
    min_train_seasons: int = 4,
) -> dict:
    """Return the best LightGBM params for `label` by mean walk-forward MAE."""
    import optuna  # tuning extra

    folds, _test = walk_forward_folds(
        sorted(panel.season.unique()), min_train_seasons=min_train_seasons
    )

    def _objective(trial: "optuna.Trial") -> float:
        params = dict(
            num_threads=LGB_THREADS,
            objective=objective,
            learning_rate=trial.suggest_float("lr", 0.01, 0.1, log=True),
            num_leaves=trial.suggest_int("leaves", 15, 63),
            min_data_in_leaf=trial.suggest_int("min_leaf", 20, 200),
            feature_fraction=trial.suggest_float("ff", 0.5, 1.0),
            lambda_l2=trial.suggest_float("l2", 0.1, 20.0, log=True),
            verbosity=-1,
        )
        if objective == "tweedie":
            params["tweedie_variance_power"] = trial.suggest_float("tvp", 1.1, 1.9)
        maes = []
        for train_seasons, val_season in folds:
            tr = panel[panel.season.isin(train_seasons)]
            va = panel[panel.season == val_season]
            model = lgb.train(
                params,
                lgb.Dataset(build_X(tr), tr[label],
                            weight=sample_weights(tr, val_season),
                            categorical_feature=["position"]),
                num_boost_round=2000,
                valid_sets=[lgb.Dataset(build_X(va), va[label])],
                callbacks=[lgb.early_stopping(100, verbose=False)],
            )
            maes.append(float(np.abs(model.predict(build_X(va)) - va[label]).mean()))
        return float(np.mean(maes))

    study = optuna.create_study(direction="minimize")
    study.optimize(_objective, n_trials=n_trials)
    return study.best_params
