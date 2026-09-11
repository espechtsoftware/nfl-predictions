# Failing test inventory — 2026-09-11

**Bottom line: none of this affects scoring.** The live Week-1 path is green.
Everything below is frozen research chains and audit/forensic modules failing
against a production policy that legitimately moved.

## Scoring impact: none

Two independent checks agree.

**1. The live path passes.** The money lane covers `test_scoring`,
`test_optimizer`, `test_optimizer_policy_isolation`, `test_production_policy`,
`test_feature_sql`, `test_dk_client`, `test_dk_standings_capture`,
`test_dk_paid_freshness_scheduler_contract` and `test_app`:

```
./scripts/test_lanes.sh money  ->  218 passed, 1 skipped, 0 failed, 4m17s
```

**2. The construction-path failures are stale tests, and the money path
provably still carries every incumbent rule.**

*Correction to an earlier draft of this file:* it claimed no failing module
imports the scoring path. That was drawn from a partial failure list and was
wrong. Four modules do import it — `test_single_stack_boom_solves`,
`test_wr_lowown_levers`, `test_research_infra` and `test_persistence_contract`
reach `nfl_dfs.optimizer.lineup`, `nfl_dfs.backtest.replay`,
`nfl_dfs.inference.live_lineups` and `nfl_dfs.models.blend`. Each was therefore
investigated individually rather than dismissed.

All four share one root cause: `f29c6da4` "Make Classic construction rules
explicit" moved construction levers from ambient process environment to
caller-supplied data, so that *omitting* the strategy environment cannot
silently activate a house rule. The tests still assert the old ambient
behaviour. Verified directly:

```
no env                    -> low_own 1      (lever inactive, by design)
explicit MIN_LOWOWN=2     -> low_own 2      lever works
explicit MAX_PER_GAME=3   -> max/game 3     lever works
```

The production construction preset `classic-incumbent-gpp-v1` carries every
incumbent rule:

```
forbid_rb_vs_dst: true      forbid_two_rb_same_team: true
min_salary: 49000           min_games: 2        max_overlap: 7
qb_stack_min: 2             bring_back_min: 1
```

So the `$49k` floor and the RB-vs-DST and same-team-RB rules are live on the
money path. `MIN_LINEUP_SALARY` reading 0 in the config manifest is the
deliberate default (explicit, not ambient), not a deleted floor.

All four were repaired to supply what they claim to check, and the hardening
itself is now asserted — exported-but-not-supplied levers must NOT bind — so
the property that replaced the old behaviour is covered rather than merely
accommodated.

## What needs fixing, in priority order

### 1. Extreme-tail factorial band — ~125 failures — TRUE POSITIVE, protocol decision

Modules: `test_corpus_extreme_tail_factorial_manifest`,
`test_corpus_extreme_tail_generation_additions`,
`test_corpus_extreme_tail_generation_companion_manifest`,
`test_corpus_expansion_build`.

Eleven environment keys drifted since the freeze commit `c876e7f2`
(2026-08-24): `N_BOOM` 40->160, `GEN_TOTAL_BUDGET` 52->172, plus `N_LEV` and
eight new construction levers. Proven exactly — reconstructing the policy at
that commit reproduces the pinned hash.

Do **not** relax the `BOOM_UNIQUE_FILL` sentinel (tried and reverted: it
deletes the earliest alarm in one true signal) and do **not** repoint at
`incumbent_control_environment` (restores `n_boom=40`, still misses the hash).
The underlying defect is that the chain re-derives a frozen constant from a
mutable live object. Full analysis:
`reports/2026-09-11-frozen-factorial-policy-drift.md`.

**Owner: protocol authority. Not a code fix.**

### 2. Forensic/ladder error cluster — ~61 ERRORS — uninvestigated

Modules: `test_final_forensic`, `test_final_forensic_cleanup`,
`test_final_forensic_corpus`, `test_final_forensic_diagnostics`,
`test_final_forensic_hpcs`, `test_final_forensic_outputs`,
`test_final_served_dependence`, `test_finish_a7_select_ladder`.

These are **errors**, not failures — setup/fixture/collection problems, a
different class from everything else here. Clustered tightly enough to suggest
one shared root cause. Not yet diagnosed; no scoring exposure (see above), so
deprioritised behind Week 1.

### 3. Scattered failures — ~59 — uninvestigated

Outside the factorial band, at roughly the 3-5%, 27%, 35% and 77-78% marks of
collection order. `test_app` was one of these and is now fixed (`978d00be`) --
it was a genuinely stale expectation, not a quarantine candidate: the app
deliberately grew `portfolio_allocation` to disclose the boom-first figures
while retaining the legacy keys.

Expect others in this group to be the same shape: assertions pinned to a
pre-boom-first policy. Each needs the same treatment — verify the served value
derives correctly from the policy *before* touching the expectation.

## A bug this inventory found in its own tooling

The full lane ran `pytest -rf` and grepped `^FAILED`. pytest reports errors
(`-rE`) separately from failures (`-rf`), so the ~61 ERRORS above would have
appeared in **neither** the KNOWN nor the NEW bucket — they would have vanished,
and the lane would have looked cleaner than the suite is.

That is exactly the failure the quarantine exists to prevent, reproduced in the
tool built to prevent it: a check that can only see one category of problem
reports success when the other category happens. Fixed to `-rfE` with both
`FAILED` and `ERROR` classified.

## Standing rule for this inventory

A quarantine entry must carry a dated, specific reason, and quarantined modules
still execute in the full lane — their failures are reported under `KNOWN`,
anything else as `NEW`, and an entry that stops failing is flagged as a release
candidate. Nothing here is suppressed.
