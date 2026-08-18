"""Paired weekly-maximum co-primary statistics (N7, 2026-08-18).

Clear-counts at fixed thresholds discard magnitude, and on 54 (or a
season's ~18) slates they cannot resolve effects of a few mean points.
Every paired arm also produces a continuous per-slate statistic — the
difference in realized weekly maximum — and paired sign-flip inference on
that difference has materially more power. This module computes, for one
control/treatment pair of aligned per-slate weekly maxima:

* the mean and median paired difference;
* deterministic two-sided sign-flip p-values for the mean difference and
  for the Wilcoxon signed-rank statistic (exact enumeration when the
  number of nonzero differences is small, fixed-seed Monte Carlo
  otherwise);
* per-threshold clear counts, discordant pairs, and exact McNemar
  binomial p-values.

It is a measurement helper: it reads whatever series it is given, fits
nothing, tunes nothing, and licenses nothing. Callers feeding realized
outcomes are outcome-facing and must say so in their own protocols. The
preregistration that makes this the standing co-primary for future arm
reports and 2026 shadow grading is
reports/2026-08-18-paired-max-coprimary-preregistration.md.
"""
from __future__ import annotations

from collections.abc import Sequence
from math import comb

import numpy as np

PROTOCOL_ID = "20260818-paired-max-coprimary-v1"
DEFAULT_THRESHOLDS = (240, 230, 220, 210, 200, 194, 187)
# Exact sign-flip enumeration up to 2**EXACT_LIMIT patterns; above that a
# fixed-seed Monte Carlo keeps the result deterministic across reruns.
EXACT_LIMIT = 20
MONTE_CARLO_RESAMPLES = 200_000
MONTE_CARLO_SEED = 20_260_818
_CHUNK = 1 << 16
_EPS = 1e-12


def _validate(control, treatment, slate_keys):
    control = np.asarray(control, dtype=float)
    treatment = np.asarray(treatment, dtype=float)
    if control.ndim != 1 or treatment.ndim != 1:
        raise ValueError("weekly maxima must be one-dimensional")
    if len(control) != len(treatment):
        raise ValueError("control and treatment lengths differ")
    if len(control) < 2:
        raise ValueError("paired statistics need at least two slates")
    if not (np.isfinite(control).all() and np.isfinite(treatment).all()):
        raise ValueError("weekly maxima must be finite")
    if slate_keys is not None:
        keys = list(slate_keys)
        if len(keys) != len(control):
            raise ValueError("slate keys are misaligned with the maxima")
        if len(set(map(str, keys))) != len(keys):
            raise ValueError("slate keys are not unique")
    return control, treatment


def _signed_rank_ranks(nonzero: np.ndarray) -> np.ndarray:
    """Average ranks of |d| across the nonzero differences (ties shared)."""
    magnitude = np.abs(nonzero)
    order = np.argsort(magnitude, kind="mergesort")
    ranks = np.empty(len(nonzero), dtype=float)
    sorted_mag = magnitude[order]
    i = 0
    while i < len(sorted_mag):
        j = i
        while j + 1 < len(sorted_mag) and sorted_mag[j + 1] == sorted_mag[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def _sign_matrices(m: int):
    """Yield (patterns, signs) chunks over all 2**m sign patterns."""
    total = 1 << m
    bits = np.arange(m)
    for start in range(0, total, _CHUNK):
        stop = min(start + _CHUNK, total)
        codes = np.arange(start, stop, dtype=np.int64)
        flips = ((codes[:, None] >> bits[None, :]) & 1).astype(float)
        yield 1.0 - 2.0 * flips  # 0 bit -> +1, 1 bit -> -1


def _sign_flip_pvalues(nonzero: np.ndarray, n_total: int) -> dict:
    """Two-sided sign-flip p-values for the mean difference and the
    Wilcoxon signed-rank statistic, over the nonzero differences."""
    m = len(nonzero)
    ranks = _signed_rank_ranks(nonzero)
    obs_sum = float(nonzero.sum())
    obs_w = float(ranks[nonzero > 0].sum())
    w_center = float(ranks.sum()) / 2.0
    if m == 0:
        return {
            "method": "degenerate", "n_nonzero": 0,
            "p_mean_two_sided": 1.0, "p_signed_rank_two_sided": 1.0,
            "signed_rank_statistic": 0.0,
        }
    if m <= EXACT_LIMIT:
        hits_sum = hits_w = total = 0
        for signs in _sign_matrices(m):
            sums = signs @ nonzero
            ws = ((signs > 0) * ranks[None, :]).sum(axis=1)
            hits_sum += int((np.abs(sums) >= abs(obs_sum) - _EPS).sum())
            hits_w += int(
                (np.abs(ws - w_center) >= abs(obs_w - w_center) - _EPS).sum())
            total += signs.shape[0]
        method = "exact_enumeration"
        p_sum = hits_sum / total
        p_w = hits_w / total
    else:
        rng = np.random.default_rng(MONTE_CARLO_SEED)
        hits_sum = hits_w = 0
        done = 0
        while done < MONTE_CARLO_RESAMPLES:
            take = min(_CHUNK, MONTE_CARLO_RESAMPLES - done)
            signs = rng.choice((-1.0, 1.0), size=(take, m))
            sums = signs @ nonzero
            ws = ((signs > 0) * ranks[None, :]).sum(axis=1)
            hits_sum += int((np.abs(sums) >= abs(obs_sum) - _EPS).sum())
            hits_w += int(
                (np.abs(ws - w_center) >= abs(obs_w - w_center) - _EPS).sum())
            done += take
        # Add-one so the observed arrangement counts as one resample.
        method = "monte_carlo"
        p_sum = (hits_sum + 1) / (MONTE_CARLO_RESAMPLES + 1)
        p_w = (hits_w + 1) / (MONTE_CARLO_RESAMPLES + 1)
    return {
        "method": method, "n_nonzero": m,
        "p_mean_two_sided": float(min(1.0, p_sum)),
        "p_signed_rank_two_sided": float(min(1.0, p_w)),
        "signed_rank_statistic": obs_w,
    }


def _mcnemar_exact_p(b: int, c: int) -> float | None:
    """Two-sided exact binomial McNemar p (doubling convention, capped)."""
    n = b + c
    if n == 0:
        return None
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return float(min(1.0, 2.0 * tail))


def paired_weekly_max_report(
    control: Sequence[float],
    treatment: Sequence[float],
    *,
    thresholds: Sequence[int] = DEFAULT_THRESHOLDS,
    slate_keys: Sequence | None = None,
    labels: tuple[str, str] = ("control", "treatment"),
) -> dict:
    """The standing paired co-primary block for one arm/control pair."""
    control, treatment = _validate(control, treatment, slate_keys)
    diffs = treatment - control
    nonzero = diffs[diffs != 0.0]
    inference = _sign_flip_pvalues(nonzero, len(diffs))
    grid = []
    for threshold in thresholds:
        c_clear = control >= threshold
        t_clear = treatment >= threshold
        b = int((c_clear & ~t_clear).sum())   # control-only clears
        c_only = int((t_clear & ~c_clear).sum())
        grid.append({
            "threshold": int(threshold),
            labels[0]: int(c_clear.sum()),
            labels[1]: int(t_clear.sum()),
            "discordant_control_only": b,
            "discordant_treatment_only": c_only,
            "mcnemar_exact_p_two_sided": _mcnemar_exact_p(b, c_only),
        })
    return {
        "protocol_id": PROTOCOL_ID,
        "labels": list(labels),
        "n_slates": int(len(diffs)),
        "mean_diff": float(diffs.mean()),
        "median_diff": float(np.median(diffs)),
        "n_treatment_better": int((diffs > 0).sum()),
        "n_control_better": int((diffs < 0).sum()),
        "n_tied": int((diffs == 0).sum()),
        "inference": inference,
        "threshold_grid": grid,
        # This helper measures; it licenses nothing.
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
    }
