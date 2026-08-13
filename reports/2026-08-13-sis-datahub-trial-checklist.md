# SIS DataHub Pro trial checklist

Date: 2026-08-13

SIS offers the seven-day trial as a combined NFL and college-football trial,
not an NFL-only trial. Use both parts. The primary purpose is to establish NFL
fitness; the college portion should also determine whether SIS can fill the
historical-performance gap behind the repo's existing 2026 CFB
salary/contest-collection scaffold. Do not assume that a top-20 trial export
is a complete training dataset.

## Data handling

Keep unedited exports under the gitignored `sis-trial/` directory. Do not
commit raw vendor files, account credentials or browser state. Licensing
correspondence is not a prerequisite for this technical evaluation.

## Trial smoke exports

For each download, save the unedited CSV under a temporary folder named
`sis-trial/`; do not commit vendor data. Apply the filter before downloading
and use filenames that encode season, week range, leaderboard and coverage.

1. Team coverage deployment, 2025 regular season:
   all coverage; man; zone; Cover 0; Cover 1; Cover 2 Man; Cover 2; Cover 3;
   Cover 4; Cover 6. Capture coverage snaps/plays and rate/share fields.
2. Team coverage deployment, a single 2025 week:
   repeat all-coverage plus at least Cover 1 and Cover 3. This verifies true
   individual-week filters rather than a season-total display.
3. QB passing, 2025 regular season:
   all/man/zone plus Cover 1 and Cover 3. Include opportunity denominators
   (dropbacks or attempts), yards, touchdowns, efficiency/EPA/Total Points,
   accuracy and explosive/boom fields where offered.
4. Receiving, 2025 regular season:
   all/man/zone plus Cover 1 and Cover 3. Include routes, targets, receptions,
   yards, touchdowns, target/route rates, YPRR, aDOT, alignment and
   efficiency/value fields where offered.
5. Pass defense/defensive backs, 2025 regular season:
   all/man/zone plus Cover 1 and Cover 3. Include coverage snaps or routes
   defended, targets, catches, yards, touchdowns, target rate, passer rating,
   alignment and value/efficiency fields where offered.
6. Historical reach:
   attempt the same minimal all-coverage team/QB/receiving exports for 2019,
   2021 and 2022. Record the earliest selectable season and whether the column
   schema changes.

## College-football smoke exports

This is an audit extension, not authorization to build or deploy a CFB model.
The current repo intentionally collects only DraftKings CFB slates, salaries
and contest fills during 2026 for a 2027 go/no-go decision. Use the included
trial access to learn whether SIS could supply the missing historical inputs:

1. Record the earliest available college season, selectable week ranges and
   whether regular season, conference championships and bowls are separable.
2. Export one complete-looking season and one individual week from each
   available team-offense, team-defense, passing, rushing and receiving
   leaderboard. Prefer 2023--2025 when selectable.
3. Repeat the NFL coverage smoke tests for college where those filters exist:
   defensive shell deployment, QB performance by coverage, receiver
   performance by coverage/route/alignment and pass-defense/DB results.
4. Capture school, conference, opponent, game/date, season/week, position and
   stable player/team identifiers. Record transfer-player and duplicate-name
   behavior explicitly; NFL/GSIS matching assumptions do not transfer to CFB.
5. Record whether the 20-row trial cap also applies to college, whether CSV
   exports preserve the active filters, and when a completed Saturday's data
   becomes available.
6. Sample the injury, blocking/pass-rush and team pace/pass-rate views if they
   are exposed in the trial. These address CFB availability, line-play and
   play-volume gaps that our DraftKings collection cannot reconstruct.

The college audit can materially strengthen the 2027 decision even if the
trial is too row-limited to form a training panel: it tells us whether a paid
month could backfill history instead of waiting several seasons for our own
collection.

SIS's own product materials say it charts every NFL and FBS game, exposes
Universal Player IDs, and aims to keep statistics and filters consistent
across NFL/CFB player and team leaderboards. Treat those as claims for the
trial to verify in the actual CSVs, especially stable IDs and week-level CFB
filters.

The official FAQ says trial leaderboards return only 20 rows. That is enough
to inspect the file and feature schema, but not enough to run a historical
arm. Do not work around a trial limit by scraping or account manipulation.

The first Pass Defense export is audited in
`reports/2026-08-13-sis-first-export-audit.md`. It confirmed the 20-row cap
and useful coverage-opportunity columns, but returned full-season aggregates,
no week/game/opponent or stable ID, and a broken `[object Object]` Rank field
despite the visible Split-by-Game check. The next required smoke is a 2025
Week-1-only query after explicitly pressing Submit and verifying `Games=1`
before download.

That retry was byte-identical to the full-season export because Submit had not
been pressed. A subsequent correctly submitted full-2025 Split-by-Game export
passes the grain test: it includes `Week` and `Opp.`, every row has `Games=1`,
and values differ from the aggregate. It remains limited to the top 20
player-games and has no stable IDs. This confirms the workflow rule: after
every filter change, press Submit and verify the rendered table before
Download.

## Acceptance checks for each CSV

- Season and selected week range are present or can be encoded unambiguously.
- Player/team names are accompanied by a stable SIS or universal player ID;
  if no ID is exported, record that as a material matching risk.
- Opportunity denominators are present; never model a rate without its sample
  size.
- Coverage labels distinguish Cover 2 Man from zone Cover 2.
- CSV row count and displayed row count agree.
- Changing a week or coverage filter changes the exported values.
- The file is valid comma-delimited text with one header row, no merged group
  headers and no hidden totals masquerading as player rows.
- The source's weekly availability is early enough for our Sunday-main lock.

## Purchase decision

Buy at most one paid month initially, selecting the product required after the
combined trial, and only if:

1. coverage history reaches enough of 2019--2025 to support walk-forward
   tests (or provides a clearly useful independent 2026 live signal);
2. full paid exports can recover all relevant players, not merely the top 200;
3. stable identifiers and opportunity denominators are present; and
4. weekly updates arrive before lineup lock.

Treat useful college history as additional value, not as a substitute for
failing the NFL requirements. Conversely, record a separate CFB-only purchase
case if its historical coverage is strong enough to accelerate the 2027
decision.

If any condition fails, cancel by emailing SIS before renewal. The official
FAQ says cancellation is handled by email and continues through the current
subscription period.

## Planned modeling use

First import and audit the raw files with source hashes, schemas and explicit
availability timestamps. Then run a score-free coverage diagnostic using only
weeks `< W` to predict week `W`. Do not join a game's own coverage result to
that same game's prediction. A successful score-free diagnostic may license a
separately frozen lineup arm; the subscription alone does not justify adding
features to production.
