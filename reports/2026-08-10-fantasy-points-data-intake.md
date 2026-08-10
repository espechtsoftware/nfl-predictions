# Fantasy Points Data Suite intake

Frozen: 2026-08-10 after the operator purchased the standalone $200 Data
Suite. This file records acquisition and validation state without committing
licensed vendor rows.

## Storage and provenance

- Keep untouched downloads under repository-local `fantasy-points/`. The
  directory is gitignored because the exports are licensed inputs.
- Do not open and resave, rename, merge or normalize original files. Derived
  data must go to a separate ignored path and retain the source filename and
  SHA-256 in its manifest.
- The git repository does **not** transport these files between computers.
  Copy the ignored directory separately or establish an operator-approved
  private backup before a machine move.
- Vendor reports are postgame data. A Week N replay may use observations only
  through Week N-1; season aggregate columns are never point-in-time inputs.

## Requested exports

For each report, select one season at a time, all weeks, all teams and all
available offensive positions, clear player filters, and prefer CSV. Acquire
2022, 2023, 2024 and 2025.

| Report | Purpose | 2022 | 2023 | 2024 | 2025 |
|---|---|---:|---:|---:|---:|
| Weekly Route Share | primary player opportunity | validated | validated | validated | validated |
| Weekly Target Share | primary player opportunity | validated | validated | validated | validated |
| Weekly Snap Share | role/injury replacement | validated | validated | validated | validated |
| Weekly PROE Report (Offense) | secondary team context | validated | validated | validated | validated |
| Weekly PROE Report (Defense) | secondary opponent context | pending | pending | pending | pending |
| Weekly Fantasy Points Scored | identity/scoring audit only | validated | validated | validated | validated |
| Advanced Receiving | route, alignment, first-read and separation candidates | pending | pending | pending | pending |

Do not bulk-add these fields to production. The frozen evaluation remains:
walk-forward player residual/tail calibration, then candidate-union oracle
gain, then one exact fixed-budget lineup panel.

## Validated source files

### `2022-receivingRouteShareReportExport.csv`

- SHA-256:
  `68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637`
- Encoding: UTF-8 with BOM; valid CSV.
- Shape: 647 data rows and 25 columns.
- Scope: `Season=2022` only; `W1` through `W18`; QB 84, RB 156, FB 15,
  WR 255 and TE 137.
- Values: every player has at least one weekly value; all populated weekly and
  aggregate percentages parse numerically and lie in `[0, 100]`.
- Vendor-specific normalization required: Baltimore/Houston/Cleveland/Los
  Angeles abbreviations differ from the warehouse convention, and 31 players
  have comma-delimited multi-team season labels.
- Source quirk: Brock Wright / DET / TE appears in two rows with disjoint week
  blocks (Weeks 1--10 versus 11--18). Treat this as one player-week series and
  fail if duplicate rows ever contain conflicting non-null values for the same
  week. This is not an operator export error.
- Stable player IDs are absent, so ingestion must use the repository's audited
  name/team/season-to-GSIS bridge and emit unresolved/ambiguous match reports.

### Route Share family validation

All four files share the same 25-column schema (`Rank`, player/team/position,
games, season, `W1`--`W18`, season `TM RTE %`). Every populated weekly or
aggregate value parses numerically and lies in `[0, 100]`; every row has a
name/team/position, and no CSV row has a width error. The aggregate column will
be retained for source auditing but cannot be used as a weekly model feature.

| Season | Rows | SHA-256 | Duplicate/conflicting player-week values |
|---:|---:|---|---:|
| 2022 | 647 | `68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637` | one split row / zero conflicts |
| 2023 | 621 | `c4940b8d7163b2baf0734b0b70d5c5c9bee456c1c004c61341ebcc5aa97a81d0` | zero |
| 2024 | 625 | `45b68bb3fef0cd74c96ad88943141f37865647ef699f1e41553fca895f5408f7` | zero |
| 2025 | 637 | `305b5ff5523e09645ef41bd7f3c1f290b035e3d97b5f1d0c942815feebc43717` | zero |

The Windows `Zone.Identifier` sidecars are download metadata, not report data,
and must be excluded from ingestion.

An outcome-blind identity/coverage audit joined only season, week, normalized
name, position and team to the accepted corrected K1 player snapshots, then
weighted coverage by roster appearances without reading actual scores. The
simple existing abbreviation bridge plus `FB→RB` produced no ambiguous match
and no missing feature ID. Route Share coverage of offensive roster
appearances is already high enough for a measured pilot:

| Season | All candidate appearances | Selected-book appearances |
|---:|---:|---:|
| 2022 | 95.11% | 93.84% |
| 2023 | 93.39% | 94.50% |
| 2024 | 94.64% | 94.89% |
| 2025 | 96.14% | 96.35% |

Missing route observations must remain missing rather than being imputed to
zero: the salary/player universe includes inactive and deep-reserve players
who may not record a route.

The separate hash-locked Route Share importer has now created private table
`nfl_raw.fantasy_points_route_share` with 27,305 normalized weekly rows,
26,881 resolved rows, 1,029 resolved GSIS players and all four source hashes.
The licensed originals remain local/ignored. General ingestion for the other
report families is still unfrozen.

### Fantasy Points Scored family validation

All four season files use the same 26-column schema: the common identity and
`W1`--`W18` fields plus `FP/G` and `FP`. Their row/position universes exactly
match the corresponding Route Share files. Every populated score parses
numerically; negative weekly values are valid fantasy outcomes. The sum of
displayed one-decimal weekly values differs from the vendor season total by at
most 0.3 points, consistent with rounding. The 2022 Brock Wright split is the
same non-conflicting duplicate observed in Route Share.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 647 | `b22af974eefb7df47df00875f0187c89430d527133cd66ae9c3e12ca7f99b5b0` |
| 2023 | 621 | `c6a8565cc6fd239ed256d8b7e72adbd286d0f67a5c69784bf3e4bd2d6979db7f` |
| 2024 | 625 | `b912e9a52c59214d8518ba8241c0783954d1a0cda4efa33ef69aa6d20faf71fe` |
| 2025 | 637 | `b169cbeb2695790f03583c4629fc13f500936ab73ebc3984b3d53274d981f954` |

The unprefixed `fptsScoredReportExport.csv` is byte-identical to the named
2023 export and is ignored as a duplicate. These scores may validate identity
and broad scoring reconciliation only; they do not replace authoritative
DraftKings `player_week_actuals` labels.

### Offense PROE family validation

Every season export contains exactly 32 unique teams and the same 25-column
schema: team identity, games, season, `W1`--`W18`, and aggregate `PROE`. Every
populated value parses numerically, and each team's populated weekly count
equals its reported games. Negative values are expected. Season aggregate
PROE is retained for source auditing only; replay features must be constructed
from strictly prior weekly values.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 32 | `28cc6fe66fb15b254559246015e31bbb67e8529118bd0b43452b0107bce8479d` |
| 2023 | 32 | `f164b37ab0eff22cbbb9fc06352a7b25df1cc4c29730b17e1b1af80ce03f4afa` |
| 2024 | 32 | `2ae96cc7cee70c65f21b122726af1a099a1ebc4d12aadfe97e7465b408031d41` |
| 2025 | 32 | `a1d85bc3e183a501b846782692b480cb0efb6ede2be387cb11966a5981638102` |

The unprefixed `proeReportExport.csv` is byte-identical to the named 2024
offense export and is ignored as a duplicate.

### Snap Share family validation

The four stable files have the same 25-column identity/weekly schema
as Route Share, ending in `Snap %`. Their player/position universes match the
corresponding Route Share and Fantasy Points Scored files; every populated
value is numeric in `[0, 100]`. The 2022 Brock Wright split is again
non-conflicting. The first observed 2022 download was subsequently replaced by
the operator with the complete all-position/zero-snap export; only the stable
647-row file below is valid.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 647 | `0fec6ed4e7cb94af7c530d77530304cdc64d73fc38267a6bdcc91d2f193964b8` |
| 2023 | 621 | `8091dd5be6c3bc47976b334e8bf0157bd82cd8c510e5c88a1d68ab88904517a2` |
| 2024 | 625 | `58af626a07e0f04d274adfd6c0237c1ef52cd3571ca26ed086066be119058324` |
| 2025 | 637 | `87de49352d816292ce6d09e2e38abe74ec5a9ad9d027e01dbceb0855c2bd01b3` |

The no-hyphen `2024offenseSnapShareReportExport.csv` is byte-identical to the
named 2024 export and is ignored as a duplicate.

### Target Share family validation

All four files use the same 25-column identity/Weeks 1--18 schema as Route
Share, ending in `TM TGT %`. Every populated weekly and aggregate value parses
numerically and lies in `[0, 100]`; season, name and position fields are
complete. The known 2022 Brock Wright split again has disjoint weeks and zero
conflicts. Multi-team strings sometimes list teams in a different order than
Route/Snap; identity normalization must treat them as unordered team sets
rather than as different players.

| Season | Rows | Populated weekly values | SHA-256 |
|---:|---:|---:|---|
| 2022 | 647 | 6,787 | `89ad27d72e52199e11beea11308883a06c74dbf4912c9f56b951af9096856893` |
| 2023 | 621 | 6,816 | `1633732c2cd9a023df089e74db1d23c8ce5ca2e9a09c75cbb16383be7df1d60f` |
| 2024 | 625 | 6,818 | `c9719fcada009cdd18f6d69b62f0cc390cb8a786d949d613dc683bc4b843f4c1` |
| 2025 | 637 | 6,884 | `257f752d8cae71ac057335148d2eb4a733cfd06a99a96b07966afcb1d9ca74f8` |

## Importer gate

Do not freeze a *general multi-report* normalized schema or importer until at
least one file from every requested report family has been inspected. The
separately preregistered Route Share-only diagnostic may use its narrow
hash-locked importer from
`reports/2026-08-10-fantasy-points-route-share-experiment.md`; it must not
infer schemas for the pending families. Before loading any derived rows,
require:

1. exact source hashes and unchanged originals;
2. declared season/week coverage and numeric ranges;
3. deterministic wide-to-long conversion;
4. explicit team/name normalization with ambiguity failures;
5. duplicate coalescing only when populated weeks do not conflict; and
6. tests proving Week N features use only observations from weeks `< N`.
