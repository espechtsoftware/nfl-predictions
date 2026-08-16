# ATLAS repair3 output-prefix invalidation

Date: 2026-08-16

Run ID: `20260816-atlas-matched-diversity-mvp-v1-repair3`

## Disposition

Repair3 is a terminal mechanical non-result. All 54 executions failed before
querying source data or starting an ATLAS optimization, and the create-only
repair3 GCS prefix contains zero objects. No candidate, selector, score-free
effect, realized score, or production evidence exists for this run.

## Exact failure

Every execution reached terminal `Completed=False`, reason
`NonZeroExitCode`, with one failed task, zero successful tasks and zero
configured retries. Every execution emitted the same traceback:

`RuntimeError: ATLAS MVP shard season/week/output identity differs`

The pinned repair2 runner validates its shard URI against the constant
`SHARDED_OUTPUT_PREFIX`, which is hard-coded to the repair2 run prefix. The
repair3 launcher correctly created a new immutable repair3 prefix, but the
unchanged old runner necessarily rejected it at the first identity check in
`run_slate_shard`, before `_query` or any solver call.

This is not a recurrence of the CBC failure and says nothing about the
4-CPU / 16-GiB resource treatment. The successful preflight remains valid.

## Corrective boundary

A new repair4 may preserve the exact pinned repair2 image, code and binary
interaction formulation while mechanically overriding only the runner's
allowed shard-output prefix to a new repair4 identity. Before launching the
grid, a real-container verification must prove the pinned runner source hash,
the expected original repair2 prefix and the exact replacement prefix. The
complete 54-cell population must use new jobs, executions and object URIs.

No repair3 execution or object may be reused. Historical scoring remains
blocked until a complete new grid is terminal successful and strictly
harvested.

## Durable evidence

- Launch manifest SHA-256:
  `08a6ad9e4f8581c101965e1928a3d69aee96fd244d265e80b6eaa4cc00c93b84`.
- Complete 54-row execution ledger SHA-256:
  `4bc8f940253b98e3a6f03f28b127b16cf3677ab8254b775f9fca6c1253b36467`.
- Strict failure summary SHA-256:
  `4da1f34de96f8ae9224d8c330abeae9ec3ade562c512e58f8e9ad60e6e8d4558`.
- Strict failure completion SHA-256:
  `8dc630d58fae604b466792563402daff5a0801305eafde2c5e742c2d4686b149`.
- Complete stderr census SHA-256:
  `5633ff462a144dbaab0711ac2f9cea3394f8eae23a650dcc10cabed37efa603f`.
- Execution-metadata ledger SHA-256:
  `c5678a3220fb36765673821f83bb08e083b7827424b80a5c2f00877a374fc81e`.
