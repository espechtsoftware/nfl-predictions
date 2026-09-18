# E0d: bounded one-for-one retrieval search on the retained D800 pool

September 18, 2026. Operator prioritizes retrieval and weekend readiness. This separately frozen
experiment follows E0c; it does not change live books or read actual outcomes. Independent review pending.

Question: does the full-archive greedy K80 book leave objective value recoverable by simple one-for-one
replacements, once sampling error is removed relative to the finite archive? This is a lower bound on
heuristic search headroom in that empirical law, not an exact optimality gap or an NFL effect.

Inputs, hashes, array/roster order, equal component weights and GLOBAL_WEMAX_PROXY utility are exactly
E0c's pinned397-player/800-candidate/20000-column archive. Reuse the hash-verifying outcome-excluding
loader; no actual/rank/summary columns. Read the same fixed historical utility constants as declared in
E0c. First reproduce the saved E0c reference book and utility within1e-12; refuse on mismatch.

Start with that K80. Exhaustively score every possible one-for-one replacement of a selected candidate
with an unselected candidate under the full empirical law. Compute objective using current best and
second-best utility per world. Keep the greatest positive improvement >1e-12; exact/tolerance ties
prefer earlier removed book slot, then lower archive candidate index. Repeat at most THREE accepted
swaps. If no improvement exceeds tolerance, stop and record one-swap local optimality at that iteration.
Three swaps is a budget, not a claim of convergence. No multiswap grid or parameter tuning afterward.

Reorder the resulting80-member set by the same full-law greedy utility objective. Report original,
unreordered-final and reordered-final prefixes1/10/20/40/80 with proxy, raw expected max and P220.
Report turnover, swapped indices, per-step gains and timing. Secondary no-harm screen: reordered book
must not lower full-law proxy at ANY named prefix more than1e-12 to be nominated for further testing.
If it fails, report the failure, no repair/tuning in this study. Passing is not live-adoption permission.

Check optimized replacement scores against a direct small synthetic fixture, including tied best values,
and full-array evaluation for each accepted replacement. Confirm exact input identities, baseline
reproduction, uniqueness, monotonic full-book utility and no outcome columns read. Single process,
one BLAS/OpenMP thread, five-minute compute cap (ten-minute wall including download), <1GiB arrays.
If incomplete publish status without silently narrowing the search. Commit script before run.

Routing: nontrivial stable search improvement nominates an independently evaluated current-week
shadow comparison; tiny/no gain redirects effort toward original-law/tail discrimination and capture,
not a wider arbitrary swap grid. New outcome-based efficacy requires its own declared reader and
cohort. Neither failure nor success closes all selection methods, changes dose, or spends operator stakes.
