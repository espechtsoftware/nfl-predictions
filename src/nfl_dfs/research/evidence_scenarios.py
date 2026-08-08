"""Evidence-conditioned component scenarios.

Unlike the rejected generic EPI/Gumbel arms, these worlds change only when a
timestamped pre-lock claim is active. Effects are drawn at the affected
player/component level from the partial-pooling evidence effect model;
conflicting reports center the adjustment at zero and widen it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from .evidence_effect import EffectModel
from .evidence_schema import ActiveAdjustment


def apply_evidence_scenarios(
    component_draws: Mapping[str, np.ndarray],
    player_ids: Sequence[str],
    positions: Mapping[str, str],
    adjustments: Sequence[ActiveAdjustment],
    effect_model: EffectModel,
    seed: int = 260806,
) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    """Return adjusted component draws plus an auditable shock summary."""
    out = {name: np.asarray(values, dtype=float).copy()
           for name, values in component_draws.items()}
    if not out:
        return out, pd.DataFrame()
    shapes = {v.shape for v in out.values()}
    if len(shapes) != 1 or next(iter(shapes))[0] != len(player_ids):
        raise ValueError("component draws must share shape (n_players, n_worlds)")
    index = {str(pid): ix for ix, pid in enumerate(player_ids)}
    rng = np.random.default_rng(seed)
    audit: list[dict] = []
    for adj in adjustments:
        if adj.gsis_id not in index or adj.component not in out:
            continue
        ix = index[adj.gsis_id]
        pos = positions.get(adj.gsis_id, "")
        estimates = [effect_model.predict(event_type, pos)
                     for event_type in adj.event_types]
        if estimates:
            raw_mean = float(np.mean([e.mean for e in estimates]))
            raw_sd = float(np.sqrt(np.mean([e.sd ** 2 for e in estimates])))
        else:
            estimate = effect_model.predict("other", pos)
            raw_mean, raw_sd = estimate.mean, estimate.sd
        if adj.direction == "opportunity_up":
            mean = abs(raw_mean) * adj.confidence
        elif adj.direction == "opportunity_down":
            mean = -abs(raw_mean) * adj.confidence
        else:
            mean = 0.0
        # Confidence represents a mixture with "no real effect", which both
        # shrinks the mean and retains uncertainty instead of pretending a
        # low-confidence report is precise.
        sd = raw_sd * adj.variance_inflation
        n_worlds = out[adj.component].shape[1]
        shocks = np.clip(rng.normal(mean, sd, n_worlds), -0.95, 3.0)
        out[adj.component][ix] *= (1.0 + shocks)
        audit.append({
            "gsis_id": adj.gsis_id,
            "component": adj.component,
            "direction": adj.direction,
            "conflict": adj.conflict,
            "mean_shock": float(shocks.mean()),
            "sd_shock": float(shocks.std()),
            "n_worlds": n_worlds,
        })
    return out, pd.DataFrame(audit)
