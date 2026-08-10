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
| Weekly Target Share | primary player opportunity | pending | pending | pending | pending |
| Weekly Snap Share | role/injury replacement | pending | pending | pending | pending |
| Weekly PROE Report (Offense) | secondary team context | pending | pending | pending | pending |
| Weekly PROE Report (Defense) | secondary opponent context | pending | pending | pending | pending |
| Weekly Fantasy Points Scored | identity/scoring audit only | pending | pending | pending | pending |
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

## Importer gate

Do not freeze the normalized schema or write the importer until at least one
file from every requested report family has been inspected. Before loading any
derived rows, require:

1. exact source hashes and unchanged originals;
2. declared season/week coverage and numeric ranges;
3. deterministic wide-to-long conversion;
4. explicit team/name normalization with ambiguity failures;
5. duplicate coalescing only when populated weeks do not conflict; and
6. tests proving Week N features use only observations from weeks `< N`.
