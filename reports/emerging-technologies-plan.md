# Emerging Technologies and Differentiation Plan

Status: proposed research and implementation plan. This document does not
authorize adoption of any model or change to the production lineup path.

## 1. Objective

Build a differentiated NFL DFS prediction and lineup system whose advantage
comes from four capabilities that are difficult to reproduce with a standard
projection model and optimizer:

1. Generate a broad distribution of high-value legal lineups rather than
   repeatedly finding nearby optimizer modes.
2. Learn and continuously validate the parameters of the football simulator
   instead of relying on hand-set dependence assumptions.
3. Create proprietary player representations from tracking, usage, and
   evidence data that remain useful when ordinary box-score history is thin.
4. Adapt uncertainty and decision risk as the season changes, while retaining
   strict point-in-time and walk-forward evaluation.

The primary technologies are:

- Conditional Generative Flow Networks for lineup generation.
- Simulation-based inference for simulator calibration.
- Self-supervised graph and trajectory models for player embeddings.
- A provenance-preserving evidence-to-prior pipeline for news and role changes.
- Online conformal calibration and conformal risk control.
- New tabular and time-series foundation models as shadow challengers.
- Discrete diffusion optimization only as a contingency if GFlowNets fail.

## 2. Program principles

### 2.1 Decision quality is the final target

Player-level MAE or RMSE is necessary but insufficient. Every experiment must
identify both a mechanism metric and a lineup-level decision metric.

Examples:

- A dependence model must improve held-out role-pair dependence scores before
  its lineup results are considered.
- A candidate generator must improve the candidate frontier before changes to
  the selector are considered.
- An ownership model must improve full-slate ownership and lineup-shape
  calibration before it may affect field-relative generation.
- A news-derived adjustment must improve component forecasts out of sample;
  persuasive text or intuitive examples are not evidence.

### 2.2 Point-in-time fidelity is mandatory

All data used for a prediction must have been available before the relevant
slate lock. Every persisted prediction, candidate, evidence event, simulator
posterior, and calibration state must include an availability timestamp and a
data-snapshot identifier.

### 2.3 Structural changes require mechanism gates

No joint-distribution change proceeds directly to the six-season lineup panel.
It must first demonstrate that it changes the intended statistic and moves that
statistic closer to held-out reality.

### 2.4 Disabled experiments must be behaviorally inert

An off-by-default experiment must preserve the control's deterministic draw
stream, candidates, and selections. New stochastic components should use named
or component-specific random-number streams so source-code reordering cannot
silently change the baseline.

### 2.5 One causal question per arm

Do not combine a new marginal model, copula, generator, selector, and field
model in one experiment. Test each layer against the current accepted layer,
then test interactions only after individual mechanisms pass.

### 2.6 The production system remains reversible

New technologies enter as shadow outputs or additional candidate batches.
Existing production paths remain available until the replacement clears all
scientific, operational, and latency gates.

## 3. Prerequisites and correctness work

The following work is a prerequisite because emerging techniques will learn
from or be evaluated against these artifacts.

### 3.1 Correct the TD event ledger

- Group the passing-TD ledger by `(game_id, team)`, not bare team abbreviation.
  Historical replay simulates an entire season in one call, so a bare team key
  incorrectly combines all of a team's games.
- Preserve the original independent-draw order when `TD_LEDGER` is disabled,
  or give targets, carries, yardage, turnovers, and touchdowns independent
  named RNG streams.
- Define the behavior when the sum of receiver TD means exceeds the sum of
  passer TD means. Do not claim marginal preservation if receiver means are
  rescaled. Record reconciliation error explicitly.
- Assign a unique group to missing team identifiers; never combine unrelated
  missing-team rows.
- Add tests for multiple games by the same team, multiple passers, missing
  identifiers, incomplete receiver pools, and inconsistent component totals.

### 3.2 Correct the live ownership universe

- Apply `allowed_ids`, slate bans, and draft-group restriction before ownership
  normalization.
- Recompute both naive and trained ownership on the exact requested player
  universe.
- Persist `draft_group_id`, contest type, contest ID when available, first lock,
  prediction timestamp, source model, and model version.
- Grade the final eligible pre-lock ownership snapshot against ownership from
  the same contest and slate definition.

### 3.3 Correct the divergence shadow experiment

- Replace DK historical PPG with timestamped, de-vigged prop-market expected
  points from the actual prop feed.
- Retain book, market type, observation timestamp, line, price, aggregation
  method, and market-coverage indicator.
- Implement the registered statistic using both divergence directions. A
  suitable signed error is
  `sign(model - market) * (actual - market)` for `abs(model - market) >= 2`.
- Freeze the eligible evaluation slates before grading and prevent later
  snapshots from replacing the last valid pre-lock snapshot.

### 3.4 Make diagnostic persistence non-blocking

- Remove synchronous BigQuery load jobs from the lineup-response critical path.
- Write diagnostic records through a bounded background queue, durable event
  stream, or batch flush.
- Treat persistence failure as an observable health event, but do not delay or
  change lineup generation.
- Do not mutate `os.environ` inside request handling. Pass persistence settings
  through explicit function arguments or an immutable run context.

### 3.5 Reconcile configuration and documentation

- Maintain one machine-readable manifest of shipping defaults.
- Include the manifest hash in every replay and live build.
- Generate human-readable configuration summaries from that manifest.
- Mark superseded review packages clearly so old conclusions cannot be mistaken
  for current production behavior.

## 4. Shared research infrastructure

Every workstream should use the same run identity, data lineage, metrics, and
adoption protocol.

### 4.1 Canonical run context

Every research or production run should carry:

- `run_id`: immutable UUID.
- `parent_run_id`: comparator or source run where applicable.
- `run_type`: replay, live shadow, live build, calibration, or data build.
- `code_sha` and dirty-worktree indicator.
- `config_hash` and serialized effective configuration.
- `data_snapshot_id` and maximum source timestamp.
- Season, slate, week, draft group, and contest identifiers.
- Model versions for components, marginals, ownership, simulator, generator,
  selector, and field model.
- Random seed plus named RNG-stream seeds.
- Simulation count, candidate count, entry count, and tail threshold.
- Start time, completion time, status, and failure reason.

### 4.2 Candidate data model

Use normalized candidate and candidate-player tables rather than a comma-
separated player string as the primary representation.

`candidate_run` should contain:

- Run context and slate identifiers.
- Generator configuration and generator versions.
- Candidate and entry counts.
- Locks, bans, theses, notes, and other manual constraints.
- Whether the build is canonical, experimental, or user-customized.
- Lock-relative timing and whether the run is eligible for research.

`candidate_lineup` should contain:

- `run_id` and stable `candidate_id`.
- Source generator and all source tags if multiple generators produced it.
- Canonical sorted player-set hash.
- Salary, projected score, simulated mean, standard deviation, quantiles, and
  threshold probabilities.
- World-support count and weighted world support.
- Stack, bring-back, game-concentration, salary-allocation, ownership,
  duplication, and correlation features.
- Selection status and selection rank.
- Actual score, actual rank, and actual threshold status populated only after
  results become available.

`candidate_player` should contain one row per candidate-player relationship:

- Run and candidate IDs.
- Player identifiers, position, team, opponent, game, salary, and roster slot.
- Pre-lock projection, marginal quantiles, ownership, role, and evidence flags.
- Model and data versions used for that player.

### 4.3 Simulator evaluation artifacts

Persist enough held-out draws or summary statistics to calculate:

- Marginal MAE, RMSE, CRPS, interval coverage, PIT histograms, and tail coverage.
- Role-weighted variogram score.
- QB-receiver, opposing-QB, receiver-receiver, RB-DST, and teammate-usage
  covariance.
- Upper-tail dependence at registered quantile levels.
- Team-level reconciliation errors.
- Distribution of legal oracle-lineup scores by slate.
- Candidate regret relative to the per-world legal oracle.

### 4.4 Common experiment card

Every experiment must declare before execution:

1. Hypothesis.
2. Exact code and data baseline.
3. Single changed mechanism.
4. Mechanism metric and expected direction.
5. Lineup or business metric and expected direction.
6. Walk-forward splits and excluded data.
7. Falsification rule.
8. Adoption rule.
9. Rollback procedure.
10. Expected operational cost and latency ceiling.

### 4.5 Evaluation hierarchy

Evaluate in this order:

1. Unit and property tests.
2. Synthetic truth-recovery tests.
3. Held-out marginal and dependence diagnostics.
4. Candidate-frontier evaluation.
5. Selector evaluation on a frozen candidate pool.
6. Six-season walk-forward panel and LOSO analysis.
7. Live shadow operation.
8. Limited production adoption with explicit rollback.

An experiment stops at the first failed gate.

## 5. Workstream A: Conditional GFlowNet lineup generator

### 5.1 Research question

Can a reward-conditioned generative model produce a more diverse and valuable
legal candidate pool than repeated MILP solves at the same candidate count and
evaluation budget?

This is the highest-priority differentiating technology because GFlowNets are
designed to sample diverse composite objects approximately in proportion to a
reward, rather than returning only one or a few modes.

### 5.2 Initial role in the system

The GFlowNet begins as one additional candidate generator. It does not replace:

- Player projections.
- The football simulator.
- Existing MILP generators.
- Tail selection.
- Field modeling.

This isolates whether it improves the candidate frontier.

### 5.3 State and action representation

Represent lineup construction as a finite directed acyclic graph.

State features should include:

- Players already selected.
- Required roster slots remaining.
- Salary spent and salary remaining.
- Position counts and FLEX feasibility.
- Teams, games, QB identity, stack progress, and bring-back progress.
- Punt, minimum-game, team-limit, lock, ban, and thesis status.
- Minimum and maximum feasible future salary.
- Slate and contest conditioning vector.

Actions should be:

- Add one eligible player to the next canonical roster slot.
- Assign the FLEX position under a canonical rule.
- Finish only when every hard constraint is satisfied.

Use a canonical slot order to reduce the number of trajectories representing
the same player set. Canonicalize the final lineup by player-set hash so slot
symmetry cannot inflate diversity.

### 5.4 Hard-constraint masking

The policy must never select an action that makes a legal terminal lineup
impossible. The action mask should enforce:

- Salary cap and registered salary floor.
- Position and roster-slot requirements.
- No duplicate player.
- Team and game limits.
- Stack and bring-back rules.
- RB-versus-opposing-DST rule when enabled.
- Locks, bans, allowed player universe, and thesis requirements.
- Feasibility of completing remaining slots with remaining salary.

Legality must be guaranteed by construction, not repaired after sampling.

### 5.5 Slate encoder

Start with a compact architecture:

- Per-player MLP encoding projection, quantiles, salary, position, ownership,
  role, injury state, and game context.
- Learned position, team, opponent, and game embeddings.
- A small attention or graph layer with edges for same team, opponent, same
  game, direct stack, and negatively related usage roles.
- A pooled slate representation plus current partial-lineup representation.

Avoid a large transformer. The reward simulator provides many training
examples, but the number of distinct historical slates remains small.

### 5.6 Reward definition

GFlowNet rewards must be positive and numerically stable. Begin with a reward
derived solely from information available before lock.

Candidate reward families should be tested separately:

1. `P(lineup >= tail_line)` from the simulator.
2. Expected simulated payout against a frozen field model.
3. Probability of beating the simulated field maximum.
4. A registered weighted utility combining tail probability and duplication.

A stable initial transformation is:

`reward = epsilon + exp(clip((utility - center) / temperature, low, high))`

The center, temperature, and clipping limits must be fitted without using the
evaluation season. Cache rewards by `(run_id, lineup_hash, reward_version)`.

Do not use actual historical score as the training reward. Actuals are reserved
for held-out candidate-frontier evaluation.

### 5.7 Training sequence

1. Build a deterministic legal environment and verify action masks.
2. Warm-start from trajectories produced by existing MILP candidates.
3. Train with trajectory balance or detailed balance on simulator rewards.
4. Add off-policy replay containing both strong and weak completed lineups.
5. Condition the generator on slate and contest descriptors.
6. Test temperature conditioning so one model can sample exploratory or greedy
   candidate distributions.
7. Add field-relative rewards only after the field model is calibrated.

### 5.8 Baselines

Compare at equal terminal-lineup count and, separately, equal compute budget:

- Existing generator mixture.
- Per-world MILP argmax generation.
- Gumbel-perturbed MILP objectives.
- Random legal lineups weighted by projection.
- GFlowNet alone.
- Existing generator mixture plus a GFlowNet batch.

### 5.9 Mechanism metrics

- Legal-lineup rate must be 100%.
- Unique player-set rate.
- Effective sample size of the reward distribution.
- Entropy by QB, game, stack type, salary band, and ownership band.
- Mode coverage relative to known MILP modes.
- Simulated upper-tail regret relative to exact per-world MILP oracles.
- Reward calibration: sampled frequency should track the intended reward
  distribution after accounting for temperature.

### 5.10 Decision metrics

- Candidate-oracle actual score by slate.
- Candidate-oracle threshold clears.
- Best actual candidate at fixed candidate count.
- Rank of the actual-best candidate under pre-lock reward.
- Incremental contribution when mixed with existing generator families.
- Selected-portfolio performance only after candidate gates pass.

### 5.11 Falsification conditions

Stop or redesign if any of the following occurs:

- The generator cannot guarantee legality.
- Diversity rises only because reward quality falls.
- Candidate-oracle improvement disappears at equal candidate count.
- Gains are isolated to one season or one generator seed.
- The model merely reproduces existing MILP lineups.
- Reward improvements fail to transport from simulated to actual candidate
  outcomes.
- Inference latency is incompatible with live lineup generation.

### 5.12 Adoption path

Adopt first as a fixed-size candidate batch. Preserve the existing selector and
report the batch's unique contribution. Expand its share only if its marginal
candidate contribution remains positive. Replacement of an existing generator
requires an ablation showing that the removed generator no longer contributes
unique candidate-frontier value.

## 6. Workstream B: Simulation-based inference for simulator calibration

### 6.1 Research question

Can the system infer a posterior distribution over simulator parameters that
matches observed marginal, dependence, and tail behavior better than one fixed
hand-tuned configuration?

### 6.2 Candidate simulator parameters

Begin with a small identifiable parameter vector:

- Shared game-factor variance.
- Possession or drive-count variance.
- Vegas-total pace elasticity.
- Within-team target-share concentration.
- Within-team carry-share concentration.
- Passing-TD allocation concentration and unrostered-receiver share.
- Rushing-TD allocation concentration.
- Yardage dispersion per opportunity by position.
- Big-play mixture rate by role.
- Correlation strength between opposing offenses.
- Garbage-time or game-script asymmetry strength.

Do not infer every parameter simultaneously. Add parameters only after synthetic
identifiability tests show that the registered summaries can recover them.

### 6.3 Prior construction

- Derive broad prior ranges from historical play-by-play estimates.
- Use hierarchical priors where parameters vary by position or season phase.
- Keep priors wide enough to expose simulator misspecification.
- Record all prior versions and never tune a prior using the evaluation season.

### 6.4 Observation summaries

Construct an observation vector from point-in-time historical outcomes:

- Marginal mean, variance, zero rate, and registered upper quantiles by role.
- Target, carry, reception, yardage, and TD concentration within teams.
- QB-receiver and QB-opposing-QB variogram components.
- Receiver-receiver and RB-DST dependence.
- Upper-tail co-occurrence rates.
- Team passing-versus-receiving reconciliation gaps.
- Legal oracle-lineup score distribution.

Normalize summaries using training-only location and scale. Retain raw summaries
for posterior predictive checking.

### 6.5 Simulation design

- Draw parameter vectors from the prior using a space-filling design.
- Run the simulator on representative historical slate contexts without using
  their outcomes during simulation.
- Calculate the same summary vector for every simulation batch.
- Store parameter-summary pairs with simulator and data versions.
- Increase simulation density only in posterior-relevant regions.

### 6.6 Inference methods

Evaluate:

- Sequential neural posterior estimation for direct posterior sampling.
- Neural ratio estimation if posterior density evaluation is useful.
- Generalized Bayesian or cost-based inference when the simulator is known to
  be misspecified.
- Robust summary learning that downweights summaries the simulator cannot
  reproduce.

The initial implementation should prefer the simplest method that passes
simulation-based calibration and posterior predictive checks.

### 6.7 Synthetic truth recovery

Before real-data inference:

1. Sample known parameter vectors from the prior.
2. Generate synthetic observations.
3. Infer the posterior using those observations.
4. Measure rank calibration and credible-region coverage.
5. Verify that parameters claimed to be learned are identifiable.

Parameters that cannot be recovered should be fixed, combined, or removed.

### 6.8 Walk-forward real-data inference

For every evaluation season:

- Fit or condition the simulator posterior using strictly earlier seasons.
- Draw parameter vectors from that posterior for the evaluation season.
- Generate worlds by sampling both parameter uncertainty and ordinary event
  uncertainty.
- Never use target-season outcome summaries to choose its posterior.

For live operation, update a separate in-season posterior only after completed
slates become available, retaining the preseason posterior as the prior.

### 6.9 Posterior predictive checks

- Overlay observed summaries on posterior predictive distributions.
- Report summaries the simulator cannot reproduce.
- Compare fixed-parameter and posterior-mixture variogram scores.
- Check marginal calibration separately from dependence calibration.
- Examine whether posterior uncertainty collapses implausibly.
- Inspect sensitivity to prior width and summary selection.

### 6.10 Decision gates

The SBI simulator must:

- Pass synthetic calibration.
- Improve held-out joint scores without material marginal degradation.
- Improve or maintain candidate-oracle performance under walk-forward replay.
- Remain stable across prior and seed sensitivity checks.
- Demonstrate that parameter mixing adds value beyond selecting a single
  posterior-mean parameter vector.

If it improves simulator summaries but not candidate outcomes, retain it as a
diagnostic tool rather than a production generator.

## 7. Workstream C: Tracking-derived player representation model

### 7.1 Research question

Can public tracking data produce transferable player traits that improve
forecasts for rookies, team changes, role changes, and sparse-history players?

### 7.2 Data acquisition and governance

- Catalog every public NFL Big Data Bowl tracking release, covered games, play
  types, seasons, fields, and license conditions.
- Preserve the original raw archives and checksums.
- Build deterministic mappings from tracking IDs to GSIS and project player IDs.
- Track mapping confidence and require human resolution for ambiguous players.
- Record selection bias because each competition exposes different play types
  and seasons.

### 7.3 Canonical coordinate system

- Orient every play in the same offensive direction.
- Normalize field position while retaining goal-line distance.
- Standardize angular variables and player orientation.
- Represent velocity and acceleration in field-relative coordinates.
- Preserve frame rate, event timestamps, play context, and ball state.
- Validate coordinate transformations with invariant tests.

### 7.4 Player-interaction graph

At each frame, create a graph with:

- Player and ball nodes.
- Relative-position, relative-velocity, teammate, opponent, and assignment edges.
- Node attributes for position, motion, orientation, field location, and role.
- Global play attributes for down, distance, score, formation, and play phase.

Use permutation-equivariant processing so arbitrary player ordering cannot
change the embedding.

### 7.5 Self-supervised objectives

Train representations using several compatible tasks:

- Masked trajectory reconstruction.
- Next-frame or future-segment prediction.
- Contrastive agreement between two augmentations of the same play.
- Contrastive player identity across plays, with controls preventing simple
  jersey, team, or position leakage.
- Relative-position and closing-speed prediction.
- Route-family and coverage-family auxiliary classification where labels exist.
- Target, catch, separation, tackle, or yards-after-catch auxiliary tasks.

The representation objective should not include DFS outcomes. DFS evaluation is
a downstream test, not the pretraining target.

### 7.6 Embedding products

Produce uncertainty-aware player-role embeddings such as:

- Receiver separation creation.
- Route diversity and depth profile.
- Performance against man and zone indicators.
- Speed and acceleration retention.
- Contested-catch environment.
- Running-lane exploitation and tackle avoidance.
- Defensive attention drawn.
- Coverage and tackling traits relevant to opponent projections.

Aggregate embeddings at player-season and recent-role levels. Include sample
count, data recency, play-type coverage, and embedding uncertainty.

### 7.7 Downstream integration

Begin by adding frozen embeddings to shadow component models. Test them on:

- Cold-start and low-history players.
- Rookies with compatible college or preseason descriptors, if legally and
  consistently available.
- Players changing teams or offensive systems.
- Players receiving a material role change.
- Receiver efficiency, target earning, and explosive-play components.

Do not allow embeddings to alter the simulator until their marginal component
value is established.

### 7.8 Evaluation splits

- Hold out complete seasons.
- Hold out complete players to test transfer rather than memorization.
- Hold out teams or schemes where practical.
- Report performance by embedding sample size and player-history depth.
- Compare against simple physical-trait, position, and historical-stat baselines.

### 7.9 Falsification conditions

- Gains disappear when player identity leakage is removed.
- Embeddings help only players already represented heavily in tracking data.
- Improvements do not survive a held-out season or player split.
- Mapping uncertainty explains the apparent effect.
- The feature adds no value beyond speed, position, and recent usage summaries.

## 8. Workstream D: Evidence-to-prior pipeline

### 8.1 Research question

Can unstructured pre-lock information be converted into calibrated component
priors with complete provenance and no direct LLM control over projections?

### 8.2 Architectural boundary

The language model may:

- Retrieve from approved sources.
- Resolve candidate entities subject to validation.
- Extract structured claims.
- Identify supporting text and timestamps.
- Classify event type, direction, horizon, and uncertainty.

The language model may not:

- Directly set fantasy points.
- Invent an adjustment magnitude.
- suppress conflicting evidence.
- Execute lineup or warehouse actions based on retrieved text.
- Treat its verbal confidence as calibrated probability without validation.

### 8.3 Evidence schema

Each event should include:

- `event_id`, source URL, publisher, author, publication time, and retrieval time.
- Exact supporting excerpt or source location.
- Player, team, position, and resolved identifiers.
- Event type: inactive, limited, promotion, demotion, starter change, committee,
  route change, target emphasis, workload cap, weather, or other registered type.
- Direction: opportunity up, down, redistributed, or uncertain.
- Affected component: active probability, snaps, routes, targets, carries,
  red-zone share, efficiency, or variance.
- Effective start, expiration rule, and superseding event.
- Extraction confidence and entity-resolution confidence.
- Conflict group linking contradictory reports.
- Human-review status and final disposition.

### 8.4 Source controls

- Maintain an allowlist and source reliability history.
- Treat all retrieved content as untrusted data, not instructions.
- Strip scripts, markup, and prompt-like content.
- Require direct provenance for every extracted claim.
- Store corrections and retractions rather than overwriting history.
- Distinguish firsthand coach/team reports from commentary or aggregation.

### 8.5 Historical event labeling

- Backfill a representative set of events without using post-game articles.
- Resolve each event to the last valid pre-lock version.
- Link events to subsequent snaps, routes, targets, carries, red-zone usage, and
  active status.
- Label whether the reported change occurred and its realized component effect.
- Preserve non-events and false reports to avoid survivorship bias.

### 8.6 Effect model

Begin with a hierarchical partial-pooling model by event type and position.
Estimate changes to components rather than fantasy points.

The model should account for:

- Previous role and depth-chart position.
- Teammate absences.
- Team pace and pass rate.
- Player quality and experience.
- Source reliability.
- Time between report and lock.
- Conflicting reports.

Where sample size supports it, compare doubly robust or causal-forest estimates.
Do not describe an estimate as causal unless its identification assumptions are
explicit and tested.

### 8.7 Applying an evidence prior

- Convert the event model into a distribution over component adjustments.
- Mix that distribution with the baseline component model according to
  calibrated event reliability.
- Increase variance when evidence conflicts rather than averaging contradictory
  reports into false certainty.
- Apply explicit decay and expiration.
- Record the baseline, adjustment distribution, final component distribution,
  and evidence IDs for every affected player.

### 8.8 Human review

Provide a review surface showing:

- Extracted claim and source.
- Conflicting evidence.
- Proposed component and direction.
- Historical event-type reliability.
- Adjustment distribution and expiration.
- Accept, reject, or modify action with reason.

Human actions become labeled data but must remain separate from model-generated
labels.

### 8.9 Evaluation

- Entity resolution precision and recall.
- Event extraction precision and recall by type.
- Source and confidence calibration.
- Brier score for whether the reported role change occurs.
- Component CRPS and interval coverage with and without the evidence prior.
- Incremental candidate and lineup performance.
- False-adjustment rate and average magnitude of harmful adjustments.

## 9. Workstream E: Online conformal calibration and risk control

### 9.1 Research question

Can the system adapt uncertainty to current-season distribution shifts without
retraining the full model or making unsupported parametric assumptions?

### 9.2 Calibration targets

Calibrate separately:

- Player component distributions.
- Final fantasy-point marginals.
- Upper-tail probabilities.
- Ownership predictions.
- Portfolio-level probability claims.

Do not assume one calibration adjustment works for every layer.

### 9.3 Nonconformity scores

Candidate scores include:

- Absolute residual for point predictions.
- Quantile or interval miss score.
- PIT-based distribution score.
- Upper-tail event score for registered thresholds.
- Signed ownership error.
- Portfolio loss measuring overstatement of a tail-clear probability.

### 9.4 Calibration groups

Use partial pooling or Mondrian groups for:

- Position.
- Starter, committee, backup, and cold-start roles.
- Rookie and veteran status.
- Early-season and established-season contexts.
- Injury or evidence-adjusted players.
- Prop-covered and uncovered players.

Avoid groups too small to support stable quantiles. Fall back through a declared
hierarchy to broader groups.

### 9.5 Online update

- Initialize from strictly historical calibration residuals.
- Update after outcomes become available.
- Use adaptive conformal methods or recency weighting to respond to drift.
- Persist the full calibration state before and after every update.
- Never retroactively alter the state used for an earlier slate.
- Monitor effective calibration sample size and fallback behavior.

### 9.6 Distribution application

Apply conformal corrections by widening, narrowing, or shifting the relevant
predictive distribution while preserving ordering where possible. Recompute
lineup simulations from the calibrated marginals rather than adjusting final
lineup scores after simulation.

### 9.7 Conformal risk control

Define a monotone control parameter, such as distribution scale or minimum
required simulated tail probability. Use conformal risk control to choose the
parameter that limits a registered loss, for example:

- Overstatement of player upper-tail probability.
- False-confidence rate among promoted ceiling plays.
- Expected error in claimed portfolio clear probability.
- Ownership underestimation among players classified as low-owned.

State precisely what guarantee applies and under which exchangeability or
online assumptions. Do not market a marginal player guarantee as a guarantee on
the selected portfolio.

### 9.8 Evaluation

- Coverage and interval width by role and season segment.
- Long-run and local-window calibration error.
- Adaptation following identifiable distribution shifts.
- Sharpness at equal coverage.
- Tail-probability calibration.
- Candidate and lineup results after recalibration.

## 10. Workstream F: Foundation-model challengers

These are inexpensive shadow tests, not primary differentiation investments.

### 10.1 TabFM challenger

Test the newly released TabFM as:

- A zero-shot component predictor.
- A residual predictor on top of the existing ensemble.
- An ensemble member alongside LightGBM and TabPFN.
- A disagreement signal used only after calibration.

Use exactly the same point-in-time rows, targets, walk-forward splits, and
feature availability as existing models.

Evaluate:

- Component MAE, RMSE, CRPS, and calibration.
- Performance by sample size, position, rookie status, and cold start.
- Residual correlation with LightGBM and TabPFN.
- Ensemble gain at fixed complexity.
- Stability to row order, feature order, missingness, and context selection.

The primary value is orthogonal error, not winning a generic tabular benchmark.

### 10.2 Time-series foundation models

Create point-in-time player sequences for:

- Snaps, routes, targets, carries, receptions, red-zone usage, and efficiency.
- Availability and injury state.
- Team context and role rank.

Represent missing games, byes, inactives, and true zeros distinctly. Compare
open models such as Chronos, MOMENT, or other reproducible challengers against:

- Last value.
- Rolling mean and exponentially weighted mean.
- State-space model.
- Existing tabular features and component model.

Test direct forecasts and embeddings separately. Foundation-model outputs do
not enter production unless they add walk-forward value beyond simple sequence
baselines.

### 10.3 Foundation-model adoption rule

- Require point-in-time walk-forward improvement.
- Require value in multiple seasons or a pre-registered special population such
  as cold-start players.
- Prefer residual diversity that improves the ensemble.
- Reject gains that depend on unavailable live context or unversioned remote
  behavior.

## 11. Workstream G: Discrete diffusion contingency

Discrete diffusion is a secondary research path, activated only if the GFlowNet
fails for a reason that diffusion plausibly addresses.

### 11.1 Suitable activation reasons

- Sequential GFlowNet construction is too slow.
- Flow training is unstable despite correct reward scaling.
- The policy cannot represent useful global player interactions.
- A fixed-size binary representation offers a clear implementation advantage.

### 11.2 Proposed representation

- Represent a lineup as a binary player-selection vector.
- Condition the denoiser on slate, contest, projections, ownership, and game
  graph.
- Train it to denoise corrupted high-reward legal lineups.
- Apply hard feasibility projection or a constrained decoder after each reverse
  step.

### 11.3 Required comparison

Compare directly with the GFlowNet and MILP at equal candidate count, legality,
and compute. Do not operate two large neural candidate-generation programs
without a registered decision between them.

## 12. Integrated architecture

The intended long-run pipeline is:

1. Build the exact pre-lock slate and run context.
2. Produce component marginals from the accepted ensemble, with TabFM or
   time-series challengers remaining shadow features until adopted.
3. Apply tracking embeddings as model inputs only where validated.
4. Apply evidence-derived component priors with provenance and uncertainty.
5. Apply online conformal calibration to component or fantasy-point marginals.
6. Sample simulator parameters from the walk-forward SBI posterior.
7. Generate coherent player-outcome worlds.
8. Produce candidates from the existing generator mixture plus the conditional
   GFlowNet batch.
9. Evaluate candidates with the accepted selector.
10. Apply field-relative objectives only after the field model passes its own
    calibration gates.
11. Persist the complete run, candidate, calibration, evidence, and lineage
    artifacts asynchronously.

Each numbered layer must have an independent bypass so it can be ablated or
rolled back without changing other layers.

## 13. Test strategy

### 13.1 Property tests

- All generated lineups are legal.
- Equivalent player sets have one canonical hash.
- Disabled experiments reproduce control outputs exactly.
- Simulator identities reconcile within declared tolerance.
- No future timestamp enters a point-in-time build.
- Calibration-state updates are append-only and ordered.
- Evidence adjustments expire and can be superseded deterministically.

### 13.2 Synthetic tests

- GFlowNet samples a known small reward distribution correctly.
- GFlowNet recovers all modes in a multimodal toy slate.
- SBI recovers known simulator parameters with calibrated posterior ranks.
- Conformal methods achieve expected coverage on controlled shifts.
- Tracking representations obey coordinate and player-order invariances.
- Evidence extraction handles conflicts, retractions, and adversarial text.

### 13.3 Integration tests

- Full live build with every external write mocked.
- Candidate persistence failure does not change or delay returned lineups beyond
  the registered tolerance.
- Exact draft-group ownership normalization.
- Complete replay-season simulation with repeated teams across games.
- Run reproduction from stored code, configuration, data, and RNG identifiers.

### 13.4 Research tests

- Same-build controls for every stochastic source change.
- Walk-forward season isolation.
- LOSO stability.
- Candidate-count and compute-budget normalization.
- Seed sensitivity.
- Multiple-comparison and experiment-family accounting.
- Negative controls expected to be inert.

## 14. Operational controls

### 14.1 Shadow-first deployment

Every new model publishes shadow outputs with:

- Freshness status.
- Coverage and missingness.
- Model and data version.
- Comparator deltas.
- Calibration status.
- Operational latency.

Shadow output must never silently become a production input.

### 14.2 Health checks

Add alerts for:

- Missing candidate batches.
- Empty or degenerate GFlowNet distributions.
- SBI posterior collapse or prior-boundary concentration.
- Tracking ID-map failures.
- Evidence-source outages or extraction spikes.
- Conformal effective-sample-size collapse.
- Foundation-model version changes.
- Synchronous warehouse calls in request paths.

### 14.3 Resource isolation

- Keep live lineup generation independent of research GPU availability.
- Cache deterministic feature and reward calculations.
- Bound background queues and expose dropped-event counts.
- Store large draw artifacts outside operational tables, retaining summary and
  lineage records in BigQuery.
- Version remote models and persist their raw outputs when reproducibility is
  otherwise impossible.

## 15. Decision sequence

The program should proceed through these dependency-ordered decisions:

1. Establish a trustworthy deterministic baseline and shared instrumentation.
2. Correct the TD ledger, ownership universe, divergence source, and diagnostic
   persistence.
3. Build the role-weighted dependence evaluation suite.
4. Test the GFlowNet as an additive candidate generator.
5. Test simulator-based inference on a small identifiable parameter set.
6. Begin accumulating structured, provenance-preserving evidence events and
   conformal shadow state during normal operation.
7. Build tracking representations as an independent feature research program.
8. Run TabFM and time-series foundation models as low-cost challengers.
9. Consider discrete diffusion only after a documented GFlowNet failure.
10. Integrate technologies only after each one passes its isolated mechanism and
    decision gates.

## 16. Deliverables

### 16.1 Baseline and instrumentation

- Canonical run-context schema.
- Candidate-run, candidate-lineup, and candidate-player schemas.
- Named RNG-stream specification.
- Marginal, dependence, reconciliation, candidate, and portfolio scorecards.
- Machine-readable shipping configuration manifest.

### 16.2 GFlowNet

- Legal lineup environment and masks.
- Toy-distribution validation suite.
- Conditional slate encoder and flow policy.
- Cached reward service.
- Candidate export compatible with the existing selector.
- Equal-budget comparison report.

### 16.3 SBI

- Parameter and prior registry.
- Simulator summary builder.
- Parameter-summary simulation bank.
- Synthetic calibration report.
- Walk-forward posterior artifacts.
- Posterior predictive and lineup comparison report.

### 16.4 Tracking

- Licensed raw-data catalog and ID map.
- Canonical tracking representation.
- Self-supervised encoder and frozen embedding registry.
- Player-role embedding table with uncertainty and coverage metadata.
- Held-out player and season evaluation report.

### 16.5 Evidence system

- Source registry and security policy.
- Evidence-event schema and extraction benchmark.
- Conflict and retraction handling.
- Historical effect model.
- Human-review interface specification.
- Component-prior shadow evaluation.

### 16.6 Conformal system

- Nonconformity-score registry.
- Calibration grouping hierarchy.
- Append-only online calibration state.
- Coverage, sharpness, drift, and risk-control dashboard.
- Shadow-to-production adoption report.

### 16.7 Foundation challengers

- TabFM walk-forward benchmark.
- Residual-correlation and ensemble study.
- Time-series foundation-model benchmark against simple baselines.
- Reproducibility and operational-cost report.

## 17. Risk register

### Simulator reward exploitation

A generator may learn simulator artifacts rather than football edge. Mitigate
with held-out actual candidate-frontier gates, posterior parameter mixtures,
negative controls, and reward-version comparisons.

### Small number of independent slates

Thousands of candidates from one slate are not thousands of independent
training examples. Split and bootstrap at slate or season level, never at
candidate level.

### Tracking-data selection bias

Big Data Bowl releases cover selected seasons and play types. Record coverage,
evaluate held-out players, and use embeddings as uncertain priors rather than
complete current-season truth.

### LLM hallucination and prompt injection

Use LLMs only for structured extraction from allowlisted sources. Require direct
provenance, schema validation, conflict handling, and calibrated downstream
effect models.

### Conformal guarantee overstatement

Document the exact unit, loss, and assumptions of every guarantee. Selection,
dependence, and distribution shift can invalidate a guarantee transported from
players to portfolios.

### Neural generator mode collapse

Monitor entropy, effective sample size, unique modes, and reward-frequency
calibration. Compare with Gumbel and MILP diversity baselines.

### SBI non-identifiability

Require synthetic truth recovery. Remove parameters that the chosen summaries
cannot identify.

### Operational fragility

All emerging models remain bypassable. Live generation must work when research
services, GPUs, remote models, or diagnostic warehouses are unavailable.

### Research overfitting

Use registered experiment families, same-build controls, walk-forward seasons,
LOSO reporting, and explicit graveyard rules. Do not repeatedly tune a new
architecture against the same 107-slate outcome panel.

## 18. Success definition

The program succeeds if it produces at least one durable advantage in each of
these categories:

- **Generation:** a legal candidate distribution with superior held-out
  candidate-frontier value at equal candidate count.
- **Simulation:** a posterior-predictive simulator with measurably better joint
  behavior and no material marginal regression.
- **Information:** a proprietary, point-in-time player representation or
  evidence feature that improves sparse-history forecasts.
- **Reliability:** online uncertainty and risk claims that remain calibrated as
  conditions change.
- **Operations:** full lineage, reproducibility, graceful degradation, and no
  research-side latency in the live request path.

The differentiating product is not any single model. It is the combination of a
self-calibrating football world model, a diverse reward-conditioned lineup
generator, proprietary player and evidence representations, and a rigorous
decision-focused validation system.

## 19. Primary technical references

- Bengio et al., "GFlowNet Foundations":
  https://www.jmlr.org/papers/v24/22-0364.html
- Boelts et al., "sbi reloaded":
  https://joss.theoj.org/papers/10.21105/joss.07754
- Huang et al., robust simulation-based inference under model misspecification:
  https://proceedings.neurips.cc/paper_files/paper/2023/hash/16c5b4102a6b6eb061e502ce6736ad8a-Abstract-Conference.html
- Gibbs and Candes, online conformal inference under distribution shift:
  https://www.jmlr.org/papers/v25/22-1218.html
- Angelopoulos et al., "Conformal Risk Control":
  https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html
- NFL Big Data Bowl 2026 tracking challenge:
  https://www.kaggle.com/competitions/nfl-big-data-bowl-2026-prediction/overview/abstract
- Google Research, TabFM:
  https://research.google/blog/introducing-tabfm-a-zero-shot-foundation-model-for-tabular-data/
- Goswami et al., "MOMENT":
  https://proceedings.mlr.press/v235/goswami24a.html
- Ansari et al., "Chronos":
  https://arxiv.org/abs/2403.07815
- Sun and Yang, "DIFUSCO":
  https://proceedings.neurips.cc/paper_files/paper/2023/hash/0ba520d93c3df592c83a611961314c98-Abstract-Conference.html
- Zhang et al., structured context in LLM event forecasting:
  https://aclanthology.org/2025.realm-1.32/
