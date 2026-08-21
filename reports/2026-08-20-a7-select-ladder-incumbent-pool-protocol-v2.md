# A7-v2 incumbent-pool clipped-ladder selector — frozen repair protocol

**Protocol ID:** `20260820-a7-select-ladder-phase-s-incumbent-v2`

**Prior failed run:** `20260820-a7-select-ladder-phase-s-incumbent-v1`

**Status:** outcome-blind repair arm; no A7-v1 retry and no scientific change

## Purpose and permitted repair

A7-v1 stopped during its first outcome-blind real-artifact smoke before a
science receipt existed. The player-source query returned SQL `NULL` for 439
`mean_projection` cells; strict query-receipt canonicalization correctly
rejected those non-finite Python values. No historical-outcome query was
formatted or executed, no historical-outcome lease was acquired, and no A7
result object exists.

A7-v2 is a fresh run, protocol, object prefix, and job claim. It is not a
retry under the v1 identity. The only scientific-source repair is this exact
player column expression:

`COALESCE(mean_projection, 0.0) AS mean_projection`

This matches the already-canonical CBWU candidate reconstruction, which maps
an absent projection to `0.0`. SQL NaN, positive infinity, negative infinity,
and every other non-finite value are not coalesced and remain fatal at query
canonicalization. Candidate construction, player draws, worlds, selector
laws, endpoints, gates, and disposition rules are unchanged.

The only transport repair is to use the registered B1 `Completed`-condition
parser truth table at both A7 polling sites: no `Completed` row is `Unknown`;
one row whose status is exactly `Unknown`, `True`, or `False` returns that
status; duplicates, missing status, and every unexpected status are
`Malformed`. This repair has no access to science or outcomes.

## Frozen population and sources

- Exactly 54 Sunday-main slates: seasons 2023, 2024, and 2025, weeks 1-18.
- The research law remains finite Dirichlet `K=28.154043586960896` plus
  Phase-S SIS-ASOE treatment `beta=0.07771181538347656`; it is not the live
  production-multinomial law.
- The five incumbent Phase-S finite-K plus SIS-ASOE panels are unchanged:
  `20260813-sis-asoe-treatment-r0-v1` through
  `20260813-sis-asoe-treatment-r4-v1`.
- Each panel contributes exactly 10,000 worlds per slate; canonical
  `R0,R1,R2,R3,R4` combination yields exactly 50,000 worlds per slate.
- Candidate admission remains unchanged `combine_cbwu_books`; the R0 native
  candidate count is the fixed budget. Candidate order, identities, totals,
  player draws, tags, seeds, and admitted pools are byte-identical between
  arms.
- The source report remains
  `reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json`,
  SHA-256
  `556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33`.
- The exact registered weekly baseline remains
  `reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1/report.json`,
  SHA-256
  `a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239`.
- The forensic player manifest remains
  `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`.

All 270 source artifacts remain generation-, SHA-256-, byte-, panel-, slate-,
row-count-, and combined-input-bound. Missing, extra, duplicate, mutable,
malformed, non-finite, or identity-misaligned source data invalidates v2.

## Frozen arms

Both arms receive the identical candidate/world matrix and an exact-80 budget.
Both must return 80 unique legal rosters. Neither inherits selector settings
from the host environment.

- Control: `select_tail_entries(T, 80, 194,
  env={"SELECT_LSE":"0","SELECT_LADDER":""})`.
- Treatment: `select_tail_entries(T, 80, 194,
  env={"SELECT_LSE":"0","SELECT_LADDER":
  "170:10,180:10,187:7,194:7,200:6,210:10"})`.

The treatment cumulative utility is exactly 10/20/27/34/40/50 at
170/180/187/194/200/210 and is clipped at 210. `mean_weight=0`; there is no
mean term. Thresholds 220/230/240 are report-only. Control keeps marginal
uncovered 194-world coverage, individual p194, then simulated mean as its tie
law and must reproduce the registered exact-80 control identities. Treatment
keeps marginal ladder gain, simulated mean, then lower candidate index.

The canonical exact-80 call is the selection call. N4 and N14 are only the
literal `[:4]` and `[:14]` prefixes. Direct audit calls at 4 and 14 must equal
those prefixes and cannot optimize or replace them.

## Outcome-blind gates

The simultaneous-extremes falsifier remains unchanged. Per player and each
10,000-world block, q99 and q99.5 use NumPy `method="higher"`; a value is
extreme only when strictly greater than its cutoff. For each positive marginal
ladder gain, count how many of the lineup's nine players are extreme.

Primary `R3` is the fraction of ladder utility attributable to at least three
strict q99 exceedances, aggregated across all 54 slates and five blocks.
Before any outcomes:

1. Exact source census and registered control reproduction pass on all slates.
2. Both books are unique, legal, exact-80, and prefix-invariant.
3. The candidate/world object is shared exactly across arms.
4. Treatment changes membership on at least one slate.
5. Treatment total ladder utility exceeds control and exceeds it in at least
   four of the five aggregated world blocks.
6. Each arm has at least 100 positive-gain R3 events in aggregate and more
   than zero in every block.
7. `R3_treatment - R3_control <= 0.01`, decided by exact integer
   cross-multiplication against `1/100`.

Failure of gates 1-6 is `invalid`. Supported failure of gate 7 is the
outcome-blind `tail-artifact-risk-phase-s` closure. Neither branch may format
or execute the outcome query. R2, R4, and q99.5 are mandatory non-gating
diagnostics.

## Historical baseline, pool conversion, and endpoints

Only a complete external freeze may authorize one historical query. The
control's 54 weekly exact-80 maxima must reproduce this exact registered
vector:

- 2023: `[173.64, 187.28, 235.60, 167.72, 173.98, 171.34, 168.16,
  180.28, 224.20, 194.72, 166.98, 162.62, 171.08, 193.28, 188.84,
  169.02, 173.06, 171.20]`
- 2024: `[170.48, 160.72, 225.28, 153.90, 185.22, 177.90, 144.20,
  166.80, 158.52, 149.72, 192.48, 179.20, 146.94, 218.48, 193.72,
  189.46, 207.26, 188.54]`
- 2025: `[136.18, 217.20, 168.14, 156.46, 163.86, 170.74, 158.54,
  156.98, 189.10, 167.50, 160.42, 217.34, 151.76, 148.64, 188.80,
  163.62, 161.34, 148.96]`

It must also reproduce mean `176.06296296296293` and threshold counts
17/8/7/6/3/1/0 at 187/194/200/210/220/230/240. Aggregate agreement cannot
rescue a vector mismatch.

For each slate and arm, retain `C`, the maximum score in the shared admitted
candidate pool; `S`, the maximum score in the selected book; and `C-S`.
Because the incumbent pool is identical, `C` must be identical between arms.
The native outcome rows and admitted-candidate aligned score vector must be
complete, finite, retained, hashed, and independently replayable.

The sole realized gating endpoint is paired weekly `S80`. Its two
co-primaries are an intersection:

1. mean paired delta is positive and its deterministic two-sided sign-flip
   p-value is at most 0.05; and
2. signed-rank direction is favorable and its deterministic two-sided
   sign-flip p-value is at most 0.05.

Use exhaustive sign flips only with at most 20 nonzero deltas; otherwise use
exactly 200,000 NumPy `default_rng(20260818)` draws with the registered add-one
correction. The 194 and 200 treatment-minus-control clear-count changes must
each be at least -1 slate. The 187/194/200/210/220/230/240 grid, medians,
direction counts, exact McNemar cells, season directions, all leave-one-slate
and leave-one-season values, and the exactly 10,000-draw season-stratified
bootstrap using `default_rng(20260820)` and linear 0.025/0.975 quantiles remain
mandatory reports. N4 and N14 remain non-gating and cannot rescue or veto S80.

Dispositions remain, in order: `invalid`, `tail-artifact-risk-phase-s`,
`rejected-phase-s-dose`, `historical-null-or-inconclusive-phase-s`, and
`historical-positive-phase-s`. A positive result can license only one separate
frozen outcome-blind production-law score-free selector-transfer test.
`prospective_shadow_licensed=false` and `production_change_licensed=false`
remain literal for every v2 disposition.

## V1 closure and v2 ownership

V1 is permanently closed and remains identifiable by its original protocol,
run ID, object prefix, source commit, image, build, reused-job claim, smoke
execution, and failure report. V2 must never create, overwrite, delete, or
reinterpret any v1 science, freeze, result, or claim object.

The A3 logical release continues to name v1, not v2. Before a v2 job claim may
exist, the separate outcome-blind v1 failed-preflight logical release must:

- be validated under its isolated close-only protocol;
- name v1 as `run_id` and this exact v2 ID as `next_run_id`;
- bind the exact v1 source/build/image, durable job claim, prepared and launch
  ledgers, first poll, strict failed terminal execution, singleton v1 prefix,
  and definitive historical-outcome lease absence;
- state `historical_look_consumed=false`, no realized-outcome access, and all
  retry, scientific-transfer, shadow, and production licenses false; and
- exist create-only at
  `gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/preflight/failed-preflight-logical-release.json`,
  with its generation-pinned object receipt validated against the remote body.

The fresh v2 job claim must bind the exact v1 release-body SHA-256 and its full
generation-pinned object identity. Every later v2 preflight, freeze, launch,
and harvest inherits that binding through the immutable claim. Absence,
mutation, body/object mismatch, or a release naming any other successor blocks
v2 before any reused-job update or execution.

## Execution governance

- V2 uses only its own run-derived local directories and GCS prefix.
- The reused research job is updated only after the v1 release and fresh v2
  create-only claim validate. No job or scheduler is created.
- Smoke reconstructs the complete 2023 Week 1 score-free path. Support repeats
  it for all 54 slates. Smoke must be strictly harvested before support;
  support before freeze; freeze before lease; lease before the single outcome
  execution.
- Every update replaces the complete environment and clears volumes, mounts,
  secrets, workdir, and startup-probe state. Exact image, args, resources,
  service account, UID/generation/spec chain, and zero retries are mandatory.
- The v2 preflight inventory is exactly claim; claim+smoke+smoke-terminal;
  claim+smoke+smoke-terminal+support+support-terminal; then those objects plus
  the freeze manifest. Extras or missing objects fail closed.
- Cloud JSON is retained only after successful capture and canonicalized
  strictly. Polling uses the exact Completed truth table defined above.
- The approved build source is the exact direct GitHub commit with the exact
  committed Cloud Build contract and immutable image digest.
- Strict harvest requires terminal success, exact execution and object
  inventories, generation-pinned source/query replay, in-image and local
  selector/science replay, complete native outcome reconstruction, and exact
  frozen disposition recomputation before lease closure.
- Prelaunch or terminal failure may abandon only its own generation-bound
  lease. Ambiguous execution or harvest state holds the lease for review.
- There is one v2 historical look. No result-dependent repair, alternative
  ladder, dose sweep, pool change, rule change, or hidden retry is licensed.
