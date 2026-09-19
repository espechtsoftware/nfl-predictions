# Salary-week contract repair: validation in progress

Recorded September 19, 2026, 00:46 UTC. Production fix branch `fix/2026-09-salary-week-resolution`, source `bae741de`; SQL last changed at `99440a23`. Full isolated feature build and projection comparison requested from the workstation in lab handoff `410fe35`. No live feature/projection tables, schedules, entries or serving policy have changed.

## Finding and repair

DraftKings ingestion deliberately writes NULL `week`, with a comment promising downstream resolution against schedules. The salary feature SQL instead excluded every NULL-week row without implementing that resolution. The workstation independently measured 722,516 raw 2026 rows, all with NULL week; the live salary feature table contained no 2026 rows. As a result, all 928 Week-2 inference rows had missing usage history and zero prior games despite available Week-1 statistics and snaps. A routine refresh of the original SQL cannot fix the mismatch.

The repair resolves a missing week from source season, canonical team and the player's own game timestamp converted to the Eastern calendar date. It accepts only one distinct regular-season game and week for that team/date. Duplicate identical schedule records collapse; conflicting games/weeks, preseason dates, unknown teams and missing timestamps stay unresolved. Explicit source weeks retain their existing behavior. The historical vendor branch, salary source precedence, deduplication and usage rolling windows are unchanged.

SQL SHA-256: `d9ce21722065b65dc7ac03f6bf7d3dcb517b60902a215e1fb29d73d5e7d8f5a8`.

## Completed validation

- Existing feature SQL module: **77 passed, 1 skipped**.
- Actual repaired SQL on BigQuery literal fixtures: **PASS**, 16 player identities / 17 salary observations yielding exactly seven expected rows. Coverage includes Sunday UTC/Eastern rollover, January season boundaries, aliases, schedule ambiguity, explicit weeks, preseason exclusions and latest salary precedence. Job `b3396acb-1ba4-4e01-a721-9a47e1ec3fbd`, zero source bytes processed.
- Co-run original/repaired SQL against real source data: **104,847 historical rows through 2025 in each result, zero row-set differences in either direction, identical counts, zero duplicate repaired player-season-week keys**.
- New 2026 salary rows: **861 Week 1**, **769 Week 2**; original result has none.
- Week-1 usage retains zero prior games and missing snap/target/carry history for all 861 rows. Week-2 usage has 930 rows, including 928 upcoming; **424 players recover prior-game history**, all at exactly one prior game. Snap history exists for 423, target/carry share for 424 each.

| Previously zero-support selected WR | Prior snap share restored | Prior target share restored |
|---|---:|---:|
| Chris Moore | 0.37 | 0.083333 |
| Kalif Raymond | 0.60 | 0.346154 |
| Kendrick Bourne | 0.67 | 0.216216 |
| Jack Bech | 0.40 | 0.137931 |
| Denzel Boston | 0.92 | 0.181818 |

The sixth WR, Devontez Walker, and backup QB Tyson Bagent still have no prior-game support; the repair invents none. These are archived model-role observations, not live player-status determinations.

The real-data preview uses three query-job temporary tables, not durable or live dataset writes. It applies the unchanged usage SQL and canonical smoothing prior K=4. Job `0ef86800-3ac5-4e06-bc29-e53d9b705df8`, 260,773,795 bytes processed, 1 GB cap. Supporting [preview evidence](reviews/evidence/2026-09-19-salary-week-real-preview.json) retains exact query, hashes and counts; [fixture evidence](reviews/evidence/2026-09-19-salary-week-fixtures.json) retains the exact SQL test.

Independent workstation review `93fef92` confirms 100% resolution among current regular-season classic salary rows: 403,614 raw observations at Week 1 and 184,245 at Week 2. The 1,231 unresolved observations are entirely preseason (August 20–29). These are raw snapshot counts, not deduplicated feature counts. Its historical alias census found no source rows carrying the five newly accepted aliases; the full parity check independently covers their effect on current historical data.

## Failed attempts retained in the record

The first fixture run caught BigQuery resolving an unqualified HAVING `week` against an aggregate alias. Qualifying source `g.week` fixed it before a successful run. The first real-data preview, using nested CTEs, failed at dry-run because BigQuery would not decorrelate the unchanged usage anti-join over that derived salary relation. Job-local temporary tables fixed the preview without changing usage logic. That unexecuted first preview also used a literal smoothing prior of 3; the successful helper imports the canonical value of 4. Neither failed attempt modified live tables.

## Remaining gates and decision

The workstation owns the isolated full build, unchanged leakage checks and projection comparison; the laptop owns source repair and additional simulation diagnostics. Scratch feature/prediction destinations must be asserted before imports initialize settings or any writes occur. The player-id override table must be copied and row-count matched, even though it currently contains zero rows.

Measure the refreshed pipeline with exact model and TabPFN cache identities. A same-cache comparison is a useful isolation step but is not a complete measurement: a stale TabPFN cache can conceal the effect of repaired inputs. Preserve original and repaired inputs side by side. Report feature support, projection shifts and lineup-selection changes before a live decision.

Current evidence establishes a real pipeline defect and a narrowly correct salary repair. It does **not** establish improved realized 220+ performance, full-pipeline leakage correctness, or live readiness. The preliminary five-WR support recovery is a reason to finish validation promptly, not proof of model superiority. The operator explicitly requested the best validated system possible for this weekend; automatic deferral on the assumption that validation is too slow is unwarranted. Measured workstation feature/projection durations total roughly twelve minutes.

Repair the free-data baseline before crediting Fantasy Points Route Share for information that free snaps/targets already contain. Paid-source incremental-value experiments remain useful after this correction.
