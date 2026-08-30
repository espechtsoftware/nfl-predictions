# LR8 legal-relaxation residual columns: historical integrated-arm draft

**Protocol ID:** `20260820-lr8-historical-residual-columns-v1`

**2026-08-30 erratum:** the immutable LR8-v1 hard-domain identifier says
"DraftKings-only," but the implementation also retained a two-game
construction rule. LR8-v1 is preserved for artifact replay and must be
described as the legacy LR8 domain, not true platform-only legality. Existing
artifacts are not relabeled. A future true legality-only LR8 experiment needs
a new hard-domain/protocol identity and fresh source/fit artifacts.
**Prepared:** 2026-08-20
**Status:** mechanics implemented locally; **not source-frozen, launch-ready, scored,
shadow-licensed, or production-licensed**.

## One question

Can portfolio-marginal residual-world construction add better lineups to the
canonical incumbent pool when the generated columns are constrained only by
DraftKings NFL Classic legality, while keeping candidate, world, solve, and
exact-80 entry budgets fixed?

This is one integrated historical arm, not a general permission to remove
rules. It is also not a B1 retry. The earlier-period learning stage uses a new,
temporally separate corpus; B1's 2023--2025 outcome-viewed model, labels,
coefficients, predictions, and retained outcome tables are forbidden inputs.
A2a output is likewise forbidden.

`LR8` means **up to eight replacements independently in Fold A and up to eight
independently in Fold B**. Each fold has its own fixed-budget construction and
untouched simulated evaluation and receives weight 0.5 in those diagnostics.
It does not mean four plus four or eight combined. Historical adoption uses
one deployable exact-80 book per slate under the pre-outcome rule: odd week uses
Fold A and even week uses Fold B.

## Serialized time law

The arm has three irreversible stages.

1. **Earlier-period fit:** generate and source-lock a point-in-time candidate
   corpus for the exact season set `{2019, 2021}`. Read those candidates'
   realized totals once and fit the one fixed 200+ soft-anatomy model below.
   Freeze the portable artifact before any later-period outcome access.
2. **Later-period construction:** on exact 2023--2025 pre-lock worlds and
   catalogs, construct both folds, freeze every control and treatment exact-80
   candidate pool and exact-80 book, and prove all budgets and receipts without
   reading a 2023--2025 realized score.
3. **One later-period read:** after a create-once remote attempt and live
   generation-pinned historical-outcome lease, read exactly the frozen
   candidate-pool union's roster totals for 2023--2025 once. This supplies both
   candidate ceiling `C` and selected-book maximum `S`. No crash, partial
   output, null, or failed gate permits a retry, refit, alternate feature,
   alternate threshold, or alternate dose.

The training seasons are the literal set `{2019, 2021}`, not the inclusive
range 2019--2021. Season 2020 is absent from the registered learning source.
Season 2022 is excluded because the repository's documented DraftKings salary
gap makes its construction population incomparable. Evaluation is the exact
set `{2023, 2024, 2025}`, Weeks 1--18.

The earlier-period cell lattice is exact: 2019 Weeks 1--17 and 2021 Weeks
1--18, 35 season-week cells total. The fit and its frozen artifact fail closed
if any cell is absent or any additional cell appears.

All point-in-time features and model training for a slate must see only data
available before that slate's lock. No future season or week can enter a
training or construction query.

LR8 was designed after aggregate winner and B1 2023--2025 evidence had already
been reviewed, so its one 2023--2025 evaluation is disciplined historical
decision evidence, not an untouched statistical holdout or causally
independent proof. B1 rows, model, coefficients, and predictions remain
forbidden arm inputs, and no post-read retune is allowed. A full pass is
default-off Week-1-ready adoption evidence subject to the registered 2026
confirmation, not a claim of independent causal validation.

## Canonical control and fixed budgets

For each 2023--2025 slate, the control candidate pool is the canonical
incumbent R0 pool already paired to the five current-money simulation blocks
`R0..R4`. The control is not the all-panel B1 union. Within each cross-fit
fold, the unchanged incumbent selector is:

`select_tail_entries(totals, n_entries=80, line=194,
env={"SELECT_LSE":"0", "SELECT_LADDER":""})`.

The fold split reuses the August 17 residual-world seam:

| Fold | construction blocks | untouched simulated evaluation blocks | weight |
|---|---|---|---:|
| A | R0, R2, R4 | R1, R3 | 0.5 |
| B | R1, R3 | R0, R2, R4 | 0.5 |

Each fold:

- begins with the entire canonical incumbent candidate pool;
- protects its ordered incumbent exact-80 book;
- freezes an eight-row reverse-greedy removal order drawn only from
  **unselected** incumbent candidates;
- replaces the first `k` removals with exactly `k` novel residual columns,
  where `0 <= k <= 8`;
- retains exactly the incumbent candidate count at every realized dose;
- reruns the unchanged exact-80 selector after each admitted column; and
- stops irrevocably at the first null marginal solve.

Removing each prefix of one through eight candidates must reproduce the
ordered incumbent control book before any residual column may be generated.
The control and treatment use identical player worlds, active-world quotas,
candidate budgets, exact-80 budgets, and solver limits. A future source freeze
must pin the exact per-slate candidate, world, reservoir, active-world, and
solve counts; none is sweepable.

## Relaxed hard legality, exactly

New residual columns have the legacy LR8-v1 hard domain:

- nine unique players;
- exactly one QB and one DST;
- 2--3 RB, 3--4 WR, and 1--2 TE;
- total salary at most $50,000;
- no more than eight players from one team; and
- players from at least two games (an LR8-v1 construction rule, not a
  DraftKings platform requirement).

The following inherited house rules are not hard constraints for new LR8
columns:

- no $49,000 salary floor;
- no QB stack minimum or maximum;
- no bring-back minimum or maximum;
- no RB-versus-opposing-DST prohibition;
- no same-team-RB prohibition; and
- no ownership, punt, game-concentration, or other research lever.

The canonical incumbent is not regenerated under this relaxed law. Existing
incumbent candidates remain bit-identical. Only the at-most-eight replacement
columns use the relaxed domain.

## Fixed soft anatomy law

The soft model is a single `sklearn.linear_model.LogisticRegression` with
`C=1.0`, `solver=lbfgs`, `class_weight=None`, `max_iter=2000`. Inputs are
standardized once with the same weights used by the fit; every training
season-week gets equal total weight in both standardization and likelihood.
The binary label is candidate realized total `>=200` DK points.

The feature vector is frozen to:

1. salary used;
2. games and teams represented;
3. maximum players from one game and one team;
4. same-team QB WR/TE partner count;
5. opposing QB bring-back skill-player count;
6. RB-versus-DST count;
7. same-team RB-pair count;
8. naked-QB and exact-one-QB-partner indicators; and
9. QB/RB/WR/TE/DST salary spend.

There is no feature, hyperparameter, target, threshold, calibration, season,
or model sweep. After the one logistic fit, its standardized coefficients are
converted once to raw-feature linear weights, `w_j=beta_j/scale_j`, and raw
intercept, `b=intercept-sum(w_j*mean_j)`. Each is quantized at scale 1,000,000
with `Decimal` and `ROUND_HALF_EVEN`. The operative integer tier is exactly
`b_units + sum(w_units_j * anatomy_j)`. The frozen artifact stores and the
validator recomputes a conservative absolute bound using the exact DK feature
bounds (including up to six same-team QB WR/TE partners); that bound must stay
within CBC's exact integer range. The sigmoid probability remains report-only
and nonoperative.

This fixed-point linear predictor is the operative but subordinate
lexicographic tier: it follows all four portfolio threshold-clear counts and
precedes only the 210-clipped book-max gain. It can never reject an otherwise
DK-legal lineup, impose a structural quota, outrank a registered threshold
clear, make a portfolio-null lineup admissible, change the fixed candidate
budget, or be refit on 2023--2025.

## Portfolio-marginal pricing law

For the current selected reference book and each active construction world,
let `m` be its maximum and `s(l)` a proposed lineup's score. Pricing is the
lexicographic vector:

`(g_210, g_200, g_194, g_187, anatomy_linear_units, sum clipped_gain)`

where:

- `g_t = sum 1[m < t <= s(l)]`; and
- `anatomy_linear_units` is the exact signed fixed-point raw-feature linear
  predictor frozen above; and
- `clipped_gain = max(0, min(s(l),210) - min(m,210))` in integer micro-DK.

Thus 210 is the highest rewarded threshold and the book-max term cannot
reward movement above 210. Counts at 220/230/240 may be reported later but can
never affect generation, pruning, selection, or disposition. A lineup is in
the pricing domain only if at least one threshold count or its clipped gain is
positive; anatomy alone cannot qualify it. Within that positive-residual
domain, anatomy is therefore non-vacuous when the four counts tie, even when
clipped gains differ. The retained canonical roster law is minimum UTF-8
player-rank sum followed, only when that face is ambiguous, by UTF-8 incidence
chunks. This is an exact deterministic last tie-break on the frozen rank-sum
face; it is not described as the globally lexicographically smallest roster.

A null is an explicit exact proof that the positive-residual pricing domain is
empty. A zero-residual roster may not stand in for null. The sequence stops at
that first null and cannot skip it, change the active set, relax another rule,
or resume. A positive clipped gain with zero new threshold clears is not null;
it remains lower priority than any registered threshold gain.

Reverse-greedy pruning uses the same four threshold counts and the same
210-clipped sum-max tie tier. This is the only default-preserving
parameterization added to the August 17 utility helper.

## Later-period evaluation and decision

Before any 2023--2025 outcome read, each slate maps to one deployable book:
odd weeks use Fold A and even weeks use Fold B. That single exact-80 book is the
primary, license-bearing policy. Both fold books are also valued with weight
0.5 as cross-fit diagnostics, preventing the three-block fold from receiving
more diagnostic weight than the two-block fold, but their average cannot
license adoption because it is not itself a deployable 80-entry policy.

For the primary fold, `C` is the best realized score in its full frozen
candidate pool and `S` is the best realized score in its frozen exact-80 book.
Both control and treatment `C`, `S`, and `C-S` are retained per slate and in
aggregate.

All gates must pass:

1. every control/treatment candidate budget matches and every book has exactly
   80 unique lineups;
2. primary treatment mean `S` strictly improves over primary control mean `S`;
3. the primary treatment number of 200+ `S` weeks strictly improves;
4. the primary treatment 210+ `S` count is no worse;
5. the primary treatment 194+ `S` count is no worse;
6. primary treatment mean candidate ceiling `C >= 205`;
7. primary treatment mean `C-S <= 5`; and
8. primary treatment mean selected maximum `S >= 194`.

The frozen minimum `S` gate is 194 DK; 200 DK remains the objective. A tiny
lift that passes only relative gates is not a strategy pass.

The complete 187/194/200/210 grid, every fold-cell maximum, season directions,
and paired deltas must be retained. A failure closes this exact LR8 contract
with no retune. A full pass licenses only the separately frozen default-off
2026 Weeks 1--6 confirmation; it never changes production directly.

## Required real sources and present blockers

The checked-in repository supports mocked mechanics but does **not** currently
contain all immutable real inputs needed for the one-shot arm.

Required before launch:

1. Fresh point-in-time baseline player worlds, DK legality catalogs,
   DK-legal-only fixed-budget candidate pools, and candidate realized totals
   for exactly 2019 and 2021. Source audit of panel
   `20260811-pitclean-e80-k1-role12union-a12ab31` found 35 registered slates,
   8,848 accepted old-law candidates, 11,021 catalog rows, and 35 nominal
   10,000-world NPZs. Those NPZs contain only `cand_ix`, `totals`, and
   `tail_line`; they contain no player ids or player draws and therefore cannot
   score a novel relaxed roster. LR8 may reuse the generation-pinned catalog,
   incumbent no-good identities, and object receipts, but never treat the
   old-law candidate identities as relaxed candidates or reuse their totals as
   novel-roster scores. The new source freezes two baseline projection-draw
   blocks R0/R1 with 10,000 worlds each and 40 unique exact DK-only solves per
   block (80 before cross-block deduplication) for every one of the 35 cells.
   Role-belief worlds are explicitly unused; an environment role seed is
   nonoperative provenance and is absent from solve inputs and hashes.
2. A create-once training source lock proving exact years, weeks, query text,
   table generations, candidate/solve budgets, pre-lock provenance, and the
   absence of B1/A2a/later-period fields.
3. A frozen portable anatomy artifact and independent replay of its exact fit.
4. A new source lock for the 270-cell 2023--2025 `atlas-money-worlds` R0--R4
   player-world lattice, canonical R0 incumbent candidates, and relaxed
   DK-legality catalog. It must bind the repaired R3 2025 Week 1 object SHA
   beginning `7eaef50c`. The stored player-world artifacts are reusable
   score-free; the existing August 17 candidate lock enforces the old house-law
   domain and cannot license novel LR8 columns by itself.
5. Binding of the existing retained exact CBC proof path to the relaxed model,
   positive-residual eligibility, four threshold tiers, operative fixed-point
   anatomy tier, and 210-clipped gain. The local exact-solver adapter retains
   every exact-Optimal CBC stage, freezes the rank-sum/incidence tie law, emits
   canonical proof bytes to a caller-owned create-once evidence publisher, and
   supports a fresh-model exact replay validator. This mechanics proof is not
   itself a launch/source/outcome license.
6. Outcome-blind reality smokes for the training and evaluation sources,
   clean-archive validation, immutable image, update-only reused Cloud Run job,
   create-once attempt, strict terminal harvester, independent evaluator
   replay, and crash-safe lease closure.

The retained B1 outcome tables are not a shortcut for item 1. They contain
only 2023--2025 rows and fitting LR8 to them would be outcome-informed B1
retuning. B1 may be cited as motivation, never consumed as training data,
soft coefficients, labels, probabilities, or a selection comparator.

## Local implementation boundary

Prepared locally without real data or outcome access:

- `src/nfl_dfs/research/lr8_historical_arm.py` -- DK-only legality builder and
  independent audit; fixed earlier-period soft fit; fold-isolated matched-
  budget mechanics; capped marginal utility; deterministic one-book deployment
  mapping; equal-fold diagnostics; path-to-200 gates; and a strict mocked
  later-period evaluator.
- `scripts/run_lr8_historical_arm.py` -- canonical, create-only, local runner
  that deliberately accepts only `synthetic_fixture=true` contracts.
- `tests/test_lr8_historical_arm.py` and
  `tests/test_lr8_historical_runner.py` -- mocked/unit coverage only.

No Dockerfile, Cloud Build recipe, Cloud Run job, scheduler, monitoring script,
shared lease, A7/B1 code, production policy, or HANDOFF record is changed by
this mechanics milestone.
