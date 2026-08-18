# Overtime shared-duration mixture v2 — protocol (S2, DRAFT for operator freeze)

**Protocol ID:** `20260818-ot-shared-duration-v2`
**Status:** DRAFT — operator approved drafting (2026-08-18 decision b);
the ARM stays gated on the production-law dependence scorecard, which is
itself blocked behind the coherent chain's score-free harvest repair.
**Class:** dependence-only law mechanism; research module with NO
production call site until an arm passes its gates.

## Estimand — and why it is not the failed v1

v1 tried to PREDICT which games reach overtime (2022–24 spread/total
model; AUC 0.507 held out on 2025) and its licensing gate correctly
failed. v2 removes prediction entirely: every game is flagged OT in a
world at the frozen league base rate **p_OT = 14/272 ≈ 0.0515** (2025
current-rule regular season, from the frozen OT study), and flagged
worlds are rank-remapped so that game's players co-move upward while
every player's sorted marginal is preserved EXACTLY. The measured basis
is the same study's +23.77 skill DK points per OT game concentrated in
one game — a shared-duration co-boom the simulator cannot produce (no
overtime branch exists; a tied simulated game simply ends), while player
marginals already carry OT mass because they are fit on real outcomes.
This targets precisely the 210+ book-tail under-prediction (realized 6
vs expected 2.76) without touching any marginal.

## Frozen mechanism (implemented, offline-tested)

`research/ot_shared_duration.apply_ot_duration_mixture`: per game, in
deterministic sorted-game order from seed 20260818, draw world flags at
p_OT; for each variance player in a flagged game, add kappa = 1.5 draw
standard deviations in flagged worlds, then rank-remap onto the player's
own sorted marginal (stable ties). Marginal preservation is exact by
construction and enforced (`assert_marginals_preserved`, max sorted
delta must equal 0.0); constant rows (DST under the current law) and
keyless rows are byte-identical; p_OT = 0 is the identity. kappa affects
only how decisively flagged worlds occupy the marginal upper tail; it is
frozen here and may not be tuned on any outcome.

## Gates, in order

1. **Mechanism gate (score-free):** exact sorted-marginal preservation on
   real slate draws; same-game co-movement rises; cross-game rows
   byte-identical. (Already demonstrated on synthetic fixtures:
   `tests/test_ot_shared_duration.py`.)
2. **Dependence scorecard gate:** on the exact production-law worlds,
   the mixture must improve the scorecard's TAIL families (joint-q90
   Brier, multiplicity) — Addendum 115's lesson is frozen in: improving
   variogram averages while worsening tail Brier is a FAIL.
3. **Candidate/selection arm:** only after gate 2, one fixed-budget
   paired arm under the standing laws, reported with the full grid,
   paired weekly-max co-primary, and McNemar discordant slates.
   Predeclared two-sided risk: at fixed marginals the mixture THINS
   non-OT co-boom mass; the arm may lose shoulder counts while adding
   extreme-tail counts, and the operator's frozen utility decides.
4. **Adoption shape (N2, predeclared here):** if adopted, the repaired
   law enters as one or two of the five CBWU world blocks (mixture
   fraction from a small preregistered grid), never a wholesale swap —
   the selected book then covers both hypotheses about the world.

## Upgrade path

At the first live 2026 market window the already-planned bounded probe
for a regulation `h2h_3_way` Draw / explicit OT market runs; a real
market P(OT) may replace the base rate in a SEPARATELY frozen v3. No
in-house OT prediction model may ever gate this family again.
