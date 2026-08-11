# Fantasy Points Route Share tail-candidate union

Preregistered 2026-08-10 after the player-level Route Share mechanism passed,
but before any Route Share lineup candidate was generated or scored. This is
the one candidate-union experiment licensed by
`2026-08-10-fantasy-points-route-share-experiment.md`.

## Question and source policy

Can the held-out improvement in 30-point player-tail probability generate
novel lineups that improve the final 80-entry weekly maximum under the
operator's 240→230→220→210 law?

Do not choose the source generator using this experiment. First complete the
already-running corrected K1→CE12→role chain and mechanically resolve its
incumbent under the frozen tail-first comparisons. The source for this test is
that incumbent. If role is rejected, fall back to CE12 if accepted, otherwise
corrected K1. Route Share may neither influence that choice nor run early.

Only 2024 and 2025 receive Route Share candidates, because those are the two
held-out seasons that passed the player gate. The 2019, 2021, 2022 and 2023
books must reproduce the source exactly.

## Frozen point-in-time score

Reproduce the diagnostic's exact strict-prior Route Share features, control
columns, imputation/scaling, and `LogisticRegression(C=0.1, solver="lbfgs",
max_iter=2000)` 30-point models.

- For a 2024 target slate, train on eligible 2022--2023 player-weeks.
- For a 2025 target slate, train on eligible 2022--2024 player-weeks.
- Score only RB/WR/TE players with a strictly prior Route Share observation.
- Define `route_delta_30 = P_treatment(actual >= 30) -
  P_control(actual >= 30)`.
- Set the delta to exactly zero for QB, DST, or uncovered players. Do not
  extrapolate the paid signal outside the population that passed the gate.

No current-week outcome, season aggregate, alternate window, model,
regularization, position slice, clip, rank transform, or missing-value rule is
allowed.

## Frozen candidate construction

Regenerate the final source policy with identical code, data, seeds, player
universe, simulations, constraints, salary floor, stack rules, and incumbent
candidate budgets. Add exactly twelve candidates on each 2024--2025 slate and
none elsewhere. For Route candidates only, optimize:

```text
route_objective = proj_tourney + 30 * route_delta_30
```

The coefficient is fixed before lineup outcomes: it is the expected utility
of a 30-point bonus event, expressed in fantasy-point units. It is not fitted
to portfolio scores. Produce twelve sequential MILP solves, banning every
incumbent and earlier Route roster only against exact nine-player duplication
(`max_overlap=8`). Retain all normal legality and stacking constraints. Every
solve must succeed and yield a novel roster; otherwise the mechanism is
invalid and no smaller dose or relaxed constraint may follow.

Score all candidates with the unchanged incumbent production worlds. Route
Share changes candidate generation only: it may not change player simulation,
candidate support, `actual_score`, or the selector's belief matrix. Preserve
every source candidate, append the twelve novel candidates, and rerun the
unchanged 194-world-coverage selector to return exactly 80 unique entries.

## Mechanical gate and decision

Before reading lineup outcomes require:

1. complete source and treatment slate sets and exactly 80 selected entries;
2. exact source-candidate containment and equality of shared actual scores,
   simulated means, probabilities, 187/194/200/210/220 support masks, feature
   rows, player order, and required artifact presence/provenance;
3. zero Route candidates outside 2024--2025 and exactly twelve novel
   `route_tail` candidates on every 2024--2025 slate; and
4. an audit proving every nonzero Route value came from a strictly earlier
   source week and the frozen fold/model above.

If mechanically valid, compare source and union selected weekly maxima at
240, 230, 220 and 210, highest threshold first, using the existing
`candidate_union.tail_first_decision`. Promotion is allowed only when the
first non-tied threshold improves and at least one 210+ count improves.
187/194/200 counts, mean/median weekly maximum, pool oracles, season slices,
paired gains/losses, novel-candidate selection, and runtime are diagnostics.

This is one confirmatory lineup test. A valid rejection closes this exact
Route Share construction for pre-Week-1 adoption; do not tune the coefficient,
dose, optimizer constraints, selector, folds, or model on these 107 outcomes.

Pre-outcome implementation clarification: source and treatment score-artifact
checksums cannot be equal because each NPZ stores the complete candidate matrix
and the treatment has twelve additional rows. Equality is therefore required
for every persisted shared-candidate score/support statistic, while both
panel-specific artifacts must be present and hash-addressed. This correction
was made before a Route lineup was generated or scored.

## Implementation status

Candidate construction is guarded by `N_ROUTE_TAIL=12` in the replay engine;
the signal builder reuses the frozen diagnostic models and persists source
season/week plus control/treatment p30 probabilities in the immutable player
snapshot. The source cap is applied before the twelve paid candidates, so the
arm is a true added-budget union.

The evaluator is `research/route_tail_union.py`, CLI command
`route-tail-union`, with guarded runner `scripts/cloud_route_tail_union.sh`.
It refuses incomplete/unaccepted panels, validates exact source containment,
all shared support statistics, twelve correctly tagged novel candidates on
every treated slate and none elsewhere, strict-prior signal provenance, and
reproduction of the persisted treatment selection before computing outcomes.
The corrected generator chain selected direct-role panel
`20260810-lockfix-e80-k1-role12union-8677d21` as its incumbent. Before any
Route lineup was generated, wrapper `scripts/prop_lock_route_tail_union.sh`
froze treatment panel `20260810-lockfix-e80-k1-role12-route12-aa087b8`, the
audit-complete generator code identity `aa087b8`, the exact direct-role
settings, and `N_ROUTE_TAIL=12`. It requires the source's passed comparison
and promoted acceptance record before launch. No Route arm has yet been
generated or scored.
