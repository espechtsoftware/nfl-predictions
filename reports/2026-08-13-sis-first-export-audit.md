# SIS first trial-export audit

Date: 2026-08-13

## Input

- Local file: `sis/2025-pass-defense.csv` (raw file is gitignored)
- SHA-256: `cb9d1ebd32a9e5d97a9e4e84e858860a685d972fe58c5003f9142bef19d5daa8`
- Visible filter state: NFL Player Leaderboards / Pass Defense; season 2025;
  weeks 1--22; playoffs excluded; Split by Game checked; minimum targets 1.

## Findings

The file is valid comma-delimited text with one header and 20 data rows. It
contains 19 columns:

`Rank`, `Season`, `Player`, `Team`, `Pos.`, `Games`, `Cov. Snaps`, `Tgts`,
`Catchable`, `Comp`, `Yds`, `TDs`, `Ints`, `Dropped INT`, `Int. Yards`,
`Pass Def.`, `Intended Air Yards`, `DPI`, and `DPI Yds`.

All numeric fields parse, all 20 player names are unique, and no field is
blank. The coverage-opportunity and outcome columns are potentially useful
for a defender-quality prior.

The export is not yet a usable weekly/PIT dataset:

- it is exactly the trial's documented 20-row cap;
- every `Rank` value is the broken literal `[object Object]`;
- it has no week, game, opponent, date or stable SIS/universal player ID;
- all rows are season aggregates (`Games` ranges from 12 through 17), despite
  the visible `Split by Game` check.

The likely explanation is that the checkbox was changed after the last query
and `Submit` had not yet refreshed the rendered table, or that this report's
CSV ignores that control. We must distinguish those possibilities before
judging the product.

## Week-1 retry result

The requested retry was saved as
`sis/2025-week01-pass-defense-all.csv`. It has SHA-256
`cb9d1ebd32a9e5d97a9e4e84e858860a685d972fe58c5003f9142bef19d5daa8`,
which is exactly identical to the first full-season file at both the hash and
byte level. It therefore did not apply the Week 1 window or Split-by-Game
state to the downloaded result. Do not make additional season downloads from
this report until the rendered-table-versus-download behavior is isolated.

The remaining distinction is observable in the browser: after pressing
`Submit`, did the visible table itself change to rows with `Games=1`? If no,
the query/filter submission failed. If yes, the Download button returned a
stale or unfiltered CSV.

## Correct submitted split-by-game export

The operator identified that Submit had not been pressed on the failed retry
and then supplied `sis/SIS DataHub - NFL.csv` after applying the full-2025
Split-by-Game query. SHA-256:
`23e39cf6413a39429e9818573d4b1f58efcb52bab667b2a6f82461376beba55c`.

This file behaves correctly:

- it adds explicit `Week` and `Opp.` columns;
- all 20 rows have `Games=1`;
- it contains 12 distinct weeks, 19 players, and no duplicate
  `(Player, Team, Week)` key;
- all fields are populated and numeric fields parse;
- its contents differ from the season aggregate.

The report therefore supports filterable game-level CSV export. The file is
still only the top 20 player-games across the requested season because of the
trial cap; it is a successful schema/PIT-grain smoke test, not a complete
historical panel. `Rank` remains broken and there is still no stable player or
game ID, although `(Season, Week, Team, Opp., Player)` provides a workable
auditable bridge candidate.

## Exact next smoke export

On the same Pass Defense page:

1. set Season 2025 to 2025;
2. set Week 1 to Week 1;
3. keep playoffs off, Split by Game on, and minimum targets 1;
4. press `Submit`;
5. wait for the table to refresh and verify the visible `Games` values are 1;
6. download as `sis/2025-week01-pass-defense-all-v2.csv`.

This retry is no longer required: the correctly submitted full-season
Split-by-Game export already proves game-level filtering. The next useful
technical test is whether a paid account returns all qualifying player-games
or only its documented top 200, and whether an API/full-export option avoids
that truncation.
