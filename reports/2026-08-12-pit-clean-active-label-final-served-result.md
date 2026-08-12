# PIT-clean active-label final-served result

The repaired v2 active-only-label treatment **passes** its frozen score-free
gate. This licenses exactly one already-frozen paired exact-80 lineup
comparison; it does not itself select active-only labels or mutate production.

## Immutable run

- Execution: `tabpfn-active-label-final-served-v2-mbs5t`
- Audit image digest:
  `sha256:aec3c368dd493b166f99b444f06dc87b892d2220e4b0e544aa7314b9f03bd9a6`
- Code: `23da1dd`
- Repaired selected panel: `20260811-pitclean-e80-k1-role12union-a12ab31`
- Usage: fitted Dirichlet `K=28.154043586960896`
- Caches: validated write-once v2 current-label control and active-only
  treatment, 52,307 equal target rows each
- Evaluation: 13,876 active RB/WR/TE rows over 54 2023--2025 slates

The raw log and complete report are under
`reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v2-pit-clean/`.

## Gate and diagnostics

| aggregate metric | current-label control | active-only treatment | treatment - control |
|---|---:|---:|---:|
| 30-point Brier (primary) | 0.0140557446 | 0.0140065605 | **-0.0000491841** |
| 20-point Brier | 0.0495149643 | 0.0494353120 | -0.0000796523 |
| CRPS | 2.6292865002 | 2.6041234883 | -0.0251630119 |
| point MAE | 3.6546548778 | 3.6328205058 | -0.0218343721 |

The primary Brier-30 improvement and mean-preservation requirement both pass.
Brier-30 also improves in every evaluation season:

| season | control | treatment | treatment - control |
|---|---:|---:|---:|
| 2023 | 0.0146616694 | 0.0146108827 | -0.0000507867 |
| 2024 | 0.0130459005 | 0.0130305180 | -0.0000153825 |
| 2025 | 0.0144488956 | 0.0143676624 | -0.0000812332 |

These secondary improvements are encouraging but do not replace the portfolio
tail objective. The licensed exact-80 comparison must now decide at
`240,230,220,210,200,194,187`, first nonzero treatment-minus-control count;
mean weekly maximum is consulted only after a complete count tie.
