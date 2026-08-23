# Predicting overtime: data, measurement, and an honest assessment

Date: 2026-08-15. **No code was changed.** The measurement below is an
outcome-free query over `nfl_raw.schedules`.

---

## 1. You already have the data

`nfl_raw.schedules` carries an `overtime` flag alongside `spread_line`,
`total_line`, scores and `game_type`. No acquisition is needed to model this.

Measured over 2,895 regular-season games, 2015–2025, with a closing spread:

| closing spread | n | % overtime |
|---|---:|---:|
| pick to 2.5 | 669 | 5.38 |
| 3 to 5.5 | 1,140 | **7.02** |
| 6 to 9.5 | 731 | 5.47 |
| 10+ | 355 | **2.54** |

Overall base rate ≈ **5.7%**.

**What is actually significant here:** only the 10+ band. At `n = 355` its
standard error is ~0.84%, so 2.54% against ~6% elsewhere is roughly 4σ. Big
favourites rarely go to overtime, which is unsurprising.

**What is not significant:** the apparent peak at 3–5.5. The difference between
5.38% and 7.02% carries a standard error of about 1.15% — roughly 1.4σ. It is
tempting to read a story into it (NFL margins cluster at 3 and 7, so a
three-point spread puts mass on a zero margin) but the data does not support
that story yet, and the story is exactly the kind that survives on plausibility
rather than evidence.

So: spread predicts overtime **weakly**, and mostly through one negative signal.

## 2. A public figure to disregard

Secondary sources quote "306 overtime games in 2,560 regular-season games over
the past decade — a 12% rate." That is wrong, and it contradicts the same
source's own 2025 figure of 5.47%. 306 overtimes over ten seasons would be
~30 per year against ~272 games; the true count is roughly half that.

Your warehouse gives ~5.7%, consistent with the 5.47% single-season figure.
**Trust the measurement, not the citation.**

## 3. The market prices it directly

Sportsbooks offer a "will this game go to overtime" prop. Typical pricing is
around **+1000 yes / −2000 no**, implying roughly 5–9% after removing a wide
vig — consistent with the measured base rate and with a modest game-specific
lean.

That market is **not** among the ten Odds API markets currently stored
(`player_pass_yds`, `player_pass_tds`, `player_rush_yds`,
`player_reception_yds`, `player_receptions`, `player_anytime_td` plus four
alternate ladders). If overtime were worth modelling, the market view is
purchasable rather than estimable — but see §4 before spending anything.

## 4. Honest assessment: this is the right *kind* of mechanism pointed the wrong way

**As a marginal input, it is negligible.** Overtime adds roughly one possession
each way — call it a 10% volume boost for that game's players, conditional on
occurring. Shifting a game's overtime probability from 6% to 10% changes
expected volume by about half a percent. That is far below anything the marginal
channel has been able to detect, and the marginal channel is closed anyway.

**As a dependence input it is structurally interesting**, because overtime is a
game-level event that lifts *every player in that game simultaneously* — which
is exactly the co-boom mechanism the dependence programme has been chasing.

**But it points the wrong direction given the measured shape error.** The
current simulator already **over-produces** high multiplicity: ≥4 simultaneous
teammate exceedances at 6.18 simulated against 2.33 realized, and ≥3 at 2.38
against 1.84. An overtime mechanism adds *more* simultaneous co-booming to a
simulator that already generates too much of it. It would improve nothing and
plausibly worsen the worst-calibrated cell.

That is the same reasoning that closed the TD ledger on its merits rather than
only on protocol, and it applies here identically.

**And the binding constraint is elsewhere.** The forensic puts 79 of ~88 lost
points in the **construction** layer — combinations never built from players
already in the pool. Overtime is a game-environment signal. It cannot address a
combinatorial coverage problem.

## 5. Where overtime *could* legitimately matter

One place, and it is not lineup construction.

**The per-slate winning-line model.** Overtime inflates a game's total scoring,
which raises the whole slate's scoring, which raises the score required to win.
On a 13-game slate at a 5.7% base rate you expect ~0.75 overtime games, and a
slate with two is materially higher-scoring than one with none.

The standing proposal to predict a **per-slate winning line** from pre-lock
observables — rather than selecting at a fixed 194 — is the natural home for
this. Expected overtime count is a legitimate feature there, it is derivable
from data already held, and it is a *slate-level* quantity where a 5.7% per-game
event aggregates into something measurable.

That use is cheap, does not require the market, and does not touch the copula.

## 6. Recommendation

1. **Do not build an overtime model for lineup construction.** Negligible as a
   marginal input; wrong-signed as a dependence input; irrelevant to the
   construction layer where the loss is.
2. **Do not buy the overtime market.** The Odds API expansion budget is better
   spent on alternate team totals and volume markets, which supply the
   team-scoring *distribution* the copula needs rather than a single rare event.
3. **Do carry expected overtime count as a candidate feature for the per-slate
   winning-line model**, if that model is built. One derived column from
   `schedules`, no acquisition.
4. Record the base-rate table above so the question is not re-derived. The
   useful facts are: **~5.7% overall, ~2.5% when the spread is 10+, and no
   reliable structure elsewhere.**

---

## Sources

- Measurement: `nfl_raw.schedules`, 2,895 REG games 2015–2025
- [NFL overtime prop odds and typical pricing — SportsBetting3](https://www.sportsbetting3.com/nfl/nfl-game-to-overtime-prop-bet-odds)
- [What percentage of NFL games go to overtime — The Sports Geek](https://www.thesportsgeek.com/blog/how-many-nfl-games-will-go-into-ot-or-end-in-tie-this-season/) (note the erroneous 12% decade figure, §2)
- [NFL overtime betting guide — SportyTrader](https://www.sportytrader.com/us/sports-betting/guide/nfl-overtime-betting/)
