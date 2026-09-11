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

**2. The failing modules do not import the scoring path.** No known-failing
module imports `nfl_dfs.optimizer`, `nfl_dfs.inference`, `nfl_dfs.models` or
`nfl_dfs.backtest`. They live in `nfl_dfs.research.*` and `nfl_dfs.analysis.*`,
and `test_finish_a7_select_ladder` imports no `nfl_dfs` at all.

A failing test that never executes scoring code cannot produce a scoring
defect. These are audit chains reporting that the policy changed — which it
did, deliberately.

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
