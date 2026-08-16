# ATLAS repair5 terminal failure-census protocol

Date frozen: 2026-08-16, while the binary 32-GiB full-cell preflight was
nonterminal, before repair5 was licensed or launched and before any repair5
effect existed.

Protocol ID: `20260816-atlas-repair5-terminal-census-v1`

## Purpose

The normal repair5 strict finisher requires all 54 cells successful. If any
cell fails, it correctly refuses to harvest, but that alone would leave no
durable complete failure census and no auditable indication that research
capacity has been released for the already-frozen continuous-interaction
parity diagnostic.

This protocol closes only that operational gap. It does not retry, replace,
cancel or score a cell and does not inspect any shard content.

## Preconditions and population

The census may run only if repair5's exact create-only `manifest.txt` and
`executions.txt` exist, the ledger contains exactly one unique cell for every
2023--2025 Week 1--18 combination, and all 54 exact execution identities are
terminal. At least one execution must be terminal failed. If all 54 succeeded,
use only the normal strict repair5 finisher.

Every execution must match the repair5 contract byte-for-byte:

- run/prefix `20260816-atlas-matched-diversity-mvp-v1-repair5`;
- pinned image/code and unchanged rendered binary-interaction command;
- one task at 8 CPU/32 GiB, zero retries and 43,200-second timeout;
- exact service account and environment; and
- its exact ledger-declared create-only object URI.

The census records terminal status, reason/message, counts and completion time.
It lists GCS object URIs only, requiring every listed URI to be one of the 54
ledger destinations. It must not download or open any shard, report an effect
field, inspect a lineup identity or query a realized outcome.

## Output and consequence

Create one immutable local census containing:

- all 54 exact execution metadata records and their hash ledger;
- URI-only object inventory and hash;
- manifest and execution-ledger hashes;
- success/failure counts and categorized terminal reasons; and
- explicit flags `scientific_result_valid=false`,
  `effect_fields_inspected=false`, `historical_scoring_licensed=false` and
  `production_change_licensed=false`.

Any failed repair5 population is terminally invalid and cannot feed the
historical scorer. Once all 54 cells are terminal and this census validates,
research capacity is released. The original continuous-interaction parity
protocol may then run as a separate formulation diagnostic; no binary shard or
effect may be mixed into that path.
