#!/usr/bin/env bash
# PAPER rebuild of a union from its own recorded inputs (adoption track v2's unchanged comparison; reviewer 10-02): the
# union dir's union_args.txt, with the Saturday and T-70 runs PINNED to the ones its receipt names (content-checked
# against the receipt's input sha256s), the ownership source swapped, and the output sent to --out (never the live tree).
#   union_paper_rebuild.sh <union dir> <out dir> same                   # reproduce the entered book (determinism check)
#   union_paper_rebuild.sh <union dir> <out dir> own <file> <tilt>      # the term (and the field row) on another file
#   union_paper_rebuild.sh <union dir> <out dir> none                   # no term; the field row on the lag file given
#                                                                       #   as SLEEVE_OWN=<file>
# Env: CLONE (the lab clone the union ran on), PROD (default: this checkout), LAB_PY.
set -euo pipefail
U=${1:?union dir}; OUTD=${2:?out dir}; MODE=${3:?same|own|none}
PROD=${PROD:-$(cd "$(dirname "$0")/.." && pwd)}; LAB_PY=${LAB_PY:-$HOME/projects/nfl2/.venv/bin/python}; : "${CLONE:?CLONE}"
[[ -f "$U/union_args.txt" && -f "$U/receipt.json" ]] || { echo "PAPER REBUILD REFUSED: $U lacks union_args.txt or receipt.json"; exit 2; }
[[ -e "$OUTD" ]] && { echo "PAPER REBUILD REFUSED: $OUTD exists"; exit 2; }
eval "ARGS=( $(cat "$U/union_args.txt") )"
read -r SAT T70 < <("$LAB_PY" -c "import json,sys; u=json.load(open(sys.argv[1]))['config']['union']; print(u['saturday_run'], u['t70_run'])" "$U/receipt.json")
# the pinned inputs must still be the ones the union read (content, not path)
"$LAB_PY" - "$U/receipt.json" "$SAT" "$T70" <<'PY'
import hashlib, json, sys
from pathlib import Path
u = json.load(open(sys.argv[1]))["config"]["union"]["input_sha256"]; sat, t70 = Path(sys.argv[2]), Path(sys.argv[3])
for name, f in (("saturday_candidates", sat / "candidates.parquet"), ("t70_candidates", t70 / "candidates.parquet"), ("t70_frame", t70 / "frame.parquet")):
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    if h != u[name]:
        sys.exit(f"PAPER REBUILD REFUSED: {f} sha256 {h[:12]} != the receipt's {name} {u[name][:12]}")
print("inputs match the receipt (saturday candidates, t70 candidates, t70 frame)")
PY
NEW=(); skip=0
for x in "${ARGS[@]}"; do
  if (( skip )); then skip=0; continue; fi
  case "$x" in
    --saturday-run|--t70-run|--out) skip=1 ;;
    --main-own-tilt|--main-own-source|--sleeve-own-source) [[ "$MODE" == same ]] && NEW+=("$x") || skip=1 ;;
    *) NEW+=("$x") ;;
  esac
done
case "$MODE" in
  same) ;;
  own)  NEW+=(--main-own-source "${4:?file}" --main-own-tilt "${5:?tilt}" --sleeve-own-source "$4") ;;
  none) [[ -n "${SLEEVE_OWN:-}" ]] && NEW+=(--sleeve-own-source "$SLEEVE_OWN") ;;
  *) echo "mode: same | own <file> <tilt> | none"; exit 2 ;;
esac
NEW+=(--saturday-run "$SAT" --t70-run "$T70" --out "$OUTD" --rehearsal)   # --rehearsal: refuses an --out inside --live-dir; receipt says PAPER
cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py "${NEW[@]}"
