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
UPSTREAM_ID=20260816-atlas-matched-diversity-mvp-v1-repair2
UPSTREAM="$ROOT/reports/atlas-matched-diversity-runs/$UPSTREAM_ID"
UPSTREAM_PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$UPSTREAM_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-historical-score-diagnostic-protocol.md"
PROTOCOL_SHA=4b618b5f8b8b8ed61dc5518e5b8b1cb8d5941e92f088ddb0a53af05d37f4239e
PARITY_AMENDMENT="$ROOT/reports/2026-08-16-atlas-historical-score-source-parity-amendment.md"
PARITY_AMENDMENT_SHA=6e3997e4e81ffe20063fdf76aff7c3655cdd1424aea350a5e29a681a1cd1832e
SHARDED_AMENDMENT="$ROOT/reports/2026-08-16-atlas-historical-score-sharded-upstream-amendment.md"
SHARDED_AMENDMENT_SHA=ce32274be00678cdef24b3d174578a2e2ce212164166da2a712a9df1562fcd5d
CBC_RETRY_PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-cbc-single-shard-retry.md"
CBC_RETRY_PROTOCOL_SHA=bc55775c5a98a7027a0c117cf5371a67cc886c6da34dcdb7b1031bd6a471c455
UPSTREAM_CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9
UPSTREAM_IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
UPSTREAM_MANIFEST_SHA=080c85700219ac246b093f2556c474f4bd79257809cf0e006766a1ed48e95d24
UPSTREAM_ORIGINAL_EXECUTION_LEDGER_SHA=6794f8e608497613aec2f06f2bd13e57cf08b945d7ac20e2d4d00eb1ee3d5ea5
UPSTREAM_EXECUTION_LEDGER_SHA=cb7d54fa9dd3dd9a61a19006477ae6cc974ca0597966eb88385723905031bbfd
UPSTREAM_FAILED_EXECUTION_SHA=28b6f509d22d1b217ccf995f80e337d14f370f97b67ee7e319886a1b7e29191f
UPSTREAM_FAILED_LOG_SHA=fe9c3d0a542c5e651b3c522b9154213d8cea47d5ac0b48650e0c5cd765e26249
UPSTREAM_REPLACEMENT_RECEIPT_SHA=f71831c7f81850493a7b418427cb5dcfac5e06c3871ba2f270222d65a6eb575d
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
[ "$(sha256sum "$SHARDED_AMENDMENT" | awk '{print $1}')" = "$SHARDED_AMENDMENT_SHA" ] || {
  echo "ERROR: ATLAS historical sharded-upstream amendment differs" >&2; exit 2; }
[ "$(sha256sum "$CBC_RETRY_PROTOCOL" | awk '{print $1}')" = "$CBC_RETRY_PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS historical CBC retry protocol differs" >&2; exit 2; }
[ "$(sha256sum "$UPSTREAM/manifest.txt" | awk '{print $1}')" = "$UPSTREAM_MANIFEST_SHA" ] || {
  echo "ERROR: strict upstream ATLAS launch manifest differs" >&2; exit 2; }
[ "$(sha256sum "$UPSTREAM/executions.txt" | awk '{print $1}')" = "$UPSTREAM_ORIGINAL_EXECUTION_LEDGER_SHA" ] && \
  [ "$(sha256sum "$UPSTREAM/effective-executions.txt" | awk '{print $1}')" = "$UPSTREAM_EXECUTION_LEDGER_SHA" ] && \
  [ "$(sha256sum "$UPSTREAM/failed-execution.json" | awk '{print $1}')" = "$UPSTREAM_FAILED_EXECUTION_SHA" ] && \
  [ "$(sha256sum "$UPSTREAM/failed-log.json" | awk '{print $1}')" = "$UPSTREAM_FAILED_LOG_SHA" ] && \
  [ "$(sha256sum "$UPSTREAM/replacement-execution.txt" | awk '{print $1}')" = "$UPSTREAM_REPLACEMENT_RECEIPT_SHA" ] || {
  echo "ERROR: strict upstream ATLAS execution/replacement receipt differs" >&2; exit 2; }
for NAME in report.json completion.txt season-2023.json season-2024.json season-2025.json shards.sha256 execution-metadata.sha256; do
  [ -s "$UPSTREAM/$NAME" ] || {
    echo "ERROR: strict upstream ATLAS harvest lacks $NAME" >&2; exit 2; }
done
[ -d "$UPSTREAM/execution-metadata" ] && \
  [ "$(find "$UPSTREAM/execution-metadata" -maxdepth 1 -name '*.json' | wc -l)" = 54 ] || {
  echo "ERROR: strict upstream ATLAS execution metadata differs" >&2; exit 2; }
[ -d "$UPSTREAM/shards" ] && \
  [ "$(find "$UPSTREAM/shards" -maxdepth 1 -name 'slate-*.json' | wc -l)" = 54 ] || {
  echo "ERROR: strict upstream ATLAS shard harvest differs" >&2; exit 2; }
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
    CBC_RETRY_PROTOCOL_SHA256, PROJECT, UPSTREAM_CODE_SHA,
    UPSTREAM_EXECUTIONS, UPSTREAM_IMAGE,
    _download_json, _upload_create_only, _validate_execution,
)

upstream = Path(sys.argv[1])
prefix, target = sys.argv[2], Path(sys.argv[3])
target_uri = sys.argv[4]
gcs = storage.Client(project=PROJECT)
executions = {}
for (season, week), name in UPSTREAM_EXECUTIONS.items():
    path = upstream / "execution-metadata" / f"{name}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    _validate_execution(value, season, week)
    executions[f"{season}-{week}"] = value
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
    "version": "atlas-historical-upstream-receipt-v3",
    "uses_realized_outcomes": False,
    "upstream_code_sha": UPSTREAM_CODE_SHA,
    "upstream_image": UPSTREAM_IMAGE,
    "upstream_manifest_sha256": sha256(
        (upstream / "manifest.txt").read_bytes()
    ).hexdigest(),
    "upstream_original_execution_ledger_sha256": sha256(
        (upstream / "executions.txt").read_bytes()
    ).hexdigest(),
    "upstream_execution_ledger_sha256": sha256(
        (upstream / "effective-executions.txt").read_bytes()
    ).hexdigest(),
    "cbc_retry_protocol_sha256": CBC_RETRY_PROTOCOL_SHA256,
    "failed_execution_sha256": sha256(
        (upstream / "failed-execution.json").read_bytes()
    ).hexdigest(),
    "failed_log_sha256": sha256(
        (upstream / "failed-log.json").read_bytes()
    ).hexdigest(),
    "replacement_receipt_sha256": sha256(
        (upstream / "replacement-execution.txt").read_bytes()
    ).hexdigest(),
    "single_shard_replacement": {
        "season": 2024, "week": 7,
        "original_execution": "atlas-md-s2024-w7-r2-r9gnq",
        "replacement_execution": "atlas-md-s2024-w7-r2-6l2q2",
    },
    "executions": executions,
    "objects": objects,
    "strict_harvest": {
        "completion_sha256": sha256(
            (upstream / "completion.txt").read_bytes()
        ).hexdigest(),
        "report_sha256": sha256((upstream / "report.json").read_bytes()).hexdigest(),
        "shards_sha256": sha256(
            (upstream / "shards.sha256").read_bytes()
        ).hexdigest(),
        "execution_metadata_sha256": sha256(
            (upstream / "execution-metadata.sha256").read_bytes()
        ).hexdigest(),
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
  "sharded_upstream_amendment_sha256=$SHARDED_AMENDMENT_SHA" \
  "cbc_retry_protocol_sha256=$CBC_RETRY_PROTOCOL_SHA" \
  "upstream_run_id=$UPSTREAM_ID" "upstream_code_sha=$UPSTREAM_CODE_SHA" \
  "upstream_image=$UPSTREAM_IMAGE" \
  "upstream_manifest_sha256=$UPSTREAM_MANIFEST_SHA" \
  "upstream_original_execution_ledger_sha256=$UPSTREAM_ORIGINAL_EXECUTION_LEDGER_SHA" \
  "upstream_execution_ledger_sha256=$UPSTREAM_EXECUTION_LEDGER_SHA" \
  "upstream_failed_execution_sha256=$UPSTREAM_FAILED_EXECUTION_SHA" \
  "upstream_failed_log_sha256=$UPSTREAM_FAILED_LOG_SHA" \
  "upstream_replacement_receipt_sha256=$UPSTREAM_REPLACEMENT_RECEIPT_SHA" \
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
