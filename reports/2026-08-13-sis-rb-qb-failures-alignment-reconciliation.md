# Reconciliation: SIS marginal failures and alignment feasibility

Date: 2026-08-13. This reviews
`reports/2026-08-13-sis-rb-qb-failures-and-alignment-feasibility.md`
after both frozen SIS marginal gates completed. It does not change a scoring
result or inspect a sealed lineup outcome.

## Reproduced and accepted

- The QB-line and RB run-defense summaries match their immutable reports. The
  RB Brier-30 change is effectively null, with mixed fold signs and a paired
  interval spanning zero. Both exact marginal arms remain closed.
- Independent parsing of the hash-recorded 2025 Fantasy Points Separation by
  Alignment file exactly reproduced the review's `>=100`-route modal-share
  table: WR `n=146`, median `0.67345`, p25 `0.59611`, p75 `0.77603`, and
  `44.52% >=0.70`; TE `n=69`, median `0.54220` and `17.39% >=0.70`; RB `n=59`,
  median `0.85819`. The four route buckets sum to Overall within floating
  tolerance.
- The repeated pattern in which a constant team/opponent column helps point
  error without improving distributional or extreme-tail loss is a useful
  prospective prior. Future *broadcast-only* features must report CRPS and
  upper-tail loss and cannot advance on MAE alone. This is a heuristic based
  on a small number of mechanisms, not a theorem or a retroactive gate.
- Preserve the five remaining guarded SIS sample calls. Given the independent
  receiver diffuseness evidence and the lack of direct shadow assignments,
  the expected value of spending them on the original individual-CB crossing
  screen is now low.
- A defense-profile-by-player-alignment allocation mechanism is conceptually
  distinct from a broadcast feature: the same opponent profile produces a
  different interaction for a slot-heavy versus outside-heavy receiver. If
  built, it should first face a score-free dependence gate with explicit
  QB-WR improvement and WR-WR must-not-worsen checks.

## Required corrections and limits

1. The existing four Fantasy Points alignment files are full-season summaries.
   They are valid for the aggregate outcome-blind feasibility calculation but
   **cannot** be joined to target Weeks 5--18 without future leakage. A
   historical conditional-allocation arm needs a new frozen strictly-prior
   window collection (or another point-in-time source); the receiver input is
   therefore license-free but not already operationally held.
2. Four-way season-level receiver concentration is not the registered
   one-game, three-bucket SIS calculation. It contains no CB distribution, and
   the claim that Wide will split roughly evenly into Left/Right is an
   unmeasured inference. The original feasibility experiment is retired for
   low expected value, not relabeled as a scientific failure.
3. Team pass-defense filtered by receiver alignment/shell may fit below the
   200-row cap, but its exact row grain, filter payload, denominator schema and
   query cost have not yet passed a guarded sample. Do not assume `32 rows per
   week` until a normal-UI response proves it. Freeze the smallest schema/cap
   check before any historical acquisition.
4. The TD-ledger mechanism did not pass its own frozen final-served gate and is
   not an accepted component. A future interaction may borrow its event-ledger
   idea only as a new, isolated, preregistered arm; it may not compose an
   unaccepted ledger post hoc or inherit a claim that the ledger supplies the
   missing dependence.
5. Independent per-arm calibration schedules are properties of these research
   evaluators. They make the comparisons fair; they do not mean either SIS
   feature or schedule is live in production.

## Revised queue

1. Keep the original SIS individual-CB sample dormant at `7/12` requests and
   retain its private state. Do not reset it or spend the five-call reserve.
2. Finish the already-frozen Fantasy Points QB offense/defense shell-fit test.
   It is a different, strictly-prior schematic interaction and was queued
   before this review.
3. Before collecting more SIS rows, freeze one bounded normal-UI schema/cap
   sample of team pass defense split by broad receiver alignment and broad
   shell, using volume plus value fields but no target-week outcomes.
4. If that sample proves usable, separately collect strictly-prior receiver
   alignment profiles and SIS defense profiles. Then freeze one allocation-only
   rank/concentration transform against the incumbent final-served marginals
   and the G0/G1 dependence scorecard. No marginal mean shift is permitted.
5. Individual defender backfill and any ledger composition remain conditional
   on that isolated allocation mechanism first showing score-free value.

