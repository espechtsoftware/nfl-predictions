# ATLAS matched-diversity MVP output-prefix repair4 protocol

Date frozen: 2026-08-16, after strict repair3 failure harvest and before any
repair4 job, execution or object existed

Run ID: `20260816-atlas-matched-diversity-mvp-v1-repair4`

## Mechanical reason

Repair3 changed to a new create-only object prefix while deliberately using
the exact repair2 image. The pinned runner itself hard-codes the repair2 shard
prefix, so all 54 repair3 cells rejected their new URI before querying data or
starting an optimization. Strict evidence is recorded in
`reports/2026-08-16-atlas-repair3-prefix-invalidation.md`.

Repair4 corrects only that output-transport identity. It does not change the
ATLAS calculation, candidates, worlds, interaction variables, selector,
score-free gate or historical score rule.

## Immutable scientific calculation

Retain the exact repair2/repair3 image:

`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`

Retain code identity `60f296fdad769b30c0bb7334118698f156e462b9` and the
original binary interaction formulation. The runner file inside that image
must have SHA-256
`0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`.

Load that exact file, require its original `SHARDED_OUTPUT_PREFIX` to be the
repair2 prefix, and replace only that in-memory constant with:

`gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair4`

Then invoke its unchanged `main()` with the normal season, week and output-URI
arguments. The wrapper source and fully rendered command must be hash-bound in
the launch manifest and every execution receipt.

## Mandatory real-container verification

Before creating any repair4 grid job, run the same bootstrap in verification
mode inside the exact pinned image. It must:

1. verify the runner file hash;
2. verify the original repair2 prefix;
3. apply and verify the exact repair4 prefix;
4. print the single frozen verification marker; and
5. terminate successfully without querying data, solving, persisting a lineup
   or addressing a repair4 output object.

The launcher must strictly validate and retain the smoke execution metadata
and marker before continuing. A missing or failed smoke blocks the grid.

## Resource envelope and population

The successful 16-GiB preflight remains authoritative. Every scientific cell
uses four CPUs, 16 GiB memory, one task, parallelism one, zero retries, the
same service account and a 12-hour timeout.

Create exactly the 54-cell cross product of seasons 2023--2025 and Weeks
1--18 with new jobs `atlas-md-s<season>-w<week>-r4`, new executions and new
create-only repair4 object URIs. No repair2 or repair3 execution, shard or
aggregate may be reused.

## Harvest and consequence

Do not inspect partial shard outputs. Poll only execution status until the
complete grid is terminal. The strict repair4 finisher must validate all 54
successful execution identities, the exact bootstrap command, the pinned
image/code, resources, environment and output URI; then validate and assemble
all score-free shards with the unchanged aggregator and gate.

Whether the original score-free gate passes or fails, a mechanically valid
repair4 aggregate proceeds to the separately frozen exact-80 historical score
diagnostic with the 220/230/240 no-decline amendment. Repair4 itself cannot
license production.
