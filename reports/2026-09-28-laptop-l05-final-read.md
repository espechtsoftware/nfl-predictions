# PREREG-L05 final read: the chalk-core sleeve on lag-model labels

Laptop agent, read once on 2026-09-28 (05:46 CDT), with the frozen reader `scripts/l05_report.py` from a clean checkout of
lab `cb4fb33`.

**Inputs:**
- banks 1140 and 1141: production, lab `production/l05-early-results-1140-1141-20260925`;
- bank 1142 and the workstation's 1143: `production/l05-results-1142-1143-workstation-20260928` @ `5122a87`;
- the laptop's 1143: `laptop/l05-bank1143-results-20260925`;
- 144 slate-banks in all, every one with identity `cb4fb33`.

**Cross-host check:** bank 1143 is **identical on the workstation and the laptop, 36 of 36 slates,** on every
non-timing field (content comparison). The workstation's copy was read.

**Disclosure:** banks 1140–1141 were read early on 2026-09-25 under operator-directed AMENDMENT-L05-1 (lab `ef2fa56`).
That read found the lag arm not adoptable for Week 3. This is the second look at that pair and the first at 1142–1143.

## Reader output (verbatim)

```
identity cb4fb337df3b67380f80b90d7cc29f411b670bd2; 144 slate-banks over banks [1140, 1141, 1142, 1143]
season              arm   n  finish_share_above_best  book_best  book_mean  clears_194  clears_220  pool_oracle  overlap_vs_ctrl  low<=2_lag  chalk>=1_lag  low<=2_oracle  chalk>=1_oracle
  2023             CTRL  72                  0.02682     185.52     119.97          52           7       206.49             80.0       0.264         0.869          0.260            0.875
  2023    SLEEVE_L2_LAG  72                  0.02737     186.59     120.50          46           8       207.84             35.4       0.537         0.908          0.291            0.883
  2023 SLEEVE_L2_ORACLE  72                  0.02314     187.46     121.01          53           8       208.95             36.9       0.304         0.879          0.493            0.904
  2024             CTRL  72                  0.01904     179.73     120.07          30           1       198.96             80.0       0.455         0.922          0.332            0.904
  2024    SLEEVE_L2_LAG  72                  0.01757     179.92     120.33          32           0       200.08             38.0       0.690         0.955          0.363            0.918
  2024 SLEEVE_L2_ORACLE  72                  0.01521     182.20     121.17          33           4       200.64             39.2       0.512         0.928          0.567            0.928
   ALL             CTRL 144                  0.02293     182.63     120.02          82           8       202.72             80.0       0.359         0.895          0.296            0.889
   ALL    SLEEVE_L2_LAG 144                  0.02247     183.25     120.42          78           8       203.96             36.7       0.614         0.932          0.327            0.901
   ALL SLEEVE_L2_ORACLE 144                  0.01917     184.83     121.09          86          12       204.80             38.1       0.408         0.903          0.530            0.916

=== decision (frozen in PREREG-L05.md) ===
SLEEVE_L2_LAG [PRIMARY]: mean d -0.00045 [90% -0.00400, +0.00357]; by season 2023 +0.00056, 2024 -0.00146 -> NOT FLIP-ELIGIBLE
SLEEVE_L2_ORACLE [DIAGNOSTIC (not adoptable)]: mean d -0.00376 [90% -0.00667, -0.00089]; by season 2023 -0.00368, 2024 -0.00383 -> FLIP-ELIGIBLE
LAG - ORACLE [DIAGNOSTIC]: mean d +0.00330 [90% +0.00083, +0.00604]; by season 2023 +0.00424, 2024 +0.00237 -> LAG worse than ORACLE (interval > 0)
VERDICT: SLEEVE_L2_LAG NOT FLIP-ELIGIBLE; interpretation cell C (PREREG-L05.md)
```

## Reading (the frozen cell table)

**Cell C:** the lag arm is not eligible (mean d −0.00045, 90% [−0.00400, +0.00357]); the oracle arm is eligible
(−0.00376, [−0.00667, −0.00089]); and LAG − ORACLE's interval lies above 0 (+0.00330, [+0.00083, +0.00604]).
- **The predictor is the bottleneck, not the sleeve.** The sleeve stays paper.
- The frozen reopening condition: a new ownership predictor that beats the lag model's walk-forward Spearman on
  2023–25 by at least 0.03, tested in its own protocol.

Three independent observations agree that realized ownership carries information our predicted ownership does not:
- this read (oracle labels help, lag labels do not);
- the Week-3 tilt, where realized ownership gave 156.8 and the pre-lock sets gave 148.1 against 151.4 with no tilt
  (`rehearsal_two_track.py`);
- the Week-3 paper books, where both sleeve arms trailed control.

## What follows

**The next lever is a better pre-lock ownership estimate.** The operator already pays for one:
- Fantasy Points publishes weekly DraftKings NFL ownership projections
  (<https://www.fantasypoints.com/nfl/stats/dfs/ownership-projections>).
- It belongs in production's weekly vendor capture (the operator's order of 2026-09-28), taken Saturday and Sunday
  morning before lock.

A 2023–25 walk-forward comparison is impossible without back-captures. The honest test is **prospective**:
- from Week 4, each week compare the Spearman of FP's projection and of our lag model against the realized Millionaire
  ownership;
- preregister the adoption rule (≥ +0.03 over the lag model across the captured weeks) before the Week-4 numbers are
  seen.
