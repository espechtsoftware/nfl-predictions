# Existing D800 archive: structural readiness for an outcome-disabled pilot

September 18, 2026. Read-only structural inspection following synthetic E0. No NFL result values read.

The previously identified prelock D800 archive contains 800 candidate rows, 397 frame rows and two
float32 score arrays, each shaped (397, 10000). Parquet object hashes, GCS generations/checksums,
full schemas and NPY headers are recorded in `reviews/evidence/2026-09-18-e0-archive-schema.json`.
The inspection script is beside it. Parquet bytes were downloaded into memory solely to read structural
metadata; no row values were decoded. NPY reads were limited to the first 512 bytes for the headers.
Book JSON/CSV, exposure ledger and receipt payloads were not opened.

Important: `frame.parquet` includes an `actual` column. Future reads must select an explicit allowlist
of prelock input columns and never decode `actual`. Candidate columns include selection/audit summary
estimates; those must likewise be excluded from the initial identity/roster census. Existing column names
such as `aud_mean` do not establish an independent evaluation bank.

## What this supports

A real fixed-pool mechanics pilot appears structurally feasible without regenerating candidates:
800 delivered rows and dimensionally compatible player matrices are retained. This is stronger than a
filename-only existence check. It is not proof of unique/legal candidates, correct player ordering,
prelock feature provenance, exact replay, or independence of the archived banks.

## Remaining prerequisites, in order

1. Read only candidate identity/roster columns and frame identity columns under a frozen allowlist.
   Establish unique candidate counts, legal roster shape, player mapping and array-row order from writer
   code plus retained identities. Matching row counts alone do not establish ordering.
2. Inspect the archive writer and an allowlisted receipt subset for generating code/config and source
   timestamps. Never assume incumbent versus corrected_hsim means independent random banks; these names
   imply different laws, which is a different contrast from same-law independent evaluation.
3. Determine a reproducible independent-audit construction, with a small cost cap, before selection.
   A held-out split of an old score bank is at most a conditional pilot: candidates may have been generated
   using those same worlds, and the split does not remove generation dependence retrospectively.
4. Freeze a separate pilot protocol for precision and selection stability under the stated model law.
   No realized-score grading, money-path reordering, or full historical reconstruction follows automatically.

The synthetic experiment is complete; this real-pool step remains a readiness inventory, not a launched
performance study. The September 10 archive concerns one already-observed Week-1 slate and an older live
revision; any later results must be labelled retrospective development.
