# Stack-core x shell historical-score execution protocol

Date frozen: 2026-08-16, before any stack-core/shell support, score-free,
production-lock, or realized-score result existed.

Protocol ID: `20260816-stack-core-shell-historical-score-execution-v1`.

## Release boundary

The single scorer remains inert unless the strict production-lock finisher has
published both report and completion for
`20260816-stack-core-shell-production-lock-v1`. The report must contain all 54
outcome-free production-form locks and 270 source-artifact receipts, and the
completion must bind the same report, the accepted 54-execution ledger, the
positive score-free license, `actual_scores_queried=false`, and
`rosters_locked_before_actual_query=true`.

The launcher and scorer independently download and validate those exact object
hashes, generations, sizes, identities and dispositions. A missing, changed,
negative or incomplete lock closes this diagnostic without querying an actual
score.

## Exact execution

Use the same immutable treatment/lock/scorer image and exact source commit
validated by the stack treatment Cloud Build. Run one Cloud Run task with one
parallel worker, 4 CPU, 16 GiB, a two-hour timeout, task retries zero and the
project compute service account. Its only command is the frozen historical
runner with the create-only report URI and exact lock report/completion
SHA-256 arguments. The output prefix and job identity are unique to this
protocol.

There is no separate canary because this one task is the entire score-facing
population. A memory, timeout, signal, solver, nonzero, cancellation,
ambiguous or object-bearing failure is terminal. At most one unchanged
replacement execution is allowed only when the primary terminal message is
the literal `Internal error running task`, the primary has zero successes and
one failure, and the create-only report object is absent. No second
replacement is allowed.

## Strict harvest

Monitoring may inspect execution status and output-object metadata only. It
must not download or inspect the partial/final score report until the accepted
execution is terminal successful and the exact one-or-two-attempt population,
command, image, environment, resources, service account, upstream lock hashes
and positive object metadata are all validated.

Only then may the strict finisher download the report. It must verify the
frozen report version/run ID/protocol, all 54 paired slate rows, complete
candidate/selected/generated threshold and transition grids, the 68,199-row
native actual-score parity receipt at absolute tolerance `1e-9`, the exact
lock receipt, the frozen three-condition gate and
`production_change_licensed=false`. It publishes a create-only completion
binding the report hash, accepted execution, attempt disposition and all
upstream hashes.

The result is descriptive historical evidence only. It may prioritize or
de-prioritize the already licensed 2026 shadow, but cannot alter production,
the UI, the mechanism, the gate or any lineup.
