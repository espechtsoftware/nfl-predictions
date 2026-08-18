# Selected-book tail calibration result

Date: 2026-08-17

Protocol: `20260817-selected-book-tail-calibration-v1`

This is a retrospective diagnostic of the already-selected CBWU exact-80 book.
It did not fit or tune a model, choose an arm, define a promotion gate, license a
production change, or permanently close a research direction.

## Frozen identities

- Source report:
  `reports/multiseed-candidate-world-runs/20260813-multiseed-candidate-world-v1/report.json`
- Source SHA-256:
  `a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239`
- Result:
  `reports/book-tail-calibration-runs/20260817-selected-book-tail-calibration-v1/report.json`
- Result SHA-256:
  `d3ca53303e195e66a6e476bfab830b4246595a1151a6d61054621a42fe78b628`
- Population: 54 slates, exactly 18 in each of 2023--2025, 50,000 simulated
  worlds per selected book.
- Exact-80 count is transitively attested by the pinned mechanically passing
  source and its five seed counts. The compact source intentionally omitted
  ordered roster identities, so this audit did not revalidate roster membership.
- Uncertainty: 10,000 deterministic within-season-stratified slate resamples,
  seed `20260817`.

## Aggregate result

`Mean q` is the average simulated probability that the selected 80-lineup book
would clear the threshold. `Expected` is `54 * mean q`. Brier skill is relative
to a leave-one-season-out prevalence forecast.

| Threshold | Realized | Mean q / expected | Brier skill (95% CI) | ROC AUC (95% CI) | AP / prevalence |
|---:|---:|---:|---:|---:|---:|
| 187 | 17 / 54 (31.5%) | 29.6% / 16.01 | +0.044 (-0.050, 0.206) | 0.571 (0.408, 0.728) | 0.365 / 0.315 |
| 194 | 8 / 54 (14.8%) | 19.0% / 10.26 | +0.009 (-0.243, 0.154) | 0.630 (0.410, 0.839) | 0.231 / 0.148 |
| 200 | 7 / 54 (13.0%) | 12.1% / 6.53 | +0.022 (-0.083, 0.167) | 0.635 (0.392, 0.861) | 0.218 / 0.130 |
| 210 | 6 / 54 (11.1%) | 5.1% / 2.76 | -0.022 (-0.091, 0.125) | 0.670 (0.392, 0.905) | 0.221 / 0.111 |

Every Brier-skill interval crosses zero and every ROC-AUC interval crosses 0.5.
The simulator therefore has not demonstrated reliable selected-book calibration
or discrimination on 54 slates. The point AUC and average precision values at
194--210 are nevertheless above chance/base prevalence, so the evidence also
does not support the stronger claim that the simulator is useless.

The largest visible calibration miss is at 210: six slates cleared the threshold
against 2.76 expected from the simulated probabilities. At 194 the direction is
reversed (eight observed against 10.26 expected), while 187 and 200 are close in
aggregate. With only 6--17 events per calibration threshold, these discrepancies
are diagnostic clues rather than licenses to fit a correction on the same data.

The simulated q95/q99 weekly-book maxima also have only weak association with
the realized selected maximum:

- q95: Pearson 0.169 (95% CI -0.048, 0.382); Spearman 0.158
  (95% CI -0.111, 0.411).
- q99: Pearson 0.171 (95% CI -0.044, 0.382); Spearman 0.166
  (95% CI -0.102, 0.423).

All four intervals cross zero. Season rows are heterogeneous: 2023 is near zero
or negative, 2024 is the strongest positive season, and 2025 is weakly positive.

The sparse thresholds remain descriptive only: 220 had three realized events
(mean simulated coverage 1.93%), 230 had one (0.69%), and 240 had none (0.28%).

## Consequence

1. Do not use simulated book coverage as the sole promotion, rejection or
   permanent-closure criterion.
2. Retain simulation as a weak ranking/diagnostic input; the point AUC/AP and
   previously valid candidate-level associations are inconsistent with a
   literal zero-signal conclusion.
3. Prioritize upstream marginal/dependence calibration and a separate,
   same-context paired arm-transport audit (`delta simulated coverage` versus
   `delta realized tail`) over another broad construction sweep.
4. Collect the same probabilities and realized book outcomes prospectively in
   2026. That out-of-sample record is more valuable than fitting these 54 slates.
5. The production policy remains unchanged. This audit licenses no production
   change and does not block the Week 1 operational-readiness lane.

## Independent validation

An independent stdlib-only implementation recomputed every aggregate and
by-season point metric without importing the audit module, NumPy, SciPy or
scikit-learn. It found zero mismatches (maximum absolute floating-point delta
`4.44e-16`), verified the exact source/result hashes and canonical JSON, checked
all 594 book seed-count receipts and 54 CBWU/C0W0 candidate-budget equalities,
and confirmed that every bootstrap finite-plus-undefined count equals 10,000
with ordered, bounded intervals.
