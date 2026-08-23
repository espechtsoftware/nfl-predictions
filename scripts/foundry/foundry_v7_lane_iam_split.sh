#!/usr/bin/env bash
# Split the corpus-parametric runtime IAM between the two v7 lanes.
#
# The transport's least-privilege law requires each lane's service account
# to hold EXACTLY its own batch/foundation prefixes (configure refused the
# OR'd two-lane conditions fail-closed, pre-write). Lane A keeps the
# original SA with conditions SHRUNK to lane-a prefixes; lane B gets its
# own SA (corpus-parametric-research-b@) and its own single-permission
# custom role pair (corpusParametricObject{Get,Create}V2B — a distinct
# role per lane so the raw bucket's unconditional principal-exact GET
# binding can never merge members), with lane-b conditions on the
# parametric bucket and mirrored read conditions on source/retrieval/raw.
#
# Dry-run by default; pass --execute to apply all four buckets.

set -euo pipefail

PROJECT="nfl-predictions-503414"
SA_A="serviceAccount:corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com"
SA_B="serviceAccount:corpus-parametric-research-b@nfl-predictions-503414.iam.gserviceaccount.com"
ROLE_GET_B="projects/${PROJECT}/roles/corpusParametricObjectGetV2B"
ROLE_CREATE_B="projects/${PROJECT}/roles/corpusParametricObjectCreateV2B"
OBJ="projects/_/buckets/nfl-predictions-503414-corpus-parametric/objects"
ROOT="research/corpus-parametric-research"
BATCH_A="${OBJ}/${ROOT}/batches/20260823-corpus-parametric-production-batch-v7a/"
FOUND_A="${OBJ}/${ROOT}/foundations/20260823-corpus-parametric-production-foundation-v7a/"
BATCH_B="${OBJ}/${ROOT}/batches/20260823-corpus-parametric-production-batch-v7b/"
FOUND_B="${OBJ}/${ROOT}/foundations/20260823-corpus-parametric-production-foundation-v7b/"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

apply_bucket() {
  local bucket="$1" transform="$2"
  gcloud storage buckets get-iam-policy "gs://$bucket" --project "$PROJECT" \
    --format=json >"$WORK/$bucket-current.json"
  jq "$transform" "$WORK/$bucket-current.json" >"$WORK/$bucket-proposed.json"
  jq -e '.bindings | type == "array"' "$WORK/$bucket-proposed.json" >/dev/null
  echo "=== $bucket"
  diff <(jq -S . "$WORK/$bucket-current.json") \
       <(jq -S . "$WORK/$bucket-proposed.json") || true
  if [[ "${EXECUTE}" == "yes" ]]; then
    jq '.version = 3' "$WORK/$bucket-proposed.json" >"$WORK/$bucket-final.json"
    gcloud storage buckets set-iam-policy "gs://$bucket" \
      "$WORK/$bucket-final.json" --project "$PROJECT" >/dev/null
    echo "$bucket APPLIED"
  fi
}

EXECUTE="no"
[[ "${1:-}" == "--execute" ]] && EXECUTE="yes"

# Refuse to run twice: lane-b role must not already appear anywhere.
if gcloud storage buckets get-iam-policy \
    gs://nfl-predictions-503414-corpus-parametric --project "$PROJECT" \
    --format=json | grep -q "corpusParametricObjectGetV2B"; then
  echo "refused: lane-b bindings already present" >&2
  exit 2
fi

apply_bucket nfl-predictions-503414-corpus-parametric "
  (.bindings[] | select(.members == [\"$SA_A\"]
     and .condition.title == \"corpus-parametric-create-v2\").condition.expression)
    = \"resource.name.startsWith('$BATCH_A')\" |
  (.bindings[] | select(.members == [\"$SA_A\"]
     and .condition.title == \"corpus-parametric-read-v2\").condition.expression)
    = \"resource.name.startsWith('$FOUND_A') || resource.name.startsWith('$BATCH_A')\" |
  .bindings += [
    {role: \"$ROLE_CREATE_B\", members: [\"$SA_B\"],
     condition: {title: \"corpus-parametric-create-v2\",
                 expression: \"resource.name.startsWith('$BATCH_B')\"}},
    {role: \"$ROLE_GET_B\", members: [\"$SA_B\"],
     condition: {title: \"corpus-parametric-read-v2\",
                 expression: \"resource.name.startsWith('$FOUND_B') || resource.name.startsWith('$BATCH_B')\"}}
  ]"

for bucket in nfl-predictions-503414-corpus-retrieval \
              nfl-predictions-503414-corpus-source; do
  apply_bucket "$bucket" "
    (.bindings[] | select(.members == [\"$SA_A\"]
       and .condition.title == \"corpus-parametric-read-v2\").condition) as \$cond |
    .bindings += [{role: \"$ROLE_GET_B\", members: [\"$SA_B\"], condition: \$cond}]"
done

apply_bucket nfl-predictions-503414-raw "
  .bindings += [{role: \"$ROLE_GET_B\", members: [\"$SA_B\"]}]"

[[ "$EXECUTE" == "yes" ]] || \
  echo "(dry run only; rerun with --execute to apply all four buckets)"
