# Week-1 A5 capture contract v3

Status: **HOLD before manifest publication or paid upload.** The evidence
adapter is fail-closed, but a generation-pinned lobby projection and the final
four-book allocation raw/semantic identity do not yet exist. The code must not
invent either identity.

This contract records evidence for the already approved A5 allocation. It does
not change scoring, generation, selection, paid-entry behavior, or deployment.
The implementation is
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py`.

## Exact A5 boundary

| Role | Contest ID | Name | Fee | Capacity | Limit | Template | Paid K |
|---|---:|---|---:|---:|---:|---:|---:|
| `milly-5` | `193028206` | NFL $3.5M Fantasy Football Millionaire [$1M to 1st] | $5 | 832,342 | 150 | `963916` | 57 |
| `large-20max-3` | `193028208` | NFL $400K Play-Action [20 Entry Max] | $3 | 158,541 | 20 | `388597` | 20 |
| `championship-qualifier-18` | `194478066` | $14M 2026 Fantasy Football World Championship Qualifier #6 | $18 | 5,000 | 150 | `970817` | 3 |
| `championship-qualifier-5` | `194478065` | $14M 2026 Fantasy Football World Championship Qualifier #5 | $5 | 17,835 | 150 | `970816` | 10 |

The draft group is `151307`, slate is `dk-151307`, and lock is
`2026-09-13T17:00:00Z`. The paid total is 90 entries/$449. P_CTRL,
D400_DEMAX, and D800_WEMAX remain the same-K shadow policies.

Contest ID, name, draft group, lock, fee, capacity, limit, qualifier,
guarantee, payout ladder, and qualifier ticket terms are rederived from the
exact contest-detail bytes. Template IDs are source-qualified to the earlier
public-lobby projection recorded in
`reports/2026-09-04-week1-a5-live-contest-capture.md`; contest-detail bytes do
not contain them. That projection currently has only semantic SHA-256
`5a98a3ebeb03e0f95afe8845e1f66cf7a21882054f45dd23ef9e85cde60611ee`,
not a raw object identity. Allocation publication therefore remains blocked.

The pinned terminal contest-source manifest is:

- URI:
  `gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/contests/a5/20260904T105535Z/manifest.json`
- generation `1788519340044066`
- 2,664 bytes
- SHA-256
  `28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4`

Its four exact child identities are pinned in the module. Both qualifiers must
retain one first-place ticket with the two eligible FFWC destination names;
cash and ticket awards are distinct facts.

## Identity and exact-reopen law

Every semantic JSON artifact contains `semantic_sha256`, computed over the
canonical body with that field absent. Its complete canonical serialization,
which includes `semantic_sha256`, has a separate external identity:

```text
artifact_identity = {uri, generation, sha256, bytes}
```

The two hashes are not compared for equality. Every consumer generation-
exactly reopens the external identity, verifies byte length and raw SHA-256,
parses those bytes, and then recomputes `semantic_sha256`. Provider creation
time—not a URI spelling—enforces pre-lock and settlement boundaries.
`frozen_at`, `accepted_at`, and `publish_by` are prospective create-once
publication cutoffs: the bytes are serialized first, the object is published,
and its provider creation time must be no later than that already-declared
cutoff. They are not backdated observation times. Raw source `observed_at`
values are separate and must be no later than the provider creation time of
the archived source bytes. Create-once publication is followed by an
independent exact reopen before its receipt is returned.

## Evidence sequence

### 1. Player bridge, books, and allocation authority

The bridge must exact-reopen the paid exporter's normalized salary catalog and
recompute its production catalog SHA. It then proves a complete one-to-one
mapping among canonical internal IDs, stable DK player IDs, and slate-specific
DK draftable IDs, with the exact display name, team, eligible position, salary,
active status, slate, and draft group. Each exact book is reopened from bytes
and replays nine ordered Classic slots, position eligibility, salary, team
limit, bridge membership, and the $50,000 salary cap. It re-enforces:

```text
roster_sha256 = sha256(canonical sorted internal-player membership)
lineup_id = "lineup-v1-" + roster_sha256
```

`week1-a5-allocation-authority/v2` is derived from those four exact books, the
exact contest sources, and the generation-pinned lobby/template projection.
It records all paid and shadow prefix edges. After create-once publication and
independent reopen, both its raw object identity and semantic SHA must be
committed as the only accepted live A5 root. `live_capture_pins()` intentionally
fails until that happens.

### 2. Four pre-lock manifests

Each `dk-contest-manifest/v3` is reconstructed from the pinned allocation and
source bytes. `advertised_field_capacity` and
`entries_observed_at_freeze` remain separate. No final size, score, rank,
payout result, or other realized outcome is present. Every referenced source,
book, bridge, allocation, and manifest must have provider creation time no
later than the declared freeze and strictly before lock.

### 3. Paid acceptance and four-contest root

`week1-a5-entry-acceptance/v2` exactly reopens:

- the production exporter's `paid-entry-capture/v1` JSON;
- the filled DK CSV whose raw SHA/bytes the prepared capture records;
- a separately archived raw DraftKings active-entry export;
- `dk-accepted-entry-provider-capture/v1`, which binds that raw export to the
  allowlisted authenticated provider method, exact A5 contest, observation
  time, raw generation, and prospective publication cutoff; and
- `dk-accepted-entry-evidence/v2`, rebuilt only from that capture/raw export;
- the manifest, allocation, P_MIX book, and player bridge.

Accepted Entry IDs and ordered slot IDs are parsed from the reopened provider
CSV. `complete=true`, accepted status, exact K, and the normalized rows are
therefore derived facts, not caller inputs. The provider observation must be a
separate archived object from the locally filled upload; roster truth is then
joined back to the filled CSV and exact book. A free-standing JSON array of
`status=accepted` rows is rejected. Min-churn assignment is a legitimate
permutation:

```text
entry_index = export_ordinal + 1
lineup_rank = paid_input_book_ordinal + 1
```

The two domains must independently be complete bijections over `1..K`.
`entry_index == lineup_rank` is not required after fill. The root exactly
reopens all four manifests/receipts and requires K57/K20/K3/K10 plus 90
globally unique Entry IDs before lock.

### 4. Complete-field normalization and settlement

A `dk-final-field-provider-capture/v1` receipt binds two exact raw objects in
one capture: the DraftKings contest-detail HTTP response body and the full
standings export. Reviewed code derives contest ID, draft group, settled state,
and final submitted entry count from `contestDetail` in the raw provider body;
it stream-counts the exact standings Entry IDs and refuses publication unless
that count agrees. The retired `dk-final-field-provider-source/v1` caller
wrapper cannot authorize a field, even when a truncated CSV and false claimed
N agree.

`dk-final-field-evidence/v2` and `dk-normalized-complete-field/v2` are rebuilt
only from that generation-exact provider capture, its two raw objects, and the
exact player bridge. Normalization derives every Entry ID, competition rank,
signed score, cash payout, ticket award, settled time-remaining value, and
final roster. Raw parsed row count must exactly equal the entry count parsed
from the settled provider response.

`dk-contest-settlement/v2` reopens the normalized artifact, raw CSV,
final-size evidence, four-contest acceptance root, per-contest manifest and
acceptance, and bridge. It rejects another contest's field and a top-N file
paired with the genuine displayed size. Every accepted roster must equal its
final roster; a late swap requires a separately reviewed frozen-transition
successor and cannot be asserted by a boolean.

Guarantee/underfill behavior and payout tiers come from contest-detail bytes.
Cash and qualifier tickets are reconciled separately. Tied cash groups use
the exact pooled cents with floor/one-cent-remainder allocation; no
`field_size × one cent` tolerance exists. Negative fantasy scores are valid.

## Operational order and remaining gates

1. Publish a generation-pinned copy of the already recorded lobby projection,
   without rereading or changing its September 4 semantics.
2. Finish and exact-publish the player bridge and all four exact K80 books.
3. Build, create-once publish, independently reopen, and code-pin the allocation
   raw identity and semantic SHA.
4. Independently review this repair and run its focused adversarial suite plus
   an outcome-blind smoke against the five real source objects and a
   representative production prepared-entry/filled-CSV/active-entry-export
   shape. `scripts/week1_a5_capture_real_shape_smoke.py` is default-off,
   performs no writes or network calls, emits only redacted counts/hashes, and
   requires `--execute-real-shape-smoke`. Its post-lock mode additionally
   requires `--allow-postlock-outcome-bytes`.
5. Only after those gates, publish four manifests, perform owner-authorized
   uploads, capture raw acceptance evidence, and publish the 90-entry root.
6. After contests settle, preserve all four complete fields inside DK's short
   export window and publish normalized/settlement evidence.

There is still no governed repository-owned end-to-end A5 publisher/CLI. Do
not manually stitch JSON. Any future shared Cloud Run refresh must use
`scripts/launcher_registry.sh run`, one authenticated immutable image, and
durably record execution IDs and terminal counters. The direct `gcloud run
jobs execute` examples from the held candidate are withdrawn.

The separate legacy v2 rehearsal module and its tests remain available for
fixtures and historical compatibility, but its single mutable-meaning
`field_size` procedure is not a live A5 authority. The held caller-normalized
accepted-evidence and final-field-source v1 adapter shapes are explicitly
retired rather than retained as a fallback.

## Validation boundary

The adversarial suite covers raw-versus-semantic identity, wrong generation,
bytes and raw SHA, alternate allocation roots, post-lock provider time,
reverse min-churn permutation, missing/duplicate realized ranks, fabricated
projections against genuine raw evidence, immutable contest facts, truncated
and cross-wired fields, final-roster drift, qualifier tickets, and negative
scores. No test, smoke, cloud call, DK action, or paid action is authorized by
this document itself.
