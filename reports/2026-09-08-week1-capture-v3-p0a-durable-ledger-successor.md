# Week-1 capture-v3 P0-A durable-ledger successor

Date: 2026-09-08

Branch: `codex/week1-capture-v3-p0a-r2-repair-20260908`

Controlling review:
`reports/2026-09-08-week1-capture-v3-p0a-repair-independent-review.md`

## Disposition

**Code/test candidate ready for a fresh independent review. Live activation,
provider contact, publication, deployment, and paid entry remain HOLD.**

The successor closes the review's last P0 edge without changing the frozen v2
contracts. It makes each root-last issuance ledger's exact object identity,
provider creation time, authority event, and cutoff durable in the provider-
capture artifact. Every downstream accepted-entry or final-field evidence build
reopens the acquisition authority, reconstructs that exact ledger binding, and
enforces:

```text
receipt <= root-last ledger <= stored provider-capture generation <= cutoff
```

Final-field evidence performs this check independently for the contest-detail
and full-standings sources.

## Implementation

- Added `src/nfl_dfs/ingest/week1_a5_governed_capture_v3.py` with additive
  provider-capture and evidence schemas:
  - `dk-accepted-entry-provider-capture/v3`;
  - `dk-accepted-entry-evidence/v3`;
  - `dk-final-field-provider-capture/v3`; and
  - `dk-final-field-evidence/v3`.
- Added a ledger-bound private authority read. It returns the same exact
  authenticated acquisition plus the exact root-last ledger identity, provider
  creation time, and bound publication cutoff. The legacy v2 authority return
  remains available and unchanged.
- Added default-off, non-injectable live v3 publication surfaces. They construct
  the fixed repository-owned authority and store internally and publish under
  separate `acceptance-v3/` and `final-field-v3/` prefixes. Existing v2 live
  surfaces and artifacts remain available for compatibility.
- Downstream v3 evidence builders reopen the exact stored provider-capture
  generation so its provider creation time is evidence, not an in-process call-
  order assumption. Validation reconstructs the artifact from current sole-
  generation ledger authority and requires byte-for-byte semantic equality.

## Exact adversaries

- Acceptance: a semantically correct provider capture stored at
  `2026-09-13T15:02:30Z` is rejected when its bound authority ledger was created
  later at `15:03:00Z`.
- Final field: two separately issued sources are used. A provider-capture stored
  at `18:04:30Z`, after the contest-detail ledger but before the standings
  ledger at `18:05:00Z`, is rejected by the downstream final-field evidence
  builder.
- A capture carrying a modified retained ledger timestamp is rejected because
  it differs from durable authority.

## Preserved boundaries

- `src/nfl_dfs/ingest/week1_a5_capture_contracts.py` remains byte-identical at
  SHA-256 `90c712df78e61c290cc4e41cef739de6693b7c1c33de76dd7176eb25a45ff2c8`.
- `tests/test_week1_a5_capture_contracts.py` remains byte-identical at SHA-256
  `78850f72c351411b10a2494b7ca6db8491170583d499a7c97e75e98f2bfe4706`.
- The already-passed complete direct-bucket governance, pre-contact redirect,
  cutoff/lock, fixed private-authority, and no-injection behavior is retained.
- Every activation pin remains absent. There is no production call site for the
  new module.
- No network, DraftKings, provider, GCS, cloud, deployment, paid-entry,
  generation, selection, score, or outcome action occurred.

## Validation

Every pytest invocation began after a separate global Python/pytest process
census found no active pytest process. Tests ran serially.

- Governed acquisition and successor adversaries: **26/26 passed**.
- Unchanged generic P2 suite: **42/42 passed**.
- Unchanged legacy-v2 rehearsal: **15/15 passed**.
- Python byte compilation: passed for both implementation modules and the
  focused test module.
- Ruff 0.16.5 lint: passed for both implementation modules and the focused test
  module.
- `git diff --check`: passed.

No broad suite or local simulation was run.

## Remaining gate

Obtain a fresh independent review of the exact committed successor. The review
should focus on the durable provider-generation ordering edge for acceptance
and both final-field sources, while confirming the prior governance, redirect,
dormancy, compatibility, and fixed-live-surface findings remain intact. P0-B
and every live action remain separate and HOLD until that review passes and a
new production gate is recorded.
