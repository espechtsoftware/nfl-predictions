# Reconciliation of ATLAS approach and code review

Date: 2026-08-15 CDT. This reconciliation was written while the original
score-free ATLAS execution was still running and before its result was
harvested. No realized player, candidate or selected-lineup outcome was
queried.

## Summary disposition

The review is technically strong and changes the interpretation and next
stage materially. The active execution remains valid, immutable and useful,
but it is one simulator-law cell rather than a production-transfer verdict.

| Finding | Disposition |
|---|---|
| Phase S artifacts differ from the money simulation law | Confirmed; add an exact current-money-law score-free transfer cell before claiming production relevance. |
| Raw diversity can veto Part A ranking | Confirmed; preserve the official all-six result, but interpret the three quality and three raw-diversity conditions separately. Match diversity explicitly in the next stage. |
| Forty attempts may yield fewer than 40 unique boom additions | Confirmed in `backtest/engine.py`; freeze realized post-dedup opportunity-count parity for the MVP. |
| Use CBWU-OI for clean attribution | Accepted; P2-versus-P1 is the ATLAS contrast and P2-versus-P0 is composite context. |
| Novelty must be conditional on the full non-boom pool | Accepted as a mandatory score-free receipt. |
| World/MILP ties need canonicalization | Accepted for the transfer/MVP version; audit incumbent cutoff ties and use lexicographic multi-pass optimization. |
| Position-only proxy may be too loose | Accepted as a boundary. Inspect score-free slack before invoking one frozen salary-aware bound; do not treat a proxy failure as proof against all attainable ranking. |
| Harvester trusts self-reported identity too much | Confirmed; independently bind the current result to execution-owned metadata and exact source/diagnostic key sets before retention. |
| Pair objective and 98% treatment details | Accepted for the Part-B/C protocol, with leave-one-seed-out weights, capped novelty, class normalization, fixed refill and absolute-regret reporting. |

## Confirmed source-law boundary

The active runner hard-codes
`20260813-sis-asoe-treatment-r0-v1` through `r4-v1`. Phase R selected finite
Dirichlet `K=28.154043586960896`, and Phase S selected SIS-ASOE treatment.
Those worlds deliberately alter joint opportunity concentration/rank order.

The adopted money receipt instead pins `GAME_SIM_USAGE=""`, no Dirichlet K,
`usage_allocation="production-multinomial"`, and no Phase S ASOE branch.
Because ATLAS ranks joint worlds, this difference can change both attainable
quality and structural concentration. The original brief has been corrected
to name the source law explicitly.

The active run's official six-condition disposition is preserved. Its valid
claims are scoped as follows:

- a pass supports the position-aware proxy under finite-K + ASOE Phase S;
- a fail rejects that proxy only under the same law;
- neither result establishes current-money transfer; and
- neither result alone adopts, rejects or scores a money book.

## Pre-result interpretation of the six conditions

The official frozen disposition remains `all(six conditions)`. No result cell
is removed or reweighted after launch. For mechanism diagnosis, report two
subsets alongside it:

- **Part-A quality:** aggregate mean exact optimum improves; at least three of
  five seed means improve; aggregate q25 is non-worse.
- **Raw top-40 structure:** unique roster, QB-stack-core and dominant-game
  ratios each average at least 80% of control.

If quality passes while only raw structure fails, record
`ranking-quality-passes/raw-diversity-fails`; this licenses a matched-
diversity score-free cluster comparison, not an outcome-facing result. Part B
exists specifically to impose structure, so raw diversity cannot be treated
as proof that Part A found poor worlds. If quality fails, investigate proxy
slack and the exact-money-law transfer cell before abandoning attainable
ranking. The official all-six flag remains fully disclosed.

## Required current-money transfer cell

After the current report is strictly harvested, construct five independent
R0--R4 player-world blocks under the exact public money-policy environment:

- production possession simulator and team factors;
- production-multinomial usage allocation;
- blank `GAME_SIM_USAGE`, no `DIRICHLET_K`;
- no SIS-ASOE rank transport or finite-K research cache/schedule;
- the same active-only player/model/market/marginal policy receipt;
- the same 54 2023--2025 slates and 10,000 worlds per block; and
- no realized score, ownership, rank or payout input.

Apply the identical position-only control/treatment rankings, top-40 count,
exact production MILP constraints and Part-A quality conditions. Preserve all
structural metrics as diagnostics. The current Phase S and money-law results
must be reported next to their complete simulation-law receipts. Parameters
cannot change between laws.

This is an outcome-free transfer test, not a new historical scoring arm. A
money-law Part-A pass is required before ATLAS can be described as a
production-law shadow mechanism. Engineering work may continue after a Phase
S pass, but production relevance remains unproven until transfer passes.

## Part-B/C causal contract

The next MVP must use three explicitly labeled books:

| Book | Boom generator | Admission | Role |
|---|---|---|---|
| P0 | incumbent | canonical production CBWU | non-gating money context |
| P1 | incumbent | passed CBWU-OI | attribution control |
| P2 | ATLAS | passed CBWU-OI | ATLAS treatment |

The causal comparison is P2 versus P1. Both use the same five world blocks,
unchanged non-boom families, final selector and order-invariant admission.

For every seed/slate, first build the unchanged non-boom families and freeze
their identity set. Measure the number of unique incumbent boom candidates
actually added after global deduplication. P2 must add exactly that count—not
merely make the same number of solve attempts. Generate proposals round-robin
over the fixed eight clusters. When a 98%-eligible world cannot supply five
unique additions, refill at the same tolerance from the next qualifying world
within that cluster, then the next eligible cluster. If the frozen hierarchy
cannot match count, P2 fails mechanically; do not loosen 98%.

Required receipts include attempts, feasible solutions, duplicates, unique
post-dedup additions, exact native/final budgets, conditional new player-pair
and stack-core-triple reach, weighted coverage gained per admitted candidate,
overlap by non-boom family, absolute and percentage regret, and held-out
p194/p210/p230 on blocks not used to price an interaction.

## Determinism and diversity requirements

Before identities influence a gate:

1. audit whole-slate-total ties, especially the top-40 cutoff, against the
   actual incumbent sorting convention;
2. use one shared deterministic world-ranking helper in control and
   treatment;
3. exact-solve with two passes: maximize world score, constrain within a
   declared numerical tolerance, then minimize a stable roster-identity rank;
4. near-optimal solves use three explicit stages: 98% primary floor, maximize
   uncovered interaction value, stable identity tiebreak; and
5. prove repeated-run and player-row-permutation identity invariance.

The matched-cluster stage applies the same frozen eight-cluster rule to both
control and treatment, then compares exact legal quality at that structural
requirement. Report capped preservation
`mean(min(treatment/control, 1))`, q10/median/min ratios, entropy/Simpson
effective counts, pairwise roster overlap, top-player Jaccard and the full
maximum-game signature including ties. Uncapped mean ratios remain visible
but cannot hide concentrated collapse.

## Proxy slack and one bounded fallback

The current position-only value is a valid upper bound but can be loose.
Before interpreting a quality failure, report within the exact-solved union:
proxy-minus-exact slack, proxy/exact rank correlation, exact-quality
win/tie/loss counts, top-8/20/40 overlap and cutoff tie counts.

If the position-only proxy fails Part-A quality under the money law, one
outcome-free salary-Lagrangian upper bound may be frozen before execution. It
must include lambda=0, use a fixed nonnegative grid derived without realized
scores, retain the same exact legal comparator and report bound slack. It is a
new proxy version, not a post-hoc reinterpretation of v1.

Near-optimal interaction enumeration on incumbent worlds remains separable
even if both attainable-ranking proxies fail; that would test Part C without
claiming Part A.

## Harvester repair

The current strict finisher is being strengthened before retention. In
addition to its existing report checks, it will:

- find the `Completed` condition by type and require terminal success,
  `succeededCount=1`, `failedCount=0` and completion time;
- bind the execution-owned image, command/args, environment, resources,
  task/retry/timeout and service account to the local manifest;
- persist and hash the execution JSON;
- require 270 unique source and diagnostic keys with identical key sets and
  exactly 54 slates per seed;
- verify proxy/world/top-count/relaxation and production-constraint receipts;
  and
- reject nonfinite aggregate metrics.

This is stricter evidence verification only. It does not modify the running
container, source population, output, diagnostic or frozen gate.

## Consequence

ATLAS remains high priority. The next decision sequence is now:

1. strictly harvest the immutable Phase S cell;
2. disclose official all-six, Part-A quality and raw-diversity dispositions;
3. run the unchanged outcome-free transfer cell under the exact money law;
4. if current-law quality survives, build the deterministic matched-budget
   P0/P1/P2 score-free MVP; and
5. freeze books before 2026 locks for any realized C/S evidence.

No production change is licensed by this review or the running diagnostic.
