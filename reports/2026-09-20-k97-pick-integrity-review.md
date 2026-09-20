# K97 pick-integrity review

I audited the archived preview book, the fresh-status final book, and the
promoted upload book from the Week-2 receipt package. The review used only the
CSV IDs, the archived frame's identity/legality/status/depth columns, the
replacement/vetting receipts, and the Week-2 QB-classifier artifacts. The
frame's realized `actual` column was not read.

All three books contain 97 rows with the expected nine slots. Every row has
nine distinct player IDs, every ID resolves to the archived frame, every slot
has a legal position, every salary is between 49,000 and 50,000, every lineup
uses at least two games, and no team exceeds the eight-player limit. There
are no duplicate rows within a book. The preview and fresh final books have
the same 97-lineup set; the promoted book has the same set again and changes
only the order, moving source rank 7 to row 1.

No book row contains a player whose archived DK status is O/OUT/IR, and every
book player's archived roster status is ACT. The final-vetting receipt also
binds zero unavailable-by-membership players and zero hard flags. The 39
material/soft vetting rows are expected questionable/doubtful cases: chiefly
Ladd McConkey and Chris Olave, plus primary QBs Joe Burrow and Tua Tagovailoa.
Those are not backup-QB flags; the protocol intentionally leaves Q/D players
in until an official OUT/IR/inactives update.

## Backup-QB check

The previous failure mode does **not** appear in this book. Every one of the
97 rows has a QB, and the final-vetting flags contain no
`backup_qb:behind-healthy-primary`, `backup_qb:ambiguous`, or unknown-backup
flag. The receipt's exclusion set contains the known backup QBs that were
gated out, and none of those names is in the promoted book.

Four rows deserve an explicit visual check because their depth-chart rank is
2: Carson Wentz appears at rows 18, 20, and 94, and Drew Lock at row 52. The
Week-2 QB classifier labels both as `role=primary` because their teams have no
healthy depth-1 QB row in the captured frame; the corresponding depth-3
players are gated. Tua Tagovailoa also has depth rank 2, but his `depth_rank_delta=-1`
and final-vetter flag is `qb:primary/doubtful`, so he is not classified as a
backup. These are not accidental backups under the current classifier. The
receipt package should archive the exact `qb-flags.csv` body in future weeks,
rather than only its hash/path, so this role decision can be independently
reproduced without relying on a local classifier artifact.

The 15:30Z late-inactives sweep remains the authority for any new official
OUT/IR status. If Wentz, Lock, Tua, Burrow, or any other player becomes
officially unavailable, the reviewed sequence is a fresh status replacement,
then promotion/relayout and upload verification. This review found no current
row-level integrity failure and made no production change.

## Evidence

The audited receipt package is shared handoff commit `e35df552` under
`handoffs/receipts/2026-09-20-sunday-live-k97/` and the pre-status preview is
under `handoffs/receipts/2026-09-20-install-and-d12800/`. The local audit used
the verified D12800 archive manifest and an explicit frame-column allowlist;
all package SHA-256 values had already passed the independent receipt check.
