# Preseason test queue — the single ordered list

**Date:** 2026-08-19 (operator: "be sure these latest ideas are logged and
prepared to be tested at the appropriate time in this preseason queue").
This document supersedes scattered queue notes; the plan doc
(`2026-08-19-selection-volume-admission-plan.md`) remains the evidence
record behind items it introduced. Update THIS file when an item's status
changes; `HANDOFF.md` points here.

Season clock: schedulers resume ~Aug 24; Week 1 lock ~Sep 7. Historical
one-shot arms belong BEFORE the season; prospective shadows must be
deployed BEFORE Week 1; in-season items follow the September cadence in
`CLAUDE.md`.

## A. Offseason one-shot arms (historical corpus, frozen protocols)

| # | Arm | Status | Gate / prerequisite | Decides |
|---|---|---|---|---|
| A1 | **All-boom S follow-up** (`20260819-all-boom-selection-s-v1`) | Implemented; smoke in progress; launch on smoke pass + freeze | Licensed by the C arm's clear (+9.06) | Does boom depth reach the actual 80-lineup book (the operator's "boom as actual lineups against full history") |
| A2 | **Dependence repair** (factor split first) | Design logged (`2026-08-19-dependence-repair-design.md`) | All-boom S read (owns the next law build slot); measured shape is the target | Whether the law's co-boom misallocation (generic ↑, QB–WR ↓) is fixable; guard: book-tail + optimum-realism |
| A3 | **Stack-relaxation carved budget** | Draft frozen-ready (`2026-08-19-stack-relaxation-carved-budget-draft.md`) | Operator k (proposed 8); comparator = whichever boom config the S read crowns; anatomy chance-null mechanism gate included | Whether removing QB-stack/bring-back on a carve reaches the 43/51 winners the rules exclude |
| A4 | **Ownership-template arm** (B lane) | Draft (`2026-08-19-ownership-template-arm-draft.md`) | ENTRY GATE first: own_est-vs-realized calibration on the 51 winner slates (descriptive, runnable anytime); then queue behind A3 | Whether imposing the measured chalk-core+4-leverage shape on a carve closes the chance-level proximity gap |
| A5 | **A3-audit: selector optimality** (CBC exact vs greedy) | Implemented, unrun | None (score-free) — run in any idle window | Closes the selector-ALGORITHM question permanently |
| A6 | **S1 null-gap floor** | Implemented; needs operator freeze + R5 fresh-seed world block | Operator decision | The winnable share of the P−C gap under a perfect law (construction vs law budget split) |
| A7 | **SELECT_LADDER one-shot** | Implemented, default-off | Operator utility freeze (mean vs ladder vs lexicographic) + one-shot selector amendment | The 5.01-point C−S objective-alignment prize |
| A8 | **Regret-targeted generation** | Concept logged (winner-audit result doc) | All-boom S read; N1c reframed it as sim-coverage-hole closing, not winner-reaching | Whether choosing WHICH worlds to solve by pool regret beats rank-order depth |
| A9 | Marginal-tail Stage 2/3 | **PARKED** by the Stage-1 census (transform is a no-op; defect is allocation) | Revisit only after A2 lands | — |
| A10 | **Boom vs deep history (2019–2022)** | Logged as operator option | Requires rebuilding the corrected-universe artifacts for those seasons (the old panels are invalid: DST aliases, Thursday dupes, slate mixing). Large lane; needs an explicit operator go | Extends the boom verdicts beyond the 54-slate 2023–2025 corpus — the current runs already cover the full VALID history |

## B. Prospective — must exist before Week 1

| # | Item | Status | Notes |
|---|---|---|---|
| B1 | **shadow-cbwu-volume k=20** weekly variant | NOT implemented — next implementation slot after A1 launches | Largest measured selection-side gain (B2-prime +2.0–2.75 mean S at fixed budget); adoption only via the prospective record |
| B2 | **Contest-entries collection** | Importer ready; `contest_entries` still empty | LOAD-BEARING: Mon/Tue standings downloads from Week 1 (DK purges ~4 days). Feeds field model, measured N_eff, top-N winner sets. Verify rows land Week 1 |
| B3 | Shadow fleet + schedulers resume (~Aug 24) | Operator action | Existing CT schedules; no research lever enabled |
| B4 | September cadence | Standing (`CLAUDE.md`) | standings → import-ownership; Wed tabpfn-gen; ETR CSV; persona/env-forecast grading; CQR at ≥100 rows; DIV_TILT grade wk 4–6; entries per contest-mix |

## C. Operator decision queue (blocking the flagged items)

1. Stack-relaxation k (A3) — proposed 8 of 40.
2. Utility freeze + one-shot selector amendment (A7).
3. S1 freeze + R5 fresh-seed block (A6).
4. Deep-history rebuild go/no-go (A10).
5. Job-deletion list for quota headroom — operator-only, erases cloud
   execution history.

## Standing rules

Fixed budgets, preregistered readings, one shot per protocol version,
outcome-blind reality smokes before every freeze, co-primary reporting,
audit before verdict. No production change from any historical
diagnostic; 2026 prospective season is the confirmation instrument.

## Addendum (2026-08-19, operator review): winner-analysis follow-ons not previously queued

| # | Item | Status | Why |
|---|---|---|---|
| A11 | **Stack-shape census**: winners' stack anatomy (QB+nWR/TE, double stacks, bring-back shapes, game concentration) versus our registered books' | NEW — descriptive, all data local, runnable anytime | Dependence found QB–WR under-coupling; anatomy B measured ownership shape but never STACK shape. Directly informs the A2 repair target and the A3 carve design |
| A12 | **Eight-constructible-winners forensic**: the 8 rule-legal winners still peaked at 4.5/9 pool overlap — per-case, were their generating worlds solved? players candidate-eligible? salary-reachable? | NEW — 8 cases, cheap | Names the residual non-rule blocker; sharpest possible microscope on why legal winners still are not built |
| A2+ | **Post-repair winner re-census**: after any dependence repair passes its law-shape gate, re-run N1b/N1c under the repaired law (generating-world counts, winner-vs-optimum gaps) | NEW — amendment to A2's guard metrics | The winner-side validation that the repair moves worlds TOWARD winners, not merely inside equivalence bands |
| — | **Standing rule:** every future generation/selection arm reports the anatomy-A instrument (selected-book winner overlap vs exposure-null) | ADOPTED in A1; now standing | Distinguishes aim from volume in every future positive result |
