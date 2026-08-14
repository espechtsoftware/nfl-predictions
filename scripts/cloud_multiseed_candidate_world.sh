#!/bin/bash
# Launch the frozen artifact-only multi-seed factorial after Phase S.
# Usage: cloud_multiseed_candidate_world.sh
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1"
REPORT="$PHASE_S/report.json"
MANIFEST="$PHASE_S/manifest.txt"
PROTOCOL="$ROOT/reports/2026-08-13-multiseed-candidate-world-factorial-protocol.md"
RUN_ID=20260813-multiseed-candidate-world-v1
OUT="$ROOT/reports/multiseed-candidate-world-runs/$RUN_ID"

[ -s "$REPORT" ] && [ -s "$MANIFEST" ] && [ -s "$PROTOCOL" ] || {
  echo "ABORT: harvested Phase S and frozen protocol are required"; exit 2; }
[ ! -e "$OUT/manifest.txt" ] || {
  echo "ABORT: immutable multi-seed run already launched"; exit 2; }
read -r MECHANICAL SOURCE <<< "$("$ROOT/.venv/bin/python" - "$REPORT" <<'PY'
import json
import sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
selected = r.get("result", {}).get("decision", {}).get("selected_arm", "")
print(str(bool(r.get("mechanical_passes"))).lower(), selected)
PY
)"
[ "$MECHANICAL" = true ] || { echo "ABORT: Phase S did not pass"; exit 2; }
case "$SOURCE" in control|treatment) ;; *) echo "ABORT: invalid Phase S arm"; exit 2;; esac
IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image missing"; exit 2;; esac
[ -n "$CODE_SHA" ] || { echo "ABORT: code SHA missing"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "source_arm=$SOURCE" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "phase_s_report_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  'arms=C0W0 C0WU CUW0 CUWU' 'confirmation_arms=CBW0 CBWU' \
  'proper_scores=q95 q99 weekly-selected-book-maximum' \
  'entries=80' 'worlds_per_seed=10000' \
  'replicates=R0 R1 R2 R3 R4' > "$OUT/manifest.txt"

JOB=analyze-multiseed-candidate-world-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python \
  --args "scripts/analyze_multiseed_candidate_world.py,--expected-code-sha,$CODE_SHA,--source-arm,$SOURCE" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 14400 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: analyzer deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: analyzer execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/analyzer_execution.txt"
echo "MULTISEED_CANDIDATE_WORLD_LAUNCHED $EXEC source=$SOURCE"
