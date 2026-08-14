# TD-ledger rank-coupling five-seed exact-80 addendum

Frozen 2026-08-14 CDT while
`td-ledger-rank-coupling-v1-d9zdr` was still nonterminal and before any
rank-coupled lineup was generated, selected or scored. This makes the sole
conditional exact-80 license in
`2026-08-14-td-ledger-rank-coupling-protocol.md` executable without a
post-result choice.

## Conditional license and question

Run this experiment only if the terminal score-free report has disposition
`td-ledger-rank-coupling-gate-passes` and every registered invariant passes.
Otherwise this addendum expires without a lineup run.

The experiment asks one question: under the accepted finite-K incumbent, does
replacing only the final-served incumbent within-player world order with the
frozen TD-ledger rank order improve the tail of the best realized score among
exactly 80 selected lineups per slate?

This is one paired experiment evaluated over five pre-existing Monte Carlo
seed books, not five independent adoption attempts. Five books are required
because the frozen incumbent seed audit found material tail-count sensitivity
and only about 12.21 common rosters among independently selected portfolios of
80. The 54 slates, not the 270 seed-slate observations, remain the independent
outcome units.

## Frozen common stack

Both arms use the exact finite-K incumbent represented by
`20260812-pitclean-e80-selected-tabpfn-active-v2`:

- seasons 2023--2025, all 54 main slates;
- active-label cache `tabpfn_active_label_treatment_v2`;
- 45/55 model/market blend and the accepted served-position schedules:
  - 2023: `QB:0.965,RB:0.99,TE:0.945,WR:1.03`;
  - 2024: `QB:0.905,RB:0.97,TE:0.95,WR:1.06`;
  - 2025: `QB:0.925,RB:0.96,TE:0.94,WR:1.04`;
- possession simulation with finite Dirichlet
  `K=28.154043586960896`;
- direct role belief using exactly
  `target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump`;
- 12 role candidates, 40 boom candidates, no CE candidates and no Gumbel
  candidates;
- 10,000 worlds, 194-world coverage, a $49,000 salary floor and exactly 80
  selected entries per slate; and
- unchanged point-in-time snapshots, solvers, candidate budgets, selector,
  tiebreakers and actual-score labels.

Do not enable SIS ASOE, SIS pass-tail, SIS run-tail, route dependence, G2/G3,
production K=1, a second rank source, or any other dependence or marginal
mechanism in either arm.

## Fixed seeds and panels

Use the five seed pairs already frozen before the incumbent seed audit:

| book | baseline/simulator seed | role-belief seed |
|---|---:|---:|
| R0 | 0 | 7,331 |
| R1 | 1,137,260,708 | 2,690,847,602 |
| R2 | 2,875,959,182 | 1,630,284,992 |
| R3 | 253,722,715 | 3,374,646,876 |
| R4 | 1,643,280,042 | 3,977,633,467 |

Panel IDs are
`20260814-td-rank-control-r{0..4}-v1` and
`20260814-td-rank-treatment-r{0..4}-v1`. Control and treatment in each book
use identical seeds. No replacement, retry seed or favorable subset is
permitted.

## Sole arm difference

Control uses the unchanged final-served incumbent draws. Treatment performs
exactly the score-free protocol's stable rank coupling after all common
marginal shaping, market blending and served-position scaling:

1. independently produce the rank-source book with only `TD_LEDGER=1` and
   the same baseline seed;
2. take each aligned player's stable ascending rank-source world order;
3. stable-sort that player's unchanged control final-served values; and
4. place those values into the rank-source order.

Only world order changes. No TD-ledger value, mean, quantile, scale or weight
enters treatment. Repeating the independent rank source must reproduce the
treatment bit-for-bit. The implementation must be off by default and the
launch manifest must pin a full code SHA and immutable full-test image digest
built after focused exact-permutation, repeatability, control-parity and
incompatibility tests pass.

The permutation applies only to the incumbent baseline draw matrix used for
boom generation, candidate scoring and coverage selection. The separately
trained role-belief draw matrix is an alternate candidate generator and stays
bit-identical between arms. Applying TD-ledger ranks to that matrix would be a
second, score-free-unvalidated coupling and is prohibited. This binding was
added while the upstream execution remained nonterminal and before either
exact-80 arm existed; the launch manifest pins this final addendum hash.

## Mechanical gate before realized scoring

Require all of the following before comparing realized lineup scores:

1. the upstream score-free pass and its report/protocol hashes match the
   launch manifest;
2. every arm/book/season has 18 slates, exactly 80 distinct selected rosters
   per slate, complete labels and checksummed 10,000-world artifacts;
3. control seed R0 exactly reproduces the registered incumbent under the
   explicit current code path, while the other four control books reproduce
   their frozen seed identities;
4. within each pair, player keys, point-in-time inputs, market means, cache,
   served factors, seeds and all non-arm settings match exactly;
5. every treatment player row is a bit-exact permutation of its paired
   control row, has maximum float64 mean drift at most `1e-10`, and the
   independently repeated rank source is bit-exact;
6. treatment changes at least one eligible player's world order and reaches
   candidate masks or scores; and
7. candidate/player snapshots are exhaustively equal after excluding only
   registered distribution-derived fields, while shared roster actuals agree.

Any violation makes the exact-80 experiment invalid. Infrastructure retries
are allowed only byte-identically after proving zero destination candidate,
feature and artifact rows. Cloud release is capped at ten nonterminal cells.

## Frozen tail-first decision

For each arm and seed book, take the maximum realized score among that slate's
80 selected lineups. Sum threshold counts over all five books in order
`240,230,220,210,200,194,187`. The first nonzero treatment-minus-control
difference decides. A positive difference selects treatment; a negative
difference retains control. If all counts tie, compare the mean of all 270
seed-slate maxima; an exact tie retains control.

Report every book, aggregate and per-season tails, mean/median, paired
better/worse/tied slates, selected-roster overlap, candidate-pool overlap and
all absolute weekly deltas of at least 10 points. Also report a 2,000-resample
whole-slate cluster bootstrap with seed `8,142,027`, averaging the five books
within each resampled slate. These diagnostics measure uncertainty but do not
override the frozen decision.

A treatment win is adaptive historical evidence only. It may enter the
research baseline and a labeled 2026 prospective shadow, but it does not
silently change production, K=1, the UI or another registered experiment.
