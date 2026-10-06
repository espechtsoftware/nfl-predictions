#!/usr/bin/env bash
# Study 38's pre-lock snapshot (the laptop's part; reviewer 10-06): copy EXACTLY the inputs the union used, in the Sunday
# form the s38 build reads (one file per pattern), plus MANIFEST.txt (sha256, bytes, name, source path, source mtime,
# the union receipt's built_utc, the snapshot time). Read-only on the live tree: never edits a run dir, never writes under
# ~/weekN-sunday. Refuses if a destination exists (create-once) or if a file the union args name differs from OUT's copy.
#   bash s38_snapshot.sh <union run dir> <OUT dir> <RUN_TAG> <contest-details json> <plan-overrides json | -> <dest dir>
# A NO-TERM week (the union names no --main-own-source, e.g. the tilt set to 0): the build makes no FP ownership file
# (sunday_build_host runs the capture and export only at a non-zero tilt), so this tool runs exactly what the build would
# have: the FP ownership collect under the same FP_PROFILE_LOCK flock, then ownership_fp.py on the union frame with OUT's
# lag file and --now = the snapshot time (before lock). Env: SEASON, WEEK, PROD (a checkout), PROD_PY. S38_NO_COLLECT=1
# skips the vendor collect (tests; the export then reads the newest BigQuery capture <= --now). A refusal is printed
# and the snapshot completes without the file (the build then refuses that week, by its own rule).
# (tracked copy of the laptop tool; reviewer 10-06) Sunday: DEST=~/private/paper-corun/2026-wNN   (BEFORE 12:00 CT)
# Wednesday rehearsal (A3): DEST=~/private/paper-corun/rehearsal-w05
set -uo pipefail
UD=${1:?union run dir}; OUT=${2:?OUT}; TAG=${3:?RUN_TAG}; DETAILS=${4:?contest-details json}; OVR=${5:?plan-overrides json or -}; DEST=${6:?dest}
die() { echo "SNAPSHOT REFUSED: $*"; exit 1; }
[[ -e "$DEST" ]] && die "$DEST exists (create-once; pick a new dest)"
[[ "$DEST" == "$HOME"/week*-sunday* ]] && die "never under ~/weekN-sunday"
ARGS="$OUT/union-args-$TAG.txt"
for f in "$UD/frame.parquet" "$UD/receipt.json" "$ARGS" "$OUT/proj_fp-$TAG.csv" "$OUT/proj_fp-$TAG.csv.json" "$OUT/contests.json" "$DETAILS"; do
  [[ -s "$f" ]] || die "missing $f"
done
# the files the union actually read, by its own arguments (never assumed)
argval() { python3 - "$ARGS" "$1" <<'EOF'
import shlex, sys
a = shlex.split(open(sys.argv[1]).read()); k = sys.argv[2]
print(a[a.index(k) + 1] if k in a else "")
EOF
}
PSRC=$(argval --proj-source); OSRC=$(argval --main-own-source); DSRC=$(argval --dk-status)
[[ -n "$PSRC" ]] || die "the union args name no --proj-source (FP projections fell back?): no FP week for study 38"
cmp -s "$PSRC" "$OUT/proj_fp-$TAG.csv" || die "--proj-source $PSRC differs from $OUT/proj_fp-$TAG.csv"
if [[ -n "$OSRC" ]]; then
  case "$(basename "$OSRC")" in ownership_fp-*) ;; *) echo "NOTE: the term's source is $(basename "$OSRC"), not FP ownership (a fallback); copied as named";; esac
else
  echo "NOTE: no --main-own-source in the union args (a no-term week): generating ownership_fp-$TAG.csv at snapshot time"
  : "${SEASON:?}" "${WEEK:?}" "${PROD:?}" "${PROD_PY:?}"; [[ -s "$OUT/ownership_lag.csv" ]] || die "no $OUT/ownership_lag.csv for the export"
fi
mkdir -p "$DEST" && chmod 700 "$DEST" || die "cannot create $DEST"
cp -p "$UD/frame.parquet" "$DEST/frame.parquet"
cp -p "$PSRC" "$DEST/proj_fp-$TAG.csv"; cp -p "$OUT/proj_fp-$TAG.csv.json" "$DEST/proj_fp-$TAG.csv.json"
if [[ -n "$OSRC" ]]; then
  cp -p "$OSRC" "$DEST/$(basename "$OSRC")"
else
  NOWS=$(date -u +%Y-%m-%dT%H:%M:%SZ); OGEN="$DEST/ownership_fp-$TAG.csv"
  if [[ "${S38_NO_COLLECT:-0}" != 1 ]]; then
    LOCK=${FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock}; mkdir -p "$(dirname "$LOCK")"
    ( cd "$PROD" && PYTHONPATH="$PROD/src" flock -w 300 "$LOCK" timeout 240 "$PROD_PY" -m nfl_dfs.ops.fantasy_points_ownership collect --week "$WEEK" ) \
      > "$DEST/.ownership_collect.log" 2>&1 || echo "NOTE: the FP ownership collect failed (see $DEST/.ownership_collect.log); the newest earlier capture is used if fresh"
  fi
  ( cd "$PROD" && PYTHONPATH="$PROD/src" timeout 120 "$PROD_PY" scripts/ownership_fp.py --season "$SEASON" --week "$WEEK" \
      --frame "$UD/frame.parquet" --lag "$OUT/ownership_lag.csv" --max-age-hours "${FP_MAX_AGE_HOURS:-30}" --now "${S38_NOW:-$NOWS}" \
      --out "$OGEN" ) > "$DEST/.ownership_export.log" 2>&1 \
    && echo "ownership_fp-$TAG.csv generated: $(grep -h '^FP OWNERSHIP AGE' "$DEST/.ownership_export.log" | tail -1)" \
    || { echo "NOTE: FP OWNERSHIP EXPORT REFUSED: $(grep -h REFUSED "$DEST/.ownership_export.log" | tail -1)"; rm -f "$OGEN"; }
  OSRC_LABEL="(generated after the T-70 union by ownership_fp.py, --now ${S38_NOW:-$NOWS}; capture: $(grep -h '^FP OWNERSHIP AGE' "$DEST/.ownership_export.log" 2>/dev/null | tail -1 | tr -s ' ' | cut -c1-120))"
fi
# production passes no --dk-status (OPEN-DEFECTS O-16): then NO dk-status file is copied and the build must use none
[[ -n "$DSRC" ]] && cp -p "$DSRC" "$DEST/$(basename "$DSRC")"
cp -p "$ARGS" "$DEST/union-args-$TAG.txt"             # ONE union-args file (never also the union dir's union_args.txt)
cp -p "$OUT/contests.json" "$DEST/contests.json"
cp -p "$DETAILS" "$DEST/contest-details.json"
if [[ "$OVR" == "-" ]]; then printf '{}\n' > "$DEST/plan-overrides.json"; else cp -p "$OVR" "$DEST/plan-overrides.json"; fi
BUILT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('built_utc'))" "$UD/receipt.json")
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OVR_SRC=$OVR; [[ "$OVR" == "-" ]] && OVR_SRC="(written: {})"
{
  echo "# study 38 snapshot: union $UD (built_utc $BUILT), OUT $OUT, RUN_TAG $TAG; taken $NOW"
  echo "# sha256  bytes  name  source  source_mtime_utc"
  declare -A SRC=([frame.parquet]="$UD/frame.parquet" ["proj_fp-$TAG.csv"]="$PSRC" ["proj_fp-$TAG.csv.json"]="$OUT/proj_fp-$TAG.csv.json"
                  ["union-args-$TAG.txt"]="$ARGS" [contests.json]="$OUT/contests.json"
                  [contest-details.json]="$DETAILS" [plan-overrides.json]="$OVR_SRC")
  [[ -n "$DSRC" ]] && SRC["$(basename "$DSRC")"]="$DSRC"
  if [[ -n "$OSRC" ]]; then SRC["$(basename "$OSRC")"]="$OSRC"; else SRC["ownership_fp-$TAG.csv"]="${OSRC_LABEL:-}"; SRC["ownership_fp-$TAG.csv.receipt.json"]="(written by ownership_fp.py with the export)"; fi
  for n in $(ls "$DEST" | sort); do
    [[ "$n" == .* ]] && continue
    [[ "$n" == MANIFEST.txt ]] && continue
    s=${SRC[$n]:-?}; m=$( [[ -e "$s" ]] && date -u -r "$s" +%Y-%m-%dT%H:%M:%SZ || echo - )
    echo "$(sha256sum "$DEST/$n" | cut -d' ' -f1)  $(stat -c %s "$DEST/$n")  $n  $s  $m"
  done
} > "$DEST/MANIFEST.txt"
chmod 600 "$DEST"/*
echo "snapshot written: $DEST ($(($(ls "$DEST" | wc -l) - 1)) files + MANIFEST.txt; union built_utc $BUILT; taken $NOW)"
cat "$DEST/MANIFEST.txt"
