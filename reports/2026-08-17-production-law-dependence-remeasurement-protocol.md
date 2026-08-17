# Exact production-law dependence remeasurement protocol

Date frozen: 2026-08-17, before reading any result from this remeasurement.

## Question and boundary

The adopted money policy explicitly serves the production-multinomial usage
law.  The earlier G0 dependence diagnostic recreated a selected fitted-
Dirichlet research law, so its numeric result cannot establish the dependence
shape of the law now used by the UI and exact-80 portfolio builder.

This diagnostic asks only whether the exact production law reproduces the two-
part premise for a future sparse pass-event-ledger prototype:

1. the simulated QB-to-WR hub is materially weaker than realized; and
2. simulated same-team high multiplicity at three or more q90 exceedances is
   materially stronger than realized.

It is a control-law diagnostic, not a lineup arm.  It reads no candidate or
lineup score, changes no roster, and cannot promote production.  A pass
licenses only implementation of one separately frozen, point-in-time sparse
pass-event-ledger prototype.  Any later simulator or exact-80 comparison needs
its own protocol and cannot inherit a retrospective promotion claim.

## Immutable production inputs

The source is the exact five-block acquisition already validated by
`20260815-atlas-current-money-transfer-v1`:

- policy `classic-k1-role12-boom40-poscal-cbwu-v4`;
- possession game mode and team factors enabled;
- blank `GAME_SIM_USAGE`, no Dirichlet K, and TD ledger disabled;
- production-multinomial opportunity allocation;
- blocks R0--R4, each containing 10,000 player worlds for every registered
  2023--2025 Week 1--18 Sunday-main replay slate; and
- the separately repaired R3/2025 Week 1 staging identity where required.

The machine transfer report, its complete 270-artifact URI/generation/SHA
grid, the CBWU-OI source report, and the repair receipts are checksum-bound.
No source is regenerated.

Before any realized outcome query, one create-only source-lock object must:

1. validate the exact production policy receipt and all 270 artifact metadata
   identities;
2. query only the R0 pre-lock player catalog fields needed for identity,
   position, team and served mean;
3. reject duplicate or missing season/week/player identities, non-finite
   served means, an incomplete 54-slate grid, or any outcome-bearing query
   token; and
4. persist the canonical catalog rows plus their deterministic SHA-256.

The outcome runner must fully validate that source-lock object and recheck all
270 GCS object metadata identities before it may issue its one player-outcome
query.  Each artifact is then downloaded by immutable URI and content SHA and
decoded; any player-universe, shape, finite-value, receipt or catalog mismatch
fails the run before a report is emitted.

## Population and estimands

The population is all R0 catalog players at QB, RB, WR or TE with served mean
projection at least 4.0 on the exact 54 registered slates.  Player eligibility
is common across all five blocks and is fixed by the locked served mean, not a
block-specific Monte Carlo mean.

The diagnostic reuses the frozen G0 definitions without alteration:

- each player's boom threshold is its simulated q90;
- multiplicity cells are same-team q90 exceedance counts at >=2, >=3 and >=4;
- directed conditional cells are QB->WR, QB->TE, QB->RB, WR->WR, RB->RB and
  TE->TE;
- the heterogeneous Poisson-binomial reference, practical bands, minimum
  support, 2,000 whole-slate bootstrap replicates and seed 1701 remain fixed;
  and
- gaps are `log(simulated / realized)`.

G0 is evaluated separately on R0--R4.  A sixth aggregate evaluation aligns the
same locked player rows and concatenates the five simulation blocks into one
50,000-world Monte Carlo sample.  The aggregate is one estimate of the same
production law; the five blocks are not described as independent historical
replications.

## Frozen premise decision

A directional block success requires the named cell to be supported, to have
classification `material-miss`, and to have the required sign:

- QB->WR: `log(simulated / realized) < 0`;
- multiplicity >=3: `log(simulated / realized) > 0`.

The sparse-ledger premise is reproduced only when all four conditions hold:

1. aggregate QB->WR is a directional material miss;
2. at least three of R0--R4 have the same QB->WR directional material miss;
3. aggregate multiplicity >=3 is a directional material miss; and
4. at least three of R0--R4 have the same >=3 directional material miss.

The >=4 cell is mandatory reporting but never substitutes for >=3 because the
earlier G0 population did not clear its frozen rare-event support minimum.
Likewise, no other favorable cell may substitute after results are visible.

Disposition is exhaustive:

- all four conditions: `production-law-shape-reproduced-ledger-prototype-licensed`;
- exactly one of the two aggregate/three-block mechanisms clears:
  `partial-production-law-shape-requires-reframe`;
- either primary aggregate cell or at least three corresponding block cells
  lack support/classifiability: `production-law-dependence-inconclusive`;
- otherwise: `production-law-shape-not-reproduced-ledger-dropped-or-reframed`.

No disposition licenses a production or UI change, an exact-80 score run, or
historical parameter selection.

## Outcome firewall and execution

Only one historical-outcome-reading experiment may be active.  Source locking,
implementation, tests and image validation are outcome-free and may proceed
in parallel.  The remeasurement outcome job must wait until the already-frozen
coherent market-state historical scorer has reached a strict terminal harvest;
it must also acquire the shared historical-outcome execution lease used by
other queued scorers before launch.

The outcome job is one create-only Cloud Run execution with zero retries.  Its
strict finisher validates the exact image digest, code commit, protocol/source
hashes, source-lock generation and SHA, task resources, complete six-report
schema, all support/classification fields, exhaustive disposition, and sole
create-only report object before interpreting the premise decision.
