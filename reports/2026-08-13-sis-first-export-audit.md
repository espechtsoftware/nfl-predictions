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

## Exact next smoke export

On the same Pass Defense page:

1. set Season 2025 to 2025;
2. set Week 1 to Week 1;
3. keep playoffs off, Split by Game on, and minimum targets 1;
4. press `Submit`;
5. wait for the table to refresh and verify the visible `Games` values are 1;
6. download as `sis/2025-week01-pass-defense-all-v2.csv`.

If the new file still has season totals, the export/control is defective. If
it has one-game values but no explicit week/game key, a manifest-encoded
season/week window can still support carefully controlled weekly files, though
the missing stable ID remains a material matching risk.
