# Weekly coverage data-source audit

Date: 2026-08-13

## Question

Are there additional sources, including the successor to Football Outsiders,
that can supply useful weekly NFL coverage data for the DFS model?

## Decision

Do **not** purchase another feed yet. First evaluate the freely available
nflverse participation history. If a distinct live 2026 feed is still needed,
the first paid trial should be Sports Info Solutions (SIS) DataHub Pro. FTN's
consumer Stats tool is the second option, but its bulk-export rights and exact
consumer price need confirmation before purchase. PFF+ is useful as a player
quality supplement, not the first choice for a coverage-shell feed.

This does not change the current Fantasy Points tests or authorize a new
outcome-aware arm. Any model use must be frozen prospectively and preserve the
project's point-in-time rules.

## 1. Free historical source: nflverse participation

Official sources:

- <https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html>
- <https://nflreadr.nflverse.com/articles/dictionary_participation.html>
- <https://github.com/nflverse/nflverse-data/releases/tag/pbp_participation>

The released play-level participation files contain
`defense_man_zone_type` and `defense_coverage_type`. Direct inspection on
2026-08-13 verified the following nonblank shell counts:

| Season | Rows | Nonblank man/zone | Nonblank named shell |
|---:|---:|---:|---:|
| 2022 | 50,150 | 18,975 | 18,975 |
| 2023 | 46,168 | 22,916 | 22,916 |
| 2024 | 45,919 | 22,408 | 22,408 |
| 2025 | 45,184 | 22,055 | 22,055 |

Named values include Cover 0/1/2/3/4/6/9, 2-Man, Combo, Prevent and Blown,
with season-specific availability. Earlier participation files extend to 2016.

Important limitation: nflverse says the pre-2023 source is NFL NGS, while
2023 onward is FTN Data and arrives only after the postseason. Therefore:

- it is valuable now for historical, walk-forward mechanism diagnosis;
- it cannot serve a same-season 2026 weekly feature;
- the NGS-to-FTN provider break must be measured explicitly;
- it must not be silently bridged to live Fantasy Points fields as though the
  vendors used identical charting definitions.

The repo already ingests the separate live-updating `ftn_charting` subset.
That table does not contain coverage-shell fields. The participation source is
different and is not currently ingested.

## 2. Sports Info Solutions DataHub Pro

Official sources:

- <https://store.sportsinfosolutions.com/>
- <https://pro.sisdatahub.com/Home/FAQ>
- <https://www.sportsinfosolutions.com/football/>

SIS is the strongest paid candidate under the operator's stated $200 ceiling.
The operator confirmed that the trial is offered as combined NFL and college
football access rather than an NFL-only trial:

- NFL plan: $99.99/month or $749.99/year at the time of this audit;
- seven-day trial;
- player and team leaderboards, time filters and CSV export;
- advanced filters explicitly include routes and coverage types;
- the FAQ specifically describes querying the coverages WRs/QBs face and the
  coverages DBs play.

Before buying, use the trial to verify all of the following rather than relying
on marketing copy:

1. 2019--2025 NFL history and selectable individual week ranges;
2. team shell deployment and QB/receiver performance by shell;
3. defender coverage snaps, targets, alignment and any receiver assignment;
4. CSV exports at the required grain with stable player/game identifiers;
5. regular in-season availability early enough for the next slate;
6. whether the included college product provides historical team/player data
   that can complement the repo's CFB salary/contest collection scaffold.

The official FAQ adds two important trial constraints: trial accounts return
only the top 20 rows per leaderboard (paid accounts return the top 200), and
the subscription agreement caps use at 1,000 queries per week. Therefore the
trial can validate schemas, filters, dates and exports, but cannot by itself
produce a complete historical player panel. The exact NFL and college audit
sequence is in
`reports/2026-08-13-sis-datahub-trial-checklist.md`.

If these checks pass, SIS can fill a more distinct gap than another aggregate
matchup grade: individual defensive responsibility and coverage efficiency.

## 3. FTN Stats (Football Outsiders successor)

Official sources:

- <https://ftnfantasy.com/nfl/stats>
- <https://ftnfantasy.com/nfl/historical-dvoa-archive>
- <https://ftnfantasy.com/learn-more-about-dvoa>
- <https://ftnfantasy.com/data>

Football Outsiders' DVOA moved to FTN in August 2023. FTN Stats advertises
in-house charting of every play, filters by week and coverage, defensive looks,
routes, and player/team splits. FTN also exposes historical DVOA workbooks,
including as-of-week DVOA and defense-versus-receiver splits. This makes it a
credible research source, especially for DVOA and offense/defense performance
against man/zone.

The consumer pages do not clearly confirm a general CSV export for arbitrary
Stats queries. FTN's separate data offering lists $599 for three seasons of
base-stat/play-by-play CSV access and $5,000 for its charting API, both outside
the current incremental-data budget. Before considering FTN, confirm through a
demo that the consumer Stats plan permits the historical weekly coverage
exports we need. Do not buy the enterprise feed on the current evidence.

## 4. PFF+

Official source:

- <https://www.pff.com/lp/membership>

PFF+ includes weekly/game-by-game player grades and premium stats, with player
grades back to 2006. Coverage grades and defender results can provide a stable
prior for secondary quality, but the current consumer page does not establish
that raw shell labels, receiver assignments, or arbitrary coverage-query CSVs
are included. It is therefore a secondary option for the planned PFR coverage-
quality ablation, not the preferred source for the QB/WR shell mechanism.

## 5. Lower-cost and secondary sources

### NFL Pro / Next Gen Stats

Official sources:

- <https://pro.nfl.com/nflpro>
- <https://support.nfl.com/hc/en-us/articles/35869706651156-NFL-Pro-FAQ-s-and-Answers>
- <https://support.nfl.com/hc/en-us/articles/35869716246804-How-much-does-NFL-cost-Monthly-and-Annual-Regular-and-Premium>

NFL Pro is included in NFL+ Premium ($14.99/month or $99.99/year at this
audit), updates Next Gen Stats the day after games, and publishes coverage and
man/zone splits in its analysis. It is attractive as a cheap live cross-check.
The public documentation does not establish bulk export, a stable API, or the
historical depth of each coverage field, so it is not yet a model-ingestion
recommendation. If subscribed for video/RedZone anyway, inspect it before
paying for another dashboard.

### MatchQuarters

Official/example sources:

- <https://www.matchquarters.com/p/2025-nfl-weekly-data-download-end-of-season-2025>
- <https://www.matchquarters.com/p/2024-nfl-weekly-data-download-end-of-season>

MatchQuarters publishes weekly defensive data downloads with coverage stats,
team dashboards and coverage matrices. It is useful for football interpretation
and independent spot checks, but the underlying provider changed from Field
Vision in 2024 to FTN in 2025 and the public pages do not establish machine-
readable bulk export. That makes it a research subscription, not a clean
longitudinal training feed.

### Sharp Football Analysis

Official sources:

- <https://www.sharpfootballanalysis.com/stats-nfl/nfl-coverage-schemes/>
- <https://www.sharpfootballanalysis.com/stats-nfl/nfl-coverage-stats-by-position/>

Sharp publicly displays team man/zone and middle-open/middle-closed rates plus
yards per target allowed by receiver position/alignment. These are useful
current-season sanity checks. No verified weekly historical CSV/API was found,
so they do not fill the replay requirement.

### Reception Perception

Official source:

- <https://receptionperception.com/subscription-page-new/>

Reception Perception advertises all historical NFL receiver data tables for
$99.99/year. Its charting is valuable for persistent receiver skill against
man, zone and press, but it is sampled receiver evaluation rather than a full
weekly opponent-coverage deployment feed. It could support a distinct receiver
trait prior, not replace the Fantasy Points/SIS defense matrices.

### SumerSports

Official sources:

- <https://sumersports.com/live/>
- <https://sumersports.com/the-zone/how-sumerlive-tracks-the-game/>

SumerLive now identifies formations, routes and coverages in real time from a
tracking-data model. Public access currently emphasizes live/postseason game
analysis, and no consumer historical export or API was verified. Monitor it;
do not base the 2026 pipeline on it yet.

### StatRankings CoverageIQ

Official sources:

- <https://statrankings.com/nfl/coverage-intelligence>
- <https://statrankings.com/checkout>
- <https://statrankings.com/terms-of-service>

CoverageIQ is much cheaper (`$24.99/month` or the displayed annual offer) and
has excellent-looking week filters, all eight common coverage shells, and
offensive/defensive player splits. It is **not an ingestion option under its
published terms**: automated extraction and ingestion into machine-learning
or AI models are explicitly prohibited. It can be used manually for a small
number of personal sanity checks, but do not scrape, automate, download into
the model, or treat the price as a substitute for a licensed feed.

## Recommended queue

1. Add a non-production audit loader for nflverse participation and quantify
   weekly shell availability, source-shift stability, and point-in-time lag.
2. Use it only for a prospectively frozen diagnostic. Do not add it to the
   production feature table because 2023+ data is postseason-only.
3. Complete the already-frozen Fantasy Points QB shell-fit test; it is the
   cleanest train/serve-aligned path with data already purchased.
4. If that mechanism is promising but needs defender-level detail, inspect
   NFL Pro first if it is already included in an NFL+ subscription, then take
   the combined SIS NFL/college seven-day trial and run the technical checks
   above. Use the college access to audit historical depth, identifiers,
   week-level exports and coverage availability for the existing CFB
   collection-only roadmap.
5. Consider FTN Stats only if its consumer plan demonstrates exportable weekly
   history; consider PFF+ or Reception Perception only for separately frozen
   player-quality priors.
6. Use MatchQuarters, Sharp and SumerLive as cross-check/research sources unless
   they document stable historical exports and private-model usage rights.
