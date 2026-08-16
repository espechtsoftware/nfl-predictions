# ATLAS deployment-set evidence index

**Purpose:** reviewer-facing map of the complete ATLAS/CBWU-OI/exact-N
deployment sequence. This file records positive findings, adverse findings,
evidence boundaries and immutable source locations so a second reviewer can
reproduce the conclusions without relying on a chat summary.

**Status:** open while production-law transfer execution
`atlas-current-money-transfer-v1-52smn` runs. Update this index with its strict
harvest and disposition before closing the deployment set.

## Findings at a glance

1. **ATLAS Phase S is strongly positive under its source simulation law.**
   Exact attainable legal world quality improves by `+12.8754` mean and
   `+14.8784` q25, with positive means in all five seed blocks. This is a
   score-free law-specific premise pass, not a production or realized-score
   gain.
2. **CBWU-OI produces a stronger fixed-budget candidate pool by realized C,**
   but the unchanged exact-80 selector is less reproducible under finite world
   resampling: `54.5787/80` versus canonical `61.1252/80` pairwise overlap.
   Candidate quality and selector stability are separate properties.
3. **Cardinality-aware exact-N ranking is positive for small books.** N=`1`,
   `3` and `20` pass the frozen outcome-free falsifier; N=`40` fails. The N=3
   relative 230-point simulated-coverage gain is `+7.23%`. These are 2026
   pre-lock shadow licenses only.
4. **Production-law world acquisition is mechanically complete.** All 15
   executions succeeded and all 270 artifact cells are bound. One cell uses
   the preregistered GCS recovery path after an ancillary BigQuery 429; its
   world artifact and successful execution passed every integrity check.
5. **The decisive production-law ATLAS transfer is pending.** It is the common-
   law comparison that determines whether the Phase S attainable-quality
   premise transfers to the current-money simulation law. No partial result
   will be interpreted.

## A. ATLAS Phase S score-free attainable-world test

- Frozen protocol:
  `reports/2026-08-15-atlas-world-ranking-scorefree-protocol.md`
- Human result:
  `reports/2026-08-15-atlas-scorefree-result.md`
- Raw result:
  `reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1/report.json`
- Execution receipt:
  `reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1/execution.json`
- Cloud Run execution: `atlas-world-ranking-scorefree-v1-l59bt`
- Result SHA-256:
  `014fbddb3b846ec84bea5fe05cafc5da66b9cd82ac44d80ee77c44f9f0a29119`
- Execution SHA-256:
  `76f7082c6dc848cd1ff846026deb49300e68cf497c8e300f8017e4638f8fc49c`
- Disposition: all six frozen conditions pass under the Phase S finite-K plus
  SIS-ASOE law; no production adoption licensed.

Key measurements:

| Measure | Control | ATLAS | Delta / ratio |
|---|---:|---:|---:|
| Mean exact attainable quality | 269.8262 | 282.7017 | +12.8754 |
| Mean q25 attainable quality | 261.2042 | 276.0826 | +14.8784 |
| Seed mean deltas R0--R4 | — | — | +12.8131 / +12.6841 / +12.9821 / +12.7718 / +13.1262 |
| Unique-roster reach ratio | — | — | 1.0000 |
| QB-stack-core reach ratio | — | — | 1.0044 |
| Game reach ratio | — | — | 0.9464 |

Non-gating post-result context: pair reach `1203.25 -> 1172.11` (ratio
`0.9742`) and QB-stack-core reach `38.83 -> 38.97` (ratio `1.0044`).

## B. Law-separation correction

- Supplied review:
  `reports/2026-08-16-atlas-law-separation-review.md`
- Reconciliation:
  `reports/2026-08-16-atlas-law-separation-review-reconciliation.md`
- Frozen transfer amendment:
  `reports/2026-08-16-atlas-transfer-law-separation-amendment.md`
- Simulation-law ledger:
  `reports/2026-08-16-simulation-law-ledger.md`
- Amendment SHA-256:
  `59326d6c8db4209a4eac44bbc80935adb8d93fb71a0b92a5d5325a30562fae54`

Correction retained for review: Phase S ATLAS and CBWU-OI used the same five
Phase S panels, not different simulation laws. They still cannot be ranked
against each other because they measure different endpoints. The
production-relevant causal contrast is P2 ATLAS versus P1 non-ATLAS under the
same current-money law; P2 versus P0 is composite context only.

## C. CBWU-OI selector-stability diagnostic

- Frozen protocol:
  `reports/2026-08-15-cbwu-oi-selector-stability-protocol.md`
- Pre-result interpretation amendment:
  `reports/2026-08-15-cbwu-oi-selector-stability-interpretation-amendment.md`
- Human result:
  `reports/2026-08-15-cbwu-oi-selector-stability-result.md`
- Raw result:
  `reports/cbwu-oi-selector-stability-runs/20260815-cbwu-oi-selector-stability-v1/report.json`
- Full compressed candidate frequencies:
  `reports/cbwu-oi-selector-stability-runs/20260815-cbwu-oi-selector-stability-v1/candidate-frequencies.json.gz`
- Execution receipt:
  `reports/cbwu-oi-selector-stability-runs/20260815-cbwu-oi-selector-stability-v1/execution.json`
- Cloud Run execution: `cbwu-oi-selector-stability-v1-sfdvb`
- Result / execution / frequency SHA-256:
  `d6d4055633b2f3202615cf637776b7724d3c2b1945789d9861d41902603896fe` /
  `e8aaae2b9fd08ac7ab9cacfa6ffba8090c58a50fdd64845ce3cc830e91ef5673` /
  `73b6a4086b157a82877321c8e093a6a683584386989975b316212ca075d01047`

Key measurements:

- CBWU-OI score-free 194 coverage is higher on all 54 slates, mean absolute
  delta `+0.05019`.
- Bootstrap pairwise exact-80 overlap: canonical `61.1252`, CBWU-OI `54.5787`,
  paired delta `-6.5466`.
- Disjoint-half overlap: canonical `65.6852`, CBWU-OI `60.8704`, paired delta
  `-4.8148`.
- This is an operational membership/order risk, not a C-to-S conversion
  estimate and not permission to tune the selector from historical results.

## D. Exact-N small-book diagnostic

- Frozen protocol: `reports/2026-08-15-exact-n-scorefree-protocol.md`
- Frozen source amendment:
  `reports/2026-08-15-exact-n-order-invariant-source-amendment.md`
- Human result: `reports/2026-08-15-exact-n-scorefree-result.md`
- Raw result:
  `reports/exact-n-scorefree-runs/20260815-exact-n-scorefree-v1/report.json`
- Execution receipt:
  `reports/exact-n-scorefree-runs/20260815-exact-n-scorefree-v1/execution.json`
- Cloud Run execution: `exact-n-scorefree-v1-jv7r4`
- Result / execution SHA-256:
  `2af0549c1880529d1c9380f28b8e9565c5ed3833db23f1b2bc128ddccea8b287` /
  `d501daa6cda79049a81319337a3029e0c53bab528f49a8e518d057e4079d8609`

| N | Target | Relative primary-coverage change | 194 retention | Blocks improving | Disposition |
|---:|---:|---:|---:|---:|---|
| 1 | 230 | +3.53% | 91.64% | 3/5 | pre-lock shadow |
| 3 | 230 | +7.23% | 90.07% | 5/5 | pre-lock shadow |
| 20 | 210 | +1.62% | 96.80% | 5/5 | pre-lock shadow |
| 40 | 200 | -0.05% | 98.60% | 1/5 | failed/closed |

## E. Production-law world acquisition

- Frozen transfer protocol:
  `reports/2026-08-15-atlas-current-money-transfer-protocol.md`
- Frozen artifact-native repair:
  `reports/2026-08-15-atlas-money-artifact-native-repair.md`
- Complete acquisition manifest, environment receipts, execution receipts,
  candidate grid and source grid:
  `reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/`
- Execution count: 15 successful
- Source grid: 270 cells, 54 common slates per panel
- Bindings: 269 `candidate_table`, 1 `gcs_artifact_recovery`
- Acquisition-complete / source-grid / candidate-grid SHA-256:
  `a29f773f35d4121db785fc5be2e1a18895f897bf91c248dd24c1566ace5c34cb` /
  `9a18458c63f0155b72f3847c705fbd0bdde9b64c923a5b63cc4a1f42bfe3445b` /
  `b18216ca8900b54381c3f5ed5031442143f2d5e1ee38c6ae193e2f5dfbc6bac0`
- Execution/environment receipt-list SHA-256:
  `ee73688bfe5662c94b6886ea5f90b3cfc87a5b7a038ada5511f48a260ea01377` /
  `eb88e6f35226034907869397c6efc9f25e09cb3173a3e40bbcfc952f87d74348`

The recovery cell is R3/2025 Week 1. Its replay execution
`replay-atlasmoney-r3-2025-htrch` succeeded. The GCS object was created inside
that execution's verified time window and independently passed object
generation, size, digest, array-shape, finite-value and player/candidate
identity validation. The repair does not excuse a failed execution or a
missing/malformed object.

## F. Current-money production-law transfer (pending)

- Run directory:
  `reports/atlas-money-transfer-runs/20260815-atlas-current-money-transfer-v1/`
- Cloud Run execution: `atlas-current-money-transfer-v1-52smn`
- Analyzer image digest:
  `sha256:b4f39a23a7a6b028bb174c34d5c54d1cf636e5711f87aa156dadf274c0797083`
- Exact image source commit:
  `d1b67b15b85cf09305c27bdaeca0ae93353e0208`
- Full validation build: `5106f00d-f58b-41f7-bbe0-e00be6497e08`
- Full suite: 1,580 passed, 2 skipped, 5 warnings in 749.02 seconds
- State: running; no partial output interpreted

When terminal, add here:

1. execution terminal state/runtime and strict execution receipt hash;
2. raw report path/hash and a human result report;
3. all three Part-A quality conditions separately;
4. law-dependent quality distributions and per-seed deltas;
5. mechanical validity separately from effect disposition;
6. bound slack, proxy/exact rank correlations, exact win/tie/loss counts,
   top-8/20/40 overlap and cutoff-tie diagnostics;
7. non-gating unique-roster, player-pair, QB-stack-core and game reach; and
8. exact consequence: close, continue to MVP, or prospective-only follow-up.

## Evidence firewall for reviewers

- Score-free results establish simulated-law premises, not realized DFS
  profits or historical ROI.
- No post-result target/threshold sweep is licensed.
- A law-specific Phase S pass does not establish transfer to current money.
- A source/mechanical failure and an effect failure must remain separately
  labeled.
- Any later realized-score MVP must use its own frozen protocol and compare
  ATLAS+CBWU-OI against incumbent+CBWU-OI so candidate construction is held
  constant.
