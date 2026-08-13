# Market-implied dependence review

Date: 2026-08-13. This reviews
`reports/2026-08-13-oddsmaking-techniques-and-market-implied-dependence.md`
against the terminal G0 result, the current Odds API integration, and the
documented vendor surface. No sportsbook quote was collected and no model,
production path, score, or Odds API request bundle was changed.

## Decision

The central research direction is useful, but it is **not currently an
executable arm**. Preserve it as an availability-gated prospective lead.

The algebra is correct:

`P(A and B) / (P(A) * P(B)) = P(B | A) / P(B)`.

That makes a fair joint-market multiplier conceptually comparable to a
co-exceedance lift when—and only when—A and B are the same events under both
calculations. A properly calibrated pre-lock joint quote could therefore be a
valuable independent dependence target and, later, a game-specific context
signal.

The supplied document nevertheless needs three material corrections before
that idea can be tested.

## Corrections

### 1. The stated correlation-tax direction is reversed

Suppose the fair joint probability is 0.20, implying fair decimal odds of
5.00. If a book reduces the payout to 4.00, naively inverting that quote gives
0.25. Holding the single-leg probabilities fixed, the apparent multiplier is
therefore **larger**, not smaller.

Consequently a payout haircut does not make the naively inverted multiplier a
lower bound on the book's unshaded belief. It can bias the estimate upward,
and the bias may itself vary with pair type and dependence. Statements such as
"a lower bound of 2.5" are not licensed by an SGP price alone.

### 2. One SGP quote cannot be conventionally de-vigged

A two-way single-player over/under market supplies complementary outcomes from
which a chosen margin-removal rule can estimate fair probabilities. A single
offered two-leg SGP payout does not supply the complete mutually exclusive
joint outcome set. There is no model-free `P_AB` to recover merely by applying
the usual two-way de-vig operation.

Any useful implementation therefore needs one of:

- a vendor-supplied fair joint probability or explicit correlation factor;
- prices for a complete joint outcome grid with documented treatment of voids
  and pushes; or
- a preregistered empirical calibration from quoted payout to realized joint
  frequency on a separate historical sample.

Without one of those, the price can be retained as an ordinal market signal,
not interpreted as the book's true joint probability.

### 3. The proposed leg events are not G0's events

G0 used the events `QB actual DK points > that QB row's final-served q90` and
`WR actual DK points > that WR row's final-served q90`. A passing-yards over
and a receiving-yards over use vendor-selected yardage thresholds and omit
touchdowns, rushing, receptions, bonuses, turnovers, and the rest of DraftKings
scoring. Their multiplier may validate the *sign* of QB/receiver dependence,
but its numerical value cannot be compared directly with G0's realized 3.321
or simulated 1.053.

If joint prices become available, the simulator must be evaluated on the exact
same prop events and thresholds as the quote. G0 remains a separate terminal
fantasy-point scorecard.

## Availability audit

The documented Odds API V4 surface provides single-event odds for requested
market keys and lists individual NFL player props plus their alternate lines.
Its published market catalog does not list an SGP/parlay quote, joint
probability, or correlation-factor market key. The project's live and
historical integration matches that surface: it persists individual prop
outcomes in `nfl_raw.prop_lines` and has no representation of a multi-leg
quote.

The request audit currently shows 99,924 credits remaining after the latest
live game-odds call. No experimental request was made: guessing an undocumented
market key would not settle whether a book-builder product is available and
would spend credits without a frozen payload contract.

Therefore the existing Odds API subscription and importer cannot currently
produce `P_AB`. Historical individual player props becoming available from
2023 does not change that conclusion.

## Corrected availability-first branch

1. Ask The Odds API (and only then other licensed feeds) whether it offers an
   NFL two-leg SGP quote, fair joint probability, or explicit correlation
   factor with pre-lock timestamps and historical availability. This is a
   product-capability inquiry, not a data call.
2. If the answer is no, close the direct market-implied joint target without
   code or quota spend. The documented individual and alternate props remain
   useful only for the already tested marginal-market paths.
3. If the answer is yes, inspect a schema/cost sample before purchasing or
   backfilling. Require stable leg identities, exact thresholds, book, quote
   timestamp, odds format, void/push rules, and either fair probability
   metadata or enough outcomes to calibrate the margin.
4. Freeze a small validation protocol before inspecting realized pair rates.
   Compare quoted and simulated probabilities for the **same** prop events;
   do not compare a yards-over multiplier numerically with G0's fantasy-point
   q90 multiplier.
5. Only a calibrated, held-out validation result may license fitting or a live
   game-specific dependence feature. Do not enumerate pair combinations or
   scrape sportsbook interfaces.

## Queue placement

Keep this behind the already collected Fantasy Points QB shell-fit diagnostic
and the separately scoped receiver-allocation work. It is a credible data-
availability lead, not evidence that current scoring should change. The active
baseline remains unchanged.

## Primary vendor references

- [The Odds API V4 endpoint documentation](https://the-odds-api.com/liveapi/guides/v4/)
- [The Odds API published betting-market catalog](https://the-odds-api.com/sports-odds-data/betting-markets.html)
