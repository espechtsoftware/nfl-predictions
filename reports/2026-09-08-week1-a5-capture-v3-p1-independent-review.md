# Week-1 A5 capture-v3 provider-authority repair independent review

Date: 2026-09-08

Review branch: `codex/week1-capture-v3-p1-independent-review-20260908`

Reviewed handoff tip: `57e84f79c0bd7bfa62c241f5b987c15e7d54adb9`

Reviewed code/report candidate: `cb2a398fe0ff467665b4f415f2aa71f0aa1ee669`

Reviewed candidate tree: `33d004f26f6328452e909f33f931a0424fdca24a`

Exact implementation base: `4713cb835bd7e190e1cd1015125bbaeee1f397b5`

Prior independent HOLD: `1f4e0f82` (format-only tip `e15a6bb1`)

## Decision

**P0 HOLD. Do not use this candidate to prove paid acceptance, certify a
complete contest field, freeze the live A5 manifest/root, or authorize a paid
upload.**

The repair makes meaningful progress at the byte-integrity layer. Once a raw
object identity is supplied, its exact generation, bytes, SHA-256, provider
creation time, parser projection, and every downstream semantic reference are
reopened and reproduced. The old caller-normalized accepted rows and
final-field wrapper are retired; a genuine contest-detail body paired with a
different-size standings file now fails.

The two former P0s are nevertheless not closed at the source-authority layer.
The generic store protocol proves only that caller-selected bytes were archived
immutably. It carries no authenticated request/download receipt and cannot
prove those bytes came from the `source_locator` later stamped on the derived
artifact. Both tests expose the remaining gap:

1. the alleged active-entry provider observation is a second object containing
   the exact locally filled upload bytes; and
2. the alleged contest-detail response is a JSON object authored directly by
   the fixture with whatever `entries` value the caller selected.

Consequently, copying the unsubmitted filled CSV to another URI still becomes
`status="accepted"`, and a provider-shaped JSON object asserting false N can
still be paired with an N-row standings prefix. Exact storage makes either
claim durable; it does not make it a DraftKings observation.

This is an outcome-blind code review. No provider, DraftKings, cloud, paid,
scoring, generation, selection, deployment, or outcome action occurred.

## Requirement disposition

| Requirement | Disposition | Evidence |
|---|---|---|
| Exact raw bytes and immutable downstream references | **PASS for byte integrity** | `_reopen_exact` checks exact URI/generation/raw SHA/bytes and provider creation time; semantic consumers exact-reopen the capture and raw children before rebuilding their projections. |
| Accepted-entry source authority | **P0 HOLD** | `build_acceptance_provider_capture_v1` accepts an arbitrary `raw_observation_identity`; `source_system`, method, and locator are constants added after the bytes are read. The parser turns every matching DKEntries row into hard-coded `status="accepted"`. |
| Final state/N source authority | **P0 HOLD** | `build_final_field_provider_capture_v1` accepts arbitrary raw JSON and standings identities. The fixed locator is not derived from or bound to an authenticated HTTP acquisition receipt. |
| Honest provider body plus truncated standings | **PASS** | Raw parsed Entry-ID count must equal `contestDetail.entries`; an N versus N-1 mismatch refuses. |
| Matching false provider body plus matching prefix | **HOLD** | The validator cannot distinguish provider-fetched bytes from caller-authored provider-shaped bytes. The fixture's ordinary success path authors both the state/N body and the short field itself. |
| Prospective cutoff semantics | **PASS with one causal gap** | Observation, raw archive, capture publication, normalized publication, acceptance/root, and post-lock cutoffs are executable and monotone. Acceptance does not require the prepared/filled upload artifacts to predate the purported provider observation. |
| Exact A5/source facts and lineup/player bridge | **PASS at contract layer; operational HOLD** | Exact source pins, allocation root, catalog, one-to-one IDs, slots, salary, team limit, lineup ID, roster hash, and min-churn bijection are replayed. Required live lobby/allocation/book/bridge pins remain absent. |
| Legacy v2 compatibility | **PASS** | Candidate and base use identical blobs for both the v2 implementation (`250e9f9b...`) and v2 tests (`e5e7be46...`); the focused v2 suite passes. |
| Default-off shape smoke | **PASS as a parser diagnostic only** | Without `--execute-real-shape-smoke`, argparse exits before `_read`; output is redacted and write-free. Reading a local path does not authenticate its source and must not be promoted into evidence authority. |
| Scoring/generation/selection/paid drift | **PASS** | The five-file candidate diff is confined to the v3 contract/docs/report/test and new local smoke; no score, simulator, generator, selector, exporter, deployment, or paid-action implementation changed. |

## Blocking findings

### P0-1: a copied local upload is still accepted as provider truth

`_parse_active_entry_export` delegates to the same `_parse_filled_upload`
parser used for the locally prepared DKEntries file, then assigns
`status="accepted"` to every row unconditionally
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1916-1945`). There is no
provider status field or provider acquisition metadata in those bytes.

`build_acceptance_provider_capture_v1` receives only a generic object identity
and caller timestamp. After exact reopen, it inserts the fixed strings
`source_system="draftkings"`,
`capture_method="authenticated-active-entry-export-csv"`, and
`source_locator="https://www.draftkings.com/mycontests"`
(`src/nfl_dfs/ingest/week1_a5_capture_contracts.py:1976-2021`). The
`ImmutableObjectStore` interface has only create-once/read-exact methods; it
does not return the source request, response locator, authenticated-session
method, HTTP metadata, collector identity, or an acquisition receipt.

The passing fixture makes the problem executable. It serializes `filled`,
archives it as the intended filled upload, then archives the **same bytes**
again under `provider-active-entries-*` and treats the second object as the
provider observation
(`tests/test_week1_a5_capture_contracts.py:494-525`). The later check that raw
identities differ (`week1_a5_capture_contracts.py:2324-2325`) passes because
the URIs/generations differ, even though neither storage identity proves a
download and both byte bodies are identical.

This is the same substantive failure as the prior self-authored normalized
accepted rows, moved one layer earlier. A producer can copy an unsubmitted
filled file into the raw-observation namespace and receive a complete accepted
root. Exact Entry-ID, roster, min-churn, and byte checks then faithfully prove
the copied intent—not DraftKings acceptance.

The source-observation chronology is also incomplete. The code requires
`observed_at <= raw archive created_at <= publish_by`, but the final acceptance
builder does not require either the prepared capture or filled upload to exist
before the provider observation (`week1_a5_capture_contracts.py:2256-2325`).
An alleged acceptance observation can therefore predate the upload artifacts
it is supposed to confirm.

### P0-2: provider-shaped JSON can still authorize a false complete field

`_parse_final_field_provider_body` correctly rejects the retired wrapper and
parses `contestKey`, `draftGroupId`, `contestState`, and `entries` from a
provider-shaped body (`week1_a5_capture_contracts.py:2722-2763`). However,
`build_final_field_provider_capture_v1` accepts that body's arbitrary object
identity directly from its caller. The exact API URL is stamped onto the
result after parsing; it is not derived from an authenticated GET/download
receipt (`week1_a5_capture_contracts.py:2837-2920`).

The fixture again demonstrates the surviving trust boundary. `_normalized_ref`
chooses `size`, authors a new dictionary with
`contestState="Completed"` and `entries=size`, archives it through the generic
memory store, and passes that identity as the provider body
(`tests/test_week1_a5_capture_contracts.py:738-780`). It independently authors
the standings bytes. This is accepted as the ordinary valid path.

The new truncation test changes only one side: it pairs a 57-row Milly file
with a body saying 58, so count mismatch correctly fails
(`tests/test_week1_a5_capture_contracts.py:1141-1153`). The new matching-false-N
test mutates a downstream evidence projection while retaining the earlier
body, so deterministic reconstruction correctly fails
(`tests/test_week1_a5_capture_contracts.py:1180-1197`). Neither test exercises
the actual unresolved attack: author a provider-shaped body saying N, pair it
with an N-row prefix, and supply both generic storage identities. That is the
fixture's own success construction.

Thus the repair proves consistency between two supplied byte bodies, not that
either is the named contest-detail response or full contest export. A false
matching N remains certifiable until acquisition provenance is part of the
validated contract.

## Properties that are correctly repaired and should remain

- Keep the raw SHA/byte identity distinct from `semantic_sha256`.
- Keep exact-generation reopens at every downstream edge.
- Keep the reverse min-churn `(entry_index,lineup_rank)` bijection.
- Keep exact source facts, A5 role constants, salary/player bridge, roster
  legality, canonical lineup ID, and fail-closed live allocation pins.
- Keep the executable prospective-cutoff interpretation and strict pre/post
  lock provider creation checks.
- Keep the raw standings count against `contestDetail.entries`; it is necessary
  even though it is not sufficient without source authentication.
- Keep v1 accepted/final-field wrapper APIs explicitly retired and legacy v2
  fixture-only for live A5.
- Keep the local shape smoke default-off, redacted, and explicitly
  non-authoritative.

## Narrow repair required for reconsideration

1. Add a repository-owned, default-off provider acquisition boundary, separate
   from the generic immutable object store. It must perform or consume one
   authenticated DK request/download and atomically preserve:
   - exact request method and canonical response/download locator;
   - exact contest and authenticated provider-surface profile;
   - response status/content type and observation time;
   - collector code/image identity and capture method;
   - exact raw body object identity and provider creation time; and
   - one create-once acquisition receipt that downstream validators reopen.
2. Make both provider-capture builders consume the exact acquisition receipt,
   not a free `raw_*_identity` plus strings supplied or stamped later. The raw
   object's GCS namespace alone is not source authority.
3. For acceptance, bind the exact active-entry download acquisition and require
   `prepared/filled creation <= provider observation < lock`. Preserve the
   possibility that a real provider export is byte-identical to the upload;
   authority must come from the acquisition receipt, not a forced byte
   difference. If DK exposes no machine-readable post-upload artifact, use the
   already specified lossless browser/HAR/page-evidence plus separately
   reviewed attestation adapter.
4. For final field, bind one authenticated contest-detail GET receipt and one
   exact contest-scoped full-standings download receipt. Require both locators,
   contest identity, and observation times to agree with the capture, then
   retain the exact `entries == unique standings Entry IDs` check.
5. Add the two adversaries that are currently missing:
   - a separately archived copy of the local filled upload without a valid
     provider acquisition receipt must not become accepted; and
   - a caller-authored provider-shaped JSON body with false N plus an N-row
     standings prefix must fail even though both raw objects and all downstream
     hashes are internally consistent.
6. Run one redacted real-shape smoke to establish the actual active-entry
   export/download locator and one historical settled contest-detail shape.
   Then run the separately required 832,342-row rehearsal. These are release
   gates, not substitutes for the acquisition contract.

This repair does not need to change scoring, generation, selection,
allocations, the paid exporter, or the legacy v2 implementation.

## Independent validation

- Candidate commit and tree reproduced exactly.
- Python compilation of the changed contract, focused test, and shape-smoke
  script: **PASS**.
- `git diff --check` from exact implementation base through candidate:
  **PASS**.
- Focused repaired-v3 suite: **PASS**, exit 0, 36 test cases/dots in 16.16
  seconds after an exact empty global pytest census.
- Legacy-v2 suite: **PASS**, 15/15 in 1.06 seconds. Its first exit-zero
  execution raced with a new lab CP-4 invocation that appeared after the exact
  pre-command census and is not treated as evidence. After that process
  terminated, a fresh exact census was empty, the 15/15 suite was repeated,
  and a same-shell post-run census remained empty. Candidate/base blob
  identities also prove the v2 source and tests are unchanged.
- No broad test ran.
- No real-shape file was opened; the real-shape gate remains operationally
  outstanding.

The exact next action is a bounded provider-acquisition repair followed by a
fresh independent review. Do not publish the live A5 allocation/manifests,
claim acceptance/complete-field authority, or perform a paid upload from this
candidate.
