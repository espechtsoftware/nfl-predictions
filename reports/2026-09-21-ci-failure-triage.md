# CI failure triage — run 35611477377

**Written for:** the lab agent and the operator.

Branch `fix/ci-gcp-extra-20260921`, completed 2026-09-21 after 3:19:42:
**263 failed, 7,938 passed, 16 skipped, 116 errors.** The operator received the
"all jobs have failed" email for this run.

## Headline

Nothing in the money path is broken. The 263 failures fall across 42 distinct
files, and **none of those 42 files is one of the 26 money-path lane files.**
Every failure is one of three things: two cases of tests drifting behind a
deliberate hardening (now repaired), one test-only race (now repaired), and a
large block of frozen-chain drift that is the guard working as designed.

## What was actually wrong, and what changed

### 1. `test_bq_load.py` — 3 failures — REPAIRED (`204da306`)

The autouse guard added in `10430879` (2026-09-20) records every
`nfl_dfs.bq.load_dataframe` call instead of executing it. It was added for a
good reason: the offline live smoke had written 1,558 synthetic rows into
`market_source_log` and 502 into `own_shadow` on a workstation that holds
warehouse credentials.

Its docstring asserted that no offline test needs the real function and
promised an explicit opt-out. Both were wrong. `tests/test_bq_load.py`
exercises `load_dataframe` itself against a fake BigQuery client, so the guard
made those three tests exercise the stub — the fake client was never called at
all, which is why the failure read `assert {} == {...}`.

Repair: added the promised opt-out as a registered `real_load_dataframe`
marker and applied it to the three tests of `load_dataframe` itself. The guard
still applies everywhere else; `test_live_smoke.py` still asserts its write
through the recorder.

### 2. `test_persistence_contract.py` — 5 failures — REPAIRED (`204da306`)

`f29c6da4` (2026-08-29, "Make Classic construction rules explicit") replaced
six `os.environ` fallbacks with `{}`, so a lever can never be picked up
ambiently from the process environment. That is the no-silent-fallbacks
discipline, and it is the guard against the unrecorded-lever class that
invalidated panel `20260806-universe-baseline-81b7ff3`.

These five tests still set levers with `monkeypatch.setenv` and expected the
engine to read them. Every env-derived provenance field therefore arrived
empty: `lever_env` `""`, `code_sha` `"unknown"`, `panel_run_id` `""`.

**This is not a production defect.** The money path already passes the lever
set explicitly — `inference/live_lineups.py:1070` passes `policy_env=policy_env`.
Candidate provenance in production is intact.

Repair: the tests now pass levers through `policy_env`. The `setenv` calls are
kept deliberately, so a lever present only in the process environment must NOT
appear in the recorded set. `test_explicit_shadow_identity_overrides_process_env`
is strengthened: the explicit argument must now beat both a `policy_env` entry
and a process-environment one.

### 3. `test_launcher_registry.py` — 1 failure — REPAIRED (`42b12458`)

`test_sigkill_orphan_blocks_contender_while_child_group_survives` failed at
`assert receipt.exists()` on a path named `.registration.tVAQq7` — the
registry's mktemp staging file, not a receipt. `launcher_registry.sh` writes
`.registration.XXXXXX`, hardlinks it into place, then unlinks the temp.

The helper globbed with `pathlib`'s `glob("*")`, which matches dotfiles —
unlike `glob.glob`, whose dotfile-skipping behaviour the helper appears to
have assumed. In the window after mktemp and before the hardlink, the staging
file is the only entry, so the helper returned it and the name was gone by the
time the test checked.

**The registry behaved correctly throughout:** the contender refused the
orphaned lane with exit 2 and the real receipt was never removed, which is why
the preceding assertion passed. The single-writer lane guard (CLAUDE.md rule
6) is not implicated. Repair is test-only.

### 4. Six atlas tests — NO ACTION, and none should be taken

- `test_atlas_minimal_c_runner.py::test_generation_env_blanks_persistence_only`
  asserts `env["N_BOOM"] == "40"`. Live policy is `N_BOOM=160`.
- The other five are sha256 source-inventory and frozen-protocol checks with
  mismatched digests.

This is exactly the condition CLAUDE.md already records: *"Frozen research
chains pinned to the old environment now fail closed against the live policy
— that is the guard working, not a test defect."* See
`reports/2026-09-11-frozen-factorial-policy-drift.md`.

"Repairing" these would mean either editing a frozen chain's environment,
which destroys the comparability the freeze exists to protect, or changing
live policy to match a superseded chain. Neither is acceptable. The correct
disposition is quarantine, which is a research-chain decision and belongs to
the lab, not a unilateral change from this side.

### 5. The remaining bulk — frozen-chain hash-pin drift

Concentrated in `test_corpus_extreme_tail_generation_companion_manifest.py`
(64), `test_finish_a7_select_ladder.py` (42), and
`test_corpus_extreme_tail_factorial_manifest.py` (33). Same class as §4.

## Why this went unnoticed

The full-suite lane has not completed since it hit its three-hour ceiling on
2026-09-15 (build `2a28b013`). Neither `test_bq_load.py` nor
`test_persistence_contract.py` is in the targeted money-path lanes, so nothing
was running them. The `test_persistence_contract.py` failures have most likely
been red since 2026-08-29.

## Verification

29 passed across `test_bq_load.py`, `test_persistence_contract.py` and
`test_live_smoke.py`; 15 passed in `test_launcher_registry.py`.

## Open question for the lab

Whether the frozen chains in §4 and §5 should move into the existing test
quarantine (cf. `c35c669e`, "Release two modules from the test quarantine") so
that a red CI again means something actionable. Until they do, this branch's
CI cannot go green, and an "all jobs have failed" email carries no signal.
