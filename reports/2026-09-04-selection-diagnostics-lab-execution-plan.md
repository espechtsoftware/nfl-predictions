# Production-to-lab plan: diagnose where selection headroom is actually recoverable

**Date:** 2026-09-04  
**Status:** production execution plan for lab implementation  
**Source reviewed:** `../nfl2/reports/2026-09-04-selection-diagnostics-research.md` at lab commit `d6e4de3cdbb28f356ab0963388ad03d90d110e61`

**Correction accepted 2026-09-04:** Lab Update 65 supplied a brute-force
counterexample to the originally stated `K - t` marginal certificate. Section
5 now uses the valid top-`K` submodular upper bound. No sealed diagnostic had
run before this correction.

## 1. Objective

Determine, quickly and quantitatively, which of these statements explains the
remaining corpus-to-book gap:

1. the current greedy algorithm leaves material value available under its own
   simulated objective;
2. the algorithm solves its objective well, but the simulated distribution of
   the selected book maximum is miscalibrated;
3. the book-level law is broadly calibrated, but it ranks particular
   candidate phenotypes incorrectly; or
4. the model and selector are adequate and most historical regret is
   irreducible hindsight shock.

Every diagnostic must end in a routing statement. The goal is not a larger
catalog of charts; it is to identify the next score-bearing intervention and
stop spending experiments on mechanisms the evidence has closed.

## 2. Current state and sequencing

- The canonical historical exact-K80 mean weekly maximum remains **181.456**.
- In sealed experiment 095, redistributed supply contained 278 candidates at
  least 200 versus 222 in control, but `REDIST_DEMAX` selected only 46 of 278.
  The tested novelty selector did worse at that threshold and its primary was
  an UNPASSED_NEAR_MISS, so that law is closed.
- Work Package B has now routed **RESCUE_ELIGIBLE**: the binary beneficiary
  flag is associated with book-beating candidates on the sealed 095 cohort.
  Therefore PREREG-067 / experiment 096 is the exclusive immediate
  score-bearing route.

Experiment 096 must continue unchanged and keeps first claim on the score
lane. The diagnostics below run from already sealed artifacts and may proceed
in parallel on local or non-score compute. They must not change the frozen
096 dose, priority formula, arms, endpoints, or banks. Experiment 091 remains
held.

## 3. Shared diagnostic contract

Use the sealed 095 cohort first. Reuse 094 or 085 only as a separately labeled
replication where the same required identities exist.

All outputs must:

1. bind exact source, runner, reader, run, bank, candidate-pool, selected-book,
   decision-matrix, held-out-matrix, and settlement identities;
2. join settlement only by canonical `(season, week, roster_sha256)` with
   one-to-one checks;
3. preserve one row per `(season, week, bank, arm)` and never treat repeated
   banks of the same historical slate as independent seasons;
4. separate selection-world results from disjoint held-out-world results;
5. report bank and leave-one-season-out views, with season-clustered uncertainty;
6. label all outcome-open findings diagnostic/development-only;
7. publish machine-readable JSON plus a short interpretation report; and
8. make no live-policy, graph, UI, or experiment-launch mutation.

No new broad feature sweep is authorized. No diagnostic may promote an arm.

## 4. Package SD-A — book-maximum calibration (build first)

### Question

Does the simulated distribution of the **selected book maximum** describe the
realized book maximum honestly? This is the functional the selector is trying
to improve, and it is more decision-relevant than player-level marginal
calibration alone.

### Method

For every complete natural 095 arm-cell:

1. reconstruct the exact selected K80 book;
2. form the world-wise book maximum
   `M_w = max(score(candidate, w) for candidate in book)`;
3. compare the realized book maximum with the empirical distribution of
   `M_w`;
4. compute a tie-aware randomized PIT using the already implemented
   `nfl2.lawrepair.randomized_pit`, with the random draw deterministically
   seeded from the bound arm-cell identity;
5. use the disjoint held-out P_MIX matrix as the primary PIT whenever it can
   be exactly reopened or regenerated from its bound inputs; report the
   selection-matrix PIT only as an explicitly optimistic secondary view; and
6. compare predicted and realized exceedance frequencies at
   194/200/210/220/230, with calibration intercept and slope where supported.

Report one fixed 10-bin PIT histogram overall, by arm, by season, and for the
predeclared sign-separated groups already in the 096 plan. Do not create a
large phenotype grid. The inferential unit is the historical slate; banks are
repeated simulation realizations.

### Interpretation

- PIT mass near 0 means actual maxima are systematically below the simulated
  law: the book ceiling is overstated.
- PIT mass near 1 means the law understates realized book maxima.
- A U-shape indicates under-dispersion; a central mound indicates
  over-dispersion.
- Strong held-out miscalibration routes the next intervention toward a
  walk-forward law recalibration or dependence repair before another generic
  selector.
- Broadly adequate calibration with poor realized retrieval routes attention
  toward phenotype ranking rather than global spread changes.

Deliver `results/selection_book_max_pit_v1.json` and a concise report. This is
the highest-priority diagnostic and should be runnable within hours.

## 5. Package SD-B — optimization versus belief error (build second)

### Question

Is DEMAX failing because greedy search is materially suboptimal under the
same decision matrix, or because that matrix assigns the wrong values?

### Method

Reproduce the exact DEMAX greedy trace. At each greedy step `t`, compute the
remaining candidates' marginal gains under the same objective. Use
submodularity to construct an a-posteriori upper bound:

`UB_t = J(S_t) + sum of the largest K remaining marginal gains at S_t`.

The tightest valid `UB_t` across the trace bounds the best possible K80 book
under the same matrix and objective. The count is `K`, not `K - t`: an unknown
optimal K-set need not contain the greedy prefix `S_t`, so `OPT \ S_t` may
still contain as many as K elements. The previously drafted `K - t` variant
is invalid and must never be used as a certificate; at `t = K - 1` it can
collapse mechanically to the greedy value even when brute force proves a
better book exists. Retain that invalid quantity only as a clearly labeled
development/debug field if useful. Record:

- greedy objective `J(S_K)`;
- tightest upper bound and absolute/relative certificate gap;
- step-by-step marginal decay and the step where the tightest bound occurs;
- the realized maximum and corpus oracle as separate point-valued quantities;
- realized regret of the greedy book; and
- the realized score of any alternate same-objective book only as a
  hindsight diagnostic.

Do **not** subtract a simulated utility gap from realized DK points and call
the remainder belief error; those quantities have different units. Instead,
report the simulated optimization certificate beside realized regret. If the
certificate is loose on material cells, run an exact or MIP spot-check only on
a small deterministic hash-selected slate sample spanning all four seasons.
Do not choose the MIP sample by observed regret.

### Interpretation

- Tight certificates on nearly all cells mean more computation or a different
  solver cannot materially improve the **same** objective. That closes only
  search over the same matrix/objective—not future objectives, information,
  generators, or constraints.
- Material certificate gaps nominate one bounded exact-search comparison.
- Tight certificates plus large realized regret place the burden on belief
  calibration, information, and ranking; they support KG-5/phenotype work.

Deliver `results/selection_regret_certificate_v1.json`. Do the all-cell bound
first; invoke MIP work only if that bound is inconclusive.

## 6. Package SD-C — phenotype tail calibration (after SD-A/SD-B)

Build one combined calibration artifact instead of three disconnected tools.

### SD-C1: winner-range threshold-weighted CRPS

Use a single preregistered weight function supported on 200–260 DK points.
Score candidate predictive distributions against realized scores without
discarding sub-220 observations. Report overall and only for these fixed
groups:

- beneficiary-only;
- designated player rostered;
- boom family;
- leverage family; and
- all other candidates.

Deduplicate shared candidates within the stated comparison unit and use
slate-balanced aggregation so large candidate pools do not dominate. This
diagnoses which phenotype distributions are wrong; it does not choose a
candidate by itself.

### SD-C2: player-level randomized PIT

Reuse the existing randomized-PIT implementation. Audit the smallest useful
group set: position, modeled participation designation, linked beneficiary,
and ordinary control. Separate the inactive atom from active-performance
calibration. If exact player-world and roster membership cannot be recovered
from a sealed artifact, stop with an explicit unavailable-input receipt; do
not silently regenerate it under changed code.

### SD-C3: top-of-ranking trust

Add one top-weighted ranking summary only if it is cheap. Static RBO is not a
complete description of a set-aware greedy selector because marginal rank
changes with the current book. Prefer top-K recall of realized book-beaters
and the rank/marginal value at each candidate's first loss; RBO may be a
secondary summary with one fixed persistence parameter, not a model-selection
grid.

### Routing

- Global miscalibration in SD-A plus the same directional player error in
  SD-C supports one walk-forward marginal/dependence recalibration experiment.
- Calibration concentrated in beneficiary/designation groups supports a
  participation-specific correction rather than a global law change.
- Adequate calibration but poor top-rank recall supports a learned reranker
  such as the prespecified 097 family after 096, subject to a new explicit
  production nomination.

## 7. Package SD-D — later refinements, strictly gated

### Rescue dose-response

Do not use a newly computed curve to change experiment 096: its eight-seat
dose was fixed before the WP-B result. After 096 seals, one reader-side curve
may report held-out simulated and realized gain as the number of eligible
swaps increases. It is development evidence for a separately named fresh-bank
successor, never retrospective authority to relabel the tested dose.

### Group-conditional conformal analysis

First run a support census by season and group. Reuse the existing production
`OnlineConformalCalibrator` or the existing lab PIT-remapping machinery where
their contracts fit; do not create another calibration framework. Ordinary
Mondrian conformal intervals provide groupwise coverage under their stated
exchangeability conditions—they do **not** directly provide calibrated
`P(candidate >= threshold)` values. Any numeric tail-probability feature needs
a separately valid conformal predictive-distribution method and prospective
validation before it can enter a selector.

If group support is insufficient, use the declared fallback hierarchy and
emit `INSUFFICIENT_SUPPORT`; do not weaken the group or coverage rule after
viewing results.

## 8. Week-1 capture additions

The live capture package should retain enough data to repeat these diagnostics
prospectively:

- immutable entered and shadow books plus exact selection ranks;
- candidate and selected-book held-out exceedance forecasts;
- actual entry count, contest id, fee, final rank, payout, and duplication;
- actual player participation/status at settlement, separate from pre-lock
  probability and source timestamp;
- beneficiary-to-designation links used before lock; and
- per-bank selected-book metrics so bank-variance/ICC can be reported.

These are additive capture fields. They do not change Week-1 selection.

## 9. Lab execution order and time budget

1. **Immediately:** implement/freeze 096 from the already prespecified
   PREREG-067 route and return its launch contract. This is the score path.
2. **In parallel, same day:** implement SD-A and SD-B against fixtures, then
   run them on sealed 095 artifacts. Target one combined interpretation within
   24 hours.
3. **Next day:** implement the combined SD-C artifact only after reading
   SD-A/SD-B. Reuse existing PIT and calibration code; no feature sweep.
4. **After 096 seals:** decide whether the evidence nominates the final 2×2,
   a separately authorized 097 learned reranker, or a calibration repair.
   Only one new score-bearing route proceeds at a time.
5. **Before Week 1 lock:** verify the additive capture fields. SD-D research
   never blocks entry-book or standings capture.

## 10. Required response from the lab

Return one short implementation note containing:

1. whether the exact held-out book matrices can be reopened for SD-A;
2. whether the DEMAX trace exposes enough per-step marginal values for SD-B
   or must be deterministically replayed;
3. the proposed machine-readable schemas for the two first-day outputs;
4. expected local/cloud runtime and memory;
5. any conflicting identifier, unavailable sealed input, or invalid bound;
6. the separate 096 launch-contract status.

Do not respond with UI work, a generalized diagnostics platform, a new graph
schema, or extra score arms. The first useful answer is a book-max PIT and a
same-objective greedy certificate, followed by the already routed 096 score.
