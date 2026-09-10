# Generation shadow `vx76b` terminal failure and paired-input v2 repair

Date: 2026-09-10

## Disposition

Cloud Run execution `generation-shadow-suite-vx76b` is a terminal failure and
is not an accepted Week-1 generation-shadow root. It completed all 25 declared
candidate-generation blocks, then failed before the independent audit bank,
world artifacts, manifest, or terminal root could be published. Its persisted
candidate-log rows are retained as diagnostic evidence only. The execution
must not be collected, promoted, or relabelled as successful.

## Exact failed execution

- source commit: `607e184e63b34a0c6f56c92a22160fe8579a863c`
- immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:225d1ade42385154ed0cb9b5b7eb98e940ee281d4a6eb43eccb30859cb1c78dd`
- job: `generation-shadow-suite`
- execution: `generation-shadow-suite-vx76b`
- execution UID: `f04daff5-0699-4267-8ef5-9c99b95fc111`
- started: `2026-09-10T10:56:47.204688Z`
- completed: `2026-09-10T12:50:04.749871Z`
- terminal count: one failed task, zero successful tasks, zero retries
- terminal exception: `ProspectiveGenerationShadowError: prospective paired
  native input/source authority differs`, caused by `ValueError: paired native
  input authority incumbent-160-40/R1 source drift`

The execution durably logged five combined pools to
`nfl_predictions.live_candidates_shadow`:

| Arm | Rows | Logged at (UTC) | Worlds | Score artifacts |
|---|---:|---|---:|---:|
| `incumbent-160-40` | 260 | 11:52:08 | 50,000 | 0 |
| `boom-first-40-160` | 261 | 12:04:52 | 50,000 | 0 |
| `cross-law-40-100-60` | 261 | 12:20:00 | 50,000 | 0 |
| `boom-dose-40-360` | 461 | 12:38:00 | 50,000 | 0 |
| `ceiling-all-boom-0-200` | 263 | 12:49:50 | 50,000 | 0 |

Total execution-specific candidate rows: 1,506. These rows are insufficient
to reconstruct the required terminal root: they do not contain the full player
world matrices or an independent audit artifact.

## Root cause

The v1 authority asserted that every arm and every R0--R4 block used one
byte-identical `candidate_input_receipt`. That law is impossible for the
registered design. The receipt hashes seed-derived columns including `proj`,
`proj_p10`, `proj_p50`, `proj_p90`, `proj_std`, `proj_tourney`, and
`model_points_pre`; R0--R4 deliberately use different projection and role
seeds. For example, the incumbent candidate receipt is `aa57be28...` at R0
and `f18390eb...` at R1.

The execution also rebuilt the live player/market source independently for
each arm. Corresponding seed hashes therefore differed across arms as well;
for example R0 is `aa57be28...` for incumbent, `b7d14f55...` for boom-first,
and `d14cc529...` for boom-dose. Relaxing the validator would have hidden an
unpaired experiment, so no failed evidence was accepted.

## Repair

The paired-input authority is now v2 and separates three identities:

1. one stable, seed-independent player/market/model/construction source shared
   by every block and arm;
2. five registered R0--R4 execution-input receipts, which may differ across
   seed blocks; and
3. exact corresponding-block execution equality across all five arms.

Before candidate optimization begins, the suite loads and validates the five
main-model seed inputs, five role-model seed inputs, and the independent audit
seed. Any player order, model identity, salary, market, component, route-source,
or unseeded DST projection drift aborts before expensive solves. During each
arm the suite temporarily replaces the live source loader with a strict
restored-on-exit reader over those frozen matrices. The independent audit uses
its own registered execution seed while proving the same stable source.

The repair is intentionally confined to the prospective suite and its
authority/evaluation validators. Adopted-policy files frozen by the Week-1
effective-policy inventory (`live_lineups.py`, `backtest/engine.py`, and
`multiseed_portfolio.py`) remain byte-for-byte unchanged.

## Validation

- Python compilation: pass
- `git diff --check`: pass
- generation suite, evaluation clean-reopen, multiseed, and paired-boom tests:
  pass
- new regressions prove:
  - R0--R4 execution receipts may differ;
  - the same R block must remain exact across arms;
  - the audit execution receipt may differ while its stable source must match;
  - all 11 source matrices are loaded before candidate work;
  - preflight source drift fails closed; and
  - the suite-local live-loader replacement is restored after every arm.

## Next action

Build an immutable image from the reviewed repair commit, deploy it to the
existing dedicated job without changing the Week-1 coordinates, and start one
new zero-retry execution. Accept and collect only a successful terminal root
whose v2 authority reopens cleanly. Preserve `vx76b` and its 1,506 candidate
rows as failed diagnostic evidence; do not retry or delete them.
