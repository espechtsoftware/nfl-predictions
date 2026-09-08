# Week-1 capture-v3 P0-A durable-ledger successor independent review

Date: 2026-09-08

Review branch:
`codex/week1-capture-v3-p0a-r2-independent-review-20260908`

Candidate branch:
`origin/codex/week1-capture-v3-p0a-r2-repair-20260908`

Candidate commit/tree:
`563af790efc475a85e4cd8da7de4f58384643a10` /
`67cc749eb246121ceb490d3b78595ce701122465`

Candidate parent:
`a929aa57d6b00d30a0eef9c3b92ba92a8bb4e64c`

Controlling HOLD:
`reports/2026-09-08-week1-capture-v3-p0a-repair-independent-review.md`

## Disposition

**PASS / CODE GO for selective integration of this exact additive,
default-off successor. This is not authorization for P0-B, provider contact,
publication, deployment, paid entry, or any outcome-bearing operation.**

The candidate closes the controlling review's last P0-A defect. Each v3
provider-capture artifact durably contains the authority event, exact
root-last ledger object identity, ledger provider creation time, and the
ledger's publication cutoff. A downstream evidence build first exact-reopens
the stored provider-capture generation, reconstructs the provider-capture
artifact through the current authenticated authority, and compares the whole
semantic object. It then enforces the stored provider generation against the
retained ledger time.

The enforced ordering is:

```text
receipt <= root-last ledger <= stored provider-capture generation <= cutoff
```

The final-field path carries two distinct ledger records and applies the same
check independently to the contest-detail and standings acquisitions.

No network, DraftKings, provider, GCS, cloud, deployment, publication,
paid-entry, score, generation, selection, or outcome action occurred in this
review.

## Independent findings

### 1. The ledger edge is durable and exact

`read_authenticated_acquisition_with_ledger()` first performs the complete
existing authority read. That read authenticates the exact acquisition
receipt and raw/trace evidence, exact-reopens the sole root-last ledger
generation before and after the evidence checks, and verifies unchanged full
bucket governance. The successor return then adds:

- `authority_ledger_identity` with exact URI, generation, SHA-256, and bytes;
- `authority_ledger_created_at` from the provider object;
- `authority_ledger_publish_by`; and
- the already-authenticated authority event ID.

The v3 provider-capture builders normalize that return into an
`authority_ledger` record and seal it under the provider-capture semantic
hash. Final-field capture retains one separately named record per source and
rejects a shared ledger identity.

Downstream validation does not merely trust the retained record. It rebuilds
the provider-capture artifact from the referenced acquisition receipts and
the current authority. A changed identity, generation, content hash, byte
count, provider timestamp, authority event, or cutoff makes the rebuilt
semantic object differ and fails closed.

### 2. Stored-generation ordering is checked at the correct boundary

Both evidence builders call `_reopen_semantic()` on the exact referenced
provider-capture identity. The returned `ReopenedObject.created_at` is the
provider creation time of that exact stored generation. Only after the
provider-capture body is reconstructed from durable authority does the code
compare each retained ledger time with that stored generation time.

This closes the earlier retrospective-authentication path. A semantically
correct acceptance capture stored at `2026-09-13T15:02:30Z` cannot become
valid when its ledger is later created at `15:03:00Z`. The focused test
reproduced that exact attack and rejected it with `stored provider capture
predates an authority ledger`.

The final-field adversary uses two real offline collector issuances. The
contest-detail ledger is created at `18:03:00Z`, the standings ledger at
`18:05:00Z`, and the provider capture at `18:04:30Z`. The downstream builder
rejects the capture because it predates the second ledger even though it
follows the first. This demonstrates that the two edges are evaluated
separately rather than collapsed into one event.

An independent positive-path probe also passed:

```text
acceptance: receipt 15:02 <= ledger 15:03 <= capture 15:04 <= cutoff 15:30
final field: ledgers 18:03 and 18:05 <= capture 18:06 <= cutoff 19:00
```

The accepted-entry projection contained all 57 expected entries, and the
final-field projection reproduced the 57-entry provider count.

### 3. Previously passed trust properties remain intact

The candidate changes no direct-bucket governance or transport logic. Source
inspection plus the focused adversarial suite retain the prior findings:

- complete direct-bucket IAM bindings/version/ETag are retained and hashed;
- direct `roles/storage.objectUser` is treated as an object mutator;
- public, custom, new, or unreviewed direct roles fail closed;
- redirects are handled one hop at a time with every target checked before
  contact, HTTPS port 443 enforced, loop/count bounds retained, and automatic
  redirects disabled;
- live publishers accept no authority, store, transport, locator, session,
  project, bucket, image, or service-account injection;
- every activation and locator-family pin remains absent;
- every live acquisition/publication boolean remains default false; and
- repository call-site search finds no production consumer outside the fixed
  acquisition module itself.

The v3 functions are additive. The frozen legacy-v2 source and test files are
byte-identical to the candidate parent:

- `src/nfl_dfs/ingest/week1_a5_capture_contracts.py`:
  `90c712df78e61c290cc4e41cef739de6693b7c1c33de76dd7176eb25a45ff2c8`;
- `tests/test_week1_a5_capture_contracts.py`:
  `78850f72c351411b10a2494b7ca6db8491170583d499a7c97e75e98f2bfe4706`.

### 4. Scope boundary after this PASS

This review passes the code/test-only v3 provider-capture and immediate
accepted-entry/final-field evidence contracts. It does not claim that the
whole Week-1 acceptance/settlement root has already been migrated from its
legacy v2 evidence inputs. The v3 module has no production call site, and its
live publishers cannot execute while the pins are absent. A later explicitly
reviewed integration must make the governed operational path consume the v3
evidence rather than silently falling back to v2.

P0-B remains the separate outcome-blind provider-reality gate described by
the earlier reviews. Inherited effective IAM, managed-service-account
impersonation, job-update authority, immutable runtime/image facts, real
locator/redirect behavior, media/disposition, and response shape remain
unclaimed until that gate is authorized and completed.

## Independent validation

Every pytest invocation began after a separate global process census showed
no active Python/pytest process. Tests ran serially.

- Governed acquisition plus v3 successor suite: **26/26 passed**, exit 0,
  1.15 seconds wall time, 143,536 KiB maximum RSS.
- Frozen generic P2 suite: **42/42 passed**, exit 0, 16.17 seconds wall time,
  140,280 KiB maximum RSS.
- Legacy-v2 rehearsal suite: **15/15 passed**, exit 0, 1.07 seconds wall time,
  147,380 KiB maximum RSS.
- Independent positive acceptance and two-ledger final-field probe: passed.
- Exact source-identity, pin/default, export/signature, and repository
  call-site inspection: passed.
- Python byte compilation: passed for the frozen contract, acquisition
  adapter, v3 successor, and focused test module.
- Ruff 0.16.5: passed for both changed implementation modules and the changed
  focused test module.
- `git diff --check` over the complete candidate delta: passed.

An optional lint invocation that also included the untouched frozen-v2 module
reported its pre-existing FURB162 timestamp-style warning. That file is
byte-identical to the parent and the warning is not introduced by this
candidate; no source was changed to silence it.

No broad suite or local simulation ran.

## Exact next action

Selectively integrate exact candidate
`563af790efc475a85e4cd8da7de4f58384643a10` with this review record. Keep all
pins absent and all live paths disabled. Then define and independently review
the narrow P0-B outcome-blind provider-reality gate before any real contact or
publication. The eventual acceptance/settlement integration must bind the v3
evidence path explicitly; no legacy-v2 fallback is authorized for a governed
live claim.
