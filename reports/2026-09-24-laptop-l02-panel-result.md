# L02 result: the chalk-core boom sleeve vs the live generator against real Millionaire ownership (PREREG-L02, read once 2026-09-24)

Frozen design: nfl2 `laptop/l02-chalk-replay-20260922` @ `ccfb0603` (`PREREG-L02.md`), clean tree. Banks **1110, 1111**, both complete
(72/72 slate-banks, 0 errors). Arms at D3200 with `MAX_PER_GAME=4`: `CTRL`; `SLEEVE_L1` / `SLEEVE_L2` (25% of boom solves with ≤ 1 / ≤ 2
LOW-owned players, ≥ 1 of the top-15 chalk, salary ≥ \$49,500). Primary: the share of a 200,000-lineup field, sampled from the slate's
real ownership, that finishes above the book's best (lower is better).

## Frozen reader output (verbatim)
```
identity ccfb06038ce37f63730203f69efe7aab4ffe8b96; 72 slate-banks over banks [1110, 1111]
season       arm  n  finish_share_above_best  book_best  book_mean  clears_194  clears_220  pool_oracle  overlap_vs_ctrl  book_low<=1  book_chalk>=1
  2023      CTRL 36                  0.02327     185.78     119.59          19           1       205.54             80.0        0.055          0.878
  2023 SLEEVE_L1 36                  0.03049     185.12     120.39          24           4       207.01             34.7        0.361          0.906
  2023 SLEEVE_L2 36                  0.01776     190.66     120.30          25           3       208.09             35.6        0.035          0.914
  2024      CTRL 36                  0.01908     179.62     119.99          15           0       199.31             80.0        0.167          0.942
  2024 SLEEVE_L1 36                  0.01627     183.26     120.66          23           2       200.38             30.9        0.518          0.964
  2024 SLEEVE_L2 36                  0.01600     182.05     120.65          19           1       200.83             37.3        0.136          0.972
   ALL      CTRL 72                  0.02118     182.70     119.79          34           1       202.42             80.0        0.111          0.910
   ALL SLEEVE_L1 72                  0.02338     184.19     120.52          47           6       203.70             32.8        0.440          0.935
   ALL SLEEVE_L2 72                  0.01688     186.35     120.47          44           4       204.46             36.5        0.085          0.943

=== decision (frozen in PREREG-L02.md) ===
SLEEVE_L1: mean d +0.00220 [90% -0.00364, +0.00821]; by season 2023 +0.00722, 2024 -0.00281 -> NOT FLIP-ELIGIBLE
SLEEVE_L2: mean d -0.00430 [90% -0.00903, +0.00099]; by season 2023 -0.00551, 2024 -0.00308 -> NOT FLIP-ELIGIBLE
```

## Reading
- **Neither sleeve is flip-eligible under the frozen rule.**
  - **SLEEVE_L1:** mean d +0.0022; worse in 2023 (+0.0072), better in 2024 (−0.0028).
  - **SLEEVE_L2 is a near miss:** mean d −0.0043, **better in both seasons** (−0.0055, −0.0031). But the 90% interval
    [−0.0090, **+0.0010**] crosses zero, so it fails the upper-bound condition.
- **Co-reported (not decisive) lineup counts all favour the sleeves:**
  - books reaching 194+: CTRL 34, L1 47, L2 44;
  - book best: +1.5 for L1, +3.7 for L2;
  - pool oracle: +1.3 for L1, +2.0 for L2.
  L2's book-best gain (190.7 vs 185.8 in 2023) is the largest single co-reported move.
- **Operational consequence: none.** The sleeve stays out of the entered book. The Week-3 paper triple (control / low-max 1 /
  low-max 2, never entered) runs as planned and adds prospective evidence. Monday's scoreboard will show it.
- **Reopening (PREREG-L02):** it reopens only on a new mechanism, e.g. a better chalk predictor, never by re-running these arms on
  new banks. The aligned ownership-lag model (`8ce82ef4`) is a candidate new mechanism for a successor design, since it changes
  which players are CHALK/LOW. That would be a new preregistration, not a re-read.
