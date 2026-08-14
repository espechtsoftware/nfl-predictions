# Project handoff

This tracked file is the authoritative record for resuming development. It
must travel with the repository. Do not rely on assistant memory, an
individual workstation, unpushed commits, or cloud artifacts as the only copy
of project state.

## Handoff policy

Before pausing work, changing computers, or handing the project to another
agent or developer:

1. Update this file with the branch and commit, what changed, validation
   results, durable Cloud Build/Run IDs, unresolved risks, and the exact next
   action.
2. Commit the handoff together with the code it describes and push it whenever
   credentials and repository availability permit.
3. Keep secrets out of the repository. Record account/project identifiers and
   authentication requirements, never tokens or credential contents.
4. Treat local notes, assistant memory, and cloud logs as supporting evidence
   only. If they contain material state, summarize it here before stopping.

## Current state — 2026-08-14 14:46 CDT

### 2026-08-14 SIS run-tail exact-80 branch preregistered while images build

- In addition to GPU cache build `039902ab-0f13-4a66-b0d7-9a657444199a`,
  full-test audit build `b8a3e085-fbab-4ef4-80bd-e410eb354c3b` was submitted
  concurrently from the same clean `git archive` and full source SHA
  `23fdbba47590af3ba7594ae22bdbf2e764d86389`. It targets
  `nfl-dfs:sis-runtail-23fdbba` and may run the score-free final-served gate
  only after the write-once caches validate.
- Before either cache or a new score-free result existed, the sole conditional
  lineup branch was frozen in
  `reports/2026-08-14-sis-run-tail-exact80-addendum.md`. A valid final-served
  pass licenses one paired five-seed exact-80 experiment; both arms retain the
  finite-K incumbent and differ only by their registered cache and the exact
  strict-prior served schedule serialized by that arm's passing score-free
  report. The aggregate tail-first order is
  `240,230,220,210,200,194,187`. No ASOE/pass-tail/TD/K1 composition or
  post-result schedule/seed choice is allowed.
- Next action remains polling both builds. Launch the control/treatment GPU
  cache pair immediately after the GPU digest is available; separately retain
  the successful full-test audit digest for the final-served gate.

### 2026-08-14 TD ledger terminally invalid; SIS run-tail build released

- Cloud Run execution `td-ledger-rank-coupling-v1-d9zdr` completed cleanly in
  22m25.91s. The strict harvester produced immutable report
  `reports/td-ledger-rank-coupling-runs/20260814-td-ledger-rank-coupling-v1/report.json`
  with SHA-256
  `6342eab48c2a3b7f417f60d18a2c58111388b03a60a7917e4ad5fee3c833c0c1`.
  Disposition is `td-ledger-rank-coupling-invalid-or-inconclusive` and
  `exact80_licensed=false`; the conditional exact-80 branch expires and no TD
  lineup may be generated or scored.
- The rank mechanism itself passed its local invariants: bit-exact sorted
  player marginals, bit-exact independent repeat, finite output, maximum mean
  drift `7.11e-15`, 15,396 changed rows, 137,300,516 changed cells and exact
  frame alignment. The terminal failure was the supposedly unchanged control:
  48 G0/G1 simulated values missed the frozen `1e-12` reproduction gate, with
  deltas as large as `+5.1384`.
- The evidence points to a stale-reference/current-code mismatch. Frozen G0
  and G1 were generated from 2026-08-12 commits `ee94725` and `64e0428`; the
  2026-08-13 PIT repair `26e73c5` changed finite-Dirichlet season replay from a
  franchise-wide season allocation pool to correct `(game, team)` units. The
  terminal run used that repaired path, which materially changes dependence.
  This enters the forensic chronology but does not license a fourth TD repair.
  Full result and diagnostic deltas are in
  `reports/2026-08-14-td-ledger-rank-coupling-result.md`.
- With TD terminal, exact-commit GPU Cloud Build
  `039902ab-0f13-4a66-b0d7-9a657444199a` was submitted from a clean
  `git archive` of full SIS run-tail SHA
  `23fdbba47590af3ba7594ae22bdbf2e764d86389`, targeting
  `tabpfn-sis-rb-runtail:23fdbba`. Poll the build; on success resolve its
  immutable digest, launch the write-once control/treatment GPU cache pair,
  poll and run `scripts/cloud_finish_tabpfn_sis_rb_runtail.sh` with that full
  SHA. Do not launch the expired TD exact-80 implementation.

### 2026-08-14 conditional TD exact-80 replay lever implemented and tested

- While the upstream score-free execution remained nonterminal, the
  preregistered exact-80 treatment was implemented as the off-by-default
  `TD_LEDGER_RANK_COUPLING=1` replay lever. It independently regenerates the
  frozen `TD_LEDGER=1` rank source twice, verifies aligned rows and bit-exact
  repeatability, and then stably permutes only the incumbent final-served
  baseline draw matrix. Every treatment row must retain its exact sorted
  control multiset, float64 mean drift at most `1e-10`, finite output and at
  least one changed world cell. The separately trained role-belief candidate
  draw matrix remains common and unchanged; the addendum now explicitly
  prohibits extending the unvalidated rank treatment to it.
- The lever fails closed unless cache, finite K, possession simulation, served
  schedule, five registered seed pairs, model/generator counts and role
  features exactly match the frozen incumbent. It rejects direct TD-ledger,
  SIS ASOE, route/coverage-tail, ensemble-world and Schaake composition. Its
  identity is now present in both the effective research config and persisted
  candidate `lever_env`.
- Thirty-eight focused tests pass across the new lever, terminal score-free
  rank coupling, generation config, candidate provenance and unchanged
  default replay/seed behavior. Python compilation and whitespace validation
  also pass. No exact-80 lineup has been generated or scored, and this local
  implementation may launch only after a valid upstream score-free pass and a
  new exact-code full-test image build.
- `td-ledger-rank-coupling-v1-d9zdr` remains running. It completed the first
  six visible season-book simulations by `19:25Z` and is progressing through
  the independent repeat book. Continue polling it before any SIS job.

### 2026-08-14 Full Access restored and TD exact-80 branch preregistered

- Toggling the IDE's access selector back to Full Access restored the effective
  unrestricted filesystem/network/no-approval profile. Direct checks now pass
  for the active GCP account, Cloud Run execution descriptions and
  `git ls-remote origin refs/heads/main`; no additional IDE setting or GCP
  authentication is required.
- `td-ledger-rank-coupling-v1-d9zdr` progressed from image import to a deployed
  running execution at `2026-08-14T19:15:45Z`. Its logs show the registered
  active-label cache, prop-market path and simulator books executing. It
  remains nonterminal and is the only cloud mechanism allowed to occupy the
  queue before the SIS RB run-tail jobs.
- Before the score-free disposition was visible, the sole conditional lineup
  branch was frozen in
  `reports/2026-08-14-td-ledger-rank-coupling-exact80-addendum.md`. A valid
  score-free pass licenses one paired exact-80 experiment across the five
  already registered seed books. Both arms retain the finite-K incumbent,
  active cache, served schedules, 12 role/40 boom generator, 194 coverage and
  all 54 slates; the only treatment difference is the exact final-served
  TD-ledger rank permutation. The aggregate decision is tail-first at
  `240,230,220,210,200,194,187`, with whole-slate clustered uncertainty and no
  composition with SIS or another dependence mechanism.
- Next concrete action: continue polling and harvest
  `td-ledger-rank-coupling-v1-d9zdr`. If it passes, implement and full-test the
  off-by-default replay lever, pin an immutable image/code identity and run the
  preregistered paired exact-80 comparison. If it fails or is invalid, expire
  that branch and immediately build/launch the exact `23fdbba` SIS run-tail
  cache pair.

### 2026-08-14 restart checkpoint: SIS RB run-tail path implementation complete locally

- The IDE/restarted agent process retained branch `main` at pushed commit
  `51fb0f3`; Full Access restored GCP and Git network access without new
  authentication. Terminal TD-ledger exact-code Cloud Build
  `ac8758bc-712b-4cda-a9fc-fc6e1252bdc2` succeeded and produced immutable
  digest
  `sha256:b9c0480571b2941b6074d78cb577762d9c1658de2dbb70490169be7a8cb0ce88`.
  The single frozen score-free rank-coupling execution is
  `td-ledger-rank-coupling-v1-d9zdr`; it was launched from full code SHA
  `934d2c3d0e55312502da83964a6f16e806b8d231` and was importing its image at
  this checkpoint. Poll and harvest this execution before launching the queued
  SIS arm.
- The adaptive opponent run-defense Boom%/Bust% cache and score-free served-tail
  path is fully implemented and pushed on `main` as commit `23fdbba`:
  strict-prior four-game volume-weighted features, an exclusive GPU generator
  branch, write-once control/treatment cache launch and validation, final-served
  active-RB q95/q99 normalized-pinball evaluation, chunk/meta identity-checked
  transport, CLI/replay research-table plumbing, and frozen Cloud Run launch and
  harvest scripts. It keeps the protocol's finite Dirichlet
  `K=28.154043586960896`, 10,000 worlds, 45/55 blend, earlier-fold-only scale
  fitting, exact mean invariant, `adaptive_retrospective=true` label, and
  terminal-ledger queue ordering.
- Cache validation now binds report, BigQuery row, feature-contract and full
  requested code identities; it also requires exact control reproduction.
  Source construction fails closed on incomplete source-run/hash identities,
  null/non-finite/negative attempt inputs, invalid rates, duplicate keys,
  current/future weeks and row-changing joins. The final report transport pins
  both compressed and uncompressed lengths/hashes and uses zero-based complete
  chunk framing.
- Shell syntax, Python compilation, whitespace validation and 28 focused SIS
  run-tail/RB-defense/pass-tail tests pass. Five relevant replay tests also
  pass. The unrelated role-belief model-training replay test exceeded a
  45-second local timeout after starting; this is not a failing assertion and
  the new run-tail allowlist is directly covered by the focused suite.
- Uncommitted final-forensic diagnostic/corpus changes listed below remain
  intentionally separate and were not bundled with the SIS commit. Next action
  is to poll and harvest `td-ledger-rank-coupling-v1-d9zdr`; after its terminal
  disposition, build the exact `23fdbba` SIS GPU image and launch/harvest the
  cache pair and score-free final-served gate in frozen order.

### 2026-08-14 pre-forensic exhaustion review reopens two bounded gates

- On `main` from parent `3ded0dc`, the amended
  `reports/2026-08-14-pre-forensic-exhaustion-review.md` was checked against
  the frozen TD-ledger, SIS RB, SIS pass-tail, G0 and G1 evidence. No new lineup
  outcome was queried. The final forensic freeze is withheld and the empty
  `nfl_forensic_review` dataset remains empty.
- The review is correct that TD-ledger v1/v2 were invalidated mechanically,
  not scientifically adjudicated. Both runs passed the substantive score-free
  gates; v1 failed exact marginal identity and v2 changed the shared incumbent
  numeric path enough to miss the frozen `1e-12` control-reproduction
  tolerance. The predeclared terminal remedy is now frozen in
  `reports/2026-08-14-td-ledger-rank-coupling-protocol.md` and implemented by
  `nfl-dfs td-ledger-rank-coupling`: stable TD-ledger world ranks permute each
  unchanged incumbent marginal, with bit-exact sorted marginals, repeated-rank
  determinism, frozen G0/G1 control reproduction and the original seven
  scientific gates. A valid pass licenses one separately frozen exact-80
  comparison; failure or invalidity closes the mechanism with no fourth repair.
- The amended SIS recommendation is accepted with an evidence qualifier in
  `reports/2026-08-14-pre-forensic-exhaustion-reconciliation.md`. SIS tail data
  are not generally untested: the pass-defense Boom%/Bust%/pressure arm passed
  and improved the five-seed exact-80 high-score grid. The open candidate is
  specifically opponent run-defense Boom%/Bust% for RBs. Because the earlier
  RB Points-Saved protocol prohibited appending Boom/Bust after its result, any
  new arm must first pass a formal outcome-blind support/redundancy audit and
  must be frozen/labeled `adaptive_retrospective=true`; it queues behind the
  ledger rather than being presented as fresh confirmatory evidence.
- Odds API alternate team/game-total ladders and volume markets, SIS Receiving
  and bounded player-grain acquisition remain open prospective work. Raw
  ingestion and read-only outcome-blind screens may proceed, but no
  `build-features` run may occur before the ledger is terminal and acquisition
  must not compete for its Cloud Run capacity.
- Shell syntax, Python compilation and 25 focused TD-ledger/final-forensic
  tests pass. The terminal launch/harvest scripts require a full immutable code
  SHA and image digest, pin every G0/G1/cache/schedule/protocol input, use 32 GiB
  and 8 CPU, enforce write-once run artifacts and validate chunked transport.
- Terminal repair commit `934d2c3` is pushed on `main`. Exact-commit full-test
  Cloud Build `ac8758bc-712b-4cda-a9fc-fc6e1252bdc2` is `WORKING`, targeting
  tag `nfl-dfs:td-rank-934d2c3`. Only its immutable success digest may launch
  the frozen ledger job.
- The formal exact-panel SIS run-tail prerequisite completed as read-only
  BigQuery job `bqjob_r7410ee58c589ee60_000001a001818c04_1`. It queried no
  player/lineup outcome. Strict-prior support is 5,842/6,731 salary RB rows
  overall and 86.14%/86.05%/88.13% across 2023/2024/2025. Aggregate correlations
  are Boom/Bust versus existing RB-FP-allowed `+0.1906/-0.0829` and versus rush
  EPA `+0.4820/-0.2726`. The prerequisite passes. The two-feature RB-only
  score-free protocol is frozen, explicitly adaptive, and queued behind the
  ledger; no cache/model output exists.
- Uncommitted final-forensic diagnostic/corpus improvements are locally tested
  but do not license a freeze and must not be included in the TD-ledger image
  identity accidentally. The last forensic Cloud Build
  `036d54f4-467b-4b97-8e04-b380cb95bb2a` is validation-only even if successful.
- Next concrete action: commit/push the bounded terminal ledger repair, publish
  its exact full-test image, launch the single score-free Cloud Run execution,
  poll and harvest it. In parallel, formalize the read-only SIS run-tail audit;
  keep all feature rebuilds and forensic outcome queries blocked.

### 2026-08-14 final-forensic queryable corpus retention frozen outcome-free

- On `main` from parent commit `830729c`, the operator's requirement to leave
  the final forensic corpus and exact selections queryable for further review
  is now part of the governing closure protocol and fail-closed manifest. No
  new realized outcome query was run and no forensic destination table has
  been created by this implementation work.
- The manifest pins four fully qualified, write-once (`WRITE_EMPTY`) BigQuery
  tables in the dedicated, production-inaccessible
  `nfl-predictions-503414.nfl_forensic_review` dataset: suffixes
  `final_forensic_20260814_player_corpus`, `_candidate_corpus`,
  `_actual_selections` and `_oracle_rosters`. Their exact field/type/mode
  schemas are code-frozen. Every row includes the manifest hash, immutable
  analyzer image, analyzer commit, evidence scope, season and week. The player
  table retains the salary universe, authoritative actuals and served
  distribution fields; the candidate table retains every roster and frozen
  selection metric; the selection table retains the ordered exact-80 books;
  and the oracle table retains independently audited H/P/C/S rosters and gaps.
- Automatic expiration is 90 days from materialization as a failure backstop,
  but the operator subsequently required removal before Week 1. The binding
  cleanup deadline is now before the first 2026 production feature/lineup
  build and, operationally, before the Aug 24 scheduler resume. The runner
  attaches and verifies expiration metadata, records table ids/row counts/
  expiry timestamps in provenance, supports only a verified same-manifest
  retry after a completed partial multi-table write, and refuses an unrelated
  or schema/row-count-drifted existing destination.
- New manifest-bound cleanup command
  `scripts/cleanup_final_forensic_warehouse.py` requires all four exact schemas,
  full manifest identity, labels and expirations before deleting anything. It
  deletes only the four frozen tables, independently proves each is absent and
  emits a write-once receipt; `--verify-only` requires that receipt and fails
  if any table reappears. The receipt must be committed/pushed before production
  schedulers resume. Production configuration names only `nfl_raw`,
  `nfl_features` and `nfl_predictions`, never the isolated review dataset.
- Season-start scheduler resumption now has a fail-closed executable gate,
  `scripts/resume_2026_production_schedulers.py`. It first invokes the live
  absence verifier, requires the byte-identical cleanup receipt to be present
  in `HEAD`, fetches `origin/main` and proves `HEAD` is pushed, then describes
  all 22 exact scheduler identities before it can mutate any scheduler. It is
  a dry run unless the operator explicitly supplies `--resume`; the README no
  longer presents the raw resume loop as an approved path. Three focused gate
  tests pass, including receipt-byte drift and the exact scheduler inventory.
- Dataset `nfl-predictions-503414:nfl_forensic_review` now exists in `US` with
  `defaultTableExpirationMs=7776000000` (90 days), labels
  `purpose=final_preseason_forensic` and `production_use=forbidden`, and an
  explicit temporary-review description. It is empty; creation did not query
  or write a historical outcome.
- A live outcome-free schema audit caught that
  `slate_player_features.feature_missing` is a required STRING containing a
  serialized feature-name list (`[]` on all 228,048 relevant source rows), not
  a BOOL. The retained player schema now preserves that raw STRING and derives
  a separate required `feature_missing_any` BOOL; the summary count uses the
  same empty-list semantics. This prevents the truthiness of string `[]` from
  falsely labeling every player row as missing. Candidate preflight also found
  zero null roster/index/salary/selection/score-metric fields and zero incomplete
  labels across 40,724 replay plus 68,493 staging rows; no actual score was
  selected or aggregated in these checks.
- The forensic runner now emits the exact nine-output JSON contract in
  addition to the queryable corpus: H/P/C/S, exact-80 and nested 20/40/80
  portfolio distributions, available first-place context, the limited 2025
  Week-5 payout-floor anchors, player capture/calibration, candidate rank/tag
  diagnostics and the outcome-free ledger/readiness/charter/certificate
  outputs. It labels places 2--5 and exact multi-season ROI unidentifiable
  because complete standings/payout rows are absent rather than fabricating
  them.
- The arm registry now has 46 rows and every one of the 12 certificate families
  has an explicit disposition: role12 availability, the historical construction
  census, the contest-choice evidence gap and the pre-Week-1 operations blocker
  fill the four previously empty taxonomy families without fabricating a new
  experiment or result.
- The freeze now hash-pins every non-Markdown input/evidence artifact that the
  analyzer consumes or cites: both contest-score CSVs plus the terminal G0,
  G1, effective-rank, multi-seed candidate-world, selector-resampling and
  pass-tail JSON reports. The validator rejects an omitted or duplicate
  artifact path and the builder refuses a missing file. This closes a
  provenance hole that otherwise could have allowed the retained corpus to be
  regenerated against silently changed evidence.
- Focused manifest, H/P/C/S, corpus, cleanup, output-builder and multi-seed
  validation passes 27 tests; Python compilation and whitespace validation pass. The
  exact-80 corpus test proves 80 ordered selections and four independently
  legal H/P/C/S rows are preserved.
- Validation-only Cloud Builds are terminal success:
  `694ff04f-4148-4575-8dbf-b9346fe77270` produced digest
  `sha256:3d2c1a56125550ccc4a19dc13f48599d711dff164c30c15526dbcd9c367c6832`
  from the registry-only source, and
  `ed546b09-fd02-485e-8308-00a7b8885ac9` produced digest
  `sha256:347a922effeef5b5f26403dd2ca057c740e632664c76677a035f9ef5fb423e34`
  from commit `830729c`. Neither digest contains this retained-corpus extension
  and neither may be named in the final freeze manifest.
- Exact-commit build `ff5d548f-89f6-4dea-a1de-fb877bf618dc` was launched from
  pushed commit `3557cf1` and is currently `WORKING`; the later review-dataset
  isolation/cleanup requirement means its eventual image is validation-only.
  A superseding exact-commit build is required after the cleanup-gate commit.
- The isolated-dataset/cleanup implementation is pushed on `main` as
  `a8ca7b5`. Superseding exact-code Cloud Build
  `739bd75d-ea0d-419c-91ea-14131950234b` is `WORKING` with image tag
  `forensic-a8ca7b5`; if successful, its immutable digest is the only current
  analyzer image eligible for the freeze manifest. Later HANDOFF-only commits
  do not change that analyzer-code identity.
- The subsequent live STRING/list schema correction changes analyzer code and
  makes both in-flight builds validation-only. Commit it and launch one final
  superseding full build; do not freeze `a8ca7b5` or either in-flight digest.
- The required-artifact pinning above is one final analyzer-code correction;
  builds `739bd75d-ea0d-419c-91ea-14131950234b` and
  `cda141a1-e20a-4a62-bafe-c900eeb3e6b7` remain validation-only even if they
  succeed. The eventual freeze image must be built from the commit containing
  this correction.
- The artifact-pinning implementation is pushed as commit `4df618a`. Build
  `739bd75d-ea0d-419c-91ea-14131950234b` is terminal `SUCCESS` with validation-
  only digest
  `sha256:70a0acb3640eb0e642b72939da1c482cc4d99b293f67ac798cb9a01885896df0`;
  `cda141a1-e20a-4a62-bafe-c900eeb3e6b7` is still `WORKING`. The final eligible
  exact-commit build is `036d54f4-467b-4b97-8e04-b380cb95bb2a`, currently
  `QUEUED`, targeting tag `forensic-4df618a`.
- Next concrete action: harvest that exact-commit Cloud Build, then create and
  commit the freeze inputs/manifest pinned to that digest and these four table
  contracts. Only after that commit may the first new outcome query or forensic
  table write occur. After the independent review, run/commit the deletion
  receipt before Aug 24; the production resume is blocked until absence verifies.

### 2026-08-14 final-forensic freeze/analyzer primitives implemented outcome-free

- The feedback in
  `reports/2026-08-14-pass-tail-and-selector-resampling-feedback.md` is
  reconciled without reopening either frozen decision. The pass-tail exact-80
  report now carries non-nested breadth: the deciding >=220 delta is three
  improving versus one worsening seed/slate over two distinct improving and
  one distinct worsening calendar slates; across all thresholds it is 19
  improving versus 15 worsening seed/slates, 14 distinct improving and 14
  distinct worsening slates, and 23 distinct changed slates. The 2025 adverse
  pattern is an explicit prospective checkpoint. The selector diagnostic gives
  the disjoint-half 54.2778/80 overlap equal billing, but labels it correctly
  as reproducibility rather than an economic entry-count recommendation.
  Bootstrap-mean bagging is closed, and the finite-K pass-tail/K=1 production
  transfer boundary remains binding.
- The GCP historical scoring/analyzer queue is empty and a fresh status-only
  check found no active Cloud Run job execution. Production remains the
  already deployed K=1 CBWU v4 service below. This satisfies the no-active-
  outcome-experiment prerequisite for freezing the final forensic analysis.
- New outcome-free module `src/nfl_dfs/research/final_forensic.py` implements
  deterministic report inventories and hashes, a self-digested fail-closed
  freeze-manifest validator, independent roster legality/score reconstruction,
  an exact PuLP full/support player oracle, and corrected H/P/C/S decomposition
  with additive player-support/construction/selection gaps. It requires all
  inventoried `*-protocol.md` and `*-result.md` files to be represented by a
  terminal ledger row or a reasoned exclusion; it also pins the exact nine
  closure outputs and all 12 mechanism-taxonomy families.
- Eight focused offline tests pass. They prove an omitted high scorer appears
  in H but not P, candidate score drift and RB-versus-DST illegality fail,
  unaccounted protocols/results and open statuses fail, file drift fails, and
  a mutated manifest self-digest fails. No real historical outcome has been
  queried by this implementation or validation.
- The reviewed terminal registry now contains 42 rows and accounts for all 35
  prior `*-protocol.md` arm files plus all 30 `*-result.md` files; the only
  excluded protocol is the governing final-closure protocol itself. It keeps
  the narrow SIS team-defense schema disposition, both failed Route channels,
  the selector reproducibility/economic boundary and every selected/rejected/
  neutral/prerequisite/prospective disposition explicit. The manifest builder
  expands defaults, pins hashes and exact output schemas, and validates the
  result before it can be written.
- Outcome-free BigQuery prelock capture excludes `actual_score`, `actual_rank`
  and player `actual` by construction. It froze candidate/player counts and
  combined row hashes for component-107 (`27,051`/`50,418`, 107 slates,
  `ab3720ef...3e2c`), position-54 (`13,673`/`29,605`, 54 slates,
  `8cb6f8f5...342b`) and the five Phase-S CBWU source books (`68,493`/
  `148,025`, 54 slates, `869a648a...e7e`). The complete signed-summary inputs
  are tracked in the run directory; these are metadata/provenance queries, not
  a new outcome read.
- The post-freeze H/P/C/S runner is now implemented but has not been run. It
  validates the committed manifest and runtime image/code identity, recomputes
  every prelock hash before requesting outcomes, independently reconciles the
  complete salary-listed Sunday-main skill/DST universe and authoritative
  actuals, reconstructs CBWU from the five source books and hash-verified score
  artifacts, then solves/reconstructs H/P/C/S. The new CBWU forensic transport
  reproduces the registered fixed-budget CBWU selected order exactly in its
  pure test; 20 focused final-forensic/multiseed tests pass.
- Registry commit `08725b3` is pushed. Full Cloud Build
  `694ff04f-4148-4575-8dbf-b9346fe77270` is active for that contract-only
  commit. Because the H/P/C/S runner was implemented after its source upload,
  any image it emits is validation evidence only and must not be pinned as the
  final analyzer; the exact H/P/C/S commit requires a superseding full build.
- Next concrete action: commit the H/P/C/S runner, harvest the validation-only
  build, run the superseding exact-commit full build, and commit the freeze
  manifest pinned to the superseding digest. Only after that manifest
  commit may the first new outcome-facing H/P/C/S query run. Keep the evidence
  scopes explicit: component evidence spans 107 slates, position/Phase-S/CBWU
  evidence spans 54; there is no 107-slate CBWU book and one must never be
  fabricated.

### 2026-08-14 licensed CBWU mechanism validated and deployed in K=1 production

- On `main` from parent commit `8ba41f7`, the frozen multi-seed production
  verdict is now implemented as policy
  `classic-k1-role12-boom40-poscal-cbwu-v4`, sourced to
  `20260813-multiseed-candidate-world-v1`. It preserves K=1 `tail_k1`/
  `tail_k1_role`, model ensemble 1, role12 + boom40, the 45/55 blend, the
  $49,000 floor, position scales and the unchanged line-194 greedy selector.
  It does not enable the separately tested finite-K pass-tail cache/schedules.
- The production transport runs the exact registered R0--R4 projection/role
  seed pairs. Each native preselection book is captured inside the existing
  engine. `inference/multiseed_portfolio.py` validates native candidate totals
  against aligned player worlds, requires identical unique player universes,
  deduplicates by first supplying seed, allocates exactly the R0 candidate
  budget by the frozen score-blind quota/fill order, and cross-scores every
  retained roster in five equal 10,000-world blocks. Missing, extra,
  malformed, short or misaligned books fail closed before a final lineup is
  returned or persisted.
- The engine capture/transform seam retains the existing selection, thesis,
  oracle, full candidate persistence, clear-mask and score-artifact paths for
  the final 50,000-world CBWU book. Non-base native searches explicitly
  disable candidate persistence, so the warehouse cannot contain five
  misleading native `selected` books. Candidate provenance records its source
  seed in `all_tags`, and the multi-seed contract is now included in
  `lever_env` and the API/CSV/UI public policy identity.
- A live/replay parity defect was repaired: role-belief worlds now use the
  registered `ROLE_BELIEF_SEED`, not the baseline projection seed. Ownership
  shadow capture is emitted only for the final R0 baseline slate; the four
  auxiliary baselines and all five alternate role builds no longer create
  duplicate calibration snapshots.
- Candidate generation retains the licensed 80-entry basis even if the user
  has fewer reserved entries; the unchanged greedy prefix selects the
  requested count. Requests above 80 fail clearly instead of silently
  extrapolating an unvalidated mechanism. The older CE12/boom28 outage
  fallback remains complete, labeled and single-seed because CBWU did not
  validate that candidate mix.
- Pure fixed-budget/cross-score, fail-closed, live seed-orchestration, role
  seed, policy identity, app identity and persistence tests pass. The broad
  local suite excluding the deliberately expensive real five-search
  `test_adopted_policy_builds_true80_dk_csv` collected 1,230 tests and reached
  100% with no failures; the ordinary live-chain smoke also passes. A local
  attempt at the new exact true-80 smoke was manually stopped after six
  minutes while actively solving CBC jobs, in accordance with the repository
  rule that sustained heavy validation runs in GCP; this was not a test
  failure.
- Implementation commit `74c22b5` is pushed on `main`. Exact-commit Cloud
  Build `78f7ea3a-5503-47e3-b6b9-57359695c4a3` completed successfully,
  including the real five-search exact-80 DK CSV smoke. The complete suite
  passed `1,233` tests with `2` skipped and `5` warnings in `754.72s`. It
  published immutable image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:869bda10ffbdfe9c76491f96f606aaa63083e43d3754226593b87a46a34bcd58`
  (tag `nfl-dfs:cbwu-74c22b5`).
- That immutable image is deployed to Cloud Run revision
  `nfl-dfs-app-00070-29b`, which is Ready/Active/ContainerHealthy and serves
  100% of service traffic. The deploy preserved IAP, all-ingress routing,
  4 CPU, 4 GiB RAM, 1,800-second request timeout, concurrency 2, maximum scale
  20 and startup CPU boost. Do not reduce the five searches or 50,000 final
  selection worlds in response to latency; measure the first full Week-1
  rehearsal and adjust service resources/concurrency from that evidence.
- The final forensic closure protocol now carries the selector/pass-tail/
  multi-seed feedback forward without changing a historical verdict. It makes
  distinct improving/worsening/changed calendar slates mandatory, gives the
  54.28/80 disjoint-half reproducibility diagnostic equal billing without
  mislabeling it as 54 economic entries, preserves the finite-K pass-tail/K=1
  transfer boundary, and adds an exact CBWU production transport/latency
  audit. Next exact action: freeze the final evidence manifests before querying
  any remaining forensic outcomes, then perform the Week-1 production dress
  rehearsal with one ownership snapshot and a complete five-book/50,000-world
  artifact.

### 2026-08-14 selector-resampling feedback reconciled; pass-tail analyzer live

- The external selector-stability review in
  `reports/2026-08-14-selector-stability-under-world-resampling.md` has been
  reconciled before reading any pass-tail outcome. Its fixed-candidate
  world-resampling diagnostic is useful and is now frozen separately in
  `reports/2026-08-14-selector-resampling-score-free-protocol.md`; the exact
  technical reconciliation is
  `reports/2026-08-14-selector-stability-resampling-reconciliation.md`.
- Do not implement the review's proposed mean-bagged selector as written. For
  a fixed covered set, the equal-half mean of marginal clear counts is exactly
  the full-sample marginal clear count, and the expectation over ordinary
  bootstrap resamples is the same empirical objective. Finite resampling only
  adds noise. A genuinely new selector would require a separately frozen
  stability penalty/lower-confidence objective or new independent worlds.
  The realized-maximum diagnostic is outcome-facing and is deferred to the
  final forensic closure.
- The adopted score-free diagnostic holds the selected Phase S treatment R0
  candidate set fixed and uses its checksum-verified 10,000 worlds on all 54
  2023--2025 slates. It requires exact reproduction of the persisted ordered
  80-entry book, uses one deterministic reciprocal 5,000/5,000 split and 32
  deterministic 10,000-world bootstrap resamples, and reports exact-80 plus
  prefix overlap, reciprocal coverage optimism, and per-candidate selection
  frequency. Frequencies go to a write-once checksum-addressed gzip artifact;
  the tracked report remains score-free and has no production authority.
- Implementation is in `src/nfl_dfs/research/selector_resampling.py`,
  `scripts/analyze_selector_resampling.py`, and the guarded launch/harvest
  scripts. The BigQuery query deliberately excludes players and realized
  scores, the launcher pins the original feedback, reconciliation, protocol,
  Phase S report/manifest, source image/code/beta/panel and the new immutable
  analyzer image. Focused selector plus multi-seed validation passes 10 tests;
  Python/shell syntax and whitespace validation pass. The complete local
  suite passes 1,218 tests with 2 skipped. Publish one exact-commit immutable
  image before launch.
- The pending multi-seed factorial already isolates fixed candidates versus
  new worlds: `C0W0` and `C0WU` use the identical R0 candidate set while only
  the selection worlds change from R0's 10,000 to the equal R0--R4 50,000
  union. `C0` versus `CU` is the candidate-generation contrast. The new
  within-R0 resampling diagnostic complements rather than replaces it.
- Pass-tail exact-80 has all 30 terminal successes and zero failures. The final
  treatment R4/2025 cell `replay-sisptt4-2025-ph97f` completed in 1h30m59s.
  The guarded finisher independently verified the full arm/replicate/season,
  panel, image, code and terminal-status provenance for every cell, then
  launched exact-80 analyzer execution
  `analyze-sis-pass-tail-exact80-v1-pvd6b` on the frozen audit digest. It
  failed before emitting a scientific report in the mechanical feature audit:
  BigQuery BOOL columns were numerically coerced and pandas/NumPy reject
  boolean subtraction. The terminal error and non-result disposition are
  tracked in `analyzer_failure.txt`; no outcome was harvested.
- The mechanical comparer now handles bool/nullable-boolean columns as exact
  values before tolerant numeric comparison, matching the already-hardened
  Phase R/Phase S comparers. A regression test exercises unchanged, null and
  changed nullable booleans. The dedicated retry launcher verifies the exact
  original terminal failure and feature-audit frame, changes only the audit
  code/image, preserves every panel/input/gate/resource argument, and records
  separate retry provenance. Focused repair/selector validation passes 24
  tests; Python/shell syntax and whitespace checks pass.
- Exact-commit selector build
  `65db620b-1c95-4864-b916-0c52d9b8e34a` from `2ff57b4` was cancelled after
  the analyzer exposed this repair need; it did not publish an eligible
  immutable image. Superseding exact-commit full-test build
  `feea8d38-ba32-43e3-8717-2b5511e4fdb8` completed from pushed commit
  `2a336d3`; it passed 1,220 tests with 2 skipped and published immutable
  digest
  `sha256:a39e28b155d607af5c1757091979652908f1c18a8389cb044d58585380821345`.
  The guarded retry verified the original failure signature and launched
  execution `analyze-sis-pass-tail-exact80-v1-6cchk` with every scientific
  input and resource unchanged. Poll and harvest that execution; retry
  provenance is tracked separately from the failed original.
- Current concrete GCP queue is: run/harvest the score-free
  selector-resampling analyzer, then run/harvest the frozen multi-seed
  candidate/world factorial. Apply the licensed production decisions only
  after those immutable reports, then prepare the registered final forensic
  closure. No other replay-score panel is currently licensed or queued.
- The repaired analyzer completed successfully in 2m54s and the immutable
  mechanically valid result is now harvested. The tail-first decision selects
  pass-tail `treatment` at the first differing threshold, 220. Across five
  seed books, selected 240/230/220/210/200/194/187 counts move from
  `0/1/3/11/20/37/60` to `0/1/5/13/23/38/60`. Mean weekly maximum moves
  `173.8999` to `173.4789` (-0.4210; slate-clustered mean-delta 95% interval
  `[-1.5092,0.7001]`). This is the operator-authorized trade: two more >=220,
  two more >=210 and three more >=200 seed-weeks despite lower mean.
- Season diagnostics are mixed: 2023 improves throughout the tail, 2024 adds
  220/210/200/194 weeks while losing at 187/mean, and 2025 loses at
  210/200/194 while gaining at 187. The amended aggregate tail-first rule is
  binding and does not require uniform season gains. Human-readable result is
  `reports/2026-08-14-sis-pass-tail-exact80-result.md`; complete report SHA-256
  is `6d92edb503747a729ad7cecfd95315b0eff1e04be72491bea296a33aeb8e3689`.
- Selected finite-K pass-tail research state is cache
  `tabpfn_sis_pass_tail_treatment_v1` with the frozen treatment schedules in
  `selected_pass_tail.txt`. This licenses a later explicit live/UI integration
  decision but not silently combining it with the distinct K=1 money-lineup
  policy; that transfer cell was not tested. After the artifact queue closes,
  preserve this boundary while recording the exact Week 1 production and
  prospective-shadow states.
- The frozen score-free selector-resampling diagnostic launched on validated
  digest `sha256:a39e28b1...1345` as execution
  `analyze-selector-resampling-v1-wdb6m`. Its manifest pins the 54-slate Phase
  S treatment R0 source, code/image/beta, 10,000 worlds, exact-80/194 selector,
  feedback/reconciliation/protocol hashes and write-once frequency artifact.
  It cannot read realized outcomes or change production; interpret it
  alongside the multi-seed factorial.
- Selector-resampling execution `...-wdb6m` completed successfully in 15m01s
  and the mechanically valid report/frequency artifact are harvested. Every
  persisted full book reproduced exactly and no realized outcome was read.
  Mean pairwise bootstrap exact-80 overlap is `61.6362`, disjoint-half overlap
  is `54.2778`, and reciprocal train-minus-validation coverage optimism is
  `0.01275`. All seasons fall in the frozen intermediate band; 2025 is least
  stable at `60.3221` pairwise overlap.
- Average candidate-frequency counts per slate are 45.15 selected in at least
  90% of bootstrap books, 29.80 in 50%--under-90%, and 90.57 at positive but
  under 50%. Mean prefix overlap at 1/5/10/20/40/60/80 is
  `0.59/3.13/6.49/13.58/29.08/45.12/61.64`, confirming greater instability at
  the top of the order. This has no production authority; enter it in the
  forensic opportunity register and use the frozen multi-seed result as the
  only current test of genuinely new selection worlds.
- Human result is
  `reports/2026-08-14-selector-resampling-score-free-result.md`. Tracked report
  SHA-256 is
  `8ad05426312cfa4fccf9ba6bc12ad47b0650dd6ce05c06b1bfbf86d1502e5d60`;
  compressed frequency artifact hash is
  `6774188eaa15d76807c78f63c49b574d908ec9a1cd3d0a21cca27d7036349cf2`.
- With pass-tail completely harvested, the one-active-outcome-experiment
  firewall is clear. The frozen multi-seed candidate/world factorial launched
  concurrently with the score-free diagnostic as execution
  `analyze-multiseed-candidate-world-v1-blhp5`, using the Phase S-selected
  treatment source. Its tracked manifest pins the source report/protocol,
  immutable source image/code, all five R0--R4 books, exact-80 and all frozen
  candidate/world cells. Poll and harvest only the terminal complete report.
- Multi-seed execution `...-blhp5` completed successfully in 5m44s, but the
  first harvest found its legacy single JSON log entry truncated at the Cloud
  Logging limit: 102,428 stored bytes ending inside a string, with
  `Unterminated string` at column 102,369. No complete report/decision was
  recovered. The original truncated log and partial JSON are preserved and
  cannot be cited as a result.
- Transport-only repair is frozen in
  `reports/2026-08-14-multiseed-report-transport-repair.md`. It changes only
  output framing to deterministic zlib/base64 numbered chunks under 75,000
  characters. The guarded retry requires the original successful execution
  and exact truncation signature, then preserves source arm/panels/code,
  candidate/world cells, metrics, gate and resources. Focused multi-seed and
  selector validation passes 12 tests; Python/shell syntax and whitespace
  checks pass. Publish an exact-commit full-test image, retry the analyzer and
  harvest only the complete reconstructed report. Exact-code build
  `cc1ddc35-d1e2-4971-b110-fa1623091e87` is running from `24ced17` with tag
  `nfl-dfs:multiseed-transport-24ced17`; use only its successful immutable
  digest for the guarded retry.
- Exact-code build `cc1ddc35-d1e2-4971-b110-fa1623091e87` succeeded from
  `24ced17`, passed 1,222 tests with 2 skipped, and published immutable digest
  `sha256:279b81a693a786fdbea2ba2fecf61075c056561f5933e5b9582551cbebb48bac`.
  The first guarded launch then exposed a provenance-check mismatch: the
  deliberately empty `truncated_report.json` placeholder was incorrectly
  required to be nonempty. The guard now validates the unterminated JSON
  directly from the preserved first log line; this changes no scientific
  input or computation. Validate and push this guard-only repair, then launch
  the exact transport retry on that already-validated digest.
- Guard-only repair commit `4ba1d25` is pushed. The corrected guard verified
  the original successful execution and registered truncation signature, then
  launched transport-only execution
  `analyze-multiseed-candidate-world-v1-9zf9b` on the validated immutable
  digest above. Poll it to terminal and harvest only the complete chunked
  reconstruction; do not use the partial original log.
- Transport-only execution `analyze-multiseed-candidate-world-v1-9zf9b`
  completed successfully in 5m12.77s. The harvester reconstructed every
  numbered chunk, passed the frozen mechanical gate and wrote the immutable
  complete report. Report SHA-256 is
  `a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239`;
  raw chunk-log SHA-256 is
  `cb4dc642baffa57d35b44e6113e9d6317a6c800b4f68f140b63974fc15693bd4`.
- The four-cell research winner is `CUW0`. Its exact-80 counts at
  240/230/220/210/200/194/187 are `0/1/1/6/8/11/21` versus C0W0
  `0/0/0/3/6/10/12`; mean weekly maximum improves by `4.8363` with diagnostic
  slate-clustered interval `[0.8972,8.8152]`. Because CU has about 579.80
  candidates versus 253.81, this remains added-budget discovery evidence.
- The clean world comparison selects C0WU over C0W0 first at 210 (`4-3`).
  The prospectively frozen same-budget confirmation then selects `CBWU` as the
  final production mechanism arm: counts are `0/1/3/6/7/8/17` versus C0WU
  `0/0/0/4/6/9/11`, with the same mean candidate count 253.81 and exactly 80
  final entries. Mean weekly maximum is `176.0630` versus `174.9041` (+1.1589).
  Human result is
  `reports/2026-08-14-multiseed-candidate-world-result.md`.
- The production mechanism verdict licenses five score-blind candidate seeds
  under the fixed total quota/fill law and five equal selection-world blocks,
  failing closed if any block is absent. It does not license pass-tail's
  finite-K cache/schedules. Wire it into the existing K=1 money policy without
  changing marginals, direct-role/boom allocation, position scales or the
  exact-80 export, then run outcome-blind unit/integration/Week-1 validation.
- Feedback in
  `reports/2026-08-14-pass-tail-and-selector-resampling-feedback.md` is
  reconciled in the adjacent tracked report. A descriptive, non-binding
  crossing retrofit shows the pass-tail 220 result is three improving and one
  worsening seed/slate crossing on only two calendar slates (2023-W03 and
  2024-W03). Across all thresholds, 19 unique seed/slates improve and 15
  worsen, spanning 23 changed calendar slates. The frozen treatment decision
  stands but is now labeled modest-breadth. Disjoint-half selector overlap
  `54.28/80` receives equal forensic billing; it is not called an effective
  entry count. The 2025 negative below-220 shape is predeclared for 2026
  finite-K shadow checkpoints at Weeks 4/8/13/18.
- The historical GCP scoring/analyzer queue is now empty. The next concrete
  actions are production/UI reconciliation for the licensed CBWU mechanism,
  exact outcome-blind deployment validation, then the mandatory frozen final
  forensic closure. Do not query that forensic outcome set before its required
  freeze commit.
- The pass-tail analyzer now emits gross and distinct threshold-crossing
  diagnostics for future exact-80 reports. Focused pass-tail/multi-seed tests
  pass 20 tests, the complete local suite passes, and whitespace validation
  passes. Commit and push the harvested reports, feedback reconciliation and
  diagnostic together before beginning CBWU production wiring.

### 2026-08-14 Phase S complete; SIS ASOE selected; Route follow-ups ready

- Independent queue verification confirms that pass-tail is the only active
  historical score experiment and that G3, Route marginal, Route I1/R2 rank
  dependence and the registered SIS team-defense schema estimand all have
  terminal frozen dispositions. Carry the SIS qualifier precisely: only Team
  Pass Defense Totals at team/game grain as a source of
  coverage-snap-normalized efficiency is closed; `Att`-composition ASOE and
  player/defender-grain denominators are separate mechanisms. Phase S already
  selected the ASOE mechanism. The three Route results together close both
  registered current-stack historical insertion points: marginal Route fields
  failed the served-tail gate, and unshrunk plus fixed midpoint-shrunk
  rank/copula treatments failed their dependence gates. This closes the frozen
  queue, not every conceivable Route interaction or transform; no further
  historical Route score arm is licensed, while the 2026 prospective shadow
  remains open.
- One terminology correction to the verification: conditional I2 is the Route
  marginal x ASOE factorial. Because the marginal `M` gate failed, I2 is
  terminally not run under its frozen branch. The separate artifact-only
  multi-seed candidate/world factorial is not I2; it remains frozen and
  not-yet-launched for the Phase S-selected treatment law. Run it after the
  pass-tail exact-80 experiment is completely harvested, preserving the
  one-active-historical-score-experiment discipline, and before final forensic
  closure.
- The durable reconciliation is
  `reports/2026-08-14-mechanism-queue-verification-reconciliation.md`. It also
  narrows the review's capacity argument: another replay panel would contend
  with the pass-tail cells, but the later artifact-only analyzer is a single
  8-vCPU/32-GiB job that fits nominal quota. It remains sequential because of
  the outcome firewall, not because quota alone makes concurrency impossible.
- The same verification identified that a live pass-tail ledger batch could
  exist only in the working tree. The launcher now checkpoints and pushes
  `executions.txt` immediately after every provenance-verified release and
  before allocating the next cell. The already-running launcher predates that
  edit, so its observed batches were checkpointed manually; all 30 released
  mappings are now preserved in the repository. Editing the source while the
  old Bash process was still reading its final loop caused that controller to
  exit with a mixed-source parse error immediately after it had appended and
  provenance-verified cell 30. This did not alter or interrupt any Cloud Run
  execution, and the current tracked launcher passes `bash -n`; do not restart
  the immutable launcher.
- The external Phase S infrastructure-failure review has been reconciled with
  the shipped recovery path. Its blocking ledger-substitution risk is closed:
  the finisher verifies the execution-owned job, full arm/replicate/season
  environment, seeds, panel, image, code, resources and terminal status before
  analysis. Future panel launchers enforce a hard ten-cell in-flight cap and
  own their ledgers; transient BigQuery 429/5xx reads retry from a fresh query;
  replay workers run a deterministic NumPy/SciPy startup self-check. True
  per-slate replay resumability remains deliberately open because the final
  lineup table must be atomically reconstructed and validated with candidate,
  feature and artifact stores. The Phase S scientific result below is valid;
  every final cell passed the complete execution-provenance audit.
- The frozen Route R2 midpoint-shrinkage screen completed and fails clearly.
  Its only treatment transform was
  the preregistered stable rank of `0.5 * control + 0.5 * Route`, populated
  with each player's exact sorted control values. The implementation reuses
  the fixed I1 population, common component worlds, pair book, bootstrap books
  and five-family gate; its launcher pins every prerequisite hash, exact
  source checksum, finite K, selected ASOE beta and midpoint weight. The
  harvester fails closed on incomplete chunks, wrong disposition/weight, or a
  marginal/mean delta above `1e-10`. Focused and all 1,215 complete offline
  tests pass. Exact-commit Cloud Build
  `2f3ce908-1a6d-4136-a943-6f338219fe99` succeeded from `a611de2` and
  published immutable digest
  `sha256:9f8f1ad528a9b84eb9559fb5c8ce95a8e6cbb665820785e9857e77b2c68d1868`.
  The fully guarded launcher reverified every frozen prerequisite and
  execution `route-rank-dependence-r2-v1-gkbtw` succeeded. Complete report
  hash is
  `10d0c3ff103d6f6da2575873bbc0175b03d20738fb55008736e6848d8bfb9ede`.
  R2 exactly preserves sorted marginals (`0.0` maximum delta) and player means
  (`7.11e-15`), but all five dependence families worsen; their equal-weight
  mean loss ratio is `2.073476`. Multiplicity/role-pair/primary-broad ratios
  are `4.331711/2.096520/1.932749`, joint-q90 Brier is `1.001729`, and
  variogram is `1.004671`. QB-WR/QB-TE hub error rises from `0.169897` to
  `0.216526`, with material regressions for QB_TE, QB_RB, WR_WR and RB_RB.
  Disposition is `route-rank-dependence-r2-fails`. Close midpoint Route-rank
  shrinkage on this panel and do not launch an R2 exact-80 score experiment.
- SIS pass-tail exact-80 has released all 30 registered cells under its hard
  ten-cell cap; both arms and all R0--R4/2023--2025 cells are represented
  exactly once. The final cell is treatment R4/2025 execution
  `replay-sisptt4-2025-ph97f`. No execution failure was observed at release.
  Continue status-only polling of the 30 recorded execution IDs and do not
  read partial score outcomes. After every execution is terminal `True`, run
  the guarded finisher with the frozen audit image/code, then poll and harvest
  the one analyzer.

- Branch is `main`; the cache freeze shipped in pushed commit `9052868`, the
  score-free evaluator shipped in `975a223`, and the rank/dependence screen
  shipped in pushed commit `799a27e`. All 30 Phase S cells completed
  successfully, and the guarded finisher verified every immutable image,
  code SHA, arm, replicate, season, panel and execution before launching the
  frozen analyzer. Analyzer execution
  `analyze-sis-asoe-phase-s-v1-8lcpc` succeeded and the complete mechanically
  passing report is tracked under
  `reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/`.
- The frozen tail-first decision selects SIS alignment-based target allocation
  (`treatment`, beta `0.07771181538347656`) over finite-K control. Across the
  five paired seed books, treatment raises selected >=210 seed-weeks from
  14 to 16 and >=187 from 58 to 64; >=194/200/220/230/240 are tied at
  42/26/5/1/0. Mean weekly best rises 173.822 to 174.173 (+0.352), although
  the 54-slate clustered 95% interval is [-1.223, 1.949]. The selected
  treatment state is now the common inherited ASOE law for all preregistered
  Route and SIS pass-tail follow-ups; do not refit beta or change the branch.
- Route marginal cache executions `tabpfn-route-i1-control-r4hvs` and
  `tabpfn-route-i1-marginal-9l2vl` succeeded. Their frozen validator passes:
  52,307 identical unique target keys per arm, exact control reproduction at
  `0.0` maximum delta, the treatment adds exactly the four registered Route
  fields, treatment predictions change, and all source/context/output checks
  pass. Initial score-free evaluator execution
  `tabpfn-route-channel-final-served-i1-v1-c8hkl` later required the OOM retry
  described below. Separately, Route component/rank execution
  `route-rank-dependence-i1-v1-j6xfl`
  completed all computation but failed while encoding its report because a
  NumPy boolean was not JSON serializable. No incomplete metrics were read.
  Report transport now normalizes NumPy scalars/arrays, a regression test
  exercises the actual failure class, and the complete local suite passes
  with one existing skip. Exact-commit retry build
  `3dfdf7e0-e115-4ab3-a5a1-e865b60781a8` succeeded from `c263939` and
  published immutable digest
  `sha256:5928949f9503dcab7a33979a1fa1a3ee88f5f1ddd2fcc4ad2fa7c5ecd645f56f`.
  A
  dedicated retry path verifies the original execution and exact error line,
  preserves every scientific setting, and records the new image/code and
  execution separately. It passed those provenance checks and launched retry
  execution `route-rank-dependence-i1-v1-gwkxp`, which succeeded.
- The complete I1-R report is mechanically valid but fails the frozen gate.
  Four of five equal-weight families improve: role-pair MSE ratio `0.992884`,
  broad-relationship MSE `0.994875`, joint-q90 Brier `0.999872`, and
  variogram `0.999947`. QB-WR/QB-TE mean absolute log gap improves
  `0.169897` to `0.160869`, with no material/double-score relationship
  regression. Multiplicity MSE worsens to ratio `1.022204`, however, leaving
  equal-family mean ratio `1.001957` above one. Sorted-marginal and mean
  deltas are only float32-scale `3.8147e-6` but exceed the frozen `1e-10`
  invariant. Disposition is `route-rank-dependence-i1-fails`; do not call it
  a pass or directly promote it. Freeze one new fixed 50% rank-score
  shrinkage screen, with exact control-marginal remapping and no tuned grid,
  before executing it; I1-R score outcomes remain unseen.
- The follow-up is now frozen in
  `reports/2026-08-14-route-rank-r2-shrinkage-protocol.md` before
  implementation. R2 uses exactly one midpoint rank score,
  `0.5 * control + 0.5 * Route`, then stable-rank maps the exact sorted control
  values back to each player. There is no weight grid or field subset. It
  inherits the same population and five-family gate, and cannot score lineups
  unless it first passes with exact marginal/mean reproduction at `1e-10`.
- The first SIS pass-tail exact-80 launcher invocation stopped before creating
  a run manifest or allocating compute because its prerequisite guard treated
  the frozen report's per-arm `maximum_mean_delta` object as a scalar. The
  local orchestration guard now requires exactly control/treatment keys and
  validates both finite values against `1e-10`; the unchanged scientific
  panel and frozen generation image/code remain intact. Shell syntax, the
  actual frozen-report contract, focused tests and whitespace checks pass.
  The repair shipped in pushed commit `1736d97`; the unchanged panel passed
  all prerequisite/write-once checks and launched treatment smoke execution
  `replay-sis-pass-tail-e80-smoke-ppsk6`. The smoke is active; on success the
  launcher will release the 30 registered cells at a ten-cell cap.
- The pass-tail smoke succeeded and the first ten registered control cells,
  control R0/2023 through R3/2023, were released with live provenance checks.
  The launcher remains active and is holding at its ten-cell cap; continue
  polling session `51675` so later cells are released as capacity frees.
- Route score-free execution
  `tabpfn-route-channel-final-served-i1-v1-c8hkl` failed without a report when
  Cloud Run reached the registered launcher's 16Gi memory limit. Its failure
  condition is a verified OOM, not a scientific result. A dedicated retry
  path now verifies the entire original execution contract and changes only
  memory to 32Gi, records `retry_execution.txt`, and leaves the frozen image,
  inputs, seed, Phase S state and finisher gate unchanged. Focused tests and
  shell/whitespace validation pass. Retry execution
  `tabpfn-route-channel-final-served-i1-v1-wppdl` passed the OOM provenance
  check and ran at 32Gi.
- The 32Gi Route score-free retry succeeded and the complete report is
  mechanically valid, but marginal-only Route fields fail the frozen tail
  gate. Equal-position q95/q99 mean pinball ratio is `1.009900` (worse), with
  RB `1.007856`, WR `1.006717`, TE `1.015126`, and zero of three positions
  improving. Means are preserved within `7.11e-15`. Marginal Route improves
  central CRPS by `0.014800` and point MAE by `0.025027`, but q95 and q99
  pinball worsen by `0.002748` and `0.002925`; the tail-first rule controls.
  Disposition is `tabpfn-route-channel-final-served-fails`. Do not launch a
  marginal-only exact-80 or the conditional M-by-ASOE factorial. The separate
  component/rank Route screen remains live and is not affected by this result.
- The current-stack I1 Route Share marginal-channel experiment is frozen in
  `reports/2026-08-14-route-channel-i1-protocol.md`, before Phase S is
  harvested and before either new cache exists. It compares accepted
  active-only TabPFN control `C` with marginal-only treatment `M`, adding
  exactly `fp_route_share_last`, `fp_route_share_l4`,
  `fp_route_share_jump`, and `fp_route_cross_season`. It does not reuse the
  older Route component or candidate-union conclusions.
- The source is pinned to 102,927 rows/checksum
  `1904430067081090565`, the accepted v2 validation hash, baseline feature
  hash and immutable TabPFN 2.2.1 GPU base image. New write-once cache
  generation, launcher, finisher and validator require identical target keys,
  active-only prior-season contexts, exact feature-contract difference,
  non-identical treatment predictions and exact control reproduction of
  `tabpfn_active_label_treatment_v2` within `1e-10`. The launcher cannot run
  until Phase S has a complete mechanically valid decision.
- Replay licenses only the two exact new cache names. Python and shell syntax,
  shell lint where available, whitespace validation, focused tests and the
  complete offline test suite pass (one existing skip). After this commit,
  publish an immutable GPU image from the exact commit. Once Phase S is
  harvested, generate/validate C/M and run the preregistered score-free
  q95/q99 pinball gate before any Route exact-80 score test. The rank-only `R`
  cell and conditional I2 Route-marginal x ASOE factorial remain separately
  registered follow-ups and may not inherit `M`'s result.
- Exact-commit GPU Cloud Build
  `3795bfac-5a1f-45c0-9ec4-3d01c8232dbd` succeeded and published the cache
  image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-route-channel@sha256:86008932590aead9585119093e94668d35e84c8fc40e9df66d10b6e3553871a8`.
  The build source was a clean `git archive` of `9052868`, not the live Phase
  S ledger worktree.
- The I1 score-free evaluator, CLI command, launcher and chunked harvester are
  prepared. They require both the valid cache report and the complete Phase S
  report, inherit its selected ASOE state identically for `C/M`, retain finite
  `K=28.154043586960896`, fit each arm's position schedule strictly from prior
  OOS folds, and report q90/q95/q99 pinball/reliability, Brier 20/25/30,
  CRPS/MAE and paired whole-slate clustered intervals. Control Phase S fails
  closed on stray ASOE settings; treatment requires the exact frozen beta.
  Focused tests and the complete offline suite pass with one existing skip.
- Exact-commit full-test/audit Cloud Build
  `7d71804f-f195-4533-a289-178e4f5f5a4b` succeeded from `975a223` and
  published
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:abecbf8bb13952c8e7714073446cd1e1d8ffa9a08c96ca83b0691d864b4db2d7`.
- The separately registered I1 `R` component/rank screen is now frozen before
  either Phase S or Route-marginal results are available. Its sole arm change
  is the four Route fields in component training; both cells retain the
  accepted active-label v2 marginal cache, selected G0 schedule, finite K,
  selected Phase S ASOE state and every other final-served law. It fails
  mechanically unless every sorted 10,000-value player marginal reproduces
  within `1e-10`.
- `R`'s five equal-weight loss families are G0 multiplicity squared log-gap,
  G0 role-pair squared log-gap, G1 primary broad relationship squared log-gap,
  overall joint-q90 Brier and overall p=0.5 variogram. The preregistered gate
  requires an aggregate ratio below one, at least three improving families,
  non-worsening QB-WR/QB-TE hub error, no primary relationship absolute-gap
  increase above `log(1.15)`, and no relationship worsening both proper scores
  by over 10%. Its launcher also rechecks the frozen training-table checksum
  and cannot run without the complete Phase S decision. Focused tests, shell
  validation, whitespace checks and the complete offline suite pass with one
  existing skip.
- Exact-commit Route rank audit Cloud Build
  `9a2f826e-dfba-476a-ab98-234cdd2418d6` succeeded from `799a27e` and
  published immutable digest
  `sha256:bd2e744c2f7da238ec8937b2ce38f7827d7d8f6081cd73405c53e985247805f2`.
  Use this digest for the registered `R` screen after Phase S is complete;
  do not substitute the older score-free-audit image because it predates the
  rank implementation. Continue status polling until Phase S is 30/30.

### 2026-08-14 Phase S at 11 successes; future replay startup hardened

- Branch was `main` at pushed commit `d2f95c7`; the ledger and infrastructure
  hardening described here subsequently shipped in `f83b7c2`. The
  bounded Phase S recovery has reached 11 clean successes, ten active cells
  and nine queued failures. The latest controlled replacement is treatment
  R2/2024 execution `replay-sisasoet2-2024-p4zpk`. The releaser was stopped
  only to make this ledger milestone atomic; status-only monitor session
  `72912` remains active. Restart the bounded releaser immediately after the
  commit and continue at the ten-cell cap.
- Exact-commit Cloud Build `b2f7fdd4-3eac-4d4c-89ee-cde17efd991f` succeeded
  and published the pass-tail audit image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:1940ccc6aa6969111ce89abf7b16719c150dbf97c9e8aa8d151784f963890c1a`.
  This is an audit/harvest image for the already-frozen `d2f95c7` code; the
  conditional exact-80 generation image remains the preregistered `f92ce05`
  digest recorded below.
- The remaining low-risk recommendations from the Phase S infrastructure
  review are implemented for future images without changing any current
  Phase S cell: `query_df` retries only BigQuery 429/500/502/503/504 read
  failures, starts a fresh query/download each time, uses bounded 2/4/8-second
  backoff and exposes no partial DataFrame. Replay now verifies fixed
  NumPy/SciPy solve, CDF and checksum results before importing the expensive
  replay stack. Authentication, SQL, schema and permission errors still fail
  immediately. Focused tests, Python compilation and whitespace validation
  pass; run the complete suite before committing.
- True per-slate resumability is deliberately not claimed yet. The current
  candidate/artifact writer is per slate, but the human-review lineup table is
  written only after the season engine returns. A correct resume path must
  validate all candidate, feature and GCS stores and reconstruct a complete
  lineup table rather than merely skipping weeks. Keep the partial-output
  cleanup procedure for the immutable Phase S/pass-tail images and implement
  this redesign before a later multi-cell scientific panel.

### 2026-08-14 Phase S bounded recovery advancing; pass-tail exact-80 frozen

- Branch was `main`, based on pushed commit `b286de4`; this historical
  milestone and its exact-80 implementation were subsequently pushed as
  `d2f95c7`.
  Phase S's scientific arms, seeds and decision law remain unchanged and no
  incomplete-panel outcome has been used.
- The bounded controller reduced the current ledger from 18 failed cells to
  12: eight are clean successes and ten are active at the hard cap. It
  byte-identically released replacements through treatment R1/2023, recording
  each immutable execution in `executions.txt` and
  `infrastructure_retries.txt`. The controller was stopped only long enough to
  validate and commit this stable milestone; the status-only monitor remains
  active and the exact next action is to restart the bounded releaser.
- Control R3/2025 execution `replay-sisasoec3-2025-lgczd` exposed the recovery
  case the zero-output path intentionally rejected: Cloud Run reported an
  internal error/exit 0 after 15 weeks had persisted. Recovery removed exactly
  that panel/season's 3,820 candidate rows, 8,312 feature rows and 15
  candidate-world artifacts; its dedicated lineups table did not yet exist.
  All three stores were verified empty before the cell was queued. The durable
  classification is in `partial_infrastructure_recoveries.txt`. The cleanup
  was required to prevent mixed-run duplicates and did not use the outcome in
  deciding whether to retry.
- The one exact-80 lineup experiment licensed by the passing SIS pass-tail
  final-served gate is now fully frozen before Phase S is harvested. Its
  addendum registers five paired seed books, all 54 slates, exact 80, 10,000
  worlds, the high-tail-first order `240/230/220/210/200/194/187`, clustered
  bootstrap diagnostics, exact per-arm walk-forward schedules, and the
  conditional common Phase S branch. Generation is fixed to replay-capable
  commit/image `f92ce05` / digest `018f0def...d358`; it cannot launch until
  Phase S passes mechanically and selects control or treatment.
- New launcher, execution-owned verifier, analyzer, finisher and chunked
  harvester fail closed on the Phase S/cache/final-served hashes, all 30
  execution specs, seeds, cache/schedule identity, finite K, conditional ASOE,
  complete player-feature invariance outside exactly ten registered
  distribution outputs, exact-80/artifact identity, common actuals and a
  material path to candidate scoring. Cloud release is capped at ten and the
  audit report uses compressed numbered chunks below Cloud Logging's limit.
- Shell syntax, Python compilation, whitespace checks, 15 focused tests and
  the complete 1,189-test collection pass (1,188 passed, 1 skipped). No
  pass-tail lineup candidate or outcome exists yet. After Phase S reaches 30
  verified successes, run its frozen analyzer/harvester first; only then run
  `cloud_tabpfn_sis_pass_tail_exact80_v1.sh` with the frozen generation image
  and code, monitor all 30 cells, and finish with a newly built audit image.

### 2026-08-14 Phase S infrastructure review reconciled and recovery hardened

- The operator-supplied review at
  `reports/2026-08-13-phase-s-infrastructure-failure-review.md` has been read
  in full and reconciled at
  `reports/2026-08-14-phase-s-infrastructure-failure-reconciliation.md`. Its
  core operational recommendation is accepted: a launch delay did not limit
  concurrency. Thirty 8-CPU/32-GiB cells requested 240 vCPU/960 GiB against
  the last recorded regional quota of 200 vCPU/400 GiB. The image is already
  co-regional and about 330.5 MB, so quota/capacity pressure is demonstrated
  while a single registry/BigQuery root cause is not.
- `scripts/verify_sis_asoe_phase_s_execution.py` now verifies every execution's
  own Cloud Run specification against its registered arm, seed replicate,
  season, panel, job, image digest, code SHA, allocation law, ASOE flag,
  resources and terminal status. The Phase S finisher requires all 30
  execution-spec checks before analyzer launch. This is defense in depth: the
  analyzer already queries immutable panels directly and checks their stored
  seeds/levers/season completeness, so it does not relabel results merely from
  ledger row order.
- The Phase S launcher now enforces at most ten in-flight cells. New bounded
  one-cell retry release and atomic ledger-update helpers recheck zero BigQuery
  candidate/feature rows and zero GCS artifacts, validate the launched
  execution spec, require 30 unique factorial cells/IDs and then substitute
  exactly the matching ledger row. Twelve focused execution/analyzer/ledger
  tests and the complete 1,181-test suite pass; shell syntax, Python
  compilation and whitespace validation also pass.
- The first bounded release check correctly stopped on a newly failed current
  cell rather than launching anything: treatment R2/2023 replacement
  `replay-sisasoet2-2023-lf7l8` terminated after about 30 minutes with Cloud
  Run internal error/exit code 0, no application logs, zero candidate rows,
  zero feature rows and zero candidate-world artifacts. It is now back in
  `pending_infrastructure_retries.txt`. No outcome was read and the main
  execution ledger was not changed.
- The status-only monitor then found two more replacements from the overloaded
  wave had the identical 30-minute internal-error/exit-0 signature: control
  R0/2025 `replay-sisasoec0-2025-v6jfr` and treatment R4/2023
  `replay-sisasoet4-2023-hqskx`. Both have only the platform error log and zero
  candidate rows, feature rows and candidate-world artifacts, so both are also
  in the pending bounded queue. No replacement was launched at the still-high
  active occupancy.
- Continue status-only polling. Do not release any queued retry until the
  current nonterminal count is below ten; then run
  `scripts/cloud_release_sis_asoe_phase_s_retry.sh`, which releases at most one
  verified cell and owns its ledger substitution. Any new current failure
  outside the pending queue makes the releaser stop for zero-output
  classification. After 30 verified successes, run the hardened Phase S
  finisher/analyzer and harvest the frozen decision.

### 2026-08-13 Phase R complete; finite K selected

- All 30 registered multinomial/finite-K replay executions are now clean
  Cloud Run successes. The final clean retry was 2025 finite-K R4 execution
  `replay-gtrk4-2025-66fnq`.
- Frozen analyzer execution `analyze-game-team-usage-phase-r-v1-phwnl`
  correctly failed its completeness gate because multinomial R0 had 53 rather
  than 54 slates. The original successful 2025 execution log proves the
  missing slice is Week 4: its candidate artifact and feature rows persisted,
  but the 256-row candidate-table append received BigQuery HTTP 429 (too many
  concurrent table update operations). The replay continued, so Cloud Run's
  success status alone did not expose the missing append.
- The append-only repair path is now tracked in
  `scripts/cloud_repair_game_team_usage_phase_r_week4.sh` and its finish
  script. It reproduces weeks 1--4 under the exact original immutable image,
  seeds, levers and lineup table into a provenance-only panel; the finish
  script validates Week 4, appends only that absent slice to the original
  panel, retains provenance rows, and launches the unchanged frozen analyzer.
  No arm definition or decision rule changed. The repair execution was
  `replay-gtrmult0-2025-w4-repair1-5v4jq`.
- The exact repair succeeded and its 256 unique, label-complete Week 4
  candidate rows (80 selected) were appended to the original panel. Frozen
  analyzer retry `analyze-game-team-usage-phase-r-v1-msp2x` passed and the
  report is harvested at
  `reports/game-team-usage-runs/20260813-game-team-usage-phase-r-v1/report.json`.
- Under the registered high-tail-first decision, finite K is retained:
  across five seeds it wins first at the 230 threshold (`1` week versus `0`),
  with 194/200/210/220 totals `42/26/14/5` versus multinomial
  `37/21/12/3`. Average weekly best is `173.82163` versus `173.56993`.
  Multinomial has more 187 weeks (`62` versus `58`), but that is downstream
  of every registered higher threshold and cannot override the decision.
  Phase S is launching on selected control law `k` using the already validated
  `4d6f5cf` image digest recorded below. Its mandatory 32-GiB smoke execution
  `replay-sisasoe-phase-s-smoke-lwh7r` passed. All 30 registered cells are now
  launched and recorded in
  `reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/executions.txt`.
  Poll terminal state only; after 30 clean successes run the Phase S finish,
  poll/harvest its analyzer, and apply the frozen five-seed decision.
- Three initial Phase S executions failed before application startup with zero
  application logs, candidate rows, feature rows and artifacts. Each received
  one byte-identical retry, recorded in `infrastructure_retries.txt` and
  substituted into the execution ledger: control R0 2024
  `replay-sisasoec0-2024-vntds`, control R1 2024
  `replay-sisasoec1-2024-kpj74`, and treatment R3 2023
  `replay-sisasoet3-2023-fsnmw`. No outcome was read and no arm/config changed.
- Treatment R2 2023 then failed before replay import because that container
  replica exposed a truncated SciPy shared library (`file too short`), again
  with zero candidate rows, feature rows or artifacts. Its one byte-identical
  retry is `replay-sisasoet2-2023-lf7l8`; the ledger/provenance is updated.
- Control R0 2025 and treatment R4 2023 later failed on transient BigQuery
  Storage internal 500s before their first replay write, both with zero rows.
  Their byte-identical retries are `replay-sisasoec0-2025-v6jfr` and
  `replay-sisasoet4-2023-hqskx`; both are substituted in the ledger.
- Fourteen more of the original 30-cell burst then terminated after about 30
  minutes with Cloud Run `Internal error running task`, exit code 0, zero
  application logs, and zero candidate/feature rows. They are enumerated in
  `pending_infrastructure_retries.txt`. Do not burst-launch all 14: six earlier
  retries plus ten original cells currently occupy the active capacity. Poll
  the 16 current cells and release queued byte-identical retries in small
  batches only as active slots finish; move each launched row to
  `infrastructure_retries.txt` and substitute its execution ID in the main
  ledger. No scores may be read while this repair queue is active.
- Treatment R3 2023 replacement `replay-sisasoet3-2023-fsnmw` itself then hit
  the same 30-minute internal-error/exit-0 path with zero rows. It has been
  returned to the pending staggered queue rather than relaunched at capacity.
- With current occupancy at 15, one queued replacement was released into the
  open slot: control R3 2024 `replay-sisasoec3-2024-hcrkg`. The remaining queue
  stays held until another slot actually frees.

### 2026-08-13 SIS pass-tail caches validated; frozen score gate running

- Both write-once cache executions completed successfully: control
  `tabpfn-sis-pass-tail-v1-control-8hkl2` and treatment
  `tabpfn-sis-pass-tail-v1-treatment-z7hv4`.
- `scripts/cloud_finish_tabpfn_sis_pass_tail.sh f2560d1` passed every frozen
  mechanical check, including exact keys/row counts, control reproduction
  (`maximum_abs_delta=0.0`), mean preservation, source/code identities,
  feature contracts, context counts and support audits. The durable validation
  artifact is
  `reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-v1/validation.json`.
- The preregistered final-served calibration evaluation was launched as
  Cloud Run execution `tabpfn-sis-pass-tail-final-served-v1-mn64m` on audit
  digest
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:fdd00d6bf36778c38415068bda5809b8d3324a5ee77ecb5ba3feefafc73da339`.
  It did not produce a report; the immediately following bullet records the
  failure and unchanged retry path.
- Execution `tabpfn-sis-pass-tail-final-served-v1-mn64m` failed before
  producing a report because the shared replay fail-closed research-table
  allowlist omitted the two newly generated pass-tail table names. The cache
  data, arm, panel and frozen evaluation rules were not implicated or changed.
  The allowlist now explicitly includes only those two exact tables and a
  regression test covers both direct resolution and context restoration; 18
  focused replay/pass-tail tests pass. Repair commit `0c86821` is pushed;
  exact-commit Cloud Build `ac2ceacb-b0f1-446a-a5fe-305546fa60f4` passed the
  full suite and published immutable digest
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:1a51a8132bca8a58caff0f7bca4c3bdd594c4a75ad26bd2cac7ce7c289946e6f`.
  The tracked one-retry wrapper preserved the failed execution and frozen
  manifest while launching the repaired evaluator on that digest.
- Repaired evaluator execution `tabpfn-sis-pass-tail-final-served-v1-k9w8n`
  completed successfully, but its single JSON log entry exceeded Cloud
  Logging's 100-KiB text limit and was truncated at 102,400 bytes before the
  local harvester could parse it. The frozen computation succeeded; no
  disposition is yet recoverable from the truncated transport.
- The evaluator now emits the same deterministic JSON as zlib-compressed,
  base64, numbered chunks capped at 80,000 characters, and the finish script
  verifies complete framing before decoding. A round-trip regression test and
  the full focused pass-tail/replay suite pass. Commit `f92ce05` exact Cloud
  Build `5fc982be-181a-4ecf-b34b-31e73ff44bd5` passed the full suite and
  published digest
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:018f0def471ba3f0a304cafb77e301c35e43d51658798f64a9ec85c95751d358`.
  Transport-only execution `tabpfn-sis-pass-tail-final-served-v1-c7dsz` is
  a clean success and its chunked report harvested. The frozen gate **passes**:
  equal-position/equal-q95/q99 ratio `0.9950319868`, improving positions QB
  and TE, and maximum row-mean change `7.11e-15`. CRPS also improves by
  `0.0089196` with a slate-cluster 95% interval wholly below zero. This
  licenses exactly one Phase-S-law exact-80 lineup test; do not launch it until
  Phase S is harvested and selects the allocation law. Human-readable result:
  `reports/2026-08-13-sis-pass-tail-final-served-result.md`.

### 2026-08-13 SIS pass-tail cache and score gate implemented prospectively

- On `main` from UI commit `be255fc`, the frozen pass-tail arm now has a
  dedicated strict-prior helper, the common TabPFN GPU generator supports its
  exact three-column treatment, and write-once launch/finish/validation
  scripts target `tabpfn_sis_pass_tail_{control,treatment}_v1`.
- Before either cache was generated, implementation reconciled the required
  2022 calibration fold: final-served reconstruction is bound to historical
  panel `20260811-pitclean-e80-k1-role12union-a12ab31`, finite Dirichlet
  `K=28.154043586960896`, 10,000 worlds, seed 0, fitted widening and the 45/55
  model/market blend. The protocol records this prospective clarification;
  the exact-80 follow-on still inherits the later Phase-S allocation law.
- The separate score gate independently fits each arm's walk-forward position
  schedule and applies the registered equal-position/equal-q95/q99 pinball
  gate on active QB/WR/TE. It also persists every position/season fold,
  Brier/reliability at 20/25/30, q90/q95/q99 calibration and pinball, CRPS,
  MAE, mean preservation and paired slate-cluster uncertainty.
- Commit `f2560d1` is pushed. Validation passes: 22 focused new/regression
  TabPFN SIS tests, Python compilation, shell syntax and whitespace checks.
  GPU Cloud Build `b907b29c-4161-4a5a-9819-e061dc931d6d` passed and published
  immutable digest
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-sis-pass-tail@sha256:21067518a2f013cdea4a43a1eb0ef224b6d81bc4ced8bddef4ebdf30959a81e7`.
  The write-once executions are control
  `tabpfn-sis-pass-tail-v1-control-8hkl2` and treatment
  `tabpfn-sis-pass-tail-v1-treatment-z7hv4`. Exact-commit audit build
  `4d4d00c4-24ce-432c-a177-1215bee9dee5` passed the full suite and published
  immutable digest
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:fdd00d6bf36778c38415068bda5809b8d3324a5ee77ecb5ba3feefafc73da339`.
  Poll cache status only; when both succeed run
  `scripts/cloud_finish_tabpfn_sis_pass_tail.sh f2560d1`, then launch the
  score-free final-served gate on that audit digest. No treatment prediction
  or score had been read at launch.

### 2026-08-13 repository explainer promoted into the product UI

- On branch `main` from parent `102a4e8`, the existing non-technical explainer
  was moved to the single product-owned source
  `src/nfl_dfs/app/static/explainer.html`, served at `/explainer`, and linked
  as **About** in the common product navigation. At the operator's request,
  the original `docs/explainer/` directory and its duplicate Markdown
  companion were removed so only one evolving copy can become stale.
- The app package already includes `static/*`, so the normal production image
  carries the page without a separate Docker copy. The route adds a small
  product navigation bar while preserving the standalone explainer styling.
- Validation passes: the full `tests/test_app.py`, focused route checks,
  Python compilation and whitespace checks. Exact-commit Cloud Build
  `be0dfcad-c9d9-4aef-884a-3c446d1c328d` passed and produced digest
  `sha256:3f91211d7837d6705e8e8824d33f682cac87e4c814f8fb75aa7887ca11ccebb2`.
  Cloud Run service `nfl-dfs-app` is ready on revision
  `nfl-dfs-app-00069-np4` with that digest. Anonymous HTTP redirects through
  the existing IAP login as expected; the exact page/navigation assertions
  passed in Cloud Build.

### 2026-08-13 SIS paid-surface gaps reopened with bounded next tests

- The outside coverage audit is tracked at
  `reports/2026-08-13-sis-plan-coverage-gap-audit.md`; the repository
  reconciliation is
  `reports/2026-08-13-sis-plan-coverage-gap-reconciliation.md`. Its core
  conclusion is accepted: SIS is not exhausted. Corrections: rushing
  Boom/Bust was already audited; pass-rush pressure was screened but never in
  a formal arm; player grain was planned/attempted and one valid smoke already
  proved `Cov. Snaps`, but no filtered historical table was completed.
- The missing original-priority team Receiving family now has a validated,
  tracked 36-artifact/160-request plan at
  `automation/sis/plans/team-receiving-v1.json`. It covers team Receiving
  Totals/Value for 2019 and 2021--2025 in the three cap-safe windows. Do not
  run until the operator supplies a fresh terminal SIS login and provider
  budget is available. It is historical research, not a weekly plan.
- An outcome-free strict-prior pass-tail prerequisite now passes: all three
  source fields are non-null on 3,230 team-games; `10,018/11,435` active
  QB/WR/TE rows (`87.61%`) are supported. Redundancy correlations are
  Boom-vs-existing-EPA `+0.59938`, Bust-vs-existing-EPA `-0.56054`,
  pressure-vs-existing-pressure `+0.41030`, and Boom-vs-Bust `-0.11521`.
  No player outcome or lineup score was read. Reproducible result:
  `reports/2026-08-13-sis-pass-tail-support-result.md`.
- The resulting current-stack three-feature marginal cache comparison is
  frozen before treatment output at
  `reports/2026-08-13-sis-pass-tail-marginal-protocol.md`. It appends only
  volume-weighted opponent pass-defense Boom/Bust and pass-rush pressure for
  QB/WR/TE. Its primary score-free gate is equal-position q95/q99 normalized
  pinball improvement in at least two of three positions, with no season veto;
  all other tail/central metrics remain diagnostics. A pass licenses only one
  Phase-S-law exact-80 test. Passing charting and player-grain receiver
  allocation remain separate later hypotheses.
- Validation passes: 48 focused SIS support/context/downloader tests, Python
  compilation, plan expansion (`36` artifacts exactly) and whitespace checks.
  Exact next SIS action is implement/generate the frozen control/treatment
  caches without delaying Phase R/S, then run the score-free final-served gate.

### 2026-08-13 strengthened Phase S/multi-seed image validated

- Exact-commit Cloud Build `445a5071-62a3-4354-ab6a-e66004a099a7` passed the
  full repository test suite from `4d6f5cf` and published immutable image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:757f0784937492c23917c245b082e052508fcac693840a1469e0020257fad6a4`.
  This supersedes `e6ba5e2...` for Phase S because it contains the prospective
  seed-noise, proper-score and fixed-budget factorial amendments. Use code
  identity `4d6f5cf` when Phase S launches.
- Phase R now has 29 clean successes: identical R4/2024 infrastructure retry
  `replay-gtrk4-2024-rdpd4` completed successfully. R4/2025 retry
  `replay-gtrk4-2025-66fnq` remains active. Continue status-only polling;
  after it cleanly succeeds, run the guarded Phase R finisher/harvester and
  launch Phase S on the digest above.

### 2026-08-13 multi-seed implementation review incorporated prospectively

- The outside review is tracked at
  `reports/2026-08-13-multiseed-factorial-implementation-review.md`. Its four
  corrections to the interaction-design report are accepted, and that source
  now carries the correction in its own amendment log. No Phase R/Phase S
  score or multi-seed outcome was read before making these changes.
- The not-yet-launched multi-seed artifact analyzer now reports all five native
  seed books, the seven-threshold min/max seed-noise envelope, all ten
  pairwise selected-book overlaps, and q95/q99 pinball for the simulated
  weekly selected-book maximum. It also reports candidate/world main effects
  and the difference-in-differences interaction.
- The four-cell `CU` candidate factor is explicitly added-pool-budget discovery
  evidence. To eliminate a later post-hoc construction choice, the protocol
  prospectively defines and the analyzer implements `CBW0`/`CBWU`: exactly the
  R0 candidate count, near-equal deterministic R0--R4 source quotas, canonical
  candidate order, and deterministic deficit filling. The clean `C0W0` versus
  `C0WU` result chooses the world setting; if and only if a `CU` research arm
  wins, the corresponding fixed-budget `CB` comparison may change production
  candidate generation. All books still select exactly 80 final lineups.
- Focused multi-seed/artifact/persistence validation passes (33 tests). Build a
  superseding full-test immutable image from the committed milestone before
  Phase S so the strengthened analyzer and its player-world contract share one
  image. The prior `e6ba5e2...` image remains a valid simulation build but does
  not contain this prospective analyzer amendment.
- Full score-blind Phase R polling found that K-law R4/2024
  `replay-gtrk4-2024-rp575` and R4/2025 `replay-gtrk4-2025-ftflh` ended with
  Cloud Run internal platform errors after reported exit code 0. Exact
  season-level completeness checks showed zero 2024/2025 candidate rows,
  feature rows, or score-artifact rows; the panel's existing rows are only the
  successful 2023 season. One byte-identical retry per failed execution is
  running as `replay-gtrk4-2024-rdpd4` and
  `replay-gtrk4-2025-66fnq`, both on the registered digest
  `sha256:4c59f038...`. The active execution list and durable infrastructure
  retry ledger are updated. Current Phase R status is 28 clean successes and
  two active retries; no partial lineup score was queried.
- Exact next action: commit/push this milestone, launch the superseding full
  Cloud Build, continue status-only Phase R polling, run its guarded frozen
  finisher/harvester at 30 clean successes, then launch Phase S with the new
  digest/code identity and proceed to the strengthened artifact-only
  multi-seed analysis after Phase S.

### 2026-08-13 interaction-design review reconciled before Phase R/S outcomes

- The amended outside review is tracked at
  `reports/2026-08-13-experimental-design-arm-interactions.md`; its bounded
  repository reconciliation is
  `reports/2026-08-13-experimental-design-arm-interactions-reconciliation.md`.
  The original claim that weak dependence makes marginal improvements unable
  to propagate was correctly retracted: weak dependence reduces leverage but
  does not make propagation impossible. The amended marginal-versus-rank
  channel distinction is adopted.
- Four safeguards are now explicit. The cited failures are not one homogeneous
  marginal family; old Route component/union results cannot populate a new
  current-stack channel cell; aggregate G0/G1 moments do not uniquely specify
  an oracle copula; and the fourteen-panel retrospective can estimate only
  full-rank, supported design contrasts. The oracle and panel meta-analysis
  remain in the final forensic phase and cannot revive/adopt a historical arm.
- Every future protocol must name its stage/channel, estimand, terminal
  incumbent, downstream transfer boundary and interaction status, and report
  channel-appropriate tail proper scores or dependence metrics. After Phase S,
  run a current-stack score-free Route screen with common control, TabPFN-
  marginal-only Route and component/rank-only Route cells. If the marginal
  cell passes, run the predeclared five-seed exact-80 Route-marginal x SIS-ASOE
  2x2 regardless of either standalone Phase S lineup disposition. This adds no
  post-result choice and does not change the frozen Phase R or Phase S arms.
- The existing multi-seed candidate/world factorial remains frozen for the
  Phase S-selected upstream law. If the later interaction factorial selects a
  different Route/ASOE cell, its downstream production conclusion must be
  revalidated under that cell rather than assumed to transfer.
- Latest score-blind Phase R status before this milestone: the first two clean
  platform retries completed successfully, bringing the panel to 29 successful
  jobs. The last retry, `replay-gtrk4-2023-pkbvk`, remains active/unknown with
  one running task. No partial score or candidate result was queried. Exact
  next action: continue status-only polling; after all 30 succeed, run
  the frozen Phase R finisher/harvester, launch Phase S on immutable image
  `sha256:e6ba5e2...` / code `1e0bf04`, and implement the Route channel screen
  without altering either active protocol.

### 2026-08-13 ASOE passed; incumbent seed sensitivity measured

- ASOE execution `sis-asoe-allocation-v1-nxhvc` completed successfully and
  passed every frozen Stage A gate. The 2022-only fit selected
  `beta=0.07771181538347656`; untouched 2023--2025 aggregate target-allocation
  NLL improved by `-0.0003686816` per group, each season improved, evaluation
  geometry covered 93.00%/88.26%/84.41%, and the clustered 95% interval was
  wholly favorable `[-0.000663052,-0.000077982]`. This licenses final-served
  exact-80 evaluation but is not a scoring result. The immutable result is in
  `reports/sis-asoe-allocation-runs/20260813-sis-asoe-allocation-v1/` and the
  concise interpretation is
  `reports/2026-08-13-sis-asoe-allocation-stage-a-result.md`.
- Repaired seed analyzer `analyze-incumbent-seed-variance-v1-qh9l8` completed
  and passed all mechanical gates without rerunning any replay. The incumbent
  is materially seed-sensitive: selected >=194 ranges 3--9, >=210 ranges
  0--2, mean per-slate best-score range is 22.31, and pairwise selected-book
  overlap averages only 12.21/80. Full immutable JSON is under
  `reports/incumbent-seed-variance-runs/20260813-incumbent-seed-variance-v1/`;
  concise result is `reports/2026-08-13-incumbent-seed-variance-result.md`.
- Before Stage B launch, code review found the accepted finite-K replay's
  allocation unit is wrong for season-wide replay: `simulate.py` factorizes
  only team abbreviation, pooling the same team's rows across games/weeks.
  Live single-week inference is unaffected, and the ASOE Stage A evaluator
  used explicit team-week groups, so neither result above is invalidated.
  Historical finite-K lineup panels are not a faithful direct control and
  must be revalidated after changing the unit to `(game, team)`.
- Exact next action: repair/test the finite-K game-team grouping, implement
  ASOE target-center tilting before the existing final marginal remap, freeze
  a paired multi-seed corrected-control versus ASOE exact-80 protocol, build
  one immutable image, and launch its control/treatment panels in parallel.
- The grouping repair and its focused 45-test simulator/ledger/SBI suite now
  pass. The pre-outcome Phase R standing-law and Phase S ASOE protocol is
  frozen in
  `reports/2026-08-13-game-team-usage-repair-and-sis-asoe-exact80-protocol.md`.
  It binds the finite-K/multinomial branch before repaired results exist, uses
  all five registered seed pairs, and requires exact player-marginal rank
  transport for ASOE.
- ASOE final-served implementation is complete locally. It validates the
  three hash-bound warehouse sources, applies the frozen beta only to target
  centers, composes only the target/reception/receiving-yard contribution,
  and rank-transports exact control draw multisets. A real 2023 replay smoke
  preserved all 9,614 projection summaries and every sorted player draw
  exactly while changing 8,333 rows' joint ordering. The full repository
  suite passed with one expected skip; the post-provenance focused suite
  passed 70 tests. Exact next action: commit/push, build one full-test
  immutable image, then launch the frozen Phase R multi-seed standing-law
  panel.
- Implementation commit `d6b0e5d` is pushed. Full-test mechanism build
  `d6ee547b-e406-4852-a9e0-3ee7cbc56e2c` succeeded with immutable digest
  `sha256:c1ad0d5bf39ec7af663bc0124e7a832550d03e1b9cc9b6875b60f265d1775612`.
  A guarded
  30-season-execution Phase R launcher, score-blind poller and mechanical
  analyzer were then added/pushed in `45ece38`; superseding full-test build
  `a65ee32e-4a87-443e-b205-b6f9a1976aba` is the intended generation/audit
  image. The launcher runs one corrected finite-K cloud-week smoke before
  fanning out all five paired seeds and both laws.
- Superseding build `a65ee32e-4a87-443e-b205-b6f9a1976aba` succeeded;
  immutable image is
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:4c59f038898d7a21aa2d6067c78238b0349f1e3b090999a6e9da8703ea316e43`
  with embedded code `45ece38`. Phase R run
  `20260813-game-team-usage-phase-r-v1` is launched and currently at its
  outcome-blind preflight `replay-gtrphase-r-smoke-5z6xn`. The still-running
  local launcher session `63787` will automatically fan out 30 jobs after
  that smoke succeeds. Exact next action: poll/resume that session; do not
  relaunch the immutable run.
- Phase R smoke `replay-gtrphase-r-smoke-5z6xn` passed. All 30 immutable
  season jobs are now launched and recorded in
  `reports/game-team-usage-runs/20260813-game-team-usage-phase-r-v1/executions.txt`;
  the launcher completed normally. Initial poll has all jobs active/pending
  with no explicit failure. Exact next action: use
  `scripts/poll_game_team_usage_phase_r.sh`; when all 30 are `True`, run the
  guarded finisher and harvester. Do not query partial staging scores.
- Phase S runner/analyzer is now prepared and pushed through commits
  `66ff2dd` and `ca1eea0`. It binds the Phase R-selected allocation law,
  regenerates five same-image controls and five ASOE treatments (30 season
  jobs total), requires exact marginal-feature/common-candidate mean parity,
  and requires the new controls to reproduce Phase R before scoring SIS.
  Full-test Phase S build `c1bae3b3-8656-46c8-9289-7a72fe1ab67e` is running.
  Latest Phase R poll: 30 `Unknown`/active, zero explicit failures.
- Phase S's diagnostic slate-cluster bootstrap and guarded finisher/harvester
  were frozen/pushed in `9837ea4`; build
  `54a0e163-1794-496f-bb85-45dd19d8beb8` is running but will be superseded by
  the next image because its reproduction check compared only weekly maxima.
  The local follow-up now requires the complete Phase S control candidate
  fingerprint (index, roster, selected flag/rank, actual and simulated mean)
  to reproduce Phase R, preventing an equal weekly maximum from masking a
  changed pool or book. Its five focused tests pass. Commit/push it and build
  the final Phase S image before launching Phase S.
- Latest score-blind Phase R poll still has all 30 jobs `Unknown`/active and
  zero explicit failures. Continue with
  `scripts/poll_game_team_usage_phase_r.sh`; do not inspect partial candidate
  or score rows. After all 30 are successful, run the guarded Phase R
  finisher and harvester, follow its mechanically selected law, then launch
  Phase S using the final post-fingerprint immutable image.
- The follow-on multi-seed experiment is now frozen before any Phase R/S
  result in
  `reports/2026-08-13-multiseed-candidate-world-factorial-protocol.md`. It is
  a four-arm exact-80 factorial separating R0-versus-union candidates from
  R0-versus-five-seed worlds, with a tail-first decision and no season veto.
  Existing candidate-total artifacts cannot cross-score a roster in another
  seed's worlds, so the engine now has an opt-in, checksum-covered
  player-id/player-draw payload. Phase S requests it for all ten panels and
  fails the run if its upload fails. The existing effective-rank decoder
  accepts and validates both legacy and extended artifacts; 32 focused tests
  pass. Build a superseding image from this milestone; do not use builds
  `54a0e163-1794-496f-bb85-45dd19d8beb8` or
  `e5588fea-857a-459a-a0a7-ed5920854212` to launch Phase S because neither
  contains the complete player-world contract.
- Phase R finite-K R1/2024 execution `replay-gtrk1-2024-wc8wv` failed after
  provisioning with Cloud Run internal code 14, reported application exit 0,
  and emitted no application logs. Read-only completeness checks found zero
  candidate rows, zero feature rows, and zero score artifacts, so it had no
  partial scientific output. The identical already-deployed immutable job was
  retried once as `replay-gtrk1-2024-r59l9`; the active execution ledger now
  points to that retry and preserves the failed ID/reason in
  `infrastructure_retries.txt`. Poll the replacement with the other 29 jobs;
  do not relaunch the entire panel or query partial scores.
- Phase R finite-K R3/2025 `replay-gtrk3-2025-kxw8x` then failed with the
  identical platform signature (internal code 14, application exit 0, no
  application logs) and likewise had zero candidate/feature/artifact output.
  Its one identical retry is `replay-gtrk3-2025-kmz7l`, recorded in the same
  tracked retry ledger and active execution manifest.
- The artifact-only four-arm multi-seed analyzer, guarded launcher/harvester,
  and Docker packaging are now implemented locally. It verifies every native
  candidate from player draws, reproduces each native selected order,
  cross-scores every union roster in every seed's worlds, and applies the
  frozen exact-80 tail-first decision. Thirty-seven focused Phase S/artifact/
  multi-seed tests pass. Commit/push and run one final full-test build; the
  queued intermediate build `6296a6f2-af03-4434-a786-9df7c5cf860e` was
  intentionally cancelled before consuming compute, and build
  `e5588fea-857a-459a-a0a7-ed5920854212` succeeded but lacks the player-world
  payload and multi-seed analyzer, so neither may launch Phase S.
- Final full-test build `3cea9f4e-e8b0-4649-89a7-55a8777a49a4` succeeded from
  code `1e0bf04` and produced the only Phase S-eligible immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:e6ba5e2ea34ac1a2206ddc3d693fb13549dac53bea5da2d27ce13d153b0720f5`.
  Latest score-blind Phase R poll has three clean successes and 27 active
  executions, including both platform retries, with no current failure. Once
  all 30 succeed, finish/harvest Phase R and invoke
  `scripts/cloud_sis_asoe_phase_s.sh` with that digest and code `1e0bf04`.
- Phase R finite-K R4/2023 `replay-gtrk4-2023-5dkmt` became the third
  original-batch Cloud Run platform failure with exactly the same internal
  code-14/application-exit-0/no-log signature and zero rows/artifacts. Its one
  identical retry is `replay-gtrk4-2023-pkbvk` and is recorded in both the
  active manifest and infrastructure retry ledger. These are platform
  provisioning failures, not failed model executions; do not treat them as
  scientific results.

### 2026-08-13 SIS ASOE Stage A launched

- Superseding full Cloud Build `5c2d59d5-25f1-4b4d-a8dd-3707a255975f`
  passed the complete repository test suite and published immutable image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:d172587c0a45d8e6ebdcec14c941bde022622551ab3dd7f8f54793038e1cd565`
  from code `8226b04`.
- The one frozen score-free ASOE conditional target-allocation gate is now
  running as Cloud Run execution `sis-asoe-allocation-v1-nxhvc`. Its durable
  manifest and execution ID are in
  `reports/sis-asoe-allocation-runs/20260813-sis-asoe-allocation-v1/`.
  It reads the already imported write-once Fantasy Points/SIS BigQuery tables;
  no local vendor CSV is required by the cloud job.
- Exact next action: poll `sis-asoe-allocation-v1-nxhvc` to terminal state,
  run `scripts/cloud_harvest_sis_asoe_allocation.sh` only after success, and
  follow the frozen result. A pass immediately freezes/implements the
  mean-preserving final-served ASOE treatment and runs the exact-80 tail
  comparison; a fail closes only this team-ASOE law and advances the
  player-grain SIS denominator branch. Independently rerun only the repaired
  incumbent seed analyzer against its twelve completed replay tables.
- The guarded analyzer-only repair was subsequently launched as
  `analyze-incumbent-seed-variance-v1-qh9l8` using that same immutable image.
  It expects the original panel code identity `8fb2585`, leaves failed
  execution `analyze-incumbent-seed-variance-v1-kkg6q` intact, and reads the
  twelve already-completed replay tables; no replay or score generation was
  repeated. Poll it alongside ASOE and harvest only after terminal success.

### 2026-08-13 SIS session freshness and ASOE acquisition resumed

- The operator renewed SIS authentication and `sis-download verify-login`
  passed against the protected NFL Player Leaderboards. Historical collection
  is happening now; point-in-time means that a target Week W may use only
  completed Weeks `< W`, not that acquisition must wait until the season.
- The ASOE request ledger now honestly records four identical setup submits
  that reached SIS while the response listener was repaired. None produced an
  artifact, and no historical attempt/performance value was persisted or
  read. The fourth proved that SIS coerces minimum attempts from zero to one;
  missing zero-attempt cells will be reconstructed from the schedule. Before
  any artifact or value read, the protocol was amended from a 26-call to a
  28-call operational ceiling, with the scientific 24-artifact grid and every
  report/alignment/shell/consumed-field/decision unchanged. The ignored
  durable counter is corrected to `4/28`, leaving exactly 24 calls for the 24
  files.
- SIS login now supports `sis-download login --terminal-credentials --fresh`.
  It deliberately signs out, clears the old browser cookies/storage state,
  requires a replacement login, reloads the protected NFL page and saves only
  the newly verified session. `nfl-weekly-data run --week W` invokes this
  fresh SIS login every run before it can proceed unattended. Thirty-six
  focused SIS/weekly-workflow tests, Python compilation and whitespace checks
  pass; operator documentation and the main schedule carry the same contract.
- Fantasy Points exact prior-window Separation by Alignment acquisition
  completed all 56 artifacts and wrote its validated complete manifest at
  `fantasy-points/automated/20260813T202926Z__same-season-alignment-last-four-v1/`.
  Exact next action: commit/push this milestone, resume the SIS ASOE
  downloader on the verified session, finish/validate both manifests, then
  implement and run the frozen score-free conditional-allocation gate.

### 2026-08-13 SIS/Fantasy Points ASOE acquisition passed

- SIS acquisition completed and passed its immutable gate: 24/24 artifacts,
  4,077 team-game/alignment rows, 32 teams, 32,587 Wide/Slot attempts, no
  row-cap/schema/scope/hash/identity failures, and `performance_values_read=[]`.
  Its ignored durable manifest/result live under
  `sis/team-pass-defense-asoe-v1/`; the request ledger finished exactly
  `28/28` including the four documented setup calls.
- Fantasy Points acquisition completed and passed its manifest contracts:
  56/56 exact target Week 5--18 prior windows across 2022--2025, all with
  source Weeks W-4..W-1, Player context and group headers. Its ignored run is
  `fantasy-points/automated/20260813T202926Z__same-season-alignment-last-four-v1/`.
- Before reading any historical player target allocation outcome, the fixed
  score-free construction and gate were registered at
  `reports/2026-08-13-sis-asoe-allocation-stage-a-protocol.md`. It calibrates
  one nonnegative schedule-adjusted Wide/Slot allocation coefficient on 2022,
  evaluates 2023--2025 aggregate target Dirichlet-multinomial likelihood, and
  deliberately reports rather than vetoes on individual-season/bootstrap
  stability. A pass advances to a final-served marginal-preserving exact-80
  tail comparison. A failure leaves the player-grain SIS branch open.
- The fixed importers and Stage A analyzer are implemented. The private,
  write-once BigQuery sources were created as
  `nfl_raw.fantasy_points_alignment_player_l4` (16,482 rows; 16,119 resolved;
  9,452 supported), `nfl_raw.fantasy_points_alignment_team_l4` (1,792/1,792
  supported team windows), and `nfl_raw.sis_alignment_attempt_game` (4,077
  rows, 32,587 attempts). The SIS reader reproduced the acquisition result
  exactly and consumed no performance values. Forty-one focused tests pass,
  including manifest/PIT/partition checks, explicit schedule-spine zero-cell
  reconstruction, opponent-direction geometry and probability-simplex
  preservation. Exact next action: commit/push the implementation, build one
  immutable audit image, run `sis-asoe-allocation`, and follow its frozen
  pass/fail branch without revising the aggregate held-out likelihood gate.
- Implementation commit `e239f79` is pushed on `main`. Its superseded build
  `fb2f7943-7389-4644-9653-afe67439a5ea` was cancelled after the Week-18
  boundary repair; it must not launch an experiment. Superseding full build
  `5c2d59d5-25f1-4b4d-a8dd-3707a255975f` is running for tagged audit image
  `nfl-dfs:asoe-8226b04`; after success, resolve its digest and launch the one
  Stage A execution. The completed seed-panel analyzer's independent nullable-
  boolean repair also passes its five focused tests and is ready to commit;
  rerun only that analyzer after the ASOE launch, never the 12 completed seed
  replays.
- A local outcome-free source-construction smoke found and fixed one scope
  defect after that build began: the schedule spine initially required source
  Week 18 even though the frozen acquisition correctly stops at Week 17.
  Week 18 is now excluded before the source join and covered by regression.
  The real source build yields 1,792 defense-target-week rows, 1,656 supported
  (92.41%), 16 explicit zero alignment cells reconstructed, and supported
  counts 406/425/415/410 in 2022/23/24/25. These are input/support statistics,
  not target-allocation or scoring outcomes. Build a superseding image from
  the scope-fix commit; do not launch Stage A on the earlier image.

### 2026-08-13 SIS ASOE path reopened and acquisition frozen

- The operator-supplied scope challenge is tracked at
  `reports/2026-08-13-sis-schema-gate-scope-challenge.md`; the accepted,
  bounded reconciliation is
  `reports/2026-08-13-sis-schema-gate-scope-challenge-reconciliation.md`.
  The completed team Pass Defense schema failure remains valid only for the
  registered coverage-snap-normalized estimand. It did not test player-grain
  denominators, team Wide-versus-Slot `Att` composition, or conditional
  receiver allocation. The coverage grain-bind/kill list now records that
  exact limit; ASOE is active rather than dead.
- Historical data is available now. "Strictly prior" describes the leakage
  boundary, not a wait for the 2026 season. Before reading any historical SIS
  alignment attempt or score, the exact acquisition was frozen in
  `reports/2026-08-13-sis-asoe-acquisition-protocol.md`. SIS will collect 24
  normal-UI Team Pass Defense Totals artifacts: 2022--2025, disjoint Weeks
  1--6/7--12/13--17, Wide and Slot, all shells, WR targets, all teams, game
  grain. Six-week windows are theoretically at most 192 rows, below the
  200-row cap. Only explicit Submit calls are armed; the 24-call plan has a
  hard durable 26-call ceiling for two identical retries. Only `Att` and
  identity/scope fields may be read at this acquisition gate.
- Matching strictly-prior player alignment routes are frozen in
  `automation/fantasy_points/plans/same-season-alignment-last-four-v1.json`:
  exactly 56 Receiving Separation by Alignment exports across seasons
  2022--2025 and target Weeks 5--18, always source Weeks W-4 through W-1.
  The four manually downloaded full-season summaries remain ineligible for a
  historical target-week join.
- Resumable SIS acquisition/manifests and the outcome-limited acquisition
  analyzer are implemented as `sis-download team-pass-defense-asoe`; licensed
  artifacts remain ignored under `sis/team-pass-defense-asoe-v1/`. Python
  compilation and 55 focused SIS/Fantasy Points downloader tests pass. Exact
  next action: commit/push this protocol and implementation, then launch both
  authenticated historical downloads immediately. On an acquisition pass,
  freeze/implement the ASOE allocation/dependence gate; on its pass, run the
  exact-80 score comparison.
- Independently, the completed 12-run incumbent seed analyzer execution
  `analyze-incumbent-seed-variance-v1-kkg6q` failed mechanically before
  emitting a score report because pandas rejected boolean subtraction in its
  equality helper. The local boolean-safe repair and regression test pass but
  remain uncommitted at this milestone; build and relaunch only the analyzer
  after the SIS acquisition is safely running. Do not rerun the 12 completed
  seed replays.

### 2026-08-13 SIS warehouse/join audit reconciled

- The operator-supplied structural review is tracked at
  `reports/2026-08-13-sis-warehouse-and-join-audit.md`; the code/warehouse
  reconciliation is
  `reports/2026-08-13-sis-warehouse-and-join-audit-reconciliation.md`.
  Outcome-free BigQuery checks independently confirm both SIS raw tables have
  3,230 unique, non-null team-game rows, identical row sets, complete report
  provenance, and a perfect 3,230/3,230 schedule join with matching opponent.
  The strict-prior rolling joins are valid. No completed SIS result, baseline,
  or production policy is invalidated.
- Correct one claim from the source review: both SIS cache arms did compute,
  persist and enforce active-position feature support with an 80% fold floor.
  Exact final-served support is QB 88.85%/88.05%/88.17% and RB
  87.06%/87.22%/87.62% in 2023/24/25. No evaluation rows were dropped and
  these TabPFN generators pass nulls directly rather than using the cited
  median imputer. The omission was confined to concise result prose, so the
  registered failures remain closed and require no rerun.
- Correct a second claim: centralized `src/nfl_dfs/features/leakage.py` has no
  SIS-specific checks. Research helpers/tests do enforce unique keys,
  target-week exclusion, source-week ordering, opponent direction, unchanged
  row counts, support and source identity. If a future SIS arm passes, it must
  still gain a schedule-spined as-of feature for both training and live
  inference plus centralized leakage registration before production. Also
  document the intentional season-boundary policy before the next SIS
  consumer. The misleading raw-table content map is now explicit in both
  ingest module docstrings. No SIS feature currently ships.
- The first schema sampler process stopped safely after four complete Totals
  artifacts; durable state is 5/10 requests because the first Value-view
  transition consumed one identical-scope Submit without persisting an
  artifact. Root cause is now proven from the live page without another
  Submit: the site's Submit serializer derives subtype from the visibly active
  family tab, while the first implementation set only its hidden subtype
  field. The repair activates that exact visible subtype while the guarded
  route is disarmed, verifies both active-tab and hidden identities, and then
  permits only the registered Submit. Twenty-seven focused acquisition tests,
  compilation and an authenticated no-Submit browser check pass. Commit/push
  the repair, then resume the same sample once; it has exactly five requests
  remaining for four Value artifacts. The retired individual-CB sample remains
  untouched at 7/12.
- Incumbent seed jobs remain healthy. A poll bug briefly printed the condition
  type (`Completed`) instead of its boolean status; the fail-closed finisher
  rejected launch and no partial result was read. At the corrected poll, ten
  of twelve were `True`; `replay-mcseedr3-2025-457pw` and
  `replay-mcseedr4-2023-sbf94` were still `Unknown`. Continue polling the
  boolean status, then run
  `scripts/cloud_finish_incumbent_seed_variance_panel.sh` only when all twelve
  are `True`.

### 2026-08-13 SIS team pass-defense schema screen completed

- The frozen outcome-blind team defense-profile sampler finished all eight
  registered 2025 Week 1 views within 9/10 durable requests. Local licensed
  artifacts remain ignored under `sis/team-pass-defense-schema-v1/`; manifest
  SHA-256 is `1516b5b92df642329cce9163110ceaf43424ebf94f2e3011fe31549df320204a`
  and machine-result SHA-256 is
  `4a6d6b1a80f96e723dc5582095c3ea77c6c61d559c8f17e47e82638e3908511a`.
  Concise result is
  `reports/2026-08-13-sis-team-pass-defense-schema-result.md`.
- The exact consumer-UI path **fails and closes**. All scopes were sub-cap,
  Totals/Value team IDs matched per slice, their union covered 32 teams, and
  Value exposed Points Saved/PS Per Play. However, all four team Totals slices
  expose only `Att`, not coverage snaps or targets. The frozen gate required
  both denominators for an opportunity-controlled receiver allocation law.
  Do not substitute `Att`, retry, narrow filters, bulk-acquire history, or read
  performance values for this path. `outcome_values_read=[]`; no dependence or
  lineup score was computed.
- All twelve incumbent seed replays subsequently reached boolean completion
  `True`. The guarded finisher launched immutable analyzer execution
  `analyze-incumbent-seed-variance-v1-kkg6q`. Poll that execution, then run the
  tracked harvester only after it succeeds; do not read partial analyzer logs.

### 2026-08-13 next SIS allocation prerequisite frozen

- With G3 closed and the seed panel still running, the next independent data
  prerequisite is frozen before any response or performance value in
  `reports/2026-08-13-sis-team-pass-defense-schema-protocol.md`. It permits
  exactly eight normal-UI team Pass Defense submits for 2025 Week 1: Wide and
  Slot crossed with predeclared Man and Zone shell sets, in Totals and Value.
  It may inspect only scope, IDs, schemas, row counts and hashes; all outcome
  values are forbidden. The eight-call scientific plan has a hard ten-call
  durable ceiling only for two identical operational retries. A complete
  32-team, sub-cap, matching-identity, denominator/value schema pass licenses
  a separately frozen PIT historical acquisition plan; a fail closes this
  exact consumer-UI path. The retired individual-CB sample remains untouched
  at `7/12`. The guarded sampler and outcome-blind analyzer are now
  implemented: incidental API refreshes are blocked, only visible Submit is
  armed, the counter and partial manifest are durable/resumable, all eight
  filters/subtypes are exact, and only header/scope/identity/hash data reach
  the gate. Twenty-six focused SIS tests, compilation and whitespace checks
  pass. Exact next action: commit/push this implementation before making the
  first live Submit, then run the one immutable sample and follow its frozen
  pass/fail branch without inspecting performance values.

### 2026-08-13 unified Wednesday vendor/Odds workflow

- Branch is `main`; the workflow, G3 result artifacts, and this durable state
  are committed together in the milestone commit that contains this entry.
- The single operator-started weekly acquisition command is now
  `nfl-weekly-data run --week W`, scheduled/documented for every Wednesday at
  10:00am America/Chicago. It verifies the saved Fantasy Points and SIS
  sessions before starting any long work and securely prompts for either
  expired login; after those prompts it can run unattended. A live headless
  validation on this machine opened the protected Fantasy Points Route Share
  report and SIS NFL Player Leaderboards successfully. No credentials or
  browser state are stored in Git.
- The combined run executes the deployed `ingest-odds` Cloud Run job, keeping
  `ODDS_API_KEY` in Secret Manager rather than requiring it in the replacement
  computer's `.env`. This is a supplemental Wednesday snapshot: existing
  `s-odds` remains `0 9,15 * * 3-7` and `s-props` remains `0 11 * * 4`, both
  America/Chicago. `--include-props` is opt-in so a manual run does not
  silently spend extra provider quota.
- Week 1 captures odds plus Fantasy Points matchup reports and automatically
  skips Route Share. From Week 2, the command validates the frozen plan,
  downloads only source Week W-1 Route Share, performs the guarded immutable
  archive/append, and captures/archives QB Coverage, WR Coverage, and OL/DL
  Matchups. Each step is durably recorded in ignored
  `weekly-data-runs/<run-id>/manifest.json`; failures persist before raising.
  If Week W-1 has not posted at 10:00am, retry Wednesday evening and finish
  before `s-features-route` Thursday 6:30am CT.
- SIS is always session-preflighted but the default command makes zero SIS
  data queries. No SIS family has an evidence-approved recurring plan yet.
  Once one passes, check in its bounded plan and add `--sis-plan <path>`; never
  point the weekly command at closed historical tranche plans. The UI Weekly
  guide, main season schedule, and both vendor automation guides carry this
  exact contract. The new Fantasy Points `verify-login` command, workflow
  entry point, fail-closed manifest, plan validation, Cloud execution wrapper,
  and operating-text checks have 45 focused tests passing. Full local
  validation passed 1,117 tests with 2 skipped.
- Full Cloud validation/image build
  `fac7cbe4-d316-423b-8ba7-a6a885cfaa61` passed for workflow commit `4b6b8e9`
  and produced immutable digest
  `sha256:6df3e2d1b21fd93e4ec47fdc98e0ca07f3c9bd88963a8d6eab077e97b528cb32`.
  Only `nfl-dfs-app` was updated, preserving its existing environment,
  secrets and IAP; live revision `nfl-dfs-app-00068-27j` is Ready on that
  exact digest. `scripts/verify_deployment.py` passed the complete adopted
  policy contract. Direct anonymous HTML inspection correctly reaches the IAP
  login rather than protected app content. Scheduled jobs were intentionally
  not redeployed for this desktop-workflow/UI milestone.

### 2026-08-13 G3 image and independent Stage A execution

- Full Cloud Build `85c91487-a191-41ce-ac30-c65848c03493` passed for G3 code
  commit `72420c7`, producing immutable audit image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:17771b0e6a44bf2e2c13b04ecf21a9cc96d6b08ad8b76d5193ea1765fbfa7ae3`.
  The sole preregistered score-free G3 Stage A execution is
  `g3-participation-allocation-v1-tl2cr`, with immutable manifest under
  `reports/g3-participation-allocation-runs/20260813-g3-participation-allocation-v1/`.
  It completed and the immutable report was harvested. Stage A fails and is
  closed: evaluation aggregate mean treatment-minus-control NLL is
  `+0.001568` (worse); carry allocation is `+0.003927` (worse), target
  allocation is `-0.000729` (better), only 2025 improves, and the clustered
  bootstrap 95% interval is `[-0.000133, +0.003293]`. Geometry coverage also
  misses the preregistered 80% floor in every held-out kind-season cell. The
  fitted conditional law was active and PIT-valid, but it is not licensed to
  proceed to dependence or lineup scoring. Do not tune its embeddings,
  coefficients, support threshold, seeds or representation on this result.
- The twelve incumbent Monte Carlo seed replays are still running. A compact
  status read was briefly misinterpreted because the condition type is named
  `Completed` while its value is `Unknown`; the fail-closed finisher correctly
  refused to proceed, and no partial scores were read. Require
  `status.conditions[0].status=True` for all twelve, then run
  `scripts/cloud_finish_incumbent_seed_variance_panel.sh`, poll its analyzer,
  and harvest via the tracked seed-variance harvester.

### 2026-08-13 G3 conditional allocation Stage A frozen

- While the twelve immutable incumbent seed-variance season jobs remain
  active, the next independent score-facing mechanism has advanced without
  reading partial seed outcomes. G3 Stage A is frozen in
  `reports/2026-08-13-g3-participation-conditioned-allocation-protocol.md`.
  The current accepted branch is unambiguous: global Dirichlet
  `K=28.154043586960896` is the control and a strictly-prior
  participation/action embedding-conditioned hierarchy regularized around that
  exact K is treatment. The fixed representation is a 16-dimensional shifted-
  PMI/negative-sampling skip-gram factorization of valid 11-player offensive
  participation with passer/target/rusher context upweighting. Only 2021--2022
  can fit the two kind-specific coefficients; 2023--2025 are held out. Its
  score-free likelihood, coverage, activity and clustered-bootstrap gate must
  pass before G1 dependence evaluation, and G1 must pass before any exact-80
  test. Exact next action: implement and validate the frozen Stage A analyzer
  and immutable runner while polling the seed envelope; do not inspect partial
  seed scores.
- The frozen G3 Stage A analyzer and immutable Cloud launch/harvest path are
  implemented. It loads each 2016--2024 nflverse participation/PBP source only
  once, constructs cumulative strictly-prior embedding folds for target years
  2021--2025, reuses the PIT-clean usage-group/model law, fits only two
  calibration coefficients, and withholds any lineup path unless the complete
  likelihood gate passes. Ten focused G3/usage tests, Python compilation,
  shell parsing and whitespace validation pass. A real 2016 source smoke
  retained 41,286 valid 11-player offensive plays, 1,624 players and 21,778
  weighted edges; its 16-dimensional shifted-PMI factorization embedded all
  1,624 players with unit-normalized rows. Exact next action: commit/push the
  implementation, run the full Cloud test/image build from that exact tree,
  then launch Stage A only from the immutable digest while the seed envelope
  continues.

### 2026-08-13 incumbent numeric path restored before new arms

- TD-ledger v2 fixed the world-order marginal drift but proved that the shared
  sorted-float64 repair changed all 13 frozen incumbent G1 variograms beyond
  the registered `1e-12` control tolerance. Neither TD-ledger run licensed a
  lineup comparison, so the unadopted shared repair has been removed and the
  default replay/live transforms are restored to their pre-`b9c47e6` /
  pre-`89615a6` byte-compatible behavior. The diagnostic code and immutable
  results remain in Git history and artifacts. The decision record is
  `reports/2026-08-13-incumbent-numeric-path-restoration.md`; 48 focused
  blend/replay/served-position tests pass. Any future dependence arm must be
  frozen as an isolated terminal rank permutation of unchanged incumbent
  final-served marginals. It must not alter shared transforms or reinterpret
  TD-ledger v1/v2.
- The currently frozen next marginal arm is the active-QB-only SIS
  offensive-line bundle in
  `reports/2026-08-13-sis-qb-line-context-protocol.md`. Implement its strict
  prior feature builder, paired control/treatment cache generator and
  score-free final-served gate next. Production and the selected scoring
  baseline remain unchanged.
- Operator review
  `reports/2026-08-13-sis-usage-review-and-priorities.md` is tracked and
  reconciled in
  `reports/2026-08-13-sis-usage-review-reconciliation.md`. Its strongest
  recommendation is accepted: after the unchanged QB-line gate, prioritize an
  outcome-blind player-level pass-defense/alignment feasibility sample, retain
  lagged Boom%/Bust% plus volume denominators, and—only if alignment crossing
  is concentrated—freeze a conditional competitive receiver-allocation arm
  against the G0/G1 dependence scorecard. This is distinct from the failed
  diffuse team-shell family and can eventually compose with ledger coupling.
  Corrections: fitted K and the direct role union are current selections, G2
  was a dependence arm, and the 200-row cap requires adaptive team-season/
  window slicing rather than assuming a week-by-team query explosion. The QB
  protocol now predeclares that an MAE/CRPS-only improvement with a Brier-30
  miss closes only its two-column marginal arm, not SIS.
- The frozen SIS QB line arm is now implemented locally: strict same-season
  shift-one last-four features, QB-only attachment, active-only/shared-33
  same-code cache pair, exact inherited-cache reproduction validator,
  licensed replay tables, QB-only walk-forward final-served gate, CLI and
  immutable Cloud launch/harvest scripts. A live read-only warehouse audit
  reconstructed all 3,230 SIS team-games against 102,927 training rows with
  unchanged row count and zero non-QB supported rows. Active-QB support is
  88.54% / 88.95% / 88.43% / 88.43% in 2022--2025, above the frozen 80%
  mechanical floor. Thirty-one focused SIS/team-QB/replay tests pass and all
  new shell scripts parse. The final-served launcher explicitly binds the
  active-label selection's historical source panel
  `20260811-pitclean-e80-k1-role12union-a12ab31`; its selected evaluation panel
  has only 2023--2025 and cannot provide the frozen 2022 calibration fold.
  Exact next action: commit/push this implementation, run a full Cloud Build,
  build the GPU generator image from the same commit, then launch both
  write-once caches and require exact reproduction before the score-free gate.
- Full Cloud validation build
  `bce536c7-6d8b-4900-ba79-9f8dc5dfeca2` passed and produced audit digest
  `sha256:c536b05c33b120cea860fb6d0067192c740a33cfe9fd60461195c039ecd40db5`.
  GPU build `a6f7fbff-50a2-4722-8a26-003d1a1b0943` passed and produced
  `sha256:90e1643723c1f7084cd729b8e24ddb92812f6322602310d6a30f38074a95b91e`.
  Frozen cache executions completed successfully: control
  `tabpfn-sis-qb-line-v1-control-gkzlj` and treatment
  `tabpfn-sis-qb-line-v1-treatment-567t2`. The harvested mechanical gate
  passes every registered check: both tables contain the same 52,307 unique
  target keys over 2022--2025; the control reproduces inherited cache
  `tabpfn_active_label_treatment_v2` with maximum absolute delta `0.0`; the
  treatment predictions changed; and 2023/24/25 active-QB support is
  88.95%/88.43%/88.43%. Their manifest, raw reports and immutable
  `validation.json` are under
  `reports/tabpfn-sis-qb-line-runs/20260813-tabpfn-sis-qb-line-v1/`.
  Exact next action is the now-licensed score-free final-served gate from the
  immutable audit image; do not read lineup scores unless that gate passes.
- SIS tranche-2 resume exposed a new acquisition defect before import. The
  site submits team Passing Value (`MetricGroupSubType=1.3`) correctly but its
  split-by-game Download renders/exports the Totals schema. Fourteen completed
  Passing Totals/Value scope pairs are therefore byte-identical; none is a
  valid Passing Value artifact. The 108-file tranche-1 audit has zero
  cross-view duplicate hashes and exact expected schemas, so the already
  imported SIS QB source and running arm are unaffected. The resumed process
  was stopped at 82/108 local CSV pairs and a durable 337/440 requests. Export
  code now requires exact submitted subtype plus per-report CSV schema
  signatures and waits for both row count and view columns, so stale views
  fail closed. Do not resume the original plan unchanged or import tranche 2.
  Track/quarantine the 14 invalid Passing Value pairs, preserve the request
  counter, and freeze a reduced recovery plan for only missing/valid Passing
  Totals, Rushing Totals/Value and Run Defense Totals/Value. Team Passing Value
  requires a different verified UI workflow or is unavailable at game grain.
  The reduced 22-artifact recovery plan is frozen at
  `automation/sis/plans/team-context-tranche-2-recovery.json` with its own
  92-request ceiling and excludes Passing Value. Combined maximum known plan
  usage is 869 before the small surface audits. Run it only into
  `sis/team-context-tranche-2-recovery`; never reset or reuse the original
  plan state.
- The frozen recovery completed all 22/22 guarded artifacts under
  `sis/team-context-tranche-2-recovery` using 88/92 requests; a second
  validation-only run reverified every CSV/manifest pair without another
  request. This restores all remaining valid Passing Totals, Rushing
  Totals/Value and Run Defense Totals/Value windows through 2025. It does not
  repair or authorize any Passing Value artifact. Before import, implement a
  merged tranche-2 importer that requires the original/recovery exact universe,
  explicitly excludes all Passing Value files, and records both plan/state
  hashes. The combined upper-bound plan usage is now 865, not 869.
- The merged tranche-2 importer is implemented as
  `nfl-dfs import-sis-team-run-context`. It binds both frozen plan hashes and
  both durable state hashes; proves the exact 82-file original stop and the
  exact 22-file recovery; proves all 14 excluded Passing Value artifacts have
  the known byte-identical Totals-schema defect; then merges only the exact 68
  valid original plus 22 recovered artifacts. Audit reproduced a common
  3,230-row / 1,615-game universe for Passing Totals, Rushing Totals/Value and
  Run Defense Totals/Value over 2019 and 2021--2025. Write-once import created
  `nfl_raw.sis_team_run_context_game`; a second write returned
  `already-identical`. Backup snapshot
  `nfl_backups.sis_team_run_context_game_20260813_sisrun` independently has
  all 3,230 rows, and 29 focused SIS/import/backup tests pass. The README data
  deficiency log records the Passing Value defect. Exact next data action:
  run a strictly-prior outcome/redundancy audit of the new run context, with
  special attention to lagged RB Boom%/Bust%, volume denominators and
  opponent Run Defense; freeze a small model arm only if directions/support
  justify it. This does not supersede the higher-priority alignment and
  conditional-allocation feasibility path from the SIS usage review.
- The strictly-prior active-RB audit is implemented as
  `nfl-dfs sis-team-run-context-audit` and interpreted in
  `reports/2026-08-13-sis-team-run-context-feature-audit.md`. It uses
  volume-weighted numerator/denominator sums over four completed same-season
  games, minimum two and shift one. Support is 3,458/3,961 active RB rows
  (87.30%) over 48 evaluation slates. Opponent run-defense Points Saved/play
  has aggregate residual/beat-10/25+/30+ correlations
  `-0.0486/-0.0434/-0.0506/-0.0304`, with residual and beat-10 negative in
  each 2023/24/25 fold. It is moderately distinct from existing opponent
  rush EPA (`r=-0.4531`). SIS opponent EPA is too redundant (`r=0.8029`),
  while offense Boom% is weaker and reverses on important 2025 views. The
  one-column RB-only model question is frozen before treatment output in
  `reports/2026-08-13-sis-rb-run-defense-protocol.md`; YAC, EPA, positive
  rate, Boom% and every offense field are explicitly excluded. The cache
  generator, exact-control validator, licensed replay tables, active-RB
  final-served evaluator, CLI, immutable GPU/audit launchers and harvesters
  are now implemented; 32 focused SIS/import/replay tests pass and all scripts
  parse. Full validation build `a18342e0-85fb-497d-be8e-678be55f99b9`
  passed from immutable source `7a63350` and produced audit digest
  `sha256:c866d39875a81532f209a2e33c16d0a17c538724312efdae2d26dd30a0768267`.
  GPU build `3cd4d6a5-9d24-49ec-bec8-b86d96e86566` passed from the same
  source and produced generator digest
  `sha256:cef2543d77b0632e4cf7e57da6b52a191ceabd851977a97a2d3bf24972664540`.
  The write-once cache pair is running as control execution
  `tabpfn-sis-rb-rdef-v1-control-wpqn6` and treatment execution
  `tabpfn-sis-rb-rdef-v1-treatment-7rb8c`; their immutable manifest is under
  `reports/tabpfn-sis-rb-rdef-runs/20260813-tabpfn-sis-rb-rdef-v1/`.
  Exact next action: poll both executions; when both succeed, harvest and
  require exact inherited-cache reproduction before launching the score-free
  final-served RB gate from the audit digest. Do not inspect lineup scores
  unless that gate passes.
  The first poll instead found that both v1 executions failed before fitting
  or writing a cache: `player_week_training` uses canonical column
  `opponent`, while the new attachment helper expected the replay/audit alias
  `opp`. The shared failure is recorded by those execution IDs and is
  operational, not a model result. The helper now resolves both known schemas
  into a private join key without changing either input contract, with a
  canonical-schema regression test. GPU build
  `c013c82d-324c-4df7-8f69-e53754609a19` passed from repaired source
  `fedeaa8` and produced digest
  `sha256:b8e1520dc2f2ebc6574488c1d90226751868631297bd6861aeb8c6dd1fb77e6e`;
  full validation build `9c9a2f56-280f-4d14-b318-a11ecdbd06c1` remains
  running. After proving both write-once tables were still absent, the v2 pair
  launched as control `tabpfn-sis-rb-rdef-v2-control-mzrgt` and treatment
  `tabpfn-sis-rb-rdef-v2-treatment-smlvr`; immutable manifest is under
  `reports/tabpfn-sis-rb-rdef-runs/20260813-tabpfn-sis-rb-rdef-v2/`.
  Poll and harvest the v2 pair when complete, but do not launch the score-free
  final-served gate until the full build also passes and its digest is bound.
  Both v2 caches completed successfully and their mechanical validation passes:
  52,307 exact matching keys per arm; maximum inherited-control delta `0.0`;
  changed treatment predictions; ordered finite quantiles; and active-RB
  support `87.93%/88.02%/87.84%` in 2023/24/25. Full validation build
  `9c9a2f56-280f-4d14-b318-a11ecdbd06c1` also passed and produced audit digest
  `sha256:e86c6f963bbceca71d8f6cbd15f28c25651b1be75c4947494b604df3dcdee0e0`.
  The final launcher now binds the v2 validation. Launch and poll the frozen
  score-free final-served gate next; do not inspect lineup scores unless it
  passes.
  Conditional exact-80 mechanics are now fixed pre-result in
  `reports/2026-08-13-sis-rb-run-defense-exact80-protocol.md`: exact panel IDs,
  inherited active-only/shared-33/finite-K laws, arm-specific unrounded
  position schedules, strict mechanism invariants and the operator's terminal
  `240..187` first-difference rule. It remains dormant unless the running
  score-free gate passes; no candidate or lineup score may be read otherwise.
  The score-free gate is now running as execution
  `tabpfn-sis-rb-rdef-final-served-v1-lmb74` from that immutable audit digest;
  manifest is under
  `reports/tabpfn-sis-rb-rdef-runs/20260813-tabpfn-sis-rb-rdef-final-served-v1/`.
  Poll it to completion and harvest exactly one machine report. A pass licenses
  only a separately frozen exact-80 comparison; a fail closes this one-column
  arm without reading lineup scores.
  The execution completed cleanly and the immutable score-free report was
  harvested. The arm **failed** its frozen gate: aggregate active-RB Brier-30
  moved `0.0188522320 -> 0.0188536595` (treatment-minus-control
  `+0.0000014275`; lower is better), with paired slate-cluster 95% interval
  `[-0.0000234100,+0.0000262650]`. Point MAE improved about `0.00978`, but
  CRPS, Brier-20 and q90/q95/q99 pinball all worsened. Both arms preserved
  means to approximately `7.11e-15`. No lineup score was read and the
  conditional exact-80 protocol remains permanently dormant for this result.
  The decision record is
  `reports/2026-08-13-sis-rb-run-defense-final-served-result.md`; raw evidence
  is in the final-served run directory. This exact one-column arm is closed.
  The outcome-blind SIS filter audit confirmed exact separate receiving
  alignment and pass-defense receiver/defender alignment controls using three
  UI query calls. The one-game feasibility decision is frozen before sample
  output in `reports/2026-08-13-sis-alignment-feasibility-protocol.md`:
  2025 Week 1 Arizona offense versus New Orleans defense, four WR alignment
  buckets and three CB alignment buckets, Routes/Coverage Snaps only, a hard
  12-query ceiling, and predeclared concentration/overlap thresholds. Implement
  a guarded UI sample acquisition next; do not inspect outcome columns or
  expand to a backfill unless this screen passes.
  The first sampler invocation spent three of its 12 guarded requests but
  created no artifact: opening the Receiving family and Totals subtab consumed
  two intermediate refreshes, leaving insufficient reserve for the seven
  frozen Submit slices. The durable state remains `3/12`; it was not reset.
  The recovery now sets only the exact group/subtype values advertised by the
  visible menu and lets each visible Submit perform the needed refresh, while
  resuming the existing counter. This is a query-efficiency repair only; the
  frozen sample, filters, volume calculations and thresholds are unchanged.
  A second recovery attempt created no artifact and raised the durable counter
  to `5/12` because filter-change refreshes were still metered. The final
  budget-safe repair now blocks all incidental UI API refreshes client-side and
  arms the durable route only around each visible Submit. Exactly seven calls
  remain for exactly seven frozen slices; do not retry unless this guarded
  implementation and its counter test pass.
  The first armed Submit also failed closed before accepting an artifact,
  leaving `6/12`. Operational scope repair
  `reports/2026-08-13-sis-alignment-sample-scope-repair.md` is frozen before
  sample output: Left Slot and Right Slot are now one multi-value Submit because
  the original decision already sums them into a single Slot bucket. Exactly
  six Submit calls remain for exactly six artifacts; no game, identity,
  volume-only calculation, mapping or threshold changes.
  The repaired attempt sent one exact validated Submit payload but received no
  accepted response/artifact, leaving the immutable counter `7/12`. Stop this
  acquisition for now: no raw SIS alignment row has been inspected, so this is
  neither a feasibility pass nor fail. Preserve the private run-state and the
  five remaining requests. Diagnose/replay the response listener with blocked
  networking or defer until the provider weekly counter resets; do not reset
  the local counter or spend another live query speculatively.
  The subsequent outside review
  `reports/2026-08-13-sis-rb-qb-failures-and-alignment-feasibility.md` is
  reconciled in
  `reports/2026-08-13-sis-rb-qb-failures-alignment-reconciliation.md`.
  Independent parsing exactly reproduced its 2025 full-season receiver modal
  alignment shares (WR median `0.67345`, TE `0.54220`, RB `0.85819` for
  players with at least 100 routes). That makes spending the five remaining
  calls on inferred individual-CB crossing low-value, so keep the original
  sample dormant and preserve its state. Do not call it a scientific failure:
  the aggregate file has no defender side, is coarser than the registered SIS
  buckets, and its full-season rows cannot be used as PIT in-season features.
  The revised distinct lead is a separately frozen defense-profile-by-player-
  alignment allocation interaction. It requires a guarded SIS team-view
  schema/cap sample and a new strictly-prior receiver-alignment collection
  before a G0/G1 dependence gate; the failed TD ledger is not an accepted
  component and cannot be composed post hoc.
  In parallel, the already-frozen Fantasy Points QB shell-fit collector's first
  run failed closed before writing a CSV. The rendered filters/table were exact,
  but after the visible Defense-to-Offense context switch the listener still
  awaited the catalog's Defense `/values` route; the site correctly responded
  on the active Offense route. The acquisition-only repair now derives the
  response endpoint from the authenticated page URL while retaining all JSON,
  rendered-table and CSV scope guards. It is documented in
  `reports/2026-08-13-fp-qb-shell-download-context-repair.md`; the failed run
  `20260813T140405Z__same-season-qb-shell-fit-last-four-v1` has zero accepted
  artifacts. Run focused downloader tests, commit/push, then start a new
  immutable 56-export run under the unchanged frozen plan.
  The context repair passed 25 focused downloader tests and was pushed at
  `ee75e58`. Fresh immutable run
  `20260813T141434Z__same-season-qb-shell-fit-last-four-v1` completed all 56/56
  Offense exports with manifest status `complete`. A dry import independently
  validated every manifest hash/schema plus all 168 artifacts in accepted
  Defense run `20260811T053208Z__same-season-coverage-last-four-v1`, yielding
  the exact 1,792-row, 56-window, 32-team source universe. The manifest-locked
  two-source importer and frozen walk-forward diagnostic are implemented along
  with immutable Cloud launch/harvest scripts. They bind the new Offense run to
  accepted Defense run
  `20260811T053208Z__same-season-coverage-last-four-v1`, parse the repeated
  `FP/DB` fields by exact column position, enforce 80-dropback/two-shell support,
  build only the two registered grades, and gate on >=70% coverage plus strict
  aggregate Brier-30 improvement. Forty focused downloader/import/diagnostic/
  backup tests pass and shell syntax is clean. No outcome has been evaluated.
  Write-once import then created
  `nfl_raw.fantasy_points_qb_shell_l4`; a second write returned
  `already-identical`. Warehouse audit independently confirms 1,792 rows, one
  offense run, one defense run, 56 windows, 32 teams and every source ending
  exactly at target week minus one. Backup snapshot
  `nfl_backups.fantasy_points_qb_shell_l4_20260813_fpshell` has all 1,792 rows.
  Implementation/review commit `62d4eb0` is pushed on `main`. Full Cloud
  validation build `c42bb2a2-727a-4880-83ca-8fa0f0da99d1` passed 1,094 tests
  (2 skipped) and produced immutable digest
  `sha256:9aa494e18c6dd2fbd855a200dc5101208f63eeb3279af595fb0430d6e0770ad5`.
  The sole frozen diagnostic completed cleanly as Cloud Run execution
  `fantasy-points-qb-shell-pgnfj`; its manifest and machine report are under
  `reports/fantasy-points-qb-shell-runs/20260813-fp-qb-shell-l4-v1/`.
  Coverage passed at `100.00%/99.30%/99.39%`, but the arm **failed** its
  registered aggregate 30-point Brier gate: `0.0187107295 -> 0.0187176038`
  (treatment minus control `+0.0000068743`; lower is better). Aggregate
  20-point Brier also worsened `+0.0001364522` and residual MAE worsened
  `+0.005205585`; the two shell grades had small, season-unstable descriptive
  correlations. No lineup score was read and no exact-80 comparison is
  licensed. Close this exact two-grade last-four team-shell mechanism without
  tuning. The concise decision record is
  `reports/2026-08-13-fantasy-points-qb-shell-fit-result.md`.
  Follow-up grain review confirms this failure does **not** validate or refute
  the active PFR `cb_ypt_allowed_l6`, `cb_comp_rate_allowed_l6`,
  `db_ypt_allowed_l6`, or `top_cb_out` fields. The first three are opponent
  secondary quality at team/six-game grain; the fourth is current CB1
  availability. The tracked grain-bound taxonomy and shell-proxy kill-list
  seed are in
  `reports/2026-08-13-coverage-grain-bind-and-kill-list.md`. A current-stack
  four-cache ablation is now frozen before treatment output in
  `reports/2026-08-13-pfr-secondary-drop-features-protocol.md`: unchanged
  control, drop three rates, drop `top_cb_out`, and drop all, with the combined
  branch declared now. It requires exact inherited-control reproduction and a
  score-free aggregate active-player Brier-30 improvement before one
  predeclared branch can reach an exact-80 tail-grid comparison. Genuine named
  WR/CB assignment remains data-blocked rather than disproven. Exact next
  action: implement the write-once cache generator/validator and final-served
  evaluator without reading any treatment output.
  That implementation is now complete and outcome-blind: immutable GPU cache
  generation/validation lives under `scripts/tabpfn_pfr_secondary/` plus
  `scripts/cloud_*tabpfn_pfr_secondary*`; the coordinated LightGBM + TabPFN
  final-served evaluator is
  `src/nfl_dfs/analysis/tabpfn_pfr_secondary_final_served.py`. The mechanical
  validator requires bit-for-bit control equality with
  `tabpfn_active_label_treatment_v2`, exact 52,307-key equality, exact declared
  feature subtraction and distinct changed treatments before the score-free
  job is licensed. The final-served evaluator applies the same `DROP_FEATURES`
  law to component models and the matching cache, independently refits each
  arm's walk-forward position factors, evaluates all active QB/RB/WR/TE rows,
  and applies the frozen lowest-Brier/tie-order choice. Focused tests pass;
  no cache or treatment outcome existed at this milestone. Implementation
  commit `50a20b1` is pushed on `main`. GPU image build
  `87ec1e8f-15d4-4ad0-b720-34094473360e` passed and produced immutable digest
  `sha256:e5d0e06b183afec2873a2a810557c3fa7008e2c82d8e1d67a3a83ac8e764e668`.
  Full-test application build `da65723a-fc0f-4b9e-9972-fbac9b3f8440` is in
  progress. Four cache executions were launched without reading treatment
  logs: control `tabpfn-pfr-secondary-ctl-wsjkp`, rate drop
  `tabpfn-pfr-secondary-rates-44qvk`, availability drop
  `tabpfn-pfr-secondary-topcb-nl28w`, and combined drop
  `tabpfn-pfr-secondary-all-nfw5s`. Their immutable manifest is under
  `reports/tabpfn-pfr-secondary-runs/20260813-tabpfn-pfr-secondary-v1/`.
  Before any cache log or outcome was read, the final-served no-drop replay
  was also bound to the inherited panel mean-parity check in
  `reports/2026-08-13-pfr-secondary-control-parity-addendum.md`; this is a
  mechanical abort check and does not change the frozen outcome gate.
  Exact next action: poll all four executions and the full-test build; only
  after clean completion run `scripts/cloud_finish_tabpfn_pfr_secondary.sh
  50a20b1`. Launch the score-free job only if that mechanical validation
  passes.
  All four cache executions then completed cleanly and mechanical validation
  passed in full. The tracked raw records and `validation.json` are under the
  same run directory. Control is bit-for-bit equal to inherited
  `tabpfn_active_label_treatment_v2`; all arms have the exact same 52,307
  unique keys and finite ordered quantiles; declared feature subtraction is
  exact; and every treatment is changed and mutually distinct. This licenses
  the score-free comparison but reveals no forecast outcome. Full-test build
  `da65723a-fc0f-4b9e-9972-fbac9b3f8440` passed for the original implementation
  and produced digest
  `sha256:c9a548337c42574d6b2e47536a3712d0410ec5a514d01712d9a10551e7b22ebf`.
  Parity-hardened full-test build `2e1b52b4-9ccb-48ec-87cb-f599d19019e3`
  passed and produced immutable digest
  `sha256:69d7ff1a7857c6fe5717ecd5ca5318126eb084c595074f20196197186700968e`.
  The sole score-free final-served comparison is running as durable Cloud Run
  execution `tabpfn-pfr-secondary-final-served-v1-rgvmc`; its manifest is
  under
  `reports/tabpfn-pfr-secondary-runs/20260813-tabpfn-pfr-secondary-final-served-v1/`.
  No partial metric has been read. Exact next action: poll that execution; on
  clean completion run
  `scripts/cloud_finish_tabpfn_pfr_secondary_final_served.sh`, then follow its
  frozen branch-selection result. No eligible arm means close/retain; exactly
  the machine-selected eligible arm licenses one exact-80 comparison.
  That execution failed before any structured report or treatment replay:
  the added no-drop assertion compared active-only forecasts to the pre-
  adoption source panel and raised `Route control post-shaper mean differs` in
  the 2022 control fold. The accepted active-label evaluator records that
  panel parity as intentionally false; the valid cache-level identity already
  passed bit-for-bit. Failure provenance is retained in `invalid_raw_log.txt`,
  and the outcome-blind narrow repair is frozen in
  `reports/2026-08-13-pfr-secondary-control-parity-repair.md`: restore the
  accepted evaluator's `require_control_parity=false` while preserving every
  arm, row, forecast gate and branch rule. Exact next action: full-test/build
  a new immutable repair image and launch exactly one repair execution using
  the same validated caches, without reading partial output.
  Repair commit `8ee7387` is pushed. Cloud full-test build
  `707244eb-881b-4f07-b8d6-e0592f278759` passed and produced immutable digest
  `sha256:e2149e596e7cb58c6e59d466205c4c9b3202ed38f1e94672ad507e6619316305`.
  The single repaired execution is running as
  `tabpfn-pfr-secondary-final-served-v1-f2zrw`; its repair manifest and durable
  ID are in the same final-served run directory. Exact next action: poll it;
  after clean completion harvest only its structured report with the frozen
  finish script and follow the machine-selected branch.
  That execution completed cleanly at `2026-08-13T16:46:20Z`, but the local
  harvester found that Cloud Logging truncated the single report line at
  exactly 102,400 bytes, leaving invalid JSON. The retained record is now
  `truncated_raw_log.txt`. Diagnosis necessarily exposed the already-computed
  top-level disposition `tabpfn-pfr-secondary-final-served-no-eligible-drop`:
  all three drops had worse aggregate active-player 30-point Brier than
  control. Do not treat this as terminal until the complete fold, position and
  uncertainty report is harvested. The frozen transport-only repair is
  `reports/2026-08-13-pfr-secondary-report-transport-repair.md`: canonical
  gzip/base64 chunks of at most 48,000 characters with compressed and
  uncompressed SHA-256 identities, plus a strict all-chunk harvester. No arm,
  row, seed, cache, fit, factor, metric, gate or branch changed. Focused tests,
  shell syntax and compilation pass. Transport rerun launcher
  `scripts/cloud_rerun_tabpfn_pfr_secondary_final_served_transport.sh` now
  binds the completed scientific execution, exact 102,401-byte retained log
  identity, all original selections/caches, and the new immutable image in a
  write-once manifest. The harvester accepts only that new execution, rather
  than accidentally rereading the already-truncated repair execution. Exact
  next action: commit/build this narrow repair, run the deterministic
  score-free task once from the new immutable image, then harvest the complete
  report. No exact-80 branch is currently licensed.
  Provenance-binding repair commit `5502f90` is pushed on `main`. Full-test
  immutable transport build `dc36bc56-e291-46ab-9761-e2270ec2156e` passed and
  produced digest
  `sha256:7ee3c5c30b21939b07dbefb9660b23b25e1c1684ecf9ce078c35c0521b24fbfe`.
  The sole transport-only deterministic rerun is active as Cloud Run execution
  `tabpfn-pfr-secondary-final-served-v1-w4k8f`; its write-once manifest binds
  prior completed execution `tabpfn-pfr-secondary-final-served-v1-f2zrw` and
  exact truncated-log identity. Exact next action: poll `w4k8f`, harvest the
  complete chunked report on success, then close or follow the frozen branch.
  The execution subsequently completed and the strict harvester reconstructed
  the complete checksum-bound report. All three registered drops worsened the
  primary aggregate active-player Brier-30 versus control `0.017203317646`:
  drop-rates `+0.000003420242`, drop-`top_cb_out` `+0.000011806401`, and
  drop-all `+0.000022000121`. Each arm preserved means within `7.11e-15`, but
  none passes the frozen point-estimate gate. The terminal disposition is
  `tabpfn-pfr-secondary-final-served-no-eligible-drop`; no exact-80 score was
  read or licensed. Retain the four fields and close these exact ablations.
  The concise decision record is
  `reports/2026-08-13-pfr-secondary-drop-features-result.md`.
  To stop score-free/data prerequisites from serializing outcome-facing work,
  the already-frozen corrected-history extreme-selector confirmation was
  independently bound to its original final corrected source panel
  `20260810-lockfix-e80-k1-role12union-8677d21` and immutable preregistered
  image `sha256:370695d6...34fce`. Cloud Run execution
  `corrected-extreme-selector-cjqq6` is active. It is the one allowed 107-slate
  same-pool exact-80 comparison of persisted 194 coverage against the frozen
  220->210->200 selector. Poll/harvest that execution without changing its
  source, thresholds or tie rules.
  The execution completed successfully and all mechanical checks passed. The
  persisted 194 selector versus extreme selector grids at
  240/230/220/210/200/194/187 are `2/3/5/7/11/22/34` versus
  `2/3/5/6/12/22/34`; means are `180.1207` versus `179.6650`. The books tie
  through 220, then the extreme selector loses one >=210 week, so its one
  additional >=200 week cannot override the first registered difference.
  Paired weekly maxima are 10 wins, 76 ties and 21 losses. Terminal disposition
  is `keep-coverage194-selector`; do not tune this selector. Decision record:
  `reports/2026-08-13-corrected-extreme-selector-result.md`.
  A separately labeled current-stack replication was frozen after that
  original result but before querying terminal panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`; protocol is
  `reports/2026-08-13-current-stack-extreme-selector-replication.md`.
  Full-test Cloud Build `635a1c70-9854-45bd-81cb-988e1515fca6` passed from
  source `262c96d` and produced immutable digest
  `sha256:0d766c187f493c240cd6a5524c53b1a1236b4a32e30caa3843ad5c8d2b6080b5`.
  The unchanged 220->210->200 law is now running across the 54 terminal
  2023--2025 slates as Cloud Run execution
  `current-extreme-selector-replication-95mnt`. A loss/tie closes it; a win
  still requires the already-frozen mask/seed stability check before any live
  selector change. Poll and harvest with
  `scripts/cloud_finish_current_extreme_selector_replication.sh`.
  The execution completed successfully and all mechanics passed. Persisted
  194 versus extreme grids at 240/230/220/210/200/194/187 are
  `0/0/0/2/6/8/11` versus `0/0/0/1/5/6/9`; means are `170.9070` versus
  `170.9893`. The first registered difference is the lost >=210 week. Paired
  weekly maxima are 11 wins, 30 ties and 13 losses. Terminal disposition is
  `keep-coverage194-selector`, matching the older-universe rejection. Close
  historical 220-first selector variants; result record is
  `reports/2026-08-13-current-stack-extreme-selector-result.md`.
  The operator-supplied Monte Carlo review is tracked as
  `reports/2026-08-13-monte-carlo-review-and-seed-variance-protocol.md` and is
  being reconciled against the actual multi-stream RNG path. The first
  outcome-free support audit is decisive: on terminal active-label panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`, every one of 13,750
  candidates has fewer than 30 supporting worlds at both 210 and 220; median
  support is one world at 210 and zero at 220, and 61.738% have zero 220
  worlds. Selected candidates average 15.341 supporting worlds at 194 but
  only 0.781 at 220, and 42.25% of selected candidates have zero 220 support.
  This is a serious warning for the prospective 220-first selector, not
  evidence against the adopted 194 selector. The corrected review, durable
  audit, and five-replicate incumbent protocol are now frozen in
  `reports/2026-08-13-monte-carlo-review-reconciliation.md`,
  `reports/2026-08-13-incumbent-tail-mask-support-audit.md`, and
  `reports/2026-08-13-incumbent-seed-variance-protocol.md`. The protocol binds
  the actual two active RNG streams: incumbent `(0,7331)` plus four declared
  baseline/role pairs, with all nonseed laws held fixed. It cannot relabel old
  arms. The explicit `REPLAY_PROJECTION_SEED` implementation is now complete:
  unset remains legacy seed 0; explicit nonnegative values reach
  `replay_projections`; and explicit seeds are recorded in both `lever_env` and
  `seeds` beside `ROLE_BELIEF_SEED`. Focused replay, generation-config and
  persistence tests pass, including default-zero and changed-seed assertions.
  The seed-0 parity gate is also implemented. It persists one explicit-zero
  2024 main slate and uses the strengthened exact-replay comparator in
  candidate-slate-only mode against the accepted panel. The comparator now
  includes 210/220 masks and all currently served component/ensemble/coverage/
  route fields, plus exact score artifacts; no reduced summary can satisfy the
  gate. Nineteen focused seed, persistence, runner, and exact-comparator tests
  pass and shell syntax is clean. Exact next Monte Carlo action: commit/build
  this narrow lever, run the explicit-zero smoke and require exact parity,
  then run only the four registered 2023--2025 panels after PFR transport
  closure.
  Full-test Cloud Build `79fbcef4-ee0a-4390-995c-0c8b2249ae1f` passed from
  packaged implementation source `8fb2585` and produced immutable digest
  `sha256:248bb8edd08625b1c6af7d3fc339662975131363d2b31d806c7eea5e32468c82`.
  The explicit seed-0 one-slate parity replay is active as Cloud Run execution
  `replay-mcseed-zero-parity-s9vps`; its write-once manifest is under
  `reports/panel-runs/20260813-incumbent-seed-zero-parity-v1/`.
  Poll/finish it next. Only exact parity licenses the four new seed-pair
  season panels.
  The replay completed successfully and exact comparator execution
  `compare-exact-replay-hmbpg` passed with zero failures; the explicit-zero
  staging slate reproduces the accepted incumbent under the strengthened
  candidate/player-feature/210-220-mask/score-artifact contract. All twelve
  licensed nonzero-seed jobs are now launched concurrently from the same
  digest: R1 `replay-mcseedr1-2023-bmgsd`,
  `replay-mcseedr1-2024-s86n9`, `replay-mcseedr1-2025-6xbzc`; R2
  `replay-mcseedr2-2023-phg9m`, `replay-mcseedr2-2024-9qdb7`,
  `replay-mcseedr2-2025-th5ss`; R3 `replay-mcseedr3-2023-95rzq`,
  `replay-mcseedr3-2024-44tk5`, `replay-mcseedr3-2025-457pw`; and R4
  `replay-mcseedr4-2023-sbf94`, `replay-mcseedr4-2024-thmjx`,
  `replay-mcseedr4-2025-srm7p`. Their frozen manifest and execution lists are
  under
  `reports/incumbent-seed-variance-runs/20260813-incumbent-seed-variance-v1/`.
  Poll all twelve without inspecting partial scores; after every clean
  success, launch the single frozen analyzer with
  `scripts/cloud_finish_incumbent_seed_variance_panel.sh`.
  The post-parity path is also implemented before any output: fixed R1--R4
  launch wrappers, twelve durable season executions, and one Cloud analyzer
  that withholds the five-replicate tail report unless all panels have exact
  slate/entry/world/label/seed/nonseed-lever/stable-feature checks and each
  nonzero seed materially changes candidates. Its frozen report includes both
  selected and oracle tail envelopes, per-slate selected-roster overlap,
  candidate-pool Jaccard, selected mask support, and week-level score ranges.
  Pre-build review corrected two outcome-blind implementation defects: overlap
  now canonicalizes player IDs inside each same-slate roster, and the R1--R4
  launcher starts the twelve season executions directly after the one shared
  parity gate instead of serializing four redundant generic preflights. Three
  focused analyzer tests pass; all new shell scripts parse cleanly.
  Implementation commits are `84e0aea` (seed lever), `e0737c9` (exact parity
  gate), and `48237b5` (four-replicate launcher/analyzer), all pushed on
  `main`. Builds `7cd6d49f-1ec6-4288-9f55-c3c8ee4a0d05`,
  `708c345d-39fc-4e9a-a381-aae443375854`, and
  `974845fc-29f2-4062-9982-965bb9877872` were cancelled before use after
  pre-execution reviews found mechanical issues; none is a valid
  seed-envelope image and neither launched a replay. The first correction is
  pushed at `a216d8c`; a second correction now uses the repository's validated
  comma-bearing `lever_values` parser, rather than splitting role-feature and
  position-scale values on commas. Four focused analyzer tests pass. Commit
  that correction and run a fresh full-test build; on success, run only the
  explicit seed-zero parity smoke first. Use no earlier seed-envelope tag.
  Parser correction commit `98ffe4e` is pushed. Final packaging review then
  found that the Dockerfile's explicit script allowlist omitted the new seed
  analyzer; the third build was cancelled before use and no replay launched.
  The analyzer is now copied into the image. Commit and run a new full-test
  build from this exact tree.
  Packaging correction `8fb2585` is pushed. Replacement full-test build
  `79fbcef4-ee0a-4390-995c-0c8b2249ae1f` is queued for immutable tag
  `mcseed-8fb2585`; no earlier seed build may be used.
  The outside oddsmaking proposal
  `reports/2026-08-13-oddsmaking-techniques-and-market-implied-dependence.md`
  is reconciled in
  `reports/2026-08-13-market-implied-dependence-reconciliation.md`. Its joint-
  probability algebra is useful, but an SGP payout haircut inflates rather than
  compresses a naively inverted multiplier; one joint quote cannot be
  conventionally de-vigged; and passing/receiving-yard overs are not G0's
  player-DK-q90 events. The official Odds API market surface and current
  importer expose individual/alternate props, not SGP quotes or correlation
  factors. Preserve this as a prospective product-availability inquiry without
  quota spend. If a licensed source exists, require fair-probability metadata
  or empirical held-out quote calibration and compare the simulator on exact
  matched prop events before any fitting/live use. This review changes no
  baseline or model.
- The SIS QB-line cache mechanical gate passed and the score-free
  final-served execution
  `tabpfn-sis-qb-line-final-served-v1-vkx49` completed from audit image
  `sha256:c536b05c33b120cea860fb6d0067192c740a33cfe9fd60461195c039ecd40db5`;
  its immutable report is under
  `reports/tabpfn-sis-qb-line-runs/20260813-tabpfn-sis-qb-line-final-served-v1/`.
  It **failed** the frozen Brier-30 gate, `0.0463863454 -> 0.0464094132`
  (treatment minus control `+0.0000230678`; paired slate-cluster CI
  `[-0.00007963,+0.00012577]`). No lineup score was read. The expected
  marginal-versus-tail pattern occurred: MAE improved `0.0109370`, CRPS
  improved `0.0049238`, and Brier-20 improved `0.0003108`, but the registered
  30-point event did not. The exact two-column arm is closed; SIS alignment,
  conditional allocation and the separately frozen RB run-defense arm remain
  open. Concise interpretation is
  `reports/2026-08-13-sis-qb-line-final-served-result.md`.

Active branch is `main`; point-in-time audit reconciliation and dynamic
leakage-check expansion commits through `7304cfc`, the active-label result and
frozen protocol commit `3966764`, and exact-80 tooling commit `8e3bbb8` are
pushed. SIS strictly-prior audit implementation and paid-surface inventory
commit `d75af8b` is committed locally and is included in the next handoff push.
The
position-calibration result, research promotion, live-policy adoption and
validated production rollout described below remain the deployed milestone.
Advanced Receiving
diagnostic implementation commit `5aee8aa` and negative result commit
`6137bad` remain pushed historical records; that exact vendor arm is closed.
The program-review reconciliation is finalized in this milestone.
The paired Route Share live-shadow implementation commit `9e34565` and its
Thursday post-download scheduler follow-up `b6dbc5e` are also pushed on
`main`. Comparator-only fitted-K gate repair commit `079de22` is pushed. The
ten previously supplied outside-review documents
`reports/2026-08-10-scoring-strategy-recommendations.md`,
`reports/2026-08-11-deep-analysis-calibration-and-data-audit.md`,
`reports/2026-08-11-end-of-program-forensic-analysis-plan.md`,
`reports/2026-08-11-fantasy-points-data-utilization.md`,
`reports/2026-08-11-feature-plumbing-defects-and-correlation-gaps.md`,
`reports/2026-08-11-graph-clustering-and-technology-options.md`,
`reports/2026-08-11-graph-queue-review-notes.md`,
`reports/2026-08-11-pit-join-and-accuracy-code-audit.md`,
`reports/2026-08-11-post-window-program-review.md`, and
`reports/2026-08-11-recommendation-scoreboard-and-pivot.md` are tracked. Treat
operator-supplied source reviews as immutable inputs; track a separate
reconciliation when their findings affect the program.

### 2026-08-13 coverage-source audit and active next mechanism

- The current selected scoring baseline is unchanged: active-only TabPFN,
  finite Dirichlet `K=28.154043586960896`, and selected weekly maxima counts
  at 240/230/220/210/200/194/187 of `2/2/2/6/14/23/35`, with mean weekly
  maximum `176.8692`. No result in this milestone changes production.
- Weekly coverage alternatives were researched and recorded in
  `reports/2026-08-13-weekly-coverage-data-source-audit.md`. Free nflverse
  participation files contain play-level man/zone and named coverage shells;
  direct checks found 18,975 / 22,916 / 22,408 / 22,055 populated shell rows
  for 2022--2025. They are useful historical diagnostics, but nflverse states
  2023+ FTN participation arrives after the postseason, so this is not a live
  2026 feed and the NGS-to-FTN source break must remain explicit. FTN is the
  Football Outsiders/DVOA successor but arbitrary consumer CSV export remains
  unverified. SIS DataHub Pro is the strongest paid live/export candidate
  under the operator's budget ($99.99/month, seven-day trial); do not purchase
  until the report's history/export/latency/identifier checks are confirmed.
  Follow-up trial due diligence found that SIS trial leaderboards are capped
  at 20 rows (paid leaderboards at 200) and the agreement caps 1,000 queries
  per week. The operator clarified that SIS offers one combined NFL/college
  trial, not an NFL-only trial, and asked that licensing review not block the
  technical evaluation. Raw exports remain private and gitignored.
  The exact smoke-export, schema and purchase checklist is tracked in
  `reports/2026-08-13-sis-datahub-trial-checklist.md`; it now includes a
  compact CFB audit of historical depth, stable identifiers, filtered exports,
  coverage fields, injuries, line play, pace and update latency. SIS materials
  claim every-FBS-game coverage, Universal Player IDs and consistent NFL/CFB
  filters; the trial must verify those claims in CSVs. This complements but
  does not change the existing collection-only CFB scaffold or authorize a CFB
  model. A cheaper
  CoverageIQ alternative was also found, but its published terms explicitly
  forbid automated extraction and ML/AI ingestion, so it is not a model data
  source.
  The operator started the combined trial and supplied the first raw export at
  `sis/2025-pass-defense.csv`; `/sis/` is now root-gitignored. Audit report
  `reports/2026-08-13-sis-first-export-audit.md` records its hash and schema
  without committing vendor rows. The CSV confirms useful defender volume and
  outcome fields but is only the 20-row trial cap, has broken literal Rank
  values, lacks week/game/opponent/stable ID, and still contains season totals
  (`Games=12..17`) despite the visible Split-by-Game check. Exact next user
  smoke: 2025 Week 1--1, Split by Game, press Submit, verify rendered
  `Games=1`, then download `sis/2025-week01-pass-defense-all.csv`.
  The first retry was byte-identical only because Submit had not been pressed.
  Correctly submitted `sis/SIS DataHub - NFL.csv` (hash recorded in the audit)
  passes the game-grain smoke: explicit Week/Opponent, all `Games=1`, 12 weeks,
  values changed, no duplicate player/team/week key. It remains only the top
  20 player-games, lacks stable IDs, and has broken Rank. The exact workflow is
  change filters -> Submit -> verify rendered table -> Download. Remaining
  purchase question: whether paid/API output can return every qualifier rather
  than top 200.
  Purchase decision: take only the `$99.99` NFL month. Do not pay `$199.99`
  for NFL+college now; the combined trial established future CFB potential,
  but college remains deferred to the existing 2027 go/no-go path. Build the
  Playwright acquisition workflow for NFL only, with persistent-session,
  mandatory-Submit, rendered-scope, stale-download, row-cap and completeness
  guards.
  SIS login tooling is pushed through `e68da11`. It deliberately standardizes
  on the secure terminal-credentials flow used for Fantasy Points. SIS's main
  identity cookie is session-scoped, so a normal persistent Chromium shutdown
  removed it despite Remember Login; the repaired command captures Playwright
  storage state outside the repo before closing. Fresh headless verification
  passed at 03:37 CDT and reached the protected NFL Player Leaderboards URL.
  No further operator authentication is currently required. Continue the
  guarded NFL-only exporter using that external state; never log or commit it.
  The paid subscription surface is now fully inventoried in
  `reports/2026-08-13-sis-nfl-subscription-inventory.md`: Player and Team
  Passing/Rushing/Receiving/Pass Defense/Pass Rush/Run Defense expose
  Totals/Rates/Value; Blocking adds Overall, Runs to Gap and Adjusted Blown
  Blocks; special teams is lower-priority. Proprietary Value views include
  Points Earned/Saved, PAA, EPA, PAR, WAR and boom/bust. Coverage/route/
  alignment/pressure/run-concept/box/technique/personnel filters are available,
  with history back to 2015. `sis-download catalog` and guarded single-export
  support are implemented. A real paid smoke for 2025 Week 1 player
  pass-defense Value, team ID 1, passed end-to-end with 11 API/CSV rows, exact
  submitted scope, API `Games=1`, rendered/download parity and hash manifest.
  The raw licensed artifact remains gitignored under `sis/smoke-v4/`. An
  unsliced Week 1 pass-defense query returned exactly 200 rows, proving the
  paid cap is binding; exporter therefore fails closed at 200 and requires
  team/week splitting. Priority is team/player pass-game, coverage, pressure
  and blocking Value plus volume denominators, followed by rush/run defense;
  same-week data remains forbidden.
  Declarative plan parsing now expands seasons/week windows/report bundles,
  rejects duplicate artifacts and fails when expansion exceeds the declared
  budget. `automation/sis/plans/team-context-tranche-1.json` validates to 108
  guarded team-context exports: six replay seasons x three six-week windows x
  pass-defense/pass-rush/blocking totals and value. Resumable normal-UI bulk
  execution is implemented with a durable per-plan API-request counter, a hard
  browser-route ceiling, a four-request reserve before each artifact, verified
  restart skips, and stable SIS identity rows from the exact submitted API
  response in each local manifest. Fourteen focused SIS tests pass. A broader
  authenticated surface audit also added explicit Runs to Gap (group 15) and
  Adjusted Blown Blocks (group 17) catalog entries; these remain priority 2
  behind the initial broad team context tranche. The audit itself made a small
  number of ordinary UI requests. Tranche 1 then completed all 108 artifacts
  under gitignored `sis/team-context-tranche-1/`, using 440/500 planned API
  requests; every artifact has its verified scope/hash/identity manifest and
  no exact-200 result was accepted. The audited importer reconstructs one
  complete 3,230-row / 1,615-game table over 2019 and 2021--2025, with both
  sides of every game and exact team-game universe equality across all six
  report families. It preserves duplicate SIS blocking headers positionally,
  normalizes percentages, canonicalizes all historical WAS names, and is
  audit-only unless `--write` is explicit. Backup discovery now includes all
  private `sis_*` base tables. Twenty-four combined SIS/backup tests pass.
  Write-once import created `nfl_raw.sis_team_context_game` with exactly 3,230
  rows. Backup verification created
  `nfl_backups.sis_team_context_game_20260813_sisctx`; the backup invocation
  had zero failed tables. The durable intake record is
  `reports/2026-08-13-sis-team-context-intake.md`. Exact next SIS action: build
  a strictly-prior correlation/redundancy audit before freezing small feature
  bundles. Bounded tranche 2 is frozen in
  `automation/sis/plans/team-context-tranche-2.json`: team Passing, Rushing
  and Run Defense Totals/Value for the same seasons, 108 artifacts and a hard
  440-request ceiling. Team Receiving remains next-week priority because it
  overlaps Passing more than the chosen run-context bundle; granular
  gap/player/special
  teams remain deferred. Do not exceed the subscription's 1,000-query weekly
  allowance.
- The reproducible tranche-1 audit is now implemented as
  `nfl-dfs sis-team-context-audit`; the concise result is
  `reports/2026-08-13-sis-team-context-feature-audit.md`. It constructs seven
  four-completed-game features with `shift(1)`, minimum two prior games and
  explicit source-week checks, then attaches both the player's offense and
  opponent to terminal panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`. Target-week mutation and
  strict-prior tests pass. A broad-population first run was discarded before
  arm freeze because it included inactive zero rows; the corrected v2 audit
  uses the exact `was_active=true` gate population. It contains 15,396 active
  rows, of which 13,476 (87.53%) have strict-prior SIS support over 48 slates.
  This is explicitly exploratory/adaptive and does not license model or lineup
  scoring.
- Outcome-blind redundancy shows SIS pass-defense EPA is mostly duplicative of
  existing opponent EPA (`r=0.8803`), while SIS pressure is more distinct
  (`r=0.4573`). The clearest outcome-viewed lead is a fixed two-feature QB
  offensive-line bundle: pass blown-block rate has residual/beat-10
  correlations `-0.0485/-0.0649` and both are negative in 2023/24/25;
  blocking Points Earned/play is `+0.0359/+0.0442`, with beat-10 positive in
  all three seasons but residual slightly negative in 2025. RB run blown
  blocks and blocking value also have stable
  directions, but the RB decision is held until direct tranche-2 run context
  is complete. Broad WR defense effects are too small; future WR/TE work
  should use a separately frozen coverage/alignment split design. Twenty
  focused SIS acquisition/audit tests pass. Any chosen feature bundle still
  requires a frozen score-free walk-forward model protocol before output.
- Tranche 2 is resumably paused, not lost. It has 50/108 verified CSV/manifest
  pairs through 2022 weeks 13--18 Passing Value under
  `sis/team-context-tranche-2/`; durable state records 206/440 API requests.
  A controlled retry stopped clearly at HTTP 429 on artifact 51, with no
  partial artifact accepted. Do not reset the state or retry rapidly; allow
  SIS's rate window to cool and resume the same plan. Tranche 1 used 440
  requests, so known plan usage is 646 plus the bounded surface audits, still
  below the documented 1,000-query weekly allowance.
- The paid-surface inventory now distinguishes included navigation from
  adjacent SIS products. The authenticated account exposes Player/Team
  Leaderboards and Player/Team Lookup. Injury data, weekly projections,
  tendency reports, on/off splits, participation/frame-timer feeds and
  player/snap projections are advertised by SIS but are not visible as
  included download surfaces; public materials list weekly projections as a
  separate subscription. Do not assume access. The highest-value remaining
  included data are predeclared filtered views: QB pressure/coverage splits,
  receiver man/zone/alignment/coarse-route splits plus defensive shell
  deployment, followed by Runs to Gap/box/concept and Adjusted Blown Blocks.
  Punting/returning are lower-priority DST diagnostics and kicking is lowest
  because DraftKings classic has no kicker slot. Freeze compact plans before
  making requests; never issue a combinatorial filter sweep.
- Incumbent effective-rank v2 completed cleanly in execution
  `portfolio-effective-rank-v2-pbxps`, image
  `sha256:450f22cbdae94e23c8322330fe3f445d256cd82dbfc96ca086593a0f80eee90e`,
  source `f4ccbcf`, build `399e8bb1-5117-43c3-ae38-af6420a1a8c4`.
  The valid 107-slate selected-80 mean raw/deflated correlation participation
  ranks are `11.8749/20.3979` (entropy rank `31.3393`), versus random-80
  `4.9952/13.6646`. This is score-free evidence that selection adds useful
  tail/diversity structure, but the simulator's unresolved QB-receiver miss
  likely makes its independent-bet count optimistic. Full result and machine
  artifacts are tracked under
  `reports/portfolio-effective-rank-runs/20260813-incumbent-effective-rank-v2/`.
- The next distinct dependence mechanism is frozen before treatment output in
  `reports/2026-08-13-td-ledger-final-served-protocol.md`. It changes only
  `TD_LEDGER=1`, keeps fixed-share multinomial allocation (`td_alloc_k=None`),
  and is explicitly adaptive/retrospective. The score-free gate requires exact
  final-served marginal multisets and G0/G1 reproduction, improved aggregate
  Brier/variogram/QB-WR/G0/G1 error, no WR-WR regression beyond `1e-12`, and
  no greater than `log(1.05)` error regression for QB-TE, RB-RB or
  multiplicity >=2/>=3. A pass only licenses a separately frozen exact-80;
  a fail closes the mechanism without TD-allocation, game-sigma, usage-K,
  yardage-ledger or G2-TE retuning.
- TD-ledger evaluator, CLI, immutable launcher/harvester and focused tests are
  implemented and pushed in `08d5a87`. Thirty focused dependence/ledger tests
  passed and both shell scripts passed `bash -n`. Cloud Build
  `dc9c0b6a-f393-4ede-b97a-562fd4ddf56c` was intentionally cancelled before
  treatment because a review found the frame-alignment helper incorrectly
  demanded bitwise `mean_projection` equality even though the frozen protocol
  allows maximum mean drift `1e-10`. No treatment or scientific metric ran.
  The transport-neutral fix leaves actual outcomes exact and delegates mean
  checking to the registered tolerance, with a regression test. Exact next
  action: replacement full-test Cloud Build
  `bf133686-f4e2-48e2-a766-480220f3b4e3` from pushed repair/source commit
  `55451fb` passed and produced immutable digest
  `sha256:58f70494f6da7647d871e11f800306f5883093dd6b48164d84b906dd1e0493a9`.
  Score-free execution `td-ledger-final-served-v1-pb4fh` completed cleanly
  from that digest in 28m22s. Its immutable machine artifact is under
  `reports/td-ledger-runs/20260813-td-ledger-final-served-v1/`, with concise
  interpretation in
  `reports/2026-08-13-td-ledger-final-served-result.md`. The frozen disposition
  is `td-ledger-invalid-or-inconclusive`, so no exact-80 is licensed and no
  lineup score was queried. All substantive score-free gates improved and all
  material-regression guards passed: joint-q90 Brier
  `0.0184902457 -> 0.0184693402`, variogram
  `1.4349192382 -> 1.4291390592`, G0 absolute-log-error sum
  `3.3128520397 -> 3.0074140876`, weighted G1 error
  `6.9441769599 -> 6.2018347057`, and QB-WR error
  `1.1383728859 -> 1.0024590461`. Both primary paired-slate bootstrap intervals
  exclude zero favorably. The only failed invariant is exact final-served
  player marginals: maximum player-mean drift was
  `3.814697269177714e-06` rather than at most `1e-10`; frame/actual alignment,
  deterministic replay, finite output, terminal identity, and control
  reproduction all passed. Treat this as promising but invalid, not as a
  scientific rejection. Exact next action is a score-free, stage-boundary
  precision/ULP diagnostic for the TabPFN -> market shift -> position-scale
  path. Repair only a demonstrated general numerical defect, prove exact
  marginal preservation and default-path safety, then rerun the unchanged
  gate; never waive the invariant or inspect lineup scores.
  The first stage-boundary diagnosis found a general numerical cause in
  `shift_draws_to_means`: float32 inputs were reduced in float32, so changing
  only world order changed the computed mean and therefore applied a
  `2^-19`/`2^-18`-scale uniform shift. Shared final-served transforms now use
  a deterministic float64 mean over sorted marginal values. That definition
  covers the market shift, replay/live pre-blend center, served tail/position
  scales and diagnostic position scale. Regression tests construct
  permutations with demonstrably unequal float32 means and prove bit-exact
  sorted marginals through the complete shift/position-scale chain; 51 focused
  blend/position/served-tail/ledger tests pass. Exact next action is full Cloud
  validation, a default-output
  safety check, then a new immutable score-free rerun of the unchanged frozen
  gate. Do not reuse the inconclusive execution as a pass.
  The first incomplete repair build
  `2a36bc49-defa-46c3-b688-b6fa554b7509` was intentionally cancelled while
  still testing because the next stage retained ~`1e-15` order drift; it is
  not validation. Superseding full validation build
  `40e20dcd-f040-451d-88e7-cd5afa318f18` passed from exact-marginal commit
  `89615a6` and produced immutable digest
  `sha256:66fbf519b4b1c8596473bef5f11e952fbb1afff9592b31f4cf9924978b06c09f`.
  The unchanged frozen score-free replacement ran as execution
  `td-ledger-final-served-v2-precision-h5ck6`, job
  `td-ledger-final-served-v2-precision`, run ID
  `20260813-td-ledger-final-served-v2-precision`. Its launch manifest is
  tracked under the corresponding `reports/td-ledger-runs/` folder. It
  completed cleanly in 26m31s and was harvested with intact checksums. The
  original marginal defect is fixed: exact sorted multisets and deterministic
  replay pass, with maximum mean drift `7.105e-15`; all scientific gates and
  material-regression guards remain favorable. V2 is still formally
  `td-ledger-invalid-or-inconclusive` because the shared precision repair
  changes all 13 frozen G1 control variograms by `2.8e-10..1.28e-8`, beyond
  the registered `1e-12` reproduction tolerance. No exact-80 is licensed.
  Full interpretation is appended to
  `reports/2026-08-13-td-ledger-final-served-result.md`. Next dependence
  action: keep the incumbent path byte-identical and freeze a distinct
  adaptive terminal rank-coupling protocol that derives ranks from the
  existing TD-ledger simulator but permutes unchanged incumbent final-served
  marginals. Never reinterpret v1/v2 or inspect their lineup scores.

### 2026-08-12 team-passing review reconciliation

- The new operator review
  `reports/2026-08-12-pit-repair-and-team-qb-feature-review.md` is reconciled
  in
  `reports/2026-08-12-pit-repair-team-qb-review-reconciliation.md`. Its note
  that fitted K was rejected is stale because it covered only through
  `24c742a`: the completed exact-80 comparison later selected fitted
  `K=28.154043586960896` at the frozen first threshold (240 count 2 -> 3),
  and commit `213e963` adopted it.
- Before any team-passing side-table execution/cache/prediction/result, the
  arm was amended to append the fixed two-column bundle
  `team_qb_cpoe_l6` + `team_qb_cpoe_cross_season`. The protocol now correctly
  calls this team passing efficiency, not pure QB quality, and predesignates a
  primary-passer-only follow-up only if the whole bundle wins. SQL,
  independent reconstruction, generator/validator contracts, audit output
  and focused tests are updated. Existing team-QB GPU/full images
  `30c5...`/`d3b4...` are superseded before execution and must not be used;
  rebuild both from this exact amended commit.
- The dead same-week `qb_quality` CTE is removed. A read-only audit proves the
  `014` final-season position fallback was unreachable across all 102,927
  usage-spine rows (zero null or unsupported positions), so future SQL now
  uses the exact salary/role position directly; the current repaired warehouse
  is unchanged. The next full feature rebuild must verify byte-equivalent
  usage/training output. Rear-view-only `022` retains and documents its
  deliberate final-season mapping.
- Injury-lock coverage is now fail-closed without inventing data: all 209
  modeled weeks have a Sunday-main lock; 191 have eligible pre-lock source
  rows and 18 2025 weeks legitimately have none. The dynamic suite requires
  every lock and forbids an empty built week whenever eligible source exists.
  Focused tests pass with one expected dashboard skip; changed SQL and both
  independent references pass BigQuery dry runs. The broader manifest-driven
  upcoming-spine check is valid queued work before final closure.
- Active-label final-served v2 execution
  `tabpfn-active-label-final-served-v2-mbs5t` completed cleanly from immutable
  audit digest `aec3...`. The terminal score-free gate passes: active-only
  aggregate Brier-30 improves `0.0140557446 -> 0.0140065605`, with smaller
  improvements in all three evaluation seasons; Brier-20, CRPS and point MAE
  also improve. The machine artifact is under
  `reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v2-pit-clean/`
  and the concise result is
  `reports/2026-08-12-pit-clean-active-label-final-served-result.md`.
- That pass licensed the frozen paired exact-80 active-label books. The first
  launch attempt used the right digest in the wrong nonexistent package
  (`nfl-dfs-gen`), so Cloud Run created no execution and no score. Its empty
  execution file/manifest/preflight are preserved under panel id suffix
  `-failed-wrong-image-package`. The launcher now requires the full exact
  `nfl-dfs/nfl-dfs@ad50...` URI. Corrected control smoke execution
  `replay-pitactv2ctl-smoke-4wtwq` and treatment smoke
  `replay-pitactv2trt-smoke-nzvmv` both passed. All six 2023--2025 books
  completed cleanly: control `replay-pitactv2ctl-2023-7dh98`,
  `replay-pitactv2ctl-2024-bxkmb`, `replay-pitactv2ctl-2025-zrx9k`;
  treatment `replay-pitactv2trt-2023-wjfqn`,
  `replay-pitactv2trt-2024-v8xv6`, `replay-pitactv2trt-2025-48d7j`.
  Execution manifests are pushed in commit `92632fc`. Independent acceptance
  executions `accept-replay-panel-wst5w` (control) and
  `accept-replay-panel-s2ndt` (treatment) passed exact-80 legality and
  replay/live mean parity.
- Original comparator execution
  `compare-tabpfn-active-label-exact80-v2-nr296` correctly stopped invalid
  before calling the score comparison: its invariant allowed the seven
  persisted marginal outputs but mistakenly demanded equality for three
  deterministic descendants of that same marginal. Field reconciliation
  found only `model_points_pre` (28,411 rows), `mean_projection` (28,411), and
  `consensus_div` (10,923). Registering exactly those three additional outputs
  leaves 29,605 equal keys, zero missing/mismatched invariant rows, and maximum
  remaining drift `3.5527136788e-15`. Raw invalid output, formatted invalid
  report, acceptance artifacts, and execution ids are tracked under the two
  panel folders and
  `reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/`.
- The score-independent repair and its observer disclosure are frozen in
  `reports/2026-08-12-active-label-comparator-invariant-repair.md`. While
  checking parity evidence, the agent unnecessarily opened ordinary
  acceptance summaries and saw each evaluation arm's aggregate
  187/194/200 counts; no 240/230/220/210 count, weekly maximum, 107-slate
  decision, or comparator selection was exposed. The decision rule, panels,
  and all causal levers remain unchanged. The same exact ten-output contract
  is frozen for SCHED and team passing before either downstream result.
  Focused active-label/SCHED/team-passing tests and shell parsing pass.
  Repair/evidence commit `f10a7a4` is pushed on `main`. Exact-commit full-test
  Cloud Build `141d2c9f-908f-4de2-a363-982d7a734490` passed 991 tests with two
  expected skips and produced immutable audit digest
  `sha256:43160f9416035183794477c6003177de2e948ebc0d0597f35a28180d400a1d9b`.
- Repaired comparator execution
  `compare-tabpfn-active-label-exact80-v2-r1-brmrp` is valid and selects
  active-only labels at the first nonzero frozen threshold: 240/230/220 tie
  `2/2`, while 210 improves `4 -> 6`. Lower diagnostics also improve:
  200 `12 -> 14`, 194 `22 -> 23`, 187 `33 -> 35`, and mean weekly maximum
  `176.3566 -> 176.8692`. Promotion acceptance
  `accept-replay-panel-rbjxg` passed. Terminal selection is
  `label_law=active-only`, cache `tabpfn_active_label_treatment_v2`, panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`. The concise result is
  `reports/2026-08-12-pit-clean-active-label-exact80-result.md`; machine
  artifacts and both comparator executions are in the run folder. Next:
  terminal selection/result commit `556cb47` is pushed. The frozen score-free
  SCHED cache pair is now running from GPU digest `6609587b...`, source code
  `23da1dd`, and terminal `label_law=active_only`: control execution
  `tabpfn-sched-v1-control-ssmpb`, treatment execution
  `tabpfn-sched-v1-treatment-8l8nm`. Their run manifest is under
  `reports/tabpfn-sched-runs/20260812-tabpfn-sched-v1-pit-clean/`. Wait for
  both clean successes, then validation passed. It proves 52,307 output rows,
  exact active-only context identity, exact control reproduction of
  `tabpfn_active_label_treatment_v2` at maximum delta `0.0`, the fixed
  33-column control and 35-column treatment contracts, and changed treatment
  predictions. Frozen SCHED final-served execution
  `tabpfn-sched-final-served-v1-fn9bv` completed cleanly from full audit digest
  `aec3c368...`, but the treatment fails its score-free prerequisite:
  aggregate calibrated 30-point Brier worsens
  `0.0140065605 -> 0.0140111906`. CRPS and point MAE improve slightly, while
  2023 Brier improves minutely and both 2024/2025 worsen; the clustered Brier
  difference interval crosses zero. All PIT/cache/coverage/mean invariants
  pass. Per the frozen branch, no SCHED exact-80 lineup or score job is
  licensed. `scripts/resolve_tabpfn_sched_fallback_v1.sh` selected the
  incumbent shared-33 active-only cache. Machine and concise results are in
  `reports/tabpfn-sched-runs/20260812-tabpfn-sched-final-served-v1-pit-clean/`
  and `reports/2026-08-12-pit-clean-tabpfn-sched-final-served-result.md`.
  Next scoring action: start the amended team-passing side-table branch using
  only review-corrected GPU digest `b6a3a896...` and full digest `df3de60e...`,
  inheriting the terminal no-SCHED context.
- The isolated amended team-passing side-table execution
  `build-team-qb-quality-v1-j4rh6` completed cleanly from review-corrected full
  digest `df3de60e...` and source `83192ca`. Its independent strict-prior
  marker and warehouse audit pass: 13,934 unique team-season-week keys, 6,270
  supported lagged-CPOE rows, 2,112 cross-season flagged rows, and no duplicate
  key. The first local read-only summary stopped before writing a report
  because it used reserved BigQuery alias `rows`; the fail-closed harvester now
  uses `row_count`, restores the stable JSON `rows` key afterward, and has a
  focused source-contract regression assertion. No model cache or outcome was
  queried before that repair.
- The frozen amended team-passing cache pair completed cleanly from corrected GPU
  digest `b6a3a896...`, source `83192ca`, terminal active-only labels, base
  shared-33 features (SCHED was not selected), and inherited cache
  `tabpfn_active_label_treatment_v2`: control execution
  `tabpfn-team-qb-v1-control-bcr4l`, treatment execution
  `tabpfn-team-qb-v1-treatment-dg556`. Validation passes every frozen
  contract: 52,307 exact equal keys, exact control reproduction of the
  inherited cache at maximum delta `0.0`, distinct amended feature hashes,
  changed treatment predictions, ordered finite quantiles, catcher-only
  support, identical PIT/source/coverage identities, and exact RNG/hyperparameter
  law. The sole score-free final-served execution
  `tabpfn-team-qb-final-served-v1-q9tsq` completed cleanly from corrected full
  digest `df3de60e...`, but failed the frozen primary gate: aggregate active
  RB/WR/TE Brier-30 worsened `0.0140065605 -> 0.0140127100` (delta
  `+0.0000061495`; paired slate-cluster 95% interval
  `[-0.0000060903, 0.0000183893]`). CRPS and all three tail pinball losses also
  worsened slightly; point MAE improved `3.63282 -> 3.61681`. All PIT,
  alignment, selected-cache, coverage, market-blend and mean-preservation
  invariants passed. No exact-80 score job was licensed. The fail-closed
  terminal selection retains active-only/shared-33 cache
  `tabpfn_active_label_treatment_v2`, fitted `K=28.154043586960896`, and panel
  `20260811-pitclean-e80-k1-role12union-a12ab31`. Machine artifacts are under
  the two terminal team-QB run folders; concise result:
  `reports/2026-08-12-pit-clean-tabpfn-team-qb-final-served-result.md`.
- G0, the next graph/dependence kill test after the marginal queue drains, is
  now preregistered before the team-passing result in
  `reports/2026-08-12-g0-final-served-dependence-protocol.md`. It mechanically
  binds the eventual terminal cache and selected control/treatment served
  schedule, uses row-specific final-served q90 thresholds, the exact
  heterogeneous Poisson-binomial null, nine fixed multiplicity/conditional
  cells, deterministic slate-cluster bootstrap uncertainty, fixed support and
  practical-equivalence bands, and three exhaustive dispositions. It reads no
  lineup score and could not launch before `selected_team_qb.txt` existed.
  The terminal selection now exists and the G0 implementation is ready: it
  reconstructs the exact selected 10,000-draw final-served book, preserves
  row means while applying the selected walk-forward position schedule,
  computes the exact heterogeneous Poisson-binomial null and six conditional
  teammate lifts, and applies the frozen 2,000-replicate slate bootstrap and
  exhaustive decision. Its launch manifest binds the terminal cache metadata,
  active-label/SCHED/team-QB/usage selections, served report, protocol, image,
  code and schedule hashes. Focused G0/team-QB tests pass 15/15; both cloud
  scripts pass shell syntax and the Python entry points compile. The complete
  local suite passes with one expected skip. Source/result commit `4aa952c` is
  pushed on `main`. Exact-tree Cloud Build
  `28ef097d-9067-48ed-bb26-670ec2fd1ef4` passed the full suite and produced
  immutable digest
  `sha256:92a9c6f8bbf6964a4153e1e054a4ac7e18bc2aeece11bab8417904cb09b35cda`.
  First execution `g0-final-served-dependence-v1-8mhvg` failed before loading
  data or computing any metric because Cloud Run's `--set-env-vars` transport
  stripped terminal base64 padding from the selected schedule. Logs contain
  zero G0 scientific output prefixes. The failure is preserved under v1 and
  classified `invalid-pre-data-operational-failure`. The transport-only repair
  restores deterministic base64 padding before strict decode; protocol, data,
  schedule, cells, uncertainty and decision rules are unchanged. V2 uses a
  new immutable run/job identity. Repair commit `ee94725` is pushed. Exact-tree
  Cloud Build `a708bbf2-435e-4184-9b2e-41ad9f2fab3a` passed the full suite and
  produced immutable digest
  `sha256:e56549d12c58137d0250a1b4b93698cd5965e88d88f9c32a67b27f4bc500f76f`.
  Replacement execution `g0-final-served-dependence-v2-7fsx6` completed
  cleanly and passed every terminal identity/alignment/mean invariant. Its
  frozen disposition is `dependence-premise-miss`, licensing G1. On 7,848
  supported rows and 54 slates, the simulator materially understates QB-WR
  lift (`3.321` realized vs `1.053` simulated), QB-TE lift (`2.359` vs
  `1.048`), and same-team q90 multiplicity at `>=2` (`1.148` vs `1.003`) and
  `>=3` (`1.835` vs `1.013`). Every corresponding slate-bootstrap interval
  excludes zero on log(simulated/realized). The `>=4` point estimate also
  shows underprediction (`2.333` vs `1.037`) but is unsupported under the
  frozen rare-event minimums; other cells are inconclusive or unsupported.
  No lineup was generated or scored. Machine report is in the v2 run folder;
  concise result is
  `reports/2026-08-12-g0-final-served-dependence-result.md`. G1 is now frozen,
  before any target-season G1 metric, in
  `reports/2026-08-12-g1-walk-forward-archetype-topology-protocol.md`. It fixes
  strictly-prior per-target archetype refits, history-short fallbacks, 13 pair
  classes including separately routed cross-game controls, Jeffreys
  shrinkage, cell support, a 2,000-slate bootstrap, deterministic positive-lift
  spectral topology diagnostics, and an exhaustive stable-QB-hub decision.
  The archetype source is explicitly limited to strictly-prior
  `was_active=true` games so inactive zero rows cannot define a player's
  scoring profile. Broad target-season support is fixed at the one-third
  thresholds (166 pairweeks, ten source booms), and cross-season stability
  requires two supported folds without treating a third unsupported fold as
  an automatic failure.
  G2 requires both broad QB-WR/QB-TE stability across seasons and at least one
  supported material archetype edge for each relationship; graph communities
  themselves cannot gate. Next: implement G1 with exact G0 reproduction tests,
  then build and run its single immutable score-free execution. G1 is now
  implemented without reading a target-season metric: the code reconstructs
  the terminal book, requires exact G0 reproduction, fits strictly-prior
  position-scoped archetypes, persists the immutable fold labels, builds all
  13 registered directed pair classes, calculates paired Jeffreys-shrunk cell
  and broad lifts with slate bootstrap intervals, emits the non-gating spectral
  topology and variogram/joint-q90 scorecard, and applies only the frozen
  stable-QB-hub decision. The read-only Cloud Run launcher binds every G0 and
  terminal selection hash; the immutable harvester validates the relationship,
  bootstrap, invariant and G2-license contracts and extracts the label artifact.
  Twelve focused G0/G1 tests, compilation, shell syntax and whitespace checks
  pass. Implementation commit `0e46292` is pushed. Exact-tree full Cloud Build
  `760e54f4-ba1b-4054-bad5-12af744eef4b` passed and produced immutable digest
  `sha256:7de0de88693e97bfb69e8b4c43268a5e652305723a0c5f7babee92b4555234af`.
  First G1 execution `g1-archetype-topology-v1-ps9vk` stopped before creating
  any pair book or G1 metric because the supported population has multiple QB
  rows in 169 team-weeks. It emitted zero G1 result records. The failure is
  preserved as an invalid pre-metric execution. Before any G1 result, the
  protocol/code are amended to restore G0's exact rule: QB-source pairs require
  exactly one supported QB and ambiguous team-weeks are excluded from those
  pairs without choosing a primary; their non-QB pairs remain eligible. This
  avoids a post-hoc highest-projection/depth-chart choice and leaves every G1
  cell, threshold and gate unchanged. Next: validate and commit the v2
  operational repair, build the exact tree, and launch the sole replacement
  execution under a new immutable v2 identity.
- Review reconciliation and active-label gate milestone commit `83192ca` is
  pushed on `main`. The complete local suite passes all 992 collected tests
  with one expected rear-view dashboard skip. Exact-commit team-passing GPU
  build `aa1882ad-ad9a-493c-a6ee-cfc46ea8d811` succeeded with digest
  `sha256:b6a3a8961afdfbf9cf37934d2558bbe48af0f6743293be4e4d2dbd3752bf3cda`;
  full audited build `615f182b-2198-4252-84da-1303bbf463a4` succeeded with
  digest
  `sha256:df3de60e08f6e88d8f3d4dba551f01e9fc37d7c7de7de2ba41496a43396d5bfd`.
  These supersede every earlier team-QB image and are the only permitted
  images for that downstream branch.
- The Lineups UI now has a dependency-free post-build Portfolio map for both
  Classic and Showdown payloads. It reports lineup count, unique players,
  roster-overlap families, average/maximum overlap, top-five-player
  concentration, and exact duplicates. One linked SVG groups lineups that
  share at least 55% of a family seed's roster; the other is an exposure-sized
  player co-occurrence network. Clicking a lineup or player highlights the
  corresponding rendered cards. Both views use only the just-generated
  portfolio and are explicitly descriptive—not an outcome-based selector.
  `tests/test_app.py` passes completely; Python compilation, HTML/JS-source
  assertions, and a headless Chromium render/click smoke passed. This UI
  milestone is pushed on `main` as commit `8e82c92`. Exact-tree full-test
  Cloud Build `cd622cbb-0590-41e8-aec5-7fb49af51658` passed 991 tests with two
  expected skips and produced immutable digest `sha256:3ea7f7c7bb0bcee77253d83316d14d3e4367d1577883d55bf8615afeb45c930b`.
  Cloud Run service `nfl-dfs-app` now serves that exact image from ready
  revision `nfl-dfs-app-00067-54b` at 100% traffic. Container readiness is
  clean, revision error logs are empty, and
  `scripts/verify_deployment.py --json` reports zero failures across the app,
  production jobs and shadow contracts. `project-slate` was deliberately not
  changed for this web-only visualization release.
- The operator-supplied marginal-arm/adoption-risk review is reconciled in
  `reports/2026-08-12-marginal-arm-pattern-adoption-risk-reconciliation.md`.
  G0's terminal dependence miss is a strong unifying hypothesis, not proof
  that it caused six old results; fitted K and the corrected direct-role union
  are current selections rather than failed arms. The fitted-K risk audit
  confirms that 2023 Week 3 alone supplied its new >=240, >=230 and >=210
  events (`195.16 -> 240.44`), while the 200/194 grids lost 3/7 weeks. That
  lineup was 53.94 below the recorded 294.38 Milly winner, shared four winner
  slots, and used a QB-WR-TE hub directly relevant to G0. Do not fabricate ROI
  from a payout ladder without full field ranks/scores and duplication; add a
  complete decision-cost disclosure to future tail-first results meanwhile.
  The review also exposes that fitted K's prior lineup verdict cannot transfer
  automatically across the subsequently selected active-only marginal and
  served-schedule stage. The required retrospective standing-law comparison
  is now frozen, before its new multinomial control exists, in
  `reports/2026-08-12-active-label-usage-revalidation-protocol.md`. It reuses
  the immutable known finite-K active-only book and creates exactly one
  same-image active-only multinomial control; its known-treatment limitation,
  seven-threshold law and mandatory decision-cost disclosure are explicit.
  Launcher, comparator, finisher and four focused tests are implemented; 11
  combined G1/revalidation tests pass, along with compilation, shell syntax
  and whitespace checks. Commit/push this exact protocol tree, launch the sole
  control from frozen generation digest `ad50...`, and build an immutable audit
  image for the comparator without inspecting partial scores. If a new
  G2 dependence law is later selected, the reconciliation now precommits the
  bounded upstream and marginal revalidation cascade before any G1/G2 result.
- Repaired G1 exact-tree regional Cloud Build
  `fa42c975-7d5f-42d8-af03-a565d2ba8da4` passed the full suite from source
  `a58cd61` and produced immutable digest
  `sha256:80c7289b1399c65899ecd81b2485643aebdddd7f6486e00dcf20243c7440e1f4`.
  Replacement execution `g1-archetype-topology-v2-fqbh6` completed its
  computation, but its single JSON text payload was truncated by Cloud
  Logging at exactly 102,400 bytes. No complete report, broad QB-WR/QB-TE
  result, disposition or G2 license is recoverable, so v2 is an invalid
  post-compute transport execution. Diagnosing it exposed only one incomplete
  unsupported cross-game cell fragment; that observer deviation is recorded
  and cannot enter a gate. The protocol's transport-only addendum now fixes a
  deterministic gzip/base64 manifest plus indexed 48,000-character chunks;
  the harvester requires every chunk and compressed/JSON checksum. Twelve
  focused G1/revalidation tests pass. Regional Cloud Build
  `af20aac6-27da-422b-a761-853fc6f75449` passed 1,009 tests with two expected
  skips from exact repair source `64e0428` and produced immutable digest
  `sha256:72002d1b1c49783e9eda5d0b60314c3a84cfde7ea749968eae520d5eeb205a5e`.
  The sole v3 replacement `g1-archetype-topology-v3-gq47v` completed cleanly;
  all checksummed chunks reconstructed and every invariant passed. Its frozen
  disposition is `stable-qb-hub-confirmed`, licensing G2 for the finite-K
  terminal identity. Broad QB-WR is `3.323` realized vs `1.064` simulated and
  material in all three held-out seasons; QB-TE is `2.371` vs `1.079`, material
  in 2023/2025 and directionally under in 2024. Seven supported QB-WR
  archetype cells and one QB-TE cell are material underpredictions. Cross-game
  controls are inconclusive, so no slate factor is licensed. The descriptive
  graph mismatch is large (relative Frobenius `0.8838`, ARI `0.4949`). Machine
  artifacts are in the v3 run folder and the concise result is
  `reports/2026-08-12-g1-walk-forward-archetype-topology-result.md`. Do not
  launch G2 until active-only fitted-K revalidation resolves: a multinomial
  selection requires G0/G1 reruns; a retained finite K permits G2 to proceed.
  The v1/v2 executions remain invalid as documented.
- The active-only usage revalidation multinomial preflight
  `replay-pitactusemult-smoke-jbrgl` passed on generation digest `ad50...` and
  released the exact registered controls: 2023
  `replay-pitactusemult-2023-k9ncc`, 2024
  `replay-pitactusemult-2024-9sjjp`, and 2025
  `replay-pitactusemult-2025-lcpx7`. Their immutable manifest is tracked under
  `reports/panel-runs/20260812-pitclean-e80-active-label-usage-multinomial-v1/`.
  Wait for all three terminal successes without partial score inspection,
  then run the frozen finisher. The later image-contract failure and licensed
  replacement digest supersede the originally intended `64e0428` audit image
  for that comparator only, as described immediately below.
- All three registered multinomial controls later completed successfully:
  `replay-pitactusemult-2023-k9ncc`,
  `replay-pitactusemult-2024-9sjjp`, and
  `replay-pitactusemult-2025-lcpx7`. Independent acceptance execution
  `accept-replay-panel-zhlb4` passed the complete staged panel. First comparator
  `compare-active-label-usage-revalidation-v1-6jftk` is invalid before science:
  digest `72002...` lacked the comparator script, Python exited file-not-found,
  and no panel/metric/result was loaded or emitted. The failure is preserved in
  the run folder. The protocol and finisher license a packaging-only v2 repair:
  use a new full-test immutable image, require an image-entrypoint `--help`
  preflight, terminal comparator success and bounded log-propagation harvest,
  while preserving the exact panels and frozen decision. Build
  `f0796f88-924a-4f77-bd12-abfdba491586` was already queued from source
  `efcfc71`; after it passes, use its immutable digest with the repaired
  finisher and record the new preflight/comparator IDs before reading the sole
  valid comparison.
- Global replacement build `14272a43-ea6a-4ba4-85e9-b6fe7802bbfd` passed 1,014
  tests with two expected skips and produced digest `sha256:6c244b...`, but the
  new executable image preflight `compare-active-label-usage-preflight-v2-545br`
  correctly failed: the Dockerfile's explicit script allowlist still omitted
  the comparator. No v2 comparator was launched and no panel was read. The
  Dockerfile now copies the registered comparator (and the new effective-rank
  analyzer), with source-contract regression tests. Build another full-test
  immutable image from this repair, rerun the same entrypoint preflight, and
  only then allow the v2 comparator.
- The corrected Dockerfile build
  `5e210824-6bbb-4623-a992-3a97365ebb86` passed 1,016 tests with two expected
  skips and produced audit digest
  `sha256:599f44746b423184c06d6ddf63d4f6170141373e2135a8c733f39e9c9bffbb59`.
  Independent control acceptance `accept-replay-panel-clf22` and comparator
  entrypoint preflight `compare-active-label-usage-preflight-v2-dj5rj`
  passed. Comparator execution
  `compare-active-label-usage-revalidation-v2-7v4p4` loaded both evaluation
  panels and completed the invariant audits, but stopped before calculating
  any score metric or applying the frozen decision: its generic validation
  calls incorrectly required one `lever_env` across all three seasons despite
  the protocol's registered season-varying served-position schedule. The
  invalid pre-score record and execution id are retained in the run folder.
  The narrowly licensed repair sets `allow_season_config=True` for only the
  two evaluation panels; the arm-specific audit still requires one exact
  registered identity within each season and every other identity/invariance
  rule remains unchanged. Focused validation passes 20 tests plus shell
  syntax. Next: commit/push this repair, run a new full-test immutable build,
  and use only v3 preflight/comparator identities. Do not inspect partial v3
  output; after a valid terminal comparison, record the frozen 107-slate grid
  and branch to either G2 (finite K retained) or multinomial G0/G1 reruns.
- The exact repair-tree Cloud Build
  `f0b7a163-86c1-4e9e-9a39-2adf43880659` passed 1,018 tests with two expected
  skips and produced immutable digest
  `sha256:f77377c4ce6be26f36f3b2d3718a515a699e4613b3c1def274340dbe2741e59a`.
  Final independent acceptance `accept-replay-panel-4299w`, entrypoint
  preflight `compare-active-label-usage-preflight-v3-vkg6n`, and sole valid
  comparator `compare-active-label-usage-revalidation-v3-8kzc6` all passed.
  The frozen 107-slate law retains finite K at the first difference: thresholds
  240/230/220 tie `2/2`; 210 is `4 -> 6` in favor of finite K; lower disclosure
  is 200 `10 -> 14`, 194 `19 -> 23`, 187 `35 -> 35`, and mean weekly maximum
  `176.70243 -> 176.86916`. The terminal allocation remains Dirichlet
  `K=28.154043586960896`, panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`. Full evaluation-panel
  crossings, >=10-point deltas, overlap and known-treatment/observer limits
  are in `reports/2026-08-12-active-label-usage-revalidation-result.md` and
  its machine run folder. G0/G1 remain applicable; proceed directly to freeze
  and implement G2 rather than rerunning them under multinomial. Run the
  effective-rank diagnostic only after G2 establishes the final dependence
  law.
- G2 is now frozen before any calibration-grid or held-out treatment metric in
  `reports/2026-08-12-g2-qb-gumbel-factor-protocol.md`. It uses one
  QB-rooted bivariate Gumbel conditional-rank overlay for same-team WR/TE only,
  skips ambiguous/unsupported QB team-weeks under G1's exact rule, preserves
  every row's marginal multiset, omits unlicensed RB/slate loadings, selects
  only `theta_WR/theta_TE` on a fixed 2019/2021/2022 score-free grid, and
  evaluates the full G0/G1 scorecard only on held-out 2023--2025. The frozen
  aggregate gate requires both variogram and joint-q90 Brier improvement,
  lower G0/G1 grid error and separate QB-WR/QB-TE error reductions before any
  exact-80 panel. The core deterministic link/inversion and exact-marginal
  overlay are implemented in
  `src/nfl_dfs/research/qb_gumbel_factor.py`; 24 focused G0/G1/G2/effective-
  rank tests pass, including identity at theta one, conditional inversion,
  exact multiset preservation, scope and upper-tail activation. No G2
  calibration or held-out result has been computed. Next: implement the
  immutable early-fit/held-out evaluator and transport/launcher contracts,
  reproduce the G0/G1 control exactly, then build and run the sole score-free
  G2 execution.
- That frozen G2 evaluator is now implemented, still without computing any
  calibration or held-out result. It reconstructs the canonical
  2019/2021/2022 historical book with exact accepted-snapshot/cache/blend
  parity, scores and persists all 81 registered theta cells before touching
  held-out outcomes, then reconstructs the exact finite-K active-label G1
  terminal book. It requires `1e-12` G0/G1 control reproduction, exact
  marginal multisets, deterministic output, unchanged non-receivers, and
  bounded mean drift; recomputes the full G0/G1 cell/broad/season/topology
  disclosures; applies every frozen gate; and adds 2,000 paired whole-slate
  bootstrap intervals for the fixed-weight Brier and variogram changes.
  Immutable launch/harvest scripts bind both prerequisite reports inside the
  image by checksum, all terminal selection/protocol hashes, finite
  `K=28.154043586960896`, the walk-forward position schedule, source SHA and
  image digest. Twenty-seven focused G0/G1/G2/effective-rank tests pass;
  Python compilation and both new shell syntax checks pass. The complete local
  suite also passes all 1,026 collected tests with only the expected skips.
  Current uncommitted implementation is based on `c4415d7`. Exact next action:
  commit/push the G2 evaluator milestone, build a full-test
  immutable image, launch `20260812-g2-qb-gumbel-factor-v1`, and poll/harvest
  it through a terminal result. Only a valid passing dependence gate may
  license the separately frozen exact-80 comparison.
  Implementation commit `724b617` is now pushed on `main`. Exact-tree Cloud
  Build `bcfe3f45-de07-4dd6-8beb-f690627c22d3` passed 1,025 tests with two
  expected skips and produced immutable G2 audit digest
  `sha256:fa20d36852b6eb6901b6f8b6619730afece81608c8d8bf03800c955a24817b49`.
  Frozen v1 execution `g2-qb-gumbel-factor-v1-jz54s` is now launched from
  that exact digest; its checksummed manifest is under
  `reports/g2-qb-gumbel-runs/20260812-g2-qb-gumbel-factor-v1/`. Poll this exact
  execution without reading partial scientific output, then harvest only a
  clean terminal result.
  V1 later terminated after 37m55s because its configured 16 GiB memory limit
  was reached while beginning held-out reconstruction. It emitted zero G2
  scientific prefixes, so no calibration cell, selected theta, held-out
  metric, disposition or license was observed. The execution is preserved as
  `invalid-operational-memory-limit` in its run folder. Before any replacement
  output, the operational addendum now requires v2 to checksummed-chunk and
  persist the complete 81-cell calibration artifact before held-out loading;
  the harvester must prove exact equality with the terminal fit section. Code
  releases calibration matrices before held-out reconstruction and v2 uses
  32 GiB. No scientific rule/data/seed/grid/gate changed. Next: validate and
  commit this operational/durability repair, build a new full-test immutable
  image, launch the sole v2 replacement, and poll/harvest it to terminal.
  The complete local suite passes all 1,027 collected tests with only the
  expected skips; 28 focused G0/G1/G2/effective-rank tests, compilation,
  shell syntax and whitespace checks also pass. Commit/push this exact repair
  tree and submit its full-test Cloud Build next.
  Repair commit `c1ac40f` is pushed. Exact-tree Cloud Build
  `3caf0362-eef6-4d3c-843a-3c2be787e28d` passed 1,026 tests with two expected
  skips and produced immutable v2 digest
  `sha256:9d00a848c1f55f172c6c7e092bd40a1dadbc6cc2015e06b9313033f29ef155d5`.
  Frozen 32 GiB v2 execution `g2-qb-gumbel-factor-v2-wfkgw` is now launched
  from that exact digest. Its manifest is under
  `reports/g2-qb-gumbel-runs/20260812-g2-qb-gumbel-factor-v2/`. Poll this exact
  execution without reading partial metrics and require both the durable
  calibration artifact and terminal report at harvest.
  V2 passed the v1 memory boundary and durably emitted its complete calibration
  artifact, then stopped with exit 1 while assembling the held-out control
  report: code incorrectly required all nine G0 cells to be supported, while
  the frozen protocol explicitly sums error over supported cells and G0
  intentionally leaves rare cells unsupported. No terminal report, held-out
  metric value, disposition or license was emitted/observed; the calibration
  grid/selected theta was not decoded or inspected. V2 is preserved as
  `invalid-post-calibration-supported-cell-code-defect`; its opaque JSON hash
  is `e387a698...14f69`. Before any v3 output, the protocol/code/launcher now
  bind the recomputed calibration artifact to that exact hash, accept only a
  nonempty supported G0 subset, and otherwise retain every rule. The adjacent
  G1 aggregation had the same unexecuted overconstraint; before v3 output it
  is also corrected to sum only supported primary cells while still requiring
  QB-WR and QB-TE support for their separate gates. Next: validate/commit/push,
  full-test build, then launch/poll/harvest v3.
  The complete local suite passes all 1,029 collected tests with only expected
  skips; the focused suite is 30/30 and compilation, shell syntax and
  whitespace checks pass. Commit/push this exact v3 repair tree and submit its
  full-test Cloud Build next.
  Repair commit `47ff083` is pushed. Exact-tree Cloud Build
  `29f0c714-8125-48da-8f60-8da1f0adb4ca` passed 1,028 tests with two expected
  skips and produced immutable v3 digest
  `sha256:c81abd2a3887593c35445f0f2b965da0dfc2293496084af770e9e0d64d984342`.
  Checksum-bound 32 GiB v3 execution `g2-qb-gumbel-factor-v3-75thv` is now
  launched from that exact digest. Its manifest is under
  `reports/g2-qb-gumbel-runs/20260812-g2-qb-gumbel-factor-v3/`. Poll this exact
  execution to terminal and require the calibration checksum and final report
  to validate before interpreting any metric.
  V3 completed cleanly and the fail-closed harvester validated both chunked
  artifacts. The recomputed calibration exactly matches the opaque V2 JSON
  hash `e387a698...14f69`, proving the operational repairs did not change the
  frozen fit. The selected cell is `theta_WR=1.0`, `theta_TE=1.05`. Across 54
  held-out 2023--2025 slates, joint-q90 Brier improves
  `0.0184902457 -> 0.0184671203` (paired-slate 95% interval
  `[-0.0000403198, -0.0000071706]`) and variogram p=0.5 improves
  `1.4349192382 -> 1.4338178790` (interval
  `[-0.0018369176, -0.0003662747]`). Supported G0 absolute-log-error sum
  improves `3.312852 -> 2.747302`, G1 weighted error improves
  `6.944177 -> 5.965699`, and QB-TE error improves
  `0.787420 -> 0.307184`. QB-WR remains exactly unchanged at `1.138373`
  because its selected theta is identity, so the mandatory separate QB-WR
  gate fails. Disposition is `g2-dependence-gate-fails`; no exact-80 panel is
  licensed and production remains unchanged. All marginal/determinism/scope/
  reproduction invariants pass. Machine report SHA-256 is
  `aff43f6b...3945dbd`; full evidence and interpretation are in
  `reports/2026-08-13-g2-qb-gumbel-factor-result.md`. Next: commit/push the
  immutable result, run the registered effective-rank/tail-overlap diagnostic
  on the unchanged incumbent, then continue the distinct G3 participation-
  conditioned allocation hierarchy around accepted finite
  `K=28.154043586960896`. Do not retune G2 or run a post-result TE-only panel.
  Result commit `f04b93d` is pushed on `main`. Before running effective rank,
  its output contract is being hardened from one oversized JSON log entry to
  deterministic checksummed gzip/base64 chunks. The exact incumbent panel,
  promoted source, 107-slate universe, 80 entries, 10,000 worlds, seven tail
  lines, nested books and controls are frozen in
  `reports/2026-08-13-portfolio-effective-rank-protocol.md`. Dedicated Cloud
  launch/harvest scripts fail closed on the terminal G2 failure, immutable
  image/code identities, complete transport and every registered report
  invariant. Next: focused validation, commit/push, full-test Cloud Build,
  launch the outcome-blind incumbent diagnostic, and poll/harvest it.
  Implementation/protocol commit `e124004` is pushed. Regional exact-tree
  Cloud Build `7538fcd8-9da3-4200-9f81-3bd4d66c86ac` passed 1,028 tests with
  two expected skips and published immutable effective-rank digest
  `sha256:8fab83020f0a9b24253727e5ae352d550f10c9286eb10f27e2c0c51e34cce486`.
  Use that digest with code identity `e124004` for the sole frozen incumbent
  execution; later review-only commit `2edd7eb` does not alter the archived
  build tree. Next: commit/push this build identity, launch with
  `scripts/cloud_portfolio_effective_rank.sh`, then poll/harvest only a clean
  terminal result.
  Frozen execution `portfolio-effective-rank-v1-jbgtr` is launched from that
  exact digest with code identity `e124004`. Its checksummed manifest is under
  `reports/portfolio-effective-rank-runs/20260813-incumbent-effective-rank-v1/`.
  Poll this exact execution without reading partial diagnostic output; on a
  clean terminal success, run the fail-closed harvester and summarize the full
  107-slate result.
  The execution completed cleanly, but the harvester correctly rejected its
  checksummed terminal payload before writing a report: it contained only the
  54 evaluation slates from 2023--2025, not the registered 107. The protocol
  had incorrectly described selected evaluation panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2` as the whole terminal
  policy; G2 and the active-label selection records prove that 2019/2021/2022
  remain on historical panel
  `20260811-pitclean-e80-k1-role12union-a12ab31`. V1 is preserved as
  `invalid-post-compute-input-scope-mismatch`; no effective-rank metric or
  result is accepted from it. The v2 operational addendum freezes the intended
  season composite without changing any diagnostic, world, book, tail,
  control or seed. The analyzer, launcher and harvester now require the exact
  two-panel season map and 107 unique slates. Twenty-three focused effective-
  rank/active-usage/G1 tests pass; compilation, shell syntax and whitespace
  checks are clean. Next: commit/push the v2 repair, build a full-test immutable
  image, launch the sole v2 replacement, and harvest only if every composite
  scope and transport check passes.
  V2 full-test Cloud Build `399e8bb1-5117-43c3-ae38-af6420a1a8c4`
  completed successfully and published immutable digest
  `sha256:450f22cbdae94e23c8322330fe3f445d256cd82dbfc96ca086593a0f80eee90e`.
  The sole frozen composite execution is now
  `portfolio-effective-rank-v2-pbxps`, launched from that digest with analysis
  code identity `f4ccbcf`; its checksummed manifest is under
  `reports/portfolio-effective-rank-runs/20260813-incumbent-effective-rank-v2/`.
  Poll without reading partial payloads, then run
  `scripts/cloud_finish_portfolio_effective_rank_v2.sh` only after a clean
  terminal success. No effective-rank result is accepted yet.
  The execution completed cleanly and the strict harvester accepted the full
  107-slate report. Result interpretation is frozen in
  `reports/2026-08-13-portfolio-effective-rank-v2-result.md`; machine evidence
  is under the v2 run folder. The selected 80-entry book's first-PC-deflated
  correlation participation ratio averages 20.40 (median 20.37), versus 13.66
  for random-80 and 11.48 for top-simulated-mean-80 controls. Its modeled
  covered-world rate averages 13.67% at 200 and 0.67% at 240, versus
  8.15%/0.31% for random-80 and 9.68%/0.39% for top-mean-80. Thus the selector
  adds meaningful simulator-implied conditional diversity/tail coverage, but
  80 entries behave like roughly 20 independent post-common-factor directions,
  not 80 independent bets. This is outcome-blind, likely optimistic while
  QB-receiver upper-tail dependence remains under-modelled, and cannot change
  production or claim a score/ROI improvement. Next: freeze and run the queued
  score-free team TD-ledger evaluation against the unchanged finite-K terminal
  incumbent.
- The operator asked explicitly whether defense-coverage effects on WRs and
  QBs are in the test plan. WR/TE coverage has already received two honest
  historical tests: the N-1 receiver/opponent fit slightly improved the
  player-level 30-point Brier gate but its licensed 12-candidate exact-80 union
  tied all 107 weekly maxima and every threshold; the same-season last-four
  fit failed support and worsened aggregate 30-point Brier. Both exact WR/TE
  mechanisms remain closed. QB Coverage Matchup and WR Coverage Matchup still
  have no historical-season selector and remain pre-lock 2026 capture-only.
  A genuine QB gap did remain: no test combined recent offense shell
  efficiency with recent opponent Defense Coverage Matrix deployment. The new
  operator-directed protocol
  `reports/2026-08-13-fantasy-points-qb-shell-fit-protocol.md` freezes exactly
  two last-four grades (Man/Zone and one-high/two-high), the walk-forward
  2023--2025 tail test and its gate before the required offense-window grid is
  collected. Its 56-export Playwright plan is
  `same-season-qb-shell-fit-last-four-v1.json`. It reuses the accepted defense
  windows and never uses the stale QB Matchup sample. Queue it behind the
  current effective-rank/TD-ledger boundary; a pass can license only a
  separately frozen exact-80 union.
- A concurrently added outside inventory,
  `reports/2026-08-13-wr-defense-coverage-test-inventory.md`, exposed an
  adjacent untested production question. Reconciliation in
  `reports/2026-08-13-wr-defense-coverage-inventory-reconciliation.md`
  verifies that the three PFR secondary-quality rates and `top_cb_out` are in
  both `NUMERIC_FEATURES` and the selected active-only TabPFN feature contract,
  while no isolated ablation is recorded. PIT checks prove safety, not value.
  Queue a current-stack score-free then exact-80 conditional ablation of the
  three rate fields as one block and `top_cb_out` separately, with a combined
  branch declared before treatment metrics. Do not remove them merely because
  adjacent Fantasy Points receiver-shell arms failed, and do not let this live
  feature question vanish into a non-promotional final forensic report.
- The external weekly-coverage source audit is now recorded in
  `reports/2026-08-13-weekly-coverage-data-source-audit.md`. Direct inspection
  verified that free nflverse participation releases contain roughly
  19k--23k nonblank play-level man/zone and named-shell rows per season for
  2022--2025 (with earlier NGS participation back to 2016). This is immediately
  useful for a historical diagnostic but not a live production feature:
  nflverse documents that its 2023+ FTN participation replacement is delivered
  only after the postseason, and the NGS-to-FTN source break must be measured.
  Do not purchase another feed yet. If a distinct live source is still needed
  after the already-frozen Fantasy Points QB shell-fit test, SIS DataHub Pro is
  the first paid trial: its $99.99/month NFL plan advertises time/coverage
  filters and CSV export. Verify history, week filters, player assignments,
  latency and identifiers during the combined NFL/college seven-day trial
  before payment. Also audit whether its college history can fill the
  collection-only CFB scaffold's current statistical gap without prematurely
  building a CFB model. FTN (Football Outsiders' DVOA successor) is a credible
  second research option, but arbitrary consumer-plan CSV export is not yet
  established; PFF+ is only a secondary coverage-quality prior on current
  evidence. NFL Pro is a cheap live cross-check ($14.99/month with NFL+
  Premium) but has no verified export contract. MatchQuarters, Sharp,
  Reception Perception and SumerLive have useful interpretation/current or
  player-trait data, but none currently displaces nflverse history plus the
  already-purchased Fantasy Points train/serve path.
  The new outside review
  `reports/2026-08-13-g2-failure-analysis-and-next-mechanism.md` is reconciled
  in `reports/2026-08-13-g2-failure-analysis-reconciliation.md`. Its core
  diagnosis is accepted: G2's identity WR choice plus clean TE repair motivates
  one distinct score-free test of the already-implemented `(game, team)` TD
  ledger under the current final-served finite-K incumbent. Two claims are
  corrected before use. G2 retains competitive residuals, so the shared-factor
  problem is a measured structural tension rather than a universal
  impossibility proof; and Poisson thinning makes fixed-share multinomial
  receiver TD counts conditionally independent after marginalizing the total,
  not persistently negative, with the random game factor adding positive
  covariance. The ledger may still add exact QB-catcher same-event coupling
  without G2's direct all-WR shared-root coupling. Effective rank remains
  `likely optimistic; not a formal bound`. Finish effective rank first, then
  freeze one no-retuning ledger-only score-free evaluator. Any pass licenses
  only a separately frozen exact-80 comparison plus explicit adaptive-history
  disclosure; do not automatically compose the failed G2 TE factor or tune a
  TD-allocation parameter.
- The operator-supplied alternative-frames review is retained unchanged at
  `reports/2026-08-12-alternative-analytical-frames.md` and reconciled in
  `reports/2026-08-12-alternative-analytical-frames-reconciliation.md`. The
  mandatory final-preseason closure protocol now includes: paired,
  nonstationarity-aware EVT as a diagnostic rather than a promotion gate;
  model-implied portfolio effective rank/eigenspectrum and tail overlap from
  the existing checksummed candidate-by-world artifacts; corrected
  slate-relative rank and ownership-consensus diagnostics; variance
  components; layer-aware inverse winner-belief distance; and a restricted
  pre-lock slate-opportunity analysis. None may retroactively reopen or promote
  a historical arm. Add EVT to the next not-yet-frozen exact-80 protocol and
  run effective-rank diagnostics after the final dependence law is known.
- The long replay runtime is not caused by Cloud Run resource contention.
  Each active usage-control execution already has 4 vCPU/16 GiB and all three
  seasons run concurrently. Over the measured window they averaged about
  23.8%, 25.0% and 25.2% CPU (roughly one busy core each) and about 11.9%,
  13.9% and 12.6% memory; 2024 briefly reached about 69.6% memory, so 16 GiB
  remains prudent. `us-central1` quota is 200 vCPU, 400 GiB and 1,000 running
  executions versus the active 12 vCPU/48 GiB/3 executions. Do not resize or
  cancel the frozen runs. Queue deterministic week-level replay sharding with
  bounded concurrency and exact season-run equivalence tests after this
  comparison; adding CPU/RAM to the current single-task process will not
  materially accelerate it.
- Generic outcome-blind portfolio diversity tooling is now implemented in
  `src/nfl_dfs/research/portfolio_effective_rank.py` with the read-only entry
  point `scripts/analyze_portfolio_effective_rank.py`. It checksum-verifies the
  exact candidate-by-world artifact, requires canonical candidate and complete
  selected-rank identities, and reports covariance/correlation participation
  ratios, entropy rank, leading factor/entry/player loadings, seven-line pair
  and multiplicity overlap, and nested 20/40/80 books. It deliberately selects
  no arm and queries no realized score. Four new tests plus the active-usage
  and G1 suites pass 16/16; compilation, shell syntax and whitespace checks
  pass. Do not execute or interpret it scientifically until the final
  dependence law is known; then run it on the incumbent and any passing G2
  treatment from an immutable validated image.
- The follow-up implementation review
  `reports/2026-08-12-effective-rank-implementation-review.md` is reconciled in
  `reports/2026-08-12-effective-rank-implementation-review-reconciliation.md`.
  Before any scientific run, effective-rank tooling now also reports exact
  first-PC-deflated spectra, same-pool top-simulated-mean and twenty
  deterministic random-book controls, and raw tail event/pair support counts.
  Deflated correlation rank is the conditional-diversity headline; raw rank
  remains visible. The current result is labelled likely optimistic under the
  measured QB-receiver miss, not a formal bound. Same-world controls remain
  in-sample; any future G2 exact-80 protocol must freeze independent
  selection/evaluation worlds for an out-of-world claim. A stable valid EVT
  diagnostic that contradicts a future empirical-grid pass requires explicit
  operator production review, but cannot promote a grid failure or silently
  veto/retune an arm. Five effective-rank tests and the active-usage/G1 suites
  pass 17/17; no outcome column has been queried and no panel has been analyzed.

### Critical pre-launch PIT repair — stale active-label caches blocked

- The expanded source-family recomputation found two genuine common-data
  defects before any active-label exact-80 lineup outcome was generated or
  queried. `014_player_week_usage.sql` used one all-history position prior in
  `rz20_targets_smoothed`/`gl3_carries_smoothed`, allowing early seasons to
  borrow later seasons. `018_player_week_injury.sql` neither deduplicated raw
  player-week revisions nor restricted same-week statuses to information
  available at the common Sunday-main lock.
- Outcome-free warehouse evidence: the deterministic 5% usage sample has
  identical 4,975 built/reference keys and exact parity on every unaffected
  field, while 3,625 red-zone-target and 3,640 goal-line-carry smoothers change
  (maximum absolute deltas `0.0673186009`/`0.0571626124`). The injury source has
  65,866 rows on 65,862 keys; 24 deterministic latest revisions are after the
  common lock and four of those are `Out`.
- Local repair: position priors now accumulate only through the previous
  `(season, week)`; injury rows choose one deterministic latest pre-lock
  revision and persist `injury_source_modified_at` plus `slate_lock_at`.
  `features/leakage.py` independently reconstructs all 29 usage-family fields,
  injury values/timestamps/status and downstream vacated opportunity with
  exact key/null/value parity. Dry-runs are 33,165,826 bytes for the full usage
  reference, 5,541,943 for injury and 10,198,069 for vacancy. Focused tests
  pass 94 with one expected dashboard-window skip; Python compilation and
  `git diff --check` are clean.
- The immutable active-label final-served result remains historically accurate
  for its v1 inputs but is superseded as a production license. The v1 exact-80
  protocol is marked pre-launch invalid. Do **not** launch the v1 control or
  treatment books. The unchanged-law repair path is: commit/build this repair;
  coordinated feature rebuild and row/key/delta reconciliation; retrain every
  live registry; generate write-once PIT-clean v2 control/treatment caches with
  the original respective label laws; repeat the identical score-free
  final-served gate; launch exact-80 only if that clean gate passes.
- Context/QB leakage exact-tree Cloud Build
  `0ae5daf8-23ec-423b-9b83-a31b995c1289` completed successfully with 930
  tests passed, two expected skips and immutable digest
  `sha256:e80f78840ec787782eb454e29974e7de0e702fbe05c23ed2b07514f241a773b4`.
  Active-label exact-80 tooling build
  `0e216434-a07c-4f82-bd22-f77017a5bcf9` completed successfully and published
  digest
  `sha256:09a7c5415abee7f4dd0a2e5271e1d9c6b3db77434d45360508a91d47649254ab`;
  its exact tree passed 935 tests with two expected skips. It validates the
  code tree but cannot authorize stale-cache launches.
  PIT-repair exact-tree build `f7317ad5-f563-458a-a28f-5f2aa85eec79` is
  complete from pushed commit `ac9a2c2`: 940 tests passed, two expected skips,
  immutable digest
  `sha256:66ee48456c5c66a290794dae6ee704a6cc42213d346931cfe0e3feb5e06f74c4`.
  `build-features` is pinned to that digest and coordinated rebuild execution
  `build-features-nbzk8` is running. Do not train, generate caches or score
  repaired panels until it completes and the outcome-free reconciliation
  passes.
- The strengthened final-preseason closure protocol now requires a ninth
  output, an exhaustion certificate that maps every known idea across all
  mechanism families to a terminal/prospective/data-blocked disposition, plus
  an adversarial repository/cloud completeness pass. It still runs only after
  all viable historical arms are genuinely terminal.
- The exact data-repair rerun set is frozen before repaired outcomes in
  `reports/2026-08-11-pit-repair-revalidation-scope.md`. Tier 1 rebuilds the
  accepted Week-1 lineage (K3/K1, direct-role union, canonical TabPFN,
  score-free position calibration plus licensed exact-80, and fallback). Tier
  2 rebuilds active-only labels and fitted usage K because they govern the
  SCHED/team-QB and G3 branches. Tier 3 preserves unrelated rejected arms
  without automatic retry. This prevents selecting reruns after repaired score
  changes are visible.
- Pre-repair feature snapshots, natural-key counts and complete-table checksums
  are tracked in
  `reports/2026-08-11-pit-repair-warehouse-manifest.md`. Ten snapshots named
  `nfl_predictions.pit_pre_ac9a2c2_*` have 30-day expirations; their durable
  BigQuery job ids are in the manifest. The old training/usage tables each have
  102,927 unique player-week rows, while old injury has 65,866 rows on 65,862
  keys. The independently computed repaired injury target is 57,550 unique
  pre-lock common-Sunday-main rows; 8,312 old keys have no eligible pre-lock
  source. Use these snapshots for exact post-build reconciliation; never
  splice them into a new repaired panel.
- PIT-clean active-label cache generation is preregistered in
  `reports/2026-08-11-tabpfn-active-label-pit-clean-cache-addendum.md` and
  implemented without changing its training law. The generator accepts only
  registered v1/v2 control/treatment names, writes with `WRITE_EMPTY`, and
  records the training table's modified time, schema hash and full content
  checksum. Versioned launch/harvest scripts target write-once v2 tables and
  the validator checks the exact registered pair. Focused active-label tests,
  shell parsing, compilation and whitespace checks pass. Do not build/launch
  the GPU pair until the repaired feature build and post-build reconciliation
  complete.
- `scripts/pit_repair_reconcile.py` is the fail-closed post-build verifier. It
  compares the ten pre-repair snapshots with live rows/keys/schemas/checksums,
  requires usage/training/defense key stability, permits material changes only
  in the registered repair fields and deterministic descendants, requires
  exactly 57,550 repaired injury rows, bounds rebuild-only floating drift, and
  proves all unaffected context tables remain byte-equivalent. It reads no
  outcome/score column.
- Coordinated feature execution `build-features-nbzk8` completed successfully
  in 4m46s and passed its full dynamic PIT/universe/live-row suite. The first
  separate before/after reconciliation then stopped as designed before any
  training, cache or lineup score: it found that the snapshot still predated
  the already-declared exact-week positional-defense repair and that the
  referee tendency's `(season, week)` window had an ambiguous same-week tie.
  The raw officials source maps Scott Novak to two 2024 Week 8 game ids; a
  rebuild changed `ref_flags_prior` on 144 training rows (maximum 0.55).
  Defense/`xfp_l4` float-only differences are bounded at
  `2.220446049250313e-16`/`7.105427357601002e-15`.
- The outcome-free addendum
  `reports/2026-08-11-pit-rebuild-reconciliation-addendum.md` freezes the
  second-build rule before scores. Referee history now has total order
  `(season, week, game_id)`. The reconciler recognizes the already-registered
  exact-week defense repair and deterministic descendants of usage/injury,
  while separately requiring zero null drift and <=`1e-12` float noise.
  Focused tests pass. Next: exact-tree build, redeploy `build-features`, run a
  second coordinated build and require the revised reconciliation to pass;
  only then train or generate PIT-clean caches.
- GPU build `0671d1fc-0a2e-4921-8f7e-fff0dd155e74` successfully produced the
  pre-addendum cache image digest
  `sha256:d59b1fbf60de8dc51ba05ebf2d19b417920fac04b487ff8223d62a8d58b2d80c`.
  Do not use it: the final cache lineage must include the referee total-order
  repair. Superseded CPU build `72d4ed86-ce91-45dc-8287-e83bb7728a94` was
  cancelled to avoid wasting compute after the gate found the new repair.
- The Tier-1 canonical TabPFN regeneration is now frozen separately in
  `reports/2026-08-11-tabpfn-canonical-pit-clean-cache.md`. It writes the
  unchanged six-season/all-prior/current-label law once to
  `nfl_features.tabpfn_projections_pit_v2`, records the complete repaired
  training-table identity and never overwrites the old production table. The
  replay cache resolver now licenses that exact table and both registered v2
  active-label tables; the prior resolver recognized only v1 names, which
  would have blocked the already-frozen v2 downstream run. K3/K1 must both pin
  the new canonical table explicitly and may not fall back silently.
- The canonical-cache launch/harvest path is now fail-closed and tracked:
  `scripts/cloud_tabpfn_canonical_pit.sh` refuses a mutable image or existing
  destination, while `scripts/validate_tabpfn_canonical_pit.py` independently
  proves the exact repaired training checksum/schema/modified time, feature
  contract, target-key equality, hyperparameters, unique finite rows and
  ordered quantiles before downstream use. Focused tests and shell parsing
  pass. No repaired lineup score has been queried.
  Its dedicated Cloud Build recipe is tracked beside the generator so the
  canonical image cannot accidentally use the active-label entry point.
- Exact referee-repair feature build
  `7344650c-38b9-40b8-9eb0-84310f0fc21b` passed the full cloud suite and
  published immutable digest
  `sha256:3dbb81f4e04e8ba55dc82f921d8e35a64198bdb435b973bc0b55fb743d1d105d`.
  `build-features-ktn4b` is the second coordinated rebuild from that digest;
  it completed successfully with all dynamic leakage checks passing.
  Outcome-free reconciliation artifact
  `reports/pit-repair-runs/20260811-pit-clean-v2/reconciliation.json` then
  passed all 21 registered checks: exact usage/training/defense keys and
  schemas, exactly 57,550 unique injury rows, intended usage/injury/defense
  deltas and descendants only, total-order referee repair, byte-equivalent
  unaffected tables, and <=`1e-12` rebuild-only floating noise. PIT-clean
  model/cache work is now licensed; no repaired lineup score has been queried.
  Canonical GPU image build
  `9211ed35-a6fb-453b-823c-0389b9b60d07` and active-label GPU image build
  `02eea485-c492-402d-943c-e9111a70cbc1` are also running from tracked commit
  `bb1ebc9`; their jobs remain blocked on clean warehouse reconciliation.
- Canonical GPU image build `9211ed35-a6fb-453b-823c-0389b9b60d07`
  failed before publishing because the newly tracked root-context recipe
  exposed that the legacy Dockerfile still used directory-local `COPY`
  paths. The Dockerfile now names both repo-root paths and a focused test
  guards that context contract; the failed image has no execution/cache data
  and is superseded by running build
  `a4a76dcd-738b-48a7-9810-3bc7ac7af1fc`. Active-label image build
  `02eea485-c492-402d-943c-e9111a70cbc1` succeeded with digest
  `sha256:d0830d9fb79643fd77faa0d8c80f4863c1769adb56d6d1782999d5aa0f40139b`.
  Full Tier-1 application build `2ce169dc-36a6-4ae2-94c9-37018b0eb0ba`
  failed during test collection only: a new test imported a non-packaged
  `scripts` namespace that happened to be on the local pytest path. The test
  now loads the validator explicitly by tracked path; no application or
  warehouse execution occurred from that failed build.
- Reconciled active-label v2 cache executions are now running from that exact
  active-label digest: control `tabpfn-active-v2-ctl-7fhxx` and active-only
  treatment `tabpfn-active-v2-trt-j4vss`. Their immutable manifest is tracked
  under
  `reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v2-pit-clean/`.
  Both completed successfully. Independent validation at `validation.json`
  passes every report/table gate: exactly 52,307 unique shared target keys per
  arm across 2022--2025; identical repaired source, feature and hyperparameter
  identity; finite ordered quantiles; positive sampled inactive labels in all
  control folds and zero in treatment; and materially changed predictions.
  This licenses the score-free final-served gate only after repaired Tier 1
  and fitted-K choose its required panel/usage branch; no v2 lineup outcome
  has been queried.
- Superseding canonical image build
  `a4a76dcd-738b-48a7-9810-3bc7ac7af1fc` succeeded with immutable digest
  `sha256:2e227119cd5009060b65bfca75ff7e9b4402132c64b478cc90dac519bd193029`.
  The sole write-once canonical cache execution is now
  `tabpfn-canonical-pit-v2-xjm2q`; its immutable manifest is under
  `reports/tabpfn-canonical-runs/20260811-tabpfn-canonical-pit-v2/`. Do not
  use the table until the independent validator passes.
- Canonical execution `tabpfn-canonical-pit-v2-xjm2q` completed successfully
  and wrote 65,455 unique rows. Its first independent validation attempt
  stopped before writing a verdict because `rows` was used as an unquoted
  BigQuery alias; the validator now uses `row_count`. This is validator-only,
  does not mutate the write-once cache and did not license downstream work.
  The corrected independent validation now passes every report/table check:
  exact 65,455 unique target keys across the six frozen seasons, exact repaired
  102,927-row source identity/checksum/schema/time, write-once table and code
  identity, feature/hyperparameter/context law, and finite ordered quantiles.
  Tier-1 registry/panel qualification may now consume this cache explicitly.
- Full generation-image build `9d774557-5542-4357-b6a5-548217d0ec10`
  passed 947 tests with two expected skips and published the frozen Tier-1
  digest
  `sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62`
  from application code `a12ab31`. Later runner/comparator commits do not alter
  that generation image or its frozen code identity.
- The repaired active-label final-served dependency is now a separate v2
  runner. It requires explicit validated v2 cache, repaired panel and repaired
  fitted-K comparison inputs; the comparison mechanically supplies either its
  exact accepted positive K or the multinomial fallback, and the Python gate
  revalidates that identity. This prevents the old v1 panel/K constants from
  contaminating the repaired branch. It is not launchable until Tier 1 and
  fitted-K are terminal.
- Tier-1 scoring is now frozen before repaired outcomes in
  `reports/2026-08-11-pit-clean-tier1-revalidation.md`: exact code/cache,
  isolated `models_pit_v2` registry qualification, exact-80 K3/K1 controls,
  predeclared K3 and K1 direct-role branches, and a 240->230->220->210->200->
  194->187 lexicographic operator law. The first non-tied high threshold wins;
  averages and season signs are diagnostics. This directly matches the
  operator's current objective and prevents either an obsolete 200-lift gate
  or a post-score branch choice from deciding the repaired baseline.
- The dedicated Tier-1 comparator reuses the existing K3/K1 and direct-role
  mechanism audits, adds exact canonical-v2 cache-key coverage, reports the
  full threshold/season grid, and applies only the newly frozen lexicographic
  law. Its pure priority tests prove that a 230 improvement wins despite lower
  thresholds declining and that mean is consulted only after a full grid tie.
- The Tier-1 panel/finish wrappers now pin the exact validated generation
  digest, canonical v2 cache and predeclared IDs, require cache/registry
  qualification, launch both exact-80 controls, promote K3 only as comparison
  source, and promote K1 only if the frozen comparator selects it. The role
  runner then refuses either branch unless it matches the durable mechanical
  selection record.
- Isolated registry qualification now has guarded launch/finish scripts. They
  require both warehouse and canonical-cache validation, refuse a nonempty
  `models_pit_v2` prefix, launch K3/K1/role jobs from one immutable image, and
  validate all component artifacts, ensemble sizes, generations/checksums and
  exact base/role feature contracts without reading scores.
- The isolated `models_pit_v2` registry qualification is now in flight from
  frozen generation digest
  `sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62`:
  canonical K3 execution `train-pit-v2-k3-2d7gh`, K1 execution
  `train-pit-v2-k1-4t9pc`, and K1 direct-role execution
  `train-pit-v2-role-5dzlw`. The first two launched normally; the role launch
  initially stopped before deployment because gcloud parsed its comma-list
  feature value as environment syntax. The launcher now uses a safe custom
  delimiter, its focused test passes, and only the missing role execution was
  resumed under the unchanged frozen manifest. Next action is to wait for all
  three executions, run the independent registry validator, then launch the
  exact-80 repaired K3/K1 controls—no partial score inspection.
- The previously predeclared selected-base role stage now also has a
  fail-closed finisher, added before any repaired panel scores were visible.
  It check-validates the one mechanically permitted role panel, runs the same
  frozen 240->187 comparator against its selected base, promotes the role
  panel only if selected, and writes a durable final Tier-1 selection record.
- Isolated registry qualification is terminal and valid. All three executions
  above succeeded, and the independent validator passed all 134 checks across
  11 components per variant: canonical K3 has 36 features and all three
  members, K1 has the same 36-feature contract and one member, and K1 role has
  exactly the six registered role features added (42 total). The durable
  generation/checksum inventory is
  `reports/pit-tier1-runs/20260811-pit-clean-registry-v2/validation.json`.
- Tier-1 audit Cloud Build `9d341683-b3e2-4a66-be2f-ba5aa3973dd5`
  passed 952 tests with two expected skips and published immutable audit
  digest
  `sha256:cc82a5ed6528a91708e39c2c1a8eb10fefc5cae952e4ac7f0d3196a0a56cba32`
  from the frozen comparator/panel-runner source at `26f5b68`. Use it for
  acceptance/comparison only; generation remains pinned to `ad50...` from
  application code `a12ab31`. Next action is to launch both exact-80 repaired
  controls and wait for all 12 season executions before reading scores.
- The mandatory repaired data-fitted usage retry now has a separate v2
  launch/finish path prepared before the repaired Tier-1 result. It cannot run
  until `selected_tier1.txt` exists; it pins the exact `ad50...` generation
  image and rechecks the reconciled training table's 102,927 keys/rows and
  checksum `1904430067081090565` immediately before launch. This retains the
  original score-free estimator/gate while preventing stale-table reuse.
- Exact-80 repaired Tier-1 launch is in progress from the frozen `ad50...`
  generation digest. K3 smoke `replay-pitk3-smoke-5strh` succeeded with exact
  canonical-v2 cache coverage; six K3 executions are now running: 2019
  `replay-pitk3-2019-bfwz5`, 2021 `replay-pitk3-2021-qr5cs`, 2022
  `replay-pitk3-2022-hm74l`, 2023 `replay-pitk3-2023-724d6`, 2024
  `replay-pitk3-2024-97p5d`, and 2025 `replay-pitk3-2025-dh9nh`. K1 smoke
  `replay-pitk1-smoke-t4mp6` is running; the launcher will release its six
  seasons only on a clean preflight. Manifests are under the exact panel IDs
  in `reports/panel-runs/`. Do not inspect partial scores; next action is to
  finish the K1 launch, wait for all 12 seasons, then run the frozen control
  finisher with audit digest `cc82...`.
- The served-position retry is now frozen before repaired Tier-1 scores in
  `reports/2026-08-12-pit-clean-served-position-calibration.md`. Its v2 code
  derives K=3/K=1 and the full promoted panel from the mechanical Tier-1
  selection, requires canonical `tabpfn_projections_pit_v2`, retains the v1
  score-free grid/gate, and rejects old factors. Guarded launch/finish scripts
  and focused contract tests are prepared; it cannot launch until Tier 1 is
  terminal and a new diagnostic image containing this code passes validation.
- All 12 repaired K3/K1 replay executions completed successfully. K3 check
  `accept-replay-panel-dp5rc` and promotion `accept-replay-panel-sg29h` passed;
  K1 check `accept-replay-panel-h4nxq` passed. First comparator execution
  `compare-pit-tier1-ensemble-x8nkn` failed before importing or querying the
  comparison because the validated audit image omitted
  `/app/scripts/compare_pit_tier1.py`; it emitted no structured report and no
  selection occurred. The Dockerfile now packages the already-frozen script,
  with a focused image-contract test and a repair runner locked to that exact
  failed execution/error. Next action: validate/build the packaging-only
  repair image, run the superseding comparator, then mechanically complete
  base selection.
- Packaging-repair Cloud Build `494d5160-48f9-4c2a-91c8-2d4543fc6186`
  passed 959 tests with two expected skips and published immutable audit
  digest
  `sha256:f73edb2d6f111bc936a2825cca397f7f35c2762b98673d3440bc88de3b2e7746`.
  Superseding comparator execution
  `compare-pit-tier1-ensemble-repair-kmrbv` completed successfully and emitted
  one valid structured report with complete canonical-v2 cache coverage and
  no mechanism failures. The report is tracked under the K1 panel directory;
  it explicitly supersedes packaging-only failure
  `compare-pit-tier1-ensemble-x8nkn`.
- The repaired exact-80 comparison mechanically selected K1 at the first
  difference in the frozen `240,230,220,210,200,194,187` order. K3 to K1
  weekly-maximum counts changed `0/1/2/5/10/13/28` to
  `1/1/2/4/12/22/36`, respectively; mean weekly maximum changed
  `175.0996` to `176.6557`. K1 promotion execution
  `accept-replay-panel-hxlbc` passed, and
  `reports/pit-tier1-runs/20260811-pit-clean-controls-v2/selected_base.txt`
  durably records the selection. The one lost >=210 week is diagnostic and
  cannot override the predeclared >=240 first difference.
- Only the predeclared selected K1 direct-role branch is running from
  generation digest `ad50...`, code `a12ab31`, and canonical-v2 cache. Smoke
  execution `replay-pitk1role-smoke-bbwjd` passed in 10m47s. The six immutable
  season executions are 2019 `replay-pitk1role-2019-gwj7p`, 2021
  `replay-pitk1role-2021-vgs79`, 2022 `replay-pitk1role-2022-t7kbj`, 2023
  `replay-pitk1role-2023-twq2p`, 2024 `replay-pitk1role-2024-j4bq9`, and 2025
  `replay-pitk1role-2025-dbgwf`. Do not inspect partial role scores. Next
  action is to wait for all six seasons, run the frozen
  role finisher with audit digest `f73e...`, then launch the score-free PIT-v2
  served-position and usage-K calibrations from the resulting terminal Tier-1
  selection.
- Observer-blinding deviation during that wait: after the aggregate staging
  count held at 102/107, a broad Cloud Logging health query intended to check
  for a stalled optimizer returned score-bearing lines for three already
  completed slates (2019 Week 15, 2022 Week 16 and 2023 Week 17). No code,
  threshold, panel, branch, protocol or downstream action was changed; the
  seven-threshold comparator and both next-stage launches were already frozen
  and remain mechanical. Do not use those accidentally exposed values for any
  choice. Complete the panel and run the unchanged frozen finisher. This is a
  disclosed observer-blindness process deviation, not a row/invariant or
  computational-validity failure.
- All six K1 direct-role season executions completed cleanly with 107/107
  slates and exactly 80 selected lineups per slate. Check acceptance
  `accept-replay-panel-qkhqw`, frozen comparator
  `compare-pit-tier1-direct-role-x5hdx`, and promotion acceptance
  `accept-replay-panel-jhfzp` all succeeded. The comparator selected direct
  role union at the first registered difference, >=240: selected weekly-max
  counts at `240/230/220/210/200/194/187` improved from
  `1/1/2/4/12/22/36` to `2/2/3/5/13/24/38`; mean weekly maximum improved
  `176.6557009346` to `177.7579439252`. Every threshold moved positively and
  no comparison invariant failed. The role union is therefore the new
  repaired Tier-1 historical baseline, durably recorded in
  `reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt`.
  Next: launch the already-frozen score-free served-position and fitted-usage
  calibrations in parallel from this exact selected lineage.
- Both frozen score-free diagnostics are now running from the terminal role
  selection. Served-position v2 execution
  `served-position-calibration-pit-v2-zmm6s` uses immutable complete audit
  image `sha256:aec3c368...`/source `23da1dd`; fitted-usage execution
  `usage-dirichlet-calibration-pit-v2-g9hhw` uses the frozen generation image
  `sha256:ad50fe19...`/source `a12ab31`. Their manifests are tracked under the
  corresponding `20260812-*-pit-clean` run directories. Next: wait for both
  terminal results, harvest without lineup scores, then launch position Stage
  B only on a passing position gate (otherwise write the identity fallback)
  and launch fitted-usage exact-80 only on a passing likelihood gate
  (otherwise write the multinomial fallback).
- Fitted-usage execution `usage-dirichlet-calibration-pit-v2-g9hhw`
  completed cleanly and its harvested score-free report passes every frozen
  gate. The selected unrounded concentration is
  `K=28.154043586960896`; aggregate held-out mean NLL per group improves
  `14.2216508181 -> 13.3257002097`, targets and carries both improve, and all
  three evaluation seasons improve. The clustered 95% interval for fitted
  minus multinomial is `[-1.0051, -0.7946]`. This licenses exactly one fitted-K
  exact-80 comparison, but its frozen launcher must wait for terminal
  `selected_position.txt`; do not launch it against an unresolved position
  law. Position execution `served-position-calibration-pit-v2-zmm6s` remains
  running.
- The already-frozen team-QB-quality branch now has its point-in-time feature
  implementation while those diagnostics run. `017l_team_qb_quality.sql`
  creates an isolated side table (it does not alter training/inference or any
  current cache identity), aggregates play-by-play CPOE by dropback, and uses
  the previous six completed team games across seasons plus only the single
  live upcoming target. Independent source recomputation is added to the
  mandatory leakage suite. Synthetic tests prove same-week exclusion,
  cross-season ordering, six-game truncation, and historical parity after an
  upcoming null row is appended. Focused feature/leakage tests pass with one
  expected skip; the BigQuery SQL dry-run validates at a 24,914,131-byte upper
  bound. The table has not been built and no team-QB prediction/result exists;
  cache/gate implementation remains sequenced after terminal SCHED as frozen.
- Team-QB implementation now also includes the isolated side-table-only CLI
  and immutable launch/harvest path, an inherited-law/write-once GPU cache
  pair, and a mechanical cache validator. The treatment contract appends only
  `team_qb_cpoe_l6`, normalizes historical team aliases, and broadcasts only
  to RB/WR/TE. Cache validation will require exact target keys, identical
  source/label/feature laws, changed predictions, and control reproduction
  against the terminal SCHED-selected cache within `1e-10`. Focused
  feature/leakage/team-QB tests pass with one expected skip. No side table or
  cache has been built and no result has been inspected; immutable image
  builds and execution remain downstream of the active-label/SCHED decisions.
- Exact-tree team-QB source `301bc94` is now building in parallel. Full audit
  build `1f12be5d-df17-4757-b363-7e9a1cef3025` must pass the complete suite;
  GPU generator build `e303764a-5371-41a7-a5f0-c6c630b971ec` must also pass.
  Their tags and pending status are tracked under
  `reports/tabpfn-team-qb-runs/20260812-team-qb-build-v1/image.txt`. Record
  immutable digests only after terminal success; do not launch the side-table
  or cache stages from mutable tags.
- Team-QB GPU build `e303764a-5371-41a7-a5f0-c6c630b971ec` succeeded; its
  immutable generator digest is
  `sha256:30c5c295ea07f27ccac4cdf4d3ff2dc40258af33313bbe73e57e407ae181150e`.
  Full-suite build `1f12be5d-df17-4757-b363-7e9a1cef3025` remains running.
  Do not launch the cache pair until the side table is validated and terminal
  SCHED selection supplies its inherited label/feature laws.
- The team-QB branch is now implemented through its terminal historical
  decision before any feature/prediction/result exists: inherited-law
  final-served Brier-30 gate, separately frozen exact-80 addendum, paired
  launcher/comparator, promotion record, and fail-closed fallback. The exact-80
  comparator reuses the proven SCHED mechanism checks with explicit cache-table
  parameters and applies the seven-threshold tail-first law. Focused team-QB,
  replay-cache and SCHED tests pass. This implementation is not yet in the
  running `301bc94` full image; build a new exact-tree audit image after this
  milestone is committed, and use only that later digest for its side table,
  gate, comparator and acceptance jobs.
- Exact-tree terminal team-QB full build
  `ecb180f5-ef76-4326-a83e-5d96f32e5823` is running from source `b5b5038`
  with tag `nfl-dfs:team-qb-b5b5038`. Older full build
  `1f12be5d-df17-4757-b363-7e9a1cef3025` validates only the pre-final-gate
  source and must not be used for team-QB execution even if it succeeds.
- Terminal team-QB full build `ecb180f5-ef76-4326-a83e-5d96f32e5823`
  succeeded from source `b5b5038`; the exact-tree audit/execution digest is
  `sha256:d3b46056a25e5dcc2c0bccfa64f45027270e499433be54a785f401d883cef657`.
  Use this full digest with the already-recorded GPU digest `sha256:30c5c295...`
  for the later side-table/cache/gate sequence. Production remains unchanged.
- Pre-terminal full build `1f12be5d-df17-4757-b363-7e9a1cef3025`
  succeeded and emitted digest `sha256:b9053c64...`, proving the complete suite
  for source `301bc94`; it remains execution-ineligible because it predates the
  final-served/comparator implementation. Terminal build `ecb180f5-...`
  remains the required exact-tree audit image and is now running.
- Served-position v2 execution `served-position-calibration-pit-v2-zmm6s`
  completed cleanly and passes every frozen score-free gate. Its unrounded
  treatment factors are `QB=0.975,RB=1.0,TE=0.955,WR=1.075`; aggregate
  position-quantile calibration gap improves `0.0060123 -> 0.0036604`, all
  position mean pinball ratios are <=1, Brier/CRPS guardrails pass, and the
  maximum mean drift is only `7.11e-15`. This licenses the one paired exact-80
  Stage B. Its control smoke is now provisioning as immutable execution
  `replay-pitposv2ctl-smoke-52q6k`; the launcher will release the registered
  2023--2025 control seasons, then treatment smoke/seasons, only after each
  prior preflight succeeds. Do not launch fitted-K exact-80 until this stage
  writes terminal `selected_position.txt`.
- Position Stage B control smoke `replay-pitposv2ctl-smoke-52q6k` passed and
  released the three registered season executions: 2023
  `replay-pitposv2ctl-2023-tr95d`, 2024
  `replay-pitposv2ctl-2024-9jgkf`, and 2025
  `replay-pitposv2ctl-2025-t87lh`. Treatment smoke
  `replay-pitposv2trt-smoke-gmwcz` is provisioning from the same immutable
  generation image and exact lineage. Wait for it to pass and release its
  three seasons; inspect no partial scores, then require all six terminal
  season executions before the frozen Stage B finisher.
- Treatment smoke `replay-pitposv2trt-smoke-gmwcz` passed and released 2023
  `replay-pitposv2trt-2023-nkkwl`, 2024
  `replay-pitposv2trt-2024-7r9hm`, and 2025
  `replay-pitposv2trt-2025-27r57`. All six control/treatment season executions
  are now running. A guarded local continuation polls only terminal status,
  stops on any failure, runs the frozen position finisher only after six clean
  successes, and then launches the already-licensed fitted-K exact-80 pair.
  The durable recovery action after a machine interruption is identical:
  inspect the six IDs above, run
  `cloud_finish_served_position_stage_b_v2.sh` after clean completion, then
  `prop_lock_usage_dirichlet_exact80_v2.sh` if the position finisher succeeds.
- All six position Stage B seasons completed cleanly at 18/18 slates and exact
  80 selections. Control/treatment acceptance checks
  `accept-replay-panel-b5dc2`/`accept-replay-panel-ghfw2` passed; comparator
  `compare-served-position-stage-b-v2-vlgk2` passed; treatment promotion
  `accept-replay-panel-zxcvx` passed. The treatment wins at the first nonzero
  tail threshold: full 107-week 240/230/220/210 counts tie `2/2/3/5`, while
  >=200 improves `13 -> 14`; >=194 improves `24 -> 26`, >=187 moves
  `38 -> 37`, and mean weekly max improves `177.7579 -> 177.9486`.
  The selected research position law is therefore
  `QB:0.975,RB:1.0,TE:0.955,WR:1.075`, durably written to
  `reports/served-position-calibration-runs/20260812-served-position-stage-b-v2-pit-clean/selected_position.txt`.
  The licensed fitted-K usage launcher immediately started control smoke
  `replay-pitusev2ctl-smoke-wws77`; it inherits this selected position law,
  exact K1/direct-role lineage and the canonical PIT-v2 cache.
- Usage control smoke `replay-pitusev2ctl-smoke-wws77` passed and released
  2023 `replay-pitusev2ctl-2023-85fsk`, 2024
  `replay-pitusev2ctl-2024-hfztg`, and 2025
  `replay-pitusev2ctl-2025-xczd5`. Treatment smoke
  `replay-pitusev2trt-smoke-xdpnd` passed and released 2023
  `replay-pitusev2trt-2023-9hcd8`, 2024
  `replay-pitusev2trt-2024-8p79k`, and 2025
  `replay-pitusev2trt-2025-rtsxp`. At 11:14 CDT the three controls were
  running and the three treatments were queued; none had failed. Wait for all
  six clean terminal executions without partial score inspection, then run
  `cloud_finish_usage_dirichlet_exact80_v2.sh` with immutable audit digest
  `sha256:aec3c368...`. If the finisher succeeds, harvest and commit the
  frozen decision before starting active-label final-served v2.
- All six fitted-usage exact-80 seasons completed cleanly at 18/18 slates and
  exactly 80 selections. Control/treatment acceptance checks
  `accept-replay-panel-5bf4g`/`accept-replay-panel-m9264`, comparator
  `compare-usage-dirichlet-exact80-v2-hg8hk`, and treatment promotion
  `accept-replay-panel-nzzh9` all passed. The fitted Dirichlet treatment wins
  at the first tail threshold: full 107-week selected weekly-max counts at
  `240/230/220/210/200/194/187` move
  `2/2/3/5/14/26/37 -> 3/3/3/6/11/19/34`; mean moves
  `177.9486 -> 177.3589`. On the evaluation-only 2023--2025 panel the counts
  move `0/0/1/1/6/11/13 -> 1/1/1/2/3/4/10`, and mean moves
  `173.0459 -> 171.8774`. Under the operator's frozen tail-first objective the
  new >=240 and >=230 weeks dominate the lower-threshold/mean losses, so the
  selected usage law is Dirichlet `K=28.154043586960896`. The machine record
  is
  `reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt`.
  Active-label v2 final-served is now running as immutable execution
  `tabpfn-active-label-final-served-v2-mbs5t` from audit digest
  `sha256:aec3c368...`, source `23da1dd`, this terminal usage law and the
  already-validated v2 cache pair. Wait for clean terminal completion and run
  `cloud_finish_tabpfn_active_label_final_served_v2.sh`; exact-80 may run only
  if that score-free gate passes, otherwise record the canonical current-label
  fallback.
- The licensed PIT-v2 served-position Stage B is implemented before its
  score-free refit result is known. It derives the selected full panel, K1/K3
  law, role/no-role candidate law, and unrounded four-factor specification;
  uses fixed control/treatment IDs from the frozen protocol; reproduces the
  selected source under an identity control; and applies the same complete
  `240,230,220,210,200,194,187` order with mean only after a seven-count tie.
  Its cloud comparator requires exact player/candidate/seed/cache invariance,
  packages separately, and records a mechanical position-law selection for
  downstream arms. Focused validation passes 30 tests plus shell parsing,
  compilation, and whitespace checks. An exact-tree audit image still must be
  built before this comparator can run; generation remains pinned to `ad50...`.
  Exact-tree build `07c0df42-a82b-4034-8a50-f6309e3e85de` succeeded from
  implementation commit `2de8898`: 962 tests passed with two expected skips,
  publishing immutable audit digest
  `sha256:13b60132ab4b7a2dd1f524e228d9b7f1317e6a95821406f7b18dbb6c9f6780b5`.
  This image contains the position v2 comparator; generation remains pinned
  to `ad50...`.
- The PIT-clean fitted-usage lineup retry is now frozen before its repaired
  likelihood report in `reports/2026-08-12-pit-clean-usage-exact80.md`. It
  mechanically inherits the terminal base/role/position laws, uses fixed v2
  control/treatment IDs, tests only the one unrounded fitted K if the
  score-free gate passes, and applies the same seven-threshold/mean-tiebreak
  operator law. Both negative branches are explicit: a likelihood-gate fail
  or exact-80 loss/tie selects multinomial `K -> infinity`; only two passes
  select finite K. This also predeclares the later G3/graph shrinkage target
  so it cannot be chosen after seeing K results. Dynamic runner, comparator,
  selection and fallback scripts pass 17 focused tests plus shell parsing,
  compilation and whitespace checks. They require a later exact-tree audit
  image because the already-running `07c0...` build predates this comparator.
- The prepared active-label v2 final-served runner now consumes the terminal
  `selected_usage.txt` contract instead of attempting to reinterpret one
  fitted-K comparison JSON. It verifies that the selected full panel and K1
  lineage match, then accepts exactly either finite positive Dirichlet K or
  `multinomial/infinity`. This covers the likelihood-fail fallback as well as
  exact-80 reject/pass branches without a post-hoc target. Nine focused tests
  and shell parsing pass; the underlying score-free active-label gate and its
  validated write-once v2 cache pair are unchanged.
- Exact-tree position+usage audit build
  `cdc76392-03c0-4e77-9b17-d1667958c755` succeeded from commit `f54d4c4`:
  965 tests passed with two expected skips, publishing immutable digest
  `sha256:ed3739ef266f3b5435101591b812e75ae7dac9e789e8ce2874afed8e06d1f2ad`.
  It contains both PIT-clean position and usage comparators; generation remains
  pinned to `ad50...`. A failed score-free position calibration now has an
  explicit immutable identity-law resolver, so every calibration outcome
  writes the required downstream `selected_position.txt` without licensing an
  untested lineup arm.
- The active-label v2 exact-80 addendum is frozen before its repaired
  final-served result in
  `reports/2026-08-12-pit-clean-active-label-exact80.md`. A gate fail retains
  canonical current labels without lineups; a pass licenses only fixed v2
  current/active panel IDs. The generated arms inherit terminal Tier-1
  role/no-role and usage laws and differ only by the two validated v2 cache
  tables plus each arm's unrounded walk-forward schedule from the score-free
  report. Its comparator uses the repaired seven-threshold/mean-tiebreak law,
  and both exact-80 rejection and final-served failure have durable canonical
  fallback records. Dynamic runner/comparator/finisher tests pass 12 focused
  checks plus shell parsing, compilation and whitespace validation. The v2
  score-free job now also has a separate terminal harvester that validates its
  panel, exact cache identities/52,307 keys, version and machine-selected usage
  law before writing `report.json`; this closes the prior async-launch gap.
  Exact-tree active-label audit build
  `d760751b-e7eb-478f-97d6-e7fc5debb7e8` succeeded from commit `23e658e`:
  967 tests passed with two expected skips, publishing immutable digest
  `sha256:c219ffce842693c9fa9fc66898c91360d61e82ad9dbedb0018d0d3b9c88f1d56`.
  It contains the active-label v2 final-served code and exact-80 comparator;
  generation remains pinned to `ad50...`.
- The outcome-free SCHED cache stage is implemented before the active-label
  branch or any SCHED prediction is visible. The protocol now fixes write-once
  tables `tabpfn_sched_control_v1`/`tabpfn_sched_treatment_v1`, run id
  `20260812-tabpfn-sched-v1-pit-clean`, and the exact shared-33-plus-appended-
  two feature order. Its GPU generator inherits the terminal current versus
  active-only context law identically in both arms; launch refuses existing
  tables, and independent validation requires exact 52,307 shared keys,
  repaired source identity, feature contracts, context sampling, finite
  ordered quantiles and changed predictions. Four focused tests plus shell
  parsing, compilation and whitespace validation pass. This prepares cache
  generation only; do not launch it until `selected_active_label.txt` exists.
  GPU image build `cde9270c-973b-4697-a30e-c491b7ac8e51` and exact-tree audit
  build `dd8cb18a-9434-43f6-95c9-1119905454d6` succeeded from commit
  `070110a`. The GPU generator digest is
  `sha256:e196dcdb1f51f661c579550256e00327d406f7c6db4a61f77d252b340635c739`;
  the audit build passed 971 tests with two expected skips and published
  digest
  `sha256:4401b455053888d668aac39688c34264685f65c6aec8ce56166ba2ef7e9ad1bd`.
  The validator now additionally requires the 33-feature control to reproduce
  every key and prediction from the terminal inherited cache within `1e-10`,
  preventing generator drift from masquerading as a SCHED effect.
  Before launch, that guard exposed a deterministic sampler-sequence mismatch:
  the canonical current-label job visits 2019/2021 before 2022, while the new
  SCHED target starts at 2022. The SCHED generator now replays the exact two
  pre-2022 seed-7 context-choice calls for current labels (but no unnecessary
  model fits), while active-only correctly has no warm-up. Both arm reports and
  validation prove the inherited sequence. The earlier GPU digest `e196...`
  predates this repair and must not generate SCHED caches; build a replacement
  from the repaired commit.
- The complete downstream SCHED branch is frozen and implemented before its
  caches or outcomes exist. The score-free final-served gate inherits the
  terminal Tier-1 panel, usage law and label law, independently fits each
  arm's walk-forward position schedule, and has separate async launch/harvest
  paths. A failed gate writes an incumbent fallback; a pass licenses only the
  fixed exact-80 panels in
  `reports/2026-08-12-pit-clean-tabpfn-sched-exact80.md`. Their comparator
  applies `240,230,220,210,200,194,187` then mean, proves cache/schedule-only
  changes and writes `selected_sched.txt` for either result. Seventeen focused
  SCHED/replay tests plus shell parsing, compilation and whitespace validation
  pass. The exact-80 runner is intentionally blocked on tracked
  `reports/tabpfn-sched-runs/20260812-sched-generation-v1/image.txt`; create
  that record only from the next successful full exact-tree build of this
  complete code, before any SCHED cache is launched.
- Corrected SCHED GPU build
  `efb515ae-be60-4c42-b779-f8ed29916be0` completed successfully from commit
  `23da1dd` and published immutable generator digest
  `sha256:6609587b95e6193c04a1cdc43529bd21e131c191a50ed0e2bf886cfc8e4e423c`.
  This is the first SCHED generator image containing the inherited RNG warm-up
  repair. Superseded pre-repair full build
  `567f53bf-ac05-48ac-98f2-4be96ae9a2cf` was cancelled without producing or
  using an artifact so corrected full build
  `94c98907-cf8b-462a-a31d-aa06d485602f` could take its build slot. At that
  milestone it remained queued and no SCHED cache was launched.
- Corrected complete SCHED build
  `94c98907-cf8b-462a-a31d-aa06d485602f` then passed 975 tests with two
  expected skips and published immutable generation/audit digest
  `sha256:aec3c368dd493b166f99b444f06dc87b892d2220e4b0e544aa7314b9f03bd9a6`
  from code `23da1dd`. The required pre-result identity record now exists at
  `reports/tabpfn-sched-runs/20260812-sched-generation-v1/image.txt`, binding
  that full digest and the corrected GPU digest before any SCHED cache or
  lineup launch. SCHED remains dependency-blocked on terminal active-label
  selection; this milestone licenses the recorded images, not an early run.

### Validated production rollout completed; Route diagnostic ready

- Exact-tree Cloud Build `4c0614be-bc8e-4e0f-a578-9e96ada30b77` validated
  the production-policy adoption tree with 899 tests passed and two expected
  skips, publishing intermediate digest
  `sha256:69c5e3b3e0f2ecbe90fadbcaf0315f62124b49eeeb196b35e2e428a9b11c1c06`.
  It was not deployed because the independently frozen Route diagnostic was
  implemented immediately afterward.
- Superseding exact-tree Cloud Build
  `17a729c8-7fd3-4cd5-a9a1-307ca3a91acd` completed successfully with 904
  tests passed, two expected skips and no failures. The immutable production
  and diagnostic digest is
  `sha256:4dbb7e7658225ca14f28f0d97d87d648682e7471a7e1e26362ad7b4ff9f45fee`.
- Cloud Run service `nfl-dfs-app` now serves that exact digest from ready
  revision `nfl-dfs-app-00066-fpz` at 100% traffic. Startup and TCP-probe logs
  are clean. Existing IAP intentionally blocks an unauthenticated `/health`
  request, so no authentication bypass was attempted. Cloud Run job
  `project-slate` is pinned to the same digest and was not executed during the
  offseason. `.venv/bin/python scripts/verify_deployment.py --json` reports
  zero contract failures and identifies adopted policy
  `classic-k1-role12-boom40-poscal-v3` with the correct source panel.
- The sole immutable `20260811-route-final-served-calibration-v1` diagnostic
  is now running as Cloud Run execution
  `route-final-served-calibration-lkwk2` from the validated digest above. Its
  frozen manifest and execution identity are tracked under
  `reports/route-final-served-calibration-runs/20260811-route-final-served-calibration-v1/`.
  The execution completed successfully and the frozen report is harvested.
  Machine disposition is `route-final-served-calibration-fails`: aggregate
  calibrated 30-point Brier is exactly `0.0140250212164889` in both arms, as
  are 20-point Brier and q90/q95/q99 exceedance. Both arms selected identical
  walk-forward position factors in every target season. TabPFN coverage is
  100%, all source/key/actual/mean checks pass, and maximum scaling mean drift
  is `7.11e-15`. The shared TabPFN cache therefore erases the Route component
  arm's per-player marginal differences; only numerical-scale CRPS and rank
  coupling differences remain. No exact-80 replay is licensed. The historical
  retry is closed under the frozen rule; do not alter factors, folds, fields,
  model or gate. Result interpretation is tracked in
  `reports/2026-08-11-route-share-final-served-result.md` and the full machine
  report remains in the immutable run directory.
- While the Route execution runs, the audit's independent R4 usage-only
  question is now frozen before producing a model-fitted K in
  `reports/2026-08-11-data-fitted-dirichlet-usage.md`. It uses strictly
  prior-season K=1 component predictions, fits one global K only on 2021--2022
  target/carry conditional allocation likelihood, and gates it once on
  untouched 2023--2025 likelihood versus the production multinomial
  (`K -> infinity`) reference. The estimator uses the simulator's exact
  `max(K*p_i, 0.05)` concentration law. Lineup outcomes and the known K=8/K=20
  score results are forbidden. The diagnostic is now implemented behind
  `usage-dirichlet-calibration-diagnostic` with the immutable one-shot runner
  `scripts/cloud_usage_dirichlet_calibration.sh`. It reproduces strictly
  prior-season target/carry component means for 2021--2025, builds the exact
  simulator-compatible conditional groups, fits the frozen global K, compares
  untouched 2023--2025 likelihood with the multinomial reference, and emits
  only aggregate/kind/season diagnostics. Forty focused usage/component/game
  simulation tests pass; compilation, CLI discovery, shell parsing and
  whitespace checks are clean. Implementation commit `5529cc0` is pushed and
  exact-tree Cloud Build `c2ea3613-f05b-4f65-ae44-788060b436a9` passed 909
  tests with two expected skips and no failures, publishing immutable digest
  `sha256:2d91c90e2b64277f12909c3069f6e7ffecc2cf0436167532c0144642f63e7462`.
  The sole frozen diagnostic is now running as Cloud Run execution
  `usage-dirichlet-calibration-spd5k` from that digest. Its manifest and
  execution identity are tracked under
  `reports/usage-dirichlet-calibration-runs/20260811-data-fitted-usage-k-v1/`.
  The execution completed successfully in 3m17s and machine disposition is
  `data-fitted-usage-concentration-passes`. Fitted global
  `K=28.246898139750336` is interior and independently matches the audit's
  approximately-29 estimate. On untouched 2023--2025 groups, mean conditional
  NLL improves `14.207682 -> 13.317778` overall, `17.360592 -> 16.824802` for
  targets and `10.970002 -> 9.716463` for carries; all three seasons improve.
  The team-week clustered fitted-minus-production 95% interval is
  `[-0.999386, -0.790824]`. All 68,609 evaluation opportunities have 100%
  population coverage and no positive usage was dropped for zero predicted
  mean. The complete result and machine artifacts are tracked in
  `reports/2026-08-11-data-fitted-dirichlet-result.md` and the run directory.
- The one licensed exact-80 test is now frozen before producing any finite-K
  candidate or lineup score in
  `reports/2026-08-11-data-fitted-dirichlet-exact80.md`. Same-image control and
  treatment will generate only 2023--2025, splice unchanged source history to
  107 slates, use the adopted CE0/direct-role12/boom40/position-scale book, and
  differ only by `GAME_SIM_USAGE=dirichlet` plus the exact unrounded K. The
  tail-first 240/230/220/210/200 first-difference law governs; mean is not a
  veto. The launcher, check/promote wrapper, comparator, pure guards and image
  packaging are now implemented. Missing `DIRICHLET_K` persistence was added
  to candidate `lever_env`, with a provenance regression test. The launcher
  verifies the K report hash/gate/value/coverage and both immutable source
  contracts; the comparator requires exact lever equality beyond K/mode,
  source/control reproduction, snapshot/shared-score parity and changed
  candidate membership. Sixty-six focused calibration/lineup/component/
  simulation/persistence tests pass; compilation, script help, shell parsing
  and whitespace checks are clean. Implementation commit `127b07f` is pushed;
  exact-tree Cloud Build `c1b80adb-a461-4e30-b293-fc0572f3d7fe` passed 913
  tests with two expected skips and no failures, publishing immutable digest
  `sha256:55f1f04bc995b0fe73b4040e7c6d4c85d6a00419e6c7966cd89ec0061917eabe`.
  The launcher revalidated the K report and both sources. Control one-week
  preflight `replay-lockk1ukctl-smoke-6tdwq` completed successfully, releasing
  immutable 2023/2024/2025 control executions
  `replay-lockk1ukctl-2023-464ks`, `replay-lockk1ukctl-2024-qhczz`, and
  `replay-lockk1ukctl-2025-d8cn6`. Separately gated fitted-K preflight
  `replay-lockk1uktrt-smoke-42q8j` also completed successfully in 11m21s,
  after which the launcher released immutable 2023/2024/2025 treatment
  executions `replay-lockk1uktrt-2023-xw5qb`,
  `replay-lockk1uktrt-2024-cf6wr`, and
  `replay-lockk1uktrt-2025-prc9d`. Exact manifests are under
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-poscal-usage-{control-v1,k28246898-v1}/`.
  All three control seasons completed cleanly. Check-only acceptance execution
  `accept-replay-panel-49qbb` passed the complete 54-slate, exact-80 control;
  its log and execution identity are tracked with the control manifest. The
  2024 treatment `replay-lockk1uktrt-2024-cf6wr` and 2025 treatment
  `replay-lockk1uktrt-2025-prc9d` have also completed cleanly. Only 2023
  treatment `replay-lockk1uktrt-2023-xw5qb` subsequently completed cleanly,
  making all six fixed season executions successful. Treatment check-only
  acceptance execution `accept-replay-panel-k6lgb` then passed the complete
  54-slate exact-80 treatment in 3m00s; its execution identity and acceptance
  log are tracked in the treatment manifest directory. First comparator
  execution `compare-usage-dirichlet-exact80-cfvdb` returned `invalid` before
  computing any threshold/weekly-score report: its inherited feature gate
  incorrectly required distribution-derived `proj`, p10/p50/p90/std,
  `proj_tourney`, and `own_est` to remain fixed even though usage allocation
  is intended to change those fields. Keys, actuals, salaries, all
  point-in-time inputs, market/model values, ensemble points and
  `mean_projection` are invariant; candidate actuals and common simulated
  means also pass. The invalid artifacts are preserved with
  `invalid_feature_gate` filenames. A comparator-only repair now excludes
  exactly those seven registered downstream outputs and fails if the set
  drifts; it does not alter either existing book, K, sources, selectors or the
  frozen tail-first law. Twenty-three focused usage/position/tail/calibration
  tests pass. Repair commit `079de22` is pushed. Regional Cloud Build
  `2050f11d-4a5c-41f9-be68-265d6a02eb39` passed 923 tests with two expected
  skips and published immutable digest
  `sha256:f92acc32c07f8118511366c321781d448ea219ed649ac647f063184bcadee38b`.
  Repaired frozen comparator execution
  `compare-usage-dirichlet-exact80-hz9j2` completed successfully against the
  unchanged books and passed every mechanical check. Machine disposition is
  `reject`: the full 107-slate control/treatment selected threshold grids are
  34/24/13/7/5/3/2 versus 37/21/12/6/4/2/2 at
  187/194/200/210/220/230/240. The frozen tail-first rule ties at 240 and first
  differs at 230, where fitted K loses 2--3; its +3 187 clears, +0.025 mean and
  +1.00 median cannot rescue it. Candidate-pool oracles are
  43/31/19/9/5/3/2 versus 43/27/18/9/4/2/2. Snapshot keys/upstream fields,
  common actuals and simulated means all pass; treatment materially changes
  candidate membership. Production retains multinomial allocation
  (`K -> infinity`); no finite-K retry or deployment is licensed. Full result
  is `reports/2026-08-11-data-fitted-dirichlet-exact80-result.md` and machine
  artifacts are in the treatment panel directory.
- The operator-supplied point-in-time/join audit is reconciled in tracked
  `reports/2026-08-11-pit-join-audit-reconciliation.md`. It correctly found
  that `team_week_pace`, `defense_week_blitz`,
  `team_week_target_concentration`, and `team_week_ftn_offense` lacked target
  rows for exact-week live inference. The local repair appends only null
  upcoming observations before each strictly-prior window and adds a
  mandatory post-build reconciliation query across all four tables. It also
  replaces season-final roster position with exact player-week position in
  the modeled defense aggregation. The audit's claim that Week-18 position
  directly overwrote the player model feature is too broad: that feature is
  sourced from the exact salary/player week, while the genuine leak was the
  opponent positional-defense aggregate. Outcome-free warehouse counts found
  403 exact-week/final-season position differences over 2019--2025, with
  annual incidence 0.11%--0.64%; nine otherwise missing rows were zero-point,
  unsalaried 2020 records from one unrostered ID. Its “7 of 54” leakage-check
  count also omits existing defense-EPA recomputations, first-row invariants,
  Route source-order checking and static SQL-window guards, though broader
  source-family dynamic recomputation remains valid queued work. The sparse
  `qb_cpoe_l6` diagnostic is added to the already-frozen team-QB protocol; the
  generator passes NaNs directly and has no imputation path. All five changed
  SQL files dry-run against live BigQuery schemas; focused feature/leakage
  tests pass, Python compiles, and `git diff --check` is clean. Repair commit
  `314aa6a` is pushed. Its exact archived tree passed regional Cloud Build
  `b691da39-95dd-453e-9e6c-bd07359bd9c6` with 926 tests and two expected
  skips, publishing immutable digest
  `sha256:1589cb254c8524d62487d1f51aeca7d69c19a8a9ba1de6e4dc2a7dd13fb5a8a4`.
  Do not rebuild the warehouse mid-panel. Apply it only in the next coordinated
  feature rebuild with historical key/delta checks and full retraining. The
  queued dynamic source-family expansions now cover:
  `dk_points_l4`, expanding `dk_points_std` and sample `dk_points_vol` are
  reconstructed from exact actual/provenance rows, preserving inactive-label
  missingness; `ez_targets_l4`, `deep_targets_l4`, `separation_l4` and
  `stacked_box_l4` are reconstructed from PBP/NGS on the complete usage spine
  with exact null-support parity; the adopted neutral-pass ratio is recomputed
  as rolling numerator/denominator sums, and both QB NGS fields preserve their
  cross-season window. Synthetic include-current/null/key/value tests and
  read-only live comparisons pass on identical 11,686-/4,975-/1,336-/253-row
  efficiency/advanced/neutral-pass/QB-NGS samples. Focused leakage tests,
  Python compilation and whitespace checks pass. Efficiency-only commit
  `13549d8` is pushed and regional Cloud Build
  `d7b3e601-9088-4026-9819-e0987b997d4e` passed 928 tests with two expected
  skips, publishing intermediate digest
  `sha256:472e43b2f949dfe50da0e1e1908738d18f26f130cf3d39d78323e10d11cb2da5`.
  Advanced commit `4c7e986` is pushed with active superseding build
  `eef87cfa-7659-4f7f-a09b-985dfa753b1d`; neutral-pass/QB-NGS commit `7304cfc`
  is pushed with queued final build
  `0ae5daf8-23ec-423b-9b83-a31b995c1289`. Monitor both and record the final
  exact-tree result. Smoothed usage and injury/vacancy remain next.
- The operator made the end-of-preseason forensic review mandatory after the
  historical arm queue is genuinely exhausted. The strengthened tracked
  protocol is `reports/2026-08-11-final-preseason-forensic-closure-protocol.md`;
  it does not stop or reorder current work. It corrects the outside plan's
  mathematically zero “best 80-subset from the pool” layer by decomposing the
  hindsight gap into player support, lineup construction and selection; adds
  all-entry/entry-count outcomes, identifiable contest ROI, top-finisher and
  empirical duplication analysis, player capture, marginal/joint-tail
  calibration, pre-lock regime actionability, complete experiment/PIT/data
  reconciliation and a Week-1 dress rehearsal. Its first outcome query is
  forbidden until a tracked closure commit proves every historical arm
  terminal, all executions/artifacts recorded, final production validated and
  the analysis manifest frozen. The output is a prospective 2026 charter,
  opportunity register, kill list and operational readiness gate; it cannot
  promote or retune a historical arm.
- A separate code audit found that `scripts/tabpfn_gen/gen.py` does not apply
  the component path's `active_training_rows` safeguard. The current training
  table contains 6,202/6,041/6,130/6,021 synthetic inactive zero labels in
  2022/2023/2024/2025 versus 7,044/7,043/7,002/6,824 active labels, and the
  production TabPFN cache contains the expanded 2022--2025 universe. A
  same-code active-only training-label test is frozen before producing any
  corrected cache or result in
  `reports/2026-08-11-tabpfn-active-label-protocol.md`. Cache generation is
  independent of the fitted-K decision, but the final-served comparison must
  wait and use whichever common simulator law that decision accepts. Next
  implementation step is a research-only same-image cache generator plus a
  validated/persisted alternate-cache table selector that production
  explicitly resets to canonical.
  That implementation is now complete locally: the isolated GPU image builds
  exact same-code control and active-only caches into two frozen research
  tables, records feature/source/context manifests, rejects any production
  table destination, and requires an immutable code SHA. The replay path now
  accepts only those two explicitly licensed alternate cache names, persists
  the choice in candidate provenance, and the production policy forcibly
  resets the selector to the canonical cache. Thirty-four focused replay,
  persistence, production-policy and calibration tests pass; Python compile,
  shell parse and whitespace checks are clean. Next action is commit/push,
  build the dedicated GPU image from that exact tree, then launch both cache
  arms asynchronously while the six fitted-K season jobs continue.
  Implementation commit `82619ed` is pushed. Dedicated GPU Cloud Build
  `854ef4b7-d0f9-49e4-be80-c939e6e7389c` passed and published immutable image
  digest `sha256:1e6a57f60c962f155c227e3fa6b3e3691d10752935401b906a0f5db53b3f2d8a`.
  A separate immutable-result harvester/validator now checks the two Cloud Run
  reports, same source/code/feature/hyperparameter identity, exact 52,307-key
  equality, finite ordered quantiles, treatment removal of every inactive
  context label, and an actual prediction change before licensing the later
  final-served stage. Thirty-six focused tests pass after adding the validator;
  its Python compile and shell parsing are clean. Validator commit `f249225`
  is pushed. Both same-image cache arms are now running: current-label control
  `tabpfn-active-ctl-gh6f4` and active-only treatment
  `tabpfn-active-trt-lj66c`. Their immutable manifest is tracked under
  `reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v1/`. Next
  action: monitor both to clean completion, run the one mechanical harvester,
  and commit its reports/validation. Do not run final-served comparison until
  the fitted-K decision fixes the common simulator law.
  Both executions completed successfully in 9m19s/9m03s. The repaired local
  harvester (NumPy booleans normalized at the JSON boundary; caches unchanged)
  passed every frozen mechanical check. Both tables contain the exact same
  52,307 unique keys, finite ordered quantiles and identical source/feature/
  hyperparameter identities, with changed predictions. Control sampled
  73/2,860/4,409/5,765 inactive zeros for target seasons 2022/2023/2024/2025;
  treatment sampled zero and retained 28,000 active context rows in every
  fold. The result is documented in
  `reports/2026-08-11-tabpfn-active-label-cache-result.md`; full reports are in
  the run directory. Commit/push the validation artifacts and serializer-only
  repair. The next scientific stage remains blocked only on the fitted-K
  decision fixing the common simulator law; cache validation itself is done.
  The frozen final-served stage is now implemented behind
  `tabpfn-active-label-final-served`. It compares only the two validated
  research cache tables, reconstructs 2022--2025 same-seed served worlds under
  the already-decided common usage law, independently fits the exact
  walk-forward position-scale schedule for each arm, and applies the frozen
  aggregate active RB/WR/TE 30-point Brier gate. The Cloud runner fails closed
  until both the cache-validation artifact and fitted-K exact-80 comparison
  exist; it derives either the exact unrounded fitted K or the production
  multinomial law from that decision and records input hashes. Focused
  active-label/Route/replay/persistence/policy/infrastructure tests pass (55
  tests); Python compilation, shell parsing and whitespace checks are clean.
  Implementation commit `bff6f7d` is pushed. Exact-tree Cloud Build
  `fa1b0d0b-c9da-4a66-b5a1-25cf57447edc` passed 922 tests with two expected
  skips and published immutable CPU digest
  `sha256:ce28df5bccce1a0be8966f5d86b2c53709db4d9dc83d8b1f8050043a93af6762`.
  The fitted-K rejection fixed the common simulator as production multinomial.
  The sole final-served Cloud Run execution
  `tabpfn-active-label-final-served-h5jpq` completed successfully from that
  digest and passed its frozen gate. On 13,876 active RB/WR/TE rows across 54
  2023--2025 slates, aggregate 30-point Brier improved
  `0.014021024 -> 0.014010786` (`-0.000010238`). The paired team-week 95%
  interval `[-0.000048884, 0.000028408]` crosses zero; 2023 and 2024 worsened,
  2025 improved, 20-point Brier worsened slightly, and CRPS improved. Those
  were frozen diagnostics rather than vetoes. Both arms have 100% cache
  coverage, exact common production-multinomial usage, 52,307 cache rows and
  maximum mean drift `7.11e-15`. Full result is tracked in
  `reports/2026-08-11-tabpfn-active-label-final-served-result.md` and the
  immutable run directory. This does not promote the cache. The sole licensed
  exact-80 comparison is now frozen, before producing a lineup outcome, in
  `reports/2026-08-11-tabpfn-active-label-exact80-protocol.md`. It compares
  research current-label versus active-only caches using their exact
  independently fitted 2023/2024/2025 schedules under common production
  multinomial usage and the 240/230/220/210/200 first-difference law. Result
  and protocol commit `3966764` is pushed. The exact-80 implementation is now
  complete locally without querying a lineup outcome: the shared panel runner
  supports a frozen per-season arm environment, while acceptance and pure
  panel validation allow exactly one config/lever identity per season only
  when the reviewed wrapper opts in. The launcher revalidates both prerequisite
  hashes, pass, cache tables, production-multinomial law, row count, mean
  preservation, exact factor schedules and 107-slate splice before deployment.
  The comparator requires identical upstream snapshots, registers exactly the
  seven served-distribution outputs that may differ, validates cache/schedule
  provenance by season, proves the mechanism reaches candidate scoring, and
  applies the frozen tail-first law. Direct promotion of either research panel
  is refused; a pass requires separate canonical cache regeneration. Forty-five
  focused active-label/replay/acceptance/tail tests pass; shell parsing, Python
  compilation and whitespace checks are clean. Next: commit/push this
  implementation, run an exact-tree Cloud Build, and only then launch the two
  immutable books from its digest.
- The new read-only outside review
  `reports/2026-08-11-feature-plumbing-defects-and-correlation-gaps.md` was
  reconciled. Its two-channel diagnosis is correct: TabPFN owns covered player
  marginals while the component path chiefly changes the copula/ranks. The GPU
  feature list is missing only the adopted SCHED pair (`net_rest_diff`,
  `body_clock_hour`) and contains no candidate features. The active-label jobs
  intentionally keep that old 33-feature list; syncing SCHED inside them would
  confound the frozen question. A schema-v2 config-manifest contract now makes
  the exact known two-column omission visible, and an offline test requires
  tracked `scripts/tabpfn_gen/features.txt` to match that contract in exact
  feature order. Any additional silent drift fails. Forty-eight focused
  infrastructure/cache/replay/persistence/policy tests pass. After active-label
  validation, test SCHED sync as a separate marginal-cache arm, then a strictly
  prior QB-quality broadcast to pass-catchers. Weather remains conditional on
  proving historical pre-lock forecast provenance; realized game weather may
  not be used as if it were a forecast. Code inspection confirms the current
  weather table is unsafe for that historical test: it selects the latest raw
  forecast snapshot and otherwise falls back to nflverse schedule temperature/
  wind (observed game conditions). It also found an unused `qb_quality` CTE in
  `015_player_week_efficiency.sql`: team PBP CPOE is computed but never joined
  or selected. A strictly-prior, team-level PBP CPOE window broadcast to
  pass-catchers may be more complete than sparse player-level NGS CPOE and is
  the preferred D1 design to preregister after active-label and SCHED-sync.
  A separate live-plumbing repair now appends exactly one null upcoming row
  before the adopted `neutral_pass_rate_l6` team window and the adopted
  `qb_cpoe_l6`/`qb_time_to_throw_l6` player window. This makes their last six
  completed observations joinable to live inference without changing any
  historical window population. BigQuery dry-runs validate both DDLs; direct
  proposed-versus-current warehouse comparisons find zero mismatches across
  all 6,254 existing neutral-pass rows and all 5,526 existing NGS rows. The
  complete feature-SQL and config-manifest suites pass (one expected dashboard
  skip). Commit/push this point-in-time plumbing repair; do not rebuild feature
  tables mid-panel. Schedule a normal validated feature rebuild after the
  immutable fitted-K and cache jobs finish.
  The next cache question is now preregistered, without changing the feature
  list or producing results, in
  `reports/2026-08-11-tabpfn-schedule-feature-sync-protocol.md`. It starts only
  after the active-label sequence reaches a terminal decision, inherits that
  accepted label law in both arms, and changes only the appended adopted SCHED
  pair. It uses the same independently calibrated final-served Brier30 gate
  before any separately frozen exact-80 score comparison.
  The following QB-hub question is also preregistered, outcome-blind, in
  `reports/2026-08-11-tabpfn-team-qb-quality-protocol.md`. It deliberately uses
  dropback-weighted, strictly-prior six-team-game PBP CPOE broadcast only to
  RB/WR/TE instead of the sparse NGS player field, and inherits all terminal
  active-label/SCHED decisions before changing one feature. Do not implement or
  launch it ahead of those prior stages.
  The operator's graph/clustering/technology suggestions are now reconciled in
  `reports/2026-08-11-graph-dependence-research-queue.md` and linked from the
  scoring roadmap. G1 is a walk-forward archetype-pair co-exceedance topology
  diagnostic; G2 is a conditional upper-tail QB bi-factor copula; G3 is a
  strictly-prior participation-embedding allocation hierarchy; G4 is a
  prospective field-neighbourhood/payout objective once full 2026 standings
  and payout ladders exist. Neo4j, a slate-label GNN and LLM projections are
  explicitly not queued. The historical archetype job is not point-in-time for
  this use and must be refit within each target fold; embeddings require the
  participation feed rather than ordinary PBP alone.
  Two follow-up qualifications are frozen before the fitted-K score is known.
  G1 recomputes every q90 threshold/rate/lift from final-served draws; the
  outside review's widened-summary 8.53% rate and lifts are motivation only.
  G3 branches mechanically on the fitted-K comparator: an adopted K makes the
  conditional hierarchy incremental to K=28.246898139750336; neutral/reject
  keeps production K→infinity as lineup control and requires the conditional
  law to beat both K→infinity and the fixed outcome-free K on score-free
  likelihood/dependence gates before any exact-80 test.
  The complete graph-queue review adds G0 before G1: one immutable-cache-pinned
  nine-cell final-served premise test covering three multiplicities, three
  QB→position lifts and three same-position lifts. Multiplicity must use the
  exact heterogeneous team-week Poisson-binomial null; pooled binomial is
  diagnostic. G1 runs only after the marginal queue drains and only on a G0
  miss; any later cache change invalidates/requires recomputing G0/G1. G2 fits
  on 2019/2021/2022 and evaluates only 2023--2025. Stable cross-game evidence
  routes to a separate winning-line model, not lineup stacking credit.
- Fantasy Points' live projected ownership is now explicitly part of the 2026
  field-model plan. The frozen prospective protocol is tracked in
  `reports/2026-08-11-fantasy-points-projected-ownership-protocol.md`: capture
  immutable DraftKings Classic Sunday Main snapshots at first publication,
  Saturday evening and before both Sunday book freezes; append them to
  `nfl_raw.fantasy_points_ownership_snapshots`; grade each pre-lock vector
  against exact-contest realized ownership; and use the source for legal
  opponent-field simulation, duplicate estimates and payout-aware portfolio
  research. It is not a scoring feature and does not reopen the rejected
  generic `milly_fade` arm. The indexed page says Premium access is required
  and Fantasy Points describes the optimizer ownership as FanShare-powered,
  so the standalone Data Suite entitlement/export must be confirmed when the
  2026 page opens. README and the in-app weekly guide now carry the acquisition
  item, and the old automatic ETR purchase is replaced with a measured
  second-source/fallback decision. Naming the future raw table
  `fantasy_points_*` makes the current daily backup discovery include it.
  Focused app/status and external-import validation passes 19 tests. Next
  implementation step, without interrupting the active immutable fitted-K
  panel, is the dedicated authenticated ownership-page collector, append-only
  importer and status contract before August 24.

### Final-served position calibration passed, promoted, and adopted

- The latest deep-analysis correction was verified in code: positive upstream
  `_widen_draws` factors preserve each row's ranks, and the fully covered
  TabPFN rank-remap therefore erases those factors. The historical served-tail
  imbalance is a final-marginal/TabPFN calibration issue, not a stale-widen
  effect. The independently fitted final-served correction remains valid
  because it is applied after TabPFN shaping and the 45/55 market mean shift.
- Stage A selected frozen mean-invariant factors QB `0.970`, RB `1.005`, TE
  `0.940`, WR `1.070`. On untouched 2023--2025 rows they improved absolute
  position q90/q95/q99 gap `0.006113 -> 0.003149`, mean q95/q99 pinball ratio
  to `0.996151`, WR q99 exceedance `1.881% -> 1.439%`, TE q99
  `0.737% -> 1.079%`, and both 20/30 Brier losses. CRPS worsened only
  `0.3005%`, within the frozen limit, with maximum row-mean drift
  `7.11e-15`.
- The exact-80 Stage B protocol is tracked in
  `reports/2026-08-11-served-position-calibration-lineup.md`. Same-image
  control `20260811-lockfix-e80-k1-role12-position-control-v1` and treatment
  `20260811-lockfix-e80-k1-role12-position-scales-v1` used CE 0 / direct-role
  12 / boom 40, line 194, the same seeds, and evaluation seasons 2023--2025.
  All six replay executions and check-only acceptances succeeded; durable IDs
  are in the protocol and panel manifests.
- The first comparator `compare-served-position-stage-b-jr6kl` failed before
  importing or querying because the image omitted the comparator script. No
  score field was produced. Packaging-only repair commit `c1fbb58` passed
  exact-tree Cloud Build `59bfd59c-2c14-4a8c-a226-40b22a31fa57` with 899
  tests passed and two expected skips, publishing digest
  `sha256:535230fdce1396d1544abffc69676d5fc3b4f42b485fa7d15e54365148d982a7`.
  Comparator-only execution `compare-served-position-stage-b-repair-qzwrs`
  then completed on the unchanged books with zero failures.
- The control exactly reproduced all 54 accepted-source evaluation weekly
  maxima. Both arms have 29,285 player-feature rows with zero missing or
  mismatched rows and maximum numeric delta `3.55e-15`; all shared actuals
  match and maximum persisted shared served-mean delta is `0.0000305176`,
  within the registered `1e-4` storage tolerance. All 108 winner-position
  decompositions resolve every player. Candidate membership changes
  668/667 rows as expected from a tail-shape mechanism.
- Full 107-slate selected counts at 187/194/200/210/220/230/240 improve from
  `34/22/11/7/5/3/2` to `34/24/13/7/5/3/2`. The frozen tail-first order ties
  through 210 and first differs positively at 200, so machine disposition is
  `pass`. Pool oracle at 200 improves `16 -> 19`. Mean weekly best declines
  `180.1207 -> 179.8361`; it is diagnostic and not a veto under the operator's
  standing maximum-score objective. Threshold gains are 2023w3
  `197.36 -> 215.56`, 2024w14 `177.46 -> 194.08`, and 2024w17
  `191.16 -> 204.06`; 2024w5 loses a 210 (`213.48 -> 206.88`) while 2023w3
  creates its replacement, preserving the aggregate 210 count.
- Canonical promotion `accept-replay-panel-z784c` passed and copied treatment
  seasons 2023--2025 to the accepted research tables; accepted historical
  seasons 2019/2021/2022 remain unchanged. The durable comparison report is
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-position-scales-v1/served_position_stage_b_comparison.json`.
- Production policy is now `classic-k1-role12-boom40-poscal-v3`, source panel
  `20260811-lockfix-e80-k1-role12-position-scales-v1`, K=1, CE 0, direct-role
  12, boom 40, exact 80, line 194, and the four factors above. This one object
  drives projections, UI/API and both CSV routes. A role-registry outage
  restores the complete prior `classic-k1-ce12-boom28-v1` identity-scale
  book; it does not mix the new calibration into an untested fallback.
  Focused policy/app/live-order/fallback tests pass. Exact-tree full Cloud
  Build and deployment of the resulting digest are the next validation step.
- After deployment, the next scientific action is the preregistered R3
  question corrected for the TabPFN finding: independently calibrate the
  **final-served** control and Route Share treatment distributions, freeze the
  factors without lineup outcomes, then compare once. Do not rerun upstream
  widen factors, which TabPFN erases. In parallel only after freezing its
  usage-only estimator, the genuinely new R4 diagnostic may fit Dirichlet K
  from leave-season model-fitted shares rather than select K from scores.
  That R3 design is now frozen before producing any new calibrated output in
  `reports/2026-08-11-route-share-final-served-recalibration.md`. It uses
  strict walk-forward factors per arm and target: 2023 fits only 2022;
  2024 fits 2022--2023; 2025 fits 2022--2024. Factors act after TabPFN and the
  market shift, preserve means, and retain the original aggregate 30-point
  Brier decision. A pass licenses one separately frozen exact-80 comparison;
  a fail closes the historical retry. Implement this diagnostic without
  querying its new calibrated results until the implementation commit passes
  exact-tree validation.
  The diagnostic is now implemented behind
  `route-final-served-calibration-diagnostic` with a one-shot immutable runner
  `scripts/cloud_route_final_served_calibration.sh`. It reproduces final
  TabPFN-shaped, market-blended control and exact four-feature Route worlds for
  2022--2025; fits separate arm/target QB/RB/TE/WR factors on the frozen grid;
  validates strict row/outcome/coverage alignment and control accepted-mean
  parity; and reports the frozen metrics, paired week-clustered uncertainty,
  factor curves and mean invariant. Factor curves use the common registered
  grid plus aligned objective arrays so the one structured Cloud log stays
  below its size limit. Twenty-nine focused Route/position tests, compilation,
  CLI wiring, shell syntax and whitespace checks pass locally. Commit and run
  a new exact-tree Cloud Build before the sole diagnostic execution; do not
  inspect or produce its calibrated result before then.

### Tail-first law revised; role-union v2 adopted and live

- Corrected direct-role confirmation
  `20260810-lockfix-e80-k1-role12union-8677d21` passed immutable 2024
  preflight `replay-lockk1role-smoke-bbg27` and launched all six season jobs
  from corrected generation digest
  `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`:
  `replay-lockk1role-2019-7hb9j`, `replay-lockk1role-2021-42gdb`,
  `replay-lockk1role-2022-mhn54`, `replay-lockk1role-2023-qzfdq`,
  `replay-lockk1role-2024-w2ft7`, and `replay-lockk1role-2025-w4bnb`.
  All six completed successfully. Check-only acceptance execution
  `accept-replay-panel-vlxrz` passed 107 complete exact-80 books. Frozen
  comparator execution `compare-corrected-k1-direct-role-d2wn4`, using digest
  `sha256:5319704c23ac40f30771a43b2fb6b4d012a7b2d8f610b980ecfd509ba55deb6b`,
  returned disposition `pass` with zero source-containment, shared-score,
  p-line, or support mismatches. At 240/230/220/210 the corrected K1 source is
  `1/2/4/7` and direct-role is `2/3/5/7`; the broader
  187/194/200/210/220/230/240 grid is `34/22/11/7/5/3/2`, mean weekly best
  `180.1207`, median `178.44`, and pool oracle `42/28/16/9/5/3/2`.
  Direct-role is now the corrected research incumbent. Promotion execution
  `accept-replay-panel-2prcg` completed successfully and copied the complete
  candidate books plus player snapshots into the accepted research tables.
- The new operator-supplied post-window review has been reconciled against
  the actual code and durable results in
  `reports/2026-08-11-post-window-review-reconciliation.md`. Its strongest
  lead is valid but not yet a production-path finding: raw component draws
  exceeded q90/q95/q99 at 11.11%/7.10%/2.69%, before the fitted widening,
  TabPFN/empirical marginal shaper and 45/55 market blend that score the
  adopted books. The exact next diagnostic is frozen before generating those
  unseen final-path quantiles in
  `reports/2026-08-11-served-tail-calibration-protocol.md`. It must reproduce
  the exact 13,876 active accepted RB/WR/TE rows for held-out 2023--2025,
  match every persisted pre/post-blend mean within `1e-4`, report
  q90/q95/q99 exceedance, pinball, CRPS, 20/30 Brier and week-clustered
  uncertainty, and confirms the defect only if all three exceedances are
  high and q99's clustered 95% lower bound remains above 1%. A confirmation
  licenses one separately frozen mean-invariant recalibration; it cannot
  reopen a closed vendor arm. Advanced Rushing collection is deliberately
  deferred until this cheaper, directly relevant calibration path resolves.
  Implementation now reproduces the frozen production environment, aligns
  final draws to exact accepted rows, checks the accepted pre/post-blend
  means, and reports pinball, CRPS, Brier and both binomial and week-clustered
  exceedance uncertainty. The new CLI is
  `served-tail-calibration-diagnostic`; one-shot runner
  `scripts/cloud_served_tail_calibration.sh` requires an immutable image and
  records one execution/report. Twelve focused served-tail/Route-component
  tests pass, with compilation, CLI discovery, shell syntax and whitespace
  clean. Exact-tree Cloud Build
  `98d988c4-ba7e-4dc6-b36b-73ec5842d761` passed 827 tests with two expected
  skips and published immutable digest
  `sha256:4501adb4d4d7389feb931b4f2696eb780c18f3207d5e00732b54c5d616bdf7ff`.
  The one immutable execution `served-tail-calibration-6fk9k` completed and
  reproduced exact fold populations 4,666/4,596/4,614 with zero actual and
  post-shaper mean delta and maximum post-blend mean delta `3.55e-15`.
  Aggregate served q90/q95/q99 exceedance is
  `10.5794%/5.4627%/1.4774%`; q99's week-clustered 95% interval is
  `1.2526%--1.7021%`, wholly above nominal. The frozen defect gate therefore
  passes. The durable report is in
  `reports/served-tail-calibration-runs/20260811-served-tail-calibration-v1/`.
  One follow-up is now frozen before producing any corrected metric or score
  in `reports/2026-08-11-served-tail-recalibration-experiment.md`: fit one
  global mean-invariant RB/WR/TE spread scale only on 2019/2021/2022 final
  served draws, gate it on untouched 2023--2025 calibration/loss metrics,
  and only then run one exact-80 2023--2025 lineup treatment. The exact next
  action is to implement and validate Stage A; production remains unchanged.
  Stage A is now implemented locally: the shared scaler runs only after
  shaping and the market mean shift, changes only RB/WR/TE spread, preserves
  each mean within `1e-10`, and is pinned to identity by the live production
  policy. The frozen fitter evaluates `1.000..1.250` by `0.005` using only
  equal-season normalized q95/q99 pinball on 2019/2021/2022, then gates the
  one factor on exact untouched 2023--2025 rows. It reports paired
  week-clustered loss uncertainty and cannot launch a lineup treatment unless
  Stage A passes. Replay and live paths call the same helper. The complete
  local test suite passes with the expected skip, plus compilation, CLI,
  shell and whitespace checks. Exact-tree Cloud Build
  `fc4a2b96-e428-44b4-9f0f-93eff87efc81` from implementation commit
  `623b1b4` passed 831 tests with two expected skips and produced immutable
  digest
  `sha256:a7fb5dd48960cb26292a5ae60f6c71df8789cc06ba87497659916e63ed61972c`.
  The one immutable Stage A execution `served-tail-recalibration-l49zt`
  completed from that digest and passed every frozen gate. The pre-evaluation
  2019/2021/2022 fit used 4,395/4,755/4,625 rows and selected global factor
  `1.025`. On the untouched 13,876 evaluation rows, q90/q95/q99 exceedance
  improved from `10.5794%/5.4627%/1.4774%` to
  `10.2767%/5.2393%/1.3332%`; q99 absolute error improved 30.2% and the
  equal-season q95/q99 pinball ratio was `0.997879`. Both 20/30 Brier losses
  improved slightly. CRPS worsened 0.334%, within the frozen 0.5% limit, and
  every row mean was preserved within `7.11e-15`. The durable report is under
  `reports/served-tail-recalibration-runs/20260811-served-tail-recalibration-stage-a-v1/`.
  This licenses exactly one factor-1.025 direct-role exact-80 treatment on
  2023--2025; it does not yet alter production. The exact next action is to
  build and launch the now-implemented Stage B partial panel. Candidate
  persistence records the scale, canonical acceptance supports and strictly
  checks the exact requested season set, and the immutable wrapper is fixed
  to panel `20260811-lockfix-e80-k1-role12-tail1025-v1`, seasons 2023--2025,
  factor `1.025`, 80 entries, 12 direct-role candidates and 40 boom
  candidates. The comparator audits exact player-input/mean/seed/lever
  invariance apart from the scale, combines untouched source 2019/2021/2022
  with treatment 2023--2025 for 107-slate metrics, and applies the frozen
  240/230/220/210 decision order. Mixed high-threshold results require
  operator review. The complete local test suite, focused contracts,
  compilation, shell syntax and whitespace checks pass. Production is still
  pinned to identity. Exact-tree Cloud Build
  `82147e17-6c8d-4a99-bd3d-b56475d0724a` succeeded from commit `3431add` and
  published immutable digest
  `sha256:22f0936b307236a2cfc9462f50e9bf4bd31f57dfa0b7975132baec9766db90e8`.
  The sole Stage B launch used immutable 2024 smoke
  `replay-lockk1tail-smoke-md2tb` passed, then the wrapper launched
  `replay-lockk1tail-2023-bdhsj`, `replay-lockk1tail-2024-4727d`, and
  `replay-lockk1tail-2025-6mnfb`. The exact manifest is tracked under
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-tail1025-v1/`. Do not
  rerun this treatment or test another factor.
  All three treatment executions subsequently completed successfully.
  Check-only acceptance `accept-replay-panel-mmkps` passed the exact 54-slate,
  exact-80 contract. First comparator execution
  `compare-served-tail-stage-b-pgwcw` failed mechanically: its `1e-6`
  candidate-mean tolerance was below persisted float resolution, flagging
  4,342/13,562 shared rosters whose absolute deltas were only
  `0.000015--0.000031`, while all 29,285 player-input rows were invariant to
  `3.55e-15`. Its unbounded per-draw generator summary also exceeded a single
  structured Cloud log payload. Score fields became visible before this was
  diagnosed and are recorded without alteration in
  `comparison_failure_diagnostic.json`: the full challenger is
  `33/23/13/7/5/3/2` at 187/194/200/210/220/230/240 versus incumbent
  `34/22/11/7/5/3/2`, with means `179.952` versus `180.121`. The repair is
  frozen after disclosure: keep books and score law unchanged, use an absolute
  candidate-mean tolerance of `1e-4`, report the max delta, collapse only
  per-draw role provenance for bounded logging, and run one comparator-only
  execution from a new immutable image. Thirty-two focused tests pass; the
  unchanged-books local validation cleared all invariants and returned neutral
  because 240/230/220/210 tied at `2/3/5/7`. Mechanical repair commit
  `cb9d851` then passed `859 passed, 2 skipped` in exact-tree Cloud Build
  `56664509-b59c-4005-ad22-720b7d4228d3`, publishing immutable digest
  `sha256:52cf9615755f3c4228accabd180601231d9d605d1a31bd1285a2ab78ea84f937`.
  Comparator-only repair `compare-served-tail-stage-b-repair-lpgt2`
  completed successfully on the unchanged books and confirmed zero failures,
  the `0.0000305176` maximum shared-mean delta, and final disposition neutral.
  The treatment keeps 240/230/220/210 at `2/3/5/7`, improves 200 `11→13` and
  194 `22→23`, declines 187 `34→33`, and lowers mean/median slightly. It does
  not pass the frozen high-tail law and is not promoted. Production remains
  identity; never regenerate this treatment or retry its factor. The lower-
  threshold gain is retained only as a prospective diversification clue.
- The next post-window-review action is frozen in
  `reports/2026-08-11-advanced-receiving-support-window-collection.md` and the
  declarative plan
  `automation/fantasy_points/plans/same-season-advanced-receiving-support-windows-v1.json`.
  It contains exactly 108 unique grouped-header Player exports: 56 cumulative
  prior windows for 2022--2025 target Weeks 5--18 and 52 last-four-prior
  windows for target Weeks 6--18; Week 5 is not duplicated because both
  definitions are Weeks 1--4. Every source week is strictly before its target
  week. This phase permits only collection and an outcome-blind support and
  redundancy audit of six preregistered receiving fields; it cannot inspect
  target outcomes, choose a predictive feature, generate candidates, score a
  lineup, or alter production. The plan check validates all 28 catalog reports
  and expands to exactly 108 artifacts, and all 23 focused downloader tests
  pass. Commit `5627f30` freezes and pushes this protocol. The outcome-blind
  audit implementation is now local behind
  `fantasy-points-advanced-receiving-support-audit`: it accepts no outcome
  fields; reports fixed 20/40/80-route support, six-field availability,
  cumulative/last-four overlap and predictor-only redundancy; and requires the
  exact complete hash-locked 108-export manifest. The audit was further
  hardened to emit JSON `null` for undefined constant-column correlations and
  to measure every route/feature support rate against the full eligible target-
  slate player universe, not just vendor-returned rows. The exact predictor-
  only BigQuery query has been schema-validated live. Twenty-seven focused
  tests, compilation, CLI discovery and whitespace checks pass; the complete
  866-test collection also finishes successfully with its expected skips.
  The first browser run
  `20260811T145426Z__same-season-advanced-receiving-support-windows-v1`
  preserved 52 valid files and failed visibly when export 53's Apply response
  exceeded 120 seconds. Clean recovery run
  `20260811T155845Z__same-season-advanced-receiving-support-windows-v1`
  re-hashed/reused those 52 and completed all 108 with zero failed entries.
  The outcome-blind audit normalized 34,227 WR/TE window rows: 33,432 resolved,
  795 unresolved, zero ambiguous and ten split duplicates suppressed. The
  vendor surface contains no RB rows, so the audit universe was mechanically
  corrected to WR/TE before interpretation. Cumulative target-universe match
  rates are 66.57% WR/65.58% TE versus 58.28%/58.72% last-four; cumulative
  >=40-route support is 46.70%/39.48% versus 34.12%/22.93%. TPRR, YPRR and XFP
  per route are the only stable nonduplicate block (maximum pooled absolute
  predictor correlations 0.586/0.524/0.604 cumulative), while aDOT, air-yard
  share and first-read rate are closed by correlations 0.886/0.914/0.928.
  The machine report and readable disposition are tracked under
  `reports/fantasy-points-support-runs/20260811-advanced-receiving-support-v1/`
  and `reports/2026-08-11-advanced-receiving-support-audit.md`.
  One diagnostic is frozen before outcomes in
  `reports/2026-08-11-advanced-receiving-same-season-diagnostic.md`: exact
  cumulative >=20-route support, a fixed last-four/80-route blend, exactly the
  three retained fields, 2023--2025 walk-forward folds, deterministic residual
  ensembles, all-row CRPS/q95/q99 primary gates, Brier safeguards and paired
  week-clustered uncertainty/MDE. The completed normalized collection is now
  create-only in private table
  `nfl_raw.fantasy_points_advanced_receiving_windows` with 34,227 rows; the
  mandatory repeated write returned `already-identical`. Backup snapshot
  `nfl_backups.fantasy_points_advanced_receiving_windows_20260811` contains
  exactly 34,227 rows, and the table is explicit plus dynamically discoverable
  in the backup code. The local diagnostic implementation follows the frozen
  three-field blend, Ridge/logistic laws, deterministic 1,000-member residual
  ensembles, walk-forward folds, CRPS/pinball/Brier metrics, week-clustered
  intervals and MDE. Fourteen focused ingestion/diagnostic/backup tests pass,
  compilation, CLI discovery and whitespace checks are clean; all 871
  collected repository tests finish successfully with the expected skip.
  Implementation commit `5aee8aa` was pushed before the one outcome query.
  The frozen run then evaluated 6,710 supported held-out rows and 101 realized
  30-point events, clearing both support gates but failing the scientific
  gate. CRPS worsened `3.009499 -> 3.014598` and MAE worsened
  `3.976948 -> 3.988477`, each in all three folds; their paired week-clustered
  95% treatment-minus-control intervals were wholly unfavorable at
  `+0.001829--+0.008059` and `+0.005517--+0.017644`. Equal-fold q95/q99
  pinball ratio was `0.999835`, short of the required `0.995`; 30-point Brier
  was effectively neutral but slightly worse. The durable machine report is
  `reports/fantasy-points-diagnostic-runs/20260811-advanced-receiving-v1/diagnostic.json`
  and the readable result is
  `reports/2026-08-11-advanced-receiving-diagnostic-result.md`. This exact
  family is closed with no lineup arm, retry or production change.
- The outside review's prospective Route Share recommendation is now frozen
  before any 2026 Route value or outcome in
  `reports/2026-08-11-route-share-2026-operating-contract.md`. The declarative
  2026 plan uses exactly source Week W-1 for target Weeks 2--18, and the
  downloader can select one target via `--target-week`. The new weekly importer
  requires one complete frozen-plan manifest, re-hashes and schema-checks the
  artifact, proves source < target, resolves against point-in-time 2026
  rosters while retaining unresolved audits, archives exact bytes to a
  create-only hash-addressed GCS object, and append-only rejects any stored
  value/hash conflict. `017k_fantasy_points_route.sql` derives last/l4/jump/
  cross-season features mechanically from strictly earlier observations and
  joins the same nullable, labeled-fallback fields to training and inference;
  the production model remains unchanged unless an explicit shadow model opts
  into the already registered four features. A dedicated leakage assertion
  enforces source season/week < target season/week, and backup discovery has a
  focused actual-table guard. The live target-Week-2 plan/catalog check
  validates all 28 reports and expands to exactly one Week-1 artifact; the
  combined Route/training/inference SQL passes a BigQuery dry run. The complete
  local suite passes `850 passed, 2 skipped`, with compilation and whitespace
  checks clean. The implementation and operating docs are pushed in `9cf0965`;
  the three operator review documents remain deliberately untracked.
  Exact-tree container build `8153b6d9-9e56-406d-b692-1d7cf215f7d4`
  succeeded from `8bd5588` and published digest
  `sha256:44b478167ffb39d09357678d5e6469bd67c330805846825edcea325775292377`.
  This is a build artifact only; no live job has been redeployed from it.
- The review's other prospective recommendation is frozen, without using the
  stale offseason samples, in
  `reports/2026-08-11-fantasy-points-live-matchup-capture-contract.md`.
  The `fantasy-points-matchups` command now captures exactly QB Coverage
  Matchup, WR Coverage Matchup and OL/DL Matchups before the target week's
  first kickoff. It selects and verifies Schedule Week W, presses Apply and
  checks its values-response contract, requires the vendor All/default input
  scope, downloads grouped-header CSVs, and rejects the whole capture unless
  every vendor team/opponent pair exactly matches the project-derived 2026
  target-week schedule. Exact passing bytes/manifests can be archived under
  create-only hash-addressed GCS names; Weeks 1--3 retain the vendor's
  prior-season-input regime label and Week 4 onward requires active-season
  inputs. The UI Weekly guide now includes the exact operating command. The
  three existing offseason samples were mechanically checked and correctly
  fail the 2026 Week 1 gate (QB: 33 unexpected/32 missing pairs; WR: 46/32;
  OL/DL: 32/32). Fifty-eight focused Matchup/Route/downloader/backup/status
  tests pass, the installed console entry point is discoverable, and diff/
  shell checks are clean. The first accepted capture must wait for the vendor
  surface to roll to a matching 2026 schedule. The data remains collection-
  only until a separately frozen prospective scoring gate passes; no current
  production path depends on it.
  The complete committed-tree suite subsequently passed all 858 collected
  tests (856 passed, two expected skips). The durable reconciliation of the
  outside review now records this completed Route/matchup implementation and
  the three in-flight immutable Stage B execution IDs.
- The independent Route scoring law is now frozen before 2026 data in
  `reports/2026-08-11-route-share-2026-shadow-gate.md`. It replaces rare-event
  Brier as the sole decision maker with an all-row CRPS primary, q95/q99
  pinball and exceedance calibration, while retaining 20/30 Brier, paired
  week-clustered uncertainty and a reported minimum detectable effect. It
  requires at least 12 paired slates/2,500 covered rows/40 thirty-point events,
  then permits a future-only exact-80 shadow whose final decision is the
  operator's 240/230/220/210/200 lexicographic weekly-max objective. No 2026
  outcome may tune or backfill an earlier forecast. A pre-implementation
  clarification now freezes the exact live pairing: existing `tail_k1` plus
  `tail_k1_role` control versus isolated `tail_k1_route` plus
  `tail_k1_route_role` treatment, both under the same promoted 12 CE / 12 role
  / 28 boom policy. That implementation is now complete locally without
  exposing the Route registry to production. Isolated `tail_k1_route` and
  `tail_k1_route_role` training jobs have exact registered feature contracts;
  treatment inference masks every row except prior-season/hash-attributed
  Week 1 values or exact current-season W-1/hash-attributed values, and both
  training and inference fail closed after Week 1 if the manifest-locked W-1
  source is absent. Source hashes now propagate through the feature SQL.
  Existing `shadow-k1-roleunion` is the paired control and new
  `shadow-k1-route-roleunion` is the treatment; both synchronously persist a
  create-only NPZ containing aligned base/role draws, both component sets,
  served quantiles, market/model means and Route lineage before candidate
  generation. Candidate player snapshots carry the artifact URI/hash and arm
  identity. Five new off-season-paused schedulers are included in the Aug 24
  runbook: a Thursday post-download feature rebuild, two isolated Thursday
  retrains, and the two Sunday treatment snapshots. Deployment verification
  covers both new registries and the treatment job. Local validation passed
  all 874 tests with two expected
  skips before the final per-component/create-only hardening; the superseding
  focused Route/tail/SQL/persistence set passes 101 tests with one expected
  skip, plus compilation, CLI discovery, shell syntax and whitespace checks.
  Exact-tree Cloud Build `3be0f6e0-be9c-4566-bb89-5d2b5559e747`
  subsequently passed 875 tests with two expected skips from code commit
  `9e34565` and published tag `route-shadow-9e34565` at immutable digest
  `sha256:cfa61d612568bd3e1e01a40e49f2d74f26f422ccc163fb4a30769706c04fa501`.
  `build-features` generation 50, `train-weekly-k1-route` generation 1,
  `train-weekly-k1-route-role` generation 1, control
  `shadow-k1-roleunion` generation 2 and treatment
  `shadow-k1-route-roleunion` generation 1 are Ready on that digest;
  deployment verification passes all app/project/control/treatment registry
  and job checks. The five new America/Chicago schedulers are present and
  explicitly PAUSED: Thursday `s-features-route` 06:30,
  `s-train-k1-route` 07:30 and `s-train-k1-route-role` 08:00, plus Sunday
  `s-shadow-k1-route-roleunion-early` 10:20 and `...-late` 11:10.
  Ad hoc infrastructure-only smoke executions `build-features-h5r8q`,
  `train-weekly-k1-route-fm25f` and
  `train-weekly-k1-route-role-kpm4s` all completed successfully. The two
  trainings registered 11 contract-valid component models as
  `pooled/components__tail_k1_route/2026-W33` and
  `pooled/components__tail_k1_route_role/2026-W33`. There are currently no
  2026 Week 1 rows in `nfl_features.player_week_inference`, as expected before
  a real Week 1 DraftKings slate exists, so live player support/source-hash
  verification remains pending rather than being inferred from offseason
  data. No lineup shadow was executed and Cloud Run has zero incomplete
  executions. Keep all five schedules paused through August 23; on August 24
  resume the full 22-scheduler season set. After the first genuine vendor W-1
  download/import, let the Thursday feature/train chain build the treatment,
  then collect the paired Sunday control/treatment snapshots without changing
  the production policy.
- The operator-supplied recommendation-scoreboard review was checked against
  the experiment ledger in
  `reports/2026-08-11-recommendation-scoreboard-pivot-reconciliation.md`.
  Its served-tail correction, Stage B joint-tail implication, prohibition on
  recycling failed marginal families, and prospective contest/payout direction
  are retained. Its assertion that within-team allocation is untested is
  incorrect: `GAME_SIM_USAGE=dirichlet` already tested K=20 (`177.3`, 3/17
  >=194) and K=8 (`175.0`, 11 tails), and the corrected TD ledger lost 19 vs
  27 on the full panel. That mechanism family remains closed; no relabeled
  concentration retune is authorized. All previously launched historical
  non-Fantasy-Points arms are complete. The remaining non-vendor work is
  prospectively data-blocked: 2026 K1/K3/floor/role/selector shadows and a
  contest-aware payout/duplication objective after complete standings and
  payout metadata exist.
- The recommendation-scoreboard file was materially updated at 14:21 CDT and
  now points to a new outside deep-calibration audit. Its dead-call-site and
  stale-constant findings are verified, but its causal account misses the
  actual served order: `DEFAULT_WIDEN` runs before TabPFN marginal mapping,
  which erases every positive row scale by remapping unchanged ordinal ranks.
  The accepted served-tail evaluation had 100% TabPFN coverage overall and in
  every evaluated position, so stale upstream constants cannot explain that
  final-path positional imbalance. The imbalance itself remains actionable.
  A reconciliation is tracked in
  `reports/2026-08-11-deep-calibration-audit-reconciliation.md`, and the one
  new R1/R2 diagnostic is frozen before execution in
  `reports/2026-08-11-served-position-calibration-refit.md`. New command
  `served-position-calibration-diagnostic` first invokes the existing summary
  refit unchanged, then independently fits mean-invariant final-served
  QB/RB/WR/TE factors on 2019/2021/2022 and gates them once on untouched
  2023--2025. It never generates or scores lineups. Five focused calibration
  test files pass 23 tests; compilation, CLI discovery, shell syntax and
  whitespace checks are clean. Pre-result commit `fcbaf0f` is pushed.
  Exact-tree Cloud Build `fa8677da-1d00-4639-86fc-67622df925d5` passed 880
  tests with two expected skips and published immutable digest
  `sha256:0c03d5f31eb2f786a02779502bc4ec6ef3dd03708a43d1ced381c83d033f9c00`.
  The corrected outside review now agrees with the TabPFN mechanism audit.
  Its zero-compute R1-prime decomposition is tracked in
  `reports/2026-08-11-tabpfn-stage-calibration-audit.md`: cached q99 already
  measures QB/RB/TE/WR `1.184%/1.439%/0.711%/1.635%`, and the market shift
  modestly raises final RB/WR to `1.565%/1.881%` while TE ends at `0.737%`.
  The single immutable execution `served-position-calibration-47r24` passed
  every frozen final-served gate. Fit factors from 2019/2021/2022 are
  QB/RB/TE/WR `0.970/1.005/0.940/1.070`. On untouched 2023--2025 rows,
  position-averaged absolute q90/q95/q99 gap fell `0.006113→0.003149`, mean
  position/fold/quantile pinball ratio was `0.996151`, WR q99 improved
  `1.881%→1.439%`, TE improved `0.737%→1.079%`, both Brier losses improved,
  CRPS worsened only 0.3005% inside the gate, and maximum row-mean drift was
  `7.11e-15`. Durable report:
  `reports/served-position-calibration-runs/20260811-served-position-calibration-v1/`.
  This is positive distribution evidence, not a scoring adoption. Exact next
  action was to freeze and implement the one licensed same-image exact-80
  lineup control/treatment on corrected direct-role evaluation seasons only.
  That pre-result implementation is now complete. Protocol
  `reports/2026-08-11-served-position-calibration-lineup.md` fixes the fitted
  QB/RB/TE/WR factors at `0.970/1.005/0.940/1.070`, identity control panel
  `20260811-lockfix-e80-k1-role12-position-control-v1`, treatment panel
  `20260811-lockfix-e80-k1-role12-position-scales-v1`, exact-80 CE0/role12/
  boom40 generation, and the standing 240/230/220/210/200 first-difference
  score law. The shared replay/live helper acts only after TabPFN shaping,
  market mean shift and global identity scale; it requires all four positions,
  permits the frozen narrowing factors, enforces row means within `1e-10`, is
  persisted in candidate provenance, and is pinned to identity by production
  and calibration diagnostics. The paired runner requires the durable passing
  fit and launches both books from the same immutable image. The comparator
  rejects source-control non-reproduction, player/mean/seed/lever differences,
  or incomplete books before scoring, then reports changed weeks and winning-
  roster position contributions. Forty-one focused tests pass with
  compilation, shell syntax and whitespace clean. Production remains identity.
  Implementation commit `d86e4f6` is pushed. Exact-tree Cloud Build
  `34e9f490-5059-4e32-bf26-32c6916dc117` passed 898 tests with two expected
  skips and published immutable digest
  `sha256:0ade85a514d03f8c6c20ecdf60885be52377bffa4e2e826686baca4505c79ccf`.
  Control preflight `replay-lockk1posctl-smoke-gm4w5` and treatment preflight
  `replay-lockk1postrt-smoke-4glbp` both passed. Active control executions are
  `replay-lockk1posctl-2023-ndv6m`, `replay-lockk1posctl-2024-stsgq`, and
  `replay-lockk1posctl-2025-hkp7h`; active treatment executions are
  `replay-lockk1postrt-2023-g2wp4`, `replay-lockk1postrt-2024-jtspx`, and
  `replay-lockk1postrt-2025-xdj42`. Their exact manifests are tracked under
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-position-control-v1/`
  and
  `reports/panel-runs/20260811-lockfix-e80-k1-role12-position-scales-v1/`.
  Exact next action: monitor statuses only without reading partial scores;
  after six clean successes, run check-only exact-season acceptance on both
  and the frozen comparator exactly once. Production remains identity.
  While these jobs run, the lower-priority deep-audit recommendations were
  reconciled without reading lineup outcomes. A route retry must calibrate
  each arm's **final-served** position scales, not erased upstream widening.
  The data-fitted Dirichlet recommendation is genuinely new: existing SBI
  proved only synthetic identifiability and never fit real usage. Its future
  diagnostic must estimate one K from leave-season component-model fitted
  shares and conditional realized allocation likelihood, then pass an
  untouched usage gate before any lineup replay. Neither follow-up is yet a
  score-bearing authorization. All six active position-scale executions then
  completed cleanly. Check-only acceptance `accept-replay-panel-w75gc`
  (control) and `accept-replay-panel-75wpd` (treatment) both passed the exact
  54-slate, exact-80 contract. First comparator execution
  `compare-served-position-stage-b-jr6kl` failed before importing or querying
  the experiment because its validated image omitted the new comparator
  script from the Dockerfile. Its only application log is Python's file-not-
  found error; no mechanism or score output was produced. The frozen books and
  factor remain untouched. Exact next action: commit/push the Dockerfile-only
  packaging repair plus regression test, run a new exact-tree Cloud Build,
  and run one comparator-only repair tied to that failed execution. Never
  regenerate either panel.
- The next paid-data correlation study was frozen and pushed before any
  outcome join at commit `8263fe8`:
  `reports/2026-08-10-fantasy-points-coverage-fit-experiment.md`. It tests only
  four supported WR/TE matchup-fit features derived from strict season N-1
  Man/Zone, Coverage Separation, and opponent Defense Coverage Matrix data.
  It reports Spearman correlation with projection residuals, binary
  correlation and quintile lift for 30-point events, plus fixed control versus
  treatment Brier/MAE metrics on held-out 2024/2025. No alignment, individual
  route, route-break, field, support, or model sweep is licensed.
- The coverage-fit importer/diagnostic is implemented locally behind
  `import-fantasy-points-coverage` and
  `fantasy-points-coverage-diagnostic`, with guarded runner
  `scripts/cloud_fantasy_points_coverage_diagnostic.sh`. Audit-only import
  verified 2,093 normalized receiver rows (2,044 resolved, 48 unresolved, one
  ambiguous, one known duplicate suppressed) and all 128 defense seasons.
  The fixed support rules cover 1,709/5,927 2024 and 1,683/5,775 2025 WR/TE
  snapshot rows. Because those roughly 1,700-row folds are adequate but below
  the provisional 50% availability gate, that gate was explicitly amended to
  25% before any outcome query; features, support thresholds, folds, models,
  and score gates are unchanged. Sixteen focused Coverage/Advanced/Route
  tests pass, along with compilation, shell syntax, and whitespace checks.
  Initial build `bfb523d3-0652-42cf-8c36-357e7166afa5` passed 768 tests with
  2 skipped. The first guarded write created both private raw tables (2,093
  receiver rows and 128 defense rows). The required repeat check exposed a
  reserved BigQuery alias in the check query; no outcome diagnostic had run.
  The alias was fixed with a regression test, and the repeated guarded write
  reported `already-identical` for both tables. Corrected exact-tree build
  `82a58b86-1b13-49b1-a4f9-7e8633d4212d` passed 770 tests with 2 skipped and
  produced digest
  `sha256:d7ff29257db2153d95fc3be1f98223c02e6ddd215b8da925386e35239aa68e22`.
  Backup execution `backup-tables-5bgsw` succeeded with 11 snapshots, 5
  expected absent tables and zero failures; it created UTC-date snapshots
  for both new tables with exact 2,093/128 row counts. Frozen execution
  `fantasy-points-coverage-diagnostic-wbwlf` then returned
  `coverage-fit-player-tail-passes`: aggregate 30-point Brier improved
  `0.01813348→0.01809495`, 2024 improved, and 2025 worsened only 0.20%
  within the frozen 1% limit. Aggregate 20-point Brier worsened 0.24% and MAE
  worsened 0.0123, both mandatory diagnostics. Coverage was 28.83%/29.14%.
  This is a narrow signal, not direct adoption.
- The one licensed coverage lineup test is now preregistered before any
  coverage candidate or lineup outcome in
  `reports/2026-08-10-fantasy-points-coverage-tail-union.md`. After Route
  resolves the source mechanically, it adds exactly twelve novel 2024/2025
  candidates using `proj_tourney + 30 * (treatment_p30-control_p30)`, keeps
  earlier seasons byte-identical, reuses unchanged worlds/selection and
  returns exactly 80. Implementation commit `d977d0c` adds the score-free
  signal loader, replay attachment, twelve-novel-candidate generator, strict
  PIT/parity comparator, CLI and guarded Cloud runner. The full 776-test local
  suite passed, with compilation and whitespace checks clean. Conditional
  wrapper `scripts/prop_lock_coverage_tail_union.sh` is frozen to code
  `d977d0c` and refuses to launch until the Route report mechanically selects
  direct or Route source. Real score-free loader audits produced 1,709 2024
  rows using source season 2023 and 1,683 2025 rows using source season 2024,
  with finite deltas throughout. Exact-tree Cloud Build
  `b9a70848-cf5b-469e-83d4-de43f3af9315` from wrapper tree `848d977` passed
  775 tests with 2 skipped and produced immutable digest
  `sha256:d3d53256d8db9c34f120108bead5bb44a3ab2f512c2db4a7c6956eeb1e3d5534`.
  Route selected the corrected direct-role source, so use this digest for the
  one `direct` coverage panel; there is no dose/feature retry.
- The frozen coverage launch is active. Immutable preflight
  `replay-lockk1cov-smoke-mnxfg` passed. Panel
  `20260810-lockfix-e80-k1-role12-cov12-d977d0c` launched all six executions:
  `replay-lockk1cov-2019-kh9xl`, `replay-lockk1cov-2021-l9bd9`,
  `replay-lockk1cov-2022-4xgrm`, `replay-lockk1cov-2023-nvhqp`,
  `replay-lockk1cov-2024-tvgnt`, and `replay-lockk1cov-2025-ptnj6`.
  All six executions completed successfully: 2019 in 1h32m28s, 2021 in
  1h13m6.01s, 2022 in 1h21m13.89s, 2023 in 1h8m49.79s, 2024 in 1h28m5.73s,
  and 2025 in 1h26m12.01s. Check-only exact-80 acceptance execution
  `accept-replay-panel-t56n4` passed 27,468 candidates across 107 exact-80
  slates with replay/live parity. Coverage candidates were 1.6% of the pool
  and 0.2% of selected slots; acceptance's selected 187/194/200 remained
  `34/22/11`. Frozen comparator execution
  `fantasy-points-coverage-tail-union-gxfwg` then passed every mechanical
  check. It added 432 novel candidates and changed 33 selected slots in each
  direction, but all 107 weekly maxima tied the source exactly. Selected
  187/194/200/210/220/230/240 remained `34/22/11/7/5/3/2`, as did the pool
  oracle `42/28/16/9/5/3/2`; disposition is `keep-source-incumbent`. This
  prior-season coverage candidate arm is closed with no retry.
- The operator supplied an outcome-viewed outside review of the paid Fantasy
  Points data. Its repository-verified disposition is tracked in
  `reports/2026-08-11-fantasy-points-utilization-reconciliation.md`. Weekly
  Route Share remains the clearest incremental asset, but the review omitted
  that the same four Route features worsened held-out residual MAE in both
  folds and aggregate (`2.882990→2.892476`) while improving tail Brier; a
  future full component-model test is therefore open but not a demonstrated
  mean repair. The review also incorrectly called Defense PROE redundant:
  current SQL joins only the offense's own lagged PROE, while the vendor
  Defense PROE is distinct opponent context. Target/Snap require an
  outcome-blind agreement audit before closure, and an early-week Advanced
  retry would still be an outcome-viewed subset. Do not alter the frozen
  unions or restore a significance veto. The eventual 2026 Route path needs
  an idempotent weekly ingest contract; the current importer is historical
  and hash-locked. A shareable operator-facing description of all six weekly
  report families and their current priority is tracked in
  `reports/2026-08-11-fantasy-points-weekly-reports-summary.md`.
- The vendor-window semantics audit is now complete for the first priority
  families. Advanced Receiving Weeks 1--4 versus 5--8 returned 285/299
  players, every populated `G<=4`, distinct hashes and zero unchanged common
  players across `G/RTE/TGT/YDS/FP`. Defense and Offense Coverage Matrix each
  returned 32/32 teams with `G=4` and distinct hashes. Advanced Passing,
  Advanced Rushing, Man-vs-Zone, Separation by Coverage/Alignment, RB+WR
  Efficiency and detailed Snaps also returned distinct exact-window files
  with `G<=4`. This opens same-season strictly prior-week inputs; it does not
  alter the completed N-1 verdicts or in-flight frozen coverage union. The
  full catalog/redundancy disposition is tracked in
  `reports/2026-08-11-fantasy-points-filter-surface-audit.md`.
- The outcome-blind exact-window redundancy audit is tracked in
  `reports/2026-08-11-fantasy-points-redundancy-audit.md`. Existing
  strictly-prior target/air-yard/snap shares, XFP, YPC and YPT reproduce the
  corresponding vendor values closely (typically 0.95--1.00 correlations),
  so they are excluded from bulk model search. Fantasy Points separation is
  distinct from NGS separation, and recent defensive shell deployment has no
  close existing feature. A second outcome-blind screen found Advanced
  Passing `HERO %`, deep-throw rate, pressure rate, turnover-worthy throw
  rate, checkdown rate and `PrROE` only weakly/moderately aligned with the
  nearest existing QB inputs; that complete process family is the best
  follow-up after the coverage diagnostic. Advanced Rushing is somewhat more
  redundant, although missed tackles forced per attempt remains distinct.
  No target-week outcome or residual was read and no second model test is yet
  licensed. A compact same-season Man/Zone diagnostic was
  therefore preregistered before any outcome join in
  `reports/2026-08-11-fantasy-points-same-season-coverage-protocol.md`.
  Its plan contains only Man-vs-Zone, Separation-by-Coverage and Defense
  Coverage Matrix for seasons 2022--2025, target Weeks 5--18 and exact
  last-four-prior windows. Plan/catalog validation expanded 168 safe exports.
  First bulk run `20260811T040729Z__same-season-coverage-last-four-v1` was
  stopped and rejected after the importer proved its apparently filtered
  files contained stale full-2025 rows (`G=17/18`). No row was consumed.
  The downloader now awaits and validates the exact report-values POST,
  rendered game counts, and downloaded Season/G scope. Live regression run
  `20260811T042431Z__apply-scope-regression-check` passed with 299 Season-2022
  rows and `G=1..4`. Run
  `20260811T042759Z__same-season-coverage-last-four-v1` safely completed all
  112 receiver exports, then stopped before the first matrix export because
  the rendered-row guard assumed a visible Season cell that the team grid
  omits. No matrix file was accepted. The guard now recognizes the actual
  Rank/Name/G layout while Apply and CSV gates still enforce Season. Live
  regression `20260811T053128Z__coverage-matrix-window-semantics-v1` passed
  two exact 32-team windows. New immutable run
  `20260811T053208Z__same-season-coverage-last-four-v1` revalidated and
  reused the exact 112-file prefix and is collecting the remaining matrices;
  do not consume it until its final manifest passes the locked importer. The importer,
  same-season PIT attachment/diagnostic, CLI commands and focused tests are
  implemented in the working milestone without reading outcomes. The two new
  raw table names are explicit daily-backup members and also match automatic
  Fantasy Points table discovery.
- The next distinct paid-data family is frozen before any exact-window
  Advanced Passing outcome join in
  `reports/2026-08-11-fantasy-points-same-season-advanced-passing-protocol.md`.
  Its tracked 56-export plan uses seasons 2022--2025, target Weeks 5--18 and
  exact W-4:W-1 windows. The treatment is the complete predeclared QB
  process-rate/time block with an 80-dropback support floor; walk-forward
  held-out seasons are 2023--2025 and only aggregate 30-point Brier plus 50%
  per-fold coverage gates the mechanism. The manifest-locked importer,
  strict-prior attachment, walk-forward diagnostic, CLI and explicit backup
  member are implemented; 12 focused coverage/passing/backup tests pass and
  the real 52-row schema sample parsed all 22 treatment features. Collection
  must wait for the active coverage plan to finish; no table write, outcome
  diagnostic or lineup arm has started.
- Exact-tree Cloud Build `adc359ee-ee1d-4914-a251-680cf05dd221` from commit
  `34dfaa6` passed 801 tests with 2 skipped and produced immutable image
  `sha256:b1292d1ed171e20edf94e8a2f6ded5d63fdb1f83e9daa91e8d3acb6f37fa7d98`.
  Use this digest for both same-season player-tail diagnostics after their
  respective manifest-locked imports; never run from mutable tag
  `same-season-data-34dfaa6`.
- Corrected same-season coverage run
  `20260811T053208Z__same-season-coverage-last-four-v1` completed all 168
  artifacts with zero failures. Audit normalized 16,482 receiver windows
  (16,119 resolved, 363 unresolved, zero ambiguous, three duplicate groups
  suppressed and 6,287 supported) and 1,792 defense rows across all 56
  target windows/32 teams. Both private tables were created; the mandatory
  repeat returned `already-identical`. Backup snapshots
  `fantasy_points_receiver_coverage_l4_20260811` and
  `fantasy_points_defense_coverage_l4_20260811` exist with exact
  16,482/1,792 rows. The one-shot cloud runner ran once with immutable digest
  `sha256:b1292d1e...7fa7d98`.
- Frozen execution `fantasy-points-same-season-coverage-k2zt2` completed
  successfully and returned `same-season-coverage-player-tail-fails`.
  Supported coverage was 23.41%/22.74%/21.79% in held-out 2023/2024/2025,
  below the frozen 30% gate in every fold, and aggregate 30-point Brier
  worsened `0.02956174→0.02971345`. Aggregate 20-point Brier also worsened
  `0.09749424→0.09760344`; residual MAE improved slightly
  `5.67203→5.66299`. The registered correlations were small and unstable.
  Durable artifacts are tracked under
  `reports/fantasy-points-same-season-coverage-runs/20260811-fp-same-season-coverage-l4-v1/`.
  The exact same-season coverage mechanism is closed with no candidate union
  or retry; proceed to the already-preregistered Advanced Passing collection.
- The auditable Playwright downloader under `automation/fantasy_points/` and
  `ops/fantasy_points_downloads.py` is authenticated and operational. It uses
  a persistent profile outside the repository, never commits credentials or
  licensed CSVs, validates the live vendor catalog, runs sequential exports,
  names every file by report/season/source weeks/target week, and writes a
  SHA-256/CSV-shape/retrieval-time manifest. Plans support explicit windows
  and generated cumulative-prior or last-four-prior target-week policies;
  invalid same/future-week source windows fail closed. Direct authenticated
  report routes, custom Headless UI Season/Week controls, context-first
  navigation, mandatory `Apply`, post-Apply exact-week revalidation, custom
  export switches/action and bounded empty-SPA retries are implemented.
  Playwright 1.62, Chromium 151 and system libraries are installed. Seventeen
  focused downloader tests pass. Successful ignored manifests include
  `20260811T033115Z__advanced-receiving-window-semantics-v1`,
  `20260811T033342Z__coverage-matrix-window-semantics-v1`, and
  `20260811T035458Z__coverage-matrix-offense-window-semantics-v1`. Never
  record or request credentials in chat or Git. Long interrupted plans can
  now start a new immutable run with `--reuse-from`; the downloader rechecks
  the exact plan hash, ordered filters, file hash/shape and Season/G scope of
  every copied prefix artifact. The original run is never mutated.
- The live Fantasy Points menu is now guarded in full: exactly 28 NFL reports,
  of which 25 support historical Season + Week(s) plans and only QB Coverage,
  WR Coverage and OL/DL Matchups remain nonhistorical/prospective. The new
  remainder plan sampled both 2025 Weeks 1--4 and 5--8 for all nine previously
  unexercised historical families. Immutable resumed run
  `20260811T062906Z__remaining-catalog-window-semantics-v1` completed all 18
  exact-scope exports. Two fail-closed DOM repairs were required before that
  completion: metric halves may render as separate rows, and Routes Run has
  hidden title copies before its visible heading; Fantasy Points Scored also
  uses Rank/Name/POS/G identity rows. Twenty focused downloader tests and live
  scope regressions pass.
- The remainder audit found no missed immediate priority. Basic stats, Bell
  Cow, detailed Fantasy Points and Routes Run are redundant; Routes Run's
  alignment counts correlate 0.9987--0.9998 with Separation by Alignment.
  Named routes are too sparse over four weeks. Broader Horizontal/Vertical
  route-break groups are the only new lead, with 104--122 players at 20-route
  support per window; keep that lead outcome-blind and behind the already
  preregistered Advanced Passing diagnostic.
- Advanced Passing collection
  `20260811T063609Z__same-season-advanced-passing-last-four-v1` completed all
  56 exact W-4:W-1 artifacts with zero failures. Audit normalized 2,879 QB
  windows (2,868 resolved, 11 unresolved, zero ambiguous, 1,636 supported at
  80 dropbacks). The private table was created and the required repeat
  returned `already-identical`; backup
  `fantasy_points_advanced_passing_l4_20260811` is verified at 2,879 rows.
  One-shot runner `scripts/cloud_fantasy_points_same_season_passing.sh` is
  frozen to the source run/count, accepted panel and immutable image. Launch
  it once with digest `sha256:b1292d1e...7fa7d98`, then record the one
  preregistered result with no scientific retry.
- Frozen execution `fantasy-points-same-season-passing-s887m` completed
  successfully and returned `same-season-passing-player-tail-fails`.
  Supported accepted-QB coverage was 28.39%/26.88%/25.96%, below the 50%
  gate in every fold. Aggregate 30-point Brier worsened
  `0.06357934→0.06628405` and declined separately in 2023, 2024 and 2025;
  20-point Brier worsened `0.19692595→0.20648459` and MAE
  `6.41074→6.67482`. Durable artifacts are under
  `reports/fantasy-points-same-season-passing-runs/20260811-fp-same-season-passing-l4-v1/`.
  The exact Advanced Passing mechanism is closed with no candidate arm or
  retry. Next use the catalog audit's outcome-blind route-break support lead;
  do not test sparse individual named routes.
- The next outcome-unseen mechanism is frozen before collection in
  `reports/2026-08-11-fantasy-points-same-season-route-shape-protocol.md` and
  plan `same-season-route-shape-last-four-v1.json`. It uses only the four
  independent Horizontal/Vertical/Static/Shallow route-count shares, with
  Backfield implicit, Overall routes >=30, seasons 2022--2025, target Weeks
  5--18 and exact W-4:W-1 windows. The five vendor counts partition Overall
  routes exactly in both samples; 30-route support covered 58.2%/52.2% of
  accepted WR/TE rows with prior activity. No conditional efficiency,
  separation score, named route or outcome-selected field is licensed.
  Preregistration commit `99f665d` was pushed before implementation. The
  manifest-locked importer, strict-prior attachment, frozen walk-forward
  diagnostic, CLI and explicit daily-backup member are now implemented.
  The complete 812-test offline suite passes with one expected skip;
  compilation, CLI discovery and whitespace checks are clean. Immutable run
  `20260811T073453Z__same-season-route-shape-last-four-v1` then completed all
  56 exact exports with zero failures. The outcome-blind importer normalized
  16,482 receiver windows (16,119 resolved, 363 unresolved, zero ambiguous),
  suppressed three duplicate groups, validated exact component sums for all
  16,485 source rows and marked 9,489 rows supported. The private table was
  created and the mandatory repeat returned `already-identical`. Backup
  execution `backup-tables-p8ckj` completed successfully; snapshot
  `fantasy_points_route_shape_l4_20260811` has exactly 16,482 rows. One-shot wrapper
  `scripts/cloud_fantasy_points_same_season_route_shape.sh` is frozen to the
  source run/counts, accepted panel and an immutable image. Exact-tree Cloud
  Build `1dfbb3a2-9ab5-410a-933c-0913af4f17f1` from commit `3039af9` passed
  811 tests with two expected skips and published digest
  `sha256:35283c02d0be0bfb1be32fd4c9f8a3d9ee81da15ff20e6dc6d471772a11f3d76`.
  Frozen execution `fantasy-points-same-season-route-shape-fsrdg` completed
  successfully with disposition `same-season-route-shape-player-tail-fails`.
  Held-out support passed at 34.32%/33.60%/34.20%, but aggregate 30-point
  Brier worsened `0.02080521→0.02094089` and worsened in all three folds.
  Aggregate 20-point Brier worsened `0.07253747→0.07256688`; residual MAE
  worsened `4.92840→4.93420`, and correlations were small. Durable artifacts
  are under `reports/fantasy-points-same-season-route-shape-runs/20260811-fp-same-season-route-shape-l4-v1/`.
  The mechanism is closed with no candidate union or retry. No lineup or
  production policy changed. Next perform an outcome-blind strict-prior
  audit of the already downloaded weekly Defense PROE series, the remaining
  distinct opponent-context question, before licensing any model test.
- The outcome-blind weekly Defense PROE audit is now complete. The four
  registered licensed files normalized to 2,174 unique defense-game rows.
  A strict W-4:W-1 mean with at least three games covered all 1,646 scheduled
  defense-week contexts in target Weeks 5--18 for every 2022--2025 season.
  Its maximum absolute Spearman correlation with the nine existing opponent
  inputs was only 0.2955; no outcome column was queried. One single-feature
  QB/WR/TE diagnostic is frozen before outcomes in
  `reports/2026-08-11-fantasy-points-defense-proe-protocol.md`: heldouts
  2023--2025, 90% per-fold coverage and strictly improved aggregate 30-point
  Brier. The private raw table was created with 2,174 rows and the mandatory
  repeat returned `already-identical`. Backup execution `backup-tables-bd497`
  completed successfully; snapshot `fantasy_points_defense_proe_20260811`
  has exactly 2,174 rows. The frozen diagnostic, CLI and one-shot runner are
  implemented; eight focused Defense PROE/backup tests plus compilation,
  CLI discovery, shell parsing and whitespace checks pass. Exact-tree Cloud
  Build `6b84f0cc-bda4-434f-92ba-1b829f5a8c3d` from commit `e34a078`
  passed 815 tests with two expected skips and published immutable digest
  `sha256:0450ef0f2e3b332d7bf415263e044e081111644c25c001d92e94e71bc9ba6573`.
  Frozen execution `fantasy-points-defense-proe-cfvsv` completed successfully
  with disposition `defense-proe-pass-game-tail-fails`. Coverage was 100% in
  all three held-out folds, but aggregate 30-point Brier worsened
  `0.0092894466→0.0092929218`; 2023 and 2025 improved slightly while 2024
  worsened. Aggregate 20-point Brier also worsened
  `0.0334110003→0.0334847264`; residual MAE improved slightly
  `2.7439164→2.7432783`. Descriptive correlations were tiny and sign-unstable.
  Durable artifacts are under
  `reports/fantasy-points-defense-proe-runs/20260811-fp-defense-proe-l4-v1/`.
  The exact mechanism is closed with no candidate union or retry; no lineup
  or production policy changed. Next freeze the full weekly Route Share
  component-model test already left open by the utilization reconciliation,
  without changing its four registered Route inputs after outcomes.
- The full Route Share component-model test is now frozen before any new
  component prediction, simulation or lineup outcome in
  `reports/2026-08-11-fantasy-points-route-component-protocol.md`. It adds
  exactly `fp_route_share_last/l4/jump/cross_season` to same-code K=1
  LightGBM components, evaluates active corrected Sunday-main RB/WR/TE rows
  in held-out 2023--2025, and gates only on 80% per-fold prior coverage plus
  strictly improved aggregate 30-point Brier. Component errors, composed
  point MAE/CRPS, 20-point Brier, quantile exceedance, folds and positions are
  mandatory diagnostics, not vetoes. This is explicitly retrospectively
  motivated because the auxiliary Route outcomes are already viewed; no
  threshold, position subset, coefficient, window, model or feature retry is
  licensed. Next implement the outcome-free attachment/control/treatment
  harness and focused tests, then commit before its one immutable Cloud run.
  A pre-implementation clarification makes all eleven component diagnostics
  use QB/RB/WR/TE Sunday-main rows while the composed primary gate uses only
  Route-relevant RB/WR/TE rows, and pins the adopted possession/team-factor
  simulator; no outcome had been generated under either arm.
  The strict-prior full-panel attachment, K=1 control/treatment harness,
  supported component metrics, empirical CRPS, common-seed 10,000-draw
  simulation, frozen gate, CLI and one-shot Cloud runner are now implemented.
  Route fields are opt-in candidate features only; production is unchanged
  with `EXTRA_FEATURES` unset. The live source contract is exactly 26,881
  resolved rows, four hashes and 1,029 players. Thirty-four focused Route,
  component, feature-set and status tests pass; compilation, CLI discovery,
  shell syntax and whitespace checks are clean. Commit/push this outcome-free
  implementation. Exact-tree Cloud Build
  `fac5d0cb-67d9-4272-9934-80bda8b429ac` from commit `e19df7f` passed 821
  tests with two expected skips and published immutable digest
  `sha256:39d656915f75f67a41b0543456d16acda951f5b2fb4f5b92c09b2fa209827d7b`.
  Outcome-free preflight found all 28,091 accepted 2023--2025 QB/RB/WR/TE
  keys in the training table, with zero position or actual-score provenance
  mismatches. Frozen execution `fantasy-points-route-components-xvvbf`
  completed successfully with disposition `route-share-component-tail-fails`.
  Prior coverage passed at 95.71%/96.06%/96.60%, but aggregate 30-point
  Brier worsened `0.0140014643→0.0140280477`; 2023 improved while 2024 and
  2025 worsened. This is nevertheless the first paid-data component result
  with a consistent mean/distribution-quality gain: composed point MAE
  improved in all three folds and aggregate `3.7879193→3.7315403`, while
  CRPS improved `2.5794510→2.5687227`. Aggregate 20-point Brier worsened
  `0.0499138020→0.0501555362`, and q90/q95/q99 exceedance moved farther
  above nominal. Durable artifacts are under
  `reports/fantasy-points-route-component-runs/20260811-fp-route-components-v1/`.
  Under the tail-first gate, the exact historical component mechanism is
  closed with no lineup arm, calibration retry or production change. Preserve
  the exact Route contract only as a 2026 prospective shadow candidate while
  continuing to the next paid-data hypothesis, preregistered before its
  outcomes; do not describe the mean gain as evidence of improved
  extreme-lineup selection.
- Contest-placement/ROI evidence is now summarized durably in
  `reports/2026-08-10-contest-placement-roi-audit.md`. The local 2025 files
  are first-place-only; BigQuery has 103,556 ownership rows but no
  `contest_entries` table and zero contest-fill rows, so historical ranks
  2--5 and realized GPP ROI cannot currently be computed. Across 68 known
  Millionaire winning lines the corrected direct-role book is 0 wins, 0
  within 20, 2 within 30, 8 within 40, with 57.14 mean gap. On the one 2025
  Week 5 contest with supplied min-cash metadata, 3/80 direct-role lineups
  clear the 169.34 Milly min-cash line and best is 190.04 versus the 246.82
  winner. Preserve full 2026 standings and payout curves immediately after
  settlement; simulated ROI remains an internal upper-bound diagnostic, not
  a bankroll forecast.
- The README season-start schedule and in-app Weekly guide now make the
  ephemeral data requirement explicit: every Monday/Tuesday, upload Entry
  History and preserve the full standings CSV for one target GPP per slate.
  Winner-only roster files such as `reports/2025-milly-rosters.csv` contain
  exactly nine first-place players per week and cannot recover ranks 2--5 or
  realized ROI. The focused UI/status suite passes 13 tests.
- The passed Route Share signal will now be tested from the direct-role
  incumbent. Before launch, `scripts/prop_lock_route_tail_union.sh` freezes
  treatment `20260810-lockfix-e80-k1-role12-route12-aa087b8`, generator code
  `aa087b8`, the exact direct-role settings, and twelve Route candidates on
  2024/2025 only. Use immutable generation digest
  `sha256:b907bc6242d6b872cf10e4ff9ea59e56d89a1b99861780007eb767636a97041c`.
  The wrapper requires the direct-role promotion record. Shell syntax and
  whitespace checks passed. Immutable 2024 preflight
  `replay-lockk1route-smoke-vg5w8` passed, and all six immutable season jobs
  are running: `replay-lockk1route-2019-xmlzn`,
  `replay-lockk1route-2021-qqfch`, `replay-lockk1route-2022-mg9ns`,
  `replay-lockk1route-2023-bn27p`, `replay-lockk1route-2024-5lbcf`, and
  `replay-lockk1route-2025-vm6zd`. All six completed successfully. Exact-80
  check execution `accept-replay-panel-gw5qm` passed all 107 slates. Frozen
  comparison `fantasy-points-route-tail-union-nqx99` returned
  `keep-corrected-incumbent`: the union contained all 27,036 source rows and
  432 novel Route candidates, changed 25 selected slots in each direction and
  selected 10 Route rows, but all 107 weekly maxima tied exactly. Selected
  187/194/200/210/220/230/240 remains `34/22/11/7/5/3/2`, mean weekly best
  `180.1207`, median `178.44`. The Route lineup arm is closed with no retry;
  do not promote its staging rows. Use the direct-role incumbent as the
  coverage source and as the no-floor incumbent unless a later arm promotes.
- The preregistered corrected no-floor candidate union finished generation. Its
  launcher had required the never-launched CE12+role branch; before any
  corrected no-floor generation or outcome read, the protocol and launcher
  were amended to require the accepted direct-role source
  `20260810-lockfix-e80-k1-role12union-8677d21`. The independent no-floor
  treatment remains byte-for-byte the frozen K1 binary ablation. Shell syntax
  and whitespace checks pass. Immutable preflight
  `replay-locknofloor-smoke-dzrqw` passed, and all six season jobs completed
  successfully:
  `replay-locknofloor-2019-4ztp8`, `replay-locknofloor-2021-fjsrj`,
  `replay-locknofloor-2022-swpsn`, `replay-locknofloor-2023-lsb6k`,
  `replay-locknofloor-2024-kjftz`, and `replay-locknofloor-2025-kqwdn`.
  Check-only acceptance execution `accept-replay-panel-jbxkq` passed all 107
  exact-80 slates. The first union execution
  `corrected-floor-union-6rv2c` failed before producing any confirmation JSON
  or comparison result: `floor_union_confirmation.load_panel()` incorrectly
  required `research_eligible=TRUE` even for the staging add-on, whose 25,890
  valid rows are false by construction after check-only acceptance. A second
  pre-result launcher defect was also fixed: gcloud rejected the repeated
  direct-role panel value when source and incumbent were the same, so the
  unchanged CLI call is now passed as one shell argument. The staging loader
  now follows the already-validated Route loader rule—eligibility is required
  only in the accepted table—and a regression test covers both tables. This
  is an operational repair with no score outcome observed, not a parameter or
  decision-rule retry. Exact-tree Cloud Build
  `cb203be1-0765-479b-8fc4-e5d69c8dd056` succeeded and produced immutable
  evaluator digest
  `sha256:bcb88cff4e7f70ea34e0f52997254f420a39041e680eb4e26752ed2f9596fd69`.
  Repaired execution `corrected-floor-union-k8v5b` passed all 107 exact-80
  mechanical checks. It added 6,969 novel candidates and moved selected
  187/194/200/210/220/230/240 from `34/22/11/7/5/3/2` to
  `34/22/13/7/5/3/2`, with mean `180.1207→180.0084` and paired 5 wins/98
  ties/4 losses. Because every active 240→230→220→210 threshold tied, the
  frozen disposition is `keep-corrected-incumbent`; no-floor is not promoted
  and receives no retry. Durable artifacts are under
  `reports/floor-union-runs/20260810-corrected-role-nofloor-union-loaderfix/`.
- The operator's paid-data operations request is implemented on branch `main`
  at commit `ea6dca4`. The README season-start schedule now requires the final
  evidence-selected Fantasy Points reports, exact filters and pre-lock
  deadline to replace the temporary in-app Weekly-guide message before Week
  1; rejected reports will not become recurring downloads, and same-week
  completed data remains forbidden. Daily backups explicitly include
  `fantasy_points_route_share` and `fantasy_points_advanced_prior` and also
  discover every future base `nfl_raw.fantasy_points_*` table. Focused backup
  and UI/status validation passed 16 tests locally. Exact-tree Cloud Build
  `1253eb90-fca7-4bd2-bcac-e4b8e47b9a31` passed 764 tests with 2 skipped and
  produced immutable digest
  `sha256:3c5b0a6f2a450b252ef47a3b41600fd1517923f0f64672a8005593e53f7188a8`.
  Only year-round job `backup-tables` was updated; scheduler `s-backup`
  remains enabled at 07:00 UTC. Verification execution
  `backup-tables-9sqrb` completed with 9 snapshots kept/created, 5 expected
  absent tables and zero failures. It created
  `fantasy_points_route_share_20260810` (27,305 rows) and
  `fantasy_points_advanced_prior_20260810` (3,771 rows) in `nfl_backups`.
- The hash-locked prior-season Fantasy Points Advanced importer and frozen
  player-tail diagnostic are implemented at commit `b014748` behind CLI
  commands `import-fantasy-points-advanced` and
  `fantasy-points-advanced-diagnostic`. It imports only the preregistered
  Passing/Receiving/Rushing fields, resolves identities without outcomes,
  suppresses the known Brock Wright split rates, and attaches exactly season
  N-1 to target season N. Required event counts, Advanced-feature missingness
  and stable 30-point calibration deciles are emitted without changing the
  frozen models or gate. Twelve focused Advanced/Route tests pass; Python
  compilation, shell parsing and whitespace checks are clean. Outcome-blind
  audit-only import found 3,772 source rows, 3,771 normalized rows, 3,705
  resolved normalized rows, 64 unresolved source rows, two ambiguous source
  rows and one coalesced duplicate group. The guarded first write created
  private table `nfl_raw.fantasy_points_advanced_prior` with all 3,771 rows;
  a second write returned `already-identical` without mutation. Direct
  family/season verification found the expected twelve unique source hashes,
  3,705 resolved rows and only the known split duplicate. Exact-commit Cloud
  Build `cfe28aad-21be-4de0-9bcb-d90ff28c7ddc` from tree `755a216` passed
  762 tests with 2 skipped and produced immutable digest
  `sha256:1a0745b2a6aae3b78cfc4dfebb9be1661004c33e24fcf834d427705d9d1f1e6f`.
  Frozen execution `fantasy-points-advanced-diagnostic-vb9xz` completed
  cleanly in 1m44s with disposition `advanced-prior-player-tail-fails`.
  Coverage passed at 60.27%--66.87%, both folds and aggregate 30-point Brier
  improved slightly (`0.013278655→0.013268547` aggregate), but only WR/TE
  improved by position; QB and RB worsened. Aggregate 20-point Brier worsened
  `0.049025677→0.049177765` and residual MAE worsened
  `3.279949→3.303976`. The required two-position gate therefore fails. No
  Advanced candidate arm is licensed, and no position/field/model retry is
  allowed. Durable result artifacts are tracked under
  `reports/fantasy-points-advanced-runs/20260810-fp-advanced-prior-v1/`.
- `fantasy-points/qbCoverageMatchupExport.csv` was validated as a clean
  37-QB/32-column grouped export, SHA-256
  `888d31272b16b921af50fdeec0bcf20ed526873443495c4983079842a1b83c32`.
  The initial prospective interpretation was later disproved: its opponent
  pairs reproduce 2025 Week 1, not 2026 Week 1, while its metrics contain
  completed 2025 totals. It is a schema sample only and is forbidden from
  replays, diagnostics, promotion and live projections.
- The WR Coverage Matchup sample is also validated: 374 unique
  RB/FB/WR/TE rows, 38 grouped columns, no malformed populated values, and
  SHA-256
  `e0e369d4fee3130d0cfea29709d66ad9f74a6ae02f7495e2509c97ac6a221a5a`.
  Its matchup layer also reproduces 2025 Week 1 and has the same schema-only
  disposition. Future matchup snapshots require a mechanical target-schedule
  match plus a pre-lock retrieval timestamp before prospective use.
- The OL/DL Matchups sample and corrected matchup timing disposition are
  recorded on branch `main` at commit `797b6c0`. The file is a complete
  32-team/20-column grouped export, SHA-256
  `15dfbc9759b123d835998546610c3404893a0a9e227c67f865bdc4c31db349db`.
  Its 16 reciprocal pairs exactly match 2025 Week 1 while every row declares
  completed `Season=2025`, `G=17`; none of those pairs matches 2026 Week 1.
  It is hindsight schema evidence only, cannot support historical testing,
  and may be recollected prospectively only after the vendor rolls the page
  to the target schedule and before the shared slate lock.
- Paid acquisition follow-up: Basic Receiving, Routes Run and Bell Cow were
  declined as materially redundant with the existing weekly share and
  Advanced exports. The operator was asked to preserve 2022--2025 Receiving
  Man-vs-Zone and Separation-by-Coverage/Alignment/Routes/Route-Breaks files,
  plus one current WR Coverage Matchup snapshot. These are acquisition-only;
  none is licensed for a model, diagnostic or lineup arm until its schema and
  point-in-time availability are inspected and a distinct protocol is frozen.
- All four Receiving Man-vs.-Zone exports are now validated and hash-locked at
  commit `ded9344`: 545/517/528/526 rows in 2022--2025 with identical grouped
  Overall/Man/Zone/Single-High/Two-High schemas. They are season aggregates
  and therefore strict N-1 priors only. A vendor semantic defect makes QB
  `FP/RR` unusable (one receiving route paired with full QB fantasy scores as
  high as 336.46); any future treatment must exclude QB, freeze minimum route
  support before outcomes, and use a separate protocol. The files are not
  added to the already-frozen Advanced diagnostic. Continue acquisition with
  Separation by Coverage, Alignment, Routes and Route Breaks, then one
  current prospective WR Coverage Matchup snapshot.
- Receiving Separation-by-Routes is also validated at commit `525ee31`:
  540/513/522/519 RB/FB/WR/TE rows for 2022--2025, 95 unique grouped
  columns covering Overall plus twelve named route families, and no malformed
  numeric cells. Blank route splits are legitimate; the known 2022 Brock
  Wright split is the only duplicate. This is sparse full-season aggregate
  data, so any later N-1 diagnostic must freeze a small football-motivated
  feature block and minimum route support before outcomes. It is acquisition-
  only and does not alter the frozen Advanced treatment.
- Receiving Separation-by-Route-Breaks is validated at 540/513/522/519 rows
  with 41 grouped columns spanning horizontal, vertical, static, shallow and
  backfield concepts. It is a lower-dimensional possible alternative to the
  individual-route grid, not permission to test both after outcomes. The same
  N-1, minimum-support and separate-preregistration restrictions apply.
- Defense Coverage Matrix 2022--2025 is validated at exactly 32 teams and 22
  complete columns per season. Hashes and the unprefixed/misspelled 2025
  source filename are recorded in the intake report. The vendor repeats
  `FP/DB` within both Man/Zone and middle-of-field groups even with group
  headers, so any importer must assign those four fields by frozen positional
  context and reject reordered schemas. These are N-1-only acquisition data;
  acquire the four Offense Coverage Matrix files before considering a
  distinct scheme-matchup protocol.
- Offense Coverage Matrix 2022--2025 is also complete and validated at the
  same 32-team/22-column shape with all cells populated. Exact hashes are in
  the intake report. Both sides of a possible N-1 scheme-matchup signal now
  exist, but no diagnostic is licensed until the remaining Separation by
  Alignment family is acquired and a small support-aware feature block is
  frozen before any outcome join.
- Receiving Separation-by-Coverage 2022--2025 is complete and hash-locked on
  branch `main` at commit `7635c5e`: 540/513/522/519 rows with a stable
  38-column grouped schema spanning
  Overall, Man, Zone, Red Zone, and Cover 2/3/4/6. All populated metrics parse
  numerically; the skill-position identity universes match the other
  separation reports. Four 2024 Denver players each have one overall route
  without a Man/Zone/Red Zone assignment, now recorded in the deficiency log;
  future code must preserve that missing classification. The data remains
  strict season N-1 and acquisition-only. Separation by Alignment is the last
  requested historical receiver family before an outcome-unseen scheme
  protocol may be designed.
- Receiving Separation-by-Alignment is now also validated on branch `main`
  at commit `fcce6d5`: 540/513/522/519 rows with a stable 41-column grouped
  schema. Wide, Slot,
  Inline and Backfield route counts reconcile exactly to Overall for every
  row, every populated metric parses numerically, and the identity universes
  match the other separation reports. Exact hashes are in the intake report.
  This completes the requested historical receiver-separation acquisition;
  all files remain strict N-1, acquisition-only evidence until a small
  support-aware feature block and gate are preregistered before outcomes.

- Optimization has resumed with one new point-in-time information path rather
  than another selector sweep on the same 107 outcomes. Protocol
  `reports/2026-08-10-market-tail-disagreement-experiment.md` freezes a
  common-slate-lock diagnostic of signed production-versus-DraftKings
  alternate-yardage tail disagreement before querying its current-panel
  outcomes. Availability-only inspection found all 18 corrected main slates
  and 1,576/1,700 covered primary-market player rows in 2024/2025; 2023 has
  only four covered slates and is excluded. The diagnostic trains fixed
  low-capacity control/treatment models on 2024 and evaluates 2025 30-point
  Brier, 20-point Brier and residual MAE. If and only if it passes, one
  predeclared twelve-candidate market-belief union may run against live v2;
  it preserves incumbent scoring/selection worlds and uses the revised
  240→230→220→210 operational law. This is distinct from and does not reopen
  the rejected raw `ALT_CEIL`, `DIV_TILT`, or q99-wildcard mechanisms.
- Preregistration `53c78d8` and implementation `391934e` are pushed on
  `main`. Guarded implementation lives in
  `analysis/market_tail_disagreement.py`, CLI
  `market-tail-diagnostic`, and
  `scripts/cloud_market_tail_diagnostic.sh`. Nine focused market tests pass,
  Python compilation, shell parsing and `git diff --check` are clean.
- Full exact-tree validation build `9780568e-c338-49fd-af55-27909542625c`
  passed 727 tests with 2 skipped and produced immutable digest
  `sha256:4bed5d04fe433b0a9da6fc2a4f4d3464af8aeab9cafa653e30d4d3366841355e`.
  Frozen execution `market-tail-diagnostic-jg52t` then completed and failed
  the mechanism gate: 2024 edge-quintile residual separation was negative
  (`-0.3587`) despite positive 2025/aggregate signs, and held-out 30-point
  Brier worsened `0.0305295→0.0305408`. Residual MAE and WR/TE-only metrics
  improved slightly, but those diagnostics cannot override the frozen gate.
  No lineup union may launch, current live v2 is unchanged, and no quota was
  spent. Durable artifacts are tracked under
  `reports/market-tail-runs/20260810-market-tail-v1/`.
- While enforcing the alternate-prop common lock, a more important existing
  point-in-time defect was confirmed in `models.prop_market.market_points()`:
  historical standard props use each game's two-hour pre-kick close, so
  late-afternoon main-slate players receive lines written after the shared
  1 p.m. DFS lock. Availability-only audit found post-lock market use on
  1,842/1,788/1,716 accepted player-weeks in 2023/2024/2025; honest pre-lock
  rows are absent for 1,841/1,617/1,315 of them. Full correction and
  revalidation order are frozen in
  `reports/2026-08-10-prop-common-lock-correction.md`. Existing panels remain
  preserved but are point-in-time-ineligible for new decisions until K3,
  K1, CE and role are rebuilt on the fixed common-lock reader. The live
  mechanism remains provisionally served because freezer snapshots occur
  before lock, but its historical adoption evidence must be re-established.
  No quota spend is authorized.
- The strict reader is now implemented in `models/prop_market.py`. It derives
  the exact domestic Sunday-main cutoff from schedules, selects the latest
  row strictly before it (including a valid opening when no later row exists),
  logs excluded post-lock volume, and returns model-only fallback when honest
  coverage is absent. A companion repair consolidates multiple prop aliases
  to one player-week; the live warehouse read now returns 4,452/4,687/5,008
  unique priced player-weeks in 2023/2024/2025 with zero duplicates. Eleven
  focused market tests pass, including London/1 p.m./late/SNF cutoff, exact-
  lock exclusion, latest-valid selection, TD-only, no-prop and alias cases.
  Exact-tree Cloud Build and both immutable one-week replay smokes passed;
  the validated digest and durable execution IDs are recorded below.
- Revalidation runner `scripts/prop_lock_rebaseline.sh` freezes the corrected
  panel chain and 2024 preflight: K3
  `20260810-lockfix-e80-k3-8677d21`, K1
  `20260810-lockfix-e80-k1-8677d21`, CE12
  `20260810-lockfix-e80-k1-ce12-8677d21`, and role union
  `20260810-lockfix-e80-k1-ce12-roleunion-8677d21`. It is shell-parse clean;
  CE/role modes fail closed until their exact corrected source panel has been
  accepted. Cloud Build `3470d0d4-df09-4776-96e8-eaf5a76d0243` passed 729
  tests with 2 skipped and produced immutable generation digest
  `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`.
  Corrected K3 2024 preflight `replay-lockk3-smoke-tmjcp` passed, logging
  15,007 excluded post-lock prop rows and completing the full one-week
  true-80 path. Six K3 executions are now running:
  `replay-lockk3-2019-mf5jk`, `replay-lockk3-2021-b8w7x`,
  `replay-lockk3-2022-zsjcj`, `replay-lockk3-2023-dzhqz`,
  `replay-lockk3-2024-7dqbl`, and `replay-lockk3-2025-n95bb`. K1 2024
  preflight `replay-lockk1-smoke-zgm9n` also passed with the same corrected
  coverage. Its six executions are `replay-lockk1-2019-65m5t`,
  `replay-lockk1-2021-qwvqg`, `replay-lockk1-2022-gsddd`,
  `replay-lockk1-2023-75d9m`, `replay-lockk1-2024-9hlf4`, and
  `replay-lockk1-2025-nj6sn`. Both durable manifests are tracked under their
  `reports/panel-runs/` panel directories. Do not inspect partial scores;
  monitor only execution state and row completeness. Once all twelve are
  clean, run check-only acceptance on both and compare under the revised
  240→230→220→210 law before launching CE.
- `scripts/prop_lock_finish_controls.sh` now freezes that completion sequence:
  K3 check→promote, K1 check, then the existing ensemble mechanism comparator
  at exact 80 entries. It deliberately leaves K1 in staging for an explicit
  corrected tail-first decision. Shell parsing and `git diff --check` pass;
  the wrapper and handoff are pushed on `main` at `b6d4d38`.
- One previously untested combination is now preregistered before corrected
  outcomes are available: retain the complete corrected CE/role source pool,
  add the exact binary no-salary-floor K1 pool, and reselect the same 80
  entries at line 194. An outcome-free join of the preserved old pools found
  7,848 distinct no-floor rosters absent from the role pool (73.35/slate), so
  the mechanism is real rather than a relabeling. Full frozen construction,
  the 240→230→220→210 gate, no-retry rule, and live-feasibility requirement
  are in `reports/2026-08-10-corrected-floor-union-experiment.md`. Do not
  launch it until corrected K1→CE→role is complete; do not inspect an old or
  partial union score.
- Outcome-blind implementation support for that future test now lives in
  `research/candidate_union.py`. It preserves source candidate order, appends
  only add-on-novel rosters, fails closed if shared actual/mean/probability/
  world masks differ, reruns the unchanged 194 coverage selector at an exact
  entry count, and applies the highest-difference-first tail law. Thirteen
  focused union/portfolio tests pass; Python compilation and
  `git diff --check` are clean. No corrected no-floor score panel or union has
  been launched.
- `scripts/prop_lock_rebaseline.sh nofloor` now prepares the exact corrected
  K1 no-floor source `20260810-lockfix-e80-k1-nofloor-8677d21`. It refuses to
  launch until all 107 corrected role-source slates are present in the
  accepted table, then changes only `MIN_LINEUP_SALARY=0` from the frozen K1
  control. Shell parsing and whitespace checks pass. Do not invoke it before
  the corrected role comparison is complete; implementation readiness is not
  permission to inspect this score arm early.
- The floor-union evaluator is now complete behind CLI command
  `corrected-floor-union` and guarded runner
  `scripts/cloud_corrected_floor_union.sh`. It constructs exactly one union,
  requires shared rosters to match at all persisted 187/194/200/210/220
  masks, returns 80 entries, and applies 240→230→220→210 against both the
  role source and the actual corrected incumbent. Fifteen focused union,
  selector and portfolio tests pass; compilation, shell parsing and
  whitespace checks are clean. Exact-tree Cloud Build
  `a4079b03-2a23-453f-85b1-917550fc73c0` passed 742 tests with 2 skipped and
  produced immutable evaluator digest
  `sha256:ef0747eb3232ad797488dd8f38dcec522ea8815615120d31b2f7a39e332da85f`.
  The union has not been executed and no union score has been queried.
- A new no-cost information path is preregistered before reading its outcomes:
  lagged weekly NFL Next Gen Stats receiver separation, cushion, intended air
  depth, air-yard share and YAC above expectation. Availability-only audit
  found 8,976 2019--2025 rows and roughly 88% coverage weighted by candidate
  roster appearances. The frozen 2024/2025 low-capacity comparison prioritizes
  30-point Brier loss and requires nonworsening 20-point Brier/MAE plus
  coverage and fold safeguards. Full point-in-time construction and gate:
  `reports/2026-08-10-ngs-receiver-tail-experiment.md`. Do not query its
  outcomes or launch a feature/lineup arm until the corrected K1 control is
  complete and the protocol implementation is immutable.
- The NGS diagnostic is now implemented behind CLI command
  `ngs-receiver-tail-diagnostic`. It excludes week-zero aggregates and
  postseason rows, joins across careers with a strict earlier-week boundary,
  target-weights the last four observations, restricts evaluation to players
  actually present in the corrected K1 candidate pool, and fails closed on an
  incomplete true-80 source. A guarded Cloud Run harvester refuses to start
  until corrected K1 check-only acceptance is recorded. Twelve combined NGS,
  candidate-union, and participation tests pass; compilation, shell parsing,
  and whitespace checks are clean. No outcome query or NGS execution has run.
- A pre-outcome static audit corrected the NGS premise: production already
  uses same-season `separation_l4`, PBP air-yard share, and aDOT. The frozen
  control and implementation now include those raw fields explicitly; the
  treatment asks only whether cross-season last-four carry-forward plus NGS
  cushion/YACOE adds value. This correction occurred before any outcome or
  cloud diagnostic. Build `f68cedf9-2634-413c-bd8c-2e517691755d` contains
  the superseded control and must never run the NGS job even though validation
  completed. Corrected exact-tree build
  `e8dd679c-7a40-4e98-8525-31e4ecf700eb` from commit `2d75ba0` passed 738
  tests with 2 skipped and produced immutable digest
  `sha256:fe380648b9a146a95b8c4d942c484979b50f95762f16a277d704151106a82374`.
  Only that digest may run the NGS job after corrected K1 acceptance.
- Frozen execution `ngs-receiver-tail-diagnostic-nkb2h` subsequently
  completed cleanly after K1 check-only acceptance and returned
  `ngs-receiver-tail-gate-fails`. Coverage was 97.43%/98.25% in 2024/2025
  over 2,936 held-out player-weeks, but aggregate 30-point Brier worsened
  `0.0230785→0.0231012`, 20-point Brier worsened
  `0.0912537→0.0914343`, and residual MAE worsened `5.65602→5.66138`.
  No NGS lineup arm is licensed and no field/regularization/window retry is
  allowed. This does not negate the distinct passed true-route purchase
  diagnostic, because these NGS descriptors do not measure route volume or
  first-read opportunity.
- All twelve corrected-control executions completed cleanly. Both K3 and K1
  now contain 107/107 slates and exactly 8,560 selected rows (80 per slate).
  The apparent earlier K3 2019 Week 17 omission was only asynchronous
  warehouse-write lag; no repair, rerun, or score decision was made. No
  partial score was queried. Frozen finish wrapper
  `scripts/prop_lock_finish_controls.sh` is now running on the corrected
  generation digest; K3 check-only acceptance execution is
  `accept-replay-panel-tk27s`, followed by K3 promotion, K1 check, and the
  K1-versus-K3 ensemble comparison.
- K3 check-only acceptance passed in `accept-replay-panel-tk27s`: 25,778
  candidates, 50,098 immutable player rows, complete mean/label/artifact
  parity, and selected 187/194/200 counts `25/18/8` versus pool-oracle
  `38/22/12`. The subsequent promotion execution
  `accept-replay-panel-tbjlb` failed safely after the repeated acceptance
  pass because staging contains the new 210/220 masks (44 columns) while the
  older accepted table has 42; BigQuery rolled back the transaction and no
  candidate or snapshot row was promoted. `harvest_accept.py` now additively
  migrates its complete candidate schema and uses an explicit name-aligned
  target/source column list instead of positional `SELECT *`. Seven focused
  acceptance tests, compilation and whitespace checks pass locally. Build a
  fresh validation image, retry only K3 promotion from the unchanged staging
  panel, then resume K1 check and comparison; do not rerun generation.
- Repair build `a49f788a-9135-48a9-977b-3aebf7364712` passed 743 tests with
  2 skipped and produced digest
  `sha256:3f1aabf90065150e787c53fb5233741657c3b5219a2f231b444db899b8e14593`.
  Retry execution `accept-replay-panel-c6zpv` repeated the full K3 acceptance
  pass but failed before DML because BigQuery counts each of the repair's 44
  `ALTER TABLE IF NOT EXISTS` statements toward its table-update rate limit.
  Accepted candidates/snapshots still remain at zero. The superseding repair
  now reads the existing schema and performs one schema API update containing
  only missing fields, retaining the explicit name-aligned transactional
  insert. Validate a new image and retry promotion after the metadata-rate
  cooldown; do not reuse `c6zpv` or rerun generation.
- K1 check-only acceptance subsequently passed in
  `accept-replay-panel-9qw7z`: 25,766 candidates, the same 50,098 immutable
  player rows, and complete parity/legality/artifact checks. Its selected
  187/194/200/210/220/230/240 grid is `34/21/11/7/4/2/1`, mean weekly maximum
  `178.9327`, and pool-oracle grid `41/28/16/9/4/2/1`. The corresponding K3
  selected grid is `25/18/8/3/1/1/1`, mean `175.5402`, and oracle grid
  `38/22/12/5/1/1/1`. K1 therefore provisionally wins the revised high-to-low
  law at the first non-tied threshold (230), while tying at 240 and improving
  every lower reported threshold. Still require the frozen ensemble mechanism
  comparator after schema-safe K3 promotion before promoting K1 or launching
  CE.
- The final schema-safe acceptance repair at commit `9021a11` was validated by
  Cloud Build `8d4c5d94-52bc-4db2-9fef-8a6dbda65f85`: 743 tests passed with
  2 skipped, producing immutable digest
  `sha256:8dea3952912a8464882ed07d3286da50f59e96b2cc9425f93a2c1fd59820d76b`.
  K3 promotion execution `accept-replay-panel-25jbg` then completed cleanly.
  Direct warehouse verification found exactly 25,778 accepted candidate rows,
  50,098 eligible immutable player-feature rows and the complete 44-column
  accepted schema. K1 promotion execution `accept-replay-panel-rbbgs` also
  completed cleanly and direct verification found 25,766 accepted candidates
  plus 50,098 eligible feature rows. The workstation reboot interrupted only
  the local wrapper after the durable K1 execution; it did not affect the
  transaction.
- Frozen ensemble comparison `compare-adoption-panel-bspsn` completed with no
  mechanism failures. K1 changed only the ensemble member count, retained the
  identical player/input universe, and improved the exact-80 selected
  187/194/200/210/220/230/240 grid from K3's `25/18/8/3/1/1/1` to
  `34/21/11/7/4/2/1`; mean weekly best improved `175.5402→178.9327`.
  The revised tail-first operational gate passes, even though the superseded
  per-season stability gate does not. K1 is therefore adopted as the corrected
  control. Corrected CE12 source panel
  `20260810-lockfix-e80-k1-ce12-8677d21` was launched from the original
  generation digest. Preflight execution `replay-lockce-smoke-l7mzs` passed
  the full 2024 true-80 path in 8m10s. The six asynchronous executions are
  `replay-lockce-2019-bp8b2`, `replay-lockce-2021-6f6j6`,
  `replay-lockce-2022-j5lsm`, `replay-lockce-2023-2ntf7`,
  `replay-lockce-2024-7ff5s`, and `replay-lockce-2025-7gxrm`. Their immutable
  manifest is tracked under the CE12 panel directory. Monitor execution state
  and final row completeness only; do not inspect partial score outcomes.
- Before any corrected CE12 score was inspected, its comparator was updated
  to match the current operator objective. The original fixed 200-point gate
  remains in the report as an immutable scientific diagnostic, while the
  active fixed-budget disposition now uses the documented
  240→230→220→210 highest-difference-first decision plus mandatory mechanism
  validity. New guarded runner
  `scripts/cloud_compare_corrected_k1_ce_panel.sh` freezes the corrected K1
  and CE12 panel IDs. Nine focused CE/union tests pass; Python compilation,
  shell parsing and whitespace checks are clean. Comparator commit `db093ad`
  is pushed on `main`. Exact-commit Cloud Build
  `b3772bb8-e30a-4ca8-ac95-f9edc40911bd` passed 745 tests with 2 skipped and
  produced immutable acceptance/comparator digest
  `sha256:aab92b9120661e8764a4acd3d012298e5e5fcd746052452997a514f5afdaa6d1`.
  Use that digest only after CE12 reaches 107/107 complete slates; do not score
  or compare a partial panel.
- The operator purchased the standalone Fantasy Points Data Suite for $200.
  Licensed downloads are excluded by repository `.gitignore` under
  `fantasy-points/`. The untouched first export,
  `2022-receivingRouteShareReportExport.csv`, has SHA-256
  `68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637`,
  647 valid 2022 player rows, Weeks 1--18 and QB/RB/FB/WR/TE coverage. The
  2023--2025 Route Share exports are also complete and schema/range valid at
  621/625/637 rows; exact hashes are tracked in the intake report. One
  vendor-origin Brock Wright duplicate splits non-overlapping week blocks and
  must be coalesced by player-week; vendor team abbreviations and multi-team
  labels also require an explicit crosswalk. Continue untouched 2022--2025
  exports for the remaining Weekly Reports and Advanced Receiving before
  freezing the importer/schema. The four Fantasy Points Scored files are now
  also complete and valid, but are identity/scoring audits only rather than
  replacement labels. The four offense PROE exports are complete at exactly
  32 teams per season with valid weeks/game counts. Do not commit licensed
  source rows or use same-week postgame values in a replay.
  All four Snap Share exports also pass at 647/621/625/637 rows. The exact
  hashes, byte-identical extra 2024 file, and the replaced, filtered first 2022
  download caveat are recorded in the intake report. All four Target Share
  exports now pass at 647/621/625/637 rows with exact hashes in the intake
  report. All four Defense PROE exports also pass at 32 unique defenses and
  exact hashes recorded in the intake report. Advanced Receiving Player
  exports now pass at 545/517/528/526 rows with 63 common columns and exact
  hashes recorded in the intake report. They are full-season aggregates, not
  weekly histories, so they are eligible only as strict prior-season inputs.
  The known 2022 Brock Wright split requires count-aware coalescing. The
  separately named Defense Advanced Receiving files remain 32-team season
  aggregates and are not accepted as player history. Advanced Rushing Player
  exports are also complete at 354/334/322/329 player rows. Their two-row
  grouped schema cleanly identifies the repeated Zone and Man/Gap metric
  blocks; exact hashes are in the intake report. Like Advanced Receiving,
  they are strict prior-season inputs only: season N is forbidden for every
  target in season N and first becomes eligible in season N+1. Advanced
  Passing Player exports are also complete at 83/80/77/77 QBs with a clean
  grouped 59-column schema and exact hashes in the intake report; the same
  strict prior-season restriction applies. No further Fantasy Points download
  is currently requested.
- Before any Advanced value was joined to a target-season outcome, one narrow
  prior-season player-tail diagnostic was frozen in
  `reports/2026-08-10-fantasy-points-prior-season-advanced-tail.md`. It joins
  only season N-1 to target season N, uses fixed process-trait blocks for
  QB/RB/WR-TE, and evaluates 2024/2025 30-point Brier with position/fold
  safeguards. Outcome-blind coverage is 60.27%--66.87% across the required
  position/fold cells. Implement the exact hash-locked parser and diagnostic;
  no target-season aggregate, field subset or model retry is permitted.
- Corrected CE12 completed all 107 slates with season counts
  `17/18/18/18/18/18`, 25,766 candidate rows and exactly 8,560 selected rows.
  All six authoritative executions completed cleanly. Check-only acceptance
  `accept-replay-panel-55vrb` passed candidate/feature parity, legality,
  artifacts and exact-80 structure. Its selected 187/194/200 grid is
  `37/25/13` and the panel is mechanically eligible for comparison. Frozen
  K1-versus-CE12 comparison execution
  `compare-corrected-k1-ce-panel-s98dc` completed from immutable image digest
  `sha256:d4566a1031efd391ece5758dd294cd01069e5dae3d4f1bee5c04f0af6ec13b33`
  with zero mechanical failures. CE12 moved selected
  187/194/200/210/220/230/240 from K1's `34/21/11/7/4/2/1` to
  `37/25/13/6/3/1/1` and mean weekly best `178.9327→179.4993`; its pool
  oracle moved `41/28/16/9/4/2/1→44/30/17/9/3/1/1`. It therefore loses at
  the first non-tied active threshold (230) and also at 220/210. Frozen
  tail-first disposition is `reject`; do not promote CE12. Corrected K1
  remains the accepted incumbent. CE's rejection does not measure the
  distinct role-belief generator; freeze any direct K1+role test before
  generating or reading a corrected role outcome.
- Direct corrected K1+role confirmation is now frozen before any treatment
  generation in
  `reports/2026-08-10-corrected-k1-direct-role-union.md`. It excludes CE,
  retains K1's 40 boom candidates, and adds exactly 12 candidates using the
  pre-existing six role fields and seed 7331. Final output remains exactly 80
  and the only active decision is 240→230→220→210 at the first difference.
  Guarded generation runner `scripts/prop_lock_direct_role_union.sh`,
  comparator `scripts/compare_corrected_k1_direct_role.py`, and Cloud Run
  harvester `scripts/cloud_compare_corrected_k1_direct_role.sh` are
  implemented. Sixteen focused role/CE/union tests pass; both shell scripts
  parse and the comparator compiles. Build an exact-tree comparator image,
  then launch the single treatment panel from the original corrected
  generation digest
  `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`.
  Initial validation build `fbb4221a-7825-4999-903e-f02a0f9ab2cb` from
  preregistration/implementation commit `e0e1a04` was cancelled during its
  test step, before any image or panel launch: a prelaunch packaging audit
  found Dockerfile's explicit script allow-list omitted the new comparator.
  Commit `875164e` added that copy line. Superseding exact-tree Cloud Build
  `b45029c0-a715-403e-8dba-c3323e27da91` passed 756 tests with 2 skipped and
  produced immutable comparison digest
  `sha256:5319704c23ac40f30771a43b2fb6b4d012a7b2d8f610b980ecfd509ba55deb6b`.
  Launch the single direct-role treatment from the original corrected
  generation digest, then use this later digest for check/comparison.
- At approximately 15:18 CDT, an operational recent-log check on the final
  running 2022 CE execution unintentionally surfaced the already-written Week
  16 and Week 17 best-score log lines before the panel was complete. No gate,
  comparator, code, candidate construction, or planned next action was changed
  after that accidental exposure; all CE decision rules and the immutable
  comparator image had already been frozen. Do not use those two partial
  values for any decision and do not query further execution logs; monitor
  only status and row completeness until 107/107.
- Before joining any paid Route Share value to an outcome, the exact first
  paid-data diagnostic was frozen in
  `reports/2026-08-10-fantasy-points-route-share-experiment.md`. It normalizes
  only the four validated Route Share files, enforces source hashes and
  conflict-safe identity resolution, and adds exactly last/l4/jump plus a
  cross-season indicator under a strict earlier-week join. Corrected K1
  player folds train 2024 on 2022--2023 and 2025 on 2022--2024, using fixed
  Ridge/logistic controls. The active gate prioritizes aggregate and WR/TE
  30-point Brier with per-fold/coverage safeguards; 20-point Brier and MAE are
  diagnostics. Outcome-blind availability is 82.07%/82.95% in 2024/2025.
  Implement and validate this exact diagnostic without inspecting intermediate
  outcomes; no field/window/model retry is permitted.
- The Route Share-only importer and diagnostic are now implemented behind CLI
  commands `import-fantasy-points-route` and
  `fantasy-points-route-diagnostic`, with guarded runner
  `scripts/cloud_fantasy_points_route_diagnostic.sh`. Four focused tests pass;
  compilation, shell parsing and whitespace checks are clean. Audit-only import
  normalized 27,305 weekly rows; the first authorized `WRITE_EMPTY` created
  private table `nfl_raw.fantasy_points_route_share` with 26,881 resolved rows,
  1,029 resolved GSIS players, four exact source hashes and values in `[0,1]`.
  A repeated write returned `already-identical` without mutation. No outcome
  diagnostic had run at implementation time. Implementation commit `501760b`
  is pushed on `main`. Exact-tree Cloud Build
  `24d0a97b-b51e-43c0-a733-332f24064d25` passed 749 tests with 2 skipped and
  produced immutable digest
  `sha256:a08ae363d937a428849f62b3bd07ea7527d8dd4ab487496d0408fa3da9e49d42`.
  The single frozen diagnostic is now running as durable Cloud Run execution
  `fantasy-points-route-diagnostic-rthzs`. It completed successfully in 2m17s
  and passed every gate. Strict-prior coverage was 82.35%/83.02% in
  2024/2025; aggregate 30-point Brier improved
  `0.00968358→0.00965675`, and WR/TE 30-point Brier improved
  `0.00763166→0.00760188`, with nonworsening fold safeguards. The treatment
  also improved 20-point Brier; diagnostic-only MAE worsened slightly
  `2.88299→2.89248`. This licenses one separately preregistered Route Share
  candidate-union test but does not itself change production. The immutable
  final report is under
  `reports/fantasy-points-route-runs/20260810-fp-route-share-v1/`; do not retry
  or tune this player diagnostic.
- Before any Route Share lineup was generated or scored, its one licensed
  candidate test was frozen in
  `reports/2026-08-10-fantasy-points-route-tail-union.md`. After the corrected
  K1→CE12→role chain mechanically selects its incumbent, reproduce that source
  and add exactly twelve novel candidates per 2024--2025 slate using
  `proj_tourney + 30 * (treatment_p30 - control_p30)` from the same held-out
  Route models. Other seasons reproduce source exactly; production worlds and
  the 194 selector remain unchanged. Exact source containment/invariance and
  twelve novel candidates per treated slate are mandatory before applying the
  240→230→220→210 law. No dose/scale/model retry is allowed.
- The preregistered Route candidate construction is now implemented but has
  not run. It reconstructs the exact held-out control/treatment p30 models
  without requiring target outcomes, persists the strict-prior audit fields,
  and adds the paid signal only to the 2024/2025 candidate objective. The
  engine applies the incumbent pool cap first, then adds exactly twelve
  source-banned `route_tail` rosters using the frozen coefficient; unsupported
  doses, missing/non-finite signals, failed solves or duplicate rosters abort.
  Other seasons add zero candidates. Six focused Route tests plus the related
  generation/persistence/replay suites pass (61 tests total); compilation and
  whitespace checks are clean. Implementation commit `2c0f93b` is pushed.
  A post-commit audit found that the first implementation carried the delta
  into candidate construction but did not persist its source season/week and
  control/treatment probabilities. Those audit fields are now carried into
  the immutable feature snapshot, and the relevant 31 tests pass. Cloud Build
  `d01b4116-2abf-45af-b56c-1a0b1f7342bf` is therefore superseded even if it
  succeeds; build the audit-complete commit before any execution. Do not
  launch the arm until the corrected generator chain chooses its incumbent.
- The Route union protocol's artifact condition was clarified before any arm
  generation: whole NPZ checksums necessarily differ when twelve candidate
  rows are appended. Both artifacts must be present/hash-addressed, while all
  persisted shared-candidate actual/mean/probability/support fields must match.
- The guarded Route union evaluator is implemented behind CLI
  `route-tail-union` and `scripts/cloud_route_tail_union.sh`. It fails before
  scoring unless source containment/shared supports, exact 12-per-treated-
  slate Route provenance, zero additions elsewhere, strict-prior signal
  provenance, artifacts, exact-80 completeness, and persisted-selection
  reproduction all pass. Two focused evaluator tests plus 43 related tests
  pass; compilation, shell parsing and whitespace checks are clean. No Route
  lineup exists. Audit-complete generator build
  `6c96b5bb-5958-4b17-bf1a-7ec2bdcfc9d1` from commit `aa087b8` passed 751
  tests with 2 skipped and produced immutable generation digest
  `sha256:b907bc6242d6b872cf10e4ff9ea59e56d89a1b99861780007eb767636a97041c`.
  Evaluator build `cff83915-db3e-4576-b547-090f8c1cac0a` from commit
  `c94c0e6` also passed and produced immutable comparison digest
  `sha256:d4566a1031efd391ece5758dd294cd01069e5dae3d4f1bee5c04f0af6ec13b33`.
  Do not launch Route generation until the corrected CE/role chain chooses
  its incumbent.
- One corrected-history selector confirmation is now frozen before either
  corrected control outcome is read:
  `reports/2026-08-10-corrected-extreme-selector-confirmation.md`. After the
  K3→K1→CE12→role chain chooses its final mechanically accepted generator,
  apply the already-deployed prospective 220→210→200 lexicographic selector
  exactly once to that source pool and compare its same-80 weekly maxima at
  240→230→220→210. It excludes every other selector variant and cannot
  influence which generator pool is chosen. Guarded implementation is
  `research/extreme_selector_confirmation.py`, CLI command
  `corrected-extreme-selector`, and
  `scripts/cloud_corrected_extreme_selector.sh`; thirteen focused selector,
  union and portfolio tests pass, along with compilation, shell parsing and
  whitespace validation. Implementation/protocol commit `177c113` is pushed;
  exact-tree build `604b1496-5bc2-406f-9565-dd41c6870c96` passed 740 tests
  with 2 skipped and produced immutable digest
  `sha256:370695d6f576b6d71d770b4a0f9fa6745376167600188a481db51e9eedc34fce`.
  Use that digest for the eventual selector confirmation. No corrected
  selector score has been queried.
- The operator supplied an outside strategy review. Its reconciled,
  repository-verified disposition is tracked in
  `reports/2026-08-10-strategy-review-reconciliation.md`. The useful new
  direction is explicit opponent-field/payout simulation, which is distinct
  from the rejected ownership fade and supported by the cited primary DFS
  optimization research. It is prospective/data-blocked: the warehouse has
  103,556 aggregate ownership rows from 1,258 contests/72 slates and 68 winner
  rosters, but no historical opponent lineups, payout curves, field sizes,
  min-cash lines or duplication labels. Seek a metadata-only export first and
  use 2026 full standings for field-model validation. The review's proposed
  ordinary-tail widening reverses the measured calibration direction
  (`7.37%/0.72%` exceedance is conservative, not too thin); its claimed-new
  within-team Dirichlet mechanism already failed at K=20 and K=8; and its
  world-argmax proposal is the existing boom generator. Do not launch those
  three as new arms. Constant-budget candidate reallocation remains a lower-
  priority possible arm after the corrected queue, not a current sweep.

- The operator explicitly revised the operational objective after the valid
  role union improved the same 80-entry portfolio at every 210+ threshold.
  Scientific dispositions remain immutable, but season-sign requirements and
  the role gate's requirement to rescue previously sub-200 pools are no
  longer operational vetoes. The hard gates are point-in-time/mechanical
  validity, exact final entry count, reproducibility/live parity, and no
  hidden outcome-tuned parameter. The primary score comparison now proceeds
  from 240→230→220→210→200; lower thresholds, means and season signs are
  diagnostics. Full law and audit:
  `reports/2026-08-10-tail-first-adoption-review.md`.
- A fresh warehouse inventory covered every corrected-universe, complete,
  mechanically valid true-80 panel. The role union is the strongest: selected
  187/194/200/210/220/230/240 is `39/27/18/12/6/3/2`, mean `182.5725`, and
  pool oracle `48/32/22/13/6/3/2`. Against CE12/boom28 it improves 15 paired
  weekly maxima, declines on 6, ties 86, and has positive mean delta in five
  of six seasons. No older valid arm beats it under the revised high-tail
  law. Incomplete-universe and otherwise invalid panels remain ineligible.
- Repository policy `classic-k1-ce12-role12-boom28-v2` now names valid panel
  `20260810-e80-k1-ce12-roleunion-c616390`: K1 baseline registry `tail_k1`,
  alternate K1 registry `tail_k1_role`, exact six frozen role inputs, CE seed
  1701, role seed 7331, 12 CE / 12 role / 28 boom generation, line 194, $49k
  floor, 45/55 blend, and 80 final entries. The role candidates add only
  pre-selection compute. Prior `classic-k1-ce12-boom28-v1` is implemented as
  a labeled fallback if the role registry/load/quota fails.
- Live inference now lets each loaded booster materialize its own registered
  feature columns rather than depending on process-global `EXTRA_FEATURES`.
  This is required for a baseline and alternate-role registry to serve safely
  in the same web process. JSON exposes the baseline and role model versions,
  effective policy, and fallback flag; CSV headers expose the effective
  policy. A new isolated weekly role training job, early/late role-union
  shadow jobs, and two role-union freezer books are defined. Prospective
  freezer policy is `tail-first-v6-20260810` with eleven books.
- Branch `main`; implementation commits `031c0c1` and `75c8791` are pushed.
  Exact-tree Cloud Build `ab7073fa-a53b-4253-a481-9e47c150c7cd` passed `724`
  tests with `2` skipped in 353.27 seconds. The deployable immutable image is
  `sha256:41de2eaee84bb9eb72b07b6a96b35b7223951e4fa0c979780dd703b1c11d7349`.
  An earlier green build `3ca9d329-e5ce-44d3-be5b-ecbf381f7aec` is not the
  final tree and must not be deployed. Focused offline validation includes a
  real 80-lineup role-union build and the labeled CE-only fallback; Python
  compilation, shell parsing, deployment-contract validation, and
  `git diff --check` are green.
- Isolated role training execution `train-weekly-k1-role-zhd7w` completed
  successfully in 3m25.78s and registered all 11 K=1 component models as
  `pooled/components__tail_k1_role/2026-W33`. A read-back check proved that
  every component contains the exact six frozen role fields, while baseline
  `pooled/components__tail_k1/2026-W32` excludes them. Both registries report
  ensemble size one.
- Cloud Run service `nfl-dfs-app` now serves v2 from ready revision
  `nfl-dfs-app-00065-v8d`, with 100% traffic on the exact validated digest.
  Startup logs are clean. Existing IAP correctly redirects an unauthenticated
  `/health` request to Google sign-in, so the real authenticated
  UI -> 80 lineups -> DKEntries check remains a first-live-slate task rather
  than bypassing IAP. The complete offline live-builder path already passed.
- Jobs `train-weekly`, `train-weekly-k1`, `train-weekly-k1-role`,
  `project-slate`, `shadow-k1`, `shadow-k1-nofloor`, `shadow-k3`,
  `shadow-k1-roleunion`, `freeze-tail-early`, and `freeze-tail-late` are all
  pinned to the same exact digest. `scripts/verify_deployment.py --json`
  reports zero contract failures. The three new schedules
  `s-train-k1-role`, `s-shadow-k1-roleunion-early`, and
  `s-shadow-k1-roleunion-late` target the intended jobs and use the existing
  compute service account. All 17 seasonal schedulers are `PAUSED`; year-round
  ingestion, backups, scoring, trends, and freshness jobs were not changed.

- The predecessor/fallback `classic-k1-ce12-boom28-v1` comes from accepted
  panel `20260809-e80-k1-ce12-c616390`. Its true-80 selected weekly-max counts at
  187/194/200/210/220/230/240 remain `40/26/18/11/5/2/1`; mean/median are
  `181.1243/178.64`, and pool-oracle counts are `47/32/22/13/5/2/1`.
- A fresh accepted-panel audit found that the pool omits 36 of 612 player
  slots across 28 of 68 matched Millionaire winners, concentrated at WR (12),
  TE (11), and RB (7). Those missing slots averaged 21.11 actual points versus
  7.82 projected. The pool has an unselected weekly maximum on 25/107 slates,
  but only four nonredundant unselected oracles clear 200, so another flexible
  selector search is not justified on the same 107 outcomes.
- The 36 omitted winner slots average $4,128 salary and 5.88% realized
  ownership, with 61.1% below 5%, versus $5,644 and 13.88% for covered winner
  slots. Eleven misses are fast-role players and six are vacancy/promotions.
  Treat this as support for better cheap-player role inputs; the already
  rejected generic ownership-scoring arm remains closed.
- The existing point-in-time breakout analysis was run on the final accepted
  snapshots and persisted 27,266 same-slate/same-position matched pairs to
  `nfl_predictions.archetype_matched_pairs`. Fast-role-rise players produced
  +2.1908 mean DK points and +0.03791 probability of 20+ versus controls over
  5,540 pairs; both effects are positive in all six seasons. Vacancy/promotion
  produced +1.3849 and +0.01920 over 8,490 pairs, again positive in every
  season. Cheap-DST and cold-start/rookie states were negative and are not
  reopened.
- A separate walk-forward TabPFN calibration audit found fast-role q90/q99
  exceedance of 9.76%/1.06% and vacancy/promotion exceedance of 9.03%/1.20%,
  close to their nominal 10%/1% rates. Ordinary players were overestimated at
  7.37%/0.72%. This rejects a generic role-tail widening as the immediate
  path and supports one bounded test of the already-frozen role-belief
  candidate generator.
- Protocol `reports/2026-08-10-k1-ce-role-belief-experiment.md` freezes the
  exact pre-existing six role inputs, seed 7331, and 12-candidate dose before
  treatment outcomes. The union panel
  `20260810-e80-k1-ce12-roleunion-c616390` adds 12 role candidates to the
  accepted 12 CE / 28 boom allocation and must create at least two new
  role-caused 200-point oracle weeks. Only then may fixed panel
  `20260810-e80-k1-ce12-role12-c616390` replace 12 boom solves, yielding equal
  12 CE / 12 role / 16 boom compute and exact per-slate source pool sizes.
- The fixed scoring gate follows the operator's tail-first utility: at least
  +2 selected 200-point weeks; selected 210/220/230/240 and pool-oracle
  200/210/220/230/240 all nonworse; a novel role frontier; and full mechanical
  validity. Mean, 187/194 counts, and season signs are diagnostics, not vetoes.
  No parameter retry is allowed after a valid rejection.
- All six union seasons completed cleanly and immutable comparator execution
  `compare-k1-role-panel-ps9mx` returned a mechanically valid `reject` with
  zero failures. The union retained all 25,787 source rosters, added 1,269
  novel role rosters, held every common score/support value invariant, and
  reached 11 role-specific realized frontiers. However, it created zero new
  200-point weeks on slates whose source oracle was below 200 (required two),
  so the equal-budget fixed panel was not launched and remains closed. The
  originally rejected added-budget union moved selected
  210/220/230/240 `11/5/2/1→12/6/3/2`, oracle
  `13/5/2/1→13/6/3/2`, and mean `181.12→182.57`. That machine disposition is
  preserved, but the operator's documented tail-first override adopts the
  mechanically valid union because these are direct gains in the stated
  tournament objective. Tracked report and execution are under
  `reports/panel-runs/20260810-e80-k1-ce12-roleunion-c616390/`.
- New guarded runner/comparator scripts and focused tests are implemented.
  The comparator proves feature/common-world invariance, exact seed/lever
  identity, union containment, fixed pool equality, source CE preservation,
  and exact 12-role realization on all slates. `31` focused role/CE/budget
  tests pass; both shell scripts parse, the comparator compiles, and
  `git diff --check` is clean. The Docker image now explicitly packages the
  comparator.
- Preregistration/runner commit `c02cded` is pushed on `main`. Full validation
  build `35ec292e-94ea-48b2-8597-23292b77dbd3` passed `716` tests with `2`
  skipped in 387.33 seconds and produced immutable comparator digest
  `sha256:a410648bc20b10ec65e7ca49a2bc67108771067136259d73fad65f8cdb72087f`.
- Union preflight `replay-e80k1ru-smoke-l4fjb` passed on the frozen generation
  digest. The six exact asynchronous union executions are
  `replay-e80k1ru-2019-kn4jf`, `replay-e80k1ru-2021-6sj8b`,
  `replay-e80k1ru-2022-6n9gr`, `replay-e80k1ru-2023-t5r9v`,
  `replay-e80k1ru-2024-zg8lx`, and `replay-e80k1ru-2025-wtsxz`. Their immutable
  manifest is tracked under
  `reports/panel-runs/20260810-e80-k1-ce12-roleunion-c616390/`. Do not inspect
  partial scores or infer status from a job's latest execution.
- No Odds API historical quota was spent. Official historical player props
  are potentially useful from May 2023 onward, but route/target/alignment data
  is a more direct paid-data lead for the observed WR/TE misses. Any quota
  backfill remains a separately approved, credit-capped experiment.
- The ranked follow-on queue is now tracked in
  `reports/2026-08-10-scoring-opportunity-roadmap.md`. The preferred paid-data
  pilot is Fantasy Points Data only if checkout is below $200 and full
  2022-2025 CSV exports are confirmed; requested fields and the walk-forward
  player-tail -> union-oracle -> fixed-budget gates are frozen there. A later
  Odds API pilot is capped to three volume markets and 20,000 credits. The
  Historical threshold diagnostics found 200 coverage at 19/12 weeks over
  200/210 versus the 194 control's 18/11, while 187 coverage reached 17/13;
  all three tied at 5/2/1 for 220/230/240. Both threshold alternatives and
  the zero-tuning deterministic one-swap refinement are now implemented as
  prospective early/late books under `tail-first-v4-20260810`; none can affect
  the adopted/UI portfolio. Deep generative dependence work is deferred until
  more field data exist.
- Threshold-shadow implementation commit `d4a5e15` is pushed on `main`; 15
  focused selector/freezer tests pass, including a proof that 187/194/200 use
  their distinct persisted support masks. Full Cloud Build
  `a000bbb2-5327-4de5-b216-0b35b4daf896` passed 717 tests with 2 skipped and
  produced immutable digest
  `sha256:9d02ecc3cfa1951d74056c64593314ce47facecbadeb500c998f6aa98ed7e297`.
  Only `freeze-tail-early` and `freeze-tail-late` were updated to that digest;
  both retain their exact early/late commands, GCP project environment, 1 CPU,
  1Gi, one retry and 3600-second timeout. Schedulers
  `s-freeze-tail-early` / `s-freeze-tail-late` remain PAUSED at 11:05 / 11:50
  Sunday CT. Neither job was executed off-season. This supersedes the v3
  freezer digest without changing the adopted/UI lineup path.
- One-swap implementation commit `b90047b` is pushed on `main`; 14 focused
  shadow/refinement tests pass. Full validation build
  `7ab5a1e2-1994-4ec5-8ac8-a188669b54c5` passed 716 tests with 2 skipped in
  453.35 seconds and produced immutable digest
  `sha256:603d20c09a878a1679b6559d4be56a6a59d0f7b367a1fb99019883203337e18d`.
  Only `freeze-tail-early` and `freeze-tail-late` were redeployed to that
  exact digest; both preserve `nfl-dfs freeze-tail-portfolios --slot
  early|late`, 1Gi/1 CPU, one retry, and 3600 seconds. Schedulers
  `s-freeze-tail-early` / `s-freeze-tail-late` remain PAUSED on their original
  11:05/11:50 Sunday CT schedules. No live app or adopted lineup path changed.
- The next-data review found a usable no-cost diagnostic before buying route
  data: installed `nflreadpy` currently serves 46,168 / 45,919 / 45,184
  participation plays for 2023 / 2024 / 2025, including every offensive
  player ID on a play. The frozen protocol in
  `reports/2026-08-10-pass-participation-proxy.md` derives strictly lagged
  player-on-field shares for all dropbacks and red-zone dropbacks, then tests
  whether those four fields improve 2024/2025 walk-forward residual MAE and
  20-point Brier loss beyond the accepted pre-lock projection, salary,
  position, target/snap share, and vacancy features. The feed is
  season-delayed and presence is not a route, so it can only support or reject
  a paid route-data trial; it cannot become a production input or historical
  lineup arm. Implementation, CLI, and three focused tests are complete; nine
  combined participation/selector tests pass. Implementation/protocol commit
  `0261801` is pushed on `main`; full validation build
  `6200e344-837e-4935-9adf-8eb062383017` passed 720 tests with 2 skipped and
  produced immutable digest
  `sha256:2665a7f9a683e2d737d620519a15a431e4a5c7baa6feb43aade7f2f4084fde62`.
  Guarded runner `scripts/cloud_pass_participation_proxy.sh` requires an
  immutable digest, deploys the unscheduled diagnostic with 2 CPU / 4Gi / no
  retries, records the execution and manifest, and harvests exactly one JSON
  disposition under `reports/pass-participation-runs/`.
  Execution `pass-participation-proxy-vmxdq` completed cleanly. Across 9,887
  held-out 2024-2025 player-weeks, the treatment improved residual MAE
  `3.71089→3.67957`, 20-point Brier `0.045375→0.045226`, and WR/TE Brier
  `0.039258→0.039082`; both primary metrics improved in each season. All
  frozen conditions pass and disposition is `supports-paid-route-trial`.
  This justifies verifying/buying the under-$200 full-history true-route
  export, not adding the season-delayed proxy or claiming a lineup result.
  Fantasy Points remains first because it explicitly advertises weekly route
  share plus CSV/Excel. Lower-cost fallback questions are logged for
  Reception Perception ($99.99/year historical tables, but no public CSV or
  complete-player promise) and SIS DataHub ($99.99/month with CSV, but no
  public confirmation of route fields/history); do not buy either without
  confirming the missing contract.
- Research on the subsequent selector question is recorded in
  `reports/2026-08-10-scoring-opportunity-roadmap.md`. After current shadows,
  prospective snapshots may retain 210/220 support and freeze a deterministic
  220→210→200 lexicographic book. A separate mechanism test may reduce seed
  noise when estimating 210/220 support only after exposing an exact change
  of measure on the possession simulator's own latent variables. The existing
  CE weights are not valid for this purpose because CE deforms deterministic
  means rather than sampling the production law. Any valid proposal must pass
  analytic likelihood-ratio checks, confidence-interval parity, ESS,
  max-weight, repeated-seed variance, marginal-invariance and roster-stability
  gates before any portfolio. This is not a retry of the already-adopted CE
  candidate generator and may not inspect the 107 known scores to set rules.
- Prospective extreme-selector protocol
  `reports/2026-08-10-prospective-extreme-selector.md` is now frozen and
  implemented without consulting historical outcomes. Candidate persistence
  adds complete 210/220 masks; policy `tail-first-v5-20260810` retains the
  prior eight books and adds one K=1 book that greedily covers new worlds
  lexicographically at 220→210→200. The implementation validates nested masks,
  deterministic priority/tiebreaks, 80 unique rosters and old 194 selection
  reproduction. Thirty-five combined selector/persistence/participation tests
  pass locally. This mechanism was subsequently retained in the eleven-book
  `tail-first-v6-20260810` policy alongside two role-union books.
  Implementation commit `d1c9318` is pushed on `main`; full validation build
  `9e3e6c14-f70a-4f8d-9863-7120c5fae74f` passed 721 tests with 2 skipped and
  produced immutable digest
  `sha256:75daf1607c2f08197d1357c10702434161b1093cff2a21e8cdc7ca7d5bcdf95c`.
  That digest is historical. The four paused shadow generators and two paused
  freezers now use the final v2 digest recorded above; the original three
  generators record `CODE_SHA=75c8791` and preserve their exact command,
  registry/K, possession mode, generator quotas, salary floor, 45/55 blend,
  30,000 worlds, 4 CPU / 8Gi, retry and timeout settings. Freezers preserve
  their early/late commands and 1 CPU / 1Gi settings. All ten shadow/freezer
  schedulers remain PAUSED. No off-season shadow or freezer was executed.
- Exact next action: monitor the six coverage executions without reading
  partial scores; after all succeed, run check-only exact-80 acceptance and
  the one frozen comparator against direct role. The no-floor union is closed.
  For paid data, run the preregistered 168-export same-season coverage
  collection sequentially, validate every manifest/schema/game count, then
  implement the frozen importer and diagnostic without reading outcomes
  until its PIT/support tests pass. Keep all
  17 seasonal schedules paused until the Aug 24 resume date. On the first real
  Sunday-main slate, run the authenticated UI -> 80 lineups -> DKEntries smoke
  and confirm v2 provenance; deliberately exercise and label the CE-only
  fallback in a controlled smoke. New historical experiments must use the
  revised tail-first law; do not tune the role seed, six fields, or
  12-candidate dose on these 107 outcomes.

## Previous state — 2026-08-09 21:05 CDT

### Pre-season arm/UI promotion gate complete

- Branch `main`; implementation commit `f647d00` promotes the adopted policy
  through every money-lineup path. The frozen production decision is
  `classic-k1-ce12-boom28-v1`, sourced from historical panel
  `20260809-e80-k1-ce12-c616390`: K=1 `tail_k1`, possession simulation,
  45/55 model/prop-market blend, $49,000 salary floor, fixed greedy coverage
  at 194, 80 default entries, candidate multiple 2, seed 1701, and fixed
  12 CE / 28 boom replacement allocation. The selected weekly-max counts over
  107 slates at 187/194/200/210/220/230/240 are
  `40/26/18/11/5/2/1`; mean/median weekly maxima are `181.1243/178.64`.
  Its candidate-pool oracle counts are `47/32/22/13/5/2/1`.
- `src/nfl_dfs/inference/production_policy.py` is now the single frozen
  mapping consumed by projection and live lineup code. It passes a
  request-local environment mapping rather than mutating process environment,
  and overrides every research lever capable of changing a roster. The
  projection job explicitly loads and verifies a one-member model from the
  isolated `tail_k1` registry. The simulator, replay shaper, optimizer,
  generator, selector, and provenance paths accept that explicit mapping.
- `/lineups`, `/lineups.csv`, and `/lineups/entries.csv` all use the same
  policy. The UI defaults to 80 and displays the policy plus exact loaded model
  version; JSON returns the full policy identity and both CSV routes return
  `X-Lineup-Policy` / `X-Model-Version`. The selector remains fixed at 194
  when a field size is supplied; field-size winning-line estimates are
  comparator metadata only. `sim=false` remains an explicitly labeled,
  non-adopted plain-MILP emergency escape hatch. DKEntries files still govern
  their actual reserved entry count.
- Validation is complete. The full local suite reached 100% green. Cloud Build
  `9b67b443-1924-4200-b749-ddc0bd147b5d` passed `712` tests with `2` skipped
  in 351.73 seconds, including a real offline K=1 end-to-end build of 80 legal,
  distinct, $49k+ lineups and an 81-line DraftKings CSV. Validated immutable
  image digest:
  `sha256:78ba7d76efcbe81913cef33a879dea1197b1440804c67d73d8bd6ae29219bc47`.
- Cloud Run service `nfl-dfs-app` is deployed from that exact digest as ready
  revision `nfl-dfs-app-00064-qgn` with 100% traffic. Its existing IAP policy
  correctly rejects unauthenticated and ordinary identity-token curls, so the
  external smoke was limited to Cloud Run readiness rather than bypassing IAP.
  The `project-slate` job is also ready on the exact digest and explicitly
  declares `MODEL_ENSEMBLE=1`, `MODEL_REGISTRY_VARIANT=tail_k1`,
  `BLEND_MODEL_WEIGHT=.45`, and possession simulation; its project setting and
  Odds API secret reference were preserved. It was not executed off-season
  because no matching live slate exists.
- All fourteen seasonal schedulers were rechecked after deployment and are
  `PAUSED`: `s-nflverse`, `s-features`, `s-train`, `s-train-k1`,
  `s-project-tu`, `s-project-su`, all six K=1/no-floor/K=3 early/late shadows,
  and both freeze-tail jobs. Year-round backups, odds/DK/CFB/weather ingestion,
  and freshness monitoring were left alone. This also prevents another
  expected off-season `shadow-k1-nofloor` no-slate failure alert.
- The alternate use of existing 2022-2025 ownership was completed, not lost:
  the contest-aware ownership predictor passed its calibration gate but its
  single frozen true-80 scoring arm failed to improve the adopted K=1 tail
  book and is rejected. The CE reranker confirmation also failed its adoption
  gate. Neither may enter live behavior; both remain durable negative evidence
  rather than tasks to rerun or tune on the same 107 outcomes.
- Exact next action: keep the fourteen jobs paused through Aug 23. On Mon Aug
  24, run the resume command in the README season-start table, verify the
  Tuesday K=1 training completes before projections, and use the first real
  Sunday-main slate for the authenticated UI -> 80 lineups -> DKEntries CSV
  smoke. Grade the already frozen K=1, no-floor, K=3, top-p, and mixed books
  prospectively without changing their membership. New data signals remain
  shadow-only until they have pre-lock evidence; do not retune this adopted
  policy against the known historical outcomes.

## Previous state — 2026-08-09 20:12 CDT

### Autonomous scoring research resumed after context recovery

- Live Cloud Run history and every tracked manifest were reconciled after the
  operator reported that research had stopped unexpectedly. There is no
  unharvested scoring execution: all six true-80 K=1 no-floor seasons,
  acceptance `accept-replay-panel-8m9hv`, and comparator
  `compare-adoption-panel-7c4cs` completed. The concurrent work was the Odds
  API shadow/telemetry implementation, which also completed. Paused Week-1
  prospective schedulers do not pause historical mechanism research.
- Two bounded next paths are preregistered before new outcomes. The first is
  the one allowed corrected-universe K=1 CE confirmation: union panel
  `20260809-e80-k1-ceunion-c616390` (`12 CE / 40 boom`) must pass its
  candidate-oracle gate before fixed replacement panel
  `20260809-e80-k1-ce12-c616390` (`12 CE / 28 boom`) can launch. Both retain
  immutable generation digest `sha256:98a31edd...`, K=1, true 80, $49k,
  45/55, line 194, and seed 1701. Protocol:
  `reports/2026-08-09-k1-ce-true80-experiment.md`.
- The recovered parallel ownership direction is also frozen. Do not repeat
  the failed generic `OWN_MODEL=fade` test: its target averaged incompatible
  cash/GPP, Classic/Showdown, and slate scopes. Build a walk-forward
  large-field Sunday-main Milly ownership target from the existing 2022-2025
  data and exact accepted K=1 snapshots. It earns one fixed K=1 scoring arm
  only after the preregistered held-out ownership-calibration gate passes.
  Protocol: `reports/2026-08-09-milly-ownership-alternative.md`.
- The reviewed CE runner and comparator are now implemented. The union runner
  pins the old generation image/code, K=1, seed 1701, 80 entries, and
  `12 CE / 40 boom`; the fixed runner refuses to launch unless the tracked
  union JSON passes, then derives all 107 caps from the promoted source before
  launching `12 CE / 28 boom`. The comparator proves exact feature invariance,
  source-roster union containment/shared-world equality, active CE candidates,
  fixed pool equality, and the complete 187-240 tail grid. Focused validation:
  32 tests passed across the new comparator, canonical tail gate, and
  generation-budget controls; both shell scripts parse and `git diff --check`
  passes.
- CE infrastructure commit `2650c77` is pushed on `main`. Union panel
  `20260809-e80-k1-ceunion-c616390` is now launched on immutable generation
  digest `sha256:98a31edd...`; its durable 2022 one-week preflight execution is
  `replay-e80k1ceu-smoke-z4rlq` and passed. The six durable season executions
  are `replay-e80k1ceu-2019-7zp2w`, `replay-e80k1ceu-2021-hhbfh`,
  `replay-e80k1ceu-2022-wnsz6`, `replay-e80k1ceu-2023-vrmsz`,
  `replay-e80k1ceu-2024-9r566`, and `replay-e80k1ceu-2025-zjw6k`; all were
  launched asynchronously and must be checked by these exact IDs rather than
  by each job's latest execution.
- The contest-aware ownership diagnostic is implemented while CE computes.
  It deterministically selects the largest-field mass-valid Classic Milly,
  excludes parenthetical alternate/single-game slates and high-roller copies,
  maps DK defense nicknames to snapshot team codes, never imputes unmatched
  ownership as zero, and trains 2023/2024/2025 strictly on earlier seasons.
  It compares the low-capacity contest model to both the existing all-contest
  model and a prior-season-mass-calibrated version of the current naive proxy,
  emitting preregistered correlations/MAE/top-quartile/position calibration,
  join coverage, and a binary gate. Ten focused ownership/current-model/CE
  tests pass; both evaluator scripts compile/parse and whitespace checks pass.
- Exact next action: finish/record the CE union preflight and six execution
  IDs; commit/push the ownership evaluator; run a full Cloud Build; then use
  its immutable digest for the CE comparator and ownership diagnostic. The
  first queued build `0405d235-34af-49b0-bd72-d189f913f0e3` was cancelled
  before use because review caught that Docker's explicit script allow-list
  omitted the two new cloud entry points; no image from that build is valid.
  Dockerfile now includes both scripts. Never query or launch fixed-arm lineup
  outcomes unless the tracked union mechanism/frontier gate passes.
- Replacement full Cloud Build
  `28ea77e8-1775-4b3d-a9d6-56888997f292` passed 694 tests with 2 skipped from
  pushed packaging commit `1933b85`. Its immutable audit/evaluator digest is
  `sha256:a1217fec4074fe97f4e811bed439a9239ddfd662b5484b7ddeae46dfc539ea22`.
  The frozen ownership diagnostic launched on that exact digest as durable
  execution `evaluate-milly-ownership-6s2rq`; it failed closed before model
  training or a scientific verdict because a few accepted snapshot rows have
  null display names and collapsed to duplicate `PLAYER_NAN` join keys. The
  repair retains those rows in full-slate naive normalization but assigns
  them unique, explicitly unmatched ID keys; ownership truth still may never
  be zero-filled. No preregistered feature, model setting, fold, comparator,
  or gate changed. Eight focused tests pass after the repair, including a
  two-null-row regression. The retry must use a distinct run directory/ID.
  Failure provenance is tracked under
  `reports/ownership-runs/20260809-milly-k1-c616390/`.
- Null-name repair build `1e5f3245-30ec-4637-b42d-85fa90add577` passed 695
  tests with 2 skipped and produced immutable digest
  `sha256:3929447c0dfb376dc70847a1d4d6291333a42b8d4c96fe8f66b4c25abf0be17a`.
  Distinct retry `evaluate-milly-ownership-kb9fl` failed closed before model
  training or a scientific verdict on the next genuine identity ambiguity:
  separate Ryan Griffin players at different native positions share a name.
  The join key now includes native position plus normalized name, which is
  present on both truth and snapshots and is not a model feature. All eight
  focused tests pass. Preserve the v2 failure directory and use a distinct v3
  retry after full validation; do not reinterpret either failure as evidence
  for or against ownership modeling.
- Position-aware build `7cbd0f43-930c-491d-93d2-2bfe37c73655` passed 695
  tests with 2 skipped and produced immutable digest
  `sha256:a306743b802b2904907f998b0653c626dc8c19e22dbe55795472dbe89942feb2`.
  V3 execution `evaluate-milly-ownership-644mf` completed and appeared to
  pass every frozen gate. Its recorded aggregate contest-aware MAE/Spearman are
  `2.8147/0.7924` versus old all-contest `3.6142/0.5657` and naive
  `4.6548/0.2589`; it appeared to beat both metrics in all three 2023-2025
  seasons and lower top-quartile MAE to `7.5983` versus `9.8483/11.5424`.
  These metrics are now **scientifically superseded**, not an adoption input:
  serve-path review found salary/value ranks were recomputed after the truth
  join, leaking which players appeared in settled ownership instead of using
  the full-slate ranks available live. No scoring arm launched from V3.
- Coverage review found the only zero-match week is a scope mismatch, not a
  name join failure: Christmas 2022 fell on Sunday; the accepted Week-16
  replay contains only the two Sunday games, while DK's named Milly was its
  large Saturday main slate. V3 held-out metrics are unaffected (the week is
  2022 training-only and contributed no joined row), but its coverage
  denominator is also superseded. The evaluator now declares this one
  calendar-proven exclusion, requires every other week to retain >=90% mass,
  and will emit a final v4 report over 71 eligible contest/slate pairs. Nine
  focused tests pass. Do not launch the scoring arm until that clean report is
  tracked and passes the original gate on full-slate rank features.
- Reporting build `5e6db78f-665d-4ab4-867e-2b618f05612f` was cancelled before
  use after the rank-skew audit; no image/result from it is valid. The
  evaluator and reusable training frame now preserve features computed on the
  complete accepted slate through the truth join. Off-by-default downstream
  plumbing for `OWN_MODEL=milly_fade` is implemented but not launched: it
  fits only earlier-season eligible Milly rows, normalizes predicted ownership
  within position to the incumbent penalty scale, and keeps the simulated
  field naive. Focused ownership/replay/infrastructure validation is 28
  passed. Do not run a lineup panel until the corrected diagnostic passes.
- The one allowed downstream arm is now fully guarded but remains unlaunched.
  `OWN_MODEL=milly_fade` changes only the optimizer's ownership fade, never the
  field sampler. Its runner requires the clean 71-slate v4 JSON before it can
  launch true-80 K=1 `0/0/0/40`; its comparator requires exact invariant
  upstream player features, unchanged shared candidate worlds, the frozen
  `proj_tourney = proj - 25*own_est` delta, estimate/candidate/selection
  movement, ownership sum/product diagnostics, and the existing tail-first
  gate. Focused validation across ownership, comparator, panel gate, replay,
  live smoke, and infrastructure is 39 passed; shell parsing, compilation and
  whitespace checks pass. Corrected diagnostic build
  `fa00ea6f-ffd0-49c6-8352-553c24989eb2` passed 697 tests with 2 skipped from
  rank-aligned commit `638ce2a` and produced immutable digest
  `sha256:1530d8d9f9bd67a4928b40c7c42edcc740a8ab2887ddfcda1a6ca5dcb7852959`.
  Corrected v4 execution `evaluate-milly-ownership-wd4ll` passed every frozen
  diagnostic condition over 9,010 held-out rows and 71 eligible slates.
  Aggregate contest-aware MAE/Spearman are `2.8666/0.7865`, versus old
  all-contest `3.6142/0.5657` and naive `4.6548/0.2589`; top-quartile MAE is
  `7.7347` versus `9.8483/11.5424`. It beats both metrics in every held-out
  2023-2025 season, retains `98.90%` ownership mass overall, and retains at
  least `93.74%` in every eligible week. The tracked clean report is
  `reports/ownership-runs/20260809-milly-k1-c616390-v4/`; superseded v3 still
  must never be used.
- The ownership panel preflight is now pinned to 2023 so it must train on 2022
  and exercise the actual `milly_fade` serve path; a 2022 smoke would only
  exercise the intentional cold-start fallback. Focused ownership/comparator/
  replay tests pass (19 tests), shell parsing and whitespace checks pass.
  Exact next action: commit/push this diagnostic milestone, run a full Cloud
  Build of the final guarded scoring code, then launch the one frozen ownership
  panel from that immutable digest. In parallel, continue polling the six exact
  CE union execution IDs and compare the union only after all six succeed.
- Final scoring-code Cloud Build
  `53c60d18-3f77-4a70-bd4c-906261c3d7c6` passed 700 tests with 2 skipped from
  commit `f3086097b79f13de9a7e9eccef570f9063f53d3a` and produced immutable
  digest `sha256:5cab563fdb9bad9f4241631f05bad51e73929851f0aa0acb3cc7cd7135a2c3c0`.
  The guarded 2023 preflight `replay-e80k1milly-smoke-tt2g5` fit on 3,146
  exact 2022 rows, then failed before candidates because DST concatenation
  promoted `is_cold_start` to pandas `object` and LightGBM requires numeric
  serve columns. No season execution launched and no lineup outcome was
  viewed. Provenance is tracked at
  `reports/panel-runs/20260809-e80-k1-millyown-f308609/`.
- The failed preflight manifest also records a supplied full `CODE_SHA` that
  had the correct `f308609` prefix but did not equal the actual image-source
  commit. This did not create panel rows, but it is an audit defect. The runner
  now requires the supplied full SHA to equal local HEAD. The serve repair
  coerces every declared ownership feature to float and adds a regression for
  object-typed `is_cold_start`; 20 focused ownership/comparator/replay tests
  pass. Exact next action: commit/push this fail-closed repair, run a new full
  Cloud Build, and retry from a distinct commit-derived panel ID. Never reuse
  the failed f308609 panel or its digest for the ownership scoring panel.
- Repair build `59f7cbd2-09f5-4cd1-819a-fe1bba0c6d8f` passed 701 tests with
  2 skipped from exact commit `6d4a549e518fbed0677158b57b07fe0532b72a4f`
  and produced immutable digest
  `sha256:24d1b2b778c3e5ca905270d8836b7ee4b1e9632912ff6aa0609c77516813e7aa`.
  Corrected 2023 preflight `replay-e80k1milly-smoke-7zvnq` passed after
  fitting 3,146 exact 2022 ownership rows and serving the actual model.
  True-80 K=1 ownership panel `20260809-e80-k1-millyown-6d4a549` is launched
  with exact season executions `replay-e80k1milly-2019-578rs`,
  `replay-e80k1milly-2021-27qdm`, `replay-e80k1milly-2022-k2cmq`,
  `replay-e80k1milly-2023-rsntz`, `replay-e80k1milly-2024-p82td`, and
  `replay-e80k1milly-2025-2nmwq`. Do not read or compare partial outcomes;
  wait for all six exact IDs to succeed, then run the frozen ownership
  mechanism/tail comparator on the same immutable digest.
- CE union executions for 2019, 2021, 2022, 2023, and 2024 have completed
  successfully. The 2025 execution has written all 18 slates but is still
  finalizing. Exact next action: wait for `replay-e80k1ceu-2025-zjw6k` to
  report success, then run the union comparator. Launch fixed CE replacement
  only if its tracked binary union gate passes.
- All six CE union executions ultimately reported success. Comparator v1
  `compare-k1-ce-panel-kkkzh` failed closed with one reported mechanism issue:
  2,229/50,098 feature payloads were not bit-exact. A column-level audit shows
  zero row/identity/config/actual differences and zero numeric differences
  above `1e-12`; the maximum is `3.552713678800501e-15`. All 25,787 source
  candidates have exact shared actual/p-line/sim-mean/support values; union
  adds 12 candidates on every slate and 1,284 novel CE rosters. V1 is
  preserved under the union panel directory and remains mechanically invalid.
- V1's provisional tail result is highly favorable but not yet a gate pass:
  selected 187/194/200/210/220/230/240 moves `36/22/12/6/3/1/1` to
  `39/26/16/11/5/2/1`; pool oracle moves `44/30/19/9/3/1/1` to
  `47/33/22/13/5/2/1`. The comparator repair keeps bit-exact mismatches as a
  diagnostic, uses `1e-12` only for numeric materiality, and still requires
  every nonnumeric field exactly equal. The gate, CE seed/dose, and thresholds
  are unchanged. Eleven focused comparator/panel tests and the live corrected
  query pass; shell parsing and whitespace checks pass. Exact next action:
  commit/push, full Cloud Build, run labeled union v2, and launch the frozen
  fixed replacement only if `ce_comparison_v2.json` passes.
- Comparator build `4acbc4dd-d54e-4556-9097-1870589f8dcb` passed 701 tests
  with 2 skipped from `04ec460` and produced immutable reporting digest
  `sha256:342c96629fd335c57ab2ff695b79ee29d9b11df73a001ddf7d34ee0c8fee0eff`.
  Labeled v2 execution `compare-k1-ce-panel-wbspp` passed all original union
  gates with zero material feature, shared-world, or candidate mechanism
  failures. The tracked `ce_comparison_v2.json` is the valid gate record; v1
  remains preserved as false-positive audit provenance.
- Fixed equal-budget panel `20260809-e80-k1-ce12-c616390` froze all 107
  source-pool caps before treatment scoring (range 224–251), uses old immutable
  generation digest `sha256:98a31edd...`, code `c616390`, K=1, true 80,
  `12 CE / 28 boom`, and seed 1701. Preflight
  `replay-e80k1cef-smoke-mcv5c` passed. Exact season executions are
  `replay-e80k1cef-2019-4xr9f`, `replay-e80k1cef-2021-sfdjt`,
  `replay-e80k1cef-2022-9km62`, `replay-e80k1cef-2023-8p8z9`,
  `replay-e80k1cef-2024-7tz6v`, and `replay-e80k1cef-2025-xjhhh`.
  Do not read partial outcomes. Once all six succeed, run the frozen fixed
  comparator and promote only if its selected-tail and oracle gates pass.
- Ownership panel remains healthy and partial outcomes remain unread; current
  no-score progress is 7/10/8/12/9/8 slates for 2019/2021/2022/2023/2024/2025.
  Exact next action: monitor the six fixed CE and six ownership execution IDs,
  compare each only after its complete six-season success contract, update
  both protocols/HANDOFF, and continue from whichever mechanisms pass.
- The contest-aware ownership scoring panel subsequently completed all 107
  slates and all six exact executions reported `Completed=True` with one
  successful task and no failures. Comparator execution
  `compare-k1-milly-ownership-wcqqj` found no tail benefit: selected
  187/194/200/210/220/230/240 moves `36/22/12/6/3/1/1` to
  `33/22/12/6/3/1/1`, mean/median weekly max moves
  `179.60/178.82 -> 178.60/177.14`, and pool oracle moves
  `44/30/19/9/3/1/1` to `41/29/18/8/3/1/1`. It therefore fails both the
  required +2 selected-200 lift and the non-worse oracle-200 safeguard.
  The arm is rejected and must not be tuned on these outcomes.
- Ownership comparator v1 labeled the result `invalid` only because 330
  upstream payloads were not bit-exact. Column-aware local re-audit found zero
  material/categorical mismatches, maximum numeric delta `3.5527e-15`, exact
  shared candidate worlds, all 54 trained slates changed, and frozen fade
  equation error `3.9968e-15`. The comparator repair retains that bit-level
  diagnostic while applying the already-established `1e-12` numeric
  materiality rule. Its local disposition is the scientifically correct
  `reject`; no arm setting, tail gate, or result changed. One partial 2023
  weekly score was inadvertently surfaced while checking a raw progress log,
  after all settings and gates were frozen; it was not used for any change or
  decision. Exact next action: commit/push the reporter-only repair, complete
  a full Cloud Build, run a labeled immutable ownership v2, and continue
  monitoring the fixed CE panel (currently 74/107 slates, no failed
  execution).
- Ownership reporter build `b6528016-6572-4b79-8278-a4b1d2999110` passed 702
  tests with 2 skipped from pushed main commit `54b29ca` and produced
  immutable digest
  `sha256:40839f1d99e9a08f54a1343c49c539ed7fe5329d3f1400b8c6cd5bf4f1fc18b3`.
  Labeled v2 execution `compare-k1-milly-ownership-wqgj5` returned valid
  `reject` with zero failures and the unchanged tail metrics above. Its
  tracked `ownership_comparison_v2.json` is the definitive disposition; v1
  remains preserved as false-positive audit provenance. Close this historical
  ownership arm and do not try field-only ownership (the current 194 coverage
  selector does not read opponent-field ownership) or tune the fade dose on
  these outcomes. Fixed CE is now 90/107 slates with 2021 and 2024 complete;
  exact next action is to wait for all six CE execution IDs to succeed, then
  run the frozen fixed comparator on immutable reporting digest
  `sha256:342c9662...0eff`.
- All six fixed CE executions completed successfully and immutable comparator
  `compare-k1-ce-panel-87l22` returned `pass` with zero failures. Selected
  187/194/200/210/220/230/240 improves from `36/22/12/6/3/1/1` to
  `40/26/18/11/5/2/1`; mean/median weekly maximum moves
  `179.60/178.82 -> 181.12/178.64`; pool oracle improves from
  `44/30/19/9/3/1/1` to `47/32/22/13/5/2/1`. The fixed tail-first gate passes
  by +6 selected 200 weeks, +5 selected 210 weeks, and +3 oracle-200 weeks.
- The fixed mechanism audit proves equal pools on all 107 slates (25,787 rows
  each), exactly 12 CE candidates per slate replacing 12 boom candidates,
  1,284 novel CE rosters, exact shared candidate worlds, zero material player
  feature differences, and zero failures. Canonical promote execution
  `accept-replay-panel-p6ll4` independently passed all completeness,
  provenance, feature, authoritative-actual, score-artifact, mask, selection,
  and parity contracts, then atomically promoted 25,787 candidates and 50,098
  player features. `20260809-e80-k1-ce12-c616390` is now the accepted
  historical research baseline. At this historical milestone live/UI behavior
  remained unchanged pending the README's pre-season arm-policy gate; the
  current section records that gate's later completion.
- The promoted baseline has 6 recoverable >=194 weeks across 4 seasons and 4
  recoverable >=200 weeks. Canonical acceptance therefore passes the original
  reranker-development opportunity gate. Exact next action: commit/push the
  CE comparison and promotion artifacts, then preregister a corrected
  true-80 tail-first reranker confirmation on this accepted CE pool before
  evaluating its outcomes. Do not reuse the old 40-entry constants or choose
  a feature arm after seeing new results.
- The one allowed true-80 fixed-pool reranker confirmation is now frozen in
  `reports/2026-08-10-k1-ce-reranker-confirmation.md` before any reranker
  outcome. It uses only the prior structure/provenance lead, strictly
  earlier-season equal-slate-weighted ridge training (`alpha=10`), a fixed
  +/-15 point candidate-world shift, 2019 cold-start fallback, the unchanged
  194 coverage selector with 80 entries, and a within-slate shuffled-shift
  control at seed 314159. Candidate generation and oracle are fixed. Adoption
  requires +2 selected 200 weeks, non-worse 210/oracle-200, a valid mechanism,
  and a lexicographic win over the shuffled control; season signs/mean remain
  diagnostics. Ownership/disagreement arms are not reopened. Thirteen focused
  reranker/panel tests and 38 reranker/infrastructure/persistence tests pass;
  shell parsing, compilation, and whitespace checks pass. Exact next action:
  commit/push, run a full Cloud Build, then execute the one immutable evaluator
  and close or promote the selector arm from its frozen report.
- Reranker Cloud Build `44264eea-f58b-419a-a9b6-a77f13d60dff` passed 707
  tests with 2 skipped from pushed commit `cbd770a` and produced immutable
  digest
  `sha256:09a7ed659928afef1e720b40fc55e2aec8ca643e706c720dee21047aa5d0dd9f`.
  Execution `evaluate-k1-ce-reranker-vhg99` completed with zero mechanism
  failures and valid `reject`. Source/primary/shuffled selected
  187/194/200/210/220/230/240 are respectively
  `40/26/18/11/5/2/1`, `42/26/18/12/5/2/1`, and
  `39/26/19/11/5/2/1`; mean weekly maximum is `181.12/181.40/180.57`.
  The primary moves 1,449 selected slots but adds no 200 week (required +2)
  and loses the lexicographic negative-control comparison because the shuffled
  book reaches 19 at 200. Close A1 and do not run A2/A3, alternate alpha/cap,
  or another shuffle seed on these outcomes.
- Exact next action: commit/push the reranker report, then treat historical
  scoring discovery as closed at the promoted K=1 `12 CE / 28 boom` baseline.
  Complete the README pre-season arm-policy/UI gate so live lineup generation,
  API, UI, and CSV paths explicitly use and expose the adopted policy; keep
  any genuinely new data (Odds API shadow/prospective ownership) point-in-time
  and shadow-only until its own held-out gate passes.

### Recovery provenance

- GitHub `main` was stale at `4619015`; the missing August 7–8 work had been
  built and run in Google Cloud but had not been pushed.
- The latest source was recovered from Cloud Build
  `f182b575-0396-4973-86b9-5ecdebce7f55`, object
  `gs://nfl-predictions-503414_cloudbuild/source/1786195071.986052-229507cc4ee34d3a8067eb4d60e09ba9.tgz`.
- Its audit image is
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:4100028f3d5c29c4b6de423e590054dc765f605a4a88d57670a64ca6f8c21acb`.
  The underlying fully tested replay image is tag `ee6f433`, digest
  `sha256:6e34cb1f3580be71ad2acd50f0faeacf45b59a7039fe7e32b0996ecf26dda9d0`.
- The recovery branch was fast-forwarded into `main` and pushed. Local and
  remote `main` both pointed to `1e3361f` before the 80-entry audit began.
  GitHub-only reports were preserved; no files were deleted during recovery.

### Environment on the replacement computer

- System tools: GitHub CLI 2.97.0, Google Cloud CLI 579.0.0, jq 1.8.1,
  Python 3.14.4, `python3-venv`, and `libgomp1`.
- `.venv` contains editable `.[gcp,app,dev,tuning]` dependencies and passes
  `pip check`.
- GitHub CLI is authenticated as `espechtsoftware`; gcloud and Application
  Default Credentials are authenticated as `espechtsoftware@gmail.com` for
  project/quota project `nfl-predictions-503414`.
- Local `.env` sets `GCP_PROJECT=nfl-predictions-503414` and is gitignored.
  No credential material belongs in this file.
- `ingest-odds` and `ingest-props` now resolve `ODDS_API_KEY` from Secret
  Manager secret `odds-api-key:latest`; both retain immutable image digest
  `sha256:6c556b9e...` and their existing enabled schedules. The default
  compute service account has `roles/secretmanager.secretAccessor`. The
  deployment script now preserves this secret reference and no longer reads
  or distributes a workstation-local Odds API key. No secret value was read.

### Odds API shadow-data implementation milestone

- On `main` after `04fd2ab`, the existing game-lines and live-props requests
  now record secret-free request identity, HTTP status, returned markets, and
  provider quota headers in new partitioned table
  `nfl_raw.odds_api_requests`. Sanitized exceptions intentionally discard the
  provider URL/query so an HTTP or transport failure cannot put the API key
  in logs or BigQuery. Audit-write failures do not trigger a Cloud Run retry
  that would repeat paid calls.
- The fixed nine-market live-only bundle covers pass attempts/completions,
  rush attempts, pass interceptions, rush/reception touchdown allocation,
  and dual-role yards/TDs. It writes only to partitioned
  `nfl_raw.prop_lines_shadow`; repository search confirms no production
  model, API, optimizer, or UI consumer reads that table. Every shadow call
  requires a fresh provider-reported remaining balance and preserves a
  5,000-credit reserve. Missing quota headers fail closed. Historical shadow
  backfill is not implemented and remains prohibited.
- A related point-in-time defect was fixed before season start: `ingest-props`
  formerly assigned all currently listed NFL events—including August
  preseason—to the next regular-season week. It now filters events to the
  next regular-season week's exact US-local game-date window before either
  paid prop request. The deficiency is recorded in README.
- Initial source commit `910bc6e` is pushed on `main`. Focused offline
  validation was green: 26 tests across request sanitization,
  quota capture/persistence, reserve boundaries, local-date filtering,
  base/shadow table isolation, existing game-line behavior, and prop parsing;
  Python compilation and `git diff --check` also passed. Cloud Build
  `5ad9f2e5-4141-41bc-b1f2-3e1ff71b247b` passed 685 tests with 2 skipped and
  produced immutable digest
  `sha256:8dc28e1c06f618118ad2e7695864a56e7428033e367146249520a0f246da1617`.
  Both additive DDL tables were created and verified empty/partitioned before
  deployment. `ingest-odds` generation 32 and `ingest-props` generation 29
  are Ready on that digest; Secret Manager bindings, CPU/memory, command,
  service account, retries/timeouts, and the existing enabled scheduler
  cadences remained unchanged. Only `ingest-props` added
  `ODDS_SHADOW_MARKETS_ENABLED=1` and reserve `5000`.
- Preseason smoke `ingest-props-mmx2l` completed but correctly keeps this
  milestone open. The provider already lists all 16 Week 1 events. The job
  therefore made one events request and inferred 16 base plus 16 shadow
  attempts; four games returned 82 legitimate very-early DraftKings
  anytime-TD base rows, while the shadow returned zero rows. Exact credits
  cannot be cited because the 33-row audit batch failed to load. No job retry
  occurred and no shadow row landed.
- The audit failure was a schema-contract defect: the new table declared five
  fields `NOT NULL`, while the shared DataFrame loader appends an autodetected
  nullable schema. Production columns have been safely relaxed to NULLABLE,
  the tracked DDL now matches, and audit DataFrames explicitly assign Arrow
  string/boolean/integer/timestamp dtypes so all-null fields cannot infer an
  incompatible type. A new `check-odds-quota` command uses the provider's
  free `/sports` endpoint, requires its audit row to persist, and avoids
  repeating any event prop request. Updated focused validation is 27 passed.
- Follow-up commit `ca47ac6` is pushed. Cloud Build
  `313ca4a3-6acc-4f60-83e1-194ef05f6b65` passed 686 tests with 2 skipped and
  produced digest
  `sha256:59ed4fbf111a688125619cfebe41721b54b85e20fcdb762b486274b673880b53`;
  both ingestion jobs were moved to it without other template/schedule
  changes. Free quota-only execution `ingest-props-n5zch` then reproduced a
  second distinct schema defect and was explicitly cancelled before any
  automatic retries. It made no event-prop call and wrote no prop rows.
- Exact warehouse error from an isolated synthetic conversion (which failed
  before writing data): the partitioned+clustered destination expected
  clustering `(request_kind,is_shadow,http_status)`, while the shared loader
  repeated only its `requested_at` partition contract. BigQuery requires both
  when the job supplies partitioning. The same defect would have rejected the
  first nonempty `prop_lines_shadow` append. `load_dataframe` now accepts and
  applies explicit clustering fields; audit and shadow callers pin the exact
  DDL order. A focused helper regression plus all Odds tests pass (28 tests).
- Final source commit `aad6739` is pushed on `main`. Cloud Build
  `00a055a7-d31b-463b-b757-b704560fb21e` passed 687 tests with 2 skipped and
  produced immutable digest
  `sha256:0a55920d638951aaa6516b059f7ae3d1218cc6ee0d89a332805ca611fefc052d`.
  `ingest-odds` generation 34 and `ingest-props` generation 31 are Ready on
  that exact digest with their original scheduled args. Secret refs,
  resources, retries, timeout, service account, and schedulers remain intact;
  `s-odds` is enabled at `0 9,15 * * 3-7` and `s-props` at
  `30 9 * * 3-7`, both America/Chicago.
- Final free validation `ingest-props-8tgqd` completed successfully using
  only the execution-time `check-odds-quota` args override. Its one audit row
  persisted with HTTP 200, endpoint `/sports`, `requests_last=0`,
  `requests_remaining=99940`, and `requests_used=60`. It wrote zero base and
  shadow prop rows; `prop_lines_shadow` remains empty. The audit table has
  one row and zero endpoints containing a query string or API-key-like text.
  The scheduled job template still runs ordinary `ingest-props`, not the
  diagnostic override.
- This milestone is closed. Do not buy or backfill historical Odds markets:
  the account has ample prospective quota, but the new data is not allowed
  into models/UI until held-out residual, tail-calibration, and
  candidate-oracle gates are frozen and passed. Next concrete action is to
  inspect `odds_api_requests` and `prop_lines_shadow` after the next scheduled
  in-season pull, verify actual per-market cost/coverage, and then freeze the
  prospective evaluation before any lineup outcome is viewed.

### Latest validated research state

- Under the operator's explicitly amended aggregate-tail utility, true-80
  K=1 panel `20260808-e80-k1-c616390` is now the **promoted tail-first
  research baseline**. Promotion execution `accept-replay-panel-jhcwr`
  passed on validated digest
  `sha256:4182a4c077a1dcc183be3c82dfcfa44d60d8909dc5807a4996622a49bab29fdd`:
  25,787 candidates, 107 slates, exactly 8,560 selected rows, 50,098 eligible
  player snapshots, zero missing joins, and candidate/live mean parity within
  `2.34e-05`. At the frozen 194 selector its 187/194/200/210/220/230/240
  counts are `36/22/12/6/3/1/1`, mean weekly maximum 179.60, and pool-oracle
  >=200 count 19. K=3 `20260808-e80-k3-c616390` remains the stability and
  production reference at `29/19/8/5/1/1/1`, mean 177.08, oracle >=200 count
  12. This promotion changes the research incumbent only; no live deployment
  default has been changed.

- Final K=1 no-salary-floor panel `20260809-e80-k1-nofloor-c616390`
  completed on all 107 slates with 25,904 candidates and exactly 8,560
  selections. Acceptance `accept-replay-panel-8m9hv` passed on reporting
  digest `sha256:67e20d8308bd...ed4f3f6`; salary comparator
  `compare-adoption-panel-7c4cs` had zero failures. Selected
  187/194/200/210/220/230/240 moves from `36/22/12/6/3/1/1` to
  `37/24/16/8/3/1/1`; mean/median moves 179.60/178.82 to 179.11/177.52.
  Five weeks are gained and one lost at 200; season deltas are
  `{2019:+2, 2021:+1, 2022:0, 2023:0, 2024:0, 2025:+1}`. The source/treatment
  pool oracle grid moves `44/30/19/9/3/1/1` to `43/28/18/9/3/1/1`, so the
  frozen oracle safeguard fails and formal disposition remains
  `tail-first-not-supported`. Never promote the staging panel or tune an
  intermediate floor/selector on it. Because submitted weekly highs are the
  operator's explicit utility, the exact unchanged policy is retained only
  as a distinct prospective `tail_k1_nofloor` shadow; it is not a historical
  adoption and remains excluded from the UI.

- Prospective K=1 shadow infrastructure is implemented on `main` in commits
  `97cee37` and `0e0278d`. Canonical model labels
  remain unchanged; `MODEL_REGISTRY_VARIANT=tail_k1` writes/loads only
  `comp_*__tail_k1` labels, and the loader verifies their stored member count
  is exactly the configured K=1. New `nfl-dfs shadow-k1` refuses canonical or
  incorrectly sized models, selects the same Sunday-main draft group as the
  UI, freezes exactly 80 entries at line 194 with notes disabled, and writes
  a distinct `live_shadow` run synchronously. Missing artifact storage,
  partial lineup counts, feature/candidate warehouse failures, and score
  artifact failures make the job fail rather than silently lose prospective
  evidence. The app and canonical K=3 registry are untouched. Focused local
  validation is green: 47 tests across shadow/registry, persistence, live
  smoke, ensemble, and research infrastructure; Python compilation, CLI
  discovery, shell syntax, and diff whitespace also pass.

- First full validation of commit `97cee37` passed Cloud Build
  `fc5691cf-b359-466c-85cb-b28b2424fec4` with 667 passed and 2 skipped,
  producing digest
  `sha256:39b097ebf714beefecc5478f70c9449de2788ff7371db7b3df375dc29506260c`.
  Jobs `train-weekly-k1` and `shadow-k1` were deployed on that digest; paused
  schedulers are `s-train-k1` (Tue 08:30 CT), `s-shadow-k1-early` (Sun 10:30),
  and `s-shadow-k1-late` (Sun 11:20). Training smoke
  `train-weekly-k1-hrhl8` completed successfully, creating isolated
  `comp_targets__tail_k1/2026-W32`. The canonical `comp_targets` latest object
  remains `2026-W32` and its full listing checksum remained exactly
  `e85a892e48da1b31eb87712b1ace96ea8f8c25f841d9bcdca9084a29b6cd1a8d`.
  A post-deploy review then found that an August preseason DK group could be
  the largest upcoming Sunday before Week 1. Commit `0e0278d` requires the DK
  group's Eastern date to equal the next regular-season week's Sunday. A
  read-only live check resolves the target to 2026w01 / 2026-09-13, finds no
  matching current DK group, and fails closed before model loading or writes.
- Replacement Cloud Build `d5c080e9-03a6-46e8-b8d9-aca3874b287c` passed the
  full suite again (667 passed, 2 skipped) and produced the date-gated K=1
  digest
  `sha256:d7df959ce3f7ed6f41427b6015f4e275606c07e91671aa24872422c8f3319998`.
  Both `train-weekly-k1` and `shadow-k1` are now pinned to that digest. The
  verified shadow contract is `nfl-dfs shadow-k1`, K=1, variant `tail_k1`,
  possession mode, generation `0/0/0/40`, $49k salary floor, 45/55 blend,
  30,000 live worlds, 8Gi/4 CPU, and code SHA `0e0278d`; training uses the
  same image with only K=1/variant settings. All three scheduler states and
  schedules were rechecked and remain PAUSED. Canonical registry checksum is
  still unchanged after that deployment. This image is superseded for the
  paired shadow jobs by the `cb57798` build below.
- Same-time K=3 reference shadow is implemented, validated, and deployed from
  source commit `cb57798`. New `nfl-dfs shadow-k3` requires the
  canonical registry and K=3, shares every 80-entry/194-tail generation,
  date, persistence, and artifact contract with K=1, and records distinct
  `live-shadow-tail_k3-*` panel IDs. K=1 remains `live-shadow-tail_k1-*`.
  Final Cloud Build `a97781f2-c764-4067-b578-feacf931f03c` passed 668 tests
  (2 skipped), producing digest
  `sha256:939778e31defe13dc48b6410d3621422070864cbc60f7fd9680e1faf0d555b89`.
  `train-weekly-k1`, `shadow-k1`, and `shadow-k3` are all pinned to that exact
  digest; verified shadow envs differ only in declared K/registry/command and
  otherwise share the frozen possession, 0/0/0/40, $49k, 45/55, 30k-world,
  artifact-bucket, 8Gi/4 CPU contract. Paired schedules are 10:30 and 11:20
  CT; all five new schedules, including K=1 training, are PAUSED. The
  canonical registry checksum remains unchanged. This control makes future
  K=1 gains/losses paired under near-identical pre-lock information rather
  than judged in isolation.

- Prospective selector/mix freezing and grading are implemented, fully
  validated, and deployed for paused off-season operation. After each
  complete early/late K=1/K=3 source pair, `freeze-tail-portfolios` verifies
  unlabeled live provenance, exact 80-entry counts, registry/K isolation,
  score artifacts, p-line/mask parity, and exact persisted coverage
  reconstruction before appending immutable memberships. It freezes four
  separately labeled books: K=1 194 coverage, K=1 top individual p-line,
  K=3 194 coverage, and 20 K=1 / 60 K=3 coverage. The mixed rule keeps the
  first 20 entries from K=1's own complete coverage order, then walks K=3's
  complete coverage order until it has 60 rosters not already present;
  duplicate count and every source rank/panel/candidate are persisted. This
  exact asymmetric backfill rule is frozen before prospective outcomes and
  must not be changed after Week 1.
- Portfolio run IDs are fixed as
  `live-tail-portfolios-<season>w<week>-early|late`; an existing run is
  accepted only when its complete identity matches byte-for-byte on the
  membership keys. `grade-tail-portfolios` later joins the frozen nine-player
  rosters to authoritative skill/DST DK points, fails on any missing or
  duplicate actual, reports the full 187/194/200/210/220/230/240 grid and
  paired >=200 gains/losses versus K=1 coverage, and never mutates candidates
  or memberships. Focused local validation is green: 38 tests across the new
  freezer/grader, portfolio helpers, both shadow arms, and persistence;
  Python compilation, CLI discovery, shell syntax, and diff whitespace also
  pass. Source commit `c916de4` passed Cloud Build
  `f19ebeb0-5e19-4288-bb50-7bd11bc5e713` with 673 tests passed and 2 skipped,
  producing immutable digest
  `sha256:747aa216d61e25e33a2c31d1d6722449369bb62bab3a8337eff9e71fe19e1e30`.
  Cloud Run jobs `freeze-tail-early` and `freeze-tail-late` are Ready on that
  exact digest with 1Gi/1 CPU, `nfl-dfs freeze-tail-portfolios --slot
  early|late`, one retry, and a 3600-second timeout. Schedulers
  `s-freeze-tail-early` (`5 11 * * 7`) and `s-freeze-tail-late`
  (`50 11 * * 7`) use `America/Chicago` and are both verified PAUSED. Neither
  job has been executed because no matching regular-season Sunday-main source
  panel exists yet.

- Prospective policy v2 is now validated and deployed from source commit
  `e356e1c`. Cloud Build `c2f468ac-405d-4cef-98ed-8cadcda8c08c` passed 675
  tests (2 skipped) and produced immutable digest
  `sha256:19c30dbb0d1ee9fddd55d4f79fc036ba716a2e1dd8788a6f6afa2d23a5381b36`.
  `shadow-k1`, new `shadow-k1-nofloor`, `shadow-k3`, `freeze-tail-early`, and
  `freeze-tail-late` are all Ready on that digest. The three 8Gi/4-CPU shadow
  jobs share possession, `0/0/0/40`, 45/55, 30k-world, artifact, and 80-entry
  contracts; K1/K1-no-floor/K3 differ only in command/panel identity,
  registry/K, and salary floor ($49k/$0/$49k). The freezer now requires all
  three complete unlabeled pools and writes five separately labeled books:
  K1 coverage, K1 top-p, exact K1 no-floor coverage, K3 coverage, and 20/60
  K1/K3. Policy version is `tail-first-v2-20260809`.
- New schedulers `s-shadow-k1-nofloor-early` (Sun 10:30 CT) and
  `s-shadow-k1-nofloor-late` (Sun 11:20 CT) are verified PAUSED alongside
  K1/K3/freezer/training schedules; all nine research schedules remain
  PAUSED. Preseason smoke `shadow-k1-nofloor-b5wqp` failed closed exactly as
  intended—no 2026-09-13 all-Sunday DK group—before model loading,
  generation, or writes. `live_candidates_shadow` still does not exist, so
  zero prospective rows were created. Do not treat this expected failed
  execution as an infrastructure defect.

- The old 27/107 result and the later 17/107 result are invalid controls. The
  former contains illegal repriced lineups; the latter omitted historical DST
  aliases. See the detailed corrections in `CLAUDE.md`.
- The formerly promoted `20260808-livefaithful-b3-ee6f433` (18/107) is
  superseded because its same-image exact replica failed. The current
  accepted and promoted deterministic control is
  `20260808-deterministic-baseline-c616390` on digest `sha256:98a31edd...`:
  107/107 slates, 17,432 candidates, exactly 40 selected per slate, 11/107
  selected clears at 194, mean selected best 173.06, and 20/107 pool-oracle
  clears. Check execution `accept-replay-panel-2t7vn` and promotion execution
  `accept-replay-panel-mlbxt` passed the canonical acceptance and replay/live
  mean-parity contracts. Full same-image replica
  `20260808-deterministic-replica-c616390` passed exact comparison in
  `compare-exact-replay-4j5hz`; the control is reproducible.
- The baseline uses `N_CE=0`, `N_EPISTEMIC=0`, `N_GUMBEL=0`, `N_BOOM=40`,
  `MODEL_ENSEMBLE=3`, and possession simulation. CE, Gumbel, hierarchical
  Gumbel, fast-role, and role-belief variants remain rejected or research-only.
- Cloud Build `b36ed2c6-caa0-4333-9e41-0cafed5f30b8` validated the underlying
  source with `614 passed, 2 skipped` before producing image `ee6f433`.
- Targeted tests on this replacement machine passed for configuration,
  market-implied projections, notes, live smoke, the most recent app flows,
  the two formerly CI-failing replay tests, exact-replay comparator helpers
  (6 tests), and adoption-mechanism helpers (7 tests). Do not run parallel
  tests, local simulations, or other sustained heavy work; use Cloud
  Run/Build.

### Operator tail-first policy amendment — 2026-08-09

- The operator clarified after the completed K=1 comparison, but before the
  candidate-multiple-4 panel completed, that aggregate high-scoring weeks are
  the real utility and that declines in individual seasons are acceptable.
  Mean score is secondary. Future decisions must therefore report season
  variation as risk information, not use the prior four-positive-season and
  at-most-one-negative-season law as an automatic veto.
- Preserve every earlier comparator and disposition under its originally
  frozen law; do not relabel those results as preregistered successes. Under
  the newly clarified utility, however, true-80 K=1 is the current
  **tail-first historical leader**: versus accepted K=3 it moves the
  187/194/200/210/220 counts from `29/19/8/5/1` to `36/22/12/6/3`, keeps
  230/240 at `1/1`, and raises mean weekly maximum 177.08 to 179.60. Its
  season deltas at 200 are `{2019:+3, 2021:-1, 2022:+2, 2023:-1, 2024:0,
  2025:+1}`. This is an explicitly post-result operational interpretation,
  not a retroactive change to `compare-adoption-panel-x9tsz`.
- Freeze the prospective tail-first adoption rule now: require a valid and
  reproducible mechanism, at least **+2 aggregate weeks >=200**, non-worsening
  aggregate >=210, and non-worsening candidate-pool oracle >=200. Report the
  full 187/194/200/210/220/230/240 grid, all season deltas, and mean weekly
  maximum, but neither season signs, >=194, nor mean are hard vetoes. Prefer
  Pareto improvements at 220/230/240; if extreme-tail counts trade off, keep
  the arm research-only until a payout utility is frozen from prospective
  contest/field data rather than inventing retrospective weights.
- The in-progress candidate-multiple-4 arm must still receive its original
  frozen scientific disposition. Because this amendment precedes its full
  result, also apply the prospective tail-first rule as a separately labeled
  operational disposition. Do not inspect or tune individual weeks, K,
  selection line, or another candidate multiple from the outcome.

### Tail-first reinterpretation of earlier valid arms — 2026-08-09

- Reassess only arms whose original rejection depended on the former
  lower-threshold/mean/season-uniformity utility. Do not reopen mechanisms
  that directly lost the 200/210 tail, failed a held-out mechanism gate, or
  were measured only on an invalid historical universe.
- The leading prospective selector hypothesis is **K=1 top individual
  p-line**. On the valid true-80 pool it reached 15 weeks >=200 and 8 >=210,
  versus 12/6 for the promoted K=1 194-coverage book and 8/5 for K=3. This
  rule was found among several post-result sensitivities, so it is not a
  historical adoption; freeze it as a distinct prospective shadow before
  outcomes and grade it with multiplicity clearly reported. K=1 coverage at
  selection line 200 is a weaker secondary clue: 15/6/3 at 200/210/220,
  versus 12/6/3 at line 194.
- The outcome-viewed 20/60 K=1/K=3 allocation is a prospective hedge lead,
  not an adoption. It tied homogeneous K=1 at 12 weeks >=200 and 3 >=220
  while improving 6->7 at >=210. A live implementation must reselect the
  declared quotas from each frozen pool and deterministically backfill
  cross-book duplicate rosters.
- Read-only recomputation of the full valid 40-entry A01/A03 tails found that
  both were more interesting under the amended utility than their old 194
  verdicts showed. The accepted K=3 source's
  187/194/200/210/220/230/240 grid is `26/11/1/1/1/0/0`, mean 173.06, and
  pool-oracle >=200 count 8. Model-only A01 is
  `22/11/3/2/2/0/0`, mean 172.14, oracle 8; both added >=200 weeks were in
  2023. No-floor A03 is `21/11/3/2/1/0/0`, mean 172.43, oracle 9; its added
  >=200 weeks were in 2023 and 2024. Each would satisfy the new aggregate
  tail rule if it had been frozen before those results, but the policy was
  changed afterward. Treat them as hypotheses for fresh K=1 true-80 tests,
  with model-only first because it also added a 220+ week and its 2023w3
  winner is absent from the current K=1 selected book. No-floor is lower
  priority because all three of its historical 200+ weeks are already
  present in the current K=1 book.
- Keep candidate-multiple 4, coherent member-sampled worlds, the conditional
  dependence forest, and K=3 ranked selectors closed: they failed the newly
  important tail directly. Older CE/Gumbel/role arms are not promoted by a
  looser utility because their comparison universe is superseded or their
  tail mechanism was null; CE may receive a clean corrected K=1 exploratory
  test only after the higher-prior selector/model-only work, not a parameter
  sweep.

### Work in progress

- Same-image reproduction panel
  `20260808-livefaithful-b3r-ee6f433` completed and passed ordinary acceptance:
  107 slates, 17,426 candidates, 18/107 clears, mean selected best 175.36.
- Single-member ensemble ablation
  `20260808-a02-ensemble1-ee6f433` completed and passed ordinary acceptance:
  107 slates, 17,488 candidates, 18/107 clears, mean selected best 174.55,
  pool oracle 26/107.
- The exact B3-to-B3r parity audit **failed** in Cloud Run execution
  `compare-exact-replay-pckdb`. All 50,098 player-feature keys and values
  match within the registered tolerance and every candidate's actual score
  matches, but 2019 and 2024 do not reproduce their simulated worlds: 14
  roster keys differ per side, 41 selected flags differ, and 22 slate
  artifacts differ. The other four seasons reproduce exactly. The failure is
  a real reproducibility defect, not an ordinary score loss.
- Do not interpret the K=3 versus K=1 arm yet. Its ordinary acceptance is
  useful only as completeness evidence; the frozen adoption comparator is
  blocked until the same-image control is reproducible.
- Investigation found stable warehouse inputs and exact persisted ensemble
  member point predictions. Component canonicalization eliminated the first
  hypothesis—sub-machine input drift—from the cheap probe and exposed the
  remaining CPU-dependent tied-rank behavior in marginal shaping.
- The first determinism repair was implemented and fully tested: the shared
  live/replay simulator rounds component means to 10 decimal places at its
  boundary and logs raw/effective SHA-256 fingerprints; replay also deduplicates
  its display-only `player_ids` join (which had duplicated 31 old training
  rows) and orders DST inputs. The exact comparator can now compare two
  staging-only smoke probes before a full panel is spent.
- Targeted validation for the repair is green: components (including exact
  seeded equality under machine-epsilon perturbations), replay-shape SQL,
  simulator golden/RNG-parity tests, live smoke, and exact-comparator helper
  tests. The first full repair build,
  `9e42b0d2-418b-4b7d-ae01-93406f247148`, reached 620 passed and 2 skipped but
  failed one repository-layout assertion: recovery had preserved the obsolete
  `sql/features/019_dk_salary_week.sql` alongside its expanded replacement,
  `001a_dk_salary_week.sql`. The obsolete duplicate has now been removed and
  all 66 feature-SQL tests pass locally. Replacement build
  `3a27a669-bf91-465e-ad0c-8aa4a90e2f67` passed the complete suite (619
  passed, 2 skipped) and produced immutable digest
  `sha256:efa18a9a56b62c5c2606eaae3ad37a9765306863a389de8d4af09f8329545a55`.
- The first cheap 2019 probe pair completed on that digest:
  `replay-det19a-2019-lzfjv` and `replay-det19b-2019-45g2g`. Each persisted
  164 candidates for one slate and exactly 40 selected. Their raw component
  hash (`77d4194f...`) and canonical component hash (`3a5abdc4...`) were
  identical, with the same `5e-11` maximum adjustment.
- Exact comparator `compare-exact-replay-g5hf5` nevertheless failed. All 335
  player snapshots and all 164 candidate roster keys matched; player feature
  summaries, actual scores and selected flags were exact. Only the joint
  world assignment drifted: the 164x10,000 totals matrices differed by at
  most 3.1025 points, changing 3 threshold masks and several candidate
  quantiles. This isolated the remaining defect to marginal reshaping:
  NumPy's unstable default quicksort gave tied simulator outcomes different
  ordinal ranks on different CPU implementations while preserving every
  player's marginal distribution.
- Commit `1ab4d32` makes the simulation-column index the stable tie-break for
  both TabPFN and empirical marginal shaping. The focused replay-shape,
  empirical-marginal, draw-widen and SBI suites pass (29 tests). Cloud Build
  `f0251844-2cfe-470c-a12b-f1591f1c97af` then passed the complete suite (620
  passed, 2 skipped) and produced digest
  `sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`.
- The fresh 2019 pair on that digest, `replay-det19c-2019-87z8s` and
  `replay-det19d-2019-cjgvc`, again persisted 164 candidates and 40 selected
  with the same component hashes as the failed pair. Exact comparator
  `compare-exact-replay-zznbf` **passed**: all 335 player snapshots and 164
  candidates matched, candidate ordering did not move, every mismatch count
  and numeric delta was zero, and the full 164x10,000 totals artifact was
  bit-for-bit identical. The 2019 cheap gate is closed.
- The 2024 pair on the same digest, `replay-det24a-2024-bkhfb` and
  `replay-det24b-2024-8zvzx`, also passed in comparator execution
  `compare-exact-replay-mrdnx`: all 700 player snapshots and 161 candidates
  matched, candidate ordering and every mismatch count were zero, and the
  161x10,000 totals artifact was bit-for-bit identical. Both formerly
  drifting-season smoke gates are now closed.
- Fresh default panel `20260808-deterministic-baseline-c616390` completed in
  executions `replay-detbase1-2019-wvc7l`, `...-2021-qtkn4`,
  `...-2022-prk7g`, `...-2023-xkxmz`, `...-2024-x9vv7`, and
  `...-2025-sh6dq`, after preflight `replay-detbase1-smoke-b5djr`. Acceptance
  found 50,098 unique player snapshots, zero missing candidate slates or
  roster players, 17,432 candidates, and exact 107-slate/40-selected
  completeness. Selected clears are 26/107 at 187, 11/107 at 194, and 1/107
  at 200; pool oracle is 20/107 at 194. The 18/107 unstable-world checkpoint
  is not a valid scoring control for later arms.
- Full same-image replica `20260808-deterministic-replica-c616390` completed
  in executions `replay-detrep1-2019-jk6g9`, `...-2021-2hm8h`,
  `...-2022-l7kgq`, `...-2023-r6mqz`, `...-2024-9jdm8`, and
  `...-2025-qmpp2`, after preflight `replay-detrep1-smoke-zzr66`. Check-only
  acceptance execution `accept-replay-panel-2qfbr` passed with the same
  107-slate counts and headline metrics as the promoted control.
- Exact comparator execution `compare-exact-replay-4j5hz` **passed** against
  the promoted control: all 50,098 feature keys and 17,432 candidate keys
  joined with zero mismatch counts, all candidate simulation summaries had
  zero numeric delta, candidate ordering never moved, and all 107
  roster-aligned 10,000-world score matrices were bit-for-bit identical.
  Feature-value round trips were within the registered floating-point
  tolerance (maximum `3.56e-15`). The full deterministic control gate is now
  closed; scoring arms may proceed in the frozen order.
- A01 model-only panel `20260808-a01-modelonly-c616390` completed from the
  same image after preflight `replay-a01model1-smoke-rpw6n`; its six season
  execution IDs are retained in the report directory. The generic baseline
  acceptance execution `accept-replay-panel-xmdlw` intentionally failed only
  its hard-coded 45/55 blend assertion; it still proved 107-slate
  completeness, 50,098 unique feature rows, zero missing joins, and candidate
  mean parity. The wrapper now preserves failed audit logs automatically.
- Mechanism-aware blend comparator `compare-adoption-panel-bc4qd` passed with
  no failures: 15,538 covered player-weeks moved by 0.941 points on average,
  model and market inputs were invariant, all 53 no-market slates reproduced
  exactly, and candidate/player means joined within `2.36e-05`. Model-only
  tied the control at 11/107 clears at 194, fell 26→22 at 187, rose 1→3 at
  200, lowered mean selected best 173.06→172.14, and lowered pool oracle
  20→19. The preregistered disposition is `unsupported-neutral`: neither the
  deletion nor strong incumbent-support directional gate passed. Model-only
  is not adopted; the existing blend remains the default pending future
  evidence.
- A02 K=1 panel `20260808-a02-ensemble1-c616390` completed all six seasons
  after preflight `replay-a02ens1-smoke-cppnj`; check execution
  `accept-replay-panel-w86nj` passed with 17,423 candidates, 107/107 slates,
  50,098 unique feature rows, 16/107 selected clears at 194, mean selected
  best 174.55, and 24/107 pool-oracle clears.
- First ensemble comparator `compare-adoption-panel-5r5vx` failed only the
  assertion that post-shaping player means must move. Code audit proved that
  assertion targets the wrong layer: K changes component beliefs and the
  joint-world rank copula, while full-coverage TabPFN marginal shaping fixes
  each player's downstream marginal distribution. K=1 provenance was exact,
  all 47,692 offensive rows showed K=3 member disagreement, K=1 differed from
  the K=3 member mean by 0.281 points, all other inputs/seeds matched, and the
  post-shaping mean was therefore invariant. The comparator now treats that
  downstream mean as a diagnostic rather than a required direction; focused
  mechanism/panel tests pass (12 tests). No scoring gate was changed. Cloud
  Build `a8ed72ec-d909-447f-881e-3eeaca6b2e7f` then passed the full suite
  (621 passed, 2 skipped) and produced reporting digest
  `sha256:5b7e8e38399c29315a11a8c13c4c2453dc15042c06ed5c29e45b67ac37ebe712`.
- Corrected ensemble comparator `compare-adoption-panel-6kf7z` passed with no
  mechanism failures, but its disposition is `unsupported-neutral`. K=1
  improved the 194 count 11→16, the 200 count 1→9, mean selected best
  173.06→174.55, and pool oracle 20→24. Season deltas were
  `{2019:+1, 2021:0, 2022:+3, 2023:+3, 2024:-1, 2025:-1}`: only three
  positive seasons and two negative seasons, versus the frozen requirements
  of at least four positive and at most one negative. K=1 is not adopted;
  the aggregate gain is retained as a future confirmation candidate.
- A03 salary-floor deletion panel `20260808-a03-nofloor-c616390` changed only
  `MIN_LINEUP_SALARY=0` on the same immutable generation digest after
  preflight `replay-a03floor1-smoke-pddht`. Season executions were
  `replay-a03floor1-2019-cjn9c`, `replay-a03floor1-2021-tl84k`,
  `replay-a03floor1-2022-br5km`, `replay-a03floor1-2023-z8gpc`,
  `replay-a03floor1-2024-nd7bv`, and `replay-a03floor1-2025-vcmkx`; all six
  completed successfully. Check execution `accept-replay-panel-pwlzs` passed
  with 17,514 candidates, 107/107 slates, 50,098 unique feature rows, zero
  missing joins, and replay/live mean parity.
- Salary comparator `compare-adoption-panel-2k87b` passed with no mechanism
  failures. Upstream feature values were invariant. The source generated zero
  candidates below $49k; the deletion generated 3,729 and selected 468 of
  them, with treatment candidate salary minimum $34,100 and selected minimum
  $43,100. The arm tied at 11/107 clears at 194 and 20/107 pool-oracle clears,
  but fell 26→21 at 187 and reduced mean selected best 173.06→172.43. Its
  season-194 deltas were `{2019:0, 2021:0, 2022:0, 2023:+1, 2024:0,
  2025:-1}`. The frozen gate fails; disposition is `unsupported-neutral`.
  Keep the $49k floor and do not tune an intermediate floor on this panel.
- The A03 audit layer was validated in Cloud Build
  `eccb96c1-8fbc-420f-ba37-5d90db0790fc` (624 passed, 2 skipped). Its immutable
  reporting digest is
  `sha256:f6cb471cbb50d5aca186e7f318e29f24d46b83c772cac4951a4c0f4f101ceaee`.
- The operator clarified that the weekly maximum from the submitted portfolio
  is much more important than average lineup score and that 80 entries are
  more likely than 40. Frozen-mask analysis reselected both accepted K=3 and
  staging K=1 candidate pools at 40/80 entries and selection lines
  187/194/200. The 40-entry reconstructions had zero persisted-selection
  mismatches.
- With selection line 194, frozen K=3 moved 11→18 at 194, 1→7 at 200, and
  1→3 at 210 when entries increased 40→80. Frozen K=1 moved 16→22 at 194,
  9→15 at 200, and 5→9 at 210. At 80, K=1 beats K=3 at every measured
  threshold 187 through 220 and its >=200 season deltas are
  `{2019:+3, 2021:0, 2022:+2, 2023:0, 2024:+1, 2025:+2}`—four positive,
  zero negative.
- The 80-entry books each left only one consequential >=200 candidate-pool
  winner unselected. K=3's 2023-week-3 winner was buried at p-line rank
  144/159 and depended on a +30.61 Keenan Allen surprise. K=1's
  2019-week-6 winner ranked 53/161 and could replace one selected entry with
  zero final simulated-coverage loss; it was an ATL/NYJ construction versus
  the selected SEA construction. Deeper audit showed free swaps were common,
  not special to the winners: 32/79 K=3 and 24/81 K=1 unselected candidates
  on those slates had a non-worsening coverage swap. This is a non-unique
  frontier, not permission to hindsight-tune selection. Full evidence is in
  `reports/2026-08-08-80-entry-tail-audit.md`.
- A deterministic, outcome-blind one-swap refinement was added to make that
  claim stronger and reproducible. K=3's missed oracle ranked 25th/30th/26th
  by probability/mean/q99 within its 32-candidate free frontier; local search
  improved coverage 1,795→1,797 but still missed it. K=1's oracle ranked
  4th/10th/4th within 24, yet local search improved coverage 3,595→3,598 with
  other candidates and also missed it. Neither realized maximum changed.
- The frozen 80 result is a lower-bound diagnostic: replay generates
  `CAND_MULT * n_entries` leverage candidates, so a true 80-entry replay has
  160 initial leverage candidates versus 80 in these source pools. The panel,
  acceptance, and comparison runners now accept explicit entry counts while
  defaulting to 40. New selector/audit helpers and focused tests are green.
- Production-faithful 80-entry panels are running on immutable generation
  digest `sha256:98a31edd...`. K=3 preflight
  `replay-e80k3a-smoke-rw4tk` passed, then launched season executions
  `replay-e80k3a-2019-ghcpn`, `...-2021-kl7r7`, `...-2022-t4wzx`,
  `...-2023-6wmkq`, `...-2024-b8ltc`, and `...-2025-qrpkg`. K=1 preflight
  `replay-e80k1a-smoke-gkdnq` passed, then launched
  `replay-e80k1a-2019-hgqwn`, `...-2021-xxqks`, `...-2022-t8d9w`,
  `...-2023-zwbc4`, `...-2024-2z87w`, and `...-2025-k544g`. The manifests
  under `reports/panel-runs/` are authoritative; all 12 season jobs were
  running without a failed condition at the last check.
- Reporting build `38655fa6-f535-45fd-9c03-90392373a167` passed from commit
  `5120014` and produced digest `sha256:835c8320...`. Final comparator build
  `1bce24eb-079e-41d4-8606-e8a63c49605d`, including the explicitly
  preregistered >=200 directional report, also passed and produced immutable
  reporting digest
  `sha256:89f692b6209adbbd070e7b26c998f59f265207877de79496d4419884159410c7`.
- Off-by-default future-arm instrumentation now supports
  `ENSEMBLE_WORLD_MODE=member_sample`: balanced seed-8161 member assignment,
  one coherent member belief per world, centered player point shifts before
  the frozen marginal shaper, and explicit provenance. It requires K>=2 and
  the replay draw path, so it cannot silently affect ordinary projections or
  live defaults. Focused and full local tests pass. It is not preregistered or
  launched; define its same-image comparator only after the running 80-entry
  K=3/K=1 result establishes which configuration is the incumbent.
- Before querying any realized scores from the running true-80 panels, a
  cross-model 80-entry allocation diagnostic was frozen. Report K=1/K=3
  splits `0/80, 20/60, 40/40, 60/20, 80/0`, always selecting at 194 inside
  each model's own true-80 pool and scoring the complete realized tail grid.
  The primary 40/40 split must beat the stronger homogeneous endpoint by at
  least two >=200 weeks, satisfy the standing 4-positive/<=1-negative season
  law, and preserve the 194/210/oracle/mean safeguards. Count cross-book
  duplicate rosters; retaining them in weekly-max scoring is conservative.
  Endpoint strength is ordered by >=200, then >=210, >=194, then mean weekly
  maximum. Use `scripts/analyze_mixed_tail_portfolios.py` after acceptance.

### Deployment caution (superseded by the completed gate above)

The recovered source defaults to the corrected `0/0/0/40` generation budget,
a three-member model ensemble, the 45/55 model/market blend, and the $49k
salary floor. A01, A02, and A03 retain their original scientific
dispositions. Under the later operator-utility amendment, true-80 K=1 with
fixed `12 CE / 28 boom` is now the accepted historical research baseline.
K=3 was the live/stability reference until the pre-season policy gate. That
gate is now complete: the adopted K=1 fixed-CE policy is live, while K=3
remains an isolated prospective stability shadow.

### Next concrete action

The true-80 K=1 model-only arm is complete and closed. All six season jobs
completed cleanly: `replay-e80k1mo-2019-hcxpf`,
`replay-e80k1mo-2021-6s8rw`, `replay-e80k1mo-2022-n5f6s`,
`replay-e80k1mo-2023-n4h4g`, `replay-e80k1mo-2024-qtbq2`, and
`replay-e80k1mo-2025-prbcr`. Reporting build
`95911a3d-8925-4859-bee4-afa5bb69ad8c` passed 673 tests with 2 skipped and
produced audit/comparator digest `sha256:67e20d8308bd...ed4f3f6`. Check-only
acceptance `accept-replay-panel-ggzqg` failed
only its intentionally inapplicable 45/55 assertion while proving complete
107-slate/80-entry provenance and mean joins. Purpose-built comparator
`compare-adoption-panel-qlh5s` had zero failures and returned
`tail-first-not-supported`: selected 187/194/200/210/220/230/240 moved from
`36/22/12/6/3/1/1` to `33/21/12/7/4/1/1`, pool-oracle >=200 fell `19→17`,
and mean weekly max fell `179.60→178.33`. The 200 count trades a new 220.48
in 2025 Week 9 for the lost 201.74 in Week 5; both winning rosters are absent
from the opposing pool. Full mechanism and missed-oracle evidence is in
`reports/2026-08-09-k1-model-only-true80-experiment.md` and the tracked panel
artifacts. Never promote or retune this arm.

The true-80 K=1 salary-floor deletion is complete. The immutable 2022 smoke
`replay-e80k1nf-smoke-7rrbr` and all six season executions passed:
`replay-e80k1nf-2019-nrw5b`, `replay-e80k1nf-2021-zjwt8`,
`replay-e80k1nf-2022-rdvll`, `replay-e80k1nf-2023-57cw8`,
`replay-e80k1nf-2024-gdx9t`, and `replay-e80k1nf-2025-2bpt5`. The complete
result, gained/lost weeks, mechanism, formal failed gate, and post-result
prospective-shadow decision are in
`reports/2026-08-09-k1-no-floor-true80-experiment.md`; immutable acceptance
and comparison artifacts are tracked under
`reports/panel-runs/20260809-e80-k1-nofloor-c616390/`.

The isolated `shadow-k1-nofloor` path is complete and closed until genuine
2026 pre-lock slates exist. Do not add a no-floor/top-p combination, tune an
intermediate salary floor, or query/freeze it before Week 1. No further
historical selector/floor sweep is justified on these 107 known outcomes.

Next, continue the genuinely new-information path: add quota telemetry and a
strictly point-in-time shadow bundle for the already-paid Odds API's unused
volume, touchdown-allocation, and dual-role markets. Preserve existing base
market columns and ingestion jobs, bound requests from measured remaining
quota, store per-book prices/timestamps and response quota headers, and keep
all new features out of production decisions until their held-out residual,
tail-calibration, and candidate-oracle gates are frozen and passed. Do not
launch a historical credit-consuming backfill until the account's remaining
quota and exact request cost are known.

The data-acquisition audit requested during this run is tracked in
`reports/2026-08-09-data-acquisition-priorities.md`. Its ordering is: complete
Classic contest-entry/payout standings first (free and directly aligned with
winning money), one independent ownership/projection source as a measured
trial, expanded shadow use of the already-paid Odds API, then route-level
usage data only if it adds held-out signal. BigQuery has 369,727 prop rows in
10 markets but the vendor exposes many unused volume/TD/combo/tail markets;
the first proposed expansion is shadow-only and quota-metered. The replacement
computer does not need a local Odds API key: both ingestion jobs and the
tracked deployment script now use the existing Secret Manager reference.

Historical full-field backfill was subsequently audited because DraftKings'
free full-standings CSV expires after 10 days. Affordable UI/backtest products
exist, but no public vendor documentation yet guarantees a bulk raw-field
export. First choice is DFS Hero's $1/five-day all-tools trial: BacktestIQ says
it uses real historical opponent fields. Before renewal, require 2023–2025 NFL
Sunday Classic coverage plus either import/grading of our exact 80-lineup
portfolios or usable score/rank/payout output. FantasyCruncher NFL Pro is the
fallback at its current $89.95/month and explicitly includes NFL Lineup Study;
ask support about retained years, contest list, payouts, and export before
purchase. FantasyLabs ($39.95/month NFL) documents historical ownership and
NFL Contest Dashboard lineups but not export or depth. Fantasy Team Advice
advertises projected/live ownership rather than historical fields, and the
claimed Sports Data Direct $34.95 feed could not be verified as current. No
purchase/account creation has been authorized. The exact vendor gate and
primary-source links are preserved in the acquisition report.

The operator subsequently activated DFS Hero's $1 Power trial. Direct access
to the offseason NFL Contest Analyzer listed 309 DraftKings contests for
2025-10-05 and supplied contest-level field, payout, min-cash, and winner
metadata. It did not supply the required underlying fields: both the 161,764-
entry main-slate Millionaire and the distinct main-slate `$40K MEGA mini-MAX`
opened to `Contest data not available`, leaving no leaderboard or CSV export.
DFS Hero therefore fails the current backfill gate unless its support team can
identify a working retained 2023–2025 NFL Classic field and explain a temporary
offseason defect. Do not allow the $149.95 renewal. The fallback remains a
pre-purchase export/coverage confirmation from FantasyCruncher rather than
another blind subscription.

A targeted GitHub/public-repository audit found no usable archive of settled
historical DraftKings NFL ownership or full contest fields. The closest live
repository, `925Sports/925Sports-nfl-dfs-data`, was created in August 2026 and
publishes current projected `RST%` ownership from a Google Sheet, not settled
post-lock historical ownership. Older optimizer repositories contain
salaries/scores or expect the user to supply projected ownership; exact
DraftKings standings-header searches found no public field archive. This is
not presently an acquisition path: BigQuery already has 103,556 actual
ownership records across 1,258 contests and every week of 2022–2025. Continue
searching only for the material gaps—verified 2019–2021 actual ownership or
complete entry/rank/payout fields—and keep source provenance/license checks.
The linked evidence is preserved in the acquisition report.

The operator then confirmed the acquisition direction: existing 2022–2025
actual ownership is sufficient. Do not buy or prioritize additional aggregate
historical ownership, including the 2019–2021 gap. Historical acquisition now
requires complete entry-level lineups/ranks/duplication/payouts to justify
cost; an independent projected-ownership feed remains only a prospective,
timestamped signal trial.

The arm/UI promotion gate in the README's August 24 runbook completed on
August 9; see the current section above for the policy, validation, image,
revision, and exact resume action. Keep all fourteen seasonal schedules paused
until August 24. Do not execute either source shadow or freezer before DK
posts the matching regular-season Sunday main slate. Never mutate the pre-lock
candidate or membership records, and do not retune K, the 194 control target,
the top-p rule, the 20/60 quota, or its asymmetric duplicate backfill on the
107 known historical slates or after prospective outcomes begin.

### 2026-08-08 true-80 completion update

- Both production-faithful panels completed and passed acceptance. K=3
  `20260808-e80-k3-c616390` has 25,813 candidates; K=1
  `20260808-e80-k1-c616390` has 25,787; both cover 107 slates with exact 80
  selections. K=3 check/promote executions were
  `accept-replay-panel-vlw7c` / `accept-replay-panel-d6fbn`; K=1 check was
  `accept-replay-panel-cjct8`.
- At selection line 194, K=3/K=1 scored 29/36 >=187, 19/22 >=194, 8/12
  >=200, 5/6 >=210, 1/3 >=220, and mean weekly maxima 177.08/179.60.
  K=1's >=200 season deltas are `{2019:+3, 2021:-1, 2022:+2, 2023:-1,
  2024:0, 2025:+1}`. Only three seasons improve and two regress, so the new
  high-tail gate fails. At 194 four improve but two regress, so the old gate
  also fails. Do not adopt K=1 or weaken the stability law.
- Official comparator `compare-adoption-panel-x9tsz` ran on digest
  `sha256:458dd21d9074a1a3a35222c5b3aa67c4e331b4ee2e3ea62768c7870ef52fe4a1`
  after Cloud Build `1520f9b3-9f76-47bc-ba15-47f4d621c22b` passed 636 tests.
  Mechanism failures were zero; disposition is `unsupported-neutral`.
- The primary 40/40 mixed book failed (9 >=200, three negative seasons).
  Sensitivity 20/60 tied K=1 at 12 >=200 and improved to 7 >=210, but it is
  post-result sensitivity only and improves just three seasons vs K=3. The
  40/40 book had 392 duplicate roster slots across 96 slates.
- K=3's true pool has 12 >=200 opportunities and captures 8; K=1 has 19 and
  captures 12. The four/seven consequential misses are fully audited. A
  deterministic pre-lock one-swap refinement recovers none, so no simple
  greedy repair is supported. Week-level results are in
  `reports/2026-08-08-true80-weekly-max.csv`.
- Next preregistered pair uses same-image digest `sha256:458dd21d...` and code
  `d99b125`: control `20260808-e80-msctl-d99b125` versus treatment
  `20260808-e80-msarm-d99b125`, true 80, K=3, selection line 194, default
  `0/0/0/40`, with treatment only `ENSEMBLE_WORLD_MODE=member_sample` seed
  8161. Use the unchanged >=200 high-tail gate and the new `member_world`
  mechanism comparator. Do not tune allocation/K/line/seed/budgets.
- Member-world preflights passed: control `replay-e80msc-smoke-mzzgb` and
  treatment `replay-e80msm-smoke-ns5pj`. Treatment logged balanced member
  counts `[3334,3333,3333]` at seed 8161. All six season executions per arm
  are launched; immutable IDs are authoritative in each panel's
  `reports/panel-runs/.../executions.txt` manifest.
- Member-world reporting build `b9c6fb26-6a7d-4e40-bd49-4863fc0d2a99`
  passed 638 tests (2 skipped) and produced immutable digest
  `sha256:29bb404d84e1a6d8d27d94f4204ffa6fbac7d97dab164c54069c4a4a9ec02dea`.
  Use it for both acceptance runs and the `member_world` comparator.
- The deeper true-80 missed-winner audit now measures each oracle against its
  nearest selected simulated-support substitute. None of the 11
  consequential >=200 misses is support-dominated by a selected lineup; the
  nearest support Jaccard is only 0.140-0.464, while every selected entry owns
  unique worlds. This rules out simple duplicate pruning and attributes the
  residual misses to joint-outcome beliefs/candidate ranking. Focused
  validation: `tests/test_tail_portfolio.py`, 7 passed. Full Cloud Build
  `8b8ba490-a181-408b-bba0-a13a36b69790` passed 638 tests (2 skipped) and
  produced immutable audit-tooling digest `sha256:c591980d...`. Production
  selection was not changed.
- The member-world pair completed with all 12 season executions clean: both
  panels have 25,813 candidates, 107 slates, and exactly 80 selections per
  slate. Control check/promote executions were
  `accept-replay-panel-jcx6k` / `accept-replay-panel-wkxsd`; treatment check
  was `accept-replay-panel-b4tqk`; official comparator was
  `compare-adoption-panel-hz7f7`. All durable acceptance/comparison artifacts
  are tracked under the two panel report directories.
- The mechanism passed strongly: 24,118 support masks, 3,545 rosters, and
  2,100 selected slots per side changed with zero invariant-feature or
  same-roster-actual mismatches. At the frozen 194 selector, treatment moved
  187/194/200/210 counts from 29/19/8/5 to 32/20/6/4 and mean weekly max
  177.08→177.94. Its >=200 season deltas are `{-1,0,0,0,-1,0}`; pool oracle
  remains 12. It fails the primary high-tail, stability, and 210 gates and is
  `unsupported-neutral`; keep `ENSEMBLE_WORLD_MODE` off.
- Treatment expands consequential >=200 misses from four to six. The lost
  2019w15 204.66 and 2024w5 211.12 control winners remained available in the
  treatment pool with nearly unchanged marginal probability/mean but were
  displaced by changed joint-world overlap. Outcome-blind local refinement
  recovers none of the six misses. Full evidence is in the 80-entry audit.
- Candidate-budget comparator instrumentation is implemented and focused
  validation is green (39 tests plus shell syntax). It requires default
  `CAND_MULT=2` versus explicit 4, exact invariant features/seeds/shared-roster
  worlds, a strict source candidate subset with extra leverage candidates on
  all 107 slates, and selected-book movement. It also fixes disposition
  reporting so a genuine primary high-tail pass is labeled
  `high-tail-improves`; no score threshold changed. The exact arm and frozen
  gate are in Addendum 113 and the 80-entry audit.
- Full candidate-budget reporting validation passed in Cloud Build
  `d0fc0c32-e055-4765-bcf6-3854aa7ec29d` (641 passed, 2 skipped). Its
  immutable reporting digest is
  `sha256:6c4d71ab991fe26460d77094b84e7cef3579a33a18437d1ba28998e29e50bf70`.
  Use this digest for the treatment acceptance and `candidate_budget`
  comparator.
- Candidate-multiple-4 treatment `20260808-e80-cm4-d99b125` passed preflight
  execution `replay-e80cm4-smoke-2wbs8` in 17m42s. First-slate throughput of
  14-16 minutes proved the inherited 10,800-second task timeout insufficient
  for 17-18 weeks. Before any score was inspected, all six season executions
  were cancelled, their 1,610 partial candidate and 2,406 feature rows were
  transactionally deleted, and the identical jobs were relaunched with only
  timeout extended to 21,600 seconds. Authoritative execution IDs are
  `replay-e80cm4-2019-sb95x`, `replay-e80cm4-2021-2zmrk`,
  `replay-e80cm4-2022-hns7s`, `replay-e80cm4-2023-bfk69`,
  `replay-e80cm4-2024-slxz5`, and `replay-e80cm4-2025-9zsqq`. The cancelled
  IDs and reason are retained in `superseded-executions.txt`; image, CPU,
  memory, args, arm, and seeds did not change. Do not inspect realized scores
  before the full panel completes; row-count/status monitoring is allowed.
- The authoritative candidate-multiple-4 panel has now persisted all 107
  slates, 42,706 candidates, and exactly 8,560 selected rows. Executions for
  2021-2025 are clean successes. The 2019 container explicitly logged
  `exit(0)` at `2026-08-09T10:07:53Z` after persisting all 17 slates, but its
  Cloud Run execution/task metadata remains `Completed=Unknown` with a
  `WaitingForOperation` 30-minute retry condition. Canonical acceptance
  correctly aborted rather than bypass that clean-success contract. Do not
  delete, rerun, promote, or manually override the panel; wait for the control
  plane to reconcile, then rerun `cloud_accept_panel.sh` in check mode.
- Reporting code now implements the separately labeled prospective
  tail-first gate documented above while retaining the frozen scientific
  disposition. It requires +2 aggregate >=200, non-worse >=210, non-worse
  pool-oracle >=200, and a valid panel/mechanism; season signs, >=194, and
  mean remain diagnostics. Focused comparator validation passes 26 tests.
  Full Cloud Build validation is the next step; use its resulting reporting
  digest only after the original immutable candidate-budget comparison is
  also preserved.
- Tail-first reporting validation passed Cloud Build
  `c1080fc9-3210-401c-9f7a-21e048a98d9e` with 655 tests passed and 2 skipped;
  validated image digest is
  `sha256:81ac495c696ca05cddf39208a652896bc73e55dc49e21e8377adbe5fbfa758a9`.
  The earlier direct Docker build `b95d8af8-bb47-423d-ba87-d1371612c0ed`
  succeeded but did not run tests and must not be cited as validation.
- Original-image acceptance execution `accept-replay-panel-fjwz7` passed mean
  parity, all 107 slates, 42,706 candidate rows, 50,098 unique feature rows,
  exact labels/joins, and selected structure, but failed only the old fixed
  candidate range `(80, 400)` on 46 deliberately enlarged slates. This is a
  reporting-contract defect: that ceiling predated and cannot represent the
  registered `CAND_MULT=4` arm. No scoring gate is changing.
- Acceptance now requires a caller-declared candidate multiple to match every
  persisted `lever_env`. Default multiple 2 preserves the old `(80, 400)`
  range exactly; true-80 multiple 4 receives the bounded `(80, 480)` range
  derived from `entries * (multiple + 2)`. The wrapper passes the declaration
  explicitly. Focused acceptance/comparator validation passes 32 tests plus
  shell syntax. Build, rerun check mode as `... check 80 4`, then run the
  immutable mechanism comparison and the separately labeled tail-first
  report; never promote a failed treatment.
- The accepted K=3 missed-winner analysis now separates genuinely lost weeks
  from redundant high scores: 16 unselected >=200 rows span eight slates, but
  ten are on slates where the submitted book already cleared 200; six rows
  create only four consequential missed weeks. Outcome-blind top-80 books by
  p-line/mean/q99 each recover two of those misses but fall from 8→7 aggregate
  >=200 weeks. The best K=3 60/20 coverage/rank hedge only ties eight >=200
  (though 5→6 at 210) and worsens 194. K=1 ranking/hybrid sensitivities reach
  14-15 >=200, but remain positive in only three seasons and negative in two
  versus K=3. No selector change is supported. New reusable ranked/hybrid
  diagnostics pass all nine focused tests; details are in the 80-entry audit.
  The high-unselected table now includes selected weekly best, signed gain,
  and whether the candidate actually adds a 200+ week, so dominated raw
  scores cannot be misread as missed winners.
- Exact weekly pool maxima are selected on 74/107 slates and omitted on 33;
  omitted-oracle median regret is 6.36 and max regret 35.52, while all-slate
  mean regret is 2.72. Only five omitted maxima reach 200: the four threshold
  misses plus 2019w15, where unselected 207.14 beats selected 204.66 by 2.48
  but does not add another 200+ week. The analyzer now prints this broader
  weekly-max view via `--top-unselected-oracles` so threshold summaries cannot
  hide smaller payout-relevant upgrades.
- Against 68 known same-week Milly winning scores, corrected true-80 K=3
  beats 0, comes within 20 points in 0, within 30 in 2, and within 40 in 7;
  mean gap is 60.69. Its candidate-pool oracle also beats 0/68 and narrows
  mean gap only to 57.69. K=1 likewise beats 0 and is never within 20. Thus
  194/200 are comparison markers, not top-prize claims; almost all of the
  first-place gap precedes selection. The analyzer now reports this same-week
  winning-line context automatically.
- Only 7/33 omitted weekly oracles have a non-worsening coverage swap, and
  zero of the five omitted 200+ oracles do. Even 2019w15's 207.14 costs six
  simulated covered worlds in its best swap. Thus the high omissions are not
  free/tied selector choices; current pre-lock beliefs explicitly prefer the
  scenarios that occupy those slots.
- Paired-week evidence also supports retaining the frozen stability law.
  Preregistered K=1 coverage has seven gained versus three lost 200+ weeks
  against K=3 (one-sided exact paired `p=0.172`). Post-result top-p-line has
  eleven gained versus four lost (`p=0.059` uncorrected), but was selected
  from several sensitivities. Treat it only as a prospective shadow lead, not
  as permission to relax the historical gate or play it as the incumbent.
- The four consequential K=3 missed oracles are not obvious contrarian
  lottery tickets. Their naive pre-lock ownership-product ranks are at the
  78.8th-95.0th percentiles of the selected books, and all are more popular
  by proxy than that week's selected-best lineup. They span five or six games
  rather than sharing an omitted concentrated-stack shape. Actual duplication
  cannot be recovered without historical classic entry rows, so this is a
  caution—not a payout claim—but it further argues against hindsight swaps.
- Full validation of ranked/hybrid diagnostics passed Cloud Build
  `b24be18a-13c8-4912-b324-04d872981ebe` (643 passed, 2 skipped), producing
  immutable tooling digest
  `sha256:805a7c1e4e8bfdcf088bc0c4a169ef31196a9a35f88e68c58f24a9bbe91ce5f0`.
- Superseding full validation including weekly-oracle, coverage-cost, and
  same-week Milly-line context passed Cloud Build
  `9a33319b-db99-4f4d-95ae-58016db7382f` (643 passed, 2 skipped), producing
  immutable audit digest
  `sha256:21489a693a72cb533551e9603db60b53af2fe3e8867fd788e6cac96a304cac59`.
- A conditional dependence mechanism was logged and frozen in the 80-entry
  audit before launch: learn walk-forward conditional weights over fixed-role
  historical game-residual templates with an MMD-style random-feature forest,
  then rank-reorder the current calibrated marginals. Off-by-default
  implementation uses `SCHAAKE_TEMPLATE_MODE=forest`; focused tests cover
  leakage exclusion, context weighting, integration, exact marginals, and
  default seeded-path invariance. The exact seed/dimensions and three-season
  gate are frozen in the audit. It must first beat production on both held-out
  role-pair variogram error and joint-q90 tail Brier while preserving every
  marginal draw multiset. Only a passing dependence gate may reach a newly
  preregistered candidate-oracle stage; do not tune it on the 107 realized
  portfolio outcomes.
- The diagnostic is hardened with `SCHAAKE_DIAG_ONLY=1`, which returns before
  role-belief, market-blend, candidate-generation, persistence, and lineup
  scoring paths. `scripts/cloud_dependence_panel.sh` launches only the frozen
  2023-2025 reports after an immutable-image smoke, and
  `scripts/compare_dependence_panel.py` applies the machine-readable weighted
  aggregate/stability gate. `scripts/cloud_finish_dependence_panel.sh`
  requires three clean immutable executions and verifies each diagnostic-only
  exit before recording either a positive or negative scientific result.
- Conditional-dependence Cloud Build
  `107a8e47-1a31-4dc6-a7b8-5d95562bdb60` passed 650 tests (2 skipped) from
  mechanism commit `3dbebb2` and produced immutable digest
  `sha256:12cdf18151af051ac766e302514cceaf34c3d9cf320d13bd1467ed8e88e96978`.
  Use that digest for the smoke and frozen 2023-2025 dependence-only panel.
  Commit `a8c0c38` is only the local log harvester/docs and need not be in the
  diagnostic image.
- Immutable-image smoke `conditional-schaake-smoke-xnt89` passed. Frozen run
  `20260809-forest-dep-3dbebb2` launched 2023/2024/2025 executions
  `dependence-forest-2023-hrh2x`, `dependence-forest-2024-zvrz9`, and
  `dependence-forest-2025-srdqt`. The exact manifest is tracked under
  `reports/dependence-runs/20260809-forest-dep-3dbebb2/`.
- All three dependence executions completed cleanly and emitted the required
  diagnostic-only exit. The forest improved role-pair variogram error in all
  three seasons and aggregate **0.168911→0.165064**, but worsened joint-q90
  tail Brier aggregate **0.017582→0.017635**; only 2023 improved both metrics.
  Machine disposition is `dependence-gate-fails`. The mechanism is valid and
  active (2,304/2,576/2,848 templates; mean effective weights about
  229/239/238) but does not proceed to candidates or scoring. Do not tune its
  seed, forest size, leaf size, RFF dimension, roles, features, or seasons on
  this result.
- The known-real-winner audit now resolves all 612 player slots from 68 Milly
  winners against the immutable accepted K=3 snapshots. The pool exposes
  8.51/9 winning players on average, but its closest candidate contains only
  3.46. That assembly is not below an exposure-preserving null (3.30), and
  winner-pair occurrence is 0.368 versus null 0.366; selection is likewise
  3.31 versus 3.22 and 0.325 versus 0.330. The old broad assembly-defect story
  does not survive the corrected true-80 baseline. Only 33/612 winner slots
  are missing from the entire pool; they average 22.74 actual versus 7.19
  projected (+15.55 surprise), led by WR/TE. New reusable
  `real_winner_overlap.py` diagnostics and two focused tests are tracked. No
  construction or selector lever is adopted from this outcome-aware audit.
- The same real-winner diagnostic on rejected K=1 finds essentially equal
  player coverage (8.50/9; 34 missing slots) but modestly higher pool/selected
  closest-roster overlap (3.53/3.44 versus K=3 3.46/3.31) and realized
  oracle/selected-best overlap (2.31/2.24 versus 2.07/1.97). Paired
  selected-best overlap gains 25, ties 27, and loses 16 weeks. This is a
  legitimate prospective K=1-shadow lead but cannot override its frozen
  three-positive/two-negative season defect.
- Real-winner audit Cloud Build
  `3469c6ad-06fa-4058-8287-f8d4adecc81e` passed 652 tests (2 skipped) from
  code commit `dd08bd8` and produced immutable digest
  `sha256:81b9faa89829bc5035fdb135e9df8c39ed0f74b5f8ddc6ee5f5dcf2e29950a4a`.
- Candidate-budget acceptance repair passed Cloud Build
  `0cba47ea-954e-451e-b481-f93585d4b593` with 657 tests passed and 2 skipped;
  validated reporting digest is
  `sha256:4182a4c077a1dcc183be3c82dfcfa44d60d8909dc5807a4996622a49bab29fdd`.
  Check-only acceptance `accept-replay-panel-z5ncj` then passed the complete
  42,706-row, 107-slate, true-80 multiple-4 panel. Do not promote it.
- Candidate-budget comparator `compare-adoption-panel-ljdlp` completed with
  zero failures. The treatment is a strict superset on all 107 slates:
  25,813 shared rows plus 16,893 new leverage rows, 153-160 extras per slate,
  exact shared actual/p-line/mean/support values, exact invariant player
  features, and 1,832 selected slots changed in each direction.
- At the frozen 194 selector, candidate multiple 2→4 moves
  187/194/200/210/220/230/240 from `29/19/8/5/1/1/1` to
  `30/22/9/2/1/1/1`; mean weekly maximum moves 177.08→177.27. The 200 gain is
  only +1, all in 2021, and 210 loses three weeks. Frozen disposition is
  `unsupported-neutral`; the prospectively amended operational disposition
  is `tail-first-not-supported`. Raw candidate scaling is rejected and closed
  on this historical panel; do not tune multiple 3/5/8 or selection line.
- Deeper treatment audit finds 16 pool-oracle weeks >=200 versus 12 for the
  control, but only 9 are selected. Seven consequential >=200 oracle weeks
  remain unselected: 2025w12 220.86, 2019w9 216.42, 2025w11 213.58, 2025w2
  210.64, 2019w6 205.44, 2023w16 202.74, and 2025w9 202.50. Only 2025w2 has
  a non-worsening one-swap; the outcome-blind refinement still misses it.
  Across all realized rows, 55 unselected >=200 candidates span 14 slates,
  but most are redundant to an already higher selected score.
- Exact source/treatment joining shows all four newly created >=200 oracle
  weeks are extra leverage rosters and all remain unselected: 2025w11
  213.58, 2025w2 210.64, 2023w16 202.74, and 2025w9 202.50. Conversely, the
  sole selected >=200 gain—2021w11 205.20—already existed in the smaller
  control pool; the added candidates only changed coverage interactions
  enough to select it. That reshuffle displaced control 210+ winners in
  2022w14 (214.02→206.42), 2023w3 (212.38→201.28), and 2024w5
  (211.12→202.42). This is direct evidence that selection/belief interaction,
  not absence from the raw generator, limits the submitted extreme tail.
- The enlarged pool preserves individual real-winner-player coverage at
  8.51/9 and the same 33/612 missing winner slots. Closest candidate overlap
  rises modestly 3.46→3.57, but selected overlap remains 3.31 and same-week
  first-place gaps remain enormous (selected/pool mean 60.17/55.68; 0/68
  wins or within 20). More leverage candidates add opportunities without
  fixing selection or rare-boom beliefs.
- Declared sensitivities do not displace K=1. Multiple-4 at selector 187
  reaches 10 >=200 and 5 >=210; top simulated-mean selection reaches 10/6
  and 2 >=220, but both trail K=1's 12/6/3 and are outcome-viewed
  sensitivities. K=1 remains the tail-first historical leader under the
  operator's amended utility. Next work must develop K=1 under the new
  prospective policy or add genuinely new prospective field/belief data—not
  mine another selector/multiple on these 107 known outcomes.
