# ATLAS repair4 cost-control cancellation amendment

Date frozen: 2026-08-16, after repair4 2023 Week 8 reached a terminal
configured-memory-limit failure, while the other 53 repair4 cells and the
32-GiB preflight were nonterminal, and before any repair4 effect field or shard
content was opened.

## Reason

Repair4 requires all 54 exact executions to succeed. The terminal failure of
`atlas-md-s2023-w8-r4-6rn7r` makes that contract permanently unattainable. The
remaining 53 executions cannot restore a mechanically valid repair4 result,
regardless of their outputs, while their resource occupancy delays the exact
8-CPU/32-GiB full-cell preflight that can license a new complete grid.

## Authorized action

Cancel every exact repair4 execution that is still nonterminal. Do not rerun,
replace or reuse any repair4 cell. Do not open, aggregate or score any repair4
shard. Preserve the complete original 54-row launch ledger and harvest terminal
metadata for all 54 identities after cancellation settles.

The terminal census must distinguish:

- the natural 2023 Week 8 configured-memory-limit failure;
- operator-cancelled executions; and
- any execution that independently became terminal before cancellation.

It may inventory object URIs and hashes of metadata/census files, but it may not
download or inspect score-free effect fields. Repair4 remains a mechanical
non-result and cannot feed historical scoring.

## Consequence

Cancellation is cost and capacity control after unavoidable invalidation. It
does not alter, improve or hide a scientific result: no complete repair4 result
can exist. It allows the already-frozen exact 32-GiB preflight to start sooner.

The conditional repair5 license remains unchanged: all 54 repair4 executions
must be terminal, the census must preserve the natural memory failure, and the
exact 32-GiB preflight must strictly succeed. Repair5, if licensed, uses 54 new
identities and cannot combine repair4 outputs.

This amendment licenses no production, historical scoring or arm adoption.
