#!/usr/bin/env bash
# Move the four lane conditions v8 -> v9 (finalizer certificate respin;
# v8a burned by its consumed failed launch, v8b burned by the image pin;
# perfect 7000/7000 generation evidence retained under
# 20260823-foundry-production-v8a/terminal-failure-evidence/).
set -euo pipefail
PROJECT="nfl-predictions-503414"
BUCKET="gs://nfl-predictions-503414-corpus-parametric"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" --format=json >"$WORK/current.json"
sed -e 's/production-batch-v8a/production-batch-v9a/g' \
    -e 's/production-foundation-v8a/production-foundation-v9a/g' \
    -e 's/production-batch-v8b/production-batch-v9b/g' \
    -e 's/production-foundation-v8b/production-foundation-v9b/g' \
    "$WORK/current.json" >"$WORK/proposed.json"
echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true
grep -q "v8a\|v8b" "$WORK/proposed.json" && { echo "refused: v8 remains" >&2; exit 3; }
grep -q "production-batch-v9a" "$WORK/proposed.json" || { echo "refused: v9a absent" >&2; exit 3; }
grep -q "production-batch-v9b" "$WORK/proposed.json" || { echo "refused: v9b absent" >&2; exit 3; }
if [[ "${1:-}" == "--execute" ]]; then
  jq '.version = 3' "$WORK/proposed.json" >"$WORK/final.json"
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/final.json" --project "$PROJECT" >/dev/null
  echo "APPLIED"
else
  echo "(dry run only)"
fi
