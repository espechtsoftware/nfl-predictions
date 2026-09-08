# Week-1 A5 capture-v3 P2 provider-acquisition authority repair

Date: 2026-09-08

Branch: `codex/week1-capture-v3-p2-repair-20260908`

Implementation base: lab-independent-review tip
`1c63b7028e8dcc8e9ec138b834757f0de89fc419`

Independent P1 HOLD report commit:
`04686eb4d9dcdc2a8b6c4c5594f2e20af904328e`

Disposition: **bounded P2 implementation candidate; operational HOLD; fresh
independent review required**

## Why this repair exists

The P1 candidate made raw objects immutable and rebuilt every downstream
projection from exact generations. It did not establish that those bytes came
from DraftKings. Its success fixture copied the locally filled upload into a
second object and labeled it an active-entry export. Its final-field fixture
authored a `contestDetail` body with a selected `entries=N` value. A copied
upload and a fake provider-shaped body plus a matching N-row prefix could
therefore remain internally consistent.

This repair makes generic object storage and provider acquisition two separate
trust boundaries. An exact GCS-like object proves bytes and provider creation
time. It does **not** prove source. Provider capture now additionally requires
an exact acquisition receipt recognized by an independent authenticated-
acquisition authority.

## Narrow implementation

The contract adds three acquisition profiles:

1. authenticated active-entry export download;
2. authenticated contest-detail API GET; and
3. authenticated contest-scoped full-standings download.

Each profile consumes one canonical
`dk-authenticated-provider-acquisition/v1` artifact. The artifact binds:

- one authority event ID and closed authority profile;
- exact GET method and profile-specific canonical locator;
- the authenticated DraftKings account-session surface;
- exact contest role, contest ID, and draft-group ID;
- response observation time, HTTP status, media type, and download
  disposition where applicable;
- exact collector source commit, collector-code SHA-256, and immutable image
  digest;
- one immutable transport-trace identity;
- one immutable raw-body identity and its exact provider creation time; and
- its own distinct semantic and serialized-object identities.

The generic store and `AuthenticatedProviderAcquisitionAuthority` independently
reopen the same acquisition-receipt generation. Authority bytes, object
identity, provider creation time, and authority event ID must agree exactly.
The contract also exact-reopens the raw object and the transport trace. The
trace must be canonical JSON and reproduce the receipt's method, locator,
authenticated surface, observation, response metadata, collector identity,
and raw identity. Observation must precede both source archives; both archives
must precede the acquisition receipt and the enclosing prospective cutoff.

The provider-capture schemas advance to:

- `dk-accepted-entry-provider-capture/v2`; and
- `dk-final-field-provider-capture/v2`.

Their old v1 builders and validators now fail explicitly. Accepted-entry
capture accepts an acquisition receipt rather than a raw identity and caller
timestamp. Final-field capture accepts two acquisition receipts rather than
caller-selected contest-detail and standings identities. Every downstream
acceptance, root, normalization, and settlement rebuild receives the same
authority dependency and reauthenticates the acquisition chain.

## Causal ordering repaired

For acceptance, the production prepared-entry capture and filled upload must
exist no later than the authenticated provider observation. The provider
observation must remain strictly before lock. This closes the P1 path in which
an alleged acceptance could predate the upload it purported to confirm.

Byte equality is not itself prohibited. A real post-upload active-entry export
could legitimately serialize exactly like the filled upload. The distinction
is that only the authority-recognized acquisition can establish provider
observation; publishing another copy into the generic object store cannot.

## Exact active-entry locator remains fail-closed

The known `https://www.draftkings.com/mycontests` URL is an account page, not
proven to be the exact export response URL. The production constant
`PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR` is deliberately `None`. Live acceptance
acquisition therefore fails before parsing until one redacted real-shape smoke
establishes the actual locator and an independent review pins it. Tests patch
only that explicit absent pin with a fixture-only URL.

The contest-detail locator and full-standings locator are closed to the exact
contest-specific forms already used by production:

```text
https://api.draftkings.com/contests/v1/contests/<contest_id>
https://www.draftkings.com/contest/exportfullstandingscsv/<contest_id>
```

## Adversarial coverage

The focused suite now includes both attacks required by the independent HOLD:

- a separately archived byte-for-byte copy of the locally filled upload,
  accompanied by a perfectly shaped but authority-unrecognized acquisition
  receipt, cannot become accepted; and
- a caller-authored settled `contestDetail` body saying N plus an N-row
  standings prefix, each with internally consistent object identities, cannot
  become a complete field when the body acquisition is not recognized by the
  authority.

It also checks the new prepared/filled-before-observation ordering. The
ordinary success fixture intentionally retains byte-identical filled/provider
CSV bodies but issues the provider copy through the separate test authority,
demonstrating that authority rather than inequality is the distinction.

All prior raw/semantic, generation, timestamp, min-churn, contest-fact,
truncation, cross-wire, roster-drift, payout, ticket, and negative-score cases
remain.

## Validation completed

Before each pytest command, the exact global census

```text
ps -eo pid=,etimes=,comm=,args= | awk '$3 ~ /python/ && $0 ~ /-m pytest/ {print}'
```

was empty. Each same-shell post-command census was also empty.

- Focused repaired-v3 suite:
  `PYTHONPATH="$PWD/src:$PWD" ... python -m pytest -q
  tests/test_week1_a5_capture_contracts.py` — **42/42 passed**, 15.87 seconds,
  140,060 KiB maximum RSS after the complete repair and final hardening landed.
- Legacy-v2 compatibility suite:
  `tests/test_contest_capture_rehearsal.py` — **15/15 passed**, 1.04 seconds,
  145,712 KiB maximum RSS. That source and test module are unchanged.
- Python compilation for the contract, focused suite, and default-off shape
  smoke — **PASS**.
- `git diff --check` — **PASS**.
- Ruff is unavailable in the current environment and was not inferred.

No broad pytest suite or local simulation ran. No cloud, provider, browser,
DraftKings, paid-entry, deployment, scoring, generation, selection, warehouse,
or outcome state was read or changed.

## What remains deliberately blocked

This branch defines and enforces the authority interface; it does not invent a
live authority event or pretend a generic local file is one. Before live A5
use, production still needs:

1. a separately reviewed live implementation of
   `AuthenticatedProviderAcquisitionAuthority` backed by the governed
   authenticated collector/retained event ledger;
2. one redacted active-entry real-shape acquisition to pin the exact download
   locator and response shape;
3. one redacted historical-settled contest-detail/full-standings shape check;
4. the already outstanding 832,342-row rehearsal;
5. generation-pinned lobby/template projection, player bridge, four exact
   books, final allocation raw/semantic root, and governed A5 publisher;
6. a fresh independent code/adversarial review of this exact candidate; and
7. only afterward, the owner's separate paid-upload authorization and live
   acquisition/capture events.

`live_capture_pins()` remains default-off. This repair changes no allocation,
lineup, score, model, selector, generator, deployment, or paid action.

## Exact next action

Commit and push the bounded candidate, then independently review the exact
commit/tree. A GO may authorize only integration of this contract. It must not
be read as authorization to fabricate an authority receipt, pin an unobserved
active-entry locator, freeze the live allocation, contact DraftKings, or make a
paid upload.
