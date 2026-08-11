# Advanced Receiving same-season diagnostic result

Run once on 2026-08-11 CDT under the frozen protocol in
`2026-08-11-advanced-receiving-same-season-diagnostic.md`. The implementation
was committed and pushed as `5aee8aa` before target outcomes were queried.
The hash-locked source was the 108-export recovery collection
`20260811T155845Z__same-season-advanced-receiving-support-windows-v1`.

## Result

Disposition: **fails; close this exact Advanced Receiving family**.

The evaluation had 6,710 supported held-out WR/TE rows and 101 realized
30-point events, so both minimum-support gates passed. The treatment nevertheless
failed all three primary accuracy gates:

| metric | control | treatment | treatment/control | result |
|---|---:|---:|---:|---|
| CRPS | 3.009499 | 3.014598 | 1.001694 | fails required <=0.995 |
| residual MAE | 3.976948 | 3.988477 | 1.002899 | fails non-worsening |
| equal-fold q95/q99 pinball ratio | — | — | 0.999835 | fails required <=0.995 |

CRPS and MAE worsened in each of 2023, 2024 and 2025. The paired
week-clustered treatment-minus-control intervals were also wholly unfavorable:

- CRPS: +0.004926, 95% interval +0.001829 to +0.008059;
- MAE: +0.011640, 95% interval +0.005517 to +0.017644.

Upper-tail and rare-event safeguards did not reveal an offsetting benefit.
Aggregate q95 pinball improved only 0.048%, q99 pinball worsened 0.018%, and
the frozen equal-fold combined improvement was far below the required 0.5%.
Thirty-point Brier was effectively unchanged but slightly worse
(0.01407425 to 0.01407660); its clustered interval crossed zero. Aggregate
q95/q99 exceedance moved from 5.618%/1.311% to 5.678%/1.297% and stayed within
the calibration safeguards.

## Consequence

The fixed cumulative-plus-last-four TPRR, YPRR and XFP-per-route signal does
not license a candidate or exact-80 lineup consequence. There will be no
alternate route floor, recency scale, field subset, fold or threshold retry.
The normalized point-in-time table remains useful for the separately governed
2026 prospective operating path, but production and the current accepted
lineup baseline remain unchanged.

Machine-readable evidence:
`fantasy-points-diagnostic-runs/20260811-advanced-receiving-v1/diagnostic.json`.
