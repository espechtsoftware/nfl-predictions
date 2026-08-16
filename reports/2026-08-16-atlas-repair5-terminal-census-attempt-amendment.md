# ATLAS repair5 terminal-census attempt amendment

Date frozen: 2026-08-16, while the exact 32-GiB full-cell preflight was
nonterminal, before repair5 launch and before any repair5 effect existed.

Applies to `20260816-atlas-repair5-terminal-census-v1`. It supersedes only the
original protocol's statement that every primary failure immediately invalidates
repair5. The bounded platform-retry amendment now controls that boundary.

The terminal census may run only after the attempt resolver has classified all
54 primary executions. It is released in either of two cases:

1. the primary classification contains at least one ineligible failure and the
   attempt disposition is `terminal-invalid-primary`; or
2. every primary failure was eligible, all declared replacement executions are
   terminal, and at least one accepted replacement failed.

If all primaries succeeded, or every eligible replacement succeeded, only the
attempt-aware strict finisher may run. A nonterminal replacement cannot be
censused.

The census remains URI- and metadata-only. It must additionally retain the
attempt classification/resolution, primary/retry/accepted ledgers, and every
replacement execution metadata document. It must not download or inspect a
shard. A valid census records the primary and replacement status populations
separately, binds all attempt receipts, declares the scientific population
invalid, prohibits historical scoring, and releases only the already-frozen
continuous-parity capacity path.
