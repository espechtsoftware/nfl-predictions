# Constraint-lattice source and execution amendment

Date frozen: 2026-08-16, before any constraint-lattice Cloud execution or
result existed and while the ATLAS 32-GiB binary full-cell preflight remained
nonterminal.

Applies to: `20260816-constraint-lattice-scorefree-v1`.

This amendment resolves source and transport identities that the original
protocol described semantically but did not name. It changes no constraint
cell, quota, candidate rank, swap rule, held-out measurement or gate.

## Exact source binding

The five native books are the exact passed CBWU-OI source panels, in canonical
block order:

- R0: `20260813-sis-asoe-treatment-r0-v1`
- R1: `20260813-sis-asoe-treatment-r1-v1`
- R2: `20260813-sis-asoe-treatment-r2-v1`
- R3: `20260813-sis-asoe-treatment-r3-v1`
- R4: `20260813-sis-asoe-treatment-r4-v1`

Candidate identities and artifact URIs/hashes come only from
`nfl-predictions-503414.nfl_predictions.replay_candidates_staging`.
Player identity, position, team, opponent, game, salary and pre-lock mean come
only from
`nfl-predictions-503414.nfl_forensic_review.final_forensic_20260814_player_corpus_repair4`
with manifest SHA-256
`51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`.
The passed CBWU-OI report is
`reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json`,
SHA-256
`556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33`.

Every shard must revalidate all five panel rows, artifact hashes and object
generations for its slate. Queries may not name realized score, actual rank,
actual ownership, selection labels, payout, contest rank or label-completeness
fields.

## Exact transport

- Run ID: `20260816-constraint-lattice-scorefree-v1`.
- Create-only GCS prefix:
  `gs://nfl-predictions-503414-raw/research/constraint-lattice-runs/20260816-constraint-lattice-scorefree-v1`.
- Population: exactly 54 independent season/week executions for 2023--2025
  Weeks 1--18. Each execution runs all five held-out folds for one slate.
- Resources: 4 CPU, 16 GiB, zero retries and a 12-hour task timeout.
- Each job must use one immutable image digest and one full 40-character source
  commit. The image must pass the complete repository test suite and a real-
  container `--help` smoke for the exact runner before launch.
- Execution names, output URIs and source-artifact generations are immutable
  and create-only. No failed cell may be replaced under this run ID.

The runner emits outcome-free fold-completion markers only after a fold is
fully constructed and measured. These markers may be used for progress and
runtime monitoring; they carry no result metric.

## Strict harvest

The finisher may run only after all 54 exact executions are terminal successful.
It independently validates command, image, code, service account, resources,
retry/timeout policy, output generation/hash, exact 54-slate/five-fold grid,
protocol/amendment/source-report hashes, source artifact receipts, exact-80
mechanics and absence of outcome fields. It then invokes the frozen aggregate
gate once over all 270 held-out folds.

Any missing, failed, replaced or malformed cell invalidates the population and
produces no scientific disposition. A valid gate pass licenses only the
separately labeled 2026 pre-lock shadow already allowed by the original
protocol; it never changes production or licenses historical scoring.
