#!/bin/bash
# Run the full B2 -> instrumented-rebuild equality proof in Cloud Run.
# Usage: bash scripts/cloud_compare_exact_replay.sh <IMAGE@sha256:...> <REFERENCE> <CANDIDATE> [promoted|staging] [full|slate-only]
set -euo pipefail

IMG=${1:-}
REFERENCE=${2:-}
CANDIDATE=${3:-}
REFERENCE_MODE=${4:-promoted}
SCOPE=${5:-full}
REGION=us-central1
PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$CANDIDATE"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$REFERENCE" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid reference panel"; exit 2;; esac
case "$CANDIDATE" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid candidate panel"; exit 2;; esac
case "$REFERENCE_MODE" in promoted|staging) ;; *) echo "ABORT: reference mode is promoted or staging"; exit 2;; esac
case "$SCOPE" in full|slate-only) ;; *) echo "ABORT: scope is full or slate-only"; exit 2;; esac
[ -d "$OUT" ] || { echo "ABORT: candidate report directory absent: $OUT"; exit 2; }

JOB=compare-exact-replay
ARGS="scripts/compare_exact_replay.py,$REFERENCE,$CANDIDATE"
[ "$REFERENCE_MODE" = "promoted" ] || ARGS="$ARGS,--reference-staging"
[ "$SCOPE" = "full" ] || ARGS="$ARGS,--candidate-slate-only"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null

DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: comparator deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/exact_rebuild_execution.txt"

harvest_logs() {
  # A compact JSON stdout record is recognized by Cloud Logging and stored as
  # jsonPayload rather than textPayload.  Ask for only that structured entry;
  # the resulting one-element JSON envelope is complete and parseable even
  # when the comparator exits non-zero to report a mismatch.
  gcloud logging read \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND jsonPayload.passes:*" \
    --project "$PROJECT" --limit 10000 --order asc \
    --format='json(jsonPayload)' > "$OUT/exact_rebuild_comparison.json"
}

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = "True" ] && break
  # completionTime may precede the final Completed=True transition.  Treat
  # only an explicit False as terminal failure.
  if [ "$STATE" = "False" ]; then
    # A failed equality proof is valuable evidence, not disposable output.
    # Harvest it before returning non-zero so the precise differences remain
    # reviewable and committed rather than being stranded in Cloud Logging.
    harvest_logs
    echo "ABORT: exact comparator failed: $EXEC"
    exit 1
  fi
  sleep 30
done

harvest_logs
grep -Eq '"passes":[[:space:]]*true' "$OUT/exact_rebuild_comparison.json" || {
  echo "ABORT: exact-pass marker absent from comparator log"; exit 1; }
echo "Exact rebuild parity passed: $OUT/exact_rebuild_comparison.json"
