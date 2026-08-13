# PFR secondary feature ablation result

Status: terminal score-free rejection. No exact-80 lineup comparison is
licensed by this result.

## Result

The deterministic transport rerun completed as Cloud Run execution
`tabpfn-pfr-secondary-final-served-v1-w4k8f`. Its chunked report passed the
compressed and uncompressed checksum contract and exactly reconstructed the
complete machine report under
`reports/tabpfn-pfr-secondary-runs/20260813-tabpfn-pfr-secondary-final-served-v1/`.

All three registered feature-drop arms preserved final-served means within
`7.11e-15`, but all three worsened the primary aggregate active-player
30-point Brier score (lower is better):

| Arm | Brier-30 | Treatment - control |
|---|---:|---:|
| Control | 0.017203317646 | -- |
| Drop three secondary rates | 0.017206737888 | +0.000003420242 |
| Drop `top_cb_out` | 0.017215124047 | +0.000011806401 |
| Drop all four fields | 0.017225317768 | +0.000022000121 |

The paired slate-cluster 95% intervals for those Brier-30 deltas were,
respectively, `[-0.0000164111,+0.0000232516]`,
`[-0.0000030054,+0.0000266182]`, and
`[-0.0000044287,+0.0000484289]`. None satisfies the frozen point-estimate
improvement gate. The machine disposition is
`tabpfn-pfr-secondary-final-served-no-eligible-drop`.

## Decision

Retain `cb_ypt_allowed_l6`, `cb_comp_rate_allowed_l6`,
`db_ypt_allowed_l6`, and `top_cb_out` in the current feature contract. Close
these exact three ablations without reading lineup scores or tuning a subset
from the observed result. This does not validate the fields as causal, and it
does not answer the distinct named WR/CB assignment or coverage-shell
questions; it only shows that removing the registered blocks did not improve
the current final-served 30-point probability forecast.
