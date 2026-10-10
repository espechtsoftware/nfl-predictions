# How the 26 lineups become 53 entries, and whether the best ones go up front (2026-10-10, Saturday morning)

**For:** Erich, and the laptop who runs the deal. Written by the outside model after your question: "review the way we are
putting together the lineups into the entries ... are we getting the best lineups up front? Check how that sorting works."
Read for it: `enter_layout.py` (the head and spread layouts), `mix_shapes.py` (the cell interleave and the block positions),
`vet_book.py`, the Week-5 plan at its installed path (Rev6), the Sunday book rebuilt on Week 4, the Week-4 entered book, and the
dealing studies in both ledgers. Aggregates only; contest names are not reproduced.

## In one page

- **How a row gets its rank.** The 26 rows are solved in order and the rank is the build order. The cheap block takes fixed
  positions 2, 5, 9, 12, 15, 18, 22 and 25; the other 18 rows are dealt to the cells (A1 / A2 / B / C) by a weighted
  round-robin, where rank 1 goes to the cell with the largest quota because it carries the most entries. Within a cell, each
  solve is the best projection still allowed, so projection falls with rank. Vetting can sink a flagged row only within its
  cell's positions. Upload row = rank.
- **How a rank gets its entries (the head layout, Rev6).** Single-entry contests take distinct rows in plan order (rows 1–9, 10,
  15–17, 20–22); two-entry contests take rows 1–2 and 3–4, then 11–14; the Millionaire rows 18–19; the eight super-satellites
  are pinned to rows 1–26, one each; the FFWC qualifier is pinned to row 1. **Entries per row: 4, 3, 3, 3, then 2 on rows 5–22
  and 1 on rows 23–26.** The spread layout would give 3, 2, 2, 2, …: the two layouts are nearly the same on this plan. The deal
  is already almost flat; "which row goes up front" decides little weight.
- **"Best" is by projection only.** Row 1 is the highest-projected lineup the construction can make (147.7 on Week 4's
  slate); rows 3 and 4 are next (147.7, 146.5). **Those rows are also the most value-dense, the chalkiest and the only ones
  without a star:** 6–7 of their 8 skill players sit in the top value tenth, their Fantasy Points ownership sums are 166–181,
  they hold no $8,000+ player. The cheap-block rows are the opposite (ownership sums 63–103, 1–2 stars, 2–3 cheap players).
- **Rank does not predict the finish, and in Week 4 it predicted it backwards.** The Sunday construction on Week 4's slate:
  the correlation of rank with realized points was +0.08 and of projection with points −0.09; rows 1–2 averaged 118.8 points,
  rows 3–13 126.8, rows 14–26 123.1; row 1 scored 107.3 (fourth worst of 26); the best row was rank 22, a cheap-block row,
  at 177.9. The Week-4 entered book (the old construction, 110 rows): rows 1–2 carried 28 of 147 entries and were the worst
  segment (106.7 points against 119.7 for rows 61–110); the head weighting cost about 2.9 points per entry that week. The
  ledgers agree: every one-row ranking trailed random picks (study 32); the best-first fill order finished worse on average in
  Weeks 2–4 (42); deals by priority, winner score or touchdowns read no difference or worse (59, 48b, 52); all-distinct dealing
  no difference (24). In the real fields, a user's higher-projected half of his own lineups reached the top 1% at odds 2.19 /
  0.76 / 1.36 / 0.56 by week, and the regulars send median-projected lineups to their one-seat satellites.
- **The one thing the head rows do carry is duplication risk.** In the Millionaire, lineups with an ownership sum of 160 or
  more had an exact copy in the field 25–52% of the time in every week (130–160: 7–16%; under 100: 2–4%). In your contests
  the 160+ band was copied 4–8% of the time where the fields were large enough to read (W1 FFWC 4.1%, W3 8.2%). Row 1 sits at
  181 under Fantasy Points' ownership, and it is pinned into the FFWC qualifier and the first single-entry satellite; rows 3–4
  at 166–168 go to the next single-entry satellites and the two-entry contests. A copy in a one-seat contest halves or loses the
  seat. (The ownership PRODUCT, the usual duplication filter, badly understates this: it predicts 0.002 copies for row 1 in
  5,000 entries; the band data say 4–8%. The sum is the better predictor because optimizers converge on the same lineups.)

**What I would change, and what I would not.**
1. **Do not spend more on sort rules.** The weight is already flat (1–4 entries per row), rank carries no information at the
   top, and the ledger has six null reads on dealing.
2. **Keep the chalkiest rows out of the one-seat contests** (class E, your authority; a plan edit, a relayout check, no build
   change). Concretely: pin the FFWC qualifier to a row whose ownership sum is under about 130 rather than row 1, and let the
   first single-entry satellites take rows from the middle of the book rather than rows 1–4. The expected cost is zero if rank is
   uninformative (the evidence) and positive if the first solves are the most overrated (Week 4); the gain is the 4–8% copy
   risk removed from the seats that matter most to you. The spread layout does not do this on its own: pins are kept, and the
   single-entry group still starts at row 1.
3. **A standing Monday line: realized points by book rank** (and the ownership-sum band of each row), so the "front rows"
   question is answered weekly instead of from one week. The Week-4 numbers above are its first row.
4. **For Week 6, if you want the deal to follow a measurable rule:** the ownership-sum band, not the product, is the duplication
   predictor; one-seat contests get rows under 130, the Millionaire and the super-satellites take the rest. Study-list row 50
   (dupe-aware dealing) should be designed around the sum.

## 1. The mechanics, in detail

- **Cells and positions.** `mix_shapes.allocate` gives A1 / A2 / B / C 8 / 4 / 7 / 7 rows at 26 (the live block 5 / 3 / 5 / 5,
  the cheap block 3 / 1 / 2 / 2). `block_positions(26, 8)` puts the cheap block at ranks 2, 5, 9, 12, 15, 18, 22, 25.
  `interleave` assigns each remaining rank to the cell furthest below its quota of the entries dealt so far, weighting rank r by
  the plan's entries at that rank (`plan_weights`), so the heaviest ranks go to the largest cells first: on Week 4's slate the
  ranks read A1, A1 (block), B, C, B (block), A2, B, C (block), C, A1, A2, A2 (block), B, C, B (block), A1, B, C (block), C, A1,
  A2, A1 (block), B, C, A1 (block), A1.
- **Within a cell, the order is the solve order:** each solve maximises the sum of Fantasy Points projections (plus the cheap
  block's +2 in its rows) under the caps, the row rules, the ownership cap and the overlap limit with every earlier row, so later
  rows are more constrained and lower-projected. The live rows run from 147.7 down to about 137 by rank 26; the block rows
  128–135.
- **Vetting** (`vet_book.py`) sorts flagged rows behind clean ones **within each cell's own positions**, so the entered cell mix
  is unchanged. **`ENTER_ORDER=greedy`** means the book's order is the upload order; the alternative `fewest-low` (fewest
  predicted low-owned players first, the head rows protected) exists and is off.
- **The head layout** (`_head_ranks`): a contest of one or two entries is "all head": the first four such contests of a size
  take rows 1–4 in blocks of their size, the rest take the next unique rows in plan order; larger contests take rows 1–2 (1–4 if
  over five entries) and then unique rows snake-fashion; pins override. **Rev6 as installed:** 29 contests, 53 entries, 26 rows;
  18 single-entry contests, 6 two-entry, 1 three-entry, 4 five-entry; 8 pinned (the super-satellites on rows 1–26, the FFWC
  qualifier on row 1).
- **Who sits where** (by plan position): the first four single-entry satellites rows 1–4; the next five rows 5–9; the first
  two-entry contest rows 1–2 and the next 3–4 (then 11–12, 13–14); the second FFWC contest row 10; three more single-entry
  contests rows 15–17 and three rows 20–22; the Millionaire rows 18–19; the super-satellites one row each, 1–26.

## 2. What the rows look like, by rank (the Sunday construction on Week 4's slate)

| Rank | Cell | Entries | FP projection | Top-value players (of 8) | $8k+ | Sub-$4k | FP ownership sum | Salary spread | Realized W4 points |
|---|---|---|---|---|---|---|---|---|---|
| 1 | A1 | 4 | 147.7 | 6 | 0 | 1 | **181** | 1,230 | **107.3** |
| 2 | A1, cheap block | 3 | 134.5 | 3 | 1 | 2 | 96 | 1,591 | 130.3 |
| 3 | B | 3 | 147.7 | 7 | 0 | 1 | 168 | 1,394 | 126.2 |
| 4 | C | 3 | 146.5 | 7 | 0 | 0 | 166 | 970 | 137.1 |
| 5 | B, cheap block | 2 | 132.9 | 1 | 2 | 3 | 103 | 1,915 | 111.8 |
| 6 | A2 | 2 | 147.0 | 6 | 1 | 1 | 164 | 1,558 | 135.0 |
| … | | | | | | | | | |
| 22 | A1, cheap block | 2 | 129.3 | 1 | 1 | 3 | 69 | 1,902 | **177.9** |
| 25 | A1, cheap block | 1 | 128.0 | 0 | 2 | 3 | 78 | 2,096 | 112.2 |

Correlations across the 26 rows: rank with projection −0.42 (by construction), rank with value density −0.22, rank with the
ownership sum −0.36, rank with realized points +0.08. The 8 cheap-block rows (16 of 53 entries) averaged 128 realized points
against 123 for the 18 live rows; one week.

## 3. Duplication by ownership-sum band (realized ownership, Weeks 1–4)

| Band | Millionaire: share with an exact copy, W1 / W2 / W3 / W4 | Millionaire top-1% rate, W1 / W2 / W3 / W4 | Your contests: copy share where readable |
|---|---|---|---|
| under 100 | 4% / 2% / 2% / 2% | 0.5% / 0.6% / 0.3% / 1.4% | 0.2% (W1), 0.3% (W3) |
| 100–130 | 6% / 3% / 3% / 3% | 1.1% / 1.1% / 1.0% / 1.1% | 0.8% / 0.5% |
| 130–160 | 16% / 8% / 7% / 11% | 1.8% / 1.2% / 1.5% / 0.4% | 8.1% / 1.1% |
| 160+ | **52% / 25% / 28% / 48%** | 1.0% / 1.7% / 1.8% / 0.0% | 4.1% / 8.2% |

Chalkier rows reached the top 1% more often in Weeks 1–3 and never in Week 4; above 160 they are copied a quarter to a half of
the time in the Millionaire. The product of the nine ownerships, the usual duplication filter, predicts 0.002 copies for row 1 in
a 5,000-entry field and 0.05 in 170,000: it assumes the choices are independent, and they are not.

## 4. Limits

One week of realized points for the Sunday construction (Week 4's slate; the book was never entered) and one entered book; the
harness's dealing studies are the broader evidence and they read "no difference", which is also what "rank is uninformative"
predicts. Ownership sums for the fields are realized; the book's are Fantasy Points' projections. The copy shares in your
contests rest on the two fields large enough to read.

## 5. Sources

`src/nfl_dfs/inference/enter_layout.py`, `src/nfl_dfs/inference/mix_shapes.py` (`allocate`, `interleave`, `plan_weights`,
`block_positions`), `scripts/vet_book.py`; the installed Week-5 plan (Rev6) read through `enter_layout.assign_ranks` and
`plan_weights`; `~/rehearsals/minprojcheck-live-20261010T102003Z/LIVE` (the Sunday construction on Week 4) with
`~/moneygate/inputs/own/w4_ownership_fp.csv` and the Week-4 Millionaire's realized points (`nfl_raw.contest_ownership`); the
Week-4 entered book under `~/moneygate/inputs/entered/`; `reports/2026-10-10-winner-patterns/winner_patterns2.*` (the band
tables); the lab ledger rows for studies 24, 32, 42, 48b, 52, 59; `reports/2026-10-07-how-professionals-sort-lineups.md`.
