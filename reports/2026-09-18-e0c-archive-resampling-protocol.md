# E0c: bounded D800 empirical-distribution selection-stability pilot

September 18, 2026. Frozen before performance evaluation. Exploratory, conditional on the archived
September 10 D800 pool and its two selection banks. No live changes, candidate generation, training,
cloud execution or 2026 actual-score reads. Independent review pending; operator directed progress.

## Estimand and inputs

Treat the equal-mass mixture of the archived incumbent and corrected-hsim matrices as a FINITE
empirical joint distribution. This is not the true NFL law or an independent original-law audit.
Sampling decision worlds from this fixed distribution permits exact evaluation over its full 20,000
columns. It measures resampling instability conditional on what was archived, including its omissions.

Pin object generations and SHA256 in the existing archive-schema and archive-identity evidence files.
Verify full NPY bytes against this archive's own receipt BEFORE consuming values; verify shape, dtype,
finite values and exact frame-order/roster hashes. No 392-player or Week-2 hashes may be substituted.
Read only candidate cand/players/salary and frame id; never actual, ranks, summary estimates or book files.
Use all 800 candidates and all 397 player rows without data-dependent filtering.

Primary selection objective: GLOBAL_WEMAX_PROXY using the existing fixed 48-value historical utility
registry and bandwidth 8. Pin registry SHA256 4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f
from lab source; read registry bytes from archived clean revision fa5d035. Those fixed historical utility
constants are the ONLY outcome-derived registry read; no slate actuals or experimental results are read.
Compute candidate raw totals by summing the nine mapped player rows in float64; apply the monotone
utility to each candidate-world total. This is a numerically specified pilot, not an assertion of
bitwise original-book replay (archived summation/order precision may differ).

## Reference and treatments

Reference: weighted greedy expected maximum of utility over all 20,000 columns, K80. It is a
full-archive GREEDY reference, not an exact optimum. Its value is known for that book on this finite
law; no global-optimality or true-regret claim follows. First maximize standalone mean utility, then
mean marginal utility gain; deterministic ties select first candidate in archive order.

Decision sample sizes 1000, 5000, 20000 total columns, exactly half sampled with replacement from each
component. Five replicates numbered 0..4, RNG PCG64 SeedSequence([20260918,3,replicate,component]).
Draw 10,000 indices per component and use nested prefixes for sample sizes. Generation randomness
is absent: candidates remain fixed. Both components retain 50% mass, regardless of duplicate counts.
Collapse duplicate columns into frequency weights for computation; do not resample individual players.
No independent audit draws are needed: exact evaluation uses the entire finite distribution.

Select an ordered K80 book for each case and evaluate prefixes K=1,10,20,40,80. No post-selection
vetting, reordering, roster swaps or changes to the historical candidate population. Report all cases.

## Outputs and routing

Primary: full-archive GLOBAL_WEMAX_PROXY difference from the full-archive greedy reference, at K80,
for every count/replicate. Signed differences are allowed: a sampled greedy path could exceed the
reference under the full law. Report decision estimate minus full-law value separately. Secondary:
all named prefixes, raw expected maximum, P(book max>=220), Jaccard versus reference prefix,
selected candidate indices and cross-replicate variability. Aggregate means/ranges/Monte Carlo SE
with n=5 prominently labelled a small engineering pilot, not confirmatory NFL inference.

Retain full-law and decision values of the SAME book to avoid attributing changed books to estimation
bias. Compute paired 1000-to20000 contrasts across the five shared seed replicates, without a pass/fail
threshold. Differences in overlap alone do not imply meaningful value differences.

Checks before main selection: hashes/shapes/finite arrays, mapped roster identities, utility-registry
identity/count, weighted greedy parity with explicit duplicated worlds on a complementary synthetic
fixture, K1 top-mean agreement, unique 80-candidate books, full-law evaluation of every selected book,
nondecreasing prefix objective. Validate chunked and scalar evaluation agree on selected prefixes.

Single local process, BLAS/OpenMP one thread, maximum five minutes of computation after downloads,
working-array budget 1 GiB. No other heavy local work in parallel. External wall timeout ten minutes
includes downloads. On cap/failure report incomplete status; no silent replicate reductions or retries.
Commit the executable before the full run. Record source SHA, dirty state, registry hash, input hashes,
versions, timing and all summaries. No separate candidate/model-performance look at actual outcomes.

## Interpretation limit

Even tiny resampling sensitivity would not prove correct tails, efficient greedy K80 search, or that
more accurate new information cannot help. Large sensitivity would nominate precision work under this
finite law, not automatically authorize higher live compute. Do not interpret bootstrap conditioning
on originally selected worlds as a fresh independent audit of the original construction. Next routing
is based on this bounded report and reviewer critique, not an automatic full-panel rebuild.
