# Preregistration: study 35, QB diversity on the winners' mix (a per-QB cap at the regulars' level) (FROZEN 2026-10-06)

**Status: FROZEN 2026-10-06** by the reviewer, after the calibration census and the smoke (§5), before any scored bank. The laptop acks the binding census and re-runs the frozen reader. Production's matching lever is built and OFF (`production/qb-cap-20261006` @ `b5514472`; parity with this harness confirmed: the ban at count ≥ cap, one running state across all cells, spares counted).

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

## 5. Calibration, smoke and integrity
- **The calibration census** (bank 1406, outcome-blind; `results/s35/CALIB_s35.txt`).
  - Uncapped MIXT: the dealt entries' most-used QB is at 0.477, with 4.1 distinct QBs (effective number 2.8).

    | row cap (of 26) | most-used QB | distinct QBs | projection given up per lineup |
    |---|---|---|---|
    | 4 | 0.187 | 7.9 | −0.50 |
    | **5** | **0.223** | **6.7** | **−0.31** |
    | 6 | 0.261 | 5.9 | −0.22 |
    | 7 | 0.287 | 5.5 | −0.18 |
    | **8** | **0.323** | **5.3** | **−0.12** |
    | 9 | 0.363 | 4.9 | −0.10 |
    | 10 | 0.392 | 4.8 | −0.06 |

  - At every level: no passes to A1, no short books, and the cells stay within 3 points of their quotas.
  - **A = 5 rows**, the loosest at or under 0.25. **B = 8 rows**, the loosest at or under 0.35.
- **The binding census at the frozen caps** (1406, 36/36, code `25991ee`; `CENSUS_s35_binding.txt` `79f502b7…`, raw
  `621354ba…`): it reproduces the calibration exactly. Neither capped arm is identical to MIXT on any slate-bank.
- **The smoke** (2023 W1, 1406, the full path): the census and reader exited 0; the reader printed its 2 headers and
  REFUSED mechanics-only rows. No outcome line was read.
- **Code:** nfl2 `production/s35-qb-cap-20261006` @ `a90dc3a`:
  - `experiments/s35_qb_cap.py`, sha256 `afbb85d26063d135423c5f92b3a107749d45c0ee04bfee6631cde0b620b9d82a` (the caps are
    frozen in code, with no environment override);
  - `scripts/s35_drive.py`, `2d0f49578fd5b0c611fcb699497f3d9d86fe305a1e0425159c83536532d19683`;
  - **`scripts/s35_report.py` (the reader), sha256 `bf55070e56439a5f4a6bba23198ead737d6f05e989737674b6374c347bbbf69a`**;
  - `scripts/s35_census.py`, `ecc1354be7e435c60a2c571b9dbce91d93ca5445db0846ccbe2bd4459b5ed7ce`;
  - `tests/test_s35_qb_cap.py`, `ea573a8575e78fd6c97d156f0807c7c5334d5e06c841b5b2f327994785b61a5b` (5 tests).
- **Production `enter_layout`:** `3cb051ac…`. **Banks:** 1455–1460 (scanned clean by the laptop). **Seed:** 20261017.
- **Order:**
  1. this freeze;
  2. the laptop's ack;
  3. the scored run;
  4. the confirmatory census;
  5. the read;
  6. the laptop's re-run;
  7. the LEDGER row and an Addendum.
