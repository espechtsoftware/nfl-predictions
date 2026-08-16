# Stack-core x shell score-free construction protocol

Date frozen: 2026-08-16, before this mechanism was implemented, before any
stack-core/shell treatment candidate existed, and without reading a realized
score. The ATLAS 32-GiB full-cell preflight was still nonterminal and the
constraint-lattice support population had not launched.

Protocol ID: `20260816-stack-core-shell-scorefree-v1`.

## Purpose and separation

This is the prospectively queued fallback for the repeated-MILP ATLAS search.
It tests whether useful partial solutions already present in the incumbent
candidate geometry can be recombined into tail-plausible legal rosters that a
single linear solve did not produce. It is not ATLAS, a stack relaxation, a
candidate-budget expansion, a selector sweep or a realized-oracle search.

The treatment is inserted after four-block CBWU-OI admission and before the
unchanged exact-80 selector. The final treatment candidate budget is identical
to control: 40 recombinant proposals merely compete with the admitted control
pool for the same fixed number of candidate slots.

## Frozen inputs and folds

- Use the immutable R0--R4 production-multinomial ATLAS money-world panels
  `20260815-atlas-money-worlds-r0-v1` through `-r4-v1`, their completed
  acquisition receipts, and the repaired point-in-time player catalog bound
  by the current-money ATLAS transfer.
- Evaluate all 54 Sunday-main slates from 2023--2025.
- For each held-out block R0--R4, reconstruct the candidate-budget-matched
  four-training-block CBWU-OI control used by the constraint lattice. Neither
  treatment construction, admission nor exact-80 selection may read the
  held-out block.
- No actual fantasy score, contest result, rank, payout or post-lock ownership
  field is permitted.

## Core and shell library

Use only the fixed admitted control candidates for the fold. Every source
lineup must satisfy the incumbent $49,000 salary floor, exact DK Classic
legality, QB+2 catcher minimum, opponent bring-back minimum, distinct-team RB
rule and RB-versus-opposing-DST ban.

For each source lineup enumerate every four-player core consisting of its QB,
any two same-team WR/TE pass catchers, and any one opponent RB/WR/TE
bring-back. The complementary five players are that core's shell. Deduplicate
cores and shells by sorted player identity while retaining all parent
provenance.

Score each complete parent lineup on the four training blocks. Rank parents
lexicographically by worst-block then aggregate p230 support, worst-block then
aggregate p210 support, worst-block then aggregate p194 support, aggregate
mean, and stable roster identity. A component inherits the best rank of any
parent containing it.

Retain exactly 32 cores, with no more than four per QB and eight per dominant
game, and exactly 128 shells. A slate/fold that cannot supply these fixed
libraries is mechanically invalid; counts are not relaxed.

## Recombination and fixed proposal book

Cross the 32 cores with the 128 shells. Retain only disjoint unions that form
nine unique players and satisfy every incumbent legality and strategic rule.
Exclude every roster already in the admitted control pool. Deduplicate a
roster produced through multiple decompositions by the best component-rank
pair, then stable core/shell identity.

Score every legal recombinant on all four training blocks and rank it by the
same p230/p210/p194 worst-block, aggregate and mean order used for parents.
Keep the best 256-roster beam. From that beam choose exactly 40 proposals:

1. choose the best-ranked roster first;
2. thereafter maximize the number of previously uncovered core-to-shell
   player pairs, then use the frozen recombinant rank and stable identity; and
3. require every accepted roster after the first to add at least one such
   pair.

Failure to produce 40 unique proposals closes the cell. No alternate beam,
library size, threshold, refill or objective may be selected after inspection.

## Candidate admission and selection

Append the 40 proposals to the fixed control candidate pool, sort the union by
stable roster identity and reapply the identical four-training-block CBWU-OI
p194 admission law to the original candidate budget. Thus every admitted
proposal displaces a control candidate and a proposal that adds no simulated
value may be rejected. Apply the unchanged deterministic exact-80 p194
selector to control and treatment separately. Evaluate both books only on the
excluded fifth block.

Receipt, for every slate/fold, component counts and caps, legal/duplicate
recombination counts, exact 256/40 proposal counts, proposal admission count,
candidate and selected identities, pair/core/game reach, overlap/effective
rank, and held-out candidate/selected book-max coverage at
187/194/200/210/220/230/240.

## Support gate and score-free disposition

Before any treatment is constructed, run a separate control-only census over
this protocol's production-multinomial inputs and exact four-block CBWU-OI
control. For every held-out block it must report each slate's control
candidate and exact-80 book-maximum event counts at p194/p210/p220/p230,
complete 54-slate contribution vectors and concentration diagnostics. The
first anchor in the predeclared 230, 220, 210 order with at least 540 events
and 41/54 positive slates in every block is supported. Terminally insufficient
support closes this score-free execution. No treatment may be constructed by
the census and no lower anchor may be invented afterward.

A score-free pass requires all of:

1. exact mechanics and 54 slates x five held-out folds;
2. treatment selected-book coverage at the supported anchor improves in
   aggregate and in at least three of five blocks;
3. treatment candidate-pool coverage at that anchor improves in aggregate;
4. selected p210 coverage does not decline in aggregate (or strictly improves
   when 210 is the primary anchor);
5. selected p194 coverage retains at least 95% of control; and
6. distinct candidate-player-pair, selected QB-stack-core and selected
   dominant-game reach each retain at least 90% of control in every block.

Report the full threshold grid, season splits, complete slate contribution
vectors and leave-one-slate-out decision stability as diagnostics. They may
not change the frozen gate.

## Consequence boundary

A pass licenses one separately labeled 2026 pre-lock shadow and, if ATLAS
remains mechanically infeasible, permits this search to be evaluated as its
construction fallback. It cannot alter production, inherit ATLAS evidence,
authorize historical-score tuning, or be combined with the constraint-lattice
exception sleeve without a new prospective factorial protocol. A failure
closes this exact 32/128/256/40 mechanism and does not license a parameter
sweep.
