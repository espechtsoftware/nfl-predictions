# Week-1 capture-v3 P0-A governed collector candidate

Date: 2026-09-08

Branch: `codex/week1-capture-v3-p0a-collector-20260908`

Production base at implementation start:
`545709bc098a573fd4aba50e86cd94e57524760a`

Implementation commit after rebase to current production:
`538f0f6ea9ee2bdb6f307c53c7c270dbe556b8fd`

## Disposition

**CODE CANDIDATE READY FOR INDEPENDENT REVIEW. LIVE ACQUISITION,
PROVIDER-CAPTURE PUBLICATION, MANIFEST PUBLICATION, PAID ENTRY, AND OUTCOME
CONTACT REMAIN ON HOLD.**

This change implements the narrow P0-A trust root required by the selectively
integrated capture-v3 P2 scaffold. It does not activate any live path and does
not claim that a DraftKings response shape or locator has been observed.

## Implemented boundary

`src/nfl_dfs/ingest/week1_a5_dk_acquisition.py` adds:

1. A repository-owned authenticated DraftKings HTTP collector. The public live
   function accepts only an allowlisted acquisition profile, one of the four
   fixed A5 contest roles, and an explicit execution acknowledgement. It does
   not accept a locator, transport, object store, authority, session-state
   path, image, service account, or ledger writer.
2. An exact collector allowlist covering the reviewed source commit,
   implementation-module SHA, immutable image digest, collector and reader
   service accounts, fixed session profile, project/buckets/prefixes, draft
   group, four role/contest bindings, GET-only profile methods, expected media
   type/disposition, and every permitted request/redirect/effective-locator
   family.
3. A fixed authenticated cookie bridge. It admits cookies only from the fixed
   Playwright storage-state path and only for DraftKings domains. After the
   response body is complete it derives raw bytes, observation time, every
   response/redirect URL and status, redirect targets, terminal status,
   content type/disposition, session profile, and body identity from the
   transport object. Login/sign-in/registration terminal paths are rejected.
4. Root-last immutable issuance. Raw response bytes, a P2-compatible exact
   transport trace, and the acquisition receipt are create-once published and
   exact-reopened first. The collector then writes one deterministic issuance
   event to a dedicated authority ledger, binding the exact receipt
   generation, authority event, raw/trace identities, policy, runtime
   collector identity, response facts, and redacted redirect chain.
5. A production read-only acquisition-authority adapter. Its public surface
   has only `read_authenticated_acquisition`; there is no register, mirror,
   enrollment, or publication method. It demands one and only one authority
   object generation, exact current bucket governance, exact allowlist
   identity, and an issuance created no earlier than its receipt. It then
   exact-reopens and independently verifies the receipt, raw object, transport
   trace, redacted transport event, timing, response metadata, body identity,
   locator chain, role/contest/draft group, collector source/code/image, and
   session profile.
6. Fixed live provider-capture publishers. They construct the concrete adapter
   and two-prefix object store internally. They accept no arbitrary authority,
   store, URI, locator, or registration object, and remain default-off.

The activation pins live separately in
`src/nfl_dfs/ingest/week1_a5_dk_acquisition_pins.py`. This avoids the
self-referential error of changing the collector module while attempting to
pin that same module's SHA. Every activation pin is deliberately `None` in
this candidate.

## Ledger governance

The live policy requires a dedicated GCS authority bucket with:

- uniform bucket-level access;
- object versioning;
- a locked retention policy of at least seven days;
- no public principal;
- exactly the reviewed collector service account as object creator; and
- the reviewed collector and authority-reader identities in the exact viewer
  set.

The collector checks this governance before provider contact. The adapter
checks it again on every read. Create-once publication uses provider
generation precondition zero; authority reads enumerate versions and reject
anything except a sole generation. Collector and authority runtime service
accounts are read from the provider metadata service rather than accepted as
caller claims.

Independent activation review must additionally prove there is no inherited
project/folder/organization permission that grants another principal write,
overwrite, delete, retention-change, IAM-change, job-update, or service-account
impersonation capability. The code-side bucket-policy census alone cannot
establish those external governance facts.

## Adversarial coverage

`tests/test_week1_a5_dk_acquisition.py` proves, before any provider-capture
publication:

- a mirror authority cannot be injected into either live publisher;
- a byte-identical copied receipt at a new URI/generation is not issued;
- an unknown receipt generation is not issued;
- a locally authored matching contest-detail/final-N receipt has no ledger
  authority;
- an otherwise recognized event claiming an unapproved collector image is
  rejected;
- a recognized event cross-wired to another role/contest is rejected;
- off-family or discontinuous response redirects are rejected;
- extra/forged redirect-projection fields are rejected;
- changed raw bytes or changed trace bytes are rejected on exact reopen;
- weakened/public ledger governance invalidates previously issued records;
- the concrete authority is read-only and cannot be caller-constructed; and
- every live acquisition/publication surface fails before client or transport
  construction while pins remain absent.

## Validation

- New focused P0-A adversarial suite: **13/13 passed**.
- Existing capture-v3 P2 suite: **42/42 passed**.
- Unchanged legacy-v2 compatibility suite: **15/15 passed**.
- Python compilation: passed for both new source modules and the focused test.
- Ruff: passed for both new source modules and the focused test.
- `git diff --check`: passed.

Each pytest invocation followed the repository-wide process census and began
only while no other `python ... -m pytest` process was active.

## Facts intentionally still blocked

No real provider transport was performed. Therefore all of the following
remain unknown and must not be guessed:

1. the exact authenticated active-entry export request locator;
2. its complete redirect chain and effective response/CDN locator families;
3. its observed media type and content-disposition form;
4. the settled contest-detail response shape and any redirects;
5. the full-standings response shape and any redirects;
6. whether the fixed authenticated storage-state bridge succeeds without
   landing on an authentication surface;
7. the 832,342-row streaming rehearsal behavior;
8. the immutable production image digest and source commit for this reviewed
   collector;
9. the dedicated collector and reader service accounts; and
10. the dedicated authority bucket's provider metageneration, locked retention
    period, complete effective IAM, and absence of inherited mutation paths.

These are P0-B/infrastructure facts. They require a separately authorized,
outcome-blind acquisition after independent code review. The acquisition must
run through this exact collector; a browser download, copied filled upload,
local fixture, generic GCS object, or permissive authority is not a substitute.

## Independent-review request

Review the code and trust interface, especially:

1. whether the dedicated bucket plus sole creator identity is a sufficiently
   non-substitutable issuance root once effective IAM/job governance is proven;
2. whether any live function permits locator/store/transport/authority/session
   injection;
3. whether the redacted redirect projection retains enough evidence without
   persisting signed query values;
4. whether the runtime image/source identity must gain an additional
   provider-signed job/revision attestation before activation; and
5. whether any adversary above can reach publication.

Do not perform a real transport smoke, fill pins, deploy, publish, contact
DraftKings, enter a contest, or inspect outcome-bearing data during this code
review. On CODE GO, the next action is a separate pin/infrastructure review and
one explicitly authorized outcome-blind P0-B acquisition.
