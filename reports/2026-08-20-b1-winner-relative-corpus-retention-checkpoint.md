# B1 winner-relative corpus retention checkpoint

Date: 2026-08-20  
Disposition: `retention-independent-copy-archive-complete`

## Scope

This checkpoint records the bounded preservation of the exact anonymous
BigQuery result tables consumed by the frozen B1 winner-relative census. It is
metadata-only: no SQL was submitted, no result row was queried or inspected,
and no outcome was re-read. The two original create-only snapshot jobs were
allowed to finish. After both returned the same retryable BigQuery
`backendError`, exactly one authorized snapshot retry per table was submitted
with a distinct deterministic `_retry1` job ID. Both retries returned the same
error, so snapshot creation stopped permanently.

A separately authorized fallback then made exactly one normal server-side,
create-only copy per source. Both copy jobs completed cleanly. Their
destinations are durable independent tables, not snapshots; they have no
expiration, carry explicit outcome-viewed/retention/no-license labels, and
match their source result tables exactly on row count, logical bytes and
canonical schema hash. This document is the canonical retention manifest and
operation ledger for that archive pair.

## Frozen source anchors

The anchors below are copied from the already-published census source lock and
were reconciled against BigQuery job/table metadata without reading rows.

| Extract | Source query job | Query SHA-256 | Content SHA-256 | Anonymous result table | Rows | Bytes | Schema SHA-256 | Result-table etag | Expires (UTC) |
|---|---|---|---|---|---:|---:|---|---|---|
| generated candidates | `6cc6e627-3aa3-4110-966e-2adaae8ac9c6` | `4a3225f5cf25ddcf70b55537af9939ec78075cbe04bfce2480af7f8d2f9af4fa` | `07fec9adaa57620c3db8948424b3c111c1e4801c03bb814628da3ca40bbb1356` | `nfl-predictions-503414:_a5ce71d9ee02cf15dca224a9a278800663704e30.anonc70808e1ad7cfe572fafbe94b50c9273f43b8de4f99f715ffea549deca8da37c` | 698,172 | 135,014,001 | `ac8516379e6f43515d08f07df02bbae5502e404d009896a9e4e0deeb91eba622` | `CjheATfeoP8owg3rQ9iURg==` | 2026-08-21T18:01:41Z |
| companion player catalog | `8aa760e0-3eca-4d29-abb8-d327501a71de` | `d85f7c29eb7103b592aeded2d1e6a4cc884269da9a0e66f14840df6d947d5ff2` | `1764de93f22a397474bae9504c8fc8620e33c62c065f7b354012c318d817cc6f` | `nfl-predictions-503414:_a5ce71d9ee02cf15dca224a9a278800663704e30.anonb739fcf7ee05f4da8b274fa682fd3af051c59827073164117aedf47ed99d8929` | 29,605 | 2,591,917 | `734ab32b435d866e1c5d66e20972a37e325f3aa957013c3395622519de8053d5` | `bfomnBf67hUPl5SLtB308w==` | 2026-08-21T18:02:54Z |

Both source jobs are `DONE` with no job error. Their destination-table
references exactly match the anonymous tables above. The source tables were
still present with the recorded row counts, byte counts, schemas, etags and
expirations after the final retry failed.

The source-lock lineage remains:

- winner-relative census protocol SHA-256:
  `bb5851e38ae6a2934fc791997916ce6d1f7be46187d1263682ff15b70725ff03`
- winner-line input SHA-256:
  `13b7a7a1647fe9070b1e8583c9fc579c8fe882b1124e85eaa53d587de2759eb5`
- B1 union protocol SHA-256:
  `2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789`
- B1 union report SHA-256:
  `4e654a58563391ed3020b0b221756070cd07fb10e962fc80e4bbedfd5f2631b6`
- B1 union runner SHA-256:
  `fc12e2871d638995603258f16d9e1beeee68f8a885ba3a53f9f32790d62c608f`

## Failed snapshot attempt ledger

All four jobs used `jobType=COPY`, `operationType=SNAPSHOT`,
`writeDisposition=WRITE_EMPTY`, location `US`, and the exact source and
destination mapping below. All reached `DONE`; all contain one
`errorResult`/`errors` entry with reason `backendError` and message
`Error encountered during execution. Retrying may solve the problem.`

| Extract | Job ID | Created (UTC) | Started/ended (UTC) | Canonical job-metadata SHA-256 |
|---|---|---|---|---|
| generated candidates | `b1_wr_candidate_snapshot_20260820` | 2026-08-20T22:13:47Z | 2026-08-20T22:18:47Z | `d2698135fb11c7a58b47005c6f5b83042f5874ebf264450b26bd9e3304f033ba` |
| companion player catalog | `b1_wr_player_snapshot_20260820` | 2026-08-20T22:13:51Z | 2026-08-20T22:18:51Z | `933827035ca3447acc24edbbaab6c87f82216cbe19b4211fe60b783cb57be5d9` |
| generated candidates | `b1_wr_candidate_snapshot_20260820_retry1` | 2026-08-20T22:20:52Z | 2026-08-20T22:25:52Z | `b875e9eb68c68b4fe8e0128de5586703cffe65aea713a3ddb925d0e2a4c71bf3` |
| companion player catalog | `b1_wr_player_snapshot_20260820_retry1` | 2026-08-20T22:20:56Z | 2026-08-20T22:26:02Z | `946e2080bb73924deecec5467f50432f5dd8057e3ad63ed2de7c9dbc2aa815f2` |

Failed snapshot mappings:

- candidate source:
  `nfl-predictions-503414:_a5ce71d9ee02cf15dca224a9a278800663704e30.anonc70808e1ad7cfe572fafbe94b50c9273f43b8de4f99f715ffea549deca8da37c`
- candidate destination:
  `nfl-predictions-503414:nfl_predictions.b1_wr_candidate_extract_20260820_snapshot`
- player source:
  `nfl-predictions-503414:_a5ce71d9ee02cf15dca224a9a278800663704e30.anonb739fcf7ee05f4da8b274fa682fd3af051c59827073164117aedf47ed99d8929`
- player destination:
  `nfl-predictions-503414:nfl_predictions.b1_wr_player_extract_20260820_snapshot`

After both retry jobs became terminal, `bq show` returned `Not found` for
each destination. Therefore snapshot base references, destination row counts,
destination schemas and destination expiration cannot pass validation. No
destination was partially accepted or relabeled as successful.

## Successful independent archives

After the snapshot primitive failed twice, one bounded normal-copy fallback
was authorized. Both commands retained `--no_clobber`; each submitted one
deterministic BigQuery copy job and neither was retried. Job metadata proves
`jobType=COPY`, `operationType=COPY`, `writeDisposition=WRITE_EMPTY`, location
`US`, the exact source/destination mapping, terminal `DONE`, and no
`errorResult` or `errors`.

| Extract | Copy job ID | Created / started / ended (UTC) | Destination | Canonical job-metadata SHA-256 |
|---|---|---|---|---|
| generated candidates | `b1_wr_candidate_copy_archive_20260820` | 2026-08-20T22:30:40Z / 22:30:40Z / 22:30:41Z | `nfl-predictions-503414:nfl_predictions.b1_wr_candidate_extract_20260820_archive` | `1273bcbc45487b767730af94a66e1e003c311846141090221ac236b8613b8048` |
| companion player catalog | `b1_wr_player_copy_archive_20260820` | 2026-08-20T22:30:42Z / 22:30:43Z / 22:30:43Z | `nfl-predictions-503414:nfl_predictions.b1_wr_player_extract_20260820_archive` | `d92361f4940ee79c705c64bf843d32d913c1bc14f4b1c46dcaf955064db6a690` |

Immediately after copy success, both destinations were updated with
`expiration=0` and the exact labels shown below. Final metadata independently
validated each destination as `type=TABLE` with no `snapshotDefinition` and
no `expirationTime`.

| Extract | Rows | Logical bytes | Schema SHA-256 | Destination etag | Canonical final table-metadata SHA-256 |
|---|---:|---:|---|---|---|
| generated candidates | 698,172 | 135,014,001 | `ac8516379e6f43515d08f07df02bbae5502e404d009896a9e4e0deeb91eba622` | `6+tbrZMQhDpPzFYd0WqAfw==` | `796d2823f11e0ec2c96304b19d6dfe2c7cb35ae93f8862591d324ebaf6c6c0fa` |
| companion player catalog | 29,605 | 2,591,917 | `734ab32b435d866e1c5d66e20972a37e325f3aa957013c3395622519de8053d5` | `c0cgfzjQZqZ4xBXflpEFiA==` | `e5d49746242f681f1a2af338dab1b8049bf4a6d951e9ffe26c67a5563e0809f3` |

Those values exactly match the corresponding anonymous source table. The
archive tables' exact labels are identical:

```text
historical_retune_licensed=false
outcome_viewed=true
production_change_licensed=false
production_use=forbidden
retention_complete=true
retention_only=true
```

## Governance truth table

| Field | Value |
|---|---|
| `outcome_viewed` | `true` |
| `retention_only` | `true` |
| `retention_complete` | `true` |
| `archive_table_type` | `independent TABLE` |
| `snapshot_use_licensed` | `false` |
| `historical_retune_licensed` | `false` |
| `production_use` | `forbidden` |
| `production_change_licensed` | `false` |
| `contains_only_actually_generated_rosters` | `true` (candidate extract; the second extract is its companion player catalog) |
| `contains_hindsight_h_or_p` | `false` |
| `contains_simulated_world_optima` | `false` |

The compact, tracked census result remains available independently. The two
archive tables now preserve the full candidate extract and its exact companion
player catalog beyond the anonymous-result expiration window. Preservation
does not grant a retrospective retune, production use, or production change;
it must not be interpreted as permission to inspect or tune on the
outcome-viewed rows outside a separately frozen protocol.
