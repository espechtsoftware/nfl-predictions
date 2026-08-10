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
| Weekly PROE Report (Defense) | secondary opponent context | validated | validated | validated | validated |
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

### Defense PROE family validation

Every season contains 32 unique defenses and the same 25-column schema:
full team name, games, season, separate location/nickname fields, `W1`--`W18`,
and aggregate `PROE`. Every populated value parses numerically, and each
defense's populated weekly count equals its reported games. The 2022 total is
542 rather than 544 because two teams correctly report 16 games. Every file
is distinct from its same-season Offense PROE export.

| Season | Rows | Populated weekly values | SHA-256 |
|---:|---:|---:|---|
| 2022 | 32 | 542 | `ea07de3dff814c88599af1ff7e64e9c2ef2021ef53c2133442cd7086dff8be2b` |
| 2023 | 32 | 544 | `f7ab17479bf6b68a42db1147e963f53ab5059dba3c1331c32efd1539a4505dc6` |
| 2024 | 32 | 544 | `38951d500d25d8ec8f2e331a6eb347e5636a1245eb46a0468ca7dc4ee7b425c3` |
| 2025 | 32 | 544 | `07940fdae0475756d29329c9f5279534ec7069b9d35850d95fb46a30b5a4435b` |

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

### Advanced Receiving family validation

The first attempted 2022 export (SHA-256
`8951a30802e93bc602c07f63fd3a43107f42a15bd1dbb97775c7dd11687b1356`)
was a 32-team season aggregate and was subsequently replaced. The four stable
files below are the correct **Player** view. They share a 63-column schema with
player/team/position identity plus route participation, air-yard, target,
first-read, alignment, efficiency, fantasy-point and expected-fantasy-point
fields. Every row has the declared season and a consistent CSV width.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 545 | `28a0c4d19cb1578c0d3eb36bea84f971ae1e645c72d784915b031b1f3fec4313` |
| 2023 | 517 | `38a4424f952b62250e6dd721f34b1b95de4704d01686f41aa242ba39fcc6510f` |
| 2024 | 528 | `c656488c84fa3a90d536690546d9a5dee42cd5c3ac8683d1c1b67166a6195753` |
| 2025 | 526 | `354648754659d2308b32b3c3b5ab9dd2423608ae82820c07b664edea93b81974` |

These reports remain full-regular-season aggregates (`G` reaches 16--17 and
there is no week column). They may be evaluated only as a prior-season/career
prior; using a season's final values for a slate within that same season would
leak future games. The weekly Route/Target/Snap files remain the primary
same-season point-in-time sources. The known Brock Wright 2022 vendor split
also appears here as two DET rows (8 and 9 games); any prior-season importer
must coalesce additive counts and recompute rates rather than choosing one row
or adding already-normalized rates. The separately named Defense Advanced
Receiving exports are still 32-team season aggregates and are not accepted as
player history.

### Advanced Rushing family validation

All four stable files are the **Player** view with both group and column
headers enabled. The two-row schema is essential: the six columns named
`ATT`, `ATT %`, `YDS`, `TD`, `YPC`, and `Success %` occur once under `Zone
Concept` and once under `Man/Gap Concept`. Group-qualified column keys are
unique, every data row has the expected 42 fields, and every row declares the
expected season.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 354 | `05600c957a50fa63116517ffe72a54f73a5af47496aa52f556b112cfbee6164f` |
| 2023 | 334 | `c24551981349c807b429ca71bbbe4ce8efa6f0e5d695f409e13875b54b4a0f43` |
| 2024 | 322 | `3300d87d81080232a8f619558d9b9e009e5ec9e83ad4778a227c4e14cb102c30` |
| 2025 | 329 | `fcd858042ddc1f90bd60dd1461a9cf4f6402ea127c68d681e8ec3a0e86c9c390` |

The files cover QB/RB/FB/WR/TE rushing activity and contain total rushing,
expected-run/yards, inside-five, success/stuff, missed-tackle, yards-after-
contact, zone, man/gap, fantasy-point and expected-fantasy-point metrics. Like
Advanced Receiving, they are full-season aggregates with no week column.
They are eligible only as strict prior-season/career priors; same-season use
would leak future games. The superseded no-group-header downloads must never
be ingested because ordinary name-based CSV readers silently overwrite the
first repeated metric block with the second.

### Advanced Passing family validation

All four files are the complete **Player** QB view with group and column
headers. They share 59 columns grouped as Player Details, Passing, Scrambles,
Passing Advanced and FPTS. Every data row has the expected width, position is
QB throughout, season matches the filename, and group-qualified column names
are unique.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 83 | `55d29f3e7995c0f08c6943d02e7f28a55744a11dd82b167821d1c61509e9aeba` |
| 2023 | 80 | `5085de7ab8dc8f9d1f228dcff60cec2ccff73d2dc2ed72b09921ad0c87424474` |
| 2024 | 77 | `753b7a000e7483e4633b1416b33402dad358be95b5bf503fad8641e0094be069` |
| 2025 | 77 | `615fc914ff57b708d09ce525007df09f52db1370172aaa3f0d7456d0046da5c1` |

Potential prior-season QB ceiling inputs include CPOE, aDOT, deep-throw rate,
first-read rate, turnover-worthy throw rate, pressure/sack behavior, scramble
rate and fantasy points per dropback/opportunity. These files are again
full-season aggregates with no week column: season N values are forbidden for
all season N targets and first become eligible in season N+1.

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
