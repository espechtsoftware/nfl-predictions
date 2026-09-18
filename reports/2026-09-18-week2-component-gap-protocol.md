# Week2 component-gap decomposition: fixed selected book, no outcomes

Frozen September18 before this decomposition's calculations. Follows independently observed
K90P220~7.29%vs30.29%, meanmax~190vs210. Purpose: determine whether empirical player means or
centered joint distributions account for this difference. No component accuracy/adoption verdict.

Inputs: exactfive hash-pinned Week2 archive objects from week2-archive-preflight.json; frame read
allowlist id/position/mean_projection/proj; candidate allowlist players/book_rank. Keep originalK90
book fixed, retain original order. Read incumbent andhsim player matrices, not actuals or historical
result tables. Projection columns are prelock model inputs; no new vendor calls.

For each player's two archived arrays define empirical means mI,mH and centered residuals RI,RH.
Evaluate four diagnostic distributions on the SAMEbook: mI+RI (incumbent),mH+RH (hsim),mH+RI,mI+RH.
The crosses are additive mean-shift diagnostics, may yield negative player scores, and are not valid
new serving policies by assumption. Do not clip: that would change both means and residuals.

For expected book maximum andP220 separately, report all four values and symmetric two-factor
attribution: means=0.5*[(F(H,I)-F(I,I))+(F(H,H)-F(I,H))]; residuals=0.5*[(F(I,H)-F(I,I))+
(F(H,H)-F(H,I))]. Sum must equalF(H,H)-F(I,I) within1e-10. This averages two decomposition orders;
it is descriptive, not causal and not a calibration test. Residual term includes marginal variance,
skew and cross-player dependence; it does not isolate any one of those.

Also report mean/median/maxabs per-player differences between components byposition, and against
served mean_projection andproj, wherefinite. Report selected-book players and entireframe separately.
No names/individual player scores in public tracked evidence. Check raw component book means match
the already publishedK90mixture~200.2197586 within1e-4 andP220componentcounts within1world of earlier
mixedprecision diagnostics. If mismatch exceedstolerance, report mechanicsfailure before interpretation.

Report variance decomposition of each selected lineup: sum of per-player marginal variances and
remaining twice-covariance contribution, summarized across90. Descriptive same-world covariance,
not identification of correct dependence. Report mean expectedscore perlineup and residual-bookmax
lift above highest lineup mean for each component. No selector changes or mixtureweight tuning.

Full-byte SHA/generation verification required. Singleprocess/1BLASthread,compute60sec cap after
networkdownload,512MiBworkingarrays,wall5min. Freeze executable before read. All fixed outputs
reported regardless of direction. Next test must address the observed mechanism, not assume means
or tails caused the difference before this census.

## Mechanics amendment, before attribution results

First run7a409181 stopped at the declaredHsim threshold-count agreement check. A narrow precision
check found float64 summation gives3027hits while the previousfloat32 lineup summation gives3029.
The two differing maxima are219.999999523 and219.999996185 in float64 but220.0 in float32. Incumbent
count729 agrees. Component meanbookmax differs by<0.000003points. Thus this is numerical boundary
classification, not a roster/model mismatch. No attribution or position/variance results were read.

Preserve the original raw-selector diagnostic's float32 player-to-lineup summation, then cast the
lineup matrix tofloat64 for mean-shift evaluation. Per-player empirical means and additive shifts
remain float64; crossings are explicitly diagnostic. No threshold tolerance is enlarged and no
classification is tuned to an expected effect. The two unchanged baseline components must now match
the original counts. Precision evidence retained separately; original failed invocation disclosed.
