# ATLAS repair5 real-path canary amendment

Date frozen: 2026-08-16, while the exact 32-GiB full-cell preflight was
nonterminal, before repair5 was licensed or launched, before its output prefix
existed, and before any repair5 score-free effect or historical score existed.

Applies to `20260816-atlas-matched-diversity-mvp-v1-repair5`.

This is a mechanical launch-contract amendment responding to the repair3
namespace failure. It changes no image, code, rendered command, resource
envelope, output prefix, cell computation, score-free gate, retry class or
historical scoring rule.

## Frozen canary law

After the existing renderer/prefix smoke passes, the launcher deploys and
executes only the actual repair5 2023 Week 1 primary cell. It uses the final
job name `atlas-md-s2023-w1-r5`, final create-only repair5 output URI, exact
immutable image and code, exact rendered grid command, 8 CPU, 32 GiB, a
43,200-second timeout, task `maxRetries=0` and the production research service
account.

The remaining 53 primary cells may be deployed or executed only after a
strict validator establishes, without downloading the shard, that:

1. the canary job has exactly the one receipted execution;
2. its execution specification matches the repair5 manifest and rendered
   command exactly;
3. it is terminal with `Completed=True`, `succeededCount=1`,
   `failedCount=0` and a completion time; and
4. its exact final URI exists with positive size and immutable generation.

The validator retains hash-bound execution and object metadata plus a
create-only `canary-completion.txt`. It may not download the shard, inspect
support/effect fields, query realized outcomes or make any scientific
decision. A canary failure of any class terminates repair5 before the other 53
cells and is not eligible for the later bounded platform replacement rule.

After canary success, the launcher appends the remaining 53 primary
identities to the same `executions.txt` ledger and writes a hash-bound
`grid-release.txt`. The existing bounded platform-attempt resolver continues
to apply only after all 54 primaries are terminal. The resolver and strict
finisher must bind the canary and grid-release receipts.

## Consequence boundary

The separate 2023 Week 8 32-GiB preflight answers whether the largest observed
workload can complete at the frozen resource envelope. This canary answers
whether the final repair5 job, command and immutable namespace are wired
correctly. Neither substitutes for the other. The canary cannot alter an
ATLAS result, authorize a retry, license historical scoring by itself, or
change production or the UI.
