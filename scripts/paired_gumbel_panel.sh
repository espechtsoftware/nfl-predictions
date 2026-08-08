#!/bin/bash
# Audited fixed-budget Gumbel panel: 40-boom control versus a treatment
# replacing 20 boom solves with 20 Gumbel perturb-and-MAP solves. Both arms
# use one immutable image and exactly equal realized candidate-pool sizes.
#
#   bash scripts/paired_gumbel_panel.sh <IMAGE@sha256:...> <SEED> <FAMILY> [MODE]
# MODE is independent (the archived arm) or hierarchical (frozen equal-
# variance game/team/player shocks).
set -o pipefail
IMG=$1; SEED=$2; FAM=$3; MODE=${4:-independent}
P=/home/erich/nfl-panels/$FAM
SEASONS=${PANEL_SEASONS:-"2019 2021 2022 2023 2024 2025"}
REGION=us-central1

case "$IMG" in
  *@sha256:*) ;;
  *) echo "ABORT: immutable @sha256 image required, got '$IMG'"; exit 2;;
esac
[ -z "$SEED" ] && { echo "ABORT: independent GUMBEL_SEED required"; exit 2; }
case "$MODE" in
  independent|hierarchical) ;;
  *) echo "ABORT: MODE must be independent or hierarchical"; exit 2;;
esac
case "$FAM" in
  ""|rev|g2|panel|ceconf1)
    echo "ABORT: dedicated FAMILY required (not '$FAM')"; exit 2;;
esac
mkdir -p "$P"

launch() {
  local ARM=$1 ENVS=$2 S JOB EXEC GOT
  : > "$P/${ARM}_execs.txt"
  for S in $SEASONS; do
    JOB=replay-$FAM-$S
    gcloud run jobs deploy "$JOB" --image "$IMG" --region "$REGION" \
      --command nfl-dfs --args "replay,--season,$S,--contest,gpp,--entries,40" \
      --set-env-vars "^|^GCP_PROJECT=nfl-predictions-503414|GAME_SIM_MODE=possession|$ENVS" \
      --memory 12Gi --cpu 4 --max-retries 0 --task-timeout 10800 >/dev/null 2>&1 \
      || { echo "ABORT: deploy failed for $JOB"; exit 1; }
    EXEC=$(gcloud run jobs execute "$JOB" --region "$REGION" --async \
           --format='value(metadata.name)' 2>/dev/null)
    [ -z "$EXEC" ] && { echo "ABORT: no execution id for $JOB"; exit 1; }
    GOT=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
          --format='value(spec.template.spec.containers[0].image)' 2>/dev/null)
    [ "$GOT" != "$IMG" ] && {
      echo "ABORT: $EXEC runs $GOT, want $IMG"; exit 1; }
    echo "$S $JOB $EXEC" >> "$P/${ARM}_execs.txt"
  done
  echo "$ARM launched: $(wc -l < "$P/${ARM}_execs.txt") executions"
}

wait_arm() {
  local S JOB EXEC ST SUCC FAIL DONE
  while read -r S JOB EXEC; do
    while true; do
      ST=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
           --format='value(status.conditions[0].type,status.conditions[0].status)' 2>/dev/null)
      [ "$(echo "$ST" | tr -d ' \t')" = "CompletedTrue" ] && break
      DONE=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
             --format='value(status.completionTime)' 2>/dev/null)
      [ -n "$(echo "$DONE" | tr -d ' ')" ] && break
      sleep 60
    done
    SUCC=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
           --format='value(status.succeededCount)' 2>/dev/null)
    FAIL=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
           --format='value(status.failedCount)' 2>/dev/null)
    ST=$(gcloud run jobs executions describe "$EXEC" --region "$REGION" \
         --format='value(status.conditions[0].type,status.conditions[0].status)' 2>/dev/null)
    if [ "${SUCC:-0}" != "1" ] || [ "${FAIL:-0}" != "0" ] \
       || [ "$(echo "$ST" | tr -d ' \t')" != "CompletedTrue" ]; then
      echo "ABORT: $EXEC failed (state='$ST' succeeded=$SUCC failed=$FAIL)"
      exit 1
    fi
  done < "$P/${1}_execs.txt"
  sleep 30
}

harvest() {
  local ARM=$1 S JOB EXEC L
  : > "$P/${ARM}_pools.txt"
  echo "=== $ARM image=$IMG seed=$SEED family=$FAM ===" > "$P/${ARM}_results.txt"
  while read -r S JOB EXEC; do
    L=$(gcloud logging read "resource.type=\"cloud_run_job\" labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
        --limit 2500 --order=asc --format='value(textPayload)' 2>/dev/null)
    echo "--- season $S ($EXEC)" >> "$P/${ARM}_results.txt"
    echo "$L" | grep -E 'tail: mean best|median finish' | head -2 >> "$P/${ARM}_results.txt"
    echo "$L" | grep -oE 'pool final: [0-9]+ wk[0-9]+ n=[0-9]+' >> "$P/${ARM}_pools.txt"
  done < "$P/${ARM}_execs.txt"
}

echo "== CONTROL: 40 boom, 20 protected replacement slots =="
launch control 'N_CE=0|N_BOOM=40|N_GUMBEL=0|REPLACEMENT_SLOTS=20'
wait_arm control
harvest control

python3 - "$P/control_pools.txt" "$P/cap_map.json" "$SEASONS" <<'PY'
import json, re, sys
caps = {}
for line in open(sys.argv[1]):
    m = re.search(r"pool final: (\d+) wk(\d+) n=(\d+)", line)
    if m:
        caps[f"{m.group(1)}-{m.group(2)}"] = int(m.group(3))
missing = [s for s in sys.argv[3].split()
           if not any(k.startswith(f"{s}-") for k in caps)]
if missing or not caps:
    print(f"ABORT: incomplete control cap map; missing seasons={missing}")
    raise SystemExit(1)
json.dump(caps, open(sys.argv[2], "w"))
print(f"cap manifest: {len(caps)} slates, range {min(caps.values())}-{max(caps.values())}")
PY
[ $? -ne 0 ] && { echo "ABORT: cap manifest incomplete"; exit 1; }
MAP=$(tr -d '\n' < "$P/cap_map.json")

echo "== TREATMENT: 20 boom + 20 Gumbel ($MODE), slots protected =="
launch treatment "N_CE=0|N_BOOM=20|N_GUMBEL=20|GUMBEL_SCALE=2.0|GUMBEL_MODE=$MODE|GUMBEL_SEED=$SEED|REPLACEMENT_SLOTS=20|GEN_POOL_CAP_MAP=$MAP"
wait_arm treatment
harvest treatment

python3 - "$P/control_pools.txt" "$P/treatment_pools.txt" <<'PY'
import re, sys
def load(path):
    out = {}
    for line in open(path):
        m = re.search(r"pool final: (\d+) wk(\d+) n=(\d+)", line)
        if m:
            out[(m.group(1), m.group(2))] = int(m.group(3))
    return out
c, t = load(sys.argv[1]), load(sys.argv[2])
missing = sorted(set(c) - set(t))
extra = sorted(set(t) - set(c))
bad = [(k, c[k], t[k]) for k in sorted(set(c) & set(t)) if c[k] != t[k]]
print(f"paired={len(c)} missing={len(missing)} extra={len(extra)} mismatched={len(bad)}")
raise SystemExit(1 if missing or extra or bad or len(c) != 107 else 0)
PY
[ $? -ne 0 ] && { echo "PAIRING FAILED"; exit 1; }
echo "GUMBEL_PAIRED_PANEL_DONE"
