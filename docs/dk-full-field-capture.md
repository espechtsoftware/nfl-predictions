# DraftKings full-field standings capture

Use this manual workflow on Monday or Tuesday after each target NFL contest
settles. DraftKings removes the export quickly; the raw CSV cannot be recovered
later. Capture the Millionaire Maker and every qualifier whose field behavior
or advancement line we want to model.

The command is deliberately unscheduled and defaults to validation-only. It
never needs a DraftKings credential: download the **full contest standings
CSV** in a logged-in browser, then pass the local file to the CLI.

## 1. Validate without writing

Record the exact submitted field size displayed by DraftKings, then run:

```bash
nfl-dfs capture-dk-standings ~/Downloads/contest-standings-12345.csv \
  --season 2026 \
  --week 1 \
  --contest-id 12345 \
  --contest-name "NFL Millionaire Maker" \
  --expected-entries 40000
```

Validation fails closed unless all of the following hold:

- the parsed entry count exactly equals `--expected-entries`;
- every entry has a unique DraftKings entry ID, positive rank, final score,
  complete legal Classic or Showdown slot shape, and no duplicate player;
- ranks and scores agree and any `TimeRemaining` values demonstrate settlement;
- every rank exactly reproduces competition ranking from all entry scores;
- the ownership block is present, bounded, sums to the expected roster mass,
  and reproduces the player counts derived from all captured lineups;
- lineup strings, ordered slot JSON, Classic/Showdown-aware duplicate keys,
  optional payout fields, and the complete source hash can all be retained.

If validation fails, do not edit the CSV. Redownload the full export or correct
the command metadata and validate again.

## 2. Apply the exact validated capture

Rerun the same command with `--apply`:

```bash
nfl-dfs capture-dk-standings ~/Downloads/contest-standings-12345.csv \
  --season 2026 \
  --week 1 \
  --contest-id 12345 \
  --contest-name "NFL Millionaire Maker" \
  --expected-entries 40000 \
  --confirm-settled \
  --confirm-full-field \
  --apply
```

The two confirmations are intentional. Use `--confirm-settled` only after the
DraftKings contest page shows the contest complete following scoring review.
Use `--confirm-full-field` only after checking that `--expected-entries` is the
submitted field size displayed by DraftKings, not a contest capacity or the
number of rows in an already-truncated file, and after checking the supplied
season, week and contest name against that page. The numeric contest ID must
also appear in the original download filename.

The apply order is intentional:

1. Archive the exact CSV create-only under
   `gs://$GCS_BUCKET/operator/dk-contest-standings/v1/season=.../week=.../contest_id=.../capture_id=.../source.csv`.
2. Append the complete entries and ownership rows through deterministic
   BigQuery load-job IDs derived from the source and contest identity.
3. Write a create-only JSON receipt beside the CSV only after both loads pass.

An ambiguous network retry cannot overwrite the source or append the same load
again. Every value persisted by a load is bound into its capture ID; the exact
same source buffer is parsed, hashed and archived. A byte-identical retry is
accepted, while a corrected final export receives a distinct immutable capture
ID. The output includes source/receipt URIs, SHA-256,
capture ID, counts, duplicate summary, and the two warehouse job IDs.

Before the first write, the command checks any existing destination's base
schema, `imported_at` partition and `season/week/contest_id` entry clustering.
An old autodetected or incompatible table fails before archival; apply the
targeted [`sql/raw/004_ownership.sql`](../sql/raw/004_ownership.sql) migration
and validate again. The command does not run a broad deployment script.

A corrected DK export is retained as a separate capture rather than overwriting
the first bytes. There is not yet a mutable/canonical “accepted capture” pointer;
if a correction occurs, record the authoritative capture ID in the weekly
handoff before downstream grading. Add such a pointer only when a real
correction demonstrates the need.

The browser download time defaults to the source file modification timestamp.
For a copied file, preserve the original observation explicitly with
`--captured-at 2026-09-15T10:30:00-05:00`. `GCP_PROJECT`, `GCS_BUCKET`, and
the BigQuery dataset variables provide the only machine-specific settings;
normal Google Application Default Credentials supply access. Never put a
DraftKings session cookie or credential in the repository, command, receipt,
or environment.

## 3. Verify durability

Keep the command's JSON output with weekly operations records. Confirm the
receipt URI exists, then let the existing `backup-tables` cadence snapshot
`contest_entries` and `contest_ownership`. The immutable raw CSV remains the
reparseable source of truth if a schema or parser improves later.

Applied rows are labeled `evidence_timing=post_settlement` only after explicit
confirmation and carry `captured_at`; the partitioning `imported_at` is set to
that same deterministic source-availability time so a retry cannot alter load
identity. These outcome-bearing standings must never be
joined into the same contest week's pre-lock features or lineup decisions.
The capture changes no model, selector, production policy, or scheduler.

The legacy `import-ownership` command remains available for controlled
historical work, but it does not enforce exact full-field size or create the
immutable archive. Use `capture-dk-standings` for all 2026 weekly captures.
