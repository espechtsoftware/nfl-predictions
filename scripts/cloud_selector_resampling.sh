#!/bin/bash
# Launch the frozen score-free selector world-resampling diagnostic.
# Usage: cloud_selector_resampling.sh <AUDIT_IMAGE@sha256:...> <AUDIT_CODE_SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
AUDIT_IMG=${1:-}
AUDIT_CODE=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260814-selector-resampling-v1
OUT="$ROOT/reports/selector-resampling-runs/$RUN_ID"
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1"
REPORT="$PHASE_S/report.json"
SOURCE_MANIFEST="$PHASE_S/manifest.txt"
PROTOCOL="$ROOT/reports/2026-08-14-selector-resampling-score-free-protocol.md"
RECONCILIATION="$ROOT/reports/2026-08-14-selector-stability-resampling-reconciliation.md"
FEEDBACK="$ROOT/reports/2026-08-14-selector-stability-under-world-resampling.md"
FREQUENCY_URI="gs://nfl-predictions-503414-raw/analysis/selector-resampling/$RUN_ID/candidate-frequencies.json.gz"

case "$AUDIT_IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$AUDIT_CODE" in ''|*[!0-9a-f]*) echo "ABORT: lowercase hexadecimal audit code required"; exit 2;; esac
for file in "$REPORT" "$SOURCE_MANIFEST" "$PROTOCOL" "$RECONCILIATION" "$FEEDBACK"; do
  [ -s "$file" ] || { echo "ABORT: required source is missing: $file"; exit 2; }
done
[ ! -e "$OUT/manifest.txt" ] || {
  echo "ABORT: immutable selector-resampling run already launched"; exit 2; }

SOURCE_IMG=$(awk -F= '$1=="image" {print $2}' "$SOURCE_MANIFEST")
SOURCE_CODE=$(awk -F= '$1=="code_sha" {print $2}' "$SOURCE_MANIFEST")
SOURCE_BETA=$(awk -F= '$1=="beta" {print $2}' "$SOURCE_MANIFEST")
case "$SOURCE_IMG" in *@sha256:*) ;; *) echo "ABORT: source image is not immutable"; exit 2;; esac
[ "$SOURCE_CODE" = 4d6f5cf ] || { echo "ABORT: source code identity differs"; exit 2; }
[ "$SOURCE_BETA" = 0.07771181538347656 ] || { echo "ABORT: source beta differs"; exit 2; }
read -r MECHANICAL SELECTED <<< "$("$ROOT/.venv/bin/python" - "$REPORT" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
print(str(bool(r.get("mechanical_passes"))).lower(),
      r.get("result", {}).get("decision", {}).get("selected_arm", ""))
PY
)"
[ "$MECHANICAL" = true ] && [ "$SELECTED" = treatment ] || {
  echo "ABORT: Phase S selected treatment is not mechanically valid"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "audit_image=$AUDIT_IMG" "audit_code_sha=$AUDIT_CODE" \
  "source_image=$SOURCE_IMG" "source_code_sha=$SOURCE_CODE" \
  'source_panel=20260813-sis-asoe-treatment-r0-v1' \
  "source_beta=$SOURCE_BETA" "frequency_artifact_uri=$FREQUENCY_URI" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "reconciliation_sha256=$(sha256sum "$RECONCILIATION" | awk '{print $1}')" \
  "feedback_sha256=$(sha256sum "$FEEDBACK" | awk '{print $1}')" \
  "phase_s_report_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  "phase_s_manifest_sha256=$(sha256sum "$SOURCE_MANIFEST" | awk '{print $1}')" \
  'seasons=2023 2024 2025' 'slates=54' 'entries=80' 'worlds=10000' \
  'line=194' 'bootstrap_resamples=32' 'reads_realized_outcomes=0' \
  > "$OUT/manifest.txt"

JOB=analyze-selector-resampling-v1
ARGS="scripts/analyze_selector_resampling.py,--expected-code-sha,$SOURCE_CODE,--frequency-artifact-uri,$FREQUENCY_URI"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$AUDIT_IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 14400 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$AUDIT_IMG" ] || { echo "ABORT: analyzer image differs"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: analyzer execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/analyzer_execution.txt"
echo "SELECTOR_RESAMPLING_LAUNCHED $EXEC"
