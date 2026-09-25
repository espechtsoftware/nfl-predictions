# L04 result: the live props blend vs model-only and vs a 0.70 model weight, at lineup level (PREREG-L04, read once 2026-09-25)

**Frozen design:** nfl2 `laptop/l04-props-blend-retest-20260924` @ `bf4ad3bc` (`PREREG-L04.md`), clean tree.
- **Banks:** 1130–1133, all complete: 144/144 slate-banks, 0 errors, run on the laptop 16:35 Thu – 12:30 Fri.
- **Arms,** D3200, `MAX_PER_GAME=4`: a player's served mean is `w × model + (1 − w) × PLAIN` where a ≥ 2-market price
  exists, else the model.
  - `LIVE_045`: w = 0.45, the deployed blend (base);
  - `MODEL_ONLY`: w = 1.00;
  - `ALT_070`: w = 0.70.
- **Primary:** the share of a 200,000-lineup real-ownership field above the book's best (lower is better).
- **Rule:** a challenger flips if its 95% upper bound < 0 and it is ≤ 0 in both seasons. A null closes only if every
  lower bound > −0.0043.

## Frozen reader output (verbatim)
```
identity bf4ad3bc49e8131d4d0ea6265a3786720d235b56; 144 slate-banks over banks [1130, 1131, 1132, 1133]
season        arm   n  finish_share_above_best  book_best  book_mean  clears_194  clears_220  pool_oracle  overlap_vs_live  mae_all  crps_all  mae_priced  crps_priced
  2023   LIVE_045  72                  0.02783     184.22     119.81          40           5       205.50             80.0   2.5309    1.6761      5.3843       3.9107
  2023 MODEL_ONLY  72                  0.03843     180.60     117.51          36           9       204.48             27.4   2.5484    1.6774      5.4810       3.9172
  2023    ALT_070  72                  0.03569     183.19     118.79          43           9       204.64             40.7   2.5364    1.6736      5.4152       3.8975
  2024   LIVE_045  72                  0.01544     182.10     118.89          40           1       199.08             80.0   2.5921    1.6812      5.4233       3.8909
  2024 MODEL_ONLY  72                  0.02145     178.58     117.68          31           2       198.20             26.1   2.6220    1.6848      5.5676       3.9103
  2024    ALT_070  72                  0.02032     180.27     118.55          42           1       198.36             39.5   2.6017    1.6791      5.4688       3.8807
   ALL   LIVE_045 144                  0.02163     183.16     119.35          80           6       202.29             80.0   2.5615    1.6787      5.4038       3.9008
   ALL MODEL_ONLY 144                  0.02994     179.59     117.59          67          11       201.34             26.8   2.5852    1.6811      5.5243       3.9138
   ALL    ALT_070 144                  0.02801     181.73     118.67          85          10       201.50             40.1   2.5691    1.6764      5.4420       3.8891

=== decision (frozen in PREREG-L04.md) ===
MODEL_ONLY vs LIVE_045: mean d +0.00831 [95% +0.00411, +0.01275]; by season 2023 +0.01060, 2024 +0.00602 -> NOT FLIP-ELIGIBLE
ALT_070 vs LIVE_045: mean d +0.00638 [95% +0.00121, +0.01249]; by season 2023 +0.00787, 2024 +0.00489 -> NOT FLIP-ELIGIBLE
VERDICT: no challenger is flip-eligible; LIVE_045 stays; CLOSED for 2026 (every 95% lower bound > -0.0043)
```

## Reading
- **The live blend is better than both challengers, not merely not worse.**
  - Both intervals lie entirely **above** 0 (a positive d means the challenger's best lineup is beaten by more of the
    field), in both seasons.
  - Dropping the market (`MODEL_ONLY`) costs +0.0083 in finish share. Keeping it at a lower weight (`ALT_070`) costs
    +0.0064.
  - The ordering is monotone in market weight across the three points tested.
- **The co-reported numbers agree:**
  - book best 183.2 (live) vs 179.6 / 181.7;
  - book mean 119.4 vs 117.6 / 118.7;
  - player MAE lowest for the live blend, on all modelled rows (2.56) and on priced rows (5.40 vs 5.52 / 5.44).
  - Exceptions, never decisive: CRPS is marginally lowest for `ALT_070` (1.676 vs 1.679; priced 3.889 vs 3.901), and
    `ALT_070` clears 194 more often (85 vs 80).
- **What it settles:** this is the first lineup-level test of the live ≥ 2-market blend against model-only. The laptop's
  census (`cc5d4485`) had found that PREREG-007 tested the *defective* one-market snapshot blend. The ≥ 2-market props
  blend earns its place at lineup level.
- **Disclosed limits (from the PREREG):** 2023–24 only (no prop lines earlier). Historical ≥ 2-market coverage (~19% of
  rows) is thinner than live (~43%), and concentrated above \$4,000. D3200 against the live D12800.
- **What it does not test:** more market weight (a model weight below 0.45). The monotone ordering nominates it, but by the
  frozen reopening rule that needs its own preregistration. Testing it on these slates would be panel mining.

## What follows
- **`BLEND_MODEL_WEIGHT` stays 0.45.** The question closes for 2026 (the frozen "closed" branch).
- **The props-or-nothing guard and coverage floor stay as they are.** The value of the blend argues for keeping market
  coverage healthy (R4's wider book set helps), not for lowering the floor.
- **Ledger:** results on nfl2 `laptop/l04-results-20260925` for production's re-run before the row enters.
