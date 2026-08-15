# Independent tail-scoring review: reconciliation and execution queue

Date: 2026-08-15  
Source reviewed: `reports/2026-08-15-independent-tail-scoring-review.md`  
Status: implementation decisions and pre-outcome test order

## Decision

The review's central diagnosis is accepted: the largest measured opportunity
is candidate construction, and ATLAS is the highest-priority new construction
mechanism. It is sufficiently different from the closed noisy-objective,
Gumbel, candidate-count and selector sweeps to merit a fixed-budget test.

This does not authorize historical tuning or immediate money adoption. The
correct sequence is correctness repair, score-free falsification, one frozen
offline implementation, and then a book frozen before each 2026 lock. No
realized 2023--2025 score may choose ATLAS's world ranking, clustering,
near-optimal tolerance, interaction universe, weights or quotas.

## P0 findings and actions

### Live inactive eligibility: concern confirmed and repaired

The stored projection path adjusted/zeroed known inactive players, while the
sim-mode money path rebuilt component draws without that step. `allowed_ids`
represented salary-list membership, not active status, so it was not an
eligibility gate.

The live path now:

1. detects `O`, `OUT`, `IR`, and injury-report `Out` from the current feature
   row;
2. applies the existing historical vacated-usage redistribution when its
   inputs are available;
3. excludes every detected inactive before component prediction and
   simulation, even if redistribution inputs are unavailable; and
4. refuses a disagreement between the direct status gate and the cascade.

An end-to-end live-slate fixture includes an `O` player in the selected salary
IDs and asserts that the player is absent before simulation and cannot be
reintroduced by `allowed_ids`. Stored projection artifacts may continue to
retain inactive rows at zero for auditing; lineup construction may not.

### Effective simulation law: contradiction confirmed, policy unchanged

`ClassicProductionPolicy.engine_environment()` pins `GAME_SIM_USAGE=""` and
does not activate a Dirichlet K. `simulate.py` therefore uses the default
per-player Poisson/multinomial opportunity path. The fitted Dirichlet
`K=28.154043586960896` is a separately selected historical research law and is
also the explicitly frozen control for the current SIS receiver-copula
experiment. It is not part of
`classic-k1-role12-boom40-poscal-cbwu-v4`.

The production public identity now emits an explicit simulation-law receipt:
possession game mode, team factors enabled, production-multinomial usage,
blank `GAME_SIM_USAGE`, no Dirichlet K, and TD ledger disabled. It also emits
the complete sorted canonical engine environment and its SHA-256; the UI
renders the usage law and both CSV routes return the usage law and environment
hash as headers. Dirichlet will not be silently enabled. A separately frozen
dependence remeasurement under this exact production receipt is required
before any sparse pass-event ledger is considered.

The receipt audit exposed a second isolation defect before any strategy result:
`engine_environment(os.environ)` previously copied every ambient variable and
then overwrote only the known production keys. An unlisted research lever could
therefore survive into a money build even though it was absent from the policy
definition. The policy now starts from a narrow allowlist containing only
non-roster provenance and candidate-artifact plumbing, then constructs every
model, simulation, candidate and selector setting explicitly. The optimizer's
`MIN_LOWOWN` constraint also reads the passed policy mapping rather than global
`os.environ`. A regression test sets hostile ambient research variables and
proves that neither the receipt nor the optimizer observes them. This is a
correctness repair; it does not alter the adopted strategy values.

## Frozen execution order

Only one historical-outcome-reading experiment may be active. Score-free work
may proceed beside it.

1. Finish the repaired SIS reference, then its already frozen calibration and
   held-out dependence gate.
2. Run the already frozen exact-P generator-constraint census once the SIS
   chain releases the 32-GiB Cloud Run slot.
3. Run a score-free CBWU seed-order invariance audit.
4. Run the score-free attainable-world diagnostic.
5. Run the exact-size selector control/diagnostic.
6. If the attainable-world premise survives, implement the fixed ATLAS MVP and
   freeze its Week-1 shadow before any realized result.
7. Keep constraint-lattice exceptions, option-valued late swap, and any later
   dependence/event-ledger mechanism separate from ATLAS.

## ATLAS score-free diagnostic

Control and treatment use identical pre-lock player rows, worlds, salaries,
stack rules, locks/bans, seeds and player marginals. No actual fantasy score,
contest rank, payout or post-lock ownership is permitted.

- Control worlds: the incumbent 40 boom worlds ranked by total points across
  the whole slate.
- Treatment worlds: 40 worlds ranked by an attainable legal-lineup bound. Use
  an LP relaxation of the actual lineup formulation when practical; a
  documented legal upper-bound approximation may be used only as a cheaper
  falsification stage.
- For both sets, solve the exact legal MILP and compare attainable optimum,
  top-player/stack-core duplication, and cross-seed rank stability.
- The premise survives only if the mean exact legal optimum improves in at
  least three of five seeds and in aggregate, aggregate q25 does not decline,
  and treatment mean unique-roster, QB-stack-core and dominant-game counts are
  each at least 80% of control. These are frozen score-free falsifiers, not an
  adoption gate. This stage cannot promote or reject a money lineup using
  historical outcomes.

The ATLAS MVP is one fixed treatment:

- all non-boom families and the incumbent selector remain unchanged;
- exactly 40 boom replacements: eight structural world clusters times five
  unique lineups;
- each cluster's first lineup is its legal optimum;
- subsequent lineups must retain at least 98% of that world's positive legal
  optimum and maximize uncovered eligible pair weight, with stack-core triples
  as the only triples;
- exact prior rosters are banned; deterministic refill preserves the exact
  realized candidate count;
- eligibility uses only pre-lock feasibility, current simulated tail support,
  and native R0--R4 membership/frequency;
- one seed may not dominate a non-stack interaction weight; use a frozen
  robust aggregation across R0--R4;
- incumbent QB+2/bring-back, RB bans, salary floor and roster legality remain
  fixed in the first A/B.

Required pre-outcome receipts include player/world identity, legality,
uniqueness, exact candidate count, weighted pair/triple coverage, stack-core
coverage, player frequency, overlap, effective rank and p194/p210/p230 on each
held-out simulation block. The first historical implementation, if used for
engineering validation, is diagnostic-only; adoption evidence begins with
books frozen before 2026 kickoff.

## Exact-size books: accepted with one correction

The current greedy max-coverage selector is prefix-invariant: rerunning the
same algorithm for N=`1/3/20/40` returns the same first N as the 80-entry run.
Therefore a literal "rerun for N" is a useful parity test but cannot improve
the book.

The actionable treatment is a genuinely cardinality-aware selector, tested at
N=`1/3/20/40` against the incumbent prefix. Its objective and deterministic
tiebreak must be frozen before results; N=80 first reproduces the incumbent
through the control path. The treatment may use exact cardinality maximum
coverage or a separately specified robust individual-tail objective for N=1,
but these are distinct cells and may not be selected post hoc. Any small-book
money change remains a 2026 prospective promotion.

Entries 81--150 remain conditional on the user actually entering such a
contest. They are a marginal-coverage extension conditioned on the first 80,
not a simple larger prefix.

The first exact-N treatment is now frozen separately in
`reports/2026-08-15-exact-n-scorefree-protocol.md` (SHA-256
`4918cdf96675a2b7608c5688e80fb826b61c443e9beb6bbb210f34a5b6319c11`)
and implemented as a pure
selector. It uses robust 230 worlds for N=1/3, 210 for N=20 and 200 for N=40;
each greedy step prioritizes minimum then total marginal coverage across the
five fixed seed blocks, followed by robust individual 210/194 support and
mean. The score-free admission rule requires a strict primary-target gain in
aggregate and at least three blocks while retaining at least 90% of incumbent
194 coverage. N=80 is parity-only. This is one predeclared treatment, not a
threshold sweep; passage can license only a pre-lock 2026 shadow. A separate
create-only immutable-artifact runner is still required.

## CBWU seed-order audit

Rotate R0--R4 through all five cyclic orders while holding every book and
world block fixed. Report retained identities, quota/fill attribution,
eligible tuple coverage, selection identities and simulated world coverage.
This is score-free. Any order sensitivity requires a canonical order-proof or
an order-invariant allocation repair before ATLAS inherits CBWU inputs; it
does not license choosing the historically most favorable order.

The pure audit is now implemented. It fixes the candidate budget to canonical
R0 even when a different seed is first, rebuilds and cross-scores every cyclic
order, applies the unchanged selector, and reports candidate/selected identity
Jaccard, pair/triple coverage, source counts and simulated world coverage. It
accepts no realized-score input. Its create-only runner is also implemented
against the frozen R0--R4 artifacts and pre-lock player catalog. The SQL
explicitly excludes actual score/rank/ownership, selected membership and
payout data. Across exactly 54 slates it will label the mechanism invariant
only if all 216 noncanonical cyclic comparisons retain both candidate and
selected identities exactly; otherwise the result requires an order-proof or
order-invariant repair and cannot choose a historically favorable order.

## Accepted later mechanisms

- An eight-entry constraint-lattice exception sleeve is worth a separate
  prospective test. Cells are QB+1+bring-back, QB+2/no-bring-back,
  QB+1/no-bring-back, and one RB anti-correlation relaxation at a time. It must
  clear a frozen multi-seed admission margin and may admit zero entries.
- Stack-core by shell recombination is the ATLAS fallback if pair-augmented
  repeated MILPs are too slow or exhaust their near-optimal regions.
- Option-valued initial late-swap construction is a different mechanism from
  the closed one-time reoptimizer and remains worthwhile only after timestamp
  and nonanticipativity tests are mechanical.
- Distinct-slate and leave-one-slate-out influence reporting are added to
  future adoption decisions. Nested thresholds remain the utility summary,
  but one slate cannot be represented as independent evidence at several
  thresholds.
- Dependency/equivalence certificates will identify which prior arms require
  revalidation after a change instead of applying either blanket closure or
  blanket reruns.

## Deferred or rejected now

- No production Dirichlet change is licensed.
- No broad salary-floor or stacking relaxation is licensed.
- No further retrospective 194-line, global-correlation, temperature,
  Gumbel/noisy-MAP, or raw candidate-count sweep is warranted.
- The sparse pass-event ledger waits for dependence remeasurement under the
  exact production receipt.
- ROI/field simulation stays a separately frozen prospective layer after
  candidate construction improves and pre-lock ownership/duplication inputs
  are available.
- Coherent model/market disagreement worlds are lower priority than ATLAS but
  remain in the queue as a fixed-budget discovery family.

## Adoption rule

No idea in this review is adopted merely because the historical opportunity
gap is large. Code correctness repairs take effect after validation. New
strategy mechanisms must first pass score-free invariants, then be frozen
before 2026 locks. Promotion requires distinct-slate prospective evidence at
the high-score thresholds, with mean, downside, overlap, effective rank and
influence disclosed. A single extreme slate may justify continued shadowing;
it does not by itself change the money policy.
