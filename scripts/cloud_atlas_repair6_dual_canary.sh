#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_repair6_dual_canary.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-atlas-matched-diversity-mvp-v1-repair6
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
PROOF_PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/${RUN_ID}-proof
PROTOCOL="$ROOT/reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md"
PROTOCOL_SHA=b4a98543b1dcd776d50ae00e380fbc695346debb0de6452131fdfd0ba7c2820a
CLASSIFICATION="$OUT/eligibility-classification.json"
ELIGIBLE="$OUT/eligible-cells.txt"
PROOF="$OUT/code-diff-proof.json"
MANIFEST="$OUT/manifest.txt"
LEDGER="$OUT/canary-executions.txt"
PENDING="$OUT/canary-executions.pending.txt"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable ATLAS repair6 image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: exact ATLAS repair6 code commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful ATLAS repair6 build ID is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS repair6 protocol differs" >&2; exit 2; }
for REQUIRED in "$OUT/classification-completion.txt" "$CLASSIFICATION" \
  "$ELIGIBLE" "$PROOF" "$OUT/repair5-failure-logs.sha256"; do
  [ -s "$REQUIRED" ] || {
    echo "ERROR: ATLAS repair6 classification is incomplete: $REQUIRED" >&2
    exit 2
  }
done
[ ! -e "$LEDGER" ] && [ ! -e "$OUT/canary-completion.txt" ] || {
  echo "ERROR: immutable ATLAS repair6 dual-canary receipt exists" >&2; exit 3; }

git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}"
for RELATIVE in Dockerfile cloudbuild.yaml \
  reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md \
  src/nfl_dfs/analysis/atlas_world_ranking.py \
  src/nfl_dfs/research/atlas_repair6.py \
  src/nfl_dfs/research/atlas_repair6_hybrid.py \
  scripts/run_atlas_matched_diversity_mvp.py \
  scripts/render_atlas_matched_diversity_repair4_command.py \
  scripts/validate_atlas_repair6_code_diff.py \
  scripts/prepare_atlas_repair6_classification.py \
  scripts/cloud_atlas_repair6_dual_canary.sh \
  scripts/finish_atlas_repair6_dual_canary.py \
  scripts/cloud_atlas_repair6_grid.sh \
  scripts/finish_atlas_repair6_hybrid_population.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: ATLAS repair6 built source differs: $RELATIVE" >&2; exit 2; }
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$CLASSIFICATION" "$ELIGIBLE" "$PROOF" <<'PY'
from hashlib import sha256
import json, pathlib, sys
classification_path, eligible_path, proof_path = map(pathlib.Path, sys.argv[1:])
classification=json.loads(classification_path.read_text())
proof=json.loads(proof_path.read_text())
eligible=[line.split() for line in eligible_path.read_text().splitlines() if line]
if classification.get("disposition")!="repair6-dual-canary-licensed" or \
   classification.get("repair6_launch_licensed") is not True or \
   classification.get("uses_realized_outcomes") is not False or \
   classification.get("candidate_or_lineup_scores_read") is not False or \
   len(eligible)!=len(classification.get("eligible_tiebreak_failures",[])) or \
   any(len(row)!=6 for row in eligible) or \
   not any(row[0:2]==["2023","7"] for row in eligible) or \
   proof.get("disposition")!="valid-exact-identity-tiebreak-extension" or \
   proof.get("tolerances")!=[1e-6,1e-5,1e-4]:
 raise SystemExit("ERROR: ATLAS repair6 classification/proof differs")
for path in (classification_path, eligible_path, proof_path):
 receipt=path.with_suffix(".sha256")
 expected=f"{sha256(path.read_bytes()).hexdigest()}  {path}\n"
 if not receipt.is_file() or receipt.read_text()!=expected:
  raise SystemExit("ERROR: ATLAS repair6 classification hash differs")
PY

BUILD_TMP=$(mktemp)
trap 'rm -f "$BUILD_TMP"' EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --region="$REGION" \
  --format=json > "$BUILD_TMP"
"$ROOT/.venv/bin/python" - "$BUILD_TMP" "$IMAGE" "$CODE_SHA" <<'PY'
import json,sys
b=json.load(open(sys.argv[1],encoding="utf-8")); image,code=sys.argv[2:]
tag=("us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:"
     f"atlas-repair6-{code[:7]}")
digest=image.rsplit("@",1)[1]
steps={row.get("id"):row.get("status") for row in b.get("steps",[])}
required={"full-test-suite","build-image","smoke-atlas-mvp-runner"}
if b.get("status")!="SUCCESS" or b.get("substitutions",{}).get("_IMAGE")!=tag or \
   any(steps.get(name)!="SUCCESS" for name in required) or \
   not any(row.get("name")==tag and row.get("digest")==digest
           for row in b.get("results",{}).get("images",[])):
 raise SystemExit("ERROR: ATLAS repair6 build identity differs")
PY

GRID_COMMAND=$("$ROOT/.venv/bin/python" \
  "$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py" \
  --replacement-prefix "$PREFIX")
DEFECT_JOB=atlas-md-s2023-w7-r6
DEFECT_URI=$PREFIX/slate-2023-7.json
PROOF_JOB=atlas-md-s2023-w1-r6-proof
PROOF_URI=$PROOF_PREFIX/slate-2023-1.json

if [ ! -s "$MANIFEST" ]; then
  [ ! -e "$PENDING" ] || {
    echo "ERROR: ATLAS repair6 ledger exists without manifest" >&2; exit 3; }
  for SPEC in "$DEFECT_JOB:$DEFECT_URI" "$PROOF_JOB:$PROOF_URI"; do
    JOB=${SPEC%%:*}; URI=${SPEC#*:}
    EXISTING=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format='value(metadata.name)' 2>/dev/null || true)
    [ -z "$EXISTING" ] || {
      echo "ERROR: ATLAS repair6 canary job already has an execution: $JOB" >&2
      exit 3
    }
    if gcloud storage objects describe "$URI" --project "$PROJECT" \
        >/dev/null 2>&1; then
      echo "ERROR: ATLAS repair6 canary object already exists: $URI" >&2; exit 3
    fi
  done
  printf '%s\n' \
    "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
    "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
    "proof_prefix=$PROOF_PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
    "classification_sha256=$(sha256sum "$CLASSIFICATION" | awk '{print $1}')" \
    "eligible_cells_sha256=$(sha256sum "$ELIGIBLE" | awk '{print $1}')" \
    "code_diff_proof_sha256=$(sha256sum "$PROOF" | awk '{print $1}')" \
    "launcher_sha256=$(sha256sum "$ROOT/scripts/cloud_atlas_repair6_dual_canary.sh" | awk '{print $1}')" \
    "finisher_sha256=$(sha256sum "$ROOT/scripts/finish_atlas_repair6_dual_canary.py" | awk '{print $1}')" \
    "grid_launcher_sha256=$(sha256sum "$ROOT/scripts/cloud_atlas_repair6_grid.sh" | awk '{print $1}')" \
    "hybrid_finisher_sha256=$(sha256sum "$ROOT/scripts/finish_atlas_repair6_hybrid_population.py" | awk '{print $1}')" \
    "hybrid_source_sha256=$(sha256sum "$ROOT/src/nfl_dfs/research/atlas_repair6_hybrid.py" | awk '{print $1}')" \
    'repair5_w1_execution=atlas-md-s2023-w1-r5-45nvf' \
    'repair5_w1_uri=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5/slate-2023-1.json' \
    'repair5_w1_generation=1786971235274440' \
    "grid_command_sha256=$(printf %s "$GRID_COMMAND" | sha256sum | awk '{print $1}')" \
    'tasks=1' 'parallelism=1' 'cpu=8' 'memory=32Gi' \
    'timeout_seconds=43200' 'max_retries=0' \
    'uses_realized_outcomes=false' 'production_change_licensed=false' \
    > "$MANIFEST"
  sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
else
  [ -s "$OUT/manifest.sha256" ] || {
    echo "ERROR: ATLAS repair6 manifest receipt is missing" >&2; exit 3; }
fi

for SPEC in \
  $'defect\t2023\t7\t'"$DEFECT_JOB"$'\t'"$DEFECT_URI" \
  $'proof\t2023\t1\t'"$PROOF_JOB"$'\t'"$PROOF_URI"; do
  IFS=$'\t' read -r ROLE SEASON WEEK JOB URI <<< "$SPEC"
  [ -n "$ROLE" ] && [ -n "$SEASON" ] && [ -n "$WEEK" ] && \
    [ -n "$JOB" ] && [[ "$URI" == gs://* ]] || {
    echo "ERROR: ATLAS repair6 canary specification differs" >&2; exit 2; }
  if ! awk -v role="$ROLE" '$1==role {found=1} END {exit !found}' \
      "$PENDING" 2>/dev/null; then
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 8 --memory 32Gi \
      --max-retries 0 --task-timeout 12h --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
      --command python --args=-c,"$GRID_COMMAND",--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
      --quiet >/dev/null
    LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
      --region "$REGION" --format='value(metadata.name)' 2>/dev/null || true)
    if [ -z "$LISTED" ]; then
      EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --format='value(metadata.name)')
    else
      [ "$(printf '%s\n' "$LISTED" | sed '/^$/d' | wc -l)" = 1 ] || {
        echo "ERROR: ATLAS repair6 canary has extra executions: $JOB" >&2; exit 3; }
      EXECUTION=$LISTED
    fi
    [[ "$EXECUTION" == "$JOB-"* ]] || {
      echo "ERROR: ATLAS repair6 execution identity differs" >&2; exit 2; }
    printf '%s %s %s %s %s %s\n' \
      "$ROLE" "$SEASON" "$WEEK" "$JOB" "$EXECUTION" "$URI" >> "$PENDING"
  fi
done
[ "$(wc -l < "$PENDING")" = 2 ] || {
  echo "ERROR: ATLAS repair6 dual-canary ledger is incomplete" >&2; exit 2; }
mv "$PENDING" "$LEDGER"
sha256sum "$LEDGER" > "$OUT/canary-executions.sha256"
mv "$BUILD_TMP" "$OUT/build-metadata.json"
sha256sum "$OUT/build-metadata.json" > "$OUT/build-metadata.sha256"
trap - EXIT
echo "ATLAS_REPAIR6_DUAL_CANARY_LAUNCHED"
