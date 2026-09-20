# The reviewed Sunday final path, as tracked source

Vendored 2026-09-20 from the workstation, byte-identical to what ran on Week-2 Sunday (hashes in `SHA256SUMS`; the lab
reviewed these versions on `lab/workstation-reply-bank991-20260918` under `handoffs/tools/`). Order of operations:

1. `qb_flags.py` + `qb_classify.py` (ID-keyed QB classifier: primary / gated / out / ambiguous; BigQuery read-only)
2. `vet_book.py` v2.1 (tiers: HARD = DK O/IR, report Out, gated backup QB, placeholder salary, VANISHED; material = risk >= 1.0)
3. `vet_replace_v4.py` v4.2 (fresh DK status; whole-slate exclusion set; replaces confirmed-unavailable lineups from the
   run's own pool; `--admit-risky`; validates with `nfl2.validator.validate_roster`; rehearsal flags
   `--test-exclude-dk` / `--no-fresh-dk` mark the output NOT-PUBLISHABLE and must never reach the operational chain)
4. emit + atomic ENTER layout + `verify_enter_bundle.py` (chain: `scripts/sunday_after_build.sh`, `ENTER_LAYOUT=sequential`)
5. `promote_first.py` v1.2 + `first_delivered_promotion.py` (frozen MEAN first-entry rule, sha 36ffcbce...) via
   `run_promotion.sh` v2.1, then `relayout_enter.sh` v2 (chain layout vendored verbatim; atomic bundle swap)
6. fill: `scripts/fill_dk_entries.py` (same bytes as the tools copy) on the newest DK entries export; the watcher
   `scripts/sunday_watch_dk_entries.sh` does this until 16:58Z; after that, by hand
7. late swaps: `apply_swaps.py` v1.1 (fresh-feed presence check, locked-game refusal, receipt) + `relayout_enter.sh` + fill
8. page/sheet: `make_page.sh`, `gen_sheet.py`, `book_sheet.py`, `swap_suggest.py`; archive: `manifest_and_gap.py`

## Required environment (from `scripts/week_env.sh`; export overrides BEFORE calling `week_env W`)

`PROD` (this checkout), `PROD_PY` (production venv python), `LAB_PY`, `TOOLS` (this directory), `CLONE` and `EXPECT_SHA`
(the pinned lab release: Week 2 = `.nfl2-worktrees/week2-release-2dc116c`, 2dc116ce...; `week_env.sh` still DEFAULTS to
the Week-1 clone e7255e9, so both must be exported explicitly by every entrypoint), `OUT` (`/home/erich/week<W>-sunday`),
`CONTESTS_JSON` (`$OUT/contests.json`, ordered by top payout; `BOOK_ENTRIES` is derived from it), `ENTER_LAYOUT=sequential`,
`GROUP` (DK draft group), `LIVE_DIR=$CLONE/results/live/<season>-w<WW>`, the chosen dose file
`/home/erich/week<W>-chosen-dose.env` (`CHOSEN_LEV`, `CHOSEN_BOOM`; the chain's poll mode processes only runs at that
dose), `LOCK_UTC`, `LATE_CUTOFF_UTC`, `WATCH_END_UTC`. Refresh jobs (operator, Saturday ~09:45 CT after the 09:30 props
pull, and Sunday morning): `build-features`, `tabpfn-gen` (`TABPFN_UPCOMING=<season>:<week>`), `project-slate`; check the
newest project-slate logs "market blend source: props".

## Known defaults inside the vendored tools (env-overridable; do not rely on them from another host)

* `run_promotion.sh`: `PROD`, `TOOLS`, `PY` default to this workstation's paths; pass them explicitly.
* `vet_replace_v4.py --lab-src` defaults to the Week-2 clone; the chain on this branch now passes `--lab-src "$CLONE/src"`
  (change to `sunday_after_build.sh` in this branch's history; re-review before Sunday).
* `book_sheet.py`, `make_page.sh`, `gen_sheet.py`: Week-1/Week-2 default directories in their argument defaults.
* Transient systemd services do not inherit the shell; the watcher wrapper's `setsid nohup` children die with the service
  cgroup (2026-09-20 defect). Persistent-unit supervision is laptop-owned.

## Bounded rehearsal (outcome-blind, real artifacts, scratch OUT dir, synthetic entries template, no DK keys)

    export PROD=<this checkout> PROD_PY=/home/erich/projects/nfl-predictions/.venv/bin/python
    scripts/sunday/rehearse_final_path.sh <archived RUN_DIR> <LAB_CLONE> <scratch OUT_DIR> <WEEK> [contests.json]

Runs the chain in once-mode into the scratch OUT (fresh DK status is consulted, read-only), the promotion, and the fill of
a synthetic template (`make_synthetic_entries_template.py`: fake 9xxxxxxxxx entry ids). Verified 2026-09-20 on the
archived D12800 run `20260919T153008787414Z-2dc116c` with the Week-2 contests.json: 97 rows, 12 contests, promotion
rank 7 -> 1, bundle verified, synthetic template filled. The live `ENTER` and Downloads are never touched.
