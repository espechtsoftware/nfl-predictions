# Stack-relaxation carved-budget arm — DRAFT (NOT FROZEN)

**Status:** draft for operator review, 2026-08-19. Freezes only AFTER
the all-boom aggregate is read (its result sets the depth prior and the
comparator book). One shot when frozen; no k sweep, ever.

## Motivating evidence (N1c, frozen report `50ea349c…`)

43/51 tracked Milly winners violate the production construction
contract in our own snapshots — 32 fail QB-stack>=2, 31 fail
bring-back>=1, 20 fail both — while the $49k floor and the
same-team-RB / RB-vs-DST bans exclude ZERO winners. 84% of real winning
rosters are structurally unbuildable at any world depth, any ranking,
any admission policy. This is the only lever class that can ever emit
them.

## Ledger honesty

A WHOLESALE stack-mandate deletion was tested in the pre-CBWU regime
and rejected ("true-deletion tests cost tails"). Two differences: the
post-ensemble/post-selection law says that verdict does not transfer
across the changed selector stack, and a CARVED budget (most solves
keep the mandate; a small carve drops it) is a different lever from
deletion. The old verdict is context, not a block — but it mandates
modest expectations and a strict fixed-budget design.

## Proposed design (single lever, fixed budget)

- Same worlds, same candidate budget, same seeds as the comparator.
- Treatment: k of the 40 boom solves become OPEN solves — identical
  world, identical budget slot, constraint set drops qb_stack_min
  (2 -> 0) and bring_back_min (1 -> 0) ONLY. The $49k floor and both
  bans stay (measured to exclude no winner; keeps the arm minimal).
- Proposed k = 8 (20% carve), preregistered as the single point.
  Operator chooses the final k at freeze; no post-hoc tuning.
- Control: the registered production natives, exact-paired (all-boom
  pattern: verbatim natives, cross-scored under baseline draws).
- Co-primary: paired weekly-max >=194 count and mean weekly best, with
  the McNemar/sign-flip block from the paired-max preregistration.
- Mechanism gates (vacuity law): (a) the open solves must actually
  differ from their stacked counterparts on a majority of solved
  worlds; (b) report how many open-solve candidates violate the stack
  rules and how many are selected; a treatment whose open candidates
  are never selected is a dead lever regardless of the score delta.
- Uniqueness handling (BOOM_UNIQUE_FILL) must be identical in both
  arms; inherit whatever the all-boom read establishes as the
  comparator configuration.

## Open questions for the freeze (after the all-boom read)

1. Which k slots carve: ranks 1..8 of the boom order, or interleaved
   (every 5th)? Interleaved avoids confounding with world rank.
   Recommendation: interleaved (ranks 1,6,11,...,36).
2. Comparator: registered natives (pure production) or the all-boom
   book if it wins its arm — whichever the all-boom verdict crowns as
   the standing boom configuration.
3. Engine seam: whether the boom solve path already parameterizes
   stack minima per-solve or needs a lever (implementation survey
   before freeze; new levers register in `_lever_keys` per the
   registry test).

This draft licenses nothing. No build, no launch, no lever until the
freeze document exists with pinned SHAs and the operator's k.

## Update 2026-08-19 (operator: "I'm in favor of relaxing them")

1. **Operator direction recorded:** relaxation of the construction
   mandates is approved as a direction; this arm remains the frozen
   test that earns any production change. k defaults to the proposed 8
   unless the operator overrides at freeze.
2. **Engine seam implemented and tested** (`OPEN_BOOM_SOLVES=k`,
   registered in `_lever_keys`, default off, byte-identical when unset
   — golden-hash parity confirmed): the first k boom visits at stride
   `n_boom/k` solve with `qb_stack_min=0, bring_back_min=0`; both RB
   prohibitions and all salary bounds unchanged; open solves stay
   primary-tag `boom` (family quotas untouched) and carry a secondary
   `open` tag in `all_tags`, so they are self-identifying in the
   warehouse and in receipts.
3. **Census baseline attached** (`39d66b7c…`): winners are 22% naked-QB,
   63% stack ≤1, 61% no bring-back, 69% game-concentration ≤3 — the
   mechanism gate now reads: open-solve candidates must actually occupy
   that shape region (structure census of the carve), selected books
   must beat the chance-overlap null, and the score endpoint follows
   the standard paired co-primary.
4. Freeze still waits on the all-boom S read for its comparator; with
   the lever in the engine, the freeze-to-launch gap is one protocol
   document.

## Carve size DECIDED: k = 8 open solves per seed, absolute dose
(2026-08-19, operator delegated: "I will trust your best informed and
researched judgement on the carve size")

Reasoning, recorded so the freeze inherits it:

1. **The dose must be modest because of a measured interaction.** The
   dependence remeasurement says the law OVER-couples generic teammate
   booms (RB–RB +1.49, TE–TE +1.34 log-ratio) and UNDER-couples QB–WR.
   The stack mandate currently masks part of that bias: forced QB
   stacks stop the solver from freely chasing the whole-team pile-ups
   the law overvalues. Open solves remove that mask — they will express
   the law's biases MORE, not less. The retained same-team-RB ban
   mitigates the worst cell; TE–TE and WR–WR piles remain reachable. A
   20%-of-solves, ~3%-of-pool dose lets the selector see genuinely new
   shapes without letting a known law bias steer the book.
2. **Absolute, not proportional.** k = 8 per seed regardless of whether
   the comparator is boom-40 or boom-200 (the S read decides): the same
   absolute open-candidate dose per seed keeps the pool-composition
   change identical across comparators, so the arm stays one lever.
3. **Dose-response comes later, honestly.** The wholesale deletion
   (100%) was tail-negative in the old regime; 0% is the incumbent.
   One preregistered point at 8 decides the direction; any k sweep on
   this corpus would be panel mining and is forbidden. If k=8 clears,
   the next dose is a NEW frozen arm or a prospective shadow.
