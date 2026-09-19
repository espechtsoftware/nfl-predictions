# Week2 component gap: both means and centered distributions contribute

September18 overnight analysis. Same90 selected lineups, hash-pinned ThursdayD6400archive, noactual outcomes. Descriptive decomposition, not an adoption/calibration test.

The incumbent andhsim expected book maxima differ by19.713points. Symmetric two-factor mean-shift decomposition attributes12.734points to empirical mean differences and6.979points to centered-distribution differences. ForP220, the23.00percentage-point gap decomposes into12.805points associated with means and10.195points associated with residual distributions. This averages the two orders of substitution; it is not causal attribution.

| Means | Centered distribution | Expected book maximum | Model P220 |
|---|---|---:|---:|
| Imean | Iresidual | 190.3633 | 7.290% |
| Hmean | Hresidual | 210.0762 | 30.290% |
| Hmean | Iresidual | 202.6555 | 17.600% |
| Imean | Hresidual | 196.9010 | 14.990% |

The cross-centered distributions are diagnostic constructions, not proposed serving laws. They create negative player scores in some worlds and were deliberately not clipped, because clipping would also change their means and shape. No mixture weights or production centering were altered.

## Selected-player mean differences by position

| Position | Unique selected players | Mean hsim minus incumbent | Max absolute player difference |
|---|---:|---:|---:|
| DST | 9 | -0.8068 | 2.4269 |
| QB | 22 | -0.1197 | 13.4819 |
| RB | 28 | +2.1612 | 5.4500 |
| TE | 31 | +1.1183 | 2.7647 |
| WR | 52 | +0.9253 | 11.5909 |

The incumbent empirical means match served mean_projection to floating-point precision on selected players. Hsim does not: selectedRBs average+2.16points,TEs+1.12,WRs+0.93; QBmean differences vary substantially in both directions. The largest differences warrant tracing against the existing five-iteration upstream calibration and role-allocation logic. This does not establish a code defect or that forcing all means to agree improves outcomes. Coherent opportunity constraints may conflict with independently served marginal projections.

## Variation and dependence

Across90lineups, incumbent mean variance is580.0:408.35from marginal player variances plus171.65from twice within-lineup covariances. Hsim mean variance is781.32:677.41marginal plus103.91covariance. Thus the larger hsimbank dispersion in these selected lineups comes with larger marginal variances, not larger average within-lineup covariance. This is not a calibration result; cross-lineup dependence also influences portfolio maxima.

## Verification and precision failure

The initial invocation stopped at a declared baseline check. Summingfloat32storedplayers in float64classified2hsimworlds just below220 whereas the original float32sum rounded them to220. Those maxima were219.999999523 and219.999996185; mean maxima differed by<0.000003points. The mechanics amendment retained original float32lineup summation before float64diagnostic shifts. It did not relax the threshold or tune a result. Allbaseline counts then matched, and both additive decompositions summed exactly within1e-10.

Successful frozen source `c5d73628d362c4170a42495962b82b8f4e67644b`, clean tree, runtime 0.059s after downloads. Fiveinput hashes/generations verified;435players/90rosters/10000worlds percomponent. [Protocol and amendment](2026-09-18-week2-component-gap-protocol.md), [script](reviews/evidence/2026-09-18-week2-component-gap.py), [results](reviews/evidence/2026-09-18-week2-component-gap.json), [precision failure evidence](reviews/evidence/2026-09-18-component-gap-mechanics-failure.json).

Next: source-level calibration/role trace and independent replication. Do not treat the twenty-point gap as entirely a mean problem or entirely a tail problem, and do not change model weights solely from this one selected population.
