"""Field-max null calibration (N1d, 2026-08-19): how extreme should a
contest winner look under a CORRECT law?

The winner-law audit (N1) found all 51 tracked Milly winners at a median
percentile of 1.0 within their own simulated distributions. That headline
is confounded: winners are the maximum over an enormous entry field, and
even under a perfectly correct law the field-max roster's realized score
sits near the top of its own distribution (roughly 1 - 1/N_effective).
This module computes the null the headline was missing.

Null construction, entirely under our own archived law (no realized
outcome is read anywhere): treat each archived world as a realized
contest; the "winner" is the registered candidate with the highest total
in that world (our pool standing in for the field); its null percentile
is the mid-rank placement of that total within the SAME candidate's
distribution across all other worlds (self-world excluded, matching the
observed semantics where the realized outcome is not among the sims).
Contests run PER SEED BLOCK: the pre-freeze reality smoke found that each
seed book registers its own candidate set, so candidate rows cannot be
stacked across blocks. Per-block contests are statistically equivalent —
the selection effect depends on the number of competing rosters, not on
the reference-world count — and five blocks give 50,000 null contests
per slate.
Sweeping the candidate count via fixed-seed subsampling traces how the
null exceedance probability grows with field size, and inverting the
iid-percentile relation p = 1 - 0.999**N yields the implied effective
field size at each pool size. Extrapolating the effectiveness ratio to
the observed exceedance fraction asks: how large would the real field
have to be for a correct law to produce what N1 observed?

Frozen decision rule (see the protocol document): if the full-pool null
already produces the observed exceedance count with probability >= 0.01,
selection alone explains N1 at pool size; otherwise, if the required raw
field size is within the literal entry-count cap, N1 is non-diagnostic
(consistent with a correct law and a plausible field); only a required
field size beyond any real field confirms missing joint mass at winner
scale. Diagnostic-only; fits nothing; licenses nothing.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

PROTOCOL_ID = "20260819-field-max-null-v1"
EXCEEDANCE_LEVELS = (0.95, 0.99, 0.999)
# Hard upper bound on plausible effective field size: no effective count
# can exceed the literal number of entries (Milly fields run ~150-236k;
# 300k is a deliberately generous cap frozen before any number was seen).
FIELD_SIZE_CAP = 300_000
# The full-pool null explains N1 outright when it reproduces the observed
# exceedance count with at least this probability.
NULL_EXPLAINS_MIN_PROB = 0.01
MIN_WORLDS = 100


class FieldMaxNullError(ValueError):
    """Fail-closed protocol violation."""


def combine_block_nulls(block_results: Sequence[dict]) -> dict:
    """Pool per-block null contests into one slate-level result.

    Each entry comes from :func:`null_field_max_percentiles` on ONE seed
    block. Candidate sets differ across blocks by construction (each seed
    book registers its own candidates), so results concatenate at the
    contest level — never at the candidate-row level.
    """
    if not block_results:
        raise FieldMaxNullError("at least one block result is required")
    for result in block_results:
        if not {"n_candidates", "n_worlds", "percentiles", "pr_ge"} \
                <= set(result):
            raise FieldMaxNullError("malformed block null result")
    return {
        "block_candidates": [int(r["n_candidates"]) for r in block_results],
        "n_worlds": int(sum(r["n_worlds"] for r in block_results)),
        "percentiles": np.concatenate(
            [np.asarray(r["percentiles"], dtype=np.float64)
             for r in block_results]),
        "pr_ge": np.concatenate(
            [np.asarray(r["pr_ge"], dtype=np.float64)
             for r in block_results]),
    }


def _percentiles_for_picks(
    row_sorted: np.ndarray,
    winner_rows: np.ndarray,
    values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Self-excluded mid-rank percentile of each pick within its row.

    ``row_sorted``: per-candidate sorted totals (candidates, worlds);
    ``winner_rows``: the picked candidate row per contest; ``values``:
    the picked total per contest, which must be present in its row (the
    self world). Returns (percentile, pr_ge) arrays with the self draw
    removed from the reference distribution.
    """
    n_worlds = row_sorted.shape[1]
    percentile = np.empty(len(values), dtype=np.float64)
    pr_ge = np.empty(len(values), dtype=np.float64)
    for row in np.unique(winner_rows):
        mask = winner_rows == row
        picked = values[mask]
        left = np.searchsorted(row_sorted[row], picked, side="left")
        right = np.searchsorted(row_sorted[row], picked, side="right")
        equal = right - left
        if (equal < 1).any():
            raise FieldMaxNullError(
                "picked total absent from its own candidate row")
        percentile[mask] = (left + 0.5 * (equal - 1)) / (n_worlds - 1)
        pr_ge[mask] = (n_worlds - left - 1) / (n_worlds - 1)
    return percentile, pr_ge


def null_field_max_percentiles(totals: np.ndarray) -> dict:
    """Treat every world as one contest won by the pool argmax."""
    totals = np.asarray(totals, dtype=np.float64)
    if totals.ndim != 2 or totals.shape[0] < 2:
        raise FieldMaxNullError("totals must be (candidates >= 2, worlds)")
    n_cand, n_worlds = totals.shape
    if n_worlds < MIN_WORLDS:
        raise FieldMaxNullError(
            f"at least {MIN_WORLDS} worlds are required")
    winner = np.argmax(totals, axis=0)
    values = totals[winner, np.arange(n_worlds)]
    row_sorted = np.sort(totals, axis=1)
    percentile, pr_ge = _percentiles_for_picks(row_sorted, winner, values)
    return {
        "n_candidates": int(n_cand),
        "n_worlds": int(n_worlds),
        "percentiles": percentile,
        "pr_ge": pr_ge,
    }


def subsample_field_null(
    totals: np.ndarray, n_sub: int, seed: int, reps: int,
) -> np.ndarray:
    """Null percentiles when only ``n_sub`` pool rosters form the field.

    Fixed-seed subsampling without replacement; the winning candidate's
    reference distribution stays its FULL row (field size changes who
    wins, never the law). Returns percentiles stacked over repetitions.
    """
    totals = np.asarray(totals, dtype=np.float64)
    n_cand, n_worlds = totals.shape
    n_sub = int(n_sub)
    if not 2 <= n_sub <= n_cand:
        raise FieldMaxNullError(
            f"subsample size {n_sub} outside [2, {n_cand}]")
    if int(reps) < 1:
        raise FieldMaxNullError("at least one repetition is required")
    rng = np.random.default_rng(int(seed))
    row_sorted = np.sort(totals, axis=1)
    out = []
    for _ in range(int(reps)):
        chosen = np.sort(rng.choice(n_cand, size=n_sub, replace=False))
        sub = totals[chosen]
        winner_local = np.argmax(sub, axis=0)
        winner = chosen[winner_local]
        values = sub[winner_local, np.arange(n_worlds)]
        percentile, _ = _percentiles_for_picks(row_sorted, winner, values)
        out.append(percentile)
    return np.concatenate(out)


def implied_field_size(p_beyond_999: float) -> float | None:
    """Effective iid field size implied by a beyond-p999 probability."""
    p = float(p_beyond_999)
    if not 0.0 < p < 1.0:
        return None
    return math.log1p(-p) / math.log(0.999)


def _poisson_binomial_tail(probs: Sequence[float], observed: int) -> float:
    """P(count >= observed) for independent Bernoulli slates."""
    dp = np.zeros(len(probs) + 1, dtype=np.float64)
    dp[0] = 1.0
    for p in probs:
        p = float(p)
        if not 0.0 <= p <= 1.0:
            raise FieldMaxNullError("slate probability outside [0, 1]")
        dp[1:] = dp[1:] * (1.0 - p) + dp[:-1] * p
        dp[0] *= 1.0 - p
    return float(dp[int(observed):].sum())


def field_max_null_report(
    per_slate: Sequence[dict],
    observed_beyond: dict,
    n_winners: int,
    subsample_sizes: Sequence[int],
) -> dict:
    """Aggregate the frozen N1d report.

    ``per_slate`` entries carry season/week/n_candidates/n_worlds,
    ``p_beyond`` ({level: null fraction at or beyond}), ``p_zero`` (null
    fraction where the pick beats every other world in its row) and
    ``subsample`` ({n: beyond-p999 fraction}). ``observed_beyond`` maps
    level to the observed N1 winner count at or beyond that percentile.
    """
    if not per_slate:
        raise FieldMaxNullError("no slates to aggregate")
    n_winners = int(n_winners)
    if len(per_slate) != n_winners:
        raise FieldMaxNullError(
            "per-slate results do not match the observed winner count")
    levels = {}
    for level in EXCEEDANCE_LEVELS:
        probs = [float(s["p_beyond"][level]) for s in per_slate]
        observed = int(observed_beyond[level])
        levels[f"p{str(level).replace('0.', '')}"] = {
            "observed_count": observed,
            "null_expected_count": float(np.sum(probs)),
            "null_prob_count_ge_observed": _poisson_binomial_tail(
                probs, observed),
        }
    p999 = levels["p999"]
    scaling = []
    full_sizes = sorted({int(s["n_candidates"]) for s in per_slate})
    for n_sub in [int(n) for n in subsample_sizes]:
        fracs = [
            float(s["subsample"][n_sub]) for s in per_slate
            if n_sub in s["subsample"]
        ]
        if not fracs:
            continue
        mean_frac = float(np.mean(fracs))
        n_eff = implied_field_size(mean_frac)
        scaling.append({
            "field_size": n_sub,
            "n_slates": len(fracs),
            "mean_p999_fraction": mean_frac,
            "implied_effective_size": n_eff,
            "effectiveness_ratio": (
                None if n_eff is None else float(n_eff / n_sub)),
        })
    full_fracs = [float(s["p_beyond"][0.999]) for s in per_slate]
    full_mean = float(np.mean(full_fracs))
    full_eff = implied_field_size(full_mean)
    mean_pool = float(np.mean([s["n_candidates"] for s in per_slate]))
    scaling.append({
        "field_size": mean_pool,
        "n_slates": len(per_slate),
        "mean_p999_fraction": full_mean,
        "implied_effective_size": full_eff,
        "effectiveness_ratio": (
            None if full_eff is None else float(full_eff / mean_pool)),
    })

    target = float(int(observed_beyond[0.999])) / n_winners
    required_eff = implied_field_size(target)
    last_ratio = next(
        (s["effectiveness_ratio"] for s in reversed(scaling)
         if s["effectiveness_ratio"]), None)
    required_raw = (
        None if required_eff is None or not last_ratio
        else float(required_eff / last_ratio))

    if p999["null_prob_count_ge_observed"] >= NULL_EXPLAINS_MIN_PROB:
        verdict = "selection_effect_explains_n1_at_pool_size"
    elif required_raw is not None and required_raw <= FIELD_SIZE_CAP:
        verdict = "n1_nondiagnostic_within_plausible_field"
    else:
        verdict = "missing_mass_confirmed_at_winner_scale"

    prob_no_zero = float(np.prod(
        [1.0 - float(s["p_zero"]) for s in per_slate]))
    return {
        "protocol_id": PROTOCOL_ID,
        "n_slates": len(per_slate),
        "n_winners": n_winners,
        "pool_sizes": full_sizes,
        "exceedance": levels,
        "field_size_scaling": scaling,
        "observed_p999_fraction": target,
        "required_effective_field_size": required_eff,
        "required_raw_field_size": required_raw,
        "field_size_cap": FIELD_SIZE_CAP,
        "null_prob_any_pr_zero": float(1.0 - prob_no_zero),
        "verdict": verdict,
        "per_slate": list(per_slate),
        # Pure self-law computation: no realized outcome is read; the
        # observed counts enter only as published N1 constants.
        "uses_realized_outcomes": False,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
