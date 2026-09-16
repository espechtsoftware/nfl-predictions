# Moving from the workstation to the laptop — your step-by-step guide (2026-09-15)

Everything durable is already on GitHub (both repos, every branch) and in Google Cloud. The move is about three
things: not killing what is still running here, carrying over the small amount of host-only state, and starting
clean on the laptop. Budget about an hour of hands-on time, most of it waiting for downloads and installs.

Use the same WSL username (`erich`) and home directory on the laptop. Every script defaults to `/home/erich/...`.

---

## Part A — on the workstation, before you shut it down

**A1. What is still running here (updated 2026-09-16 morning).** The admission-cap cohort and the PREREG-097
repairs are finished and read. The only live host process is the hourly DraftKings pull loop
(`host_ingest_dk_loop.sh`, defect 18): stop it here just before you pack (`pkill -f host_ingest_dk_loop`) and start
it on the laptop in B8. Ask the assistant "is anything still running on this machine?" before you start, in case
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
```
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

**B8. DraftKings pulls (defect 18):** Cloud Run is 403-blocked by DraftKings, so the hourly salary/status pull runs from the host: after B6, start `setsid nohup /home/erich/week1-sunday/host_ingest_dk_loop.sh > /home/erich/week1-sunday/host_ingest_dk_loop.log 2>&1 < /dev/null &` and stop the copy on the workstation before you shut it down (`pkill -f host_ingest_dk_loop`). Without it there are no Week-2 salaries, projections or builds.

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
