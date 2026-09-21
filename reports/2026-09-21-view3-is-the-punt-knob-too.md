# View 3 has the same defect view 2 just had — and both remaining views are punt knobs

Against nfl2 `research/exploration-sleeve-20260921` @ `3dbcd7d4`
("Use production forecast schema for perturbation views").

The `model_points_pre` fix for view 2 is correct and fails closed — good. But
the same commit introduces the identical defect one view along, and measuring
it changes what the arm is actually testing.

## 1. `mean25` does not exist in nfl2

```
$ git grep -n "mean25" 3dbcd7d4 -- src/   # outside forecast_views.py
(nothing)
```

So the new fallback

```python
mean_col = "mean25" if "mean25" in frame else ("mean_projection" if "mean_projection" in frame else None)
```

**always takes the `mean_projection` branch.** This is the `market_projection`
situation again: a column that exists nowhere, silently replaced — except this
time the substitute is a *different quantity*, not an empty series, so it will
not show up as a missingness count.

## 2. `mean_projection` is not a historical mean — it is served

`pipeline.py:162`, your own comment:

> PRODUCTION centers on the market-blended MEAN (`mean_projection` = 0.45 model
> + 0.55 market, model-only without a market). **`proj` equals that mean except
> in the punt band (salary <= $4k)**, where it is the p90 "punt valuation" used
> only as an optimizer objective.

So for every player above $4,000, `proj == mean_projection`, and

```
0.70 * served + 0.30 * mean_projection  ==  served
```

exactly. The view is **identical to served** for those rows. Below $4,000 it
differs, and in a specific direction: it pulls the punt-band valuation 30% of
the way *down* from the p90 punt number toward the blended mean.

The plan asked for a **history blend** — "`0.70 * served + 0.30 * mean25`, using
only information available at lock". A 25-game historical mean is a genuinely
different belief. `mean_projection` is the current projection. Substituting one
for the other does not weaken the view, it replaces it.

## 3. The punt band is most of the pool, not a tail

Current DK classic rows with future kickoff, by position:

| pos | rows ≤ $4,000 | all rows | share |
|---|---|---|---|
| TE | 6,088 | 6,662 | **91.4%** |
| WR | 8,702 | 11,168 | **77.9%** |
| QB | 2,605 | 4,012 | 64.9% |
| RB | 4,203 | 7,013 | 59.9% |

(Row counts span several draft groups so they are not distinct players; the
proportion is the point.)

So view 3 is not "served with a small tail adjustment". It is unchanged on the
expensive minority and systematically **de-emphasises punts** across the
majority.

## 4. What the four views actually are

| view | what it really does |
|---|---|
| `served` | control |
| `market_fallback` | model-only — correct now, but the **name is wrong**: it is neither market nor a fallback |
| `served70_mean25_30` | **punt de-emphasis** (identical to served above $4k) |
| `served50_p90_50` | **punt amplification** (+152% sub-5, +47% at 20+) |

**Two of the three treatments differ from the control only through the punt
band, in opposite directions.** Neither is testing "does the generator build
differently under alternative pre-lock beliefs" — together they are a
two-position punt knob. If both run, the likely readout is that one raises
coverage and the other lowers it, and the conclusion drawn will be about
beliefs when the mechanism was punt valuation.

## 5. Suggestions

1. **Fail closed on `mean25` exactly as you now do on `model_points_pre`.** If
   the history blend is wanted, the column has to be produced first; silently
   substituting the current projection makes the view untestable. The rule you
   applied to view 2 is the right rule here.
2. **Rename `market_fallback` to `model_only`.** It reads `model_points_pre`
   now; the name is a leftover and will mislead the readout.
3. **If a punt-valuation arm is wanted, make it the deliberate arm** — one knob,
   stated, swept in both directions — rather than arriving at it twice by
   accident. Given the Week-1 evidence (sub-8 punts dead, 8–12 punts raise
   tails) that is a defensible experiment in its own right, and it would be
   cleanly interpretable, which the current pair is not.

## Not a criticism of the fix you just made

`model_points_pre` with a hard raise on an absent column is exactly right, and
it is the pattern this note is asking you to extend one line further.
