# own_est calibration gate: the ownership-template arm (A4) is NOT viable as designed

**Date:** 2026-08-20. One-shot execution of the A4 entry gate
(`20260820-own-est-calibration-gate-v1`, report
`reports/winner-law-audit-runs/20260820-own-est-calibration.json`,
SHA `9ea49c1f…`). Score-free (no lineup score, no fantasy points, no
simulated total); ran alongside the in-flight A3 arm.

## Why this gate existed

Winner anatomy measured the winners' shape in REALIZED ownership: a
chalk core plus a median of four sub-10% pieces. But generation can only
constrain PREDICTED ownership (`own_est`). The A4 draft therefore made
this an explicit entry gate: if `own_est` cannot separate sub-10% from
20%+ players, the arm is "dead on arrival."

## Result: it cannot

36,074 predicted/realized pairs across all 54 slates.

| Metric | Value |
|---|---|
| Spearman rank correlation (overall) | **0.176** |
| Per-slate Spearman: median / q25 / min | 0.225 / 0.157 / −0.017 |
| Precision, predicted "chalk" (>=20%) | **0.102** |
| Precision, predicted "leverage" (<10%) | 0.845 |
| Mean predicted vs realized ownership | 1.47% vs 5.05% |

Confusion (rows predicted, columns realized):

| | low | mid | high |
|---|---|---|---|
| **low** | 30,065 | 4,076 | 1,452 |
| **mid** | 237 | 66 | 11 |
| **high** | 95 | 55 | **17** |

Read plainly: of 167 players `own_est` calls chalk (>=20%), **17 actually
are** — 10% precision. The model predicts almost everything as
low-owned (mean 1.47% against a realized 5.05%), so the 0.845 "leverage
precision" is the base rate, not skill: predicting low is correct
because low is nearly always the answer. Rank information is weak but
non-zero (rho 0.176 overall, 0.225 median within slate) — enough to
sort roughly, nowhere near enough to place a hard constraint on.

## Verdict

**A4 as drafted is closed.** Its design required "at least one anchor at
own_est >= 20% and at least 4 players at own_est < 10%." The first
clause would select on ~10%-precision noise, and the second is
vacuously satisfied by nearly the whole slate. Freezing it would have
burned a full build/launch cycle to constrain generation on an input
that does not carry the signal.

## What this does NOT say

- It does not refute the winner-ownership FINDING (chalk core plus ~4
  leverage pieces). That was measured in realized ownership and stands.
- It does not close the ownership lane. It closes this arm at this
  input quality.

## Consequences

1. **Ownership-aware construction is gated on a better ownership model,
   not on a new constraint design.** The existing trained-ownership work
   (`own_shadow`, `train-ownership`) becomes the prerequisite: it must
   demonstrate materially better chalk precision on held-out slates
   before any template arm is worth freezing.
2. **The Week-1 standings collection gains a second load-bearing role.**
   It is already required for the field model; it is now also the only
   route to a training/validation set for a usable ownership model
   (`contest_ownership` gives realized ownership; the pre-lock `own_est`
   snapshot gives the paired prediction).
3. Queue: A4 moves from "queued behind A3" to **blocked pending an
   ownership-model improvement**, with this report as the bar to clear.
