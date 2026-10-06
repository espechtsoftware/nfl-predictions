# Preregistration: study 35, QB diversity on the winners' mix (a per-QB cap at the regulars' level) (DRAFT 2026-10-06)

**Status: DRAFT 2026-10-06.** The reviewer drafts it and freezes it after the calibration census and the smoke. The
laptop comments, acks the binding census and re-runs the frozen reader.

## 1. Why
- **The operator (10-06):** "I'm more interested in the winner's mix than our way we've been doing it. However, it
  sounds like we're not getting the diversity of quarterbacks that we should be getting. Please look further into that.
  I suspect that there's something going on with the winners where they look at the value of quarterbacks. And
  sometimes find a cheaper quarterback that has a good matchup."
- **What the data say** (2026 Weeks 1–4, the regulars' per-player panel; descriptive; aggregates only):
  - **No cheap-QB habit.** Share-weighted QB salary: regulars $5,878, the field $5,961, ours $5,794. QBs under $6,000:
    56% / 53% / 69%. Their within-week tilt against QB salary is +0.02 (Spearman), and against value +0.12 (slight).
  - **No good-matchup habit.** They lean slightly AWAY from QBs facing defences that look soft on 2026-to-date numbers
    (−0.22: the small-sample distrust) and slightly toward high totals (+0.09).
  - **Projections:** in Week 4 they leaned toward the QBs FP rated above our model (+0.30; ours −0.22). FP picks the
    lineups from Week 5.
  - **The real gap is CONCENTRATION, and it is new.**
    - Our Weeks 1–3 QB spread matched the field (effective number of QBs 16 / 16 / 11).
    - In Week 4 one QB took 60% of our entries (effective number 2.2).
    - Both Week-5 books do it too: 51% / 59% (the pre-mortem).
    - Each regular's most-used QB is in about 23% of his entries.
    - The mechanics: a 26-row book, the player cap (13 rows) applying to QBs too, and the head layout weighting the
      top rows.
- **The question:** does capping any one QB at about the regulars' level raise his chance of a big win on the winners'
  mix?
- **The prior:**
  - Study 24's per-GAME QB cap (G25S) cost −1.8 points and failed his 20% tolerance.
  - A per-QB cap is looser: two QBs of one game can still reach 50%.
  - Study 1b's player cap cost finish.
  - The result can go either way. Guard 1 (finish) is reported prominently.

## 2. Arms (study 31's harness: 36 slates, Rev3, K 26, caps 13 / 6, head, `enter_layout` `3cb051ac…`, the 0.20 term)
- **MIXT** (reference): the winners' mix as he would enter it.
- **MIXT_QA** (DECISION): the same, with a per-QB ROW cap A. A QB is banned once in A rows, as the DST cap works.
- **MIXT_QB** (exploratory): a milder cap B.
- The caps come from an outcome-blind calibration census on bank 1406 over the row-cap pairs (A, B) = (4, 7), (5, 8),
  (6, 9), (7, 10).
  - A is the loosest cap whose dealt entries' most-used QB is at most 25% on average (the regulars' level).
  - B is the loosest with at most 35%.
  - If no tested A reaches 25%, the grid extends downward before the freeze.
- Study 28's `mix_book` (production's `mix_rows` mechanics) runs unchanged; the capped builder is swapped in for the
  call.

## 3. Endpoint and rule (study 18b's)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIXT_QA − MIXT.
  - Six fresh banks 1455–1460 (scanned by the laptop); B 20,000, seed 20261017; two-sided 0.95.
- **Guards:**
  - guard 1, mean entry pct, one-sided lower > −0.015;
  - guard 2, expected big seats ratio ≥ 0.80 (his tolerance).
- **Verdicts:**
  - DEAD LEVER: identical on > 80% of slate-banks;
  - WORSE;
  - PASS: lower > 0, at most one negative season, guards hold;
  - FAIL (guard);
  - NO DIFFERENCE.
- **EXPLORATORY:** MIXT_QB − MIXT; per arm, the dealt entries' QB diversity (top share, distinct, effective number),
  QB salary and dealt mean projection.

## 4. What a verdict can do (to be frozen)
- **PASS:** a per-QB cap becomes a candidate class-S lever on the live MIXT build.
  - This is new production code mirroring the DST cap: `qb_cap` in `mix_rows` / `pmo_rows`, off by default, with a
    test that it is inert when off.
  - It is offered to him with its evidence and armed after a rehearsal.
- **NO DIFFERENCE:** QB concentration is a feature of the book without a measured cost or benefit. He may still choose
  the cap as a preference (the bust-risk view), told plainly.
- **WORSE or FAIL:** no cap. The concentration is the price of the projection-driven book, as for studies 24 and 1b.

## 5. Integrity (filled at the freeze)
Code (nfl2 `production/s35-qb-cap-20261006`), the reader sha, the caps and the calibration census, the binding census.
Order:
1. this draft;
2. the laptop's comments;
3. the calibration census;
4. the smoke;
5. the freeze;
6. the binding census;
7. the laptop's ack;
8. the scored run;
9. the confirmatory census;
10. the read;
11. the laptop's re-run;
12. the LEDGER row and an Addendum.
