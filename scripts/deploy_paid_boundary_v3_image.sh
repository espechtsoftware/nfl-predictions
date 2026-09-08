#!/usr/bin/env bash
# Deploy one authenticated paid-v3 image through an externally bound authority.
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
[[ "$SERVICE" == "nfl-dfs-app" ]] || \
  die "paid-v3 deployment is pinned to nfl-dfs-app"
[[ ! -e "$RECEIPT" ]] || die "attestation output already exists"
command -v git >/dev/null || die "git is required"
command -v gcloud >/dev/null || die "gcloud is required"
command -v jq >/dev/null || die "jq is required"
command -v sha256sum >/dev/null || die "sha256sum is required"
command -v python >/dev/null || die "the repository Python environment is required"

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

# These coordinates are part of the reviewed paid-v3 law, not deployer input.
PROJECT=nfl-predictions-503414
REGION=us-central1
AUTHORITY_BUCKET="${PROJECT}-paid-authority"
STAGING_SUFFIX="paidv3s-${CODE_SHA:0:8}-${BUILD_ID:0:8}"
ACTIVE_SUFFIX="paidv3-${CODE_SHA:0:8}-${BUILD_ID:0:8}"
STAGING_REVISION="${SERVICE}-${STAGING_SUFFIX}"
ACTIVE_REVISION="${SERVICE}-${ACTIVE_SUFFIX}"
[[ ${#STAGING_REVISION} -le 63 && ${#ACTIVE_REVISION} -le 63 ]] || \
  die "derived Cloud Run revision is too long"
ACTIVATION_URI="gs://${AUTHORITY_BUCKET}/paid-v3/${SERVICE}/${ACTIVE_REVISION}/activation.json"
DIGEST=${IMAGE##*@}

TMP_ROOT="$SOURCE_ROOT/.build-contexts"
mkdir -p "$TMP_ROOT"
TMP=$(mktemp -d "$TMP_ROOT/paid-v3-deploy.XXXXXX")
ROLLBACK_ARMED=0

cleanup() { rm -rf -- "$TMP"; }

# A provider-exported service preserves the former template, traffic, and tags.
# A hand-reconstructed --to-revisions string would not preserve those facts.
rollback_traffic() {
  [[ "$ROLLBACK_ARMED" == 1 ]] || return 0
  local rollback_status=0
  set +e
  gcloud run services replace "$TMP/previous-service.yaml" \
    --project="$PROJECT" --region="$REGION" --platform=managed --quiet \
    >/dev/null
  rollback_status=$?
  if [[ "$rollback_status" -eq 0 ]]; then
    gcloud run services describe "$SERVICE" --project="$PROJECT" \
      --region="$REGION" --platform=managed --format=json \
      >"$TMP/rollback-service.json"
    rollback_status=$?
  fi
  if [[ "$rollback_status" -eq 0 ]]; then
    jq -S '.status.traffic // []' "$TMP/previous-service.json" \
      >"$TMP/previous-traffic.json"
    jq -S '.status.traffic // []' "$TMP/rollback-service.json" \
      >"$TMP/rollback-traffic.json"
    cmp -s "$TMP/previous-traffic.json" "$TMP/rollback-traffic.json"
    rollback_status=$?
  fi
  set -e
  ROLLBACK_ARMED=0
  if [[ "$rollback_status" -ne 0 ]]; then
    printf '%s\n' \
      "ERROR: provider traffic rollback could not be authenticated" >&2
    return 1
  fi
  printf '%s\n' "paid-v3 provider traffic restored after failed cutover" >&2
}

on_error() {
  local status=$?
  trap - ERR INT TERM
  rollback_traffic || true
  cleanup
  exit "$status"
}

on_signal() {
  local status=$1
  trap - ERR INT TERM
  rollback_traffic || true
  cleanup
  exit "$status"
}

trap cleanup EXIT
trap on_error ERR
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

# Snapshot the complete former assignment before either no-traffic revision is
# created. It is the rollback authority once the traffic mutation is armed.
gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json \
  >"$TMP/previous-service.json"
gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=export \
  >"$TMP/previous-service.yaml"

gcloud builds describe "$BUILD_ID" --project="$PROJECT" --format=json \
  >"$TMP/build.json"
jq -e --arg build "$BUILD_ID" --arg code "$CODE_SHA" \
  --arg digest "$DIGEST" --arg project "$PROJECT" '
    .id == $build and .projectId == $project and .status == "SUCCESS" and
    .substitutions._CODE_SHA == $code and
    (.results.images | length) == 1 and
    .results.images[0].digest == $digest
  ' "$TMP/build.json" >/dev/null || \
  die "Cloud Build provider record does not authenticate this release"
PYTHONPATH="$SOURCE_ROOT/src" python -m \
  nfl_dfs.optimizer.paid_classic_deployment_v3 \
  --verify-build-only --build-json "$TMP/build.json" \
  --build-contract "$SOURCE_ROOT/cloudbuild.paid-boundary-v3.yaml" \
  --build-id "$BUILD_ID" --source-commit "$CODE_SHA" --image "$IMAGE" \
  >"$TMP/build-evidence.json"

# Stage 1 authenticates a Ready, no-traffic provider revision and the future
# activation URI. It intentionally lacks exact object coordinates, so every
# money path remains disabled in this revision.
gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" --platform=managed --quiet \
  --image="$IMAGE" --revision-suffix="$STAGING_SUFFIX" --no-traffic \
  --remove-env-vars="PAID_V3_ACTIVATION_GENERATION,PAID_V3_ACTIVATION_SHA256,PAID_V3_ACTIVATION_BYTES,PAID_V3_ACTIVATION_AUTHORITY_JSON" \
  --update-env-vars="IMAGE_SOURCE_COMMIT_SHA=$CODE_SHA,IMAGE_DIGEST=$DIGEST,IMAGE_URI=$IMAGE,PAID_V3_CLOUD_BUILD_ID=$BUILD_ID,PAID_V3_SERVICE=$SERVICE,PAID_V3_PROJECT=$PROJECT,PAID_V3_REGION=$REGION,PAID_V3_ACTIVATION_URI=$ACTIVATION_URI"
gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json >"$TMP/service-stage.json"
gcloud run revisions describe "$STAGING_REVISION" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json \
  >"$TMP/revision-stage.json"
PYTHONPATH="$SOURCE_ROOT/src" python -m \
  nfl_dfs.optimizer.paid_classic_deployment_v3 \
  --build-json "$TMP/build.json" --service-json "$TMP/service-stage.json" \
  --revision-json "$TMP/revision-stage.json" \
  --build-contract "$SOURCE_ROOT/cloudbuild.paid-boundary-v3.yaml" \
  --build-id "$BUILD_ID" --source-commit "$CODE_SHA" --image "$IMAGE" \
  --service "$SERVICE" --revision "$STAGING_REVISION" \
  --activation-uri "$ACTIVATION_URI" --pre-activation \
  --output "$TMP/staging-pre-activation.json"
gcloud storage cp --no-clobber "$TMP/staging-pre-activation.json" \
  "$ACTIVATION_URI.staging-pre-activation.json" >/dev/null

# This authority names a distinct predeclared runtime revision. It is created
# before that revision, so its exact immutable coordinates can be injected
# without asking a running revision to authenticate a future version of itself.
PYTHONPATH="$SOURCE_ROOT/src" python - \
  "$TMP/staging-pre-activation.json" "$TMP/activation.json" \
  "$PROJECT" "$REGION" "$BUILD_ID" "$CODE_SHA" "$IMAGE" "$SERVICE" \
  "$ACTIVE_REVISION" "$ACTIVATION_URI" <<'PY'
import json
from pathlib import Path
import sys

from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
    create_paid_classic_activation_authority_v3,
)

staging = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
authority = create_paid_classic_activation_authority_v3(
    staging,
    expected_project=sys.argv[3],
    expected_region=sys.argv[4],
    expected_build_id=sys.argv[5],
    expected_source_commit=sys.argv[6],
    expected_image=sys.argv[7],
    expected_service=sys.argv[8],
    authorized_runtime_revision=sys.argv[9],
    activation_uri=sys.argv[10],
)
with Path(sys.argv[2]).open("x", encoding="utf-8") as stream:
    stream.write(json.dumps(authority, sort_keys=True, separators=(",", ":")))
PY
ACTIVATION_SHA256=$(sha256sum "$TMP/activation.json" | awk '{print $1}')
ACTIVATION_BYTES=$(wc -c <"$TMP/activation.json" | tr -d '[:space:]')
gcloud storage cp --no-clobber "$TMP/activation.json" "$ACTIVATION_URI" \
  >/dev/null
gcloud storage objects describe "$ACTIVATION_URI" --format=json \
  >"$TMP/activation-object.json"
ACTIVATION_GENERATION=$(jq -er '.generation | tostring' \
  "$TMP/activation-object.json")
REMOTE_BYTES=$(jq -er '.size | tonumber' "$TMP/activation-object.json")
[[ "$ACTIVATION_GENERATION" =~ ^[0-9]+$ && "$ACTIVATION_GENERATION" != 0 ]] || \
  die "activation provider generation is invalid"
[[ "$REMOTE_BYTES" == "$ACTIVATION_BYTES" ]] || \
  die "activation provider byte length differs"

# Reopen the exact remote generation before the authorized revision is made.
PAID_V3_ACTIVATION_URI="$ACTIVATION_URI" \
PAID_V3_ACTIVATION_GENERATION="$ACTIVATION_GENERATION" \
PAID_V3_ACTIVATION_SHA256="$ACTIVATION_SHA256" \
PAID_V3_ACTIVATION_BYTES="$ACTIVATION_BYTES" \
PAID_V3_PROJECT="$PROJECT" PAID_V3_REGION="$REGION" \
PAID_V3_CLOUD_BUILD_ID="$BUILD_ID" \
IMAGE_SOURCE_COMMIT_SHA="$CODE_SHA" IMAGE_URI="$IMAGE" \
PAID_V3_SERVICE="$SERVICE" K_REVISION="$ACTIVE_REVISION" \
PYTHONPATH="$SOURCE_ROOT/src" python - <<'PY' >"$TMP/activation-reopen.json"
import json
import os

from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
    reopen_paid_classic_activation_authority_v3,
)

print(json.dumps(reopen_paid_classic_activation_authority_v3(os.environ), sort_keys=True))
PY

# Stage 2 receives the exact authority identity but still receives no traffic.
gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" --platform=managed --quiet \
  --image="$IMAGE" --revision-suffix="$ACTIVE_SUFFIX" --no-traffic \
  --remove-env-vars="PAID_V3_ACTIVATION_AUTHORITY_JSON" \
  --update-env-vars="IMAGE_SOURCE_COMMIT_SHA=$CODE_SHA,IMAGE_DIGEST=$DIGEST,IMAGE_URI=$IMAGE,PAID_V3_CLOUD_BUILD_ID=$BUILD_ID,PAID_V3_SERVICE=$SERVICE,PAID_V3_PROJECT=$PROJECT,PAID_V3_REGION=$REGION,PAID_V3_ACTIVATION_URI=$ACTIVATION_URI,PAID_V3_ACTIVATION_GENERATION=$ACTIVATION_GENERATION,PAID_V3_ACTIVATION_SHA256=$ACTIVATION_SHA256,PAID_V3_ACTIVATION_BYTES=$ACTIVATION_BYTES"
gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json \
  >"$TMP/service-active-pre.json"
gcloud run revisions describe "$ACTIVE_REVISION" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json \
  >"$TMP/revision-active-pre.json"
PYTHONPATH="$SOURCE_ROOT/src" python -m \
  nfl_dfs.optimizer.paid_classic_deployment_v3 \
  --build-json "$TMP/build.json" --service-json "$TMP/service-active-pre.json" \
  --revision-json "$TMP/revision-active-pre.json" \
  --build-contract "$SOURCE_ROOT/cloudbuild.paid-boundary-v3.yaml" \
  --build-id "$BUILD_ID" --source-commit "$CODE_SHA" --image "$IMAGE" \
  --service "$SERVICE" --revision "$ACTIVE_REVISION" \
  --activation-uri "$ACTIVATION_URI" \
  --activation-generation "$ACTIVATION_GENERATION" \
  --activation-sha256 "$ACTIVATION_SHA256" \
  --activation-bytes "$ACTIVATION_BYTES" --pre-activation \
  --output "$TMP/active-pre-activation.json"
gcloud storage cp --no-clobber "$TMP/active-pre-activation.json" \
  "$ACTIVATION_URI.active-pre-activation.json" >/dev/null

# Arm rollback before the provider mutation. A nonzero command can be an
# ambiguous success, so observed traffic is reconciled before deciding whether
# to continue or restore the complete provider-exported former service.
ROLLBACK_ARMED=1
if ! gcloud run services update-traffic "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --quiet \
  --to-revisions="$ACTIVE_REVISION=100"; then
  gcloud run services describe "$SERVICE" --project="$PROJECT" \
    --region="$REGION" --platform=managed --format=json \
    >"$TMP/service-ambiguous.json" || true
  if PYTHONPATH="$SOURCE_ROOT/src" python - \
    "$TMP/service-ambiguous.json" "$SERVICE" "$ACTIVE_REVISION" <<'PY'
import json
from pathlib import Path
import sys

from nfl_dfs.optimizer.paid_classic_deployment_v3 import (
    validate_paid_classic_active_traffic_state_v3,
)

validate_paid_classic_active_traffic_state_v3(
    json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")),
    expected_service=sys.argv[2],
    expected_revision=sys.argv[3],
)
PY
  then
    printf '%s\n' \
      "WARNING: traffic command returned nonzero but provider state is exact" >&2
  else
    rollback_traffic || die "ambiguous cutover and rollback failed"
    die "traffic mutation returned nonzero and did not reach exact target"
  fi
fi

gcloud run services describe "$SERVICE" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json >"$TMP/service-final.json"
gcloud run revisions describe "$ACTIVE_REVISION" --project="$PROJECT" \
  --region="$REGION" --platform=managed --format=json \
  >"$TMP/revision-final.json"
PYTHONPATH="$SOURCE_ROOT/src" python -m \
  nfl_dfs.optimizer.paid_classic_deployment_v3 \
  --build-json "$TMP/build.json" --service-json "$TMP/service-final.json" \
  --revision-json "$TMP/revision-final.json" \
  --build-contract "$SOURCE_ROOT/cloudbuild.paid-boundary-v3.yaml" \
  --build-id "$BUILD_ID" --source-commit "$CODE_SHA" --image "$IMAGE" \
  --service "$SERVICE" --revision "$ACTIVE_REVISION" \
  --activation-uri "$ACTIVATION_URI" \
  --activation-generation "$ACTIVATION_GENERATION" \
  --activation-sha256 "$ACTIVATION_SHA256" \
  --activation-bytes "$ACTIVATION_BYTES" --output "$RECEIPT"
gcloud storage cp --no-clobber "$RECEIPT" \
  "$ACTIVATION_URI.traffic.json" >/dev/null
ROLLBACK_ARMED=0
printf 'PAID_V3_DEPLOYMENT_ATTESTATION=%s\n' "$RECEIPT"
printf 'PAID_V3_ACTIVATION_URI=%s\n' "$ACTIVATION_URI"
printf 'PAID_V3_ACTIVATION_GENERATION=%s\n' "$ACTIVATION_GENERATION"
printf 'PAID_V3_ACTIVATION_SHA256=%s\n' "$ACTIVATION_SHA256"
printf 'PAID_V3_ACTIVATION_BYTES=%s\n' "$ACTIVATION_BYTES"
