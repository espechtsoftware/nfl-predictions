# Reconciliation of the post-window program review

Reviewed on 2026-08-11 against the tracked experiment protocols, durable run
artifacts and current production replay code. The operator-supplied source
review remains unmodified and untracked at
`reports/2026-08-11-post-window-program-review.md`.

## Accepted findings

- The raw Route component control's q99 exceedance is 2.688%, with q90/q95
  also above nominal in every held-out season. This is a much larger and more
  stable calibration symptom than the tiny paired Brier differences that
  decided several vendor diagnostics.
- Route Share improved composed point MAE and empirical CRPS in every fold.
  Its exact four-feature contract should be implemented as the already
  licensed, labeled 2026 prospective shadow rather than re-adjudicated on the
  known historical result.
- Future distribution experiments should report paired uncertainty and a
  minimum detectable effect. A binary 30-point event metric alone can be too
  low-resolution for small changes, although it remains directly relevant to
  the operator's tail objective.
- Another historical vendor-family collection should not precede the cheaper
  and more direct calibration diagnostic.

## Necessary qualifications

- Brier loss does not literally discard the roughly 99% non-event rows; every
  row contributes squared probability error. The review's "one event moving"
  conversion is an intuitive approximation, not a standard error or power
  calculation. Its broader concern is still valid, so future paired reports
  should compute uncertainty from the actual per-row loss differences rather
  than infer it from event count alone.
- The 2.688% q99 result is **pre-shaper and pre-market blend**. It does not yet
  establish that the final distribution used for lineup selection is 2.7x too
  thin. `replay_projections(..., return_draws=True)` subsequently applies
  fitted widening plus TabPFN/empirical marginal shaping, and
  `_market_blend_worlds` shifts those draws to the 45/55 blended mean. The
  newly frozen served-path diagnostic must measure that final distribution.
- Calling the raw symptom the cause of the 33 missing known-winner slots is a
  plausible hypothesis, not established causality. Candidate generation,
  salary/stack feasibility, joint dependence and selector coverage also
  affect whether a surprising player reaches a lineup.
- Same-season coverage did not fail only because of support: its aggregate
  30-point Brier also worsened, as did every fold. A longer-window/shrinkage
  formulation would be a new mechanism and would need prospective
  preregistration; it cannot revise the closed last-four result.
- Defense PROE and Route components remain valid registered failures under
  their frozen gates. Their tiny deltas should be described as inconclusive
  effect estimates, but their labels must not be changed after observing
  other metrics.

## Resulting queue

1. The final served-path diagnostic is complete. It reproduced the exact
   13,876-row population and confirmed a thin upper tail: q90/q95/q99
   exceedance was 10.5794%/5.4627%/1.4774%, with q99's week-clustered 95%
   lower bound at 1.2526%.
2. The separately frozen one-factor, mean-invariant Stage A recalibration
   passed and selected `1.025` using only 2019/2021/2022. Its untouched
   2023--2025 calibration gates all passed. The sole exact-80 Stage B lineup
   replay completed successfully as `replay-lockk1tail-2023-bdhsj`,
   `replay-lockk1tail-2024-4727d` and `replay-lockk1tail-2025-6mnfb` from the
   immutable registered image; check-only acceptance
   `accept-replay-panel-mmkps` passed all 54 exact-80 books. The first
   comparator failed on an overly precise persisted candidate-mean tolerance
   and an unbounded log diagnostic, not on generation. Its exact failure and
   already-visible score fields are frozen before one comparator-only repair;
   no book, factor, selector, threshold or disposition rule may change.
   The immutable repair `compare-served-tail-stage-b-repair-lpgt2` subsequently
   passed every mechanical audit and returned neutral: 240/230/220/210 tied
   at `2/3/5/7`, while 200 improved `11→13`, 194 improved `22→23`, 187 declined
   `34→33`, and mean best declined slightly. Production therefore remains at
   identity, and no second factor or treatment is licensed.
3. The immutable 2026 Route Share weekly append path and prospectively frozen
   shadow gate are implemented and pushed. Its all-row CRPS primary, q95/q99
   pinball and calibration checks, paired week-clustered uncertainty and MDE
   directly incorporate the review's gate-resolution recommendation without
   re-adjudicating the known historical arm.
4. The three no-history live matchup tools now have a fail-closed prospective
   collector. It verifies the target schedule week, Apply response and every
   team/opponent pair, requires capture before the target week's first kickoff,
   archives hash-addressed bytes, and keeps all snapshots collection-only. The
   stale offseason samples fail the 2026 Week 1 schedule gate as intended.
5. Only after the calibration path resolves, reconsider whether the
   outcome-blind Advanced Rushing pair or a support-aware Advanced Receiving
   family has enough expected value for one further historical test.
