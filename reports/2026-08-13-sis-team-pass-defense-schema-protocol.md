# SIS team pass-defense filtered-view schema/cap protocol

Status: frozen before any filtered team-pass-defense response, CSV schema,
row count, or performance value is read. This is a bounded acquisition
feasibility screen, not a scoring arm.

## Question

Can the normal paid SIS team leaderboard produce auditable game-grain defense
profiles split by broad WR alignment and broad coverage family, with both
volume denominators and value fields, without hitting the 200-row cap or
losing stable team identity? A passing screen licenses a separately frozen
strictly-prior historical acquisition plan. It does not license a model,
dependence transform, lineup comparison, or weekly production query.

This is the next item in the reconciled queue after the Fantasy Points QB
shell test. It is distinct from the retired individual-WR/CB alignment sample,
whose private state must remain untouched at `7/12` requests.

## Exact normal-UI sample

Use only 2025 Week 1, regular season, Team Leaderboards, Split by Game, all
teams, pass-defense views. Set minimum targets and minimum attempts to zero so
the screen directly reveals whether zero-opportunity team rows are retained.
Restrict receiver position to WR. Submit the following four mutually exclusive
profile slices in each of Pass Defense Totals and Pass Defense Value, for eight
planned Submit calls total:

| Slice | `PassDefenseFilters.TargetLinedUp` | `PassDefenseFilters.Schemes` |
|---|---:|---|
| `wide-man` | Wide `2` | Cover 0 `0`, Cover 1 `1`, Man Cover 2 `5` |
| `wide-zone` | Wide `2` | Cover 2 `2`, Cover 3 `3`, Cover 4 `4`, Cover 6 `6` |
| `slot-man` | Slot `3` | Cover 0 `0`, Cover 1 `1`, Man Cover 2 `5` |
| `slot-zone` | Slot `3` | Cover 2 `2`, Cover 3 `3`, Cover 4 `4`, Cover 6 `6` |

Every request must also contain `PassDefenseFilters.ReceiverPos=4`, the exact
season/week/group/subtype, and `TimeFilters.ByGame=1`. Incidental family,
subtype, or filter-change refreshes are blocked client-side. Only a visible
Submit is armed and metered. The scientific plan is eight queries; the hard
durable ceiling is ten solely to permit at most two byte-identical operational
retries after a response/download failure. No extra alignment, shell, route,
season, week, entity, or report may consume that reserve.

## Intake and no-outcome rule

Preserve each raw licensed CSV locally under ignored `sis/`, its SHA-256,
exact submitted payload, retrieval time, headers, row count, and the response's
identity-only fields. The analyzer may read only:

- Season, Week, Games, Team, Opponent and stable SIS ID fields;
- CSV headers and row count; and
- file bytes for SHA-256 verification.

It must not parse, summarize, rank, correlate, print, or branch on targets,
completions, yards, touchdowns, Points Saved, EPA, Boom%, Bust%, or any other
performance value. Record `outcome_values_read=[]` in the result.

## Mechanical pass gate

All conditions are required:

1. all eight exact artifacts exist and re-hash to their manifests;
2. each submitted payload matches the frozen filters and report subtype;
3. each API row is Season 2025, Week 1, Games 1 and carries a stable team ID;
4. each slice has one row per returned team, never more than 32 teams and
   never the 200-row cap;
5. Totals and Value return exactly the same team-ID set within each slice;
6. the union of the four profile slices covers all 32 team IDs;
7. Totals contains a coverage-snap denominator plus targets, accepting only
   the vendor-label aliases `Cov. Snaps`/`Coverage Snaps` and
   `Tgts`/`Targets`; and
8. Value contains `Points Saved` and `PS Per Play`.

Missing teams in an individual slice are allowed only because the zero-target
profile may be structurally absent; a future importer must reconstruct those
zeros against the complete schedule rather than treat missing as unknown.
Duplicate team rows, player-grain rows, mismatched Totals/Value identities,
missing denominators, cap binding, ambiguous scope, or any unplanned request
fails the screen.

## Branch rule

- Pass: write disposition `sis-team-pass-defense-schema-passes`. Freeze a
  bounded 2019 and 2021--2025 strictly-prior acquisition plan for these exact
  eight report/slice views, then separately collect point-in-time receiver
  alignment profiles. Only after those sources pass intake may an isolated,
  mean-preserving target-allocation transform face the incumbent G0/G1
  dependence scorecard, requiring QB-WR improvement and WR-WR
  must-not-worsen.
- Fail: write disposition `sis-team-pass-defense-schema-fails` and close this
  exact consumer-UI path. Do not mine narrower shells, routes, players, weeks,
  thresholds, or alternative report views on the observed result.

No lineup score is read under either branch.
