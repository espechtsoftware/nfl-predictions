# Fantasy Points coverage-fit candidate-union protocol

Preregistered 2026-08-10 after the player-level coverage-fit gate passed and
before any lineup using the coverage signal was generated or scored.

## Licensed question

Does the small but valid prior-season receiver/opponent coverage-fit signal
add a nonredundant high-scoring lineup when used only to generate twelve novel
candidates, while the incumbent simulator, candidate scores, selector and
final 80-entry count remain unchanged?

This is the only lineup test licensed by
`reports/2026-08-10-fantasy-points-coverage-fit-experiment.md`. It may not
select a feature, position, support threshold, model, coefficient, dose or
season after seeing lineup outcomes.

## Mechanical source choice

Wait for the already-running Route Share union to finish. The source is chosen
mechanically:

1. if Route Share passes its frozen high-to-low law and is promoted, use the
   complete accepted Route treatment panel
   `20260810-lockfix-e80-k1-role12-route12-aa087b8`;
2. otherwise use accepted direct-role incumbent
   `20260810-lockfix-e80-k1-role12union-8677d21`.

Exactly one of those branches may launch. The choice cannot depend on a
coverage-lineup outcome, because none may exist before the source is fixed.

## Frozen player signal

Reproduce the exact walk-forward models from the passing diagnostic:

- target 2024 trains on target-season 2023 rows whose coverage inputs come
  from source season 2022;
- target 2025 trains on target seasons 2023--2024 whose coverage inputs come
  from source seasons 2022--2023;
- control inputs, treatment inputs, imputation, scaling and
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` remain byte-for-
  byte the diagnostic definitions; and
- `coverage_delta_30 = treatment_probability(actual >= 30) -
  control_probability(actual >= 30)`.

Target-season outcomes are neither required nor read when constructing the
delta. WR/TE players without all frozen support fields receive a zero delta;
all other positions receive zero. Every nonzero row must prove both receiver
and opponent-defense source seasons equal target season minus one.

## Frozen candidate construction

For 2024 and 2025 only, retain every source candidate and append exactly twelve
novel coverage candidates per slate:

1. set each player's temporary optimizer objective to
   `proj_tourney + 30.0 * coverage_delta_30`;
2. solve the unchanged legal optimizer twelve times, banning every source
   roster and each already-added coverage roster at exact-nine overlap;
3. keep `max_overlap=8`, the incumbent stack rules, locks, salary rules and
   deterministic candidate order; and
4. tag every addition `coverage_tail`.

The factor 30 and dose 12 are frozen now. They mirror the already-registered
Route construction and cannot be swept. For 2019, 2021, 2022 and 2023 the
treatment candidate pool and selected book must be byte-identical to the
source. The coverage batch is added after any Route batch, so a Route source
roster cannot be relabeled as coverage novelty.

Run the unchanged 194 coverage selector over the augmented pool and return
exactly 80 unique final entries. Source-candidate actuals, simulated means,
187/194/200/210/220 support masks and common world counts must match exactly;
the paid signal may generate candidates but may not rescore them.

## Frozen reports and decision law

The comparator must report:

- all 107 slate counts and exact-80 completeness;
- source containment and exactly twelve novel `coverage_tail` candidates on
  every 2024/2025 slate, zero on all earlier slates;
- shared-roster actual, simulated-mean, probability and support-mask parity;
- selected and pool-oracle counts at 187/194/200/210/220/230/240;
- paired weekly wins/ties/losses, mean/median and season deltas; and
- candidate salary, position, selected-membership and runtime diagnostics.

After mechanical validity, compare selected counts in fixed order
240, 230, 220, then 210. Promote only if at least one 210+ threshold improves
and no higher threshold worsens. A tie through 210 closes the arm. Counts at
200/194/187 and mean score are diagnostics, not vetoes. There is one launch,
one comparison and no retry.

Even a historical pass is not live adoption until the same signal is
reproduced before lock from the retained 2025 source exports, the final source
policy remains an explicit fallback, and generation fits the Week 1 operating
window.

## Pre-outcome implementation status

No coverage-tail candidate, panel, selected lineup or score exists at this
milestone. Implementation must add a score-free signal loader, a guarded
twelve-candidate generator, strict point-in-time/parity tests, an immutable
panel wrapper and a one-shot comparator before launch. The original licensed
exports remain private and hash-locked; no additional vendor table is allowed.
