# Week-1 contest-capture rehearsal

This is the local mechanical rehearsal that must pass before
the nonrecoverable 2026 Week-1 DraftKings standings window. It complements
[`dk-full-field-capture.md`](dk-full-field-capture.md); it does not replace the
real post-settlement `capture-dk-standings --apply` operation.

The checked-in fixture contains only synthetic settlement values. A real-mode
run reads outcome-bearing scores, ranks, ownership, and payouts and says so in
its receipt; it is never outcome-blind. The rehearsal performs no network,
Cloud Storage, or BigQuery operation. It:

1. reopens a versioned `dk-contest-manifest/v2` and every local evidence/book
   artifact by SHA-256 and byte count, then parses and reconciles their
   semantics;
2. proves the manifest froze before lock and contains contest/slate identity,
   field size, fee, entry limit, payout ladder, late-swap policy, paid and
   shadow book bindings, and append-only correction lineage;
3. calls the production complete-field parser with `apply=False`;
4. validates exact field size, settlement, roster parsing, ownership, ranks,
   winner/tie identity, duplication, and payout splits across ties;
5. prepares and hashes structural `contest_entries` and `contest_ownership`
   row shapes in memory without loading them; it explicitly does not claim to
   reproduce the live destination identity; and
6. writes a self-hashed local receipt create-only, accepting only a
   byte-identical retry.

Every receipt states that it is validation-only, performed no external write,
and is not scientific or production evidence. A green rehearsal does not
claim that the live standings were captured.

## Run the checked-in representative rehearsal

```bash
source .venv/bin/activate
python scripts/rehearse_week1_contest_capture.py \
  --standings tests/fixtures/week1_contest_capture/contest-standings-12345.csv \
  --manifest tests/fixtures/week1_contest_capture/contest-manifest-v2.json \
  --captured-at 2026-09-14T23:00:00Z \
  --rehearsed-at 2026-09-01T16:00:00Z \
  --confirm-settled \
  --confirm-full-field \
  --receipt reports/week1-contest-capture-rehearsal/fixture-v1/receipt.json
```

The fixture uses representative synthetic Week-1 dates and four entries. Its
post-settlement timestamp is a future simulation, not an assertion that a
capture occurred; the receipt records it as `representative_capture_at` with
`representative_capture_is_simulated=true`. It contains no 2026 outcome. A
non-fixture rehearsal instead fails if its rehearsal time precedes its real
capture. The command is safe to repeat: the second run must report
`already-identical`; different bytes at the same receipt path fail.

## The v2 contest manifest

Keep each referenced evidence file beside the JSON manifest. Relative paths
may not escape that directory. The manifest contains:

- the numeric DraftKings contest and draft-group IDs, slate ID, lock time,
  Classic roster format, submitted field size, entry fee, and entry limit;
- the payout ladder in integer micro-dollars;
- content identities and capture times for structured JSON contest metadata,
  payout-ladder, and late-swap evidence whose values exactly equal the
  manifest;
- every paid and shadow book's ID, count, pre-lock freeze time, and content
  identity. Book JSON must repeat the contest and draft-group IDs and contain
  the exact number of unique lineup IDs. A paid artifact must be
  `paid-classic-book/v2` and receipt exact-K, unique-roster, DK-legality, and
  active-player checks as true; and
- a correction revision, predecessor manifest hash, and reason. Revision 0
  must not name a predecessor; every later revision must.

The checked-in
`tests/fixtures/week1_contest_capture/contest-manifest-v2.json` is the exact
schema example. For live operation, copy it into the durable weekly operations
directory, set `rehearsal_fixture` to `false`, replace all representative
metadata and artifact identities, and keep the previous JSON immutable when a
correction is needed.

## Live Week-1 procedure

### Before lock (deadline: 2026-09-13 17:00Z)

1. Save the DraftKings contest page/metadata, payout ladder, and late-swap
   rules locally; record their observation times.
2. Create revision 0 of the real v2 contest manifest and bind every actual
   paid book and every frozen counterfactual shadow. All book artifacts and
   the manifest must freeze before lock.
3. Verify the total paid entry count does not exceed the contest entry limit.
4. Keep the manifest and evidence in durable storage. Do not put browser
   cookies or DraftKings credentials in any file or command.

### Monday/Tuesday after settlement

1. In a logged-in browser, download the complete standings CSV before
   DraftKings removes it. Record the submitted field size shown on the page,
   not contest capacity.
2. Save Entry History and preserve the actual download time. Confirm the
   contest page says complete after scoring review.
3. Run this local rehearsal against the real v2 manifest and CSV with both
   explicit confirmation flags. It must pass the payout, tie, field,
   ownership, source, and book-binding checks. Its receipt will state
   `live_realized_outcomes_read=true`.
4. Run the existing validation-only command from
   [`dk-full-field-capture.md`](dk-full-field-capture.md).
5. Only after both validations pass, run `capture-dk-standings` with
   `--confirm-settled --confirm-full-field --apply` to create the immutable GCS
   archive and deterministic BigQuery loads.
6. Preserve both receipts, verify the GCS receipt exists, and let the normal
   backup cadence snapshot `contest_entries` and `contest_ownership`.

The live apply requires Google Application Default Credentials plus
`GCP_PROJECT`, `GCS_BUCKET`, and the BigQuery dataset settings. The browser
download is the only step requiring a DraftKings login. If the destination
tables are missing the expected partition/clustering contract, apply
`sql/raw/004_ownership.sql` and validate again; do not bypass the preflight.

## Still manual by design

This rehearsal does not download DraftKings data, choose the contest, infer
the displayed field size, authorize settlement, apply warehouse writes, or
verify the post-apply GCS object. Those are deliberate operator boundaries.
The next product step after the first real capture is joint K-book
counterfactual settlement; the current bridge still evaluates unentered
lineups one at a time and must not be labeled portfolio EV.
