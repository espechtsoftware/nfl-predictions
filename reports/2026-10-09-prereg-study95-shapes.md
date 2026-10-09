# Preregistration: study 95, the shape comparison — each lineup shape alone, and the mix without one shape at a time, against his live Week-5 book, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (18:53 CDT; smoke done 18:59)** by the outside reviewer; code and smoke done (§5). The reviewer
reviews, runs the binding census and FREEZES; the laptop acks. **Week-6 information; nothing changes for Week 5.**
- **Banks and seed (proposed):** **3100–3111** (set A 3100–3105, set B 3106–3111; sims bases 3150–3161, fields 3800–3811), seed
  20261140 — clear of studies 91–94's {b, b + 50, b + 700} by construction (3048–3059 would collide with study 91's sims bases);
  the laptop scans.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09 evening (study-list row 85, the laptop's records):** "We currently have several shapes of linups that we do
  in different percentages, I believe. Is that correct? If so, can we do a test of each one as 100% in separate runs and determine
  if they all are still worth doing?"; then "I like what you suggesated for removing one at a time when we do the comparison of
  the shapes. But let's do that after we finish the other tests" (HANDOFF `c85774de`).
- **Then, in the outside reviewer's session, after studies 93 and 94 read** and the reviewer recommended "go ahead with
  production's tests that take away one shape at a time": **"Lets try them tonight"** (the laptop records it verbatim; HANDOFF
  commit: to be cited here before the freeze). This lifts his earlier HOLD on the each-shape-at-100% test (row 85): the ONLY_x
  arms are that test.
- **The shapes (his live book, `mix_shapes.MIX_CELLS`, by dealt entries):** A1 30% (QB + 2 + a bring-back, the old house shape),
  A2 14% (QB + 2, no bring-back), B 28% (QB + 1 + a bring-back + a pair from a second game), C 28% (QB + 1, no bring-back).
- **The prior:**
  - study 28 (Addendum 133): the mix against the house shape (≈ A1 alone) +6.1, NO DIFFERENCE, every season positive;
  - study 18 (Addendum 129): the mix NO DIFFERENCE against the house shape;
  - study 56 (Addendum 163): half of the QB + 1 rows moved to QB + 2 +1.8, NO DIFFERENCE.
  - **Prior: NO DIFFERENCE for every arm.** The harness has never found a shape mix that beats another on both draws.

## 2. Arms (`experiments/s95_shapes.py`)
**Study 93's harness exactly** (its frozen module `s93_leads.py` `5f4e1fb9…`, sha-asserted; `run()` = 93's `run()` with six listed
edits, a test asserts it). **Every arm is his live Week-5 construction:** the player cap 0.35, the ownership cap + 15 (89's
`own_caps`), at most one TE and one player predicted < 3% per row (6p's row rules), and **ONECATCH** (at most one WR / TE per team
on every B / C book solve; 93's `lead_rules(0, True, 0, …)`), the QB cap 5, the DST cap 6, the overlap limit 4, the cheap +2
block (8 rows), 15 spares, Rev6. Only the cell quotas differ, through **study 56's `quotas()`** (re-stated byte for byte; a test
asserts the text), which `term_book` reads at call time for both the live and the cheap block:
- **LIVE** — 0.30 / 0.14 / 0.28 / 0.28 (the reference).
- **NO_A1, NO_A2, NO_B, NO_C** — one shape at 0, the other three re-scaled in proportion (e.g. NO_A1 = 0 / 0.20 / 0.40 / 0.40).
- **ONLY_A1, ONLY_A2, ONLY_B, ONLY_C** — one shape at 1.0 (the whole book and the cheap block).
- The cells' rules are unchanged; a cell that cannot solve passes its quota to A1, counted (as live). ONECATCH binds only in B / C
  rows, so it never acts in ONLY_A1 / ONLY_A2 and acts on every row of ONLY_B / ONLY_C.

## 3. The read (the reader `scripts/s95_report.py`)
- 2023–24 (36 slates); twelve banks as two disjoint draws (the same past slates, two random sets of opponents) and pooled;
  study 63's frozen statistics (a test asserts them); two-sided 0.95, B 20,000; the guards gate a PASS only.
- **The decisions — "is shape x still worth doing?": NO_x − LIVE** on P(≥ 1 big seat) per slate, per shape. **His rule printed per
  arm:** better on both draws AND the pooled expected big seats ratio ≥ 0.80. **NO_x passing = the mix WITHOUT shape x beat the
  live mix: a Week-6 candidate to drop shape x. NO_x failing = keep x.**
- **Information: ONLY_x − LIVE** per shape (each shape at 100%).
- **The null rate and MULTIPLICITY, plainly:** under no true effect each arm passes about one time in four to one in three;
  **eight comparisons, so about two false passes are expected.** These are eight more readings of the same 36 slates as studies
  89–94. A pass is a candidate for his decision and the paper arms, never proof.

## 4. What the harness can and cannot say
- The census reports per arm: the book rows per cell (the quotas as built, passes to A1 included), ONECATCH's ruled / dropped
  solves, the same-team receiver pair rows away from the QB, the projection per row, and the rows shared with / dealt identical
  to LIVE (the vacuity).
- **ONECATCH is armed for Week 5** (the W5 arm `ee92d15b`, ONE_CATCHER_ALL=1, after the laptop's W4 check and study 38 6t
  passed; FRIDAY_HEAD `462ba341`), so LIVE is his live book. The reviewer's call (10-09): no separate reference without it. The
  comparison is between shapes, with the rule riding equally in all arms; if it were pulled on Saturday, his live book would
  change and a Week-6 decision would need a re-read anyway (the post-selection law).
- His real-book view (FP's projections) can differ (studies 91 / 92's transfer lesson); any Week-6 change gets the laptop's
  real-book check first. Production's vehicle exists: `union_reselect --mix-cell-quotas` (every cell must be > 0, so NO_x needs a
  small flag change; ONLY_x is a different construction).

## 5. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke: the unit tests, the mechanics smoke (2023 W3, 2023 W11,
  2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **The smoke (DONE 18:59 CDT in the gap the reviewer named; bank 1406; 2023 W3, 2023 W11, 2024 W10; PYTHONHASHSEED=0;
  `results_bank1406.jsonl` `b5afcdd7…`; code `2ca40a3f`):** the first attempt died at once on a missing `import time` in the new
  module (no row built; a name-resolution unit test now guards it). The re-run: every arm 41 rows within the armed caps, 8 term
  rows, in the pool; **0 row-rule and ownership-cap fallbacks in every arm** (78 of 78); **ONECATCH ruled on every B / C book
  solve, none dropped** (LIVE 42, ONLY_B / ONLY_C 78, NO_A1 60, NO_A2 51, NO_B / NO_C 30; none in ONLY_A1 / ONLY_A2); **the book
  rows per cell as quoted** (LIVE 8 / 4 / 7 / 7; NO_A1 0 / 6 / 10 / 10; NO_A2 9 / 0 / 9 / 8; NO_B 10 / 6 / 0 / 10; NO_C 10 / 6 /
  10 / 0; each ONLY_x 26 of its cell; no pass to A1); rows shared with LIVE 0.0–4.0 of 26, **no arm dealt identical to LIVE**;
  projection per row vs LIVE −0.56 (ONLY_A1) to +0.25 (ONLY_C); the full path: the reader exited 0 (101 lines; 133 with the
  two-draw path on a copy).
- **Disclosure (the reviewer's slip):** checking the reader's heading on the full-path copy, the reviewer's grep also printed the
  per-arm rule lines of that SMOKE (bank 1406, two slates, the same copy as both "draws"). Those numbers come from no scored bank
  and carry no information; the design (arms, decision, reader) was fixed in code before and nothing was changed after.
- **Code:** nfl2 `production/s95-shapes-20261009` @ `2ca40a3f` (branched from study 94's `a1367c2d`): `experiments/s95_shapes.py`
  `46b80611…` (pins s93 `5f4e1fb9…`); `scripts/s95_drive.py` `b000d60f…`; `scripts/s95_census.py` `e7da2408…`;
  **`scripts/s95_report.py` (the reader) `e9c0b4d5…`** (seed 20261140); `tests/test_s95_shapes.py` `e3f9ad50…` (7).
