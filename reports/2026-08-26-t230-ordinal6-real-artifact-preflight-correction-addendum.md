# T230 ordinal-6 real-artifact preflight correction addendum

Date: 2026-08-26
Status: additive pre-launch correction law; no execution authority

## Purpose and preserved law

This addendum truthfully preserves the successful first corrected focused test
and the subsequently consumed, failed first read-only real-artifact preflight.
It authorizes at most one post-fix focused test and, only after that test
passes, at most one corrected read-only preflight. It grants no replacement
intent, publication, Cloud Run submission, result, scoring, or production
authority.

This law is additive. It does not rewrite either earlier reviewed document:

- original amendment
  `reports/2026-08-26-t230-ordinal6-bounded-platform-replacement-amendment.md`,
  SHA-256
  `72d4f85eeada11ab4148a82085837a6b4e6909d402b8084b232cebb618f3b7bd`,
  10,286 bytes; and
- first focused-test correction addendum
  `reports/2026-08-26-t230-ordinal6-focused-test-correction-addendum.md`,
  SHA-256
  `2192bbd35446b89f5b5cc9dc6a7bf681747f7b4cf00bf3d4fe72c1db53965dd8`,
  10,362 bytes.

The first addendum's maximum of two focused-test invocations is superseded
only because its one corrected invocation passed and the later real preflight
exposed a production evidence-shape defect. All original exact-lineage,
first-creator, one-worker, no-outcome, no-delete, terminal-submit,
bridge-verifier, supplemental-root, and false-authority rules remain intact.

## Focused-test history through the first corrected pass

The first focused invocation and its three failures remain exactly as recorded
in the first addendum. After the independently reviewed correction, the second
lifetime focused invocation ran exactly:

```text
.venv/bin/python -m pytest -q tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py
```

It exited `0`: `271` collected, `271` passed, zero failed, zero skipped, zero
warnings, with runner wall time `3.515` seconds. Its durable raw pytest output
is:

- path:
  `reports/2026-08-26-t230-ordinal6-corrected-focused-test-output.txt`
- SHA-256:
  `194407658363bec291839dce28931401bad3c2658310563edd3ba16380809fbc`
- bytes: `320`
- lines: `4`

The exact tested four-file candidate was:

| Surface | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_extreme_tail_panel_platform_replacement_v1.py` | `f9c764cf1ed4f65ec17a6b9c8ca71062c9677d62e4094e2f0c7d2a60402e9f00` | 100,552 | 2,484 |
| `tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py` | `f00eff040af23beae5070e654905471f3d204199b7c2c01eb2058b0941a03a35` | 63,564 | 1,543 |
| `scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `1bac84bf99c6b11ca5f7009dea5279978040b62ea0eea7d290d3781e69865904` | 119,680 | 2,857 |
| `tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `a3df0976b693e3f0e727ef4c03c9a0a0af4b006ff1059f745d7bed649e244940` | 56,833 | 1,529 |

That test invocation made zero cloud calls and read no result or realized
outcome. Passing it did not authorize the preflight more than once and did not
authorize an intent or launch.

## Consumed first real-artifact preflight

The first and only preflight permitted by the first addendum ran exactly:

```text
.venv/bin/python scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py preflight-worker --preflight
```

It exited `1` with these exact ordered error labels:

```text
primary execution/task terminal literals differ
real-artifact preflight failed closed
```

Its combined raw stdout/stderr bytes and SHA-256 were not separately retained;
they are unavailable and must never be invented. The fixed receipt
`reports/2026-08-26-t230-ordinal6-platform-replacement-real-artifact-preflight.json`
remains absent.

The failed preflight performed cloud reads, but it created no preflight
receipt, replacement intent, GCS object, Cloud Run update, Cloud Run
submission, or recovery execution. It read no result body or realized outcome
and performed no graph mutation or scoring. It consumed the first preflight
invocation despite producing no receipt.

## Bounded diagnosis and exact correction

The real execution-scoped task list contains exactly one task with the frozen
task name, labels, code `13`, and `Internal error.` literals. Its exact task
shape also has:

- `spec={}`;
- no `status.index`;
- no `status.retried`; and
- no `lastAttemptResult.exitCode`.

Exit code zero appears only in the exact execution-level `Completed` message.
The rejected observer had fabricated task-list fields by projecting an index,
attempt, retry count, and task exit code as zero. That fabrication is removed.

The corrected terminal projection must instead bind exactly:

- `task_spec={}`;
- `task_status_index_present=false`;
- `task_status_retried_present=false`;
- `task_last_attempt_exit_code_present=false`; and
- `execution_completed_message_exit_code=0`.

Any present task `index`, `retried`, or `exitCode` field, even present with
zero; any nonempty task `spec`; any changed task name/labels/status; or any
changed execution message is terminal. The controller tests must cover each
near miss. The exact 16-name empty-environment normalization law from the
first correction remains unchanged.

## Superseding bounded accounting

The only truthful focused-test history permitted after this addendum is:

- first invocation: failed, exit `1`, exact three nodes already frozen;
- second invocation: passed `271/271`, exit `0`, output identity above;
- post-preflight-fix invocation: at most one; and
- lifetime focused-test invocation maximum: `3`.

The only truthful real-preflight history is:

- first invocation: failed, exit `1`, no receipt, exact labels above;
- corrected invocation: at most one; and
- lifetime real-preflight invocation maximum: `2`.

The post-fix test must use the same exact focused command. Its raw output must
be retained at the fixed repo-relative path
`reports/2026-08-26-t230-ordinal6-post-preflight-fix-focused-test-output.txt`
and bound by SHA-256/bytes/counts in the later tracked review lock. If that test
does not pass exactly once, no corrected preflight is permitted. If the second
preflight does not pass exactly once and create the fixed canonical receipt,
there is no third preflight.

## Post-fix candidate for renewed static review

The exact four-file candidate measurement set is sealed below before any
post-fix test or corrected preflight:

| Surface | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_extreme_tail_panel_platform_replacement_v1.py` | `01635e99ea41d9ecd11a2ed11622d41ece815d9e780eed3ebf88f52fb8f681c8` | 122,367 | 2,946 |
| `tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py` | `e28c09112dfd00cf9b4420b5c138f26940c4607295840959af33f5bbf43f5e6e` | 74,213 | 1,770 |
| `scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `11865ff59e7b919faa1ef250f31bd94162fb429a0e8684f20b76f9b01a299aad` | 119,206 | 2,845 |
| `tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `01996419ef22a135e7089160fd3b950b27ee644a3cc244b1f8f17af317a58cc8` | 58,106 | 1,548 |

The module's review-lock and preflight-receipt schemas are version `2`. The
future v2 receipt and lock must collectively preserve the complete history
without a circular post-test code edit. The receipt directly binds the
original amendment, both correction addenda, both durable focused-test output
measurements, exact current implementation bytes, both preflight invocation
facts, and every zero-effect/false-authority field. The tracked lock directly
binds both prior four-file candidate sets and the exact command, count, result,
and output facts for all three focused invocations, then exact-cross-checks
the receipt's addenda, outputs, implementation bytes, preflight history, and
effect closure. A v1 receipt or lock is ineligible.

## Authority closure

Until the post-fix test passes, the corrected read-only preflight passes, its
fixed receipt is durably retained, and a new independently reviewed v2 lock is
tracked clean at Git `HEAD`, all authority remains false. In particular:
automatic retry, replacement execution, worker acceptance, verifier license,
lane resume, lane root, panel root, panel release, outcome use, historical
scoring, corpus fill, graph mutation, production change, R6 freeze, promotion,
and decision authority are all false.

Any extra focused invocation, extra preflight, missing history, unequal bytes,
unavailable value presented as known, result/outcome read, write, update,
submission, or authority widening is terminal and grants no recovery action.
