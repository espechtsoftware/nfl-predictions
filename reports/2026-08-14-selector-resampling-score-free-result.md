# Score-free selector world-resampling result

Date: 2026-08-14. Complete report:
`reports/selector-resampling-runs/20260814-selector-resampling-v1/report.json`.
This diagnostic queried no realized outcome, player actual, standing or payout.
It reproduced every persisted Phase S treatment R0 exact-80 book before
resampling.

## Result

Mean exact-80 pairwise overlap across the 32 fixed bootstrap books is
`61.6362/80`, inside the preregistered **intermediate** band. The 5th/50th/95th
percentiles of slate-level mean overlap are `57.1640/61.5383/65.8260`.
All three seasons are intermediate:

| season | bootstrap overlap | disjoint-half overlap |
|---:|---:|---:|
| 2023 | 61.9178 | 55.2778 |
| 2024 | 62.6688 | 54.2778 |
| 2025 | 60.3221 | 53.2778 |
| all | 61.6362 | 54.2778 |

Across slates, an average `45.15` candidates are selected in at least 90% of
bootstrap books, `29.80` in 50%--under-90%, and `90.57` at positive but below
50% frequency. Reciprocal selection-half minus validation-half union coverage
optimism averages `0.01275` (about 1.28 percentage points).

Mean pairwise prefix overlap is `0.59/3.13/6.49/13.58/29.08/45.12/61.64` at
prefixes `1/5/10/20/40/60/80`. The exact ordering near the top is therefore
less stable than the broad membership of the 80-entry book.

## Disposition

The result has no adoption authority and does not license bootstrap-mean
bagging, which is algebraically the existing empirical objective plus finite
sampling noise. Record intermediate selector measurement instability and the
roughly 1.28-point coverage optimism in the final forensic opportunity
register.

The independently frozen multi-seed candidate/world factorial is the relevant
production experiment because its world-union cells provide genuinely new
world information. Interpret its complete result against this measured
within-R0 instability; do not invent a post-hoc penalty or selector.
