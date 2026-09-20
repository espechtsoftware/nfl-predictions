# Fresh K97 final-book ordering screen

This is the fresh post-status/replacement rerun of the outcome-blind D12800
first-entry screen. It uses the archived identity frame, the 12,555 candidate
rows, and the two frozen 10,000-world banks. It excludes `actual` and all
current-week result data.

## Result

| Objective | Chosen source rank | Candidate | Value | Change from final-book row 1 |
|---|---:|---:|---:|---:|
| pooled mean | 7 | 2123 | 144.30887 | +4.42167 points |
| pooled P220 | 1 | 12413 | 0.785% | 0.000 pp |
| pooled P230 | 7 | 2123 | 0.340% | +0.045 pp |

The production promotion moved source rank 7 to row 1, so this independent
screen reproduces the live ordering decision exactly. No additional ordering
change is indicated.

The conditional simulated cost of putting rank 7 first, while holding the
rows 2–24 block fixed, is −0.4771 mean-max points, −0.290 percentage points
of P220, and −0.150 percentage points of P230. Those are portfolio tradeoff
diagnostics, not a contest-outcome estimate.

The two simulation components disagree on the head: the incumbent bank's
mean head is rank 28 and its P220 head is rank 20; the corrected-hsim bank's
mean head is rank 14 and its P220 head is rank 21. The pooled equal-mass rule
therefore remains preferable to selecting a single component's head.

## Decision

Retain the current promoted ordering. The result is a completed shadow read,
not authorization for a new selector or a post-lock edit. Keep the paired
`dual_emax` versus `cap_prefix_then_fill` selector experiment as the next
prospective test, with realized max-of-K and 200+/210+ clears as the short-term
primary measures.

Evidence: `reports/reviews/evidence/2026-09-20-d12800-fresh-final-ordering-result.json`
(`c55aee48b446417f9e3e0356c275b85dd17e3342018b00d29ae20d90e3adde18`).
