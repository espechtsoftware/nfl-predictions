# L01 result: all-boom and max-per-game-4 vs the live generator (PREREG-L01, read once 2026-09-23 15:56 CDT)

Frozen design: nfl2 `laptop/l01-panel-20260922` @ `dc66bdb0` (`PREREG-L01.md`). Banks read: **1100,1101,1102**.

## Frozen reader output (verbatim)
```
identity dc66bdb0e89b224b510f79c87fb866e9531b5c44; 162 slate-banks over banks [1100, 1101, 1102]

=== per season (mean over slate-banks; clears are totals) ===
season          arm   n  pool_oracle  book_best  book_mean  sel_clears_194  sel_clears_220  weeks_book_194  weeks_book_220  pool_clears_194  pool_clears_220
  2022         CTRL  54       202.53     183.97     115.89              30               1              17               1              383               25
  2022 ALLBOOM_CEIL  54       203.39     183.49     116.08              32               4              14               3              414               33
  2022     MAXGAME4  54       203.99     183.56     116.50              28               4              16               4              389               23
  2023         CTRL  54       203.02     184.31     119.55              31               4              13               4              463               32
  2023 ALLBOOM_CEIL  54       204.88     183.44     119.36              38               7              13               4              614               56
  2023     MAXGAME4  54       204.82     185.64     120.36              43               1              15               1              483               32
  2024         CTRL  54       200.05     179.96     119.96              31               0              15               0              457               12
  2024 ALLBOOM_CEIL  54       199.59     178.93     119.51              20               0              11               0              490               20
  2024     MAXGAME4  54       201.65     181.02     120.30              32               1              17               1              469               15
   ALL         CTRL 162       201.87     182.75     118.47              92               5              45               5             1303               69
   ALL ALLBOOM_CEIL 162       202.62     181.95     118.32              90              11              38               7             1518              109
   ALL     MAXGAME4 162       203.49     183.40     119.05             103               6              48               6             1341               70

CTRL book lev share: 0.024

=== decision (rule frozen in PREREG-L01.md) ===
ALLBOOM_CEIL: (a) selected clears >=194 90 vs CTRL 92 -> FAIL; (b) pool-oracle delta by season 2022 +0.86, 2023 +1.86, 2024 -0.46 -> FAIL; book-best delta -0.79 [90% season-cluster -1.91, +0.32] (co-report)
  VERDICT ALLBOOM_CEIL: NOT FLIP-ELIGIBLE
MAXGAME4: (a) selected clears >=194 103 vs CTRL 92 -> PASS; (b) pool-oracle delta by season 2022 +1.46, 2023 +1.80, 2024 +1.60 -> PASS; book-best delta +0.66 [90% season-cluster -1.34, +2.44] (co-report)
  VERDICT MAXGAME4: FLIP-ELIGIBLE
```

## Mechanics (outcome-blind checkpoint)
```
slate-banks done 162/162; errors 0
  CTRL          gen  27.1 min median (max 39.2) | uniques 2680-3200 | bad solves 0 | max-per-game 4:66%, 5:31%, 6:3%, 7:0%, 8:0% | book lev 1.9/80
  ALLBOOM_CEIL  gen   6.9 min median (max 10.1) | uniques 2491-3200 | bad solves 0 | max-per-game 4:57%, 5:37%, 6:5%, 7:1%, 8:0% | book lev 0.0/80
  MAXGAME4      gen  26.8 min median (max 38.3) | uniques 1743-3200 | bad solves 0 | max-per-game 4:100% | book lev 2.6/80
  median wall per slate-bank 62 min; remaining 0 -> ~0.0 h on 8 workers (ETA Wed 15:56)
```

## Interpretation
_(written after the read; the verdict lines above are the decision under the frozen rule.)_
**MAXGAME4: FLIP-ELIGIBLE under the frozen rule, so the live `MAX_PER_GAME=4` (already flipped by the operator) stands.**
Both frozen conditions pass. (a) Selected ≥194 clears: 103 vs 92. (b) The pool oracle is higher in all three seasons
(+1.46 / +1.80 / +1.60). The decision is what the rule says. What the numbers do **not** show:
- **The book-level gain is small and not established.** Book-best delta +0.66, with a 90% season-cluster interval of
  [−1.34, +2.44] that spans 0. Mean book +0.58. ≥220 clears 6 vs 5.
- **The clears gain comes from one season.** Selected ≥194 clears by season: 2022 28 vs 30, **2023 43 vs 31**, 2024 32 vs 31.
  Two of three seasons are within ±2. The pool-oracle gain is the consistent part (3/3 seasons, about +1.5 points): capping
  one game at 4 lets the generator reach better lineups. The selector converts that into the book mainly in 2023.
- **Disclosed mechanics:** MAXGAME4 enforces the cap on 100% of its pool (CTRL has 34% of lineups above 4, so the arm is not
  vacuous). Its pool falls as low as 1,743 uniques on the tightest slate (target 3,200), still far above K80. D3200 here
  against the live D12800; seasons 2022–24.
- **Reading:** the constraint is safe to keep (no season is worse on the oracle; book deltas are small either way) and plausibly
  helps. It is not a demonstrated book-level edge. This is consistent with the operator's in-season flip; permanent adoption
  would still need the lab's six-season standard.

**ALLBOOM_CEIL: NOT FLIP-ELIGIBLE.** Selected clears 90 vs 92, and the 2024 pool oracle is lower (−0.46). A note for future
design, not a verdict: its **pools** carry more ceiling (pool ≥194 clears 1,518 vs 1,303; ≥220 109 vs 69; selected ≥220 11 vs 5),
but the selector does not convert it into ≥194 book clears, and book-best is −0.79. The all-boom generator makes more high-ceiling
lineups that the current selection does not keep. It closes in this form under PREREG-L01's reopening condition.
