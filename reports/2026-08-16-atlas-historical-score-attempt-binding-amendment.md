# ATLAS historical diagnostic repair5 attempt-binding amendment

Date frozen: 2026-08-16, while the exact 32-GiB full-cell preflight was
nonterminal, before repair5 launch and before any repair5 score-free or
historical effect existed.

Applies to `20260816-atlas-historical-score-diagnostic-v3` and supersedes only
the zero-replacement execution language in the repair5-upstream amendment. All
historical reconstruction, scoring, selection and tail-first gates remain
unchanged.

## Exact mechanical sources

- Bounded platform-retry amendment SHA-256:
  `d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0`.
- Unchanged primary repair5 launcher SHA-256:
  `9ea70f34e2591672e4b84621c116db8e4b465177bbda689d9d555c3d18d85b42`.
- Attempt resolver SHA-256:
  `c11171b607d2ab381d013adfe655567f126305e5ac65e07c8dd53df61ac9743f`.
- Attempt-aware strict finisher SHA-256:
  `c21419ca9bb65e0e39a9e9fe0efb3909ab6d437bc42e5d29db5f97a5edce9c89`.

Cloud Run task-level `maxRetries` remains zero. The only admissible replacement
is the separately receipted, at-most-one, zero-object platform-error execution
defined in the bounded amendment.

## Upstream binding

The v3 historical scorer may launch only after the attempt-aware finisher has
created a valid 54-cell repair5 completion. In addition to every receipt listed
in the original repair5-upstream amendment, the scorer must bind byte-for-byte:

- the primary `executions.txt`, `primary-execution-metadata.sha256` and all 54
  primary metadata documents;
- `primary-object-inventory.txt`, its hash receipt,
  `primary-attempt-classification.json` and its hash receipt;
- `retry-executions.txt`, including the valid empty file when no replacement
  was required;
- the 54-row `accepted-executions.txt`;
- `attempt-resolution.json`, `attempt-resolution.sha256` and
  `attempt-artifacts.sha256`;
- all accepted execution metadata in `execution-metadata.sha256`; and
- the amendment, resolver and attempt-aware finisher hashes above.

The accepted ledger, rather than a Cloud listing, is the only input allowed to
identify the 54 shards. Every accepted row must resolve to its original primary
execution or to the sole replacement bound to that same cell, job, command and
URI. Primary and replacement identities may not be selected using shard
content or effects.

## Consequence boundary

Any ineligible primary failure, failed replacement, extra attempt, missing
attempt receipt or mismatch among the primary/retry/accepted ledgers prevents
historical scoring and releases only the already-frozen terminal-failure path.
A valid accepted population releases historical scoring whether its score-free
gate passes or fails, exactly as frozen previously. This amendment cannot alter
production, the UI or a money book.
