# Recourse-aware initial-book score-free protocol

Date frozen: 2026-08-17, before this mechanism was implemented, before any
score-free treatment output existed, and while the ATLAS repair5 real-path
canary was nonterminal.

Protocol ID: `20260817-recourse-aware-initial-book-scorefree-v1`.

## Question and separation from prior work

The completed historical realistic-recourse experiment started from the
ordinary incumbent exact-80 book and changed only the late-afternoon decision
rule. Its tail-aware policy failed, while its naive conditional-mean comparator
was nonnegative but produced no new >=200 week. That experiment did **not** test
the remaining proposal in the recourse queue: choose the initial 80 entries for
the set of legal late-game alternatives they preserve.

This protocol tests that initial-construction insertion point without opening a
realized score. It is a bounded candidate-union precursor, not the full
two-stage generator. A failure closes only this candidate-union selector. It
does not prove that newly generated early cores or late completions have no
value.

## Immutable population and information boundary

- Population: 2023--2025 Weeks 1--18, exactly 54 Sunday-main slates.
- Simulation inputs: the exact R0--R4 immutable Phase-S player-world artifacts
  and candidate books already used by the passed CBWU-OI repair, including the
  independently validated R3/2025 Week 1 repair substitution.
- Five folds: hold out one complete 10,000-world block and construct on the
  other four. Use `build_training_control` from the frozen constraint-lattice
  implementation to obtain the order-invariant fixed-R0-budget candidate pool
  and ordinary exact-80 control.
- Player inputs: pre-lock ID, position, salary, team, opponent, game and exact
  kickoff only. The decision instant is always 3:55 PM America/New_York on the
  slate date.
- Forbidden: actual/final score, actual ownership, contest result/rank, payout,
  ROI, post-decision news or projection, selected historical membership and
  every treatment/effect field from another mechanism.

Every source receipt, population count, kickoff mapping and fold must validate
before an aggregate may be disclosed. A treatment uses the same candidate
pool, entry count, player worlds, legal constraints and source budget as its
control.

## Exact late-swap reachability

The initial lineup receives the existing deterministic DraftKings slot order
`QB RB RB WR WR WR TE FLEX DST` after exact kickoff timestamps are attached.
A slot is locked when its player's kickoff is no later than 3:55 PM Eastern.

A final candidate is reachable from an initial candidate only if:

1. every locked player remains in the same locked slot;
2. every other final player has kickoff strictly after the decision instant;
3. the other final players admit a complete one-to-one assignment to the open
   DraftKings slots under exact position/FLEX eligibility; and
4. the final roster is one of the same fold's admitted order-invariant
   candidates.

This is deliberately stricter than set overlap. A player from an already
started game may not be inserted, and an early FLEX occupant may not move to a
hard slot. The initial roster itself is always its fail-safe alternative.

For each initial candidate, retain at most 24 reachable alternatives, matching
the already frozen operational recourse cap. Rank alternatives on the four
training blocks only by individual simulated crossing counts at
240/230/220/210/200/194/187, then q99, mean, minimum player churn and canonical
roster identity. If the initial roster is not in the first 24, replace the
last retained alternative with it. No held-out block may choose an
alternative.

## Treatment selector

The control is the unchanged order-invariant exact-80 book. The treatment
greedily selects exactly 80 distinct initial candidates from the same pool.
At each step, adding an initial candidate exposes its frozen reachable
alternatives. Rank additions lexicographically by:

1. newly covered training worlds at 240, then 230, 220, 210, 200, 194 and 187,
   where a world is covered when any reachable alternative crosses the line;
2. number of newly exposed reachable roster identities;
3. the initial candidate's own training-world crossing counts at the same tail
   ladder;
4. its training q99 and mean; and
5. canonical initial-roster identity.

This is a set-union option-value proxy. It never sees which alternative later
wins a world and is not itself an executable late-swap rule. The held-out
evaluation reports both the initial one-shot book and the ceiling of the
reachable candidate union. A score-free pass may license one separately frozen
historical 3:55-PM policy diagnostic using the already implemented PIT scorer
and the fixed naive conditional-mean rule; it cannot license production or a
2026 money book by itself.

## Frozen score-free gate

Mechanical validity requires exact candidate-budget parity, exact-80 control
and treatment, unique initial identities, nonempty fail-safe alternative sets,
legal slot assignments and all 270 held-out folds.

The scientific disposition is
`recourse-aware-initial-book-premise-passes` only when all are true:

1. aggregate held-out reachable-union p230 coverage strictly improves and at
   least three of five held-out blocks improve;
2. aggregate held-out reachable-union coverage does not decline at p240, p220
   or p210;
3. aggregate held-out initial-book coverage does not decline at p240, p230 or
   p220;
4. aggregate held-out initial-book p194 coverage retains at least 95% of
   control;
5. mean distinct reachable alternatives per slate does not decline; and
6. treatment has at least as many distinct locked-slot signatures in aggregate
   as control.

Otherwise the disposition is
`recourse-aware-candidate-union-selector-premise-fails`. Report every threshold
from 187 through 240, per-block and per-season splits, initial-book identity
overlap, reachable-set breadth, locked-player/slot/signature distributions,
effective rank and leave-one-slate-out influence. The six conditions above are
the only gate; no post-result threshold, decision time, alternative cap,
candidate source or stability rule may be substituted.

## Consequences

- A pass licenses only a separately frozen historical policy diagnostic and a
  prospective 2026 shadow proposal. It does not adopt the treatment, alter the
  UI, or activate a scheduler.
- A failure closes this admitted-candidate-union initial selector without a
  parameter retry. It does not close a future fixed-budget generator of new
  early cores/late completions.
- Any future realized-outcome diagnostic must acquire the shared historical
  outcome lease and run only after the currently queued historical mechanism
  releases it.
