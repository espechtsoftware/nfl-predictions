#!/usr/bin/env bash
# Candidate-D-only Rule-1 worker. It runs the exact shared science path once,
# then journals only the compact false-authority receipt and raw GNU time.

set -euo pipefail
export LC_ALL=C

[[ "${FOUNDRY_T230_PREFREEZE_SMOKE_ENABLED:-}" == "1" ]]
[[ "${FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED:-}" == "1" ]]
[[ "${T230_PREFREEZE_CANDIDATE_IMAGE:-}" =~ @sha256:[0-9a-f]{64}$ ]]
[[ "${CLOUD_RUN_JOB:-}" == "atlas-minimal-c-s2023-w1-v1" ]]
[[ "${CLOUD_RUN_TASK_INDEX:-}" == "0" ]]
[[ "${CLOUD_RUN_TASK_ATTEMPT:-}" == "0" ]]
[[ "${CLOUD_RUN_TASK_COUNT:-}" == "1" ]]

receipt=/tmp/foundry-t230-prefreeze-smoke-v1.json
time_v=/tmp/foundry-t230-prefreeze-smoke-gnu-time-v.raw.txt
receipt_publication=/tmp/foundry-t230-prefreeze-smoke-publication.json

test ! -e "$receipt"
test ! -e "$time_v"
test ! -e "$receipt_publication"

/usr/bin/time -v -o "$time_v" \
  python scripts/run_corpus_extreme_tail_t230_prefreeze_smoke_v1.py \
  --execute --receipt-output "$receipt" \
  >/tmp/foundry-t230-prefreeze-smoke.stdout.json

python scripts/run_corpus_extreme_tail_panel_transport_v1.py \
  publish-prefreeze-smoke --smoke-receipt "$receipt" --execute \
  >"$receipt_publication"

python scripts/run_corpus_extreme_tail_panel_transport_v1.py \
  publish-prefreeze-smoke-time-v \
  --smoke-receipt-uri "$(jq -er '.target_identity.uri' "$receipt_publication")" \
  --smoke-receipt-generation "$(jq -er '.target_identity.generation' "$receipt_publication")" \
  --smoke-receipt-sha256 "$(jq -er '.target_identity.sha256' "$receipt_publication")" \
  --smoke-receipt-bytes "$(jq -er '.target_identity.bytes' "$receipt_publication")" \
  --smoke-receipt "$receipt" --raw-time-v "$time_v" --execute
