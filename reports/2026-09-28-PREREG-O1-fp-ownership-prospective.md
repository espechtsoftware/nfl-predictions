# PREREG-O1 — Fantasy Points ownership projections against our lag model, prospectively (laptop, 2026-09-28)

**Status: FROZEN at the commit that adds this file.** No Fantasy Points ownership projection has been captured or
seen, and no Week-4 ownership exists.

## Why

- **L05 read cell C** (`reports/2026-09-28-laptop-l05-final-read.md`): the chalk-core sleeve helps with realized
  ownership labels but not with our lag model's pre-lock labels.
- **The Week-3 tilt shows the same thing:** realized ownership gave 156.8, the pre-lock sets 148.1, no tilt 151.4.
- **The operator already pays for** Fantasy Points' weekly DraftKings ownership projections. Production captures that
  page from Week 4, on Saturday and at T-70 (nfl-predictions `a7b0f6c0`).
- **L05's frozen reopening condition** asks for a 2023–25 walk-forward comparison. Fantasy Points projections cannot
  be back-captured, so this protocol replaces that route with a prospective one. The operator approves the substitution
  or rejects it; nothing is adopted by this file.

## Protocol

**Weeks:** 2026 Weeks 4, 5, 6 and 7 (the Sunday main slate). A missing capture is recorded, never filled in after
lock.

**Predictors,** all captured before the Sunday lock:
- **FP:** the T-70 capture of the Fantasy Points ownership projections page for DraftKings. If the T-70 capture is
  missing, the Saturday capture is used, and that is disclosed.
- **LAG:** `pred_own` from the week's Saturday `ownership_sets.csv` (`scripts/ownership_sets.py sets`), the live
  predictor.

**Target:** realized per-player ownership in that week's Sunday Millionaire, counted from the contest's own lineups
(`contest_entries`, as `book_vs_field_scoreboard.field_ownership_sql` does). This is not DraftKings' printed
`%Drafted`, which omits identical-share slot rows.

**Population:** every main-slate player priced by both sources and in the realized table (players absent from the
field count as 0% owned). It is reported for all players and for skill players only. Players are matched by
DraftKings id, and by normalized name and team when a source lacks the id. Match rates are reported.

**Metric per week:** Spearman rank correlation with the target, for FP and for LAG. Also reported, never decisive: the
mean absolute error in percentage points, and the top-15 overlap (the CHALK set) with the realized top 15.

## Decision rule, applied once, after Week 7

**FP REPLACES LAG** as the pre-lock ownership source (for the sets file, any sleeve and any tilt) only if both hold:
- the mean over the four weeks of Spearman(FP) − Spearman(LAG) is ≥ 0.03;
- FP is better in at least 3 of the 4 weeks.

Otherwise LAG stays.

A replacement makes the chalk-core sleeve and the ownership tilt eligible for **new** preregistered tests with FP
labels. It adopts neither.

## Who does what

- **Production:** captures the page (Saturday and T-70) and loads the Millionaire standings each Monday.
- **The laptop:** runs the comparison each Monday, reports the per-week numbers in HANDOFF without acting on them, and
  applies the rule once after Week 7.
- **Production:** re-runs the comparison before the ledger row.


## Amendment 1 (2026-09-29 13:18 CDT, before any Week-4 ownership outcome exists): three more arms (the reviewer's route (b) for L15)

Written before the Week-4 Sunday slate is played; no Week-4 realized ownership exists. The original FP-vs-LAG
comparison and its rule are unchanged. Added, each graded by the **same rule, applied separately against LAG** after
Week 7:
- **LINESTAR:** LineStar's projected DraftKings ownership, captured pre-lock by `scripts/linestar_ownership_capture.py`
  (the T-70 capture; the Saturday capture if T-70 is missing, disclosed). Evaluated, like FP, on the players it
  covers, against LAG on the same players.
- **BLEND_LS** (the reviewer's rule, production 13:12 CDT 09-29): on the ownership-percent scale, a covered player's
  value is the mean of LAG's percent and LINESTAR's percent; an **uncovered player keeps LAG's percent**. Evaluated on
  the **full slate** (every player in the realized table), the population the +0.03 bar was set on.
- **BLEND_FP** (the reviewer's "lag + FP blend"): the same rule with FP in place of LINESTAR. Full slate.

**Co-reported for every arm, never decisive:**
- the **top-15 overlap** with the realized top 15 (the CHALK set the informed-chalk anchor consumes; the reviewer's
  metric; lag reference about 6 of 15);
- each source's coverage of the slate;
- the MAE.

**Multiplicity:** four arms against one baseline. An arm that passes is reported as a pass and **flagged for the
operator and the reviewer**. It adopts nothing by itself; any live use still needs its own preregistered test.

**Who:** production captures LINESTAR from Week 4 (Saturday and the T-70 slot; wired after the laptop's smoke). The
laptop computes all arms each Monday.


## Amendment 2 (2026-10-02, before any Week-4 ownership outcome exists): ONE early checkpoint after Week 5 (operator: "I will want those timelines escalated")

Written on Friday 10-02, before the Week-4 Sunday slate; no Week-4 realized ownership exists. The Week-7 final rule and
amendment 1 are unchanged. Added: one interim read, after Week 5 (Monday 10-12), with a stricter bar, so that a clearly
better source can start a reversible trial two weeks earlier.

- **Interim pass (EARLY-RECOMMENDABLE)** for an arm against LAG, on the same population and target as the final:
  - its Spearman gain over LAG is **>= 0.06 in BOTH Week 4 AND Week 5** (twice the final bar, every week);
  - its MAE is not worse than LAG's in either week.
- **One look only.** No other interim read is made, and nothing is decided on Week 4 alone.
- **Multiplicity:** five arms (FP, LINESTAR, BLEND_LS, BLEND_FP; TabPFN stays descriptive). If more than one passes,
  the larger two-week mean gain is named and all passes are flagged.
- **What a pass allows:** the operator MAY trial that arm from Week 6 as the pre-lock ownership source (the ownership
  term's source; the sets file; the field sleeve's targets). It is a reversible in-season trial under adoption track v2,
  named with its rollback: revert to the incumbent source.
- O1 continues weekly to Week 7. **If the Week-7 final rule fails, the trial is rolled back.**
- A miss at the interim changes nothing; the final reads as written.
