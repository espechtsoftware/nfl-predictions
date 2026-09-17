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
| PREREG-099 host driver v2 | `results/run_119_local.pid` in `/home/erich/projects/.nfl2-worktrees/prereg099-supply12800-20260916` (245998 since 2026-09-17 01:32Z; the 00:28Z launch was killed after its first wave collapsed under OpenMP oversubscription, defect 23, and never uploaded a shard) | bank 990 running: run `119b990r1-20260917T013238Z`, 72 slates, 10 workers, ≈ 10.7 h per slate (amendment 3: the rung is 12,560 candidates — boom is bounded by the 10,000-world bank); ≈ 3.2 days; STOP it Saturday 17:00 CT, resume after Sunday; read expected Monday | `results/run_119_local.log`, `results/run_119_local_tasks.log`, `results/119_local/<run id>/tNN.log`; run ids in `results/run_119_local_runs.log` | rerun `setsid nohup scripts/run_119_local_v2.sh 10 > results/run_119_local.log 2>&1 < /dev/null &` from that worktree — attach-aware (skips slates already in the bucket) |
| PREREG-099 mechanics gate | DONE 2026-09-17 00:17Z (13 h 0 min: stream 38,416 s, verify 8,247 s) | PASSED against amendment 3's expected 12,560 attempts (`results/prereg099_mechanics_gate.out`) | shard `gs://nfl-2-506823-lab/results/119_dose12800/119m990r1-20260916T111557Z/result-t00.json` | — |
| DraftKings host pull loop | `/home/erich/week1-sunday/host_ingest_dk_loop.pid` (4129) | hourly `ingest-dk` + `ingest-contests` from the host (Cloud Run is 403-blocked, defect 18); the script exports `GCP_PROJECT` itself (defect 19) | `/home/erich/week1-sunday/host_ingest_dk_loop.log` — a healthy hour shows "Loading N rows into nfl-predictions-503414.nfl_raw.dk_salaries" and "Polled N contests" | `setsid nohup /home/erich/week1-sunday/host_ingest_dk_loop.sh > /home/erich/week1-sunday/host_ingest_dk_loop.log 2>&1 < /dev/null &` |
| D6400 / D12800 timing rehearsals | DONE (both exit 0; see §4.1a for how to run one) | **D6400 7,674 s = 2 h 08 min** (run dir `20260916T144448044783Z-e7255e9`); **D12800 58,602 s = 16 h 17 min** (`20260916T165251953256Z-e7255e9`, 12,559 candidates, 90 written, nested prefix true) — the D12800 figure was inflated by the 10-worker bank sharing the machine | logs `/home/erich/week2-rehearsal/rehearse_*.log`; both books carry the defect 24/25 fallbacks, so they are valid for TIMING only | — |

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
   the DK loop's last pull, any running rehearsal, and from Saturday `systemctl --user list-timers | grep nfl-week2`.
5. When `results/run_119_local.log` says "done": read PREREG-099 exactly once (§6.3) and record it. The timing
   rehearsals are finished (§4.1a holds their numbers and how to run another); after the operator's next
   build-features → tabpfn-gen → project-slate refresh, run ONE more D6400 timing rehearsal so there is a book on the
   production law to show him (defects 24/25 made the first pair fallback-law books).
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
- PREREG-099 read when `run_119_local.log` says "done" (NOT this week: amendment 3 — the bank needs ≈ 3.2 days and pauses for Week 2; expected Monday 09-21): `cd <099 worktree> && PYTHONPATH=src
  /home/erich/projects/nfl2/.venv/bin/python scripts/prereg099_report.py <RUN990> > PREREG-099-read.txt`, record in
  `PREREG-099.md` + `LEDGER.md`, commit on the 099 branch, push. Its secondary "proxy K80 D12800 − D6400" is the only
  book-level evidence the operator has for the 12,800 go/no-go; report it plainly with its W/L and interval.
- Ask the operator: is D12800 still an early candidate for Sunday (yes → keep the 01:30 CT timer; no → drop that line).
- If the PREREG-099 bank is still running Saturday night, stop it (`kill $(cat results/run_119_local.pid)` plus the
  worker pythons `pkill -f "119_dose12800.py --bank=990$"` from a separate command) so Sunday's builds have the cores;
  it resumes later with the same command (attach-aware).

### Saturday 09-19
- **Long builds move to Saturday evening (operator decision 2026-09-16 23:45Z); the D12800 book is THE INTENDED ENTRY
  (operator decision 2026-09-17 00:50Z, no book-level evidence — recorded as his call).** Sequence (times revised 2026-09-17 09:50Z after the D12800 rehearsal measured 58,602 s = 16 h 17 min on group 153428 with the bank sharing the machine — receipt `20260916T165251953256Z-e7255e9`, 12,559 candidates, 90 written, nested prefix true, empirical-marginals fallback per defect 24): (1) by ~08:00 CT stop
  the PREREG-099 host bank if still running (`kill $(cat results/run_119_local.pid)` in the 099 worktree, then
  `pkill -f "119_dose12800.py --bank=990$"` as a separate command; it resumes later, attach-aware); (2) ~07:45 CT the
  operator triggers the production refresh so the projections carry the week's injury designations and line moves:
  `gcloud run jobs execute build-features ... --wait`, then `gcloud run jobs execute tabpfn-gen ... --update-env-vars
  TABPFN_UPCOMING=2026:2 --wait` (defect 24), then `gcloud run jobs execute project-slate ... --wait` (≈ 35 min; the harness
  refuses production executions for the assistant); (3) timers fire 08:30 CT D12800 (12–16 h → 20:30 CT Saturday to 00:50 CT Sunday; the book is 12,560
  candidates by the 10,000-world bound) and 08:35 CT D6400 fallback (2 h 08). (4) `/home/erich/week2-chosen-dose.env`
  holds `CHOSEN_LEV=2560 CHOSEN_BOOM=10240`: the Sunday after-build watcher processes ONLY run dirs at that dose, so the
  09:10 D3200 and 10:50 D800 builds can never overwrite `ENTER/`. **Fallback if the D12800 build failed or is not wanted:**
  before 09:12 CT Sunday change the file to `CHOSEN_LEV=1280 CHOSEN_BOOM=5120` (the D6400 books), or after the watchers
  started run `scripts/sunday_after_build.sh once <run dir> <tag>` by hand (it overwrites `ENTER/`; the entries watcher
  refills the export automatically when the ENTER files change). Books built Saturday lack only Sunday-morning news, which the scratch-swap protocol applies
  to whichever book is entered.
- Print `scripts/arm_week_timers.sh 2` and have the operator run the six lines (two Saturday, four Sunday) before
  07:30 CT Saturday; then `systemctl --user list-timers --all | grep nfl-week2` must show all six. `WIN_DOWNLOADS` in `/home/erich/week2-sunday-watchers.sh` is
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

**Week-2 dose plan (operator decisions 2026-09-16 — a protocol override, recorded so it is not mistaken for an untested
rule).** Evidence: PREREG-097 D6400 vs D3200 on the K80 book: proxy +0.005 near miss (32 W / 36 L) but raw best-of-book
+1.2 [+0.3, +2.0] and weeks ≥ 200 / ≥ 210 11 → 16 / 4 → 7; D6400 vs D800 PASS. Nothing measured says 6,400 hurts; the
strict gate was a near miss. 12,800 has no book evidence until PREREG-099's Friday read (its reader reports a
one-bank K80 comparison as a secondary). Plan (revised 2026-09-17 09:50Z): five builds — Saturday 08:30 CT D12800 and 08:35 CT D6400 after the operator's
production refresh at 07:45 CT (build-features → tabpfn-gen → project-slate), then Sunday 05:30 CT D6400, 09:10 CT D3200, 10:50 CT D800 — each with its own run tag
and run dir. **The operator has chosen the D12800 book as the entry** (his protocol decision; PREREG-099's book-level
read will not exist before Monday, so this rests on the dose law measured to 6,400 and on 6,400 > 3,200 raw +1.2, not on
a 12,800 measurement); D6400 is the fallback, then D3200, then the T-70 D800. The chosen dose is pinned for the Sunday
automation in `/home/erich/week2-chosen-dose.env` (§3 Saturday). Why Saturday: the projection center refreshes only Tuesday and Sunday 05:30–11:00 CT, so a
Saturday build needs the manual refresh; it then lacks only Sunday-morning news (§3 Saturday).
Measured build times on this machine (single stream, receipt `seconds`): D800 244 s, D3200 3,040 s (Week-1 receipts);
**D6400 7,674 s = 2 h 08 min** (rehearsal 2026-09-16 14:44–16:52Z on group 153428, run dir
`20260916T144448044783Z-e7255e9`, 6,400 candidates, 90 written, exit 0) → the 05:30 CT timer yields the D6400 book by
≈ 07:40 CT; **D12800 58,602 s = 16 h 17 min** (rehearsal 2026-09-16 16:53Z – 09:09Z on group 153428, 12,559 candidates, 90 written; it
shared the machine with the 10-worker bank and a one-hour thread collapse, so a clean Saturday build should be shorter;
the 08:30 CT slot assumes the measured pace plus margin).
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
2. Fill `/home/erich/week2-sunday/contests.json` from the operator's reservations (done 2026-09-16 from his
   `DKEntries-2026-09-16.csv`: 33 entries / $206).
3. Run the rehearsals in §4.1a: the chain rehearsal always, a timing rehearsal for any dose whose build has never been
   measured on this host, and the chosen-dose check before the timers are armed.
4. Have the operator arm the timers: `scripts/arm_week_timers.sh 2` prints the six `systemd-run` lines (or `--run` arms
   them). Production Cloud Run executions and systemd writes are classifier-refused for the assistant — hand him the lines.
5. Saturday: `systemctl --user list-timers --all | grep nfl-week2` shows all six; the Downloads path in
   `sunday_watch_dk_entries.sh` (`WIN_DOWNLOADS`) is right; the operator has reserved entries with a placeholder.

### 4.1a How to rehearse (do this before every Sunday; all three were run for Week 2 on 2026-09-16/17)

Three separate rehearsals answer three separate questions. **None of them may write into `$OUT` of the live week**
(`/home/erich/week2-sunday/`): always point `OUT` somewhere else, or the Sunday watcher will publish rehearsal lineups
into `ENTER/`. Rehearsal builds are real builds on the coming Sunday's draft group — `live_week.py` refuses a lock that
has passed, so a rehearsal can never run on last week's group.

**(a) Timing rehearsal — "does this dose fit the window?"** One live build at the dose, nothing downstream. Pattern
(`/home/erich/week2-rehearsal/rehearse_6400.sh` is the committed example; copy it and change `--lev/--boom`):
```
cd /home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9
NFL2_LIVE_CENTER=production PYTHONPATH=$PWD/src OMP_NUM_THREADS=1 /home/erich/projects/nfl2/.venv/bin/python scripts/live_week.py \
  --season 2026 --week 2 --group <GROUP> --selector dual_emax --lev <LEV> --boom <BOOM> --sims 10000 --k 1 \
  --seed 2026 --entries 90 --emit-a5-sidecars > <log>.out 2> <log>.err
```
Run it detached (`setsid nohup … &`) and read the wall time from the run dir's `receipt.json` `seconds`, never from the
log. Measured this way on group 153428: **D6400 7,674 s (2 h 08), D12800 58,602 s (16 h 17)** — the D12800 figure was
inflated by a 10-worker lab bank sharing the machine, so subtract contention when the host is quiet. Always chain a
second timing rehearsal behind the first (`until grep -q "^exit" <first>.log; do sleep 120; done`) rather than running
two at once. Check the `.err` for `TABPFN_MARGINALS … falling back` (defect 24) and the receipt for `production_rows`
(defect 25): a rehearsal with either is valid for TIMING but its book is not on the production law.

**(b) Chain rehearsal — "does everything downstream of the build still work?"** Reuses an existing run dir, so it costs
minutes and needs no solver:
```
cd <audit worktree>
export OUT=/home/erich/week2-rehearsal-chain CONTESTS_JSON=/home/erich/week2-sunday/contests.json
source scripts/week_env.sh && week_env 2 <GROUP>
SKIP_PAIR=1 REUSE_K90_DIR=<an existing K90 run dir> RUN_TAG=rehearsal-chain-e7255e9 scripts/sunday_build_host.sh
scripts/sunday_after_build.sh once <the same run dir> rehearsal
cat $OUT/ENTER/ENTER-layout.txt; ls $OUT/ENTER
/home/erich/projects/nfl-predictions/.venv/bin/python /home/erich/week1-sunday/tools/fill_dk_entries.py \
  /home/erich/week2-sunday/ENTERED/DKEntries-<date>.csv --contests "$CONTESTS_JSON" --enter-dir $OUT/ENTER \
  --out-dir $OUT/fill --frame <run dir>/frame.parquet
mv $OUT/fill/DKEntries-FILLED-keepers-first.csv $OUT/fill/REHEARSAL-DO-NOT-UPLOAD.csv
```
Pass: the contests line lists every contest with the right entry counts; one `emitted` line per contest per layout; the
vetted book appears; `ENTER-layout.txt` matches the operator's reservations; the fill reports "filled N (keepers N,
withdraw 0)" for every contest. **Rename the filled CSV immediately** — it holds the rehearsal's lineups and would
otherwise look like Sunday's upload.

**(c) Chosen-dose check — "will the watcher enter the right book?"** With several doses building on Sunday, the
after-build poll must process only the chosen one:
```
export OUT=/home/erich/week2-rehearsal-chain LIVE_DIR=<a live dir holding run dirs at several doses>
printf 'CHOSEN_LEV=<lev>\nCHOSEN_BOOM=<boom>\n' > $OUT/chosen-rehearsal.env
rm -f $OUT/after_build.seen
CHOSEN_FILE=$OUT/chosen-rehearsal.env timeout 150 scripts/sunday_after_build.sh
```
Pass: it logs `chosen dose: lev … / boom …`, processes the matching run dirs and prints `skip <dir> (not the chosen
dose)` for the rest. The live file is `/home/erich/week2-chosen-dose.env` (Week 2: `2560/10240` = the D12800 book).

Retire rehearsal directories after the week settles; never leave one named like the live week's `$OUT`.

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
| 23 | **FIXED 01:32Z with `OMP_THREAD_LIMIT=1 OMP_WAIT_POLICY=PASSIVE` in `run_119_local_v2.sh` (the cap LightGBM cannot override; a 50-round toy training: 80 s thrashed vs 0.5 s capped; all 10 workers reached their solver within 100 s of the relaunch, load 73 → ≈ 11).** Original finding: host bank workers thrash at wave start: every worker TRAINS the component LightGBM models in-process (`pipeline.component_models` → `components.train`, `num_threads=LGB_THREADS` from `featureset.py`), and LightGBM's explicit `num_threads` overrides `OMP_NUM_THREADS=1`, so 10 workers × 8 OpenMP threads run on 16 hardware threads during the simulation phase (load ≈ 73; the phase that takes 66 s alone took > 45 min in the first wave). Later waves are staggered, so the cost is ≈ 1–2 h over the 3-day bank; the cloud image (2 vCPU) is unaffected. Not changed mid-run (a code change would re-stamp the bank's identity); if a future host bank is launched, set `LGB_THREADS` to 1 for workers or stagger their starts. Sunday's 2–3 concurrent builds are fine. | closed (relaunched 01:32Z; the first wave's 60 min lost) |
| 24 | **The weekly `tabpfn-gen` run was missed for Week 2** (no scheduler; the design guide says run it Wednesday and after every feature rebuild with `TABPFN_UPCOMING=season:week`): `nfl_features.tabpfn_projections` holds 2026 week 1 only, so every Week-2 build so far (both timing rehearsals) fell back to the EW empirical marginals with the logged warning "TABPFN_MARGINALS on but no cached rows for season 2026" — a different law from Week 1's entered book (whose build log has no such warning). | operator runs `gcloud run jobs execute tabpfn-gen ... --update-env-vars TABPFN_UPCOMING=2026:2 --wait` (checklist), and again inside every Saturday/Sunday refresh AFTER build-features and BEFORE project-slate; verify by the absence of the warning in the build's `k90-*.err` | open until run |
| 25 | **No production projections for Week 2 mid-week**: `project-slate` runs Tuesday 09:30 CT and Sunday 06:00–11:00 CT only; Tuesday's failed (stale eligibility receipt: Cloud Run had no DK pool, defect 18), so every Week-2 build so far centred on the lab-blend fallback (`production_rows 0`, `matched_skill 0`, `unmatched_skill_fallback_lab_blend 410`; Week 1's entered build: 465 / 337 / 6). Together with defect 24 the rehearsal books are not on the production law. | operator runs build-features → tabpfn-gen (2026:2) → project-slate now (checklist) and again Saturday 07:45 CT; verify `production_rows > 0` in the next build's receipt | open until run |
| 26 | `project-slate` refuses when `player_week_inference` disagrees with DraftKings' current roster ("stale team/position"): on 2026-09-17 build-features ran at 09:54Z and the daily nflverse roster ingest at 10:00Z moved Tyler Goodson ATL→DAL, so the 10:06Z project-slate failed | run the refresh after the 05:00 CT ingest (Saturday 07:45 CT is fine); on refusal rerun build-features → tabpfn-gen → project-slate | closed (guard working) |
| 18 | **DraftKings API returns 403 to Cloud Run egress** (every scheduled `ingest-dk` execution since 2026-09-16 05:00Z; the identical request from the workstation returns 200) — no salaries/statuses/draft groups land from the cloud; Sunday's hourly `ingest-dk` and `ingest-contests-sun` are affected | stopgap: host loop `/home/erich/week1-sunday/host_ingest_dk_loop.sh` (hourly `nfl-dfs ingest-dk` + `ingest-contests` with `INGEST_CONTESTS_ENABLED=1`, from the audit worktree; pid in `host_ingest_dk_loop.pid`; started 09:45Z, 3,089 salary rows + 4,529 contests landed; **must run on whichever machine is on** — restart it on the laptop after the move); real fix = static egress (VPC connector + Cloud NAT) or move the DK pulls to a host timer permanently | **open, operator decision on the egress fix** |

---

## 10. File index (most used)

- `reports/2026-09-17-week2-operator-checklist.md` — the operator's own steps for Saturday/Sunday/Monday (timers, refresh, chosen dose, upload).

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
