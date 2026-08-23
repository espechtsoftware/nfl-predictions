# LR8-v3 warm-chain exact-solver repair protocol

Date: 2026-08-21  
Protocol ID: `20260821-lr8-training-source-smoke-v3-warm-chain-solver-repair`  
Status: source-only mechanical amendment; no cloud or outcome authority

## 1. Predecessor and failure boundary

This amendment succeeds and permanently supersedes only the failed LR8-v2
score-free smoke identity `20260821-lr8-training-source-smoke-v2`. Its sole
Cloud Run execution was `atlas-md-prefix-r4-smoke-kgsnh`, terminal
`Completed=False`, with one failed task, no retry, and no result-body or
historical-outcome read. The canonical failure closure and terminal metadata
SHA-256 values are respectively:

- `543701bb4dfeb40131da50be3dce169e177df8f3b6f9100447582e3fb88d86b4`
- `7bb71206de912d37cc86dceed0c6be0358463209e5e324e2b4d5fe7cc397d089`

The retained application evidence stopped in the first 2019-W1/R0 world's
score-remainder stage after the preceding score-quotient stage had already
produced a complete exact assignment. Timing is consistent with exhaustion of
the registered 300-second CBC limit. That timing diagnosis is an inference;
the terminal failure itself and its no-relaunch closure are facts.

LR8-v2 must never be relaunched, overwritten, or represented as a scientific
result. V3 requires a fresh run ID, result prefix, preparation claim, exact
source build, immutable image digest, and update-only zero-retry execution.

## 2. Sole licensed repair

The first score-quotient stage remains a cold exact CBC solve. Every following
stage in that same training-world optimum must warm-start from the complete
assignment proven by the immediately preceding retained CBC receipt:

1. score remainder;
2. canonical rank sum;
3. canonical ambiguity distance; and
4. every actually required UTF-8 incidence chunk, in canonical chunk order.

The implementation must use
`residual_world_columns._validate_ordered_warm_predecessor` across every
adjacent pair in the complete stage population. It must reject a missing,
extra, reordered, cold, noncontiguous, wrong-digest, incomplete, or malformed
predecessor chain. The canonical terminal decision assignment must independently
reconstruct how many incidence chunks the unchanged canonicalization algorithm
requires, so truncating both the stage list and its claimed optima also fails
closed.

The retained proof schema advances to `lr8-exact-cbc-proof-v2`; old cold-chain
training proofs are not valid v3 proofs.

## 3. Invariants that may not change

- `EXACT_SOLVE_SECONDS` remains exactly `300` for every stage.
- The player catalog, generated float32 world, micro-DK conversion, complete
  incumbent no-goods, and DraftKings Classic-only legality domain are
  unchanged.
- The bounded score quotient, remainder, offset, objective sense, and exact
  objective reconstruction are unchanged.
- The canonical law remains
  `minimum-rank-sum-then-utf8-incidence-v1`, with the same chunk width and
  direction.
- CBC stays pinned, single-threaded, zero-gap, deterministic-seed, and
  cuts-off. Preprocessing remains at its default enabled setting throughout
  the training chain. This is the sole solver-setting change from v2: the
  bounded local reproduction proved that combining the immediate-predecessor
  MIP start with `preprocess off` emits CBC's forbidden
  `LP relaxation is infeasible or too expensive` marker even on the small
  parity fixture. Leaving preprocessing on must still pass every retained MIP
  start and ordered-predecessor proof gate below.
- No timeout increase, objective rescaling, constraint relaxation, candidate
  budget change, scientific gate change, outcome access, or retry is licensed.
- The pricing solver and later historical score path are outside this repair.

## 4. Source gates before any v3 build

Focused validation must prove all of the following:

1. one positive training solve has exactly one cold receipt followed by an
   all-warm, immediate-predecessor chain through every canonical stage;
2. every retained stage has the unchanged 300-second limit and exact semantic
   label/objective parity, cuts off, and preprocessing enabled;
3. the warm-chain roster, score quotient/remainder reconstruction, objective,
   and canonical payload equal an otherwise identical all-cold reference;
4. independent retained-evidence replay passes;
5. missing, reordered, self-rehashed-truncated, and wrong-predecessor receipt
   poisons fail closed; and
6. the unchanged exact-null pricing path remains green.

Python compilation, focused pytest, and `git diff --check` must be captured
under one serialized local test slot. This protocol and the implementation
must then be recorded by the parent in `HANDOFF.md` and committed before any
build or smoke preparation.

## 5. Cloud gate

This document grants no cloud execution authority. A later transport freeze
must bind the exact v2 closure above, the v3 protocol/source/test hashes, an
exact-source successful build and immutable image digest, a real-shaped
outcome-blind solver benchmark, an idle unscheduled reused job, empty fresh v3
prefixes, and zero retries. Only a strictly harvested v3 score-free smoke may
reopen the already-frozen downstream LR8 source chain. No realized score may be
read under this repair protocol.
