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
| `main` | **fast-forwarded by the operator on 2026-09-24 to `d5705e93`** (the integration tip after merging the rules and external-review branches; 513 commits). It now carries the DK loop, its unit, `week_inputs.py` and every Sunday tool. Production work still lands on the integration branch; the operator fast-forwards `main` to it at each weekly milestone (Tuesday), with `git push origin <integration sha>:refs/heads/main`. |
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
   - **Switch the laptop's main checkout `~/projects/nfl-predictions` (clean) to the integration branch**:
     `git -C ~/projects/nfl-predictions switch production/week3-integration-20260921`, then `pull --ff-only`. With `main` now
     current (2026-09-24) the switch is small, and every path the DK unit and the Sunday scripts hard-code
     (`%h/projects/nfl-predictions`) then points at the branch production commits to. No drop-in or second checkout is needed.
   - The lab clone at exactly `9b341d77`: `git -C ~/projects/nfl2 worktree add ~/projects/.nfl2-worktrees/week3-live-center 9b341d77`.
     It must be clean. The runtime preflight refuses any other HEAD.
5. **Move the DK loop, workstation first, then laptop.**
   - Workstation: `kill $(cat ~/week1-sunday/host_ingest_dk_loop.pid)`, then confirm the pid is gone.
   - Laptop: `scripts/host_ingest_dk_loop.sh --check` from the integration checkout.
   - Then install the unit as tracked: `mkdir -p ~/week1-sunday ~/.config/systemd/user && ln -s
     ~/projects/nfl-predictions/deploy/systemd/nfl-host-dk-ingest.service ~/.config/systemd/user/`. It uses
     `%h/projects/nfl-predictions`, which step 4 put on the integration branch, and `PID_FILE=%h/week1-sunday/host_ingest_dk_loop.pid`.
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
**Cleaned up 2026-09-24 ~08:15 CT by the operator:** the four bucket objects were removed (`gcloud storage ls -a` finds nothing under `host-migration/`), and the local bundle was deleted.

## 6. Code and documents that exist only on the workstation

A read-only sweep on 2026-09-24 checked every worktree of both repos. It hashed each modified or untracked file
against every object on the remotes and ran `git cherry` on the unpushed commits.
**Nothing on the production money path exists only here:** every production branch and tool is on GitHub. What was
unique here is research leftovers:

| item | status |
|---|---|
| Primary checkout (`~/projects/nfl-predictions`), 8 modified files and 27 untracked research modules, runners and tests (r6 corpus / fair-fill / scheduler, cloud_core_v1 recovery, foundry v12 lane exports, recourse-aware transport) | **pushed** to `archive/workstation-primary-uncommitted-20260924` @ `155737d5`. The 19 untracked `reports/*.md` were already on origin/main |
| `week1-audit-adjust-20260912`: `scripts/arm_week_timers.sh`, a Week-2 release-pin hotfix, since superseded by the integration rewrite | **pushed**, `53591bcd` on its branch |
| `~/projects/nfl-predictions-explicit-construction-policy`: 7 modified files plus the 2026-09-05 construction-law runtime audit; the branch has no remote | **pushed by the operator 2026-09-24:** `codex/explicit-construction-policy-v1` @ `545665f9`. (Command used: `cd ~/projects/nfl-predictions-explicit-construction-policy && git add -A && git commit -m "Archive the explicit construction-law audit WIP" && git push -u origin codex/explicit-construction-policy-v1` |
| nfl2 main checkout: 13 untracked lab reports (2026-08-29 to 09-01, 530 KB), plus `.nfl2-worktrees/prereg098-finish-20260914/scripts/arm_118_now.sh` | **pushed by the operator 2026-09-24:** nfl2 `archive/workstation-uncommitted-20260924` @ `856edc91` (13 reports + `arm_118_now.sh`). Method: from a new nfl2 worktree on `origin/main` (branch `archive/workstation-uncommitted-20260924`), copy `git -C ~/projects/nfl2 status --porcelain \| grep '^?? reports/'` files and that script, commit, push. nfl2 is private. Do not touch the main checkout's in-progress cherry-pick of `8eaddf0`: its content is already on the remote, so `git cherry-pick --abort` loses nothing |
| ~2,220 run receipts under `reports/corpus-parametric-runs/…v12a|v12b…/transport-live-*`, `reports/r6-full-union-realized-runs/…`, t230 runs (≈ 280 MB with the `tasks/` dirs) | **left behind unless the operator wants them.** Research evidence for retired frozen chains. About half carry the Google account email in Cloud Run creator fields, so they do not belong in the public repo. The private bucket would be the place |
| Superseded drafts (cfb-audit, cp1-efficacy-package, jpar-a9, prereg073-r2-template) and the detached canonical-v2-r2 commits | already on the remote in later form; nothing to do |
| Sensitive, gitignored: `~/projects/nfl-predictions/.env` (credentials) and `.claude/settings.local.json` | **do not copy blindly**. Recreate `.env` on the laptop from the operator's own records |
| `~/projects/nfl2-092/.quarantine/linestar_raw_outcome_bearing/` (37 raw LineStar files, 51 MB) | the lab recorded these as deleted (`be58f3f`), but a local copy survives. **Operator decision:** delete, or leave on the retired disk. Do not carry it |

The full per-file table was a session scratch file; this section is its durable summary.

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

## 8. Answers to the laptop's cutover questions (`9ecc8183`)

Answered by production from the tracked scripts and the Week-2 record. Where a detail is not pinned in a script, the
answer names the file to read, not a remembered value.

**Laptop state noted:**
- The existing `~/projects/.nfl2-worktrees/week3-live-center` at `2dc116c` stays untouched during Week 3. At
  cutover, recreate it at the Week-4 pin. The path must match `CLONE` in `scripts/week_env.sh`, or export `CLONE`.
- ~~The DK unit runs through a drop-in on a dedicated integration checkout~~ **Superseded 2026-09-24:** `main` was fast-forwarded,
  so the laptop's main checkout switches to the integration branch and the tracked unit works unchanged (§3 steps 4–5).

**1. Monday settlement.**
- The operator downloads each entered contest's full standings (`https://www.draftkings.com/contest/exportfullstandingscsv/<contestId>`;
  DraftKings purges them after about 4 days) and the contest entry-history export, into `~/week<W>-sunday/ENTERED/`.
  Week 2 used `ENTERED/standings/`.
- Load them with `nfl-dfs capture-dk-standings …`: first without `--apply` (validation), then `--apply --confirm-settled
  --confirm-full-field`. The tolerance fixes (branch `production/standings-capture-tolerances-20260921` @ `e30662dd`)
  are on integration. The load writes `nfl_raw.contest_entries` and `nfl_raw.contest_ownership`.
- Scoreboard: `python scripts/book_vs_field_scoreboard.py <RUN_DIR> 2026 <W> <CONTEST_ID> [--book <book.csv>]` for each
  entered contest (the entered run dir is in the live clone's `results/`).
- The paper triple and the cash shadow are scored by their own tools (`reports/lab-handoffs/run_paper_triple.sh`,
  `cash_shadow_paper.py score`). The Route paired shadow is read every week.
- Record it all in `HANDOFF.md` plus a week evidence record (pattern: `reports/2026-09-21-week2-evidence-record.md`) and,
  when the week warrants one, a post-mortem (pattern: `reports/2026-09-21-week2-post-mortem.md`).
- `s-score` (Tue 08:00) scores last week's projections automatically.

**2. Sunday build.** `scripts/arm_week_timers.sh W` prints the plan, and `--run` arms it (operator: it writes systemd
timers). The transient units (times CT):

| unit | when | dose (LEV/BOOM) |
|---|---|---|
| `nfl-weekW-d12800-sat-build` | Sat 10:30 | 2560 / 10240, **the entry** |
| `nfl-weekW-d6400-sat-build` | Sat 10:35 | 1280 / 5120, fallback |
| `nfl-weekW-d6400-build` | Sun 05:30 | 1280 / 5120 |
| `nfl-weekW-sunday-build` | Sun 09:10 | 640 / 2560 |
| `nfl-weekW-t70-build` | Sun 10:50 | 160 / 640, **the T-70 build** |
| `nfl-weekW-watchers` | Sun 09:12 | DK-entries watcher and late-inactives watcher; check that all three processes are up (the 09-20 note) |

- **Before arming, Saturday ~09:45, after the 09:30 `s-props` pull:** `build-features` → `tabpfn-gen` (with
  `TABPFN_UPCOMING=2026:W`) → `project-slate`, each `--wait`, then the proof-line check. This is not scheduled.
- **Dose:** the D12800 values come from `chosen-dose.env`. The operator decides it and publishes it with
  `scripts/week_inputs.py push`; the laptop pulls it with `pull`. The operator decided to hold D12800 for Week 3.
- **Late inactives:**
  - No automatic salary re-pull is needed. The hourly DK loop keeps salaries current, and Sunday's schedulers refresh
    features and projections hourly (`s-features-sun` 05:30–10:30, `s-project-su` 06:00–11:00, `s-contests-sun`).
  - The late-inactives watcher alerts. Scratches follow the protocol "remove only confirmed OUT; cap exposure instead
    of removing actives" (Week-1 evidence in the settlement reports) and are done by hand on the chosen book.
- **Logs:** `~/week<W>-sunday/` (`build-*.log`, `composite-*`, `after_build*.log`, watcher logs). The run dirs and
  receipts are in `<CLONE>/results/`.

**3. Lab pin.**
- `EXPECT_SHA` defaults to `9b341d77…` in `scripts/week_env.sh` (`NFL2_EXPECT_SHA` overrides), and
  `tests/test_week_env_defaults.py::LIVE_PIN_SHA` pins it.
- It stays `9b341d77` for Week 4 unless a lab change must reach the money path.
- A bump means:
  1. a new nfl2 commit built on the current pin's lineage (not off nfl2 `main`);
  2. the full-path smoke locally with no upload;
  3. update both `week_env.sh` and the test in one commit;
  4. recreate the clone clean at the new SHA;
  5. the Saturday rehearsal (`reports/lab-handoffs/saturday_rehearsal.sh`) passes before arming.

**4. Operator-only steps**, which the harness refuses to the assistant or which need the operator's accounts. Print
these on time:
- **Vendor logins:** `sis-download login --terminal-credentials --fresh`, `fantasy-points-download login`, and
  whenever `verify-login` fails.
- **LineStar `curl`** (§3a).
- **Stake plan and dose:** fill `contests.json`, then `scripts/week_inputs.py push`.
- **Timers and units:** `arm_week_timers.sh W --run`, the DK unit install and any user-unit writes.
- **DraftKings browser work:** the entries export download, uploading the filled CSV, late swaps and the Monday
  standings and entry-history exports.
- **Git:** pushes and merges to `main`. Never `git fetch --prune`.
- **Cloud:** create-once publishes and deleting cloud artifacts.
- **The assistant may run:** Cloud Run executes for the week's build (standing authorization: `project-slate`,
  `build-features`, `tabpfn-gen`), `gcloud builds submit`, and `gcloud run jobs update` of existing jobs.

**5. §6:** done, above. The laptop needs none of the archived research code for production.

**6. Weekly steps with no scheduler:**
- Wednesday: the vendor capture, then `tabpfn-gen` (with `TABPFN_UPCOMING`).
- Again after every manual `build-features`: `tabpfn-gen`.
- Saturday: the 09:45 refresh trio.
- Monday: the standings load.
- The LineStar captures.
- `week_inputs` push/pull.
- Thursday: `week_env` (group detection) and the rehearsals.

**Scheduled already** (CT; `gcloud scheduler jobs list --location us-central1`):

| scheduler | what | when |
|---|---|---|
| `s-nflverse` | nflverse ingest | daily 05:00 |
| `s-backup` | backup | daily 07:00 |
| `s-freshness` | freshness check | daily 08:00 |
| `s-features` | build-features | Tue 06:30 |
| `s-features-route` | Route features | Thu 06:30 |
| `s-features-sun` | build-features | Sun hourly 05:30–10:30 |
| `s-train` | training | Tue 07:30 |
| `s-train-k1` | training | Tue 08:30 |
| `s-train-k1-role` | training | Tue 08:45 |
| `s-train-k1-route` | training | Thu 07:30 |
| `s-train-k1-route-role` | training | Thu 08:00 |
| `s-score` | scores last week's projections | Tue 08:00 |
| `s-project-tu` | project-slate | Tue 09:30 |
| `s-project-su` | project-slate | Sun hourly 06:00–11:00 |
| `s-props` | props pull | Wed–Sun 09:30 |
| `s-odds` | odds | Wed–Sun 09:00 and 15:00 |
| `s-weather` | weather | Fri–Sun 08:00 |
| `s-contests` | contests | Wed–Sat 10:00 |
| `s-contests-sun` | contests | Sun 06:00–11:00 |
| `s-us-dfs`, `s-us-dfs-sun` | US DFS | as scheduled |
| `s-trends` | trends | Wed 11:00 |
| `s-dk` | Cloud Run DK pull | hourly Wed–Sun; **403s by design (defect 18)**, the host loop replaces it |

## 9. Laptop addendum: items found on the laptop that the cutover must handle (laptop agent, 2026-09-24)

Found by read-only checks on the laptop (`9ecc8183`, `bb68115f`). They **add to** §3; do them in the same Tuesday session. Each has a check.

| # | item | who | how | check |
|---|---|---|---|---|
| L1 | **Chromium system libraries** (vendor capture) | operator (sudo) | `sudo apt-get install -y libnss3 libnspr4 libasound2t64` (Ubuntu 26.04). Playwright and its headless Chromium are already installed in `~/projects/nfl-predictions/.venv` (done 2026-09-24) | `~/projects/nfl-predictions/.venv/bin/python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); b=p.chromium.launch(); print('ok'); b.close(); p.stop()"` prints `ok`. **Must pass before §3 step 6** |
| L2 | **No `.env` on the laptop** | operator | recreate from the operator's own records (never copied from the workstation; §6) | the commands that need it run; nothing is logged |
| L3 | **Lab clone is at the wrong commit**: `~/projects/.nfl2-worktrees/week3-live-center` exists at `2dc116c` (the Week-2 release), not `9b341d77` | laptop agent | after Week 3 only: `git -C ~/projects/nfl2 worktree remove ~/projects/.nfl2-worktrees/week3-live-center`, then `git -C ~/projects/nfl2 worktree add ~/projects/.nfl2-worktrees/week3-live-center 9b341d77`. The path must equal `CLONE` in `scripts/week_env.sh` | `git -C <clone> rev-parse HEAD` = `9b341d77…` and `status --porcelain` is empty; the runtime preflight passes |
| L4 | ~~Main checkout is on `main` (441 behind)~~ **resolved 2026-09-24**: `main` = `d5705e93`; switch the main checkout to the integration branch (§3 step 4) | laptop agent | `git -C ~/projects/nfl-predictions switch production/week3-integration-20260921 && git -C ~/projects/nfl-predictions pull --ff-only` | `git -C ~/projects/nfl-predictions rev-parse HEAD` = the HANDOFF tip |
| L5 | ~~DK unit drop-in~~ **not needed**: the tracked unit's `%h/projects/nfl-predictions` is the integration checkout after L4 | operator (unit link) | §3 step 5; create `~/week1-sunday/` first. **The workstation loop must be stopped first; never two loops** | `journalctl --user -u nfl-host-dk-ingest` shows `host DK ingest pair succeeded` within the hour |
| L6 | **Sunday watchers' Downloads path** | laptop agent | `WIN_DOWNLOADS=/mnt/c/Users/erich/Downloads` in the watcher environment | a test export dropped there is picked up |
| L7 | **CPU contention** | laptop agent | the laptop builds the Sunday book itself from Week 4 (~6 h, one heavy job at a time). **No lab panel (L0x) may run over Sat 10:30 – Sun 12:00 CT.** Schedule panels Mon–Fri only | `ps` shows no panel workers during the build window |
| L8 | **Operator logins after L1** | operator | §3 step 6: `sis-download login --terminal-credentials --fresh`, `fantasy-points-download login` | `python -m nfl_dfs.ops.weekly_vendor_data verify-login` passes |

**Laptop state already verified (2026-09-24):**
- systemd user session running (WSL `systemd=true`);
- `gcloud`/`bq` as `espechtsoftware@gmail.com` on `nfl-predictions-503414`, with ADC set;
- 927 GB free;
- the tracked production scripts are on integration.
