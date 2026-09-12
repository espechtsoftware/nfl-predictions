# The retrieval gap is real and large. Re-ranking does not touch it.

**Date:** 2026-09-12 · **Data:** PREREG-086 r2 sealed cohort, 72 slates, realized
scores already joined (no new outcome opened) · **Status:** measured

## Result

Two selection laws were frozen before any outcome was opened: `incumbent` and
`corrected_hsim_v0.14`. Both pick a K20/K80 book from the same candidate pool.
On **realized** scores across 72 slates:

```
D800_STANDARD        incumbent   corrected_hsim   delta
  K20                   167.97          167.68    -0.29   95% CI (-4.65, +4.32)   30/72 slates
  K80                   181.52          181.20    -0.32   95% CI (-3.77, +3.11)   29/72 slates
D400_PLUS_MINIMAL_COMPLETION
  K20                   167.92          167.50    -0.43
  K80                   180.13          180.06    -0.06
```

Selector choice is worth **nothing measurable**. The interval straddles zero and
the win rate is a coin flip.

## The part that matters

The two world models were not neutral about this. Each predicted a large
advantage for its own selector, on held-out simulated worlds:

```
selected by incumbent,      evaluated under incumbent        k20 174.44
selected by corrected_hsim, evaluated under incumbent        k20 169.06   -5.4
selected by incumbent,      evaluated under corrected_hsim   k20 184.32
selected by corrected_hsim, evaluated under corrected_hsim   k20 191.86   +7.5
```

Each simulator scores its own selector 5-7 points higher. **That confidence does
not survive contact with realized outcomes, where the difference is 0.3 points
in the other direction.** Each model is measuring its own agreement with itself.

This is the instrument-explanation trap in its purest form: the lever moved, the
ranking was not inverted, but the objective the simulator optimises is not the
functional that realized scoring rewards.

## Meanwhile the gap is not noise

```
K20 retrieval gap (pool oracle - book) = 26.28   95% slate-clustered CI (22.78, 29.89)
```

26 points per slate sit in candidates we **already generate** and fail to
retrieve. The gap is solid; what is absent is any evidence that ranking rules
built on these world models can reach it.

## What this means for the queue

- **This strengthens, not contradicts, the standing ledger position** that
  selection is closed *for the current simulator and static feature set*. It adds
  realized-outcome evidence on a fresh 72-slate cohort, and it isolates the
  reason: the candidates are present, the ranker cannot see which ones matter.
- **The FP/SIS 2x2 ablation is testing a narrower lever than it appears.** It
  asks whether paid sources change *retrieval*. The evidence here says the
  retrieval bottleneck is the world model's ability to identify good candidates,
  not the rule used to order them. Paid sources could still help by improving the
  world model itself -- a different mechanism, and the one worth stating in the
  hypothesis before that chain is unblocked.
- **A better ranker is not the next experiment.** A better *discriminator* --
  something that separates the 26-point candidates from their neighbours before
  ranking -- is.

## Method note

No new outcome was opened. The realized scores for this cohort were already
joined in the 2026-09-12 efficacy read, and both selection laws were fixed before
that read, so this is a two-arm comparison of frozen rules and not a selector
search over opened outcomes. Intervals are paired and clustered on the slate,
since candidates within a slate share a game script.

Rejected approach, recorded so it is not repeated: evaluating new rules against
the discovery matrix would have meant pulling ~62 GB of matrices to the
workstation. That is against the design -- downstream workers derive their one
matrix from the registry in-cloud -- and unnecessary, because the frozen
selector comparison already existed in the sealed shards.
