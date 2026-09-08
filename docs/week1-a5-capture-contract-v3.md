# Week-1 A5 capture contract v3

This contract records the operator-frozen Week-1 allocation without changing
generation, scoring, selection, or the paid-entry path:

| Role | Contest ID | Paid K |
|---|---:|---:|
| `milly-5` | `193028206` | 57 |
| `large-20max-3` | `193028208` | 20 |
| `championship-qualifier-18` | `194478066` | 3 |
| `championship-qualifier-5` | `194478065` | 10 |

The paid total is 90 entries and the predeclared shadow total is 270 entries:
P_CTRL, D400_DEMAX, and D800_WEMAX at the same K for each contest.

The implementation is
`src/nfl_dfs/ingest/week1_a5_capture_contracts.py`. It is a pure contract
layer. It performs no network, Cloud Storage, BigQuery, DraftKings, scoring,
selection, or entry mutation.

## Why v3 exists

`dk-contest-manifest/v2` is retained unchanged for its existing rehearsal.
Its single `field_size` field is not safe for the live Week-1 record because
three distinct facts exist:

1. `advertised_field_capacity`, captured before lock;
2. `entries_observed_at_freeze`, a pre-lock lobby snapshot; and
3. `observed_final_field_size`, known only from a complete settled field.

V3 records only the first two. `dk-contest-settlement/v1` records the third.
The settlement names the exact v3 manifest generation; it never edits or
reinterprets the pre-lock values. An underfilled contest is therefore normal,
not a manifest mismatch.

## Artifact sequence

### 1. One `dk-contest-manifest/v3` per contest, before lock

Each manifest must bind:

- exact contest ID, name, role, draft-group ID, slate, fee, entry limit, lock,
  late-swap state, advertised capacity, and current observed entries;
- separately timestamped and generation-pinned contest metadata, payout,
  late-swap, and current-entry sources;
- the exact `week1-a5-contest-allocation/v1` root;
- the one-contest 1-based paid and shadow edge slices from that root;
- one contest-ready P_MIX paid book and P_CTRL, D400_DEMAX, and D800_WEMAX
  shadow books at exact contest K. Every book row binds lineup rank, lineup ID,
  canonical roster SHA, internal player IDs, and ordered DK draftable IDs;
- a payout ladder validated against advertised capacity, plus an explicit
  underfill policy; and
- revision-zero lineage or an exact predecessor SHA and correction reason.

The schema has no final-field or realized-result field. Every timestamp and
source must precede the slate lock. The allocation and all four book orders
are rederived during validation.

### 2. One `week1-a5-entry-acceptance/v1` per paid contest, before lock

The existing paid exporter can emit `paid-entry-capture/v1` through its
`prepared_entry_capture` callback without changing CSV bytes. The acceptance
builder binds that payload, the exact filled CSV identity, and separately
captured post-upload Entry History/accepted-entry evidence.

Each row retains the exact DraftKings Entry ID and this explicit bridge:

```text
a5_entry_index = prepared export_ordinal + 1
a5_lineup_rank = prepared paid_input_book_ordinal + 1
```

The receipt rejects a missing or duplicate Entry ID, wrong contest/draft
group, wrong K, roster substitution, lineup drift, or ordered-slot drift.

### 3. One `week1-a5-entry-acceptance-root/v1`, before lock

The root requires all four roles, exact K57/K20/K3/K10, four generation-pinned
acceptance receipts, 90 globally unique DraftKings Entry IDs, and the exact A5
allocation root. Three successful uploads are not a complete root.

### 4. One `dk-contest-settlement/v1` per contest, after settlement

The settlement requires complete-field and settled confirmations, the exact
pre-lock manifest, allocation root, and four-contest acceptance root. It
records `observed_final_field_size` separately and requires it to be no larger
than advertised capacity. The normalized standings row count must equal the
observed final count, competition ranks must reproduce from points, every
accepted paid Entry ID must be present, and payouts—including ties—must
reconcile over ranks that actually exist in the final field.

For `prelock-applicable-ranks-only`, underfill leaves the pre-lock ladder
unchanged and only ranks `1..observed_final_field_size` are applicable. A
contest whose rules require a new official ladder on underfill must use
`official-settlement-ladder`; v1 deliberately fails that case pending a
separately sourced successor instead of silently changing the pre-lock ladder.

## Required live order

### Refresh point-in-time inputs

Run these jobs serially against one accepted immutable production image. Do
not bypass a failed predecessor and do not use an older projection batch:

```bash
gcloud run jobs execute ingest-nflverse \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute ingest-dk \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute ingest-contests \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute ingest-odds \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute ingest-props \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute ingest-weather \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute build-features \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute project-slate \
  --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute check-freshness \
  --project nfl-predictions-503414 --region us-central1 --wait
```

Before continuing, require a nonempty 2026 Week-1 injury snapshot, successful
feature build, one atomic current projection batch covering the current DK
salary catalog, and green freshness. The commands above mutate production and
therefore require the ordinary operator/provider authorization; this contract
module never runs them.

### Freeze books and allocation

The authoritative dependency order is:

1. exact current DK salary/player bridge and accepted point-in-time projection
   batch;
2. frozen D800 candidate population and participation-designation source;
3. P_MIX and P_CTRL ordered K80 selection plus independently reopened terminal
   participation package;
4. exact D400_DEMAX and same-pool D800_WEMAX ordered K80 books;
5. contest-ready materializations for all four policies, including canonical
   player IDs and ordered DK draftable IDs;
6. `build_week1_a5_allocation_v1(...)`, using the four frozen live contest
   sources and the four exact ordered books;
7. four v3 pre-lock manifests using
   `build_week1_prelock_manifest_v3(...)`; and
8. generation-pinned, create-once publication plus independent reopen.

There is currently no accepted, repository-owned one-command publisher that
executes steps 2–8 for the P_MIX A5 design. `scripts/publish_week1_operating_book.py`
publishes the older canonical operating-book materialization and is not a
substitute for the four-policy P_MIX allocation. Do not manually stitch
unreceipted JSON or label an older K80 book as A5. The missing governed A5
publisher/materializer is a pre-entry blocker, separate from this now-defined
evidence schema.

### Upload and prove acceptance

For each contest, export exactly K lines from the already-frozen P_MIX book.
Invoke the existing paid fill with `prepared_entry_capture` enabled and archive
its exact payload and filled CSV before upload. After upload, download or save
the Entry History/accepted-entry view containing the exact Entry IDs and
rosters. Build one acceptance receipt, independently reopen it, and only then
build the four-contest root. Never infer acceptance merely from an HTTP 200 or
from the requested upload rows.

### Capture settlement

Within DraftKings' short export window, download the complete standings for
each exact contest and record the final submitted field size shown on the
settled page. First validate without writes:

```bash
nfl-dfs capture-dk-standings ~/Downloads/contest-standings-CONTEST_ID.csv \
  --season 2026 --week 1 --contest-id CONTEST_ID \
  --contest-name "EXACT CONTEST NAME" --expected-entries FINAL_FIELD_SIZE
```

Only after the complete-field and payout checks pass, run the same command
with `--confirm-settled --confirm-full-field --apply`. Then construct the v1
settlement against the generation-pinned normalized capture, independently
reopen it, and preserve the prior settlement if DraftKings later corrects the
contest. A correction gets a new artifact naming the prior settlement SHA.

## Validation

Focused tests are in `tests/test_week1_a5_capture_contracts.py`. They cover
filled/underfilled semantics, impossible final size, wrong contest identity,
post-lock pre-lock artifacts, partial standings, accepted roster drift,
incomplete roots, missing correction predecessors, payout ties, and guaranteed
underfill behavior. Existing v2 rehearsal code and fixtures are untouched.

