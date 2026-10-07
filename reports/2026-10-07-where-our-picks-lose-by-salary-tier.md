# Where our player picks lose to the field, by salary tier (2026 W1–4)

By the outside reviewing agent, 2026-10-07, for the laptop and the operator. The production team's own picks-vs-field
panel (`scripts/weekly_picks_vs_field.py` `load_week`: the 117-regular cohort, our entries from the private entry
history, the rest of the Millionaire), decomposed by tier. "Picking" is the edge minus what price and position tilts
explain (points shuffled within position × $1,000 band, 400 draws). Points per lineup against the rest of the field;
aggregates only. Code: `reports/2026-10-07-winners-strategy-study/tiers/tier_edges.py`.

| Tier | Regulars: edge / picking | Us: edge / picking | Our picking by week (W1 / W2 / W3 / W4) | Our slots vs the field |
|---|---|---|---|---|
| QB | +0.40 / +0.63 | −1.23 / −0.74 | +0.8 / −1.0 / −0.4 / −2.4 | 0.00 |
| skill $8,000+ | +1.86 / +0.26 | −2.22 / +0.56 | 0.0 / −0.7 / −0.7 / +3.6 | −0.06 |
| **skill $6,000–7,999** | +2.95 / +1.15 | −2.12 / **−6.00** | +2.1 / **−12.0** / **−5.7** / **−8.5** | **+0.30** |
| skill $4,000–5,999 | −1.48 / +0.51 | −4.51 / −0.81 | −0.3 / −2.2 / +1.6 / −2.4 | −0.44 |
| skill under $4,000 | +2.37 / **+1.65** | +4.75 / +2.03 | 0.0 / −0.2 / −2.0 / +10.3 | +0.20 |
| DST | −0.03 / +0.08 | +1.49 / +1.43 | +3.2 / +3.5 / −1.1 / +0.2 | 0.00 |
| total | +6.08 / +4.28 | −3.84 / −3.53 | | |

**Reading.** The regulars' picking edge is spread across tiers, largest under $4,000 (+1.65, three weeks of four) and
at $6,000–7,999 (+1.15). **Ours is lost almost entirely at $6,000–7,999: −6.0 points per lineup, in three of four
weeks**, and we put more of our slots there than the field does (+0.30 per lineup) while under-using $4,000–5,999.
Our cheap-player and DST picks were fine.

**Why (`tiers/mid_tier.py`).** Every projection ranks that tier poorly (rank correlation with actual points 0.16–0.36
for ours, the props market and Fantasy Points alike). The difference is which players we lean on: where our projection
sat 1.5+ points above the market (20 player-weeks) the player fell 1.3 short of our number; where the market sat above
ours (7) the player beat our number by 3.0. Our projection runs +0.6 above the market in this tier on average. The
Week-5 switch to Fantasy Points' means should shrink the gap; the weekly line will show whether it does.

**Suggestion for the Monday picks-vs-field line:** add this tier breakdown (the code reuses `load_week`; the
cohort and the entry history stay private; output aggregates only), so each week shows where our picks gained or lost.
