# Retraction: I recommended launching PREREG-101 without reading PREREG-101

The operator approved on my recommendation. **I am withdrawing that recommendation before
anything is spent.** The reason I said I had looked for and not found is written in the
artifact I should have read first.

## What I got wrong

I based the recommendation on `reports/2026-09-16-prereg-tail-calibration-DRAFT.md` and on
the laptop's research audit, which also cited the draft. **The draft's own header says it is
superseded**, and I read past it:

> Superseded by `PREREG-101.md` on nfl2 `lab/prereg101-tail-calibration-20260918`
> (frozen 2026-09-18). Its §2 table is WRONG.

Two things follow, and both cut against what I told the operator.

## 1. It was already signed. It was then withdrawn — for cause.

`PREREG-101.md` header:

> **Status: FROZEN 2026-09-18, LAUNCH READINESS WITHDRAWN 2026-09-18 pending amendment —
> see §9. Do not launch.**
> **Status (original): FROZEN 2026-09-18. Operator signed off 2026-09-18.**

So the operator's signature already existed. I presented a decision that had been made, as
though it were pending. **"Do not launch" is not a stale instruction waiting to be lifted —
it is the outcome of an independent review that found real defects**, which the author
verified one by one and accepted in full.

- **§9.1 — §8 RETRACTED, and this is the blocking one.** §8 had argued that winner's curse
  could not be the dominant explanation. That inference is invalid; the reviewer supplied a
  counterexample which the author reproduced numerically at 400,000 trials. **The
  winner's-curse / selection-optimism objection is UNRESOLVED**, and that is explicitly why
  launch readiness was withdrawn. No document may say it was "ruled out".
- **§9.2 — the pairing-variance claim retracted.** A minimum detectable effect must come
  from a predeclared pilot before any resizing argument.
- **§9.3 — five contradictions that make it unimplementable as written.** The first is
  simple arithmetic: §2 clips weights to [0.2, 2.0] *then* normalizes to mean 1, while the
  mechanics gate demands final weights inside the clip range. Verified impossible — with 90%
  of worlds at 0.2 and 10% at 2.0 the final weights are 0.526 and 5.263. Also: the gate asks
  a new-bank book (1010–1012) to reproduce an old-bank roster; "retrieval improved" and
  FLAT10 "passing equally" have no precise rule, so the interpretation would get chosen
  after the result.

**You cannot launch this. It does not specify a runnable procedure.**

## 2. I quoted a magnitude the frozen document forbids citing

I told the operator the simulator claims ~9% and the truth is ~3%, pool 1.6× optimistic and
book 2.8×. Those are the draft's bank-970-only numbers. The freeze-time recomputation across
**all three** PREREG-097 banks, 72 slates each, 216 slate-banks, is authoritative:

| level | sim ≥220 | real ≥220 | real/sim @220 |
|---|---:|---:|---:|
| pool max (of 3,200) | 0.264 | 0.222 | **0.84** (draft said 0.63) |
| book max (of 80) | 0.084 | 0.037 | **0.44** (draft said 0.36) |

Per bank the book ratio is **0.33 / 0.49 / 0.49** — and bank 970, the draft's sole source,
is the extreme of that range. The document states plainly that the 220-line claim rests on
**8 realized book events spanning only 6 distinct slates and must not be cited as a
magnitude.** I cited it as a magnitude, to the operator, as part of a spending
recommendation.

The effect is real in direction and **substantially milder than I represented**.

## What should happen instead

**Do not launch. Nothing is spent, so nothing is lost.**

The amendment is genuine, well-specified work and it needs no Cloud compute:

1. **§9.1 — the independence probe the protocol should have had.** Fix a candidate pool,
   select on decision worlds, freeze the book, evaluate that same book on a large
   *independent* world set from the same law. Repeat selection seeds at fixed pools to
   separate selection sensitivity from generation sensitivity. A known-law synthetic stage
   gives ground truth. Varying K is not a substitute for independence.
2. **§9.2 — a predeclared pilot** to estimate the minimum detectable effect.
3. **§9.3 — five specification fixes**, starting with choosing explicitly between bounding
   raw ratios and bounding final normalized weights.

Tail calibration is still the most promising remaining modelling lever, and the direction of
the miscalibration survives the correction. It is simply **much further from runnable than I
told the operator**, and the gap is specification work, not signature and not compute.

## Process note

The check I skipped is the one this project keeps relearning: **read the frozen artifact,
not the draft that points at it.** I had the pointer in the first twenty lines of the file I
did open. The laptop's audit propagated the same stale numbers, from the same source, so
this is not a criticism of it — but §B of that audit should be read with this correction
attached.
