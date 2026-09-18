# E0b: candidate-count sensitivity, known-law standalone selection

September 18, 2026. Separate exploratory synthetic study following review 88db03f. Frozen before
its full run. No NFL outcomes or live lineup changes. Original E0 remains unchanged.

## Review disposition

Agree: finite-sample selection optimism exists under a correct law, and twelve candidates cannot
calibrate optimism when selecting among thousands. Add the candidate-count axis before a real-pool
performance pilot. Disagree with a stronger interpretation: a synthetic sweep at matching nominal
counts cannot determine whether noise dominates real NFL error. Effective candidate dependence,
quality gaps, tail shape, K and the generation mechanism matter. Nor does a finite independent audit
exactly recover truth; it is unbiased conditional on the fixed selected book, with sampling error.

This bounded study isolates the strongest standalone choice (K=1). It does not simulate K80 selection,
legal rosters, production candidate dependence or candidate generation from decision worlds. K=1 has
an exact truth optimum even at 12,560 candidates. Do not claim an exact large-K optimum that cannot
be enumerated cheaply. The K1 scope is deliberate and recorded before results.

## Fixed construction

64 binary states as in E0. Two laws: six independent Bernoulli variables with p=.5 or p=.1.
Nested candidate counts 12, 100, 1000, 3200, 12560. Fix 10,000 decision worlds and 10,000 independent
audit worlds per replicate, 100 replicates. The 10,000 count matches the archived bank dimension;
it has NOT been independently verified as today's universal production world count.

Generate coefficient arrays once, before decision sampling, with PCG64 seed 2026091801: 12,560 by
6 iid standard-normal coefficients, then 12,560 independent uniform[-5,5] quality offsets. Coefficients
and offsets are shared across the laws. Persist hashes, RNG/version, and exact generation algorithm.
No data-dependent filtering, redrawing or parameter tuning.

For each law let x_j=(z_j-p)/sqrt(p*(1-p)); each candidate's state score is
160 + (18/sqrt(6))*sum_j coefficient_ij*x_j. Subtract the exactly weighted mean of the random term
per candidate to eliminate floating-point centering error. Two arms: FLAT adds zero quality offset;
GAPS adds the fixed quality offset. Thus true mean is 160 for FLAT, 160+offset for GAPS. Covariance
comes from six shared factors, so candidate count is not independent opportunity count. Coefficient
norms vary: larger pools can contain more volatile candidates. Disclose this as part of this construction,
not a pure count-only general law. These are arbitrary synthetic score units, not calibrated NFL scores.

Decision and audit state counts use separate SeedSequence([2026091802,law,replicate,stream]) RNGs,
stream 0/1 respectively. Draw multinomial counts of 10,000 iid states; weighted averages are exactly
equivalent to explicitly materializing those states. All candidate prefixes and both quality arms share
these paired samples. Generation randomness is independent. Break ties within 1e-12 by smallest ID.

## Outcomes and checks

For every selection record ID, true mean, exact best mean in prefix, true regret, decision estimate,
audit estimate and both estimate-minus-truth errors. Also record errors for a fixed candidate (ID 0)
as a nonselected reference. Summaries: mean, median, 5th/95th replicate quantiles, Monte Carlo SE;
paired 12-to-12560 changes and every intermediate prefix. No monotonicity claim or adoption gate.
FLAT true regret is identically zero despite possible selection optimism; report that openly.
GAPS permits a distinction between estimation optimism and foregone true value.

Mechanics: probability normalization; score means equal declared means; positive exact regret within
roundoff; nested maximum decision estimate cannot decrease (per law/arm/replicate); flat regret zero;
independent stream identifiers. Recompute selected values by direct sums as a separate internal check.
Single process, one BLAS thread, five-minute runtime cap, working arrays <512 MiB; no cloud execution.
Freeze code before full run. Independent review pending, per operator's instruction to continue.

## Routing

Report all cells irrespective of sign. Results can motivate instrumenting decision-versus-independent
estimates on an actual fixed pool; they cannot estimate real-world dominance or justify money-path
changes. Real-pool work still requires verified player order and independent same-law audit generation.
