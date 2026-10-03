#!/usr/bin/env bash
# Point the nfl-dfs-app Cloud Run service at a dashboard-v2 image.
#
#   scripts/deploy_dashboard.sh dashboard-<SHORT_SHA>            # tag pushed by cloudbuild.dashboard.yaml
#   scripts/deploy_dashboard.sh us-central1-docker.pkg.dev/...@sha256:<digest>
#
# What it changes, and nothing else: ONLY the nfl-dfs-app service gets the
# image digest (never a mutable tag, never :latest), command `nfl-dfs`,
# args `dashboard`, CODE_SHA, and -- when the secrets exist in Secret Manager
# -- the Milly Neo4j env vars. Every other env var, secret, service account,
# scaling and the IAP-only invoker policy are left exactly as they are
# (`gcloud run services update` keeps what it is not told to change; this
# script never passes --allow-unauthenticated). No Cloud Run job uses this
# service. Before the update it requires IAP to be enabled on the service.
# After it, it sends 100% of traffic to the new revision (a rollback pins
# traffic to a revision; `update-traffic --to-latest` releases the pin), then
# reads the service and its IAM policy and fails loudly, printing the
# rollback, unless IAP is on, nothing is public, and traffic is 100% latest.
#
# Refuses before Sunday 2026-10-04 15:30 CT (the Week-4 money path) unless FORCE=1.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE=nfl-dfs-app
REPO="us-central1-docker.pkg.dev/${PROJECT}/nfl-dfs/nfl-dfs"
NOT_BEFORE_UTC="2026-10-04T20:30:00Z"   # Sunday 2026-10-04 15:30 CDT
# env var name -> Secret Manager secret id
NEO4J_SECRETS=(
  "MILLY_NEO4J_URI=milly-neo4j-uri"
  "MILLY_NEO4J_USERNAME=milly-neo4j-username"
  "MILLY_NEO4J_PASSWORD=milly-neo4j-password"
  "MILLY_NEO4J_DATABASE=milly-neo4j-database"
)
HERE="$(cd "$(dirname "$0")" && pwd)"

ref="${1:?usage: $0 <dashboard-SHORT_SHA tag | image@sha256:digest>}"

now=$(date -u +%s)
nb=$(date -u -d "$NOT_BEFORE_UTC" +%s)
if (( now < nb )) && [[ "${FORCE:-0}" != "1" ]]; then
  echo "REFUSED: before ${NOT_BEFORE_UTC} (Sunday 15:30 CT) the money path is live; set FORCE=1 to override." >&2
  exit 2
fi

if [[ "$ref" == *@sha256:* ]]; then
  image="$ref"
else
  case "$ref" in
    latest|*:latest) echo "REFUSED: never deploy :latest" >&2; exit 2 ;;
    dashboard-*) ;;
    *) echo "REFUSED: expected a dashboard-<SHORT_SHA> tag or an @sha256 digest, got '$ref'" >&2; exit 2 ;;
  esac
  digest=$(gcloud artifacts docker images describe "${REPO}:${ref}" --project "$PROJECT" \
             --format='value(image_summary.digest)')
  [[ "$digest" == sha256:* ]] || { echo "REFUSED: could not resolve ${REPO}:${ref} to a digest" >&2; exit 2; }
  image="${REPO}@${digest}"
fi
code_sha="${CODE_SHA:-${ref#dashboard-}}"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format=json > "$tmp/before.json"
if ! python3 "${HERE}/dashboard_iam_check.py" --service "$tmp/before.json"; then
  echo "REFUSED: ${SERVICE} is not IAP-protected now; fix that before deploying anything." >&2
  exit 2
fi
prev=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" \
         --format='value(status.latestReadyRevisionName)')
rollback="gcloud run services update-traffic ${SERVICE} --region ${REGION} --project ${PROJECT} --to-revisions ${prev}=100"
echo "image:    ${image}"
echo "previous: ${prev}"
echo "rollback: ${rollback}"

secrets=()
for pair in "${NEO4J_SECRETS[@]}"; do
  env_name="${pair%%=*}"; secret_id="${pair#*=}"
  if gcloud secrets describe "$secret_id" --project "$PROJECT" >/dev/null 2>&1; then
    secrets+=("${env_name}=${secret_id}:latest")
  fi
done

args=(run services update "$SERVICE" --region "$REGION" --project "$PROJECT"
      --image "$image" --command nfl-dfs --args dashboard
      --update-env-vars "CODE_SHA=${code_sha}")
if (( ${#secrets[@]} )); then
  args+=(--update-secrets "$(IFS=,; echo "${secrets[*]}")")
  echo "neo4j:    ${#secrets[@]} secret env var(s) attached"
else
  echo "neo4j:    no milly-neo4j-* secrets in Secret Manager; the graph page will say 'not configured'"
fi
gcloud "${args[@]}"
gcloud run services update-traffic "$SERVICE" --region "$REGION" --project "$PROJECT" --to-latest

gcloud run services get-iam-policy "$SERVICE" --region "$REGION" --project "$PROJECT" --format=json > "$tmp/policy.json"
gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format=json > "$tmp/service.json"
if ! python3 "${HERE}/dashboard_iam_check.py" --service "$tmp/service.json" --policy "$tmp/policy.json" --traffic; then
  echo "FAIL: ${SERVICE} is not IAP-only on its new revision with 100% of traffic. Roll back now:" >&2
  echo "  ${rollback}" >&2
  exit 1
fi
echo "deployed. If anything looks wrong: ${rollback}"
