# Preregistration: study 117, two stars per lineup — at least two RB / WR / TE priced $8,000+ — on his armed book, in the harness (DRAFT 2026-10-10, for Week 6)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the lab reviewer's
(10-10, about 14:00). The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and reproduces.
**A pick goes to study 117b** (the fresh-draw check), whose preregistration is committed before this study's READ.
- **Timing — the operator's decision (10-10, via the laptop):** first "Test it now for this week", then, told that Week 5's pool
  has only four $8,000+ RB / WR (no TE) — 36 star slots under the 0.35 cap against the 52 that two stars on all 26 rows
  needs — **"Paper this week, test for W6 (Recommended)"**. This week STAR2_8 (and STAR2 where it fits) go on paper in study 38
  (the lab reviewer's amendment); **this study runs for Week 6** (after Sunday's canary, or Monday).
- **Banks and seed (the laptop's reservation; the full-set check: CLEAN):** **4340–4351** (set A 4340–4345, set B 4346–4351;
  sims bases 4390–4401, fields 5040–5051); the reader's bootstrap seed **20261165**.

## 1. Why
- **His request** (the laptop's session, 10-10): a two-stars rule, tested before use.
- **The prior, stated first: NO DIFFERENCE, leaning negative.** From the lab LEDGER:
  - **Study 92, STAR1** (at least one $8,000+ RB / WR / TE on every book row, the armed version before FAVHI): −0.05760
    [−0.11405, −0.00735], **WORSE**; 568 of 11,232 fallbacks dropped the armed rules too. Its real-field Week 3 / 4 replay
    (S2) also **failed** (50.4 vs 58.7 percentile, 2 vs 6 cashes).
  - **Study 78, STUDS2_8** (two $8,000+ on the first 8 rows only, an older build): +0.01819, NO DIFFERENCE, guard 1 fails.
  - **Study 86, CAP7900** (no $8,000+ player at all): −0.04914, contradicted on 2022.
- **The supply is thin:** Weeks 4 and 5 each had four $8,000+ RB / WR / TE in the pool; 21 of his 26 Week-4 lineups held fewer
  than two (the laptop's count).

## 2. Arms (`experiments/s117_two_stars.py`)
**Study 95's harness exactly** (its frozen module `s95_shapes.py` `46b80611…`, sha-asserted; `run()` = 95's `run()` with eight
listed edits, a test asserts it), with s96 / s97 brought in byte for byte (`0363a84f…` / `7df6f324…`). **Every arm is his armed
book** (the package, te1 / low1, the cheap +2 block on 8 rows, ONECATCH and the adopted FAVHI).
- **The star set:** study 92's `star_set`, pasted byte for byte (its text sha `5fb6e7b2a22c78a7`, study 38 amendment 6r's pin;
  a test): the pool's RB / WR / TE priced **≥ $8,000**. QBs and DSTs are never stars.
- **LIVE** — his armed book.
- **STAR2** — **every book row holds at least two stars.**
- **STAR2_8** — **only the 8 cheap-block (term) rows hold at least two stars** (study 78's shape: "two stars where", not "how
  many rows"). The term block's 8 solves are built after the live block in `term_book`'s order, so they are the book solves j
  in [18, 26); the census counts the term rows to show it.
- **The vehicle (`star_rules`, study 110's `book_rules` pattern):** the constraint (the star ids, ≥ 2) is **added** to whatever
  the solve carries (te1 / low1, ONECATCH, the RB-mate floor), entered beneath every rule tier. **Infeasible → the same solve
  without the star rule only** (the armed rules are kept — unlike study 92's STAR1, whose row-tier fallback dropped them),
  recorded. Spares never.

## 3. THE FEASIBILITY RULE (fixed now, before any census)
- The census prints the star pool per slate-bank (mean / minimum, by position), each arm's book rows with 0 / 1 / 2+ stars
  (LIVE's = the vacuity check), its term rows with 2+, and the star rule's ruled and re-solved-without solves.
- **An arm whose star rule is re-solved without it on more than 5% of its ruled solves is dropped before the freeze**
  (recorded). Dealt identity to LIVE above 0.80 marks a dead lever.

## 4. The read (the reader `scripts/s117_report.py`)
- **Study 100's reader with study 110's edits, relabelled** (a test asserts them); study 63's statistics; two draws (the same
  past slates, two random opponent sets) and pooled; two-sided 0.95, B 20,000.
- **Per arm − LIVE:** P(≥ 1 big seat), its guards and verdict; **his rule's line** (better on both draws AND the pooled expected
  big seats ratio ≥ 0.80); the mean best real lineup points and P(best ≥ 200), printed.
- **THE PICK (pre-stated; `floor_pick`):** among the arms passing his rule (guard 1 printed, not gating), the largest pooled
  gain. None → "keep the live book". **A pick goes to study 117b.**
- **Multiplicity:** two arms on the same 36 slates as studies 89–116; about one false pass.

## 5. Honest limits, the census and production
- **The harness's 2023–24 slates may carry more stars than his 2026 slates** (four a week in Weeks 4–5); the census prints
  the harness's star pool, and a pass on a richer pool may not carry over. STAR2 cannot hold on a four-star slate under the
  0.35 cap (36 slots < 52); STAR2_8 fits (16 slots).
- **On his real Week-4 book:** 21 of 26 lineups hold fewer than two stars (the laptop's count, 10-10). The lab reviewer's
  Week-4 smoke of study 38 amendment 6z5 (the same rule on paper, the same vehicle) on his armed book: QA0 holds 5 rows with
  2+ stars, all in the term block; **STAR2 held on 14 of 26 book solves and fell back on 12** (the four-star pool), so it would
  fail §3's 5% rule on a slate like Week 4's; **STAR2_8 held on 8 of 8, no fallback, changing 3 term rows.** The harness and the
  paper arms measure the same rule (6z5, `0ee35848`).
- **The census, per arm (outcome-blind, bank 1406):** the stars and the feasibility rule (§3); ONECATCH; the RB mate's slots;
  rows shared with LIVE and dealt identity; LIVE == study 97's RBMATE4_FAVHI (`--ref97`). Per-slate fields stay outside the
  blocks the reader compares.
- **Production:** the laptop's star flag (`b4934067`'s row-rule side) would carry the rule; a pass needs the default-off
  switch to this file's definition, tests, the Week-4 check and study 38's classification before any arming; his decision.

## 6. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke and the census (the unit tests, the mechanics smoke 2023 W3
  / 2023 W11 / 2024 W10, the census with `--ref97`, the full path: reader exit and line count only), in a gap the lab reviewer
  names.
- **The smoke:** (filled in when done).
- **Code:** nfl2 `production/s117-two-stars-20261010` @ `50486f76` (off study 114's branch `934b239b`):
  - `experiments/s117_two_stars.py` `09caab6c…` (pins s95 `46b80611…`, s97 `7df6f324…`)
  - `scripts/s117_drive.py` `b263034b…`
  - `scripts/s117_census.py` `df8d6da7…`
  - **`scripts/s117_report.py` (the reader) `f901a88c…`** (seed 20261165)
  - `tests/test_s117_two_stars.py` `58ff1c9d…` (13)
