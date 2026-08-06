# Post-review-6 scoring-improvement plan

Date: 2026-08-05

Status: design only; none of the scoring experiments in this document
are authorized or implemented by this plan.

## 1. Objective

Improve the actual score distribution of the production 40-lineup NFL
DFS portfolio without weakening the project's point-in-time discipline,
same-build comparisons, or season-level adoption standards.

The primary outcome is not generic model accuracy. It is the performance
of the final selected portfolio on historical slates:

1. Number of slate-weeks with selected best score at least 194.
2. Number with selected best score at least 187 and at least 200.
3. Selected best-score mean, median, q75, q90 and worst-season result.
4. Regret between the selected best and the frozen candidate-pool oracle.
5. Candidate-pool oracle clears and oracle-score distribution.

Real contest payout and qualifier-advancement metrics become primary
only after classic-format standings provide trustworthy score-to-rank,
duplication and payout curves. A 237 threshold remains descriptive only;
one occurrence in 107 slates cannot support optimization.

## 2. Expected scale of improvement

The recent persistence and acceptance work should produce no scoring
gain by itself. Its purpose is to make later scoring conclusions valid.

The ensemble adoption already captured an unusually large improvement.
Without genuinely new projection information, the expected next gain is
incremental. A reasonable success would be one to three additional
194-clear weeks, distributed across seasons, or a material reduction in
oracle regret without sacrificing the threshold count.

No workstream should be justified by an expectation of another +10-tail
result. Large apparent gains should trigger an audit for leakage, build
drift, invalid controls, changed RNG streams and post-hoc selection.

## 3. Laws governing every experiment

### 3.1 Same-build control

Every scoring arm runs against HF2 defaults from the same image, code
state, feature snapshot, model artifacts, random streams and slate
manifest. If an arm changes RNG consumption, run its control through the
same code path with the mechanism disabled.

### 3.2 One changed mechanism

An arm changes one mechanism. Feature plumbing, persistence, simulator
changes, candidate-budget changes and selector changes may not be bundled
into one score comparison.

### 3.3 Fixed candidate and compute budgets

Generator comparisons hold total candidate count and approximate MILP
compute constant. A new generator replaces incumbent slots rather than
simply adding candidates. Report solve failures and realized candidate
counts by generator and slate.

### 3.4 Slate is the statistical unit

Candidate rows within a slate are dependent. Cross-validation,
bootstrapping, permutation tests and confidence intervals group by slate.
Multiple seeds for the same slate remain in the same fold and are paired
augmentation, not independent observations.

### 3.5 Point-in-time inputs only

Every feature must have a timestamp, data version and availability rule.
Historical features must reproduce what was available before lock. A
feature that cannot be reconstructed point-in-time is eligible only for
prospective shadow evaluation.

### 3.6 Frozen evaluation ladder

Each mechanism progresses through this ladder:

1. Unit and contract tests.
2. One-slate dry run.
3. Mechanism metric on held-out data.
4. Frozen-pool candidate-oracle or reranking evaluation.
5. Six-season scoring panel.
6. Leave-one-season-out review.
7. Independent-seed robustness where applicable.

Failure at an earlier gate prevents later compute.

### 3.7 No sequential reuse of the panel

Do not repeatedly tune a mechanism after viewing all six-season results.
Hyperparameters, feature groups and adoption thresholds are declared
before the panel. A failed panel closes that exact family unless new data
or a materially different mechanism invalidates the original test.

## 4. Prerequisite: finish the canonical measurement contract

The scoring program does not start until the post-review-6 ACTION 0 gate
is complete in behavior, not merely in documentation.

Required acceptance conditions:

- Validate all expected slates, not a sample.
- Record code SHA, dirty flag, config/manifest hash, data snapshot and
  named seeds.
- Use one panel identity and one unique slate identity per slate.
- Persist NULL—not zero—for unavailable outcomes.
- Record complete multi-generator provenance before roster deduplication.
- Store full candidate-world score artifacts and threshold masks.
- Download every score artifact during acceptance, verify its checksum,
  dimensions and candidate alignment, and reconstruct its masks.
- Reproduce selection with the original support masks, `p_line` and
  simulated-mean tie breaker.
- Prevent staging or partial panels from entering research queries.
- Make promotion atomic and idempotent.
- Remove the stale `run_id` reference in candidate-persistence logging.

The canonical harvest must snapshot the pre-lock player inputs described
in §5 before it runs. Otherwise the expensive historical run would have
to be repeated to train the intended reranker honestly.

## 5. Immutable feature snapshot

### 5.1 Candidate-player data

Persist one row per candidate-player relationship containing:

- Panel, slate and candidate IDs plus canonical roster hash.
- Player ID, roster slot, position, team, opponent and game ID.
- Salary and final projection used by the optimizer.
- Pre-blend model projection.
- Market projection and market coverage indicator.
- Model-minus-market divergence.
- Projected ownership and its source.
- Marginal q10, q50, q90 and q99 where available.
- Model/data versions and source timestamps.
- Evidence, tracking and conformal fields only when genuinely available.
- Explicit missingness indicators for optional feature families.

### 5.2 Ensemble disagreement

If practical, expose individual ensemble-member predictions or at least
their mean, standard deviation, range and robust spread before averaging.
This is epistemic uncertainty: it measures disagreement about the mean,
not the player-outcome variance already represented by simulated draws.

If historical member predictions cannot be reproduced exactly, do not
delay the entire program indefinitely. Snapshot all currently available
historical inputs, mark ensemble spread unavailable, and evaluate it
prospectively before a later adoption decision.

### 5.3 Candidate aggregates

Derive versioned lineup features from immutable player rows:

- Projection, salary and ownership sums.
- Maximum and sum of absolute market/model divergence.
- Signed divergence for the QB, stack and bring-back players.
- Sum, maximum and concentration of ensemble disagreement.
- Stack pattern, bring-back, game concentration and salary left.
- Counts of uncertain, uncovered or conflicting-evidence players.
- Simulated mean, standard deviation, quantiles and tail probability.
- Number and effective diversity of supporting worlds.
- Complete generator tag set.

Prefer deterministic derivation over duplicating aggregates. If an
aggregate is persisted, record its definition version and test that it
recomputes from candidate-player rows.

## 6. Canonical HF2 frontier harvest

Run one pure-default six-season HF2 panel after §4 and §5 pass.

Outputs from the same run:

- The selected 40 and their actual scores.
- Every generated candidate and actual score.
- Candidate-world totals and 187/194/200 masks.
- Complete generator provenance.
- Immutable candidate-player features.
- Per-slate candidate oracle and selected regret.

The acceptance report must include:

- Selected clears and pool-oracle clears by threshold and season.
- Recoverable weeks with season/week identifiers.
- Oracle and selected score distributions.
- Oracle simulation ranks and conditional rank/regret relationships.
- Generator candidate share, selection share and exclusive/shared
  provenance counts.
- Exact comparison to the same-run HF2 headline.

### 6.1 Decision fork

Proceed to reranker development only if the shipping run shows a
material selection frontier. The preregistered default gate is:

- At least four additional candidate-pool clear weeks beyond the
  selected book, spread across at least three seasons; or
- A comparably material and distributed oracle-regret opportunity that
  is hidden by the binary 194 count.

If this gate fails, do not fit a reranker merely because the data now
exist. Concentrate on candidate generation, simulator dependence and
new projection information.

## 7. Workstream A: decision-focused residual reranker

### 7.1 Hypothesis

The simulator ranks some high-scoring non-boom candidates too low because
it lacks a small set of pre-lock signals describing epistemic model
uncertainty, market disagreement or systematic lineup-level residuals.

### 7.2 Experimental arms

Evaluate all arms within one frozen nested comparison:

1. **A0 — incumbent:** unchanged simulated totals and coverage selector.
2. **A1 — structure-only baseline:** simulator summaries, salary/stack
   structure and complete generator provenance.
3. **A2 — disagreement:** A1 plus model/market divergence and historically
   available ensemble disagreement.
4. **A3 — full historical feature set:** A2 plus point-in-time ownership,
   uncertainty and other historically complete inputs.
5. **A4 — negative control:** A3 features shuffled within each slate.

Do not run A1 as a separate adoption experiment before A2/A3 are ready.
Its purpose is to measure whether orthogonal features add value beyond
structure, not to consume a separate round of panel evidence.

### 7.3 Targets

Start with two low-capacity targets:

1. Continuous residual:

   ```text
   actual candidate score - simulated candidate location
   ```

   Compare simulated mean, median and a robust upper-location statistic
   as the baseline location inside training folds only.

2. Residual tail probability:

   ```text
   actual_score >= threshold
   ```

   Fit a grouped logistic model with `logit(p_tail)` as an offset and
   shrinkage on generator effects.

The continuous target should be primary because binary clears are sparse
and discard the difference between a 195 and a 230. The binary model is
a calibration check, not an excuse to tune thresholds.

### 7.4 Models

Begin with:

- Ridge/elastic-net residual regression.
- Hierarchical or shrinkage logistic calibration.
- A shallow gradient-boosted challenger with tightly bounded depth and
  feature count.

No neural set model or unrestricted ranker is justified by 107 slates.
Player IDs, names and unrestricted team identifiers should not become
memorization features.

### 7.5 Cross-validation

- Outer evaluation: leave one season out.
- Inner selection: season-grouped folds using training seasons only.
- Additional production-realism check: chronological walk-forward.
- Duplicate rosters across seeds/runs stay in the same outer fold and
  are deduplicated or inverse-frequency weighted.
- All preprocessing, imputation, scaling and feature selection fit only
  on training folds.

### 7.6 Portfolio integration

Do not sort candidates by a scalar residual and take the top 40. Apply
the predicted correction to candidate simulated totals and rerun the
unchanged coverage selector:

```python
adjusted_totals = candidate_totals + predicted_residual[:, None]
picked = select_tail_entries(adjusted_totals, n_entries=40, line=194.0)
```

Test a bounded correction, fitted entirely within the training fold, so
one noisy prediction cannot shift all worlds by an implausible amount.
An alternative probability-calibration implementation must still retain
world-level portfolio diversification.

### 7.7 Mechanism metrics

- Held-out candidate residual MAE and rank correlation.
- Calibration by predicted-residual decile.
- Top-40 actual score capture.
- Regret to the frozen-pool oracle.
- Recoverable-week capture.
- Result by generator tag and feature availability.
- Negative-control lift.

### 7.8 Falsification and adoption

Falsify the reranker if:

- Structure-only, disagreement and full arms fail to beat the incumbent
  on held-out portfolio metrics.
- Shuffled features perform similarly to real features.
- Gains are isolated to one season or one generator.
- Candidate-level accuracy improves but selected portfolios do not.
- Lift disappears under an independent simulation seed.

Adopt only if a preregistered arm improves a primary portfolio metric in
at least four held-out seasons, has no catastrophic season, beats the
negative control, and transports to the independent-seed harvest.

## 8. Workstream B: epistemic-scenario candidate generation

### 8.1 Hypothesis

The incumbent boom generator and selector read the same simulated
worlds. Candidates reflecting alternative beliefs about player means or
roles may reach useful lineups that aleatoric outcome draws do not
generate or rank highly.

### 8.2 Scenario families

Construct a small, preregistered set of projection scenarios:

- Each individual ensemble member, where available.
- Market-heavy and model-heavy blends inside historically defensible
  bounds.
- High-disagreement QB and stack scenarios.
- High-disagreement value-player scenarios.
- Coherent role alternatives: starter-heavy versus committee-heavy,
  only when supported by point-in-time uncertainty.
- Evidence-conditioned alternatives after the evidence pipeline has
  real, point-in-time coverage.

These are belief scenarios, not independent player p99 boosts. Changes
within a scenario must remain coherent at team/game level.

### 8.3 Candidate construction

For every scenario:

1. Build the scenario projection vector.
2. Run the existing legal MILP and stack rules.
3. Generate a small diversity batch with the existing overlap controls.
4. Record scenario ID and all generator provenance.
5. Deduplicate against the incumbent pool.

### 8.4 Fixed-budget comparisons

Run two gates before a panel:

1. **Union diagnostic:** add scenario candidates offline only to measure
   whether they improve the actual candidate oracle. This is not an
   adoptable score comparison.
2. **Replacement arm:** replace a fixed number of incumbent generator
   slots with epistemic-scenario slots while holding total candidates and
   compute constant.

Candidate additions alone cannot establish value because a larger pool
has a mechanical oracle advantage.

### 8.5 Falsification and adoption

Falsify if scenario candidates:

- Mostly duplicate incumbent candidates.
- Improve simulated ceilings but not actual candidate oracle.
- Produce gains only when added rather than replacing equal budget.
- Degrade candidate legality, salary use or stack construction.
- Win only in the scenario used to generate them and not held-out slates.

Only a fixed-budget replacement arm that improves candidate frontier and
final portfolio results earns adoption.

## 9. Workstream C: similarity-conditioned Schaake dependence

### 9.1 Hypothesis

Historical games contain joint rank patterns—shootouts, usage
cannibalization, blowouts, garbage time and correlated touchdowns—that
the current simulator does not reproduce. Mapping those empirical rank
patterns onto calibrated current-player marginals may improve candidate
generation and ranking while preserving marginal distributions.

### 9.2 Point-in-time template bank

Build historical game templates using only games preceding each replay
slate. Each template should contain:

- Pregame total, spread and implied team totals.
- Pace and neutral pass rate available before the target slate.
- Role-level usage concentration.
- Across-game outcome ranks for QB, RB1/RB2, WR1/WR2/WR3, TE and DST.
- Data-quality and role-mapping indicators.

Do not rank players within a single historical game and treat those ranks
as a copula. Each role's rank must be calculated across the matched-game
sample so current marginals remain preserved.

### 9.3 Arms

1. Current simulator copula.
2. Unconditional historical templates.
3. Similarity-conditioned templates.

Use a preregistered distance function and K-neighbor grid selected on
training seasons only. Avoid tuning K on final portfolio scores.

### 9.4 Dependence gate

Before lineup generation, require improvement on held-out:

- Role-weighted variogram score.
- QB-WR1, QB-opposing-QB and RB-DST dependence.
- WR1-WR2 usage competition.
- Upper-tail dependence at registered quantiles.
- Marginal means, quantiles and coverage unchanged within tolerance.

### 9.5 Scoring gate

Only a dependence arm that passes §9.4 proceeds to:

1. Candidate-oracle comparison.
2. Simulator rank/regret comparison.
3. Same-build 40-lineup panel.

Falsify the family if dependence metrics improve but neither candidate
oracle nor selected portfolios improve. Better covariance diagnostics
alone are not a scoring adoption.

## 10. Workstream D: cross-entropy rare-world generation

### 10.1 Hypothesis

Elite legal lineups arise from a structured subset of game environments.
A cross-entropy sampler can learn this subset more effectively than fixed
p98 scripts or generic Gumbel perturbations.

### 10.2 Latent parameters

Use only simulator parameters with clear semantics and validated bounds:

- Per-game pace multiplier.
- Pass-rate tilt.
- Team scoring allocation.
- Usage concentration/Dirichlet temperature.
- Touchdown allocation sharpness only if its default-path behavior and
  identifiability are valid.

Do not reopen the buried hand-specified TD-ledger mechanism under a new
name.

### 10.3 CE loop

```text
initialize proposal from production prior
repeat:
    sample latent game environments
    generate player worlds
    solve the legal oracle lineup in each world
    score world by oracle objective
    retain a preregistered elite fraction
    refit proposal with smoothing and bounded parameters
record importance weights relative to production prior
```

Hold out slates and random seeds from proposal fitting. Monitor effective
sample size so the learned proposal does not collapse onto a few worlds.

### 10.4 Candidate use

Generate candidates from elite CE worlds, deduplicate them, then evaluate
both union and fixed-budget replacement designs as in §8.4. Importance
weights are required if CE worlds influence probabilities or selection;
an unweighted rare-event proposal may generate candidates but may not
pretend to be the production probability distribution.

### 10.5 Gates

Require both:

- At least the preregistered reduction in simulated upper-tail legal-
  oracle regret.
- Improvement in held-out actual candidate-oracle scores.

If simulated regret improves but actual frontier does not, the simulator
cannot identify the missing real combinations. Bury the family without a
full scoring panel.

## 11. Workstream E: genuinely new projection information

### 11.1 Market movement

The current prop blend weight is already in a flat validated basin, so a
new static blend sweep has low value. The new signal is movement and
cross-book disagreement:

- Opening versus latest pre-lock line.
- Direction, magnitude and recency of movement.
- Book dispersion and number of contributing books.
- Line appearance/disappearance and limit-quality proxies where known.

Evaluate point-in-time projection residuals first, then candidate and
portfolio effects. Never use a closing line timestamp later than the
historical decision cutoff.

### 11.2 Evidence and role uncertainty

Activate the evidence pipeline prospectively with:

- Source timestamp and provenance.
- Supersession/conflict handling.
- Explicit effect on mean and uncertainty.
- Frozen mappings from evidence types to role adjustments.

Conflicting reports should widen uncertainty rather than force an
unsupported directional mean change. Grade prediction residuals before
allowing evidence features into construction.

### 11.3 Tracking traits

Use tracking traits primarily where conventional history is thin or role
changes are plausible. Evaluate incremental residual value after salary,
market, role and historical production—not raw correlation with fantasy
points. Maintain point-in-time season coverage and separate crosswalk
confidence from missingness.

### 11.4 Ensemble disagreement

Treat member disagreement as a feature or scenario trigger, not as
additional player-outcome variance without calibration. Test whether
disagreement predicts absolute or signed held-out residuals. If it does
not, it cannot justify wider distributions or special candidate slots.

### 11.5 Promotion ladder

Every new information source must pass:

1. Availability and leakage audit.
2. Held-out player residual improvement.
3. Calibration/coverage improvement where uncertainty changes.
4. Candidate-oracle or reranker mechanism improvement.
5. Fixed same-build portfolio panel.

Sources that improve player MAE but do not alter candidate or portfolio
performance remain projection diagnostics rather than scoring adoptions.

## 12. Secondary corrective test: salary-floor deletion

Run the already planned post-ensemble `MIN_LINEUP_SALARY=0` arm against
an exact same-build HF2 control. This is a simplification audit, not the
program's leading expected scoring gain.

Before interpreting the score:

- Confirm sub-$49k candidates were actually generated.
- Report how many survived selection.
- Compare candidate and selected salary distributions.
- Report mean best, threshold clears and season effects.

If the lever is inert, the arm says nothing about salary strategy. If
deletion is non-negative and produces materially different portfolios,
an intermediate 47,500 dose may be justified as a separate experiment.

## 13. Priority and decision tree

1. Complete the acceptance and provenance contract.
2. Snapshot historically available orthogonal features.
3. Run and promote the canonical HF2 frontier harvest.
4. Apply the material-frontier gate.
5. If selection regret is material, run Workstream A as one nested
   comparison containing the structure-only ablation.
6. If the pool frontier is weak, skip reranking and prioritize
   Workstreams B and C.
7. Run Workstream C's dependence instrument before any Schaake panel.
8. Run Workstream D only after its CE mechanism can be evaluated on
   held-out candidate oracle; do not jump from synthetic gain to panel.
9. Collect Workstream E signals continuously, promoting only those with
   point-in-time held-out value.
10. Use new classic standings to replace fixed score surrogates with
    contest-specific objectives after the field model is validated.

## 14. Reporting template

Every completed gate produces a report containing:

- Hypothesis and exact changed mechanism.
- Code, config, data and artifact identities.
- Same-build control identity.
- Preregistered mechanism and portfolio metrics.
- Candidate counts and compute by arm.
- Full season-by-season results.
- Failure, missingness and coverage diagnostics.
- Negative controls and falsification result.
- Decision: proceed, shadow, hold, reject or adopt.
- Conditions that could legitimately reopen a rejection.

Reports must distinguish:

- Candidate-frontier improvement.
- Selection improvement on a frozen pool.
- Raw score-distribution improvement.
- Threshold improvement.
- Expected-dollar or bankroll improvement.

These are related but not interchangeable.

## 15. Explicit stopping rules

Stop a workstream when:

- Its mechanism gate fails.
- It improves only in-sample candidate metrics.
- It requires post-lock or unreproducible features.
- Its apparent gain comes from a larger candidate or compute budget.
- A shuffled or placebo feature performs similarly.
- Results depend on one season and fail independent-seed robustness.
- It changes the metric after results are observed.
- It improves simulator self-consistency but not actual candidate or
  portfolio performance.

The purpose of this program is not to keep every sophisticated technique
alive. It is to identify the smallest number of mechanisms that produce
repeatable improvements in the actual selected score distribution.
