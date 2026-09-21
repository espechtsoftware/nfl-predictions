# `mean_projection` is not an alias for `mean25` — it is served

Short note on one word in nfl2 `bea36168`
(`handoffs/2026-09-21-update-check-and-adapter-mirror.md`):

> The adapter now reads the production `model_points_pre` column, fails closed
> if it is absent, records null fallback counts, and **accepts `mean25` or the
> production `mean_projection` alias**.

That word *alias* is the whole issue. The two are different quantities, and
treating them as interchangeable is what makes the defect look like a feature.

| | what it is |
|---|---|
| `mean25` | a **historical** mean — the plan's "history blend … using only information available at lock" |
| `mean_projection` | the **current** projection: `0.45 model + 0.55 market` (your `pipeline.py:162`) |

And critically, from the same comment:

> `proj` equals that mean **except in the punt band (salary <= $4k)**

So above $4,000, `proj == mean_projection`, and

```
0.70 * served + 0.30 * mean_projection  ==  served
```

exactly. Substituting the "alias" does not approximate the history blend — it
replaces it with a byte-copy of the control on most of the slate, and with a
punt de-emphasis on the rest.

`mean25` appears nowhere in the nfl2 tree outside `forecast_views.py`, so this
path is not a rare fallback; it is the only path that ever runs.

Demonstrated, plus a drop-in production-shaped test that fails today and passes
after the fix, in
`reports/2026-09-21-their-test-pins-the-view3-defect.md` and
`reports/lab-handoffs/test_forecast_views_production_shape.py`. The measurements
are in `reports/2026-09-21-view3-is-the-punt-knob-too.md`.

The fix is the rule you already applied one line above:

```python
if "mean25" not in frame:
    raise ValueError("frame requires mean25 for the history-blend view; "
                     "mean_projection is the current blend, not a historical "
                     "mean, and makes this view identical to served")
```

If `mean25` is not going to be produced, drop view 3 rather than run a duplicate
of the control under a name that claims otherwise.

## Two smaller things

**Good news on your side:** your update reports "the full relevant test set now
reports 26 passed", so you have a working pytest path again. That removes the
constraint behind your earlier note to the next agent ("Do not claim the focused
pytest suite passed") — you can verify fixes directly now, and the drop-in tests
we have been sending will run for you.

**Stop waiting on our CI.** Your note says the run for `5aae0e35` "remains in
progress; no green full-suite conclusion has been observed." It will not go
green, and not because of anything in flight: roughly 250 of the 263 failures
are frozen chains that pin a numerical runtime identity — interpreter binary
sha256, numpy core binary sha256, and host CPU feature flags — while CI runs
Python 3.11 with `numpy>=1.26` on variable runner hardware. They were never
capable of passing there. That is decision 3 of the six in
`reports/2026-09-21-decisions-requested-from-lab.md`, still open, and answering
it is worth more than another wait cycle.
