#!/usr/bin/env bash
# Resumable per-lane v7 chain: identities -> IAM capture -> configure ->
# contract append -> driver task-0 -> acceptance gate -> fan-out.
# Each stage is skipped when its durable receipt already exists, so the
# script is safe to rerun after any crash. Usage:
#   run_foundry_lane_chain.sh a|b
# Requires the lane foundation execute-result.json to exist already.

set -euo pipefail

LANE="${1:?lane a or b required}"
[[ "$LANE" == "a" || "$LANE" == "b" ]] || { echo "lane must be a|b" >&2; exit 2; }
ROOT=/home/erich/projects/nfl-predictions
FOUNDRY="$ROOT/scripts/foundry"
ENV_FILE="$FOUNDRY/foundry_v7${LANE}_env.sh"
RUN_ROOT="$ROOT/reports/corpus-parametric-runs/20260823-foundry-production-v7${LANE}"
PY311=/tmp/nfl-corpus-py311/bin/python

log() { printf '%s lane-%s %s\n' "$(date -u +%FT%TZ)" "$LANE" "$*"; }

[[ -s "$RUN_ROOT/foundation-live/execute-result.json" ]] || {
  echo "refused: lane $LANE foundation execute-result.json absent" >&2; exit 3; }

# 1. Publication identities into the lane env (idempotent: appender
#    refuses once present; treat that refusal as already-done).
if ! grep -q "CORPUS_PARAMETRIC_FOUNDATION_PUBLICATION_URI" "$ENV_FILE"; then
  log "appending publication identities"
  "$ROOT/.venv/bin/python" "$FOUNDRY/append_foundry_lane_identities.py" \
    --lane "$LANE" --append >/dev/null
else
  log "publication identities already appended"
fi

# 2. Runtime IAM capture (create-once inside the script).
if [[ ! -s "$RUN_ROOT/governance-live-v7${LANE}/runtime-iam-policy-capture.json" ]]; then
  log "capturing runtime IAM policy"
  "$PY311" "$FOUNDRY/capture_foundry_lane_iam.py" --lane "$LANE" >/dev/null
else
  log "runtime IAM capture already present"
fi

# 3. Configure (create-once evidence paths guard reruns).
source "$ENV_FILE"
if [[ ! -s "$CORPUS_PARAMETRIC_RUN_DIR/configured.json" ]]; then
  log "running configure"
  ( cd "$CORPUS_PARAMETRIC_SOURCE" && \
    bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute configure )
else
  log "configure evidence already present"
fi

# 4. Contract identity into the lane env.
if ! grep -q "CORPUS_PARAMETRIC_CONTRACT_URI" "$ENV_FILE"; then
  log "appending transport contract identity"
  "$ROOT/.venv/bin/python" - "$LANE" << 'PYEOF'
import json, sys
lane = sys.argv[1]
root = "/home/erich/projects/nfl-predictions"
run_dir = (
    f"{root}/reports/corpus-parametric-runs/"
    f"20260823-foundry-production-v7{lane}/transport-live-v7{lane}"
)
doc = json.load(open(f"{run_dir}/configured.json"))
contract = doc["transport_contract"]
lines = [
    "",
    "# Transport contract identity — copied from configured.json.",
    f"export CORPUS_PARAMETRIC_CONTRACT_URI='{contract['uri']}'",
    f"export CORPUS_PARAMETRIC_CONTRACT_GENERATION={contract['generation']}",
    f"export CORPUS_PARAMETRIC_CONTRACT_SHA256={contract['sha256']}",
    f"export CORPUS_PARAMETRIC_CONTRACT_BYTES={contract['bytes']}",
]
path = f"{root}/scripts/foundry/foundry_v7{lane}_env.sh"
body = open(path).read()
assert "CORPUS_PARAMETRIC_CONTRACT_URI" not in body
open(path, "a").write("\n".join(lines) + "\n")
print("contract", contract["generation"])
PYEOF
  source "$ENV_FILE"
else
  log "contract identity already appended"
fi

# 5. Task-0 (driver is receipt-resumable; FATAL propagates).
log "driving task 0"
bash "$FOUNDRY/foundry_batch_driver.sh" 0 0

# 6. Independent acceptance gate (create-once outputs).
if [[ ! -s "$CORPUS_PARAMETRIC_RUN_DIR/task0-acceptance-pass.json" ]]; then
  log "running task-0 independent acceptance gate"
  bash "$FOUNDRY/run_foundry_task0_gate.sh"
else
  log "task-0 gate already passed"
fi

# 7. Fan-out.
LAST=27; [[ "$LANE" == "b" ]] && LAST=25
log "driving tasks 1..$LAST"
bash "$FOUNDRY/foundry_batch_driver.sh" 1 "$LAST"
log "lane $LANE COMPLETE through task $LAST"
