"""Choosing m entries for ONE big contest from the week's book (study 32's rule R4, OFFERED 2026-10-06; Addendum 137).

The operator holds 1-3 entries in a big contest (a $4,444 MEGA, a $333 Wildcat, ...). Study 32 measured how to choose
them from the week's entered rows: with ONE entry no rule beat a uniformly random pick (single-row ranking is a coin flip,
as A13 / A62 / A93 found); with 2-3 entries, choosing the SET that maximises the simulated chance that AT LEAST ONE of
them finishes in the contest's top S (joint coverage, R4) beat random by +0.030 [+0.001, +0.060] pooled, +0.069 at m 3.
The simulator over-sold the edge about 3x (simulated +0.084), so the choice is printed beside book order (R0) and the
random baseline, and the pair is recorded every week (the paired R0-vs-R4 shadow of the frozen §5).

These are the frozen study-32 definitions (nfl2 experiments/s32_sorting.py @ 903a2ce: g_line, choose's R4 / RND), here
without the panel harness; tests/test_entry_choice.py pins parity on a fixed input. The worlds and the PRE-LOCK field are
built the way study 32 built them (the run's two banks thinned to W_SIM worlds; FIELD_SIM lineups from the vendored
field sampler on predicted ownership, DSTs uniform, with deviation note 1's fallback).
"""
from __future__ import annotations

from itertools import combinations, islice
from math import comb

import numpy as np
from scipy.stats import binom

W_SIM, FIELD_SIM, SEL_FALLBACK_N = 1000, 20_000, 10_000       # study 32 (S16.W_SIM, S16.FIELD_SIM; deviation note 1)
MAX_M = 4                                                     # C(K, m) is exhaustive; study 32 measured m <= 3


def g_line(F: np.ndarray, N: int, S: int, m: int) -> np.ndarray:
    """P(the best own entry is in the top S | its field CDF F), N - m independent opponents; ties count as losses."""
    return binom.cdf(S - 1, max(N - m, 0), 1.0 - F)


def worlds(bank_a: np.ndarray, bank_b: np.ndarray, w_sim: int = W_SIM) -> np.ndarray:
    """Study 32's world matrix: the two banks side by side (players x 2n), every (2n // w_sim)-th column, first w_sim."""
    draws = np.concatenate([bank_a, bank_b], axis=1)
    return draws[:, :: max(1, draws.shape[1] // w_sim)][:, :w_sim]


def field_cdf(W: np.ndarray, field_rows: np.ndarray, book_ix: list[list[int]]) -> np.ndarray:
    """F (book rows x worlds): each row's share of the sampled field it BEATS in each world (ties are not beaten)."""
    fsc = np.sort(W[field_rows].sum(axis=1), axis=0)
    rs = np.stack([W[x].sum(axis=0) for x in book_ix])
    return np.stack([np.searchsorted(fsc[:, j], rs[:, j], side="left") for j in range(rs.shape[1])], axis=1) / fsc.shape[0]


def joint_coverage(F: np.ndarray, N: int, S: int, m: int, chunk: int = 20_000) -> tuple[list[int], float, float]:
    """R4: the m-subset of rows (0-based) maximising the simulated P(at least one in the top S), exhaustive over C(K, m),
    ties to the FIRST subset in lexicographic order (np.argmax over the full list, as the frozen choose()); also returns
    its value and RND's (the mean over every subset). Chunked, so a 110-row book fits in memory."""
    k = F.shape[0]
    if not 1 <= m <= min(MAX_M, k):
        raise ValueError(f"m must be 1..{min(MAX_M, k)} for a {k}-row book (got {m})")
    it = combinations(range(k), m)
    best, best_v, tot, n = None, -np.inf, 0.0, 0
    while True:
        block = np.array(list(islice(it, chunk)))
        if block.size == 0:
            break
        v = g_line(F[block].max(axis=1), N, S, m).mean(axis=1)
        j = int(np.argmax(v))
        if v[j] > best_v:                                      # strictly greater: an earlier chunk keeps a tie
            best_v, best = float(v[j]), [int(x) for x in block[j]]
        tot += float(v.sum()); n += len(v)
    assert n == comb(k, m)
    return best, best_v, tot / n


def value_of(F: np.ndarray, rows: list[int], N: int, S: int, m: int) -> float:
    """The simulated P(at least one of `rows` in the top S)."""
    return float(g_line(F[rows].max(axis=0), N, S, m).mean())


def seats_at_or_above(payout_summary: list[dict], line: float) -> int:
    """S: the number of places paying at least `line` (DraftKings' payoutSummary: minPosition / maxPosition tiers)."""
    best = 0
    for t in payout_summary or []:
        v = sum(float(p.get("value") or 0) for p in t.get("payoutDescriptions", []) if p.get("payoutDescriptionType") == "Text")
        if v >= line:
            best = max(best, int(t["maxPosition"]))
    return best
