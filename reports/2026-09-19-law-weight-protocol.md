# Historical whole-law weighting: frozen predictive-quality screen

September 19, before construction of the study banks or any new calibration read.
The laptop owns this protocol and its first read. This is an exploratory development
screen, not fresh confirmation, a lineup outcome read, or a release authorization.

## Question and prior evidence

Can a single weight learned from earlier seasons improve the predictive distribution
over the current equal mixture of incumbent I and hierarchical H? The new dimension
is the mixing weight learned by a proper score, not marginal remapping or transplanting
dependence. Whole simulated slate states retain their model identity and internal
player dependence. No player-specific or position-specific mixture is assembled.

Lab 049b calibrated old H versions; its strongest v0.13 conclusions preceded the
spread repair. Experiment 069 collected incumbent PITs, not paired I/H score terms.
PREREG-046/076 found a strong interaction between marginal and dependence changes,
with the intact equal mixture outperforming the surgical variants. Those results
motivate preserving each law intact; they do not establish that learned weights help.

Forecast-combination research supports evaluating weights with proper scores, but
uses several distinct aggregation definitions. Our method is an elementary CDF
mixture, not the quantile aggregation algorithm in [Berrisch and Ziel](https://arxiv.org/abs/2102.00968).
[Gneiting and Ranjan](https://arxiv.org/abs/1106.1638) analyze calibration and dispersion
of forecast pools. Better distribution accuracy need not improve a downstream
decision: [Nitka and Weron](https://arxiv.org/abs/2308.15443) demonstrate that distinction
in electricity bidding. None of these sources is evidence of NFL lineup efficacy.

## Fixed population and forecast construction

The outcome-blind [support census](reviews/evidence/2026-09-19-law-weight-support.json)
authenticates eight cached benchmark files against the existing manifest's byte
counts/CRC32C and records SHA256s. It finds 89 slates, 40,387 players and 15,093
pre-lock rows with mean projection >=5, across 2019/2021/2022/2023/2024. Each slate
has eligible QB/RB/WR/TE/DST support. No current outcomes were read for that census.

Use all 89 slates and both full player laws at source lab `2dc116c`. Historical
game inputs retain the unchanged benchmark path. I uses K1, corrected mean centering
and the existing component/TabPFN shaping; H uses its ordinary upstream calibration.
No target prior, mean repair or new feature is fitted. All model fitting uses seasons
strictly before each forecast season, under the existing physical outcome firewall.
Current-season actual/y_/participation labels must be all missing in constructed
frames, then omitted from saved frames. No 2025 or bank991 access.

Two bank pairs: I seeds `slate_seed(19260901,S,W)` and `slate_seed(19260902,S,W)`;
H uses bank identifiers 19261001/19261002 respectively. Each component has 4,000
worlds. Store both full matrices and safe frames before the separate scoring stage.
Both laws within a run share the exact runtime/input build. Independent seed pairs
also vary H's upstream calibration pilots; they are not independent NFL observations.

The earliest-slate local mechanics check (2019-W1, 1,000 worlds, first pair) passed
in 9.515 seconds. Its labels were inaccessible. A Cloud Build smoke will exercise
the same path in the pinned cloud runtime before the full forecast construction.
The read below will also be checked end-to-end with an entirely synthetic panel.

## One treatment and one primary

2019 seeds the weight; evaluation seasons are 2021/2022/2023/2024. For target S,
fit one I weight lambda from all strictly earlier study seasons, using both banks.
Take each skill position's eligible-player mean CRPS within a slate, average the
four positions equally, then average slates equally within seasons and seasons
equally. DST is a declared secondary because I's static DST law would otherwise
dominate a weight intended to resolve skill-player disagreement. No realized
participation filter; missing actuals are excluded and counted, never set to zero.
Require each slate/skill-position cell to retain at least one settled eligible row.

For empirical CRPS A=score(I), B=score(H), M=score(equal mixture), compute
`D = 2*(A+B-2*M)`. The exact mixture score is
`S(lambda)=lambda*A+(1-lambda)*B-lambda*(1-lambda)*D`.
After the declared averaging, use `clip((D+B-A)/(2*D),0,1)`; use 0.5 if D<=1e-12.
Require D>=-1e-8 before clamping numerical noise. This is the exact quadratic
minimum, with no grid, regularization search, position weights or tail threshold tuning.

Primary: learned minus equal-mixture CRPS, with the same season/slate/position
weighting. Report both banks separately, all four seasons and every position.
Uncertainty: 10,000 paired bootstrap replicates, resampling slates within each
season with seed 20260919, retaining paired banks and the already learned weights.
This describes held-out score variation conditional on the training fits; it does
not include weight-fit uncertainty or establish fresh confirmatory significance.

Advance to a separately frozen lineup-transfer study only if the primary difference
is negative in both banks, negative in at least three of four seasons, and its 95%
bootstrap upper bound is below zero. Otherwise report the failure and do not search
for a different weighting rule on these outcomes. Single treatment, one primary;
no multiplicity claim for descriptive secondary metrics.

Secondary: the same CRPS at DST and by skill position; Brier and predicted/observed
rates for >=20/30/40; tail-weighted CRPS above20 (equivalently CRPS after mapping
X and y to max(value,20)); whole-population support/missingness. Report I, H, equal
and learned mixtures. These do not select a new weight. No lineup maxima, 220+
events, candidate ranking or selection results are read in this stage.

## Compute and stop conditions

Use a pinned existing lab image as a Cloud Build compute step with exact source
overlay and benchmark content checks. No shared Cloud Run job changes, live warehouse
writes, timer changes or deployment. Smoke first, then a maximum 3,600-second full
construction; budget <$5. Forecast artifacts use a new create-once GCS prefix.
Runtime/version and source hashes are recorded; local smoke is mechanics evidence,
not an exact cloud numerical replay claim. Stop on any source/input, shape, finite
value or current-label firewall failure. Publish negative and failed runs as well.
