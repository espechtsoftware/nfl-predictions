#!/usr/bin/env bash
# Test lanes, so a full 7,700-test / ~77-minute suite is not the only option.
#
#   ./scripts/test_lanes.sh money      live Week-1 path only -- must be green
#   ./scripts/test_lanes.sh changed    tests for files you changed vs origin/main
#   ./scripts/test_lanes.sh full       everything, failures classified
#   ./scripts/test_lanes.sh quarantine show what is quarantined and why
#
# The quarantine NEVER hides a failure silently.  Quarantined modules still run
# in the `full` lane; their failures are reported under a KNOWN heading and
# anything else is reported as NEW.  A quarantine entry that stops failing is
# reported too, because that means it can be released.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

# --- quarantine ------------------------------------------------------------
# module<TAB>reason.  Keep the reason specific and dated; a bare module name
# here is how a real regression gets lost.
QUARANTINE_TSV=$(cat <<'TSV'
test_corpus_extreme_tail_factorial_manifest.py	2026-09-11 frozen-chain policy drift: 11 env keys moved since c876e7f2 (N_BOOM 40->160 + 9 new levers). See reports/2026-09-11-frozen-factorial-policy-drift.md -- protocol decision, not a code fix.
test_corpus_extreme_tail_generation_additions.py	2026-09-11 same frozen-chain drift as the factorial manifest.
test_corpus_extreme_tail_generation_companion_manifest.py	2026-09-11 same frozen-chain drift as the factorial manifest.
test_corpus_expansion_build.py	2026-09-11 same frozen-chain drift as the factorial manifest.
TSV
)

quarantined_modules() { printf '%s\n' "$QUARANTINE_TSV" | cut -f1; }

show_quarantine() {
  echo "QUARANTINED (still executed in the full lane; failures reported as KNOWN)"
  echo
  printf '%s\n' "$QUARANTINE_TSV" | while IFS=$'\t' read -r mod reason; do
    [ -n "$mod" ] || continue
    printf '  %s\n      %s\n\n' "$mod" "$reason"
  done
}

# --- lanes -----------------------------------------------------------------
# The live Week-1 path: construction, scoring, policy, ingest, serving.
# Deliberately NOT the frozen research chains -- those are the slow third of
# the suite and none of them gate the season.
MONEY_TESTS=(
  tests/test_production_policy.py
  tests/test_optimizer.py
  tests/test_optimizer_policy_isolation.py
  tests/test_scoring.py
  tests/test_dk_client.py
  tests/test_dk_standings_capture.py
  tests/test_dk_paid_freshness_scheduler_contract.py
  tests/test_feature_sql.py
  tests/test_app.py
)

changed_tests() {
  local base="${BASE:-origin/main}"
  git diff --name-only "$base"...HEAD 2>/dev/null
  git diff --name-only 2>/dev/null
  git ls-files --others --exclude-standard 2>/dev/null
}

case "${1:-money}" in
  quarantine)
    show_quarantine
    ;;

  money)
    echo "MONEY LANE -- live Week-1 path"
    existing=()
    for t in "${MONEY_TESTS[@]}"; do [ -f "$t" ] && existing+=("$t"); done
    $PY -m pytest "${existing[@]}" -p no:cacheprovider -rf --tb=short
    ;;

  changed)
    # Map each changed source file to a test module of the same stem.
    mapfile -t changed < <(changed_tests | sort -u)
    targets=()
    for f in "${changed[@]}"; do
      case "$f" in
        tests/test_*.py) [ -f "$f" ] && targets+=("$f") ;;
        src/nfl_dfs/*.py|scripts/*.py)
          stem=$(basename "$f" .py)
          for cand in "tests/test_${stem}.py" "tests/test_run_${stem}.py" \
                      "tests/test_cloud_${stem}.py"; do
            [ -f "$cand" ] && targets+=("$cand")
          done ;;
      esac
    done
    if [ ${#targets[@]} -eq 0 ]; then
      echo "no test modules map to the changed files; run the money lane"
      exit 0
    fi
    mapfile -t targets < <(printf '%s\n' "${targets[@]}" | sort -u)
    echo "CHANGED LANE -- ${#targets[@]} module(s)"
    printf '  %s\n' "${targets[@]}"
    $PY -m pytest "${targets[@]}" -p no:cacheprovider -rf --tb=short
    ;;

  full)
    echo "FULL LANE -- everything (~77 min).  Quarantine is classified, not hidden."
    log=$(mktemp)
    $PY -m pytest -p no:cacheprovider -rf --tb=no | tee "$log"
    echo
    echo "==================== CLASSIFICATION ===================="
    grep '^FAILED' "$log" | sed 's/^FAILED //; s/ - .*//' > "$log.f" || true
    quarantined_modules > "$log.q"
    known=0 new=0
    while read -r line; do
      [ -n "$line" ] || continue
      mod=$(basename "${line%%::*}")
      if grep -qxF "$mod" "$log.q"; then known=$((known+1)); else
        new=$((new+1)); echo "NEW FAILURE: $line"
      fi
    done < "$log.f"
    echo
    echo "known-quarantined failures : $known"
    echo "NEW failures               : $new"
    # A quarantine entry that no longer fails should be released.
    while read -r mod; do
      [ -n "$mod" ] || continue
      grep -q "$mod" "$log.f" || echo "RELEASE CANDIDATE (no longer failing): $mod"
    done < "$log.q"
    [ "$new" -eq 0 ]
    ;;

  *)
    echo "usage: $0 {money|changed|full|quarantine}" >&2
    exit 2
    ;;
esac
