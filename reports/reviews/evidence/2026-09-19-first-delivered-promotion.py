"""Research-only deterministic head policy; no candidate membership change.

Inputs are delivered candidate indices, their delivered-order vetter clean/soft
flags, and the pre-existing two-component SELECTION-world candidate totals.
Audit worlds must never be passed to this decision function.
"""
import numpy as np


def promote(book,clean_or_soft,selection_totals):
    assert len(book)==len(set(book))==len(clean_or_soft)
    assert selection_totals.ndim==2 and np.isfinite(selection_totals).all()
    assert len(book)>0 and min(book)>=0 and max(book)<len(selection_totals)
    assert all(isinstance(x,(bool,np.bool_)) for x in clean_or_soft)
    # The first30 boundary is the existing premium delivery/vetting boundary.
    eligible=[r for r in range(min(30,len(book))) if clean_or_soft[r]]
    if not eligible:return list(book),dict(promoted_from_rank=1,no_eligible_clean_row=True)
    # Earliest delivered row wins an exact tie; no audit or outcome tie-break.
    means=selection_totals[np.asarray(book)[eligible]].mean(axis=1,dtype=np.float64)
    rank=eligible[int(np.argmax(means))]
    result=[book[rank],*book[:rank],*book[rank+1:]]
    assert len(result)==len(book) and set(result)==set(book)
    assert set(result[:30])==set(book[:30]) and result[30:]==book[30:]
    return result,dict(promoted_from_rank=rank+1,selection_mean=float(means.max()),
        eligible_delivered_ranks=[r+1 for r in eligible],tie_policy='earliest delivered rank')
