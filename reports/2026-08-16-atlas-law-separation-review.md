# Review: ATLAS law separation and transfer protocol

Date: 2026-08-16. **No code was changed. No outcome was queried.** No ATLAS
result exists yet; nothing below reads one.

---

## Position

No blocking issues. The two structural decisions are right:

- **Confirming the running ATLAS test uses finite-K + SIS-ASOE worlds rather
  than the production multinomial law, and classifying its result as
  law-specific evidence.** That is the standing "verdicts do not transfer across
  a changed downstream stage" rule applied *prospectively* rather than
  retroactively, which is the harder and more valuable direction.
- **Freezing the production-law transfer protocol before the source result is
  visible.** This forecloses choosing a transfer method that flatters whatever
  ATLAS produces — the same discipline that has protected every other arm here.

Four observations follow. Items 1 and 2 affect how the result can be
*described* and are worth settling before the harvest; items 3 and 4 affect the
transfer sequence.

---

## 1. Cross-law comparability is now a live problem

CBWU-OI's construction gain — mean `C` **181.07 → 186.73**, with **+7/+6/+4** at
194/200/210 — was measured under one simulation law. ATLAS runs under another.

**Those two construction results are not commensurable.** Neither can be ranked
against the other, and the difference between them confounds mechanism with law.

This matters concretely because the opportunity register is meant to carry sized
entries. Two construction gains listed side by side, measured under different
world laws, will be read as comparable by anyone who did not run them — and the
obvious question, *"is ATLAS better than CBWU-OI?"*, currently has no valid
answer.

**Suggestion:** record the measurement law explicitly on every construction
result, and state whether a common-law comparison is planned or deliberately
out of scope. If it is out of scope, say why, so the register does not imply a
ranking it cannot support.

## 2. The research/production law divergence is a structural tax

Production serves the multinomial law. Research now runs finite-K + SIS-ASOE.

The consequence is general rather than specific to ATLAS: **every research
result now requires a transfer step, and every transfer is an opportunity to
lose the effect.**

That is a standing cost on the entire programme, and it should be recorded as
one rather than handled case by case. This project's own history is the reason
to take it seriously — the `26e73c5` allocation-unit repair materially moved
every dependence measurement and invalidated the G-series references, which is
exactly the failure mode a persistent research/production law gap manufactures
repeatedly.

**Suggestion:** either converge the research law to production, or record the
divergence explicitly with its rationale and its expected cost. Both are
defensible; leaving it implicit is not, because the tax is currently invisible
in every result that will need transferring.

## 3. The transfer protocol needs two success criteria, not one

A transfer can succeed **mechanically** — the mechanism runs correctly under the
production law, invariants hold, marginals are preserved — while the **effect**
fails to transfer, because the `C` gain shrinks or disappears under different
worlds.

These are different outcomes with different consequences, and conflating them
would produce a "transfer failed" verdict that does not distinguish a broken
implementation from a law-dependent mechanism.

**Suggestion:** predeclare both criteria in the frozen protocol, with a stated
prior. Given the `26e73c5` precedent, the honest prior is that a construction
gain measured under one dependence law **may not survive another**. Writing that
down in advance means a shrunken effect reads as informative — evidence that the
mechanism is law-dependent — rather than as failure or as a reason to revisit
the transfer method after the fact.

## 4. Do not demote diversity too far

Separating Part-A ranking quality from raw diversity is the right fix. A
promising ranker should not be vetoed by a crude diversity count, and the
previous coupling was a genuine defect.

But note what the CBWU-OI diagnostic just established:

| quantity | canonical | OI |
|---|---:|---:|
| mean unique player-pair reach | 3,056.35 | **4,307.80** (+41%) |
| mean QB stack-core reach | 118.78 | **181.09** (+52%) |
| slates retaining all nine P players | 54 | **44** |

OI achieved its `C` gain with **worse** player coverage and **substantially
broader combination reach.** On current evidence, combination breadth is not a
guard against degenerate output — **it appears to be the mechanism itself.**

The risk in the new framing is a ranker that passes on ranking quality while
producing a concentrated candidate set. That is precisely the configuration
CBWU-OI's result predicts would yield no `C` gain, and under the revised gate it
would no longer be caught early.

**Suggestion:** keep **pair reach** and **stack-core reach** in ATLAS's primary
reported output alongside whatever ranking metric governs, even though they no
longer veto. Demote their *authority*, not their *visibility*.

---

## Summary

| # | item | when |
|---|---|---|
| 1 | Record the **measurement law** on every construction result; state whether a common-law CBWU-OI/ATLAS comparison is planned | before harvest |
| 2 | Record the **research/production law divergence** as a standing cost, or converge it | before harvest |
| 3 | Predeclare **mechanical** and **effect** transfer criteria separately, with the law-dependence prior stated | before transfer |
| 4 | Keep **pair reach and stack-core reach** as reported primaries; remove their veto, not their visibility | before transfer |

Nothing here blocks the running job.
