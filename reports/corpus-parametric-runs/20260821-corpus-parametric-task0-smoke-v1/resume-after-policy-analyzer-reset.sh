#!/usr/bin/env bash
# One-shot operator continuation after the 2026-08-22 Policy Analyzer reset.
# It takes three exact access captures, configures the accepted smoke contract,
# and consumes the producer launch exactly once. It never retries a launch.

set -euo pipefail

PROJECT="nfl-predictions-503414"
SERVICE_ACCOUNT="corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com"
MEMBER="serviceAccount:${SERVICE_ACCOUNT}"
EXACT_TREE="/tmp/nfl-predictions-corpus-12ee7ce"
PYTHON_BIN="/tmp/nfl-corpus-py311/bin/python"
RUN_ROOT="/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260821-corpus-parametric-task0-smoke-v1"
GOVERNANCE_DIR="${RUN_ROOT}/governance-live"
TRANSPORT_DIR="${RUN_ROOT}/transport-live"
LOG_FILE="${RUN_ROOT}/resume-after-policy-analyzer-reset.log"
RESET_EPOCH="$(date -d '2026-08-22T00:01:00-07:00' +%s)"

[[ "$(date +%s)" -ge "$RESET_EPOCH" ]] || {
  printf '%s\n' "refusing to consume Policy Analyzer quota before reset" >&2
  exit 2
}
[[ -e "$EXACT_TREE/.git" && -x "$PYTHON_BIN" ]] || {
  printf '%s\n' "exact worktree or Python runtime is unavailable" >&2
  exit 2
}
[[ "$(git -C "$EXACT_TREE" rev-parse HEAD)" == "12ee7cefa4d6b093562696e17f82a0bdef126636" ]] || {
  printf '%s\n' "exact worktree revision differs" >&2
  exit 2
}
[[ ! -e "$LOG_FILE" && ! -e "$TRANSPORT_DIR" ]] || {
  printf '%s\n' "one-shot local output namespace is already consumed" >&2
  exit 2
}

mkdir -p "$GOVERNANCE_DIR"
for path in \
  "$GOVERNANCE_DIR/project-policy-reset.raw.json" \
  "$GOVERNANCE_DIR/role-create-reset.raw.json" \
  "$GOVERNANCE_DIR/role-get-reset.raw.json" \
  "$GOVERNANCE_DIR/asset-runtime-reset.raw.json" \
  "$GOVERNANCE_DIR/asset-all-users-reset.raw.json" \
  "$GOVERNANCE_DIR/asset-all-authenticated-users-reset.raw.json" \
  "$GOVERNANCE_DIR/runtime-iam-policy-capture.json"; do
  [[ ! -e "$path" ]] || {
    printf '%s\n' "one-shot evidence path is already consumed: $path" >&2
    exit 2
  }
done

exec >"$LOG_FILE" 2>&1
printf '%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ') reset continuation started"

gcloud projects get-iam-policy "$PROJECT" --format=json \
  >"$GOVERNANCE_DIR/project-policy-reset.raw.json"
gcloud iam roles describe corpusParametricObjectCreateV2 \
  --project="$PROJECT" --format=json \
  >"$GOVERNANCE_DIR/role-create-reset.raw.json"
gcloud iam roles describe corpusParametricObjectGetV2 \
  --project="$PROJECT" --format=json \
  >"$GOVERNANCE_DIR/role-get-reset.raw.json"

for bucket in \
  nfl-predictions-503414-corpus-parametric \
  nfl-predictions-503414-corpus-retrieval \
  nfl-predictions-503414-corpus-source \
  nfl-predictions-503414-raw; do
  metadata="$GOVERNANCE_DIR/${bucket}-metadata-reset.raw.json"
  policy="$GOVERNANCE_DIR/${bucket}-policy-reset.raw.json"
  [[ ! -e "$metadata" && ! -e "$policy" ]] || {
    printf '%s\n' "one-shot bucket evidence path is already consumed" >&2
    exit 2
  }
  { printf '%s' 'Authorization: Bearer '; gcloud auth print-access-token; } |
    curl --fail-with-body --silent --show-error --header @- \
      "https://storage.googleapis.com/storage/v1/b/${bucket}" >"$metadata"
  { printf '%s' 'Authorization: Bearer '; gcloud auth print-access-token; } |
    curl --fail-with-body --silent --show-error --header @- \
      "https://storage.googleapis.com/storage/v1/b/${bucket}/iam?optionsRequestedPolicyVersion=3" \
      >"$policy"
done

analyze_once() {
  local identity="$1"
  local output="$2"
  local headers="$3"
  { 
    printf '%s' 'Authorization: Bearer '
    gcloud auth print-access-token
    printf 'x-goog-user-project: %s\n' "$PROJECT"
  } | curl --fail-with-body --silent --show-error --header @- \
    --dump-header "$headers" --output "$output" --get \
    "https://cloudasset.googleapis.com/v1/projects/${PROJECT}:analyzeIamPolicy" \
    --data-urlencode "analysisQuery.identitySelector.identity=${identity}" \
    --data-urlencode 'analysisQuery.options.expandGroups=true' \
    --data-urlencode 'analysisQuery.options.expandResources=true' \
    --data-urlencode 'analysisQuery.options.expandRoles=true' \
    --data-urlencode 'analysisQuery.options.outputGroupEdges=true' \
    --data-urlencode 'analysisQuery.options.outputResourceEdges=true'
}

analyze_once "$MEMBER" \
  "$GOVERNANCE_DIR/asset-runtime-reset.raw.json" \
  "$GOVERNANCE_DIR/asset-runtime-reset.headers.txt"
jq -e '
  .fullyExplored == true and
  .mainAnalysis.fullyExplored == true and
  ((.nonCriticalErrors // []) | length) == 0 and
  ((.mainAnalysis.nonCriticalErrors // []) | length) == 0 and
  (.mainAnalysis.analysisResults | length) == 5
' "$GOVERNANCE_DIR/asset-runtime-reset.raw.json" >/dev/null

analyze_once allUsers \
  "$GOVERNANCE_DIR/asset-all-users-reset.raw.json" \
  "$GOVERNANCE_DIR/asset-all-users-reset.headers.txt"
jq -e '
  .fullyExplored == true and
  .mainAnalysis.fullyExplored == true and
  ((.nonCriticalErrors // []) | length) == 0 and
  ((.mainAnalysis.nonCriticalErrors // []) | length) == 0 and
  ((.mainAnalysis.analysisResults // []) | length) == 0
' "$GOVERNANCE_DIR/asset-all-users-reset.raw.json" >/dev/null

analyze_once allAuthenticatedUsers \
  "$GOVERNANCE_DIR/asset-all-authenticated-users-reset.raw.json" \
  "$GOVERNANCE_DIR/asset-all-authenticated-users-reset.headers.txt"
jq -e '
  .fullyExplored == true and
  .mainAnalysis.fullyExplored == true and
  ((.nonCriticalErrors // []) | length) == 0 and
  ((.mainAnalysis.nonCriticalErrors // []) | length) == 0 and
  ((.mainAnalysis.analysisResults // []) | length) == 0
' "$GOVERNANCE_DIR/asset-all-authenticated-users-reset.raw.json" >/dev/null

export GOVERNANCE_DIR
cd "$EXACT_TREE"
"$PYTHON_BIN" - <<'PY'
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "scripts"))
import run_corpus_parametric_transport as transport

root = Path(os.environ["GOVERNANCE_DIR"])


def load(name: str) -> object:
    return json.loads((root / name).read_bytes())


buckets = sorted([
    "nfl-predictions-503414-corpus-parametric",
    "nfl-predictions-503414-corpus-retrieval",
    "nfl-predictions-503414-corpus-source",
    "nfl-predictions-503414-raw",
])
body = {
    "schema_version": transport.RUNTIME_IAM_CAPTURE_SCHEMA,
    "captured_at_utc": datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z"),
    "project": transport.PROJECT,
    "project_policy": load("project-policy-reset.raw.json"),
    "custom_role_definitions": sorted([
        load("role-create-reset.raw.json"),
        load("role-get-reset.raw.json"),
    ], key=lambda row: row["name"]),
    "bucket_policies": [
        {"bucket": bucket, "policy": load(f"{bucket}-policy-reset.raw.json")}
        for bucket in buckets
    ],
    "bucket_metadata": [
        {"bucket": bucket, "metadata": load(f"{bucket}-metadata-reset.raw.json")}
        for bucket in buckets
    ],
    "effective_access_analyses": {
        "runtime_identity": load("asset-runtime-reset.raw.json"),
        "all_users": load("asset-all-users-reset.raw.json"),
        "all_authenticated_users": load(
            "asset-all-authenticated-users-reset.raw.json"
        ),
    },
}
output = root / "runtime-iam-policy-capture.json"
output.write_bytes(transport.canonical_json_bytes(
    transport._self_hash(body, field="capture_sha256")
))
print(output)
PY

export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_PYTHON="$PYTHON_BIN"
export CORPUS_PARAMETRIC_RUN_DIR="$TRANSPORT_DIR"
export CORPUS_PARAMETRIC_JOB="atlas-minimal-c-s2023-w1-v1"
export CORPUS_PARAMETRIC_IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:e099b4a4feeeb2ee3e738f4661c941950181412505d28c5926d734a534e8ce69"
export CORPUS_PARAMETRIC_BUILD_ID="0332dff4-ee9d-45b2-a3c1-41dc1891cf60"
export CORPUS_PARAMETRIC_CODE_SHA="12ee7cefa4d6b093562696e17f82a0bdef126636"
export CORPUS_PARAMETRIC_SERVICE_ACCOUNT="$SERVICE_ACCOUNT"
export CORPUS_PARAMETRIC_EXPECTED_JOB_UID="d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
export CORPUS_PARAMETRIC_RUNTIME_IAM_FILE="$GOVERNANCE_DIR/runtime-iam-policy-capture.json"
export CORPUS_PARAMETRIC_BUILD_METADATA_FILE="$TRANSPORT_DIR/build-metadata.json"
export CORPUS_PARAMETRIC_TASK_INDEX=0
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI="gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260821-corpus-parametric-task0-smoke-foundation-v1/governance/publication-completion.json"
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_GENERATION="1787371186298971"
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_SHA256="6e6b0f56ea4d15934e8d7e64b7464fa5bd231c8a73329e2a653f070788b1fadc"
export CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_BYTES=7570
export CORPUS_PARAMETRIC_MANIFEST_URI="gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260821-corpus-parametric-task0-smoke-batch-v1/governance/batch-manifest.json"
export CORPUS_PARAMETRIC_MANIFEST_GENERATION="1787371185539011"
export CORPUS_PARAMETRIC_MANIFEST_SHA256="e6eab1f49d0b8eb2b5e8839417fe76167ae72574dbee93c0a034d1a6339bcbfc"
export CORPUS_PARAMETRIC_MANIFEST_BYTES=12646
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_URI="gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260821-corpus-parametric-task0-smoke-batch-v1/governance/pre-run-evidence-contract.json"
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_GENERATION="1787371185939824"
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_SHA256="86b59961f76143d981e4f392e9c9907521493d78909a22870da6c0ed795d85bd"
export CORPUS_PARAMETRIC_EVIDENCE_CONTRACT_BYTES=38493
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_URI="gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260821-corpus-parametric-task0-smoke-foundation-v1/governance/retrieval-task0-accepted-prerequisite.json"
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_GENERATION="1787371181409093"
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_SHA256="1e2090aaf88085c5fb99ad1b07e480b0d0db5cb0606b5edd464703b3a7f89c85"
export CORPUS_PARAMETRIC_RETRIEVAL_PREREQUISITE_BYTES=1925

bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute configure

configured="$TRANSPORT_DIR/configured.json"
export CORPUS_PARAMETRIC_CONTRACT_URI="$(jq -er '.transport_contract.uri' "$configured")"
export CORPUS_PARAMETRIC_CONTRACT_GENERATION="$(jq -er '.transport_contract.generation | tostring' "$configured")"
export CORPUS_PARAMETRIC_CONTRACT_SHA256="$(jq -er '.transport_contract.sha256' "$configured")"
export CORPUS_PARAMETRIC_CONTRACT_BYTES="$(jq -er '.transport_contract.bytes | tostring' "$configured")"

bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute launch-producer
printf '%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ') producer launch consumed; recover only"
