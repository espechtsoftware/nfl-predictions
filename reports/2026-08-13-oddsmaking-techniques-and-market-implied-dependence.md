# What oddsmakers do, and the one technique worth stealing

Date: 2026-08-13. Research into sportsbook odds-setting methodology and its
application here. **No code was changed.**

---

## The structural difference

Sportsbook line-setting is well documented and mostly already absorbed by this
system: power ratings as a team-strength baseline, situational adjustments
(home field ≈ 3 points, rest, weather, injuries), EPA and QB-efficiency inputs,
simulation, then movement in response to money flow. The system already
consumes the *output* of that process — implied team totals, spreads, game
totals, and a 45/55 prop blend.

But there is one structural difference that matters enormously given where this
project is stuck:

> **Sportsbooks price the joint distribution explicitly. This system prices
> marginals and simulates the joint.**

Same-game parlays force books to have a real copula. The research is explicit:
books use *"Gaussian copulas, empirical frequency tables, and correlation
matrices"*, typically a hybrid — *"empirical frequencies where data is abundant,
Gaussian copulas or other models to fill in gaps and smooth estimates."* Within
a game, outcomes are described as correlated *"by 30–50% or more."*

That is not a modelling curiosity. It is the exact object G0 measured and G2
failed to reproduce, priced daily by parties with more data, more staff and
real money at risk.

## The exact correspondence

The SGP literature defines a **correlation multiplier**:

> "the correlation multiplier is calculated as the ratio of the true joint
> probability to the independent probability."

That is `P(A∩B) / (P(A)·P(B))`.

G0's co-exceedance lift is `P(B | A) / P(B)`, which is algebraically the same
quantity.

**The market publishes, in observable prices, an estimate of precisely the
statistic the G0/G1 scorecard is built on.** G0 measured realized QB→WR at
3.3228 against a simulated 1.053. A book's SGP price for a QB-passing-yards ×
WR-receiving-yards pair contains that book's estimate of the same multiplier.

## The proposal: market-implied dependence as a second target

For a small predeclared set of leg pairs per game, extract:

- `P_A` from the single-leg price, de-vigged;
- `P_B` from the single-leg price, de-vigged;
- `P_AB` from the two-leg SGP price, de-vigged;
- implied multiplier `= P_AB / (P_A · P_B)`.

Three distinct uses, in increasing order of value:

**1. Independent validation of G0.** If the market's QB→WR multiplier lands near
3 while the simulator produces 1.05, that is confirmation of the G0 finding from
a completely independent source. If the market says 1.2, the G0 measurement
needs re-examination. Either outcome is worth knowing and neither requires a
lineup panel.

**2. A fitting target with better support than 54 slates.** G0/G1 estimate lift
from realized co-exceedances — roughly 1.7 q90 events per player-season, which
is why the `≥4` cell was correctly declared unsupported at seven events. Market
prices exist for *every* game, every week, with no event-rarity problem at all.
A dependence mechanism could be fitted to reproduce market multipliers and then
*validated* against realized co-exceedance — two independent targets rather than
one thin one.

**3. A pre-lock, per-game, conditional dependence estimate.** This is the
important one. G0/G1 give a *historical average* scorecard. SGP prices give a
dependence estimate **for this specific game, before lock**. A shootout between
two bad secondaries and a 34-degree grind-out game do not share a copula, and
the current simulator applies the same structure to both.

That is exactly what G2 lacked — its single context-free Gumbel strength per
position could not activate for WR — and exactly what the conditional-allocation
proposal wants as an input. Market SGP pricing is a per-game conditional
dependence signal that is available live.

## Honest problems, stated plainly

**The correlation tax biases the estimate, and not by a constant.** The
"correlation tax" *is* the shading books apply to related legs — SGP house edges
run 15–25%, versus roughly 5% on a single game line. Critically, books tax
*more correlated* legs *more heavily*. So the shading is correlated with the
quantity being measured, which means this is not a constant offset that cancels
in relative comparisons.

The direction, however, is known: taxation **compresses** measured correlation.
So a market-derived multiplier is a **lower bound** on the book's true belief.
That is still decisive for the question at hand — a lower bound of 2.5× on
QB→WR refutes a simulated 1.05 regardless of the tax.

**Each book's model is proprietary and not recoverable.** The research is
explicit that a calculator "cannot reverse-engineer" the book's correlation
model. We would be extracting a *number per pair*, not a model. That is fine —
a per-pair multiplier is what the G0 scorecard consumes.

**Availability is the real gate.** SGP prices are computed on demand per
combination and are unlikely to be served by the existing Odds API feed, which
supplies single-market prices. Whether they are obtainable — via a licensed
endpoint, a vendor, or the book's own builder — is an open question that must be
settled *before* any protocol is written. Note the project already has a
fail-closed prospective capture pattern from the Fantasy Points matchup tools
that would apply.

**Books restrict the most informative combinations.** Some correlated legs are
blocked or heavily shaded precisely where the dependence is strongest, which
truncates the observable set exactly where the signal lives.

**Combinatorics are manageable if the set is predeclared.** Do not enumerate.
Five pairs per game — QB×WR1, QB×WR2, QB×TE, WR1×WR2, QB×opposing WR1 — is
~65 queries per slate and directly populates the cells G0 registers, including
the WR–WR cell whose neutrality broke G2.

## What is *not* worth taking from oddsmaking

Recorded so the research does not get repeated:

- **Line movement and cross-book dispersion** were already tested and came back
  NULL (Addendum 96). Closed.
- **Alternate ladders** are already ingested; the `ALT_CEIL` objective tilt was
  rejected; the market-tail disagreement diagnostic failed its mechanism gate.
  The marginal side of market information is thoroughly worked.
- **Power ratings, home field, rest, weather** are all already in the feature
  set or implicit in the consumed lines.
- **"Move the line on money flow"** is opponent modelling. The DFS analogue is
  the field/payout model, already identified as the largest unbuilt piece and
  gated on 2026 standings. Worth noting that books consider this half of their
  job, and this system currently does none of it.

## Recommendation

1. **Settle availability first.** One afternoon establishing whether two-leg SGP
   prices are obtainable at all — licensed feed, vendor, or otherwise — before
   any protocol work. If they are not obtainable, the idea closes cheaply.
2. **If obtainable, start with validation, not modelling.** Extract the five
   predeclared pairs for a modest sample of games, de-vig, and compare implied
   multipliers to G0's realized scorecard. Report as a lower bound. This is
   score-free, needs no lineup panel, and either corroborates or challenges the
   central finding of the dependence program.
3. **Only then consider it as a fitting target or a live conditional input.**

The one-line version: **this project models marginals precisely and the joint by
assumption; sportsbooks are forced to do the opposite, and they publish the
answer — shaded, but in the same units the G0 scorecard already uses.**

---

## Sources

- [Same-Game Parlays: The Mathematics of Correlation — Wizard of Odds](https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/)
- [Correlation in Same Game Parlays: How Sportsbooks are Tackling the Challenge — OpticOdds](https://opticodds.com/blog/correlation-in-same-game-parlays)
- [Same Game Parlay Correlation: the hidden tax — OddsIndex](https://oddsindex.com/guides/same-game-parlay-correlation)
- [Correlated Parlay Guide — OddsIndex](https://oddsindex.com/guides/correlated-parlay-guide)
- [Devig Calculator (fair / no-vig odds) — DawBets](https://dawbets.com/tools/devig-calculator)
- [Sportsbook odds optimization and correlated proposition bet analysis (US patent)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12080130)
- [How are point spreads made for NFL games? Veteran Vegas oddsmakers explain — Yahoo Sports](https://sports.yahoo.com/how-are-point-spreads-made-for-nfl-games-veteran-vegas-oddsmakers-explain-140051148.html)
- [How to Make NFL Power Rankings for Sports Betting — Covers](https://www.covers.com/nfl/how-to-make-power-rankings)
