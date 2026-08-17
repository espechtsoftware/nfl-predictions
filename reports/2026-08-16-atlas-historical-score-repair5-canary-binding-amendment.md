# ATLAS historical diagnostic repair5 canary-binding amendment

Date frozen: 2026-08-16, while the exact 32-GiB full-cell preflight remained
nonterminal, before repair5 launch, before any repair5 shard/effect existed and
before any repair5 historical score existed.

Applies to `20260816-atlas-historical-score-diagnostic-v3`. It supersedes only
the repair5 launcher/resolver/finisher source hashes named by the earlier
repair5 upstream and attempt-binding amendments. Every scoring, selection,
population, retry and tail-first rule remains unchanged.

## Exact mechanical sources

- Real-path canary amendment SHA-256:
  `b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242`.
- Canary validator SHA-256:
  `e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411`.
- Canary-aware repair5 launcher SHA-256:
  `3c8092c2bc3e40840a16867621f2f3ffe231f571d3f621818feab61dbefbe330`.
- Canary-aware attempt resolver SHA-256:
  `705b65e5164b775361a2efe1440059f76978c3701c192179a40d85f4b0c27093`.
- Canary-aware strict finisher SHA-256:
  `fe7a069e42bfece580ff4f312bc2990bd31339932713d834c2c123bbc431cdd9`.
- Canary-aware terminal-failure census SHA-256:
  `e25d6ee17cc2e2c00d4517af0a1dd856613bb8414476aadcfcfd8e7c08a05ee1`.

## Additional upstream receipt binding

Before the v3 historical scorer may launch, it must bind byte-for-byte:

- `canary-completion.txt`, `canary-execution-metadata.json`,
  `canary-object-metadata.json` and `canary.sha256`;
- `grid-release.txt`, proving exactly 53 cells were released only after the
  actual 2023 Week 1 canary passed; and
- the canary amendment, validator and canary-aware launcher/resolver/finisher
  hashes above.

The canary shard remains one of the exact 54 accepted repair5 shards; it is
not rerun or selected specially during scoring. The historical scorer still
uses only `accepted-executions.txt` to identify the complete upstream
population and remains released after any mechanically valid score-free
disposition, pass or fail.

## Consequence boundary

This amendment repairs launch-path provenance only. It cannot expose or alter
an ATLAS effect, choose an execution based on content, relax an upstream
failure, change a realized score, promote production or change the UI.
