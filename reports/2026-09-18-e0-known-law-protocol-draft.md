# E0: selection precision under a known scoring law

September 18, 2026. Draft for workstation review before execution. This is the first stage agreed in
`2026-09-18-reply-and-next-week-plan.md`; it does not reopen PREREG-101 or read any NFL results.
Erich asked to advance independent experiment work while other jobs run.

## Question and scope

For a fixed synthetic candidate pool, how much expected-maximum value is lost to finite decision
samples versus greedy search? How optimistic is evaluating the selected book on its decision sample?
The true joint scoring law is enumerated exactly. We can therefore measure both losses without
assuming that a simulator describes real football correctly.

These are abstract candidate scores, not legal DraftKings rosters. Their units and threshold have no
empirical NFL calibration. This study tests measurement and selection mechanics, not player prediction,
paid-source value, or a claim that our production optimizer is suboptimal by a measured amount.

## Frozen construction proposed for review

Use all 64 binary states of six independent Bernoulli variables. State ordering is binary integer
order 0 through 63. Each state has its product probability. Use two explicitly labelled laws:
A: six probabilities 0.5; B: six probabilities 0.1. Both retain all 64 states with positive mass.
Do not search for a law that gives a desired result.

Construct exactly twelve candidates, i=0,...,11, with the following deterministic scores in state z:

    a = i % 6
    b = (a + 1) % 6
    c = (a + 3) % 6
    score(i,z) = 120 + 2*i + 55*z[a] + 35*z[b] + 20*z[c]
                 + 15*(i >= 6)*z[a]*z[b]

This deliberately gives candidates shared risks, unequal baselines, and occasional complementary
payoffs. There is no candidate generation randomness or tuning. Report the complete score/probability
arrays and their hashes, not only the generating seed. Fix K=1 and K=3; use every prefix of the same
candidate ordering only for tie breaking, not as additional dose arms. Threshold 220 is illustrative.

For each law and K enumerate all candidate subsets (12 or 220) to obtain the true optimum of
E[max score in book]. Also compute greedy selection under the true law. Greedy first selects the
highest expected score, then maximizes expected marginal improvement of the existing book maximum.
Break numerical ties within absolute tolerance 1e-12 by smallest candidate ID, or lexicographic sorted
subset for exact enumeration. Do not use a threshold-hit objective as a substitute.

## Sampling and comparison

Decision-world counts: 32, 128, 512, 2048. Run 100 prespecified replicates numbered 0,...,99.
For each law/replicate generate 2048 states and take nested prefixes for the four counts. Use NumPy
PCG64 with SeedSequence([20260918, law_index, replicate, stream_id]); stream 0 is decision sampling.
Record NumPy/Python versions and script hash. Candidates remain fixed for every count and replicate.

Select a greedy book and an exact empirical-optimum book from the same decision sample. Evaluate both
books using the exact 64-state law. Separately evaluate the selected greedy book on 8192 independent
audit states (stream 1). Audit draws are shared across counts within a replicate, never used to choose
books, and never reused as decision draws. The exact law is the reference; independent audit error is
measured against it, not silently treated as truth. Streams are separate across laws and replicates.

## Outputs and interpretation fixed before execution

Primary diagnostic: per-law/per-K mean exact-law regret of sampled greedy selection versus the exact
true-law optimum, paired differences from 32 to 2048 decision worlds, and all intermediate counts.
No adoption/pass criterion. Report means, medians, 5th/95th replicate quantiles and Monte Carlo standard
errors for means and paired differences. Replicates quantify simulation variation, not NFL uncertainty.
No assertion that regret or threshold calibration must change monotonically.

Decompose each greedy book's true regret exactly:

    [true optimum - true value of sampled exact-optimum book]
    + [true value of sampled exact-optimum book - true value of sampled greedy book].

The first term is finite-sample selection loss for exact empirical optimization (nonnegative). The
second is a signed comparison: greedy can regularize by accident and outperform the empirical optimum
on truth. Do not call that signed term a universally nonnegative greedy loss. Separately report true-law
optimum minus true-law greedy value, which is the nonnegative population greedy gap.

For every selected book also report decision estimate minus exact-law value (selection optimism),
audit estimate minus exact-law value, and decision/audit/true P(max >= 220). Threshold differences use
percentage points; ratios are omitted when the denominator is zero. Selection objective and threshold
diagnostics are not interchangeable. Retain selected IDs, selection order, exact values and sampling
estimates for every replicate/count. No best-case-only examples in the summary.

## Mechanics checks and runtime bound

Before the main loop, verify probability mass one, finite scores, valid unique book IDs, exact
optimizer at least as good on its own objective as greedy, K=1 exact/greedy agreement, decomposition
identity, and audit/decision stream separation. A deterministic complementary-payoff toy fixture should
verify that the second greedy pick uses marginal portfolio gain rather than standalone mean. Compare
vectorized objective calculations with a direct implementation on that fixture. Fail on violations.

Local CPU only, one process, BLAS threads limited to one, maximum five minutes and 512 MiB working arrays.
Enumerate subsets using weighted state-frequency vectors instead of materializing subset-by-world tensors.
No cloud, vendor requests, training, NFL artifact reads, new candidates, or production configuration edits.
If the runtime bound trips, publish the incomplete run and amend the budget before retry; do not silently
reduce the replicate count. Freeze and commit the executable implementation before the full run.

## Routing and review request

First confirm the implementation measures the proposed estimands and passes its mechanics checks. The
synthetic effect size does not estimate the real NFL effect or justify increased live compute spending.
After this study, the separate existing Week-1 D800 pool pilot needs artifact identity/schema checks,
independent model-world construction, explicit outcome exclusion and its own bounded protocol. A
full historical reconstruction remains conditional, not automatically authorized by synthetic results.

Workstation review requested: agree or amend the construction, exact-versus-greedy decomposition,
independent audit streams and reporting contract before this study runs. No deadline pressure from
Week 2: this study is isolated from Sunday operations and will not alter the entered spreadsheet.

## Execution amendment before any full-run result: September 18

Erich explicitly directed continued progress without waiting for him. The requested workstation review
has not arrived. Proceed with this bounded, exploratory synthetic mechanics study after local checks,
with independent peer review pending; do not describe the result as independently verified. The original
construction, counts, seeds, objectives and compute limits are unchanged. No production adoption or
NFL outcome read is authorized by this execution amendment. The implementation is committed before
execution, and both the source and outputs will be submitted for review. This changes the draft's
review-before-execution sequencing explicitly rather than silently treating an absent reply as approval.

Implementation: `reports/reviews/evidence/2026-09-18-e0-known-law.py`. Initial mechanics checks pass,
including a complementary-candidate fixture for marginal rather than standalone selection. Implementation
uses at most 220 by 64 subset-state values per K, well below the working-array cap. K arms reuse the
same per-law/replicate decision and audit streams intentionally; they are not independent replicates.
