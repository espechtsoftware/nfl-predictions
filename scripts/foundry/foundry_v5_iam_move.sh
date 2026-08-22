#!/usr/bin/env bash
# Atomically move the two narrow corpus-parametric runtime IAM conditions
# from the v4 smoke prefixes to the v5 production prefixes.
#
# PRECONDITION (hard): the ENTIRE v4 chain is closed (producer closed,
# verifier accepted, batch finished). The running v4 producer/verifier write
# under the v4 prefixes; moving earlier breaks them.
#
# Dry-run by default; pass --execute to apply. Re-fetches the live policy at
# run time (fresh etag), edits ONLY the two condition expressions, prints the
# diff, and sets the policy atomically.

set -euo pipefail

BUCKET="gs://nfl-predictions-503414-corpus-parametric"
PROJECT="nfl-predictions-503414"
SA="serviceAccount:corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com"
OBJ="projects/_/buckets/nfl-predictions-503414-corpus-parametric/objects"
OLD_BATCH="research/corpus-parametric-research/batches/20260822-corpus-parametric-task0-smoke-batch-v4/"
OLD_FOUNDATION="research/corpus-parametric-research/foundations/20260822-corpus-parametric-task0-smoke-foundation-v4/"
NEW_BATCH="research/corpus-parametric-research/batches/20260822-corpus-parametric-production-batch-v5/"
NEW_FOUNDATION="research/corpus-parametric-research/foundations/20260822-corpus-parametric-production-foundation-v5/"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

gcloud storage buckets get-iam-policy "$BUCKET" --project "$PROJECT" \
  --format=json >"$WORK/current.json"

jq -e --arg sa "$SA" '
  [.bindings[] | select(.members == [$sa])] | length == 2
' "$WORK/current.json" >/dev/null || {
  echo "refused: expected exactly two narrow runtime-SA bindings" >&2; exit 2; }

jq --arg sa "$SA" --arg obj "$OBJ" --arg q "'" \
   --arg ob "$OLD_BATCH" --arg of "$OLD_FOUNDATION" \
   --arg nb "$NEW_BATCH" --arg nf "$NEW_FOUNDATION" '
  .bindings |= map(
    if .members == [$sa] and (.condition.title == "corpus-parametric-create-v2")
    then .condition.expression =
      "resource.name.startsWith(\($q)\($obj)/\($nb)\($q))"
    elif .members == [$sa] and (.condition.title == "corpus-parametric-read-v2")
    then .condition.expression =
      ("resource.name.startsWith(\($q)\($obj)/\($nf)\($q))"
       + " || resource.name.startsWith(\($q)\($obj)/\($nb)\($q))")
    else . end)
' "$WORK/current.json" >"$WORK/proposed.json"

echo "=== proposed change ==="
diff <(jq -S . "$WORK/current.json") <(jq -S . "$WORK/proposed.json") || true

jq -e --arg ob "$OLD_BATCH" --arg of "$OLD_FOUNDATION" '
  [.bindings[].condition.expression // ""] | join(" ") |
  (contains($ob) or contains($of)) | not
' "$WORK/proposed.json" >/dev/null || {
  echo "refused: v4 prefixes still present after transform" >&2; exit 3; }

if [[ "${1:-}" == "--execute" ]]; then
  gcloud storage buckets set-iam-policy "$BUCKET" "$WORK/proposed.json" \
    --project "$PROJECT" >/dev/null
  echo "applied; capture the fresh policy for the v5 configure step"
else
  echo "(dry run only; rerun with --execute after the v4 chain is fully closed)"
fi
