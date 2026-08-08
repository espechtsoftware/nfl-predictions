#!/bin/bash
# PAIRED confirmatory panel: CE-off control then CE-on treatment, at
# equal per-slate pool size, on ONE immutable image, with an
# independent CE seed.
#
#   bash scripts/paired_panel.sh <IMAGE@sha256:...> <CE_SEED> <FAMILY>
#
# FAMILY must be a dedicated, non-default name (e.g. ceconf1) so the
# panel cannot overwrite the shared replay-rev-* / replay-g2-* jobs.
#
# Guards, each from a specific review finding:
#  * :latest is a moving tag — control and treatment could silently run
#    different code, so an immutable DIGEST is REQUIRED and the digest
#    is re-read from each EXECUTION.
#  * execution IDs are captured from `execute --async` itself, never by
#    polling "the job's latest execution" — a scheduler or another
#    operator could otherwise have its run harvested as ours.
#  * completionTime alone is NOT success: a failed or cancelled
#    execution has one too. Every execution must report Completed=True
#    with succeededCount=1 and failedCount=0.
#  * a scalar cap cannot equalize paired pools (realized counts vary
#    ~157-174/slate); the control emits a per-slate cap manifest that
#    must cover EVERY slate, and the treatment must match it exactly.
set -o pipefail
IMG=$1; SEED=$2; FAM=$3
P=/home/erich/nfl-panels
SEASONS=${PANEL_SEASONS:-"2019 2021 2022 2023 2024 2025"}
REGION=us-central1

case "$IMG" in
  *@sha256:*) ;;
  *) echo "ABORT: an immutable @sha256 digest is required, got '$IMG'"; exit 2;;
esac
[ -z "$SEED" ] && { echo "ABORT: CE_SEED required (independent-seed rerun)"; exit 2; }
case "$FAM" in
  ""|rev|g2|panel)
    echo "ABORT: dedicated FAMILY required (not '$FAM') — a shared family"
    echo "       would overwrite the standing replay-$FAM-* jobs"; exit 2;;
esac
mkdir -p $P

launch() {   # $1 arm   $2 env-suffix
  local ARM=$1 ENVS=$2 S JOB EXEC GOT
  : > $P/${ARM}_execs.txt
  for S in $SEASONS; do
    JOB=replay-$FAM-$S
    gcloud run jobs deploy $JOB --image "$IMG" --region $REGION \
      --command nfl-dfs --args "replay,--season,$S,--contest,gpp,--entries,40" \
      --set-env-vars "^|^GCP_PROJECT=nfl-predictions-503414|GAME_SIM_MODE=possession|$ENVS" \
      --memory 12Gi --cpu 4 --max-retries 0 --task-timeout 10800 >/dev/null 2>&1 \
      || { echo "ABORT: deploy failed for $JOB"; exit 1; }
    # the execution NAME comes from the launch itself — never from
    # "list --limit 1", which can return someone else's execution
    EXEC=$(gcloud run jobs execute $JOB --region $REGION --async \
           --format='value(metadata.name)' 2>/dev/null)
    [ -z "$EXEC" ] && { echo "ABORT: no execution id returned for $JOB"; exit 1; }
    GOT=$(gcloud run jobs executions describe "$EXEC" --region $REGION \
          --format="value(spec.template.spec.containers[0].image)" 2>/dev/null)
    [ "$GOT" != "$IMG" ] && {
      echo "ABORT: execution $EXEC runs $GOT, want $IMG"; exit 1; }
    echo "$S $JOB $EXEC" >> $P/${ARM}_execs.txt
  done
  echo "$ARM launched: $(wc -l < $P/${ARM}_execs.txt) executions on $IMG"
}

wait_arm() {  # $1 arm — completion AND success, per recorded execution id
  local S JOB EXEC ST SUCC FAIL
  while read -r S JOB EXEC; do
    while true; do
      ST=$(gcloud run jobs executions describe "$EXEC" --region $REGION \
           --format="value(status.conditions[0].type,status.conditions[0].status,status.succeededCount,status.failedCount)" 2>/dev/null)
      case "$ST" in
        Completed*True*) break;;
        *Failed*|*False*) : ;;
      esac
      C=$(gcloud run jobs executions describe "$EXEC" --region $REGION \
          --format="value(status.completionTime)" 2>/dev/null)
      if [ -n "$(echo $C | tr -d ' ')" ]; then break; fi
      sleep 120
    done
    SUCC=$(gcloud run jobs executions describe "$EXEC" --region $REGION \
           --format="value(status.succeededCount)" 2>/dev/null)
    FAIL=$(gcloud run jobs executions describe "$EXEC" --region $REGION \
           --format="value(status.failedCount)" 2>/dev/null)
    ST=$(gcloud run jobs executions describe "$EXEC" --region $REGION \
         --format="value(status.conditions[0].type,status.conditions[0].status)" 2>/dev/null)
    # a failed or cancelled execution ALSO has a completionTime
    if [ "${SUCC:-0}" != "1" ] || [ "${FAIL:-0}" != "0" ] \
       || [ "$(echo $ST | tr -d ' \t')" != "CompletedTrue" ]; then
      echo "ABORT: $EXEC did not succeed (state='$ST' succeeded=$SUCC failed=$FAIL)"
      exit 1
    fi
  done < $P/$1_execs.txt
  sleep 30
}

harvest() {   # $1 arm -> results + per-slate pool sizes
  local S JOB EXEC L
  : > $P/$1_pools.txt
  echo "=== ARM $1 (image $IMG, seed $SEED, family $FAM) ===" > $P/$1_results.txt
  while read -r S JOB EXEC; do
    L=$(gcloud logging read "resource.type=\"cloud_run_job\" labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
        --limit 2000 --order=asc --format="value(textPayload)" 2>/dev/null)
    echo "--- season $S ($EXEC)" >> $P/$1_results.txt
    echo "$L" | grep -E "tail: mean best|median finish" | head -2 >> $P/$1_results.txt
    echo "$L" | grep -oE "pool final: [0-9]+ wk[0-9]+ n=[0-9]+" >> $P/$1_pools.txt
  done < $P/$1_execs.txt
}

echo "== CONTROL (CE off, 40 boom) =="
launch control "N_CE=0|N_BOOM=40"
wait_arm control
harvest control

python3 - "$P/control_pools.txt" "$P/cap_map.json" "$SEASONS" <<'PY' 
import json, re, sys
caps = {}
for ln in open(sys.argv[1]):
    m = re.search(r"pool final: (\d+) wk(\d+) n=(\d+)", ln)
    if m:
        caps[f"{m.group(1)}-{m.group(2)}"] = int(m.group(3))
seasons = sys.argv[3].split()
missing = [s for s in seasons
           if not any(k.startswith(f"{s}-") for k in caps)]
if missing or not caps:
    print(f"ABORT: control produced no cap entries for {missing or 'any season'}")
    raise SystemExit(1)
json.dump(caps, open(sys.argv[2], "w"))
print(f"cap manifest: {len(caps)} slates, "
      f"range {min(caps.values())}-{max(caps.values())}")
PY
[ $? -ne 0 ] && { echo "ABORT: cap manifest incomplete"; exit 1; }
MAP=$(cat $P/cap_map.json)

echo "== TREATMENT (CE 12 / boom 28, paired caps, seed $SEED) =="
launch treatment "N_CE=12|N_BOOM=28|CE_SEED=$SEED|GEN_POOL_CAP_MAP=$MAP"
wait_arm treatment
harvest treatment

python3 - "$P/control_pools.txt" "$P/treatment_pools.txt" <<'PY' 
import re, sys
def load(p):
    d = {}
    for ln in open(p):
        m = re.search(r"pool final: (\d+) wk(\d+) n=(\d+)", ln)
        if m:
            d[(m.group(1), m.group(2))] = int(m.group(3))
    return d
c, t = load(sys.argv[1]), load(sys.argv[2])
missing = [k for k in c if k not in t]
bad = [(k, c[k], t[k]) for k in sorted(c) if k in t and t[k] != c[k]]
print(f"paired slates: {len(c)}; missing in treatment: {len(missing)}; "
      f"mismatched: {len(bad)}")
for k, cv, tv in bad[:10]:
    print(f"  MISMATCH {k}: control {cv} treatment {tv}")
raise SystemExit(1 if (bad or missing) else 0)
PY
[ $? -ne 0 ] && { echo "PAIRING FAILED — results are not comparable"; exit 1; }
echo "PAIRED_PANEL_DONE — pools exactly equal per slate"
