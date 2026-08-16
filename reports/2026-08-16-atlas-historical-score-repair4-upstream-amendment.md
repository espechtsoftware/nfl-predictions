# ATLAS historical diagnostic repair4-upstream amendment

Date frozen: 2026-08-16, after the repair4 execution ledger was complete but
before any repair4 shard or aggregate result was opened.
Applies to: `20260816-atlas-historical-score-diagnostic-v1` and its source-
parity, sharded-upstream and high-tail-guard amendments.
Disposition class: mechanical upstream rebinding only; no scoring or production
consequence.

## Reason

The original historical diagnostic was subsequently bound to repair2, whose
interaction-heavy CBC grid did not complete. Repair3 changed only the licensed
resource envelope but failed before querying data because the old runner's
allowed output prefix still named repair2. Neither run produced a complete
mechanically valid upstream population, so neither can be scored.

Repair4 changes only that output-prefix transport defect while preserving the
same frozen ATLAS mechanism, source population, binary interaction variables,
candidate budgets and 4-CPU/16-GiB envelope licensed by the independent
preflight. The downstream historical question, reconstruction, exact-80
selector and decision rule do not change.

## Exact replacement upstream

- Run ID:
  `20260816-atlas-matched-diversity-mvp-v1-repair4`.
- Output prefix:
  `gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair4`.
- Upstream code SHA: `60f296fdad769b30c0bb7334118698f156e462b9`.
- Upstream image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`.
- Frozen runner SHA-256:
  `0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`.
- Repair4 protocol SHA-256:
  `5e84a6b93522fd959e798e90da307687179327b23c474fbda6b5303d0483063a`.
- Repair4 manifest SHA-256:
  `083a5e158053cd03f509bfebe518516af695773c029a78a8e80aa6aa336e5df6`.
- Repair4 54-execution ledger SHA-256:
  `0ca2e0635a8cb572912aeb19156a388c9a87ba8bc0f340998a6b39eb2b28c3fd`.
- Query-free prefix-verification execution:
  `atlas-md-prefix-r4-smoke-h59tz`.
- Smoke execution, metadata, log and hash-ledger SHA-256 values:
  `353e9c4fd2941b53e7216e69092c66f10be15b30ee130258a3865e788018172e`,
  `3be5d89960c565d9a8a1e45fab9e17b890a65d42b8ef5f521863925954e4dc25`,
  `9d65901ba07b3c6b831766aa2257461162ecbff8a308a5b77b3af792f9b7af4e`
  and
  `a8bc626accdf1b64fe8f06a287ba68caa2f96f3e6a0c415e961b6cc9756428d0`.
- Population: the exact 54 cells in the frozen ledger, covering 2023--2025
  Weeks 1--18 once each. No replacement, retry or effective-execution ledger
  is permitted.
- Per-cell resources: 4 CPU, 16 GiB, zero retries and 43,200-second timeout.
- Interaction auxiliaries remain binary. The later continuous-integrality
  optimization is not part of this upstream.

The exact 54 execution names and expected object URIs are authoritative from
the ledger. The downstream receipt must bind that file byte-for-byte rather
than reproduce or select identities from a broader Cloud Run listing.

## Strict-harvest gate

Historical scoring is permitted only after the existing strict repair4
finisher validates all 54 exact executions as terminal successful, validates
their image, command, environment, resources and service account, downloads
the exact 54 create-only shard objects, and writes a mechanically valid
54-slate aggregate.

The downstream launch must bind byte hashes for all of these completed
artifacts:

- `manifest.txt`, `executions.txt`, `completion.txt` and `report.json`;
- `season-2023.json`, `season-2024.json` and `season-2025.json`;
- `shards.sha256` and all 54 exact shard object generations and hashes; and
- `execution-metadata.sha256` and all 54 exact execution metadata records.

Those terminal artifact hashes and object generations do not yet exist at the
time of this amendment. Recording them mechanically after strict harvest does
not select a scientific result: the scorer must run after any valid repair4
disposition, whether the score-free gate passes or fails. A failed or
incomplete repair4 harvest produces no historical score run.

The new upstream receipt version must not contain repair2's failed-execution,
failed-log, replacement-execution or CBC-retry fields. Their absence is part
of the repair4 identity, not an invitation to accept alternate executions.

## Unchanged scoring law

Every scoring rule in the original protocol remains fixed, including equal
P1/P2 candidate budgets, unchanged order-invariant CBWU-OI construction,
unchanged 194-support exact-80 selection, all 54 slates and exact player-score
source parity. The high-tail amendment remains controlling: a positive label
requires at least two additional selected weeks at 200, no selected decline at
210, 220, 230 or 240, no candidate-pool decline at 200, and complete mechanical
validity.

No repair4 score-free statistic, partial shard, candidate identity, realized
score or threshold count may be inspected to alter the scorer, rule or decision
boundary. The result remains retrospective evidence for the already-declared
2026 shadow and cannot by itself change production.
