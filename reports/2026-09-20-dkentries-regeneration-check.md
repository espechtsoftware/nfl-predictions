# DKEntries regeneration check

I compared the downloaded Windows export
`/mnt/c/Users/erich/Downloads/DKEntries.csv` with the post-Tua regenerated
promoted book in `regen-1048/regen-promoted-book.csv`. The comparison canonicalizes
each lineup as a set of nine internal player IDs, so contest ordering and
DraftKings RB/WR slot permutations do not create false differences.

## Findings

* The export contains 97 entry rows and 677 total data rows, the remainder
  being DraftKings's player reference table.
* All 97 entry IDs are unique.
* The 97-lineup multisets are exactly equal to the regenerated promoted book;
  there are zero missing or extra lineups.
* Tua Tagovailoa appears in zero exported player cells.
* Rashod Bateman appears once, in the expected $40K Nickel entry.
* Physical CSV line 97 is entry `5256608624`, and its lineup maps to promoted
  book row 30. This row-order difference is expected because the contest export
  is grouped by contest while the promoted upload is rank ordered.

The current export is therefore the regenerated book, not the stale pre-Tua
book. No upload correction is needed from this check.

Evidence hashes: downloaded export SHA-256
`ddbd9af560de5e215b765532403e83124c1f9d3d29598dbf33bfff16b0a2c346`; promoted
book SHA-256 `77eaf7970c0ca19ec27ccefc62301fec1ccef58c8fffc9b76e7c6c7fb676b96e`.
The comparison used only archived identity/name columns and the two CSV files;
no current-week scores or settlement data were opened.
