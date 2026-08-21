#!/usr/bin/env python3
"""REVIEWER INSTRUMENT — independent recomputation of the A7 co-primaries.

This is not part of the A7 arm. It exists to answer one question after
the fact: does the number the finisher recorded match the number the
per-slate receipts actually imply?

It deliberately shares NO code with `finish_a7_select_ladder.py`,
`research/a7_select_ladder.py`, or `research/paired_max_stats.py`. The
sign-flip test, signed-rank statistic, threshold grid and mean delta are
re-implemented here from their definitions so that a defect in the
production evaluation path cannot hide by being reused in its own check.

Why this matters for this specific arm: A7 reads outcomes exactly once
and its protocol forbids retry, refit and re-dose. Three defects in this
repository's history (the ownership-fade mislabel, the GREEN2 env typo,
the TDLEDGER season-pooling error) lived in evaluation code, produced
well-formed output, and were caught only by instrument audit. A
disposition looks equally authoritative whether or not the arithmetic
underneath it is right.

Usage:
    python scripts/review_verify_a7_coprimaries.py --result <result.json>

Exit code 0 means every recomputed statistic agreed with the recorded
one; 1 means at least one disagreed, which is a finding to investigate
BEFORE the disposition is treated as settled.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np

# Frozen in the A7 protocol; restated here rather than imported so the
# check does not inherit a wrong constant from the code under review.
ENTRY_COUNT = 80
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
EXACT_NONZERO_LIMIT = 20
MONTE_CARLO_RESAMPLES = 200_000
MONTE_CARLO_SEED = 20_260_818
TOLERANCE = 1e-9


def _pairs(result: dict, count: int) -> tuple[np.ndarray, np.ndarray, list]:
    rows = result.get("slates") or result.get("per_slate") or result.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("no per-slate rows found in the result object")
    ordered = sorted(rows, key=lambda r: (int(r["season"]), int(r["week"])))
    key = str(count)
    control, treatment, keys = [], [], []
    for row in ordered:
        control.append(float(row["control"]["realized"]["prefix_maxima"][key]))
        treatment.append(
            float(row["treatment"]["realized"]["prefix_maxima"][key]))
        keys.append((int(row["season"]), int(row["week"])))
    return np.asarray(control), np.asarray(treatment), keys


def _signed_rank_w_plus(diffs: np.ndarray) -> float:
    """Wilcoxon W+ with average ranks over nonzero absolute differences."""
    nonzero = diffs[diffs != 0.0]
    if not len(nonzero):
        return 0.0
    order = np.argsort(np.abs(nonzero), kind="stable")
    magnitudes = np.abs(nonzero)[order]
    ranks = np.empty(len(nonzero), dtype=float)
    i = 0
    while i < len(magnitudes):
        j = i
        while j + 1 < len(magnitudes) and magnitudes[j + 1] == magnitudes[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    signs = np.sign(nonzero)[order]
    return float(ranks[signs > 0].sum())


def _sign_flip_p(diffs: np.ndarray, statistic) -> float:
    """Two-sided sign-flip p with the registered add-one correction."""
    nonzero = diffs[diffs != 0.0]
    observed = abs(statistic(diffs))
    if not len(nonzero):
        return 1.0
    if len(nonzero) <= EXACT_NONZERO_LIMIT:
        extreme = total = 0
        for signs in itertools.product((1.0, -1.0), repeat=len(nonzero)):
            flipped = np.array(signs) * np.abs(nonzero)
            padded = np.zeros(len(diffs))
            padded[: len(flipped)] = flipped
            total += 1
            if abs(statistic(padded)) >= observed - TOLERANCE:
                extreme += 1
        return extreme / total
    rng = np.random.default_rng(MONTE_CARLO_SEED)
    extreme = 0
    magnitudes = np.abs(nonzero)
    for _ in range(MONTE_CARLO_RESAMPLES):
        signs = rng.choice((1.0, -1.0), size=len(nonzero))
        padded = np.zeros(len(diffs))
        padded[: len(nonzero)] = signs * magnitudes
        if abs(statistic(padded)) >= observed - TOLERANCE:
            extreme += 1
    return (extreme + 1) / (MONTE_CARLO_RESAMPLES + 1)


def _centered_w_plus(values: np.ndarray) -> float:
    nonzero = values[values != 0.0]
    if not len(nonzero):
        return 0.0
    total = len(nonzero) * (len(nonzero) + 1) / 2.0
    return _signed_rank_w_plus(values) - total / 2.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--counts", default="80,14,4")
    args = parser.parse_args(argv)

    result = json.loads(args.result.read_text())
    findings: list[str] = []
    for count in [int(v) for v in args.counts.split(",")]:
        try:
            control, treatment, keys = _pairs(result, count)
        except KeyError:
            print(f"[skip] no prefix maxima for N={count}")
            continue
        diffs = treatment - control
        mean_delta = float(diffs.mean())
        w_plus = _signed_rank_w_plus(diffs)
        p_mean = _sign_flip_p(diffs, lambda v: float(v.mean()))
        p_rank = _sign_flip_p(diffs, _centered_w_plus)
        grid = {
            str(t): (int((control >= t).sum()), int((treatment >= t).sum()))
            for t in THRESHOLDS
        }
        print(f"\n== N={count} ({len(keys)} slates) ==")
        print(f"  recomputed mean delta      {mean_delta:+.6f}")
        print(f"  recomputed W+              {w_plus:.1f}")
        print(f"  recomputed p(mean)         {p_mean:.6f}")
        print(f"  recomputed p(signed rank)  {p_rank:.6f}")
        print("  recomputed grid (ctrl->trt):",
              {k: f"{a}->{b}" for k, (a, b) in grid.items()})

        cuts = (result.get("cuts") or {}).get(str(count))
        if not isinstance(cuts, dict):
            findings.append(f"N={count}: no recorded cut to compare against")
            continue
        recorded_mean = float(cuts["treatment_mean"]) - float(cuts["control_mean"])
        if not math.isclose(recorded_mean, mean_delta, abs_tol=1e-6):
            findings.append(
                f"N={count}: recorded mean delta {recorded_mean:+.6f} != "
                f"recomputed {mean_delta:+.6f}")
        paired = cuts.get("paired") or {}
        inference = paired.get("inference") or {}
        for label, mine, key in (
            ("p(mean)", p_mean, "p_mean_two_sided"),
            ("p(signed rank)", p_rank, "p_signed_rank_two_sided"),
        ):
            theirs = inference.get(key)
            if theirs is None:
                continue
            # Monte Carlo paths agree only to sampling error; exact paths
            # must match closely.
            tol = 0.01 if len(diffs[diffs != 0.0]) > EXACT_NONZERO_LIMIT else 1e-9
            if abs(float(theirs) - mine) > tol:
                findings.append(
                    f"N={count}: recorded {label} {theirs} vs recomputed "
                    f"{mine:.6f} (tol {tol})")
        for t in THRESHOLDS:
            rc = (cuts.get("control_threshold_counts") or {}).get(str(t))
            rt = (cuts.get("treatment_threshold_counts") or {}).get(str(t))
            mc, mt = grid[str(t)]
            if rc is not None and int(rc) != mc:
                findings.append(
                    f"N={count}: control count at {t} recorded {rc} != {mc}")
            if rt is not None and int(rt) != mt:
                findings.append(
                    f"N={count}: treatment count at {t} recorded {rt} != {mt}")

    print("\n" + "=" * 60)
    if findings:
        print("DISAGREEMENTS FOUND — investigate before treating the")
        print("disposition as settled:")
        for line in findings:
            print(f"  - {line}")
        return 1
    print("All recomputed statistics agree with the recorded values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
