# Median-line yardage conversion (MARKET_LINE_MEDIAN): 2023-24 fit, 2025 out of sample

Requested by production in HANDOFF `de3042c0`. Branch `laptop/market-bonus-aware-20260923` @ `c07ba976` (default off; a value
other than 0/1 fails closed; flag off is byte-identical by test; the bonus from `MARKET_BONUS_AWARE` comes from the same gamma).

## Law choice (fit 2023-24; `reports/lab-handoffs/2026-09-23-line-median-{extract,law-fit}.py`)
The law is anchored at the line: P(Y > line) = the de-vigged p_over. Its shape is `exp(a + b·ln line)`, fitted by least squares on mean yards.
The shape must vary with the line: a constant-shape (ratio) correction leaves ±3-yard band residuals, while the realized gap is
roughly additive (+4 yards at every line level). **Gamma beat lognormal** on 2023-24 tail calibration (Brier at 50/75/100/125 yards)
in both markets, and also in 2025. Constants: receiving (−1.4142, 0.6436), i.e. shape 1.07 / 2.17 / 3.39 at lines 10 / 30 / 60;
rushing (−1.1398, 0.7652).

Yards per line, 2025 out of sample:
| market | actual mean | normal gap | gamma gap | P(≥100) predicted / realized, normal → gamma |
|---|---:|---:|---:|---|
| receiving | 33.96 | +2.54 | **−2.64** (overshoot) | 0.010 → 0.050 / 0.053 |
| rushing | 38.61 | +3.04 | **+0.53** | 0.027 → 0.043 / 0.066 |

The receiving overshoot is a season effect: the gap was +5.7 / +4.6 / +2.5 yards in 2023 / 24 / 25. I did **not** retune on 2025.

## DK-point table (`reports/lab-handoffs/2026-09-23-line-median-bias-check.py`, verbatim)
```

=== FIT 2023-24 (player-weeks 4534) ===
pos  band   n  bias_plain  bias_bonus  bias_median  bias_both   se  mae_plain  mae_bonus  mae_median  mae_both
 QB  6-10   1       -3.42       -3.42        -3.42      -3.42  NaN      3.419      3.419       3.419     3.419
 QB 10-14  83        0.70        0.70         0.55       0.55 0.88      6.423      6.423       6.432     6.432
 QB 14-18 335       -0.19       -0.19        -0.37      -0.37 0.41      5.969      5.969       5.991     5.991
 QB   18+ 200        0.07        0.07        -0.16      -0.17 0.57      6.360      6.360       6.362     6.362
 RB  6-10 243        0.76        0.75         0.15       0.12 0.38      4.471      4.470       4.526     4.527
 RB 10-14 328        1.17        1.13         0.46       0.31 0.42      5.972      5.974       6.027     6.038
 RB 14-18 229        1.41        1.17         0.64       0.22 0.57      6.971      6.933       6.920     6.894
 RB   18+  42        0.56       -0.01        -0.26      -1.02 1.26      6.894      6.830       6.914     6.957
 TE  6-10 339        1.17        1.17         0.64       0.58 0.36      4.984      4.984       4.994     5.001
 TE 10-14 121        1.02        1.02         0.42       0.16 0.71      6.215      6.215       6.275     6.303
 TE 14-18  15        0.28        0.17        -0.39      -0.96 2.42      7.382      7.426       7.520     7.681
 TE   18+   2      -10.55      -11.10       -11.24     -12.19 4.38     10.548     11.101      11.244    12.188
 WR  6-10 612        1.16        1.16         0.61       0.51 0.27      4.998      4.998       5.046     5.057
 WR 10-14 490        1.81        1.80         1.18       0.82 0.40      6.813      6.813       6.823     6.847
 WR 14-18 221        2.05        1.80         1.36       0.65 0.68      7.869      7.866       7.860     7.896
 WR   18+  63        2.44        1.44         1.70       0.49 1.31      8.339      8.252       8.292     8.309

=== OUT-OF-SAMPLE 2025 (player-weeks 2257) ===
pos  band   n  bias_plain  bias_bonus  bias_median  bias_both   se  mae_plain  mae_bonus  mae_median  mae_both
 QB 10-14  52        0.35        0.35         0.17       0.17 1.17      6.449      6.449       6.453     6.453
 QB 14-18 170        0.05        0.05        -0.14      -0.14 0.59      6.061      6.061       6.078     6.077
 QB   18+ 110       -0.19       -0.19        -0.42      -0.42 0.72      5.827      5.827       5.828     5.828
 RB  6-10  92        1.05        1.05         0.49       0.46 0.75      5.150      5.149       5.301     5.302
 RB 10-14 138        1.01        0.96         0.31       0.15 0.67      5.873      5.881       5.989     6.028
 RB 14-18  96        0.81        0.45         0.07      -0.46 0.89      6.767      6.841       6.863     7.006
 RB   18+  40        2.54        1.95         1.72       0.92 2.01      9.944     10.005       9.970    10.044
 TE  6-10 215        0.58        0.58         0.05      -0.02 0.43      4.737      4.737       4.806     4.819
 TE 10-14  72       -0.82       -0.82        -1.41      -1.67 0.81      4.943      4.945       5.109     5.212
 TE 14-18   7        3.29        3.18         2.63       2.04 4.31      8.315      8.312       8.224     8.164
 TE   18+   1        4.17        3.50         3.48       2.46  NaN      4.174      3.503       3.476     2.463
 WR  6-10 293        0.14        0.14        -0.41      -0.51 0.39      5.054      5.054       5.205     5.236
 WR 10-14 241        0.57        0.55        -0.06      -0.41 0.51      6.167      6.170       6.252     6.330
 WR 14-18  96        1.01        0.76         0.34      -0.37 0.92      7.181      7.207       7.220     7.334
 WR   18+  27        2.57        1.62         1.82       0.65 2.09      8.608      8.357       8.392     8.159
2023 WR/RB/TE bias plain +1.23  bonus +1.18  median +0.67  both +0.49  | MAE plain 5.164  bonus 5.159  median 5.189  both 5.196  | MSE plain 51.10  bonus 50.87  median 50.03  both 49.67  (n 1890)
2024 WR/RB/TE bias plain +1.15  bonus +1.08  median +0.58  both +0.38  | MAE plain 5.193  bonus 5.190  median 5.222  both 5.235  | MSE plain 50.21  bonus 50.03  median 49.19  both 48.99  (n 2025)
2025 WR/RB/TE bias plain +0.75  bonus +0.68  median +0.20  both +0.01  | MAE plain 5.152  bonus 5.156  median 5.236  both 5.270  | MSE plain 50.35  bonus 50.24  median 49.92  both 49.95  (n 1925)
MAE favours medians; MSE is the proper loss for a mean projection.
```

## Reading
- **Bias:** the WR/RB/TE level gap closes out of sample: 2025 +0.75 plain → +0.20 median → **+0.01 both**.
  In 2023-24 (in-sample) it goes from +1.2 to +0.4–0.5.
  The 2025 WR 6-10 / TE 10-14 bands now read slightly negative (−0.4 / −1.4 ± 0.4 / 0.8).
- **MSE improves in every season** (2025 out of sample: 50.35 → 49.92 median, 49.95 both). **MAE worsens**, as it must:
  MAE is minimized by the median, and this change moves a median-anchored number to a mean. For a projection that feeds
  mean-based simulation and the blend, MSE is the right loss. I flag MAE only so nobody reads the rise as a regression.
- **QB** moves −0.15 to −0.2 through the rushing leg; still within noise.
- **Adoption:** as production said, the lineup-level replay decides. I recommend testing **both** flags together (the
  unbiased 2025 arm). I can queue it on the laptop after L01 and the paper triple, or production can run it on Cloud Run.

## Addendum (same day): 2026 Weeks 1–2, a second out-of-sample check
The same bias check restricted to `season = 2026 AND week <= 2` (449 player-weeks; WR/RB/TE n 386, small):
```
2026 WR/RB/TE bias plain +0.62  bonus +0.57  median +0.06  both -0.11  | MAE plain 5.071  bonus 5.060  median 5.173  both 5.191  | MSE plain 49.84  bonus 49.46  median 49.38  both 49.02  (n 386)
```
It points the same way: the level gap closes and MSE improves. As in 2025, the low WR bands now read slightly negative
(WR 6-10 −0.67 ± 0.75).
