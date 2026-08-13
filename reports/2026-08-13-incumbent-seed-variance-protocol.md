# Incumbent Monte Carlo seed-variance protocol

Status: frozen 2026-08-13 before any new seed replicate exists. This is a
measurement of the incumbent's Monte Carlo variability, not a model arm and
not a historical adoption gate.

## Question

How much do candidate generation, 194-world coverage selection, and realized
weekly maxima vary when the accepted simulator is run with independent fixed
baseline and role-belief random streams?

The result supplies a noise envelope for future mechanism comparisons. It may
not retroactively promote, reject, or relabel any closed arm, including finite
K, active-only labels, position scaling, or direct role candidates.

## Frozen stack and panel

Use the exact selected terminal stack represented by accepted panel
`20260812-pitclean-e80-selected-tabpfn-active-v2`:

- seasons 2023, 2024, and 2025: 54 slates;
- one LightGBM ensemble member and active-only TabPFN cache
  `tabpfn_active_label_treatment_v2`;
- served position scales
  - 2023: `QB:.965,RB:.99,TE:.945,WR:1.03`;
  - 2024: `QB:.905,RB:.97,TE:.95,WR:1.06`;
  - 2025: `QB:.925,RB:.96,TE:.94,WR:1.04`;
- direct role belief with the exact six registered features, 12 role
  candidates, 40 boom candidates, no CE and no Gumbel candidates;
- finite Dirichlet usage `K=28.154043586960896`;
- 10,000 worlds, 194 coverage, $49,000 salary floor, and exactly 80 entries;
- unchanged 45/55 model/market blend, data snapshots, model training,
  candidate solvers, tiebreakers, and actual-score labels.

The accepted panel is replicate R0. Create exactly four new panels R1--R4.
Do not rerun R0 or substitute a newer cache/image based on results. The new
image may add only the explicit baseline-seed lever, provenance, validation,
and comparison code; its default seed 0 must reproduce R0 before the four
panels are licensed.

## Fixed seed pairs

The current path has two active sequential generators, so each replicate is a
fixed pair rather than a single ambiguous seed. R0 preserves the historical
incumbent exactly. R1--R4 were computed before execution as
`stream_seed(master, name) mod 2**32` using names `replay_projection` and
`role_belief`.

| replicate | baseline projection/simulator seed | role-belief seed |
|---|---:|---:|
| R0 | 0 | 7,331 |
| R1 | 1,137,260,708 | 2,690,847,602 |
| R2 | 2,875,959,182 | 1,630,284,992 |
| R3 | 253,722,715 | 3,374,646,876 |
| R4 | 1,643,280,042 | 3,977,633,467 |

CE seed 1701, Gumbel seed 4700, and member seed 8161 remain recorded but
inactive. Field simulation is not used to generate/select candidate portfolios
and remains fixed. No other seed may be tried if one of these results is
unfavorable.

## Mechanical gates

Before reading any outcome comparison:

1. a seed-0 one-week smoke must reproduce baseline projections/draws and the
   existing persisted seed identity exactly;
2. every panel has 18 slates per season, exactly 80 distinct selected rosters
   per slate, 10,000-world masks, complete labels, and one unique declared
   seed pair;
3. feature/player keys, point-in-time values, market means, served factors,
   caches, model specs, nonseed levers, and actual scores match R0 exactly;
4. R1--R4 must differ materially from R0 in simulated masks and candidate or
   selected membership; and
5. all four panels must finish and pass the same mechanical audit before any
   five-replicate tail count is computed. Operational logs may expose status,
   row counts, and exceptions only.

## Frozen report

For each replicate report:

- selected weekly-best counts at 240, 230, 220, 210, 200, 194, and 187;
- pool-oracle counts at the same thresholds;
- mean, median, standard deviation, minimum, and maximum weekly selected best;
- candidate count and selected support-count distributions at 187/194/200/210/
  220; and
- its 54 weekly selected-best values.

Across five replicates report:

- min, max, range, mean, and sample standard deviation of every selected and
  oracle tail count;
- for each slate, the max-minus-min weekly best across replicas and whether it
  exceeds 5, 10, and 20 points;
- all ten pairwise counts of weeks whose selected best differs by more than 5
  points;
- mean/median pairwise exact-roster overlap of the selected 80, using canonical
  player-id sets rather than candidate indices; and
- pairwise Jaccard overlap of the full candidate pools as a separate measure.

Do not average realized scores across seed replicas and present that as extra
historical weeks. The 54 slates remain the independent outcome units; seeds
measure algorithmic Monte Carlo sensitivity on those same outcomes.

## Interpretation fixed before results

For tail count ranges at 210, 220, 230, and 240:

- **stable:** every range is 0;
- **borderline:** the maximum range is 1;
- **materially Monte Carlo-sensitive:** any range is at least 2 weeks.

The same labels are diagnostic, not pass/fail adoption rules. A materially
sensitive result requires every future mechanism arm to report either a
paired multi-seed result or a justified effect larger than this incumbent
envelope. It does not prove that any earlier mechanism's observed difference
was caused by seed choice, because those treatments can change the RNG
consumption law itself.

Portfolio churn is reported continuously. No overlap cutoff is invented after
the result. For planning, overlap below 60/80 is flagged as high churn, 60--69
as moderate, and at least 70 as low; these labels do not determine adoption.

## Next branch

- If 220 masks and 220-first portfolios are unstable, benchmark more ordinary
  worlds first on a small frozen slate/candidate sample.
- Only if ordinary scaling is too costly may a stratified/antithetic estimator
  be designed. That future protocol must bind exact latent strata and masses,
  prove weighted marginal **and joint** event equivalence, and use weighted
  union coverage. It cannot reuse candidate-generation CE weights.
- If the envelope is stable, record the measured noise floor and close this
  question; do not use stability as permission to reopen old arms.

