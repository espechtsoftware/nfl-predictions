# D6400: a useful first-entry ordering candidate and an availability-sensitive selection gain

The broader comparison finds a practical candidate for putting a stronger lineup first. Applying the already frozen promotion rule to the actual fresh v4.3 D6400 book moves **rank 5 to rank 1**, increasing that entry's simulated mean by **8.51 points** and P220 from **0.435% to 0.600%**. Both simulator components improve, with identical effects under the two availability assumptions. Membership is unchanged. This is a contest-allocation tradeoff: the block receiving the displaced lineup loses some modeled utility.

Full participation-weighted reselection also produces a larger whole-book gain than the earlier one-exchange search, but only under its availability assumption. It raises whole-book P220 by **0.73 percentage points** under the fixed participation model and lowers it by **0.97 points** if everyone plays. These are conditional simulation results, not measured NFL scoring improvements. No operational book or upload was changed.

## What was executed

[Protocol](2026-09-19-d6400-reselection-protocol.md) and proposal constructor were frozen at `c992ea49`. Eight books distinguish the actual v4.3 control, complete ordinary/participation greedy selection, exact vetted delivery order, and the existing first-delivered promotion. All use the same **3,366 eligible candidates / 42-player exclusion set** and legal K97 contract. Q/D players remain eligible. Original selection parity was already exact; the new consumers reuse original candidate tie order and player summation order.

The exact cleared vetter was executed against its four captured real SQL responses, asserting SQL and parameters. The current control was classified for promotion eligibility without reordering it. The fixed participation map and 21:08:21Z provider-bound snapshot were replayed at the recorded cutoff; this is not a new live-status certification. The source projection batch remains **15:09:52.915006Z**, not tonight's newer projection batch.

The [eight-book packet](reviews/evidence/2026-09-19-d6400-reselection-frozen-books.json), SHA `87262e06f43a6352f7b92df1a4aacd5d6913fb9c0abb759e630b69b86cd38ecd`, and [reader](reviews/evidence/2026-09-19-d6400-reselection-read.py) were frozen at **7f3c339c** before audit effects. Both archived selection banks reconstructed exactly again before fresh event seeds **20260919 / 21260919**; availability seed **20260919062**. [Audit identities](reviews/evidence/2026-09-19-d6400-reselection-audit-receipt.json). Proposal construction took 25.6 seconds, audit construction 23.4 seconds, and the complete read 3.1 seconds, single-threaded.

[Full results](reviews/evidence/2026-09-19-d6400-reselection-result.json), SHA `9ffaa4a719fcf743052575a44f6266889f56fed94ef9aa1df561e1ec8b1ae203`, include every book, both components and availability assumptions, all 20 regions, paired stage effects and all ten predefined stresses. Intervals describe Monte Carlo error for the fixed laws; they exclude model error, probability-map error and multiple-search uncertainty.

## First-entry ordering: concrete class E candidate

The unchanged rule promotes the highest standalone selection-bank mean among clean/soft entries already in the first 30, breaking ties by earliest delivered rank. On this control, it chooses candidate **782**, currently fifth, over candidate **3116**, currently first. It changes neither players within a lineup nor membership of the book.

| Metric | Current first entry | Promoted first entry | Paired change |
|---|---:|---:|---:|
| Simulated mean | 134.7885 | 143.2961 | **+8.5076**; MC95 [8.0743, 8.9409] |
| P220 | 0.435% | 0.600% | **+0.165 pp**; MC95 [0.0275, 0.3025] pp |
| Labelled winner-score proxy | 0.007606 | 0.011202 | **+0.003596** |

Incumbent/hsim mean changes are **+9.761 / +7.254**; P220 changes **+0.220 / +0.110 pp**. These rows carry no participation discount under the fixed map, so the all-active and participation results match exactly. All reported prefixes from 10 onward are exactly unchanged for this rank-5 move, as is whole-book utility. Ranks 6–97 are byte-order preservable. The effect is real in the model's delivery order, not a larger set of strong lineups.

**Cost:** contest block **2–24** loses **0.1954 expected-max points**, **0.095 pp P220**, and **0.000941 proxy**. Its mean loss interval is [−0.2637, −0.1270]; P220 interval includes zero. The rest of the contest blocks are unchanged. This cost belongs beside the first-entry gain; a whole-book equality check alone would hide it.

**Recommendation:** prepare this reversible ordering trial for an explicit Week-2 class E decision after production's numerical cross-read and execution on the actual final delivered book. The user's stated preference for placing the strongest entry in the Millionaire makes this a relevant tradeoff. There is no reason to impose a calendar delay on preparation. Do not copy “rank 5” to a different D12800/Sunday book: apply the same frozen rule to that book's own selection banks and fresh vetting, then record its exact before/after identities and contest mapping. This report nominates a candidate, not automatic adoption.

The decision package's primary utility is first-entry quality; unchanged comparison is the exact current delivered order; operational change is a permutation only. Retain the original ordered CSV as rollback, verify legal unique K97 membership and intended entry mapping, and keep the forecasts/orders frozen before lock. Report the first-entry outcome and the displaced contest block in the weekly evidence record, including adverse results; a single week's result will not establish efficacy. Any updated source/status/book requires a new consumer execution, not reuse of these row numbers.

## Full reselection: an explicit availability tradeoff

Ordinary full eligible-pool reselection changes **15 of 97** members; participation reselection changes **33**. The former offers no clear whole-book gain on this audit. The latter's delivered first entry is candidate4871: its mean gains **9.4747**, P220 **0.310 pp**, and proxy **0.004860** versus current control, in both availability assumptions. The participation book already has its strongest eligible first-30 mean first, so its additional promotion is exactly identical. Ordinary full reselection plus promotion reaches that same first entry; full membership replacement is not required merely to achieve its head ordering.

| Delivered alternative vs current control | All-active whole-book mean-max change | All-active P220 change | Participation mean-max change | Participation P220 change |
|---|---:|---:|---:|---:|
| Ordinary full reselection | +0.0050 | +0.120 pp | −0.0333 | +0.085 pp |
| Participation full reselection | **−0.5794** | **−0.970 pp** | **+0.9518** | **+0.730 pp** |

Participation P220 rises **14.565% → 15.295%**, MC95 change **[+0.455, +1.005] pp**; mean-max rises **197.2337 → 198.1855**, interval **[+0.8385, +1.0650]**. Proxy improves **+0.005187**. Both component whole-book deltas agree: incumbent/hsim P220 **+0.690 / +0.770 pp**, mean-max **+0.9489 / +0.9546**.

The all-active cost also agrees across components: P220 **−0.510 / −1.430 pp**. Equal-mixture P220 falls **16.915% → 15.945%**, MC95 change **[−1.279, −0.661] pp**; proxy decreases **−0.004889**. The assumption about who plays is consequential. This is not broad robustness across availability models or proof that the historical map is calibrated for these exact players.

The first30 participation mean-max gains **0.5541**, P220 **0.050 pp**, proxy **0.001317**. Component P220 disagrees there (**+0.380 / −0.280 pp**), and its mixture interval crosses zero. Report that uncertainty rather than turning it into either a universal veto or an assured premium-entry gain.

**Recommendation:** prioritize this as a paired prelock shadow and evaluate a candidate-specific selection trial using current official-status handling. Full adoption is a distinct decision from the simpler order-only candidate. At inactives, refresh confirmations and remove historical nonparticipation discounts for officially active players; the current v3 research consumer deliberately refuses unresolved Q/D within 90 minutes of kickoff because verified official confirmation acquisition is not implemented. That operational gap must be closed for such live use. The fallback remains the unchanged cleared production selection/replacement chain.

## Concentration: availability improves, overall exposure does not automatically fall

The fixed map implies **17.6706 → 4.7422 expected inactive player slots**, counting across all 873 selected slots, and **39 → 14** lineups with at least one discounted player. Those are expectations conditional on the historical map, not forecasts that exactly those many slots will fail. Maximum player exposure nevertheless rises **53/97 → 58/97**, both on Justin Jefferson. Ladd McConkey exposure falls from27 as availability weighting changes the book.

The ten player/slot identities were selected from control exposures before the audit. Forcing Jefferson's score to zero reduces all-active whole-book mean-max by **9.2191 points** in control and **10.1012** in the participation book. The corresponding P220 changes are **−7.710 / −7.695 pp**. McConkey's zero-score stress costs **3.7466 / 1.8950 mean-max points**, while Javonte Williams' costs **3.2480 / 3.5186**. The vulnerability moves; it does not vanish.

Two predefined identities are team defenses (49ers/Patriots). For those, interpret the operation literally as a **zero-score slot stress**, not an assertion that a defense can be inactive. No stress reallocates usage to teammates. This is a sensitivity check, not a realistic injury simulator, an optimized cap or a worst-case guarantee. A future cap experiment must measure utility lost in ordinary worlds against protection in these stress worlds, with availability weighting as a separate control. O-14 is better understood but is not resolved by this experiment.
