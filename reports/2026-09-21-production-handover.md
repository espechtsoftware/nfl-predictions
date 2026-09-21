# Production handover for the team taking over on Tuesday 2026-09-22

Written 2026-09-20/21 by the workstation assistant at the operator's direction after the Week-2 loss. Audience: the
agent and people who will run production from Tuesday. Everything here is checkable from the repository, the
warehouse and the cloud console; nothing depends on this session's memory. Where a step must be run by a person
(cloud deploys, DraftKings exports, money decisions) it says so. The operator's standing rules are in section 9;
the one that governs every new step: **no fallbacks that hide failures; a step works as designed or the run stops;
any stand-in that survives is recorded per row and shown before upload.**

## 1. Identities (what is deployed and what is not)

| thing | identity | state |
|---|---|---|
| production repo main | `origin/main` (see `git rev-parse origin/main`; 9afb1784 at the last poll) | the deployed images were built from main-lineage commits |
| Week-3 operational wiring (laptop) | `production/week3-operational-wiring-20260920` @ 5f8f61a5 | validated here (4 runner tests, rehearsal green 2026-09-20); NOT yet merged to main |
| market repair (this weekend) | `production/prop-name-ambiguity-and-fallback-guard-20260921` @ 93bb8120 (off 5f8f61a5) | tests green (58 + 3 + 3); NOT merged, NOT deployed |
| capture tolerances + typed result classes | `production/standings-capture-tolerances-20260921` (off 5f8f61a5; tip in the reply-branch note 3) | tests green (22 + 15); twelve Week-2 exports validate; `CaptureValidationError.result_class` and `--failure-manifest`; NOT merged; nothing applied |
| Week-3 shadow arms | `production/week3-shadow-arms-20260920` @ 22b68295 | 6 tests green; pending merge by the labs |
| Week-3 outcomes builder | `production/week3-shadow-outcomes-20260920` @ 767df073 | 3 tests green; pending merge |
| regeneration lineage + chain wiring | `production/regeneration-lineage-20260921` (off 5f8f61a5; tip in the reply-branch note 6) | `scripts/regeneration_lineage.py` (7 tests; green on the real Week-2 books: 52 replaced rows with reasons, promotion permutation, upload CSV and entries export match) and `sunday_after_build.sh` wired to run it and the exposure sheet after promotion (LINEAGE FAILED = DO NOT UPLOAD in the TODAY file, non-zero return; a failed sheet is written as EXPOSURE SHEET FAILED) |
| vendor capture per-step sessions | `production/vendor-sessions-per-step-20260921` (off 5f8f61a5; tip in the reply-branch note 10+) | defect 28 fixed: an expired SIS session no longer blocks the Fantasy Points capture when no SIS step runs (recorded `not-required`); 8 tests; the Week-2 Route Share (200 rows) was captured with it on 2026-09-21 02:54Z; `automation/sis/plans/team-context-2026-w01-w02.json` ready for the SIS run after the operator's login |
| weather precipitation plumbing | `production/weather-precip-plumbing-20260921` (off 5f8f61a5) | 3 offline tests + BigQuery dry-run compile green; takes effect at the next `build-features` (s-features Tue 06:30) once merged; not a model feature |
| rules/reports branch | `production/in-season-rules-20260919` @ db05b27d | post-mortem, evidence record, command sheet, this document |
| labs reply channel | nfl2 `lab/workstation-reply-bank991-20260918` @ ab6f15a (and later) | all handoff notes and receipts; the laptop's reviews land here |
| lab release used for Week 2 | nfl2 `/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c` @ 2dc116c | clean; the Week-3 runner pins the lab clone by `--expect-sha` |
| operational worktree (Sunday chain) | `/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912` @ e45798ba | one uncommitted file: the operator's runtime pin in `scripts/arm_week_timers.sh` (leave it) |
| Cloud Run job `project-slate` (hourly projections) | image `nfl-dfs@sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758` | runs the pre-repair market code: DK-PPG stand-in still live until rebuilt |
| Cloud Run job `build-features` | `nfl-dfs@sha256:8d9b3cb55865edc66c99e01b28a7a6ba0d588458ac921c1485069fac32814e03` | unchanged by this weekend's work |
| Cloud Run jobs in us-central1 | 1000 (at the JobsPerProject quota) | never create a job; reuse and `--args` |
| BigQuery | project `nfl-predictions-503414`, datasets `nfl_raw`, `nfl_features`, `nfl_predictions` | `market_source_log` will be created by the first repaired run (WRITE_APPEND) |
| host timers | none active (the Week-2 transient units ended) | Week 3 is armed by the laptop's `arm_week_timers.sh 3 --run` after its preflight |
| DK exports | `/home/erich/week2-sunday/ENTERED/` (entries, standings zips + CSVs) | never committed, never copied into handoff packages |

Cloud Scheduler (us-central1) at the time of writing, ENABLED: s-backup 07:00 daily; s-cfb 10/14/18 daily; s-cfb-sat;
s-contests 10:00 Wed-Sat; s-contests-sun 06-11 Sun; s-dk hourly Wed-Sun; s-features Tue 06:30; s-features-sun 05:30-10:30
Sun; s-freshness 08:00 daily; s-nflverse 05:00 daily; s-odds 09:00/15:00 Wed-Sun; s-project-su hourly 06-11 Sun;
s-project-tu Tue 09:30; s-props 09:30 Wed-Sun; s-score Tue 08:00; s-shadow-cbwu-oi-paired early/late Sun; s-train Tue
07:30; s-trends Wed 11:00; s-us-dfs 10:30 Wed-Sat; s-us-dfs-sun; s-weather 08:00 Fri-Sun. PAUSED (do not resume without
the gate decision): s-features-route, s-freeze-tail early/late, s-shadow-archetype-paired, s-shadow-cbwu-volume,
s-shadow-k1 early/late, s-shadow-k1-nofloor, s-shadow-k1-roleunion early/late, s-shadow-k1-route-roleunion early/late,
s-shadow-k3 early/late, s-shadow-sis-pass-tail-paired, s-tabpfn-sis-pass-tail control/treatment, s-train-k1,
s-train-k1-role, s-train-k1-route, s-train-k1-route-role. The Route Share pair is the operator's Monday decision
(command sheet section 3); the SIS pass-tail pair waits on the gate document (draft on the rules branch).

## 2. What was wrong in Week 2 and what has been done

Full analysis: `reports/2026-09-21-week2-post-mortem.md`. The causes, in order, and their status:

1. **Prop-name ambiguity drop + DK-PPG stand-in (the Jefferson 25.3).** Introduced 2026-09-04 (5878c841); served
   25.3 = 0.45 x 18.1 + 0.55 x 31.2. FIXED on the market repair branch: ambiguous spellings resolve to the one id on
   the slate; the live market is props or nothing; a slate name in the feed that does not match stops the run; every
   row's source goes to `market_source_log`; inventory source-set v8. NOT DEPLOYED until the image is rebuilt (section 4).
2. **Concentration (six players at 25-57%, all busted).** Exposure sheet built (flags every player over 15% with the
   reason it needs); selection-only cap / market-pull / row-shape arms built for the Week-3 shadow. No live cap: the
   operator decides after the paired shadow. The chain does not yet run the sheet automatically; run it by hand before
   upload (section 5) until the laptop wires it.
3. **Chalk faded on a week chalk hit.** Descriptive; chalk-parity flag on the sheet; ownership-model note below.
4. **Selector inversion.** Stored `sel_mean` (the incumbent bank) correlated -0.49 with realized; corrected HSIM
   -0.09; pooled -0.33 (laptop's attribution). No weight change from one slate; the paired dual_emax vs ladder016
   shadow stays the primary Week-3 test; component attribution is a labs item.
5. **Standings capture rejected the exports.** FIXED on the capture branch (twelve of twelve validate); the typed
   result class (`contest_metadata_unconfirmed` / `entries_invalid` / `entries_complete_ownership_incomplete` /
   `ownership_mismatch`) and the `--failure-manifest` JSON (settled entry evidence recorded even when the ownership
   summary fails; nothing partial loaded; frozen receipt contract unchanged) are built. Nothing has been applied: run the apply
   commands (command sheet 2a) after DK's Monday scoring review, from a checkout that includes the capture branch.
6. **Instruments that were blind:** the divergence shadow logs only prop-sourced rows (still true; the market-source
   log now covers every row); `own_shadow` is written only by production's `live_lineups` build, which does not run
   in-season because the lab builds the book, so it is not a Week-2 defect but it is not a monitor either.
7. **Behaviour change to be aware of:** DST rows are now model-only (they were 0.45 model + 0.55 DK PPG). The laptop
   was asked to confirm or choose a DST market that is not a one-game PPG.

Pending (not started or not finished): the point-in-time weather shadow (precipitation probability now plumbed
through on `production/weather-precip-plumbing-20260921`; audit ING-002); the rest of the laptop's end-to-end audit
queue (`handoffs/2026-09-21-end-to-end-week2-audit.json` on nfl2 `review/prereg101-reply-20260918`: credential-failure
telemetry, strict-prior support receipts, salary-week regression fixtures, candidate-pool sidecars, row-level
regeneration lineage, upload-manifest telemetry); the cross-season window audit (done as a bounded read; a repair only
with a reproducer and a retrain cycle); the typed capture result class; the chain-level provenance gate (`production_rows >
0`, TabPFN target-week cache identity, `market blend source: props`) in the laptop's `run_week_build.sh` preflight;
wiring the exposure sheet into `sunday_after_build.sh` before the ENTER publication; the QB availability contract
repair (design on the rules branch, `2026-09-19-qb-availability-contract-repair-design.md`).

## 3. The weekly cadence (what runs when, who does what)

Times are Central. Authoritative list of inputs: `reports/2026-09-15-week2-operating-handoff.md` section 3a and
`reports/2026-09-21-monday-command-sheet.md`.

- **Monday/Tuesday:** DK standings and contest-history exports (operator, browser) -> `nfl-dfs capture-dk-standings`
  validation then `--confirm-settled --confirm-full-field --apply` (assistant, from a checkout with the capture
  branch); nflverse Week-N load (s-nflverse 05:00 daily) -> `week3_shadow_outcomes.py --i-confirm-outcomes-released`
  after the operator's release -> `week3_shadow_reader.py` on the entered book and the shadow books -> proper-score
  reader -> evidence record filled once. Operator gcloud lines for Route Share (command sheet section 3).
- **Tuesday:** s-features 06:30, s-train 07:30, s-score 08:00, s-project-tu 09:30 (cloud, automatic). Check the
  project-slate log for `market blend source: props` and, after the image rebuild, for `market-source log: N rows`
  and no `MarketMatchError`.
- **Wednesday:** paid-vendor capture `python -m nfl_dfs.ops.weekly_vendor_data verify-login` then `run --week W --skip-odds`
  (from a checkout with the vendor branch; the Route Share for the completed week W-1 imports append-once; the three
  Fantasy Points matchup reports need the vendor's week control to show W; the SIS pass-tail acquisition starts at
  week 5; an SIS plan runs only with `--sis-plan`); `tabpfn-gen` with `TABPFN_UPCOMING=2026:3` (GPU job; run by the
  operator/laptop after build-features; the Week-2 miss was defect 24). s-trends 11:00. The SIS login
  (`sis_downloads login --terminal-credentials --fresh`) is the operator's interactive step; SIS sessions last days,
  Fantasy Points longer.
- **Wednesday-Saturday:** s-props 09:30, s-odds 09:00/15:00, s-dk hourly, s-contests 10:00, s-us-dfs 10:30, s-weather
  Fri-Sun 08:00. Vendor captures (SIS, Fantasy Points) per the operating handoff; ETR never landed.
- **Saturday:** operator inputs due before 10:30: `contests.json` (Week-3 contests, entries, order), `$OUT/chosen-dose.env`
  (fail-closed if absent), the approved lab release SHA (`--expect-sha`), refresh receipts. `arm_week_timers.sh 3
  --run` (laptop) preflights and arms the build (D12800 ~16 h), the watchers (persistent unit) and the Sunday chain.
  After the build: `run_week3_shadow.sh` (RUN_WEEK3_SHADOW=1; D12800 only) writes the shadow books outcome-blind.
- **Sunday:** 05:30-10:30 s-features-sun / s-contests-sun / s-project-su hourly; the chain `sunday_after_build.sh`
  (qb_classify -> vet_book -> vet_replace_v4 with the fresh DK status feed -> emit -> sequential ENTER layout ->
  verify_enter_bundle -> atomic bundle swap), then `run_promotion.sh` (frozen mean first-entry rule; class E, the
  operator's call each week) and `relayout_enter.sh`; with the lineage branch merged the chain then runs
  `regeneration_lineage.py` and `exposure_sheet.py` on the final book and writes both results into the TODAY file; the entries watcher fills the newest `DKEntries*.csv` export
  (loop ends 16:58Z); the operator uploads the filled CSV before 12:00 CT lock (11:15 target); the late-inactives
  watcher runs to 20:25Z; `apply_swaps.py` v1.1 for late swaps (fresh-feed presence check, refuses locked games).
  **New this week: run the exposure sheet on the promoted book before upload and read every flag to the operator.**
- **Never:** resume paused schedulers without the gate decision; create Cloud Run jobs; push to main from the
  assistant (the classifier refuses; hand the operator the one-line command); commit DK exports.

## 4. Deploying the market repair (must happen before the Week-3 batches matter)

1. Review and merge `production/prop-name-ambiguity-and-fallback-guard-20260921` (and the capture branch) onto the
   wiring branch or main. The inventory v8 must travel with it (tests enforce the hashes).
2. Build the image from the merged commit (cloudbuild runs the full suite first):
   `gcloud builds submit --config cloudbuild.yaml --project nfl-predictions-503414 --substitutions _IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week3-market-source,_CODE_SHA=$(git rev-parse HEAD)`
3. Point the projection job at it (operator/laptop; the workstation assistant is not permitted to run job updates):
   `gcloud run jobs update project-slate --project nfl-predictions-503414 --region us-central1 --image us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week3-market-source`
4. Verify on the next hourly run: log lines `prop market names: ... resolved by the slate`, `market blend source: props
   (N/M rows)`, `market-source log: M rows (...)`; a `MarketMatchError` means a slate name in the feed did not match,
   which is the intended stop: fix the name, do not add a stand-in. Then `SELECT source, COUNT(*) FROM
   nfl_predictions.market_source_log WHERE season=2026 AND week=3 GROUP BY 1` should show props for most skill rows,
   model_only_no_line for the unpriced, model_only_dst for defenses.
5. If the job fails for a reason other than a match miss, the previous batch stays served; that is visible in the job
   status, not silent. Do not restore the stand-in.

## 5. Tools the Sunday operator relies on (all tracked, all tested)

- `scripts/exposure_sheet.py --book BOOK.csv --frame frame.parquet --contests contests.json --out DIR [--season 2026
  --week 3 | --market-source-csv ...] [--draft-group ID | --status-csv ...] [--field-own-csv ...]` (market repair branch):
  flags over_30, majors_over_20, dst_over_20, injured_over_10, no_line_over_5, market_gap. On the entered Week-2 book
  it flags exactly the six players that busted.
- `scripts/week3_shadow_runner.py` / `scripts/week3_shadow_reader.py` / `scripts/week3_shadow_outcomes.py` (arms and
  outcomes branches; the runner needs the clean lab clone and `--expect-sha`).
- `scripts/rehearse_final_path.sh RUN_DIR CLONE OUT_DIR WEEK CONTESTS` (wiring branch): the Sunday chain on an archived
  artifact with a synthetic entries template; green on 5f8f61a5 on 2026-09-20 and on the merged integration tree
  387b1e47 on 2026-09-21 02:03Z (52 rows replaced with the live DK feed, promotion and relayout published, 97 rows
  filled, 12 contests validated; reply-branch note 4) and again on a29f727f at 02:22Z with the lineage check and the
  exposure sheet wired in (lineage OK; sheet produced with its 'monitor not deployed' header; note 6). Rehearsal flags
  `--test-exclude-dk` / `--no-fresh-dk` must never reach the operational chain.
- `/home/erich/week2-sunday/apply_swaps.py` v1.1 (sha 2a1750c8...): late swaps; refuses locked games and illegal
  rosters; requires the fresh feed.
- `nfl-dfs capture-dk-standings` (capture branch): validation, then apply with the two confirmations.
- `scripts/check_prospective_gates.py --week N` (operational worktree): the frozen pre-lock gates; the three Route Share
  FAILs are known and accepted until the operator's Monday decision.
- `scripts/check_build_inputs.py --season 2026 --week N --chosen-dose $OUT/chosen-dose.env --contests $OUT/contests.json
  [--receipt PATH]` (market repair branch): the money-build input gate (projection batch freshness and coverage, the
  market-source monitor, the TabPFN cache for the target week, the dose file and contests.json); exit 1 stops the
  laptop's preflight; it FAILs today because the monitor is not deployed and the Week-2 batch is stale.
- `scripts/check_market_monitor.py --season 2026 --week N` (market repair branch): the latest projection batch's market
  sources (age, props share, model-only players); FAIL until the repaired image has run. Run it Tuesday after the
  first repaired batch, before the Saturday build and before the Sunday chain.
- `scripts/regeneration_lineage.py` (lineage branch): row-level proof of the Sunday regeneration; the chain runs it
  after promotion; run it by hand with `--entries-csv` on the operator's post-upload DK export.

## 6. Unresolved risks, in the order they can hurt

1. The projection job still runs the stand-in until the image is rebuilt (section 4). Every Week-3 batch before that
   carries the Week-2 defect class.
2. The props-or-nothing rule stops a run on a feed-present name miss. Expected and wanted; but it means a batch can be
   missing for an hour on a Tuesday if a new rookie collides with a star's name. The stop names the player; the
   resolution is the slate-preference rule, which already covers "one of the two is on the slate"; the residual case
   (both on the slate) needs a manual alias.
3. DST model-only (section 2, item 7) has not been reviewed by the laptop.
4. No live exposure cap exists; the sheet is a monitor. If the operator wants a cap for Week 3 it must be a chain
   step before ENTER, on the delivered selector, with the runner's `cap20`/`cap30` law; nothing untested goes on an
   entered book.
5. The capture apply for Week 2 has not been run; the field-calibration harness has no Week-2 rows until it is.
6. Cross-season windows: unresolved; Week-3 `_l4` features are two-game windows.
7. Cloud Run us-central1 is at 1000 jobs.
8. The lab release for Week 3 must be pinned (`--expect-sha`); the runner fails identity otherwise (exit 2).
9. Watchers: the persistent unit is on the wiring branch; the Week-2 failure mode (transient service killed its
   children) must not recur; verify the three processes after arming.
10. The QB availability contract (backup QBs at starter means) is handled Sunday by the classifier tools, not repaired
    in the projections.
11. Offline tests had been writing synthetic rows into `own_shadow` (18,185 rows, season 2024 week 3, since 2026-08-14) and,
    tonight, into a new `market_source_log`, through the best-effort monitor writers on machines with credentials. Both
    cleaned on 2026-09-21 (`market_source_log` dropped, 18,185 synthetic `own_shadow` rows deleted; only the 2,370 real
    2026 W1 rows remain); `tests/conftest.py` on the market repair branch records every `nfl_dfs.bq.load_dataframe` call
    instead of executing it. Any grade of a shadow table must filter to real seasons/weeks and real names until every
    checkout carries that guard.
12. `own_shadow` and the divergence shadow are not monitors in-season; `market_source_log` is the only per-row market
    monitor. The ownership input the lab generator consumes is the lab's naive fade; the booster does not run live.

## 7. Readiness checklist for Tuesday (confirm each, in writing, on the reply branch)

- [ ] BigQuery read/write to `nfl-predictions-503414`; GCS read; `gcloud run jobs describe` and `gcloud scheduler jobs
      list` work; `gcloud builds submit` and `gcloud run jobs update` are available to the person who deploys.
- [ ] Checkouts at the commits in section 1; `git status` clean except the operator's runtime pin.
- [ ] `pytest` green on the merged tree for the affected modules (200 passed on 387b1e47, reply-branch note 3); the
      full suite runs in cloudbuild before any image.
- [ ] Image digests of `project-slate` and `build-features` read from the console and compared with section 1 and
      with the rebuilt image after section 4; then `scripts/check_market_monitor.py --season 2026 --week 3` reports OK
      on the first repaired batch.
- [ ] `scripts/exposure_sheet.py` run on the entered Week-2 book (`/home/erich/week2-sunday/after-K97-...-1048/paid-vetted-promoted/book.csv`
      + the run frame + `contests.json`) reproduces the six flagged players.
- [ ] `scripts/rehearse_final_path.sh` green on the merged tree (done 2026-09-21 02:03Z on 387b1e47; repeat on the
      tree you actually deploy); the three watcher processes verified after arming.
- [ ] Monday: standings apply for the twelve contests; contest-history export for winnings; outcomes builder and
      reader; evidence record filled once.
- [ ] The operator's Saturday inputs (contests.json, chosen-dose.env, lab release SHA, refresh receipts) requested by
      Friday evening; exposure sheet read to the operator before every upload.
- [ ] The poll/handoff channel: fetch both remotes (plain `git fetch -q --all`, never `--prune`), reply on
      `lab/workstation-reply-bank991-20260918` from a detached scratch worktree, never from the cohort or running-bank
      worktrees.

## 8. Where things are

- Reports (rules branch): post-mortem, evidence record (Realized table filled from the standings; nflverse items
  TODO), Monday command sheet (section 2a: capture), Week-2 supplier scorecard (corrected-HSIM marginal best; props
  best external, receivers only; no paid source scorable), season-window audit, SIS pass-tail gate draft, data-source
  value map, stack-depth read, Week-1 field ownership read, QB availability repair design, this handover.
- Reply branch (nfl2): all handoff notes (`handoffs/2026-09-2*`), receipts (`handoffs/receipts/2026-09-21-week2-post-mortem/`:
  contest field summary, our 97 results, player signals, pool realized, standings ownership + FPTS, top-100 lineups
  without user identifiers, top-10 features, games, regeneration rows, capture validation log, the Week-2 exposure
  sheet), tools (`handoffs/tools/apply-swaps-v1.1/`, `projection-floor-repro/`).
- Memory of the workstation assistant (not authoritative): `/home/erich/.claude/projects/-home-erich-projects-nfl-predictions/memory/`.
- Sunday live outputs: `/home/erich/week2-sunday/` (books, bundles, logs, page generator); raw DK exports under
  `ENTERED/`.

## 9. Operating constraints (the ones that bit, verbatim)

- No silent fallbacks (operator, 2026-09-20). Fail closed; monitor any stand-in per row.
- Never commit DraftKings entry keys, cookies, user identifiers or entries exports; handoff packages carry names,
  salaries and draftable ids only.
- Never weaken a leakage check; never enter an untested rule on an entered book; never put a script name in a
  `pkill -f`; never commit, pull, rebase or switch branches in a worktree whose bank is running; the release worktree
  stays clean at its pinned commit.
- The harness classifier refuses pushes to main, production Cloud Run job execute/update, systemd unit writes,
  create-once publishes and `git fetch --prune`: print the exact one-line command for the operator, never route around.
- Laptop-owned files (`arm_week_timers.sh`, `week_env.sh`, `run_week_build.sh`, `run_week_watchers.sh`): send
  requirements as text.
- Current-week outcomes are not read before the operator's release; the release is his message, recorded in the
  evidence record.
- Frozen-chain rules 1-6 in CLAUDE.md, especially: smoke against real artifacts before freezing; conscious inventory
  revisions (source-set v8 is the pattern); reuse Cloud Run jobs.
