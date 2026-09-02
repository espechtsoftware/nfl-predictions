#!/usr/bin/env bash
# Build the scoped CFB collection image from one exact pushed commit.  No
# dirty, ignored, or unrelated workstation byte is uploaded to Cloud Build.
set -euo pipefail

die() {
  printf '%s\n' "ERROR: $*" >&2
  exit 2
}

[[ $# -eq 2 && "$1" == "--execute" ]] || \
  die "usage: $0 --execute FULL_PUSHED_CODE_SHA"
CODE_SHA=$2
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || \
  die "FULL_PUSHED_CODE_SHA must be a full 40-character commit"

for command_name in git gcloud tar; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done

SOURCE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || \
  die "run from the nfl-predictions repository"
git -C "$SOURCE_ROOT" cat-file -e "${CODE_SHA}^{commit}" || \
  die "requested commit is unavailable"
git -C "$SOURCE_ROOT" fetch --quiet origin main || \
  die "could not refresh origin/main"
ORIGIN_MAIN_SHA=$(git -C "$SOURCE_ROOT" rev-parse --verify \
  'refs/remotes/origin/main^{commit}') || die "local origin/main is unavailable"
[[ "$ORIGIN_MAIN_SHA" == "$CODE_SHA" ]] || \
  die "FULL_PUSHED_CODE_SHA must equal local origin/main"

PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
REGION=${GCP_REGION:-us-central1}
ARTIFACT_REPOSITORY=${CFB_ARTIFACT_REPOSITORY:-nfl-dfs}
[[ "$PROJECT" == "nfl-predictions-503414" ]] || \
  die "the governed CFB collection project differs"
[[ "$REGION" == "us-central1" ]] || \
  die "the governed CFB collection region differs"
[[ "$ARTIFACT_REPOSITORY" == "nfl-dfs" ]] || \
  die "the governed CFB artifact repository differs"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${ARTIFACT_REPOSITORY}/nfl-dfs:cfb-collection-${CODE_SHA}"

ARCHIVE_PATHS=(
  Dockerfile.cfb-collection-repair
  cloudbuild.cfb-collection-repair.yaml
  deploy/deploy_jobs.sh
  pyproject.toml
  README.md
  scripts/build_cfb_collection_repair_image.sh
  sql/raw/005_dk_contests.sql
  sql/raw/006_cfb_dk_salaries.sql
  src
  tests/test_bq_load.py
  tests/test_cfb_cloudbuild_contract.py
  tests/test_cfb_deployment_contract.py
  tests/test_cfb_job.py
  tests/test_dk_client.py
)
for relative_path in "${ARCHIVE_PATHS[@]}"; do
  git -C "$SOURCE_ROOT" cat-file -e "${CODE_SHA}:${relative_path}" || \
    die "required committed build input is absent: ${relative_path}"
done

# Whitespace and shell failures are local pre-submit gates.  Cloud Build
# repeats shell syntax checks against the exact extracted context.
git -C "$SOURCE_ROOT" diff --check "${CODE_SHA}^" "$CODE_SHA"
git -C "$SOURCE_ROOT" show "${CODE_SHA}:deploy/deploy_jobs.sh" | bash -n
git -C "$SOURCE_ROOT" show \
  "${CODE_SHA}:scripts/build_cfb_collection_repair_image.sh" | bash -n

BUILD_CONTEXT_ROOT="$SOURCE_ROOT/.build-contexts"
mkdir -p "$BUILD_CONTEXT_ROOT"
BUILD_TEMP=$(mktemp -d "$BUILD_CONTEXT_ROOT/cfb-collection-build.XXXXXX")
CONTEXT="$BUILD_TEMP/context"
ARCHIVE="$BUILD_TEMP/source.tar"
cleanup() {
  rm -rf -- "$BUILD_TEMP"
}
trap cleanup EXIT
mkdir -p "$CONTEXT"

git -C "$SOURCE_ROOT" archive --format=tar --output="$ARCHIVE" \
  "$CODE_SHA" -- "${ARCHIVE_PATHS[@]}"
tar -xf "$ARCHIVE" -C "$CONTEXT"

[[ ! -e "$CONTEXT/.git" ]] || die "build context unexpectedly contains .git"
[[ ! -e "$CONTEXT/HANDOFF.md" ]] || \
  die "build context unexpectedly contains HANDOFF.md"
[[ ! -e "$CONTEXT/reports" ]] || \
  die "build context unexpectedly contains reports"
[[ "$(find "$CONTEXT/tests" -type f -printf 'tests/%P\n' | sort)" == \
  "$(printf '%s\n' \
    tests/test_bq_load.py \
    tests/test_cfb_cloudbuild_contract.py \
    tests/test_cfb_deployment_contract.py \
    tests/test_cfb_job.py \
    tests/test_dk_client.py | sort)" ]] || \
  die "build context test set differs from the exact CFB allowlist"

# Refresh and recheck the remote-tracking authority immediately before upload.
# The source context itself remains the immutable local commit archive.
git -C "$SOURCE_ROOT" fetch --quiet origin main || \
  die "could not refresh origin/main before upload"
[[ "$(git -C "$SOURCE_ROOT" rev-parse --verify \
  'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "origin/main changed while preparing the committed build context"

BUILD_SUBMIT_OUTPUT=$(gcloud builds submit "$CONTEXT" \
  --config="$CONTEXT/cloudbuild.cfb-collection-repair.yaml" \
  --substitutions="_CODE_SHA=${CODE_SHA},_CFB_IMAGE=${IMAGE}" \
  --project="$PROJECT" --format='value(id)' --quiet)
mapfile -t BUILD_IDS < <(
  printf '%s\n' "$BUILD_SUBMIT_OUTPUT" |
    grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' |
    sort -u
)
[[ "${#BUILD_IDS[@]}" -eq 1 ]] || \
  die "Cloud Build did not return exactly one durable build ID"
BUILD_ID=${BUILD_IDS[0]}
DIGEST=$(gcloud builds describe "$BUILD_ID" --project="$PROJECT" \
  --format='value(results.images[0].digest)')
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || \
  die "Cloud Build did not return the immutable image digest"
IMMUTABLE_IMAGE="${IMAGE%:*}@${DIGEST}"

printf 'BUILD_ID=%s\nCODE_SHA=%s\nBUILD_IMAGE_TAG=%s\nIMAGE=%s\n' \
  "$BUILD_ID" "$CODE_SHA" "$IMAGE" "$IMMUTABLE_IMAGE"
