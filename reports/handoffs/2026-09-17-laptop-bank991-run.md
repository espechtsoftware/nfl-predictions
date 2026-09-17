# Handoff to the second machine: run PREREG-099 bank 991 (2026-09-17)

**For the agent or operator on the laptop.** This is a self-contained lab job. It touches no production warehouse, no
Cloud Run, no DraftKings data, and nothing on the workstation. It writes only result files into the lab bucket.

## Why

PREREG-099 (the 12,560-candidate supply study) was cut from two simulator banks to one on 2026-09-17 to get an answer
before the weekend (amendment 2). `LAB_RULES.md` prefers two banks, because one bank cannot show whether an effect
survives a different random draw. The workstation is running bank 990; this machine can run bank **991** over the same
18 slates in parallel, restoring the replication at no cost to the live week.

## Hard requirement: code identity

The frozen reader refuses a cohort whose shards disagree on `code_sha` or `benchmark`. The runner takes `code_sha` from
`git rev-parse --short HEAD` **at the moment each shard is written**, so the checkout must sit at exactly the commit
bank 990's shards carry: **`c06b2cd`** (`lab/prereg099-supply12800-20260916`, amendment 4). Check out that commit
detached and do not commit, pull, or switch branches while the run is alive. Untracked files are fine — the driver
below is meant to be untracked.

## Setup (once, ~20 minutes)

```
git clone https://github.com/espechtsoftware/nfl2.git ~/projects/nfl2
cd ~/projects/nfl2 && git checkout --detach c06b2cd && git rev-parse --short HEAD     # must print c06b2cd
python3 -m venv .venv && .venv/bin/pip install -e .
gcloud auth login && gcloud auth application-default login                            # account espechtsoftware@gmail.com
gcloud storage ls gs://nfl-2-506823-lab/results/119_dose12800/ | tail -n 2            # proves lab bucket access
```

Also required: plugged in, sleep and hibernate disabled, and the WSL memory limit raised (`.wslconfig`, `memory=56GB`,
then `wsl --shutdown` with the editor closed). Each slate is a 13–16 hour single-threaded run.

## The driver (save as `~/projects/nfl2/run_bank991.sh`, leave it untracked)

```bash
#!/usr/bin/env bash
# PREREG-099 bank 991 on the 2021 panel (task indices 0-17), laptop copy. Attach-aware: rerunning skips finished slates.
#   RUN_ID=119b991r1-<UTCSTAMP> ./run_bank991.sh [WORKERS]
set -uo pipefail
cd "$(dirname "$0")"
WORKERS=${1:-16}
BUCKET=gs://nfl-2-506823-lab/results/119_dose12800
RID=${RUN_ID:?set RUN_ID, e.g. RUN_ID=119b991r1-$(date -u +%Y%m%dT%H%M%SZ)}
[ "$(git rev-parse --short HEAD)" = "c06b2cd" ] || { echo "HEAD is not c06b2cd; refusing"; exit 1; }
export PYTHONPATH=$PWD/src NFL2_RESULTS=$PWD/results
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export OMP_THREAD_LIMIT=1 OMP_WAIT_POLICY=PASSIVE     # LightGBM overrides OMP_NUM_THREADS; without this 10+ workers thrash
export PY=$PWD/.venv/bin/python EXPERIMENT=experiments/119_dose12800.py
echo $$ > run_bank991.pid
run_task() {
  local rid=$1 idx=$2 tag; tag=$(printf 't%02d' "$idx")
  if gcloud storage ls "$BUCKET/$rid/result-$tag.json" >/dev/null 2>&1; then echo "$(date -u +%FT%TZ) $tag exists, skip"; return 0; fi
  mkdir -p "results/119_local/$rid"
  RUN_ID=$rid CLOUD_RUN_TASK_INDEX=$idx CLOUD_RUN_TASK_COUNT=72 \
    $PY -m nfl2.run $EXPERIMENT --bank=991 > "results/119_local/$rid/$tag.log" 2>&1
  echo "$(date -u +%FT%TZ) $tag exit $?"
}
export -f run_task; export BUCKET PY EXPERIMENT
seq 0 17 | xargs -P "$WORKERS" -I{} bash -c "run_task $RID {}" | tee -a run_bank991_tasks.log
echo "shards: $(gcloud storage ls "$BUCKET/$RID/" 2>/dev/null | grep -c result-t)/18"
```

Start it detached and record the run id:

```
cd ~/projects/nfl2 && chmod +x run_bank991.sh
RUN_ID=119b991r1-$(date -u +%Y%m%dT%H%M%SZ) setsid nohup ./run_bank991.sh 16 > run_bank991.log 2>&1 < /dev/null &
sleep 120 && head -n 3 run_bank991.log && cat run_bank991.pid
```

Within two minutes every worker should have a `cbc` child and the load average should sit near the worker count. If the
load climbs far above it, the OpenMP cap is not in effect — stop and say so.

## Checking and reporting

- Progress: `gcloud storage ls gs://nfl-2-506823-lab/results/119_dose12800/119b991r1-<stamp>/ | wc -l` (18 = complete).
- Report to the workstation agent by pushing a branch in `nfl2`: `review/2026-09-bank991-<yourname>` with a file in
  `handoffs/` naming the run id, the shard count, any non-zero task exits (with the failing `results/119_local/<run
  id>/tNN.log` tail), and the wall time per slate. Or simply tell the operator the run id; the workstation agent polls
  the bucket.
- **Do not run the reader.** Reading is single-shot and belongs to the workstation agent, who holds the frozen
  protocol; a second read would consume a development look.

## Deadline rule (frozen here, before any 991 shard exists)

Bank 990 completes on the workstation around midday Friday 2026-09-18. The read happens when 990 is complete:

- If bank 991 is also complete by **Friday 18:00Z**, both banks are read as one cohort, and the frozen DOUBLING rule
  additionally requires each bank's own ratio ≥ 1.5 (the `BANK_FLOOR` already in the reader).
- If 991 is not complete by then, bank 990 is read alone exactly as amendment 2 specifies, and 991 is finished
  afterwards and reported as a separate replication row in `LEDGER.md`.

This is a time rule, not an outcome rule: nobody may look at either bank's numbers before deciding which applies.
