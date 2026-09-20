# The reviewed Sunday final path, as tracked source (layout of the Week-3 operational wiring branch)

Order of operations (Week-2 Sunday, reviewed by the lab on `lab/workstation-reply-bank991-20260918`):

1. `qb_flags.py` + `qb_classify.py` (ID-keyed QB classifier; BigQuery read-only)
2. `vet_book.py` v2.1 (tiers: HARD = DK O/IR, report Out, gated backup QB, placeholder salary, VANISHED; material = risk >= 1.0)
3. `vet_replace_v4.py` v4.2 (fresh DK status; whole-slate exclusion set; replacements from the run's own pool;
   `--admit-risky`; roster validation through `nfl2.validator` of the pinned clone, `--lab-src "$CLONE/src"`;
   rehearsal flags `--test-exclude-dk` / `--no-fresh-dk` mark the output NOT-PUBLISHABLE and never reach the chain)
4. emit + atomic ENTER layout + `verify_enter_bundle.py` (`sunday_after_build.sh`, `ENTER_LAYOUT=sequential`)
5. `promote_first.py` v1.2 + `first_delivered_promotion.py` (frozen MEAN first-entry rule, sha256 36ffcbce...) via
   `run_promotion.sh` v2.2 (all paths environment-driven), then `relayout_enter.sh` v2 (chain layout vendored verbatim;
   atomic bundle swap). The chain runs this step itself when `PROMOTE_FIRST_ENTRY=1` is exported (the operator's weekly
   class-E decision; default off): after replacement and before the chain publishes a new ENTER bundle, so the entries
   watcher only sees the promoted bundle. A failure leaves the previous bundle in place and records the failure.
6. fill: `fill_dk_entries.py` on the newest DK entries export (`sunday_watch_dk_entries.sh` until its loop ends; then by hand)
7. late swaps: `apply_swaps.py` v1.1 (fresh-feed presence check, locked-game refusal, receipt) + `relayout_enter.sh` + fill
8. page/sheet/archive: `make_page.sh`, `gen_sheet.py`, `book_sheet.py`, `swap_suggest.py`, `manifest_and_gap.py`, `qb_flags.sh`

The four vetting tools (`qb_classify.py`, `qb_flags.py`, `vet_book.py`, `vet_replace_v4.py`) are byte-identical to the
reviewed versions (4c4ae415..., 7796cc5a..., a3c8aede..., 914e5da8...); `book_sheet.py` on this branch is the laptop's
adapted copy (retired Week-1 directory dependency removed) and is what `run_promotion.sh` now calls. Hashes of the
promotion-side tools: `SUNDAY-FINAL-PATH-SHA256SUMS`.

## Environment (`scripts/week_env.sh`: `week_settings` then `week_env WEEK [GROUP]`; export overrides first)

`PROD` (this checkout), `PROD_PY`, `LAB_PY`, `TOOLS` (default `$PROD/scripts`), `CLONE` + `EXPECT_SHA` (the pinned lab
release for the week; the defaults are placeholders, export the real pin in every unit), `OUT`, `CONTESTS_JSON`
(`$OUT/contests.json`, ordered by top payout; `BOOK_ENTRIES` derived), `ENTER_LAYOUT=sequential`, `GROUP`,
`LIVE_DIR=$CLONE/results/live/<season>-w<WW>`, `CHOSEN_FILE=$OUT/chosen-dose.env` (`CHOSEN_LEV`, `CHOSEN_BOOM`; the poll
path fails closed without it), `LOCK_UTC`, `LATE_CUTOFF_UTC`, `WATCH_END_UTC`. Refresh jobs (operator, Saturday after the
09:30 CT props pull, and Sunday morning): `build-features`, `tabpfn-gen` (`TABPFN_UPCOMING=<season>:<week>`),
`project-slate`; the newest project-slate must log "market blend source: props".

The tracked helpers derive their paths from this checkout. A live unit should still export the real `PROD`, `PROD_PY`,
`LAB_PY`, `TOOLS`, clean pinned `CLONE`, full `EXPECT_SHA`, `OUT`, and `CONTESTS_JSON`; no unit should rely on a deleted
week-specific worktree.

## Bounded rehearsal (outcome-blind, real artifacts, scratch OUT dir, synthetic entries template, no DK keys)

    export PROD=<this checkout> CLONE=<pinned lab clone> EXPECT_SHA=<its sha>
    scripts/rehearse_final_path.sh <archived RUN_DIR> <LAB_CLONE> <scratch OUT_DIR> <WEEK> <contests.json>

The rehearsal sets `PROMOTE_FIRST_ENTRY=1` for the chain call, so the hook is exercised without touching the live
`ENTER/` or Downloads directories.

Runs the chain in once-mode into the scratch OUT (fresh DK status consulted, read-only), the promotion, and the fill of a
synthetic template (`make_synthetic_entries_template.py`, fake 9xxxxxxxxx entry ids). Verified 2026-09-20 21:01Z on
this branch (promotion through the chain hook) with the archived D12800 run `20260919T153008787414Z-2dc116c` and the Week-2 contests.json: 97 rows, 12
contests, promotion rank 7 -> 1, bundle verified, synthetic template filled 97/97; the live ENTER and Downloads untouched.

Week-3 shadow (laptop hook `RUN_WEEK3_SHADOW=1` in `sunday_build_host.sh` -> `run_week3_shadow.sh` -> `scripts/week3_shadow_runner.py`,
which also accepts `--expect-sha` to pin the clone identity into its manifest): see `reports/2026-09-20-week3-selection-shadow-prospectus.md`.
