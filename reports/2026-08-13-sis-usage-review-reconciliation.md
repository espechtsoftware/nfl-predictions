# SIS usage-review reconciliation

Date: 2026-08-13. This reconciles the operator-supplied
`2026-08-13-sis-usage-review-and-priorities.md` before the frozen SIS QB line
arm produces model output.

## Accepted conclusions

1. Run the already-frozen QB line arm without tuning it. Its expected failure
   mode is now stated explicitly: a central/marginal improvement need not fix
   the known joint-tail deficiency, and a miss closes only that two-column arm.
2. The highest-value untested SIS mechanism is player-level pass-defense
   quality crossed with receiver/defender alignment. This is distinct from the
   failed diffuse team-shell family. It still does not identify a true shadow
   assignment, so alignment crossing must first pass a small, outcome-blind
   feasibility check.
3. Boom% and Bust% from SIS Value views belong in that feasibility schema and
   any later receiver/defender bundle. They are lagged vendor tail descriptors,
   not same-week predictors, and require volume/support shrinkage.
4. If alignment crossing is sufficiently concentrated, the best mechanism is
   conditional competitive allocation—not a hand shift to player means. SIS
   matchup context should alter receiver allocation ranks/weights and
   concentration while preserving the incumbent player or team marginal
   contract defined by the eventual protocol. Its score-free gate should use
   the terminal G0/G1 dependence scorecard, including separate QB-WR/QB-TE
   improvement and a WR-WR must-not-worsen guard.
5. This can compose with the planned isolated ledger/rank-coupling mechanism:
   the ledger supplies shared team production and conditional allocation
   supplies receiver competition. They must first be tested separately so
   attribution remains possible.

## Corrections and qualifications

- The review's “six marginal arms all ended the same way” framing is not the
  terminal record. The corrected direct role union and the active-only
  revalidated finite Dirichlet K were adopted; G2 was a dependence mechanism,
  not a marginal channel. The broader warning remains useful: several marginal
  improvements did not translate into extreme weekly lineup scores.
- The 200-row budget arithmetic is a worst case, not the required query plan.
  The normal UI can submit a team filter over a multiweek range. Acquisition
  must attempt the coarsest complete team-season or bounded-window slice and
  accept it only below 200 rows, then split further only when the cap binds.
  A 2023--2025 player pass-defense feasibility pull can therefore be far below
  `32 teams × 18 weeks × reports`, although completeness must be demonstrated
  rather than assumed.
- A single-WR/single-game check is only possible if the normal UI exposes the
  necessary player and alignment filters in submitted query state. The first
  step is a no-outcome filter/schema audit, not a broad backfill. No direct API
  calls or combinatorial filter mining are authorized.
- Boom%/Bust% are appealing tail summaries but remain outcomes of prior games.
  They must be shifted by at least one completed game, accompanied by attempt/
  coverage-snap denominators, and evaluated as an adaptive hypothesis.

## Frozen next data sequence

After the QB line cache/gate and after the current SIS throttle cools:

1. Use ordinary authenticated UI submissions to identify the exact request
   parameters and CSV columns for receiver alignment, defender alignment,
   player/team identity, pass-defense Value Boom%/Bust%, and denominators.
2. Run one bounded game/team feasibility sample. Measure, without player
   fantasy outcomes, whether receiver and likely opposing-corner alignment
   shares are concentrated enough to produce a materially individual crossing
   rather than another team average. Record row-cap/request usage.
3. If feasible, freeze the smallest 2023--2025 acquisition plan using adaptive
   team-season/window slicing and reserve budget before downloading. If not,
   close the inferred individual-CB crossing path; do not disguise it as a
   shadow-assignment data set.
4. Only after source coverage is known, preregister two distinct score-free
   questions: a small WR/TE marginal/tail descriptor bundle and a conditional
   allocation/dependence arm. Do not combine them before either has an
   interpretable result.

Rushing/run-defense, Runs to Gap and adjusted blown blocks remain behind this
pass-game path. Tranche 2 remains resumably paused at 50/108 artifacts and
206/440 recorded requests; do not reset its state.
