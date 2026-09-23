# The market's skill-position under-projection is mostly median-vs-mean on yardage lines (not TD de-vig, not bonuses)

Follow-up to the bonus-aware conversion (branch `laptop/market-bonus-aware-20260923`): even after the 100-yard bonus, WR/RB/TE
realized DK points run **+0.8 to +1.2** above the market in every projection band, including 6–10, where no bonus applies.
Pre-lock prop lines 2023–25, same lock cut-off and name resolution as `prop_market.market_points`; realized values from
`player_week_training` (active players). Scripts: `reports/lab-handoffs/2026-09-23-{td-devig-calibration,yardage-line-median-check}.py`.

## Ruled out: the anytime-TD de-vig
Devigged (/1.15) anytime-TD probability **0.171** vs realized TD rate **0.166** (12,672 player-weeks): calibrated on average.
The shape shows the usual favourite–longshot bias (longshots 0.035 priced vs 0.018 realized; favourites 0.426 vs 0.452), worth
only about ±0.1–0.3 points at the extremes. **It is not the level gap.**

## Found: yardage lines are medians; the conversion treats them as means
| market (2023–25) | n | line | implied mean (current) | realized mean | realized median | DK-point gap per line |
|---|---:|---:|---:|---:|---:|---:|
| receiving yards | 5,522 | 30.9 | 30.9 | **35.2** | ≈ line in every band | **+0.43** |
| rushing yards | 2,608 | 35.3 | 35.3 | **37.9** | ≈ line | **+0.26** |
| receptions | 5,202 | 3.13 | 3.27 | 3.23 | ≈ line | −0.04 (Poisson already handles it) |

By band, receiving means exceed the line by **+3.9 / +3.8 / +4.2 / +5.2 yards** (lines 11 / 21 / 34 / 59), with the realized
median at 9 / 19 / 34 / 58, i.e. at the line. `prop_line_to_mean(..., "normal")` is symmetric, so a line priced near 50/50
returns mean = line. Yardage is right-skewed (a floor at 0, a long upper tail), so the median-anchored line under-states the
mean. **This accounts for roughly 0.4–0.7 of the ~1-point market gap for WR/RB/TE** (a receiver with both lines about +0.43;
an RB with both about +0.7). At the 0.55 market weight, that is **+0.25–0.4 served points** per player, before the model half.

## Proposed fix (for production; not for Week 3)
Behind its own default-off flag, convert yardage lines with a **right-skewed** distribution whose **median** is the line: for
example a gamma (or lognormal) matched to the line as the median and to the book's p_over, with the scale from the same
0.30·line rule. The empirical shortcut is **mean ≈ line + ~4 receiving yards / ~2.7 rushing yards** at even prices. Validate with
the same walk-forward table (bias by position × band, plain vs corrected) before any lineup-level test. It composes with the
bonus-aware path: the bonus probability should come from the same skewed distribution, which would raise it slightly.
