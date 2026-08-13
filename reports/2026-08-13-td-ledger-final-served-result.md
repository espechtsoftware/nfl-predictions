# TD-ledger final-served dependence result

Frozen score-free execution `td-ledger-final-served-v1-pb4fh` completed
cleanly on 2026-08-13 from source `55451fbed7f2bbfd37da3f48ae4f124afc69cafa`
and immutable image
`sha256:58f70494f6da7647d871e11f800306f5883093dd6b48164d84b906dd1e0493a9`.
The machine report is under
`reports/td-ledger-runs/20260813-td-ledger-final-served-v1/`.

## Disposition

The frozen disposition is **`td-ledger-invalid-or-inconclusive`**. It does
not license an exact-80 lineup comparison and does not change production.

The result is inconclusive for one mechanical reason: final-served treatment
draws did not preserve every player's exact sorted marginal multiset. Maximum
control/treatment player-mean drift was `3.814697269177714e-06`, above the
registered `1e-10` limit. Frame alignment, actual outcomes, deterministic
treatment replay, terminal cache/schedule/usage identity, finite output and
control G0/G1 reproduction all passed. The treatment changed 15,396 player
rows and 145,894,837 world cells.

This is not a scientific rejection. The invalid/inconclusive branch of the
frozen protocol requires diagnosing the marginal-preservation failure without
using lineup outcomes. Do not waive the invariant or inspect lineup scores.
Determine whether the observed `2^-18`-scale maximum drift is caused by a
precision/order-sensitive remapping operation. Any repair must be general,
mean/marginal preserving, default-path safe and validated independently before
the same frozen score-only gate can be rerun.

## Score-free directional evidence

Every substantive frozen gate moved in the desired direction, and the
material-regression guards passed:

| Metric | Control | TD ledger | Change |
|---|---:|---:|---:|
| Joint-q90 Brier | 0.018490246 | 0.018469340 | -0.000020905 |
| Variogram p=0.5 | 1.434919238 | 1.429139059 | -0.005780179 |
| G0 absolute-log-error sum | 3.312852040 | 3.007414088 | -0.305437952 |
| G1 weighted absolute-log-error sum | 6.944176960 | 6.201834706 | -0.742342254 |
| QB-WR absolute log error | 1.138372886 | 1.002459046 | -0.135913840 |
| QB-TE absolute log error | 0.787419984 | 0.651343809 | -0.136076175 |
| WR-WR absolute log error | 0.153670142 | 0.145812415 | -0.007857727 |
| RB-RB absolute log error | 0.382712783 | 0.377899659 | -0.004813124 |

The paired whole-slate bootstrap intervals exclude zero in the favorable
direction for both primary proper scores: joint-q90 Brier treatment-minus-
control CI95 `[-0.000032807, -0.000010461]`; variogram CI95
`[-0.007321592, -0.004279678]` over 54 slates with 2,000 replicates and seed
1703. These values are diagnostic evidence only while the exact-marginal
invariant remains unresolved.

## Next action

Instrument the final-served pipeline at the post-TabPFN, post-market-shift and
post-position-scale boundaries and compare sorted player marginals using
float64/ULP diagnostics. Reproduce the failure in a score-free Cloud job. If
the problem is a shared numerical implementation defect, fix it with unit
tests proving exact marginal preservation and default-output safety, run full
validation, then rerun this unchanged gate. If the ledger intrinsically
changes final marginals, the mechanism fails the frozen premise and closes.

The first diagnostic isolated a general defect in the shared market-shift
helper: it reduced float32 draw matrices in float32. Because floating
summation depends on order, rank-permuting an identical marginal could change
its computed mean by `2^-19`/`2^-18`, after which the helper shifted every
world by that artifact. The shared final-served transforms now use a
deterministic float64 row mean over the sorted marginal values. That definition
depends only on the marginal multiset rather than world order and is used for
market blending, live projections, global/position spread scaling and the
diagnostic position scale. Deterministic regression constructions prove that
two float32 permutations with unequal native float32 means finish the complete
shift plus position-scale chain with bit-exact identical sorted marginals.
Fifty-one focused blend, position-scale, served-tail and TD-ledger tests pass.
This is a general numerical repair, not a gate waiver; full validation and a
new immutable score-free rerun remain required.
