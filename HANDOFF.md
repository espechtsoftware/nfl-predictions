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

## Current state — 2026-08-08 18:14 CDT

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
- The recovered source is overlaid on branch
  `recovery/2026-08-08-cloud-handoff`. GitHub-only reports were preserved; no
  files were deleted during recovery.

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

### Latest validated research state

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

### Deployment caution

The recovered source defaults to the corrected `0/0/0/40` generation budget,
a three-member model ensemble, the 45/55 model/market blend, and the $49k
salary floor. A01, A02, and A03 are now recorded; none was adopted. Do not
change production deployment knobs until the
deployment contract is rechecked against this corrected research state.
Earlier deployed `12 CE / 28 boom` settings are stale.

### Next concrete action

The currently executable preregistered corrected-universe arm queue is
exhausted. Do not tune the salary floor, revive a closed generator/reranker
family, or promote K=1 from its aggregate headline. Preserve the deterministic
K=3, 45/55 blend, $49k-floor control. The next evidence-bearing scoring work
requires genuinely independent data: use new 2026 outcomes for a prospective
K=1 confirmation and for point-in-time evidence/tracking/market signals, or
import real classic standings/payout curves before optimizing contest-dollar
objectives. The user-supplied lineup analyzer remains a separately logged
future product task in `README.md`, not a scoring-arm continuation.
