# SIS DataHub Pro trial checklist

Date: 2026-08-13

Use the NFL-only seven-day trial. Do not buy the NFL+NCAA plan for this
project. The purpose of the trial is to establish fitness and licensing, not
to assume that a top-20 trial export is a complete training dataset.

## Before downloading in bulk

Email `sales@sportsinfosolutions.com` with this question:

> I am evaluating NFL DataHub Pro for a private, personal, noncommercial DFS
> prediction model. May I download the CSV leaderboards, retain those files
> after my trial or subscription ends, derive model features from them, and
> use those features privately? I will not republish, resell, transfer, or
> expose the source data. If permitted, what historical NFL seasons include
> coverage-type filters, when are new weekly games available, and is there an
> export/API option that returns every qualifying player rather than only the
> top 200 leaderboard rows?

Retain their written answer outside the public repository and record only the
permission/limitations—not contact details or credentials—in `HANDOFF.md`.
Do not ingest SIS rows until the answer permits the intended use.

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

The official FAQ says trial leaderboards return only 20 rows. That is enough
to inspect the file and feature schema, but not enough to run a historical
arm. Do not work around a trial limit by scraping or account manipulation.

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

Buy at most one NFL monthly subscription initially, and only if:

1. written private-model and retention permission is affirmative;
2. coverage history reaches enough of 2019--2025 to support walk-forward
   tests (or provides a clearly useful independent 2026 live signal);
3. full paid exports can recover all relevant players, not merely the top 200;
4. stable identifiers and opportunity denominators are present; and
5. weekly updates arrive before lineup lock.

If any condition fails, cancel by emailing SIS before renewal. The official
FAQ says cancellation is handled by email and continues through the current
subscription period.

## Planned modeling use if licensed

First import and audit the raw files with source hashes, schemas and explicit
availability timestamps. Then run a score-free coverage diagnostic using only
weeks `< W` to predict week `W`. Do not join a game's own coverage result to
that same game's prediction. A successful score-free diagnostic may license a
separately frozen lineup arm; the subscription alone does not justify adding
features to production.
