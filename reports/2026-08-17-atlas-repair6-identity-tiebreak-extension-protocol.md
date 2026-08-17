# ATLAS repair6 identity-tiebreak numerical extension protocol

Date frozen: 2026-08-17, after repair5 execution
`atlas-md-s2023-w7-r5-44ccq` terminated with a score-free identity-tiebreak
infeasibility, while the other 52 post-canary repair5 primaries were still
nonterminal and before any repair5 shard body, treatment effect or realized
score was opened.

Protocol ID: `20260817-atlas-matched-diversity-mvp-v1-repair6`.

Evidence class: outcome-free mechanical/numerical completion repair.

Production impact: none. Historical scoring is forbidden until the new
population is complete and strictly bound under a separately frozen scorer.

## Observed defect and scope

Repair5 uses two exact MILP passes for every selected player world. The first
maximizes simulated player points and returns a legal optimum. The second
maximizes the stable player-identity rank subject to the same legality law and
a score floor equal to the first returned roster score minus `1e-6`.

For 2023 Week 7, seed R0, world 2605, the first pass completed and the second
returned infeasible. The execution then raised exactly:

`RuntimeError: ATLAS world 2605 identity tiebreak is infeasible`

It wrote no destination object. This is a solver/model failure and is
correctly ineligible for repair5's platform-only replacement. It invalidates
repair5 but does not reveal a candidate, effect or historical outcome.

Repair6 extends only the undefined second-pass numerical boundary. It does
not change the first-pass objective, player worlds, world rank, clusters,
interaction prices, enumeration objective, candidate count, admission,
exact-80 selector, seeds, legality constraints, resources, effect gate or any
historical-score rule.

## Frozen numerical law

For each exact world, run the unchanged first-pass optimizer once and compute
its returned roster score exactly as repair5 did. Then run the unchanged
identity-rank optimizer with the following absolute score-floor tolerances in
this exact order:

1. `1e-6` (the complete repair5 law);
2. `1e-5`, only if the preceding solve returned infeasible; and
3. `1e-4`, only if both preceding solves returned infeasible.

Accept the first feasible identity solution. Persist its actual tolerance in
the existing `identity_tolerance` field and require its original simulated
roster score to be at least `optimum - identity_tolerance - 1e-8`. If all
three solves return infeasible, the cell is terminal invalid. No tolerance is
selected from a candidate score, treatment effect or realized outcome.

This is a partial-function extension: every world for which repair5's `1e-6`
pass succeeded follows the same calls, objective, floor, result validation and
serialized fields as repair5. The larger tolerances are unreachable on those
worlds. Unit tests must prove this short-circuit and the exact fallback order.

## Repair5 terminal census and eligible cells

Allow all 54 repair5 primaries to reach terminal state and seal the already
frozen terminal census. Do not cancel them and do not open any shard body.

A repair5 cell is eligible for repair6 computation if and only if:

- its exact primary execution is terminal failed with one failed task and no
  succeeded or cancelled task;
- its ledger-declared destination object is absent;
- its Cloud Run condition reports ordinary nonzero exit; and
- its complete error traceback ends in
  `RuntimeError: ATLAS world <integer> identity tiebreak is infeasible`, with
  no memory, timeout, signal, CBC-child, infrastructure or other exception.

Every such cell is included; none may be selected or omitted. Any repair5
failure outside this exact class closes repair6 without launching it. A
repair5 terminal-success cell is mechanically reusable because repair6 cannot
reach a changed branch in that cell. The strict repair6 receipt must bind its
original execution, exact immutable object generation/size/SHA-256, and the
code-diff proof below. It must not parse the object.

## Two real-path canaries

Before releasing any other repair6-eligible cell, run exactly two canaries
under the repair6 image and code:

1. **Defect canary:** 2023 Week 7, using the final repair6 job, URI and exact
   source inputs. It must complete successfully and write one positive object.
   Metadata validation may not open it.
2. **No-change canary:** 2023 Week 1, using a dedicated create-only proof URI.
   After terminal success, compare the complete downloaded bytes and SHA-256
   with the immutable successful repair5 2023 Week 1 object. They must be
   byte-identical. These bytes are compared only for equivalence and no JSON
   field may be parsed or reported.

Failure of either canary closes repair6. The 2023 Week 7 canary is the accepted
repair6 object for that cell; it is not rerun. The Week 1 proof object is not
part of the scientific population and cannot replace the retained repair5
Week 1 object.

## Code-diff and population boundary

Before either canary, a machine verifier must compare the exact repair5 runner
source with repair6 and require that the only semantic change in
`solve_exact_worlds` is:

- declaration of the frozen ordered tolerance tuple;
- iteration over that tuple after the unchanged primary solve;
- stopping on the first feasible identity solution; and
- recording/checking the tolerance actually used.

Package and full-test the exact repair6 commit. Every job remains one task,
8 CPU, 32 GiB, zero task retries and a 43,200-second timeout with the same
service account, inputs, seeds, environment and command. Every destination is
create-only under a new repair6 prefix.

The strict completed population contains exactly one accepted object for all
54 cells:

- the immutable repair5 object/execution for every terminal-success repair5
  cell; and
- the immutable repair6 object/execution for every exact eligible
  identity-tiebreak failure.

It additionally binds the full repair5 terminal census, both canary receipts,
the exact eligible-cell classification and every primary/execution/object
identity. Extra executions, missing cells, duplicate cells, unreceipted
objects, a repair6 run for a repair5 success, a repair6 omission, or any opened
partial/effect field invalidates the population.

The only valid score-free completion disposition is
`valid-complete-repair6-hybrid-population`. A separately frozen historical
transport may then reconstruct and score that complete population. Repair6
itself cannot adopt ATLAS, alter production, or claim a scoring gain.
