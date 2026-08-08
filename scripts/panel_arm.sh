#!/bin/bash
# Six-season panel arm runner (repo-tracked, reviewable).
#
# Replaces the untracked ~/nfl-panels/panel_rev4.sh: a control runner
# that lives outside the repository cannot be reviewed, and its
# CE-off change could not be verified from a commit.
#
#   bash scripts/panel_arm.sh <ARM> <FAMILY> <ENTRIES> [EXTRA_ENV]
#
# Production defaults are the boom-only 0 CE / 40 boom baseline. This
# runner states that control explicitly and uses EXTRA_ENV only for a
# treatment arm (e.g. "N_CE=12|N_BOOM=28|GEN_POOL_CAP=160").
set -o pipefail
ARM=$1; FAM=${2:-rev}; ENT=${3:-40}; ENVS=$4
[ -z "$ARM" ] && { echo "usage: panel_arm.sh ARM [FAMILY] [ENTRIES] [ENV]"; exit 2; }
IMG=${PANEL_IMAGE:-us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:latest}
SEASONS=${PANEL_SEASONS:-"2019 2021 2022 2023 2024 2025"}
OUT=/home/erich/nfl-panels/$(echo $ARM | tr 'A-Z' 'a-z')_results.txt
mkdir -p /home/erich/nfl-panels
echo "=== ARM $ARM (image $IMG) ===" | tee $OUT

declare -A BEFORE
for S in $SEASONS; do
  E="^|^GCP_PROJECT=nfl-predictions-503414|GAME_SIM_MODE=possession|N_CE=0|N_BOOM=40"
  [ -n "$ENVS" ] && E="$E|$ENVS"
  gcloud run jobs deploy replay-$FAM-$S --image $IMG --region us-central1 \
    --command nfl-dfs --args "replay,--season,$S,--contest,gpp,--entries,$ENT" \
    --set-env-vars "$E" \
    --memory 12Gi --cpu 4 --max-retries 0 --task-timeout 10800 >/dev/null 2>&1
  BEFORE[$S]=$(gcloud run jobs executions list --job replay-$FAM-$S \
    --region us-central1 --limit 1 --format="value(name)")
  gcloud run jobs execute replay-$FAM-$S --region us-central1 >/dev/null 2>&1
done

sleep 45
for S in $SEASONS; do   # a silent no-op deploy must never look like a result
  N=$(gcloud run jobs executions list --job replay-$FAM-$S --region us-central1 \
      --limit 1 --format="value(name)")
  [ "$N" = "${BEFORE[$S]}" ] && { echo "ABORT: no new execution for $S" | tee -a $OUT; exit 1; }
  BEFORE[$S]=$N
done

while true; do
  BUSY=0
  for S in $SEASONS; do
    C=$(gcloud run jobs executions list --job replay-$FAM-$S --region us-central1 \
        --limit 1 --format="value(status.completionTime)" 2>/dev/null)
    [ -z "$(echo $C | tr -d ' ')" ] && BUSY=1
  done
  [ $BUSY -eq 0 ] && break
  sleep 150
done
sleep 45

for S in $SEASONS; do
  echo "--- season $S (${BEFORE[$S]})" >> $OUT
  gcloud logging read "resource.type=\"cloud_run_job\" labels.\"run.googleapis.com/execution_name\"=\"${BEFORE[$S]}\"" \
    --limit 1200 --order=asc --format="value(textPayload)" 2>/dev/null \
    | grep -E "tail: mean best|median finish|pool trimmed|CE round|weekly best by generator" \
    | head -8 >> $OUT
done
echo "${ARM}_DONE" | tee -a $OUT
