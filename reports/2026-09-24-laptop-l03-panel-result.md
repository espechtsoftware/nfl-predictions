# L03 result: the median-line + bonus-aware market conversion vs the live conversion, at lineup level (PREREG-L03, read once 2026-09-24)

**Frozen design:** nfl2 `laptop/l03-market-conversion-20260923` @ `bceac3a` (`PREREG-L03.md`), clean tree.
- **Banks:** 1120 and 1121, both complete: 72/72 slate-banks, 0 errors, run 06:55–16:30 CDT on the laptop.
- **Arms,** at D3200 with `MAX_PER_GAME=4`:
  - `CTRL_LIVE`: the live ≥ 2-market blend, 0.45 × model + 0.55 × plain market points;
  - `MEDIAN_BONUS`: the same blend on the median-line, bonus-aware conversion.
- **Primary:** the share of a 200,000-lineup field, sampled from the slate's real ownership, that finishes above the
  book's best (lower is better).

## Frozen reader output (verbatim)
```
identity bceac3a3f721d4c64cef36dfb0a6da520d303dfd; 72 slate-banks over banks [1120, 1121]
season          arm  n  finish_share_above_best  book_best  book_mean  clears_194  clears_220  pool_oracle  overlap_vs_ctrl  book_served_shift
  2023    CTRL_LIVE 36                  0.02701     187.26     119.73          25           5       206.77             80.0              0.242
  2023 MEDIAN_BONUS 36                  0.02456     186.35     121.09          22           4       207.54             44.1              0.265
  2024    CTRL_LIVE 36                  0.01668     181.31     118.70          13           1       201.46             80.0              0.274
  2024 MEDIAN_BONUS 36                  0.02091     179.96     119.55           8           1       202.67             44.2              0.296
   ALL    CTRL_LIVE 72                  0.02184     184.28     119.22          38           6       204.12             80.0              0.258
   ALL MEDIAN_BONUS 72                  0.02274     183.15     120.32          30           5       205.11             44.1              0.280

=== decision (frozen in PREREG-L03.md) ===
MEDIAN_BONUS: mean d +0.00089 [90% -0.00338, +0.00517]; by season 2023 -0.00245, 2024 +0.00424 -> NOT FLIP-ELIGIBLE
```

## Reading
- **Not flip-eligible, and no sign of a gain.**
  - The mean d is positive (+0.0009, i.e. worse), with its interval centred near zero.
  - The seasons disagree: better in 2023 (−0.0025), worse in 2024 (+0.0042).
  - The panel's 90% half-width is about 0.0043, so it could miss a gain of that size. But nothing here points to one.
- **The arms are not vacuous.** The books share 44 of 80 lineups, and the conversion raises the served mean of the
  book's players (0.258 → 0.280).
- **Co-reported, never decisive, all one way:** the conversion lifts the **average** and lowers the **ceiling**.
  - Up: book mean +1.1, pool oracle +1.0.
  - Down: book best −1.1, 194+ clears 38 → 30, 220+ clears 6 → 5.
  - This matches the projection-level finding. Median lines correct a mean bias. A higher mean on the priced players does
    not make the tournament book's best lineup better; if anything it pulls selection toward those players.
- **In-sample caveat (disclosed in the PREREG):** the conversion's constants were fitted on 2023–24. A pass would only
  have shown that the lineup mechanism works. The failure is therefore informative: even in-sample, the corrected means
  do not reach the lineup gate.

## What follows
- **`MARKET_LINE_MEDIAN` / `MARKET_BONUS_AWARE` stay default-off.** Parked branch `laptop/market-bonus-aware-20260923` @
  `c07ba976` stays parked. The live conversion is unchanged.
- **Reopening (frozen):** only on a new mechanism, e.g. a conversion refit that includes 2025. Never by re-running these
  arms on new banks.
- **The projection-level result stands on its own.** Median lines explain the market-level gap, and the out-of-sample
  2025/2026 tables show it. It just is not a lineup lever at D3200.
- **For L04** (the live blend vs model-only vs 0.70, same frame and conversion): L03 confirms that a mean-level change to
  the priced players can move books substantially (36 of 80 lineups differ) without moving the primary.
