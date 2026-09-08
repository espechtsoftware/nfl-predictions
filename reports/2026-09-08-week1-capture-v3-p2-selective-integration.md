# Week-1 capture-v3 P2 selective integration disposition

Date: 2026-09-08

Integration branch:
`production/week1-capture-v3-p2-integration-20260908`

Production base:
`6c0ceb796b38ac3cfa3f95ca807569e62f9ebb20`

Reviewed implementation tip:
`96c58f68a336a66fd0e5501e0526b89ddf66114e`

Reviewed implementation commit/tree:
`96cd87a8dcc37e008db3c69f14d35af63ac8ae84` /
`277b4f8630b5df9cbc67fc0f17f6e9bcf0d6e2bc`

Independent-review tip:
`abf1427d9303939709fd9ba10a3ea435819cc4ba`

Selective scaffold integration commit:
`530dc39a86a8456605f9fa97c0e5d74ac93eb8de`

## Decision

**GO to integrate the P2 contract scaffold, default-off. P0 OPERATIONAL HOLD
remains for manifest publication, acceptance claims, settlement claims, live
provider contact, and paid-entry use.**

The integrated scaffold is useful and materially safer than the prior capture
contract. It separates immutable object storage from authenticated provider
acquisition, exact-reopens receipt/raw/trace generations, rebuilds downstream
facts from source bytes, and preserves prospective pre-lock and post-lock
ordering. It does not yet contain the trust root that makes those facts
authoritative in production.

The independent review's conditional verdict is correct. The public contract
accepts any object satisfying `AuthenticatedProviderAcquisitionAuthority`.
There is no production implementation, governed collector, immutable issuance
ledger, collector allowlist, or non-injectable production publisher in the
tree. A permissive adapter can echo a generic-store receipt and thereby make
self-authored bytes pass. That is a release blocker, not a reason to discard
the scaffold.

## Exact selective integration

The integration imports the cumulative non-`HANDOFF.md` state from the final
independent-review tip. Every imported blob is byte-identical to that tip. It
includes the contract module, focused tests, default-off local shape inspector,
contract documentation, and the complete implementation/review report chain.

The donor progression represented in the squashed integration is:

1. `4713cb835bd7e190e1cd1015125bbaeee1f397b5` — exact-generation capture-v3
   foundation;
2. `cb2a398fe0ff467665b4f415f2aa71f0aa1ee669` — raw provider-source repair;
3. `04686eb4d9dcdc2a8b6c4c5594f2e20af904328e` — P1 independent HOLD report;
4. `96cd87a8dcc37e008db3c69f14d35af63ac8ae84` — authenticated-acquisition
   interface and causal-ordering repair;
5. `b88dba19ed35aa58970d1c3e00c214fbf878534a` and
   `abf1427d9303939709fd9ba10a3ea435819cc4ba` — final independent conditional
   CODE GO / operational HOLD report.

The donor's historical `HANDOFF.md` edits were deliberately excluded. Current
production already records the repair history, and replaying divergent handoff
snapshots would overwrite or duplicate newer authoritative state. Donor
handoff-only commits `1c63b702...` and `96c58f68...` therefore do not need to
be cherry-picked separately; their material report amendments are already in
the exact cumulative blobs integrated here.

For a minimal production integration, cherry-pick the scaffold commit above
and the subsequent disposition/handoff commit from this branch. Do not merge
either donor branch wholesale.

## Static verification

- Scope is limited to one new capture-contract module, one new focused test
  module, one new default-off local-byte inspector, two capture docs, and the
  review/report chain. No generator, selector, scorer, exporter, deployment,
  CLI, scheduled job, or paid-entry code changed.
- Repository call-site search finds no production consumer of the new module.
  Outside tests and reports, only the local shape inspector imports it.
- `live_capture_pins()` still raises because both allocation pins are `None`.
- `PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR` remains `None`; an active-entry
  acquisition fails before parsing.
- The local shape inspector opens no file without
  `--execute-real-shape-smoke`, performs no network or publication, and needs
  a second acknowledgement before opening post-lock bytes.
- All 12 imported blobs match the exact independent-review tip.
- `git diff --check` passes for the selective integration.
- No pytest, simulation, cloud call, provider read, DraftKings interaction,
  publication, deployment, outcome read, or paid action was performed during
  this integration. The donor's independently observed evidence remains
  42/42 focused P2 tests and 15/15 unchanged legacy-v2 tests.

## Concrete remaining P0 implementation

This should be one narrow successor, not a capture-system redesign.

### P0-A: governed collector and read-only acquisition authority

Add a repository-owned authenticated DraftKings collector and a production
implementation of `AuthenticatedProviderAcquisitionAuthority` with these
closed properties:

1. The collector, not its caller, derives the response body, observation time,
   final response locator/redirect chain, status, media type, disposition,
   authenticated-session profile, transport trace, and collector identity
   from the actual request/download event.
2. Only one reviewed collector source commit and immutable image digest can
   issue records. The allowed acquisition profiles, four A5 contest IDs,
   draft group, methods, and locator families are an allowlist, not caller
   fields.
3. Issuance writes an immutable authority-ledger event binding the exact
   receipt identity/generation, authority event ID, raw identity, trace
   identity, and approved collector pins. The authority adapter is read-only;
   no operator-facing `register`, mirror, or arbitrary-enrollment method
   exists.
4. The ledger trust root is durable and independently checkable. Prefer reuse
   of the separately reviewed canonical provider-authority infrastructure if
   it can enforce collector-only issuance and exact-generation reads; do not
   create a second ambient mutable database merely to satisfy the protocol.
5. The live publisher constructs the repository-owned adapter internally from
   code-pinned configuration. It must not accept an arbitrary authority object
   from a command-line or operator call. Dependency injection may remain in
   the pure validation functions and tests.

Minimum adversaries: a mirror authority, copied filled upload, locally authored
contest-detail N plus matching prefix, unknown receipt generation, approved
bytes issued by an unapproved collector image, and a recognized event with a
cross-wired role/contest must all fail before publication.

### P0-B: discover and pin real transport facts

After P0-A passes independent review, perform one redacted, outcome-blind
active-entry acquisition through that exact collector. Record the effective
download response locator, redirects, status, media type/disposition, and
shape without exposing account/session secrets. Independently review the
receipt, then set `PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR` by code change. The
local-byte inspector is a secondary parser check, not acquisition evidence.

Use the same governed path on one separately authorized, already settled
contest to validate the contest-detail and full-standings response shapes.
Then complete the required 832,342-row streaming rehearsal. Do not weaken the
exact count or replace the full-field exercise with a prefix.

### P0-C: close the existing A5 source/allocation path

In parallel with P0-A, without contacting DraftKings or entering contests:

1. publish a generation-pinned copy of the already recorded September 4 lobby
   projection without rereading or changing its semantics;
2. exact-publish the paid salary catalog/player bridge and the four 80-lineup
   policy books (`P_MIX`, `P_CTRL`, `D400_DEMAX`, `D800_WEMAX`);
3. construct, create-once publish, and independently reopen the allocation-v2
   root with all K57/K20/K3/K10 paid-prefix and same-K shadow edges; and
4. only after review, code-pin its raw identity and semantic SHA so
   `live_capture_pins()` can return.

Do not invent either currently absent pin. Do not manually stitch JSON. Use a
single repository-owned root-last publisher whose inputs are exact reopened
objects and whose output is independently reopened before the receipt is
accepted.

### P0-D: governed end-to-end publisher and final release review

Add one default-off operational entry point that internally selects the fixed
store, authority adapter, reviewed collector pins, A5 pins, and publication
prefix. It should expose phase and explicit execution authorization, not raw
evidence fields or an injectable trust root. It must resume by exact reopen,
publish roots last, and refuse partial/cross-wired cohorts.

Independently review P0-A through P0-D together. Operational GO requires:

- the mirror/permissive-adapter path cannot enter the live publisher;
- real active-entry locator/shape evidence is pinned;
- the historical settled shape and 832,342-row rehearsal pass;
- lobby projection, salary catalog, player bridge, four books, allocation root,
  and manifest inputs are exact-generation bound; and
- canonical paid-output authority is separately cleared.

Only a later, separate owner authorization may permit upload of the 90 paid
entries. Acceptance capture remains a post-upload observation, and complete
field normalization/settlement remains post-lock.

## Next action

Integrate these two commits as default-off scaffolding, then assign the narrow
P0-A/P0-C work in parallel. Do not activate any live capture function or treat
the integrated protocol as source evidence while the operational HOLD remains.
