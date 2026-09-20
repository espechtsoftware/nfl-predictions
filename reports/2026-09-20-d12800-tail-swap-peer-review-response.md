# D12800 tail-swap peer review and revised Week-3 protocol

The lab reviewed the candidate-tail diagnostic and controlled candidate-848 swaps in handoff commit `f462aff`. It agrees with the central finding: the selected K97 is enriched for simulated high-tail candidates, candidate 848 is highly redundant with selected rows, and swapping it into ranks 8, 46, or 97 does not improve the portfolio max. There is no Sunday book change.

The review identifies an important naming and validation correction. The proposed marginal tail coverage arm already exists as the lab's `cap_prefix_then_fill` frontier law (PREREG-016): a weighted threshold ladder with a hard pairwise roster-overlap cap during the prefix and an explicit unconstrained fill. The live control is `dual_emax`, the equal-mass incumbent/corrected-hsim expected-max greedy. Week 3 should therefore compare these two named selectors on the same pool and worlds, rather than introduce a new tail selector from the D12800 screen.

The paired shadow will freeze both books before any outcome read and report:

* realized max-of-K and realized 200+/210+ clear counts as the short-term primary read;
* simulated max mean, P220, P230, and P240, individual-row rates, prefix capture, and roster overlap;
* the simulated-to-realized 220 ratio for every arm; and
* both selection-bank components plus the independent audit where available.

The launch receipt must also freeze the exact ladder parameters. PREREG-016's
lab contract is gamma 4 with inclusive rungs 194/200/210/220 and weights
1/2/6/12; the historical production cap-prefix read used a different strict
200/210/220 contract. The requested 220/230/240 focus is a separately named
variant until its weights and overlap cap are explicitly frozen. It must not be
called an exact law-parity comparison while those parameters differ.

The 220 realized event is too sparse for a one-week adoption decision, and prior historical reads show that simulated extreme-tail objectives can lose on realized panels. A simulated D12800 improvement is therefore mechanism evidence only. Any selector adoption remains under the existing in-season paired shadow rule and requires the frozen realized scorecard. The revised execution plan is [here](2026-09-20-week3-experiment-start-plan.md).

Context reads: [paid-source ladder](paid-source-ladder-direct-20260915/read.txt), [historical cap-prefix result](2026-08-29-score-sprint-first-realized-results.md), and [prefix-order audit](2026-09-10-r6-prefix-ranking-and-breakout-capture-audit.md). These use different populations and are not exact D12800 law-parity evidence.
