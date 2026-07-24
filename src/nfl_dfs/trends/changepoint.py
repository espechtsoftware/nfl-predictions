"""Regime-change detection on usage series (guide §8.5).

Rolling averages are lagging indicators of role change: a WR promoted in
week 8 still has six weeks of WR3 usage dragging his 4-week average.
Detecting the break beats smoothing across it.

Primary detector: Bayesian online changepoint detection (Adams & MacKay
2007) with a normal-inverse-gamma conjugate model. Simpler fallbacks:
CUSUM and a two-window Welch t-test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


def changepoint_probabilities(
    series: np.ndarray | list[float],
    hazard: float = 1 / 25,
    run_cut: int = 2,
    warmup: int = 5,
) -> np.ndarray:
    """Online changepoint detection on a usage series (e.g. weekly target
    share). Returns P(run length <= run_cut) per week — a spike means the
    role changed within the last couple of weeks.

    Two deliberate departures from the textbook readout:

    * The naive "P(run length = 0)" is constant by construction — the growth
      and changepoint branches share the same predictive, so the restart mass
      always normalizes to the hazard. Evidence for a break shows up a step
      later, as posterior mass piling onto SHORT run lengths; hence run_cut.
    * Priors are set empirically from the series (mean of the first value,
      noise from robust first differences), because fixed unit-scale priors
      swamp target-share-scale data and the detector never reacts.

    hazard behaves as a sensitivity knob more than a literal prior; 1/25
    with a 0.5 alert threshold gives ~3% false positives and ~98% detection
    on a WR3->WR1-sized break in simulation. The first `warmup` weeks are
    reported as 0 — the run-length posterior is too short to mean anything.
    """
    xs = np.asarray(series, dtype=float)
    T = len(xs)
    if T == 0:
        return np.zeros(0)

    # Empirical-Bayes priors: within-regime noise from robust first diffs.
    overall_sd = float(np.std(xs)) or 1.0
    if T >= 3:
        d = np.diff(xs)
        sigma = float(np.median(np.abs(d - np.median(d)))) / 0.6745 / np.sqrt(2)
    else:
        sigma = overall_sd
    sigma = max(sigma, 1e-3 * overall_sd, 1e-9)
    mu0, kappa0, alpha0 = float(xs[0]), 1.0, 2.0
    beta0 = (alpha0 - 1) * sigma**2  # E[sigma^2] = beta0/(alpha0-1) = sigma^2

    # Run-length posterior over 0..t, plus NIG params per run length.
    r_probs = np.array([1.0])
    mu = np.array([mu0])
    kappa = np.array([kappa0])
    alpha = np.array([alpha0])
    beta = np.array([beta0])
    cp = np.zeros(T)
    warmup = max(warmup, run_cut + 1)

    for t, x in enumerate(xs):
        # Posterior predictive (Student-t) of x under each run length
        pred = stats.t.pdf(
            x,
            df=2 * alpha,
            loc=mu,
            scale=np.sqrt(beta * (kappa + 1) / (alpha * kappa)),
        )
        pred = np.clip(pred, 1e-300, None)

        growth = r_probs * pred * (1 - hazard)          # runs continue
        change = float(np.sum(r_probs * pred) * hazard)  # a run restarts

        r_probs = np.concatenate([[change], growth])
        r_probs /= r_probs.sum()
        cp[t] = r_probs[: run_cut + 1].sum() if t >= warmup else 0.0

        # Normal-inverse-gamma conjugate updates (index 0 = fresh run,
        # computed from the PRE-update parameters).
        mu_new = np.concatenate([[mu0], (kappa * mu + x) / (kappa + 1)])
        beta_new = np.concatenate([[beta0], beta + kappa * (x - mu) ** 2 / (2 * (kappa + 1))])
        kappa_new = np.concatenate([[kappa0], kappa + 1])
        alpha_new = np.concatenate([[alpha0], alpha + 0.5])
        mu, kappa, alpha, beta = mu_new, kappa_new, alpha_new, beta_new

    return cp


def cusum_flags(
    series: np.ndarray | list[float],
    k: float = 0.5,
    h: float = 4.0,
) -> np.ndarray:
    """One-sided CUSUM on a standardized series; ~15 lines, catches most of
    the same breaks. k = slack (in SDs), h = decision threshold (in SDs).
    Returns a boolean flag per observation (upward or downward shift)."""
    xs = np.asarray(series, dtype=float)
    if len(xs) < 3:
        return np.zeros(len(xs), dtype=bool)
    mu, sd = np.nanmean(xs), np.nanstd(xs)
    if sd == 0:
        return np.zeros(len(xs), dtype=bool)
    z = (xs - mu) / sd
    up = down = 0.0
    flags = np.zeros(len(xs), dtype=bool)
    for i, zi in enumerate(z):
        up = max(0.0, up + zi - k)
        down = max(0.0, down - zi - k)
        if up > h or down > h:
            flags[i] = True
            up = down = 0.0
    return flags


def two_window_pvalue(
    series: np.ndarray | list[float], recent: int = 2, baseline: int = 6
) -> float:
    """Welch t-test: last `recent` weeks vs the `baseline` weeks before
    them. Small p = the recent level is a different regime."""
    xs = np.asarray(series, dtype=float)
    if len(xs) < recent + 3:
        return 1.0
    tail = xs[-recent:]
    base = xs[-(recent + baseline):-recent]
    if len(base) < 3 or np.nanstd(base) == 0 and np.nanstd(tail) == 0:
        return 1.0
    res = stats.ttest_ind(tail, base, equal_var=False)
    return float(res.pvalue) if np.isfinite(res.pvalue) else 1.0


@dataclass
class PlayerTrend:
    gsis_id: str
    season: int
    week: int
    changepoint_prob: float
    weeks_since_change: int
    cusum_flag: bool
    two_window_p: float


def detect_panel(
    df: pd.DataFrame,
    value_col: str = "target_share",
    threshold: float = 0.5,
    min_weeks: int = 4,
) -> pd.DataFrame:
    """Run detection per player-season over a long panel with columns
    [gsis_id, season, week, value_col]. Returns one row per player-week:
    changepoint_prob, weeks_since_change, cusum_flag, two_window_p.

    Feed `weeks_since_change` and `changepoint_prob` to the model as
    features; alert on prob > threshold for the weekly watchlist.
    """
    out: list[PlayerTrend] = []
    for (gsis_id, season), grp in df.groupby(["gsis_id", "season"], sort=False):
        grp = grp.sort_values("week")
        xs = grp[value_col].to_numpy(dtype=float)
        if len(xs) < min_weeks or np.all(np.isnan(xs)):
            continue
        xs = np.nan_to_num(xs, nan=float(np.nanmean(xs)))
        cp = changepoint_probabilities(xs)
        cusum = cusum_flags(xs)
        weeks_since = 0
        for i, week in enumerate(grp.week.to_numpy()):
            # Week 1 trivially restarts the run; ignore as "no change known".
            is_change = cp[i] > threshold and i > 0
            weeks_since = 0 if is_change else weeks_since + 1
            out.append(
                PlayerTrend(
                    gsis_id=gsis_id,
                    season=int(season),
                    week=int(week),
                    changepoint_prob=float(cp[i]) if i > 0 else 0.0,
                    weeks_since_change=weeks_since,
                    cusum_flag=bool(cusum[i]),
                    two_window_p=two_window_pvalue(xs[: i + 1]),
                )
            )
    return pd.DataFrame([t.__dict__ for t in out])
