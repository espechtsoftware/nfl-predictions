# A7 incumbent-pool clipped-ladder selector — freeze candidate 2026-08-20

**Protocol ID:** `20260820-a7-select-ladder-phase-s-incumbent-v1`

**Evidence class:** one-shot historical selector-mechanism test under the
Phase-S finite-K plus SIS-ASOE research law, preceded by an outcome-blind
real-artifact smoke and full score-free support census

**Production status:** default off; no money policy, UI, scheduler,
prospective shadow, or production deployment is licensed

**Freeze model:** these protocol bytes do not change status after a preflight.
Once a smoke or support census cites their SHA-256, they are immutable. An
external, create-only operator-approval/freeze manifest must bind these exact
unchanged bytes, the passing smoke and compact support receipt, and the exact
code and source identities before the historical runner may access outcomes.
Any protocol, selector, science-module, runner, or direct scientific-dependency
repair creates a new protocol ID and requires new outcome-blind preflights and
a new external manifest. A proof-transport-only launcher/watcher/finisher
repair may instead use the standing explicit `<NAME>_REPAIR_SHA256` seam only
when the override equals the exact current file hash, is independently
reviewed and receipt-bound, and changes no scientific/input bytes or outcome
access. It never repairs a scientific receipt or result.

## Decision, law, and scope

The causal question is deliberately law-specific: with incumbent candidates
and simulated worlds held byte-identical, does a clipped multi-threshold
utility select a better exact-80 weekly book than single-line 194 coverage
under the **Phase-S finite-K plus SIS-ASOE research law**?

The source law is finite Dirichlet `K=28.154043586960896` plus the Phase-S
SIS-ASOE treatment with `beta=0.07771181538347656`. It is not the live
production-multinomial simulation law. The population, selector dose, and any
result are therefore Phase-S research evidence only.

This is one historical look. There is no alternate ladder, weight sweep,
post-result dose, boom-deep pool, construction-rule change, simulation-law
change, mean term, or cardinality-specific optimizer in this arm. A positive
result licenses only a separately frozen, outcome-blind **production-law
score-free selector-transfer test**. It never licenses an unseen-2026 shadow,
prospective outcome collection, money-policy change, or production change.
A null or rejection closes only this exact Phase-S selector dose; it does not
close the selector under the production law.

## Frozen population and source receipts

- Population: exactly 54 Sunday-main slates, seasons 2023-2025, weeks 1-18.
- Candidate/world source: the five canonical Phase-S finite-K plus SIS-ASOE
  panels `20260813-sis-asoe-treatment-r0-v1` through
  `20260813-sis-asoe-treatment-r4-v1`, exactly 10,000 worlds per block and
  50,000 combined worlds per slate.
- Candidate admission: unchanged `combine_cbwu_books` in canonical order
  `R0,R1,R2,R3,R4`; the R0 native candidate count is the fixed budget.
- Source report: the passed score-free CBWU order-invariant report
  `reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json`,
  SHA-256
  `556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33`.
  Every control ordered exact-80 identity must reproduce its registered
  per-slate identity before any outcome query.
- Historical baseline receipt:
  `reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1/report.json`,
  committed result SHA-256
  `a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239`.
- Player-catalog lock: forensic manifest
  `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`.
- Context-only baseline registry: `reports/current-baseline.json`; its exact
  SHA-256 is bound by the external freeze manifest and cannot substitute for
  the weekly vector below.

The smoke, support census, external freeze manifest, full runner, and finisher
must bind all 270 source objects by URI, generation, SHA-256, byte count,
panel, season, week, candidate row count, and combined-input hash. They must
also bind the source-report bytes. An absent, extra, duplicated, malformed,
mutable, non-finite, or identity-misaligned source invalidates the arm.

## Frozen arms and utility

Both arms receive the same finite candidate matrix `T`, candidate order,
50,000 worlds, exact-80 budget, and legal rosters. Both receive an explicit
environment; neither inherits host process levers.

- **Control:** `select_tail_entries(T, 80, 194,
  env={"SELECT_LSE":"0","SELECT_LADDER":""})`.
- **Treatment:** `select_tail_entries(T, 80, 194,
  env={"SELECT_LSE":"0","SELECT_LADDER":
  "170:10,180:10,187:7,194:7,200:6,210:10"})`.

The treatment cumulative utility is exactly 10/20/27/34/40/50 at
170/180/187/194/200/210. Utility is clipped at 210. There is **no mean term**.
Scores at 220/230/240 are report-only and cannot affect membership. The
control retains its existing marginal uncovered-world count, individual p194,
then simulated-mean keys and must reproduce its registered order exactly. The
treatment uses marginal ladder gain, then simulated mean, then lower candidate
index. No shared or newly invented tie law is inferred across the two arms.

The runner persists the exact ordered 80 indices and identities, explicit
selection environment, candidate-source tags, per-step marginal-gain trace,
simulated utility totals by world block, and arm overlap. N=4 and N=14 are the
literal first four and first 14 identities of that exact-80 order. Audit-only
direct N=4/N=14 calls must reproduce those prefixes, but their outputs cannot
replace or optimize the registered prefixes.

## Outcome-blind simultaneous-extremes falsifier

This falsifier uses only the same simulated, pre-lock Phase-S worlds. For each
slate, block, and player, calculate empirical q99 and q99.5 over that player's
10,000 block draws with NumPy `method="higher"`. A draw is extreme only when
it is **strictly greater than** that player's own within-block cutoff. A draw
equal to the cutoff is not extreme. A constant or zero-variance player series
is never extreme at either quantile. Non-finite inputs invalidate the arm.

For ordered lineup addition `j` and world `w`, calculate the marginal frozen
ladder gain

`g(j,w) = u(max(previous_book_max(w), score(j,w)))
          - u(previous_book_max(w))`.

For q in {q99, q99.5}, `k_q(j,w)` is the number of the lineup's nine players
whose draw is strictly above their own cutoff. Attribute each `g(j,w) > 0` to
exactly one `k=0..9` cell. Persist exact event counts and exact integer-weight
gain numerators and denominators; derive fractions only from those counts.

The primary realism statistic is aggregated across all 54 slates and all five
blocks within each arm:

`R3 = sum(g * 1[k_q99 >= 3]) / sum(g)`.

Support is frozen independently of the observed R3 difference. A **positive-
gain R3 event** is one `(slate, block, ordered addition, world)` cell with
`g > 0` and `k_q99 >= 3`. Each arm must have:

- at least 100 positive-gain R3 events in aggregate; and
- strictly more than zero such events in every one of R0, R1, R2, R3, and R4
  after aggregating slates within that block.

If either arm lacks that support, the arm is `invalid` before outcomes and no
scientific conclusion is permitted. The exact negative support receipt and
strict terminal metadata are still published create-only as the durable
closure; no freeze manifest is created. If both arms are supported but
`R3_treatment - R3_control > 0.01` absolute, the frozen, outcome-blind
disposition is `tail-artifact-risk-phase-s`; the hypothesis closes without an
outcome query. Only a supported difference `<= 0.01` may proceed. The inclusive
boundary must be decided by exact integer cross-multiplication of the stored
utility numerators and denominators against rational `1/100`, never by binary
floating-point comparison. R2, R4, and q99.5 analogues are mandatory
non-gating score-free diagnostics. A7 does not
require selector-resampling, winner-overlap, or never-realized-player
diagnostics.

## Mechanical and score-free eligibility

Before the external freeze manifest can authorize outcomes, require all of:

1. Exact source census, immutable receipts, and control identity reproduction
   pass on all 54 slates.
2. Both ordered books contain exactly 80 unique, production-legal rosters, and
   the N=4/N=14 report prefixes equal the literal exact-80 prefixes.
3. Candidate identities, candidate totals, player draws, candidate order,
   budget, and seeds are one shared outcome-blind object across arms.
4. Treatment changes membership on at least one slate.
5. Aggregate treatment frozen-ladder utility is strictly greater than control,
   and treatment utility is greater in at least four of the five aggregated
   world blocks.
6. Both arms meet the registered positive-gain R3 support floor.
7. The supported R3 difference is at most `+0.01` absolute.

A failure of conditions 1-6 is `invalid` and yields no scientific result. A
supported failure of condition 7 is the outcome-blind
`tail-artifact-risk-phase-s` closure. Neither branch may access outcomes.

## Historical outcome source and exact baseline vector

Only an exact external freeze manifest and all preceding eligibility gates may
authorize the historical runner to query `actual_score` for registered
candidate keys. The runner must require one finite score per
`(panel_run_id, season, week, cand_ix)`, exact roster/key parity with the
outcome-blind source, and identical scores for duplicate roster identities
within a slate.

The control is the **54-slate Phase-S CBWU historical selector baseline**, not
a replay of the production-multinomial simulator. Before any treatment summary,
the control weekly exact-80 maxima must equal this exact W1-W18 vector:

- 2023: `[173.64, 187.28, 235.60, 167.72, 173.98, 171.34, 168.16,
  180.28, 224.20, 194.72, 166.98, 162.62, 171.08, 193.28, 188.84,
  169.02, 173.06, 171.20]`
- 2024: `[170.48, 160.72, 225.28, 153.90, 185.22, 177.90, 144.20,
  166.80, 158.52, 149.72, 192.48, 179.20, 146.94, 218.48, 193.72,
  189.46, 207.26, 188.54]`
- 2025: `[136.18, 217.20, 168.14, 156.46, 163.86, 170.74, 158.54,
  156.98, 189.10, 167.50, 160.42, 217.34, 151.76, 148.64, 188.80,
  163.62, 161.34, 148.96]`

The vector must also reproduce mean `176.06296296296293` and the counts
17/8/7/6/3/1/0 at 187/194/200/210/220/230/240. Aggregate agreement cannot
rescue a vector mismatch.

The separate 53-slate ATLAS reconstruction—production-multinomial comparator,
mean 178.57 and grid 16/9/7/2/1/0/0—is contextual evidence for the arms built
on it. It is not A7's control, and its denominator must never be mixed into A7.

## Registered C-to-S conversion

After the baseline vector passes, calculate for each slate and arm:

- `C`: the maximum realized score among the shared admitted candidate pool;
- `S`: the maximum realized score among the arm's selected exact-80 book; and
- `C_minus_S = C - S`.

The candidate pool is identical, so C must be byte-identical across arms.
Persist the 54 weekly C, S, and C-minus-S vectors and their means. Report the
treatment-minus-control change in S and in C-minus-S; do not call selection
improved merely because the common C is high. C-to-S is a mandatory diagnostic,
not a separate adoption gate.

For every realized slate, retain the complete finite native actual-query row
key-and-score vector in the exact registered SQL order
`(panel_run_id, season, week, cand_ix)` (with roster identity as the
fail-closed uniqueness tie),
plus its schema/row-count/content hash. Independently derive and retain the
finite admitted-candidate actual-score vector aligned exactly to the canonical
shared candidate-identity order; every admitted value must be reconstructed
from the complete native vector. Derive C from the admitted vector, and require
selected-arm scores to equal their aligned admitted values. Without querying
outcomes again, the finisher must reconstruct and hash the complete native
outcome receipt, derive the admitted vector from independently reloaded
score-free source rows, and recompute every C, S, C-S, and aggregate value. A
scalar C or admitted-only vector that cannot reproduce the full native query is
invalid.

## Frozen endpoints

### Sole gating endpoint: S80

The sole realized gating estimand is the maximum of each aligned exact-80 book,
`S80`. The two co-primary tests are an intersection:

1. mean paired delta strictly greater than zero with the deterministic
   two-sided paired sign-flip p-value for the mean `<= 0.05`; and
2. favorable signed-rank direction with the deterministic two-sided paired
   sign-flip p-value for that statistic `<= 0.05`.

Both p-values use the standing `paired_weekly_max_report` law: exact exhaustive
enumeration only when the number of nonzero paired deltas is at most 20, and
otherwise exactly 200,000 Monte Carlo sign draws from NumPy
`default_rng(20260818)`, with the registered add-one correction. This method,
resample count, seed, exact-enumeration cutoff, and correction are frozen; the
word `exact` below applies to McNemar's finite binomial calculation, not to the
normally Monte Carlo A7 sign-flip p-values.

Both co-primaries must pass. The two realized non-inferiority guards must also
pass: treatment-minus-control clear-count change must be at least `-1` slate at
194 and at least `-1` slate at 200, over the same 54 slates.

The full 187/194/200/210/220/230/240 grid, median, better/worse/tied counts,
exact McNemar cells, season directions, deterministic bootstrap interval, and
all 54 aligned leave-one-slate plus all three leave-one-season influence values
are mandatory reports. The bootstrap is exactly 10,000 season-stratified
within-season resamples from NumPy `default_rng(20260820)`; its 95% interval is
the NumPy linear 0.025/0.975 quantile pair. Sparse tail counts are not separate
pass gates.

### Non-gating N4 and N14 secondaries

Score the literal `[:4]` and `[:14]` prefixes of each canonical exact-80 order
and report their weekly maxima, paired summaries, and threshold grids. N4 and
N14 can never rescue, veto, reweight, or change the S80 disposition. They are
diagnostics of current first-N slicing and license no exact-N policy.

## Frozen dispositions and licenses

Disposition precedence is mechanical validity, score-free support, supported
realism, and then the one-shot historical endpoints:

1. **`invalid`** — a source, identity, legality, receipt, utility-mechanism,
   support, execution, or exact-baseline condition fails. No interpretation;
   no repair using outcomes from the failed attempt.
2. **`tail-artifact-risk-phase-s`** — mechanics and the registered support
   floor pass, but the outcome-blind R3 difference is strictly greater than
   `+0.01`. Close this Phase-S ladder dose before outcomes.
3. **`rejected-phase-s-dose`** — the historical run is valid, but mean S80
   paired direction is negative or either 194/200 non-inferiority guard is
   below `-1`. Close only this Phase-S dose.
4. **`historical-null-or-inconclusive-phase-s`** — all pre-outcome gates pass,
   the rejection branch does not apply, but the co-primary intersection does
   not pass. Close only this Phase-S dose; no rung or weight sweep on this
   corpus.
5. **`historical-positive-phase-s`** — all pre-outcome gates, both S80
   co-primaries, and both non-inferiority guards pass. License only one
   separately frozen, outcome-blind production-multinomial-law score-free
   selector-transfer test. `prospective_shadow_licensed=false` and
   `production_change_licensed=false` remain literal.

N4/N14 never alter these branches. A positive prefix with S80 failure creates
no license; a declining prefix with S80 success is reported without vetoing the
Phase-S scientific result. Boom-deep supply remains closed by its own frozen
disposition; A7 does not reopen it. Any later simulation-law change requires a
new score-free protocol and creates no transport from this result.

## External operator approval and freeze manifest

The smoke and support census run against these unchanged candidate bytes.
Neither receipt edits, promotes, or freezes this file. The compact support
receipt may expose only the preregistered event counts and support pass/fail;
it hash-binds, but does not reveal, arm utilities, identities, marginal traces,
or R3 effects. If and only if the smoke and support floor pass, the operator
may create one external approval/freeze manifest. After that manifest is
loaded and revalidated, the full runner reconstructs the hidden score-free
rows and evaluates nonvacuity, utility improvement, four-of-five block
improvement, and the exact R3 non-inferiority gate before it can format or
execute the outcome query. The manifest freezes this law and the hidden input
receipts; it does not assert that the still-unread arm-effect gates passed. The
manifest must bind:

- this exact protocol URI and SHA-256;
- exact git commit/archive SHA, immutable image digest, and SHA-256 for the A7
  selector, science module, paired-statistics law, candidate combiner,
  artifact decoder, source-preflight/query helpers, legality helper, runner,
  historical-outcome lease tool, Cloud Build recipe, freeze builder, launcher,
  watcher, and finisher;
- the source report and every source object's URI, generation, SHA-256, bytes,
  panel, slate, and row count, plus canonical hashes of the complete registered
  candidate-source and player-source query rows;
- the real-artifact smoke science receipt and its strict terminal receipt,
  each by URI, generation, metageneration, SHA-256, and bytes;
- the compact support science receipt and its strict terminal receipt, each by
  URI, generation, metageneration, SHA-256, and bytes;
- the exact create-only A7 job-claim object and phase inventory hashes; and
- literal operator approvals, each `true`, for (a) the exact ladder and no-mean
  utility, (b) the positive-gain R3 support floor and `+0.01` realism margin,
  (c) the exact S80 co-primary intersection, and (d) the `-1`-slate 194/200
  non-inferiority margins. The manifest must also acknowledge S80 as the sole
  gate and N4/N14 as non-gating.

No dynamic final protocol, code, image, receipt, or source SHA is embedded here;
those final identities belong in the external manifest. The historical runner
and launcher must fail closed unless that manifest exists create-only and every
bound byte/hash/receipt matches exactly. A manifest mismatch or changed
candidate byte is `invalid`, not repair authority.

## Execution governance

- One historical-outcome arm at a time. A3 must be strict-terminal, harvested,
  dispositioned through its preregistered read, and logically released before
  A7 may update or execute the reused Cloud Run job, including for an
  outcome-blind preflight. A7 must bind a separate create-once A3 lane-release
  receipt that explicitly names A7 as the next owner; A3's strict-harvest
  completion alone is insufficient. For the completed A3 run only, its result
  bodies were opened before the newer strict finisher published its ledgers.
  A7 therefore requires the exact logical-release-v2 recovery receipt defined
  by `reports/2026-08-20-a3-post-open-forensic-closure-protocol.md`: it must
  disclose `strict_harvest_completed_before_read=false`, bind byte identity to
  all 54 generation-pinned remote objects and the original result commit,
  independently reproduce the aggregate, record the negative disposition,
  prove the historical-outcome lease absent, and make all scientific-transfer,
  rerun, retest, shadow, and production licenses false. This operational
  deviation cannot affect A7's dose because A7's scientific contract commit
  `c1dcf4f2910c4f3298c83270bd228d1ec51c975c` and prior protocol SHA-256
  `e3222f94bc5f5fdc0e7c63df277a96a98e26cc497624f799252628645e10fba0`
  predate the A3 result commit. No A7 smoke, support receipt, freeze manifest,
  or historical result existed when this governance-only recovery amendment
  was made; the ladder, endpoints, gates, sources, and disposition law are
  unchanged. The legacy release-v1 shape is rejected for this handoff. B1's
  distinct job/scheduler are outside A7's allowlist and must never be touched.
- Before the first job update, create and revalidate one generation-matched,
  create-only GCS A7 job-claim object. It binds the A3 release receipt, reused
  job name/UID/generation, run/protocol/code/image identities, and literal
  false outcome/license flags. It is never deleted as an unlock. Every smoke,
  support, freeze, and historical transport receipt must consume that exact
  claim; eventual ownership transfer requires a separate durable release.
- Every reuse-only job update must replace the complete environment and clear
  inherited volumes, volume mounts, secrets, working directory, and startup
  probe state. The retained post-update description must have the exact frozen
  command, arguments, resources, service account, environment-row schema, and
  safe empty mutable-state fields before execution is permitted.
- The real-artifact smoke runs the complete source/reconstruction/selection/
  serialization path for the predeclared 2023 Week 1 cell with
  `uses_realized_outcomes=false`; the outcome-query constructor must not be
  called and actual-score SQL must not be formatted or executed.
- The full 54-slate support census uses the same outcome-blind boundary
  and writes exactly one compact create-only receipt. Before the external
  freeze, it may disclose only registered support counts and pass/fail cells;
  arm utility, R3 ratios/deltas, selected identities, marginal traces, and all
  realized scores remain undisclosed behind exact hashes.
- The manifest-bound historical runner independently reconstructs and checks
  every hidden mechanism and R3 effect gate after freeze but still before the
  outcome SQL is formatted or executed. Unsupported support is `invalid` at
  preflight; supported-but-excess R3 is the outcome-blind tail-artifact closure.
- Preflight receipts live under the protocol-ID `preflight/` prefix and bind
  the exact protocol, code, image, source objects, combined-input hashes, and
  ordered-book hashes. No outcome-bearing result object is allowed there.
- Smoke must finish and be strictly harvested before support may launch;
  support must finish and be strictly harvested before the external freeze
  manifest may be created. Each phase has a separate create-only terminal
  receipt binding the execution ID, job UID/generation, exact args/env/image/
  resources/service account, `Completed=True`, succeeded count one, zero
  failed/cancelled/retried tasks, immutable science-receipt identity, and exact
  prefix-inventory hash. The allowed transition is exactly: empty prefix;
  create-only job claim; smoke science object; smoke terminal object; support
  science object; support terminal object; freeze manifest. At every boundary
  the inventory is the cumulative exact prefix of that list, with no extras.
  Stdout or a mutable Cloud Run job description is never the sole evidence.
- Every `gcloud --format=json` response is first captured only after the
  command succeeds, then strict-parsed with duplicate, malformed, nonfinite,
  and overflow values rejected and retained as canonical compact LF JSON.
  Pretty-printer output is never hashed or interpreted as canonical evidence.
- The outcome run requires the external approval/freeze manifest before lease
  acquisition. Clean archive, immutable image digest, exact execution metadata,
  create-only output, `maxRetries=0`, and a durable historical-outcome lease
  are mandatory.
- The only approved build source is the direct Git source
  `https://github.com/espechtsoftware/nfl-predictions.git` at the exact frozen
  40-character commit. Cloud Build metadata must report that identical
  `resolvedGitSource` URL and revision, the exact committed `cloudbuild.yaml`
  step and build-level option contracts, the approved default service account
  and logs bucket, no secrets, and the one registered image. A caller-supplied
  commit substitution, local working-tree upload, trigger mutation, or
  unresolved source is invalid. Before the create-only result upload, the historical
  runner must invoke the separately hashed finisher replay inside that exact
  immutable image against the generation-pinned inputs. It retains the full
  canonical replay receipt and its SHA-256 in the result. Strict harvest must
  validate that in-image receipt and require its own independent replay to
  agree exactly; a local runtime alone cannot substitute for the image replay.
- Reuse an existing Cloud Run research job because project job quota is full.
  Do not create an A7 job or scheduler.
- Pre-launch or terminal execution failure may generation-match abandon its own
  lease; mid-run or harvest ambiguity holds the lease for operator review.
- The finisher independently requires strict terminal `True`, exact command,
  image, environment, resources, external freeze manifest, immutable result
  object generation/hash, source-query/artifact replay, selector replay, and
  complete score-free plus retained-outcome scientific revalidation before
  writing completion and releasing the lease.
- A realized closure must first publish or revalidate the deterministic,
  create-only `lease-release-intent.json` under the A7 run prefix. That object
  binds the strict completion, execution, immutable acquisition receipt, and
  exact active-lease generation. Only then may that exact generation be
  deleted. A restart must finish the same tombstone-bound closure before any
  new acquisition; an absent old generation is acceptable only when the live
  intent proves it, while a different live generation is never touched.
- A realized result carries `uses_realized_outcomes=true`,
  `production_law_scorefree_transfer_licensed` derived only from
  `historical-positive-phase-s`, `prospective_shadow_licensed=false`, and
  `production_change_licensed=false` as literals.
- A supported R3 failure writes only the outcome-blind
  `tail-artifact-risk-phase-s` closure with `uses_realized_outcomes=false`,
  no outcome receipt/vector, and all three license flags false. The same strict
  terminal/object/source/selector/score-free finisher must replay that branch
  and may then release the lease; it must never demand or infer outcome access.
