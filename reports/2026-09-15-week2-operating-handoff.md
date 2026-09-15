# Week-2 operating handoff (written 2026-09-15 15:00Z, Tuesday) — read this first

This is the take-over document for whoever operates the project this week. It is written so that another model can
run the week without the operator having to re-explain anything. It complements, and where they disagree supersedes,
`HANDOFF.md` (the chronological log) and `reports/2026-09-14-project-briefing-for-a-new-model.md` (the background
and the science). Times are UTC unless marked CT (Central, UTC−5). Week 2's Sunday main slate is **2026-09-20**,
lock 12:00 CT (17:00Z).

Sections: 0 ground rules · 1 where everything is · 2 what is running right now · 3 the week, day by day ·
4 the Sunday money path in full · 5 Monday/Tuesday settlement · 6 lab cohort operations (nfl2) · 7 production
Cloud Build / Cloud Run operations · 8 the direct paid-source runner · 9 open defects and their status · 10 file index.

---

## 0. Ground rules (each one cost real money or a day when broken)

1. **Never enter an untested rule on an entered book.** Week 1: a "proven-scorer" filter offered without a 72-slate
   test cost the week (196 vs a held 226.64). Test on the 72 historical books first (`tools/exposure_cap_book.py`
   shape), then decide.
2. **Scratch protocol.** Remove a player from entered lineups only when DraftKings marks him OUT/IR or the official
   inactives name him. Answer "replace X" with his live DK status first. Week 1: inactive removals +124 points,
   removing active Wicks −44. Cap exposure instead of removing when unsure.
3. **Never select on raw expected payout** (a 1-in-10,000 event decides it). P(top-N) selectors are the estimable form.
4. **Never commit DraftKings entry keys, cookies, or the operator's entries export.** `DKEntries*.csv`, the entry
   history export and the standings zips stay under `/home/erich/week1-sunday/ENTERED/` and
   `/home/erich/projects/nfl-predictions/results/2026-09-13/` (local only). Roster-only candidates may be committed.
5. **Point-in-time is sacred; never weaken a leakage check.** `build-features` must pass its leakage checks.
6. **The harness classifier refuses some commands.** Known refusals: any push to `main`; create-once publishes
   (`publish_week1_a5_books.py --execute`); `gcloud run jobs execute` on the production project; `git rm` of tracked
   evidence; systemd unit writes; some greps. Do not retry or route around: print the exact one-line command for the
   operator and continue with everything else. (Lab-project job updates/executions through the registered launcher
   scripts have been allowed.)
7. **Lab lanes.** Reuse `lab-run` / `lab-run-slow`; never create jobs (JobsPerProject quota is full); ≤ 2 non-terminal
   executions across both lanes; every launcher goes through `scripts/launcher_registry.sh run` (single-writer lane);
   `CODE_SHA == HEAD` of a pushed, clean cohort branch; never commit to a cohort branch while its launcher is armed.
8. **Before arming efficacy banks run BOTH local smokes:** `--mechanics-only --smoke` and the plain `--smoke`
   (full path, `NFL2_UPLOAD=0`). The mechanics smoke cannot reach the outcome path (2026-09-15: three banks × 53
   tasks lost to a one-line outcome bug). Also run any sampler/fill loop once at production size.
9. **Compare receipts by content** (sha256/bytes/uri), never by representation; never pin a script's own hash in a
   manifest it validates; when a fail-closed gate trips, sweep the whole defect class before rebuilding.
10. **The operator retains protocol and bankroll decisions**: contest mix, entry counts, dose, adopting any selector.
    Present the measured case; do not decide for him.

---

## 1. Where everything is

| what | path / id |
|---|---|
| Production repo (GCP `nfl-predictions-503414`, us-central1) | `/home/erich/projects/nfl-predictions` — **the checkout is dirty and 449+ commits behind; do not work in it. Use worktrees.** |
| Production `main` | `a0eb8da1` (Commit B: producer fix + new capture-plan lock). Pushes to `main` need the operator. |
| Production audit/report branch (this document, HANDOFF, Week-1 reports, Sunday scripts) | worktree `/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912`, branch `production/week1-audit-adjust-20260912` |
| Production direct-runner branch | worktree `/home/erich/projects/.nfl-predictions-worktrees/source-v3-same-path-20260914` (has its own `.venv`), branch `production/paid-source-ladder-direct-20260915` (off `main`) |
| Lab repo (GCP `nfl-2-506823`; jobs `lab-run`, `lab-run-slow`; results `gs://nfl-2-506823-lab/results/<exp>/<RUN_ID>/result-tNN.json`) | `/home/erich/projects/nfl2` (do not work in it; worktrees under `/home/erich/projects/.nfl2-worktrees/`) |
| Lab cohort worktrees | `prereg098-finish-20260914` (branch `lab/prereg098-finish-objective-20260914`), `prereg097-dose6400-20260913`, `prereg096-fast-20260913`, `prereg090-amend4`, `week1-live-center-e7255e9` (the Week-1 money path, commit e7255e9), `live-center-production-20260912` (repair launcher root) |
| Launcher registry state | `/home/erich/.local/state/nfl-dfs/lab-launcher-registry/` (`launcher-registry.log`, `launchers/*.json`, `adjudicated-launcher-receipts/`) |
| Host working dir (untracked) | `/home/erich/week1-sunday/` — `tools/` (Sunday tooling), `ENTER/`, `ENTERED/` (never commit), `payout/`, `direct_runner/`, launcher/repair scripts, logs |
| Python | production: `/home/erich/projects/nfl-predictions/.venv/bin/python` (editable install of the MAIN checkout — pass `PYTHONPATH=<worktree>/src` or use a worktree's own `.venv`); lab: `/home/erich/projects/nfl2/.venv/bin/python` with `PYTHONPATH=<worktree>/src` |
| Warehouse | BigQuery `nfl_raw`, `nfl_features`, `nfl_predictions` in `nfl-predictions-503414` |
| App | Cloud Run service `nfl-dfs-app` (IAP), reads the warehouse live; not on the money path |
| Memory (assistant) | `/home/erich/.claude/projects/-home-erich-projects-nfl-predictions/memory/` |

---

## 2. What is running right now (2026-09-15 15:00Z)

- **PREREG-098 r2 — DONE 15:26Z, read 15:35Z: decisively NEGATIVE (finish objective closed at its tested form; no shadow book for Week 2). LEDGER row and transcript on the 098 branch; briefing §7 updated.** (Original launch note kept for the record:) Launcher `queue_118.sh` armed 14:23Z through the registry from the 098
  worktree on image `prereg09s-a8ec05612ffa` (`results/prereg09s_image.txt` there). Order: `118m980r2` mechanics
  (1 task) → `scripts/prereg098_mechanics_gate.py <run id>` must PASS → banks `118b980r2` / `118b981r2` (53 tasks each,
  both lanes) → `118b982r2` when a lane frees. Log: `results/queue_118_launcher.log`. When it prints
  "all three banks terminal": `cd <098 worktree> && PYTHONPATH=src /home/erich/projects/nfl2/.venv/bin/python
  scripts/prereg098_report.py <RUN980> <RUN981> <RUN982>` (run ids from `results/queue_118_launches.log`), paste the
  verbatim output into the lab `LEDGER.md` as the PREREG-098 row (commit on the 098 branch AFTER the launcher has
  exited), then update briefing §7. Consequences are frozen in `PREREG-098.md`: a PASS nominates the finish objective
  for Week 2 **as a shadow book only** (the live field needs projected ownership).
- **Direct paid-source runner (host).** Six workers (`/home/erich/week1-sunday/direct_runner/worker-[0-5].log`),
  results in `direct_runner/results/slate-NN-*.json` (26/54 at 14:20Z, ~41 min per slate per worker; ETA ~17:30Z).
  A background monitor reports when 54 exist. Then §8.
- **PREREG-097 (dose 6400) banks** finished: 970 = 65/72, 971 = 55/72, 972 = 72/72. Repairs pending (§6.4).
- **Source-v3 / FP×SIS immutable chain**: abandoned at defect 11 (§9); nothing running; main carries Commit B.
- Production cadence today (Tue): `build-features-sj96q` 11:30Z ✓, `train-weekly-bdrzh` 12:30Z ✓,
  `score-entries-wf897` 13:00Z ✓, `ingest-nflverse-28zq2` 10:00Z ✗ (FTN 2026 file 404, known; Week-1 weekly stats
  did land: 1,118 rows), `project-slate-x42x2` 14:30Z ✗ ("target-week roster eligibility receipt is stale or
  incomplete") — expected mid-week: there is no Week-2 DK pool until `ingest-dk` pulls it (s-dk runs hourly Wed–Sun)
  and `build-features` refreshes the eligibility receipt (Sunday 05:30 CT hourly). The alarm condition is a failed
  `project-slate` **after** Sunday 06:00 CT.
- Host systemd (user): monitors only (`nfl-cloud-run-lane-monitor`, `nfl-cloud-build-monitor`, `nfl-lab-*`,
  `nfl-production-monitor-heartbeat.timer`). **The Week-1 Sunday build timer no longer exists** (it was a one-shot);
  Week 2 needs a new one (§4.1).

---

## 3. The week, day by day

### Tuesday 09-15 (today)
- [x] Production Tuesday jobs verified (above). `ingest-nflverse` FTN 404: add tolerance (skip the missing
      `ftn_charting_2026.parquet`, keep the rest) — code change on a production branch; not urgent for Week 2.
- [ ] 098 r2 read + LEDGER row when terminal (§2).
- [ ] Direct runner read + report (§8).
- [ ] 097 repairs after 098 (§6.4), then `scripts/prereg097_report.py`, LEDGER row.

### Wednesday 09-16
- s-trends 11:00 CT, s-contests 10:00 CT (lobby/fills into `nfl_raw.dk_contest_fills`), s-dk hourly from now
  (`nfl_raw.dk_salaries` week=2). Check by afternoon:
  `bq query --use_legacy_sql=false "SELECT draft_group_id, MIN(game_start), MAX(game_start), COUNT(DISTINCT dk_player_id)
  FROM nfl_raw.dk_salaries WHERE season=2026 AND week=2 GROUP BY 1 ORDER BY 2"` → the **Sunday main draft group** is
  the one whose games span Sunday 12:00 CT through the late-afternoon window (Week 1: 151307). Record it.
- Operator decisions to collect this week: contest mix and entry counts (Week 1: Millionaire 57, Play-Action 20,
  FFWC Q 3 = 80 unique, fees $399; CLAUDE.md's standing memory says never < 15 per contest), stake level (his own
  read after Week 1: minimum stakes until a finish-objective result exists), whether a K90 nested build with 90
  reserved entries is wanted again.

### Thursday 09-17 / Friday 09-18
- Prepare the Week-2 Sunday script (§4.1) and rehearse it once end to end on Thursday's data with a rehearsal run id
  (it writes only under `/home/erich/week1-sunday/` and immutable run dirs; nothing is published).
- Practice-status exposure cap: test on the 72 historical books before it may touch a live book (rule 1).
- (098 was negative: no finish-objective shadow book for Week 2.)
- Weekly ETR CSV to `/market` if the operator supplies one (paid pass was Sep 8–9).

### Saturday 09-19
- `s-cfb-sat` runs (college; unrelated). Verify Sunday timer is armed (§4.1), Downloads-folder watcher path is
  correct, and that the operator has reserved his entries in DK with a placeholder lineup (§4.3).

### Sunday 09-20 (§4)
### Monday 09-21 / Tuesday 09-22 (§5)

---

## 4. The Sunday money path, in full

### 4.1 Arming the build (do on Thursday, verify Saturday)

The Week-1 driver is `/home/erich/week1-sunday-build.sh` (host-only, untracked — copy it into the audit
branch as `scripts/week1_sunday_build_host.sh` when you make the Week-2 version; the runbook it calls is tracked at
`scripts/week1_sunday_runbook.sh` on the audit branch). It is **hard-coded to Week 1**: `--week 1`, draft group
`151307`, run-dir season path `2026-w01`, run-tag suffix `e7255e9`, and the runbook's preflight asserts
`draft_group == "151307"` (`week1_sunday_runbook.sh:67`) and publishes under `gs://…/week1/prelock/2026-w01/…`.
Make a Week-2 copy (`/home/erich/week2-sunday-build.sh`, runbook `scripts/week2_sunday_runbook.sh`) with those five
things changed, keep the rest byte-identical, and rehearse it on Thursday.

The Week-1 timer was a one-shot user timer at 09:10 CT and has expired. Arm a new one (the classifier refuses systemd
writes; give the operator the line):
```
systemd-run --user --on-calendar="2026-09-20 09:10 America/Chicago" --unit nfl-week2-sunday-build \
  /home/erich/week2-sunday-build.sh
```
and a second one at 10:50 CT for the T-70 rebuild (`/home/erich/week1-sunday/t70_rebuild.sh` pattern, on the salary
pull made **after** the 10:30 CT inactives).

### 4.2 Timeline (CT)

| when | what | check |
|---|---|---|
| 05:30–10:30 hourly | `s-features-sun` → `build-features` (panel + eligibility receipt, leakage checks) | last execution succeeded; `nfl_features.player_week_training` has week 2 |
| 06:00–11:00 hourly | `s-contests-sun`, `ingest-dk` (salaries, DK statuses), `project-slate` | `nfl_predictions.player_projections` week 2, `generated_at` within the hour; `nfl_raw.dk_salaries` `pulled_at` within the hour |
| 09:10 | Sunday build: governed D800 paid (lev 160 / boom 640, K80) + D400 shadow, publisher **preflight**, K90 nested build, ordering shadows, market-move veto, vetting, composite, upload CSVs, `ENTER/` layout, `TODAY-30-LATEST.md` | ~7 min per build; run dirs under `<week1-live-center worktree>/results/live/2026-w02/<stamp>-<sha7>/`, `LATEST` marker |
| 10:30 | official inactives; DK statuses update within minutes | `watch_late_inactives.py` running |
| 10:50 | T-70 rebuild on the post-10:30 salary pull (Week 1 lesson: the 09:10 book cannot know who is inactive) | new run dir; `vetting.json` HARD tier empty |
| ~11:00 | operator step 4a: `publish_week1_a5_books.py … --execute` (create-once per run id; classifier refuses; print the line); 4b: emit P_MIX upload files | published receipts |
| 11:15 | operator uploads in the DK UI (§4.3) | `ENTERED/` export downloaded, filled, uploaded |
| 12:00 | lock | late-swap watcher keeps running for the afternoon window |
| afternoon | scratch swaps per rule 2 only (`watch_late_inactives.py` proposes: best-projected active same-position player within salary, stack bonus) | |

Every build writes an immutable run dir (`book.csv` in DK slot order with dk_player_id, `book.json`,
`candidates.parquet` — the whole pool with tags and sim stats, `frame.parquet`, `incumbent_player_scores.npy` and
`corrected_hsim_player_scores.npy` — players × 10,000 worlds, `receipt.json`, `exposure_ledger.json`). Any change to
the player universe re-bases every draw: a rebuild is a different book, not a patched one.

### 4.3 The DraftKings side (no API)

1. **Reserving entries.** The operator enters one placeholder lineup N times per contest before the build.
2. **Editing reserved entries is only possible through the entries export**: Lineups → Upload Lineups → *Download
   Entries* → `DKEntries.csv` lands in the Windows Downloads folder (WSL path
   `/mnt/c/Users/<user>/Downloads/`). `watch_dk_entries.sh` fills it positionally with
   `scripts/week1_fill_dk_entries.py` (keepers first per contest, the `ENTER/` layout) and writes the upload file;
   the operator uploads it on the same page. **Withdrawals are not available on full contests** (Week 1: 80 entries
   stood because 90 had been reserved).
3. Late swap works through the same upload during live contests for players whose games have not started.
4. Never upload a `book.csv`; only the emitted draftable-id CSVs
   (`scripts/emit_dk_upload_csv_v1.py --source run-dir --run-dir <dir> --ranks a-b --output <csv>`, create-only).

---

## 5. Monday / Tuesday settlement

1. Operator downloads from DK: the contest **entry history** export (own entries: points, place, winnings) and each
   contest's full standings `https://www.draftkings.com/contest/exportfullstandingscsv/<contestId>` (zip; DK purges
   after ~4 days). He puts them under `/home/erich/projects/nfl-predictions/results/2026-09-20/`.
2. Validate and load with the standings capture CLI (`nfl-dfs capture-dk-standings …`; the 2026-09-14 validator
   fixes handle blank-lineup entries, 2-dp ranks, full-field ownership denominators, one-entry gaps, chunked
   uploads). `--apply` requires `--confirm-settled --confirm-full-field`. Loads `nfl_raw.contest_entries` and
   `nfl_raw.contest_ownership` (Week 1: 831,028 + 158,302 + 4,998 entries).
3. Settle every book on official points (entered, paid K80, K90, shadows): `tools/compare_books.py`,
   `reports/week1-duds/` shapes; write the week's settlement report like
   `reports/2026-09-14-week1-field-winners-settlement.md`.
4. Winners' top-100 profile and the dud analysis (`tools/low_scorer_audit*.py`).
5. `s-score` (`score-entries`, Tue 08:00 CT) scores last week's projections automatically.

---

## 6. Lab cohort operations (nfl2)

### 6.1 Building and deploying a cohort image
```
cd <cohort worktree>                                   # clean, pushed branch; HEAD is the cohort commit
gcloud builds submit --project nfl-2-506823 --config cloudbuild.prereg0NN.yaml \
  --substitutions _IMAGE_TAG=us-central1-docker.pkg.dev/nfl-2-506823/lab/nfl2:prereg0NN-<sha12> --quiet
gcloud artifacts docker images describe <tag> --project nfl-2-506823 --format='value(image_summary.digest)'
echo "<full sha> <tag> <digest>" > results/prereg0NN_image.txt     # untracked (results/ is ignored)
```
`.gcloudignore` excludes `results/**`; add `!results/<frozen receipt>` for any receipt the image must carry (the
Dockerfile `COPY`s it).

### 6.2 Moving the jobs and arming a launcher (only when both lanes are idle)
```
for job in lab-run lab-run-slow; do gcloud run jobs update $job --project nfl-2-506823 --region us-central1 \
  --image <tag> --update-env-vars CODE_SHA=<full sha>,IMAGE_DIGEST=<digest> --parallelism 36 --tasks 72 --task-timeout <s> --quiet; done
setsid nohup /home/erich/projects/nfl-predictions/scripts/launcher_registry.sh run --root <worktree> \
  --state-root /home/erich/.local/state/nfl-dfs/lab-launcher-registry --lane nfl2-lab-jobs --owner production \
  --target-prefixes <prefixes> -- <worktree>/scripts/queue_NNN.sh > <worktree>/results/queue_NNN_launcher.log 2>&1 < /dev/null &
```
(`scripts/arm_118_now.sh` in the 098 worktree does exactly this for 098.) A launcher that dies with the workstation
leaves a receipt: move it to `adjudicated-launcher-receipts/…orphaned-<stamp>.json` and append an
`action=adjudicated` line to `launcher-registry.log` after confirming no surviving child work.

### 6.3 Reading
Readers are frozen with the preregistration (`scripts/preregNNN_report.py RUN…`), run once on complete banks, and
their verbatim output is the LEDGER row. Never cite a partial bank.

### 6.4 Repairs (lost tasks)
Cloud Run loses tasks to "Internal error running task" (retried up to 3×) and occasionally to the 8 GiB limit.
`/home/erich/week1-sunday/repair_bank.sh EXPERIMENT_FILE RESULT_DIR PREFIX BANK CODE_SHA` re-runs exactly the
missing slates, one execution per season (`<prefix>rep<season>-<stamp>`, args `--bank=N --season=S --weeks=…`),
through the registry; the jobs must carry the bank's image (it checks `CODE_SHA`). For 097:
`/home/erich/week1-sunday/repair_097.sh` moves both jobs back to the 09u image and runs the 970 then 971 repairs —
**run it only when 098 is finished** (the two would fight over the job image). Then
`scripts/prereg097_report.py` with `--repair` run ids (union loader), LEDGER row.

---

## 7. Production Cloud Build / Cloud Run operations

- **Deploying a production job**: `gcloud builds submit` from a clean worktree with the repo `cloudbuild.yaml`,
  image `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:<tag>`, then `gcloud run jobs update
  <job> --image <tag@digest>`; record the digest in HANDOFF. Never create jobs. Schedulers (`s-*`) are the cadence
  (list: `gcloud scheduler jobs list --location us-central1`); do not touch paused research schedulers.
- **Frozen research chains** (corpus-R6, source-v3, discovery matrix, FP×SIS ablation) build with their own
  `cloudbuild.<chain>.yaml` from a commit that is **on `origin/main`** (the build asserts ancestry) and run through
  exact-name controllers on job `atlas-cbc-32g-full-2023-w8-v1` (8 CPU / 32 GiB). The source-v3 chain is abandoned
  at defect 11 (§9); do not restart it without a protocol decision.
- **The classifier will refuse** `git push origin HEAD:main` and `gcloud run jobs execute` on this project: give the
  operator the command (he ran three main fast-forwards this week within minutes).

---

## 8. The direct paid-source runner (what replaces the abandoned chain)

`scripts/paid_source_ladder_direct_v1.py` (branch `production/paid-source-ladder-direct-20260915`, commit
`f8b995c0`) runs the frozen FP×SIS 2×2 ablation's pure computation over the frozen inputs (seven-pack v4 rows,
fixed-G0 catalogs, candidate-v2 artifacts, exp5 discovery matrices at ~1.2 GB per slate, downloaded then deleted),
adds the stage-influence sidecar and the finish endpoint (200k-lineup field from
`/home/erich/week1-sunday/direct_runner/ownership_2023_2025_catalog_ids.parquet`, all 54 slates ≥ 840 mass), and
records every input by uri/bytes/sha256 in `results/manifest.json`. Design and decision rules:
`reports/2026-09-14-prereg-paid-source-influence-ladder-DRAFT.md` (§3–§4: co-primary contrasts FP|SIS-on and
SIS|FP-on at K20 on points and on −best_pct, family 0.9875, season bootstrap + LOSO; the ladder reading table).

When 54 results exist:
```
cd /home/erich/projects/.nfl-predictions-worktrees/source-v3-same-path-20260914
.venv/bin/python scripts/paid_source_ladder_direct_v1.py --read /home/erich/week1-sunday/direct_runner/results
```
Write `reports/2026-09-15-paid-source-influence-ladder-direct.md` with the verbatim read, the ladder table, and the
frozen consequence (no deployment from this result; a favourable source goes to family decomposition and a 2026
shadow). Add the outcome to briefing §7 and to HANDOFF. Copy `manifest.json` and `read_table.csv` into the report's
folder (small) — the per-slate JSONs stay on the host.

---

## 9. Open defects and their status

| # | what | where | status |
|---|---|---|---|
| 1–7 | never-completable defects in the discovery-matrix / source-v3 chains (repository-root binding, untracked-then-clean, create-once self-refusal, task-0 parallelism, jq `-n`, secure-read contract, remote-ref census) | fixed on main by 09-12 | closed |
| 8 | source-v3 image put the checkout at `/app`; the fixed-G0 evidence is pinned by absolute workstation paths | `Dockerfile.corpus-r6-matchup-source-v3` keeps the checkout at `/home/erich/projects/nfl-predictions` and symlinks `/app` (main 6ec448fc) | closed |
| 9 | batch module's task0 **readiness smoke** calls the strict candidate reopen (passes only at 346b2a27) | smoke-only; worker path already uses the descendant reopen | open, harmless |
| 10 | component producer treated SIS coverage yards as a nonnegative count (8 real negative rows) | producer fixed (Commit A 7dcacb93); capture-plan lock re-frozen (Commit B a0eb8da1) | closed |
| 11 | immutable 2023-W1 catalog spells each game three ways; pinned `build_target_spine_v1` demands one | needs option B (re-establish the fixed-G0 authority) | **chain abandoned; direct runner instead** |
| 12 | PREREG-098 field sampler fill starved at 199,748/200,000 | batches ≥ 20k rows, 400 tries | closed |
| 13 | PREREG-098 outcome path read `field_pct` from the wrong rows (r1 banks lost) | fixed, r2 running | closed |
| 14 | `ingest-nflverse` exits non-zero on the missing `ftn_charting_2026.parquet` after loading the rest | add tolerance | open |
| 15 | `nfl-week1-sunday-build.sh` / runbook hard-coded to Week 1 (week, group 151307, `2026-w01`, tag suffix, publish root) | Week-2 copies + new one-shot timers (§4.1) | **open, needed by Sunday** |
| 16 | Cloud Run "Internal error running task" losses on the lab lanes (23–51 retries per bank) | repairs per §6.4 | recurring |

---

## 10. File index (most used)

- Reports: `reports/2026-09-14-project-briefing-for-a-new-model.md` (background, §10 build process),
  `reports/2026-09-13-week1-findings-and-recommendations.md`, `reports/2026-09-14-week1-field-winners-settlement.md`,
  `reports/2026-09-14-week1-swaps-and-cheap-players.md`, `reports/2026-09-14-payout-retro-test.md`,
  `reports/2026-09-14-prereg-paid-source-influence-ladder-DRAFT.md`, `reports/2026-09-10-neo4j-fantasy-points-sis-influence-review.md`.
- Sunday tooling (host `/home/erich/week1-sunday/tools/`, tracked copies `scripts/week1_*`): `vet_book.py`,
  `market_move.py`, `ordering_shadows.py`, `player_score.py`, `hybrid30.py`, `exposure_cap_book.py`,
  `compare_books.py`, `book_sheet.py`, `fill_dk_entries.py`, `learned_score_live.py`; watchers
  `watch_dk_entries.sh`, `watch_late_inactives.py`; drivers `t70_rebuild.sh`, `learned_after_build.sh`.
- Lab: `PREREG-098.md`, `experiments/118_finish_objective.py`, `experiments/prereg098_field_sampler.py`,
  `scripts/prereg098_report.py`, `scripts/prereg098_mechanics_gate.py`, `scripts/queue_118.sh`,
  `scripts/arm_118_now.sh`; 097: `scripts/prereg097_report.py`, host `queue_117_finish.sh`, `repair_097.sh`.
- Production chain scripts (reference only now): `scripts/cloud_corpus_r6_matchup_source_task0_v3.sh`,
  `scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py freeze-capture-plan`, `cloudbuild.corpus-r6-matchup-source-v3.yaml`.
