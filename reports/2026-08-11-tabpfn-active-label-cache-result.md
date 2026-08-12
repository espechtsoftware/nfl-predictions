# TabPFN active-label cache result

The frozen same-code cache-generation stage passed every mechanical gate. This
result does not yet claim predictive or lineup-score improvement.

## Immutable executions

- Image:
  `sha256:1e6a57f60c962f155c227e3fa6b3e3691d10752935401b906a0f5db53b3f2d8a`
- Generator code: `82619ed`
- Control: `tabpfn-active-ctl-gh6f4`
- Active-only treatment: `tabpfn-active-trt-lj66c`

Both executions completed successfully from the same image and source-table
snapshot. The complete reports and validation are under
`reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v1/`.

## Mechanical result

- Both tables contain exactly 52,307 unique and identical 2022--2025
  `(season, week, gsis_id)` keys.
- Required mean/quantile columns are finite and ordered.
- Feature contract, source snapshot, target counts, seasons, TabPFN version,
  estimator count, context cap, device and seed match.
- Predictions changed between arms.
- Treatment sampled zero inactive labels in all four folds and retained the
  full 28,000-row active context cap.

The defect is material inside the control context. Sampled inactive synthetic
zero labels were 73 for the 2022 target, 2,860 for 2023, 4,409 for 2024, and
5,765 for 2025. Before the 28,000-row cap, cumulative eligible inactive labels
were 129, 6,331, 12,372, and 18,502 respectively.

## Terminal cache-stage result and next gate

The fitted-K comparison rejected finite K and fixed the common simulator law
as production multinomial. The sole frozen final-served execution
`tabpfn-active-label-final-served-h5jpq` then passed its aggregate active
RB/WR/TE 30-point Brier gate by `0.000010238`, while two of three individual
seasons declined. Full interpretation is tracked in
`reports/2026-08-11-tabpfn-active-label-final-served-result.md`.

This licenses one separately frozen exact-80 scoring comparison; it does not
promote either table. Do not inspect corrected-cache lineup scores until that
protocol is committed.
