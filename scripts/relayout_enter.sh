#!/usr/bin/env bash
# relayout_enter.sh v2 (layout-aware row check) -- rebuild the per-contest ENTER/ bundle from a given all-lineups upload CSV (e.g. the PROMOTED one),
# with the after-build chain's OWN layout code (vendored verbatim below from scripts/sunday_after_build.sh; the chain's
# sha256 at vendoring time is recorded in CHAIN_SHA), the same staged verification (verify_enter_bundle.py) and the same
# atomic versioned-bundle publication (symlink swap).  The DK-entries watcher then refills DKEntries-FILLED-keepers-first.csv.
#   relayout_enter.sh UPLOAD_CSV OUT_DIR TAG [SHEET_MD]
# env: CONTESTS_JSON (default OUT_DIR/contests.json), ENTER_LAYOUT (default sequential, as week_env.sh sets it), PROD, PY,
#      ENTER_ORDER (greedy|fewest-low) with OWNERSHIP_SETS, ENTER_BOOK_DIR (the dir holding the upload's book.csv and its
#      vetting_final.json / vetting.json; needed for fewest-low), ENTER_PIN_FIRST=1 when row 1 is a promoted entry.
# v3 (2026-09-24): the layout and its check call src/nfl_dfs/inference/enter_layout.py, the module the chain uses.
set -uo pipefail
CHAIN_SHA_AT_VENDORING=4d3babfdac600b8af980a2f7a454698864700de331ca2b2ed32841016e42d243
all=${1:?UPLOAD_CSV}; OUT=${2:?OUT_DIR}; tag=${3:?TAG}; SHEET_MD=${4:-}
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROD=${PROD:-$(cd -- "$HERE"/.. && pwd)}
PY=${PY:-${PROD_PY:-$PROD/.venv/bin/python}}
CONTESTS_JSON=${CONTESTS_JSON:-$OUT/contests.json}; export ENTER_LAYOUT=${ENTER_LAYOUT:-sequential}
log(){ printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
[ -s "$all" ] || { log "no upload csv $all"; exit 2; }; [ -s "$CONTESTS_JSON" ] || { log "no contests $CONTESTS_JSON"; exit 2; }
entries=$($PY -c "import json,sys; print(sum(int(c['entries']) for c in json.load(open(sys.argv[1]))))" "$CONTESTS_JSON")
E="$OUT/ENTER"; STAGE="$OUT/.ENTER-staging-$tag"
rm -rf "$STAGE"; mkdir -p "$STAGE"
# ---- the chain's layout: the shared module ----
ORDER_ARGS=()
if [ -n "${ENTER_BOOK_DIR:-}" ]; then
  VF="$ENTER_BOOK_DIR/vetting_final.json"; [ -f "$VF" ] || VF="$ENTER_BOOK_DIR/vetting.json"
  ORDER_ARGS=(--book "$ENTER_BOOK_DIR/book.csv" --vetting "$VF")
fi
[ "${ENTER_PIN_FIRST:-0}" = "1" ] && ORDER_ARGS+=(--pin-first)
if ! PYTHONPATH=$PROD/src $PY -m nfl_dfs.inference.enter_layout write "$CONTESTS_JSON" "$all" "$STAGE" ${ORDER_ARGS[@]+"${ORDER_ARGS[@]}"} > "$STAGE/ENTER-layout.txt" 2> "$STAGE.err"; then
  log "ENTER layout FAILED: $(head -c 300 "$STAGE.err") -- NOT published, previous ENTER/ kept"; rm -rf "$STAGE"; exit 1
fi
cp "$all" "$STAGE/ENTER-all-rows-1-to-$(( $($PY -c "import json; print(sum(c['keep'] for c in json.load(open('$CONTESTS_JSON'))))") ))-are-the-KEEPERS.csv"
[ -n "$SHEET_MD" ] && [ -s "$SHEET_MD" ] && cp "$SHEET_MD" "$STAGE/ENTER-sheet-keepers.md"
want=$($PY -c "import json; print(len(json.load(open('$CONTESTS_JSON'))))")
got=$(ls "$STAGE"/ENTER-*-entries-KEEP-first-*.csv 2>/dev/null | wc -l)
if [ "$want" != "$got" ]; then log "staged bundle has $got per-contest files, expected $want -- NOT published, previous ENTER/ kept"; rm -rf "$STAGE"; exit 1; fi
if ! $PY "$PROD/scripts/verify_enter_bundle.py" "$CONTESTS_JSON" "$STAGE"; then log "staged bundle failed verification -- NOT published, previous ENTER/ kept"; rm -rf "$STAGE"; exit 1; fi
# rows of the staged per-contest files must equal the upload's rows mapped through the SAME layout rule the chain uses
# (sequential: each contest's keeper slice then its fill slice from the tail; top: ranks 1..n, or a cursor block for
# contests marked "block": true) -- a layout-aware check, not a contiguous slice (laptop review 2026-09-20).
if ! PYTHONPATH=$PROD/src $PY -m nfl_dfs.inference.enter_layout check "$CONTESTS_JSON" "$all" "$STAGE" ${ORDER_ARGS[@]+"${ORDER_ARGS[@]}"}
then log "staged bundle does not reproduce the upload order under the $ENTER_LAYOUT layout -- NOT published"; rm -rf "$STAGE"; exit 1; fi
BUNDLES="$OUT/enter-bundles"; VER="$BUNDLES/$tag"
mkdir -p "$BUNDLES"; rm -rf "$VER"; mv "$STAGE" "$VER"
if [ -e "$E" ] && [ ! -L "$E" ]; then rm -rf "$BUNDLES/legacy-$tag"; mv "$E" "$BUNDLES/legacy-$tag"; fi
ln -sfn "$VER" "$E.new" && mv -T "$E.new" "$E"
log "published bundle $tag atomically: $E -> $(readlink -f "$E")"
