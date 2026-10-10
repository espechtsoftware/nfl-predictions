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
CREATED=0
die() { echo "SNAPSHOT REFUSED: $*"; (( CREATED )) && echo "SNAPSHOT FAILED (partial, not usable): $*" > "$DEST/SNAPSHOT-FAILED.txt"; exit 1; }
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
# R2 (reviewer 10-06): pre-lock by content -- the union receipt's lock_utc; refuse at or after it
LOCK=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('lock_utc') or '')" "$UD/receipt.json")
[[ -n "$LOCK" ]] || die "the union receipt carries no lock_utc"
TAKEN=${S38_NOW:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}
python3 -c "import sys; from datetime import datetime as D; t=D.fromisoformat(sys.argv[1].replace('Z','+00:00')); l=D.fromisoformat(sys.argv[2].replace('Z','+00:00')); sys.exit(0 if t < l else 1)" "$TAKEN" "$LOCK" \
  || die "the snapshot time $TAKEN is at or after the lock $LOCK (pre-lock inputs only)"
PSRC=$(argval --proj-source); OSRC=$(argval --main-own-source); DSRC=$(argval --dk-status)
# study 38 amendment 6o (10-09; his W5 package: the 35% player cap + each skill player capped at FP's projected ownership
# + 15 points): a union with --main-own-cap-delta > 0 read --main-own-cap-source. The build refuses a package week whose
# own-cap file is not in the snapshot, so it is copied as named (sha in MANIFEST.txt); then no ownership file is generated
CDELTA=$(argval --main-own-cap-delta); CSRC=$(argval --main-own-cap-source)
if [[ -n "$CDELTA" && "$CDELTA" != 0 && "$CDELTA" != 0.0 ]]; then
  [[ -n "$CSRC" && -s "$CSRC" ]] || die "the union args name --main-own-cap-delta $CDELTA but the own-cap file '$CSRC' is missing"
fi
[[ -z "$CSRC" || -s "$CSRC" ]] || die "the union args name --main-own-cap-source '$CSRC', which is missing or empty"
if [[ -n "$CSRC" && -n "$OSRC" && "$(basename "$CSRC")" == "$(basename "$OSRC")" ]] && ! cmp -s "$CSRC" "$OSRC"; then
  die "--main-own-cap-source and --main-own-source share the name $(basename "$CSRC") but differ in content"
fi
# study 38 amendment 6 (10-07): a union with the prior-top term block read --term-block-source; the build refuses a week
# whose union read a term file the snapshot lacks, so it is copied with its sha in MANIFEST.txt
TROWS=$(argval --term-block-rows); TSRC=$(argval --term-block-source)
if [[ -n "$TROWS" && "$TROWS" != 0 ]]; then
  [[ -n "$TSRC" && -s "$TSRC" ]] || die "the union args name --term-block-rows $TROWS but the term file '$TSRC' is missing"
fi
# study 38 amendment 6b (10-07; the operator chose the prior-top block on PAPER): the week's paper term file, named by
# S38_PAPER_TERM_FILE (W5: reports/2026-10-07-prior-top-term/priortop-w5.csv), copied as paper-term-<basename>
PAPER=${S38_PAPER_TERM_FILE:-}
[[ -z "$PAPER" || -s "$PAPER" ]] || die "S38_PAPER_TERM_FILE '$PAPER' is missing or empty"
# study 38 amendment 6c (10-07; the operator: the FP-means DvP arm on paper): scripts/paper_dvp_file.py's week file
PDVP=${S38_PAPER_DVP_FILE:-}
[[ -z "$PDVP" || -s "$PDVP" ]] || die "S38_PAPER_DVP_FILE '$PDVP' is missing or empty"
# study 38 amendment 6d (10-07; the operator: "schedule any necessary experiments this week"): scripts/paper_factor_file.py's week file
PFAC=${S38_PAPER_FACTOR_FILE:-}
[[ -z "$PFAC" || -s "$PFAC" ]] || die "S38_PAPER_FACTOR_FILE '$PFAC' is missing or empty"
# S38_PAPER_MBLOCK_FILE (study 38 amendment 6i, 10-07: with the CHEAP block live, the 8-row MATCHUP block on paper as
# MIXT_QA0_MBLOCK8; W5: reports/2026-10-08-live-block/matchup-w5.csv), copied as paper-mblock-<basename>
PMB=${S38_PAPER_MBLOCK_FILE:-}
[[ -z "$PMB" || -s "$PMB" ]] || die "S38_PAPER_MBLOCK_FILE '$PMB' is missing or empty"
# S38_PAPER_HOT_FILE (study 38 amendment 6y, 10-10: MIXT_QA0_HOT1 on paper; the operator, relaying the researcher: "a HOT1
# paper arm in study 38 would let Week 5's real results arbitrate"; written by reports/2026-10-10-paper-hot/paper_hot_flags.py
# as ~/private/paper-corun/hot/wNN.csv), copied as paper-hot-<basename>
PHOT=${S38_PAPER_HOT_FILE:-}
[[ -z "$PHOT" || -s "$PHOT" ]] || die "S38_PAPER_HOT_FILE '$PHOT' is missing or empty"
# S38_RB_REC_FILE (study 116's RB receptions floor, 10-10: the live union's --mix-rb-rec-source when the floor is armed;
# written by reports/2026-10-10-rb-receptions/rb_rec_file.py as ~/private/paper-corun/rbrec/wNN.csv), copied as rb-rec-<basename>
PREC=${S38_RB_REC_FILE:-}
[[ -z "$PREC" || -s "$PREC" ]] || die "S38_RB_REC_FILE '$PREC' is missing or empty"
[[ -n "$PSRC" ]] || die "the union args name no --proj-source (FP projections fell back?): no FP week for study 38"
cmp -s "$PSRC" "$OUT/proj_fp-$TAG.csv" || die "--proj-source $PSRC differs from $OUT/proj_fp-$TAG.csv"
if [[ -n "$OSRC" ]]; then
  case "$(basename "$OSRC")" in ownership_fp-*) ;; *) echo "NOTE: the term's source is $(basename "$OSRC"), not FP ownership (a fallback); copied as named";; esac
elif [[ -n "$CSRC" ]]; then
  echo "NOTE: no --main-own-source, but the union read the own-cap file $(basename "$CSRC") (amendment 6o): copied as named; no ownership file generated"
else
  echo "NOTE: no --main-own-source in the union args (a no-term week): generating ownership_fp-$TAG.csv at snapshot time"
  : "${SEASON:?}" "${WEEK:?}" "${PROD:?}" "${PROD_PY:?}"; [[ -s "$OUT/ownership_lag.csv" ]] || die "no $OUT/ownership_lag.csv for the export"
fi
mkdir -p "$DEST" && chmod 700 "$DEST" || die "cannot create $DEST"
CREATED=1
cp -p "$UD/frame.parquet" "$DEST/frame.parquet" || die "copy failed: frame.parquet"
cp -p "$PSRC" "$DEST/proj_fp-$TAG.csv" || die "copy failed: proj_fp-$TAG.csv"
cp -p "$OUT/proj_fp-$TAG.csv.json" "$DEST/proj_fp-$TAG.csv.json" || die "copy failed: proj_fp-$TAG.csv.json"
if [[ -n "$OSRC" ]]; then
  cp -p "$OSRC" "$DEST/$(basename "$OSRC")" || die "copy failed: $(basename "$OSRC")"
elif [[ -z "$CSRC" ]]; then
  NOWS=$TAKEN; OGEN="$DEST/ownership_fp-$TAG.csv"
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
if [[ -n "$CSRC" ]]; then cp -p "$CSRC" "$DEST/$(basename "$CSRC")" || die "copy failed: $(basename "$CSRC")"; fi   # amendment 6o
if [[ -n "$TROWS" && "$TROWS" != 0 ]]; then cp -p "$TSRC" "$DEST/$(basename "$TSRC")" || die "copy failed: $(basename "$TSRC")"; fi
if [[ -n "$PAPER" ]]; then cp -p "$PAPER" "$DEST/paper-term-$(basename "$PAPER")" || die "copy failed: paper-term-$(basename "$PAPER")"; fi
if [[ -n "$PDVP" ]]; then cp -p "$PDVP" "$DEST/paper-dvp-$(basename "$PDVP")" || die "copy failed: paper-dvp-$(basename "$PDVP")"; fi
if [[ -n "$PFAC" ]]; then cp -p "$PFAC" "$DEST/paper-factor-$(basename "$PFAC")" || die "copy failed: paper-factor-$(basename "$PFAC")"; fi
if [[ -n "$PMB" ]]; then cp -p "$PMB" "$DEST/paper-mblock-$(basename "$PMB")" || die "copy failed: paper-mblock-$(basename "$PMB")"; fi
if [[ -n "$PHOT" ]]; then cp -p "$PHOT" "$DEST/paper-hot-$(basename "$PHOT")" || die "copy failed: paper-hot-$(basename "$PHOT")"; fi
if [[ -n "$PREC" ]]; then cp -p "$PREC" "$DEST/rb-rec-$(basename "$PREC")" || die "copy failed: rb-rec-$(basename "$PREC")"; fi
# production passes no --dk-status (OPEN-DEFECTS O-16): then NO dk-status file is copied and the build must use none
if [[ -n "$DSRC" ]]; then cp -p "$DSRC" "$DEST/$(basename "$DSRC")" || die "copy failed: $(basename "$DSRC")"; fi
cp -p "$ARGS" "$DEST/union-args-$TAG.txt" || die "copy failed: union-args-$TAG.txt"   # ONE union-args file (never also union_args.txt)
cp -p "$OUT/contests.json" "$DEST/contests.json" || die "copy failed: contests.json"
cp -p "$DETAILS" "$DEST/contest-details.json" || die "copy failed: contest-details.json"
if [[ "$OVR" == "-" ]]; then printf '{}\n' > "$DEST/plan-overrides.json" || die "write failed: plan-overrides.json"; else cp -p "$OVR" "$DEST/plan-overrides.json" || die "copy failed: plan-overrides.json"; fi
# R2(b): the union receipt, so the build verifies the snapshot was taken before lock_utc by content
cp -p "$UD/receipt.json" "$DEST/union-receipt.json" || die "copy failed: union-receipt.json"
BUILT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('built_utc'))" "$UD/receipt.json")
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
OVR_SRC=$OVR; [[ "$OVR" == "-" ]] && OVR_SRC="(written: {})"
{
  echo "# study 38 snapshot: union $UD (built_utc $BUILT; lock_utc $LOCK), OUT $OUT, RUN_TAG $TAG; taken $TAKEN"
  echo "# sha256  bytes  name  source  source_mtime_utc"
  declare -A SRC=([frame.parquet]="$UD/frame.parquet" ["proj_fp-$TAG.csv"]="$PSRC" ["proj_fp-$TAG.csv.json"]="$OUT/proj_fp-$TAG.csv.json"
                  ["union-args-$TAG.txt"]="$ARGS" [contests.json]="$OUT/contests.json"
                  [contest-details.json]="$DETAILS" [plan-overrides.json]="$OVR_SRC" [union-receipt.json]="$UD/receipt.json")
  [[ -n "$DSRC" ]] && SRC["$(basename "$DSRC")"]="$DSRC"
  [[ -n "$TROWS" && "$TROWS" != 0 ]] && SRC["$(basename "$TSRC")"]="$TSRC"
  [[ -n "$PAPER" ]] && SRC["paper-term-$(basename "$PAPER")"]="$PAPER"
  [[ -n "$PDVP" ]] && SRC["paper-dvp-$(basename "$PDVP")"]="$PDVP"
  [[ -n "$PFAC" ]] && SRC["paper-factor-$(basename "$PFAC")"]="$PFAC"
  [[ -n "$PMB" ]] && SRC["paper-mblock-$(basename "$PMB")"]="$PMB"
  [[ -n "$PHOT" ]] && SRC["paper-hot-$(basename "$PHOT")"]="$PHOT"
  [[ -n "$PREC" ]] && SRC["rb-rec-$(basename "$PREC")"]="$PREC"
  if [[ -n "$OSRC" ]]; then SRC["$(basename "$OSRC")"]="$OSRC"; elif [[ -z "$CSRC" ]]; then SRC["ownership_fp-$TAG.csv"]="${OSRC_LABEL:-}"; SRC["ownership_fp-$TAG.csv.receipt.json"]="(written by ownership_fp.py with the export)"; fi
  [[ -n "$CSRC" ]] && SRC["$(basename "$CSRC")"]="$CSRC"
  for n in $(ls "$DEST" | sort); do
    [[ "$n" == .* ]] && continue
    [[ "$n" == MANIFEST.txt ]] && continue
    s=${SRC[$n]:-?}; m=$( [[ -e "$s" ]] && date -u -r "$s" +%Y-%m-%dT%H:%M:%SZ || echo - )
    echo "$(sha256sum "$DEST/$n" | cut -d' ' -f1)  $(stat -c %s "$DEST/$n")  $n  $s  $m"
  done
} > "$DEST/MANIFEST.txt"
chmod 600 "$DEST"/*
echo "snapshot written: $DEST ($(($(ls "$DEST" | wc -l) - 1)) files + MANIFEST.txt; union built_utc $BUILT; taken $TAKEN; lock $LOCK)"
cat "$DEST/MANIFEST.txt"
