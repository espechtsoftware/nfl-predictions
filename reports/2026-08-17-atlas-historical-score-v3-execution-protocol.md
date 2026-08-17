# ATLAS historical-score v3 execution protocol

Frozen: 2026-08-17, while the repair5 score-blind grid was nonterminal and
before any repair5 shard body, score-free effect or repair5 historical score
was opened.

This protocol implements the already-frozen
`20260816-atlas-historical-score-diagnostic-v3` release. It changes no ATLAS
mechanism, candidate budget, exact-80 selector, realized-score source, scoring
threshold or consequence boundary.

## Immutable source boundary

The scorer may launch only after the repair5 attempt-aware strict finisher has
produced a valid 54-slate completion. A score-blind source sealer must then:

- validate every repair5 protocol, canary, validator-repair, primary-attempt,
  accepted-attempt and strict-harvest receipt byte-for-byte;
- validate all 54 primary and accepted execution contracts and any permitted
  replacement binding;
- enumerate every execution owned by each of the 54 jobs and reject any
  unreceipted extra execution, including a second canary;
- validate every local `sha256sum` ledger and its exact artifact population;
- bind the exact GCS generation, byte count and SHA-256 of all 54 shards,
  three season aggregates and the aggregate report without parsing an ATLAS
  effect field; and
- upload one create-only `atlas-historical-upstream-receipt-v5` object under
  the v3 historical prefix.

The historical scorer receives that receipt's exact URI, generation and
SHA-256 as command arguments and downloads that generation explicitly. It
downloads every score-blind aggregate by its bound generation and must
revalidate the complete receipt before querying a realized outcome.

## Historical execution

- Run ID: `20260816-atlas-historical-score-diagnostic-v3`.
- Job: `atlas-historical-score-v3`.
- Output:
  `gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3/report.json`.
- One task, parallelism one, 8 CPU, 32 GiB, zero task retries and an
  eight-hour timeout.
- The image must be an immutable digest produced by a successful full-test
  Cloud Build from the exact recorded 40-character code commit.
- `CODE_SHA` and `ANALYSIS_IMAGE` are the only environment variables.
- The shared historical-outcome lease must be acquired before launch and may
  be released only after a terminal execution and strict completion receipt.

The scorer uses the original registered source candidates and player outcomes,
reconstructs P1 and P2 exactly, requires byte-identical upstream exact-80
indices and roster identities, and requires exact parity between registered
candidate actual scores and sums of nine player outcomes. It scores all 54
2023--2025 Week 1--18 slates. Partial population scoring is forbidden.

## Frozen diagnostic and consequence

The controlling tail-first gate remains exactly:

1. at least two additional P2 exact-80 weeks at 200;
2. no P2 exact-80 decline at 210, 220, 230 or 240;
3. no P2 candidate-pool decline at 200; and
4. complete mechanical, source-parity and strict-harvest validity.

The report must additionally retain per-slate candidate and exact-80 maxima,
threshold crossings, P1/P2 overlap, ATLAS candidate-to-selection conversion,
season splits and leave-one-slate-out influence. These diagnostics distinguish
a candidate/world-law limitation from an exact-80 selection limitation; they
do not relax the gate.

The result is retrospective evidence for prospective shadow design only.
`production_change_licensed` remains false regardless of disposition. No
score, threshold count or diagnostic may alter this protocol after launch.
