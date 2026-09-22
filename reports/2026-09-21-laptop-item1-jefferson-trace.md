# Laptop review item 1: the Jefferson trace — and why it cannot be closed yet

Answering item 1 of `handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Trace Jefferson's actual pre-blend value and every downstream transform at the
> serving commit. **Inverting a nominal 0.45 weight is not a substitute for the
> calculation.**

**You were right, and the reason is worse than you put it.** The figure everyone
has been calling the pre-blend model value is a back-inversion of the very
blend it is supposed to explain, and for Jefferson specifically the real value
was never recorded at all.

## What the served row actually contains

Justin Jefferson, WR MIN vs CHI, $7,800, from
`receipts/2026-09-21-week2-post-mortem/player-signals-week2.csv`:

| field | value |
|---|---|
| `proj` (served) | **25.291** |
| `market_points` | 16.595 |
| `implied_model_mean` | 35.919 |
| `prod_model_pre` | **empty** |
| `dk_ppg` | 31.200 |
| `wk1` (Week-1 actual) | 31.200 |
| `mean25` (n25 = 17) | **12.382** |
| `own_milly` | 18.9% |
| our exposure | 55 of 97 rows (56.7%) |
| `fpts` (realized) | **8.5** |

The blend arithmetic is exact:

```
0.45 × 35.919  +  0.55 × 16.595  =  16.163 + 9.127  =  25.291
```

## But 35.919 is not evidence — it is the inversion

`implied_model_mean` equals `(proj − 0.55 × market) / 0.45` **on 177 of 177
rows, zero exceptions**. It is definitionally the blend solved backwards. Using
it to explain the projection is circular, which is precisely the objection you
raised.

## The independently recorded value exists — and never agrees

`prod_model_pre` is populated on 184 of 429 rows and is a genuine recording
rather than a derivation. Where both it and `implied_model_mean` are present
(175 rows):

- they are **equal on 0 rows and differ on all 175**;
- solving `proj = w · prod_model_pre + (1 − w) · market` gives a median
  **w = 0.4633** — near the nominal 0.45 — but a standard deviation of **7.46**,
  ranging −1.59 to 99.2, because `w` blows up wherever `prod_model_pre ≈ market`;
- the gap `implied − prod_model_pre` has median **+0.062** but a tail to
  **+3.59**, and the five largest are all quarterbacks: Cooper Rush +3.59,
  Rodgers +3.05, Prescott +2.87, Cousins +2.78, Purdy +2.49.

So there are transforms between `prod_model_pre` and the blend input, they are
small in the middle and material in the tail, and they bite hardest on QB —
which is also the position the Week-2 proper scoring found most miscalibrated.

## Why item 1 cannot be closed from this artifact

**`prod_model_pre` is empty for Jefferson.** The one row the question is about
has no independently recorded pre-blend value, and the only available number is
the inversion, which the 175-row comparison shows is not a safe proxy.

Closing item 1 honestly requires one of:

1. **re-running the serving commit** against the same inputs and capturing the
   model output before the blend, or
2. **finding where the model stage persists its output** for that batch, if it
   does — `prod_model_pre` covering only 43% of rows suggests it is populated
   from a source that did not cover him rather than being universally written.

We are not going to assert a pre-blend value we did not observe.

## What can be said without the pre-blend value

From recorded inputs only, the served 25.291 sat:

- **2.04× his 17-game historical mean** (`mean25` = 12.382);
- **1.52× the market** (16.595);
- below only his Week-1 score (31.200) — and note `dk_ppg` **equals** `wk1`
  exactly, which is the documented early-season identity where DK points-per-game
  *is* last week's box score.

And the implied blend input, 35.919, is **higher than his Week-1 actual** and
**2.9× his historical mean**. Whatever produced it was not anchored to his
season-long form.

He realized **8.5**, and we held him in 56.7% of the book at 18.9% field
ownership.

## Status

Item 1 is **open**, with the obstacle now identified precisely rather than
restated. The next concrete step is (1) or (2) above; (2) is cheap to check and
we can do it if you have not.
