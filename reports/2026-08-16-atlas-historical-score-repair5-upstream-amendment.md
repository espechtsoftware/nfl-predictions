# ATLAS historical diagnostic repair5-upstream amendment

Date frozen: 2026-08-16, while the binary 32-GiB full-cell preflight was
nonterminal, before repair5 was licensed or launched and before any repair5
score-free effect or historical score existed.

Applies to `20260816-atlas-historical-score-diagnostic-v1` and its source-
parity, sharded-upstream, high-tail-guard and repair4-upstream amendments.
Disposition class: conditional mechanical upstream rebinding only; no scoring
or production consequence.

## Conditional scope

This amendment is inert unless the exact 32-GiB full-cell preflight is strictly
harvested successful and the already-frozen resource-only repair5 grid is then
strictly harvested as a complete, mechanically valid 54-cell population. A
failed preflight or any failed/missing repair5 cell produces no historical
score run.

Repair4 is terminally invalid: it has zero successful cells, 54 failed cells
and zero output objects. It must never be scored. This amendment does not
reinterpret repair4, reuse any repair2--repair4 shard or relax any upstream
condition.

## Exact replacement upstream

- Run ID: `20260816-atlas-matched-diversity-mvp-v1-repair5`.
- Output prefix:
  `gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5`.
- Upstream code SHA: `60f296fdad769b30c0bb7334118698f156e462b9`.
- Upstream image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`.
- Frozen MVP runner SHA-256:
  `0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`.
- Resource-only repair5 protocol SHA-256:
  `5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e`.
- Repair5 launcher SHA-256:
  `9ea70f34e2591672e4b84621c116db8e4b465177bbda689d9d555c3d18d85b42`.
- Repair5 strict finisher SHA-256:
  `39fe8218edbfabe8a0e021407f8cca5da0fa9113c93e858556761164ca434933`.
- Population: exactly 2023--2025 Weeks 1--18, one new `-r5` execution and
  create-only shard URI for every one of 54 cells.
- Per-cell resources: 8 CPU, 32 GiB, zero retries and 43,200-second timeout.
- Interaction auxiliaries remain binary. The continuous-interaction fallback
  is excluded from this upstream.

The exact future execution names and object URIs in repair5's create-only
`executions.txt` become authoritative mechanically when the launcher runs.
The scorer must bind that ledger byte-for-byte and may not select identities
from a Cloud Run listing, replace a failed execution or combine binary and
continuous cells.

## Strict-harvest release

Historical scoring is released after any valid repair5 score-free disposition,
whether the score-free gate passes or fails. This unconditional release avoids
using the score-free effect to decide whether historical results are opened.

Before the scorer can launch, its create-only upstream receipt must bind:

- repair5 `manifest.txt`, `executions.txt`, `completion.txt` and `report.json`;
- `season-2023.json`, `season-2024.json` and `season-2025.json`;
- `shards.sha256` plus all 54 exact shard generations and hashes;
- `execution-metadata.sha256` plus all 54 exact execution records;
- the repair5 protocol, launcher and strict-finisher hashes above; and
- the exact upstream code, image, rendered command, source-repair receipts and
  preflight/census bindings already enforced by the repair5 strict finisher.

These terminal hashes and object generations do not exist at freeze time.
Recording them mechanically after strict harvest cannot change the population,
scoring law or decision boundary. The repair5-bound scorer must use new
create-only diagnostic identity
`20260816-atlas-historical-score-diagnostic-v3`; it may not overwrite or reuse
the invalid repair4-bound v2 destination.

## Unchanged historical law

All original reconstruction and scoring rules remain fixed: equal P1/P2
candidate budgets, the same order-invariant CBWU-OI construction, the same
194-support exact-80 selector, all 54 slates, exact native player-score parity
and exact sums of nine realized player outcomes.

The controlling tail-first rule remains:

1. at least two additional selected-book weeks at 200;
2. no selected-book decline at 210, 220, 230 or 240;
3. no candidate-pool decline at 200; and
4. complete mechanical and scoring-source validity.

No repair5 effect, partial shard, realized score, selector sensitivity or
threshold count may be inspected to modify the scorer or rule. The result is
retrospective evidence for the already-declared 2026 shadow only and cannot by
itself change production, the UI or a money book.
