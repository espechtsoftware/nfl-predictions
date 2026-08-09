"""Learn conditional weights over historical Schaake game templates.

This is an off-by-default dependence diagnostic.  It does not predict player
means or change any player's simulated marginal.  A random-feature embedding
of the multivariate historical role ranks approximates the Gaussian-kernel
MMD splitting target used by distributional forests.  A conventional random
forest then supplies quantile-forest-style leaf weights over the original
historical games for a new pre-lock game context.

The sampled historical templates are still applied by ``apply_schaake_game``
as exact rank permutations.  Candidate generation is forbidden until the
result beats the production copula on the preregistered held-out dependence
scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from .schaake import SIM_FEATURES


FOREST_SEED = 8162
FOREST_ESTIMATORS = 300
FOREST_MIN_LEAF = 20
FOREST_RFF_DIM = 64
FOREST_BANDWIDTH_SAMPLE = 512
FOREST_ROLES = tuple(
    f"{role}_{side}"
    for role in ("QB", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1")
    for side in ("fav", "dog")
)


def _numeric_frame(frame: pd.DataFrame, columns: tuple[str, ...]) -> np.ndarray:
    return frame.loc[:, columns].apply(
        pd.to_numeric, errors="coerce").to_numpy(dtype=float)


def _rbf_bandwidth(response: np.ndarray, rng: np.random.Generator) -> float:
    """Deterministic median pair distance on a bounded training subsample."""
    count = min(len(response), FOREST_BANDWIDTH_SAMPLE)
    positions = rng.choice(len(response), size=count, replace=False)
    sample = response[positions]
    distance = np.sqrt(np.sum(
        (sample[:, None, :] - sample[None, :, :]) ** 2, axis=2))
    upper = distance[np.triu_indices(count, k=1)]
    positive = upper[np.isfinite(upper) & (upper > 0)]
    if not len(positive):
        raise ValueError("historical template responses have zero distance")
    return float(np.median(positive))


@dataclass
class ConditionalTemplateForest:
    """Fitted forest and the historical templates its leaves reweight."""

    templates: pd.DataFrame
    context_features: tuple[str, ...]
    context_medians: np.ndarray
    model: RandomForestRegressor
    training_leaves: np.ndarray
    bandwidth: float
    seed: int

    def weights(self, context: Mapping[str, float]) -> np.ndarray:
        """Quantile-forest weights for one pre-lock game context."""
        query = np.array(
            [pd.to_numeric(context.get(name), errors="coerce")
             for name in self.context_features], dtype=float)
        query = np.where(np.isfinite(query), query, self.context_medians)
        query_leaves = self.model.apply(query.reshape(1, -1))[0]
        weights = np.zeros(len(self.templates), dtype=float)
        for tree, leaf in enumerate(query_leaves):
            members = self.training_leaves[:, tree] == leaf
            count = int(np.count_nonzero(members))
            if count:
                weights[members] += 1.0 / count
        weights /= len(query_leaves)
        total = float(weights.sum())
        if not np.isfinite(total) or total <= 0:
            raise RuntimeError("conditional template forest returned no weight")
        return weights / total

    def diagnostics(self, weights: np.ndarray) -> dict[str, float]:
        weights = np.asarray(weights, dtype=float)
        return {
            "effective_templates": float(1.0 / np.square(weights).sum()),
            "max_template_weight": float(weights.max()),
        }


def fit_conditional_template_forest(
    bank: pd.DataFrame,
    target_season: int,
    *,
    seed: int = FOREST_SEED,
    n_estimators: int = FOREST_ESTIMATORS,
    min_samples_leaf: int = FOREST_MIN_LEAF,
    rff_dim: int = FOREST_RFF_DIM,
) -> ConditionalTemplateForest:
    """Fit strictly prior-season conditional weights over game templates.

    The forest response is a random Fourier embedding of the complete
    favorite/underdog role-rank vector.  Squared-error splits in that
    embedding approximate Gaussian-kernel MMD distributional splits.  Leaf
    co-membership reweights original complete templates; it never synthesizes
    or averages a template response.
    """
    if target_season <= 0:
        raise ValueError("target_season must be positive")
    if n_estimators <= 0 or min_samples_leaf <= 0 or rff_dim <= 0:
        raise ValueError("forest dimensions must be positive")
    needed = {"season", *FOREST_ROLES}
    missing = needed - set(bank.columns)
    if missing:
        raise ValueError(f"template bank missing {sorted(missing)}")
    context_features = tuple(
        name for name in SIM_FEATURES
        if name in bank.columns
        and pd.to_numeric(bank[name], errors="coerce").notna().any())
    if not context_features:
        raise ValueError("template bank has no usable context features")

    past = bank[pd.to_numeric(
        bank.season, errors="coerce").lt(target_season)].copy()
    response = _numeric_frame(past, FOREST_ROLES)
    complete = np.isfinite(response).all(axis=1)
    past = past.loc[complete].reset_index(drop=True)
    response = response[complete]
    if len(past) < max(2 * min_samples_leaf, 50):
        raise ValueError(
            f"only {len(past)} complete prior-season templates available")

    context = _numeric_frame(past, context_features)
    medians = np.nanmedian(context, axis=0)
    if not np.isfinite(medians).all():
        raise ValueError("template context has an all-missing feature")
    context = np.where(np.isfinite(context), context, medians)

    rng = np.random.default_rng(seed)
    bandwidth = _rbf_bandwidth(response, rng)
    frequencies = rng.normal(
        0.0, 1.0 / bandwidth, size=(response.shape[1], rff_dim))
    phases = rng.uniform(0.0, 2.0 * np.pi, size=rff_dim)
    embedded = np.sqrt(2.0 / rff_dim) * np.cos(
        response @ frequencies + phases)

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        min_samples_leaf=min_samples_leaf,
        max_features=1.0,
        random_state=seed,
        n_jobs=1,
    )
    model.fit(context, embedded)
    leaves = model.apply(context)
    return ConditionalTemplateForest(
        templates=past,
        context_features=context_features,
        context_medians=medians,
        model=model,
        training_leaves=leaves,
        bandwidth=bandwidth,
        seed=seed,
    )


def cloud_smoke() -> dict:
    """Cheap dependency/mechanism probe for an immutable Cloud image."""
    rng = np.random.default_rng(17)
    rows = []
    for group in (0, 1):
        for index in range(40):
            record = {
                "season": 2024,
                "game_total": 42.0 + 10.0 * group + rng.normal(0, 0.2),
                "spread_abs": 2.0 + group,
            }
            for role_index, role in enumerate(FOREST_ROLES):
                record[role] = np.clip(
                    0.2 + 0.6 * group + 0.01 * role_index
                    + rng.normal(0, 0.02), 0.001, 0.999)
            rows.append(record)
    fitted = fit_conditional_template_forest(
        pd.DataFrame(rows), 2025, n_estimators=30,
        min_samples_leaf=5, rff_dim=16)
    weights = fitted.weights({"game_total": 52.0, "spread_abs": 3.0})
    high_mass = float(weights[40:].sum())
    if high_mass <= 0.75:
        raise AssertionError(
            f"conditional forest failed smoke separation: {high_mass}")
    result = {
        "status": "PASS",
        "templates": len(fitted.templates),
        "weight_sum": float(weights.sum()),
        "matched_group_mass": high_mass,
    }
    print("conditional-schaake-smoke " + __import__("json").dumps(
        result, sort_keys=True))
    return result
