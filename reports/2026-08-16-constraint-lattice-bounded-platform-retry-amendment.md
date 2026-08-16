# Constraint-lattice bounded platform-attempt amendment

Date frozen: 2026-08-16, before either the control-support census or the
scientific constraint-lattice population was launched and before any shard
from either population existed.

Applies to:

- `20260816-constraint-lattice-control-support-census-v1`; and
- `20260816-constraint-lattice-scorefree-v1`.

This is a mechanical execution-contract amendment only. It changes no source
book, simulator draw, held-out fold, control roster, support threshold,
constraint, exception proposal, ranking rule, admission rule, scientific gate
or consequence boundary. Cloud Run task `maxRetries` remains zero.

## Reason

Both populations contain 54 deterministic, independent cells with pinned
image, code, command, resources and create-only output destinations. A failed
execution that wrote no object has exposed no cell statistic. Re-executing the
unchanged deployed job once for a literal platform-internal failure therefore
cannot select a favorable result, while requiring all 54 primary executions
to avoid every transient platform failure needlessly risks losing the entire
population.

## Frozen attempt law

The attempt resolver runs only after all 54 primary executions are terminal.
It records every primary execution metadata document and a URI-only object
inventory before making any replacement decision. For the scientific
population it must not download or inspect any shard or effect. For the
support population it likewise must not download or inspect any support
count. No realized outcome is available to the resolver in either mode.

A terminal failed primary is replacement-eligible if and only if:

1. its `Completed` condition is `False`;
2. `succeededCount=0`, `failedCount=1`, and `cancelledCount=0`;
3. the completed-condition message contains the literal text
   `Internal error running task`;
4. that message contains none of `configured memory limit`, `timeout`,
   `signal`, `SIGKILL`, `solver`, `CBC`, or `nonzero exit`, compared
   case-insensitively; and
5. the exact ledger-declared output URI is absent both at classification and
   immediately before the replacement request.

Memory, timeout, signal, solver, ordinary nonzero-exit, cancellation,
ambiguous failure, changed execution specification, success without its exact
object, or failure with an object is ineligible. If any primary is ineligible,
no replacements are launched for any cell and the entire population is
terminally invalid.

If all failures are eligible, every eligible cell receives exactly one new
execution of its already-deployed unchanged job. The job may not be redeployed.
No cell may be selected or omitted, and no second replacement is permitted for
any reason. If all primaries succeeded, the primary population is accepted
without a replacement.

## Immutable receipts

Each population retains its original `executions.txt`, all primary execution
metadata, the URI-only primary object inventory, a machine classification,
`retry-executions.txt`, `accepted-executions.txt`, and a machine attempt
resolution binding all three ledgers and their exact hashes. The accepted
ledger exists only when no ineligible primary failure occurred. It contains
exactly one accepted execution per cell: the primary success or its sole
eligible replacement.

The strict finisher must verify the primary/retry/accepted relationship,
validate every accepted execution against the original image, command,
environment, resources, service account, cell and URI, and require the set of
Cloud Run executions for each job to equal exactly the receipted one- or
two-attempt set. A failed replacement, missing object, extra attempt,
incomplete grid or changed specification invalidates the population.

## Consequence boundary

An accepted population containing eligible platform replacements has the same
scientific meaning as an all-primary population because the deterministic
computation and create-only destination are unchanged and no result was
available when the replacement set was chosen. Attempt disposition remains
mechanical metadata. It cannot alter the support decision, re-anchor the
scientific gate, excuse a partial population, authorize historical scoring or
license production.
