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
PY=${PY:-.venv/bin/python}
# A git worktree has no .venv of its own, so this resolved to nothing and the
# lane died with a bare "No such file or directory".  Fail closed and say how to
# fix it -- never silently fall back to a system interpreter, which would run the
# suite against different numpy/CPython than the one the tree was installed into.
if [ ! -x "$PY" ]; then
  echo "test_lanes: no interpreter at '$PY'" >&2
  echo "  a git worktree has no .venv; point PY at the checkout that does, e.g." >&2
  echo "  PY=/home/erich/projects/nfl-predictions/.venv/bin/python $0 $*" >&2
  exit 2
fi

# --- quarantine ------------------------------------------------------------
# module<TAB>reason.  Keep the reason specific and dated; a bare module name
# here is how a real regression gets lost.
QUARANTINE_TSV=$(cat <<'TSV'
test_corpus_extreme_tail_factorial_manifest.py	2026-09-12 numerical runtime identity: corpus_retrieval_v2_implementation_contract pins /usr/bin/python3.14 as of 3.14.4-1ubuntu0.1 (sha b8d8288f...); apt moved it to 1ubuntu0.2 on 2026-09-09. The P0 policy drift (2026-09-11) is FIXED (pinned literal). Passes under the pinned binary: dpkg-deb -x /var/cache/apt/archives/python3.14-minimal_3.14.4-1ubuntu0.1_amd64.deb and run that python3.14 with PYTHONPATH=src:.venv site-packages. Operator decision: hold the package or re-freeze the contract.
test_corpus_extreme_tail_generation_companion_manifest.py	2026-09-12 same runtime-identity cause as the factorial manifest (it validates the same v2 contract).
test_corpus_retrieval_v2_implementation_contract.py	2026-09-12 same runtime-identity cause; this is the module that pins the interpreter binary.
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
  tests/test_dk_upload_csv_v1.py
  # load_dataframe writes player_projections and market_source_log, so the lane
  # that must be green was not covering the warehouse writer the rest of it
  # depends on. Added 2026-09-21 after its three tests sat silently disabled
  # from 2026-09-20 -- an autouse guard stubbed the very function they test, the
  # full suite has not completed since 2026-09-15, and this lane did not run them.
  tests/test_bq_load.py
  # exposure_cap_book.py runs inside sunday_build_host.sh and emits the sheet the
  # operator reads before upload, so its guarantees belong in the lane that must be
  # green on Sunday. Added 2026-09-22.
  tests/test_exposure_cap_book.py
  tests/test_ownership_slot_reconciliation.py
  # The Week-3 blocker watch guards the Saturday prop landing, the tightest window
  # of the week. Its read-only property is what makes it safe to arm on a timer.
  tests/test_week3_blocker_watch_is_read_only.py
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
    # -rfE, not -rf: pytest reports errors separately from failures, and a
    # lane that can only see failures reports success when a fixture breaks.
    $PY -m pytest -p no:cacheprovider -rfE --tb=no | tee "$log"
    echo
    echo "==================== CLASSIFICATION ===================="
    grep -E '^(FAILED|ERROR)' "$log" \
      | sed -E 's/^(FAILED|ERROR) //; s/ - .*//' > "$log.f" || true
    quarantined_modules > "$log.q"
    known=0 new=0
    while read -r line; do
      [ -n "$line" ] || continue
      mod=$(basename "${line%%::*}")
      if grep -qxF "$mod" "$log.q"; then known=$((known+1)); else
        new=$((new+1)); echo "NEW: $line"
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
