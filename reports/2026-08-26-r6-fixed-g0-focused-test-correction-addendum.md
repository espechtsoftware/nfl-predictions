# R6 fixed-G0 focused-test correction addendum

Date: 2026-08-26
Status: pre-smoke correction law; no cloud, publication, or scoring authority

## Purpose

This additive report preserves the consumed first focused-test invocation for
the fixed-G0 R6 player-catalog adapter and defines the only bounded correction
opportunity. It supplements, and does not erase, the failure record at
`reports/2026-08-26-r6-fixed-g0-focused-test-failure-summary.md` (SHA-256
`c40ade1cacae4ed4ee3b4483ac73a0467ab4576695d26b2aa0e92cc4977829b3`,
1,940 bytes).

Nothing in this addendum authorizes the task-0 real-artifact smoke, the
preliminary lock, the final release lock, the 54-member projection release,
cloud mutation, scoring, corpus fill, retrieval, or realized-outcome access.

## Consumed invocation

The exact command was:

```text
.venv/bin/python -m pytest -q tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py
```

The invocation count was `1` and pytest exited `1`. Pytest listed 27 failing
nodes, all converging on:

```text
CorpusR6FixedG0AdapterV1Error: task evidence[0] carrier differs
```

The failed candidate was:

| Surface | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `9878c3db99f1ab62bc2d1e143131c37470719854d7a58788f687a376c28f094e` | 213,447 | 5,459 |
| `tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `446a36be64c1b368ef5f574cc1043e80c658ec451b65f99cb60d554ec04d484f` | 123,862 | 3,272 |

The runner did not preserve a complete raw-output hash or exact
collected/passed/skipped/warning counts, so this addendum does not infer them.
The durable facts are the exact command, exit code `1`, 27 listed failures,
and their common exception. The invocation made zero cloud calls, read no
realized outcomes, and created neither fixed task-0 smoke marker nor success
receipt.

## Root cause and bounded correction

The production validator requires one carrier relationship to close in three
places: the carrier's `world_artifact_receipt_set_sha256`, the corresponding
lane-completion task row's same field, and the canonical SHA-256 of the exact
role-keyed world-receipt identity map must all be equal.

The synthetic fixture built the carrier from the canonical role-keyed map but
initially placed `_hash("world set {source_ordinal}")` in every completion task
row. The later fixture rewrite updated each task's carrier identity and
self-hash but did not replace that placeholder world-set hash. Task zero was
therefore the first deterministic failure for every shared replay path. This
was one all-54 fixture construction defect, not 27 distinct production
defects and not evidence that the production relationship should be relaxed.

The bounded correction:

- derives both fixture fields from one exact role-keyed world-receipt map for
  every source ordinal 0 through 53;
- retains the production equality requirement unchanged;
- separates world-identity and world-set-hash failures from the broader
  carrier diagnostic;
- adds an explicit all-54 fixture invariant; and
- adds a coherent wrong-completion-hash adversary at the exact reopen
  boundary.

No GCS identity, fixed G0 source, production carrier law, smoke one-shot law,
publication law, outcome closure, or authority field is widened.

## Corrected candidate

The corrected candidate submitted for renewed static review is:

| Surface | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `b31e39eecdcabb8e92f7833e871bb7f88414264e7150460f476f5030fad777ef` | 219,236 | 5,605 |
| `tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py` | `01610f9692039df207102b3e01b032d359b90bc4c60f71373690fb145e1e9f3c` | 128,168 | 3,385 |

Only static AST, duplicate-definition, exact field-set, whitespace, and local
file-measurement checks may occur before renewed independent review. No pytest,
module import, cloud read, cloud mutation, real-artifact smoke, publication,
or outcome read is authorized by preparing this candidate.

## One bounded post-fix license

Fresh independent static review must first report zero open P0, P1, and P2
findings against the exact corrected source/test bytes and this addendum. Only
then may a reviewer authorize at most one post-fix invocation of the same exact
pytest command.

The only truthful accounting is:

- `prior_failed_invocation_count=1`;
- `post_fix_invocation_count_max=1`;
- `focused_test_total_invocation_count_max=2`;
- the first result remains `failed`, exit code `1`, with 27 listed failures;
- both invocations must have zero cloud calls and zero realized-outcome reads;
  and
- the post-fix run must bind its exact output measurement and
  collected/pass/fail/skip/warning/exit facts if those are captured.

The corrected preliminary-lock schema is
`corpus-r6-player-catalog-fixed-g0-adapter-review-lock/v2`; the superseded v1
shape cannot erase this failure history. Its builder records total invocation count `2`,
prior failed count `1`, post-fix count `1`, prior exit `1`, prior failure count
`27`, post-fix exit `0`, and the common prior exception. It generation-free
Git-replays exact tracked file measurements for this failure summary, this
correction addendum, and the fixed post-fix output path
`reports/2026-08-26-r6-fixed-g0-post-fix-focused-test-output.txt`. The lock
cannot be built from a clean commit until all three evidence files exist at
their bound bytes.

If the post-fix invocation fails, a third invocation is not authorized by this
addendum. Even a passing post-fix test does not itself authorize the task-0
smoke: the corrected implementation, test, failure summary, this addendum,
and exact passing-test facts must first be incorporated into a freshly
reviewed preliminary-lock workflow. The fixed create-once smoke marker must
still be absent immediately before the separately authorized smoke.

## Authority closure

Until the bounded post-fix test passes and every subsequent lock/smoke gate is
separately satisfied, all source authority, scoring authority, selection
authority, corpus-fill authority, publication authority, promotion authority,
and decision authority remain false.

## Subsequent invocation

The single post-fix invocation licensed above was consumed and failed. Its
history is not rewritten here. The additive record at
`reports/2026-08-26-r6-fixed-g0-second-focused-test-correction-addendum.md`
supersedes this document's maximum-of-two accounting and its prospective v2
lock/output description, while preserving every recorded first-invocation
fact. It may license at most one final corrective invocation after a fresh
review. No fourth invocation is authorized.
