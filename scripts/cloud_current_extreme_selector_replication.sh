#!/bin/bash
# Launch the one frozen current-stack replication of the extreme selector.
# Usage: bash scripts/cloud_current_extreme_selector_replication.sh IMAGE@sha256:...
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PANEL=20260812-pitclean-e80-selected-tabpfn-active-v2
OUT="$ROOT/reports/selector-runs/${PANEL}-extreme-replication"
ACCEPT="$ROOT/reports/panel-runs/$PANEL/acceptance_check.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$ACCEPT" ] && grep -q 'ACCEPTANCE PASSED' "$ACCEPT" || {
  echo "ABORT: accepted source panel is not recorded"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable selector replication already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'image=%s\npanel=%s\ntable=replay_candidates\nselector=220-210-200-lex\nentries=80\nexpected_slates=54\nlabel=post-original-result-current-stack-replication\n' \
  "$IMG" "$PANEL" > "$OUT/manifest.txt"

JOB=current-extreme-selector-replication
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "corrected-extreme-selector,--panel,$PANEL,--table,replay_candidates,--expected-slates,54" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 2Gi --cpu 1 \
  --max-retries 0 --task-timeout 1800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: selector deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: selector execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "CURRENT_EXTREME_SELECTOR_REPLICATION_LAUNCHED $EXEC"
