#!/usr/bin/env bash
# Move the four lane conditions v11 -> v12 (exact-gaps CBC respin; v11a
# burned by task-1's consumed launch — the certificate correctly killed
# a genuinely wrong CBC optimum; v11b burned by the image pin whenever
# its own fan-out ends).
set -euo pipefail
PROJECT="nfl-predictions-503414"
BUCKET="gs://nfl-predictions-503414-corpus-parametric"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" --format=json >"$WORK/current.json"
sed -e 's/production-batch-v11a/production-batch-v12a/g' \
    -e 's/production-foundation-v11a/production-foundation-v12a/g' \
    -e 's/production-batch-v11b/production-batch-v12b/g' \
    -e 's/production-foundation-v11b/production-foundation-v12b/g' \
    "$WORK/current.json" >"$WORK/proposed.json"
echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true
grep -q "v11a\|v11b" "$WORK/proposed.json" && { echo "refused: v11 remains" >&2; exit 3; }
grep -q "production-batch-v12a" "$WORK/proposed.json" || { echo "refused: v12a absent" >&2; exit 3; }
grep -q "production-batch-v12b" "$WORK/proposed.json" || { echo "refused: v12b absent" >&2; exit 3; }
if [[ "${1:-}" == "--execute" ]]; then
  jq '.version = 3' "$WORK/proposed.json" >"$WORK/final.json"
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/final.json" --project "$PROJECT" >/dev/null
  echo "APPLIED"
else
  echo "(dry run only)"
fi
