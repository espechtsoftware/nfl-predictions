# ATLAS matched-diversity MVP resource-only repair5

Date frozen: 2026-08-16, while the exact 32-GiB full-cell preflight and the
remaining repair4 cells were nonterminal, before any repair4 shard/effect or
32-GiB preflight shard was opened.
Protocol ID: `20260816-atlas-matched-diversity-mvp-v1-repair5`

## Conditional license

Repair5 may launch only if both conditions are met:

1. exact preflight execution `atlas-cbc-32g-full-2023-w8-v1-lbzjd` is strictly
   harvested as terminal successful at 8 CPU/32 GiB, with its exact full-cell
   shard mechanics valid; and
2. all 54 repair4 executions are terminal and their metadata-only census
   confirms at least one failure, including the already-observed 2023 Week 8
   configured-memory-limit failure, without opening any effect field.

If the preflight fails, this protocol does not license a grid. Repair5 does not
depend on the number of additional repair4 failures or any successful repair4
effect.

## Frozen treatment

The population remains exactly 2023--2025 Weeks 1--18 (54 cells). Every cell
must receive a new repair5 job, execution and create-only object URI. No
repair2, repair3 or repair4 execution/object may be reused.

Relative to repair4, only the inseparable Cloud Run resource envelope changes:

- CPU: 4 to 8;
- memory: 16 GiB to 32 GiB.

Everything else remains exact:

- pinned upstream image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`;
- code SHA `60f296fdad769b30c0bb7334118698f156e462b9`;
- frozen runner SHA-256
  `0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`;
- exact runtime output-prefix override, real-container verification and all
  source/protocol bindings used by repair4;
- binary interaction auxiliaries;
- zero retries and 43,200-second per-cell timeout;
- identical source candidates, pricing, worlds, constraints, enumeration,
  candidate budgets, score-free metrics and gate; and
- no realized outcomes, contest results, payout or ownership.

The later continuous-interaction optimization remains excluded. The purpose of
repair5 is to complete the already-frozen binary formulation under a resource
envelope demonstrated by the exact failed full cell.

## Harvest and consequence

The strict finisher must require all 54 exact executions terminal successful,
validate their 8-CPU/32-GiB identity, download exactly 54 create-only shards,
recompute the unchanged aggregate and bind all execution/object hashes. Any
failed or missing cell makes repair5 mechanically invalid.

Only a complete strict harvest may release the already-frozen exact-80
historical diagnostic, which must be separately rebound to repair5 before any
effect is inspected. The historical scorer runs after any valid score-free
disposition and retains its +2-at-200 and nondecline-at-210/220/230/240 guards.

Repair5 by itself licenses no production, UI, money-book or arm-adoption
change.
