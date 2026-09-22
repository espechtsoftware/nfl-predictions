"""Exact lazy-greedy expected-max selection over the dual (incumbent + corrected-hsim) banks.

Identical objective to nfl2.selectors.select_expected_max on the equal-mass
concatenation Td = [T_inc | T_hs]; CELF only changes the evaluation order, not
the result, because the marginal gain is submodular and therefore monotone
non-increasing in the book.

An optional per-player exposure cap makes a candidate INFEASIBLE once any of its
players is at the cap. Exposure counts never decrease, so an infeasible candidate
can be dropped permanently -- this is the only difference between the arms.
"""
from __future__ import annotations
import heapq
import numpy as np


def emax_select(T_inc, T_hs, k, *, caps=None, roster_idx=None, n_players=None,
                verbose=False):
    """caps: array of per-player maximum appearances (len n_players), or None."""
    n, w1 = T_inc.shape
    w2 = T_hs.shape[1]
    W = w1 + w2
    cur1 = np.full(w1, -np.inf, dtype=np.float64)
    cur2 = np.full(w2, -np.inf, dtype=np.float64)
    have_cur = False
    counts = np.zeros(n_players, dtype=np.int32) if caps is not None else None

    def gain_of(i):
        if not have_cur:
            return (T_inc[i].astype(np.float64).sum() + T_hs[i].astype(np.float64).sum()) / W
        g = (np.maximum(T_inc[i], cur1).sum() + np.maximum(T_hs[i], cur2).sum()) / W
        return g - base

    base = 0.0
    # initial gains, chunked
    g0 = np.empty(n, dtype=np.float64)
    step = 512
    for a in range(0, n, step):
        b = min(a + step, n)
        g0[a:b] = (T_inc[a:b].astype(np.float64).sum(axis=1)
                   + T_hs[a:b].astype(np.float64).sum(axis=1)) / W
    heap = [(-g0[i], i, 0) for i in range(n)]
    heapq.heapify(heap)

    book, taken = [], np.zeros(n, dtype=bool)
    dropped = np.zeros(n, dtype=bool)
    it = 0
    while len(book) < k and heap:
        negg, i, stamp = heapq.heappop(heap)
        if taken[i] or dropped[i]:
            continue
        if caps is not None:
            r = roster_idx[i]
            if (counts[r] + 1 > caps[r]).any():
                dropped[i] = True
                continue
        if stamp == it:
            taken[i] = True
            book.append(i)
            np.maximum(cur1, T_inc[i], out=cur1)
            np.maximum(cur2, T_hs[i], out=cur2)
            have_cur = True
            base = (cur1.sum() + cur2.sum()) / W
            it += 1
            if caps is not None:
                np.add.at(counts, roster_idx[i], 1)
            if verbose and len(book) % 20 == 0:
                print(f"  picked {len(book)}", flush=True)
        else:
            heapq.heappush(heap, (-gain_of(i), i, it))
    return book, (counts if caps is not None else None)
