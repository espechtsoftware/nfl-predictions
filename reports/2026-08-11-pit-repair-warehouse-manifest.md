# PIT-repair pre-build warehouse manifest

Captured 2026-08-11 CDT before the repaired feature build and before querying
any repaired lineup outcome. Source feature tables were snapshotted into
`nfl_predictions` with a 30-day expiration. These snapshots are evidence for
row/key/value reconciliation, not production inputs.

## Snapshot tables and content identity

`checksum` is the order-independent BigQuery
`BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(row)))` over the complete table.

| source table | snapshot suffix after `pit_pre_ac9a2c2_` | rows | distinct natural keys | checksum |
|---|---|---:|---:|---:|
| `player_week_usage` | `player_week_usage` | 102,927 | 102,927 | 3316307623008824498 |
| `player_week_injury` | `player_week_injury` | 65,866 | 65,862 | 6175506643284995870 |
| `team_week_vacated` | `team_week_vacated` | 2,609 | 2,609 | 1610628163133179312 |
| `player_week_training` | `player_week_training` | 102,927 | 102,927 | 4718509956564061283 |
| `player_week_inference` | `player_week_inference` | 0 | 0 | NULL |
| `defense_week_allowed` | `defense_week_allowed` | 6,302 | 6,302 | -5167540829521695331 |
| `team_week_pace` | `team_week_pace` | 6,590 | 6,590 | 3115577818244933737 |
| `defense_week_blitz` | `defense_week_blitz` | 2,278 | 2,278 | -4361547472751984030 |
| `team_week_target_concentration` | `team_week_target_concentration` | 6,590 | 6,590 | -4875210801157159949 |
| `team_week_ftn_offense` | `team_week_ftn_offense` | 2,278 | 2,278 | 7356755772323636278 |

Player natural keys are `(gsis_id, season, week)`; team tables use
`(team, season, week)`. The four duplicate injury rows are the confirmed raw-
revision defect and are expected to disappear. `player_week_inference` is
empty because the repository is in the offseason; live-row candidate tables
and their mandatory upcoming-key gate still validate the scheduled target
spine during the build.

## Durable BigQuery snapshot jobs

| table | job id |
|---|---|
| usage | `f482a554-c72d-48c6-bb71-815917b9ad4d` |
| injury | `4749ba15-5374-4fc2-9376-719cb8fab656` |
| vacancy | `2aa17d1c-865c-4886-ba6a-bec71b137c77` |
| training | `8df17b0a-6e30-4db9-a0ff-1e8e6ab9f7bf` |
| inference | `d5a065e9-f3cc-467a-aeea-195f96d733cf` |
| defense allowed | `d30c03da-64e5-4a4b-9c61-fb71592f12c6` |
| pace | `7a85d356-dd06-4a12-a9a8-33b3eb264212` |
| blitz | `28569bf4-2e26-4c7a-9536-85895460d428` |
| target concentration | `fa5e1918-6842-4f6b-9303-ad20c7abff19` |
| FTN offense | `e5353a21-b9dd-4f05-9207-048c26700adb` |

## Post-build required comparison

Record new rows/keys/checksums and exact changed-column counts. Usage/training
player-week keys must remain exact. The independently computed pre-lock injury
target is 57,550 unique rows: 8,312 of the 65,862 old keys have no eligible
common-Sunday-main pre-lock source and are intentionally absent, while the four
duplicate revisions collapse. Vacancy rows/values may change only as a
consequence of that exact repaired `Out` set. Every other difference must
reconcile to the position-prior, pre-lock injury/vacancy or already-landed
exact player-week defense/upcoming-row repairs. The rebuilt table cannot feed
caches/models until the full dynamic PIT, salary/universe and live-row gates
pass.
