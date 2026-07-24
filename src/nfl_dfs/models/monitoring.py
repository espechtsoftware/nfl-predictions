"""Weekly drift alarms (guide §7.8). Thresholds from the guide's table:
MAE ratio 1.3×, p10/p90 coverage outside 7–13% / 87–93%, PSI 0.2, null
rate 2× baseline. A null-rate alarm means "check ingestion first, always".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MAE_RATIO_THRESHOLD = 1.3
COVERAGE_P10_RANGE = (0.07, 0.13)
COVERAGE_P90_RANGE = (0.87, 0.93)
PSI_THRESHOLD = 0.2
NULL_RATE_MULTIPLE = 2.0
# Baseline null rate is floored so a feature that was never null in
# training still alarms when nulls appear live, without alarming on dust.
_NULL_RATE_FLOOR = 0.01


@dataclass
class Alarm:
    kind: str
    message: str
    value: float


def check_mae(training_mae: float, recent_mae: float) -> Alarm | None:
    ratio = recent_mae / training_mae
    if ratio > MAE_RATIO_THRESHOLD:
        return Alarm(
            "mae_drift",
            f"rolling MAE {recent_mae:.2f} is {ratio:.2f}x training MAE "
            f"{training_mae:.2f} — model degrading, investigate before trusting",
            ratio,
        )
    return None


def check_coverage(
    y: np.ndarray, p10: np.ndarray, p90: np.ndarray
) -> list[Alarm]:
    y = np.asarray(y, dtype=float)
    alarms = []
    below_p10 = float(np.mean(y < np.asarray(p10, dtype=float)))
    below_p90 = float(np.mean(y < np.asarray(p90, dtype=float)))
    lo, hi = COVERAGE_P10_RANGE
    if not lo <= below_p10 <= hi:
        alarms.append(Alarm("coverage_p10",
                            f"p10 empirical coverage {below_p10:.3f} outside [{lo}, {hi}]",
                            below_p10))
    lo, hi = COVERAGE_P90_RANGE
    if not lo <= below_p90 <= hi:
        alarms.append(Alarm("coverage_p90",
                            f"p90 empirical coverage {below_p90:.3f} outside [{lo}, {hi}]",
                            below_p90))
    return alarms


def psi(base: np.ndarray, live: np.ndarray, bins: int = 10) -> float:
    """Population stability index of `live` against `base`, binned on the
    base distribution's quantiles."""
    base = np.asarray(base, dtype=float)
    live = np.asarray(live, dtype=float)
    edges = np.quantile(base, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(base, edges)[0] / len(base)
    q = np.histogram(live, edges)[0] / len(live)
    p = np.clip(p, 1e-6, None)
    q = np.clip(q, 1e-6, None)
    return float(np.sum((q - p) * np.log(q / p)))


def check_feature_drift(
    train: pd.DataFrame, live: pd.DataFrame, features: list[str]
) -> list[Alarm]:
    """Null-rate and PSI alarms per feature between the training frame and
    a live scoring frame."""
    alarms: list[Alarm] = []
    for f in features:
        base_null = max(float(train[f].isna().mean()), _NULL_RATE_FLOOR)
        live_null = float(live[f].isna().mean())
        if live_null > NULL_RATE_MULTIPLE * base_null:
            alarms.append(Alarm(
                "null_rate",
                f"{f}: live null rate {live_null:.1%} vs baseline {base_null:.1%} "
                f"— ingestion bug until proven otherwise",
                live_null,
            ))
        base_vals = train[f].dropna().to_numpy(dtype=float)
        live_vals = live[f].dropna().to_numpy(dtype=float)
        if len(base_vals) and len(live_vals):
            score = psi(base_vals, live_vals)
            if score > PSI_THRESHOLD:
                alarms.append(Alarm(
                    "psi",
                    f"{f}: PSI {score:.2f} vs training — upstream data change "
                    f"or genuine league shift",
                    score,
                ))
    return alarms
