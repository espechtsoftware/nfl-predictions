# Put the strongest eligible standalone lineup first: a measured allocation tradeoff

A fixed ordering rule improves the ordinary book's first entry in a fresh simulation audit: **+15.011 expected points**, **+0.800 percentage points P220**, and a higher historical winner-score proxy in both simulators. It leaves every selected lineup in the book. The benefit comes from promoting a stronger existing lineup to the Millionaire position, with a corresponding cost to the contest block giving it up.

On this particular ordinary book the rule promotes delivered rank2 to rank1. On the full participation book it makes no change. The chosen row is determined from the original selection banks, not the audit scores. This is a new, explicitly post-inspection diagnostic; it is not historical adoption validation or demonstrated NFL performance.

## The rule and its provenance

Among clean/soft lineups already in the first30 delivered rows, promote the largest standalone expected score under the book's own equal-mixture selection banks. Break exact ties by earliest delivered rank and preserve every other row's relative order. The first30 boundary already exists in production vetting. Membership, the first30 set and ranks31–97 remain unchanged.

The workstation independently traced the underlying issue and reviewed the policy source (`25b2a3a`, `d6afed2`): the vetter sorts risk tiers but retains incremental portfolio-greedy order inside each tier. Ordinary's first eight greedy rows are material-risk rows, so its first delivered row is greedy rank9, even though a stronger clean lineup survives at greedy rank11/delivered rank2. Full participation already delivers that stronger lineup first.

The [policy](reviews/evidence/2026-09-19-first-delivered-promotion.py) froze at `1874e712`. The [protocol](2026-09-19-first-delivered-promotion-protocol.md) and [reader](reviews/evidence/2026-09-19-first-delivered-read.py) froze at **840d2bbb** before this new evaluation. The caller derives eligibility as **not hard and not material** from the unchanged vetter receipts. Both original selections reproduce exactly before promotion; all four books are frozen before audit draws. Fresh seeds16260919/17260919 and availability seed20260919058 are distinct from the preceding comparisons. The exact original actual-host player-score banks are reproduced before new draws.

## First-entry benefit and transferred cost

| Metric, promoted minus ordinary | Incumbent | Hsim | Equal mixture |
|---|---:|---:|---:|
| First-entry expected score |+11.578|+18.444|**+15.011**|
| First-entry P220 |+0.120pp|+1.480pp|**+0.800pp**|
| First-entry winner-score proxy |+0.001938|+0.016410|**+0.009174**|
| Ranks2–24 expected maximum |+0.151|−1.246|**−0.547**|
| Ranks2–24 P220 |0|−1.030pp|**−0.515pp**|
| Ranks2–24 winner-score proxy |+0.000367|−0.006218|**−0.002926**|

The first-entry mixture intervals are **[+14.560,+15.463] points**, **[+0.647,+0.953] pp P220**, and **[+0.008369,+0.009979] proxy**. Incumbent P220 is uncertain: its interval is **[−0.049,+0.289] pp**. In the preceding fresh audit its P220 point difference was negative. The first-entry expected score and winner-score proxy improve in both component audits, but a robust extreme-tail improvement in both simulators is not established.

The ranks2–24 mixture cost is also clear in this model: Emax interval **[−0.632,−0.463]**, P220 **[−0.644,−0.386] pp**. It reflects reallocating a stronger standalone lineup out of that block; the hsim component drives this particular block loss. These are Monte Carlo intervals with fixed laws, not confidence intervals for real football or payouts.

**Every other tested prefix/block is exactly unchanged**, including first10, first20, first30, the entire97-entry book, and all ranks25–97. This particular policy chooses rank2, so its only numerical changes are first1/block1 and block2–24. Full participation is a complete no-op in every region. Results are identical under participation and all-active assumptions for the affected regions because neither moved lineup contains a designated-risk player. The full [numerical result](reviews/evidence/2026-09-19-first-delivered-result.json) retains all20regions, both simulators and both availability assumptions.

## Recommendation

For the stated preference to give the stronger standalone lineup the Millionaire opportunity, this is a reasonable **ordering candidate to review on the actual completed book**. It does not require accepting P_MIX or changing which97lineups are selected. It is not a whole-portfolio scoring improvement, a Pareto improvement across contests or a measured profit improvement. Actual contest payouts, field strength and duplication were not modeled here.

Use the general rule on the new book with fresh availability and the actual selection-bank identities; do not copy research row2 or this roster into a different build. Keep the ordinary delivered order for comparison and show the affected contest block explicitly. If full participation already puts its strongest eligible standalone lineup first, retain that no-op. No live entry, contest mapping, source or timer was changed. The reader completed in19.23seconds. **The workstation independently regenerated the fresh audit banks and reproduced every decision and numerical result exactly** in handoff `118afa4`, received14:15:35UTC. The [portable add-on](reviews/evidence/2026-09-19-first-delivered-publication.json) is published and download-verified. Exact replay does not change the exploratory or model-conditional interpretation.

A [named research lineup preview](reviews/evidence/2026-09-19-head-research-preview-names.csv) makes the permutation inspectable:97identical rosters, first two positions exchanged in this research book, all later rows unchanged. Its [receipt](reviews/evidence/2026-09-19-head-research-preview-receipt.json) binds the original book and frozen result. This is not Sunday's operating corpus or an entry upload file.
