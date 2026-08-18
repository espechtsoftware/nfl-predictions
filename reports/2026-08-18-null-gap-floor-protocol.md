# Null-calibrated construction floor — protocol (S1, DRAFT for operator freeze)

**Protocol ID:** `20260818-null-gap-floor-v1`
**Status:** DRAFT — operator approved the S1 direction (2026-08-18
decision a: "freezes W and the held-out-world rule before any number");
this document is that freeze once the operator pins its SHA-256.
**Class:** score-free (no realized outcome is ever read).
**Role in the queue:** per the recorded heavy-slot decision, this result
decides residual-columns versus DST/law work after the ATLAS C test.

## Question

How much of the observed 54-slate construction gap (H−P 4.057,
P−C **68.914**, C−S 5.007, exact-stack contract) would remain if the
production law were EXACTLY TRUE? P is a hindsight maximum over a vastly
larger space than any candidate pool; the self-law gap distribution is
the order-statistics noise floor, and observed − floor is the winnable
part.

## Frozen design

1. **Held-out worlds (the load-bearing rule):** a fresh world block
   generated on the frozen production image with a NEW registered seed
   pair (an "R5" block never used for candidate generation or
   selection). Selection-visible worlds are prohibited: candidates were
   generated from and selected against them, which biases C upward and
   understates the floor. The R5 seed pair and block artifacts are bound
   here at freeze time.
2. **W = 100 worlds per slate** across the 54-slate corpus (5,400
   world-decompositions; two CBC oracle solves each — H and support-P —
   ≈ 10,800 solves, a bounded cloud job, never local).
3. **Chain per world** (`research/null_gap_floor.slate_null_gaps`,
   implemented and offline-tested): substitute the world's player values
   for `actual`; H = frozen forensic oracle (QB+2, one bring-back, $49k
   floor); P = same oracle restricted to the candidate pool's player
   support; C = best candidate roster sum; S = best selected-book sum.
   Candidate rosters and selected membership come from the same immutable
   panel the observed decomposition used.
4. **Report** (`aggregate_null_floor`): per-gap null mean/median/p05/p95,
   observed value, `winnable_vs_null_median`, and the fraction of null
   worlds at or above the observed gap. Per-season splits included.

## Interpretation rules (frozen before any number)

- `winnable_vs_null_median` for P−C is the headline: it is the budget for
  ALL construction work combined (residual columns, union admission,
  generator changes) under the current law.
- If the null floor explains most of 68.914 (winnable ≲ 15), construction
  is near its practical ceiling and the heavy slots after ATLAS C belong
  to the law lanes (DST events, OT mixture, dependence). If the winnable
  share is large (≳ 25), residual columns take the next slot.
- This is a measurement; it adopts nothing, closes nothing, and cannot be
  rerun with a different W or world rule after the first number is seen.

## Fail-closed conditions

Selection-visible world reuse; missing world values for any slate player;
selected book outside the candidate pool; support oracle scoring below
the best candidate (contract defect); any non-Optimal oracle status.
