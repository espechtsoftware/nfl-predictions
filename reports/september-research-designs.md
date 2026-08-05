# September research designs (2026-08-05, from review #5 round 2)

Sol's second-round proposals, triaged into build-ready specs. These
are THE research budget for September — everything else in the idea
space is either in the graveyard or outside the narrow posture
(Addendum 78). Ordering is Sol's recommended testing order, adopted.
Evaluate EVERYTHING first on candidate-oracle improvement and the
dependence scores (instrument #0) — selector/panel testing only after
a mechanism gate passes. Panel + LOSO rules unchanged.

## 0. Instruments first (prerequisite for all of the below)

- Candidate-oracle reporting: SHIPPED (engine.py cand-oracle log
  line, 2026-08-05). Baseline arm CANDORACLE ran on the sealed
  defaults; per-week oracle gap numbers in
  ~/nfl-panels/oracle_lines.txt.
- **Role-weighted variogram dependence score** (build ~1 day): score
  simulated draws against realized joints on the pairs that matter —
  QB-WR1 same team, QB-opposing-QB (shootout), RB-own-DST,
  WR1-WR2 same team (usage competition, should be NEGATIVE),
  QB-his-WR-TDs specifically. Energy scores are insensitive to
  miscorrelation (Scheuerer & Hamill); variogram score with role
  weights is the sharper instrument. Implementation: extend the sim
  job to emit per-game draw samples for a held-out season; score
  pattern: E|d_i - d_j|^p vs realized |x_i - x_j|^p by role pair.
  Gate for ANY dependence change (TD ledger, Schaake, CE worlds):
  role-pair scores must improve held-out, marginals must not degrade
  (existing projection-replay MAE/coverage printout).
- **Reconciliation direction** (Wickramasuriya): the TD ledger is
  instance #1 (passing=receiving TDs). Next identities if #1 pans
  out: completions==receptions, team rush attempts==sum carries,
  team totals==sum player usage. Same gate pattern.

## 1. Similarity-conditioned Schaake shuffle (FIRST new arm; may be
## attempted pre-September if the window allows after TDLEDGER)

Replace/augment the simulator copula with JOINT RANK PATTERNS from
comparable historical games, keeping our calibrated marginals.

- For each current game, find K similar historical games (features:
  vegas total, spread, implied pace, pass rate, usage concentration
  HHI). All from nflverse 2016-2025 — data on hand.
- Rank each ROLE's outcome ACROSS the K matched historical games
  (review #5 round 3 axis correction: within-game rank vectors do
  NOT guarantee unchanged role marginals — the empirical copula
  needs each role's rank taken across its own matched-game
  distribution, i.e. the standard Schaake construction: for each sim
  world draw one matched game and assign every role its ACROSS-GAME
  rank from that game, then map ranks onto the current players'
  marginal quantiles). Marginals preserved exactly; the joint rank
  pattern of the historical game carries the dependence.
- Three-arm comparison (Sol's design): sim copula (control) vs
  UNCONDITIONAL historical templates vs SIMILARITY-CONDITIONED
  templates. Judge on instrument #0 first, then candidate-oracle,
  then panel.
- Env design: GAME_SIM_COPULA=schaake|schaake_cond; template bank
  precomputed to a features table (role ranks per historical game)
  by a new build step — cacheable, point-in-time safe (only past
  games enter a week's bank).
- Why it can beat the TD ledger: it imports EVERY joint pattern at
  once (TD co-occurrence, garbage time, blowout suppression, usage
  cannibalization) without specifying mechanisms.

## 2. Cross-entropy rare-world generation (replaces HYPER's fixed rule)

Learn the sampling distribution of worlds that produce elite legal
lineups, instead of hand-picking p98 scripts.

- Parameterize worlds by latent knobs the sim already has: per-game
  pace multiplier, pass-rate tilt, team scoring split, usage
  concentration (Dirichlet temperature), TD allocation sharpness.
- Iterate: sample worlds -> solve the constrained oracle lineup per
  world (the regret machinery from review #5 round 1) -> keep worlds
  whose oracle beats an elite threshold (e.g. sim-world 194-equiv)
  -> refit the knob distribution toward keepers (CE method,
  Homem-de-Mello; keep importance weights so downstream
  probabilities stay unbiased).
- MECHANISM GATE (pre-registered): simulated upper-tail regret must
  fall ~25% AND candidate-oracle ACTUAL scores must improve. If
  regret falls but actuals don't move, the simulator cannot identify
  the missing combinations — bury the whole family (this also
  retro-buries HYPER's approach).
- Cost: oracle MILP per sampled world; restrict to a few hundred
  upper-tail worlds per week; Cloud Run parallelism as usual.

## 3. Decision-focused candidate reranker (needs candidate persistence)

Learning-to-rank over COMPLETE lineups (pairwise/listwise, SPOT-style
decision-focused loss), features: proj, sim ceiling, salary
allocation, stack/bring-back shape, worlds-supporting count, joint
upper-tail probability, ownership/dup features, portfolio
similarity. Labels: realized slate scores of candidates.
- PREREQUISITE: persist ALL candidates (not just selected 40) with
  features + actuals — extend the oracle instrumentation to dump
  candidates to a table (REPLAY_CANDIDATES_TABLE env, same pattern
  as REPLAY_LINEUPS_TABLE). One 6-season instrumented run = the
  training set (~107 slates x ~150 candidates).
- Start linear/boosted; NO neural set models at 107 slates.
- Prior is LOW (selection thrice-null) — this is third in line, not
  first, and only earns a panel arm if it reranks HELD-OUT candidate
  oracles materially better than p_line ranking.

## 4. Inverse-optimization field model vs skeleton resampler (needs
## September classic standings)

Infer the field's latent utility (proj, value, salary usage,
ownership, stacks, bring-backs, recency) from observed entries;
sample entries by Gumbel-perturbing utilities and re-solving the
public MILP (Gumbel top-k). Persona mixture for heterogeneity.
- Compare vs skeleton resampling on: ownership calibration,
  salary-left distribution, stack frequencies, DUPLICATE-LINEUP
  frequencies, held-out full-lineup likelihood.
- Winner becomes the field model for the duplication penalty and
  qualifier rank<=seats objective. The 74-contest FLEX archive can
  prototype the fitting code now, but verdicts need classic-format
  imports.

## 5. Field-relative best-response GENERATION (last; needs #4)

Generate candidates that maximize P(beat simulated field max) /
expected payout directly (Haugh & Singal binary-quadratic
formulation), not just select from a fixed pool with a dollar
objective (that arm was null — Addendum 70). Different because it
changes WHICH lineups exist. Gate: only after the field model wins
its calibration comparison in #4.

## Deferred indefinitely (Sol concurs): vine copulas, Tail-GANs,
## lineup transformers — 107 slates cannot support them.

## Round 4 additions (2026-08-05, Sol's "distinctive technology" batch)
## — triaged against tonight's measurements; NOTHING here precedes
## instruments #0 or items 1-5 above

### 6. Conditional GFlowNet lineup generator (top of the new batch)

Reward-proportional diverse sampling of legal lineups (sequential
construction, action masks, condition on slate/contest/portfolio).
Directly aimed at the measured frontier problem: the pool's oracle
clears 30/107 vs the book's 22, and MILP re-solves cluster modes.
- **Caveat from tonight's data**: the reward is SIMULATED, and the
  sim cannot rank candidates by realized outcome (actual-best at
  median sim-rank 53/168). A GFlowNet inherits that blindness — its
  claim is DIVERSITY at equal quality (a wider pool frontier), not
  better per-candidate judgment.
- **Gate (Sol's, adopted)**: candidate-oracle score AND diversity at
  the SAME candidate count as the incumbent generator mix. Falsified
  if the oracle frontier doesn't widen.
- Family note: shares the diversity goal with the queued MAP-Elites/
  QD archive idea (in-season memory item 15) — build ONE of them,
  whichever the oracle instrumentation motivates first; do not run
  both as separate arms.
- DIFUSCO-style discrete diffusion: explicitly BEHIND GFlowNets
  (Sol concurs); revisit only if GFlowNets gate-pass but plateau.

### 7. Simulation-based inference for simulator parameters

Learn a posterior over hand-set sim constants (game-factor sigma,
pace response, usage concentration, TD allocation sharpness) against
observed summaries (role-pair variograms, scoring concentration,
QB-receiver tail dependence); sample parameters per world to carry
structural uncertainty.
- HARD PREREQUISITE: instrument #0 (the variogram score) — SBI's
  summaries ARE that instrument; building SBI first would be
  measuring with the ruler we haven't calibrated.
- Fits the misspecification lesson of TDLEDGER: parametric surgery
  on an uncalibrated simulator produced an invalid arm; SBI is the
  principled version of "fit the knobs to reality."

### 8. Tracking-data player embeddings (BDB 2026) — off-season moat

Self-supervised embeddings from Next Gen Stats tracking (separation,
route versatility, coverage response...) as PRIORS for rookies/team
changes/new roles — the cold-start gap TabPFN already narrowed.
Slowly-changing traits, not weekly projections. Off-season project;
coverage limits acknowledged.

### 9. Evidence-to-prior news pipeline

LLM as structured EXTRACTOR (event, expected effect, confidence,
source, expiry) feeding a conventional historical-effect model —
never raw text into prediction (Zhang et al. 2025: raw news degrades).
Upgrades the existing manual-notes/watchlist machinery into an
auditable channel. Buildable incrementally in-season; grade like
every shadow (persona pattern).

### Cheap shadow tests (in-season, challenger protocol)

- **TabFM** (Google, June 2026): zero-shot challenger vs TabPFN on
  the same eval harness (reports pattern from Addendum 42/43). Judge
  on RESIDUAL CORRELATION vs LightGBM/TabPFN as much as accuracy —
  its value would be making DIFFERENT mistakes (the ensemble
  lesson). Not a moat (public), but cheap.
- **Time-series foundation models** (MOMENT/Chronos/TimesFM) on
  usage sequences for role transitions/breakouts: must beat trailing-
  window + state-space baselines first; short intermittent NFL
  histories make the prior low.
- **Online conformal risk control**: extends the existing CQR
  auto-activation (>=100 scored rows) to position-specific coverage
  and portfolio-clear probabilities; small build, reliability not
  headline gains.

### Explicitly avoided (Sol concurs): quantum optimization, autonomous
### betting agents, end-to-end lineup transformers, GAN scenarios.
