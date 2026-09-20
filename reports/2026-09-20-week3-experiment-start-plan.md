# Week-3 experiment start plan

The D12800 archive is complete, so the next experiments can be prepared now and run as soon as the Sunday final status/replacement receipt is frozen. The experiments below are outcome-blind until their prospective books are frozen. They are shadows for the operator, not automatic production changes.

## 1. Paired selector shadow: `dual_emax` versus `cap_prefix_then_fill` — highest priority

The next selector arm is not a new algorithm. The lab already implements
`cap_prefix_then_fill` (PREREG-016), a weighted tail-ladder greedy with a hard
pairwise roster-overlap cap during its prefix and a disclosed unconstrained
fill. The live selector is `dual_emax`, the equal-mass incumbent/corrected-hsim
greedy expected-max law. Compare those two named consumers on the same fresh
candidate pool and simulation worlds. Use the existing overlap-cap value and
the already reviewed ladder semantics; do not tune a new rung weight after
seeing results.

The primary prospective read must be realized and paired: realized max of K,
realized 200+/210+ clear counts, and the frozen operator scorecard. Report
simulated max mean/P220/P230/P240, individual-row rates, prefix capture, and
the simulated-to-realized 220 ratio beside them. The 220 realized rate is too
sparse for a one-week adoption decision, so 200/210 and realized max are the
primary short-term read. Freeze both books before outcomes, keep the current
book as the operational control, and make any adoption decision under the
existing in-season shadow rule after the required number of graded weeks.

The simulator's extreme-tail ordering is not assumed calibrated. Prior reads
show that several extreme-tail objectives lost on realized historical panels,
while cap-prefix results sometimes improved realized performance despite
lower simulated tail rates. Treat the simulated D12800 marginal screen as a
mechanism shortlist only. No tail-ladder result from this archive can authorize
a production selector change by itself. Cite the prior ladder read and the
production cap-prefix results when the paired protocol is frozen.

Relevant prior evidence is [the paid-source ladder read](paid-source-ladder-direct-20260915/read.txt),
[the historical cap-prefix score sprint](2026-08-29-score-sprint-first-realized-results.md), and
[the prefix-order audit](2026-09-10-r6-prefix-ranking-and-breakout-capture-audit.md). These are development
or historical reads with different populations and should be cited as context,
not treated as exact D12800 law parity.

## 1a. Final-book first-entry objective comparison

Use one fresh final delivered K97 book and the exact two selection banks. Keep membership and all rows fixed. For delivered ranks 1–30, produce three order-only candidates: pooled selection mean, pooled P220/P230 tail frequency, and the existing winner-score proxy minus mean rule. Report pooled and per-bank values, the selected source rank, all prefix scores (1/10/20/30/40/80/97), and every contest block’s displaced-row cost. The primary decision is whichever objective the operator names before seeing the fresh numbers; the report must retain the other candidates and their costs.

The D12800 preview shows why this is needed: pooled mean chooses rank 7 (+4.4217 simulated first-entry mean), pooled P220 keeps rank 1, and the two component mean heads are ranks 28 and 14. The preview is scratch evidence only; the fresh Sunday book is the experiment input.

## 2. Risk-weighted exposure shadow

On the same eligible pool, compare the ordinary book, participation-selected book, and a risk-weighted exposure penalty that reduces a player’s marginal selection score as exposure approaches a declared cap. Keep a blanket cap-48 arm as the insurance reference and cap-38 as a negative control, but do not adopt either blanket cap by default. Freeze the player availability map and penalty before generation; report whole-book utility, P220, the global proxy, expected inactive slots, maximum exposure, and ten deterministic player-zero stresses. This separates concentration protection from the adverse nominal scoring cost observed in O-14.

## 3. Paid-source incremental-value shadow

For the first fresh slate where SIS, Fantasy Points, and Odds API snapshots are all complete and point-in-time bound, build one common candidate universe and four frozen score inputs: free stack, +Odds, +SIS, +Fantasy Points, and all three. Record whether each source changes served means, tails, candidate membership, selected membership, and order. Do not judge a source from a byte-identical downstream book; preserve the influence trace and source freshness/coverage. This answers the renewal question with an incremental test instead of another source-wide closure.

## Execution contract

Each shadow gets an immutable source receipt, candidate/book hashes, bank hashes, explicit information cutoff, code hash, and one create-once result. Current-week outcome columns remain unread until the operator’s settlement release. A negative or unresolved result closes only the tested implementation/information set/objective; it does not retire the method family or data vendor. Production can start item 1 immediately after Sunday receipts; item 2 needs the frozen availability map; item 3 needs all three paid snapshots.
