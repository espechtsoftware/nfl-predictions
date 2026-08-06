#!/bin/bash
# PAIRED confirmatory panel: CE-off control then CE-on treatment, at
# equal per-slate pool size, on ONE immutable image, with an
# independent CE seed.
#
#   bash scripts/paired_panel.sh <IMAGE@sha256:...> <CE_SEED> [FAMILY]
#
# Why each guard exists (2026-08-06 review):
#  * :latest is a moving tag — control and treatment could silently run
#    different code, so an immutable DIGEST is REQUIRED and every
#    execution's resolved digest is verified.
#  * a single scalar GEN_POOL_CAP cannot equalize paired pools because
#    realized counts vary by slate (~157-174). The control emits a
#    per-slate cap manifest; the treatment consumes it verbatim and the
#    runner FAILS if any treatment slate misses its paired cap.
#  * both arms protect the same number of replacement slots (12 CE in
#    treatment, 12 boom in control) — the engine's paired policy.
#  * executions are launched --async and their ids recorded immediately.
set -o pipefail
IMG=$1; SEED=$2; FAM=${3:-rev}
P=/home/erich/nfl-panels
SEASONS=${PANEL_SEASONS:-"2019 2021 2022 2023 2024 2025"}

case "$IMG" in
  *@sha256:*) ;;
  *) echo "ABORT: an immutable @sha256 digest is required, got '$IMG'"; exit 2;;
esac
[ -z "$SEED" ] && { echo "ABORT: CE_SEED required (independent-seed rerun)"; exit 2; }
mkdir -p $P

launch() {   # $1 arm  $2 env-suffix
  local ARM=$1 ENVS=$2
  : > $P/${ARM}_execs.txt
  for S in $SEASONS; do
    gcloud run jobs deploy replay-$FAM-$S --image "$IMG" --region us-central1 \
      --command nfl-dfs --args "replay,--season,$S,--contest,gpp,--entries,40" \
      --set-env-vars "^|^GCP_PROJECT=nfl-predictions-503414|GAME_SIM_MODE=possession|$ENVS" \
      --memory 12Gi --cpu 4 --max-retries 0 --task-timeout 10800 >/dev/null 2>&1 || {
        echo "ABORT: deploy failed for $S"; exit 1; }
    # verify the job really carries this digest and this config
    GOT=$(gcloud run jobs describe replay-$FAM-$S --region us-central1 \
          --format="value(spec.template.spec.template.spec.containers[0].image)")
    [ "$GOT" != "$IMG" ] && { echo "ABORT: $S image is $GOT, want $IMG"; exit 1; }
    BEFORE=$(gcloud run jobs executions list --job replay-$FAM-$S --region us-central1 \
             --limit 1 --format="value(name)")
    gcloud run jobs execute replay-$FAM-$S --region us-central1 --async >/dev/null 2>&1
    for _ in $(seq 1 20); do
      E=$(gcloud run jobs executions list --job replay-$FAM-$S --region us-central1 \
          --limit 1 --format="value(name)")
      [ "$E" != "$BEFORE" ] && break
      sleep 5
    done
    [ "$E" = "$BEFORE" ] && { echo "ABORT: no new execution for $S"; exit 1; }
    echo "$S $E" >> $P/${ARM}_execs.txt
  done
  echo "$ARM launched: $(wc -l < $P/${ARM}_execs.txt) executions"
}

wait_arm() {  # $1 arm
  while read -r S E; do
    while true; do
      C=$(gcloud run jobs executions list --job replay-$FAM-$S --region us-central1 \
          --limit 1 --format="value(status.completionTime)" 2>/dev/null)
      [ -n "$(echo $C | tr -d ' ')" ] && break
      sleep 120
    done
  done < $P/$1_execs.txt
  sleep 45
}

harvest() {   # $1 arm -> results + per-slate pool sizes
  : > $P/$1_pools.txt
  echo "=== ARM $1 (image $IMG, seed $SEED) ===" > $P/$1_results.txt
  while read -r S E; do
    L=$(gcloud logging read "resource.type=\"cloud_run_job\" labels.\"run.googleapis.com/execution_name\"=\"$E\"" \
        --limit 2000 --order=asc --format="value(textPayload)" 2>/dev/null)
    echo "--- season $S ($E)" >> $P/$1_results.txt
    echo "$L" | grep -E "tail: mean best|median finish" | head -2 >> $P/$1_results.txt
    echo "$L" | grep -oE "pool final: [0-9]+ wk[0-9]+ n=[0-9]+" >> $P/$1_pools.txt
  done < $P/$1_execs.txt
}

echo "== CONTROL (CE off, 40 boom) =="
launch control "N_CE=0|N_BOOM=40"
wait_arm control
harvest control

# build the per-slate cap manifest from the control's realized pools
python3 - "$P/control_pools.txt" "$P/cap_map.json" <<'PY'
import json, re, sys
caps = {}
for ln in open(sys.argv[1]):
    m = re.search(r"pool final: (\d+) wk(\d+) n=(\d+)", ln)
    if m:
        caps[f"{m.group(1)}-{m.group(2)}"] = int(m.group(3))
json.dump(caps, open(sys.argv[2], "w"))
print(f"cap manifest: {len(caps)} slates, "
      f"range {min(caps.values())}-{max(caps.values())}")
PY
MAP=$(cat $P/cap_map.json)

echo "== TREATMENT (CE 12 / boom 28, paired caps, seed $SEED) =="
launch treatment "N_CE=12|N_BOOM=28|CE_SEED=$SEED|GEN_POOL_CAP_MAP=$MAP"
wait_arm treatment
harvest treatment

# the pairing must be EXACT, per slate
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
bad = [(k, c[k], t.get(k)) for k in sorted(c) if t.get(k) != c[k]]
print(f"paired slates: {len(c)}; mismatched: {len(bad)}")
for k, cv, tv in bad[:10]:
    print(f"  MISMATCH {k}: control {cv} treatment {tv}")
raise SystemExit(1 if bad else 0)
PY
[ $? -ne 0 ] && { echo "PAIRING FAILED — results not comparable"; exit 1; }
echo "PAIRED_PANEL_DONE — pools exactly equal per slate"
