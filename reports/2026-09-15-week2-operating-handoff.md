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
| Production `main` | `cc392bf8` (Commit B + FTN tolerance + refreshed CLAUDE.md/AGENTS.md + `cloudbuild.focused.yaml`). Pushes to `main` need the operator. |
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

## 2. What is running right now (2026-09-16 15:45Z, Wednesday) — and the take-over checklist for the next model

**Host processes (this workstation, WSL, 54 GB visible after the 2026-09-16 `.wslconfig` change to 56 GB).** All are
detached (`setsid nohup`), survive the assistant session, and die only with WSL. Verify each with `ps -p <pid>`; pids
are as of 15:45Z — trust the pid FILES over these numbers.

| process | pid / pid file | what | logs | if dead |
|---|---|---|---|---|
| PREREG-099 host driver v2 | `results/run_119_local.pid` in `/home/erich/projects/.nfl2-worktrees/prereg099-supply12800-20260916` (50016) | waits for the running gate process, applies the frozen gate check, then bank 990 (72 slates, 10 workers) | `results/run_119_local.log`, `results/run_119_local_tasks.log`, `results/119_local/<run id>/tNN.log`; run ids in `results/run_119_local_runs.log` | rerun `setsid nohup scripts/run_119_local_v2.sh 10 > results/run_119_local.log 2>&1 < /dev/null &` from that worktree — attach-aware (skips slates already in the bucket) |
| PREREG-099 mechanics gate | python pid 2337 (child of the superseded driver; `pgrep -f "119_dose12800.py --bank=990 --mechanics-only"`) | full-scale 12,800 stream + one 6,400 verify build on 2023-W1, started 11:16Z, expected 8–10 h | `results/119_gate.out`; uploads `gs://nfl-2-506823-lab/results/119_dose12800/119m990r1-20260916T111557Z/result-t00.json` on success | if it died before uploading, the v2 driver starts a fresh gate itself |
| DraftKings host pull loop | `/home/erich/week1-sunday/host_ingest_dk_loop.pid` (4129) | hourly `ingest-dk` + `ingest-contests` from the host (Cloud Run is 403-blocked, defect 18); the script exports `GCP_PROJECT` itself (defect 19) | `/home/erich/week1-sunday/host_ingest_dk_loop.log` — a healthy hour shows "Loading N rows into nfl-predictions-503414.nfl_raw.dk_salaries" and "Polled N contests" | `setsid nohup /home/erich/week1-sunday/host_ingest_dk_loop.sh > /home/erich/week1-sunday/host_ingest_dk_loop.log 2>&1 < /dev/null &` |
| D6400 timing rehearsal | `pgrep -f rehearse_6400` / live_week python 56011 | K90 live build at lev 1280 / boom 5120 on group 153428, started 14:45Z | `/home/erich/week2-rehearsal/rehearse_6400.log` (prints `exit <code> <time>` and the run dir name); receipt `seconds` in `<CLONE>/results/live/2026-w02/<dir>/receipt.json` | rerun `/home/erich/week2-rehearsal/rehearse_6400.sh` |
| D12800 timing rehearsal (queued) | `pgrep -f rehearse_12800` (59447) | waits for the 6,400 rehearsal's `exit` line, then lev 2560 / boom 10240 (expected 6.5–8 h) | `/home/erich/week2-rehearsal/rehearse_12800.log` | rerun `/home/erich/week2-rehearsal/rehearse_12800_after_6400.sh` |

The assistant session's hourly poll (a session-only cron) dies with the session: **the next model must re-establish a
periodic check** of the five rows above (every hour is enough) and act on the "if dead" column.

**Cloud.** Both lab jobs idle on the prereg09u image (`ee5fe3c…`); the prereg09v image (`prereg09v-b8424efb35b2`, build
7c4673e8) exists as the PREREG-099 cloud fallback (`scripts/arm_119.sh` in the 099 worktree) — not used. Production
cadence: Wednesday `ingest-nflverse-5jzrf` 10:00Z ✓ with the FTN tolerance (2,675 charting rows); s-dk executions on
Cloud Run keep failing by design (defect 18) — ignore them while the host loop runs; s-contests / s-trends are Cloud
Run too and also 403 (the host loop covers contests). The alarm that matters remains a failed `project-slate` after
Sunday 06:00 CT.

**Take-over checklist (first hour on this machine).**
1. `git -C /home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912 log --oneline -3` — this branch
   (`production/week1-audit-adjust-20260912`) carries every Week-2 script and this document, and since the 2026-09-16
   merge commit a0699e40 it contains `origin/main` (cc392bf8) — the operator fast-forwards main with
   `git -C /home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912 push origin HEAD:main` (the
   classifier refuses that push for the assistant). The main checkout `/home/erich/projects/nfl-predictions` is DIRTY
   and on an old branch (`production/test-lanes-and-factorial-drift-20260911`): never work there; its `.venv` is fine
   to use with `PYTHONPATH=<worktree>/src`. If main has not been fast-forwarded yet, `git show origin/main:HANDOFF.md`
   is stale — read this branch's copy.
2. Read `HANDOFF.md`'s newest entry (2026-09-16), then §3 below for the day you are on, then §4 before Sunday.
3. Check the five host processes above; restart per the table.
4. Set up an hourly check (a cron prompt, a loop, or whatever the harness offers). Include: PREREG-099 driver/tasks,
   the DK loop's last pull, the rehearsal logs, and from Saturday `systemctl --user list-timers | grep nfl-week2`.
5. When `results/run_119_local.log` says "done": read PREREG-099 exactly once (§6.3) and record it. When
   `rehearse_6400.log` / `rehearse_12800.log` print `exit 0`: record the receipt `seconds` in §4.1 and in HANDOFF.md
   as the measured build times; if 12,800 exceeds ~7 h, tell the operator the 01:30 CT start is too late and move the
   timer earlier (the timer script's `01:30` and the `tag 06:30` UTC label must both change).
6. Thursday/Friday: nothing else is required from the model except the Friday PREREG-099 read and the operator's
   12,800 go/no-go (§3). Saturday: print `scripts/arm_week_timers.sh 2` for the operator to run; verify the timers.
7. Never: commit `ENTERED/` exports or entry keys; push to main; publish; edit a running bash script in place (copy to
   a new file, as `run_119_local_v2.sh` was); put a script's own name inside a `pkill -f` on the same command line.

---

## 3. The week, day by day

### Tuesday 09-15 (today)
- [x] Production Tuesday jobs verified (above). `ingest-nflverse` FTN 404 tolerance implemented and its image built (§9 #14; `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:8966bc14029f…`). **Operator:** run the two commands recorded in HANDOFF (job update; main fast-forward), then confirm Wednesday's scheduled run exits 0.
- [ ] 098 r2 read + LEDGER row when terminal (§2).
- [ ] Direct runner read + report (§8).
- [ ] 097 repairs after 098 (§6.4), then `scripts/prereg097_report.py`, LEDGER row.

### Wednesday 09-16 — DONE (this document's date of record)
- Every cohort read (097 saturation at 3200; 098 negative; PREREG-100 vetting null / Q-flags under-deliver); synthesis
  `reports/2026-09-16-findings-since-week1-synthesis.md`; tail-calibration draft awaiting sign-off.
- PREREG-099 (12,800 supply rung) moved to the workstation, one bank (amendments 1–2); gate running (§2).
- Week-2 Sunday-main draft group **153428** (658 players); DK pulls by the host loop only (defects 18/19).
- **Operator decisions taken today (protocol overrides, recorded in §4.1):** the Week-2 dose plan (D6400 intended
  entry, D12800 early candidate, D3200 and D800 fallbacks; four timers); the `top` ENTER layout; entries reserved
  (33 / $206: Millionaire 1, SUPERSatellite 2, Huddle 1, Pylon 1, Nickel 5, Flea Flicker 23); `contests.json` filled;
  the operator stays on this workstation through Week 2 (the machine move in §11 is deferred).
- Build chain reworked and rehearsed end to end on the real entries export (§4.1); D6400 / D12800 timing rehearsals
  running (§2).

### Thursday 09-17
- Read the timing rehearsals' receipts (§2 step 5) and confirm or move the 01:30 / 05:30 CT timer slots.
- s-trends / s-contests on Cloud Run are 403 (defect 18): the host loop's `ingest-contests` covers the lobby.
- Optional: the operator's sign-off on `reports/2026-09-16-prereg-tail-calibration-DRAFT.md` (a lab cohort that
  cannot start before PREREG-099 leaves the workstation's cores; it is not on the Week-2 path).

### Friday 09-18
- PREREG-099 read when `run_119_local.log` says "done" (expected Friday evening): `cd <099 worktree> && PYTHONPATH=src
  /home/erich/projects/nfl2/.venv/bin/python scripts/prereg099_report.py <RUN990> > PREREG-099-read.txt`, record in
  `PREREG-099.md` + `LEDGER.md`, commit on the 099 branch, push. Its secondary "proxy K80 D12800 − D6400" is the only
  book-level evidence the operator has for the 12,800 go/no-go; report it plainly with its W/L and interval.
- Ask the operator: is D12800 still an early candidate for Sunday (yes → keep the 01:30 CT timer; no → drop that line).
- If the PREREG-099 bank is still running Saturday night, stop it (`kill $(cat results/run_119_local.pid)` plus the
  worker pythons `pkill -f "119_dose12800.py --bank=990$"` from a separate command) so Sunday's builds have the cores;
  it resumes later with the same command (attach-aware).

### Saturday 09-19
- Print `scripts/arm_week_timers.sh 2` and have the operator run the five lines; then `systemctl --user list-timers
  --all | grep nfl-week2` must show all five. `WIN_DOWNLOADS` in `/home/erich/week2-sunday-watchers.sh` is
  `/mnt/c/Users/Erich/Downloads` (the entries export already sits there as `DKEntries-2026-09-16.csv`; the watcher
  takes the newest `DKEntries*.csv`).
- Confirm the DK loop pulled within the hour and `week_env 2` still resolves to group 153428.

### Sunday 09-20 (§4)
### Monday 09-21 / Tuesday 09-22 (§5)

---

## 4. The Sunday money path, in full

### 4.1 Arming the build (do on Thursday, verify Saturday) — FIXED 2026-09-15

The Sunday path is now week-parametrised. One env file derives everything (`scripts/week_env.sh`): season, week,
`WEEKDIR` (`2026-w02`), the Sunday date, lock (12:00 CT), late-window cutoff, the output dir `/home/erich/week<W>-sunday/`,
and the **draft group**, auto-detected by `scripts/find_main_draft_group.py` (the largest group in the latest salary
pull whose games run from Sunday 12:00 CT to no later than 16:30 CT; Week 1 resolves to 151307) unless given
explicitly. The tracked scripts and their Week-1 originals:

| Week-2 script (tracked, `scripts/`) | replaces | what changed |
|---|---|---|
| `week_env.sh` | scattered constants | single source of week facts; overrides must be `export`ed before `week_env` |
| `find_main_draft_group.py` | hard-coded 151307 | detects the Sunday-main group from `nfl_raw.dk_salaries` |
| `sunday_runbook.sh` | `week1_sunday_runbook.sh` | env-driven build/verify; the Week-1 governed publisher is **off** unless `PUBLISHER=1` (its module family is Week-1-specific down to the allocation id) |
| `sunday_build_host.sh` | host `week1-sunday-build.sh` | env-driven; per-contest emits from `contests.json`; `REUSE_PAID_DIR/REUSE_SHADOW_DIR/REUSE_K90_DIR` for rehearsals |
| `sunday_after_build.sh` | host `learned_after_build.sh` | vetted paid book → ENTER layout from `contests.json` → `TODAY-30-LATEST.md`; learned scorer removed (PREREG-096 REVERT) |
| `sunday_watch_dk_entries.sh`, `sunday_watch_late_inactives.py` | host watchers | env-driven |
| `arm_week_timers.sh W [--run]` | one-shot timer | prints (or arms) the transient user timers: **01:30 CT D12800, 05:30 CT D6400, 09:10 CT D3200, 10:50 CT D800 (T-70), 09:12 CT watchers** (Week-2 dose plan, operator decision 2026-09-16) |
| `contests.template.json` | contest ids in scripts | the week's contests: `name, contest_id, entries, keep` |

Host wrappers (untracked, already written): `/home/erich/week2-sunday-build.sh`, `/home/erich/week2-sunday-watchers.sh`,
and `/home/erich/week2-sunday/contests.json` (currently the template with `REPLACE` markers — the driver refuses to
run until the operator's Week-2 contest ids and entry counts are filled in after he reserves entries).

**Week-2 dose plan (operator decision 2026-09-16 — a protocol override, recorded so it is not mistaken for an untested
rule).** Evidence: PREREG-097 D6400 vs D3200 on the K80 book: proxy +0.005 near miss (32 W / 36 L) but raw best-of-book
+1.2 [+0.3, +2.0] and weeks ≥ 200 / ≥ 210 11 → 16 / 4 → 7; D6400 vs D800 PASS. Nothing measured says 6,400 hurts; the
strict gate was a near miss. 12,800 has no book evidence until PREREG-099's Friday read (its reader reports a
one-bank K80 comparison as a secondary). Plan: four builds Sunday, each with its own run tag and run dir, the operator
picks the book Sunday morning from whatever completed — **D6400 is the intended entry**, D12800 the early candidate (use
only if Friday's read favours it and the build completed), D3200 the fallback, D800 the T-70 fresh-salary fallback.
Measured build times on this machine (single stream, receipt `seconds`): D800 244 s, D3200 3,040 s (Week-1 receipts);
**D6400 7,674 s = 2 h 08 min** (rehearsal 2026-09-16 14:44–16:52Z on group 153428, run dir
`20260916T144448044783Z-e7255e9`, 6,400 candidates, 90 written, exit 0) → the 05:30 CT timer yields the D6400 book by
≈ 07:40 CT; D12800 rehearsal started 16:53Z (expected ≈ 6–7 h by the 2.5× step from 3200→6400; if it exceeds ~7 h,
move the 01:30 CT timer earlier).
`sunday_build_host.sh` now takes the dose from `PAID_LEV/PAID_BOOM` (env or `/home/erich/week2-dose.env`, which holds
640/2560), skips the governed pair with `SKIP_PAIR=1`, and identifies its run dir by receipt (concurrent builds write
`LATEST` at start, so `LATEST` is never trusted). The 10:30 CT inactives are applied to the chosen book by the
scratch-swap tools; a book is never rebuilt after 10:50 CT.

**ENTER layout (Week 2): `top` — every contest receives the vetted book's first N.** Contests pay independently and the
selector's greedy order makes ranks 1..N its best book of size N. Descriptive check (2026-09-16, one bank of the
PREREG-097 D3200 K80 books, 65 slates, Week-2 contest sizes, versus the Week-1 sequential layout's rank ranges in this
contest order): Nickel (5) mean best 158.5 vs 148.4 (+10.1, 40 W / 25 L; weeks ≥ 194 6 vs 0), Flea Flicker (23) 171.9 vs
169.8 (+2.1, 29/16/20 ties), SUPERSatellite (2) +2.6, Huddle (1) +6.4, Pylon (1) −3.6 (rank 1 vs rank 5, single lineups,
noise), Millionaire identical. Mean lineup points by rank: 1–5 124–126, 6–10 119, 11–80 117–119. Not a frozen gate; the
Week-1 unique-across-contests layout is `ENTER_LAYOUT=sequential`. Operator: "proceed as you suggest" (keep `top`).

**Thursday checklist**
1. `cd <audit worktree> && source scripts/week_env.sh && week_env 2` — must print the detected group (needs the
   Week-2 salary pull; if it fails, the pull has not happened yet or the group needs `week_env 2 <id>`).
2. Fill `/home/erich/week2-sunday/contests.json` from the operator's reservations.
3. Rehearse the full path once: `export OUT=/home/erich/week2-rehearsal; week_env 2; RUN_TAG=rehearsal-$(date -u +%Y%m%dt%H%Mz)-e7255e9
   scripts/sunday_build_host.sh` (≈ 25 min: D800, D400, K90 builds + vetting + emits) then
   `scripts/sunday_after_build.sh once <K90 dir> rehearsal` and read `TODAY-30-LATEST.md` and `ENTER/`. The live
   builder refuses a lock that has passed, so rehearsals need the coming Sunday's group (a Week-1 rehearsal on
   2026-09-15 proved everything downstream of the builds on last Sunday's run dirs via the `REUSE_*` overrides).
4. Have the operator arm the timers: `scripts/arm_week_timers.sh 2` prints the five `systemd-run` lines (or `--run` arms them).
5. Saturday: `systemctl --user list-timers | grep nfl-week2` shows all five; Downloads path in
   `sunday_watch_dk_entries.sh` (`WIN_DOWNLOADS`) is right; the operator has reserved entries with a placeholder.

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
| 14 | `ingest-nflverse` exits non-zero on the missing `ftn_charting_2026.parquet` after loading the rest | fixed and deployed 2026-09-15 20:15Z (`ingest-nflverse` generation 37, focused-lane image); verify Wednesday's scheduled run exits 0 | deployed, verify Wed |
| 15 | `nfl-week1-sunday-build.sh` / runbook hard-coded to Week 1 (week, group 151307, `2026-w01`, tag suffix, publish root) | week-parametrised scripts + `arm_week_timers.sh` (§4.1); Thursday rehearsal + operator timer arming remain | fixed in code; Thursday steps open |
| 16 | Cloud Run "Internal error running task" losses on the lab lanes (23–51 retries per bank) | repairs per §6.4 | recurring |
| 17 | The standard production build (`cloudbuild.yaml`, full suite before the image) cannot complete from `main`: on 2026-09-15 the suite ran 3 h to 77 % with failure blocks at 72–75 % (the frozen-factorial drift, defect-log 2026-09-11) and hit the build ceiling; the 2026-09-13 week1 build took 4.5 min from the week1 branch | `cloudbuild.focused.yaml` (`_TESTS` lane, disclosed deviation) for narrow fixes; the real remedy is the operator's drift decision + the test-lanes branch `production/test-lanes-and-factorial-drift-20260911` (`scripts/test_lanes.sh`) | **open, operator decision** |
| 19 | Host DK loop inherited no `GCP_PROJECT` from a fresh shell after the WSL restart → the code's default project (`nfl-dfs-prod`) → every pull 503 | `host_ingest_dk_loop.sh` now exports `GCP_PROJECT=nfl-predictions-503414` itself | closed 2026-09-16 11:25Z |
| 20 | `fill_dk_entries.py` carried a hard-coded Week-1 contest map (Sunday's fill would have matched nothing) | reads `--contests contests.json` (or `$CONTESTS_JSON`); the watcher passes it; tracked copy `scripts/fill_dk_entries.py` | closed 2026-09-16 |
| 21 | `live_week.py` writes `LATEST` when a run STARTS, so concurrent Sunday builds would mis-identify their run dirs | `sunday_build_host.sh` finds its run dir by receipt (lev/boom + build window), never by `LATEST` (`find_run_dir`); tested against Week-1 run dirs, not yet against two truly concurrent builds | mitigated |
| 22 | The leverage cut loop is superlinear (≈ 3.2× per doubling: 504 / 1,291 / 4,019 / 13,237 s at lev 160/320/640/1280 on the cloud) — every "2× per doubling" estimate in earlier notes is wrong | timings in §4.1; rehearsals measure D6400 / D12800 on this host | open (a parallel boom stream would not help; lev is sequential) |
| 18 | **DraftKings API returns 403 to Cloud Run egress** (every scheduled `ingest-dk` execution since 2026-09-16 05:00Z; the identical request from the workstation returns 200) — no salaries/statuses/draft groups land from the cloud; Sunday's hourly `ingest-dk` and `ingest-contests-sun` are affected | stopgap: host loop `/home/erich/week1-sunday/host_ingest_dk_loop.sh` (hourly `nfl-dfs ingest-dk` + `ingest-contests` with `INGEST_CONTESTS_ENABLED=1`, from the audit worktree; pid in `host_ingest_dk_loop.pid`; started 09:45Z, 3,089 salary rows + 4,529 contests landed; **must run on whichever machine is on** — restart it on the laptop after the move); real fix = static egress (VPC connector + Cloud NAT) or move the DK pulls to a host timer permanently | **open, operator decision on the egress fix** |

---

## 10. File index (most used)

- Week-2 Sunday scripts (this branch, `scripts/`): `week_env.sh`, `find_main_draft_group.py`, `sunday_build_host.sh` (dose env/file, `SKIP_PAIR`, receipt-based run dir), `sunday_runbook.sh`, `sunday_after_build.sh` (`ENTER_LAYOUT=top|sequential`), `sunday_watch_dk_entries.sh`, `sunday_watch_late_inactives.py`, `fill_dk_entries.py`, `arm_week_timers.sh` (five timers), `contests.template.json`.
- Host Week-2 state (untracked): `/home/erich/week2-sunday-build.sh`, `/home/erich/week2-sunday-watchers.sh`, `/home/erich/week2-dose.env` (640/2560 = the 09:10 CT D3200 build), `/home/erich/week2-sunday/contests.json` (filled), `/home/erich/week2-sunday/ENTERED/DKEntries-2026-09-16.csv` (entry keys — private), `/home/erich/week2-rehearsal/` (timing rehearsals), `/home/erich/week2-rehearsal-chain/` (chain rehearsal; its `fill/REHEARSAL-…-DO-NOT-UPLOAD.csv` holds Week-1 lineups).
- PREREG-099 worktree `/home/erich/projects/.nfl2-worktrees/prereg099-supply12800-20260916` (branch `lab/prereg099-supply12800-20260916`): `PREREG-099.md` (+ amendments 1–2), `experiments/119_dose12800.py`, `scripts/run_119_local_v2.sh` (host executor), `scripts/prereg099_report.py` (one run id), `scripts/prereg099_mechanics_gate.py`, cloud fallback `scripts/arm_119.sh` / `queue_119.sh`.
- `reports/2026-09-16-findings-since-week1-synthesis.md` — every result since Week 1 with ranked next steps (read first).
- `reports/2026-09-16-prereg-tail-calibration-DRAFT.md` — the tail-calibration preregistration awaiting operator sign-off.
- lab `PREREG-099.md` (branch `lab/prereg099-supply12800-20260916`) — the 12,800 supply rung, launched 2026-09-16; lab `PREREG-100.md` (branch `lab/prereg100-practice-status-20260916`) — practice-status vetting, read 2026-09-16.

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

---

## 11. Moving to another machine (the laptop) — checklist (DEFERRED: the operator stays on this workstation through Week 2; the operator's guide is `reports/2026-09-15-workstation-to-laptop-transition-guide.md`)

Everything durable is on GitHub (both repos, every branch pushed) and in GCS/BigQuery. What is host-only, and what
assumes this host's paths:

**Do not power this workstation off while these are running** (they are not cloud jobs): the PREREG-099 host run,
the D6400 / D12800 rehearsals and the DK pull loop (§2). The direct paid-source runner and the 097 repairs are finished.
Cloud Run jobs, Cloud Build and schedulers are unaffected by the move.

**Copy to the new machine (same WSL username `erich`, same paths — the scripts default to `/home/erich/...`):**

| what | path | notes |
|---|---|---|
| Sunday tooling, drivers, results, logs | `/home/erich/week1-sunday/` (7 GB; skip `direct_runner/work/`) | keep `ENTERED/` private (DK entry keys) |
| Week-2 wrappers and contests | `/home/erich/week2-sunday-build.sh`, `/home/erich/week2-sunday-watchers.sh`, `/home/erich/week2-sunday/` | |
| DK exports for settlement | `/home/erich/projects/nfl-predictions/results/2026-09-13/` (224 MB) | local only, never commit |
| Launcher registry + monitor state | `/home/erich/.local/state/nfl-dfs/` (3.3 GB) | receipts reference this host's pids: adjudicate any live one after the move |
| Assistant memory | `/home/erich/.claude/projects/-home-erich-projects-nfl-predictions/memory/` | same project path on the new machine |
| Worktree archive | `/home/erich/worktree-archive/` (ignored `results/` of removed worktrees) | evidence only |

**Recreate on the new machine:** `gcloud auth login` + `gcloud auth application-default login` (account
`espechtsoftware@gmail.com`, project `nfl-predictions-503414`); `bq`; Python venvs (`pip install -e ".[dev,gcp,app]"`
in each repo; the lab venv in `~/projects/nfl2`); the worktrees you need (`git worktree add <path> <branch>` — the
active set is in §1; the Week-1 money-path clone must be exactly `e7255e9`); the user monitors under
`~/.config/systemd/user/` (tracked copies in `deploy/systemd/`, minus the sunday build timers which are one-shots
per week, §4.1). The Windows Downloads path in `sunday_watch_dk_entries.sh` (`WIN_DOWNLOADS`) may differ.

**Path assumptions to know:** `scripts/week_env.sh` defaults (`PROD`, `CLONE`, `TOOLS`, `OUT`) are env-overridable;
the abandoned source-v3 chain pins `/home/erich/projects/nfl-predictions` inside its image (irrelevant unless revived).

**Cleanup done 2026-09-15:** dead worktree entries pruned, every local-only branch pushed, and clean + fully pushed +
inactive worktrees removed in both repos (logs `/home/erich/week1-sunday/cleanup_production.log`, `cleanup_lab.log`;
plans `worktree_plan_production.txt`, `worktree_plan_lab.txt`). Kept: the active set (§1), dirty worktrees
(their uncommitted changes were not judged here), detached worktrees whose commits are not on origin.
