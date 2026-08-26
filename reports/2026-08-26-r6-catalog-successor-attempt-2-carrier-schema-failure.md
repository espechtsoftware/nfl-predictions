# R6 catalog successor attempt-2 carrier-schema failure

## Disposition

The sole corrected fixed-G0 catalog projection entered the generation-pinned
54-slate replay from clean commit
`3c60aca22adbea768f24c3248385a44523dbb9bf` and exited `1` before any
catalog, derivation receipt, release, or replay-receipt publication. The
ordinal-2 attempt marker was durably created first and is consumed. Do not
rerun this entry point or delete/replace its marker.

No world-matrix body, arm-result body, realized outcome, score, graph, or live
policy was read. The adapter failed while validating the first accepted task's
small carrier object, before the all-input derivation boundary and therefore
before the first output create.

## Exact invocation and failure

- Logical locked command:
  `.venv/bin/python -m nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_projection_successor_v1 publish-projection --execute`
- Production enable gate:
  `R6_FIXED_G0_ADAPTER_PRODUCTION_ENABLED=1`
- Clean checkout:
  `/tmp/nfl-r6-catalog-projection-successor-3c60aca2`
- Exit code: `1`
- Exception:
  `CorpusR6FixedG0AdapterV1Error: task evidence[0] carrier differs`
- Attempt marker:
  `reports/2026-08-26-r6-player-catalog-fixed-g0-projection-successor-attempt.json`
- Attempt-marker internal SHA-256:
  `fef7b15fe1c5b4c566153f2f7d22b130f519ee012f49a35690294c4f25a0a02c`

## Exact carrier and defect

The failing carrier was exact-read at this immutable identity:

- URI: `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12a/tasks/task-0000-2023-w01/result/task-result.json`
- generation: `1787521590972723`
- SHA-256: `8149de8f5ca66c89d1137b92328f0add7f76c46aeff281d9323ca6ac5ce20548`
- bytes: `12023`

The real carrier's `world_schedule` field is a content-addressed object
identity with `uri`, `generation`, `sha256`, and `bytes`. The fixed-G0 adapter
correctly validates the carrier's other identity fields but then incorrectly
requires `world_schedule` to be a Python `Sequence`. A mapping is not a
`Sequence`, so the final carrier predicate fails deterministically even though
the accepted one-slate reconstruction already consumed this same carrier
successfully. The adapter fixture encoded the wrong shape and did not expose
the mismatch.

This is a structural adapter defect, not a scientific failure and not evidence
against the accepted G0 panel, its candidates, or its simulated worlds.

## Next action

Do not authorize another catalog projection attempt from this successor. Keep
the accepted 54-slate G0 panel as the source of truth and advance the separate
full-union/T230 R6 lane directly from its generation-pinned carriers and world
objects. Its historical outcome-key projection can use the already frozen
later-source catalog identity carried by every accepted task; catalog
publication is not required to freeze outcome-blind books. Correct and test
the `world_schedule` identity law independently so the reusable catalog path
can be restored later without delaying the first historical score pass.
