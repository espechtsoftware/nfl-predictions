# Data acquisition priorities for winning-money utility

Reviewed: 2026-08-09. This is a durable acquisition plan, not authorization to
blend a new source into production. Every predictive input still requires a
point-in-time shadow and a frozen validation gate.

## Recommendation in one sentence

The most valuable missing data is **complete DraftKings Classic contest
standings with every entry, lineup, rank, score, duplication, and payout**.
After that, spend first on an independent ownership/projection consensus and
on extracting more signal from the already-paid Odds API; trial route-level
usage data only after those two loops are operating.

## What is already in hand

The project already has broad free football coverage: nflverse play-by-play,
weekly stats, rosters, snap counts, NGS aggregates, FTN charting, schedules,
injuries, weather, DraftKings salaries, and immutable replay features. Buying
another generic box-score or closing-game-line feed would mostly duplicate
that stack.

BigQuery currently contains:

- 369,727 Odds API prop rows across 10 markets, two bookmakers, and 55
  season-weeks. The six base markets are passing yards/TDs, rushing yards,
  receiving yards/receptions, and anytime TD; the four stored alternate
  ladders are pass/rush/receiving yards and receptions.
- 1,258 historical `contest_ownership` contest IDs covering every week of
  2022–2025, mostly aggregate LineStar ownership rather than complete Classic
  entry rosters.
- No `nfl_raw.contest_entries` table yet. The lossless importer and field
  calibration code exist, but they have no Classic full-field observations to
  learn from.

The true-80 comparison also supplies an important clue: deleting sportsbook
means did not create more 200-point weeks and reduced the candidate-pool
oracle from 19 to 17. Market information is useful, but the next gain is more
likely to come from richer market constraints and opponent modeling than from
throwing the market mean away.

## Priority 1 — complete real contest fields (highest expected value; free)

Download the full standings CSV for every contest actually played, ideally on
Monday and no later than Tuesday. At minimum collect:

- one large-field flagship/Milly-style contest;
- every qualifier entered;
- representative small-field and single-entry contests; and
- the exact payout structure, entry fee, field size, and number of seats.

Preserve every entry, ordered roster, rank, realized score, payout, and
contest metadata—not only the winner or top 20. This data unlocks the work
that directly matches the user's utility: calibrated opponent-lineup
generation, duplicate-lineup risk, score-to-rank and score-to-dollar curves,
qualifier advancement probability, and expected-payout portfolio selection.
The repository already implements `nfl-dfs import-ownership` and the lossless
entry schema; this is primarily a strict weekly collection task because DK
exports are ephemeral.

This is more valuable than buying a projection feed because a projection feed
can improve player estimates, while complete fields tell us what combinations
the opponents submit and what score actually wins money—the objective the
optimizer cannot presently observe.

## Priority 2 — independent ownership and projection consensus (small trial)

The project should acquire one independent DFS source for an initial one-week
shadow, then pay again only if its differences change decisions and grade
better after results. Establish The Run's official 2026 material says its NFL
In-Season product includes weekly fantasy-point and ownership projections;
its currently published annual product is $259.99, while availability and
price of a weekly pass should be rechecked when the in-season catalog opens.

Import source projection, ceiling, large-field ownership, small-field
ownership, slate identity, and publication/update timestamp. Keep the vendor
value separate from the internal model and sportsbook consensus. Grade:

- mean and upper-tail calibration;
- ownership MAE and rank correlation against the matching real contest;
- whether source/internal disagreements identify realized tail outcomes; and
- whether decisions actually changed for entered lineups.

Do not buy multiple projection subscriptions simultaneously. One independent
source plus the sportsbook surface is enough to measure whether consensus
adds information before expanding spend.

Sources:
[ETR NFL In-Season product](https://establishtherun.com/product/in-season-package/),
[ETR 2026 product description](https://establishtherun.com/etr-nfl-product-overview/).

## Priority 3 — use more of the existing Odds API subscription

This is the best low-incremental-cost data opportunity. The current importer
requests only 10 of the vendor's available NFL prop/alternate markets and
only DraftKings/FanDuel. The official API currently exposes several
high-relevance constraints we do not store:

1. **Volume:** pass attempts, completions, and rush attempts.
2. **Touchdown allocation:** passing interceptions, rushing TDs, receiving
   TDs, and their alternate ladders.
3. **Dual-role usage:** rush+receiving yards/TDs and pass+rush yards.
4. **Big-play tails:** longest completion, reception, and rush.
5. **Environment tails:** team totals, alternate team totals, alternate game
   totals, and alternate spreads.

The first shadow bundle should be volume + touchdown allocation + dual-role
markets. Longest-play and alternate game/team ladders are second because they
may improve the simulated tail but need stronger calibration checks.

Expand from two books toward a deliberately chosen set of up to ten books
where those markets are available. The API documentation says a bookmaker
filter takes precedence over `regions` and up to 10 specified bookmakers
count as one region, so broader cross-book consensus/dispersion does not add a
second regional multiplier. Billing is by unique markets actually returned;
responses expose used, remaining, and last-call credits. Persist those quota
headers so expansion can be budgeted from evidence rather than assumptions.

Historical event odds cost 10 credits per returned market per effective
region. At roughly 272 games per regular season, one additional market across
2023–2025 is about 8,160 credits before empty-response savings; an eight-market
backfill is about 65,280 credits. Do not launch it until the account's current
remaining quota is known. Current published plans are $30/month for 20,000
credits and $59/month for 100,000, so a single 100K billing period can cover a
carefully bounded backfill if the current subscription does not already have
room.

For 2026 live collection, take multiple point-in-time snapshots (opening,
Saturday, early Sunday, and final pre-lock), not just the current Thursday
run. Preserve per-book prices and timestamps. New markets remain shadow
features until their held-out residual, quantile-calibration, dependence, and
candidate-oracle gates pass.

Sources:
[official NFL market list](https://the-odds-api.com/sports-odds-data/betting-markets.html),
[official v4 endpoints and quota rules](https://the-odds-api.com/liveapi/guides/v4/),
[current plans](https://the-odds-api.com/).

## Priority 4 — route participation and receiver opportunity (measured trial)

Routes run, route participation, targets per route, first-read targets,
alignment, and red-zone/end-zone route participation fill a real project gap.
They can detect a player's opportunity change before trailing targets fully
show it and are most relevant to the remaining WR/TE tail gap.

Fantasy Points Data Suite is the most practical trial candidate found: its
published materials list route share, target share, separation, coverage and
alignment splits, Monday updates, and CSV/Excel export. Its published 2026
list price is $200/year. A PFF consumer subscription also exposes route data
and CSV downloads for many reports, but PFF explicitly says ordinary PFF+
does not include API access.

Do not assume these fields improve the lineup score. Buy only if the export
license/workflow is usable, retain point-in-time weekly snapshots, and test a
small role-change feature set against the existing snap/target/air-yard
features. Continue only if held-out tail or residual performance improves.

Sources:
[Fantasy Points Data Suite contents/export](https://newsletter.fantasypoints.com/p/fantasy-points-data-free-this-week),
[2026 Data Suite price](https://newsletter.fantasypoints.com/p/early-bird-discount-2026),
[PFF API/export limitation](https://profootballfocussupport.zendesk.com/hc/en-us/articles/32094827302163-Does-API-access-come-with-a-subscription).

## Lower priority / do not buy yet

- **Real-time injury/depth-chart API:** it is operationally valuable, but a
  generic delayed plan is not. SportsDataIO's $99/month Discovery Lab is
  next-day delayed and therefore cannot protect Sunday lineups. Its real-time
  commercial feed updates injuries, depth charts, projections, and ownership,
  but overlaps the cheaper sources above. Seek a quote only if 2026 audits
  show that DK status, official injury data, and the Sunday workflow miss
  actionable late news.
- **Raw tracking data:** public NGS aggregates and Big Data Bowl data already
  support the current off-season trait work. Enterprise tracking is expensive
  and lacks a demonstrated weekly deployment path; do not buy before the
  public-data shadow proves incremental signal.
- **Another odds/game-lines vendor, generic stats API, weather API, or
  historical salary feed:** the relevant coverage is already in house. These
  would pay mostly for redundancy, not the measured bottlenecks.

Sources:
[SportsDataIO NFL workflow](https://sportsdata.io/developers/workflow-guide/nfl),
[SportsDataIO access and Discovery Lab pricing](https://sportsdata.io/developers).

## Concrete 2026 acquisition sequence

1. Before Week 1, verify the DK full-standings export/import workflow and add
   the exact contests to the weekly checklist.
2. Before changing Odds API ingestion, record account quota from response
   headers; implement market availability/quota telemetry and a shadow-only
   expanded market bundle.
3. In Week 1, collect every entered contest's full standings and one
   independent ownership/projection snapshot at each material update.
4. After 2–3 weeks, fit and grade the field model on held-out contests; only
   then enable payout-relative optimization research.
5. Trial route data only after the field/ownership loop is reliable. Buy no
   overlapping second projection or real-time data feed without a measured
   failure that it specifically resolves.

Credential note: the new computer's local `.env` does not contain the Odds
API key. Existing cloud jobs and historical BigQuery data are sufficient for
this audit. Do not redeploy `ingest-odds` or `ingest-props` from a shell with a
blank `ODDS_API_KEY`, because the current deploy script passes the value
directly. Restore the credential securely or migrate it to Secret Manager
before changing those jobs; never commit it to the repository.
