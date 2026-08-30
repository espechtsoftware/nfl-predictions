#!/usr/bin/env bash
# Submit the dedicated generation-shadow image from an exact committed tree.
# The repository working tree is never used as Cloud Build source.
set -euo pipefail

die() { printf '%s\n' "ERROR: $*" >&2; exit 2; }

[[ $# -eq 2 && "$1" == "--execute" ]] || \
  die "usage: $0 --execute FULL_PUSHED_CODE_SHA"
CODE_SHA=$2
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || \
  die "FULL_PUSHED_CODE_SHA must be a full 40-character commit"

command -v git >/dev/null || die "git is required"
command -v gcloud >/dev/null || die "gcloud is required"
command -v tar >/dev/null || die "tar is required"

SOURCE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || \
  die "run from the generation-shadow repository"
git -C "$SOURCE_ROOT" cat-file -e "${CODE_SHA}^{commit}" || \
  die "requested commit is unavailable"
ORIGIN_MAIN_SHA=$(git -C "$SOURCE_ROOT" rev-parse --verify \
  'refs/remotes/origin/main^{commit}') || die "local origin/main is unavailable"
[[ "$ORIGIN_MAIN_SHA" == "$CODE_SHA" ]] || \
  die "FULL_PUSHED_CODE_SHA must equal local origin/main"

PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
REGION=${GCP_REGION:-us-central1}
ARTIFACT_REPOSITORY=${GENERATION_SHADOW_ARTIFACT_REPOSITORY:-nfl-dfs}
[[ "$PROJECT" =~ ^[a-z][a-z0-9-]{4,61}[a-z0-9]$ ]] || \
  die "GCP_PROJECT is invalid"
[[ "$REGION" =~ ^[a-z0-9-]+$ ]] || die "GCP_REGION is invalid"
[[ "$ARTIFACT_REPOSITORY" =~ ^[a-z][a-z0-9._-]*$ ]] || \
  die "GENERATION_SHADOW_ARTIFACT_REPOSITORY is invalid"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${ARTIFACT_REPOSITORY}/nfl-dfs:generation-shadow-${CODE_SHA}"

# Keep the upload small and mechanically independent of every uncommitted or
# ignored workstation byte.  The complete package and focused build tests are
# archived from CODE_SHA; the 439-MiB reports tree and unrelated scripts/SQL
# are never materialized in the Cloud Build context.
TEST_SUPPORT_SCRIPTS=(
  scripts/aggregate_coherent_market_state_scorefree.py
  scripts/coherent_market_state_sources.py
  scripts/run_cbwu_seed_order_audit.py
  scripts/run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py
  scripts/run_legal_soft_law.py
  scripts/verify_deployment.py
)
EXPECTED_SCRIPT_PATHS=(
  scripts/build_generation_shadow_suite_image.sh
  scripts/cloud_generation_shadow_suite.sh
  "${TEST_SUPPORT_SCRIPTS[@]}"
)
ARCHIVE_PATHS=(
  Dockerfile.generation-shadow-suite
  Dockerfile.generation-shadow-suite.dockerignore
  cloudbuild.yaml
  cloudbuild.generation-shadow-suite.yaml
  pyproject.toml
  README.md
  src
  tests
  "${EXPECTED_SCRIPT_PATHS[@]}"
)
for relative_path in "${ARCHIVE_PATHS[@]}"; do
  git -C "$SOURCE_ROOT" cat-file -e "${CODE_SHA}:${relative_path}" || \
    die "required committed build input is absent: ${relative_path}"
done

# Fail locally when the committed Cloud Build contract names a Python source
# or test that is not present in the exact commit.  Checking only the parent
# src/tests trees is insufficient: an untracked new module can satisfy local
# tests while disappearing from git archive and failing remotely.
mapfile -t BUILD_REFERENCED_PATHS < <(
  git -C "$SOURCE_ROOT" show \
    "${CODE_SHA}:cloudbuild.generation-shadow-suite.yaml" |
    grep -Eo '(src|tests)/[A-Za-z0-9_./-]+\.py' |
    sort -u
)
[[ "${#BUILD_REFERENCED_PATHS[@]}" -gt 0 ]] || \
  die "committed Cloud Build contract names no source or test paths"
for relative_path in "${BUILD_REFERENCED_PATHS[@]}"; do
  git -C "$SOURCE_ROOT" cat-file -e "${CODE_SHA}:${relative_path}" || \
    die "Cloud Build references an absent committed file: ${relative_path}"
done

BUILD_TEMP=$(mktemp -d "${TMPDIR:-/tmp}/generation-shadow-build.XXXXXX")
CONTEXT="$BUILD_TEMP/context"
ARCHIVE="$BUILD_TEMP/source.tar"
cleanup() { rm -rf -- "$BUILD_TEMP"; }
trap cleanup EXIT
mkdir -p "$CONTEXT"

git -C "$SOURCE_ROOT" archive --format=tar --output="$ARCHIVE" \
  "$CODE_SHA" -- "${ARCHIVE_PATHS[@]}"
tar -xf "$ARCHIVE" -C "$CONTEXT"

[[ ! -e "$CONTEXT/.git" ]] || die "build context unexpectedly contains .git"
[[ ! -e "$CONTEXT/reports" ]] || die "build context unexpectedly contains reports"
[[ ! -e "$CONTEXT/sql" ]] || die "build context unexpectedly contains sql"
[[ ! -e "$CONTEXT/HANDOFF.md" ]] || die "build context unexpectedly contains HANDOFF.md"
[[ ! -e "$CONTEXT/CLAUDE.md" ]] || die "build context unexpectedly contains CLAUDE.md"
[[ -f "$CONTEXT/scripts/build_generation_shadow_suite_image.sh" ]] || \
  die "build helper is absent from committed archive"
[[ -f "$CONTEXT/scripts/cloud_generation_shadow_suite.sh" ]] || \
  die "deployment helper is absent from committed archive"
[[ "$(find "$CONTEXT/scripts" -type f -printf 'scripts/%P\n' | sort)" == \
   "$(printf '%s\n' "${EXPECTED_SCRIPT_PATHS[@]}" | sort)" ]] || \
  die "script set in build context differs from the exact test allowlist"
for relative_path in "${BUILD_REFERENCED_PATHS[@]}"; do
  [[ -f "$CONTEXT/$relative_path" ]] || \
    die "Cloud Build input is absent from extracted archive: ${relative_path}"
done

# The worktree may contain unrelated concurrent work.  It is never uploaded:
# every byte above came from the explicit pushed commit object.
[[ "$(git -C "$SOURCE_ROOT" rev-parse --verify 'refs/remotes/origin/main^{commit}')" == "$CODE_SHA" ]] || \
  die "origin/main changed while preparing the committed build context"

BUILD_ID=$(gcloud builds submit "$CONTEXT" \
  --config="$CONTEXT/cloudbuild.generation-shadow-suite.yaml" \
  --substitutions="_CODE_SHA=${CODE_SHA},_BUILD_IMAGE=${IMAGE}" \
  --project="$PROJECT" --format='value(id)' --quiet)
[[ "$BUILD_ID" =~ ^[0-9a-f]{8}-[0-9a-f-]{27}$ ]] || \
  die "Cloud Build did not return a durable build ID"
DIGEST=$(gcloud builds describe "$BUILD_ID" --project="$PROJECT" \
  --format='value(results.images[0].digest)')
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || \
  die "Cloud Build did not return the immutable image digest"
IMMUTABLE_IMAGE="${IMAGE%:*}@${DIGEST}"

printf 'BUILD_ID=%s\nCODE_SHA=%s\nBUILD_IMAGE_TAG=%s\nIMAGE=%s\n' \
  "$BUILD_ID" "$CODE_SHA" "$IMAGE" "$IMMUTABLE_IMAGE"
