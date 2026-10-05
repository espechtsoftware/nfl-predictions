#!/usr/bin/env bash
# O-32 correction re-run (reports/2026-10-05-o32-correction-protocol.md, amendment 1): ONE study, TWO local legs from
# the checked-out commit -- game_day_active OFF (must reproduce the original Cloud Run disposition) and ON (the
# correction) -- plus the environment record. Run one study at a time, never in a build window, never while another
# heavy local job runs.
#
#   GCP_PROJECT=nfl-predictions-503414 scripts/o32_correction_run.sh defense-proe
set -uo pipefail
STUDY=${1:?usage: o32_correction_run.sh STUDY (defense-proe|qb-shell|market-tail|ngs-receiver|pass-participation|market-movement)}
: "${GCP_PROJECT:?set GCP_PROJECT (O-31)}"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-$HOME/projects/nfl-predictions/.venv/bin/python}
case "$STUDY" in
  defense-proe)       CMD=(-m nfl_dfs.cli fantasy-points-defense-proe-diagnostic); MOD=fantasy_points_defense_proe ;;
  qb-shell)           CMD=(-m nfl_dfs.cli fantasy-points-qb-shell-diagnostic);     MOD=fantasy_points_qb_shell ;;
  market-tail)        CMD=(-m nfl_dfs.cli market-tail-diagnostic);                 MOD=market_tail_disagreement ;;
  ngs-receiver)       CMD=(-m nfl_dfs.cli ngs-receiver-tail-diagnostic);           MOD=ngs_receiver_tail ;;
  pass-participation) CMD=(-m nfl_dfs.cli pass-participation-proxy);               MOD=pass_participation ;;
  market-movement)    CMD=("$ROOT/scripts/market_movement_eval.py");               MOD="" ;;
  *) echo "unknown study $STUDY" >&2; exit 2 ;;
esac
[[ -z "$(git -C "$ROOT" status --porcelain -- src scripts)" ]] || { echo "refusing: src/ or scripts/ has uncommitted changes" >&2; exit 2; }
OUT="$ROOT/reports/o32-correction-runs/$STUDY"
[[ ! -e "$OUT/corrected.txt" ]] || { echo "refusing: $OUT/corrected.txt already exists (one correction per study)" >&2; exit 2; }
mkdir -p "$OUT"
{
  echo "study $STUDY"; echo "commit $(git -C "$ROOT" rev-parse HEAD)"; echo "started_utc $(date -u +%FT%TZ)"
  echo "host $(hostname)"; echo "python $("$PY" -c 'import sys; print(sys.version.split()[0])')"
  [[ -n "$MOD" ]] && echo "panel $(cd "$ROOT" && PYTHONPATH="$ROOT/src" "$PY" -c "import nfl_dfs.analysis.$MOD as m; print(m.PANEL_ID)")"
  "$PY" -m pip freeze 2>/dev/null | grep -i -E '^(pandas|numpy|scikit-learn|scipy|lightgbm|xgboost|google-cloud-bigquery|nflreadpy|polars)==' 
} > "$OUT/environment.txt"
for leg in uncorrected corrected; do
  flag=(); [[ $leg == corrected ]] && flag=(--game-day-active)
  echo "== $STUDY: $leg leg"
  ( cd "$ROOT" && PYTHONPATH="$ROOT/src" nice "$PY" "${CMD[@]}" "${flag[@]}" ) > "$OUT/$leg.txt" 2> "$OUT/$leg.stderr" \
    || { echo "LEG FAILED ($leg): see $OUT/$leg.stderr" >&2; exit 1; }
  grep -o '"disposition": *"[^"]*"' "$OUT/$leg.txt" | head -1 || true
done
echo "finished_utc $(date -u +%FT%TZ)" >> "$OUT/environment.txt"
