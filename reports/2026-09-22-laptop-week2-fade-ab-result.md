# Week-2 fade A/B: the fade lifts the mean and does not lift the best

Assignment from `1e5634d0`. Script: `reports/lab-handoffs/fade_ab_week2.py`.
Frame: the real money-run frame from the bucket — and the frame I had substituted is
bit-identical to it (`6899f7ed`), so no re-run was needed.

## Result, LEV=640, both arms on one frame

| arm | mean | best | ≥150 | ≥170 | missing slots | clean lineups | clean mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| control (`base`) | 74.42 | **137.70** | 0 | 0 | 298 | 342 | 72.25 |
| faded (`base − 25·own`) | **76.67** | 135.86 | 0 | 0 | 301 | 339 | **74.80** |

**Δ mean +2.25** (clean-lineup Δ **+2.55**), **Δ best −1.84**. Shared rosters **95 of 640
(14.8%)**. Fade size on this frame: mean 0.291, max 4.195.

**The fade helps the average lineup and does not help the best one.** For a tournament book
selected on its maximum, that is the less useful half. It is one slate and the best-lineup
difference is small, but the direction is the opposite of what the lever is for.

## Scoring validated against a known answer before believing any of it

My arms average ~75 where production's Week-1 control averaged 158.65, which is a large
enough gap to distrust. So I scored the **delivered Week-2 book** with the same code:

```
DELIVERED week-2 book: n=97  mean=98.40  best=157.96  >=150=3  missing-slots=6
```

**98.40 against the 98.4 production has reported all week.** The scorer is right, so the
numbers stand, and the gap has two real causes: (a) my arms are **raw LEV candidates with no
selection**, while the delivered book is chosen by expected-max from 12,555 — selection is
worth ~24 points of mean on this slate; and (b) **Week 2 was a far poorer slate than Week 1**
(pool oracle 197.26 with one candidate ≥194, against Week 1's 236.28 with 1,215 ≥150).

Week-1 and Week-2 control numbers are therefore **not comparable to each other**, and I would
not put them side by side in the ledger.

## The missing-row asymmetry I pre-registered: it did not happen

Control 298 missing slots, faded 301 — a 1% difference on 5,760 slots. The clean-lineup mean
moves the delta the same direction and slightly further (+2.55 vs +2.25), so the headline is
not an artifact of default zeros. **My own concern is closed by measurement**, the same way
production closed it for the cap sweep.

## What the arms actually picked, which is the more useful finding

The control's top lineup by objective contains **Zay Flowers at $6,700, who scored 0.0** —
the Doubtful player from the Week-2 post-mortem — alongside Jefferson at 8.5. The raw LEV
pool on this frame is contaminated by players who were never going to play, because this
frame predates the Doubtful exclusion (`2dc116c`).

**That matters for reading this A/B**: the fade was asked to improve a pool whose biggest
single defect was availability, not chalk. The Doubtful rule removes those players before any
solve; this A/B could not see that benefit because it runs on the pre-fix universe. A fade
A/B on a post-`69f98a7` frame is a different and probably fairer test.

## Timing — the measurement production asked for, and my own projection was wrong

**Measured: control 929.8 s (15.5 min), faded 796.8 s (13.3 min)** at LEV=640, 429-row frame.

I projected ~9 minutes. **The real number is 15.5, so my projection was optimistic by ~1.7x**
and should not be used. Against production's measured workstation figure of **44.5 min** on a
*smaller* 391-row frame:

**laptop ≈ 2.9x faster, not the ~5x my projection implied.**

Still a large margin, still on a bigger frame, and it still supports moving Saturday's build —
but 2.9x is the number to plan with. Two projections of mine have now been corrected by
measurement in one day (the n^2.5 exponent, and this); the pattern is that extrapolations
here are consistently optimistic and the measurement is cheap.

## What I am not claiming

One slate, one dose, no selection stage, on a pre-Doubtful-fix frame. This does not say the
fade is worthless, and it does not clear it. Paired with production's Week-1 arms it is two
slates at a matched dose, which was the point of the matched-dose instruction.
