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

---

## Addendum: option (2) is closed, and the same gap will repeat in Week 3

We said option (2) — find where the model stage persists its output — was cheap
to check. It is checked, and the answer is that **it does not persist it at
all.**

`nfl_predictions.player_projections` carries:

```
generated_at, model_version, season, week, slate_id, gsis_id, dk_player_id,
display_name, position, team, opponent, salary, proj_points, proj_p10,
proj_p50, proj_p90, proj_std, p_20_plus, value, proj_ownership
```

**No pre-blend column.** The money-path projection table records the output and
none of the inputs that produced it. That is why Jefferson is unauditable after
the fact: the value was never written anywhere, and `prod_model_pre` in the
signals CSV is a side artifact covering 43% of rows.

So item 1 requires option (1), a re-run at the serving commit. There is no
cheaper path.

## The part that is actionable before Sunday

The market-source repair (`82739685`) introduces
`nfl_predictions.market_source_log`, one row per slate player per run, carrying:

```
generated_at, season, week, gsis_id, display_name, position,
source, market_points, path, proj_points
```

That is a real improvement — it records the market value and *where it came
from*, which is exactly what was missing when the DK-PPG stand-in served
Jefferson. **But it still does not record the pre-blend model value.** It logs
the market input and the blended output, so reconstructing the model side
requires inverting the weight — the move this whole item exists to reject, and
which the 0-of-175 comparison above shows is unsafe.

**Week 3 will therefore be un-auditable in exactly the same way Week 2 was**,
unless one column is added.

**The timing argument:** `market_source_log` **does not exist yet** — it is
created the first time `project-slate` runs on the repaired image, which has not
happened. Adding a column now costs nothing. Adding it after Sunday means
altering a populated money-path table.

This is the cheapest moment there will be, and it is a one-column additive
change to `_source_log_rows`. We have not made it: it is money-path code that
must run on Tuesday, and we are not editing that unasked days before a build.
Say the word and we will implement it with tests and a mutation check.
