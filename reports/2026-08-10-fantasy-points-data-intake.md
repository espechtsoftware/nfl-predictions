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
| Advanced Receiving | route, alignment, first-read and expected-points priors | validated | validated | validated | validated |
| Advanced Rushing | rushing process and expected-points priors | validated | validated | validated | validated |
| Advanced Passing | QB process and efficiency priors | validated | validated | validated | validated |
| Receiving Man vs. Zone | coverage-shell receiving priors | validated | validated | validated | validated |
| Receiving Separation by Routes | route-specific separation priors | validated | validated | validated | validated |
| Receiving Separation by Route Breaks | route-family separation priors | validated | validated | validated | validated |
| Receiving Separation by Coverage | coverage-specific separation priors | validated | validated | validated | validated |
| Receiving Separation by Alignment | alignment-specific separation priors | validated | validated | validated | validated |
| Coverage Matrix (Defense) | team coverage-shell deployment priors | validated | validated | validated | validated |
| Coverage Matrix (Offense) | team coverage-shell faced priors | validated | validated | validated | validated |

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

### QB Coverage Matchup prospective snapshot

The operator exported `qbCoverageMatchupExport.csv` on 2026-08-10 at
approximately 16:12 CDT with Schedule Week 1 selected. SHA-256 is
`888d31272b16b921af50fdeec0bcf20ed526873443495c4983079842a1b83c32`.
The file is a valid UTF-8-with-BOM CSV containing 37 unique QB rows and 32
columns under Player Details, Matchup, Man, Cover 2, Cover 3, Cover 4 and
Cover 6 groups. Every row has complete values and `Season=2025`.

This is not historical Week 1 data. The page exposes no season selector and
the vendor states that it uses the previous season through Week 3, then the
active season from Week 4 onward. The 2025 season fields are therefore source
performance, while `OPP`, expected FP/dropback and coverage grade are the
current 2026 matchup layer. Preserve this file as a **2026 Week 1 prospective
snapshot only**, with forecast season/week and retrieval timestamp supplied
as external immutable metadata. It cannot enter a 2022--2025 replay, the
Advanced prior diagnostic or any pre-Week-1 promotion decision. If collected
weekly before the shared slate lock, it can later be graded as a shadow QB
matchup signal.

The companion `wrCoverageMatchupExport.csv`, retrieved at approximately
16:32 CDT with the same Week 1 context, has SHA-256
`e0e369d4fee3130d0cfea29709d66ad9f74a6ae02f7495e2509c97ac6a221a5a`.
It is a clean 374-row, 38-column grouped export with unique RB/FB/WR/TE
identities and Player Details, Matchup, Man and Cover 2/3/4/6 blocks. All
rows declare source `Season=2025`; 241 blank split cells are legitimate and
every populated metric parses numerically. Treat it identically as a
prospective 2026 Week 1 snapshot. It cannot enter historical validation.

### Receiving Man vs. Zone family validation

All four files have a consistent 26-column grouped schema: Player Details,
then separate Overall, Man, Zone, Single-High and Two-High blocks containing
`RTE`, `TPRR`, `YPRR` and `FP/RR`. Group-qualified keys are unique, every row
has the declared season and expected width, and every populated metric parses
numerically. Blank rates are legitimate when a player recorded too few or no
events in that split.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 545 | `8033f7b539335a1d4bf4590ac7bcb0994c19eaf66b69a749803dbbf4f686e26d` |
| 2023 | 517 | `aef16ffb479911bbdfeb072dba8edf5fa4fc3ba6ec8aad8caf029009e8e850f5` |
| 2024 | 528 | `53e22d570a89c0e5578928cf7ca3634d94e6378fd3a896f67500e86361c0585c` |
| 2025 | 526 | `b448016a04cf883bfbe53913e0666812e72f53ab92f853c6cb71db594bc86404` |

The row universes match Advanced Receiving, including the known split 2022
Brock Wright record. These are full-season aggregates and are eligible only
as season N-1 priors. They are not added to the already-frozen Advanced
diagnostic. A separately preregistered future treatment could use adequately
supported RB/WR/TE differences such as Man-versus-Zone or Single-versus-Two-
High TPRR/YPRR; it must not search split fields after reading outcomes.

Exclude QB rows from any future receiving-rate use. The vendor reports a few
QBs with one receiving route but assigns `FP/RR` values as high as 336.46,
consistent with dividing full QB fantasy production by that route rather
than measuring receiving fantasy production. Low-route skill-player split
rates are also unstable, so minimum route support must be frozen before a
diagnostic.

### Receiving Separation by Routes family validation

All four files are clean two-row grouped exports with 95 columns. They contain
Player Details and Overall fields followed by Slant, Out, In/Dig, Hitch,
Comeback, Corner, Post, Go, Crossers, Screens, Flat and Backfield blocks.
Route blocks expose route count/share, separation score, YPRR, TPRR, win rate
and (where applicable) average depth of route. All populated cells parse
numerically; blank split metrics are expected when a player did not run or
qualify for a route type. Unlike Man-vs.-Zone, these exports already omit QB
rows and contain RB/FB/WR/TE only.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 540 | `a8d238e918f6aa78758b2bafbcdf7b28e07288b689cad30aed0c56d66ebb5d6c` |
| 2023 | 513 | `dd43d574f07f23f658571c1874cc8d3bbf4aee6660493b75c7f77934f21b4153` |
| 2024 | 522 | `82b36444dddda6ca22bb4ccec39f0562fc8093ca38db5c42fffd7c3b7aae39fa` |
| 2025 | 519 | `e0f9e709dbbba2e195e82a0155a3be22ce36744b9c2001ae444403c6fdf8c49e` |

The known 2022 Brock Wright split is the only duplicate identity group. These
are full-season aggregates and can be used only as season N-1 priors. The
large sparse route grid is acquisition evidence, not permission to search
route types against outcomes. Any later diagnostic must freeze a small
football-motivated feature block and minimum route-count support in advance;
the files do not alter the active Advanced diagnostic.

### Receiving Separation by Route Breaks family validation

All four files share a clean 41-column grouped schema: Player Details and
Overall, followed by Horizontally Breaking, Vertically Breaking, Static,
Shallow/Underneath and Backfield blocks. Each split contains route count and
share, separation score, YPRR, TPRR and win rate. Every populated metric
parses numerically; blank split rates are expected for unsupported route
families. The RB/FB/WR/TE row universes exactly match the more granular
Separation-by-Routes exports.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 540 | `124cce37f1d9eca30c7cec7b484c733d53738cce32256a00d054fca7a153f2cb` |
| 2023 | 513 | `93f2239b0b941dafb22cadae22cafd9e888dcd19b3379a756cd6b35c520665d9` |
| 2024 | 522 | `6677ceea04ed3522c7d8c11e73bd921dbd4e6e11f6c5acc49dd45b9d55249973` |
| 2025 | 519 | `d15e6fc9bdff4e61ebeded828a4a60a38bd52c3713e611cf1b984b7450fbf21c` |

The known 2022 Brock Wright split is again the only duplicate. This report is
a lower-dimensional possible alternative to individual route types, not an
additional simultaneous feature sweep. It remains acquisition-only, strict
season N-1, and outside the frozen Advanced diagnostic.

### Receiving Separation by Coverage family validation

All four files share a clean 38-column grouped schema. Player Details and
Overall are followed by Man, Zone and Red Zone blocks containing route count,
separation score, YPRR, TPRR and win rate, then Cover 2/3/4/6 blocks containing
route count, separation score and win rate. Every populated metric parses
numerically; blank rate cells are expected for unsupported splits. The
RB/FB/WR/TE identity multisets exactly match the Routes and Route-Breaks
exports, including the known split 2022 Brock Wright record. Multi-team
strings use a different ordering for 13/6/9/11 players by season, so future
identity logic must treat those lists as unordered rather than as different
players.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 540 | `6eaf9e0d63794f39679f048c24f409b79c0b798611708cdc71fadfe84328ea1c` |
| 2023 | 513 | `11538dfee6662572ab5502993a36fcb45e15a8d15f6ea7e288cd1082125c0787` |
| 2024 | 522 | `2d97db23f9452118c4b16da70e7eb024c161625f84778d701d4f84b6fd033db0` |
| 2025 | 519 | `0b7ccaffba50d0a2608cfab1dbc803fd57d46693d1984ff37bf85619c91193da` |

The charted identities are internally strong: Cover 2/3/4/6 route counts sum
to Zone routes for every row. Overall routes equal Man plus Zone plus Red Zone
for every row except Courtland Sutton, Devaughn Vele, Troy Franklin and Lucas
Krull in 2024; each Denver player has exactly one additional overall route
without a coverage-category assignment. Preserve those explicit counts and
missing classifications rather than forcing equality.

These are full-season aggregates and remain strict season N-1 priors. A
future outcome-unseen scheme diagnostic may combine a small, preregistered
set of adequately supported receiver coverage splits with prior-season
offense/defense Coverage Matrix rates. It must freeze route-support thresholds
and feature definitions before joining outcomes; this acquisition does not
alter or reopen the completed Advanced diagnostic.

### Receiving Separation by Alignment family validation

All four files share a clean 41-column grouped schema. The 15-field Overall
block contains route volume, separation/YPRR/TPRR/win rates, positive and
negative separation-event rates, target/reception/yard/touchdown totals, air
yards and average depth of route. Wide, Slot, Inline and Backfield each add
route count, separation score, YPRR, TPRR and win rate. Every populated metric
parses numerically, while blank split rates occur naturally for alignments a
player did not run. Wide plus Slot plus Inline plus Backfield route counts
equal Overall routes on every row in all four seasons.

| Season | Rows | SHA-256 |
|---:|---:|---|
| 2022 | 540 | `fa583a5beeb0b928345cf55cf8ead53df0e74bb95b738722283c0d7232e8531d` |
| 2023 | 513 | `db465e27bb74be7302cdf08ecbab6c628069dfbbfe08242424fbf0dd1a82f18f` |
| 2024 | 522 | `2feacbfffb60e62de01a1e5f93c79151ce8e80135fb440e7b465e14e047357b7` |
| 2025 | 519 | `2d88d147ce5d4e8a9f7a879f77c15c7593c0c42275081d0d3f0aa51533dc8fc1` |

The RB/FB/WR/TE identity multisets exactly match the Coverage, Routes and
Route-Breaks families; the two 2022 Brock Wright records remain the only
duplicate identity group. These files are also full-season aggregates and
may only attach as season N-1 priors. Alignment shares and split performance
are plausible role-stability inputs, but any future diagnostic must choose a
small support-aware block before outcomes rather than search the 41-column
grid. This completes the requested historical receiver-separation
acquisition without changing the current model or active scoring arms.

### Defense Coverage Matrix family validation

Each season contains exactly 32 unique teams and 22 complete columns grouped
as Team Details, Man/Zone, Middle of Field Look (Closed/Open), and Coverages.
The report supplies defensive dropbacks, man/zone and single-/two-high usage
with FP/dropback, plus Cover 0/1/2/2-Man/3/4/6 deployment rates. Every cell is
populated and numeric where expected.

| Season | Source file | SHA-256 |
|---:|---|---|
| 2022 | `2022-Defense-coverageMatrixExport.csv` | `45ff5738d28c19b0dd098f07de438d335a1be229c32066fc19eb90ad58b740bf` |
| 2023 | `2023-Defense-coverageMatrixExport.csv` | `52af5f92251eec85b34b875a24bccaa1e4d1b44196bf68b2e4e14ff65e35a394` |
| 2024 | `2024-Defense-coverageMatrixExport.csv` | `7270273e2e3ee400865c4c9c69b96d0b7eba2f0f005526942b5324a8fbe9606a` |
| 2025 | `Devense-coverageMatrixExport.csv` | `35ccde32e391b65426ace44452019389d1f1ef08d9cd5a279a6d5d2c9bd2b8c8` |

The 2025 data filename retains the vendor/operator typo and missing season
prefix; identify it by its exact hash rather than renaming the licensed
original. Even with group headers, the source repeats `FP/DB` twice inside
both Man/Zone and Middle-of-Field groups. A future parser must use the frozen
column positions to name Man, Zone, 1-High and 2-High FP/DB separately; an
ordinary dict reader would silently overwrite them. These season aggregates
are strict N-1 priors only and are not part of any current diagnostic.

### Offense Coverage Matrix family validation

The Offense view has the identical 32-team, 22-column grouped layout and the
same repeated `FP/DB` headers as Defense. Its rates describe the coverage
shells each offense faced rather than the shells a defense deployed. Every
cell is populated, seasons match, and all metric cells parse numerically.

| Season | SHA-256 |
|---:|---|
| 2022 | `35b8ed32866d1e52b2858a25c8a4dc146908b4b000303bcb41c05e5af0c45f06` |
| 2023 | `209c6df570801e56e7d43befe90af36143cfa60b6d12f3503545057e0d082a56` |
| 2024 | `a69f4ed67f06601d4127c0230f0ca12c73f9c6b1ec2cc041a0046379527d10dd` |
| 2025 | `dadb20089a722485f3c502711d9df093994a6f225190bfe562f557373e061595` |

Together the two views can support an outcome-unseen N-1 matchup hypothesis:
compare a receiver/offense's prior-season coverage profile with the target
opponent defense's prior-season deployment. They cannot support same-season
historical features because no weekly observation grain was exported. The
requested receiver Coverage and Alignment schemas are now acquired, but no
diagnostic is licensed until one small feature block, support threshold and
gate are preregistered before outcome joins.

## Importer gate

Do not infer one general schema across these materially different report
families. The separately preregistered Route Share and prior-season Advanced
diagnostics use narrow hash-locked importers; the prospective Coverage
Matchup snapshot remains isolated. Before loading any derived rows, require:

1. exact source hashes and unchanged originals;
2. declared season/week coverage and numeric ranges;
3. deterministic wide-to-long conversion;
4. explicit team/name normalization with ambiguity failures;
5. duplicate coalescing only when populated weeks do not conflict; and
6. tests proving Week N features use only observations from weeks `< N`.
