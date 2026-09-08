# Week-1 A5 capture-v3 provider-authority repair

Date: 2026-09-08

Branch: `codex/week1-capture-v3-p1-repair-20260908`

Exact implementation base: `4713cb835bd7e190e1cd1015125bbaeee1f397b5`

Independent HOLD reviewed: report commit
`1f4e0f82` with formatting tip
`e15a6bb121f586d62e873f4c07542dde95a0e32b`

Disposition: **bounded implementation candidate; operational HOLD**

## Scope

This successor repairs the two raw-authority P0 findings and the real-store
timestamp concern in the independent review. It changes only the isolated
Week-1 A5 evidence adapter, its adversarial fixtures, a default-off local shape
smoke, and documentation. It does not change scoring, simulation, lineup
generation, selection, allocations, paid-entry behavior, deployment, cloud
state, DraftKings state, or any historical/live outcome.

The separate legacy `contest_capture_rehearsal.py` v2 implementation and
`tests/test_contest_capture_rehearsal.py` are untouched.

## P0-1: accepted entries now originate in exact provider bytes

The held `dk-accepted-entry-evidence/v1` accepted a caller-created JSON array
of `status=accepted` rows. The successor retires that shape and adds this
chain:

```text
raw authenticated DraftKings active-entry export CSV
  -> dk-accepted-entry-provider-capture/v1
  -> dk-accepted-entry-evidence/v2
  -> week1-a5-entry-acceptance/v2
```

The raw active-entry export is archived as its own create-once object. The
provider-capture artifact generation-exactly reopens those bytes, parses the
exact A5 contest/name/fee/Entry IDs/ordered Classic slots, requires exact K,
and records only a derived count and projection hash. The normalized evidence
artifact exact-reopens and fully revalidates that provider capture and raw
generation before deriving accepted status and rows. A caller can no longer
provide accepted rows as an independent input.

The provider observation must be a different archived generation from the
locally filled upload. Acceptance then requires its Entry-ID set and ordered
slot rosters to equal the separately exact prepared/filled/book lineage. This
preserves the legitimate min-churn permutation between export ordinal and
book ordinal. It also avoids inventing a second roster representation: the
provider export observes the active Entry IDs/slots, while canonical internal
roster truth continues to come from the exact filled CSV, player bridge, and
book.

The method is deliberately narrow:
`authenticated-active-entry-export-csv`. If the real DraftKings surface does
not provide that export shape, this code does not accept a free-standing
operator JSON substitute. A separately reviewed lossless browser-evidence and
attestation adapter would be required.

## P0-2: final N/state now originate in raw contest-detail bytes

The held `dk-final-field-provider-source/v1` wrapper allowed a caller to place
`contest_state=Settled` and `displayed_final_field_size=N` in normalized JSON.
That shape and its v1 builders now fail explicitly.

The successor binds both raw objects in one
`dk-final-field-provider-capture/v1` receipt:

1. the exact DraftKings contest-detail HTTP response body; and
2. the exact full standings CSV.

Reviewed code parses `contestDetail.contestKey`, `draftGroupId`,
`contestState`, `contestStateDetail`, and `entries` directly from the raw
provider response. It separately stream-counts unique Entry IDs in the raw
standings file and refuses the capture unless the two counts agree. It also
requires the exact A5 contest/draft group, a supported settled primary state,
post-lock observations/provider creation, and a final count no greater than
the source-pinned advertised capacity.

`dk-final-field-evidence/v2` and
`dk-normalized-complete-field/v2` then rebuild only from that exact capture and
its exact raw children. A top-N CSV paired with a new wrapper claiming the
same false N has no accepted route. A normalized false N paired with a genuine
provider capture fails deterministic reconstruction.

## Executable timestamp law

The synthetic candidate used equality between declared evidence times and
provider creation times, which concealed whether real GCS publication was
possible. The successor gives the fields one executable meaning:

- `observed_at`, `provider_observed_at`, and `standings_observed_at` are source
  observation times. They must not be later than creation of the archived raw
  object.
- `publish_by`, `frozen_at`, and `accepted_at` are prospective create-once
  publication cutoffs. The cutoff is serialized first; publication and exact
  reopen must report a provider creation time no later than it.
- pre-lock cutoffs are strictly before lock; post-lock cutoffs and source
  observations are strictly after lock; nested cutoffs must be monotone.
- a provider-capture artifact cannot predate either raw archive it references.

The focused fixture now uses strict intervals rather than equality: raw
observation archive, provider-capture publication, normalized-evidence
publication, acceptance receipt, and root each precede their independently
declared cutoff. New adversaries move the raw archive before its observation
or the capture publication after its cutoff and require rejection.

## Default-off real-shape smoke

`scripts/week1_a5_capture_real_shape_smoke.py` is a local, write-free parser
smoke. With no explicit `--execute-real-shape-smoke`, it exits before opening
any file. It makes no network/provider/cloud/warehouse call and prints no Entry
IDs, roster rows, names, scores, or payouts—only redacted counts, byte lengths,
hashes, state labels, and parser-profile identities.

Pre-lock acceptance mode reads one operator-supplied active-entry export.
Post-lock final-field mode additionally requires
`--allow-postlock-outcome-bytes` before it will open a standings file. This is
support for the required real-shape gate, not an authorization to run it or an
authority publisher.

## Adversarial coverage added

The focused tests now encode:

- exact normalized acceptance reconstruction from a separately archived raw
  provider export;
- rejection of fabricated accepted rows borrowing an honest raw capture;
- rejection when raw acceptance archive time predates its observation;
- rejection when provider-capture publication misses its prospective cutoff;
- explicit retirement of the caller-authored final-field wrapper;
- rejection of a raw standings count that differs from the settled provider
  response's final `entries` value;
- rejection of a normalized matching-false-N projection against the genuine
  raw provider body; and
- redacted/write-free shape projections plus default-off CLI behavior.

All retained min-churn, source-fact, bridge/book, payout/tie/ticket, negative
score, exact-generation, semantic/raw hash, cross-wire, and roster-drift cases
remain in the same focused module.

## Validation performed in this implementation turn

- Read the complete repository instructions and exact independent HOLD report.
- Python compilation of the modified contract, focused test, and smoke script:
  **PASS**.
- `git diff --check`: **PASS**.
- Ruff was not available in the current shell/shared environment; this is
  recorded rather than inferred.
- Pytest was intentionally **not run** because the lab owns the repository's
  single global pytest lane during this implementation interval.
- No provider, cloud, DraftKings, paid, scoring, selection, generation, or
  outcome action was performed.

## Exact remaining operational blockers

1. **Real acceptance shape/provenance.** Production still needs one redacted,
   real DraftKings post-upload active-entry export and its true source locator
   before independent review can confirm the narrow parser profile. If DK
   exposes only browser UI evidence, implement and independently review a
   lossless page/HAR/screenshot-attestation successor; do not weaken this
   adapter to caller-normalized rows.
2. **Real settled contest-detail shape.** A representative exact raw
   contest-detail response must confirm the terminal state labels and that
   `contestDetail.entries` is the final submitted count. A historical settled
   contest can be used for shape-only review; Week-1 outcomes are not needed
   for pre-lock release.
3. **Governed publisher/store.** The module still injects an
   `ImmutableObjectStore`; there is no reviewed GCS-backed A5 end-to-end
   publisher that archives both raw sources, serializes prospective cutoffs,
   publishes create-once, exact-reopens, and emits the receipts. The local
   smoke is intentionally not that publisher.
4. **Existing A5 inputs.** The September 4 lobby projection still lacks a raw
   generation identity. The final player bridge, P_MIX/P_CTRL/D400_DEMAX/
   D800_WEMAX books, allocation identity, and code pins still do not exist;
   `live_capture_pins()` remains default-off/HOLD.
5. **Release verification.** Independent static/adversarial review, the
   focused serial suite, unchanged v2 compatibility suite, one outcome-blind
   real-shape smoke, and the realistic 832,342-row streaming/normalization
   rehearsal remain required before live manifest publication.
6. **Later operator events.** Paid upload/acceptance necessarily awaits owner
   authorization and real pre-lock provider evidence. Complete-field capture
   and settlement necessarily wait until contests settle. Shadow-book grading
   and any late-swap transition remain separate visible P1 work.

Until those gates close, this branch is a provider-authority repair candidate,
not a live-capture or paid-entry authorization.
