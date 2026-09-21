# Take-over handover — production and lab, from 2026-09-21

**Read this first.** It is written for a model that has no memory of this project, taking over both roles the
previous model held: reviewing production work, and owning the laptop-side Week-3 wiring. It supersedes
`reports/2026-09-15-week2-operating-handoff.md` (Week-2 take-over document) and the 2026-09-20 draft of this file.
Where they disagree, this file wins. Everything below was re-derived from git, BigQuery, gcloud and this host on
**2026-09-21 between 05:00 and 07:00 CT**; nothing depends on any session's memory. Times are Central (CT) unless
marked Z.

Every claim below was re-checked adversarially on 2026-09-21 (118 claims, 18 corrected before publication).

**The single rule that governs every new step (operator, 2026-09-20):** no fallbacks that hide failures. A step
works as designed or the run stops. Any stand-in that survives is recorded per row and shown before upload.

Sections: 1 first hour · 2 identities · 3 Week-2 causes and status · 4 the deploy that matters · 5 Week-3 cadence
and its gaps · 6 tools · 7 paid data · 8 the two-agent channel · 9 ranked risks · 10 readiness checklist ·
11 constraints · 12 where things are.

---

## 1. First hour

1. **Fetch both repos** (plain `git fetch -q --all`; never `--prune`, the classifier refuses it):
   `/home/erich/projects/nfl-predictions` (production, GCP `nfl-predictions-503414`) and `/home/erich/projects/nfl2`
   (lab, GCP `nfl-2-506823`). **Never work in either primary checkout** — production is dirty on 143 files on an old
   branch, nfl2 is dirty on 14. Use a detached worktree in a scratch directory.
2. **Read this file, then section 8**, then the six reading-list entries there (items 1-5 plus the paid-data chain).
3. **Check the two live processes.** `ps -p $(cat /home/erich/week1-sunday/host_ingest_dk_loop.pid)` — the hourly
   DraftKings pull loop, pid 4129, running 4 days 23 h, log `/home/erich/week1-sunday/host_ingest_dk_loop.log`
   (healthy lines: "Loading N rows into … dk_salaries", "Polled N contests"). Its log mixes UTC banners with
   local-time Python lines, so the newest stamp always looks five hours stale — convert before judging and never
   restart on that stamp alone. If it is dead:
   `setsid nohup /home/erich/week1-sunday/host_ingest_dk_loop.sh > /home/erich/week1-sunday/host_ingest_dk_loop.log 2>&1 < /dev/null &`
   The second is `nfl-cloud-build-monitor.service` (pid 395), a read-only Cloud Build poller across both projects.
   **`nfl-shared-handoff-inbox.service` is INACTIVE on this host**, despite the outgoing lab note saying the
   workstation inbox is polled every 300 s. Nothing watches the channel automatically — poll it yourself.
4. **Re-establish a periodic check.** The previous session polled both remotes every 5 minutes and the host hourly.
   Session crons die with the session. Poll: both remotes, the DK loop, and from Saturday the week timers.
5. **Know the three things that block Week 3** before you plan anything (details in section 5):
   the `project-slate` image still runs the Week-2 defect; the Week-3 host files do not exist; the watchers are still
   armed as a transient unit, which is exactly how Week 2 lost them.

---

## 2. Identities (verified 2026-09-21)

### 2.1 Branches — **nothing from this weekend is merged to `main`**

`git merge-base --is-ancestor <branch> origin/main` is NO for every branch below. The deployed images therefore
contain none of the repair work.

| purpose | branch (origin/…) | sha |
|---|---|---|
| production main | `main` | `9afb1784` |
| **complete tested integration — deploy from here** | `production/week3-integration-20260921` | **`5aa2c73b`** |
| Week-3 operational wiring (laptop-owned scripts) | `production/week3-operational-wiring-20260920` | `5f8f61a5` |
| market repair (props-or-nothing, market-source log, exposure sheet, input gate, monitor check) | `production/prop-name-ambiguity-and-fallback-guard-20260921` | `8a9fdbf8` |
| standings capture tolerances + typed result classes | `production/standings-capture-tolerances-20260921` | `bf51d94b` |
| regeneration lineage + chain wiring | `production/regeneration-lineage-20260921` | `f058878f` |
| vendor per-step sessions + SIS weekly importer | `production/vendor-sessions-per-step-20260921` | `39d64d4d` |
| weather precipitation plumbing | `production/weather-precip-plumbing-20260921` | `9c516bd4` |
| Week-3 shadow arms | `production/week3-shadow-arms-20260920` | `22b68295` |
| Week-3 shadow outcomes builder | `production/week3-shadow-outcomes-20260920` | `767df073` |
| Week-3 shadow runner/reader | `production/week3-shadow-runner-20260920` | `3782d520` |
| Sunday final path v2 | `production/sunday-final-path-v2-20260920` | `8b2bf164` |
| QB availability gate | `production/qb-availability-gate-20260919` | `8dd7abc9` |
| rules/reports (this document) | `production/in-season-rules-20260919` | moves as this file is edited — `git ls-remote` it |
| operational worktree branch (what Sunday actually ran) | `production/week1-audit-adjust-20260912` | `e45798ba` |
| paid-data / Fantasy Points matchup chain | `research/2026-09-paid-source-preflight` | `6ccf5894` |
| **RETIRED, reference only** — a second, conflicting matchup loader | `fix/fantasy-points-matchup-staging-20260921` | `d673fd4a` |
| lab → workstation channel (nfl2) | `lab/workstation-reply-bank991-20260918` | moving; `56987faf` at 2026-09-21 06:05, carries `handoffs/2026-09-21-START-HERE-new-lab-model.md` |
| workstation → lab channel (nfl2) | `review/prereg101-reply-20260918` | moving; `ce41e304` at 2026-09-21 06:11, carries the outgoing lab model's own `handoffs/2026-09-21-takeover-state.md` |
| lab release pinned for the Week-2 book (nfl2) | worktree `/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c` | `2dc116c`, clean |

`production/week3-integration-20260921` @ `5aa2c73b` is new (pushed 2026-09-21): all ten production branches merged
with **zero conflicts**, 86 files and 7,021 insertions against `main`, and **191 passed / 1 skipped** across the
fifteen affected test modules (named in section 10). It is the only tree that contains every script the Week-3
cadence calls. Three earlier integration commits (`387b1e47`, `a29f727f`, `e679e785`) are cited in older notes; all
three are ancestors of `5aa2c73b` and are now on the remote, so nothing is lost — cite the branch tip, not them.
The tip moved from `a37e3339` to `5aa2c73b` on 2026-09-21 when the build lane's test list was extended (section 4).

`fix/fantasy-points-matchup-staging-20260921` must not be merged. Its shadow SQL sits under `sql/features/`, which
`build-features` globs, so the feature build would execute it against a table that does not exist; and its loader
requires a run-level `complete` manifest, which rejects the real Week-1 sealed captures. The lab retired it in
`review:handoffs/2026-09-21-paid-data-contract-disposition.md`.

### 2.2 Cloud Run and Cloud Scheduler

| job | image | state |
|---|---|---|
| `project-slate` (hourly projections) | `nfl-dfs@sha256:0993ee01…`, tag `week2-qb-f06a192c`; build `d7089008` started 2026-09-19T20:28Z. The `_CODE_SHA` substitution is baked at build time and survives only in the tag suffix — **the job carries no `CODE_SHA` env var** (its envs are `MODEL_ENSEMBLE=1`, `MODEL_REGISTRY_VARIANT=tail_k1`, `BLEND_MODEL_WEIGHT=0.45`, `GAME_SIM_MODE=possession`) | **runs the pre-repair market code**: commit `f06a192c` contains zero references to `MarketMatchError` or `market_source_log`. Last five executions all succeeded (latest 2026-09-20T16:02Z). |
| `build-features` | `nfl-dfs@sha256:8d9b3cb5…`, tag `salary-week-99440a23` | unchanged by this weekend's work |
| `train-weekly` | `nfl-dfs@sha256:41de2eae…` | last run 2026-09-15 |
| `ingest-props`, `ingest-odds` | `nfl-dfs@sha256:0a55920d…`, tag `odds-shadow-aad6739` | both succeeding |
| `tabpfn-gen` | `tabpfn-gen@sha256:fdb120dc…`, tag `preweek-fb875dd3` | GPU; **no scheduler** — must be run by hand every Wednesday |
| `ingest-dk`, `ingest-contests`, `ingest-nflverse` | see the console | `ingest-dk` from Cloud Run is 403-blocked by DraftKings; the host loop covers it |

Neither `f06a192c` nor `99440a23` is on `main`; both branch from `9afb1784`. **us-central1 holds exactly 1000 Cloud
Run jobs — the JobsPerProject quota. Never create a job; reuse one and pass `--args`.** There is no job named
`live-lineups` or `capture-dk-standings`; both are CLI subcommands run on the host.

Scheduler: 45 jobs, **22 enabled**, 23 paused. Enabled and relevant: `s-features` Tue 06:30, `s-train` Tue 07:30,
`s-score` Tue 08:00, `s-project-tu` Tue 09:30, `s-props` 09:30 Wed–Sun, `s-odds` 09:00/15:00, `s-dk` hourly,
`s-contests` 10:00, `s-us-dfs` 10:30, `s-weather` 08:00 Fri–Sun, `s-nflverse` 05:00 daily, `s-freshness` 08:00,
`s-backup` 07:00, `s-trends` Wed 11:00, `s-dk` hourly **Wed–Sun** (`0 * * * 3-7`), and the Sunday set
`s-features-sun` 05:30–10:30, `s-contests-sun` 06–11, `s-project-su` hourly 06–11.

**Two research shadows are ENABLED and will fire inside the Week-3 Sunday build window**:
`s-shadow-cbwu-oi-paired-early` 09:45 and `s-shadow-cbwu-oi-paired-late` 10:45. Confirm they are still wanted before
Saturday. `s-cfb`, `s-cfb-sat` and `s-us-dfs-sun` are also enabled and unrelated to NFL DFS.

**Paused — do not resume without the gate decision:** the four Route Share shadows (`s-shadow-k1-roleunion`
early/late, `s-shadow-k1-route-roleunion` early/late), the SIS pass-tail trio
(`s-shadow-sis-pass-tail-paired`, `s-tabpfn-sis-pass-tail-control`, `s-tabpfn-sis-pass-tail-treatment`), and the rest
of the k1/k3/archetype/freeze-tail family. The Route Share pair is the operator's Monday decision. The SIS pass-tail
trio **does** have a gate document, in DRAFT awaiting lab acceptance:
`reports/2026-09-21-sis-pass-tail-2026-prospective-gate.md` on the rules branch. Get it accepted or move the three
jobs to DORMANT with a reason before Week 5 — never silence the checker by parking a live gate.

### 2.3 Warehouse (`nfl-predictions-503414`)

| table | 2026 state |
|---|---|
| `nfl_predictions.player_projections` | **weeks 1 and 2 only — no Week-3 batch exists.** Newest Week-2 batch 2026-09-20T16:02:22Z, 513 rows, 32 DST, 69 rows ≤ 0. **Max projection is Justin Jefferson 25.349166975629** — the exact Week-2 defect value, still served. That number is the standing proof the repair is not deployed. |
| `nfl_features.tabpfn_projections` | **week 2 only, 877 rows.** No Week-3 cache: the Wednesday `tabpfn-gen` run is required before any Week-3 build. |
| `nfl_predictions.market_source_log` | **does not exist.** Created by the first repaired `project-slate` run. |
| `nfl_predictions.own_shadow` | 2,370 rows, all 2026 W1, last written 2026-09-10. Not an in-season monitor. Synthetic rows written by offline tests were deleted 2026-09-21; the row count is consistent with that but is not proof — no job id or before-count was recorded. The `tests/conftest.py` guard on the integration branch is what prevents a recurrence. |
| `nfl_predictions.div_shadow` | W1 2,142 rows / 11 batches; **W2 2,393 rows / 12 batches through 2026-09-20T16:02Z**. It *is* collecting in-season — an earlier note saying otherwise was wrong. Its blindness is to rows without a prop-sourced market, which is precisely the Week-2 defect class it could not see. |
| `nfl_raw.weekly_stats` (nflverse actuals) | **max week 2** (W1 1,118 rows, W2 1,044), loaded 2026-09-21T10:04Z. The Week-2 outcomes builder can run now. |
| `nfl_raw.contest_entries` / `contest_ownership` | **2026 W1 only** (994,328 / 2,212 rows, 3 contests). **The Week-2 standings capture has not been applied.** There is no table called `dk_contest_standings`; these two are what the capture writes. |
| `nfl_raw.fantasy_points_route_share` | W1 265 rows (target week 2, run `20260917T172911Z…`, archived to GCS at ingest, sha `07642ab6…`); W2 200 rows (target week 3, 2026-09-21T02:54Z, archived). This **is** a live model feature: `src/nfl_dfs/models/featureset.py` lines 129-132 name `fp_route_share_last`, `_l4`, `_jump` and `fp_route_cross_season`; `sql/features/017k_fantasy_points_route.sql` builds them and `021`/`023` consume them. |
| `nfl_raw.sis_team_context_game` | W1 **64 rows: 32 clean + 32 with `team`, `opp`, `source_run_id` and `ingested_at` all NULL** — a full duplicate of all 32 teams, so any query that forgets `team IS NOT NULL` double-counts every Week-1 team. W2 2 rows (the Thursday game only; SIS posts games over the following days). |
| `nfl_raw.sis_team_run_context_game` | W1 32 clean, W2 2. No NULL block. |
| Fantasy Points matchup tables | **none exist** — confirmed by an INFORMATION_SCHEMA sweep. Section 7. |
| `nfl_raw.schedules` | Week 3: 16 games, first kickoff **Thu 2026-09-24 20:15 ET**, Sunday main block 2026-09-27 13:00 ET (**9** games; 2 at 16:05, 2 at 16:25, 1 at 20:20 — size the contests off 9), last game Mon 2026-09-28. Week 4 opens Thu 2026-10-01. |

### 2.4 This host

- **Two NFL processes are running**: the DK pull loop (pid 4129) and `nfl-cloud-build-monitor.service` (pid 395,
  enabled and active, a read-only Cloud Build poller across both GCP projects). No watcher, no build, no week timer.
  `nfl-shared-handoff-inbox.service` is **inactive** — the channel is not polled automatically.
- **No week timers exist.** Every `nfl-week2-*` transient unit is gone, as transient units are.
- **Two systemd user services are crash-looping**: `nfl-cloud-run-lane-monitor.service` and
  `nfl-lab-action-note-monitor.service` (both `activating (auto-restart)`). Two more (`nfl-lab-repo-transition-monitor`,
  `nfl-production-monitor-heartbeat`) are dangling symlinks into a deleted worktree. None is on the money path;
  none was diagnosed. The lane monitor's unit file is a symlink into the dirty primary checkout, where that same
  file shows an uncommitted edit — the likely cause.
- **The operational worktree** `/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912` @
  `e45798ba` has **one uncommitted file**: `scripts/arm_week_timers.sh`, carrying the hand-applied release-pin patch
  (`EXPECT_SHA`/`CLONE`). It is not committed anywhere. A clean checkout loses it. **Commit it before Tuesday.**
- **Week-3 host files do not exist**: `/home/erich/week3-sunday-build.sh`, `/home/erich/week3-sunday-watchers.sh`,
  `/home/erich/week3-sunday/`, `/home/erich/week3-chosen-dose.env`. `arm_week_timers.sh 3 --run` references all of
  them and will fail. The Week-2 equivalents exist; the dose used was `CHOSEN_LEV=2560`, `CHOSEN_BOOM=10240`.
- **Week-2 artifacts**: `/home/erich/week2-sunday/` holds the books, bundles, logs and the tools (`apply_swaps.py`
  v1.1 sha `2a1750c8…`, `qb_flags.sh`, `gen_sheet.py`, `manifest_and_gap.py`, `run_promotion.sh`). `ENTERED/` holds
  the entry exports and **`ENTERED/standings/`** holds the Week-2 standings downloads taken 2026-09-20 19:25.
  **DraftKings purges standings about four days after the contest — these expire around Thursday 2026-09-24.**
  Never commit anything under `ENTERED/`.
- Vendor sessions: SIS refreshed 2026-09-20 21:58 (expires in days — operator re-login needed); Fantasy Points
  2026-09-12, still authenticating.
- Four SIS plan files under `automation/sis/plans/` are **untracked in the primary checkout**. Three of them
  (`team-context-2026-w01-w02-v2.json`, `-w02.json`, `-w03.json`) are on
  `production/vendor-sessions-per-step-20260921`. **`team-context-2026-w01-w02.json` (the non-v2) is on no ref at
  all** and is one `git clean` from gone; `-v2` supersedes it (v1 included the `passing-value` report, which never
  renders to a submitted state), so either commit it for the record or confirm the supersession in writing.
- Disk: 21% of 1 TB used. No pressure.
- **Durability**: every branch above is on the remote (verified individually). The working copies used this weekend
  live under `/tmp/claude-1000/…/scratchpad/` and will vanish; the branches will not.

---

## 3. What went wrong in Week 2, and the status of each repair

Full analysis: `reports/2026-09-21-week2-post-mortem.md` (rules branch). Outcome: 97 entries, best finish 8.7%,
best score 156.16 against winners at 200–235.

1. **Prop-name ambiguity plus a DK points-per-game stand-in.** Introduced 2026-09-04. `market_points` unioned three
   name sources and dropped ambiguous spellings; "justin jefferson" collided with a roster-only rookie, so Jefferson
   had no prop line, and the blend then used his Week-1 score as the "market" at 55% weight: 25.3 = 0.45 × 18.1 +
   0.55 × 31.2. Six players at 25–57% exposure all busted. **Fixed on the market repair branch**: ambiguity resolves
   to the one id on the slate; the live market is props or nothing; a feed-present name that does not match stops the
   run; every row's source is written to `market_source_log`. **Not deployed** — section 4.
2. **Concentration.** The exposure sheet flags every player over the thresholds with the reason. Selection-only cap,
   market-pull and row-shape arms are built for the Week-3 shadow. **No live cap exists** and none should be added
   without a paired shadow; the operator decides.
3. **Chalk was faded in a week chalk hit.** Descriptive; the sheet carries a chalk-parity flag.
4. **Selector inversion.** Stored `sel_mean` correlated −0.49 with realized; corrected HSIM −0.09; pooled −0.33. No
   weight change from one slate; the paired shadow is the Week-3 test.
5. **The standings capture rejected all twelve exports.** Fixed on the capture branch (twelve of twelve validate)
   with typed result classes and `--failure-manifest`. **Not applied** — the warehouse still stops at Week 1.
6. **Blind instruments.** `div_shadow` only logs prop-sourced rows, which is exactly what failed; `own_shadow` does
   not run in-season. `market_source_log` will be the first per-row market monitor.
7. **Behaviour change to know about:** DST rows are now model-only (they had been 0.45 model + 0.55 DK PPG). The lab
   has ruled on this — section 8.

Not started or unfinished: the point-in-time weather shadow; the laptop's remaining audit queue; the cross-season
window question (Week-3 `_l4` features are two-game windows); the chain-level provenance gate inside the laptop's
`run_week_build.sh`; the QB availability contract repair (design on the rules branch).

---

## 4. The deploy that matters

Until this is done, **every Week-3 projection batch carries the Week-2 defect.** The first Week-3 batch will be
written by `s-project-tu` on Tuesday 09:30.

1. Deploy `production/week3-integration-20260921` @ `5aa2c73b`. **Do not re-derive the merge by hand.** It merges
   exactly ten branches: wiring, prop-name, standings-capture, regeneration-lineage, vendor-sessions, weather-precip,
   shadow-arms, shadow-outcomes, shadow-runner, sunday-final-path-v2. `production/qb-availability-gate-20260919` is
   deliberately **not** in it — it edits `src/nfl_dfs/inference/run_projections.py`, the same file the market repair
   rewrites, so merging it is a separate and untested decision. `production/in-season-rules-20260919` is documents
   only. The inventory source-set v8 travels with the market repair; its tests pin the hashes.
2. Build the image with **`cloudbuild.week1-live.yaml`, not `cloudbuild.yaml`.** This was verified on 2026-09-21:
   the currently deployed image was produced by that narrow lane in **under six minutes** (build `d7089008`,
   steps `live-boundary-tests` → `build-live-image` → `smoke-live-image`, using `Dockerfile.week1-live` — which is
   the image `project-slate` actually runs). The full-suite `cloudbuild.yaml` has been attempted **once**, on
   2026-09-15, and **TIMED OUT at its 3-hour ceiling** (build `2a28b013`); it has not completed since, and defect 17
   in the Week-2 handoff records why (the frozen-factorial drift failures plus a ~7,700-test suite). Submitting
   `cloudbuild.yaml` on Saturday would burn three hours and produce no image.

   From a checkout of the integration branch:
   ```
   SHA=$(git rev-parse HEAD)
   gcloud builds submit --config cloudbuild.week1-live.yaml --project nfl-predictions-503414 \
     --substitutions _IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week3-market-source-${SHA:0:8},_CODE_SHA=$SHA
   ```
   Using this lane is a **disclosed deviation** from "image only after the complete suite": record the build id in
   `HANDOFF.md`. The lane's test list was extended on 2026-09-21 to run the six market-repair modules
   (`test_market_source`, `test_prop_market_ambiguity`, `test_market_monitor`, `test_build_inputs`,
   `test_exposure_sheet`, `test_effective_policy_rule_inventory`) beside its eleven live-boundary modules, so the
   props-or-nothing contract and the frozen inventory hashes are verified inside the build that ships them.
   The assistant's harness refuses `gcloud builds submit`, so this step is the operator's or the laptop's.
3. Point the job at it (**operator or laptop — the workstation assistant's harness refuses job updates**):
   `gcloud run jobs update project-slate --project nfl-predictions-503414 --region us-central1 --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week3-market-source`
4. Verify on the next run: the log must say `market blend source: props (N/M rows)` and `market-source log: M rows`.
   A `MarketMatchError` is the intended stop, not a failure to route around: it names the player whose feed name did
   not match. Then
   `SELECT source, COUNT(*) FROM nfl_predictions.market_source_log WHERE season=2026 AND week=3 GROUP BY 1`
   should show props for most skill rows, `model_only_no_line` for the unpriced and `model_only_dst` for defenses.
5. If the job fails for any other reason the previous batch stays served, visibly, in the job status. **Do not
   restore the stand-in.**

Deadline: the Thursday game locks 2026-09-24 20:15 ET; the Sunday main slate locks 2026-09-27 12:00 CT.

---

## 5. The Week-3 cadence, and the three gaps that block it

Authoritative input list: `reports/2026-09-15-week2-operating-handoff.md` §3a and
`reports/2026-09-21-monday-command-sheet.md`.

**Blocking gaps, in the order they bite:**

- **The Week-3 host files do not exist** (section 2.4). Create `week3-sunday-build.sh`, `week3-sunday-watchers.sh`
  and `/home/erich/week3-sunday/` from the Week-2 versions, and get the operator's `week3-chosen-dose.env`, before
  Saturday. `arm_week_timers.sh 3 --run` fails without them.
- **The watchers are still a transient `systemd-run` unit.** This is the exact Week-2 failure: the 09:12 transient
  service exited in two seconds and systemd killed its detached children, so no entries were ever filled. No
  persistent unit has been written. Either write one or verify the three watcher processes by hand immediately after
  arming — do not assume.
- **The operational worktree cannot run the documented chain.** It is missing eleven scripts the cadence calls:
  `run_week_build.sh`, `run_week_watchers.sh`, `run_promotion.sh`, `relayout_enter.sh`, `run_week3_shadow.sh`,
  `rehearse_final_path.sh`, `exposure_sheet.py`, `regeneration_lineage.py`, `check_build_inputs.py`,
  `check_market_monitor.py`, `week3_shadow_runner.py`. **Week 3 must run from a checkout of
  `production/week3-integration-20260921`**, not from `e45798ba`.

**Monday/Tuesday.** DraftKings standings and contest-history exports (operator, browser) → `nfl-dfs
capture-dk-standings` validation, then `--confirm-settled --confirm-full-field --apply` for the twelve Week-2
contests, with `--failure-manifest` per contest. Standings expire ~2026-09-24. nflverse Week 2 is already loaded, so
the outcomes builder can run (`week3_shadow_outcomes.py --i-confirm-outcomes-released`, only after the operator
releases outcomes), then the shadow reader and the proper-score reader, then fill the evidence record once.

**Tuesday.** `s-features` 06:30, `s-train` 07:30, `s-score` 08:00, `s-project-tu` 09:30 — all automatic. Check the
`project-slate` log for `market blend source: props`. Run `scripts/check_market_monitor.py --season 2026 --week 3`
after the first repaired batch.

**Wednesday — paid vendor capture**, from a checkout of the integration branch:
1. `python -m nfl_dfs.ops.weekly_vendor_data verify-login`, then `run --week 3 --skip-odds`. This captures the three
   Fantasy Points matchup reports and imports the completed Week-2 Route Share append-once. **The matchup step
   currently fails**: the vendor's Schedule Week control had not opened Week 3 when it ran on 2026-09-21 02:54Z.
   Rerun later in the week; do not retry in a loop.
2. `sis-download run-plan --file automation/sis/plans/<plan>.json --output-dir sis/weekly/<run>` — note the plans in
   use are **two-week spans** (`team-context-2026-w01-w02[-v2].json`), not one plan per completed week.
3. `scripts/import_sis_team_context_weekly.py --input-dir <run> --plan <plan> --write --audit <receipt>` — append-once
   per team-week; rerun later in the week as SIS posts the remaining games.
4. `gcloud run jobs execute tabpfn-gen --update-env-vars TABPFN_UPCOMING=2026:3 --wait` — **no scheduler, and there
   is no Week-3 cache today.** Missing it was a Week-2 defect.
5. SIS sessions expire in days: `python -m nfl_dfs.ops.sis_downloads login --terminal-credentials --fresh` is the
   operator's interactive step.

**Saturday.** Operator inputs due before the first build: `contests.json`, the Week-3 dose file, the approved lab
release SHA (`--expect-sha`), refresh receipts. Refresh in order **after** the 09:30 props pull: `build-features` →
`tabpfn-gen` → `project-slate`, each `--wait`. Then arm the timers and **verify the three watcher processes**.

**Sunday.** On the integration branch `sunday_after_build.sh` runs everything in one pass: classify → vet →
replace against the live DK status feed → emit → sequential ENTER layout → verify bundle → atomic swap →
`run_promotion.sh` (which itself calls `relayout_enter.sh`) → `regeneration_lineage.py` → `exposure_sheet.py`,
writing every result into the TODAY file. **Do not invoke `run_promotion.sh` or `relayout_enter.sh` separately
afterwards** — that would re-publish an already-published bundle. **Read every exposure-sheet flag to the operator before upload.** The entries watcher fills the
newest `DKEntries*.csv`; the operator uploads before the 12:00 CT lock (11:15 target); the late-inactives watcher
runs to 20:25Z; `apply_swaps.py` v1.1 handles late swaps and refuses locked games.

**Never:** resume a paused scheduler without the gate decision; create a Cloud Run job; push to `main` from the
assistant; commit anything under `ENTERED/`.

---

## 6. Tools

All are on `production/week3-integration-20260921`. None is in the primary checkout.

- `scripts/exposure_sheet.py` (flag logic in `src/nfl_dfs/inference/exposure_sheet.py`) — flags `over_30`,
  `majors_over_20`, `dst_over_20`, `injured_over_10`, `no_line_over_5`, `market_gap`. On the entered Week-2 book it
  flagged the six players that busted; reproducing that needs the Week-2 book under `ENTERED/`, and until the
  repaired image has run the sheet prints `MARKET-SOURCE MONITOR NOT DEPLOYED` with every market source `unknown`.
- `scripts/check_build_inputs.py` — the money-build input gate (projection freshness and coverage, the market-source
  monitor, the TabPFN cache for the target week, the dose file, `contests.json`). Exit 1 stops the build. It FAILs
  today: the monitor does not exist and there is no Week-3 TabPFN cache.
- `scripts/check_market_monitor.py` — the latest batch's market sources. FAILs until the repaired image has run.
- `scripts/check_prospective_gates.py --week 3` — the frozen pre-lock gates. The three Route Share failures are
  known and accepted until the operator's decision; report only new ones.
- `scripts/regeneration_lineage.py` — row-level proof of the Sunday regeneration; the chain runs it after promotion.
- `scripts/week3_shadow_runner.py` / `week3_shadow_reader.py` / `week3_shadow_outcomes.py`. **Two divergent runners
  exist** (21 KB on the arms branch, 11 KB on the runner branch); the integration branch carries the arms version.
  Confirm which the lab wants before running the shadow.
- `scripts/rehearse_final_path.sh` — the Sunday chain against an archived artifact. Re-run it on whatever tree you
  actually deploy. The rehearsal-only flags `--test-exclude-dk` (on `vet_replace_v4.py`) and `--no-fresh-dk` (on
  `vet_replace_v4.py` and `apply_swaps.py`) must never reach the operational chain.
- `/home/erich/week2-sunday/apply_swaps.py` v1.1 (sha `2a1750c8…`), `qb_flags.sh`, `gen_sheet.py`.
- `nfl-dfs capture-dk-standings` — validation, then apply with the two confirmations.

---

## 7. Paid data (Fantasy Points matchups, Route Share, SIS)

**State.** Route Share is loaded and is a live model feature. SIS team context is loaded for Weeks 1–2 with the NULL
caveat in section 2.3. **The three Fantasy Points matchup reports have never been loaded** — nine Week-1 capture
attempts and one Week-3 attempt all failed, and until this weekend there was no load path at all.

**Root causes, from the raw exports rather than the manifests.** In Week 1 the vendor answered the same request with
two different schedules minutes apart (Arizona's opponent alternated between Carolina and the Chargers across
19:01–19:40Z on 2026-09-09). The schedule gate was right every time, but because the three reports are fetched in
sequence, no single run ever passed all three. A seal assembled the valid set from separate runs and archived it to
GCS; nothing loaded it. On 2026-09-21 the Week-3 attempt failed because the vendor had not opened Week 3: the
Schedule Week control accepted 3 and reverted to 2 after Apply.

**What now exists** on `research/2026-09-paid-source-preflight` @ `6ccf5894`:
- a capture with manifest schema 2 — bounded re-apply per report, every attempt preserved on disk, the vendor control
  state recorded before and after Apply, typed failure classes, and a per-run status ledger that cannot skip a stage;
- typed DDL as the contract (`sql/raw/010_…` staging, `sql/research/fp_matchup_shadow_tables.sql` shadow — under
  `sql/research/`, which the feature build does not glob), with a test asserting the DDL columns equal the code's;
- a loader that re-derives every gate from the bytes and from `nfl_raw.schedules` (kickoff, scheduled pairs, file
  modification time, games played), with an append key that is a pure function of the bytes;
- a shadow-only point-in-time join that fails closed on any capture at or after kickoff, wired to nothing;
- a read-only status view (`python -m nfl_dfs.ops.fantasy_points_matchup_status`) separating downloaded /
  gate-passed / validated / staged / consumed. 47 tests.

**Note for triage:** the typed `failure_class` exists only in schema 2. The 2026-09-21 failure was produced by the
old code and its manifest has `failure_class: null` — read the `error` string on that run.

**The lab approved this set on 2026-09-21 06:01** (`review:handoffs/2026-09-21-paid-data-contract-review.md`), for
**one action only**: the Week-1 seal staging write. Return the BigQuery job ids, row counts, append dispositions and
staging receipts. The shadow may be built only after that raw receipt is reviewed. No merge to `main` and no feature
activation until a separate outcome-blind efficacy review.

**Outstanding — one command**, blocked for the assistant by the harness classifier and awaiting the operator:

A durable worktree of `research/2026-09-paid-source-preflight` @ `6ccf5894` is checked out at
`/home/erich/projects/.nfl-predictions-worktrees/paid-source-preflight` (clean), so the command needs no scratch path:

```
cd /home/erich/projects/nfl-predictions && source .venv/bin/activate && \
PYTHONPATH=/home/erich/projects/.nfl-predictions-worktrees/paid-source-preflight/src \
python -m nfl_dfs.ingest.fantasy_points_matchups_weekly \
  --input /home/erich/projects/.nfl-predictions-worktrees/paid-source-preflight/reports/2026-09-09-week1-fantasy-points-live-matchup-capture-seal.json \
  --target-week 1 --output-root /home/erich/projects/nfl-predictions/fantasy-points/automated --write
```

The dry run against the real seal validates all three members (QB 61 rows / 58 resolved, WR-TE 284 / 250, OL-DL 32,
32 teams each) with nothing written.

---

## 8. The two-agent channel

Two agents work through git branches, never through prose relayed by the operator. **All git commits in both repos
are authored by the operator's identity, so authorship cannot tell you who did what — ownership lives in the handoff
prose.**

- The lab/laptop agent replies on nfl2 `review/prereg101-reply-20260918`.
- The workstation replies on nfl2 `lab/workstation-reply-bank991-20260918`, from a detached scratch worktree, never
  from a cohort or running-bank worktree.

**Read these first, in order** (all in `/home/erich/projects/nfl2`):
1. `review:handoffs/2026-09-21-end-to-end-week2-audit.md` and its `.json` — sixteen findings, the spine of what is
   current. P0: `ING-001` (vendor credential/append telemetry), `FEAT-001` (build-input provenance),
   `VET-001` (regeneration lineage), `TEST-001` (offline tests writing to the live warehouse). The rest are P1.
   No finding carries an owner field; ownership is only in the notes below.
2. `review:handoffs/2026-09-21-complete-week2-repair-and-experiment-plan.md` — phases and the ownership split.
3. `bank:handoffs/2026-09-21-workstation-repairs-progress-5.md` — the per-finding assignment.
4. `bank:handoffs/2026-09-21-workstation-repairs-progress-11.md` — the newest status note (SIS Weeks 1-2 captured
   and loaded with lineage; the 32 NULL-lineage Week-1 rows). Read `-9.md` after it, for the merge-order table.
5. `bank:handoffs/2026-09-21-workstation-provenance-gate-fields.md` — the exact fields `run_week_build.sh` must gate
   on. That file is laptop-owned; the fields were delivered as text.
6. `review:handoffs/2026-09-21-takeover-state.md` — the outgoing lab model's own parting note (2026-09-21 06:11).
   One correction to it: it says the workstation handoff inbox is monitored by `nfl-shared-handoff-inbox.service`
   every 300 s; that service is **inactive** on this host.
7. The paid-data chain, in order: `bank:…paid-data-coordination.md` → `review:…paid-data-coordination.md` →
   `bank:…-ack.md` → `bank:…progress-1.md` → `bank:…progress-2.md` → `bank:…reconciliation.md` →
   `review:…contract-disposition.md` → `bank:…review-set.md` → `review:…contract-review.md`.

**What the laptop side owns and has already delivered:** the Week-3 wiring at `5f8f61a5` (`arm_week_timers.sh`,
`week_env.sh`, `run_week_build.sh`, `run_week_watchers.sh` — the workstation does not edit these four; requirements
go across as text), the late-inactives watcher race fix, the shadow-timer scoping, the arm-time preflight, the
end-to-end audit, the repair plan, the independent post-mortem review, and the paid-data review.

**Open on the laptop side:**

| item | state |
|---|---|
| Wire the provenance gate into `run_week_build.sh` (call `check_build_inputs.py`, stop on exit 1) | not built; the wiring branch has had no commit since 2026-09-20 16:20 |
| Merge the repair branches, rebuild and redeploy the `project-slate` image, report the merged SHA | not done — **section 4; `5aa2c73b` is now ready for it** |
| `GEN-001` candidate-pool sidecars; `GEN-002` cold-start / minimum-price / DST supply arms | open, lab generator |
| `FEAT-002` strict-prior support receipts for the TabPFN repair table | open |
| Week-3 selector and ordering shadows | queued, not run |
| The 32 NULL-lineage SIS Week-1 rows: write their receipt or confirm they are not yours so they can be deleted | **unanswered** |
| Monday `capture-dk-standings --apply` for the twelve Week-2 exports | unanswered |

**Answered, do not re-ask:** DST stays model-only for Week 3 — a position-specific point-in-time market must pass
support and held-out tests first, and DK points-per-game is not a substitute. The two-loader conflict is settled in
favour of the research branch. The Week-1 staging write is approved.

**Eighteen workstation questions are still unanswered**, listed verbatim in the notes above. The ones that gate work:
whether the exposure sheet should be a chain step or stay a manual tool; whether the lineage check belongs inside
`run_promotion.sh`; the exact frozen rule set for the `FEAT-003` regression harness; whether the weekly vendor runner
should call the matchup loader after its capture step; and the build-receipt field names a `weekly_receipt.py` would
bind.

---

## 9. Ranked risks

1. `project-slate` serves the Week-2 defect until the image is rebuilt. Proof: Jefferson 25.349166975629 is still the
   maximum projection in the newest batch.
2. The Week-3 host files and dose file do not exist; arming will fail.
3. The watchers are transient — the Week-2 loss mode is unrepaired.
4. The Sunday chain cannot run from the operational worktree; it needs the integration branch.
5. The uncommitted `arm_week_timers.sh` patch is one `git checkout` from gone.
6. Week-2 standings expire around 2026-09-24 and have not been applied; the field-calibration harness has no Week-2
   rows until they are.
7. No Week-3 TabPFN cache exists; the Wednesday GPU run has no scheduler.
8. The props-or-nothing rule can stop a batch on a genuine name collision. That is intended. The residual case — both
   colliding players on the same slate — needs a manual alias.
9. No live exposure cap exists; the sheet is a monitor only.
10. Cross-season windows: Week-3 `_l4` features are two-game windows.
11. Cloud Run us-central1 is at the 1000-job quota.
12. The lab release must be pinned with `--expect-sha`; the runner fails identity otherwise.
13. Offline tests used to write to the live warehouse. The guard (`tests/conftest.py` records `load_dataframe`
    instead of executing it) is on the integration branch; any checkout without it can pollute shadow tables again.
14. Two systemd monitors are crash-looping, undiagnosed.

---

## 10. Readiness checklist (confirm each in writing on the reply branch)

- [ ] BigQuery read/write, GCS read, `gcloud run jobs describe`, `gcloud scheduler jobs list` all work; whoever
      deploys has `gcloud builds submit` and `gcloud run jobs update`.
- [ ] A checkout of `production/week3-integration-20260921` @ `5aa2c73b`, with exactly this command re-run
      (a different selection is not comparable): `python -m pytest tests/test_market_source.py
      tests/test_prop_market_ambiguity.py tests/test_exposure_sheet.py tests/test_market_monitor.py
      tests/test_build_inputs.py tests/test_live_smoke.py tests/test_dk_standings_capture.py
      tests/test_regeneration_lineage.py tests/test_week3_shadow_runner.py tests/test_week3_shadow_outcomes.py
      tests/test_weekly_vendor_data.py tests/test_sis_team_context_weekly.py
      tests/test_effective_policy_rule_inventory.py tests/test_feature_sql.py tests/test_leakage.py`
      → expect **191 passed, 1 skipped** (recorded 2026-09-21, ~6 min).
- [ ] Image digests read from the console and compared with section 2.2; after the rebuild,
      `check_market_monitor.py --season 2026 --week 3` reports OK on the first repaired batch.
- [ ] `exposure_sheet.py` reproduces the six flagged players on the entered Week-2 book.
- [ ] `rehearse_final_path.sh` green on the tree you will deploy.
- [ ] The Week-3 host files created, the dose file received, `arm_week_timers.sh` committed, and the three watcher
      processes verified after arming.
- [ ] Week-2 standings applied before they expire; outcomes builder and readers run; evidence record filled once.
- [ ] The periodic poll of both remotes re-established.

---

## 11. Operating constraints

- No silent fallbacks. Fail closed; monitor any surviving stand-in per row.
- Never commit DraftKings entry keys, cookies, user identifiers or entries exports. Handoff packages carry names,
  salaries and draftable ids only.
- Never weaken a leakage check. Never enter an untested rule on an entered book. Never put a script's own name in a
  `pkill -f`. Never commit, pull, rebase or switch branches in a worktree whose bank is running.
- The harness classifier refuses pushes to `main`, production Cloud Run execute/update, systemd unit writes,
  create-once publishes, `git fetch --prune`, and BigQuery writes it reads as shared-resource changes. Print the exact
  one-line command for the operator; never route around it.
- The four laptop-owned scripts are not edited by the workstation; requirements go across as text.
- Current-week outcomes are never read before the operator releases them.
- Frozen-chain rules 1–6 in `CLAUDE.md`, especially: smoke against real artifacts before freezing; conscious
  inventory revisions; reuse Cloud Run jobs rather than creating them.

---

## 12. Where things are

- **Rules branch** `production/in-season-rules-20260919` (tip moves with this file): this document, the Week-2 post-mortem, the
  evidence record, the Monday command sheet, the supplier scorecard, the season-window audit, the SIS pass-tail gate
  draft, the data-source value map, the QB availability repair design, `reports/OPEN-DEFECTS.md`, and three scripts.
- **Paid-data documents** are on `research/2026-09-paid-source-preflight` @ `6ccf5894`, not on the rules branch:
  `reports/2026-09-21-fantasy-points-matchup-staging-contract.md` (the contract in one page) and
  `reports/2026-09-21-fantasy-points-matchup-capture-incident.md`.
- **Deployable code**: `production/week3-integration-20260921` @ `5aa2c73b`.
- **Channel**: nfl2 `lab/workstation-reply-bank991-20260918` (notes, receipts under `handoffs/receipts/`, tools
  under `handoffs/tools/`) and `review/prereg101-reply-20260918`. Both move; `git ls-remote` before citing a sha.
- **Sunday outputs**: `/home/erich/week2-sunday/`, with raw exports under `ENTERED/` and the standings downloads
  under `ENTERED/standings/`.
- **Assistant memory** (not authoritative, and the incoming model has none of it):
  `/home/erich/.claude/projects/-home-erich-projects-nfl-predictions/memory/`.
