# G2 QB-rooted upper-tail Gumbel factor protocol

Frozen 2026-08-12 CDT after G1's valid `stable-qb-hub-confirmed` result and
after active-only usage revalidation retained finite K, but before any G2
calibration-grid or held-out treatment metric is computed. G2 is score-free
until this dependence gate passes. This is a Gumbel *copula link*, not the
closed `N_GUMBEL` lineup-candidate generator.

## Immutable terminal identity

Bind every G2 run to:

- active cache `tabpfn_active_label_treatment_v2`;
- usage law `dirichlet`, exact `K=28.154043586960896`;
- evaluation panel `20260812-pitclean-e80-selected-tabpfn-active-v2`;
- historical splice `20260811-pitclean-e80-k1-role12union-a12ab31`;
- G0 v2 and G1 v3 report/manifest/protocol hashes;
- selected active-label usage comparison and protocol hashes;
- 45/55 model/market blend, 10,000 worlds, seed 0, and the accepted
  walk-forward 2023--2025 served-position schedule; and
- exact code and immutable image digest.

Any change to that cache, allocation law, marginal shaping, market blend,
served schedule or seed law invalidates G2 before an exact-80 result can be
transferred. The implementation must first reproduce G0/G1 control metrics to
`1e-12` and every terminal population/coverage invariant.

## Mechanism

For each `(season, week, team)` independently, use the same supported-QB rule
as G0/G1: a QB root exists only when exactly one QB has final-served mean at
least 4.0. Ambiguous or unsupported-QB team-weeks are unchanged; no starter is
chosen by outcome, projection, salary or depth chart.

Convert the QB and each same-team WR/TE's existing world draws to stable
mid-ranks in `(0,1)`. Keep the QB draws unchanged. For a receiver with role
parameter `theta`, treat its existing rank as the conditional innovation and
invert the bivariate Gumbel conditional CDF given the QB rank. Reassign that
receiver's original sorted draws by the new rank order. RB, DST, opposing-team
and cross-game rows are untouched.

The bivariate link is

`C(u,v)=exp(-(((-log u)^theta+(-log v)^theta)^(1/theta)))`, `theta >= 1`.

At `theta=1`, the conditional inverse is exactly the original receiver rank,
so the arm reproduces control. Values above one add upper-tail QB-receiver
dependence while retaining the accepted game/allocation structure in the
conditional innovations. This overlay is not claimed to be a fully
conditional-independent factor copula.

Every transformed row must be an exact permutation of its control draw
multiset. Require exact sorted-draw equality, exact unchanged non-WR/TE rows,
maximum row-mean drift at most `1e-10`, finite output, deterministic output,
and a nonzero changed-rank count when a selected theta exceeds one.

No RB loading is included because G1's QB-RB cell was inconclusive. No slate
factor is included because all three G1 cross-game controls were inconclusive.

## Parameter fit: early seasons only

Calibration seasons are exactly 2019, 2021 and 2022. Reconstruct their
accepted historical law from the immutable historical panel: canonical
PIT-clean TabPFN cache `tabpfn_projections_pit_v2`, its persisted allocation
law, common blend/seeds and no unrecorded served-position adjustment. Require
exact parity with the accepted historical player snapshots before fitting.

Choose `theta_WR` and `theta_TE` jointly from the Cartesian product:

`[1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.60, 2.00]`.

Use only authoritative player DK outcomes and the corresponding simulated
marginals; no lineup, candidate, selected-week maximum, contest rank, winner
or payout is read. On calibration team-weeks, build the exact G1 unique-QB
`QB_WR` and `QB_TE` directed pairs. Select the grid cell with the lowest
pair-count-weighted joint-q90 Brier across those two relationships. Break an
exact floating-point tie within `1e-12` by lower pair-count-weighted p=0.5
variogram, then lower `theta_WR + theta_TE`, then lower `theta_WR`, then lower
`theta_TE`. Persist every grid score before held-out evaluation. No grid,
bound, objective or tiebreak may change after the first calibration score.

## Held-out dependence evaluation

Evaluate control and the single fitted treatment only on 2023, 2024 and 2025,
using the exact 7,848-row/54-slate G1 population, its immutable archetype
labels and all 34,038 registered pairs. Recompute:

- all nine G0 co-exceedance/multiplicity cells;
- every G1 broad relationship, held-out-season fold and supported archetype
  cell;
- the G1 joint-q90 Brier and p=0.5 variogram by relationship; and
- topology diagnostics as disclosures only.

The primary scorecard excludes cross-game controls and uses these fixed
relationship weights: `QB_WR=3`, `QB_TE=2`, `QB_RB=1`, `WR_WR=2`,
`RB_RB=1`, `TE_TE=1`, `QB_OPP_QB=1`, `QB_OPP_WR=1`, `QB_OPP_TE=1`, and
`WR_OPP_WR=1`. For each metric, take the weight-normalized mean of the
relationship-level score (not pair-count weighting). Report deterministic
2,000-replicate paired whole-slate bootstrap intervals with seed 1703, but
under the operator's aggregate-tail objective an interval crossing zero is a
risk disclosure rather than an automatic veto.

## Frozen dependence gate

G2 passes only if all of the following hold:

1. every terminal reproduction and exact-marginal invariant passes;
2. at least one fitted theta exceeds one and eligible WR/TE rank ordering
   materially changes;
3. held-out treatment strictly lowers both the fixed-weight primary
   joint-q90 Brier and p=0.5 variogram versus control;
4. treatment strictly lowers the sum of absolute supported G0
   `log(simulated/realized)` cell errors and the fixed-weight sum of absolute
   supported G1 primary broad-cell log errors; and
5. treatment lowers absolute broad log error separately for both `QB_WR` and
   `QB_TE`.

All per-season declines, supported opposite-direction cells, bootstrap
intervals, multiplicity tradeoffs and topology changes are mandatory
disclosures but do not create an unregistered veto. A valid pass is
`g2-dependence-gate-passes`; any valid failure is
`g2-dependence-gate-fails`; missing support or failed invariants is
`g2-invalid-or-inconclusive`. No lineup is generated by this gate.

## Conditional exact-80 and diagnostics

Only `g2-dependence-gate-passes` licenses one separately frozen, same-image
paired exact-80 comparison. Its 2019/2021/2022 portion remains the identical
common historical splice; only held-out 2023--2025 control/treatment books
differ. The decision remains first nonzero treatment-minus-control selected
weekly-max count at `240,230,220,210,200,194,187`, then mean, with the full
decision-cost disclosure and no fabricated ROI.

That protocol must also create independently seeded selection and evaluation
world books (or an equivalent predeclared half split) so effective rank and
tail overlap are measured out of selector sample. Effective rank and paired
nonstationary EVT are mandatory diagnostics, not additional promotion paths.
A stable valid EVT contradiction to an empirical-grid pass requires an
explicit operator production decision. If G2 is selected, run the already
frozen bounded upstream/marginal revalidation cascade and rerun effective rank
on the final selected dependence law.
