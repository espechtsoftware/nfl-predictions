# Preregistration: study 59, priority-first dealing, in the harness, with a 2022 go / no-go (DRAFT 2026-10-07)

**Status: DRAFT 2026-10-07**, committed by the reviewer BEFORE study 56's read. The score favours QB+2 rows, and study
56 measures fewer QB+1 rows on the same slates, so its read would bear on this design.
- The code, the smoke, the binding census, the bank scan and the freeze follow.
- The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The operator, 10-07:** "Let's try to do this one this week as it seems more promising." The proposal is the outside
  reviewer's class-E change (`29e6632b`, `0b11cc89`): the book does not change, only which contest each row goes to. His
  priority contests ($4,444 / $555 / $333 / FFWC satellites) read the rows that look most like what wins there.
- **The laptop's frozen harm screen** (production `reports/2026-10-07-priority-deal-harm-screen.md`, `27a1957b`) is the
  money path's in-sample STOP rule on the W2–4 real fields. It names this harness study as the decision-bearing test.
- **The outside reviewer's evidence** (the W1–4 real priority fields, odds of a top-5% finish within user): QB with one
  teammate vs two 0.78; a bring-back 1.51; two or more sub-$4,000 players 1.93. All three are associations with realized
  results.
- **The counter-evidence:**
  - study 48b's whole-book re-deal by the winner-likeness score: NO DIFFERENCE (+0.008), at 0.899× the expected seats
    ("it breaks the shape interleave");
  - study 52's touchdown deal: NOT SUPPORTED (−0.022): "the book's own order beats both re-sorts".
- **The prior, stated before any outcome:** a re-deal moves wins between contests and does not create them. A small or
  null effect is the likeliest reading.

## 2. Arms (`experiments/s59_priority_deal.py`)
**The books:** on each slate-bank, study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted). Two books are
built, exactly as studies 53 and 56 build them:
- **LIVE:** his live Week-5 book and production's 15 spares (study 48d's 41 rows).
- **LIVE_CB:** LIVE plus Week 5's live cheap +2 block (study 53's CHEAP2_BLOCK8, `s53_cheap_pref.py` `f3f9d735…`):
  the 8 block rows at 0-based positions 1, 4, 8, 11, 14, 17, 21, 24.

**The score of a row** is computed pre-lock from the row itself, by the frozen definitions of the harm screen and
production's `priority_field_monitor.py`:
- **+2** if the QB has 2 or more teammates: players on his team other than the QB and the DST, FLEX included;
- **+1** for a bring-back: 1 or more non-DST players on the QB's opponent;
- **+1** if 2 or more non-DST players have a DK salary under 4,000.

When production's `--priority-order` lands, its score and order function is copied verbatim into the lab (text sha
asserted, as study 54's `pmo_plain.py`). The smoke checks the lab order equals production's on the same rows.

**The deals** (the book's 26 rows re-ordered; the spares untouched; every deal is then the head layout on Rev3 with the
small-contest overlap limit 5):

| arm | the book | the order |
|---|---|---|
| **CB** (reference) | LIVE_CB | the book's own |
| **CB_PRI** (THE DECISION) | LIVE_CB | the block keeps its 8 positions; the other 18 rows sorted among their own 18 positions by score, highest first, ties in book order (the reviewer's block rule, c9028505) |
| **LIVE** (reference for the exploratory) | LIVE | the book's own |
| **PRI_ALL** (exploratory) | LIVE | all 26 rows sorted by score, ties in book order |

On Rev3 under head, the $4,444 / $555 / $333 / FFWC contests read ranks 1–19, the Midseason Warm Up satellites (also
priority, the operator 10-07) 20–22, and the $20 supersats 23–26.

## 3. Endpoint and rule (the reader `scripts/s59_report.py`)
- **THE READ: 2023–24** (36 slates).
  - CB_PRI − CB, P(≥ 1 big seat) per slate on the calibrated field v2.
  - Two-sided 0.95. B 20,000, seed 20261108; slates resampled within season.
  - Banks 1587–1592. The unique-blob scan precedes the freeze.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdict:** DEAD LEVER (dealt identically on > 80% of slate-banks) / WORSE / PASS (lower > 0, at most one season mean
  < 0, both guards) / FAIL (guard) / NO DIFFERENCE.
- **THE GO / NO-GO: 2022** (17 k1 slates with real Millionaire ownership, the same banks): CONTRADICTED if the point
  estimate is < 0.
- **STUDY:** SUPPORTED only on a PASS that is not contradicted.
- **THE TRIAL RULE** (adoption track v2; study 51's frozen rule): NOT ENTERED if WORSE, CONTRADICTED on 2022, or the
  read's expected big seats ratio < 0.80; MOOT on a dead lever; otherwise ENTERABLE, his decision. The Week-5 bar is his;
  the laptop's in-sample harm screen runs beside it.
- **EXPLORATORY** (two-sided 0.95):
  - PRI_ALL − LIVE (the whole-book form, no block), on the read and on 2022;
  - P(≥ 1 big seat) over his PRIORITY contests only: the plan's big single-prize contests whose prize names a $4,444, a
    $555 or a $333 ticket, an FFWC $490 qualifier or a Midseason Warm Up ticket. The last was added to the DRAFT before
    study 56's read, on the operator's 10-07 word that the Warm Up sats are big prizes "under the 4444 and before 555"
    (`6e287447`). That makes 20 of Rev3's 29 contests. The other 9 are the Millionaire (multi-tier), the seven $20 supersats and the
    $125 FFWC satellite. CB_PRI − CB, on the
    read and on 2022;
  - the decision on l02;
  - the priority entries' QB+1, bring-back and 2+ sub-$4,000 shares under each deal.

## 4. What a verdict can do
- **SUPPORTED or ENTERABLE:** the deal is a candidate for his decision, Week 5 (after the laptop's harm screen and
  Friday's armed rehearsal) or Week 6.
- **Study 38's amendment 6k** (proposed) makes the paper arms follow `--priority-order` and adds the book-order paper arm.
- **Otherwise:** the book keeps its own order.

## 5. Production parity
- The books are studies 53's and 48d's.
- The order mirrors production's `--priority-order` (copied verbatim when it lands).
- The deal is production's head layout.

## 6. Smoke and integrity
(Added at the freeze: the smoke, including the order's parity with production, the binding census, the bank scan and
the code shas.)

## 7. Order
1. This DRAFT, before study 56's read.
2. The code, the smoke, then the binding census.
3. The freeze.
4. The laptop's ack and bank scan.
5. The scored run.
6. The confirmatory census, committed before the read.
7. The read.
8. The laptop's re-run.
9. The LEDGER row and an Addendum.
