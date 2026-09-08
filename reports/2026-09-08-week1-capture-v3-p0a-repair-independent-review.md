# Week-1 capture-v3 P0-A repair independent review

Date: 2026-09-08

Review branch:
`codex/week1-capture-v3-p0a-repair-independent-review-20260908`

Candidate branch:
`origin/codex/week1-capture-v3-p0a-review-repair-20260908`

Candidate repair implementation commit/tree:
`49d896e7c91490ef12ee30a38ea0bb00dea9d1a0` /
`f4b8db6b304cd9ee3e47f5ca9eac32238949222f`

Candidate final tip/tree:
`fcdc25b8a129a90aaa31b5c4e6abf4782016faa2` /
`20e607dbb3bd2eadb82012518d9e3eb82dcdac68`

Controlling HOLD:
`reports/2026-09-08-week1-capture-v3-p0a-independent-review.md`

## Disposition

**HOLD. Do not integrate or activate this repair candidate yet.**

The direct-bucket governance repair, pre-contact redirect handling, cutoff and
lock checks on the root-last ledger, and corrected private/live authority
interface all pass independent inspection. Every activation pin is still
absent, live functions remain default-off, no production call site imports the
module, and the generic P2 plus legacy-v2 blobs are unchanged.

One original P0-2 requirement remains open. The immediate fixed live publisher
now rejects a derived provider-capture object created before its root-last
ledger, but the ledger identity and provider creation time are kept only in a
private in-memory cache. They are not bound into the provider-capture artifact
or the authority return accepted by the unchanged P2 contract. A downstream
validator therefore accepts the same exact provider-capture bytes when their
provider generation predates the ledger. That is the retrospective
authentication attack the controlling review required the wire contract to
close.

No network, cloud, GCS, DraftKings, provider, deployment, paid-entry, or outcome
operation occurred during this review.

## P0-1: root-last ordering is not durable in the artifact

The repair correctly enforces the following inside each authority read:

```text
observation <= raw/trace <= receipt <= ledger <= publish_by
```

It also checks the lock side, exact-reopens the sole ledger generation twice,
and caches its exact identity/provider time. The fixed live publication wrapper
then compares that cached time with the newly published provider-capture
generation. That immediate wrapper rejects `derived_capture < ledger`.

The cache is not part of the authenticated acquisition return or either
provider-capture artifact. In particular:

- `read_authenticated_acquisition()` still returns exactly
  `{identity, created_at, raw, authority_event_id}`;
- `dk-accepted-entry-provider-capture/v2` contains the acquisition receipt and
  event ID, but no ledger identity or ledger provider time; and
- `validate_acceptance_provider_capture_v2()` rebuilds the semantic body by
  reopening the receipt and current ledger, but it is not given the provider
  creation time of the provider-capture object and therefore cannot enforce
  `ledger <= derived capture`.

The corresponding final-field v2 shape has the same boundary: it records the
two authority event IDs but neither exact ledger identity/time.

### Independent reproduction

An offline in-memory provider reproduced the precise missing edge:

1. response, trace, and acquisition receipt existed at
   `2026-09-13T15:02:00Z`;
2. the semantically valid provider-capture generation existed at
   `2026-09-13T15:02:30Z`;
3. its root-last ledger was created later at
   `2026-09-13T15:03:00Z`, still before the frozen cutoff and lock; and
4. the unchanged downstream `build_accepted_entry_evidence_v2()` accepted the
   provider capture after exact-reopening the repaired authority.

Observed transcript:

```text
DERIVED_CAPTURE_CREATED_AT=2026-09-13T15:02:30Z
ROOT_LEDGER_CREATED_AT=2026-09-13T15:03:00Z
DOWNSTREAM_ACCEPTED=dk-accepted-entry-evidence/v2
IMMEDIATE_WRAPPER_REJECTS=Week1A5DraftKingsAcquisitionError:derived capture predates an authority ledger it depends on
```

This does not depend on backdating a real provider object. The response,
receipt, raw identity, event ID, and deterministic provider-capture body are
all knowable before the ledger is appended. A writer can create those exact
capture bytes first; when the ledger later appears, the downstream authority
read makes the earlier capture valid retrospectively. The live wrapper's
in-process check is not durable evidence that the wrapper created a stored
artifact.

This is the same distinction made in the controlling review: honest call order
is not evidence embedded in the artifact. It explicitly required the authority
return and provider-capture artifact to bind the exact ledger identity/time,
and downstream validation to reopen it and compare it with the derived
capture's provider generation.

### Required repair

Do not weaken the ordering law. Either:

1. introduce successor authority-return and provider-capture schemas that bind
   each root-last ledger's exact `{uri, generation, sha256, bytes}` and provider
   creation time; or
2. add an equivalently authenticated create-once issuance-proof sidecar that
   is explicitly referenced by a successor provider-capture schema.

The downstream consumer must generation-exactly reopen that bound ledger,
confirm it remains the sole authority generation under the complete current
governance, and enforce:

```text
receipt <= ledger <= provider-capture provider creation <= cutoff
```

For final-field capture, apply this separately to both source ledgers. Add the
exact adversary above at the downstream accepted-evidence and final-field
evidence boundaries. The existing v2 source/test blobs may remain unchanged as
legacy compatibility; the live governed path should use the successor schema,
as the controlling review already allowed when the v2 name is frozen.

## Repairs that passed

### Complete direct-bucket policy

The repaired census retains policy version, provider ETag, every direct
binding/member/condition, and a digest over that complete representation. It
derives projections from the retained bindings, treats
`roles/storage.objectUser` and the reviewed legacy writer roles as mutators,
rejects public access, and fails closed on every custom/new/unreviewed role.
The exact full governance is checked before and after every authority read.

The deliberate P0-B boundary is accurately disclosed: inherited effective
project/folder/organization authority, managed service-account impersonation,
job-update authority, and the real runtime/image configuration are not source
claims and remain activation blockers.

### Redirects before contact

The requests adapter validates the initial locator before reading session
state, disables automatic redirects, requires each response URL to equal the
requested hop, validates every resolved `Location` before the next send,
allows only HTTPS port 443, rejects unsupported 3xx statuses and unexpected
`Location` headers, caps redirects at five, and detects a loop before another
contact. The off-family fake-session adversary contacts only the initial
allowlisted URL.

### Live authority surface

The formerly exported authority class/factory are gone. The two live
provider-capture publishers accept no authority, store, transport, locator,
session path, project, bucket, image, or service-account dependency. The sole
review port is underscore-private, boundary-bearing, absent from `__all__`, and
has no production call site. Python privacy is correctly no longer claimed as
the security boundary; immutable source plus the fixed operational call graph
and later provider attestation remain required.

### Dormancy and compatibility

- Every activation pin remains `None`.
- All three live execution booleans default false.
- Repository call-site search found no non-test consumer.
- `src/nfl_dfs/ingest/week1_a5_capture_contracts.py` SHA-256 remains
  `90c712df78e61c290cc4e41cef739de6693b7c1c33de76dd7176eb25a45ff2c8`.
- `tests/test_week1_a5_capture_contracts.py` SHA-256 remains
  `78850f72c351411b10a2494b7ca6db8491170583d499a7c97e75e98f2bfe4706`.
- Both blobs are byte-identical to exact production parent
  `0391390ca82df6bcc0661e84e2c179f20e2975b6`.

## Independent validation

Every pytest invocation began only after a separate global process census
found no `python ... -m pytest` process. Tests ran serially.

- Repaired P0-A suite: **21/21 passed**, exit 0 in 0.86 seconds, 135,968 KiB
  maximum RSS.
- Unchanged P2 suite: **42/42 passed**, exit 0 in 15.86 seconds, 139,684 KiB
  maximum RSS.
- Legacy-v2 rehearsal suite: **15/15 passed**, exit 0 in 1.12 seconds,
  145,648 KiB maximum RSS.
- Offline downstream ledger-after-capture adversary: reproduced as shown
  above.
- Exact call-site/export/default-pin and source-identity inspection: passed.
- Python byte compilation: passed.
- Ruff 0.16.5: passed for both collector modules and the focused test module.
- `git diff --check` over the complete repair delta: passed.

No broad suite or local simulation ran.

## Exact next action

Return one bounded code/test-only successor that makes the exact ledger
identity/time durable in the authority-to-provider-capture contract and
rechecks `ledger <= stored provider-capture creation` at downstream validation.
Preserve the passed governance, redirect, live-surface, dormancy, compatibility,
and no-call-site properties. Obtain a fresh independent review of that exact
successor before P0-B, network/provider contact, publication, deployment, paid
entry, or outcome access.
