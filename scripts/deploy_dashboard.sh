#!/usr/bin/env bash
# Point the nfl-dfs-app Cloud Run service at a dashboard-v2 image.
#
#   scripts/deploy_dashboard.sh dashboard-<SHORT_SHA>            # tag pushed by cloudbuild.dashboard.yaml
#   scripts/deploy_dashboard.sh us-central1-docker.pkg.dev/...@sha256:<digest>
#
# What it changes, and nothing else: ONLY the nfl-dfs-app service gets the
# image digest (never a mutable tag, never :latest), command `nfl-dfs`,
# args `dashboard` and CODE_SHA. No Neo4j secrets: the Milly graph is local
# only and not part of the UI (operator 2026-10-04). Every other env var,
# secret, service account, scaling and the IAP-only invoker policy are left
# exactly as they are
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
HERE="$(cd "$(dirname "$0")" && pwd)"

ref="${1:?usage: $0 <dashboard-SHORT_SHA tag | image@sha256:digest>}"

# Every weekend, Saturday 00:00 to Sunday 15:30 Central (DST-aware), the money
# path builds, vets and late-swaps the week's books on this host: never replace
# the app then. Was a one-off NOT_BEFORE date until 2026-10-04.
now=$(date -u +%s)
dow=$(TZ=America/Chicago date -d "@$now" +%u)     # 6 = Saturday, 7 = Sunday
hm=$(TZ=America/Chicago date -d "@$now" +%H%M)
if { (( dow == 6 )) || { (( dow == 7 )) && (( 10#$hm < 1530 )); }; } && [[ "${FORCE:-0}" != "1" ]]; then
  echo "REFUSED: Saturday 00:00 to Sunday 15:30 CT is the weekend money window (now $(TZ=America/Chicago date -d "@$now" '+%a %H:%M %Z')); set FORCE=1 to override." >&2
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

args=(run services update "$SERVICE" --region "$REGION" --project "$PROJECT"
      --image "$image" --command nfl-dfs --args dashboard
      --update-env-vars "CODE_SHA=${code_sha}")
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
