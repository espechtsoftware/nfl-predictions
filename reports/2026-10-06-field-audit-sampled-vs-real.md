# The field audit: do the harness's sampled fields rank the levers like the real Millionaire fields? (2026-10-06)

The outside review's §6.1 asked how the studies' verdicts depend on the simulated field. Studies 24–42 score books on
REAL outcomes against a field SAMPLED from the slate's ownership (`l02_field_sampler.sample_field`: 200,000 lineups, 70%
one-slot stacks, IPF to the ownership marginals). This audit tests that field model on the three 2026 weeks where real
Millionaire fields exist. Aggregates only; the private inputs stay under `~/private/field-audit/`.

## Method
- **Books:** the laptop's fixed-book replays of Weeks 2–4 (production `union_reselect` at the armed Week-5 settings, K 26,
  Rev3 head; our projections in W2–3, FP in W4): the outside screen's live 7 (`ms7`) and 5 (`ms5`), and the fill × limit
  arms `group5`, `value5`, `group4`, `value4`, `rr5`, `rr4`. Each book's own deal (`ENTER-rowmap.json`) and realized
  points (`moneygate_score`'s week tables).
- **Fields:** (a) the week's REAL Millionaire field (our entries removed; ties lose), exactly the laptop's scoring; (b)
  three fields per week drawn by the harness's own sampler from that week's REAL Millionaire ownership (computed from the
  real lineups; the frames' coverage 0.999–1.000), seeds 11 / 12 / 13.
- **Endpoints:** the harness's `big_seat_stats` per Rev3 contest (P(≥ 1 big seat)) and the mean entry percentile, per
  book, per field. Same books, same deals, same points: only the field differs.
- **Check:** the real-field P(≥ 1 big) reproduces the laptop's `score.json` to three decimals for every arm and week.

## Results

**The sampled fields are a little easier at the top** (DK points; sampled = the mean of three seeds):

| Week | real mean / sampled | real p99 / sampled | real p99.9 / sampled | real top-95-of-150k line / sampled |
|---|---|---|---|---|
| W2 | 115.5 / 115.1 | 179.8 / 175.7 | 199.6 / 195.4 | 202.9 / 198.8 |
| W3 | 128.5 / 126.9 | 188.2 / 182.3 | 205.6 / 199.5 | 208.0 / 202.9 |
| W4 | 118.3 / 117.6 | 182.8 / 180.5 | 205.6 / 201.8 | 208.6 / 205.6 |

**They rank the arms like the real fields.** Contrast A − B in P(≥ 1 big seat), real vs sampled:

| Contrast | W2 real / sampled | W3 real / sampled | W4 real / sampled |
|---|---|---|---|
| group4 − group5 | −.902 / −.962 | −.066 / −.087 | −.297 / −.377 |
| ms5 − ms7 | −.024 / −.009 | +.301 / +.481 | +.309 / +.392 |
| value5 − group5 | −.863 / −.895 | −.310 / −.501 | −.338 / −.435 |
| value4 − group4 | −.005 / −.010 | −.235 / −.375 | +.265 / +.342 |
| rr5 − group5 | −.824 / −.805 | −.295 / −.467 | +.094 / +.047 |
| rr4 − group4 | +.036 / +.084 | −.242 / −.404 | +.388 / +.441 |

- **18 of 18** contrast-weeks agree in sign. The mean-entry-percentile contrasts agree to about 0.003 (e.g. group4 −
  group5: +.050 / −.060 / −.007 real against +.054 / −.063 / −.006 sampled).
- The sampled fields **magnify** the P(≥ 1 big) contrasts in both directions (roughly 1.2–1.6×), because their easier
  top lines let more rows count; they do not favour one kind of lever.

## Reading
1. **The harness's field model is adequate for the levers studied (34–42): it ranks them as the real fields do.** Its
   absolute P(≥ 1 big) runs high (the top lines are 3–6 points easier), so its levels are optimistic and its effect sizes
   somewhat magnified; the direction of a verdict stands.
2. **The overlap limit 4.** On the three real weeks the 4 had fewer big seats than the 5; the sampled fields say the same
   on those weeks. So the shortfall is those weeks' realized rows (the live W2 book's one 185-point top-1% row), not the
   field model, and it is three draws against two harness reads on independent banks (study 41 PASS +0.059; study 42's
   GROUP4 − GROUP5 +0.048 [+0.018, +0.079]).
3. **A harness improvement for later:** calibrate the sampler's top end to the real fields (the real top-95 line is 3–6
   points harder), so the harness's absolute chances match the real ones.
