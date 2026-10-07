# Preregistration: study 59, priority-first dealing, in the harness, with a 2022 go / no-go (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding (support) census (§6), before any scored
bank. A WEEK-6 READ.
- The DRAFT (`6d8967f2`) and its plan updates through Rev6 (`9ad61eeb`, `16cb6fc0`, `597e00d4`, `3ca3d8c6`) were all
  committed before study 56's read.
- **It is no longer decision-bearing for Week 5.** The laptop's frozen in-sample harm screen (`27a1957b`, amendment 1
  `7ee09fe1`) said NOT ENTERED for the sort (lower in 2 of 3 weeks, seats ratio 0.587), so `--priority-order` is not
  armed for Week 5. This study reads the question out of sample for Week 6.
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

**THE PLAN: Rev6, his final order** (added to the DRAFT before study 56's read; it replaces Rev4 and Rev5, neither of
which was ever installed).
- **The operator, 10-07, in three steps:**
  - "I forgot about the midseason warm ups. Those are big prizes. Can we move that up to under the 4444 and before 555."
  - Then: "I'm sorry - I didn't even realize what the showdown Mega is. That should be under the $333. …"
  - Finally: "I apologize again. I didn't understand what the prizes were in some of these contests. Let's change the order
    for the final time to: 4444 (all of them including the showdown - which seems the same as the others anyway) / 555 /
    WFFC / 333 / Millionaire / Midseason warmup / Everything else including milly qualifiers".
- **Rev6** holds Rev3's 29 contests and fields, re-ordered. Under head:
  - $4,444 1–3 (the Showdown at 3);
  - $555 singles 4–9, the 2x 1–2;
  - WFFC $490 10;
  - $333 2-entry 3–4, 11–12, 13–14, singles 15–17;
  - the Millionaire 18–19;
  - Warm Up 20–22;
  - the $20 supersats alone on 23–26.
- Rev6's per-rank entry weights equal Rev3's, so the books and their built order are unchanged. Only the contest-to-rank
  map moves.
- **Every arm is dealt on Rev6's map:** `~/s24-panel/plan-week5-rev6-s24.json`, sha256 `ac10ddf6…`.
  - It was built from Rev3 by re-ordering its byte-equal contest dicts, in Rev3's format.
  - Its head ranks equal the laptop's for all 29 contests.
  - It mirrors the live installed contests.json (sha `5f8352ee…`), a different file format: the check is equivalence.
- **Every big contest (21) is above "everything else" in his order,** covering ranks 1–22. The priority-only endpoint
  would equal the primary, so it is dropped.
- The Rev3 → Rev6 move itself is his plan decision. The laptop's in-sample screen covers it.

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
- **The smoke** (`~/s59-panel/smoke.sh`; code as committed at lab `b1eca48`, clean; bank 1406; Rev6; 2024 W10 SCORED,
  2022 W6 MECHANICS ONLY):
  - LIVE's rows equal study 53's LIVE, and LIVE_CB's rows equal its CHEAP2_BLOCK8, on both slates. The books do not
    depend on the deal.
  - **Production parity:** production's `priority_deal.priority_order` (copied verbatim, `fa47594d…`) gives the same order
    as the reviewer's independent reference on the real rows, with the block (CB_PRI) and without it (PRI_ALL). A test
    also checks 200 random books.
  - The block rows keep their positions, and the spares are in place (asserted).
  - **Disclosed:** the reader ran on a FAKE file (the 2024 row relabelled 2022 as well). Its section lines, truncated at
    14 characters, showed "not" in the STUDY line for that single 2024 W10 slate-bank of bank 1406, a mechanics-test
    slate-bank.
  - The log: lab `results/s59/SMOKE_s59.log`.
- **The binding (support) census** (outcome-blind; bank 1406; 53/53; code `b1eca48` clean;
  `results/s59/CENSUS_s59_binding.txt` `c5c54b09…`, raw `9e36900d…`; lab `e7dae3d`):

  | 2023–24 | CB | CB_PRI | LIVE | PRI_ALL |
  |---|---|---|---|---|
  | score per row at ranks 1–22 / 23–26 | 2.097 / 2.340 | 2.312 / 1.160 | 1.846 / 2.292 | 2.231 / 0.174 |
  | score per dealt entry | 2.157 | 2.342 | 1.912 | 2.200 |
  | rows moved (of 26) | 0 | 16.6 | 0 | 24.6 |

  - **2022 is alike:** CB_PRI 2.267 / 1.294 against CB 2.067 / 2.397.
  - In its own order the book holds its highest-scoring rows at ranks 23–26, the $20 supersats. The sort moves them into
    the priority span.
  - Neither re-deal is dealt identically to its reference on any slate-bank.
- **Banks:** 1587–1592 and seed 20261108. The reviewer's unique-blob scan of both repositories (8,057 lab and 17,723
  production blobs up to 5 MB) found them only in study 59's own records (the DRAFTs, `s59_drive.py`, `s59_report.py`).
  No result file exists on disk.
- **Code:** nfl2 `production/s59-priority-deal-20261007` @ `b1eca48` (the census at `e7dae3d`):
  - `experiments/s59_priority_deal.py`, sha256 `6a0b65e24fdf859a22c06a10cfb85e6ea2949399acbfdb3fe6ac16db3eafb888`;
  - `experiments/priority_deal.py` (production's, verbatim), `fa47594dc9113bd74ca699ad6ea7babbc9cb6b320b37dcbc349095cf4dbef426`;
  - `scripts/s59_drive.py`, `7f74a2f97c69c71986653e6e703ed2cc8977834b3239d5a9193493d1c61e0167`;
  - **`scripts/s59_report.py` (the reader), sha256 `c6b70771acadd5a35880d85f4eaa86cd626b55451bc043b22b203964e78f31ad`**;
  - `scripts/s59_census.py`, `881735d00e6f0894e7cb325d976644da11339479034c28ac52572dbf415dd429`;
  - `tests/test_s59_priority_deal.py`, `b586bbe462d177ea2717446f8d74eb108e3f534be7452d577fc2199a975aace7` (7 tests);
  - unchanged, sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`, production's
    `enter_layout.py` `3cb051ac…`;
  - the plan: `plan-week5-rev6-s24.json` `ac10ddf6…`.

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
