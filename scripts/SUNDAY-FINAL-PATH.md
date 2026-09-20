# The reviewed Sunday final path, as tracked source (layout of the Week-3 operational wiring branch)

Order of operations (Week-2 Sunday, reviewed by the lab on `lab/workstation-reply-bank991-20260918`):

1. `qb_flags.py` + `qb_classify.py` (ID-keyed QB classifier; BigQuery read-only)
2. `vet_book.py` v2.1 (tiers: HARD = DK O/IR, report Out, gated backup QB, placeholder salary, VANISHED; material = risk >= 1.0)
3. `vet_replace_v4.py` v4.2 (fresh DK status; whole-slate exclusion set; replacements from the run's own pool;
   `--admit-risky`; roster validation through `nfl2.validator` of the pinned clone, `--lab-src "$CLONE/src"`;
   rehearsal flags `--test-exclude-dk` / `--no-fresh-dk` mark the output NOT-PUBLISHABLE and never reach the chain)
4. emit + atomic ENTER layout + `verify_enter_bundle.py` (`sunday_after_build.sh`, `ENTER_LAYOUT=sequential`)
5. `promote_first.py` v1.2 + `first_delivered_promotion.py` (frozen MEAN first-entry rule, sha256 36ffcbce...) via
   `run_promotion.sh` v2.1, then `relayout_enter.sh` v2 (chain layout vendored verbatim; atomic bundle swap)
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

In-tool defaults still pointing at this workstation (env-overridable; pass explicitly from any other host):
`run_promotion.sh` (`PROD`, `TOOLS`, `PY`), `make_page.sh`, `gen_sheet.py`.

## Bounded rehearsal (outcome-blind, real artifacts, scratch OUT dir, synthetic entries template, no DK keys)

    export PROD=<this checkout> CLONE=<pinned lab clone> EXPECT_SHA=<its sha>
    scripts/rehearse_final_path.sh <archived RUN_DIR> <LAB_CLONE> <scratch OUT_DIR> <WEEK> <contests.json>

Runs the chain in once-mode into the scratch OUT (fresh DK status consulted, read-only), the promotion, and the fill of a
synthetic template (`make_synthetic_entries_template.py`, fake 9xxxxxxxxx entry ids). Verified 2026-09-20 20:50Z on
this branch with the archived D12800 run `20260919T153008787414Z-2dc116c` and the Week-2 contests.json: 97 rows, 12
contests, promotion rank 7 -> 1, bundle verified, synthetic template filled 97/97; the live ENTER and Downloads untouched.
