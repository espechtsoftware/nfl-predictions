# Preregistration: study 93, three earlier leads re-read on his armed Week-5 version (the QB alone in 3 lineups, one receiver per team on every QB + 1 lineup, a WR in the flex on 8 lineups), in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (16:50 CDT)** by the outside reviewer; code done, the smoke running. The reviewer reviews, runs the binding
census and FREEZES; the laptop acks. **Week-6 candidates; nothing changes for Week 5.**
- **Banks and seed:** **3024–3035** (set A 3024–3029, set B 3030–3035; sims bases 3074–3085, fields 3724–3735), seed 20261138 — the
  reviewer's block, clear of study 92's by construction; the laptop scans it.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09 (in the outside reviewer's session; the laptop records it verbatim, HANDOFF `7a47ecc3`):** "is there anything
  in your log for things that seemed promising that we should still try?" — after the outside reviewer's list of five — **"let's try
  each that you suggested"**. Items 2–4 of that list are this study; item 1 (a low-ownership limit at FP 5% / 8%) is the reviewer's
  study 38 amendment 6s (paper); item 5 (an RB as a stack mate, a DST with its own RB, dupe-aware dealing) is study 94 / a replay.
- **The leads (the promising-leads log, read on his OLD book):**
  - **the QB alone in 3 lineups** (study 77, Addendum 175): +1.8 (2023 +1.4, 2024 +2.3), 2022 +0.2; in combinations it did not hold
    (study 83's COMBO −1.9; 84's +1.0; with the TE ban −2.0);
  - **one receiver per team on every QB + 1 lineup** (study 79's every-lineup version, a side reading): +2.1, 2022 +0.8;
  - **a WR in the flex on 8 lineups** (study 75, Addendum 173): +2.3 (2023 +1.6, 2024 +3.0), 2022 −1.1 (contradicted).
- **Why re-read:** a verdict does not transfer across a changed construction (the post-selection law); his book is now the armed
  version (the player cap 0.35 + the ownership cap + 15 + at most one TE and one player predicted < 3% per row). With the TE rule
  live, the flex is a WR or an RB (on his W4 real book 7 / 0 / 19), so the WR-flex question is now WR against RB.
- **The prior:** NO DIFFERENCE for each.

## 2. Arms (`experiments/s93_leads.py`)
**Study 92's harness exactly** (its frozen module `s92_shrink_star.py` `37980da6…`, sha-asserted; `run()` = 92's `run()` with the
listed edits, a test asserts it); every arm is the ARMED version (89's `own_caps` wrapping the row rules).
- **ARMED** — 6p's `row_rules` (te1, low1) inside `own_caps` (the reference; identical to studies 91 / 92's ARMED).
- **QBALONE3** — + the QB alone (no WR / TE of his team) on the first 3 C-cell book solves (study 83's C0: the naked C stack).
- **ONECATCH** — + at most one WR / TE per team on every B / C (QB + 1) book solve (study 83's ONEPC).
- **WRFLEX8** — + at least 4 WRs (a WR in the flex) on book solves j < 8 (study 83's FLEX).
- **THE COMPOSITION (the reviewer's warning):** study 83's `combo` and 6p's `row_rules` each set `S24.optimize` to a partial with
  their own `set_constraints`, so nesting them silently drops one list. `lead_rules` re-states 83's combo logic and puts the armed row
  rules and the lead's constraints in ONE optimize patch (a test records every call's kwargs and asserts both lists ride together,
  the naked C0 stack, spares never).
- **The fallback, explicit:** a lead solve that is infeasible is re-solved with the ARMED rules only (the lead dropped first, recorded
  in `lead_plain`); still infeasible → no row rule (6p's fallback, recorded); the ownership cap wraps it all. The census flags lead
  fallbacks above 5% before the freeze.

## 3. The read (the reader `scripts/s93_report.py`)
- 2023–24 (36 slates); twelve banks as two disjoint draws and pooled; study 63's frozen statistics (a test asserts them); two-sided
  0.95, B 20,000; the guards gate a PASS only.
- **Each lead − ARMED** on P(≥ 1 big seat) per slate; **the W6 candidate rule printed per lead**: better on both draws AND the pooled
  expected big seats ratio ≥ 0.80 (his rule from study 91), guard 1 beside it — information for his Week-6 decision.
- **The null rate and MULTIPLICITY, plainly:** under no true effect each lead passes about one time in four to one in three (the two
  draws share slates and outcomes); with three leads, about one false pass is expected; these are three more candidates read on the
  same 36 slates as studies 89–92. The real-week paper arms are the check.

## 4. What the harness can and cannot say
- The census reports per arm: the naked-QB rows, the same-team receiver pair rows away from the QB, the flex WR / TE / RB mix, the lead
  ruled / dropped counts and the C0 slots used, and each lead's rows shared with ARMED (vacuity).
- His real-book view (FP's projections) can differ (studies 91 / 92's transfer lesson); a real-book check by the laptop precedes any
  live use.

## 5. Production — only on his decision, for Week 6
- The three rules exist as unmerged production flags (`--mix-qb-alone-rows`, `--mix-one-catcher-rows`, `--mix-flex-wr-rows`; the
  outside reviewer's branches of 10-08 / 10-09) on an older base; a live version would be rebuilt on the armed version with parity
  against this study's `lead_rules`.

## 6. Smoke, census and integrity
- BLAS threads pinned; PYTHONHASHSEED=0 (the laptop's request); bank 1406 only for the smoke: the unit tests, the mechanics smoke
  (2023 W3, 2023 W11, 2024 W10), the binding census, the full-path smoke (reader exit and line count only).
- **The smoke (DONE; bank 1406; 2023 W3, 2023 W11, 2024 W10; PYTHONHASHSEED=0; `results_bank1406.jsonl` `7a7dfb94…`):** 8 unit tests
  pass; every arm 41 rows within the armed caps, 8 term rows, in the pool; 0 row-rule and ownership-cap fallbacks in every arm;
  **the leads: QBALONE3 9 of 9 C0 solves ruled (3 naked-QB rows per slate-bank); ONECATCH 42 of 42 ruled (same-team receiver pairs away
  from the QB 5.3 → 1.3 rows); WRFLEX8 24 of 24 ruled (flex WR rows 14.3 → 16.7: ARMED's harness book already puts a WR in the flex in
  14 of 26 rows)**; no lead dropped; rows shared with ARMED: QBALONE3 3.0, ONECATCH 9.3, WRFLEX8 3.3 (none identical); projection per
  row vs ARMED −0.01 / −0.02 / −0.08; the full path: the reader exited 0 (46 lines; 58 with the two-draw path on a copy).
- **Code:** nfl2 `production/s93-leads-20261009` @ `ac7ea5b0` (branched from study 92's frozen branch `5e9d0347`):
  `experiments/s93_leads.py` `5f4e1fb9…` (pins s92 `37980da6…`); `scripts/s93_drive.py` `b930be57…`; `scripts/s93_census.py`
  `9b0d3f40…`; **`scripts/s93_report.py` (the reader) `9dc905d4…`** (seed 20261138); `tests/test_s93_leads.py` `05633b15…` (8).
