# Transition code review — 2026-09-17

Review requested by Erich; **documentation only, no application fixes or policy changes**. Production base `879cbc63`; lab main `60b7109`; active live lab implementation `e7255e9`; bank991 frozen implementation `c06b2cd903a6de211c4d221b3ac56f710f715500`. Branch-specific files were inspected at those revisions rather than assuming lab main contains the active experiments.

The transition documentation is useful and the core pipeline has substantial validation. The generalized Sunday wrappers do not yet preserve all of that validation. **Address findings 1–5 before relying on unattended entry-file preparation; address 9–10 before interpreting bank991.** These are source-level findings, not evidence that an invalid entry has actually been uploaded.

Severity: P1 = action needed before the affected operation; P2 = correctness/reliability fix with a narrower trigger. The workstation agent owns deployment and first read. No bank990/991 scientific outputs were opened in this review.

## 1. P1 — entry watcher writes to Week 1 while copying from the current week

Locations: `scripts/sunday_watch_dk_entries.sh:17`; `scripts/fill_dk_entries.py:21`.

The watcher supplies `--enter-dir "$E"` but omits `--out-dir`. The filler independently defaults its output to `/home/erich/week1-sunday/ENTER`. The watcher then copies the current week's `$E/DKEntries-FILLED-keepers-first.csv`. In Week 2 this can fail to copy the newly generated file, or copy an older file if one exists there. Checking only the filler exit code misses the mistake.

Verified from the invocation and argparse defaults; synthetic evidence confirms the default. Fix: explicitly bind output to the current validated entry bundle, and make the default derive from the input directory. Regression: temporary Week-3 directories, an older sentinel output, and a synthetic template must produce and copy only the newly generated current-week file.

Deployment qualification: `$TOOLS/fill_dk_entries.py` is an external host copy. The workstation agent should compare its hash with this tracked source before concluding the defect is deployed; source and handoff alone cannot establish those bytes.

## 2. P1 — incomplete entry fills succeed and retain old lineups

Location: `scripts/fill_dk_entries.py:39–60`.

Missing configured contest files cause a summary message and `continue`. A count mismatch uses `min(entries, lineups)` and leaves remaining template lineups untouched. Both paths publish a normal-looking `DKEntries-FILLED-keepers-first.csv` and exit zero. The configured `entries` count is not enforced by the filler.

Reproduced with two synthetic entries and one candidate: exit 0, second entry's nine `OLD` cells unchanged. Fix: validate configured contest coverage, exact counts, nine legal cells per roster, uniqueness where required, and keep/withdraw accounting before publication. Any intentionally excluded contest needs an explicit exclusion, not implicit preservation disguised as a complete fill. Publish atomically only after validation. Test missing file, short book, malformed roster, and extra/missing template entry.

## 3. P1 — normal K90 route skips governed receipt checks

Locations: `scripts/arm_week_timers.sh:33–37`; `scripts/sunday_build_host.sh:31–45,63–84`; compare `scripts/sunday_runbook.sh:28,46–81`.

Every scheduled build uses `SKIP_PAIR=1`. The expected-SHA and receipt checks live in the skipped runbook. The direct K90 invocation's exit status is not required to succeed (`set -uo pipefail`, no explicit guard). Its directory finder accepts a receipt matching dose plus directory mtime after start-minus-60 seconds; it does not bind the result to this invocation, group, expected SHA, entry count or completed prelock receipt. Concurrent or recently reused same-dose directories can therefore satisfy the lookup after a failed build. `REUSE_K90_DIR` also reaches export with only receipt existence checked.

The live builder has its own checks; this finding is specifically the missing wrapper validation and invocation binding. Fix: capture the exact output directory from a successful invocation, then run the same authoritative verifier for K90 and reused runs. Negative smoke: child exits nonzero with another recent same-dose directory present; wrong group/SHA/lock must all stop export.

## 4. P1 — watcher records completion before processing, defeating retries and dose fallback

Locations: `scripts/sunday_after_build.sh:95–104`; `scripts/sunday_watch_dk_entries.sh:18`.

`after_build.seen` is appended before chosen-dose matching, receipt parsing, vetting or export. A transient failure is permanently skipped. A different-dose directory is also permanently skipped, so the documented fallback “edit chosen dose and restart” cannot recover that already-seen directory. The explicit `once` escape remains possible, but does not make the automated fallback correct. The entries watcher similarly advances `last` even when filling/copying fails, suppressing retries until the signature changes.

Fix: separate eligible/pending/failed/published state; mark success only after a validated bundle is published; make chosen-dose changes re-evaluate existing eligible runs. Retry must account for create-once output paths rather than colliding with the previous failed attempt. Tests: transient vet failure then recovery, dose switch after skip, copy failure then retry without input mutation.

## 5. P1 — entry bundle replacement exposes incomplete state to its concurrent consumer

Location: `scripts/sunday_after_build.sh:25–75`.

The producer deletes current `ENTER/*.csv` and writes contest files one at a time. The independently polling filler can see an incomplete bundle. Short books only print warnings; the Python layout command is not explicitly checked before later success messages. This combines with finding 2 to publish partial entries, and can remove the previous usable files before a replacement is ready.

Fix: stage a complete immutable bundle, verify counts and provenance, then switch a single current-bundle pointer atomically; consumer resolves one manifest/version once. Preserve the last valid bundle on failure. Test a deliberate failure halfway through producing the second contest and concurrent polling.

## 6. P2 — late-status watcher loses status transitions and later book changes

Location: `scripts/sunday_watch_late_inactives.py:16–34`.

Seen state is a set of player IDs whose status is any of O/OUT/IR/D. A player already marked D who changes to OUT is not a new ID and produces no new alert (synthetic set transition verified). Entered IDs and frame are read only at startup, so later chosen-book replacements are not tracked. The script exits on its first hard-status alert, leaving subsequent changes unwatched.

Fix: persist ID-to-status transitions, reload the committed entry manifest when its version changes, and keep monitoring until each applicable game's lock. This remains an alert mechanism; it must not automatically remove questionable/doubtful players contrary to the money-path rule. Test D→OUT, two different later changes, and a replaced entry bundle.

## 7. P2 — next-week and DST generalization is incomplete

Locations: `scripts/arm_week_timers.sh:27,30–41`; `scripts/week_env.sh:13–30`; watcher UTC loop bounds above.

The supposedly week-parameterized timer printer still tells the operator to run `TABPFN_UPCOMING=2026:2` for Week 3. Calendar dates are anchored to 2026 regardless of `SEASON`. UTC locks/end times remain September values across the November DST change, although timers themselves use America/Chicago. Repeated `week_env` calls in one shell retain exported GROUP/OUT/CONTESTS_JSON from the previous week unless reset.

Fix: one season/week configuration resolved from the actual slate schedule, timezone-aware game locks, and explicit persistent overrides separate from derived values. Outcome-free tests: Weeks 2, 3 and the DST boundary, another season, and two consecutive calls in one shell. No timers need to be armed for these tests.

## 8. P2 — latest prop selection retains obsolete moved lines

Location: `src/nfl_dfs/models/prop_market.py:108–114`, consumed by `market_points`.

The deduplication key includes `point`. When the main line moves from 49.5 to 59.5, both survive “latest” selection; downstream averaging can blend the obsolete and current lines. Selecting each outcome side separately can also join prices from different snapshots. Synthetic prelock Over/Under rows reproduced both retained thresholds.

Fix: define the latest complete market snapshot per event/player/book/market, then pair sides within that snapshot; explicitly distinguish alternate lines if supported. Test line movement, missing side at newest snapshot, alternate markets and different event identities. Do not just remove `point` without preserving genuinely simultaneous alternate lines.

Related, already-known operational gap: `run_projections.py:409–435` can revert an entire slate to DK PPG below 30% props coverage or on a caught exception. The “props” log count includes fallback rows, so it is not an actual props coverage measure. Moving the refresh later reduces the trigger but does not make this fail closed. Persist per-row source/age/completeness and a checked live readiness summary; define permitted degradation explicitly. This review does not authorize changing blend weights or fallback policy.

## 9. P1 — frozen reader cannot consume bank991 under either handoff scenario

Location: lab `scripts/prereg099_report.py` at `c06b2cd`, lines 34–36, 50–61, 230.

`BANKS={990}`, only `119b990r1-` accepted, repair regex also only 990, and CLI arity fixed to one run. Passing `119b991r1-20260917T230652Z` to the pure preflight helper raises “run ID is outside the frozen cohort”. It cannot read 991 alone or pool 990+991 as described in the laptop handoff.

Required owner action: prepare and commit an outcome-blind, versioned reader/amendment in a separate worktree before first read. Specify the Friday cutoff's combined-versus-later-replication semantics, exact eligible bank/slate sets, identity expectations, and interpretation. Keep running `c06b2cd` untouched. This is an integration gap between the later handoff and frozen reader, not a request to relabel results after seeing them.

## 10. P1 — single-season secondary inference can falsely print PASS

Location: same frozen reader, `_paired` lines 196–211 and `_verdict` lines 214–223.

Amendment 4 restricts the cohort to 2021, but `_paired` resamples seasons. Sampling one season with replacement always selects that same season: every bootstrap mean is identical, the interval collapses, and leaving out the sole season produces NaN. `_verdict` counts `NaN < 0` as false. A positive secondary delta can therefore print PASS without estimable season-level uncertainty.

The primary supply ratio uses a separate slate bootstrap and is not subject to this specific defect. The reader says secondaries cannot license adoption; retain that restriction. Fix before read: report season-cluster intervals/LOSO as not estimable with one season and never infer stability/PASS from them. Any alternate slate-level descriptive interval needs an explicit estimand and pre-read amendment, not a silent substitute for cross-season evidence. A second simulator bank does not provide another season.

## 11. P2 — reader boundary handling and validation are weaker than its fail-closed claim

Same reader: `_ratio:160–178`, primary formatter `:239`, `_validate_books:100–108`, `_load:132–156`.

* Zero control supply returns no `slates_with_any_full/control`; primary formatting then raises KeyError instead of reporting UNDEFINED. Reproduced with synthetic rows. Return a stable schema on every branch. Bootstrap denominator-zero draws are discarded: disclose their frequency and preregister treatment, especially for sparse higher thresholds.
* Eighty duplicate rank-1 rows pass `_validate_books`; reproduced using synthetic data. Require exact ranks 1…80, finite scores, unique roster identity and agreement with reported maxima where the artifact supports it.
* The reader requires one common code/benchmark identity, not the expected identity; counts 18 distinct 2021 slates without asserting weeks 1…18. Verify an explicit expected cohort and approved code/benchmark content identities. A uniformly wrong cohort should fail too.

These are validation counterexamples, not allegations that existing shards are malformed.

## Coverage and verification

Read the requested new-model briefing, transition/run handoffs, both CLAUDE entry points and lab coordination/laws; inspected current/recent transition changes and historical verdict corrections. Repository-wide Python AST inventory and shell parsing found **0 syntax failures** across 1,549 production Python files (934,761 lines), 567 lab Python files (129,046 lines), and 396/149 shell files respectively. This is **not a claim of manual line-by-line review of over one million lines**.

Deep tracing concentrated on Sunday builders/watchers/filler/emitter, projection/props handling, point-in-time feature safeguards, active live centering, corpus/selector interfaces, and frozen 119 reader/invocation contracts. Archived research, app/graph/trends endpoints, every historical SQL transformation, deployed BigQuery view definitions and copied workstation tools have not each received exhaustive behavioral verification. No cloud deployment, warehouse update, timer, entries export or outcome read was performed.

Existing targeted offline tests passed: `tests/test_leakage.py` and `tests/test_market_implied.py` (33 tests). They exercise synthetic PIT and market behavior, not the missing watcher contracts above. Command from this worktree:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest -q tests/test_leakage.py tests/test_market_implied.py --disable-warnings --maxfail=3
```

Synthetic reproduction and transcript are attached under `reports/reviews/evidence/`. Only pure reader helpers were AST-extracted; neither real reader entrypoint nor result loader was executed. Existing leakage checks, frozen-run discipline, and separation of prospective versus spent historical data are assets to preserve while fixing the wrappers.

## Handoff request

Workstation agent: acknowledge and triage 1–5 against actual deployed host copies; prepare outcome-blind 9–11 before your first read; record fixes with negative boundary tests on your own branch. Erich requested review documents only from this agent, so this report does not itself modify or deploy fixes. Bank991 remains running at frozen HEAD with monitoring; no verdict is implied by its operational health.
