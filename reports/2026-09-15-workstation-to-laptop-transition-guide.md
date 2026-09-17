# Moving from the workstation to the laptop — your step-by-step guide (2026-09-15)

Everything durable is already on GitHub (both repos, every branch) and in Google Cloud. The move is about three
things: not killing what is still running here, carrying over the small amount of host-only state, and starting
clean on the laptop. Budget about an hour of hands-on time, most of it waiting for downloads and installs.

Use the same WSL username (`erich`) and home directory on the laptop. Every script defaults to `/home/erich/...`.

---

## Part A — on the workstation, before you shut it down

**A1. What is still running here (updated 2026-09-16 morning).** The admission-cap cohort and the PREREG-097
repairs are finished and read. The only live host process is the hourly DraftKings pull loop
(`host_ingest_dk_loop.sh`, defect 18; salaries + contests): stop it here just before you pack
(`kill $(cat /home/erich/week1-sunday/host_ingest_dk_loop.pid)`) and start it on the laptop in B8. Ask the assistant "is anything still running on this machine?" before you start, in case
that has changed.

**A2. Pack the host state** (one command; ~500 MB; uploads to the project's private bucket):
```
/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912/scripts/pack_host_state_for_migration.sh
```
It packs: `week1-sunday/` (tools, Sunday drivers, the direct-runner results, your `ENTERED/` exports; not the 4 GB
download cache), `week2-sunday/` and the Week-2 wrappers, the DraftKings standings exports under
`results/2026-09-13/`, the launcher registry, the assistant's memory folder, and your systemd user units. It prints
the bucket path (`gs://nfl-predictions-503414-raw/host-migration/<date>/`). Not packed on purpose: the 17 GB
worktree archive (evidence only; ask if you want it) and 3 GB of monitor logs.

**A3. Tell the assistant you are moving** so it writes the final HANDOFF entry from this machine.

---

## Part B — on the laptop

**B1. Inventory the old copies before touching them** (read-only; the four numbers are: uncommitted files,
stashes, local branches with no upstream, commits never pushed):
```
for r in ~/projects/nfl-predictions ~/projects/nfl2; do echo "== $r"; git -C $r status --porcelain | wc -l; git -C $r stash list | wc -l; git -C $r branch -vv | grep -v "\[origin/"; git -C $r log --branches --not --remotes --oneline | wc -l; done
```
All zeros → nothing to save. Anything else → paste the output to the assistant before deleting; it will push or
archive what matters.

**B2. Move the old copies aside and clone fresh:**
```
mv ~/projects/nfl-predictions ~/projects/_old-nfl-predictions 2>/dev/null; mv ~/projects/nfl2 ~/projects/_old-nfl2 2>/dev/null
git clone https://github.com/espechtsoftware/nfl-predictions.git ~/projects/nfl-predictions
git clone https://github.com/espechtsoftware/nfl2.git ~/projects/nfl2
```

**B3. Tools and credentials:**
```
sudo apt-get install -y jq                                    # the launchers use jq
gcloud auth login && gcloud auth application-default login   # account espechtsoftware@gmail.com
gcloud config set project nfl-predictions-503414
bq ls nfl_raw | head -n 3                                     # proves BigQuery access
gcloud run jobs list --project nfl-2-506823 --region us-central1 --format='value(name)'   # proves lab access
```

**B4. Python environments** (each repo's `.venv` is an editable install of that checkout):
```
cd ~/projects/nfl-predictions && python3 -m venv .venv && .venv/bin/pip install -e ".[dev,gcp,app]"
cd ~/projects/nfl2 && python3 -m venv .venv && .venv/bin/pip install -e .
```

**B5. Recreate only the active worktrees** (branch names are exact; the money-path clone must be commit e7255e9):
```
cd ~/projects/nfl-predictions
git worktree add ../.nfl-predictions-worktrees/week1-audit-adjust-20260912 production/week1-audit-adjust-20260912
git worktree add ../.nfl-predictions-worktrees/source-v3-same-path-20260914 production/paid-source-ladder-direct-20260915
git worktree add --detach ../.nfl-predictions-worktrees/week1-publisher-20260912 00c6097f
cd ~/projects/nfl2
git worktree add ../.nfl2-worktrees/prereg098-finish-20260914 lab/prereg098-finish-objective-20260914
git worktree add ../.nfl2-worktrees/prereg097-dose6400-20260913 lab/prereg097-dose6400-20260913
git worktree add ../.nfl2-worktrees/live-center-production-20260912 lab/prereg090-dose1600-directtail-20260912
git worktree add --detach ../.nfl2-worktrees/week1-live-center-e7255e9 e7255e9
git worktree add ../.nfl2-worktrees/prereg096-fast-20260913 lab/prereg096-learned-pool-20260913
git worktree add ../.nfl2-worktrees/prereg090-amend4 lab/prereg090-amend4-20260912
git worktree add ../.nfl2-worktrees/prereg099-supply12800-20260916 lab/prereg099-supply12800-20260916   # added 2026-09-17
git worktree add ../.nfl2-worktrees/prereg100-practice-status-20260916 lab/prereg100-practice-status-20260916
```
The production `main` now contains the Week-2 branch (fast-forwarded 2026-09-17), so the audit worktree and a plain
`main` checkout hold the same files; keep the worktree anyway because every host script points at its path.
The direct-runner worktree needs its own venv: `cd ~/projects/.nfl-predictions-worktrees/source-v3-same-path-20260914 && python3 -m venv .venv && .venv/bin/pip install -e ".[gcp]" google-cloud-storage==3.13.1`.

**B6. Restore the host state** (replace `<date>` with the folder printed in A2):
```
mkdir -p ~/host-migration && gcloud storage cp -r gs://nfl-predictions-503414-raw/host-migration/<date> ~/host-migration/ && cd ~/host-migration/<date> && sha256sum -c SHA256SUMS
tar -xzf week1-sunday.tgz -C /home/erich
tar -xzf dk-exports-results-2026-09-13.tgz -C /home/erich/projects/nfl-predictions
mkdir -p ~/.local/state/nfl-dfs && tar -xzf launcher-registry.tgz -C ~/.local/state/nfl-dfs
mkdir -p ~/.claude/projects && tar -xzf assistant-memory.tgz -C ~/.claude/projects      # overwrites the laptop's stale memory
mkdir -p ~/.config && tar -xzf systemd-user-units.tgz -C ~/.config && systemctl --user daemon-reload
```
Then delete the bucket copy: `gcloud storage rm -r gs://nfl-predictions-503414-raw/host-migration/<date>` (it holds your
DraftKings entries exports).

**B7. Monitors (optional, recommended):** the units restored in B6 reference `~/projects/nfl-predictions/.venv` and
scripts in the main checkout; enable the ones you had: `systemctl --user enable --now nfl-production-monitor-heartbeat.timer
nfl-cloud-run-lane-monitor.service nfl-cloud-build-monitor.service nfl-lab-action-note-monitor.service`.

**B8. DraftKings pulls (defect 18):** Cloud Run is 403-blocked by DraftKings, so the hourly salary/status pull AND the contest-lobby pull run from the host loop: after B6, start `setsid nohup /home/erich/week1-sunday/host_ingest_dk_loop.sh > /home/erich/week1-sunday/host_ingest_dk_loop.log 2>&1 < /dev/null &`; stop the workstation's copy first with `kill $(cat /home/erich/week1-sunday/host_ingest_dk_loop.pid)`. Without it there are no Week-2 salaries, contest fills, projections or builds.

**B9. Windows-side path:** if the laptop's Windows user folder is not `C:\Users\Erich`, set `WIN_DOWNLOADS` in
`/home/erich/week2-sunday-watchers.sh` (used to pick up DraftKings' entries export on Sunday).

---

## Part C — first assistant session on the laptop

Open Claude Code in `~/projects/nfl-predictions` and say:

> Resumed on the laptop after the machine move. Read `reports/2026-09-15-week2-operating-handoff.md` and the top of
> `HANDOFF.md`, adjudicate any launcher-registry receipts that name the old workstation's pids, check what is still
> running in the cloud, and tell me what the next action is.

It will: mark the old host's receipts adjudicated (they hold process ids that do not exist here), confirm the 097
repairs and the admission-cap cohort results (either finished on the workstation before shutdown, or to be
relaunched here), and continue the Week-2 plan (Thursday: contests file, rehearsal on the Week-2 draft group,
the three timer commands for you).

---

## Verification checklist (five minutes)

- [ ] `git -C ~/projects/nfl-predictions log --oneline -1 origin/main` shows `cc392bf8` or newer.
- [ ] `bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM nfl_raw.contest_entries'` returns a number.
- [ ] `ls ~/week1-sunday/tools ~/week1-sunday/direct_runner/results | head` shows the tools and 54 slate files.
- [ ] `ls ~/.local/state/nfl-dfs/lab-launcher-registry/launchers` (receipts to adjudicate, Part C).
- [ ] `cat ~/week2-sunday/contests.json` still shows `REPLACE` markers (to be filled Thursday).
- [ ] `source ~/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912/scripts/week_env.sh && week_env 2`
      prints the Week-2 draft group (only after DraftKings posts Week-2 salaries, usually Wednesday).

## Do not copy

The old laptop checkouts (moved aside in B2), any `.venv`, `~/week1-sunday/direct_runner/work` (download cache),
`~/worktree-archive` (unless asked), `~/.local/state/nfl-dfs/*` other than `lab-launcher-registry`, and nothing from
`/tmp`.

---

## Part D — what the laptop is good for, and what the video card can and cannot do (added 2026-09-17)

**Status:** the move is deferred until after Week 2 (you decided to stay on the workstation through Sunday). Parts A–C
still apply when you do move; this part is about how to use the laptop once it is restored.

### D1. Where the time goes, so you know what hardware matters

A Sunday build or a lab bank slate is one long chain of integer-program solves (the CBC solver): the leverage loop
first, then one solve per simulated world. Each solve is single-threaded and the chain is sequential by construction, so
the wall time is set by **how fast one core is and how many cores you can keep busy at once**, not by memory or by the
GPU. Measured on the workstation (i9-9900K, 8 cores / 16 threads): D800 4 min, D3200 51 min, D6400 2 h 08 min, a 12,560
stream ≈ 10.7 h; a 72-slate lab bank at 10 workers ≈ 3 days.

### D2. Laptop vs workstation

Your laptop (ROG Strix, mobile i9 of the HX class, 64 GB, NVIDIA GPU) should do well **if it is kept cool and awake**:

| | workstation (9900K) | laptop (mobile i9 HX, typical) |
|---|---|---|
| cores / threads | 8 / 16 | 24 / 32 (8 performance + 16 efficiency cores on most HX parts) |
| one solve | baseline | similar or a little faster on a performance core; slower on an efficiency core |
| lab bank workers | 10 | ~16–20 (efficiency cores are fine for solves) → a bank in roughly half the time |
| Sunday builds (2–3 at once) | fine | fine |
| risk | none new | **thermal throttling** under a day of full load (many laptops fall to 60–70 % of peak after the first hour), sleep/hibernate killing detached runs, battery |

Before the first heavy run on the laptop:
1. Windows: power plan "Best performance", plugged in, sleep and hibernate off while plugged in, lid-close action "do
   nothing" if you close it.
2. `C:\Users\<you>\.wslconfig` — same as the workstation's change: `memory=56GB` (leave 8 GB for Windows), then
   `wsl --shutdown` from PowerShell with VS Code closed.
3. Let the first lab bank be the shakedown: watch `cat /proc/loadavg` and the per-slate times in the bank's task log
   after two hours. If per-slate times are drifting up, the laptop is throttling; reduce the worker count (the number
   after the driver script) rather than letting it run hot.

**Recommended split once both machines are set up:** one machine runs the Sunday money path (the one you will be at on
Sunday morning), the other runs lab banks. Lab runs are attach-aware (they skip slates already uploaded), so a bank can
even be split across both machines by starting the same driver on each; they never collide because each finished slate
is uploaded to the bucket before the next starts.

### D3. The video card: what it would and would not speed up

Nothing on the Sunday path uses a GPU. The solver is integer programming on the CPU; the simulations and the selection
matrix are numpy and already take minutes. Putting the GPU under the money path would mean replacing CBC with a GPU
integer-program solver (NVIDIA's cuOpt has one). That changes the frozen construction — solutions can differ on ties —
so it would be a preregistered equivalence study first, never a Sunday change. Not before Week 2 settles, and probably
not worth it: the chain is sequential, so a faster solver helps linearly at best.

Where the GPU **is** useful is the same place the project already rents cloud GPUs (L4 on Cloud Run, ≈ $0.70/hour, a few
minutes per week): the TabPFN projection job and the LEM training/rollout jobs. Running those locally saves a few dollars
a week and removes a cloud dependency; the benefit is mostly being able to iterate on them without a build-and-deploy
cycle.

### D4. Running the GPU training jobs on the laptop — what is involved

The jobs are ordinary Python scripts that today run inside a CUDA container on Cloud Run:

| job | source | what it does | cloud cadence |
|---|---|---|---|
| `tabpfn-gen` | `scripts/tabpfn_gen/gen.py` (+ `features.txt`) | fits TabPFN marginals per season and writes `features.tabpfn_projections`; `TABPFN_UPCOMING=season:week` adds the live week | weekly Wednesday + after every `build-features` |
| `tabpfn-comp` | `scripts/tabpfn_experiment.py` and the `tabpfn_*` folders | comparison / experiment runs | on demand |
| `lem-train`, `lem-rollout` | `scripts/lem_train/train_lem.py`, `rollout_eval.py` | trains and evaluates the lineup model | on demand |

To run them locally (one-time setup, about an hour, all inside WSL):
1. **GPU visible in WSL.** Install the current NVIDIA Windows driver (the WSL CUDA support comes with it; do NOT install a
   Linux driver inside WSL). Check with `nvidia-smi` in the WSL terminal — it must list the card.
2. **A GPU Python environment**, matching the container: `python3 -m venv ~/gpu-venv && ~/gpu-venv/bin/pip install
   torch --index-url https://download.pytorch.org/whl/cu124 "tabpfn==2.2.1" pandas pyarrow db-dtypes
   google-cloud-bigquery`, then `~/gpu-venv/bin/python -c "import torch; print(torch.cuda.is_available())"` → `True`.
3. **Credentials** are the ones you already have (`gcloud auth application-default login`); the scripts read and write
   BigQuery directly, so `GCP_PROJECT=nfl-predictions-503414` must be exported in the shell (the DK-loop lesson).
4. **Run** the same script the container runs, with the same environment variables the Cloud Run job carries (the
   assistant can print them with `gcloud run jobs describe tabpfn-gen --format=json`), e.g.
   `TABPFN_UPCOMING=2026:3 GCP_PROJECT=nfl-predictions-503414 ~/gpu-venv/bin/python scripts/tabpfn_gen/gen.py`.
5. **Keep the cloud job as the scheduled path** until a local run has produced byte-identical (or documented-equivalent)
   rows for one week; then the Wednesday scheduler can be paused and a local timer used instead. The TabPFN output feeds
   projections, so the equivalence check matters.

What it would NOT change: the Sunday build time, the lab bank time, or any result in the ledger. Treat it as convenience
and a small saving, to set up on a quiet week.
