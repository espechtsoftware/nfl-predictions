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

**Acquisition decision:** the 2022–2025 actual-ownership coverage is sufficient
for present player-level ownership modeling and validation. Do not purchase a
feed merely to extend aggregate ownership into 2019–2021. Historical spending
must add complete entry-level fields/ranks/payouts; a future projected-
ownership subscription is a separate, prospective point-in-time signal trial.

The true-80 comparison also supplies an important clue: deleting sportsbook
means did not create more 200-point weeks and reduced the candidate-pool
oracle from 19 to 17. Market information is useful, but the next gain is more
likely to come from richer market constraints and opponent modeling than from
throwing the market mean away.

## Priority 1 — complete real contest fields (highest expected value; free prospectively)

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

### Historical backfill before the 2026 season

The free DraftKings workflow cannot backfill old fields. DraftKings' current
help page says a completed contest's full standings CSV includes ranks,
complete lineups, points, and ownership, but remains downloadable for only 10
days after the contest ends. The separate personal contest-history export is
not a substitute: it describes the account's own entries and results rather
than every opposing lineup and the contest payout curve.

There are affordable products with real historical contest fields, but their
public documentation does **not** promise a bulk/raw field export. Treat the
first purchase as a workflow trial rather than as a licensed dataset:

1. **DFS Hero — first trial.** Its official site offers every tool for $1 for
   five days, then $79.95/month for Essential. BacktestIQ explicitly claims to
   test build strategies against actual past contests with real opponent
   lineups, and Contest Analyzer claims every lineup in a past DraftKings
   contest. Before allowing renewal, verify that it covers 2023–2025 NFL
   Sunday Classic slates and either accepts our exact historical 80-lineup
   portfolios or exposes enough score/rank/payout information to grade them.
   Only generated-lineup and current-data exports are publicly documented;
   historical opponent-field export is not.
2. **FantasyCruncher NFL Pro — best documented field-analysis fallback.** Its
   current signup data prices NFL Pro at $89.95/month and lists Lineup Study
   access; its current NFL support page confirms DraftKings NFL Lineup Study
   and Lineup Rewind. This is comfortably within budget and is a plausible
   one-month backfill tool, but first confirm the retained NFL years, contest
   list, payout visibility, and whether field rows or score/rank distributions
   can be exported. Public CSV help covers generated lineups, not Lineup Study
   opponent rows.
3. **FantasyLabs NFL — inexpensive research/UI fallback, not yet a data-feed
   purchase.** The current official NFL plan is $39.95/month. FantasyLabs
   documents historical ownership/player performance and an NFL Contest
   Dashboard with detailed lineups, exposures, duplicates, and leaderboards.
   It does not publicly promise complete-field export, arbitrary portfolio
   backtesting, retained-year depth, or that every needed Sunday Classic
   contest is present.

Fantasy Team Advice is not a historical-field solution based on its current
official materials. Its $29.99/month product advertises an optimizer and
**projected/live** ownership, not archived complete contest entries. The
claimed $34.95 Sports Data Direct feed could not be verified as a current
product; the discoverable Python client was last released in 2019. Do not buy
either for this purpose without new primary-source evidence.

The exact vendor gate is: “Can I export or programmatically access every
entry—rank, score, ordered lineup, duplicates, and payout—for 2023–2025
DraftKings NFL Sunday Classic contests, or upload my own 80 lineups per slate
and receive their ranks and payouts against the complete historical field?
Which slates and contests are retained?” A product that supplies only player
ownership percentages does not pass.

No purchase or account creation is authorized by this audit. Recommended next
step is the $1 DFS Hero trial after the user is available to create the account
and approve its auto-renewing billing; cancel within the five-day window unless
the gate passes. If it fails, ask FantasyCruncher support the same question
before buying one NFL Pro month.

**Trial result, 2026-08-09:** the user activated the $1 DFS Hero Power trial.
Because NFL was marked offseason, the historical Contest Analyzer was opened
directly. It listed 309 DraftKings contests for 2025-10-05 and exposed useful
contest-level metadata. For example, it listed the main-slate Millionaire as
161,764 entries with a 169.34-point min-cash line and 246.82 first-place score.
However, opening both that contest and the separate main-slate `$40K MEGA
mini-MAX` returned `Contest data not available`; no leaderboard or CSV export
was available. Thus DFS Hero fails the current historical-field gate. Retain
the trial only long enough to ask whether this is a temporary offseason defect
and whether any 2023–2025 NFL Classic fields are actually downloadable; do not
allow the $149.95 Power renewal. If support cannot identify a working retained
contest and export, proceed to the FantasyCruncher pre-purchase question.

### GitHub/public-repository audit

A targeted GitHub audit did not find a usable archive of settled historical
DraftKings NFL ownership or complete contest fields. The closest active result,
[`925Sports/925Sports-nfl-dfs-data`](https://github.com/925Sports/925Sports-nfl-dfs-data),
publishes a current `ownership.csv` sourced from a live Google Sheet. Its
`RST%` values are projected ownership, the repository was created in August
2026, and its short history cannot backfill prior seasons. Do not treat it as
actual post-lock contest ownership or ingest it without provenance and license
clarification.

Older public projects likewise do not close the gap:
[`guydotan/nfl-dfs-optimizer`](https://github.com/guydotan/nfl-dfs-optimizer)
contains 2018 salaries and realized scores but no ownership;
[`Germinsky/draft-kings-fun`](https://github.com/Germinsky/draft-kings-fun)
expects the operator to download a projected-ownership file rather than
archiving actual ownership; and a request for past contest data in
[`pydfs-lineup-optimizer`](https://github.com/DimaKudosh/pydfs-lineup-optimizer/issues/372)
contains no dataset. Exact-header searches for DraftKings full-standings CSVs
also returned no public archive.

This result makes broad GitHub scraping a low-priority acquisition path. The
warehouse already has 103,556 actual player/contest ownership records across
1,258 contests and every week of 2022–2025. A public repository is useful only
if it adds verified post-lock ownership for 2019–2021 or lossless entry-level
rosters/ranks/payouts. Projected ownership snapshots may still be useful
prospectively as an independently timestamped model input, but they are not a
historical truth set and must remain source-separated.

Sources:
[DraftKings full-standings CSV and 10-day limit](https://help.draftkings.com/hc/en-us/articles/4412213454099-How-do-I-download-a-CSV-to-see-GameCenter-standings-for-a-contest-US),
[DFS Hero tools](https://dfshero.com/tools),
[DFS Hero pricing](https://dfshero.com/pricing),
[FantasyCruncher NFL Pro signup](https://www.fantasycruncher.com/premium-signup/NFL/monthly),
[FantasyCruncher supported NFL tools](https://www.fantasycruncher.com/help/faqs/What-sites-sports-do-you-support),
[FantasyLabs NFL pricing](https://www.fantasylabs.com/pricing-al/),
[FantasyLabs NFL Contest Dashboard](https://www.fantasylabs.com/articles/use-nfl-dfs-contest-dashboard-fantasylabs/),
[Fantasy Team Advice membership](https://fantasyteamadvice.com/memberships?rfr=ownership),
[stale Sports Data Direct Python client](https://pypi.org/project/sdd-api/).

## Priority 2 — prospective ownership and projection consensus (small trial)

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
