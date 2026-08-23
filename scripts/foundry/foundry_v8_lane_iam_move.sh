#!/usr/bin/env bash
# Move the four lane-specific corpus-parametric conditions from the v7
# lane prefixes to the v8 lane prefixes (image respin for the transport's
# lane batch-mode law; the v7a/v7b namespaces hold create-once foundation
# objects pinning the superseded image digest and are burned unused —
# no launch was ever consumed under them). SA/role architecture and the
# source/retrieval/raw mirrors are unchanged.
# Dry-run by default; pass --execute to apply.

set -euo pipefail

PROJECT="nfl-predictions-503414"
BUCKET="gs://nfl-predictions-503414-corpus-parametric"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" \
  --format=json >"$WORK/current.json"
sed -e 's/production-batch-v7a/production-batch-v8a/g' \
    -e 's/production-foundation-v7a/production-foundation-v8a/g' \
    -e 's/production-batch-v7b/production-batch-v8b/g' \
    -e 's/production-foundation-v7b/production-foundation-v8b/g' \
    "$WORK/current.json" >"$WORK/proposed.json"

echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true
grep -q "v7a\|v7b" "$WORK/proposed.json" && { echo "refused: v7 remains" >&2; exit 3; }
grep -q "production-batch-v8a" "$WORK/proposed.json" || { echo "refused: v8a absent" >&2; exit 3; }
grep -q "production-batch-v8b" "$WORK/proposed.json" || { echo "refused: v8b absent" >&2; exit 3; }

if [[ "${1:-}" == "--execute" ]]; then
  jq '.version = 3' "$WORK/proposed.json" >"$WORK/final.json"
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/final.json" \
    --project "$PROJECT" >/dev/null
  echo "APPLIED"
else
  echo "(dry run only)"
fi
