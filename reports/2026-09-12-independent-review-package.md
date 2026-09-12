# Independent review package — 2026-09-12

**Purpose.** Hand this to a model that has not worked on the system, so it can
check the work rather than continue it. Everything here is written to be
falsifiable: identities, commits and numbers are given so each claim can be
re-derived. Where I am unsure, or where I made mistakes, it says so.

**Author.** The agent that performed the 2026-09-11/12 session. I acted first as
the lab agent, then took over the production role at the operator's instruction
when the production team exhausted its budget. That matters for review: **I both
produced and reviewed most of this work, which removes the independent check the
two-team arrangement normally provides.** That is the single biggest reason to
scrutinise it.

---

## 1. The two projects

### nfl-predictions — PRODUCTION

- Repo: `github.com/espechtsoftware/nfl-predictions`, local `/home/erich/projects/nfl-predictions`
- GCP project: `nfl-predictions-503414`
- What it is: the live DraftKings NFL DFS pipeline (ingest → features → models →
  inference → optimizer/backtest), plus a large body of **frozen research
  chains** — preregistered, hash-pinned, fail-closed pipelines that publish
  create-once artifacts to GCS and run on Cloud Run.
- Authoritative docs: `CLAUDE.md` (rules), `HANDOFF.md` (current-work record,
  ~39k lines, append-only in practice), `README.md` (incl. the Data deficiency
  log), `reports/2026-07-25-system-study.md` (the experiment ledger, ~99 addenda).
- Live cadence: Cloud Scheduler jobs prefixed `s-` (e.g. `s-nflverse`,
  `s-features-sun`, `s-project-su`, `s-train`, `s-dk`, `s-props`, `s-odds`).

### nfl2 — LAB

- Repo: `github.com/espechtsoftware/nfl2`, worktrees under `/home/erich/projects/.nfl2-worktrees/`
- GCP project: `nfl-2-506823` (buckets `nfl-2-506823-lab`, `nfl-2-506823-sealed`)
- What it is: a faster-iterating lab that runs **preregistrations** (`PREREG-0NN.md`)
  — designs frozen before any outcome is read, then executed as mechanics-first
  cohorts with a single gated outcome join at the end.
- Reporting channel: lab appends numbered updates to
  `handoffs/LAB-TO-PRODUCTION-2026-09-01-ACTION-NOTE.md` on branch
  `lab/lab-notes-running-20260910`. Production replies with
  `handoffs/PRODUCTION-TO-LAB-*.md` notes. This session reached Update 388.
- Standing lab constraints (these are real and were respected): lab never builds
  images, launches executions, merges to main, or opens outcomes **on its own
  authority**; publishes only under pre-declared allowlisted prefixes; never
  rewrites pushed history.

### How they relate

The lab designs and runs preregistered experiments cheaply; production reviews,
and owns the live money path and the frozen chains. Artifacts flow lab →
production for review. The two GCP projects are separate, so lab work cannot
touch production data by accident.

**Caveat for the reviewer:** in this session that separation collapsed. The
operator instructed me to take over production, so lab-origin analysis and
production-role actions were performed by the same agent.

---

## 2. The objective

Win large-field DraftKings NFL tournaments (GPPs). The program does **not**
optimise mean lineup score; it optimises the **upper tail** — how often a week's
best entered lineup clears a high threshold. The ledger's headline metric is
historically "weeks with best-of-N ≥ 194" across a 107-slate replay panel.

So every result must be read against a tail functional, not an average. A lever
that raises mean score and not tail clears is not an improvement here.

Key standing positions from `CLAUDE.md` that a reviewer should hold in mind:

- **"Selection is closed FOR THE CURRENT SIMULATOR AND STATIC FEATURE SET"**
  (Addendum 95) — five falsified selector approaches. Explicitly *not* the
  stronger claim "selection is closed".
- **Reopening condition:** a selector may be revisited only on genuinely new
  pre-lock information, with evaluation frozen before new outcomes are seen.
  Retrospective tuning on the same slates is **panel mining and forbidden**.
- **The only live capture paths are MORE ENTRIES per slate and genuinely new
  information.**
- There is currently **no citable complete-universe replay baseline** — several
  historical headline numbers were retracted after audits found contaminated
  salaries and slate-composition defects.

---

## 3. What was tried this session, and what it showed

### 3.1 PREREG-086 efficacy read — NO_NOMINATION

The lab's minimal-core completion experiment. Mechanics were sealed by
production before the read; I verified the seal independently (bytes 48,278,965,
sha256 `fdec2593…4212`, matching production's published claim).

Cohort: 72 slates, seasons 2021–2024, k1 panel, two arms
(`D800_STANDARD` control, `D400_PLUS_MINIMAL_COMPLETION` treatment),
57,541 vs 57,565 candidates, 28,800 completion attempts
(28,770 optimal / 8 integer-feasible-not-proven / 22 infeasible).

Preregistered gate and result:

```
(a) 230+ slate supply increased ......... True   (1 -> 2 slates of 72)
(b) mean pool-oracle gain >= 5.0 points . False  (+0.570)
(c) positive 95% paired interval ........ False  (-1.704, +2.973)
RESULT: NO_NOMINATION   adoption=false  promotion=NONE
```

Interpretation I offered, which a reviewer should challenge:

- The positive mean is driven entirely by one season (2022 +4.35; 2021 −1.31,
  2023 −0.73, 2024 −0.03).
- The K20/K80 books moved **against** treatment under both critic laws.
- **Criterion (a) is nearly vacuous**: 1 slate vs 2, out of 72. It passed while
  carrying no evidential weight. This is the preflight-support rule — the gate
  was frozen on a cell whose support was never censused.

**A defect the read caught that is worth verifying independently:** every DST row
in `snap_pitclean_k1` carries the placeholder `gsis_id = "0.0"`. The roster key
is the `id` column (`DST_MIN`, `DST_ARI`), and for non-DST rows `id == gsis_id`.
Keying on `gsis_id` would have collapsed all 26 defenses per slate into one row
and silently mis-scored the DST slot of all 115,106 candidates — without erroring.
The first run refused on duplicate keys; the repair was diagnosed from the
duplicate structure, not from any realized value.

### 3.2 Three levers measured on realized scores

Report: `reports/2026-09-12-retrieval-lever-measured-on-realized-scores.md`.
All comparisons use rules frozen **before** the efficacy read, so this is a
comparison of pre-existing arms, not a search over opened outcomes. No new
outcome was opened.

```
more entries (K20 -> K80)            +13.55   CI (+10.61, +16.68)   POSITIVE
minimal-core completion (PREREG-086)  +0.57   CI ( -1.70,  +2.97)   zero
selector law (incumbent vs corrected) -0.29   CI ( -4.65,  +4.32)   zero
```

Supporting numbers (arm `D800_STANDARD`, law `incumbent`, 72 slates):

```
K20 realized book max        167.97
K80 realized book max        181.52
pool oracle (best candidate) 194.25
K20 retrieval gap            26.28   CI (22.78, 29.89)
pool size                    799 candidates/slate
```

Tail clears out of 72:

```
  line    K20    K80   pool
   187     13     28     50
   194      8     17     35
   200      7     14     25
   210      3      5     14
   220      1      1      2
   230      0      0      1
```

Ranker signal against a random-selection null of the same size:

```
K20 (2.5% of pool)   6/72 =  8.3%   lift 3.33x   p=0.0094
K80 (10%  of pool)  14/72 = 19.4%   lift 1.94x   p=0.0113
```

Claims I drew, each of which should be checked:

1. **Selector choice is worth nothing measurable** (−0.29, CI straddles zero,
   30/72 win rate).
2. **The world models were confidently wrong about it.** Each scores its own
   selector 5–7 pts higher on held-out simulated worlds
   (incumbent-under-incumbent 174.44 vs corrected-under-incumbent 169.06;
   corrected-under-corrected 191.86 vs incumbent-under-corrected 184.32). That
   confidence does not survive realized outcomes.
3. **The tail splits at ~210.** Below: retrieval-limited. Above ~220:
   supply-limited (whole pool holds 2 at 220+, 1 at 230+). Tail-targeted
   selector arms are therefore measuring an empty set.
4. **The ranker is not noise but is thin** — 3.33× lift still misses the best
   candidate in 92% of slates, and dilutes to 1.94× by K80. Both laws share the
   same thin discriminator, which explains why swapping them does nothing.
5. **Proposed bar for any future retrieval lever:** roughly double the K80
   retrieval rate (19% → 40%) to close half the remaining 12.7 points.
6. **Every lever above lives below the Millionaire winning line.** Joining the
   68 tracked Milly winners gives 34 overlapping slates (2023–24). Scoring is
   identical (mean diff −0.024) and the universe matches (295/306 players
   resolve; the misses are initial ambiguities). Result: **0/34 wins at K20,
   K80, and the entire pool**; pool-oracle margin median **−36.5**, best −6.2.
   Actual winning lines: median 232–239 every season; `194` is the ledger's
   *minimum* 2025 winning line (confirmed: 2025 min = 193.9), `237` its average
   (ledger: "median N ~10^15, effectively unreachable"). So entries/retrieval
   improve *placement*, not win probability, which is ≈0 for everything measured.
   Winning is a supply problem at ~237+ (pool holds a 230+ candidate in 1/72).
   **Prior art:** ledger Addendum 114 (2026-08-09) already found the
   candidate-pool oracle beats 0/68 winners (mean gap 57.69) and concluded
   "upstream belief/candidate quality — not selector mining — [is] the dominant
   first-place problem." Item 6 is a replication on a fresh cohort, not a
   discovery; cite Addendum 114. The only lever that ever moved
   237-reachability there was variance via boom draws (1/17 → 5/17), which is
   the adopted N_BOOM=160 generator.

---

## 4. Eight structural defects found and fixed

These were all in production's frozen chains. Every one was a step that **could
not satisfy its own gate** — none were flaky. Production had burned four attempts
on #1 alone.

| # | defect | fix commit |
|---|---|---|
| 1 | `--repository-root` did not bind Python module resolution; the declared provenance tree and the executing code could differ silently | `b72e2c30`, swept `326b1592`, `3389a157` |
| 2 | capture-plan wrote an untracked artifact, then required tracked-clean-including-untracked in the same invocation | diagnosed; see §5 |
| 3 | create-once refused the path its own prior run created | `3023bc5e` |
| 4 | four sites encoded "task0 runs at parallelism 1", which Cloud Run cannot produce | `aecc18c8` |
| 5 | `jq` built the collect request from `--arg`/`--slurpfile` with no input and no `-n` → 0-byte request | `958ca248` |
| 6 | `secure_read_current` returned bytes; its consumer required an observation mapping | `2df3f261` |
| 7 | image had no `refs/remotes/origin/main`, but the runtime census required it | `a7777cc4` |
| 8 | frozen G0 evidence located by absolute operator paths → unusable in-container | attempted `b8f6235f`, **reverted** `b5ac2c0f` |

**The pattern a reviewer should test:** three of these (#4, #6, and the fixtures
behind #5) shipped green because **the tests encoded shapes no producer emits** —
executions with `parallelism: 1` that Cloud Run cannot create, an observation
mapping nothing returns. The suite was not wrong about the code; it was wrong
about reality, and it agreed with the code, so nothing caught it. This is exactly
what frozen-chain rule 1 (one outcome-blind smoke against real artifacts before
freezing) exists to prevent.

---

## 5. Open blockers

### 5.1 Capture-plan circularity (defect 2/5 family) — diagnosed, unfixed

The capture plan records **HEAD** in 6 of 95 fields. The plan must be committed
(to satisfy tracked-clean), and its marker must reach `origin/main` — both of
which move HEAD. So the HEAD recorded inside the committed plan can never equal
the HEAD at validation. Proven by a read-only derivation harness: both bodies
106,016 bytes, and in every differing field the **content hashes are identical**
and only the commit label moved.

Exact site: `corpus_r6_matchup_capture_plan_v1.py:1132 _code_identity()`, called
at 1191/1196 and 1373/1378, fed by one `implementation_commit_sha` = HEAD.

My recommendation, which should be reviewed: compare these identities by
**content** (`module_sha256`, which already matches) and treat the commit as
informational — frozen-chain rule 2. It is the smaller change than making the
field per-file.

**However** — I later found this may not be on the critical path (§5.3).

### 5.2 Source-v3 containerisation — PROTOCOL DEADLOCK, needs an operator decision

`corpus_extreme_tail_panel_execution.py` locates frozen G0 evidence through
absolute paths naming one developer tree. In the release image the repo is
`/app`, so the replay fails:

```
transitive replay path[5] exact read failed: .../g0-authority-lock-v1.json
```

That same file is `REPLAY_HEAD_STABLE_PATHS[10]` — pinned byte-identical between
the candidate commit and HEAD. Repairing it produces:

```
transitive replay path[10] changed between candidate and descendant HEAD
```

**The file must change for the container to work and must not change for the
replay to validate.** Verified empirically in both directions. I attempted the
repair, reverted it, and left the tree clean.

Two exits, both operator decisions:

1. Re-establish the fixed-G0 candidate authority at a new commit — invalidates
   the candidate-v2 lineage the capture plan, discovery matrix and ablation all
   bind.
2. Run worker/verify/publish on the host, where the absolute paths resolve.
   **I checked this and it does not work as hoped:** `publish` requires a
   `task0_authorization` validated by
   `revalidate_full_publication_authorization_provider_source_v3`, which reopens
   a `verifier_provider_receipt_identity` — a real Cloud Run verifier receipt. The
   authorization is provider-rooted by design.

### 5.3 What actually blocks the retrieval ablation

The FP/SIS 2×2 ablation's prepare input needs six fields; two are artifacts:

```
discovery_matrix_freeze_terminal_identity   DONE: 23184230…  (reopen-verified)
source_v3_release_identity                  NOT PUBLISHED
```

The source-v3 release is produced by the capture plan and published by the
source-v3 batch chain — which is blocked by §5.2.

### 5.4 Extreme-tail factorial drift — protocol decision

~115 test failures in `test_corpus_extreme_tail_*` are a **true positive**.
Reconstructing `ClassicProductionPolicy` at freeze commit `c876e7f2` reproduces
the pinned P0 hash exactly, so the drift is measured: 11 environment keys moved
since 2026-08-24, including the deliberate Week-1 generator swap (`N_BOOM`
40→160, `N_LEV` added at 40) and eight new construction levers.

Do **not** relax the `BOOM_UNIQUE_FILL` sentinel (tried and reverted — it deletes
the earliest alarm in one true signal) and do **not** repoint at
`incumbent_control_environment` (restores `n_boom=40`, still misses the hash).
Analysis: `reports/2026-09-11-frozen-factorial-policy-drift.md`.

---

## 6. Queue — what remains to be tried

Ordered by my estimate of expected value, which should itself be challenged.

1. **More entries per slate — for placement, not wins.** The only lever
   measured with a positive interval (+13.55, more than doubling 194+ clears).
   Qualified by §3.2 item 6: it moves finish position within a band that never
   reaches the winning line (0/34). It is a bankroll/contest-structure decision,
   and **its dollar value depends on the payout curve and field score-to-rank
   mapping, which do not exist in the warehouse** (`contest_entries` has never
   received a row; DK purges standings in ~4 days). **The Week-1 Monday/Tuesday
   standings capture is therefore load-bearing** — it is the first chance to
   price this lever rather than assume it.
2. **A tail-supply mechanism that demonstrably generates 220+ candidates.**
   Above 220 the pool holds 2 of 72 slates. Any mechanism should be required to
   show generation before any selector or entry change is tested there.
3. **A better discriminator (world model), not a better ranker.** Bar: double the
   K80 retrieval rate, 19% → 40%. State and test this cheaply before building a
   chain.
4. **FP/SIS 2×2 ablation (P0 in the Neo4j review).** Blocked by §5.2. Before
   unblocking it, restate its hypothesis: this session's evidence says the
   binding constraint is the world model's discrimination, not the ranking rule,
   so the ablation is worth running only under the hypothesis that paid sources
   improve the **model**.
5. **P2 generation/completion under the four source cells.** Its stated gate
   (PREREG-086's mechanics) is now clear. Note PREREG-086's own completion lever
   returned `NO_NOMINATION`, which weakens the prior.
6. **Test-suite health.** `scripts/test_lanes.sh` added (money / changed / full /
   quarantine). Money lane is green: 218 passed, 4m17s, vs ~77 min for the full
   suite. Inventory of remaining failures:
   `reports/2026-09-11-failing-test-inventory.md` — ~115 factorial (true
   positive, §5.4), ~62 ERRORs in `test_final_forensic*` /
   `test_finish_a7_select_ladder` (uninvestigated), ~59 scattered (several
   confirmed to be stale pre-boom-first expectations).

---

## 7. Things I would check first if I were reviewing

Ranked by how much damage a mistake would do.

1. **Did I mis-join realized scores?** Everything in §3.2 depends on the `id` vs
   `gsis_id` key. Verify: `id` is unique within every (season, week) in
   `snap_pitclean_k1` for 2021–2024, zero null `actual` in 35,097 rows, and every
   roster token resolves. If the key is wrong, every number in §3.2 is wrong.
2. ~~Is the entries result an artifact of the selector rather than of K?~~
   **CHECKED after first draft — resolved.** If K80 were not a superset of K20,
   "+13.55 for 60 more entries" would conflate *more entries* with *a different
   book*. Verified across both arms and both critic laws: **K20 ⊆ K80 in 144/144
   cases, mean overlap 20.0/20.** The greedy expected-max order is nested by
   construction, so the gain is attributable to the additional 60 entries alone.
   Re-derivable from `sel[slate][arm][law]['k20_candidate_ids']` vs
   `k80_candidate_ids` in the r2 shards.
3. **Is the random-selection null the right null for §3.2's lift?** I compared
   against uniform sampling from the 799-candidate pool. If candidates are not
   exchangeable (they are generated by different arms/tags), uniform may be the
   wrong baseline and the 3.33× may be over- or under-stated.
4. **Is criterion (a) of PREREG-086 as vacuous as I claim?** I assert 1-vs-2
   slates carries no evidential weight. That is a judgement, not a computation.
5. **The eight defects.** Each fix is small and has a regression test; the tests
   are the thing to check, because two of my first drafts were over-broad and
   would have condemned correct code (see §8).
6. **Whether defect 8's deadlock is real,** or whether some path resolves both
   constraints that I did not find.
7. **The winner join (§3.2 item 6).** The 0/34 rests on two alignments I
   verified myself: identical DK scoring (229 matched players, mean diff
   −0.024) and slate-universe overlap (295/306). The README warns the winner
   file has known quality issues (five salary totals over $50k; two sources
   agree on only 18/30 shared winning scores; one 2024 week duplicated, which
   the loader drops). Re-derive the per-slate winning line as the roster sum of
   `winner_actual` and confirm the 34-slate join keys before trusting the
   margin distribution.

---

## 8. My own errors this session, disclosed

Listed because a reviewer should weight my conclusions accordingly.

- **Attribution:** `git add HANDOFF.md` swept ~107 lines of production's
  uncommitted in-flight work into my commit `04f60c1d`. Content preserved,
  attribution wrong, already pushed so not rewritten.
- **A driver that misread failure as success.** `gcloud --format="value(a,b,c)"`
  emits empty fields for absent counters; `read -r s f c` shifted positionally, so
  a failed execution (succeeded absent, failed=1) printed "succeeded=1". It would
  have advanced a chain on a failed predecessor. The controller's fail-closed gate
  caught what my driver missed. Both drivers now parse JSON explicitly.
- **A wrong fix pushed to main.** I added `--parallelism` to
  `gcloud run jobs execute`; that flag does not exist. Corrected in `f5d03d56`.
- **I modified a file the frozen chain declares immutable** (`b8f6235f`,
  `REPLAY_HEAD_STABLE_PATHS[10]`), then reverted (`b5ac2c0f`).
- **I over-reverted** — my first revert of `panel_transport.py` would also have
  undone an unrelated `OUTPUT_PREFIX` v1→v2 bump from `501b68a4`.
- **Two regression tests were initially over-broad** and would have flagged
  correct code (the `task_count` conditional; jq calls with real input files).
  Both narrowed after mutation-checking.
- **I nearly pulled 62 GB of discovery matrices to the workstation** to run a
  selector experiment, against the design (downstream workers derive their one
  matrix in-cloud) and unnecessary, since the frozen selector comparison already
  existed in the sealed shards. The operator caught this.
- **I fixed defect 4 point-wise and it resurfaced twice** before I swept the
  class, which is exactly what frozen-chain rule 4 warns about.
- **I nearly reported a ~37-point anchoring error that does not exist.** Seeing
  real Milly winning lines average ~232 against the program's 194 tail line, I
  drafted the conclusion that the headline metric was mis-anchored. Reading the
  ledger first showed 194 is deliberately the *minimum* 2025 winning line and 237
  the average — a known, chosen floor, not a mistake. My own winner data then
  confirmed it (2025 min = 193.9). The lesson is the one CLAUDE.md already
  states: read the ledger before proposing, because most "new" findings are
  already there.

---

## 9. Provenance for re-derivation

```
PREREG-086 seal      fdec2593ef36f5df15278725bfad4dd996dc3e97d6594f62673919287a494212
                     48,278,965 bytes, 72/72 cells
r2 shards (local)    /home/erich/projects/.nfl2-worktrees/r2shards  (72 files, 96 MB)
realized panel       /home/erich/.cache/nfl2/v1/panel107/snap_pitclean_k1/000000000000.parquet
efficacy script      /home/erich/086_efficacy_read.py
efficacy output      /home/erich/086_efficacy_result.txt

discovery matrix terminal (reopen-verified)
  gs://nfl-predictions-503414-corpus-retrieval/research/
    corpus-r6-paid-source-discovery-matrices/exp5-discovery-matrix-20260911e/terminal.json
  200,367 B  sha256 23184230bef178aeab0dbb66a16aa6b68fe4adb1a6ce12575caed7e7a7ca278d
reopen proof  .../reopen-terminal.json  58,781 B  sha256 7ca3351da6aa46494054…

capture-plan lock (committed, unpublished)
  reports/corpus-r6-matchup-runs/20260830-r6-matchup-source-v2/
    capture-plan-outer-candidate-authority-v3-lock.json   106,016 B   commit 305fc6c6

branches
  production/test-lanes-and-factorial-drift-20260911   (reports, lanes, HANDOFF)
  production/seven-pack-repository-root-code-binding-20260911
  lab/lab-notes-running-20260910                       (nfl2, Updates 337-388)
```

Cloud Run job quota in `us-central1` sits at **1000/1000**. Every execution this
session reused the pinned job `atlas-cbc-32g-full-2023-w8-v1`
(UID `1f4bcf0a-2300-4afa-9fc1-9981844c8275`); nothing created a job. Freeing
quota by deleting jobs erases their execution history and is operator-only.
