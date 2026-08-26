# Fixed-G0 catalog projection: source-completion schema failure

Date: 2026-08-26

## Purpose

This report preserves the first licensed 54-slate fixed-G0 catalog projection
attempt as a failed, outcome-blind publication attempt.  It does not convert
the failure into a smoke, erase either prior adapter failure, or grant a retry.
A separately versioned successor review/final-lock chain is required before
one corrected projection rerun can be licensed.

## Exact invocation boundary

- Clean repository commit:
  `8660373b8d5e027acd6057ce42f03707ebdbded1`
- Working directory:
  `/tmp/nfl-r6-catalog-projection-8660373b`
- Environment gate:
  `R6_FIXED_G0_ADAPTER_PRODUCTION_ENABLED=1`
- Exact argv:
  `.venv/bin/python -m nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1 publish-projection --execute`
- Exit code: `1`
- Final exception:
  `CorpusR6FixedG0AdapterV1Error: fixed artifact-source completion keys differ`

The invocation was licensed by the create-once old final lock tracked at that
same clean commit:

- Path:
  `reports/2026-08-26-r6-player-catalog-fixed-g0-final-release-lock.json`
- Outer SHA-256:
  `6f9f0fc3d5672604013d62f82db1f9d4b0078514eeeb0f327be2d0ddbc3e3908`
- Bytes: `6560`
- Internal `final_release_lock_sha256`:
  `de08f1b51d8a71df2fc0acd399f84b869f38367e8641d0d387aceadf434cf744`

## Exact failed object and observed defect

The failure occurred while generation-pinned reading this already-fixed input
identity:

```json
{
  "bytes": 383554,
  "generation": "1787367915631771",
  "sha256": "2d3a97e524fb0f592f0c57ed67643a84281fc97203e348f01031e3c356bded6c",
  "uri": "gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/source/artifact-source-authority-completion.json"
}
```

Its exact observed top-level key set was the adapter's frozen expected key set
plus one field that the adapter omitted:
`complete_dk_salary_coverage_claimed`.  The exact observed value of that field
was the JSON boolean `false`.  The complete observed top-level key set was:

```text
artifact_count
artifact_receipt_manifest_sha256
artifact_stream_order
artifact_supported_universe_complete
artifact_validation_manifest_sha256
authority_scope
complete_dk_salary_coverage_claimed
complete_dk_salary_universe_claimed
completion_sha256
historical_scoring_licensed
later_source_freeze_manifest_sha256
later_source_freeze_object
live_strategy_authority
outcome_columns_read
production_change_licensed
registration_object
registration_sha256
salary_coverage_is_predeclared_query_relative
salary_coverage_summary
salary_diagnostic_object
salary_diagnostic_sha256
salary_only_players_have_world_draws
salary_query_result_independently_verified
schema
task_count
task_manifest_sha256
tasks
uses_realized_outcomes
world_blocks
worlds_per_block
```

The exact key sets for source tasks `0` and `53` both matched the frozen
adapter `_SOURCE_TASK_FIELDS`; the mismatch was confined to the one top-level
false-valued field.  Nothing in this evidence permits a relaxed key policy,
truthy value, missing-field default, or additional unknown field.

## Failure position and negative evidence

The stack reached
`adapter._publish_pinned_projection_release_v1`, then failed inside its
initial `_derive_pinned_projection_inputs_v1` call at
`_validate_source_completion` -> `_exact_keys`.  That boundary is before the
projection function constructs all 54 derivations and before it obtains or
calls the output `publish_create_once` function.  Therefore:

- no player-catalog object was created;
- no derivation receipt was created;
- no catalog release or replay receipt was created;
- the fixed catalog output namespace received zero creates;
- no overwrite or resume occurred;
- no world-matrix body or arm-result body was read;
- no realized outcome, score, effect, selection, or decision data was read;
- no scoring, fill, retrieval, graph, promotion, production, or analytical
  authority was created.

The generation-pinned input read is legitimate outcome-blind reality contact.
The failed attempt is consumed and remains part of lifetime accounting.

## Bounded correction

The only adapter semantic correction allowed by this report is:

1. include `complete_dk_salary_coverage_claimed` in the exact source-
   completion top-level field set;
2. require its value to be literally `false`;
3. preserve every other exact key, identity, hash, 54-task, generation-pinned
   read, create-once output, exact-reopen, and authority-closed rule.

The existing fixture must carry the field as `false`, and an existing adapter
test must reject a coherently rehashed `true` mutation without increasing the
adapter suite count.  After a separately versioned static review, one focused
offline invocation, and two new create-once successor locks, at most one
corrected projection rerun may be licensed.  A third projection attempt is
not licensed.
