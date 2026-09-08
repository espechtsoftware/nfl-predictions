# Week-1 capture-v3 P0-A governed collector independent review

Date: 2026-09-08

Review branch:
`codex/week1-capture-v3-p0a-independent-review-20260908`

Candidate branch:
`origin/codex/week1-capture-v3-p0a-collector-20260908`

Candidate implementation commit/tree:
`538f0f6ea9ee2bdb6f307c53c7c270dbe556b8fd` /
`4ef8949ff650143e2ae38942ab077f4b9b006e7c`

Candidate final tip/tree:
`47183b0cc442735579f401284fb93facf022c935` /
`4971227a443ec3144a3bacf0572fa334bbb8c0f2`

Exact production parent:
`0391390ca82df6bcc0661e84e2c179f20e2975b6`

## Disposition

**HOLD. Do not integrate or activate this P0-A candidate yet.**

The candidate makes real progress: its live publisher signatures do not
accept a caller authority, store, locator, transport, or session-state path;
all activation pins remain absent; its ordinary response, trace, and receipt
content identities are exact-reopened; and no production caller imports the
new module. The candidate is therefore safely dormant.

It does not yet establish the claimed non-substitutable authority boundary.
Three independently reproduced P0 defects permit authority or transport facts
outside the frozen boundary, and one P1 claim about caller construction is
false. These are source-contract defects, not missing real-world pins, so they
must be repaired before the separately planned P0-B infrastructure/transport
work.

No provider, network, DraftKings, cloud, publication, paid-entry, or outcome
operation was performed during this review.

## Findings

### P0-1: the authority-bucket governance census ignores a direct object-writer role

`_GcsLedgerReader.governance()` treats only these roles as writers:

- `roles/storage.objectCreator`;
- `roles/storage.objectAdmin`; and
- `roles/storage.admin`.

It silently discards every other binding before comparing the observed
governance with the pinned `CollectorGovernance`. In particular,
`roles/storage.objectUser` is not counted even though it is an object-mutation
role. Legacy owner roles, custom roles, conditions, and the complete IAM-policy
identity are likewise absent from the retained fact.

An offline fake-provider probe supplied the expected sole creator/viewers plus
an unexpected `roles/storage.objectUser` binding for another service account.
The exact candidate code reported governance equal to the frozen policy:

```text
UNEXPECTED_OBJECT_USER_IGNORED=True
REPORTED_CREATORS=serviceAccount:dk-capture@nfl-predictions-503414.iam.gserviceaccount.com
```

This defeats the stated issuance-root law. A second direct writer could create
the deterministic ledger object while the adapter reports the bucket as
having exactly the approved creator. The candidate report correctly says an
external effective-IAM review is still required, but that future review does
not cure an on-every-read validator that actively omits a bucket-level writer
binding. Nor does the pinned bucket metageneration bind the full IAM policy or
its permission semantics.

Required repair:

1. Bind the complete bucket IAM policy identity, including policy version,
   etag/digest, every role/member/condition binding, and the bucket metadata
   required by the retention/versioning law.
2. Fail on every unreviewed binding instead of recognizing only a short list
   of familiar predefined roles. Resolve custom/predefined role permissions
   during the trusted-host activation review and bind the resulting complete
   mutation-authority set.
3. Bind and recheck the effective project/folder/organization mutation paths,
   service-account impersonation paths, and job-update authority in the
   provider-signed activation attestation. A bucket-local projection alone is
   not an effective-IAM census.
4. Add an adversary with a direct `roles/storage.objectUser` binding and at
   least one custom writer role. Both must fail before provider contact and on
   every authority reopen.

### P0-2: a post-cutoff ledger can retrospectively authenticate a pre-lock receipt

The collector deliberately publishes the issuance ledger last. The reader
checks only that `ledger_created >= receipt_created`; it neither returns the
ledger identity/provider time nor compares that time with the caller's
pre-lock cutoff, lock, or derived provider-capture creation time.

The offline probe retained response, trace, and receipt creation at
`2026-09-13T15:02:00Z`, set the authority ledger's provider creation time to
`2026-09-14T15:03:00Z`, and asked the unchanged P2 builder for a pre-lock
capture with `publish_by=2026-09-13T16:00:00Z`. Both the authority and builder
accepted it:

```text
LATE_LEDGER_CREATED_AT=2026-09-14T15:03:00Z
PRELOCK_PUBLISH_BY_ACCEPTED=2026-09-13T16:00:00Z
AUTHORITY_RETURN_FIELDS=authority_event_id,created_at,identity,raw
```

The fixed live publisher would ordinarily publish after the ledger and would
reject its own post-cutoff provider creation time. That honest call order is
not evidence embedded in the artifact. A deterministic provider-capture body
can be create-once published through the generic scaffold before the ledger
exists and become valid retrospectively when a ledger appears later. The
reader currently cannot distinguish that history.

Required repair:

1. Make the authority return and the provider-capture artifact bind the exact
   ledger `{uri, generation, sha256, bytes}` and provider creation time.
2. Enforce `observation <= raw/trace <= receipt <= ledger <= derived capture`
   and require the ledger itself to satisfy the applicable `publish_by` and
   pre-lock/post-lock boundary. For acceptance, the ledger must be created
   strictly before the Week-1 lock as well as no later than the frozen cutoff.
3. Reopen the exact ledger generation again in downstream validation rather
   than treating the receipt alone as a timeless authority token.
4. Add late-ledger, ledger-after-derived-capture, and ledger-after-lock
   adversaries. Restating every semantic hash must not rescue any case.

Because this changes the P2 authority-return/capture wire contract, do it
before the first live artifact. If the current schema name is treated as
frozen, publish a successor schema rather than silently changing its meaning.

### P0-3: redirect destinations are allowlisted only after `requests` follows them

`_RequestsSessionTransport.perform()` invokes:

```python
session.get(..., allow_redirects=True, ...)
```

Only after the complete response history returns does
`_normalize_transport_event()` verify continuity and locator families. An
off-family redirect has therefore already been contacted before it is
rejected. A redirect to an unreviewed DraftKings subdomain can also receive
cookies scoped to `.draftkings.com` before the post-hoc check. The existing
fixed-transport test proves only that the serialized history is rejected; it
does not prove that a forbidden network request was prevented.

`LocatorFamily.accepts()` also ignores an explicit port, so an HTTPS URL on
an allowed hostname but an unreviewed non-443 port passes the family test.

Required repair:

1. Disable automatic redirects and perform a bounded hop-by-hop loop.
2. Validate the current request locator before every send and resolve and
   validate each `Location` target before issuing the next request.
3. Pin/validate the port (normally absent or 443), cap redirect count, reject
   loops, and retain the existing HTTPS/userinfo/fragment restrictions.
4. Add a fake-session adversary proving an off-family target is never called
   and never receives a DraftKings cookie. Add explicit-port and redirect-loop
   cases.

### P1-1: the exported authority is caller-constructible with its module token

The test named `test_authority_is_read_only_and_not_caller_constructible`
tries only `token=object()`. Python callers can import the module's
`_AUTHORITY_TOKEN` and `_build_allowlist`, then instantiate the exported
`ProductionDraftKingsAcquisitionAuthority` with caller-controlled evidence,
ledger, and policy objects. The review did so successfully:

```text
CALLER_CONSTRUCTED_AUTHORITY=ProductionDraftKingsAcquisitionAuthority
```

This does not inject the object into either fixed live publisher; those
signatures are correctly closed. It does make the class/test/doc claim false,
and the generic P2 builders still accept such an object. A leading underscore
and identity token are conventions, not a trust boundary.

Required repair:

1. Remove the public/exported claim that the Python object cannot be
   constructed. The actual security boundary must be the provider-governed
   ledger plus a fixed, repository-owned live call graph.
2. Keep all operational entry points non-injectable and complete the missing
   end-to-end live publisher so no production route accepts a generic
   `AuthenticatedProviderAcquisitionAuthority`.
3. Test the exact public/live call graph, not possession of an importable
   module token. A caller-created adapter must never yield an artifact accepted
   by the fixed operational reader/publisher.

### P0-B activation facts remain genuinely absent

This review agrees with the candidate's disclosure that source code alone
cannot prove the future runtime boundary. Before activation, a separate
provider-side review still must bind:

- the exact immutable image and source archive;
- a provider-authenticated job/revision spec rather than the self-reported
  `COLLECTOR_IMAGE_DIGEST` environment value alone;
- dedicated collector and reader service accounts and their complete
  impersonation/job-update authority;
- the full effective IAM and retention/versioning state described above;
- the real request, redirect, response/CDN, media-type and disposition facts;
  and
- the fixed storage-state secret/version and mount authority.

The current pins file leaves every activation value `None`, and
`PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR`, allocation identity, and allocation
semantic SHA are also `None`. All live public functions therefore fail before
creating a GCS client or HTTP transport. This is retained and must remain true
through the repair review.

## Retained findings

The following candidate properties passed independent inspection and should
be preserved:

1. The exact delta from the production parent is limited to the two new source
   modules, one focused test module, the candidate report, documentation, and
   `HANDOFF.md`; there is no CLI, scheduler, deployment, scoring, generation,
   selection, exporter, or entry-path edit.
2. Repository call-site search finds no non-test consumer of the new module.
3. Both live provider-capture publishers construct their store and authority
   internally and accept no authority, store, locator, transport, session path,
   project, bucket, image, or service-account argument.
4. Response bytes, transport trace, receipt, and ledger bodies are
   create-once published and exact-reopened by content identity. Raw/trace
   tampering, copied receipts, unknown generations, role/contest cross-wires,
   and restated semantic bodies are rejected under the tested honest ledger
   root.
5. Response observation and raw/trace/receipt ordering is enforced. The defect
   is specifically the missing upper/order boundary on the root-last ledger.
6. All activation pins are absent and the explicit execution booleans default
   false.
7. `src/nfl_dfs/ingest/week1_a5_capture_contracts.py` and
   `tests/test_week1_a5_capture_contracts.py` are byte-identical to the exact
   production parent. Their SHA-256 values are respectively
   `90c712df78e61c290cc4e41cef739de6693b7c1c33de76dd7176eb25a45ff2c8`
   and
   `78850f72c351411b10a2494b7ca6db8491170583d499a7c97e75e98f2bfe4706`.
   The legacy-v2 rehearsal remains unchanged.

## Independent validation

Every pytest command began only after a separately executed exact global
process census found no `python ... -m pytest` process; same-shell post-run
censuses were empty. Tests were serial.

- Candidate P0-A suite: **13/13 passed**, exit 0 in 0.73 seconds, 130,824 KiB
  maximum RSS.
- Existing capture-v3 P2 suite: **42/42 passed**, exit 0 in 15.80 seconds,
  139,996 KiB maximum RSS.
- Unchanged legacy-v2 suite: **15/15 passed**, exit 0 in 1.18 seconds,
  147,488 KiB maximum RSS.
- Exact candidate/base scope and blob-identity inspection: passed.
- `git diff --check` over the candidate delta: passed.
- Offline late-ledger/caller-construction adversary: reproduced as shown
  above.
- Offline unexpected-object-writer governance adversary: reproduced as shown
  above.
- Static redirect-order inspection: confirmed `allow_redirects=True` precedes
  every family check.

No broad suite or local simulation ran.

## Exact next action

Return one bounded code/test-only P0-A successor addressing the complete
governance-projection, ledger-time, and redirect-before-contact defect classes,
plus the caller-construction semantics. Preserve the dormant pins, frozen A5
allocation, scoring/generation/selection code, and all existing v2 behavior.
Run the focused serial suites, then obtain a fresh independent review of the
exact repair.

P0-B provider/IAM/transport discovery, image build, deployment, publication,
DraftKings contact, paid entry, and outcome access remain unauthorized until
that source review passes and production issues a separate explicit gate.
