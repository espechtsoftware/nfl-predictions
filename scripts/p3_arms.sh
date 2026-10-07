#!/usr/bin/env bash
# P3's paper arms (the frozen prereg reports/2026-10-07-prereg-p3-simple-baseline.md §2), built from the ENTERED T-70
# union's own recorded inputs, EACH TWICE, into <out>:
#   ENTERED     union_paper_rebuild.sh same -- both builds must equal the entered book.csv byte for byte, else the
#               week's P3 read is VOID;
#   MEAN_MILP   the union's recorded args MINUS our construction layers -- the shape portfolio (--mix-*), any ownership
#               term (--main-own-*), term block (--term-block-*), sleeve (--tail-sleeve / --sleeve-*), winner order /
#               select, QB cap and the overlap limit (--mean-max-shared: the union's default 7) -- PLUS --main pmo_x50
#               --tail-sleeve 0. Production's caps (main cap share, DST caps, salary floor, games per row), the pool, the
#               live projections (the union's own proj_source.csv when it read one) and the week's K are kept (K + T in a
#               week with a tail sleeve, so its last T plain rows take the tail-track contests). The house
#               stacking rules stay (pmo_rows has no switch): "no layers" = none of OUR layers, not a raw MILP;
#   PROPS_MILP  MEAN_MILP with --proj-source <out>/proj_props.csv (scripts/props_projection_file.py: props where real,
#               else the live projection).
# A paper arm whose two builds differ, or that fails to build, is VOID for the week (recorded); the others stand.
# The Saturday and T-70 runs are PINNED to the receipt's and content-checked (as union_paper_rebuild.sh does).
# Writes only under <out> (which must not exist): the builds, proj_props.csv(.json) and arms.json.
#   CLONE=<the lab clone the union ran on> bash scripts/p3_arms.sh <entered union dir> <out dir>
set -uo pipefail
U=${1:?entered union dir}; OUTD=${2:?out dir}
PROD=${PROD:-$(cd "$(dirname "$0")/.." && pwd)}; LAB_PY=${LAB_PY:-$HOME/projects/nfl2/.venv/bin/python}; : "${CLONE:?CLONE}"
PY=${PROD_PY:-$HOME/projects/nfl-predictions/.venv/bin/python}
[[ -f "$U/union_args.txt" && -f "$U/receipt.json" && -f "$U/book.csv" ]] || { echo "P3 ARMS REFUSED: $U lacks union_args.txt, receipt.json or book.csv"; exit 2; }
[[ -e "$OUTD" ]] && { echo "P3 ARMS REFUSED: $OUTD exists"; exit 2; }
mkdir -p "$OUTD"
eval "ARGS=( $(cat "$U/union_args.txt") )"
read -r SAT T70 < <("$LAB_PY" -c "import json,sys; u=json.load(open(sys.argv[1]))['config']['union']; print(u['saturday_run'], u['t70_run'])" "$U/receipt.json")
"$LAB_PY" - "$U/receipt.json" "$SAT" "$T70" <<'PY' || exit 2
import hashlib, json, sys
from pathlib import Path
u = json.load(open(sys.argv[1]))["config"]["union"]["input_sha256"]; sat, t70 = Path(sys.argv[2]), Path(sys.argv[3])
for name, f in (("saturday_candidates", sat / "candidates.parquet"), ("t70_candidates", t70 / "candidates.parquet"), ("t70_frame", t70 / "frame.parquet")):
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    if h != u[name]:
        sys.exit(f"P3 ARMS REFUSED: {f} sha256 {h[:12]} != the receipt's {name} {u[name][:12]}")
print("inputs match the receipt (saturday candidates, t70 candidates, t70 frame)")
PY
echo "== P3 arms from $U: code $(git -C "$PROD" rev-parse --short HEAD), lab $(git -C "$CLONE" rev-parse --short HEAD), out $OUTD  $(date)"

# the plain-optimizer args: drop our layers (flags that take a value, and the switches), keep the rest
DROP_V=" --saturday-run --t70-run --out --main --main-own-tilt --main-own-source --main-own-min-coverage --sleeve-own-source
 --sleeve-source --sleeve-field-n --sleeve-field-seed --sleeve-field-mode --sleeve-field-keep --sleeve-field-rows
 --sleeve-max-per-game --sleeve-cap-share --winner-select --winner-order --main-qb-cap-rows --main-qb-cap-k --mix-portfolio
 --mix-plan --mix-spares --mix-cover-games --mix-rs-rows --mix-fill --mix-layout --term-block-rows --term-block-source
 --term-block-tilt --term-block-cap-points --term-block-min-coverage --tail-sleeve --tail-line --mean-max-shared --proj-source "
DROP_S=" --sleeve-includes-main --rehearsal "
BASE=(); i=0; n=${#ARGS[@]}; PROJ=""; K=""; T=0
while (( i < n )); do x=${ARGS[$i]}
  [[ "$x" == --entries ]] && K=${ARGS[$((i+1))]}
  [[ "$x" == --tail-sleeve ]] && T=${ARGS[$((i+1))]}
  if [[ "$x" == --proj-source ]]; then PROJ=${ARGS[$((i+1))]}; i=$((i+2)); continue; fi
  if [[ "$DROP_V" == *" $x "* ]]; then i=$((i+2)); continue; fi
  if [[ "$DROP_S" == *" $x "* ]]; then i=$((i+1)); continue; fi
  BASE+=("$x"); i=$((i+1))
done
# the live projections: the union dir's own copy of what it read (content-checked by its sidecar), else the recorded path
LIVE_PROJ=""
if [[ -n "$PROJ" ]]; then
  if [[ -s "$U/proj_source.csv" && -s "$U/proj_source.csv.json" ]]; then LIVE_PROJ=$U/proj_source.csv; else LIVE_PROJ=$PROJ; fi
fi
PROPS=$OUTD/proj_props.csv
"$PY" "$PROD/scripts/props_projection_file.py" --frame "$T70/frame.parquet" ${LIVE_PROJ:+--base "$LIVE_PROJ"} --out "$PROPS" || echo "PROPS FILE FAILED: PROPS_MILP will be void"

# the head layout deals tail-track contests the book's LAST T rows (the sleeve), so in a week with a tail sleeve (W1-4) the
# plain arms solve K + T rows -- their last T plain rows take the tail contests (no sleeve); from W5 (T = 0) this is K
[[ "$K" =~ ^[0-9]+$ ]] || { echo "P3 ARMS REFUSED: no --entries in $U/union_args.txt"; exit 2; }
PLAIN_K=$((K + T)); echo "K $K, tail sleeve $T: the plain arms solve $PLAIN_K rows"
build() {  # $1 arm, $2 build number, rest: extra args
  local arm=$1 k=$2; shift 2
  ( cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py "${BASE[@]}" "$@" \
      --saturday-run "$SAT" --t70-run "$T70" --out "$OUTD/$arm-$k" --rehearsal ) > "$OUTD/$arm-$k.txt" 2>&1
  echo "  $arm build $k rc $? ($(date +%H:%M:%S))"
}
for k in 1 2; do
  CLONE="$CLONE" PROD="$PROD" LAB_PY="$LAB_PY" bash "$PROD/scripts/union_paper_rebuild.sh" "$U" "$OUTD/ENTERED-$k" same > "$OUTD/ENTERED-$k.txt" 2>&1
  echo "  ENTERED build $k rc $? ($(date +%H:%M:%S))"
  build MEAN_MILP "$k" --main pmo_x50 --entries "$PLAIN_K" --tail-sleeve 0 ${LIVE_PROJ:+--proj-source "$LIVE_PROJ"}
  [[ -s "$PROPS" ]] && build PROPS_MILP "$k" --main pmo_x50 --entries "$PLAIN_K" --tail-sleeve 0 --proj-source "$PROPS"
done
"$PY" - "$U" "$OUTD" <<'PY'
import hashlib, json, sys
from pathlib import Path
U, O = Path(sys.argv[1]), Path(sys.argv[2])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
entered = sha(U / "book.csv"); out = {"entered_union": str(U), "entered_book_sha256": entered, "arms": {}}
for arm in ("ENTERED", "MEAN_MILP", "PROPS_MILP"):
    b = [sha(O / f"{arm}-{k}" / "book.csv") for k in (1, 2)]
    void = None
    if None in b:
        void = "a build failed"
    elif b[0] != b[1]:
        void = "the two builds differ"
    elif arm == "ENTERED" and b[0] != entered:
        void = "not byte-identical to the entered book.csv: the week's P3 read is VOID"
    out["arms"][arm] = {"builds": b, "book": str(O / f"{arm}-1" / "book.csv"), "void": void}
    print(f"  {arm:10s} build 1 {str(b[0])[:12]}  build 2 {str(b[1])[:12]}  " + ("VOID: " + void if void else "OK" + (" (= the entered book)" if arm == "ENTERED" else " (twin builds identical)")))
out["week_void"] = out["arms"]["ENTERED"]["void"] is not None or out["arms"]["MEAN_MILP"]["void"] is not None
(O / "arms.json").write_text(json.dumps(out, indent=1) + "\n")
print("== arms.json written; the primary pair (ENTERED, MEAN_MILP) is " + ("VOID this week" if out["week_void"] else "valid"))
PY
