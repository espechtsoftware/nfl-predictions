# Paid Metric and Market-Source Accuracy: Lab Execution Plan

**Date:** 2026-09-03  
**Audience:** lab and production teams  
**Status:** proposed compact diagnostic followed by one conditional historical comparison  
**Purpose:** determine which pre-lock player metrics and market sources forecast
player scoring and extreme outcomes, then determine whether that information
improves the lineups selected from a fixed corpus.

## 1. Executive direction

The program should know how its player metrics relate to scoring and which
market sources are most accurate. It currently knows this only partially.

Run a compact two-stage study:

1. Build one point-in-time player-week source and metric scoreboard.
2. If it finds credible incremental information, run one frozen
   `generation fixed / selection varied` comparison on the D800 candidates.

If player-tail forecasting improves but selection does not, move the signal
upstream into one later generation comparison. Do not tune a large grid of
bookmaker weights or lineup rules. The adopted 45% model / 55% market blend
stays unchanged while this work runs.

This is additive. It must not delay Week 1 capture, change an active
experiment, reopen held experiment 091, or alter paid-entry behavior.

## 2. Current evidence

### Market information

The legacy blend comparison reported player-point MAE of 4.664 for the 45/55
blend, 4.909 for model-only, and 4.786 for market-only. This is useful prior
evidence, not a current final estimate: it predates the common-lock correction.
Some historical late-afternoon player props had used snapshots after the
shared Sunday-main lock. The corrected comparison must use the latest snapshot
strictly before that common lock.

The current `market_points()` code de-vigs by bookmaker and then averages books
within each market. Raw rows retain `bookmaker`, `market`, line, price, and
`snapshot_ts`, so books can be compared without changing production scoring.

### Paid player metrics

The incumbent model already consumes opponent CB/DB aggregate concessions and
a top-CB-out flag. Fantasy Points route-share fields are materialized but are
candidate features unless activated. SIS defender/alignment data is primarily
research evidence.

The latest F3 diagnostic found these mean within-slate associations with
realized lineup score:

| Feature | Mean rho | FDR result |
|---|---:|---|
| Participation designation count | -0.1186 | Passed |
| Fantasy Points route-share jump | +0.0744 | Passed |
| Position-matched points allowed | +0.0699 | Passed |
| Fantasy Points trailing route share | +0.0561 | Passed |
| Receiver separation | +0.0552 | Passed |
| CB yards per target allowed | +0.0383 | Did not pass |
| Top CB out | +0.0324 | Did not pass |

No F3 feature survived the separate rescue-relevance screen for rare
high-scoring candidates missed by the incumbent selector. This supports a
small conditional model, not a one-feature lineup-ranking rule.

## 3. Receiver/defender role mapping

The user identified an important, potentially stronger data seam: a source may
state that a defender usually covers the opposing WR1, WR2, slot receiver, or
another role. We independently construct pre-lock WR1/WR2/WR3+ roles and
Wide/Slot shares. If the source is present and historically point-in-time, the
two can be joined into a **role-conditioned expected matchup exposure**.

Existing research tables already provide:

- pre-lock offensive `WR1`, `WR2`, and `WR3+` roles;
- opponent concessions to those roles;
- receiver Wide/Slot shares;
- individual defender Wide/Slot performance and workload; and
- the top one/two defenders by prior workload within Wide and Slot.

Current SQL generally averages the top-two workload defenders for the
receiver's dominant alignment. It does not preserve a mapping such as
`defender A -> WR1`, `defender B -> WR2`, or `defender C -> slot`. That is a
real opportunity if the retained paid source contains it.

Before modeling, audit the raw Fantasy Points, SIS, and coverage-map exports
for fields equivalent to:

- defender primary alignment (`outside-left`, `outside-right`, `slot`);
- usual opposing receiver role (`WR1`, `WR2`, `slot`, side-based, or no
  shadow role);
- shadow/travel rate or expected coverage share;
- sample size and prior-games window; and
- target-week projection versus retrospective description.

If supported, emit candidate defender exposures for each receiver with:

- `receiver_role_prelock` and its support;
- `receiver_wide_share` / `receiver_slot_share`;
- `defender_id`, quality, workload, and availability;
- `assignment_basis` (`vendor-role`, `vendor-shadow`, `alignment-workload`,
  `side-only`, or unsupported);
- `expected_exposure_weight` and its support/window; and
- source timestamp and target week.

Use the weighted defender mixture in the scoring diagnostic. Keep role-based
expected exposure distinct from observed route-by-route coverage. A valid
vendor statement that a CB usually takes WR1 is actionable evidence, but it
is not the same claim as observing that he covered the named receiver on 65%
of that game's routes.

## 4. Questions

1. Which bookmaker or consensus best forecasts each player statistic?
2. Which source best forecasts total DraftKings points for covered players?
3. Which source best calibrates 20+, 25+, and 30+ player outcomes?
4. Which pre-lock snapshot horizon is most useful?
5. Does line movement or book disagreement add ceiling information?
6. Do spreads, totals, and implied team totals add player/stack-tail value?
7. Which paid metrics explain residual scoring after incumbent projections?
8. Does role-conditioned defender exposure outperform team/alignment context?
9. Does any of this select stronger lineups from the same D800 corpus?

## 5. Source families and proper targets

| Source | First target | Secondary use |
|---|---|---|
| Player props by bookmaker | Corresponding realized statistic | Implied DK points and boom probability |
| Mean/median book consensus | Statistic and DK points | Stable market baseline |
| Alternate prop ladders | Statistic-tail probability | Ceiling and uncertainty |
| Spreads/totals | Team points, game points, margin | Game/stack environment |
| Internal projection | Player DK points | Residual baseline |
| FP route/alignment | Residual receiving output | Role/matchup component |
| SIS defender/alignment | Residual receiving output | Defender vulnerability |
| Role/shadow coverage map | Receiver residual/tail conditional on role | Expected defender mixture |
| Participation state | Probability active and workload | Availability/downside |
| DK salary/DK PPG | Player DK points | Reference fallback |

Game odds and player props must not be compared against incompatible outcomes.
Each is first judged on what it directly predicts.

## 6. Frozen observation contract

Use one `(season, week, slate_id, player_id, source, snapshot_horizon)` row.
Preserve position, team, opponent, game, salary, market availability, and
matchup support.

For each slate, derive the earliest domestic Sunday-main kickoff. A source is
eligible only if its timestamp is strictly before that shared lock. Fixed
Friday, Sunday-morning, and latest-before-lock views may be compared only when
the archive honestly supports them.

Every release must identify source objects/tables, extraction code/query,
hash or immutable snapshot, bookmaker/market, source timestamp, slate lock,
identity-map version, actual-score source, and missingness reason. No outcome
enters the frozen feature artifact.

Props are posted selectively. Report both covered-cohort accuracy and
full-slate policy accuracy with declared fallbacks. Show coverage by season,
week, position, salary band, source, and market.

## 7. Work package A: source and metric scoreboard

This is the fast first read and requires no lineup generation.

### Preserve bookmaker forecasts separately

1. De-vig two-way over/under pairs within bookmaker and line.
2. Convert each book/market forecast with the existing frozen conversion law.
3. Apply the same disclosed anytime-TD hold approximation when only one-way
   odds are available.
4. Create equal-book mean, median-book, and trimmed-mean consensus forecasts.
5. Do not fit bookmaker weights in this package.

For game odds, compute spread, total, and implied team points at the same
cutoff. Judge them first against game/team outcomes.

### Source leaderboard

Report:

- coverage and missingness;
- MAE, RMSE, and signed bias;
- within-slate rank correlation;
- 20+/25+/30+ Brier score and calibration when probabilities exist;
- performance by position, salary, season, and snapshot horizon; and
- paired source differences with slate/week as the resampling block.

Do not treat player rows from the same slate as independent observations.

### Paid-metric ledger

Create one row per metric containing:

- source, meaning, and grain;
- timestamp and point-in-time eligibility;
- historical support and missingness;
- unadjusted within-slate association with actual scoring;
- association with `actual_points - incumbent_projection`;
- association with 20+/25+/30+ outcomes;
- stability by position and season;
- incremental value conditional on incumbent and market forecasts;
- rescue relevance on candidate-lineage labels; and
- disposition: baseline, challenger, generation-only, descriptive, or
  unsupported.

The compact receiver group should include route share and change, separation,
pre-lock role, Wide/Slot share, role-matched concessions, alignment-weighted
defender vulnerability, role-conditioned expected defender exposure when
available, team CB/DB concessions, secondary availability, and support/
freshness/assignment uncertainty.

Use a regularized or prespecified additive model. Coefficients describe
predictive conditional relationships, not causal effects of defender quality.

## 8. Work package B: one walk-forward challenger

Proceed only if package A finds stable information beyond the incumbent.

Freeze one challenger using seasons strictly before each evaluation season:

1. **Market component:** the simplest consensus or prior-fold-fitted source
   ensemble supported by package A.
2. **Paid-metric component:** a small residual-mean and/or boom-probability
   adjustment from the compact metric group.

Do not sweep weights on evaluation folds. If fitted source weights are not
stable, use median or equal-book consensus. Missing values need explicit
indicators and a declared fallback.

Use this minimal comparison:

- **M0:** incumbent projection and current 45/55 market treatment;
- **M1:** source-accuracy challenger, no paid-metric residual adjustment;
- **M2:** M1 plus the compact paid-metric residual/boom adjustment; and
- **NP:** one within-slate permuted-information negative control.

M0/M1 isolates source-composition value; M1/M2 isolates paid-metric value; NP
checks whether machinery or added variance alone changes results.

At player level, report covered/full-policy accuracy, tail calibration,
position-level residuals, and whether improvement comes from mean correction,
tail calibration, participation, or role/defender matchup.

## 9. Work package C: fixed-D800 selection test

Run M0/M1/M2/NP on the exact same immutable D800 candidates, actual scores,
ownership inputs, and selection budget. Do not regenerate candidates or change
legality/admission in this comparison.

Retain these lineup aggregates:

- adjusted mean and upper-tail probability;
- favorable player residual count/maximum;
- adverse participation-risk count/maximum;
- role-conditioned matchup exposure and uncertainty;
- stack-level joint ceiling;
- source coverage, line movement, and book disagreement;
- ownership/duplication context; and
- marginal value relative to lineups already selected.

Report:

- K80 mean weekly maximum;
- K57/K20/K10/K3 views matching A5;
- weekly maxima and 200/210/220/230 counts;
- win/loss/tie weeks versus M0;
- selected-lineup overlap and change attribution;
- unchanged pool oracle as a supply check;
- best-candidate recall at fixed budget; and
- Neo4j/lineage first-loss and rescue counts.

Show all weeks and slate-blocked uncertainty. Identify concentration by season,
position, or source.

## 10. Routing after the read

- **Forecast and selection improve:** retain the simplest challenger as a
  Week 1 shadow; this plan alone does not change paid entries.
- **Paid metrics add selection value beyond M1:** retain M2 as the shadow and
  report which feature groups contributed out of sample.
- **Player-tail forecasting improves but selection is null:** stop reranker
  tuning and nominate one `generation varied / selection fixed` comparison.
- **Only descriptive associations reproduce:** close direct historical
  promotion and continue prospective capture.
- **A bookmaker wins only in its selective covered cohort:** do not call it
  globally best; retain a market/position-specific result and full-slate
  consensus fallback.

The lab should freeze exact numerical gates before outcome-bearing M0/M1/M2
reads using its current historical decision conventions.

## 11. Required artifacts

1. `source_coverage.csv`
2. `source_accuracy.csv`
3. `paid_metric_ledger.csv`
4. `role_defender_exposure_audit.csv`
5. `calibration.json`
6. `frozen_challenger.json` if package A licenses package B
7. `fixed_d800_selection.json`
8. `lineage_changes.csv`
9. A short report separating descriptive, predictive, selection, and
   generation conclusions.

Useful visuals: source MAE beside coverage, tail calibration curves,
book-versus-consensus weekly differences, metric incremental value with
uncertainty, role/defender exposure support, M0/M1/M2 weekly differences, and a
first-loss/rescue funnel.

## 12. Ownership

### Production supplies

- corrected common-lock extraction and source identities;
- raw bookmaker-level props and game odds, subject to licensing;
- incumbent pre-lock projections and paid feature rows;
- canonical actual statistics and DK points;
- immutable D800 candidate/score identities and A5 prefixes; and
- candidate-lineage identifiers.

Production also audits whether the source really contains WR1/WR2/slot
assignment information and reviews any transformation before live use.

### Lab owns

- freezing the diagnostic before outcome reads;
- coverage/accuracy analysis and paid-metric ledger;
- the role-conditioned defender mapping when source support is verified;
- the compact M0/M1/M2/NP comparison;
- independent result reporting; and
- recommending close, selector shadow, or one generation follow-up.

The lab should assign non-conflicting experiment identifiers. No cloud launch
is requested until production input identities are named.

## 13. Fast schedule

After production supplies inputs:

- **Session 1:** common-lock validation, source coverage census, and raw
  role/defender-field audit.
- **Session 2:** source scoreboard, paid-metric ledger, and expected-exposure
  support report.
- **Same/next day:** freeze one challenger if supported.
- **Following execution window:** fixed-D800 comparison and routing decision.

Do not wait for perfect route-by-route assignments. Test role-conditioned
exposure now if it is present, clearly label its evidence grain, and preserve
missingness.

## 14. References

- `src/nfl_dfs/models/prop_market.py`
- `src/nfl_dfs/models/blend.py`
- `src/nfl_dfs/models/featureset.py`
- `sql/research/017l_receiver_week_role_pit.sql`
- `sql/research/017m_defense_receiver_role_concession_pit.sql`
- `sql/research/017n_defender_alignment_quality_week_pit.sql`
- `sql/research/017r_player_matchup_week_pit.sql`
- `reports/2026-08-10-prop-common-lock-correction.md`
- `reports/2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md`
- Lab `results/prereg062_feature_sweep_v1.json`

## 15. Requested lab response

Please respond with:

1. acceptance or objection to the compact two-stage design;
2. the minimum production extract/schema needed;
3. the experiment identifier for the first diagnostic;
4. whether median or equal-book consensus is the default simple challenger;
5. whether a retained source truly provides defender-to-WR1/WR2/slot tendency,
   and at what grain/window; and
6. any information-boundary conflict preventing the scoreboard.

Log optional refinements as later work rather than blocking the first read.
