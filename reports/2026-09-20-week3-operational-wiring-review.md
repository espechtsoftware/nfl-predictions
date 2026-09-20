# Week 3 operational wiring review

This review answers the practical question of what still has to be wired before the next Sunday build. It is on the
operational branch `fix/week3-operational-wiring-20260920` (the pushed tip is the review identity); it does not alter the current entered book,
arm timers, or execute cloud jobs.

## Findings

The tracked Week 2 generalisation still depended on machine-local state:

- `week_env.sh` defaulted to a deleted live-center worktree, a deleted production worktree, and
  `/home/erich/week1-sunday/tools`.
- `arm_week_timers.sh` invoked deleted `/home/erich/week<W>-sunday-build.sh` and watcher wrappers, tagged every run as
  the old `e7255e9`, and hard-coded `TABPFN_UPCOMING=2026:2`.
- `sunday_build_host.sh` pointed ordering shadows at another deleted live-center path.
- The current QB-aware vetting/replacement helpers used by the reviewed Sunday path existed in the handoff/tool bundle,
  not in the production checkout.
- The 09:12 watcher command launched detached children and systemd killed their cgroup before the first log line. The
  build itself was unaffected only because the operator relaunched the chain manually.
- The post-build watcher could process every dose when `chosen-dose.env` was absent, which could overwrite `ENTER/` with
  an unintended fallback book.

## Changes in this branch

- Added `run_week_build.sh` and `run_week_watchers.sh` as tracked timer entrypoints. The watcher supervisor owns and
  waits for the after-build, DraftKings-entry, and late-inactives processes; it writes a heartbeat and child logs.
- Reworked `arm_week_timers.sh` to use repository-relative entrypoints, pass explicit paths and identities, derive the
  week in the refresh command, and produce Week 3 dates/tags without hard-coded Week 2 values.
- Split `week_env.sh` into a provider-free `week_settings` phase and the BigQuery-backed `week_env` phase. Dates are
  DST-aware, `BOOK_ENTRIES` is derived from the contest layout, and the clean Week 3 live checkout defaults to
  `/home/erich/projects/.nfl2-worktrees/week3-live-center` at `e7255e98bf87297452befb61fb508ad4b368b59f`, with explicit
  overrides supported.
- Added `check_week_runtime.py`, which fails closed on a missing contest file, unresolved template marker, invalid
  identity, dirty or mismatched live clone, dirty production checkout, missing tool, insufficient book size, or absent
  chosen dose. Added `check_week_watchers.sh` for the one-minute heartbeat/log check.
- Promoted the reviewed QB/status helpers into the tracked tools directory. Their hashes are:
  `qb_classify.py` `4c4ae415…`, `qb_flags.py` `7796cc5a…`, `vet_book.py` `a3c8aede…`, and
  `vet_replace_v4.py` `914e5da8…`. The generic `player_score.py`, `book_sheet.py`, `ordering_shadows.py`, and
  `hybrid30.py` helpers are tracked as well; ordering shadows now resolve the novelty planner from `CLONE/NFL2_ROOT`.
- The polling after-build path now fails closed unless `$OUT/chosen-dose.env` contains `CHOSEN_LEV` and
  `CHOSEN_BOOM`. An explicit `REQUIRE_CHOSEN_DOSE=0` is available only for a deliberate rehearsal.

## Still required before arming Week 3

These are operator/data decisions and cannot be guessed by the scripts:

1. Create the week's real `$OUT/contests.json` from the reservations and set the chosen dose after a completed receipt.
   The template markers are intentionally rejected.
2. Complete the Wednesday paid-data cadence: verify both Fantasy Points and SIS sessions, capture the Week 3 eligible
   Fantasy Points live reports/Route Share inputs, and preserve the manifest/artifact hashes. SIS pass-tail and
   alignment remain governed by their separately documented eligibility boundary; they must not be silently treated as
   one combined source.
3. After the props pull, run the three refresh jobs in the generated timer output for `2026:3`, then inspect the next
   build receipt for the correct production projection and cutoff identities.
4. Run `python scripts/check_prospective_gates.py` against the current in-season policy. Route Share's Week 3 gate and
   the SIS registry/documentation defects remain open in `reports/OPEN-DEFECTS.md`.
5. The final-book first-entry promotion (the reviewed operator-authorized MEAN rule and atomic ENTER re-layout) is still
   a separate handoff tool in the current checkout. It must be reconciled into the same tracked production path before
   relying on the first row for the Millionaire; this review does not silently auto-promote a row.
6. Before arming, run `scripts/arm_week_timers.sh 3` and inspect every printed command. Only then use `--run`. During
   Sunday, run `OUT=/home/erich/week3-sunday scripts/check_week_watchers.sh` periodically; an old heartbeat is a stop
   condition, not a reason to continue entering.

## Validation

The branch passes Bash syntax checks, Python compilation, Week 3 date/DST derivation, a synthetic build preflight, and a
synthetic watcher preflight. The watcher preflight correctly rejects a missing chosen-dose file. No provider call,
current-week outcome, cloud execution, timer arm, upload, or production `main` mutation occurred.
