# R6 fixed-G0 v2 task-0 smoke: publication-schema failure

Date: 2026-08-26

## Disposition

The sole licensed v2 task-0 smoke was invoked once from clean detached commit
`73946e196314c938b9925b446868fc259eb022c7`. It reserved its create-once v2
attempt marker and then exited 1 while validating the immutable, tracked G0
panel publication receipt. The success receipt was not created. A third
task-0 smoke is prohibited and will not be attempted.

The failure occurred before the first generation-pinned panel, lane, task
acceptance, or carrier object read. The GCS client was constructed, but the
failing receipt was read from Git commit
`168bc70a9793dce729d7e7e0a5d809b046a7a254`. No realized outcome, lineup,
world-matrix, result, or effect body was read. No cloud object was created or
mutated, no compute was submitted, and no catalog or source release was
published.

## Exact failure

The adapter raised:

```text
CorpusR6FixedG0AdapterV1Error: fixed panel publication receipt differs
```

The defect is one literal schema comparison:

- immutable tracked receipt: `foundry-v12-panel-index-publication/v1`
- adapter and synthetic fixture expected:
  `foundry-v12-panel-publication-receipt/v1`

The immutable receipt's outer binding remains exact: SHA-256
`70dfc8e9773958272d10d9dc58d9300556f401bfe08c1e352e36746cd23ed2e5`,
1,370 bytes. Its internal publication self-hash remains
`bf5ac51420a9483028b0325f0a2f8e4b1b8dba42880f3dced8bfdd2087f2e283`.

The v2 attempt marker is
`reports/2026-08-26-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt-v2.json`,
outer SHA-256
`36e28956944cf3d9ed68152d773f381838c3385965d0bb47bfca0f068deaa6c5`,
3,904 bytes, with internal self-hash
`8a2d364c711c047a6704c9e441cea7b9275671bad224428575c62b1ccbfa1115`.

## Defect-class sweep

A repository-wide static search found the production schema constant in
`scripts/build_corpus_v12_panel_index_v1.py`, the canonical Foundry consumer
in `src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py`, and the
one-slate smoke consumer all correctly use
`foundry-v12-panel-index-publication/v1`. Only the R6 fixed-G0 adapter and its
synthetic test fixture use the incorrect literal. The bounded correction must
change both and add an exact immutable-receipt regression test.

## Recovery boundary

Do not create a v3 cloud smoke. Freeze a reviewed correction that:

1. accepts only the exact production schema already bound by the G0 lock;
2. validates the complete immutable tracked publication receipt offline;
3. binds this failed v2 marker and the prior successful outcome-blind
   one-slate real-artifact smoke for `2023-w01`;
4. updates the final-release lock to represent the truthful two-attempt
   history without claiming the v2 smoke passed; and
5. licenses only the already-designed 54-slate projection materialization,
   whose generation-pinned reads and create-once outputs remain subject to
   exact reopen.

Realized outcomes and scoring remain closed until the R6-v2 source books are
frozen.
