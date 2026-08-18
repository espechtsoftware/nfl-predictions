# Residual-world exact-solver and selector-law amendment

Date: 2026-08-17

Amendment ID: `20260817-residual-world-exact-solver-selector-v1`

Parent protocol ID: `20260817-residual-world-column-generation-scorefree-v1`

Parent protocol SHA-256:
`db02c7bb7994ea887ad32a935f3188bc78384c3c4b97a3dc712f3ffd2a8fc02a`

Status: **prospective, score-free implementation amendment** to
`reports/2026-08-17-residual-world-portfolio-column-generation-prospective-protocol.md`.

At the time this amendment was written, no real-slate residual-world column,
treatment candidate pool, treatment selected book or residual score-free
endpoint had been produced. Consequently, no residual-treatment identity or
output had been joined to historical scores or realized 2026 outcomes.
Previously known control/baseline historical results were not consulted in
choosing these implementation details. Only synthetic/brute-force fixtures and
ordinary optimizer parity fixtures had been exercised. This amendment changes
no production policy and licenses no cloud execution.

The original protocol remains controlling except where this document makes a
more exact numerical, tie-proof, selector-input or evidence distinction.
The exact parent-protocol and amendment bytes and hashes are mandatory inputs
to the code, image, launcher and scientific manifests; an ID without its
content hash is not sufficient.

## Reason for the amendment

Implementation testing exposed two facts that the original protocol did not
fully specify:

1. PuLP 3.3.2 can report CBC 2.10.3 incumbents stopped by time, node, solution
   or nonzero-gap limits as `Optimal`; in the nonzero-gap case both PuLP status
   fields can be `Optimal`.
2. Direct large micro-DK coefficients and objective values can be represented
   imprecisely in CBC rows or textual objective receipts even when the intended
   roster arithmetic is integral.

It also remained ambiguous whether the unchanged production selector should
consume integer micro-DK totals or the canonical stored float32 candidate
totals. These are mechanical questions, not treatment choices, and are frozen
here before any treatment output exists.

## Canonical selector-input law

The unchanged selector consumes the exact candidate-total representation made
by canonical `combine_cbwu_books`:

- player rows are aligned in the locked base-player row order;
- the nine selected float32 rows are summed in that row order with NumPy's
  float32 accumulation;
- the result is stored as float32; and
- `select_tail_entries` receives that stored matrix and performs its existing
  internal `np.asarray(..., dtype=float)` promotion.

Every generated residual column uses the identical row-order/sum/cast routine.
The selector never consumes `micro_DK / 1_000_000` or a separately computed
float64 sum.

Independently, every control and generated lineup is represented by:

- per-player `np.rint(float64(stored_float32) * 1_000_000).astype(int64)`
  micro-DK rows for pruning and MILP proof; and
- a float64 sum of the same nine stored float32 rows for the protocol's raw /
  integer error and threshold-indicator parity audit.

The raw selector matrix, micro-DK matrix and float64 validation result are
separate receipted objects. The validation receipt includes their canonical
digests, maximum absolute raw-versus-micro error and registered-threshold
indicator-parity digest. It must prove identical registered-threshold
indicators among the stored float32 selector total, float64 nine-row sum and
micro-DK total. Agreement within the error bound does not permit one
representation to replace another. Selector and selection-stability operations
consume the stored float32 law; exact construction and endpoint arithmetic use
the micro-DK law; mandatory parity makes their registered tail counts identical.

## Algebraically exact solver formulation

The protocol's feasible set, thresholds, lexicographic order, tight legal
bounds, positive-part definition, no-good cuts and final identities do not
change. The implementation may express the same integer relations through
small-coefficient radix and Boolean circuits:

- base-100 selected-digit/carry adders link legal-bound lineup selection to
  the exact integer micro-DK score without large-coefficient equality rows;
- binary adders link pricing lineup selection to exact scores, and exact
  comparators implement threshold bi-implications;
- the exact binary score comparator also determines the positive branch, while
  selected-player/branch product variables implement the exact positive part;
  and
- every scientific quantity encoded by auxiliaries--score, threshold
  indicator, positive part, tier objective, rank and final identity--is
  independently reconstructed from the final binary roster. Exhaustive and
  randomized fixtures verify circuit equivalence.

Exact legal minima and maxima use a nonnegative fixed-cardinality score shift,
then sequential base-100 quotient and remainder objectives. The quotient is
optimized and frozen by equality before the remainder is optimized in the same
sense. The two stages are lexicographically identical to directly minimizing
or maximizing the full integer score. Both stages require separate retained
proofs and the final roster must reconstruct the full bound exactly.

Tail optima are established in the binary-adder/comparator pricing model and
frozen as exact integers. The same proven model and complete incumbent are
retained while exact positive-branch/product and binary residual-sum machinery
is added. Separately solved radix legal-bound models supply the immutable `L`
and `H` values and witnesses consumed by pricing; they do not supply or inherit
the pricing model's auxiliary assignment. Every cross-model value is audited
from the binary roster and independently reconstructed score arithmetic.

No tolerance, threshold, tier, score, roster constraint or admissibility rule
is relaxed by these transformations. Randomized and exhaustive toy fixtures
must match direct integer enumeration.

## Exact CBC proof contract

Every nonconstant bound, tail tier, residual-gain, rank, ambiguity and
incidence solve uses a unique create-only evidence directory containing the
retained MPS, solution, log and, when applicable, MIP-start file. No bare PuLP
status can license a result.

The solver law is deterministic:

- PuLP 3.3.2 and CBC 2.10.3 are pinned; the CBC binary SHA-256 is pinned in the
  image and launch manifests and repeated in every solve receipt;
- one thread, elapsed-time mode;
- `randomSeed=170817` and `randomCbcSeed=170817`;
- relative and absolute gap zero;
- primal and integer tolerances both `1e-9`;
- 120 seconds for a bound stage and 600 seconds for a pricing/tie stage;
- the first nonconstant tail tier is cold with cuts off;
- each later nonconstant tail tier uses only the immediately preceding proven
  incumbent as a MIP start under the default-cut mode;
- residual gain is expressed as fixed most-significant-first four-bit objective
  chunks. Each non-forced chunk uses the immediately preceding fully proven
  incumbent as a complete audited MIP start, with cuts and preprocessing off,
  and freezes its exact optimum before the next chunk. A chunk that the exact
  aggregate bound and already frozen prefix force to zero is frozen directly
  and invokes no CBC solve. All exact `x`, threshold, residual-branch and
  `x * branch` values are initialized from the independently reconstructed
  incumbent; the MIP-start path/SHA and frozen-tail/chunk face are part of
  every solve receipt;
- canonical rank, ambiguity and each non-forced incidence solve likewise use
  only the immediately preceding fully proven complete incumbent, with cuts
  and preprocessing off;
- bound quotient and remainder solves are cold with cuts off;
- preprocessing is disabled for bound-remainder solves and every post-tail
  residual/rank/ambiguity/non-forced-incidence solve, and remains at the CBC
  default for bound quotient and tail-tier solves;
- structural-zero tail tiers, an all-zero residual objective,
  exact-bound/frozen-prefix-forced residual chunks and cardinality-forced
  incidence suffixes do not invoke CBC; other constant objectives are not
  implicitly solver-free;
  and
- a warning never triggers a retry under a different solver law.

An accepted solve requires all of the following:

- PuLP problem status and solution status both exact Optimal;
- a complete solution body whose header is exactly
  `Optimal - objective value N` for integral `N`, whose rows and variables
  match the registered model completely and uniquely. Every assignment token
  is decoded as one finite `Decimal`. The complete frozen
  renamed-to-scientific/domain manifest identifies every variable, its MPS
  category and its mathematical integer/binary domain. Every variable in this
  frozen formulation is mathematically integer-valued, including redundant
  auxiliaries written as continuous but proven integer-valued by the exact
  radix/Boolean construction. Such a token is accepted only when its absolute
  distance from the unique nearest integer is inclusively at most literal
  `Decimal('1e-11')`; it is then canonicalized once to that integer, and a
  binary must canonicalize to exactly zero or one. This evidence-decoding bound
  is 100 times smaller than the frozen `1e-9` CBC integer tolerance, may never
  be widened, and permits no other tolerance-based rounding;
- a strict-ASCII retained MPS accepted only under the pinned PuLP 3.3.2 writer
  profile: exactly one ordered `*SENSE`, `NAME MODEL`, `ROWS`, `COLUMNS`, `RHS`,
  `BOUNDS`, `ENDATA` sequence; normalized contiguous renamed rows and columns;
  one complete RHS vector with exactly one entry per constraint and none for
  `OBJ`; balanced, nonempty, per-integer-column `INTORG`/`INTEND` marker blocks;
  and unique finite integral scientific coefficients, RHS values and bounds.
  Duplicate records, extra vectors or sections, unsupported writer forms, and
  incompatible bounds fail closed. Only the pinned writer's `BV`, `LO`, `UP`,
  `FX`, `FR` and `MI` record forms are accepted; their exact COIN semantics
  include the distinction between an integer column inside markers with no
  explicit bound (default `[0,1]`) and an explicit `LO 0` integer
  (`[0,+inf]`), and permit the valid paired `MI` then `UP` form;
- an explicit complete bijective renamed-to-scientific/domain variable
  manifest whose canonical digest is bound to the scientific solve receipt,
  plus exact agreement among the MPS `*SENSE` marker, registered problem sense,
  and presence of exactly one CBC `-max` command token if and only if the
  problem is maximized;
- exact Python-integer reconstruction from the complete solution assignment of
  every variable bound, binary/integer condition, MPS row activity and
  `E`/`L`/`G` relation, and the objective. CBC's `%15.8g` printed row activities
  are redundant display receipts only and never license feasibility. Every
  scientific integer coefficient, bound, assignment, and worst-case row or
  objective activity must have absolute magnitude strictly below `2^53`, so
  the retained decimal model and CBC's executed double model cannot diverge;
- an operational decoding receipt containing every raw assignment token,
  canonical integer and signed residual, the maximum absolute residual,
  affected-variable count and raw solution SHA-256. The scientific receipt
  contains the canonical assignment digest and domain-manifest digest instead
  of the raw solution hash. Exact reconstruction proves the retained decoded
  point; because CBC prints assignment and row fields with `%15.8g`, it does not
  claim to reveal a smaller hidden in-memory CBC residual;
- exactly one log line `Result - Optimal solution found` and exactly one
  zero-error model-read receipt;
- exact agreement among log objective, solution objective and independently
  reconstructed integer objective;
- the registered command, binary, version, time/thread/seed/gap/cut/
  preprocessing options and artifact paths;
- no warning code ending in `W` from CBC/CGL/CLP/COIN;
- no stopped/limit/partial/gap-tolerance/final-infeasible/unbounded/error or
  numeric-nonfinite marker, including `nan` or `infinity`. CBC's exact
  informational phrases `Primal inf N` and `Dual inf N` describe an
  intermediate infeasibility measure, not numeric infinity; they are permitted
  only when `N` parses as one finite CBC number, the message has no warning
  code, and every final exact-optimal/body/reconstruction gate still passes;
  and
- reported wall time strictly below the registered limit.

All artifacts are re-hashed immediately before preparation or dose output can
be accepted. The evidence audit also requires create-only root containment,
globally unique artifact paths, and the exact expected solve labels, order,
count, model hashes, objective roles and no-good/input bindings. A timeout
incumbent, node/solution-limit incumbent, parenthetical gap-tolerance result,
missing/truncated/duplicated record, reused artifact path or unrelated valid
solver receipt is failure.

## Always-feasible canonical tie proof

The original protocol's no-good-then-`Infeasible` uniqueness check is replaced
because an `Infeasible` status is not a sufficiently auditable optimality
certificate in this PuLP/CBC boundary.

After all tail tiers and residual gain are frozen, freeze the canonical rank
sum; then:

1. retain the first rank-optimal roster;
2. minimize overlap with the first roster over the same frozen face;
3. because the first roster remains feasible, acceptance requires exact
   Optimal: overlap nine proves uniqueness and smaller overlap proves a tie;
4. if tied, partition ascending UTF-8 player IDs into fixed consecutive chunks
   of at most four. For a `k`-player chunk, maximize with
   most-significant-first weights `2^(k-1), ..., 2, 1` (therefore `8,4,2,1`
   when `k=4`), freeze every exact reconstructed bit in that chunk, and
   continue; this is lexicographically identical to bitwise prefer-one, while
   a suffix whose bits are forced by the nine-player cardinality invokes no
   CBC solve; and
5. independently reconstruct final integrality, roster identity, legality,
   every frozen objective, threshold bit, positive part, rank sum and complete
   no-good overlap.

No infeasible solve is used as uniqueness or incidence evidence.

## Scientific identity versus operational evidence

Temporary paths, execution names, timestamps, node counts and solve times are
operational evidence and must remain retained, but they are not part of the
canonical scientific identity. Otherwise two identical canaries in different
create-only directories would necessarily differ.

The deterministic scientific payload binds, at minimum:

- exact code commit, source-lock, image digest, parent-protocol ID/hash and
  amendment ID/hash;
- source/player/world/control/order/tag/matrix hashes;
- the full immutable prepared-reservoir scientific digest, not only its L/H
  selection digest;
- exact control book and pruning receipt;
- reservoir and active selections with `m`, `H` and queue tier, plus each
  world's `L` directly or transitively through a world-keyed immutable
  reservoir receipt included in that full prepared digest;
- bound and pricing model hashes, canonical assignment digests, objectives,
  witnesses, solver-law fields and binary identity;
- raw-selector, float64-validation and micro-DK parity/error receipts;
- every no-good list, generated roster and raw/micro matrix digest; and
- final exact-budget candidate and exact-80 ordered-book identities.

The operational payload separately binds every raw log and solution hash/path,
decoding receipt, timing, resource and execution receipt. Canonical scientific
serialization must be explicitly allowlisted; generic dataclass serialization
is not sufficient.
Two runs from the same image and source lock but different create-only evidence
roots must have identical scientific payload hashes while retaining distinct,
complete operational receipts.

## Scope and remaining launch blockers

This amendment governs the pure column/pricing and fold-dose implementation.
It does not substitute for the protocol's still-required:

- immutable source-lock and all 270 source-cell validation;
- canonical CBWU reconstruction and repair binding;
- fold-aware candidate/selected endpoints and stability module;
- 54-slate/108-cell shard runner and strict harvester;
- create-only immutable serializer and full scientific/operational manifests;
- shared-heavy-lease integration and queue release preflight;
- two-process real-path canary; or
- full clean-archive test/build and pinned image.

Until all of those pass, `uses_realized_outcomes=false`,
`production_change_licensed=false` and `historical_scoring_licensed=false`.
No local core result, synthetic fixture or simulated improvement may change the
money policy.
