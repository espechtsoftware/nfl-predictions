"""Weekly retrain (guide §7.8): full retrain every Tuesday with the
completed week added — training is cheap and incremental updates
accumulate drift. Every component model lands in the registry under the
current ISO week with its metrics sidecar.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from ..bq import query_df
from ..config import current_season, settings
from . import baseline, components, registry
from .featureset import FEATURES

log = logging.getLogger(__name__)

SCOPE = "pooled"


def _registry_root() -> str:
    return f"gs://{settings.gcs_bucket}/{settings.model_registry_prefix}"


def _iso_week(today: date | None = None) -> str:
    iso = (today or date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def training_panel() -> pd.DataFrame:
    from .featureset import active_training_rows

    panel = query_df(
        f"""
        SELECT * FROM `{settings.features}.player_week_training`
        WHERE season >= {settings.train_first_season}
          AND position IN ('QB', 'RB', 'WR', 'TE')
        """
    )
    return active_training_rows(panel)


def train_and_register(today: date | None = None) -> str:
    """Retrain the component models on everything up to now, validate the
    baseline walk-forward for the metrics sidecar, and register every
    booster under this ISO week. Returns the model version prefix."""
    panel = training_panel()
    season = current_season(today)
    iso_week = _iso_week(today)
    train_seasons = sorted(int(s) for s in panel.season.unique() if s < season + 1)

    wf = baseline.walk_forward(panel)
    metrics = {
        str(val): {"mae": rep.mae, "market_mae": rep.market_mae,
                   "beats_market": rep.beats_market}
        for val, rep in wf.fold_reports.items()
    }
    log.info("Walk-forward folds: %s", metrics)

    cm = components.train(panel, target_season=season + 1)
    root = _registry_root()
    for name, booster in cm.models.items():
        registry.save(
            booster,
            registry.ModelMeta(
                scope=SCOPE,
                label=f"comp_{name}",
                iso_week=iso_week,
                params=registry.model_params(booster),
                features=FEATURES,
                train_seasons=train_seasons,
                metrics=metrics,
            ),
            root,
        )
    version = f"{SCOPE}/components/{iso_week}"
    log.info("Registered %d component models as %s", len(cm.models), version)
    return version


def load_latest_component_models() -> tuple[components.ComponentModels, str]:
    """Latest registered component set + its version string, for inference."""
    root = _registry_root()
    iso_week = registry.latest_iso_week(root, SCOPE, "comp_targets")
    models = {
        name: registry.load(root, SCOPE, f"comp_{name}", iso_week)[0]
        for name in components.COMPONENT_NAMES
    }
    return components.ComponentModels(models=models), f"{SCOPE}/components/{iso_week}"
