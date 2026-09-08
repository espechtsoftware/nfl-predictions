# Week-1 A5 capture-v3 P2 independent review

Date: 2026-09-08

Review branch: `codex/week1-capture-v3-p2-independent-review-20260908`

Reviewed handoff tip:
`96c58f68a336a66fd0e5501e0526b89ddf66114e`

Reviewed implementation:
`96cd87a8dcc37e008db3c69f14d35af63ac8ae84`

Reviewed implementation tree:
`277b4f8630b5df9cbc67fc0f17f6e9bcf0d6e2bc`

Prior independent HOLD:
`04686eb4d9dcdc2a8b6c4c5594f2e20af904328e`

## Decision

**CONDITIONAL CODE GO for integrating this default-off contract scaffold;
P0 OPERATIONAL HOLD remains for every live evidence or paid-entry use.**

The P2 implementation correctly moves the claimed trust decision out of the
generic object-store namespace. A raw object or shaped receipt no longer
passes merely because its bytes, generation, timestamps, and internal hashes
agree. Every downstream v2 path now reopens an acquisition receipt through a
separate `AuthenticatedProviderAcquisitionAuthority`, exact-compares the
authority and object-store views, validates the closed acquisition profile and
locator, and binds the raw body through a canonical transport trace. The
prepared capture and filled upload must also precede the purported provider
acceptance observation. These changes close the P1 byte-plumbing and causal
ordering defects **provided that the supplied authority is a real, governed
trust root**.

That proviso is decisive. This branch contains only a `Protocol` for the
authority, not a production implementation, immutable event ledger, signature
verifier, collector allowlist, or governed acquisition entry point. All live
builders accept that authority object from their caller. The only executable
implementation is the test double, whose public `register` method accepts any
self-authored receipt. Accordingly, the positive fixture still starts with a
copy of the locally filled upload and locally authored contest-detail and
standings bodies; it becomes acceptable only because the test explicitly
registers those receipts. The negative adversaries prove that an *honest
allowlisting authority* rejects an unregistered receipt. They cannot prove
that the missing live authority is honest or that a permissive caller-supplied
adapter will reject anything.

This is not a reason to discard the contract scaffold. It is a reason to keep
the candidate's own operational HOLD exact. Merge may authorize construction
of the real adapter; it must not be cited as DraftKings source authority,
acceptance evidence, complete-field evidence, live-manifest authority, or paid
upload clearance.

No provider, browser, DraftKings, cloud, paid-entry, deployment, warehouse,
scoring, generation, selection, or outcome action occurred in this review.

## Requirement disposition

| Requirement | Disposition | Evidence |
|---|---|---|
| Generic storage cannot self-promote provider bytes | **PASS, conditional on a governed authority** | `_reopen_authenticated_acquisition` requires an independent authority read and exact-compares identity, provider creation time, bytes, and event ID before parsing the receipt. |
| Receipt/raw/transport integrity | **PASS** | Closed receipt and trace schemas bind method, locator, authenticated surface, response metadata, collector identities, raw identity, and exact creation time; every object is generation-exact reopened. |
| Copied upload attack | **PASS against an unrecognized receipt; live result unproved** | The new adversary refuses a separately archived upload copy when the authority does not recognize its receipt. The ordinary positive fixture uses the same bytes and passes only after test-authority registration. |
| Caller-authored false N plus matching prefix | **PASS against an unrecognized receipt; live result unproved** | The new adversary refuses the fake contest-detail acquisition when it is not registered. The ordinary synthetic final-field fixture remains locally authored and passes only through the test authority. |
| Prepared/filled-to-observation chronology | **PASS** | Both prepared and filled object creation times must be no later than the authority-bound provider observation; acquisition observation precedes raw/trace archives, which precede the acquisition receipt and cutoffs. |
| Exact active-entry download locator | **FAIL-CLOSED / operationally missing** | `PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR` is `None`; live acceptance fails before parsing until a real acquisition identifies and reviews the response locator. |
| Concrete provider trust root | **P0 OPERATIONAL HOLD** | No production `AuthenticatedProviderAcquisitionAuthority` implementation or governed collector exists in the tree. Every builder receives an arbitrary implementation from its caller. |
| Collector/image and authority-root governance | **P0 for live adapter; not a scaffold merge blocker** | Collector commit/code/image values are format-checked but not pinned here. The acquisition artifact does not name an immutable authority-ledger root, signature key, or authority implementation identity. The concrete adapter must supply and durably bind those facts. |
| Real-source contact | **P0 OPERATIONAL HOLD** | The included smoke reads local byte files only. It does not observe/authenticate a URL, redirect chain, account session, response headers, or collector event and therefore cannot establish the currently missing acceptance locator by itself. |
| Default-off boundary | **PASS** | Live allocation pins and acceptance locator remain absent; the shape smoke exits before reading a file without the explicit execution flag and requires a separate post-lock acknowledgement. |
| Legacy v2 compatibility | **PASS at source identity; execution result pending below** | `tests/test_contest_capture_rehearsal.py` is byte-identical to the reviewed base; no legacy capture implementation is changed by P2. |
| Scoring/generation/selection/paid behavior | **PASS** | The implementation diff is confined to the capture contract, its focused tests, docs, and report. No exporter, selector, generator, model, deployment, or paid action changed. |

## What P2 correctly repairs

### 1. The source claim is no longer inferred from a GCS-looking path

`AuthenticatedProviderAcquisitionAuthority` is intentionally distinct from
`ImmutableObjectStore`. `_reopen_authenticated_acquisition` first exact-reopens
the semantic acquisition artifact through the ordinary store, then requires
the authority to return the same exact identity, creation time, bytes, and
event ID. An arbitrary object copied into a provider-looking URI is therefore
insufficient when a real authority refuses it.

The receipt parser then enforces one closed acquisition profile, exact A5
contest role/ID/draft group, exact GET locator, HTTP 200, profile-specific
media type/disposition, and syntactically immutable collector identities. The
receipt's raw and trace identities are exact-reopened. The canonical trace
must reproduce the receipt's method, locator, authenticated surface,
observation time, response facts, collector identities, and raw identity.

### 2. The authority dependency survives all downstream rebuilds

The authority is not checked only at the first builder and then forgotten.
Provider-capture validation, accepted-entry evidence, per-contest acceptance,
the four-contest acceptance root, final-field evidence, normalization, and
settlement all reauthenticate the same acquisition chain. The old provider
capture v1 entry points explicitly fail.

### 3. The causal sequence is materially stronger

The acquisition observation must be no later than both the raw-object and
transport-trace archive times; both archives must exist no later than the
receipt. For acceptance, the prepared capture and exact filled upload must
exist no later than the provider observation and all prospective publications
remain strictly pre-lock. For settlement, both acquisitions and their source
archives are post-lock, separately event-identified, and bounded by their
prospective publication cutoffs.

### 4. The correct distinction is authority, not byte inequality

The candidate wisely does not ban a real provider export from being
byte-identical to the locally filled upload. It instead requires a separate
archive identity and a recognized acquisition event. This preserves a
plausible provider serialization while closing namespace-only promotion.

## Remaining live blockers

### P0-1: the reviewed tree does not contain the trust root it requires

The contract defines a read-only protocol, which is the right dependency
shape, but a protocol is not an authority. A caller can supply a trivial
implementation that returns the generic-store receipt unchanged and labels
its event recognized. With that implementation, a copied upload or fabricated
N/prefix passes the exact same contract because every self-authored byte and
hash is internally consistent.

The test suite makes this limitation unusually clear. `MemoryAcquisitionAuthority.register`
copies any selected generic-store receipt into its records without validating
a network event, account session, collector identity, or response. Both
positive setup paths author their raw source bytes locally and then call that
method. This is acceptable fixture machinery and the candidate discloses it;
it is not live source evidence.

The review reproduced the boundary directly without modifying the candidate.
A minimal `MirrorAuthority` implemented the public protocol by exact-reading
the caller's generic-store receipt and echoing its embedded event ID. The
unchanged acceptance validator accepted the ordinary self-authored fixture
through this object and printed
`PERMISSIVE_CALLER_AUTHORITY_ACCEPTED_SELF_AUTHORED_FIXTURE=true`. This is not
a bypass of a correctly implemented authority; it proves why the concrete
authority and a non-injectable governed publisher are release requirements,
not optional follow-up.

Before any operational GO, production must implement a repository-owned
adapter whose public validation surface is read-only and whose write/issuance
surface exists only inside the governed authenticated collector. The adapter
must reject unknown receipt generations even when their shape is perfect and
must not offer an operator/caller method equivalent to the fixture's
`register`.

### P0-2: approved collector and authority identity are not yet durable facts

The contract verifies that `collector_source_commit`,
`collector_code_sha256`, and `collector_image_digest` are well formed and
consistent with the self-contained trace. It does not compare them to reviewed
pins. Likewise `authority_profile` is a string inside the authority-recognized
receipt, while the evidence artifact carries no immutable ledger-root identity,
signature/key identity, or concrete adapter/source version.

The live adapter must close this either by returning and validating an
immutable authority-record identity/signature plus exact approved collector
pins, or by being built at one immutable reviewed source/image identity whose
closed ledger semantics and collector allowlist are code-pinned. That decision
must be independently reviewed and represented in durable evidence; an
ambient mutable database lookup is not enough.

### P0-3: the local byte-shape smoke cannot discover transport facts

`scripts/week1_a5_capture_real_shape_smoke.py` is correctly default-off,
redacted, network-free, and write-free. It can verify whether supplied CSV/JSON
bytes parse under the contract. It cannot establish the active-entry response
URL, redirect chain, authenticated account surface, HTTP status/content type,
content disposition, or collector event because none of those values enter
the tool.

The first real acceptance check therefore must be an acquisition smoke through
the reviewed collector/authority—not merely a local invocation of this byte
parser. Preserve the local smoke as a useful second-stage shape check.

## Required path to operational GO

1. Integrate this code only with its explicit default-off and operational-HOLD
   language unchanged.
2. Implement the concrete authenticated collector plus read-only authority
   adapter. Bind exact collector source/code/image and immutable authority
   ledger/signature identity; prohibit generic-store self-registration.
3. Independently adversarially review that exact implementation. The review
   must demonstrate that an externally supplied permissive adapter cannot enter
   the live publisher path and that neither copied upload nor false-N/prefix
   bytes can be enrolled through any operator-facing API.
4. Perform one redacted, outcome-blind active-entry acquisition through that
   exact collector to discover the real locator, headers, and response shape;
   pin them by reviewed code change. Use the local shape smoke on the captured
   bytes as a secondary parser check.
5. Perform one separately authorized historical-settled acquisition for the
   contest-detail and full-standings shapes, then the required 832,342-row
   rehearsal.
6. Complete the independent lobby identity, player bridge, four exact books,
   allocation root, and governed end-to-end publisher. Only then may a
   separate owner authorization permit paid upload and subsequent acceptance
   capture.

## Independent validation

- Exact reviewed commits and trees reproduced: **PASS**.
- Candidate/base scope inspection and `git diff --check`: **PASS**.
- Static call-site sweep: **PASS**. There is no non-test consumer or concrete
  authority adapter; all downstream v2 rebuilds explicitly receive the new
  authority dependency.
- Focused P2 suite: **PASS, 42/42**, exit 0 in 16.30 seconds at 144,324 KiB
  maximum RSS. An exact global pytest census was empty immediately before the
  command; the same-shell post-command census was empty.
- Legacy v2 suite: **PASS, 15/15**, exit 0 in 1.16 seconds at 147,352 KiB
  maximum RSS. A new exact global census was empty immediately before the
  command; the same-shell post-command census was empty. The legacy test blob
  is byte-identical to the reviewed base.
- Python compilation of the contract, focused test, and default-off smoke:
  **PASS**.
- Executable trust-boundary probe: **PASS as expected evidence of the HOLD**.
  A permissive caller-supplied authority accepted the self-authored ordinary
  fixture, demonstrating that the missing live adapter/publisher—not receipt
  shape—is the actual source-authentication boundary.
- No broad test or local simulation ran.

The exact next action is to commit and push this review, then integrate the
candidate only as a default-off scaffold. The independent verdict does not
authorize a provider read, a DraftKings interaction, a paid upload, or
publication of live A5 evidence. Operational work resumes with the concrete
collector/authority/publisher implementation and its own independent review.
