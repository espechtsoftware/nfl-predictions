# Frozen protocol: coherent model/market-state construction shadow

Date: 2026-08-16  
Version: `coherent-market-state-scorefree-v1`

This protocol is frozen after the outcome-blind support census and before any
treatment candidate, held-out treatment coverage, realized score or contest
outcome exists. It is an independent fixed-budget construction test queued
behind ATLAS, not a repair or sensitivity of the previously closed
player-level market-tail-disagreement feature gate.

Support receipt:
`reports/2026-08-16-coherent-market-state-support-census.md`, SHA-256
`677171a16e339083b2eb1272926e9024ecab63b531ecc861d5237f94e61c0e63`.

## Question

The live 45/55 blend is an appropriate served mean, but it can describe
neither source's coherent state when the model and market disagree. Can a
small, fixed-budget generator that preserves the disagreement as complete
team stories discover novel lineups whose extreme-tail coverage survives
scoring and selection under the unchanged incumbent simulation law?

This test changes candidate discovery only. It does not change any served
mean, marginal distribution, simulator world, candidate score, selector,
salary/stacking rule, entry count, production policy or UI behavior.

## Immutable source and folds

- Candidate source:
  `nfl_predictions.replay_candidates_staging`.
- Feature source: `nfl_predictions.slate_player_features`.
- Native panels: `20260815-atlas-money-worlds-r0-v1` through
  `20260815-atlas-money-worlds-r4-v1`.
- R3/2025 Week 1 only: replace the incomplete native row source with
  `20260816-atlas-mvp-repair-r3-2025-v1`, already mechanically proven equal
  to the registered original arrays and candidate totals.
- Scope: 2023--2025, Weeks 1--18, exactly 54 slates.
- Five walk-forward-by-simulator folds: for held-out block R0 through R4,
  build and select on the other four 10,000-world blocks; evaluate only on
  the untouched 10,000-world held-out block.

The source loader must bind the already-frozen current-money transfer, CBWU-OI
and R3 repair receipts. SQL may name only source identity, roster, artifact and
pre-lock player fields. `actual`, `actual_score`, `actual_rank`, ownership,
payout, contest rank, selected result and label-completeness fields are
forbidden.

The control in every fold is the existing four-training-block CBWU-OI control:
the score-blind union is admitted to the exact R0 native candidate budget and
the unchanged 194-tail selector returns exactly 80 lineups.

## Frozen team eligibility and ordering

The candidate universe is the set of players appearing in the native R0
candidate roster strings for that slate. A player is covered only when
`market_points`, `model_points_pre` and `mean_projection` are all finite. A
team is eligible only when that universe contains at least one covered QB and
at least two covered WR/TE players.

For each eligible team:

1. calculate `abs(model_points_pre - market_points)` for every covered
   QB/RB/WR/TE;
2. sort those player disagreements descending with player ID as the stable
   tie-break;
3. define team disagreement magnitude as the sum of the largest three; and
4. rank teams by descending magnitude with team abbreviation as the stable
   tie-break.

Use exactly the top three teams. The locked QB for a team is its covered QB
with the largest `mean_projection`, breaking ties by player ID. Any slate that
cannot reproduce exactly three ordered eligible teams is mechanically invalid;
eligibility or team count may not be relaxed after treatment construction.

## Two coherent states and two candidates per state

For each ordered team, construct exactly two epistemic states in this order:

1. `model`: for every covered QB/RB/WR/TE on that team, add
   `model_points_pre - mean_projection` to its incumbent world score;
2. `market`: for every covered QB/RB/WR/TE on that team, add
   `market_points - mean_projection` to its incumbent world score.

Players outside the named team, DSTs, and target-team players without complete
coverage retain their incumbent world score. Values are not clipped or
rescaled. The shift is used only as the optimization objective for discovery;
every admitted lineup is subsequently scored on the original unshifted
incumbent draws.

For one target team, rank all 40,000 training world identities by the sum of
the **unshifted** scores of its covered QB/RB/WR/TE players, descending, with
registered block order then world index as stable tie-breaks. The state shift
does not alter this anchor order. Scan at most the first 64 anchors.

At each anchor, solve the unchanged strict money-lineup problem with:

- salary cap 50,000 and salary floor 49,000;
- exactly nine DK Classic players and the incumbent position limits;
- `StackRules(qb_stack_min=2, bring_back_min=1)` with the incumbent RB/DST
  and same-team-RB prohibitions;
- the target team's frozen QB locked; and
- every admitted control candidate and every prior treatment addition banned
  as an exact roster identity (`max_overlap=8`).

Accept at most one candidate from an anchor and continue until exactly two
novel candidates exist for that team/state. The fixed order is team rank,
`model`, `market`, then candidate number. Any state unable to produce two
novel legal candidates within 64 anchors invalidates the entire slate/fold.
There is no fallback, extra anchor budget or lower stack/salary standard.

The treatment therefore has exactly `3 teams * 2 states * 2 = 12` novel
candidates per fold/slate, with a six-model/six-market balance.

## Fixed candidate budget and unchanged selection

Compute each admitted control candidate's training-world tail rank as the
lexicographic tuple:

1. minimum and sum of its p230 counts over the four training blocks;
2. minimum and sum of its p210 counts;
3. minimum and sum of its p194 counts; and
4. mean score over all 40,000 training worlds.

Sort ascending by that tuple, breaking ties by canonical roster identity, and
remove exactly the first 12. Record their complete source/tag lineage; removal
is not restricted to a mutable tag quota. Append the 12 coherent-state
candidates and score them on the unchanged four incumbent blocks. The
treatment candidate count must equal the control candidate count exactly.

Run the same exact-80 194-tail selector with `SELECT_LSE=0` on control and
treatment. The state-shifted objectives are never supplied to admission,
selection or held-out evaluation.

## Outcome-free report

For every slate/fold report:

- exact source receipt, teams, disagreement ranks and covered players;
- model/market shifts and the frozen QB;
- all scanned anchor identities, solve status, accepted roster and reason;
- the 12 removed and 12 added roster identities and source tags;
- fixed-budget, legality, uniqueness and exact-80 invariants;
- candidate and selected held-out world counts at
  187/194/200/210/220/230/240;
- addition-to-exact-80 conversion and state/team composition;
- candidate and selected roster overlap, unique players, player pairs,
  QB+two-catcher stack cores, dominant games and effective rank; and
- complete per-season, per-held-out-block and 54-slate aggregates plus
  leave-one-slate-out influence.

The aggregate score-free gate passes only if all conditions hold:

1. treatment candidate-pool p210 held-out coverage strictly exceeds control;
2. treatment exact-80 p210 held-out coverage strictly exceeds control;
3. exact-80 p210 improves in at least three of five held-out blocks;
4. candidate-pool and exact-80 p230 coverage are each non-declining;
5. candidate-pool and exact-80 p194 coverage each retain at least 95% of
   control; and
6. in every held-out block, treatment exact-80 unique-player-pair reach and
   QB+two-catcher stack-core reach each retain at least 90% of control.

Counts aggregate across all 54 slates within a held-out block. Block
correlations and support concentration are diagnostics, not additional gates.
No threshold or condition may be weakened after any treatment coverage is
visible.

## Interpretation and later scoring boundary

A pass licenses only a distinctly labeled 2026 pre-lock shadow. A failure
closes this exact construction family; it does not license trying different
team counts, shift scaling, anchor counts, ranking functions, source weights,
removal ranks or gates on these same held-out worlds.

The outcome-free report is not a historical scoring claim. To avoid
effect-selected disclosure, a separately frozen historical scorer should run
after any mechanically valid complete score-free harvest regardless of whether
the score-free gate passes. Its fixed tail-first signal is: at least two more
selected weekly maxima at or above 200, no decline in selected maxima at or
above 210/220/230/240, and no decline in candidate-pool maxima at or above
200 over the same 54 slates. Because this mechanism was designed after those
seasons were observed, even that signal can support only prospective 2026
shadowing, never retrospective production promotion.

Production and the UI remain unchanged unless distinct-slate prospective 2026
evidence later supports adoption.
