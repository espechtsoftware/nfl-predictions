# The adopted chalk fade has never fired in 2026 — the leverage arm is built with zero leverage

Found while answering the operator's "are there more experiments to try". This is not an
experiment. It is an adopted, twice-proven production lever that is silently inactive, and
has been for every live week of the season.

## The evidence

Both 2026 money runs carry the same receipt:

| run | formula_id | penalty | own_source | fallback_reason |
|---|---|---:|---|---|
| Week 1 `20260912T204921889774Z` | `degraded_no_ownership_punt_p90_v1` | **0.0** | `None` | no ownership source available on this build |
| Week 2 `20260919T153008787414Z` | `degraded_no_ownership_punt_p90_v1` | **0.0** | `None` | no ownership source available on this build |

## Why it happens

`nfl2/scripts/live_week.py:191`:

```python
pt, pt_receipt = proj_tourney_production(fr, draws)   # own_est omitted -> None
```

`proj_tourney_production(frame, draws, own_est=None)` takes the degraded branch whenever
`own_est` is None. **The caller never passes ownership**, so the degraded branch is taken
unconditionally, every run, forever. Nothing is misconfigured and nothing failed — the
argument is simply not supplied.

## Why it matters more than it looks

`proj_tourney` is the objective for **LEV** generation
(`pipeline.py:463`, `optimize_many(..., objective_col="proj_tourney")`). The production
formula is

```
base = max(mean_projection, bank p90)  if salary <= 4000 else mean_projection
proj_tourney = base - 25.0 * own_est
```

With `own_est = None` the whole second term vanishes. **The arm whose entire purpose is
leverage is being generated on plain mean projection with a punt floor — the leverage arm
has no leverage.** This week that is 2,560 of the 12,800 candidates.

`CLAUDE.md` lists the chalk fade in the adopted production stack: *"NAIVE-ownership chalk
fade — the fade itself is +2 twice-proven"*. It has not been applied to a single live 2026
lineup.

## The input needs no new data

`nfl_dfs/backtest/field.py:naive_ownership(players)` is a pure function of `proj`, `salary`
and `pos` — a within-position softmax on value with a mild salary boost. Everything it
needs is already on the frame pre-lock.

**The scale is right, which is the part I checked rather than assumed.** `replay.py:1200`
computes `own = naive_ownership(frame)` and assigns it straight to `frame["own_est"]`, and
`replay.py:1497` states the contract explicitly: predicted percentages are converted to
*"naive_ownership-compatible weights (normalized within position), so LEVERAGE_PENALTY's
scale ... hold"*. So the six-season replay that proved +2 used exactly these units. Passing
`naive_ownership(fr)` is restoring the proven configuration, not inventing one.

The change is one line, and it flips the receipt from `degraded_no_ownership_punt_p90_v1`
to `production_naive_fade_punt_p90_v1` — production parity.

## What I am NOT doing

**Not shipping it on the strength of this argument.** The exposure-cap lesson is four hours
old: a lever that looked uniformly good on Week 2 reversed on Week 1. Restoring the fade
changes *which candidates exist*, so it cannot be tested from archived banks — the banks
score the candidates the old objective produced.

**The test is a regeneration A/B**, and it is affordable: Week 1 ran LEV=640, and LEV cost
scales ~n^2.5, so 640 solves is roughly 1/32 of the 2,560-solve arm that took ~10 h — call
it ~20 minutes per arm, locally, which is where the operator wants historical tests to run.

Two arms, identical seed, frame, draws and dose; the only difference is whether `own_est`
is supplied. Then score both books against Week-1 realized, and repeat on Week 2 if Week 1
is encouraging. A lever that has not fired all season deserves two slates before it fires
on a money build, exactly as the cap did not.

## One caveat recorded now, before results exist

My own Week-1 field-ownership analysis found the naive fade input **near-uninformative
within position** against realized DK ownership. So there is a live possibility that
restoring the fade changes construction without improving it. That is a reason to measure,
not a reason to skip: the alternative on the table is continuing to run an adopted lever at
zero for a third consecutive week without ever having tested it live.
