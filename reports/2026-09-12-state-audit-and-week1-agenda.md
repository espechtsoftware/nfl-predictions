# State audit and agenda — 2026-09-12 (day before Week 1)

**Author:** Claude (Fable 5.1), fresh session, read-only audit. No cloud
execution, publication, policy, or repository mutation was performed; this
file is the only write.
**Inputs read:** `reports/2026-09-12-independent-review-package.md`; both
HANDOFF lineages (this checkout's and `origin/main`'s — they differ, see §1);
the lab action note through Update 388; `nfl2/LEDGER.md`; the lab synthesis,
priority, knowledge-frontier, selection-gap and corpus-population reports; the
2026-09-10 Neo4j/FP/SIS review; ledger addenda 96–120; live Cloud Scheduler,
Cloud Run, Cloud Build, GCS, BigQuery and systemd state; the running Neo4j.

**Operator goal restated:** each week, at least one of the ~90 entered
lineups scores in the 220–230 range. Averages do not matter.

---

## 0. The three things that matter most

1. **Tomorrow's money path is built but stale, and its publisher is not on
   `main`.** The four Week-1 books (P_MIX paid, P_CTRL fallback, D400_DEMAX
   and D800_WEMAX shadows) were published 2026-09-10T23:15Z from a salary
   pull with **zero** injury designations. The warehouse now holds **13 Out and
   8 Questionable** for Week 1 (pulled 2026-09-12T10:03Z). The books must be
   rebuilt Sunday morning, and the script that builds/publishes them
   (`scripts/publish_week1_a5_books.py`, commit `2fc45328`, record
   `30c87d6c`) lives only on
   `origin/production/nflverse-current-snap-absence-20260910` (and the
   jsonpayload-collector branch) — **not on `origin/main`** and not in this
   checkout. Nobody but the now-exhausted production agent has run it.
   §3 gives the procedure and a Saturday dry-run recommendation.

2. **The 220–230 target is, on every measurement we have, a SUPPLY problem
   first.** Across the sealed 72-slate lab cohort the entire 800-candidate
   pool contains a 220+ lineup on **2 of 72** slates (6/72 under the
   completion treatment) and a 230+ lineup on 1–2 of 72. Production's R6
   corpus (54 slates, 199k candidates): 230+ supply on 3/54. A perfect
   selector would therefore put a 220+ lineup in the book in well under 10% of
   weeks. Below ~210 the constraint is retrieval (pool has a 194+ lineup on
   35/72 slates; K20 finds 8, K80 finds 17); above ~220 the candidates do not
   exist. Every selector/ranker/retention experiment of the last three weeks
   measured an empty set at the line the operator cares about. The agenda in
   §5 is therefore supply-first, with prospective grading as the adoption
   authority.

3. **Repository state is fragmented and one careless merge would lose work.**
   This checkout's branch is 23 commits ahead of and **487 behind**
   `origin/main`; relative to `main` it deletes 59,825 lines (incl. the Week-1
   live-pair adapter tests). Its four reports and `scripts/test_lanes.sh` are
   not upstream. Production's last science direction ("prioritize
   belief-gated lineup completion", `37298ff2`) and the Neo4j review are also
   off-`main`. There are 110+ worktrees, 60+ prunable, and Cloud Run sits at
   1000/1000 jobs. §1 and §5.0 list the reconciliation steps.

---

## 1. Where the two teams actually left off

### 1.1 Timeline of the handover (reconstructed)

| When (CT) | Who | What |
|---|---|---|
| 09-10 07:00–18:00 | Production (Codex) | Week-1 identity preflight repaired; generation-shadow suite run four times (`vx76b`, `j5qzl`, `28wzf` failed on real contract defects; **`8mz64` succeeded** 18:22Z, safety receipt PASS); repaired D800/D400 live pair on nfl2 `fa5d035`; A5 materializer + publisher written and preflighted (42/42). |
| 09-10 18:15 | Production | **Published the four books** (`a5-books/20260910t2315z-fa5d035/`, terminal gen `1789080700983712`). `entry_allocation_published=false`, `contest_entries_submitted=false`, `bankroll_recommendation_made=false`. Recorded in `30c87d6c` (branch only). |
| 09-10 evening – 09-11 05:30 | Production | R6 prefix-ranking audit (`9c283ac0`), "refocus Neo4j on scoring gains" (`98d046aa`), "prioritize belief-gated completion" (`37298ff2`), seven-pack v1→v4 (v4 sealed), capture-plan freeze attempts 1–3, PREREG-086 r2 launched. |
| 09-11 ~09:00 | Production | Last action: repair `e9915372`, launched `nfl-week1-capture-plan-freeze-v3.service` (failed at the next gate). Account exhausted. |
| 09-11 09:30 → 09-12 07:56 | Lab agent acting as production (Claude) | Found and fixed defects 1–7 in the capture-plan / discovery-matrix / source-v3 chains; ran PREREG-086 efficacy read (**NO_NOMINATION**); measured three levers on realized scores; wrote the review package. Worked on a branch based at 09-03 `cf0ab928`, so its HANDOFF lacks production's Sep 3–11 entries. Pushed seven code commits straight to `origin/main`. |

**Did the lab team find where production left off?** Mostly, but not for the
money path. The review package correctly tracks the frozen research chains and
verifies the Week-1 *cadence* (schedulers, models). It does not mention the
A5 four-book publication, the P_MIX paid policy, the generation-shadow suite
success, the 90 DK reservations, or that all of these live on unmerged
branches. That is the gap this audit closes.

### 1.2 Repository state

**Production (`nfl-predictions`)**

- `origin/main` = `b5ac2c0f` (09-12 07:38). Authoritative HANDOFF is
  `origin/main:HANDOFF.md`, **newest sections at the top** under "Current
  science index"; this checkout's HANDOFF is stale from 09-03 with the
  Claude-session sections appended at the bottom.
- This checkout: `production/test-lanes-and-factorial-drift-20260911` at
  `1356eec7`; merge-base `cf0ab928`; 23 ahead / 487 behind. Unique valuable
  content: `scripts/test_lanes.sh`, `reports/2026-09-11-frozen-factorial-policy-drift.md`,
  `reports/2026-09-11-failing-test-inventory.md`,
  `reports/2026-09-12-retrieval-lever-measured-on-realized-scores.md`,
  `reports/2026-09-12-independent-review-package.md`, the CLAUDE.md
  `N_BOOM` correction, HANDOFF appendices. **Must be cherry-picked, never
  merged.**
- Off-`main` production branches carrying live-path code:
  `origin/production/nflverse-current-snap-absence-20260910` (tip `00c6097f`:
  publisher `2fc45328`, publication record `30c87d6c`, R6 audit, completion
  refocus, snap-count repair) and `origin/production/generation-shadow-jsonpayload-collector-20260910`.
- Untracked here: 20 reports dated 08-27…09-10 (the Neo4j review, the 076
  and 073 reviews, the selection-gap review — at least three are on no
  branch); the 09-01 Neo4j scratch dir; `.worktrees/`.
- Uncommitted diffs here (dated Aug 23–29): `scripts/cloud_core_v1_score_chain.sh`
  (+591, `--recover-failed-stage`), `run_recourse_aware_initial_single_job_transport.py`,
  foundry env files, README deficiency row (2026-09-05 $200-salary row). None
  is upstream. Treat as parked in-flight work; do not commit blind.

**Lab (`nfl2`)**

- Live lineage: `origin/lab/lab-notes-running-20260910` (Update 388; 73
  ahead of `origin/main`). `origin/main` = `49ee33a` (09-10).
- The clone production used for the live pair:
  `/home/erich/projects/nfl2-week1-a5-sidecars-current-20260910` at `fa5d035`,
  clean, holding runs `20260910T123108360022Z-fa5d035` (D800: lev 160 /
  boom 640, 10,000 sims, K=1, dual_emax, 80 entries + WEMAX sidecar) and
  `20260910T123841482022Z-fa5d035` (D400: lev 80 / boom 320).
- `results/live/2026-w01` in the main nfl2 checkout has only the 08-29…09-01
  shakedowns; the operative runs are in the clone above.

### 1.3 What is running / live right now

- **Cadence: healthy.** All production schedulers ENABLED and green:
  `s-nflverse` 05:00 CT daily, `s-features-sun` 05:30–10:30 CT hourly,
  `s-project-su` 06:00–11:00 CT hourly, `s-contests-sun`, `s-us-dfs-sun`,
  `s-dk` hourly, `s-props`, `s-odds`, `s-weather`, `s-freshness`, `s-backup`.
  `train-weekly` succeeded 09-08; `project-slate` succeeded 09-08 (the 09-06
  Sunday 4/7 failures were a scheduler-reconfiguration artifact). Research
  shadow schedulers (`s-shadow-*`, `s-train-k1*`, `s-freeze-tail-*`,
  `s-tabpfn-sis-*`) are PAUSED — correct.
- **Research: nothing running.** Today's three `atlas-cbc-32g-full-2023-w8-v1`
  executions (10:57, 11:49, 12:13Z) are the source-v3 worker failing on
  defect 8 (protocol deadlock) — expected. Lab project idle since 09-11
  10:20Z. Cloud Run `us-central1` jobs: **1000/1000**.
- **Host:** four read-only systemd monitors running (cloud-build,
  cloud-run-lane, lab-action-note, lab-repo-transition);
  `nfl-week1-capture-plan-freeze-v3.service` transient unit failed (research
  chain, not money path). Codex VS Code process still alive but its account is
  spent. Neo4j docker `nfl-kg-local-smoke` up on localhost (auth none).
- **Neo4j contents:** PREREG-083 graph (12,960 rosters, 14,400 candidate
  occurrences, 72 selected books, 675 players, 37 slates) + the E0 historical
  slice (4,258 entities) + a knowledge registry (80 experiments, 48
  preregistrations, 12 claims, 13 questions). It is an index; the sealed
  JSON/NPZ/parquet artifacts remain authoritative.

---

## 2. Science state, read against the operator's goal

### 2.1 The numbers that bound what is possible today

| Quantity | Value | Source |
|---|---|---|
| Milly winner median (2023–25), mean book-to-winner gap | 234; −55 | objective-change notice; 0/93 books beat a matched winner |
| Pool oracle (best of 800 candidates), mean | 194.3 | PREREG-086 r2, 72 slates |
| Book max K20 / K80 (D800, incumbent law), mean | 168.0 / 181.5 | same |
| Slates where the **pool** holds ≥194 / ≥210 / ≥220 / ≥230 | 35 / 14 / **2** / **1** of 72 | same |
| Slates where **K80** holds ≥194 / ≥210 / ≥220 | 17 / 5 / 1 of 72 | same |
| K20 → K80 (60 more entries) | **+13.55** [10.6, 16.7] | only positive interval measured |
| Selector law swap (incumbent vs corrected hsim) | −0.29 [−4.7, +4.3] | zero |
| Minimal-core completion (086) | +0.57 pool oracle; 220+ supply 2→6/72 | NO_NOMINATION on its frozen gate |
| Ranker lift vs random, K20 / K80 | 3.3× / 1.9× (p≈0.01) | real but thin |
| R6 corpus (54 slates): 200+ / 230+ supply | 29/54 / **3/54** | 09-10 prefix audit |
| R6: eligible 220+ lineups captured by any final book | 4 of 34 | E0 graph |
| 083 direct-tail generator: expected 220+ / 230+ exceedances | 2.15→3.35 / 0.66→1.11 (ratio rises with threshold) | mechanics gate; realized: supplied two 220+ lineups, K80 took neither |
| corr(simulated p194, realized) | ≈0.15 | lab |

**Reading:** a 220+ candidate exists in the pool roughly one week in fifteen;
a 230+ roughly one in forty. The book contains one about half as often. The
goal of "≥1 of 90 at 220–230 every week" is not reachable by any selection
change; it needs the generator to produce winner-range lineups it does not
produce today, and then a book that will take them. The realistic near-term
objective is to raise P(pool holds 220+) from ~5% toward 20–30% and keep
book capture near half of that — i.e. from ~1 week/season to ~4–6.

### 2.2 What is closed (do not re-run on the historical panel)

Selection objective (WEMAX vs DEMAX flat); selector law swap; scheduler
(079/083); bank breadth (078); admission/compression (058/063); belief scaling
and retention sleeves (088, STRUCT harmful); dependence-law repairs (089
ECC/min-KL, 090 regime overlay); one-player completion (066); minimal-core
completion at its frozen mean gate (086); PREREG-082 breakout reranker R4
(fitted model anti-tail); PREREG-084 direct-tail read (no nomination — but
its utility floors *passed* in 2025, +3.65 raw at K20; only the interval
failed, and its breakout route was unmeasurable on a fold whose control never
reached 200); 076 union-EMAX; production's Gumbel family, GFlowNet, Schaake,
TD coupling, CE, cap-4, EPI, fast-role. Candidate-budget doubling at the old
selector damaged the selected extreme tail (Addendum 117) — but that was
under coverage-194, before DUAL_EMAX/D800.

### 2.3 What is adopted or live-eligible

D800_DEMAX (dose +1.2), DUAL_EMAX (+1.4 K80), **P_MIX** participation
mixture (+1.4 raw, proxy pass, all banks/LOSO) = tomorrow's paid policy.
Shadows: P_CTRL, D400_DEMAX, D800_WEMAX, and the five generation-shadow arms
(incumbent-160-40, boom-first-40-160, cross-law-40-100-60, boom-dose-40-360,
ceiling-all-boom-0-200) frozen pre-lock in `8mz64`. PG_AWARE+P_MIX
(unreplicated). No-bring-back tail sleeve (live-eligible at D400, absorbed at
D800).

### 2.4 Open and genuinely promising for the tail

- **Direct-tail generation (083 mechanism):** the only arm whose supply ratio
  rises monotonically with threshold. Its read failed only because the
  incumbent selector discarded the 220+ lineups it supplied.
- **Belief-gated / minimal-core completion:** 3× the 220+ supply at zero
  mean cost; gate was mis-sited on the mean.
- **Column-generation pricing pass (lab M1)** and **scenario reduction
  (S1)**: never tried; M1 is the first mechanism that lets selection tell
  generation what it is missing, priced against held-out worlds (which is what
  CE lacked).
- **Discriminator, not ranker:** bar = double K80 retrieval (19%→40%).
  PREREG-085 (set-aware, served mean/q90/q99/multimetric) is built; its only
  clean evaluation cohort is prospective.
- **Unique entries:** the largest measured lever. The A5 allocation enters
  **57 unique lineups** (the 20/3/10 are duplicates of the top ranks). For a
  max-functional, 90 unique shots beat 57 unique + 33 duplicated shots.

### 2.5 Neo4j — was it fully used?

Used well as a lineage/diagnostic index: it produced the two findings the
program now runs on (241/279 high scorers absent from every final book;
supply-vs-selection split with the treatment's two 220+ lineups unselected)
and the structural profile of missed high scorers (fewer QB teammates,
flatter, more games). Not used for: paid-source attribution (FP/SIS never
attached), per-player realized contribution, portable player traits, live
attribution. Both the 09-10 review and production's own 09-10 note conclude:
keep it as an index, add the stage-influence sidecar when the ablation runs,
do not enlarge the graph. One cheap unexploited use is in §5.2.

---

## 3. Week 1 — exact state and Sunday procedure

### 3.1 Allocation (A5), fixed and reserved

| Contest | ID | Entries | Fee | Field | Book prefix |
|---|---|---:|---:|---:|---|
| NFL $3.5M Millionaire [$1M to 1st] | 193028206 | 57 | $5 | 832,342 | P_MIX ranks 1–57 |
| NFL $400K Play-Action [20 max] | 193028208 | 20 | $3 | 158,541 | ranks 1–20 |
| FFWC Qualifier #6 | 194478066 | 3 | $18 | 5,000 | ranks 1–3 |
| FFWC Qualifier #5 | 194478065 | 10 | $5 | 17,835 | ranks 1–10 |

Draft group `151307`, lock **2026-09-13T17:00Z = 12:00 CT**. Total 90
entries / $449. 90 reservations exist on DK (authenticated lineups-API capture
09-09) — all currently holding **one shared placeholder lineup**
(`final_entry_roster_acceptance_authority=false`).

### 3.2 What exists vs what is missing

Exists: repaired live pair (nfl2 `fa5d035`), adapter-validated, four K80
books + salary catalog + player bridge + participation package published and
independently reopened; generation-shadow suite `8mz64` frozen with safety
PASS; contest sources and lobby projection generation-pinned; FP live
matchups sealed (prior-season regime; not consumed by the book).

Missing / stale: (a) books built with 0 designations — now 13 Out, 8 Q;
(b) allocation authority v2, four manifests, accepted-entry capture — the
governed chain is on HOLD by its own contract ("no end-to-end A5 publisher;
do not manually stitch JSON"); (c) bankroll decision recorded as not made;
(d) the publisher is not on `main`.

### 3.3 Recommended procedure

**Today (Saturday) — full dry run, then upload a real placeholder book.**

1. In `/home/erich/projects/nfl2-week1-a5-sidecars-current-20260910` (clean,
   `fa5d035`), with the production venv/ADC:
   `python scripts/live_week.py --season 2026 --week 1 --group 151307 --selector dual_emax --lev 160 --boom 640 --sims 10000 --k 1 --seed 2026 --entries 80 --emit-a5-sidecars`
   then the same with `--lev 80 --boom 320` (no sidecars) for D400. Expect
   ~5 min and ~2 min. Check the receipt: `injury_out` > 0 now, Out players
   absent from `frame.parquet`, 80 unique legal entries, `dk_violations 0`.
2. From a clean detached checkout of production `2fc45328` (or the branch tip
   `00c6097f`): `python scripts/publish_week1_a5_books.py --paid-run-dir <D800 dir> --shadow-run-dir <D400 dir> --nfl2-source-root <nfl2 clone> --run-id 20260912t<hhmm>z-fa5d035 --code-sha <sha>` **without** `--execute` first. It reads
   the live DK status snapshot and prices Q/D via P_MIX. Confirm P_MIX turns
   over members relative to P_CTRL (it did 16/80 on 09-10 with 24 designations).
3. Produce the DK upload CSV for the P_MIX book (draftable IDs via the
   published player bridge; `book.csv` from `live_week.py` is already
   DK-importable and equals P_CTRL). If no CSV emitter exists for P_MIX, the
   fallback is to upload P_CTRL (= D800_DEMAX `book.csv`) — the adopted
   selector without the participation adjustment.
4. Upload to DK today so the 90 entries hold a real book, then re-run
   tomorrow. DK permits edits until lock.

**Sunday.** 05:00 `s-nflverse`; 05:30+ `s-features-sun`; 06:00+
`s-project-su` (production app path — also the last-resort fallback via the
app's DK CSV export, greedy-tail-coverage 40/160). ~09:30 CT rebuild D800/D400,
publish (`--execute`), upload by ~11:15 CT. Watch the tightest coupling:
projections at :00 depend on features from :30.

**Monday/Tuesday (load-bearing, unrecoverable after ~4 days).** Download all
four contests' standings + Entry History in a logged-in browser; run
`scripts/rehearse_week1_contest_capture.py` against the real manifest, then
`capture-dk-standings --confirm-settled --confirm-full-field --apply`. Settle
every frozen book and all five generation-shadow arms and the full candidate
corpus (`scripts/settle_live.py`). This is the first real field/ownership data
the program has ever had, and the first prospective grade of P_MIX vs P_CTRL,
D800 vs D400, and the five generator arms.

### 3.4 Decision the operator should make before lock

**Unique entries.** The science says more *unique* lineups is the only lever
with a positive interval, and the goal is a weekly max. Entering ranks 1–20
again in Play-Action and 1–10/1–3 in the qualifiers buys payout exposure on
the same lineups, not tail shots. Within the same $449, using ranks 58–77 for
Play-Action and 78–80 + shadow rows for the qualifiers gives 90 unique
lineups. This is a payout-structure/ROI choice, not a model change; it should
be frozen in the manifest before lock either way. (Lab's 09-02 A5 note
already argued for Milly-weighted allocation for the same reason.)

---

## 4. Risks (ranked)

1. **Sunday chain has a single-operator history and lives off-`main`.** A
   dry run today removes most of this. Fallbacks in order: P_MIX → P_CTRL
   (`book.csv`) → production app export.
2. **Repository divergence.** A merge of this branch into `main` would delete
   the Week-1 adapter tests and 59k lines; cherry-pick only. Production's
   publisher branch must be merged (fast-forward-checked) after Week 1.
3. **No independent check.** The same agent produced and reviewed the
   09-11/12 work (disclosed in the review package). Re-establish a reviewer
   lane on Monday (Sol/Gemini rounds worked before; the ledger's
   audit-before-verdict law came from them).
4. **Cloud Run 1000/1000.** Any new chain must reuse a job; the
   `generation-shadow-suite` job now occupies the freed slot.
5. **Frozen-chain deadlock (source-v3 defect 8) and factorial drift** are
   research-only; neither blocks Week 1. Both need an operator protocol
   decision, not code.

---

## 5. Agenda

### 5.0 Housekeeping (this weekend, low effort, prevents loss)

- Cherry-pick the doc/tooling commits from this branch onto a fresh branch
  off `origin/main` (reports, `test_lanes.sh`, CLAUDE.md `N_BOOM`
  correction, HANDOFF appendices as a new top section); do not merge.
- Commit the untracked reports (Neo4j review, 076/073/selection-gap reviews)
  from the 09-10 checkout to `main`.
- After Week 1: fast-forward/merge
  `production/nflverse-current-snap-absence-20260910` (publisher + R6 audit +
  completion refocus) into `main`; prune the ~60 `/tmp` worktrees
  (`git worktree prune`) and the finished 09-08..09-10 review worktrees.
- Add one HANDOFF section on `origin/main` naming the money-path commits and
  this report, so the next agent does not repeat today's archaeology.

### 5.1 Prospective grading — the only adoption authority (every week, free)

Freeze before lock; settle after: P_MIX, P_CTRL, D400_DEMAX, D800_WEMAX, the
five generator arms, the full 800-candidate corpus, and the Milly winning
score. Maintain a **tail ledger**: per week — pool max, book max, winner
score, rank of the pool max in the book, count of pool/book lineups ≥200/210/
220/230. With 17 slates and a ~5% base rate at 220, no single arm will reach
significance at 220 this season; the honest weekly KPIs are 200+/210+ supply
and pool-oracle, with 220+/230+ counted and reported, never gated.

### 5.2 Supply at 220+ (P0 science — the only path to the stated goal)

All as **prospective shadow arms** added to the weekly generation-shadow
suite (no new historical reads; gates frozen now, before Week-1 outcomes):

1. **Direct-tail generation (083 mechanism) as a generator arm**, plus a
   preregistered fixed-size sleeve (8–12 of the 57 Milly slots) that admits
   its candidates to the paid book. Rationale: it is the only arm whose tail
   ratio rises with threshold, and its read failed at selection, not supply.
   The 088 "sleeves are null/harmful" result was about retention from the
   same pool; this sleeve carries *new* candidates.
2. **Belief-gated / minimal-core completion as a shadow arm** with the gate
   re-sited on 220+ supply *count* after an outcome-blind support census
   (preflight rule). Not a re-read of 086 (that would be panel mining).
3. **One column-generation pricing iteration (lab M1)**: build the book, price
   worlds where it is weak on a held-out bank, solve for lineups with maximum
   positive reduced value, add them. Genuinely new; composes with everything.
4. **Scenario reduction for solve worlds (S1)** co-run against total-order
   scheduling at equal budget — attacks the ~31-effective-rank redundancy at
   the source.
5. **Neo4j, cheaply:** a phenotype census of the extreme tail (R6's 34
   eligible 220+ lineups, 083's supplied 220+ pairs) vs their nearest selected
   neighbours — QB-teammate count, game spread, salary shape, leverage share,
   ownership — used only to *design* arm constraints for (1)–(4), graded
   prospectively. Hypothesis generation from opened panels is allowed;
   tuning on them is not.

### 5.3 Discriminator (P1 — matters below 210, where entries also help)

- PREREG-085 (set-aware selector; served mean/q90/q99/multimetric) as a
  prospective shadow with prefix recall, candidate-oracle loss and NDCG.
- KG-5 candidate-level features never tried: coverage/matchup grades,
  tracking traits, prop-ladder shape, projected duplication — walk-forward,
  bar = K80 retrieval 19%→40% on shadow weeks before any chain is built.

### 5.4 Deprioritise / park

- **FP/SIS 2×2 retrieval ablation**: blocked by the source-v3 deadlock (an
  operator decision to re-establish the fixed-G0 lineage) and aimed at
  retrieval, which is not the binding constraint above 210. Park until a
  cheaper "does paid data improve the world model" design exists (player-level
  tail proper scores on 2026 weeks, walk-forward).
- **Extreme-tail factorial drift**: choose option 2 (pin the frozen
  environment as a constant) when convenient; no Week-1 impact.
- **Larger Neo4j / React observatory**: no.

### 5.5 Contest structure (operator, this week)

- Decide unique-vs-duplicated entries (§3.4) and record it in the manifest.
- After Week 1 standings land: first measured field size, ownership and
  duplication — the inputs the FIELD_WIN objective and late-swap work have
  been waiting on since August.

---

## 6. Provenance

```
production origin/main                b5ac2c0f (2026-09-12 07:38 CT)
this checkout                         production/test-lanes-and-factorial-drift-20260911 @ 1356eec7, base cf0ab928
publisher commit / record             2fc45328 / 30c87d6c on origin/production/nflverse-current-snap-absence-20260910 (tip 00c6097f)
A5 books terminal                     gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/a5-books/20260910t2315z-fa5d035/terminal.json
                                      gen 1789080700983712, semantic 55c14171…e57b, paid=P_MIX fallback=P_CTRL
generation-shadow suite               generation-shadow-suite-8mz64 (succeeded 2026-09-10T18:22Z), envelope self-hash 5c02e70b…27c96
live pair runs (nfl2 fa5d035)         /home/erich/projects/nfl2-week1-a5-sidecars-current-20260910/results/live/2026-w01/
                                      20260910T123108360022Z-fa5d035 (D800) · 20260910T123841482022Z-fa5d035 (D400)
DK reservations                       reports/2026-09-09-week1-draftkings-lineups-api-a5-reservation.json (90 entries, 57/20/3/10)
Week-1 injuries in warehouse          nfl_raw.injury_snapshots 2026 w1: Out 13, Questionable 8 (pulled 2026-09-12T10:03Z)
lab live lineage                      nfl2 origin/lab/lab-notes-running-20260910 (Update 388)
PREREG-086 seal / result              fdec2593…4212 / NO_NOMINATION
Neo4j                                 docker nfl-kg-local-smoke, bolt://127.0.0.1:7687, auth none
Cloud Run us-central1 jobs            1000/1000
```
