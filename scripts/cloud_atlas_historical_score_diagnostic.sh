#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_historical_score_diagnostic.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-historical-score-diagnostic-v1
OUT="$ROOT/reports/atlas-historical-score-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/$RUN_ID
UPSTREAM_ID=20260816-atlas-matched-diversity-mvp-v1-repair1
UPSTREAM="$ROOT/reports/atlas-matched-diversity-runs/$UPSTREAM_ID"
UPSTREAM_PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$UPSTREAM_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md"
PROTOCOL_SHA=4b618b5f8b8b8ed61dc5518e5b8b1cb8d5941e92f088ddb0a53af05d37f4239e
PARITY_AMENDMENT="$ROOT/reports/2026-08-16-atlas-historical-score-source-parity-amendment.md"
PARITY_AMENDMENT_SHA=6e3997e4e81ffe20063fdf76aff7c3655cdd1424aea350a5e29a681a1cd1832e
UPSTREAM_CODE_SHA=44236483bb5bbf874da3f281a66af9e77dc3c9c9
UPSTREAM_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:15916bf8d4ced52cc94f502a2a2979b9e386420aec943208ba0b933d51727771
IMAGE=${1:-}
CODE_SHA=${2:-}

[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable scorer image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full scorer code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS historical protocol differs" >&2; exit 2; }
[ "$(sha256sum "$PARITY_AMENDMENT" | awk '{print $1}')" = "$PARITY_AMENDMENT_SHA" ] || {
  echo "ERROR: ATLAS historical source-parity amendment differs" >&2; exit 2; }
for NAME in report.json completion.txt season-2023.json season-2024.json season-2025.json; do
  [ -s "$UPSTREAM/$NAME" ] || {
    echo "ERROR: strict upstream ATLAS harvest lacks $NAME" >&2; exit 2; }
done
[ -d "$UPSTREAM/execution-metadata" ] && \
  [ "$(find "$UPSTREAM/execution-metadata" -maxdepth 1 -name '*.json' | wc -l)" = 3 ] || {
  echo "ERROR: strict upstream ATLAS execution metadata differs" >&2; exit 2; }
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS historical local run exists" >&2; exit 3; }
for NAME in upstream-receipt.json report.json; do
  if gcloud storage objects describe "$PREFIX/$NAME" \
      --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: immutable ATLAS historical output $NAME exists" >&2
    exit 3
  fi
done

mkdir -p "$OUT"
RECEIPT="$OUT/upstream-receipt.json"
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$UPSTREAM" "$UPSTREAM_PREFIX" "$RECEIPT" "$PREFIX/upstream-receipt.json" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

from google.cloud import storage

from run_atlas_historical_score_diagnostic import (
    PROJECT, UPSTREAM_CODE_SHA, UPSTREAM_EXECUTIONS, UPSTREAM_IMAGE,
    _download_json, _upload_create_only, _validate_execution,
)

upstream = Path(sys.argv[1])
prefix, target = sys.argv[2], Path(sys.argv[3])
target_uri = sys.argv[4]
gcs = storage.Client(project=PROJECT)
executions = {}
for season, name in UPSTREAM_EXECUTIONS.items():
    path = upstream / "execution-metadata" / f"{name}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    _validate_execution(value, season)
    executions[str(season)] = value
objects = {}
for key, name in [
    ("season-2023", "season-2023.json"),
    ("season-2024", "season-2024.json"),
    ("season-2025", "season-2025.json"),
    ("report", "report.json"),
]:
    _, receipt = _download_json(gcs, f"{prefix}/{name}")
    local = upstream / name
    if sha256(local.read_bytes()).hexdigest() != receipt["sha256"]:
        raise SystemExit(f"ERROR: local/GCS strict upstream {name} differs")
    objects[key] = receipt
payload = {
    "version": "atlas-historical-upstream-receipt-v1",
    "uses_realized_outcomes": False,
    "upstream_code_sha": UPSTREAM_CODE_SHA,
    "upstream_image": UPSTREAM_IMAGE,
    "executions": executions,
    "objects": objects,
    "strict_harvest": {
        "completion_sha256": sha256(
            (upstream / "completion.txt").read_bytes()
        ).hexdigest(),
        "report_sha256": sha256((upstream / "report.json").read_bytes()).hexdigest(),
    },
}
raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
target.write_bytes(raw)
upload = _upload_create_only(gcs, target_uri, raw)
print("ATLAS_HISTORICAL_UPSTREAM_RECEIPT " + json.dumps(upload, sort_keys=True))
PY
sha256sum "$RECEIPT" > "$RECEIPT.sha256"

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "source_parity_amendment_sha256=$PARITY_AMENDMENT_SHA" \
  "upstream_run_id=$UPSTREAM_ID" "upstream_code_sha=$UPSTREAM_CODE_SHA" \
  "upstream_image=$UPSTREAM_IMAGE" \
  "upstream_receipt_sha256=$(sha256sum "$RECEIPT" | awk '{print $1}')" \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  'seasons=2023,2024,2025' 'slates=54' 'comparison=P2_vs_P1' \
  > "$OUT/manifest.txt"

JOB=atlas-historical-score-v1
URI="$PREFIX/report.json"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args scripts/run_atlas_historical_score_diagnostic.py,--upstream-receipt-uri,"$PREFIX/upstream-receipt.json",--output-uri,"$URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 8h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS historical execution identity is missing" >&2; exit 1; }
printf '%s %s %s\n' "$JOB" "$EXEC" "$URI" | tee "$OUT/execution.txt"
echo "ATLAS_HISTORICAL_SCORE_DIAGNOSTIC_LAUNCHED $RUN_ID"
