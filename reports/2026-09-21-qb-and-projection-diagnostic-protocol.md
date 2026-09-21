# Frozen weekly projection diagnostic — QB centre and dispersion

**Frozen 2026-09-21, before any Week-3 outcome was read.** This document fixes
what is measured and what would license a change, so that neither can be chosen
after seeing a result.

## Why it exists

The Week-2 score read found the served QB projections biased −3.50 ± 1.43, with
**0 of 31 quarterbacks reaching their own 90th percentile** where about three
were nominal. That is one slate. The lab's ruling of 2026-09-21 is the standing
instruction:

> Freeze a QB variance/centre diagnostic protocol now and accumulate at least
> three to four prospective weeks before changing the model. Record mean bias,
> median bias, calibration by projection bucket, and dispersion by position each
> week. Do not apply a Week 3 QB correction from this one observation.

Production accepted that ruling. Nothing below is a licence to change weights,
centring or dispersion in Week 3.

## Instrument

`scripts/week_proper_scores.py`, run once per week after the operator releases
that week's outcomes:

```
python scripts/week_proper_scores.py --season 2026 --week W --slate <main slate> \
    --batch <last pre-lock generated_at> --out reports/weekly-scores/week-W.json
```

It reads `nfl_predictions.player_projections` and `nfl_raw.weekly_stats`
directly, applying the same DK formula as `sql/features/013_player_week_actuals.sql`,
so it does not wait on the Tuesday feature rebuild. It writes nothing.

Two exclusions are part of the protocol, not options. DST, because
`weekly_stats` carries no team-defence rows. And zero-variance stand-ins, rows
with `proj_points` and `proj_std` both exactly 0, which are will-not-play markers
rather than forecasts — scoring them credits the model for predicting 0 for a
player who scored 0 and, in Week 2, made QB median absolute error read 0.00.

## Recorded every week, per position

| measure | what it answers |
|---|---|
| mean bias ± standard error | is the centre off, and by more than noise |
| median bias | is the centre off for the typical player, not just on average |
| dispersion ratio: stated sd / realized sd | is the predictive spread honest |
| calibration by projection bucket | does the error depend on the size of the projection |
| share reaching projection, per bucket | 50% for an unbiased median forecast |
| coverage below p10 / p50 / p90 | interval honesty, with the caveat below |
| CRPS, RMSE, pinball at q=0.90 | overall and upper-tail proper scores |

Projection buckets are **fixed** at 0–5, 5–10, 10–15, 15–20, 20+. Fixed edges,
not quantiles, so the weekly rows stay comparable. Do not retune them after
seeing a week.

**Caveat carried forward:** `proj_p10` is a raw Gaussian quantile with no
truncation at zero, so for RB/WR/TE it runs negative and a player scoring 0 is
almost never "below p10". Treat the p10 coverage column as uninformative for
those positions until that is repaired, and read dispersion instead. QB p10 is
well clear of zero and its coverage is real.

## Week 2 baseline, the first entry

Slate 153430, last pre-lock batch `2026-09-20T16:02:22Z`, 412 scored rows.

| position | n | mean bias | median bias | stated sd | realized sd | ratio |
|---|---|---|---|---|---|---|
| all skill | 412 | −1.00 ± 0.28 | −1.11 | 6.00 | 7.33 | 0.82 |
| QB | 31 | −3.50 ± 1.43 | −5.12 | 12.73 | 8.57 | **1.49** |
| RB | 107 | −1.12 ± 0.45 | −0.88 | 6.38 | 6.14 | 1.04 |
| WR | 166 | −0.75 ± 0.48 | −1.41 | 5.94 | 7.53 | 0.79 |
| TE | 108 | −0.56 ± 0.45 | −0.65 | 3.78 | 5.68 | 0.66 |

Two things the dispersion column adds that the Week-2 write-up did not have.

**The QB distribution is too wide, not too narrow** — stated sd half again the
realized sd. That is the same fact as none of the 31 reaching their own p90:
outcomes sit well inside an interval that is drawn too broad, on a centre that
is also too high. Centre and spread are both wrong, in opposite directions.

**WR and TE are the reverse**, at 0.79 and 0.66. Their stated spread is too
narrow. So there is no single dispersion story across positions, and a global
variance change would make two positions worse while fixing one.

Bias by projection bucket, all positions pooled, is monotone in the projection:

| bucket | n | mean proj | mean realized | bias | reached projection |
|---|---|---|---|---|---|
| 0–5 | 215 | 1.70 | 1.64 | −0.07 | 27.9% |
| 5–10 | 91 | 7.53 | 5.77 | −1.77 | 28.6% |
| 10–15 | 60 | 12.22 | 10.33 | −1.89 | 33.3% |
| 15–20 | 34 | 17.11 | 14.95 | −2.16 | 38.2% |
| 20+ | 12 | 21.55 | 17.26 | −4.29 | 25.0% |

This is the mechanism behind the book-level result. Lineups are built from the
top buckets, so the per-lineup bias of −31.4 is roughly nine slots times the
high-projection bias, not nine times the −1.00 average. **It also says where a
repair would have to act: the top of the projection distribution, not the mean
player.** The share reaching projection is 25–38% everywhere against a nominal
50%, consistent with the negative median bias.

## What would license a change, decided now

1. **Four weeks recorded**, Weeks 2 through 5, each read after the operator's
   release and committed before the next week's build.
2. **A consistent sign** on QB mean bias in at least three of the four, with the
   pooled estimate excluding zero by at least two standard errors.
3. **A stated mechanism** that predicts the dispersion direction too, since
   Week 2 has QB centre and spread wrong in opposite directions and any
   correction that fixes only the centre will leave the tail wrong.
4. **A separate decision for dispersion**, per position. The Week-2 split makes a
   single global variance multiplier inadmissible.
5. Any change is then **a trial under the in-season adoption track**, reversible
   and scored the following week, never a silent weight edit.

Absent all five, the projections are left alone. Recording a week is not
evidence for a change; it is the thing that makes evidence possible later.

## What this protocol does not cover

The negative `proj_p10` repair, which stays in research until after the Week-3
score receipt. Any floor rule built on p10, which must not be built on p10 at
all. And selector or ordering objectives, which the lab has separately ruled may
not use a simulated tail quantity.
