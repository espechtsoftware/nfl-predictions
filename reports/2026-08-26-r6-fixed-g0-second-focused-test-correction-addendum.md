# R6 fixed-G0 second focused-test failure and correction addendum

Date: 2026-08-26

## Purpose

This additive record preserves the second failed focused-test invocation and
defines the only bounded correction path. It does not rewrite the first
failure summary or first correction addendum. It grants no smoke, cloud,
publication, scoring, selection, corpus-fill, promotion, or decision
authority.

## Consumed second invocation

The exact command was:

```text
.venv/bin/python -m pytest -q tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py
```

This was the second lifetime invocation of that focused command. It exited
`1` with 13 listed failures. No cloud client was contacted, no realized
outcome was read, and neither the task-0 smoke attempt marker nor smoke receipt
was created. No exact collected/pass count or raw-output hash is claimed.

The exact candidate identities at invocation time were:

| File | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `b31e39eecdcabb8e92f7833e871bb7f88414264e7150460f476f5030fad777ef` | 219236 | 5605 |
| `tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `01610f9692039df207102b3e01b032d359b90bc4c60f71373690fb145e1e9f3c` | 128168 | 3385 |
| `reports/2026-08-26-r6-fixed-g0-focused-test-correction-addendum.md` | `d54228ed919c10a10558f9704082e7a4011c639e73ecd8ac49c64fbcd8cb3ed1` | 6198 | 132 |

The 13 listed failing nodes were:

1. `test_final_release_lock_reopens_smoke_and_runtime_closure_before_cloud`
2. `test_final_release_lock_builder_is_deterministic_and_requires_approval`
3. `test_final_lock_production_builder_replays_tracked_inputs_and_writes_once`
4. `test_final_lock_production_builder_rejects_current_code_drift_before_write`
5. `test_final_release_lock_rejects_tracked_smoke_drift`
6. `test_final_release_lock_rejects_tracked_attempt_marker_drift`
7. `test_final_release_lock_rejects_current_batch_dependency_drift`
8. `test_final_release_lock_rejects_coherently_rehashed_widening[gcs_overwrite_licensed-True]`
9. `test_final_release_lock_rejects_coherently_rehashed_widening[required_source_task_count-True]`
10. `test_final_release_lock_rejects_coherently_rehashed_widening[unexpected_authority-True]`
11. `test_task0_smoke_production_writes_one_fixed_local_receipt`
12. `test_task0_smoke_failed_first_read_consumes_attempt_before_retry`
13. `test_task0_smoke_post_read_crash_window_cannot_contact_gcs_twice`

The first ten shared the exception class `task-0 real-artifact smoke receipt
differs`. The final three failed because their production-smoke fixtures did
not install the fixture's fixed-G0 pins before reaching the intended GCS
boundary. The original 27-failure carrier mismatch class was absent.

## Bounded corrections

Two fixture-boundary defects were corrected:

1. Pure fixture final-lock replay had validated its synthetic smoke receipt
   against production-global fixed pins. The private fixture-only
   builder/validator path now accepts explicit expected smoke inputs. The
   public final-lock builder and validator expose no such parameter and always
   derive the production expectation from normalized `FIXED_PINS`.
2. The three production-smoke boundary fixtures now install their graph's
   fixed pins before exercising the intended read/collision/crash behavior.

Production strictness is unchanged: no public production entry accepts a
caller-selected pin set or caller-selected expected smoke inputs.

The corrected candidate submitted for fresh static review is:

| File | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `56eaaf1e48736d684d8504fd82eaba1e7071e3ff6261a80b9f75e4f3442ffdd7` | 222714 | 5681 |
| `tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `1f3612146c51546b95975fddeae430475e428ef812cfed7a0ce65e81ecd9f510` | 131576 | 3456 |
| `reports/2026-08-26-r6-fixed-g0-focused-test-correction-addendum.md` | `a933d408e34dbf7fed353196fffe75f3d5160ecfbc8d1a42be81a90a742acf50` | 6699 | 142 |

## Corrective invocation accounting

After a fresh independent static review of the corrected source, tests, and
this report, exactly one final corrective invocation of the same focused
command may be licensed. The lifetime accounting is then exactly:

- first failed invocation: `1`, exit `1`, 27 listed failures;
- second failed invocation: `1`, exit `1`, 13 listed failures;
- final corrective invocation: maximum `1`;
- total lifetime invocation maximum: `3`.

There is no fourth invocation authority. A passing final invocation must be
captured at the fixed tracked path
`reports/2026-08-26-r6-fixed-g0-final-corrective-focused-test-output.txt`.
The v3 preliminary lock must bind the first failure summary, the updated first
correction addendum, this second correction record, that eventual final output,
and the exact current implementation measurements. It must replay all four
evidence files from the clean implementation commit.

Even a passing final corrective invocation does not authorize the task-0
real-artifact smoke. The exact corrected bytes, passing output, and v3 lock
must first receive their own review and tracked clean commit. All authority
remains false until each later gate is separately satisfied.
