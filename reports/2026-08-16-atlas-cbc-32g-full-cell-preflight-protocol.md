# ATLAS CBC 32-GiB exact-full-cell preflight protocol

Date frozen: 2026-08-16, after repair4 cell 2023 Week 8 became terminal but
before any repair4 shard or aggregate scientific result was opened.
Protocol ID: `20260816-atlas-cbc-32g-full-cell-preflight-v1`

## Mechanical evidence and question

Repair4 execution `atlas-md-s2023-w8-r4-6rn7r` is terminal failed. Cloud Run's
terminal condition states: `The configured memory limit was reached.` Its
validated execution specification is the frozen repair4 command at 4 CPU and
16 GiB, with zero retries and the pinned old image/code. This is a mechanical
resource failure, not an ATLAS effect or historical-score result.

The previous 16-GiB preflight executed one R0 enumeration and was sufficient
to reject the old 4-GiB envelope, but it did not reproduce the full five-seed
slate lifecycle. The new question is therefore narrower and exact: can the
unchanged full repair4 2023 Week 8 cell complete at the established 8-CPU/
32-GiB ATLAS envelope?

## Frozen execution

- Cell: 2023 Week 8 only.
- Image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb`.
- Code SHA: `60f296fdad769b30c0bb7334118698f156e462b9`.
- Frozen runner SHA-256:
  `0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`.
- Runtime prefix renderer SHA-256:
  `69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671`.
- CPU/memory: 8 CPU, 32 GiB.
- Timeout: 43,200 seconds. Retries: zero.
- Interaction auxiliaries remain binary.
- The runner performs the exact full five-seed slate calculation and writes
  its normal score-free shard to a dedicated create-only preflight prefix.
- Realized player scores, contest results, payout and ownership are forbidden.

The only scientific-mechanism change from repair4 is none. The transport-only
change is the create-only preflight output prefix; the inseparable resource
envelope is the treatment under test.

## Decision rule

- Terminal success, exact execution identity and one create-only shard object
  license freezing a complete resource-only repair5 grid at 8 CPU/32 GiB.
- Terminal failure does not license a larger grid. Record its terminal reason
  and return to the already-proved continuous-interaction optimization or a
  separately frozen solver/resource repair.
- The preflight shard's ATLAS gate/effect fields must not be inspected for this
  decision. Its object generation, byte size and SHA-256 may be recorded as
  mechanical provenance.
- Repair4 continues to terminal for failure census. No repair4 success may be
  combined with the preflight or a future repair5 grid unless a separately
  frozen mixed-execution rule explicitly licenses that design. The current
  repair4 and historical scorer remain fail-closed.

This protocol licenses no production change, historical scoring, arm adoption
or UI change.
