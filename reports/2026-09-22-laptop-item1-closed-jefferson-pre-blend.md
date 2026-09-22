# Item 1 is closed: Jefferson's pre-blend model value is 18.07, and the model was not the defect

The last genuinely unfinished post-mortem task. **No re-run at the serving commit was
needed** — the value is exactly reconstructable, and the reason item 1 stalled is a wrong
input rather than a missing record.

## The answer

```
served proj        25.29084
blend input (market) 31.2      <- dk_ppg, which for Week 2 IS his Week-1 score
model weight       0.45

pre-blend model =  (25.29084 - 0.55 x 31.2) / 0.45 = 18.0685
check:             0.45 x 18.0685 + 0.55 x 31.2   = 25.29084   exact
```

**Jefferson's model said 18.07.** Independently corroborated twice, in artifacts that were
already in the repository:

- `run_projections.py`'s own docstring: *"Week 2 served Jefferson at 25.3 from 0.45 x 18.1 +
  0.55 x 31.2 (his Week-1 score)."*
- `reports/2026-09-21-season-window-audit-week2.md`: the same decomposition.

## Why item 1 got stuck, which is the part worth keeping

Item 1 rejected the inversion because `implied_model_mean` (35.919) disagreed with the
independently recorded `prod_model_pre` on 175 of 175 rows. That disagreement is real. **Its
cause is not that the inversion is unsafe — it is that the inversion was fed the wrong
market value.**

Measured on the 184 Week-2 rows where both exist, using `nfl_predictions.div_shadow` as the
authority:

| comparison | result |
|---|---|
| `prod_model_pre` vs `div_shadow.our_points` | **exact on 184/184**, max diff 0.0000 |
| `implied_model_mean` vs `div_shadow.our_points` | disagrees on **175/175**, max 3.5886 |
| **`csv.market_points` vs `div_shadow.market_points`** | **differs on 184/184**, max 2.5812 |
| blend identity `blend = 0.45·our + 0.55·market` | **exact on 211/211**, residual **0.0** |

So `prod_model_pre` is authoritative (it *is* `div_shadow.our_points`), the blend arithmetic
is exactly linear, and the signals CSV's `market_points` column is **a different quantity
from the value actually blended**. Inverting with it produces 35.92; inverting with the true
input (31.2) produces 18.07 and reproduces the served projection to the fifth decimal.

**The inversion is arithmetically exact. Item 1's objection was right about the number and
wrong about the reason** — and the distinction matters, because "never invert" would forbid
a reconstruction that is provably sound when given the right input.

## The correction this forces on the Week-2 narrative

Item 1 concluded, of the implied 35.919:

> *"the implied blend input, 35.919, is higher than his Week-1 actual and 2.9× his historical
> mean. Whatever produced it was not anchored to his season-long form."*

**That sentence is about a number the model never produced.** The model's actual output was
18.07 against a 17-game historical mean of 12.38 — **1.46×**, not 2.9×. For a WR1 in a
plus matchup that is an ordinary projection, not an unanchored one.

**The entire inflation came from the market stand-in.** DK-PPG in Week 2 *is* the Week-1 box
score, so the stand-in fed Jefferson's 31.2-point Week-1 outlier back in at **55% weight**,
dragging a sober 18.07 up to a served 25.29. He then scored 8.5.

That reframes the Week-2 defect cleanly: **the model was not miscalibrated on Jefferson; the
stand-in was the whole error.** Which is precisely what the props-or-nothing repair
(`82739685`) removed — so the fix already shipped matches the actual cause, and it now has
the right justification rather than a coincidentally correct one.

## The structural finding: the diagnostic excludes its own failure cases

`div_shadow` is written under `if _mkt_src == "props"` and filtered by `[_has]`, the
prop-sourced mask. **So a player served by the stand-in is excluded from the table that
records pre-blend values** — exactly the players whose pre-blend value anyone would want.
Jefferson is absent; Zay Flowers is absent; Bijan Robinson, who had a real prop, is present.

That is why item 1 could not close from the artifacts: the diagnostic omits the failure mode
it exists to diagnose. Worth fixing on its own terms, independently of anything else.

**Forward, this gap is already closed** — `market_source_log.model_points_pre` (`63b1e3ae`)
records the model side for every row, and under props-or-nothing a player with no prop is
model-only, where `blend()` returns the model unchanged and the served value *is* the
pre-blend value.

## Status

**Item 1: CLOSED.** Both halves — the Jefferson trace (this document) and the
season-partitioned-windows clause (the season-window audit, `737104bb`) — are answered. That
was the last open item of the eight; the remaining post-mortem work is item 2's uncalled
instrument, which is production's.

No re-run was performed, nothing was written to the warehouse, and no money-path file was
touched.
