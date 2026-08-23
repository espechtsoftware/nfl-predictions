#!/usr/bin/env bash
# Move the four lane conditions v9 -> v10 (policy-derived fallback respin;
# v9 lanes burned unused by the image pin — no launch consumed).
set -euo pipefail
PROJECT="nfl-predictions-503414"
BUCKET="gs://nfl-predictions-503414-corpus-parametric"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" --format=json >"$WORK/current.json"
sed -e 's/production-batch-v9a/production-batch-v10a/g' \
    -e 's/production-foundation-v9a/production-foundation-v10a/g' \
    -e 's/production-batch-v9b/production-batch-v10b/g' \
    -e 's/production-foundation-v9b/production-foundation-v10b/g' \
    "$WORK/current.json" >"$WORK/proposed.json"
echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true
grep -q "v9a\|v9b" "$WORK/proposed.json" && { echo "refused: v9 remains" >&2; exit 3; }
grep -q "production-batch-v10a" "$WORK/proposed.json" || { echo "refused: v10a absent" >&2; exit 3; }
grep -q "production-batch-v10b" "$WORK/proposed.json" || { echo "refused: v10b absent" >&2; exit 3; }
if [[ "${1:-}" == "--execute" ]]; then
  jq '.version = 3' "$WORK/proposed.json" >"$WORK/final.json"
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/final.json" --project "$PROJECT" >/dev/null
  echo "APPLIED"
else
  echo "(dry run only)"
fi
