#!/usr/bin/env bash
# Deploy one authenticated paid-v3 image and attest observed provider state.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

[[ $# -eq 6 && "$1" == "--execute" ]] || \
  die "usage: $0 --execute FULL_PUSHED_CODE_SHA BUILD_ID IMAGE@sha256 SERVICE RECEIPT.json"
CODE_SHA=$2
BUILD_ID=$3
IMAGE=$4
SERVICE=$5
RECEIPT=$6
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || die "source commit is malformed"
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$ ]] || \
  die "Cloud Build ID is malformed"
[[ "$IMAGE" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] || \
  die "image must be an immutable @sha256 reference"
[[ "$SERVICE" =~ ^[a-z][a-z0-9-]{0,61}[a-z0-9]$ ]] || \
  die "Cloud Run service is malformed"
[[ ! -e "$RECEIPT" ]] || die "attestation output already exists"
command -v git >/dev/null || die "git is required"
command -v gcloud >/dev/null || die "gcloud is required"
command -v jq >/dev/null || die "jq is required"

SOURCE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || \
  die "run from the production repository"
ORIGIN_MAIN_SHA=$(git -C "$SOURCE_ROOT" rev-parse --verify \
  'refs/remotes/origin/main^{commit}') || die "local origin/main is unavailable"
[[ "$ORIGIN_MAIN_SHA" == "$CODE_SHA" ]] || \
  die "source commit must equal local origin/main"
for exact_path in \
  scripts/deploy_paid_boundary_v3_image.sh \
  cloudbuild.paid-boundary-v3.yaml \
  src/nfl_dfs/optimizer/paid_classic_deployment_v3.py; do
  git -C "$SOURCE_ROOT" cat-file -e "${CODE_SHA}:${exact_path}" || \
    die "attestation implementation is absent from the exact source commit"
  git -C "$SOURCE_ROOT" diff --quiet "$CODE_SHA" -- "$exact_path" || \
    die "local attestation implementation differs from the source commit"
done

PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
REGION=${GCP_REGION:-us-central1}
REVISION_SUFFIX="paidv3-${CODE_SHA:0:8}-${BUILD_ID:0:8}"
REVISION="${SERVICE}-${REVISION_SUFFIX}"
[[ ${#REVISION} -le 63 ]] || die "derived Cloud Run revision is too long"
TMP_ROOT="$SOURCE_ROOT/.build-contexts"
mkdir -p "$TMP_ROOT"
TMP=$(mktemp -d "$TMP_ROOT/paid-v3-deploy.XXXXXX")
cleanup() { rm -rf -- "$TMP"; }
trap cleanup EXIT

gcloud builds describe "$BUILD_ID" --project="$PROJECT" --format=json \
  >"$TMP/build.json"
DIGEST=${IMAGE##*@}
jq -e --arg build "$BUILD_ID" --arg code "$CODE_SHA" \
  --arg digest "$DIGEST" '
    .id == $build and .status == "SUCCESS" and
    .substitutions._CODE_SHA == $code and
    (.results.images | length) == 1 and
    .results.images[0].digest == $digest
  ' "$TMP/build.json" >/dev/null || \
  die "Cloud Build provider record does not authenticate this release"
# Authenticate the complete provider build record against the committed build
# law before changing a serving revision or traffic.  The final pass below
# additionally attests the observed Cloud Run service and revision.
PYTHONPATH="$SOURCE_ROOT/src" python -m \
  nfl_dfs.optimizer.paid_classic_deployment_v3 \
  --verify-build-only --build-json "$TMP/build.json" \
  --build-contract "$SOURCE_ROOT/cloudbuild.paid-boundary-v3.yaml" \
  --build-id "$BUILD_ID" --source-commit "$CODE_SHA" --image "$IMAGE" \
  >"$TMP/build-evidence.json"

gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" --platform=managed --quiet \
  --image="$IMAGE" --revision-suffix="$REVISION_SUFFIX" \
  --update-env-vars="IMAGE_SOURCE_COMMIT_SHA=$CODE_SHA,IMAGE_DIGEST=$DIGEST,IMAGE_URI=$IMAGE,PAID_V3_CLOUD_BUILD_ID=$BUILD_ID"

gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json >"$TMP/service.json"
gcloud run revisions describe "$REVISION" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json >"$TMP/revision.json"
PYTHONPATH="$SOURCE_ROOT/src" python -m \
  nfl_dfs.optimizer.paid_classic_deployment_v3 \
  --build-json "$TMP/build.json" --service-json "$TMP/service.json" \
  --revision-json "$TMP/revision.json" \
  --build-contract "$SOURCE_ROOT/cloudbuild.paid-boundary-v3.yaml" \
  --build-id "$BUILD_ID" \
  --source-commit "$CODE_SHA" --image "$IMAGE" --service "$SERVICE" \
  --revision "$REVISION" --output "$RECEIPT"
printf 'PAID_V3_DEPLOYMENT_ATTESTATION=%s\n' "$RECEIPT"
