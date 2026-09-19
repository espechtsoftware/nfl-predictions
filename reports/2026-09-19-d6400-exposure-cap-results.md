# Exposure caps buy some single-player protection and cost modeled scoring utility

On the completed D6400 pool, blanket caps are **an insurance tradeoff, not a demonstrated scoring improvement**. The primary48-per-player cap on the participation-selected book reduces Jefferson exposure58→48, with a small nominal utility cost. If Jefferson is forced to score zero, the capped book does better. Some other player-zero scenarios get worse. The tighter38cap buys more Jefferson protection at a larger nominal scoring cost.

This executes the [O-14 protocol](2026-09-19-d6400-exposure-cap-protocol.md) for Week3research; no Week2entry/source changes. Both uncapped ordinary/participation controls reproduce exactly. Four capped treatments and three controls make seven frozen legal unique K97books from the same3,366eligible candidates and42exclusions. Caps apply to every roster identity, including QB/DST, with no silent relaxation. Four mechanics assertions cover binding/loose caps, deterministic ties and refusal when a cap prevents completing K.

Proposal source/protocol froze at **aa6e9eeb**. The [seven-book packet](reviews/evidence/2026-09-19-d6400-exposure-cap-frozen-books.json), SHA `53bba4df0a9a5394323ea8bbf39273b11503a77e50d1c854f1e0e7a9e3e042eb`, and [reader](reviews/evidence/2026-09-19-d6400-exposure-cap-read.py) froze at **01208c60** before effects. Both original player banks again reconstruct exactly; fresh event seeds24260919/25260919, availability20260919064. Proposal construction84.9seconds, audit construction23.5seconds, complete read2.7seconds. [Audit identities](reviews/evidence/2026-09-19-d6400-exposure-cap-audit-receipt.json), [all results](reviews/evidence/2026-09-19-d6400-exposure-cap-result.json), SHA `c809be0043aec4c0b10eda6719c759ba13bfea6a49162b0ef02f1c30f9fe5fb7`. No current outcomes were read.

## Ordinary-world costs

Each difference is the capped book minus its own uncapped selection-law control. P220 changes are percentage points; all numbers below are the equal I/H mixture. Intervals are Monte Carlo error within fixed laws, not NFL/model/probability-map uncertainty.

| Selection law / cap | Changed members | All-active mean-max | All-active P220 | Participation mean-max | Participation P220 | Participation proxy |
|---|---:|---:|---:|---:|---:|---:|
| Ordinary /48 |4|−0.0298|−0.015pp|−0.0597|−0.025pp|−0.000350|
| Ordinary /38 |16|−0.3155|−0.330pp|−0.2582|−0.205pp|−0.001860|
| Participation /48 |12|−0.0799|−0.070pp|−0.0451|−0.110pp|−0.000693|
| Participation /38 |24|−0.2903|−0.375pp|−0.3259|−0.490pp|−0.003092|

The primary participation48cap proxy change is **−0.000693**, MC95 **[−0.001248,−0.000137]**. Its mean-max interval **[−0.1146,+0.0244]** and P220 interval **[−0.2864,+0.0664] pp** crosszero. Components disagree: incumbent mean-max/P220/proxy **−0.3221/−0.410pp/−0.002258**, hsim **+0.2319/+0.190pp/+0.000872**. This is not a robust cross-component benefit or a precise NFL loss estimate.

The38cap has clearer adverse nominal results: participation mean-max **−0.3259 [−0.4265,−0.2252]**, P220 **−0.490 [−0.726,−0.254] pp**, proxy **−0.003092**. Both components are adverse on all three. The result applies to this blanket-cap implementation, fixed information/laws and greedy search budget; it does not retire targeted risk controls or other portfolio methods.

## What the caps protect, and what they do not

The ten stress identities were fixed from the original control's most-exposed players before this audit. Each stress sets that player's/slot's score to zero while preserving the other draws; it does not redistribute teammate usage or estimate the probability of the event. DST stresses are literally zero scores, not inactive defenses.

| Participation-selected book | Jefferson count | Mean-max when Jefferson is zero | P220 when Jefferson is zero | Change in stressed mean-max vs uncapped |
|---|---:|---:|---:|---:|
| Uncapped |58|188.8451|8.340%|—|
| Cap48 |48|190.2039|9.250%|+1.3589|
| Cap38 |38|191.5815|9.670%|+2.7365|

These are **absolute stressed outcomes**, so the improvement does not merely reflect a lower starting point. The uncapped Jefferson-zero loss is10.0702mean-max points;48cap8.6315;38cap7.0435. However, the48cap's absolute stressed mean-max is worse than uncapped for Bijan Robinson (**−0.3532**), Javonte Williams (**−0.2182**) and Drake London (**−0.1262**) zero-score scenarios. The38cap also worsens several other stresses. Full component, proxy and P220 stress results remain in the reader output; no single favorable scenario is an overall robustness verdict.

Availability weighting and concentration remain distinct. Expected inactive player slots under the fixed map are **4.7422 uncapped,4.6628 at48,5.2722 at38**; discounted lineups **14,14,16**. A lower cap can move the book toward more uncertain players. A cap is not a substitute for fixing how availability enters selection.

## Delivery scope and next step

The cap first changes greedy positions **90/71** under ordinary48/38, and **83/66** under participation48/38. First30 and first40 greedy prefixes are unchanged in these comparisons. **These cap/control orders are before delivery vetting**, whereas the common `control` artifact is the real delivered v4.3 book. Do not call their prefix/block diagnostics final contest-allocation effects. Whole-book values remain invariant to a row-only vetting permutation on the same fixed eligible population; a fresh-status consumer can change membership and requires its own run.

Keep48cap as an explicit robustness option for Week3shadow comparison, not a blanket scoring upgrade. The38cap's greater nominal cost makes it a useful negative control, not the default recommendation. Before any trial, state the amount of scoring upside the operator is willing to exchange for protection and show complete final-book delivery. Do not estimate that preference or a zero-score event probability from these stress scenarios.

The more direct scoring work remains participation calibration/official-status handling, eligible-pool quality, and first-entry ordering. Next concentration experiments should separate **risk-weighted exposure control** from blanket caps and test uncertainty in the activity law; collect proper prospective availability scores and preserve prelock books. A healthy player's high exposure and45lineups on a Doubtful player are different problems. O-14 now has measured costs/protection but is not resolved or adopted by this report. Independent production replay is requested before a numerical-verification conclusion.
