# T230 ordinal-6 focused-test correction addendum

Date: 2026-08-26
Status: pre-launch correction law; no execution authority

## Purpose

This addendum truthfully records the first focused offline test invocation for
the ordinal-6 bounded platform-replacement candidate, its three failures, and
the one bounded correction opportunity. It supersedes only the original
amendment's statement that there would be a single focused test invocation.
Every science, lineage, absence, one-worker, first-creator, ambiguous-submit,
bridge-verifier, supplemental-root, no-outcome, and false-authority rule in the
original amendment remains unchanged.

The original pre-launch amendment is:

- path:
  `reports/2026-08-26-t230-ordinal6-bounded-platform-replacement-amendment.md`
- SHA-256:
  `72d4f85eeada11ab4148a82085837a6b4e6909d402b8084b232cebb618f3b7bd`
- bytes: `10,286`

No replacement intent, preflight receipt, Cloud Run submission, GCS
publication, result read, realized-outcome read, or scoring action occurred
during the failed focused invocation.

## First invocation: exact known record

The command was exactly:

```text
.venv/bin/python -m pytest -q tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py
```

The command exited `1`. The exact three printed failing node IDs were:

1. `tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py::test_review_lock_rejects_changed_preflight_receipt_measurement[sha256-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee]`
2. `tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py::test_production_cli_wires_only_reviewed_live_entry`
3. `tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py::test_preflight_cli_uses_fixed_tracked_output_and_blocks_second_invocation`

The captured runner established three failures and exit code `1`. It did not
durably preserve an exact collected/pass count or test-output SHA-256. Those
values are explicitly unavailable and must not be inferred or invented in a
review lock.

The failed candidate measurement set was:

| Surface | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_extreme_tail_panel_platform_replacement_v1.py` | `83dfa819da046777bcd9b0520519300bb8efd13fe3fc13401e813c25853a321b` | 90,541 | 2,262 |
| `tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py` | `a01e486bb25db1112c322ff1825b7c9d5595a64900fe0879f1fa4ce1cbc86b6a` | 54,236 | 1,316 |
| `scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `169a385e00165f88b029509ffd89848a1e34b2e06a66af17770f1a246249576a` | 118,931 | 2,839 |
| `tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `4b2a6bbd0a937149af2c0c6a70368063953f0f052ba6a50d0653baa83f31255e` | 50,301 | 1,346 |

The failed invocation had:

- `prior_failed_invocation_count=1`;
- `prior_failed_pytest_exit_code=1`;
- `prior_failed_failure_count=3`;
- `prior_failed_cloud_call_count=0`;
- `prior_failed_preflight_invocation_count=0`;
- `prior_failed_intent_built=false`;
- `prior_failed_realized_outcomes_read=false`;
- `prior_failed_collected_passed_counts_available=false`; and
- `prior_failed_test_output_sha256_available=false`.

## Post-failure read-only real-shape diagnostic

After the failed focused invocation and before any corrected test rerun, one
read-only diagnostic Cloud Run describe was executed exactly once:

```text
gcloud run jobs executions describe atlas-minimal-c-s2023-w1-v1-rffts --project nfl-predictions-503414 --region us-central1 --format=json(spec.template.spec.containers[0].env)
```

It confirmed that the Cloud Run v1 projection represents these exact 16
frozen empty-string attempt-0 overrides as name-only objects with no `value`
field:

- `T230_PRED1_URI`, `T230_PRED1_GENERATION`, `T230_PRED1_SHA256`,
  `T230_PRED1_BYTES`;
- `T230_RESULT_URI`, `T230_RESULT_GENERATION`, `T230_RESULT_SHA256`,
  `T230_RESULT_BYTES`;
- `T230_LANE0_URI`, `T230_LANE0_GENERATION`, `T230_LANE0_SHA256`,
  `T230_LANE0_BYTES`; and
- `T230_LANE1_URI`, `T230_LANE1_GENERATION`, `T230_LANE1_SHA256`,
  `T230_LANE1_BYTES`.

This diagnostic was a cloud read, not part of either focused test invocation.
It performed no cloud mutation, GCS publication, Cloud Run submission,
preflight invocation, replacement-intent build or publication, result read,
or realized-outcome read. Its only authority is the exact environment-shape
basis above. It grants no replacement or scoring authority.

## Bounded diagnosis

The module failure was a test-layer expectation error. The pure review-lock
validator can validate the shape and fixed path of a post-preflight file
measurement, but it cannot know that file's future SHA-256. A different valid
64-character lowercase SHA-256 is therefore not independently rejectable at
that pure layer. The production reopen boundary already compares the lock's
measurement to the actual tracked preflight receipt bytes, canonical-replays
the receipt, and requires all lock, receipt, addendum, implementation, and test
files to equal tracked-clean Git `HEAD` bytes.

The two controller failures were fixture errors:

- one fixture required a pre-existing `google.cloud.storage` attribute on a
  namespace package instead of allowing the reviewed production import to be
  monkeypatched; and
- one fixture omitted the already-existing safe `reports/` parent now
  required by the reviewed lexical/symlink path hardening.

The later read-only diagnostic also exposed one bounded production-shape
defect before any corrected rerun: the observer required every environment
row to carry a literal `value`, while the actual v1 projection omits `value`
for the exact 16 frozen empty overrides listed above. The corrected observer
normalizes a name-only row to the empty string only for that exact
contract-bound allowlist. Unknown name-only rows, `valueFrom` rows, rows with
extra fields, duplicate names, and any changed non-empty value remain
terminal.

None of the three failures widens a production permission or changes the
frozen Cloud Run, GCS, lineage, result, or authority law.

## Corrected candidate

The bounded corrections are:

- use a malformed 63-character SHA in the pure measurement-shape adversary;
- add a production `_reopen_recovery_review_lock_v1` adversary proving that a
  well-formed but wrong preflight SHA fails against the actual receipt bytes;
- remove one duplicate, behavior-neutral contract dictionary key;
- make the two controller fixtures accurately model the import and the safe
  existing tracked-output parent; and
- bind the exact ordered 16-name empty-environment allowlist in the module
  contract, derive the controller allowlist from that public binding, and add
  production-shaped positive and adversarial environment-row coverage; and
- make the contract, preflight receipt, intent, tracked lock, and tracked-clean
  Git replay bind this correction addendum and the truthful two-invocation
  history.

The corrected candidate submitted for renewed static review is:

| Surface | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `src/nfl_dfs/research/corpus_extreme_tail_panel_platform_replacement_v1.py` | `f9c764cf1ed4f65ec17a6b9c8ca71062c9677d62e4094e2f0c7d2a60402e9f00` | 100,552 | 2,484 |
| `tests/test_corpus_extreme_tail_panel_platform_replacement_v1.py` | `f00eff040af23beae5070e654905471f3d204199b7c2c01eb2058b0941a03a35` | 63,564 | 1,543 |
| `scripts/run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `1bac84bf99c6b11ca5f7009dea5279978040b62ea0eea7d290d3781e69865904` | 119,680 | 2,857 |
| `tests/test_run_corpus_extreme_tail_panel_platform_replacement_v1.py` | `a3df0976b693e3f0e727ef4c03c9a0a0af4b006ff1059f745d7bed649e244940` | 56,833 | 1,529 |

AST parsing and duplicate literal dictionary-key inspection passed for the
four corrected implementation/test surfaces. No corrected pytest invocation,
cloud preflight, publication, submission, intent creation, result read, or
outcome read has occurred. The separately recorded one read-only environment
diagnostic is the only post-failure cloud read.

## Corrected-run and lock law

The only permitted test accounting is:

- `prior_failed_invocation_count=1`;
- `corrected_candidate_invocation_count_max=1`;
- `focused_test_total_invocation_count_max=2`; and
- the corrected invocation must use the same exact command shown above.

The corrected candidate receives no launch authority merely by existing or
by passing static review. After renewed independent review, at most one
corrected focused invocation may occur. It must pass with exit code `0`, zero
test failures, zero cloud calls, and no realized-outcome access. Only then may
the already-specified single read-only real-artifact preflight occur. Only
after that preflight passes may a revised tracked-clean review lock be created.

That lock must bind:

- the original amendment measurement;
- this addendum's repo-relative path and exact SHA-256/byte measurement;
- the failed and corrected four-file measurement sets;
- the exact failed command, exit code, and three failure node IDs above;
- the explicit unavailability of prior collected/pass counts and output hash;
- corrected invocation count `1`, total invocation count `2`, and corrected
  result `passed`;
- the corrected run's exact collected/pass/failure/skip/warning/exit/output
  facts;
- zero cloud calls during both focused invocations;
- the one read-only preflight receipt and its no-mutation/no-submit closure;
  and
- all original false-authority fields.

Any second corrected invocation, any total invocation count above two, any
unequal measurement, any cloud call during focused testing, any outcome read,
or any missing tracked-clean binding is terminal. It does not authorize a
replacement intent or Cloud Run submission.

## Authority closure

Until the corrected test passes, the read-only preflight passes, and the
revised lock is independently reviewed and tracked clean, all of the following
remain false: automatic retry, replacement execution acceptance, worker-stage
acceptance, bridge-verifier license, lane resume, canonical lane root, panel
release, amended panel-root acceptance, realized-outcome use, historical
scoring, corpus fill, graph mutation, live-policy access, production change,
analysis authority, R6 freeze, promotion, and decision authority.
