"""Weekly retrain (guide §7.8): full retrain every Tuesday with the
completed week added — training is cheap and incremental updates
accumulate drift. Every component model lands in the registry under the
current ISO week with its metrics sidecar.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date

import pandas as pd

from ..bq import query_df
from ..config import current_season, settings
from . import baseline, components, registry

log = logging.getLogger(__name__)

SCOPE = "pooled"
CANONICAL_VARIANT = "canonical"


def registry_variant(value: str | None = None) -> str:
    """Return a safe component-registry namespace.

    Canonical labels remain unchanged for production compatibility. Research
    shadows use suffixed labels, so training K=1 cannot overwrite live K=3.
    """
    variant = (value if value is not None else
               os.environ.get("MODEL_REGISTRY_VARIANT", CANONICAL_VARIANT))
    variant = str(variant).strip().lower() or CANONICAL_VARIANT
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", variant):
        raise ValueError(
            "MODEL_REGISTRY_VARIANT must match [a-z][a-z0-9_]{0,31}")
    return variant


def validate_variant_feature_contract(variant: str) -> None:
    """Pin isolated live-shadow registries to their declared feature sets."""
    from ..inference.route_share_shadow import ROLE_FEATURES, ROUTE_FEATURES

    expected = {
        "tail_k1_route": set(ROUTE_FEATURES),
        "tail_k1_route_role": set((*ROLE_FEATURES, *ROUTE_FEATURES)),
    }.get(variant)
    if expected is None:
        return
    actual = {
        value.strip()
        for value in os.environ.get("EXTRA_FEATURES", "").split(",")
        if value.strip()
    }
    if actual != expected:
        raise RuntimeError(
            f"registry variant {variant} requires exact EXTRA_FEATURES="
            f"{','.join(sorted(expected))}; got {','.join(sorted(actual))}")


def _component_label(name: str, variant: str) -> str:
    base = f"comp_{name}"
    return base if variant == CANONICAL_VARIANT else f"{base}__{variant}"


def _component_version(iso_week: str, variant: str) -> str:
    family = ("components" if variant == CANONICAL_VARIANT
              else f"components__{variant}")
    return f"{SCOPE}/{family}/{iso_week}"


def registered_ensemble_size(models: components.ComponentModels) -> int:
    """Member count encoded by a loaded component set; all must agree."""
    sizes = {
        len(members) if (members := getattr(model, "members", None))
        is not None else 1
        for model in models.models.values()
    }
    if len(sizes) != 1:
        raise RuntimeError(
            f"registered component models have mixed member counts: "
            f"{sorted(sizes)}")
    return next(iter(sizes))


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


def train_and_register(today: date | None = None,
                       variant: str | None = None) -> str:
    """Retrain the component models on everything up to now, validate the
    baseline walk-forward for the metrics sidecar, and register every
    booster under this ISO week. Returns the model version prefix."""
    variant = registry_variant(variant)
    validate_variant_feature_contract(variant)
    if variant in {"tail_k1_route", "tail_k1_route_role"}:
        from ..inference.route_share_shadow import require_prior_week_source
        from ..inference.tail_shadow import upcoming_season_week

        target_season, target_week, _ = upcoming_season_week()
        require_prior_week_source(target_season, target_week)
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
                label=_component_label(name, variant),
                iso_week=iso_week,
                params=registry.model_params(booster),
                features=list(booster.feature_name()),
                train_seasons=train_seasons,
                metrics=metrics,
            ),
            root,
        )
    version = _component_version(iso_week, variant)
    log.info("Registered %d component models as %s (variant=%s)",
             len(cm.models), version, variant)
    return version


def load_latest_component_models(
    variant: str | None = None,
) -> tuple[components.ComponentModels, str]:
    """Latest registered component set + its version string, for inference."""
    root = _registry_root()
    variant = registry_variant(variant)
    iso_week = registry.latest_iso_week(
        root, SCOPE, _component_label("targets", variant))
    models = {
        name: registry.load(
            root, SCOPE, _component_label(name, variant), iso_week)[0]
        for name in components.COMPONENT_NAMES
    }
    return (components.ComponentModels(models=models),
            _component_version(iso_week, variant))
