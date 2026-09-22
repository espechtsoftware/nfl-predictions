#!/usr/bin/env bash
# Sunday money-path runbook for any regular-season week (generalised from scripts/week1_sunday_runbook.sh, which is
# kept untouched as the Week-1 record).  Builds the D800 paid / D400 shadow pair in the nfl2 live clone (or reuses
# given run dirs) and verifies both receipts against the week's lock time and draft group.  The Week-1 governed
# publisher (publish_week1_a5_books.py and its week1_* module family) is Week-1-specific down to its allocation id,
# so the preflight/publish steps run only when PUBLISHER=1 is set explicitly; the money path from Week 2 on is the
# run-dir path (K90 nested build -> vetting -> emit from run dirs -> ENTER layout -> DK entries fill).
#
# Usage:  source scripts/week_env.sh && week_env 2 [GROUP]
#         scripts/sunday_runbook.sh --run-id 20260920t1410z-e7255e9
#         scripts/sunday_runbook.sh --run-id ... --paid-dir DIR --shadow-dir DIR    # reuse builds
set -euo pipefail
: "${WEEK:?source scripts/week_env.sh and call week_env WEEK first}"
# Week-3 per-game cap (week_env.sh MAX_PER_GAME; 0 = omitted). Same cap as sunday_build_host.sh.
MPG_FLAG=""; if [[ "${MAX_PER_GAME:-0}" != "0" ]]; then MPG_FLAG="--max-per-game $MAX_PER_GAME"; fi
: "${GROUP:?}" "${LOCK_UTC:?}" "${WEEKDIR:?}" "${CLONE:?}" "${LAB_PY:?}" "${EXPECT_SHA:?}" "${OUT:?}"
LEV=${PAID_LEV:-160}; BOOM=${PAID_BOOM:-640}; SHADOW_LEV=${SHADOW_LEV:-80}; SHADOW_BOOM=${SHADOW_BOOM:-320}

RUN_ID=""; PAID_DIR=""; SHADOW_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID=$2; shift 2 ;;
    --paid-dir) PAID_DIR=$2; shift 2 ;;
    --shadow-dir) SHADOW_DIR=$2; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ "$RUN_ID" =~ ^[a-z0-9][a-z0-9-]{0,79}$ ]] || { echo "--run-id must be lowercase [a-z0-9-]" >&2; exit 2; }
git -C "$CLONE" rev-parse --is-inside-work-tree > /dev/null 2>&1 || { echo "clone missing: $CLONE" >&2; exit 2; }
[[ "$(git -C "$CLONE" rev-parse HEAD)" == "$EXPECT_SHA" ]] || { echo "clone HEAD != $EXPECT_SHA" >&2; exit 2; }
[[ -z "$(git -C "$CLONE" status --porcelain)" ]] || { echo "clone is dirty" >&2; exit 2; }
mkdir -p "$CLONE/results/live/$WEEKDIR"

step() { printf '\n==== %s ====\n' "$*"; }

build() {  # $1 = lev, $2 = boom, $3 = entries, $4 = extra flags
  local before after
  before=$(cat "$CLONE/results/live/$WEEKDIR/LATEST" 2>/dev/null || true)
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
      --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector dual_emax \
      --lev "$1" --boom "$2" --sims 10000 --k 1 --seed 2026 --entries "$3" $4 \
      > /dev/null 2> "$CLONE/results/live/$WEEKDIR/runbook-build-$1-$2-$3.err" )
  after=$(cat "$CLONE/results/live/$WEEKDIR/LATEST")
  [[ -n "$after" && "$after" != "$before" ]] || { echo "build did not create a new run dir (see $CLONE/results/live/$WEEKDIR/runbook-build-$1-$2-$3.err)" >&2; exit 1; }
  echo "$CLONE/results/live/$WEEKDIR/$after"
}

verify() {  # $1 = run dir, $2 = lev, $3 = boom, $4 = entries, $5 = require sidecars (1/0)
  "$LAB_PY" - "$1" "$2" "$3" "$4" "$5" "$EXPECT_SHA" "$LOCK_UTC" "$GROUP" <<'PYEOF'
import csv, json, sys
from pathlib import Path
d, lev, boom, entries, sidecars, sha, lock, group = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "1", sys.argv[6], sys.argv[7], sys.argv[8]
r = json.loads((d / "receipt.json").read_text())
problems = []
if r["identity"]["sha"] != sha or r["identity"]["dirty"]: problems.append(f"identity {r['identity']}")
if (r["config"]["lev"], r["config"]["boom"]) != (lev, boom): problems.append(f"config {r['config']['lev']}/{r['config']['boom']}")
if r["written"] != entries or r["config"]["operational_k"] != entries: problems.append(f"written {r['written']} / operational_k {r['config']['operational_k']} != {entries}")
if str(r["lock_utc"]) != lock: problems.append(f"lock_utc {r['lock_utc']} != {lock}")
if str(r["draft_group"]) != str(group): problems.append(f"draft_group {r['draft_group']} != {group}")
rows = list(csv.reader((d / "book.csv").open()))
if rows[0] != ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]: problems.append("book.csv header")
if len(rows) - 1 != entries or len({tuple(sorted(x)) for x in rows[1:]}) != entries: problems.append("book.csv rows/uniqueness")
need = ["book.csv", "book.json", "candidates.parquet", "frame.parquet", "exposure_ledger.json", "receipt.json"]
if sidecars: need += ["book_wemax.csv", "book_wemax.json", "incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"]
missing = [n for n in need if not (d / n).is_file()]
if missing: problems.append(f"missing {missing}")
if problems:
    print("RECEIPT CHECK FAILED: " + "; ".join(problems)); sys.exit(1)
print(f"receipt ok: {d.name} lev/boom {lev}/{boom} entries {entries} candidates {r['candidates']} salary_pull {r['salary_pull']} seconds {r['seconds']}")
PYEOF
}

if [[ -z "$PAID_DIR" ]]; then
  step "1a. build D$((LEV + BOOM)) paid (lev $LEV / boom $BOOM, K80, sidecars)"
  PAID_DIR=$(build "$LEV" "$BOOM" 80 "--emit-a5-sidecars $MPG_FLAG")
fi
if [[ -z "$SHADOW_DIR" ]]; then
  step "1b. build D$((SHADOW_LEV + SHADOW_BOOM)) shadow (lev $SHADOW_LEV / boom $SHADOW_BOOM)"
  SHADOW_DIR=$(build "$SHADOW_LEV" "$SHADOW_BOOM" 80 "$MPG_FLAG")
fi
step "2. verify receipts (lock $LOCK_UTC, group $GROUP)"
for _d in "$PAID_DIR" "$SHADOW_DIR"; do
  python3 - "$_d" "${MAX_PER_GAME:-0}" <<'CAPEOF' || { echo "per-game cap NOT in effect in $_d"; exit 1; }
import json, sys
r = json.load(open(sys.argv[1] + "/receipt.json")); want = int(sys.argv[2])
got = (r.get("config", {}).get("arm", {}) or {}).get("max_per_game")
print(f"receipt max_per_game={got} expected={want or None}")
sys.exit(0 if ((got is None) if want == 0 else (got == want)) else 1)
CAPEOF
done
verify "$PAID_DIR" "$LEV" "$BOOM" 80 1
verify "$SHADOW_DIR" "$SHADOW_LEV" "$SHADOW_BOOM" 80 0
echo "paid=$PAID_DIR"
echo "shadow=$SHADOW_DIR"

if [[ "${PUBLISHER:-0}" == "1" ]]; then
  step "3. governed publisher preflight (Week-1 publisher family; only valid for week 1)"
  exec "$PROD/scripts/week1_sunday_runbook.sh" --run-id "$RUN_ID" --paid-dir "$PAID_DIR" --shadow-dir "$SHADOW_DIR"
else
  step "3. governed publisher SKIPPED (Week-1-specific; set PUBLISHER=1 for week 1). The immutable run dirs and the emit receipts are the record."
fi
