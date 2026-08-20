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
| A1 | **All-boom S follow-up** | **DONE — NULL** (ΔS +1.34, p 0.49; 19/18/16; winner-overlap worse than control). Reallocation CLOSED for the money path at this dose; boom-deep pool shelved pending a selector change. Results: `2026-08-19-all-boom-selection-s-results.md` | — | Selector cannot harvest the +9 ceiling; selection-side lane elevated |
| A2 | **Dependence repair** (factor split first) | **SCOREFREE PROTOCOL FROZEN; implementation next.** Exact half-residualized/one-hot QB-WR rank dose, no grid (`2026-08-20-a2a-rank-factor-split-scorefree-protocol.md`) | Complete outcome-blind mechanism census; only its pass licenses a separately frozen remeasurement | Whether the law's co-boom misallocation (generic ↑, QB–WR ↓) is mechanically fixable before any score arm |
| A3 | **Stack-relaxation carve** | **DONE — NEGATIVE** (ΔS −0.98; 6/11/36; 194-line 9→8). Mechanism non-vacuous: 530 open lineups entered the books across all 53 slates, and scores got worse. Mandates are acting as a correction for the law's QB→WR under-coupling. Closed at this dose; lever stays default-off. Results: `2026-08-20-stack-relaxation-carve-results.md` | — | Relaxation RESEQUENCED behind the A2 law repair |
| A4 | **Ownership-template arm** (B lane) | **BLOCKED — entry gate FAILED.** own_est has 10.2% precision on predicted chalk and rho 0.176 vs realized; constraining on it would constrain on noise. Results: `2026-08-20-own-est-calibration-gate-results.md` | Needs a materially better ownership model first (own_shadow / train-ownership on Week-1+ standings) | Closed at this input quality; the winner-ownership finding itself stands |
| A5 | **Selector optimality audit** | **DONE — CLOSED.** 255/255 blocks exact; mean gap 2.84 worlds = 0.134% of greedy coverage. Greedy is effectively optimal; algorithm family closed permanently. Results: `2026-08-19-selector-optimality-results.md` | — | Loss is in the OBJECTIVE, not the algorithm → elevates A7 SELECT_LADDER |
| A6 | **S1 null-gap floor** | Implemented; needs operator freeze + R5 fresh-seed world block | Operator decision | The winnable share of the P−C gap under a perfect law (construction vs law budget split) |
| A7 | **SELECT_LADDER one-shot** | **V1 CLOSED AT OUTCOME-BLIND SMOKE; DEFERRED.** No historical look or score result; no retry (`2026-08-20-a7-outcome-blind-smoke-failure-and-queue-disposition.md`) | Fresh protocol/build/preflights would be required; do not displace A2 | The 5.01-point C−S objective-alignment prize remains unadjudicated |
| A8 | **Regret-targeted generation** | Concept logged (winner-audit result doc) | All-boom S read; N1c reframed it as sim-coverage-hole closing, not winner-reaching | Whether choosing WHICH worlds to solve by pool regret beats rank-order depth |
| A9 | Marginal-tail Stage 2/3 | **PARKED** by the Stage-1 census (transform is a no-op; defect is allocation) | Revisit only after A2 lands | — |
| A10 | **Deep-history rebuild** | Scoped 2026-08-19: 2019 and 2021 are REBUILDABLE with the already-fixed pipeline (salaries exist via RotoGuru); 2020 and 2022 are salary-gated (no free source; paid/community archive only). Needs an operator go | Adds ~36 valid slates (2019+2021) to every construction/selection experiment and extends the winner censuses to 2019 winners |

## B. Prospective — must exist before Week 1

| # | Item | Status | Notes |
|---|---|---|---|
| B1 | **shadow-cbwu-volume** (20 books) | **BUILT** — combine, policy env, live dispatch, CLI subcommand, job + Sunday 08:30 schedule, and FROZEN grading spec (`2026-08-19-cbwu-volume-prospective-shadow-spec.md`). Deploys with the next `deploy_jobs.sh` run | Operator: deploy + resume schedulers | Prospective test of the B2-prime volume gain; adoption bar frozen before collection |
| B2 | **Contest-entries collection** | Importer ready; `contest_entries` still empty | LOAD-BEARING: Mon/Tue standings downloads from Week 1 (DK purges ~4 days). Feeds field model, measured N_eff, top-N winner sets. Verify rows land Week 1 |
| B3 | Shadow fleet + schedulers resume (~Aug 24) | Operator action | Existing CT schedules; no research lever enabled |
| B4 | September cadence | Standing (`CLAUDE.md`) | standings → import-ownership; Wed tabpfn-gen; ETR CSV; persona/env-forecast grading; CQR at ≥100 rows; DIV_TILT grade wk 4–6; entries per contest-mix |

## C. Operator decision queue (blocking the flagged items)

1. Stack-relaxation k (A3) — DECIDED: k=8 absolute per seed (operator delegated sizing 2026-08-19; rationale in the draft). Arm awaits only the S-read comparator.
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
| A11 | **Stack-shape census** | **DONE** — report SHA `39d66b7c…`, results in `2026-08-19-winner-structure-census-results.md` | — | Winners: 16% full production shape, 63% stack ≤1, 61% no bring-back; our books: 100% full shape |
| A12 | **Eight-constructible-winners forensic** | **DONE** — same report | — | Blocker is worlds+combinations, not coverage: 7/8 zero missing players, best ranks 43–119 (all past top-40), gaps 17–57 |
| A2+ | **Post-repair winner re-census**: after any dependence repair passes its law-shape gate, re-run N1b/N1c under the repaired law (generating-world counts, winner-vs-optimum gaps) | NEW — amendment to A2's guard metrics | The winner-side validation that the repair moves worlds TOWARD winners, not merely inside equivalence bands |
| — | **Standing rule:** every future generation/selection arm reports the anatomy-A instrument (selected-book winner overlap vs exposure-null) | ADOPTED in A1; now standing | Distinguishes aim from volume in every future positive result |
