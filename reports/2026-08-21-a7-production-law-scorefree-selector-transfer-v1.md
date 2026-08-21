# A7 production-law score-free selector transfer v1

Status: **FROZEN SCIENCE LAW — CONDITIONAL, UNEXECUTED**
Protocol/run ID: `20260821-a7-production-law-scorefree-selector-transfer-v1`

This is the one separate transfer test permitted only if the final A7-v2
historical chain closes with exact disposition `historical-positive-phase-s`.
No A7 result is presumed by this document.  The runner must strictly validate
the final local A7 harvest, report, and realized historical-outcome lease
closure before it constructs a BigQuery or Cloud Storage client.  A negative,
incomplete, unclosed, or noncanonical predecessor makes this transfer
unrunnable.

The scientific choices below are frozen now.  In accordance with the
real-artifact rule, runner/receipt implementation hashes are not frozen here.
One outcome-blind real-artifact smoke must pass first; a separate immutable
execution manifest must then bind the tested code/image, this protocol hash,
the smoke object, and the two complete source-query content hashes before the
full transfer may run.  Neither smoke nor source inspection may change any
scientific choice below.

## Question and scope

Does A7's already frozen clipped ladder continue to improve its own score-free
utility and pass its simultaneous-extremes realism guard when applied to the
exact current production-multinomial candidate and player-world law?

This is not a historical-score rerun.  It may read candidate identities,
candidate simulated totals, player simulated draws, tags, salaries, positions,
teams, opponents, game IDs, and point-in-time mean projections.  It must never
format or execute an actual-score, rank, ownership, payout, contest-result, or
winner query.  It acquires no historical-outcome lease.

Population is exactly the 54 Sunday-main historical slates: Weeks 1--18 of
2023, 2024, and 2025.  There is one treatment dose and one look.

## Conditional predecessor gate

Before any cloud client or job action, validate the exact A7-v2 run
`20260820-a7-select-ladder-phase-s-incumbent-v2` using its unchanged strict
finisher.  Required facts are:

- strict science replay and immutable finish ledgers validate;
- `report.json` is byte-bound by `completion.txt`;
- realized outcomes were read exactly once by A7 and its disposition is
  `historical-positive-phase-s`;
- `production_law_scorefree_transfer_licensed=true` in both the report and its
  outcome receipt;
- `prospective_shadow_licensed=false` and
  `production_change_licensed=false`;
- the exact realized lease generation has been closed with action
  `released-after-realized-outcome`.

The transfer projects only content identities and the positive license from
that evidence.  It must not copy A7 effect sizes or use them as transfer
inputs.

## Immutable production source

The source is exactly:

- URI:
  `gs://nfl-predictions-503414-raw/research/production-law-dependence-runs/20260817-production-law-dependence-source-lock-v1/source-lock.json`
- generation: `1786950155692968`
- SHA-256:
  `7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c`
- bytes: `1341911`
- policy: `classic-k1-role12-boom40-poscal-cbwu-v4`
- simulation law: production multinomial, possession game mode, team factors
  on, no finite Dirichlet K, no SIS-ASOE transport;
- panels: exact `20260815-atlas-money-worlds-r0-v1` through `r4-v1`;
- grid: 270 generation-pinned artifacts, five 10,000-world blocks for every
  registered slate.

Candidate rosters, `tag`, and `all_tags` come from the matching immutable panel
IDs in `nfl_predictions.replay_candidates_staging`.  The R3/2025 Week 1 rows
must come from `20260816-atlas-mvp-repair-r3-2025-v1`; its artifact SHA-256
must equal the source lock's original R3 artifact SHA-256 exactly.  Full legal
lineup fields come from the R0 rows in
`nfl_predictions.slate_player_features`.  The candidate roster union must
equal the source-lock catalog slate by slate.

The smoke queries the complete 54-slate candidate and player populations even
though it reconstructs only 2023 Week 1.  Its canonical query-content hashes
must be reproduced by the all-54 support census and frozen into the later
execution manifest.  Full mode must reproduce both hashes exactly before
downloading or evaluating a treatment slate.

## Arms and estimand

Each slate constructs the canonical five native books once and combines them
once with `combine_cbwu_books` in exact R0--R4 order.  Control and treatment
receive the same `CandidateBatch` object: identical candidate order,
candidate budget, player order, 50,000 player worlds, and 50,000 candidate
totals.  Candidate generation is not rerun by arm.

- Control selector:
  `select_tail_entries(..., 80, 194.0,
  env={"SELECT_LSE":"0","SELECT_LADDER":""})`.
- Treatment selector:
  `select_tail_entries(..., 80, 194.0,
  env={"SELECT_LSE":"0","SELECT_LADDER":
  "170:10,180:10,187:7,194:7,200:6,210:10"})`.
- Ladder mean weight remains zero.
- Both books must contain exactly 80 unique production-legal DK Classic
  rosters.  Direct N4 and N14 selections must equal their exact-80 prefixes.

The control order must also reproduce a call using the adopted production
policy environment, whose `SELECT_LSE` is `0` and `SELECT_LADDER` is blank.
The only selector input that differs between arms is `SELECT_LADDER`.

## Unchanged score-free gate

Import and apply the A7-v2 `scorefree_book_receipt`, `support_census`, and
`aggregate_scorefree` functions unchanged.  The transfer passes if and only if
that inherited gate passes on all 54 production-law rows:

1. treatment membership changes on at least one slate;
2. treatment aggregate clipped-ladder utility is strictly greater;
3. treatment utility is greater in at least four of five world blocks;
4. each arm has at least 100 positive-gain R3 events in aggregate and more
   than zero in every block; and
5. treatment's q99 R3 utility rate is no more than `0.01` above control,
   evaluated by A7's exact integer cross-product comparison.

No realized 187/194/200/210/220/230/240 counts, paired score test, historical
baseline, or A7 Phase-S effect enters this transfer.

## Modes, dispositions, and licenses

`real-artifact-smoke` reconstructs exactly 2023 Week 1 and publishes only
mechanical/source/selector receipts.  It does not aggregate a treatment
effect.  All licenses are literal false.

`support-census` reconstructs all 54 slates but publishes only A7's unchanged
R3 support census, source identities, and compact per-slate receipt hashes. It
must reproduce the smoke query-content hashes.  It must not call or publish
the aggregate treatment utility comparison.  Unsupported closes the transfer;
supported licenses only creation of the immutable execution freeze manifest.
All outcome, shadow, and production licenses remain literal false.

`full` reconstructs all 54 slates exactly once.  Its dispositions are:

- `production-law-scorefree-transfer-passes-shadow-licensed` when the
  unchanged A7 score-free gate passes;
- `production-law-scorefree-transfer-fails-closed` otherwise.

Before a full pass, historical-outcome access, historical scoring,
prospective shadow, production change, historical retune, and transfer retry
are all unlicensed.  A full pass changes only
`prospective_shadow_licensed=true`; every outcome, production, retune, and
automatic-deployment license remains false.  A pass does not deploy a shadow.
A failure closes this dose and corpus with no retry or tuning.

## Execution safety

- Perform the real-artifact smoke and support census before freezing
  runner/receipt hashes.
- Use a full-test immutable image and create-only result objects.
- Reuse one existing idle, unscheduled Cloud Run job by update; create no job,
  delete no job, use one task/one parallelism, and set retries to zero.
- The predecessor validation must finish locally before job inventory, update,
  or execution.
- No scheduler, historical-outcome lease, shadow deployment, or production
  mutation belongs to this protocol.
