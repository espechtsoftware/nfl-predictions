#!/usr/bin/env bash
# Build the bounded live-job image without uploading frozen research evidence.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
project="${GCP_PROJECT:-nfl-predictions-503414}"
region="${REGION:-us-central1}"
code_sha="$(git -C "$root" rev-parse HEAD)"
image="${WEEK1_LIVE_IMAGE:-${region}-docker.pkg.dev/${project}/nfl-dfs/nfl-dfs:week1-live-${code_sha:0:12}}"

if ! git -C "$root" diff --quiet --ignore-submodules -- \
  || ! git -C "$root" diff --cached --quiet --ignore-submodules --; then
  echo "refusing to build a dirty tracked tree" >&2
  exit 2
fi

context_parent="$root/.build-contexts"
mkdir -p "$context_parent"
context="$(mktemp -d -p "$context_parent" week1-live-build-XXXXXXXX)"
trap 'rm -rf -- "$context"' EXIT

for path in \
  pyproject.toml README.md CLAUDE.md \
  Dockerfile.week1-live cloudbuild.week1-live.yaml \
  src sql scripts tests; do
  cp -a "$root/$path" "$context/$path"
done

echo "source_commit=$code_sha"
echo "image=$image"
du -sh "$context"
gcloud builds submit --async \
  --project "$project" \
  --config "$context/cloudbuild.week1-live.yaml" \
  --substitutions "_CODE_SHA=${code_sha},_IMAGE=${image}" \
  "$context"
