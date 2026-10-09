# Preregistration: study 94, a running back as a stack mate (the QB + one pass catcher + his own RB on 4 lineups) and a defense with its own running back (8 lineups), on his armed Week-5 version, in the harness (FROZEN 2026-10-09)

**Status: FROZEN 2026-10-09 (17:51 CDT)** by the reviewer, after the outside reviewer's DRAFT, the smoke, the laptop's W4 counts
and the binding census, before any scored bank. The text changed at the freeze in this status block and §6 only. The laptop acks.
**Week-6 candidates; nothing changes for Week 5.**
- **Banks 3036–3047** (set A 3036–3041, set B 3042–3047), **seed 20261139**. The laptop's scan of both repositories (whole repos; the larger blobs not searched) found none of the 37 numbers in a bank / seed context in nfl-predictions and only two incidental hits in nfl2 (3086 as a timing value in L03's drive log; 3089 inside a sha256 in study 80's raw manifest); no results file exists for any of them; its full-set check of {b, b + 50, b + 700} over 674 used banks (93's block included) is clean. Disclosed: both scans started before 94's own files were pushed, so its prereg and reader seed are not among the hits.
- **Run environment:** PYTHONHASHSEED=0 for the census and the scored run (O-63), recorded in `RUN_ENV_s94.txt` committed with
  the confirmatory census.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09 (in the outside reviewer's session; the laptop records it verbatim):** "is there anything in your log for
  things that seemed promising that we should still try?" — after the outside reviewer's list of five — **"let's try each that you
  suggested"** (HANDOFF `7a47ecc3`). Item 5 was the construction suggestions' S4 (`briefings/2026-week-05/2026-10-09-lineup-construction-suggestions.md`,
  §S3): an RB as a stack mate, a defense with its own RB, dupe-aware dealing. Asked "why is this one for next week?", then offered
  "run the duplication check now, and build study 94 tonight after study 93", he answered **"yes"**.
- **The duplication check (done, private aggregates):** across his Week 1–4 entries, 535 entries, 15 with a copy in the field, no
  tie for first in a one- to three-seat contest. Dupe-aware dealing has no measured cost to fix today; it stays a Week-6 replay item,
  not part of this study.
- **The two shapes:**
  - **an RB as a stack mate.** Today a mate is a WR or TE only. The 2026 Week-2 Millionaire was won with a QB + RB + TE from one
    team. Here: on the first 4 C-cell book solves (the QB + exactly one WR / TE, no bring-back, ≤ 3 from his game), his OWN RB is
    in the lineup too;
  - **a defense with its own RB.** A leading team runs the ball and its defense gets sacks and turnovers. Here: on the first 8
    book solves (any cell), the lineup's DST has an RB of its own team beside it.
- **The prior (cited, both ledgers checked):**
  - the realized QB–RB1 correlation is weak: **.082** (2,195 games 2018–25; Addendum 27), against QB–WR1 .446 and QB–TE1 .311;
  - **study 16** (the operator's thesis portfolio, Addendum 125): its 7.5% RB-led blowout alternative was the lead RB of a team
    favoured by ≥ 6 plus that team's DST (≤ 1 opponent) — close kin to DSTRB8; the portfolio read NO DIFFERENCE and is closed
    (Addendum 126);
  - production's permanent **FORBID_RB_DST** (the RB-vs-OPPOSING-DST ban; system study, KEEP at −4.2). DSTRB8 pairs a DST with
    its OWN team's RB, so it does not conflict; the ban stays on in every arm;
  - the co-ownership audit (Addendum 71): **RB + own DST was the most inflated chalk pair (1.7×)** in the archive (showdown
    format), so DSTRB8 likely RAISES duplication with the field;
  - neither shape has been read in the harness. **Prior: NO DIFFERENCE for each.**
- **Why re-read on the armed version:** a verdict does not transfer across a changed construction (the post-selection law); his book
  is now the armed version (the player cap 0.35 + the ownership cap + 15 + at most one TE and one player predicted < 3% per row).

## 2. Arms (`experiments/s94_rb_pairs.py`)
**Study 93's harness exactly** (its frozen module `s93_leads.py` `5f4e1fb9…`, sha-asserted; `run()` = 93's `run()` with six listed
edits, a test asserts it); every arm is the ARMED version (89's `own_caps` wrapping 6p's `row_rules`, te1 / low1).
- **ARMED** — the reference (identical mechanics to studies 91–93's ARMED).
- **RBMATE4** — on the first 4 C-cell book solves, the lab optimiser's **interaction floor** over every (QB, RB of the QB's team)
  pair in the pool, weight 1, floor 1: the lineup holds its QB's own RB. The C cell's stack rules are unchanged (exactly one WR / TE
  mate, no bring-back, ≤ 3 from the QB's game), so the row is QB + one catcher + his RB. The slot is used whether the solve is
  ruled or the floor is dropped.
- **DSTRB8** — on book solves j < 8 (build order, any cell), the floor over every (DST, RB of the DST's team) pair: the lineup's DST
  has its own RB.
- **THE COMPOSITION:** 6p's `row_rules` and a floor each patch `S24.optimize` with a `partial`; nested, one would silently drop the
  other. `lead_rules` (93's pattern) puts the armed rules (`set_constraints`) AND the floor (`interaction_floor_weights`,
  `interaction_floor` 1.0) in ONE `partial`, ONE solve. Tests record every optimiser call's kwargs and assert both ride in the same
  call; spares never carry either. One floor per arm (asserted).
- **The fallback, explicit:** a floor solve that is infeasible is re-solved with the ARMED rules only (the floor dropped, recorded in
  `lead_plain`); still infeasible → no row rule (6p's fallback, recorded); the ownership cap wraps it all. The census flags floor
  fallbacks above 5% before the freeze.

## 3. The read (the reader `scripts/s94_report.py`)
- 2023–24 (36 slates); twelve banks as two disjoint draws and pooled; study 63's frozen statistics (a test asserts them); two-sided
  0.95, B 20,000; the guards gate a PASS only.
- **Each lead − ARMED** on P(≥ 1 big seat) per slate; **the W6 candidate rule printed per lead**: better on both draws AND the pooled
  expected big seats ratio ≥ 0.80 (his rule from study 91), guard 1 beside it — information for his Week-6 decision.
- **The null rate and MULTIPLICITY, plainly:** under no true effect each lead passes about one time in four to one in three (the two
  draws share slates and outcomes); these are two more candidates read on the same 36 slates as studies 89–93. The real-week paper
  arms are the check.

## 4. What the harness can and cannot say
- The census reports per arm: the QB + own-RB rows and the DST + own-RB rows (ARMED against each lead = the binding), the floor's
  ruled / dropped counts and the RBMATE slots used, the pair pools, and each lead's rows shared with / dealt identical to ARMED (the
  vacuity).
- The scored field (v2, `l02b_field_sampler.py`) carries the real Millionaire field's structure measured on about 490,000 W2–4
  lineups, **including a QB-team RB in about 18% of lineups** (RB_MATE_P), so RBMATE4 is read against a field that already plays
  the shape at its real rate. **The field's DST is drawn on its own** (no DST + own-RB pairing), so the harness cannot see the
  duplication cost the co-ownership audit predicts for DSTRB8: its read is optimistic on that count. His real-book view (FP's
  projections) can differ (studies 91 / 92's transfer lesson); a real-book check by the laptop precedes any live use.

## 5. Production — only on his decision, for Week 6
- No production flag exists. A live version would be a union_reselect flag rebuilt on the armed version, with parity against this
  study's `lead_rules` and `rb_pairs` (production optimise takes pair floors differently; the outside reviewer writes it on a GO).

## 6. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke: the unit tests, the mechanics smoke (2023 W3, 2023 W11,
  2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **The smoke (DONE 17:05 CDT in the gap the reviewer named, before study 93's run; bank 1406; 2023 W3, 2023 W11, 2024 W10;
  PYTHONHASHSEED=0; `results_bank1406.jsonl` `72089739…`; code `627e5153`):** 10 unit tests pass; every arm 41 rows within the
  armed caps, 8 term rows, in the pool; 0 row-rule and ownership-cap fallbacks in every arm (78 of 78); **the floor: RBMATE4 ruled
  12 of 12 (12 C-cell slots), DSTRB8 24 of 24, none dropped; THE BINDING: QB + own-RB rows ARMED 2.0 → RBMATE4 6.0 (DSTRB8 5.3);
  DST + own-RB rows ARMED 1.7 → DSTRB8 9.0**; pair pools per slate-bank (QB, own RB) 126.0 (min 105), (DST, own RB) 61.7 (min 60);
  rows shared with ARMED: RBMATE4 4.33, DSTRB8 0.67 (dealt identical 0.000 both); projection per row vs ARMED −0.08 / −0.16; flex
  WR / TE / RB: ARMED 14.3 / 0 / 11.7, RBMATE4 17.7 / 0 / 8.3, DSTRB8 15.7 / 0 / 10.3; **ARMED's rows and dealing are identical to
  study 93's smoke ARMED on all three slates**; the full path: the reader exited 0 (35 lines; 43 with the two-draw path on a copy);
  only those were read.
- **His real W4 book on the armed version** (the laptop's outcome-blind counts, `~/rehearsals/flagcheck-pkgTE1LOW1-20261009T183613Z/on`,
  rank order as the build-order proxy): both leads bind there. RBMATE4: 1 of the first 4 C rows already holds the QB's own RB (3
  of 4 change); 1 of the 7 C rows; 2 of 26 rows book-wide. DSTRB8: none of the first 8 rows holds an RB of the DST's own team (all 8
  change); 3 of 26 rows book-wide.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all 36 slate-banks of 2023–24; code `627e5153`
  clean; PYTHONHASHSEED=0; 10 tests pass; lab `results/s94/CENSUS_s94_binding.txt` `82414e83…`, the raw mechanics rows
  `census_mechanics_bank1406.jsonl` `19ed871a…` with no outcome field, committed at `1088d74d`):
  - every arm 41 rows within the package's caps, 8 term rows, in the pool; 0 row-rule / ownership-cap fallbacks in every arm;
    **no floor dropped** (RBMATE4 144 of 144 slots ruled; DSTRB8 288 of 288);
  - the pool per slate-bank: (QB, own RB) pairs 120.5 (min 82); (DST, own RB) pairs 61.6 (min 43);
  - **RBMATE4:** QB + own-RB rows 2.7 → 5.3 of 26; rows shared with ARMED 6.44; none dealt identical; projection +0.00;
  - **DSTRB8:** DST + own-RB rows 3.1 → 9.0 of 26; rows shared with ARMED 1.28; none dealt identical; projection −0.07;
  - **PARITY:** ARMED builds identical rows to study 93's ARMED binding census on all 36 slate-banks.
- **Code:** nfl2 `production/s94-rb-pairs-20261009` @ `627e5153` (branched from study 93's `8bc3ef7a`):
  `experiments/s94_rb_pairs.py` `2eb7835b…` (pins s93 `5f4e1fb9…`); `scripts/s94_drive.py` `d71eb15e…`; `scripts/s94_census.py`
  `b9b70ab6…`; **`scripts/s94_report.py` (the reader) `82260ef0…`** (seed 20261139); `tests/test_s94_rb_pairs.py` `327815db…` (10).
