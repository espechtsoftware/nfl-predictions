#!/bin/bash
# Retry only report transport after the successful analyzer JSON was truncated.
# Usage: cloud_retry_multiseed_candidate_world_transport.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
IMG=${1:-}
CODE_SHA=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1"
MANIFEST="$OUT/manifest.txt"
PRIOR=$(tr -d '[:space:]' < "$OUT/analyzer_execution.txt")
RETRY_EXEC="$OUT/analyzer_retry_execution.txt"
RETRY_MANIFEST="$OUT/analyzer_retry_manifest.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable retry image required"; exit 2;; esac
case "$CODE_SHA" in ''|*[!0-9a-f]*) echo "ABORT: lowercase hexadecimal retry code required"; exit 2;; esac
[ -s "$MANIFEST" ] && [ -s "$OUT/raw_log_truncated.txt" ] && \
  [ -e "$OUT/truncated_report.json" ] || {
    echo "ABORT: original truncation evidence is incomplete"; exit 2; }
[ ! -e "$RETRY_EXEC" ] && [ ! -e "$RETRY_MANIFEST" ] && \
  [ ! -e "$OUT/report.json" ] || {
    echo "ABORT: multi-seed retry/output already exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$PRIOR" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || { echo "ABORT: original analyzer was not successful"; exit 2; }
"$ROOT/.venv/bin/python" - "$OUT/raw_log_truncated.txt" <<'PY'
import json
import sys

raw = open(sys.argv[1], encoding="utf-8").read()
prefix = "MULTISEED_CANDIDATE_WORLD_JSON="
if len(raw.encode("utf-8")) < 100_000 or not raw.startswith(prefix):
    raise SystemExit("ABORT: Cloud Logging truncation signature absent")
partial = raw.splitlines()[0][len(prefix):]
try:
    json.loads(partial)
except json.JSONDecodeError as exc:
    if "Unterminated string" not in str(exc):
        raise SystemExit("ABORT: unexpected truncated JSON error") from exc
else:
    raise SystemExit("ABORT: prior report was not truncated")
PY

SOURCE_CODE=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
SOURCE_ARM=$(awk -F= '$1=="source_arm" {print $2}' "$MANIFEST")
case "$SOURCE_ARM" in control|treatment) ;; *) echo "ABORT: source arm differs"; exit 2;; esac
JOB=analyze-multiseed-candidate-world-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_multiseed_candidate_world.py,--expected-code-sha,$SOURCE_CODE,--source-arm,$SOURCE_ARM" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 14400 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: retry image differs"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: retry execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$RETRY_EXEC"
printf '%s\n' \
  "retry_image=$IMG" "retry_code_sha=$CODE_SHA" \
  "prior_execution=$PRIOR" \
  'retry_reason=cloud_logging_single_entry_truncation' \
  "source_code_sha=$SOURCE_CODE" "source_arm=$SOURCE_ARM" > "$RETRY_MANIFEST"
echo "MULTISEED_CANDIDATE_WORLD_TRANSPORT_RETRIED $EXEC"
