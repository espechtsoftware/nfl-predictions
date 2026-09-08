#!/usr/bin/env bash
# Build paid-v3 only from an exact pushed commit and report its immutable digest.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

[[ $# -eq 2 && "$1" == "--execute" ]] || \
  die "usage: $0 --execute FULL_PUSHED_CODE_SHA"
CODE_SHA=$2
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || \
  die "FULL_PUSHED_CODE_SHA must be a full 40-character commit"
command -v git >/dev/null || die "git is required"
command -v gcloud >/dev/null || die "gcloud is required"

SOURCE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || \
  die "run from the production repository"
ORIGIN_MAIN_SHA=$(git -C "$SOURCE_ROOT" rev-parse --verify \
  'refs/remotes/origin/main^{commit}') || die "local origin/main is unavailable"
[[ "$ORIGIN_MAIN_SHA" == "$CODE_SHA" ]] || \
  die "FULL_PUSHED_CODE_SHA must equal local origin/main"
git -C "$SOURCE_ROOT" cat-file -e \
  "${CODE_SHA}:cloudbuild.paid-boundary-v3.yaml" || \
  die "paid-v3 build contract is absent from the exact commit"

PROJECT=nfl-predictions-503414
REGION=us-central1
REPOSITORY=nfl-dfs
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT}/${REPOSITORY}/nfl-dfs:paid-v3-${CODE_SHA}"

BUILD_ROOT="$SOURCE_ROOT/.build-contexts"
mkdir -p "$BUILD_ROOT"
BUILD_TEMP=$(mktemp -d "$BUILD_ROOT/paid-v3-build.XXXXXX")
cleanup() { rm -rf -- "$BUILD_TEMP"; }
trap cleanup EXIT
git -C "$SOURCE_ROOT" archive "$CODE_SHA" \
  cloudbuild.paid-boundary-v3.yaml | tar -x -C "$BUILD_TEMP"
[[ ! -e "$BUILD_TEMP/.git" ]] || die "build context unexpectedly contains .git"
[[ "$(git -C "$SOURCE_ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "origin/main changed while preparing the build"

SUBMIT_OUTPUT=$(gcloud builds submit "$BUILD_TEMP" \
  --config="$BUILD_TEMP/cloudbuild.paid-boundary-v3.yaml" \
  --substitutions="_CODE_SHA=${CODE_SHA},_BUILD_IMAGE=${IMAGE_TAG}" \
  --project="$PROJECT" --format='value(id)' --quiet)
mapfile -t BUILD_IDS < <(
  printf '%s\n' "$SUBMIT_OUTPUT" |
    grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}' |
    sort -u
)
[[ "${#BUILD_IDS[@]}" -eq 1 ]] || \
  die "Cloud Build did not return exactly one durable build ID"
BUILD_ID=${BUILD_IDS[0]}
DIGEST=$(gcloud builds describe "$BUILD_ID" --project="$PROJECT" \
  --format='value(results.images[0].digest)')
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || \
  die "Cloud Build did not return an immutable image digest"
IMMUTABLE_IMAGE="${IMAGE_TAG%:*}@${DIGEST}"

printf 'BUILD_ID=%s\nSOURCE_COMMIT_SHA=%s\nIMAGE=%s\n%s=%s\n' \
  "$BUILD_ID" "$CODE_SHA" "$IMMUTABLE_IMAGE" \
  'IMAGE_DIGEST' "$DIGEST"
