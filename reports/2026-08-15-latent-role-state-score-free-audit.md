# Latent role state: score-free transition audit

Date: 2026-08-15  
Protocol: `reports/2026-08-15-prospective-latent-role-state-protocol.md`  
Implementation: `86788eafd2302d61e5e40c82989f09976d74f936`  
Source-query SHA-256:
`9d4399033487e2c62d31e92126a42802f5ae829dbf4cff7e65749cb908115bd9`

## Boundary

This audit selected usage, snap, pre-lock injury/practice and team-vacancy
columns only. The source query contains no fantasy-point, lineup-score,
selection, winner, payout or ROI column, and the code rejects a returned frame
that contains any registered outcome column. No 2019--2025 lineup outcome was
queried or used.

This is a prerequisite result only. It can license implementation of the
prospective role-state candidate shadow; it cannot promote a lineup policy.

## Data and state support

The exact score-free warehouse query produced 62,155 labeled RB/WR/TE
player-weeks over 2018--2025:

| State | Rows |
|---|---:|
| inactive | 23,001 |
| dormant | 7,152 |
| rotation | 21,107 |
| secondary | 5,057 |
| primary | 5,838 |

The classifier left active rows with missing realized snap/opportunity data
unlabeled rather than treating missing source data as inactivity. Predictors
are strictly prior role usage plus timestamp-qualified same-week availability;
the realized Week-W state is used only as the transition label.

## Expanding-season results

The frozen multinomial model was compared with the protocol's Dirichlet-one
empirical `position x previous_state` transition table. Lower is better.

| Evaluation season | Train rows | Test rows | Model log loss | Baseline log loss | Model Brier | Baseline Brier |
|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 31,018 | 10,388 | 0.693266 | 0.827061 | 0.359741 | 0.413707 |
| 2024 | 41,406 | 10,437 | 0.673648 | 0.810262 | 0.350232 | 0.405198 |
| 2025 | 51,843 | 10,312 | 0.741758 | 0.804337 | 0.380488 | 0.404500 |
| test-row weighted | -- | 31,137 | 0.702750 | 0.813904 | 0.363425 | 0.407806 |

The model beats the empirical baseline on both metrics in every held-out
season. The advantage narrows in 2025, where the upstream final injury file has
no usable modification timestamps and those availability fields correctly
remain missing, but it does not reverse.

## Disposition

The protocol's score-free prerequisite passes. The discrete transition stage
is nondegenerate, retains all five states, returns a valid canonical
probability simplex, is deterministic on repeated fits and improves both
required calibration losses out of sample.

This licenses the next engineering steps only:

1. persist a checksum-bound transition artifact with exact fit boundary and
   source identities;
2. implement state-conditional role frames and team share-cap rejection;
3. replace exactly the 12 incumbent direct-role candidates in a separately
   named control/treatment shadow; and
4. perform a score-free live-slate parity smoke before adding any scheduler.

The K=1 CBWU exact-80 money baseline remains unchanged. No historical exact-80
test of this mechanism is licensed.
