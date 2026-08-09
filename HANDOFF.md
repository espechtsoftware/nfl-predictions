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

## Current state — 2026-08-08 19:19 CDT

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

### Deployment caution

The recovered source defaults to the corrected `0/0/0/40` generation budget,
a three-member model ensemble, the 45/55 model/market blend, and the $49k
salary floor. A01, A02, and A03 are now recorded; none was adopted. Do not
change production deployment knobs until the
deployment contract is rechecked against this corrected research state.
Earlier deployed `12 CE / 28 boom` settings are stale.

### Next concrete action

The member-world pair is complete and rejected. Do not tune its line, K,
allocation, seed, or budget on these outcomes. Before another costly panel,
run the now-frozen final historical confirmation: accepted source
`20260808-e80-msctl-d99b125` versus treatment
`20260808-e80-cm4-d99b125`, changing only `CAND_MULT=4` from default 2 on the
same generation digest/code. Build the new `candidate_budget` reporting gate,
run the treatment preflight/panel, accept it, compare it at true 80, and apply
the unchanged >=200 high-tail law. Do not tune another multiple or target line
afterward. The lineup analyzer remains logged in `README.md`.

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
- Exact weekly pool maxima are selected on 74/107 slates and omitted on 33;
  omitted-oracle median regret is 6.36 and max regret 35.52, while all-slate
  mean regret is 2.72. Only five omitted maxima reach 200: the four threshold
  misses plus 2019w15, where unselected 207.14 beats selected 204.66 by 2.48
  but does not add another 200+ week. The analyzer now prints this broader
  weekly-max view via `--top-unselected-oracles` so threshold summaries cannot
  hide smaller payout-relevant upgrades.
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
