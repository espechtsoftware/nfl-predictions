# Active-only usage-allocation revalidation result

Date: 2026-08-12 CDT. The frozen standing-law comparison is valid and retains
finite-K Dirichlet usage allocation for the active-only terminal book.

## Frozen decision

Across the unchanged 107-slate book, selected weekly maxima are:

| Threshold | Multinomial | Finite K | Delta |
|---:|---:|---:|---:|
| 240 | 2 | 2 | 0 |
| 230 | 2 | 2 | 0 |
| 220 | 2 | 2 | 0 |
| 210 | 4 | 6 | +2 |
| 200 | 10 | 14 | +4 |
| 194 | 19 | 23 | +4 |
| 187 | 35 | 35 | 0 |

The first nonzero difference in the registered order
`240,230,220,210,200,194,187` is the two-week finite-K gain at 210. Therefore
the selected allocation remains `dirichlet` with
`K=28.154043586960896`. The selected panel remains
`20260812-pitclean-e80-selected-tabpfn-active-v2` and the active cache remains
`tabpfn_active_label_treatment_v2`.

Mean weekly maximum also improves slightly over multinomial
`176.70243 -> 176.86916` (+0.16673), while median declines
`177.30 -> 175.42` (-1.88). Those are disclosures, not the frozen selector.

## Evaluation-panel disclosure

On the 54 changed 2023--2025 slates alone, finite K versus multinomial is:

- 210: `0 -> 2`; 200: `2 -> 6`; 194: `4 -> 8`; 187: `11 -> 11`;
- mean weekly maximum: `170.57667 -> 170.90704` (+0.33037);
- median weekly maximum: `170.13 -> 166.49` (-3.64); and
- 26 weeks favor finite K, 26 favor multinomial, and two tie on selected best.

Ten weeks cross at least one registered threshold. Seven have only finite-K
gains, while three lose only the 187 line. Twenty-five weeks have an absolute
selected-best difference of at least ten points: twelve favor finite K and
thirteen favor multinomial. Multiple threshold gains are sometimes supplied
by the same week; the complete paired crossings and weekly deltas are retained
in `comparison.json` and cannot be counted as independent evidence.

The two books share only 288 of 4,320 selected evaluation lineups. Candidate
auditing found 3,611 common candidates across all 54 slates, identical common
actuals, and common simulated means within the registered `1e-4` tolerance
(maximum absolute delta `3.0518e-5`). This is a materially different
allocation/book, not a cosmetic reranking.

## Validity and limits

- Final independent panel acceptance:
  `accept-replay-panel-4299w`.
- Image-entrypoint preflight:
  `compare-active-label-usage-preflight-v3-vkg6n`.
- Sole valid comparator:
  `compare-active-label-usage-revalidation-v3-8kzc6`.
- Exact-tree Cloud Build:
  `f0b7a163-86c1-4e9e-9a39-2adf43880659`, 1,018 tests passed with two
  expected skips.
- Immutable audit image:
  `sha256:f77377c4ce6be26f36f3b2d3718a515a699e4613b3c1def274340dbe2741e59a`.

The finite-K treatment scores were known before this retrospective protocol;
the comparison is a required standing-law check, not independent discovery.
During the final acceptance rerun, ordinary acceptance output exposed the
multinomial evaluation-only 187/194/200 counts before the comparator; no
240/230/220/210 result or frozen selection was exposed, and no registered rule
changed. This observer deviation remains attached to the result.

No payout or ROI is inferred without full contest field ranks/scores and a
duplication/tie model. Invalid v1 packaging and v2 pre-score validation
executions remain preserved with their licensed operational repairs.

## Consequence

The finite-K terminal law evaluated by G0/G1 is retained. Their
`stable-qb-hub-confirmed` result therefore remains applicable and directly
licenses the preregistered G2 dependence branch; no multinomial G0/G1 rerun is
required first.
