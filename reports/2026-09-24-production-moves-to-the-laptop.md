# Production moves to the laptop: the workstation retires after Week 3

Written 2026-09-24 by production (the workstation agent), for the laptop agent, which becomes the only production
operator from Week 4, and for the operator. **This supersedes §11 of
`reports/2026-09-15-week2-operating-handoff.md` and `reports/2026-09-15-workstation-to-laptop-transition-guide.md`.**
The weekly cadence (§3a of the operating handoff) and the Sunday money path (§4 there) still hold and are not
repeated here. Only what depends on *this machine* is.

Operator decision (2026-09-24): after Week 3 only the laptop is used.

## 0. Timeline

| when (CT) | what | where |
|---|---|---|
| through Sun 09-27 | Week 3 as planned: Saturday props → `build-features` → `project-slate` → ownership sets → rehearsal → D12800 build; Sunday entries and watchers | workstation |
| Mon 09-28 | settlement, scoreboard, paper-triple scoring, Route read; the last production work on the workstation | workstation |
| **Tue 09-29 morning** | **cutover** (§3). The DK loop moves first, since Week-4 salaries post Monday/Tuesday | both |
| Wed 09-30 | first Week-4 cadence day, run entirely from the laptop (vendor capture, `tabpfn-gen`, projection refresh) | laptop |

Nothing in the cloud moves: Cloud Run jobs, schedulers, Cloud Build, BigQuery and GCS are machine-independent.

## 1. Production state of record (2026-09-24 06:00 CT)

| item | value |
|---|---|
| Integration branch (all production work, handoff, tools) | `production/week3-integration-20260921`; live tip in `HANDOFF.md`, never in memory |
| Shipping branch (the deployed code) | `production/week3-qbgate-on-cf630a68-20260922` @ `3f7084e0` (default-off changes after the deploy; not built) |
| `main` | `9afb1784`, **441 commits behind integration**. `host_ingest_dk_loop.sh`, `nfl-host-dk-ingest.service` and `week_inputs.py` are **not on main**. Run production from an integration checkout (§3 step 4) until the operator merges integration into `main` (pushes to `main` are operator-only). |
| Live image (`project-slate`) | `…/nfl-dfs/nfl-dfs@sha256:796380e43a0495d2af1e14bbd00078f0233ae946cb58bb186278db49e25fd17a`, built from shipping `e457560b` |
| `project-slate` env (besides `GCP_PROJECT` and the `ODDS_API_KEY` secret) | `GAME_SIM_MODE=possession MODEL_ENSEMBLE=1 MODEL_REGISTRY_VARIANT=tail_k1 BLEND_MODEL_WEIGHT=0.45 Q_HAIRCUT=0.80 CASCADE_DOUBTFUL=1 CASCADE_SKIP_PRICED_CARRIES=1 QB_Q_PRIMARY_BACKUP_SCALE=0.20 RETURNING_TEAMMATE_ADJ=1` (`RETURNING_RB_ADJ` is unset, so off) |
| Lab money-path clone | nfl2 at exactly `9b341d77` (`EXPECT_SHA`); on the workstation `/home/erich/projects/.nfl2-worktrees/week3-live-center` |
| Week-3 Sunday main | draft group `153769`, lock Sun 09-27 12:00 CT |
| Private weekly inputs | `gs://nfl-predictions-503414-raw/week-inputs/2026/wNN/` (`contests.json`, `chosen-dose.env`, manifest); `scripts/week_inputs.py push|pull|validate` |
| Proof-line check after every `project-slate` | `reports/lab-handoffs/week3_proof_lines.py` (pinned to `796380e4`) |

**Deploy procedure for a projection change** (what production did three times this week):
1. Commit on the shipping branch. If the change touches a file the frozen effective-policy inventory pins
   (`run_projections.py`, `engine.py`, …), add a new source-set version to
   `src/nfl_dfs/research/effective_policy_rule_inventory.py` and its test. Measure the read-site diff first: it must be
   position-free identical.
2. Run the targeted tests without `-q`. Then build from a clean worktree at that exact commit:
   `gcloud builds submit --config cloudbuild.week1-live.yaml --substitutions=_CODE_SHA=<full sha>,_IMAGE=<tag>`.
   The plain `cloudbuild.yaml` times out.
3. Point the job at the new image by **digest**: `gcloud run jobs update project-slate --region us-central1 --image
   …@sha256:<digest>`, plus any `--update-env-vars`. Never create a job (us-central1 is at the 1000-job quota).
4. Execute it with `gcloud run jobs execute project-slate --region us-central1 --wait`, then run the proof-line check.
   Before any flag goes on, it must pass the check. Record the image digest and the execution id in `HANDOFF.md`.

The integration branch is deployable too, now that `market_source_log` has `model_points_pre` and `model_weight`.
From Week 4, merge shipping into integration and deploy from integration only, so there is a single branch.

## 2. What runs on the workstation, and what replaces it

| workstation | what it does | laptop replacement | priority |
|---|---|---|---|
| `host_ingest_dk_loop.sh` (pid in `~/week1-sunday/host_ingest_dk_loop.pid`, cwd = the integration worktree) | **the only source of DK salaries and the contest lobby.** Cloud Run `ingest-dk` has returned 403 since 09-16 (defect 18); its hourly failures are expected | tracked unit `deploy/systemd/nfl-host-dk-ingest.service` (§3 step 5). **Never run two loops**: both append, so every hour would double-pull | **1 — no arm-time gate catches its absence** |
| Saturday/Sunday build (`scripts/arm_week_timers.sh W --run`, `sunday_build_host.sh`, lab venv + pinned clone) | builds the D12800 book and the Sunday doses | same scripts on the laptop; the benchmark (`reports/2026-09-22-laptop-readiness-if-the-build-moves.md`) says ~6 h instead of ~10 h | 2 |
| Sunday watchers (`sunday_watch_dk_entries.sh`, `sunday_watch_late_inactives.py`) | pick up the DK entries export from the Windows Downloads folder; late-inactive scratch alerts | same; set `WIN_DOWNLOADS` to the laptop's Windows Downloads path. Start them by hand and check the three processes: a transient timer kills their children (see the watchers note in `HANDOFF.md` 09-20) | 2 |
| Vendor capture (`weekly_vendor_data run --week W --skip-odds --no-login-if-needed`) | Fantasy Points + SIS every Wednesday | same command; the operator logs in once on the laptop (§3 step 6) | 3 |
| LineStar capture (operator-run `curl`, §3a) | ownership history | same, into `~/week<W>-sunday/linestar/` on the laptop | 4 |
| User monitors (`nfl-cloud-build-monitor`, `nfl-cloud-run-lane-monitor`, `nfl-lab-action-note-monitor`, heartbeat timer) | research-era read-only alerts; two are crash-looping | **do not recreate.** Nothing on the money path reads them | — |

## 3. Cutover checklist (Tuesday 09-29, in this order)

Each step has its check. Do not start the next step until the check passes.

1. **Laptop: fetch both repos** with `git fetch --all` (never `--prune`). Confirm the integration tip matches `HANDOFF.md`.
2. **Laptop: auth.** Run `gcloud auth login` and `gcloud auth application-default login` as `espechtsoftware@gmail.com`,
   project `nfl-predictions-503414`. Check: `bq query --use_legacy_sql=false 'SELECT 1'` works.
3. **Laptop: venvs.** Production: `pip install -e ".[dev,gcp,app]"`. Lab: `~/projects/nfl2/.venv`.
   Remember `PYTHONPATH=<worktree>/src` whenever you run from a worktree. The main venv imports the main checkout, so
   without it you silently test the wrong code.
4. **Laptop: checkouts.**
   - An integration checkout, either `git worktree add ~/projects/nfl-predictions-week4 production/week3-integration-20260921`
     or the main checkout switched to that branch.
   - The lab clone at exactly `9b341d77`: `git -C ~/projects/nfl2 worktree add ~/projects/.nfl2-worktrees/week3-live-center 9b341d77`.
     It must be clean. The runtime preflight refuses any other HEAD.
5. **Move the DK loop, workstation first, then laptop.**
   - Workstation: `kill $(cat ~/week1-sunday/host_ingest_dk_loop.pid)`, then confirm the pid is gone.
   - Laptop: `scripts/host_ingest_dk_loop.sh --check` from the integration checkout.
   - Then install the unit. It hard-codes `%h/projects/nfl-predictions` as `PROD` and as the script path, so either
     that checkout is on the integration branch, or you add a drop-in (`systemctl --user edit nfl-host-dk-ingest`)
     that sets `WorkingDirectory`, `Environment=PROD=` and `ExecStart` to the integration checkout.
     Keep `PID_FILE=%h/week1-sunday/host_ingest_dk_loop.pid`.
   - `systemctl --user daemon-reload && systemctl --user enable --now nfl-host-dk-ingest`.
     Writing a unit is operator-only; the harness refuses it.
   - Check: within the hour, `journalctl --user -u nfl-host-dk-ingest` shows `host DK ingest pair succeeded`, and the
     `Loading N rows into … dk_salaries` lines include the Week-4 groups.
6. **Operator: vendor logins on the laptop.** `sis-download login --terminal-credentials --fresh` and
   `fantasy-points-download login`. Sessions live in `~/.local/share/nfl-dfs/{sis,fantasy-points}-playwright`. Do not
   copy those folders: they are credentials. Check: `python -m nfl_dfs.ops.weekly_vendor_data verify-login`.
7. **Carry the host data (§4).**
8. **Week-4 inputs:** `scripts/week_inputs.py pull --season 2026 --week 4` once the operator has pushed them.
   The stake plan never goes into the repo.
9. **Workstation last:** stop any remaining nfl processes, and delete the migration upload (§5) once the laptop has
   verified its copy.
10. **Record the cutover in `HANDOFF.md`:** the laptop's checkout paths, the DK unit status, the first successful loop
    pair, and the vendor `verify-login` output.

## 4. Data to carry

Everything durable is already in GitHub, BigQuery and GCS. This is what exists only on the workstation's disk.

| data | path on the workstation | size | sensitivity | needed for |
|---|---|---|---|---|
| Week folders: `ENTER/`, `ENTERED/`, `contests.json`, `chosen-dose.env`, build logs, composites, `enter-bundles/`, `linestar/` | `~/week1-sunday`, `~/week2-sunday`, `~/week3-sunday` | 375 MB, 84 MB, <1 MB (Week 3 grows through Monday) | **DK entry keys and the stake plan**: private | settlement history; Week-3 Monday scoring |
| Home-dir wrappers and dose files | `~/week1-sunday-build.sh`, `~/week2-sunday-build.sh`, `~/week2-sunday-watchers.sh`, `~/week3-build.sh`, `~/week2-props-check.sh`, `~/week2_runtime_pin.sh`, `~/week2-runtime-pin.patch`, `~/week2-RELEASE-STEPS.md`, `~/week2-dose.env`, `~/week2-chosen-dose.env`, `~/milly_win_join.csv` | small | none (the dose values are already public in `config/week-inputs-schema.md`) | reference only; the tracked scripts replaced them |
| DK exports (standings, entry history) | `~/projects/nfl-predictions/results/` | 224 MB | **DK user data**: private | field and settlement analyses |
| Licensed vendor captures (run manifests + files) | `~/projects/nfl-predictions/{fantasy-points,sis,weekly-data-runs}`, `…/week1-audit-adjust-20260912/{fantasy-points,weekly-data-runs}`, `…/week3-readiness-20260921/{fantasy-points,sis}` | ~90 MB | **licensed**: private, never the repo | re-sealing a week; the GCS archives under `gs://…-raw/licensed/` already hold the files the loaders used |
| Entered books and build receipts | `~/projects/.nfl2-worktrees/{week1-live-center-e7255e9,week2-release-2dc116c,week3-live-center}/results` | 600 MB, 233 MB, grows | contains lineups (not entry keys) | scoreboards, post-mortems |
| Assistant memory | `~/.claude/projects/-home-erich-projects-nfl-predictions/memory/` | 0.5 MB | internal | the laptop agent's own memory is separate. Everything operational is in this document and `HANDOFF.md` |

**Left behind on purpose:**
- `~/worktree-archive` (17 GB), `~/winner-audit-cache` (5.9 GB) and `~/nfl-panels` (4 GB): research caches, regenerable.
- `~/.local/state/nfl-dfs/cp4-*` (3.2 GB): frozen-chain research state.
- The results dirs of the other lab worktrees: their cohorts are in `gs://nfl-2-506823-lab`.
- The vendor login sessions, which are credentials.

**Transport is the operator's decision.**
- Option A, a direct copy between the two machines (USB drive, or `scp`/`rsync` over the home network), keeps the
  private files off any server. This is the one to prefer for the DK and licensed rows.
- Option B is the project's private bucket, as `scripts/pack_host_state_for_migration.sh` does. That script is **v1**
  (Weeks 1–2 only; it misses `week3-sunday`, the vendor captures, all of `results/` except `2026-09-13`, and the
  live-clone results). The assistant's attempt to extend it was refused by the session's safety check because it
  uploads DK entry files. Either the operator extends and runs it, or uses option A.

## 5. Incident, 2026-09-24 ~05:57 CT: a partial migration upload

Production ran `pack_host_state_for_migration.sh --list`, meaning to preview it. v1 has no `--list` mode; every
argument except `--no-upload` means pack and upload. The run was stopped during upload. What reached the private
bucket:

```
gs://nfl-predictions-503414-raw/host-migration/20260924/{SHA256SUMS,assistant-memory.tgz,launcher-registry.tgz,systemd-user-units.tgz}   (280 KB)
```

The DK-export and week-folder tarballs did **not** upload. Complete local copies of all five tarballs sit in
`/home/erich/host-migration/20260924/`, and one of them holds `ENTERED/`. The bucket is project-private, and nothing
went to the public repo. To remove both, the operator runs:
`gcloud storage rm -r gs://nfl-predictions-503414-raw/host-migration/20260924/` and `rm -r ~/host-migration/20260924`.
The script needs a real `--list` mode and a fail-closed argument check before anyone uses it again.

## 6. Code and documents that exist only on the workstation

(Filled in from a read-only classification of every checkout with local-only state; see below.)

## 7. Operating rules the laptop inherits (all already in the repo; pointers)

- The vendor capture from an assistant session always uses `--no-login-if-needed`. Attended mode wipes the SIS
  session (§3a).
- `git fetch --all`, never `--prune`. Never `pgrep -f`/`pkill -f` with a script name; use pid files.
- Never create Cloud Run jobs. Reuse and update existing ones (CLAUDE.md rule 5).
- Licensed data (Fantasy Points, SIS, LineStar) and DK entries/standings never go in the public repo.
- `contests.json` is private storage only (`scripts/week_inputs.py`).
- No silent fallbacks: a step either works as designed or the run stops.
- The props-or-nothing blend stops `project-slate` when ≥ 2-market coverage is under 30%. That is expected early in
  the week. The first clean run comes after the Friday or Saturday 09:30 props pull.
- The weekly steps are §3a of `reports/2026-09-15-week2-operating-handoff.md`. The Week-3 operator steps are in
  `reports/2026-09-21-operator-runbook-week3.md`.
