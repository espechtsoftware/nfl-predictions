# A7 outcome-blind smoke failure and queue disposition

**Recorded:** 2026-08-20 10:11 CDT

**Run:** `20260820-a7-select-ladder-phase-s-incumbent-v1`

**Disposition:** `invalid-outcome-blind-preflight-closed-no-retry`

## Outcome

A7 v1 did not reach its support census or historical evaluation. Its only
real-artifact smoke execution failed before any realized-score query, output
upload, or historical-outcome lease acquisition. It produced no evidence
about the selector's score effect and licenses no retry, shadow, transfer,
money-policy, or production change.

The initial launcher exit was caused by a real polling defect: a newly created
Cloud Run execution temporarily omitted its `Completed` condition and the
parser called that malformed. That was not the terminal result. The retained
execution continued independently and later failed for a distinct input-
receipt reason. Both facts are recorded so neither is mistaken for the other.

## Durable identities

- Source commit:
  `96f4487bdefa297f66d03e4aca896728581540b2`
- Successful Cloud Build:
  `3503c493-60d5-4fe6-a853-583679c8e33d`
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:9956f2b4444bc60255c29a1844c23a1f772d6b0c85ae1a532e032ece975e86ed`
- Create-once job-claim generation:
  `1787237723143509`
- Job-claim SHA-256:
  `3a8d4a25868d2c450b2a4059b50028f2262d9315b6ca439054fd6cee9eaabb8c`
- Execution:
  `atlas-minimal-c-s2023-w1-v1-6qfpk`
- Execution UID:
  `168674b0-4f13-48fb-9ff9-6a6e1e5ce49e`
- Reused-job UID/generation:
  `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2` / `9`
- Terminal completion:
  `2026-08-20T15:00:41.442723Z`
- Terminal condition/counters:
  `Completed=False`, `succeeded=0`, `failed=1`, `retried=0`,
  `maxRetries=0`

The exact cloud prefix inventory after terminal failure is one object:

```text
1026 bytes  gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/preflight/job-claim.json
```

There is no real-artifact smoke object, smoke-terminal object, support object,
freeze manifest, or historical result. A direct object describe returned
NotFound for
`gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json`.

## Failure diagnosis

The terminal traceback ends at
`run_a7_select_ladder.py::_canonical_query_value` with:

```text
RuntimeError: A7 source query contains a non-finite value
```

The call was constructing the canonical `player_source` receipt, before A7
downloaded/scored its slate artifacts or formatted/ran its realized-score
query. A read-only BigQuery census of
`nfl_forensic_review.final_forensic_20260814_player_corpus_repair4` for
`scope='phase-s-cbwu-54'` found:

| Field check | Count |
|---|---:|
| Rows | 30,044 |
| `mean_projection IS NULL` | 439 |
| non-null projection NaN | 0 |
| non-null projection Inf | 0 |
| null salary/name/position/team/opponent/game | 0 each |

The shared CBWU reconstruction intentionally converts a non-finite parsed
projection to `0.0`; the A7 raw query receipt rejected the pandas NaN produced
from SQL NULL first. A prospective A7 repair would need an A7-specific,
explicit normalization such as `COALESCE(mean_projection, 0.0)` and a new
protocol/run/source build. It may not be patched into or retried as v1.

## Boundary and licenses

- `uses_realized_outcomes = false`
- `actual_score_query_executed = false`
- `historical_look_consumed = false`
- `preflight_retry_licensed = false`
- `historical_scoring_licensed = false`
- `prospective_shadow_licensed = false`
- `production_law_scorefree_transfer_licensed = false`
- `production_change_licensed = false`

Do not call the success-only `finish-preflight` path and do not relaunch the
execution. The initial no-condition poll receipt remains retained locally for
the separate parser defect diagnosis.

## Queue disposition

A7 v1 is closed administratively at the outcome-blind boundary. Building a
new A7 v2 now would not answer the project's most important winner-structure
question, so it is deferred rather than expanded into another repair cycle.

The active research order is:

1. implement and run the A2a **score-free** same-team dependence mechanism
   census;
2. only if that law-shape gate passes, freeze the prepared default-off
   `SINGLE_STACK_BOOM_SOLVES` arm, which tests exactly one QB pass catcher
   while holding bring-back and all other construction rules fixed;
3. evaluate bring-back/game dependence separately; and
4. reconsider a fresh A7 selector protocol only after the construction-law
   path or when it can run without displacing it.

This is deliberately not a relaxation of evidence, point-in-time, fixed-
budget, or adoption rules. It is a reprioritization toward the measured Milly-
winner mismatch while keeping production unchanged until a frozen arm proves
its endpoint and then passes an unseen prospective shadow.
