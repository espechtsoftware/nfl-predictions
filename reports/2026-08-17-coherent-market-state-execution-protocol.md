# Frozen execution protocol: coherent model/market-state score-free grid

Date: 2026-08-17  
Run ID: `20260816-coherent-market-state-scorefree-v1`

This transport protocol is frozen after the scientific protocol and local
implementation, but before any treatment object, treatment effect, cloud image
or Cloud Run job exists. It changes no scientific source, state, candidate,
selector or gate rule.

## Bound scientific sources

- `reports/2026-08-16-coherent-market-state-scorefree-protocol.md`, SHA-256
  `ddf40d804614aa3011604cda49c1c599309418fd7d0298a56529e87de4ef1208`
- `reports/2026-08-16-coherent-market-state-support-census.md`, SHA-256
  `677171a16e339083b2eb1272926e9024ecab63b531ecc861d5237f94e61c0e63`
- Exact five money panels and R3/2025 Week 1 repair receipts already named and
  hash-bound by `scripts/coherent_market_state_sources.py`

## Build boundary

Build only from a clean tracked archive whose commit contains this protocol,
the scientific protocol, support receipt, source loader, pure analysis module,
runner, aggregator, tests, Docker copy entries and real-container smokes. The
full test suite must pass before the image is published. Resolve the tag to one
immutable Artifact Registry digest and use only that digest with the exact
40-character source commit in `CODE_SHA` and the digest in `ANALYSIS_IMAGE`.

## Queue boundary

The grid must not compete with the active 32-GiB ATLAS repair5 branch. It may
release only after the existing strict ATLAS queue receipt proves one of its
frozen terminal closure branches. It may execute alongside later lower-memory
independent mechanisms only if regional CPU/memory quota remains available;
queue ordering may not select cells by a scientific result.

## Fixed population and resources

- Project/region: `nfl-predictions-503414` / `us-central1`
- Service account:
  `817589974517-compute@developer.gserviceaccount.com`
- Cells: 2023--2025, Weeks 1--18, exactly 54 independent jobs
- One task per job; parallelism one
- CPU: 4
- Memory: 16 GiB
- Timeout: 14,400 seconds
- Cloud Run task `maxRetries=0`
- Output prefix:
  `gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/20260816-coherent-market-state-scorefree-v1`
- Create-only object: `slate-{season}-{week}.json`

## Actual-path canary

Create only the actual 2023 Week 1 primary job first, using its final job name,
command, environment, image, resources and output URI. Before releasing any
other cell, require:

1. exactly one Cloud execution for that job;
2. terminal successful status with one succeeded and zero failed tasks;
3. exact image/command/environment/resource/account parity;
4. positive final output-object size and generation; and
5. no object download and no treatment/effect field inspection.

Any canary failure terminates this version. It is not retry-eligible. Only a
passing metadata-only canary may create `grid-release.txt` and release the
remaining 53 primary cells.

## Narrow external attempt law

Cloud Run task retries remain zero. After all primaries are terminal, at most
one separately receipted replacement may be created for a non-canary cell only
when all of these hold:

- terminal condition is the literal platform message
  `Internal error running task`;
- the exact output URI has no object;
- no other substantive or ambiguous failure exists in the primary population;
  and
- the replacement uses byte-for-byte identical image, command, environment,
  resources, account and output URI under a new immutable job/execution name.

Memory, timeout, signal, solver, cancellation, nonzero-exit, object-bearing or
ambiguous failures are terminal scientific/mechanical data and are never
retried. Retain primary, replacement and accepted ledgers. The strict finisher
must independently prove every job's Cloud execution set equals its receipted
attempt set.

## Strict harvest and disclosure

Until every accepted execution is terminal, monitoring may inspect only Cloud
status, resource identity, the named fold-completion markers and object
existence/metadata. It may not download any shard or inspect treatment coverage.

After exactly 54 accepted terminal successes, the strict finisher must:

1. revalidate every execution spec/status and source/object generation;
2. download all 54 shards into a pending directory;
3. reject any forbidden outcome key, source/hash difference, malformed
   top-three team grid, non-12-for-12 candidate budget, non-exact-80 book,
   missing fold, invalid artifact receipt or duplicate roster;
4. invoke only the frozen strict aggregator once over all 270 folds;
5. upload the aggregate create-only and bind all execution/object/shard/report
   hashes in a completion receipt; and
6. disclose the score-free disposition only after the complete aggregate is
   mechanically valid.

Any mechanically valid full harvest licenses the separately frozen historical
scorer regardless of score-free pass/fail, preventing effect-selected outcome
disclosure. The historical scorer must be separately implemented and
hash-bound before it can query an outcome. A score-free pass can license only a
distinctly labeled 2026 pre-lock shadow; production and UI remain unchanged.
