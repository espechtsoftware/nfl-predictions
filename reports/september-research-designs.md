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
- Represent each historical game by ROLE outcome ranks (QB, RB1,
  RB2, WR1-3, TE, DST x both teams): the within-game rank vector of
  realized DK scores.
- Draw a historical template per sim world; apply its rank pattern
  to the current players' marginal quantiles (Schaake shuffle:
  sort-and-substitute). Marginals preserved EXACTLY by construction
  — only the dependence changes, and it is real, not modeled.
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
