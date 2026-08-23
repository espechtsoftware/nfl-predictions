#!/usr/bin/env bash
# Move the four lane conditions v10 -> v11 (lane-safe selection respin;
# v10a burned by its consumed launches — producer succeeded end to end,
# verifier failed on the ledger certificate law; v10b burned by its
# consumed producer launch — positional source-row selection).
set -euo pipefail
PROJECT="nfl-predictions-503414"
BUCKET="gs://nfl-predictions-503414-corpus-parametric"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" --format=json >"$WORK/current.json"
sed -e 's/production-batch-v10a/production-batch-v11a/g' \
    -e 's/production-foundation-v10a/production-foundation-v11a/g' \
    -e 's/production-batch-v10b/production-batch-v11b/g' \
    -e 's/production-foundation-v10b/production-foundation-v11b/g' \
    "$WORK/current.json" >"$WORK/proposed.json"
echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true
grep -q "v10a\|v10b" "$WORK/proposed.json" && { echo "refused: v10 remains" >&2; exit 3; }
grep -q "production-batch-v11a" "$WORK/proposed.json" || { echo "refused: v11a absent" >&2; exit 3; }
grep -q "production-batch-v11b" "$WORK/proposed.json" || { echo "refused: v11b absent" >&2; exit 3; }
if [[ "${1:-}" == "--execute" ]]; then
  jq '.version = 3' "$WORK/proposed.json" >"$WORK/final.json"
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/final.json" --project "$PROJECT" >/dev/null
  echo "APPLIED"
else
  echo "(dry run only)"
fi
