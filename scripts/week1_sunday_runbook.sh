#!/usr/bin/env bash
# Week-1 Sunday money-path runbook (state audit §3.3), stopping before anything
# irreversible.  Builds the D800/D400 live pair in the nfl2 clone (or reuses
# given run dirs), verifies both receipts, runs the publisher preflight
# WITHOUT --execute, and then prints the exact --execute, emit and upload
# commands for the operator to run by hand.  Nothing here publishes, uploads,
# or opens an outcome.
#
# Usage:
#   scripts/week1_sunday_runbook.sh --run-id 20260913t0930z-fa5d035
#   scripts/week1_sunday_runbook.sh --run-id ... --paid-dir DIR --shadow-dir DIR   # reuse builds
set -euo pipefail

CLONE=${WEEK1_CLONE:-/home/erich/projects/.nfl2-worktrees/week1-live-center-818f672}   # corrected centering: reports/2026-09-12-week1-baseline-fix-and-tonight-steps.md
PUBLISHER_TREE=${WEEK1_PUBLISHER_TREE:-/home/erich/projects/.nfl-predictions-worktrees/week1-publisher-20260912}
CODE_SHA=${WEEK1_CODE_SHA:-00c6097f6b369c7f28ff88a5b8db2c3c936e9c39}
LAB_PY=${WEEK1_LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
PROD_PY=${WEEK1_PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
PUBLISH_ROOT="gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/a5-books"
GROUP=151307
LOCK_UTC="2026-09-13 17:00:00+00:00"
EXPECT_SHA=${WEEK1_EXPECT_SHA:-818f672f4fd75b87d4a4a3f9f4677af6384df0c5}   # lab/live-center-production-20260912 (NFL2_LIVE_CENTER=production)
UPLOAD_DIR=${WEEK1_UPLOAD_DIR:-/home/erich}

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
[[ -f "$PUBLISHER_TREE/scripts/publish_week1_a5_books.py" ]] || { echo "publisher tree missing" >&2; exit 2; }
[[ "$(git -C "$PUBLISHER_TREE" rev-parse HEAD)" == "$CODE_SHA" ]] || { echo "publisher tree HEAD != $CODE_SHA" >&2; exit 2; }
[[ -z "$(git -C "$PUBLISHER_TREE" status --porcelain)" ]] || { echo "publisher tree is dirty" >&2; exit 2; }
[[ "$(git -C "$CLONE" rev-parse HEAD)" == "$EXPECT_SHA" ]] || { echo "clone HEAD != $EXPECT_SHA" >&2; exit 2; }
[[ -z "$(git -C "$CLONE" status --porcelain)" ]] || { echo "clone is dirty" >&2; exit 2; }

step() { printf '\n==== %s ====\n' "$*"; }

build() {  # $1 = lev, $2 = boom, $3 = extra flags
  local before after
  before=$(cat "$CLONE/results/live/2026-w01/LATEST" 2>/dev/null || true)
  ( cd "$CLONE" && NFL2_LIVE_CENTER=production PYTHONPATH="$CLONE/src" "$LAB_PY" scripts/live_week.py \
      --season 2026 --week 1 --group "$GROUP" --selector dual_emax \
      --lev "$1" --boom "$2" --sims 10000 --k 1 --seed 2026 --entries 80 $3 \
      > /dev/null 2> "$CLONE/results/live/2026-w01/runbook-build-$1-$2.err" )
  after=$(cat "$CLONE/results/live/2026-w01/LATEST")
  [[ -n "$after" && "$after" != "$before" ]] || { echo "build did not create a new run dir" >&2; exit 1; }
  echo "$CLONE/results/live/2026-w01/$after"
}

verify() {  # $1 = run dir, $2 = lev, $3 = boom, $4 = require sidecars (1/0)
  "$LAB_PY" - "$1" "$2" "$3" "$4" "$EXPECT_SHA" "$LOCK_UTC" <<'PYEOF'
import csv, json, sys
from pathlib import Path
d, lev, boom, sidecars, sha, lock = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] == "1", sys.argv[5], sys.argv[6]
r = json.loads((d / "receipt.json").read_text())
problems = []
if r["identity"]["sha"] != sha or r["identity"]["dirty"]: problems.append(f"identity {r['identity']}")
if (r["config"]["lev"], r["config"]["boom"]) != (lev, boom): problems.append(f"config {r['config']['lev']}/{r['config']['boom']}")
if r["written"] != 80 or r["config"]["operational_k"] != 80: problems.append(f"written {r['written']}")
if str(r["lock_utc"]) != lock: problems.append(f"lock_utc {r['lock_utc']}")
if str(r["draft_group"]) != "151307": problems.append(f"draft_group {r['draft_group']}")
rows = list(csv.reader((d / "book.csv").open()))
if rows[0] != ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]: problems.append("book.csv header")
if len(rows) - 1 != 80 or len({tuple(sorted(x)) for x in rows[1:]}) != 80: problems.append("book.csv rows/uniqueness")
need = ["book.csv", "book.json", "candidates.parquet", "frame.parquet", "exposure_ledger.json", "receipt.json"]
if sidecars: need += ["book_wemax.csv", "book_wemax.json", "incumbent_player_scores.npy", "corrected_hsim_player_scores.npy"]
missing = [n for n in need if not (d / n).is_file()]
if missing: problems.append(f"missing {missing}")
if problems:
    print("RECEIPT CHECK FAILED: " + "; ".join(problems)); sys.exit(1)
print(f"receipt ok: {d.name} lev/boom {lev}/{boom} candidates {r['candidates']} written 80 salary_pull {r['salary_pull']} seconds {r['seconds']}")
PYEOF
}

if [[ -z "$PAID_DIR" ]]; then
  step "1a. build D800 (lev 160 / boom 640, sidecars)"
  PAID_DIR=$(build 160 640 --emit-a5-sidecars)
fi
if [[ -z "$SHADOW_DIR" ]]; then
  step "1b. build D400 (lev 80 / boom 320)"
  SHADOW_DIR=$(build 80 320 "")
fi
step "2. verify receipts"
verify "$PAID_DIR" 160 640 1
verify "$SHADOW_DIR" 80 320 0

step "3. publisher preflight (NO --execute)"
PREFLIGHT_FILE="$UPLOAD_DIR/week1-preflight-$RUN_ID.json"
[[ ! -e "$PREFLIGHT_FILE" ]] || { echo "preflight record exists: $PREFLIGHT_FILE (use a new run id)" >&2; exit 2; }
( cd "$PUBLISHER_TREE" && PYTHONPATH="$PUBLISHER_TREE/src" "$PROD_PY" scripts/publish_week1_a5_books.py \
    --paid-run-dir "$PAID_DIR" --shadow-run-dir "$SHADOW_DIR" --nfl2-source-root "$CLONE" \
    --run-id "$RUN_ID" --code-sha "$CODE_SHA" 2> "$UPLOAD_DIR/week1-preflight-$RUN_ID.err" | tail -1 > "$PREFLIGHT_FILE" )
"$PROD_PY" - "$PREFLIGHT_FILE" <<'PYCHECK'
import json, sys
p = json.load(open(sys.argv[1]))
assert p["execute"] is False and p["contest_entries_submitted"] is False, p
hashes = p["book_semantic_sha256"]
assert len(set(hashes.values())) == 4, hashes
assert p["pmix_turnover_per_side"] >= 1, p["pmix_turnover_per_side"]
print(f"preflight ok: pmix_turnover_per_side={p['pmix_turnover_per_side']} "
      f"designations={p['designation_count']} history_rows={p['history_rows']} "
      f"record={sys.argv[1]}")
PYCHECK

step "4. operator commands (not run by this script)"
cat <<EOF
# 4a. publish, exactly once for this run id (create-once):
cd $PUBLISHER_TREE && PYTHONPATH=$PUBLISHER_TREE/src $PROD_PY scripts/publish_week1_a5_books.py \\
  --paid-run-dir $PAID_DIR --shadow-run-dir $SHADOW_DIR --nfl2-source-root $CLONE \\
  --run-id $RUN_ID --code-sha $CODE_SHA --execute

# 4b. emit draftable-ID upload files from the PUBLISHED books (paid = P_MIX):
cd $(git -C "$(dirname "$0")" rev-parse --show-toplevel) && for spec in "P_MIX:milly-193028206:1-57" "P_MIX:playaction-193028208:1-20" "P_MIX:ffwc-q6-194478066:1-3" "P_MIX:ffwc-q5-194478065:1-10" "P_CTRL:fallback-all:1-80"; do
  IFS=: read -r book name ranks <<<"\$spec"
  PYTHONPATH=src $PROD_PY scripts/emit_dk_upload_csv_v1.py --source published \\
    --terminal-uri $PUBLISH_ROOT/$RUN_ID/terminal.json --book-id \$book --ranks \$ranks \\
    --output $UPLOAD_DIR/week1-upload-$RUN_ID-\$book-\$name-ranks-\$ranks.csv
done

# 4c. upload each file to its contest in the DK UI (by ~11:15 CT; lock 12:00 CT).
#     Never upload book.csv (player ids).  §3.4 unique-entry alternative is the
#     operator's call; if chosen, change the --ranks per contest accordingly.
EOF
