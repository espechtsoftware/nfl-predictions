# What usage recovery newly restores and newly removes

The exact before/after census of the saved 435-player slate finds **41 players recover nonzero simulated scoring support and 22 tight ends newly lose it**. Six of those 22 tight ends have prior snap shares of at least 30%. No running back or wide receiver newly becomes a zero-score player in this comparison. These transitions are identical with benchmark game lines held fixed (A to B) and with current game lines held fixed (C to D).

| Position | Players | Zero-score before | Zero-score after | Newly zero | Recovered |
|---|---:|---:|---:|---:|---:|
| RB | 91 | 39 | 35 | 0 | 4 |
| WR | 147 | 95 | 59 | 0 | 36 |
| TE | 100 | 22 | 43 | 22 | 1 |

This sharpens the [remaining-support census](2026-09-19-remaining-opportunity-support-census.md). The salary repair reveals a downstream weakness: observed zero opportunity shares survive as structural zeros, while missing shares had received a positional fallback. A small prior warrants testing, especially with just one observed game. Conversely, restored snaps activate 7 running backs, 39 wide receivers and 2 tight ends that failed the old activity mask. The old implementation did not give everyone positive support: it applied that mask after filling missing shares.

The workstation's full-inference count of 122 observed zero target shares (19 with at least 30% snaps) measures a different population and quantity. It is not a count of newly zero total scores. A running back can retain rushing production, and an observed-zero wide receiver may already have been excluded by the old activity mask. On this actual slate, nine running backs and 22 tight ends lose positive target weights; zero wide receivers do. The observed regression is real, but describing all 19 high-snap full-inference cases as newly unable to score overstates the evidence.

This is a descriptive census of already-retained simulations, not validation against future football outcomes or a proposed automatic player exclusion. All affected identities, both activity masks and before/after target/carry weights are retained in the [evidence](reviews/evidence/2026-09-19-opportunity-support-transitions.json). Source `90a26b4f`; no new simulations, warehouse queries or current outcomes. The full-chain rehearsal uses refreshed predictions and may have a different current player universe.
