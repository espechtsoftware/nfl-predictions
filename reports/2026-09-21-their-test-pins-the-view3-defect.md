# Their new forecast tests pass — on a frame production cannot produce

Against nfl2 `b6acbb2c` ("mirror corrected forecast views and tests").

## We ran them for you: 2 passed

```
tests/test_forecast_views.py::test_model_only_view_uses_production_schema_and_counts_fallbacks PASSED
tests/test_forecast_views.py::test_missing_model_source_fails_closed PASSED
```

`test_missing_model_source_fails_closed` is a good test — it genuinely pins the
view-2 fix.

## The other one pins the view-3 defect as correct behaviour

Its fixture:

```python
"proj": [10.0, 20.0],
"mean_projection": [9.0, 19.0],      # 1.0 apart on BOTH rows
...
assert views["served70_mean25_30"]["proj"].tolist() == [9.7, 19.7]
```

That assertion can only hold where `proj != mean_projection`. Per your own
`pipeline.py:162`, **production has them equal except in the punt band.** Run
the same function on a production-shaped frame:

```
served              : [10.0, 20.0]
served70_mean25_30  : [10.0, 20.0]
identical to served? True
```

So view 3 is a byte-copy of the control on every row above $4,000 — which is
40% of the pool at worst and 8% at best, by position — and the test passes
because its fixture uses values production never emits.

**The consequence is worse than an untested path: the test now defends the
defect.** Fixing view 3 to fail closed on a missing `mean25`, exactly as view 2
now fails closed on `model_points_pre`, would break
`test_model_only_view_uses_production_schema_and_counts_fallbacks`. Whoever
attempts that fix will see a red test and may reasonably back it out.

This is the same shape as a defect we hit in the production repo this morning: a
test that passes because it is exercising a stand-in rather than the thing it
names. A green suite is not evidence when the fixture cannot reach the failure.

## A test that fails today and passes after the fix

`reports/lab-handoffs/test_forecast_views_production_shape.py` — drop-in, two
tests:

- `test_history_blend_is_not_a_byte_copy_of_served` — production-shaped frame,
  asserts view 3 differs from the control. **Fails on `b6acbb2c`.**
- `test_absent_history_column_fails_closed` — the rule view 2 already follows.

Suggested fix, mirroring what you already did one line above:

```python
if "mean25" not in frame:
    raise ValueError("frame requires mean25 for the history-blend view; "
                     "mean_projection is not a historical mean and makes this "
                     "view identical to served")
```

If the history blend is wanted, `mean25` has to be produced first. If it is not
going to be produced, drop view 3 rather than ship a duplicate of the control
under a name that claims otherwise — `served70_mean25_30` currently names a
column that exists nowhere in the codebase.

Background and the punt-band measurements: `reports/2026-09-21-view3-is-the-punt-knob-too.md`.
