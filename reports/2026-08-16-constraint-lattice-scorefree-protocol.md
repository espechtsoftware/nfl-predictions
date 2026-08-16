# Constraint-lattice exact-80 score-free protocol

Date frozen: 2026-08-16, while the ATLAS 32-GiB binary full-cell preflight
was nonterminal and before any constraint-lattice implementation or result
existed.

Protocol ID: `20260816-constraint-lattice-scorefree-v1`

## Question and consequence boundary

Can a bounded sleeve of lineups that violate exactly one incumbent strategic
constraint improve the simulated extreme-tail reach of an exact-80 book while
retaining the incumbent majority and the lower-tail safety of the control?

This is an outcome-free construction diagnostic. It may read only immutable
pre-lock player catalogs, salaries, native R0--R4 player worlds and candidate
identities already validated by the CBWU-OI source chain. It may not query or
load realized fantasy scores, historical selected scores, ownership, contest
rank, payout, ROI, post-lock news or any forensic outcome label.

A pass licenses only a separately identified 2026 pre-lock shadow. It cannot
change production, the UI default or a money book and cannot inherit any
historical score from CBWU-OI, ATLAS or another arm. A valid null or failure
closes this exact v1 design; its cells, quotas, world ranker, admission margin
and gate may not be swept on the same 54-slate simulation panel.

## Fixed population and common inputs

- Population: 2023--2025 Weeks 1--18, exactly 54 Sunday-main slates.
- Source blocks: the exact five immutable R0--R4 native books used by the
  passed CBWU-OI score-free repair, exactly 10,000 worlds per block.
- Player identity, position, team, opponent, game, salary and all row draws
  must align exactly across blocks before a solve starts.
- The R0 native candidate count is the fixed control candidate budget in every
  fold, including the fold that holds out R0. Reading that count does not
  admit any R0 roster or score into the R0-held-out training set.
- DraftKings Classic roster shape, $50,000 cap, $49,000 floor, at least two
  games, all status/eligibility rules and exact roster uniqueness remain hard.
- Control and treatment use the same four training blocks, the same held-out
  block, the same source candidates and the same deterministic tie breaks.

## Five-fold score-free separation

Each slate produces five independently reconstructed comparisons. For fold
`Rh`, block `Rh` is excluded completely from candidate construction,
candidate admission, exact-80 selection and swap decisions. Only after both
books are frozen is `Rh` used to measure them.

The four training source books are combined by the CBWU-OI complete-union law:
canonical sorted roster identity, symmetric tag/source aggregation,
cross-scoring on the four training blocks, fixed R0 candidate budget and the
unchanged 194-point candidate-admission selector. The unchanged 194-point
exact-80 selector creates the fold's control book. A held-out source roster is
not part of the union. All five folds must return the fixed candidate budget
and exactly 80 legal, unique control lineups.

This is a simulated-block falsifier, not a claim that simulator seeds are
independent NFL seasons. It prevents the candidate/swap rule from being chosen
on the same block used for its final score-free measurement.

## Atomic exception cells

Every exception must satisfy all common legality and salary constraints and
must violate exactly the named incumbent strategic constraint. The five atomic
cells and maximum sleeve quotas are fixed:

| order | cell | exact exception | quota |
|---:|---|---|---:|
| 1 | `qb1_bringback` | exactly one QB-team WR/TE and at least one opposing RB/WR/TE | 2 |
| 2 | `qb2_no_bringback` | at least two QB-team WR/TE and exactly zero opposing RB/WR/TE | 2 |
| 3 | `qb1_no_bringback` | exactly one QB-team WR/TE and exactly zero opposing RB/WR/TE | 2 |
| 4 | `rb_vs_dst` | incumbent QB+2/bring-back and at least one RB against the selected DST | 1 |
| 5 | `two_rb_same_team` | incumbent QB+2/bring-back and at least two RBs from one team | 1 |

The two RB cells are separate: `rb_vs_dst` retains the one-RB-per-team ban;
`two_rb_same_team` retains the RB-versus-opposing-DST ban. No lineup may enter
more than one cell. The treatment therefore contains at most eight exception
lineups and at least 72 incumbent-constraint lineups. There is no quota refill
between cells; an infeasible or non-admitted slot remains unused.

## Fixed candidate construction

For every fold, each of its four training blocks and each atomic cell:

1. Rank all 10,000 worlds by the existing deterministic Classic attainable
   roster upper bound used by the ATLAS score-free ranker. This ranker is
   common to every cell and does not use a realized score.
2. Visit worlds in descending bound and ascending world-index order. Solve the
   exact legal MILP with the cell's exact exception constraint and all other
   incumbent constraints. Retain the first two distinct legal exception
   rosters; exact duplicates of a control candidate or an earlier exception
   are skipped. At most 16 raw proposals per cell and fold can result.
3. Cross-score every proposal on all four training blocks. Within each cell,
   retain at most its fixed quota by descending lexicographic order of:
   minimum block p230, total p230, minimum block p210, total p210, minimum
   block p194, total p194, q99, mean, then ascending canonical roster key.

The construction limit is therefore at most 40 accepted source solves per
fold and 200 per slate. Attempts, infeasibility, duplicates, exact exception
classification, candidate identities and runtime must be receipted. The
treatment receives more construction compute than the control; that cost is
mandatory context and no fixed-budget superiority claim is permitted.

## Frozen sleeve admission

Start from the fold's exact-80 control. Process retained candidates in the
cell order above and then their within-cell rank. Previously admitted
exceptions cannot be removed.

For each candidate, evaluate swapping it for every still-removable strict
lineup using only the four training blocks. Choose the swap with the greatest
lexicographic vector:

1. minimum block change in book p230 coverage;
2. total p230 coverage change;
3. minimum block change in book p210 coverage;
4. total p210 coverage change;
5. minimum block change in book p194 coverage;
6. total p194 coverage change; and
7. ascending removed-roster key.

The chosen swap is admitted only when all conditions hold:

- p230 book coverage gains at least one world in at least three of four
  training blocks;
- p230 book coverage declines in no training block;
- p210 book coverage declines in no training block; and
- aggregate p194 coverage after the swap is at least 95% of the original
  fold-control coverage.

One world is the exact finite-sample margin; probabilities may not replace it
with a rounded comparison. Rejected candidates remain rejected. There is no
second pass, threshold fallback, quota transfer or post-result cell choice.

## Held-out measurements and gate

After both fold books are immutable, score their 80 roster totals in the one
held-out 10,000-world block. Persist per fold and in aggregate:

- exact entry count, uniqueness, legality and exception-cell counts;
- candidate attempts, retained candidates, admitted swaps and compute time;
- book-maximum coverage at 187, 194, 200, 210, 220, 230 and 240;
- q90, q95 and q99 of the book maximum plus its mean;
- player, pair, QB-stack-core and dominant-game reach;
- control/treatment identity overlap and maximum pairwise roster overlap; and
- the five held-out block deltas at every threshold.

The mechanism passes only if all mechanical checks pass and:

1. aggregate held-out p230 book coverage strictly improves;
2. held-out p230 coverage improves in at least three of five folds;
3. aggregate held-out p210 coverage does not decline;
4. aggregate held-out p194 coverage retains at least 95% of control; and
5. every fold retains at least 90% of control's player-pair and QB-stack-core
   reach.

Thresholds above and below 230, q90/q95/q99/mean, individual cells and season
splits are mandatory context, not alternate gates. In particular, a p210-only
gain cannot rescue a p230 failure, and one favorable cell cannot be selected
after seeing the held-out result.

## Execution and queue rules

Implementation must be a pure analysis module plus create-only Cloud Run
runner, launcher and strict finisher. Before launch, an immutable full-test
image must pass a real-container CLI smoke. The runner must deny outcome-named
query fields and the finisher must independently validate the exact five-fold
population, inputs, resources, code/image identity, object generations and
protocol hash.

This diagnostic may be implemented while ATLAS runs because implementation
opens no outcome or ATLAS effect. Its Cloud execution queues behind the active
ATLAS binary/repair5/historical branch and must not compete for the 32-GiB
research slot. No ATLAS result may alter this v1 protocol.

