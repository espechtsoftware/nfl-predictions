"""The measured entries sweet-spot curve (2026-08-04, Addendum 53):
P(best-of-N >= line) from the 3-season 150-entry study (54 week-slates,
reports/entries_study/). Powers the contest comparator.

p_reach interpolates in N (log-spaced between measured points) and in
the line dimension (log-linear through the three measured anchors —
capped extrapolation, honest about its range).
"""
from __future__ import annotations

import math

ANCHOR_LINES = (187.0, 194.0, 199.0)
# N: (P>=187, P>=194, P>=199)
CURVE: dict[int, tuple[float, float, float]] = {
    1: (0.019, 0.001, 0.001), 2: (0.037, 0.019, 0.019),
    3: (0.056, 0.019, 0.019), 5: (0.074, 0.019, 0.019),
    8: (0.111, 0.037, 0.037), 10: (0.167, 0.056, 0.037),
    15: (0.204, 0.074, 0.056), 20: (0.204, 0.093, 0.056),
    25: (0.241, 0.130, 0.074), 30: (0.259, 0.130, 0.074),
    40: (0.315, 0.130, 0.074), 50: (0.333, 0.130, 0.074),
    75: (0.407, 0.222, 0.111), 100: (0.426, 0.241, 0.148),
    150: (0.444, 0.259, 0.148),
}
_NS = sorted(CURVE)


def _interp_n(n: int, k: int) -> float:
    n = max(1, min(int(n), 150))
    if n in CURVE:
        return CURVE[n][k]
    lo = max(x for x in _NS if x < n)
    hi = min(x for x in _NS if x > n)
    f = (math.log(n) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return CURVE[lo][k] + f * (CURVE[hi][k] - CURVE[lo][k])


def p_reach(n_entries: int, line: float) -> float:
    """P(best of first n_entries >= line), interpolated from the study.
    Lines outside ~180-210 are capped extrapolations — treat as rough."""
    ps = [max(_interp_n(n_entries, k), 1e-4) for k in range(3)]
    xs = ANCHOR_LINES
    line = float(line)
    if line <= xs[0]:
        # extrapolate below 187 on the 187-194 slope, capped
        slope = (math.log(ps[1]) - math.log(ps[0])) / (xs[1] - xs[0])
        return float(min(math.exp(math.log(ps[0]) + slope * (line - xs[0])),
                         0.95))
    if line >= xs[2]:
        slope = (math.log(ps[2]) - math.log(ps[1])) / (xs[2] - xs[1])
        return float(max(math.exp(math.log(ps[2]) + slope * (line - xs[2])),
                         1e-5))
    if line <= xs[1]:
        f = (line - xs[0]) / (xs[1] - xs[0])
        return float(math.exp(math.log(ps[0]) + f * (math.log(ps[1]) - math.log(ps[0]))))
    f = (line - xs[1]) / (xs[2] - xs[1])
    return float(math.exp(math.log(ps[1]) + f * (math.log(ps[2]) - math.log(ps[1]))))
