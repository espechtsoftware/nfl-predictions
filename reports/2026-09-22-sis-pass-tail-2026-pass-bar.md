# SIS pass-tail 2026 — pass bar (frozen 2026-09-22, before any graded outcome)

Operator decision 2026-09-22: keep the SIS subscription only if it helps, and grade the one SIS
mechanism still open. This document adds the decision rule that
`reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md` left open ("any adoption requires the
full preregistered 2026 evidence or a separately frozen rule written before the relevant outcomes").
Everything else — arms, seeds, cache law, acquisition, identities — is that protocol, unchanged.

## Why this is not retrospective design

The 2026-09-22 dormant ruling objected that a gate written now would be chosen with two weeks of 2026
outcomes visible. The objection does not reach this rule: the SIS pair has **never run** (no control or
treatment book exists for any 2026 week), and it grades **Weeks 5–18 only**, none of which has been played.
No outcome of either arm can have informed a threshold below. The thresholds follow the protocol's own
reporting list and the program's standing tail-line (194).

## Graded unit

- Eligible Sunday-main target weeks 5–18. A slate is **complete** only if all five registered seed pairs
  × both arms produced exact-80 books from one identity, persisted create-only before lock. Anything less
  is incomplete and not scored (protocol: "any identity drift or partial five-seed/arm grid invalidates
  that snapshot"). An ineligible week is an explicit no-run.
- Seed-slate: one seed pair on one complete slate. Per arm, record the book's realized maximum.

## Support floor

At least **10 complete slates**. Fewer → **NO VERDICT**; the renewal decision is then made on other
grounds and this mechanism is not cited either way.

## Decision (read once, after Week 18 is scored)

**PASS** requires all four; anything else is **FAIL**.

1. **Tail clears.** Σ over complete seed-slates of [treatment max ≥ 194] − [control max ≥ 194] **≥ +3**.
2. **Breadth.** Calendar slates where treatment clears more seeds than control **exceed** slates where it
   clears fewer.
3. **No mean cost.** Season mean of the per-slate mean maximum (over seeds): treatment − control **≥ 0**.
4. **Not one slate.** Removing the single slate with the largest treatment − control clear difference
   leaves criterion 1 **≥ +1**.

Reported alongside, never decisive: counts at 240/230/220/210/200/187, exact-80 and candidate overlap,
source coverage, operational failures (the protocol's list).

Interim reads at Weeks 8 and 13 are descriptive only and cannot pass, fail or stop the gate.

## What a result means

- **FAIL** is decisive for this mechanism: the SIS pass-tail fields do not earn a place, and they cannot
  justify the SIS renewal.
- **PASS** is necessary, not sufficient. The pair runs the protocol's frozen August policy
  (`classic-k1-role12-boom40-…`), not the live boom-160 / lev-40 dual expected-max path. Adoption would
  need one live-policy confirmation arm frozen before its outcomes. A PASS does justify renewing SIS long
  enough to run it.

## Arming

Nothing can run before Week 5 (four completed games of SIS context). Required, in order, each week from
Week 5: the operator's Wednesday SIS acquisition (`weekly_vendor_data`, Weeks 1–4 backfill for target
Week 5, then W−1), then `s-tabpfn-sis-pass-tail-control` / `-treatment` (Thursday), then
`s-shadow-sis-pass-tail-paired` (Sunday 06:00 CT). The three schedulers are resumed on or before
**Wednesday 2026-10-07**. `scripts/check_prospective_gates.py` now carries this gate: it warns in Weeks 3–4
if they are paused and fails from Week 5.
