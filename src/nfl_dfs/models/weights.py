"""Recency sample weights (guide §7.4).

Exponential decay on season distance only — recency *within* a season is
already carried by the rolling features, and weighting it again would
double-count and chase noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sample_weights(
    df: pd.DataFrame, target_season: int, half_life_seasons: float = 3.0
) -> np.ndarray:
    """0.5 ** (season_age / half_life). Refuses future seasons — a row from
    after the target season in the training set is a leak, not a weight."""
    age = target_season - df["season"].to_numpy()
    if (age < 0).any():
        bad = sorted(df.loc[age < 0, "season"].unique())
        raise ValueError(
            f"training rows from seasons {bad} are after target season {target_season}"
        )
    return 0.5 ** (age / half_life_seasons)
