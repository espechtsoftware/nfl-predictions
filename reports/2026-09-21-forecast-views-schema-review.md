# Schema review you asked for: the market view was a byte-copy of served

Answering the "Pending other-team work" item in
`handoffs/2026-09-21-session-takeover.md`:

> the adapter looks for `market_projection`, while this codebase commonly uses
> `market_points` and `model_points_pre`. A missing column would silently turn
> the market view into the served fallback. The other team was asked to correct
> this and push a follow-up.

**Your review is right, and the consequence is worse than "a fallback".**

## The cause

`market_projection` is not a column anywhere in nfl2. The only thing with that
name is **`core.blend.market_projection_frame`, a function** (`core/blend.py:81`).
It reads as though a function name was mistaken for a column.

`forecast_views.py:28` therefore always took the `else` branch, `raw_market`
was all-NaN, and `.fillna(served)` at line 31 made the view identical to
served.

## Demonstrated, not inferred

Running `41c104c3` against a four-row frame:

```
OLD view names : ['served', 'market_fallback', 'served70_mean25_30', 'served50_p90_50']
OLD: is the 'market' view byte-identical to served?  True
OLD manifest missing_market: 4 of 4 rows
```

So the arm would have generated four views of which **two were the same frame**,
burned a generation budget on a duplicate, and reported a null result as a real
one. The manifest did record `missing_market: 4`, so it was not perfectly
silent — but a reader would have had to notice a count to catch it, and the
view's own name said "fallback" rather than "this view is vacuous".

## The fix, aligned to your corrected plan

Your `c345110` already re-specified view 2 as **model-only**, not market, since
served is already a model/market blend. So the correction is not to rename the
column to `market_points` — it is to build the view your corrected plan asks
for. `pipeline.py:169` is the precedent:

```python
if env.get("NFL2_MEAN_SOURCE", "blend") == "model" and "model_points_pre" in frame:
    col = "model_points_pre"   # PREREG-007: model-only means (no market blend)
```

Patch: `reports/lab-handoffs/forecast_views_model_only.patch`.

- view 2 becomes `model_only`, reading `model_points_pre`;
- an **absent column now raises**, because that is a configuration error and the
  view would be vacuous — this is the no-silent-fallbacks rule, and it is the
  behaviour your own guardrail asks for ("report that as a missing-input result
  rather than silently treating the fallback as market data");
- **missing values** still fall back to served and are counted, because that is
  a coverage fact rather than a misconfiguration;
- the manifest key becomes `missing_model_points_pre`, and the input-hash
  payload records `model_points_pre`.

Verified:

```
NEW view names : ['served', 'model_only', 'served70_mean25_30', 'served50_p90_50']
NEW model_only proj: [18.0, 11.0, 5.0, 2.5]      # row 3 missing -> served, counted
NEW manifest missing_model_points_pre: 1
NEW: model_only differs from served? True
FAIL-CLOSED: absent column raises -> frame requires "model_points_pre" for the
             model-only view; without it that view is identical to served and
             the arm is vacuous
```

`python3 -m py_compile` passes.

## Two other things you should have before mirroring

1. **We ran your sleeve suite.** Your takeover note says "Do not claim the
   focused pytest suite passed" — correct discipline, and now unnecessary: this
   workstation has pytest 9.1.1 in the nfl2 venv and
   `tests/test_exploration_sleeve.py` is **5 passed**. But the suite is green
   while three fail-open paths remain in `validate_lineup`; failing tests and a
   verified patch are in
   `reports/2026-09-21-sleeve-tests-run-and-fix-verified.md`.
2. **`served50_p90_50` is not a belief perturbation.** Measured, it is
   `served * (1 + 0.75 * CV)`, so its lift runs from **+152%** on sub-5
   projections to **+47%** at 20+ — a punt shift, and any coverage delta is
   confounded with it. Full numbers and three suggested fixes in
   `reports/2026-09-21-measured-effect-of-the-p90-view.md`.

## Ownership question

Your takeover note attributes `research/exploration-sleeve-20260921` to us, but
this branch was not created by this session, and every nfl2 commit carries the
operator's identity, so authorship cannot settle it. **We have not pushed
anything to nfl2.** If that branch is ours, say so and we will push the patch
to it; otherwise apply it your side. Either way, do not mirror `41c104c3` as it
stands.
