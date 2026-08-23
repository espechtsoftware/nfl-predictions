#!/usr/bin/env bash
# Atomically move the two narrow corpus-parametric runtime IAM conditions
# from the burned v6 prefixes to BOTH v7 lane prefixes (a and b).
#
# v6's single 54-task batch died with its task-0 producer (one non-optimal
# cell fails a batch terminally and finish-batch demands every task), so
# v7 runs two concurrent half-batches on two reused jobs under the same
# runtime service account. The create condition covers both lane batch
# prefixes; the read condition covers both lane foundations and batches.
#
# Dry-run by default; pass --execute to apply.

set -euo pipefail

BUCKET="gs://nfl-predictions-503414-corpus-parametric"
PROJECT="nfl-predictions-503414"
SA="serviceAccount:corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com"
OBJ="projects/_/buckets/nfl-predictions-503414-corpus-parametric/objects"
OLD_BATCH="research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v6/"
OLD_FOUNDATION="research/corpus-parametric-research/foundations/20260822-corpus-parametric-production-foundation-v6/"
BATCH_A="research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v7a/"
FOUNDATION_A="research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v7a/"
BATCH_B="research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v7b/"
FOUNDATION_B="research/corpus-parametric-research/foundations/20260823-corpus-parametric-production-foundation-v7b/"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" \
  --format=json >"$WORK/current.json"

jq -e --arg sa "$SA" '
  [.bindings[] | select(.members == [$sa])] | length == 2
' "$WORK/current.json" >/dev/null || {
  echo "refused: expected exactly two narrow runtime-SA bindings" >&2; exit 2; }

jq --arg sa "$SA" --arg obj "$OBJ" --arg q "'" \
   --arg ba "$BATCH_A" --arg fa "$FOUNDATION_A" \
   --arg bb "$BATCH_B" --arg fb "$FOUNDATION_B" '
  .bindings |= map(
    if .members == [$sa] and (.condition.title == "corpus-parametric-create-v2")
    then .condition.expression =
      ("resource.name.startsWith(\($q)\($obj)/\($ba)\($q))"
       + " || resource.name.startsWith(\($q)\($obj)/\($bb)\($q))")
    elif .members == [$sa] and (.condition.title == "corpus-parametric-read-v2")
    then .condition.expression =
      ("resource.name.startsWith(\($q)\($obj)/\($fa)\($q))"
       + " || resource.name.startsWith(\($q)\($obj)/\($ba)\($q))"
       + " || resource.name.startsWith(\($q)\($obj)/\($fb)\($q))"
       + " || resource.name.startsWith(\($q)\($obj)/\($bb)\($q))")
    else . end)
' "$WORK/current.json" >"$WORK/proposed.json"

echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true

jq -e --arg ob "$OLD_BATCH" --arg of "$OLD_FOUNDATION" '
  [.bindings[].condition.expression // ""] | join(" ") |
  (contains($ob) or contains($of)) | not
' "$WORK/proposed.json" >/dev/null || {
  echo "refused: v6 prefixes still present after transform" >&2; exit 3; }

jq -e --arg ba "$BATCH_A" --arg fa "$FOUNDATION_A" \
      --arg bb "$BATCH_B" --arg fb "$FOUNDATION_B" '
  [.bindings[].condition.expression // ""] | join(" ") |
  (contains($ba) and contains($fa) and contains($bb) and contains($fb))
' "$WORK/proposed.json" >/dev/null || {
  echo "refused: v7 lane prefixes absent after transform" >&2; exit 3; }

if [[ "${1:-}" == "--execute" ]]; then
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/proposed.json" \
    --project "$PROJECT" >/dev/null
  echo "applied; capture fresh policy per-lane for the configure steps"
else
  echo "(dry run only; rerun with --execute once the v6 chain is terminally closed)"
fi
