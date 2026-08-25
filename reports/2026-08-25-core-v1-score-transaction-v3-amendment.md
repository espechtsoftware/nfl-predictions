# Core v1 score transaction v3 amendment

**Date:** 2026-08-25
**Status:** prospectively frozen and outcome-blind; execution waits for the
accepted T230 v2 panel release

## Decision

Create a third operational incarnation of the unchanged Core v1 first-score
transaction. The `*-v2` transaction was bound to candidate
`56d64cbe-2d77-4f51-adf8-21b65dbe7b7c`, which failed before producing an
image or smoke. Its identifiers remain terminal-unused and are never aliases
or recovery inputs.

Core science remains exactly 12 strategies by budgets `4/14/80` by 54 slates,
or 1,944 immutable book cells, with the same contrast registry,
`r194:incumbent` baseline, one player/DST outcome snapshot and score-once
grader.

## Frozen upstream binding

- Foundry G0 panel:
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/panels/20260823-foundry-production-v12/foundry-v12-combined-panel-index-v1.json`,
  generation `1787663639938214`, SHA-256
  `4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9`.
- T230 run: `20260825-foundry-t230-production-v2`.
- Image source S3:
  `a6bc9d4c862777c03d7dd802c5950486e7d85134`.
- Candidate build:
  `52c91739-aa85-4c61-95fa-155e1a1c96a5`.
- Runtime image: exactly the future digest D2 produced and successfully
  Rule-1-smoked by that candidate, then accepted by a same-S3, same-D2 release
  with `candidate_image_rebuilt=false`.
- T230 panel release:
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230/20260825-foundry-t230-production-v2/foundry-t230-panel-release-v1.json`.
- Reused job/region: `atlas-minimal-c-s2023-w1-v1`, `us-central1`.
- Runtime service account:
  `817589974517-compute@developer.gserviceaccount.com`.

A failed candidate, absent smoke gate, different digest, rebuilt release,
different source, or different T230 panel cannot satisfy this binding.

## Frozen Core transaction identifiers

- Chain: `20260825-core-v1-score-chain-v3`.
- Catalog ID: `20260825-core-v1-score-catalog-v3`.
- Catalog prefix:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1/catalogs/20260825-core-v1-score-catalog-v3/`.
- Catalog logical-byte ceiling: `100000000`.
- Outcome run: `20260825-core-v1-realized-score-v3`.
- Outcome prefix:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1-realized/20260825-core-v1-realized-score-v3/`.
- Grade run: `20260825-core-v1-realized-grade-v3`.
- Grade prefix:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-core-v1-grades/20260825-core-v1-realized-grade-v3/`.
- Grade logical-byte ceiling: `200000000`.

## Outcome boundary

The candidate, smoke, release, T230 prepare/benchmark/panel and Core catalog
are outcome-blind. Only after the complete 1,944-cell catalog is immutable may
one historical-outcome lease and the one fixed outcome query run. A scoring
claim requires all 54 grade shards, `contrast-summaries.json`, the grade root
and terminal `completion.json`; partial output is never interpreted.
