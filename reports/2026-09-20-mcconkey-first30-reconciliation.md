# McConkey first-30 reconciliation

## Finding

The current post-Tua promoted book does contain McConkey in two of its first
30 delivered rows. The exact regenerated file has 28 McConkey lineups in the
97-row book, at promoted positions **27 and 28**. The uploaded Windows
`DKEntries.csv` contains the same 28 lineups after canonicalizing the nine
player cells in each row. This is an internal receipt inconsistency, not an
upload identity mismatch.

## Evidence

The comparison used only the archived identity frame (`id`, `dk_player_id`,
and `display_name`) and the two CSV files. It did not read current-week
scores, settlement fields, or provider data.

* `regen-1048/regen-promoted-book.csv`: 97 rows, 28 McConkey rows, with
  McConkey at positions 27 and 28 of the first 30.
* `regen-1048/regen-vetting_final.json` and `regen-promotion.json`: both flag
  positions 27 and 28 for `DK:Q` and `report:Questionable`.
* `/mnt/c/Users/erich/Downloads/DKEntries.csv`: 97 entry rows, 28 McConkey
  rows; its canonical lineup multiset is exactly equal to the regenerated
  promoted book.
* The two affected promoted rows are both in the `$40K Nickel [5 Entry Max]`
  block: entry `5256597536` (promoted row 27) and entry `5256608601`
  (promoted row 28). No Millionaire or $19 satellite entry contains him.
* The earlier `sunday-promoted-book.csv` contained 26 McConkey rows, but it
  also put him at positions 27 and 28. The later Tua refresh changed the
  total to 28 without changing those first-30 positions.

The exact current contest counts are 13 entries in the $0.25 supersatellite,
13 in the $1 supersatellite, and 2 in the $5 Nickel. The first 26 delivered
rows are clear; the statement in the workstation receipt that the first 30
were clear is therefore stale or a wording error. The contemporaneous
`sunday-TODAY-30-LATEST.md` and final-vetter receipt already show flags at
positions 27 and 28.

## Operational interpretation

The regenerated book and the actual upload agree, and the Millionaire row is
still unaffected. The correction matters for exposure reporting: the live
book has 28/97 (28.9%) McConkey exposure and 2/30 exposure in the leading
delivered block, rather than 26/97 with no first-30 exposure. It does not by
itself establish that McConkey should be swapped. The existing protocol still
waits for official OUT/IR/inactives information and uses the tested unlocked
cell swap after an early-game lock.

The outcome-blind exposure diagnostic is consequently interpreted with
`first30_exposure=2`. It reports that McConkey also contributes unique
simulated tail worlds, so a blanket exposure cap would require a measured
portfolio tradeoff rather than an automatic removal.

Evidence hashes: regenerated promoted book
`77eaf7970c0ca19ec27ccefc62301fec1ccef58c8fffc9b76e7c6c7fb676b96e`; current
DKEntries export
`ddbd9af560de5e215b765532403e83124c1f9d3d29598dbf33bfff16b0a2c346`.
