# Selection-gap review: untried ways to overcode conversion without mining the panel

Date: 2026-09-03

Status: research recommendations only; no production or lab policy change

Evidence use: the historical outcomes discussed below are development evidence only. Any adoption decision belongs on frozen 2026 prospective shadows.

## Review identity and scope

The requested memo was not present in the checked-out `../nfl2` worktree, but it was available in that repository's fetched Git object database. I reviewed:

- source path: `reports/2026-09-03-selection-gap-state-for-review.md`;
- introducing commit: `2f7d144ff64ca96a2e3e5e88ad220e4c063ab826`;
- Git blob: `779947d397c854d23917c4c9e4e6e71f4cbff76b`;
- file SHA-256: `5c2d9484d72307e6a3c51f4466dafc9c012ca3b3986517bef8f8e16d5522dc48`.

I also checked the current `nfl2` reports, code, experiment queue, and earlier untried-idea inventories. That matters because many superficially attractive suggestions are already tested, queued, or documented: fixed leverage sleeves, ordinary QD, DPP/overlap diversity, extra same-law worlds, Gumbel perturbations, cross-entropy proposals, ECC/Schaake-style rearrangement, pooled coherent overlays, calibration sleeves, posterior/model parliaments, rare-event SMC, core-first generation, prop-ladder shape, robust optimization, and learned set/reranking variants.

The recommendations below are deliberately narrower. Three appear genuinely absent from the reviewed corpus:

1. covariate-conditioned extremal dependence at the role/team-game unit;
2. DFS pick'em desk ecology as a distinct pre-lock information source;
3. compilation of the legal lineup space for explicit configuration-level weighted sampling.

Three others are material new implementations of concerns the project has recognized but has not treated this way:

4. roster-incidence leverage weighting and correlation-preserving feature controls inside a KG5 follow-up;
5. a shock-equivalence audit of the apparent leverage-family regret;
6. a one-case-per-slate winner retrieval challenge rather than winner-row training.

## Executive verdict

The system does not primarily need another smooth score over the same simulated beliefs. The evidence says:

- increasing D400 to D800 improved the book, so more support still helps;
- nevertheless, the D800 pool oracle is about 13 points above the selected book, so conversion is also material;
- eight selectors compress into roughly a 2.4-point band, and WEMAX changed many rosters without changing score;
- the realized correlation of modeled `p194` is about 0.15 and pool containment is approximately random;
- fixed dependence repairs have failed, but the football mechanism is plainly conditional on game, role, participation, and market state;
- the `86.1% leverage regret` headline may represent many forecastable misses, or it may be thousands of roster rows inheriting a few unforecastable player shocks. The current summary does not distinguish those cases.

The useful score map is stage-specific. On the D800 comparison, roughly
`181.5 -> 194.5` is selection/conversion headroom conditional on that pool.
The broader hindsight corpus reaches about `202.7`, so a further approximately
eight-point difference is associated with support outside the D800 pool. These
are oracle bounds from related but not necessarily additive views, not expected
gains. N1/N2 target the first gap; N4/N5 target the second. N3 can affect both
by adding information upstream and at selection.

My recommendation is therefore conditional:

1. Finish experiments 085 and PREREG-060 exactly as frozen.
2. Before spending heavily on KG5, run the outcome-open **shock-equivalence audit** below. It is a diagnostic, not a new selector.
3. If PREREG-060 shows that high-quality missed candidates are already in D800 and the shock audit shows several independent, pre-lock-distinguishable miss mechanisms, KG5 is the right route—but a follow-up should use **incidence-balanced training and source-block negative controls**, not a high-capacity candidate-row soup.
4. Start a score-free census and prospective capture of **US DFS pick'em quotes and multipliers** now. This can add genuinely different marginal-tail and role information with the already-used Odds API ecosystem.
5. If the pool is barren or conditional co-boom scoring fails, build one small **covariate-conditioned extremes** law at the role/team-game level.
6. Only if the law/critic has improved but proposal support remains weak, spike a **compiled legal-space sampler**. It is a supply engine, not a substitute for information.

Do not optimize effective rank or independent-equivalent shots as objectives. T3 already shows why: a book can gain nominal shots and lose actual exceedance. Optimize the registered expected-max/winner utility under accepted belief models; use rank and shots as diagnostics for collapse, never as rescue endpoints.

## The statistical correction KG5 needs

For one slate, let `A` be the `n_candidate × n_player` binary roster-incidence matrix and let `r` be the one realized player-score vector. Every candidate's realized score is exactly

```text
y = A r.
```

Thus 172,611 candidate rows are not 172,611 outcome observations. Within a slate, the realized lineup-score vector lies in the column space of `A`; its number of independent linear directions is at most `rank(A)`, and the actual football dependence makes the usable information smaller still. Slate-blocked validation prevents train/test leakage, but it does not by itself stop the training loss from letting 20,000 near-duplicate rosters repeat the same player shocks 20,000 times.

Earlier reports already recognized the unit-of-analysis problem and proposed player/team-game targets. The new, implementable addition is to make the roster geometry an explicit training receipt and treatment.

### N1 — Incidence-balanced KG5b with source-block knockoff controls

Do not silently change the frozen PREREG-061/KG5 contract. Run this as an amendment before any read if governance permits, or as a separately named KG5b follow-up.

For each slate:

1. Build sparse `A` from exact roster hashes and compute a stable thin SVD/QR.
2. Publish `rank(A)`, singular-value concentration, row leverage `h_i = diag(A (A' A)^+ A')`, maximum leverage, and leverage mass by source/family and selected/omitted status.
3. Give every slate total loss weight one.
4. Compare the current equal-within-slate loss with exactly one frozen shrinkage treatment:

   ```text
   w_i ∝ α / n + (1 - α) h_i / rank(A)
   ```

   Choose `α` from roster geometry alone to cap the largest weight ratio; do not tune it on scores. A reasonable preregistered default is `α = 0.5`, subject to an outcome-blind weight-concentration gate.
5. Keep the model small. Use player/role/team-game aggregates and explicit low-order interactions; no player IDs, slate IDs, winner flags, or selected-book labels.
6. Retain family as a control/stratum, not as the principal signal. The fact that an omitted winner came from `lev` is not itself a pre-lock feature.

Statistical leverage is a principled way to identify rows that carry unusual matrix directions, but it is not guaranteed to improve statistical prediction; the literature explicitly finds that uniform and leverage schemes need not dominate one another. That is why this is a paired treatment, not a claimed correction ([Ma, Mahoney, and Yu, JMLR 2015](https://jmlr.org/papers/v16/ma15a.html)).

The second addition is a **correlation-preserving source-block negative control**. A simple shuffled-feature control is often too easy: it destroys the correlations among projection, ceiling, props, ownership, salary, and role. For each source family, generate a knockoff/control block from pre-lock covariates only, preserving its joint relationship with the other pre-lock blocks as well as the fitted training data permits. Fit real and control blocks together and ask whether the real block wins out of time. Model-X/group knockoffs motivate this construction because they compare features with synthetic variables that retain feature dependence while carrying no added response information ([Candès et al., JRSS-B 2018](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/rssb.12265); [Gimenez, Ghorbani, and Zou, AISTATS 2019](https://proceedings.mlr.press/v89/gimenez19a.html)).

Important limitation: ordinary Model-X guarantees assume a valid covariate model and exchangeable rows. NFL player-weeks and slates do not satisfy that simple setup. Use these blocks as hard negative controls, not as a claim of finite-sample FDR control. Require season-forward scoring, one total weight per slate, and season/slate bootstrap uncertainty.

The smallest useful KG5b crossing is:

| Arm | Candidate pool | Labels/features | Row treatment |
|---|---|---|---|
| Control | exact same D800 | frozen KG5 | equal within slate |
| Treatment | exact same D800 | exact same KG5 | incidence-shrinkage weights |

Feature-family real-versus-knockoff results are mechanism receipts. They should not create several post-read selector arms. If no source block beats its correlation-preserving control on player/team-game targets or near-tie candidate ordering, do not expect a full-set model to manufacture information.

### Why this could score higher

The present corpus contains many boom candidates and relatively few leverage candidates. Equal row loss can learn the most repeated roster/player directions. Incidence weights deliberately increase the representation of lineups that add a distinct player direction without hard-coding a leverage quota. This is more targeted than geometric diversity: it changes the training measure, then still requires the selected K80 to win the registered objective.

### Kill conditions

- incidence weighting changes fewer than 10% of K80 on the exact same pool;
- real source blocks cannot beat their conditional controls;
- performance is carried by one season or by raw family identity;
- candidate-rank improvement does not improve K80 expected max on untouched audit banks;
- realized improvement disappears under slate-level rather than candidate-row uncertainty.

## First diagnostic: is “leverage regret” learnable or just shock multiplication?

### N2 — Shock-equivalence and regret-heredity audit

The `86.1%` best-omitted-leverage share and `73/82` leverage-family count sound decisive, but candidates on the same slate share the same realized players. Fifty omitted rosters can all “win” because one low-owned receiver scored 40 points. That is one football shock, not fifty independent examples that a reranker can learn.

Build an analysis-only audit from already-open development outcomes:

1. For every omitted candidate that beats its book, identify the best book comparator and compute the symmetric player difference.
2. Decompose the actual score advantage into:
   - pre-lock mean/projection advantage;
   - atomic player residuals (`actual - frozen pre-lock center`);
   - a shared team/game component from one prespecified leave-season-out
     hierarchical residual model, with the remainder labeled idiosyncratic.
3. Recompute the comparison after clamping, one at a time, each player residual and each game residual to its frozen pre-lock center. Do not reselect the book.
4. Build a bipartite graph from omitted wins to the player/game shocks that are necessary for those wins.
5. Publish:
   - unique winning slates, QBs, games, and player shocks;
   - HHI/Gini of regret by slate, game, and player;
   - the number of shocks needed to explain 50%, 80%, and 90% of regret;
   - leave-one-player-out and leave-one-game-out persistence;
   - family opportunity denominators, not just win counts;
   - the same quantities for boom, leverage, and random matched candidates.

This is a **learnability gate**, not an adoption score. A convincing KG5 opportunity would look like many independent slates, multiple player/game states, persistent advantages after removing the largest shock, and a feature pattern visible before lock. If most of the headline collapses after removing one atomic residual per slate, forcing more leverage exposure is likely to replay outcome luck.

This audit is cheap, uses no new outcome, and resolves an ambiguity more important than another selector comparison. Its outputs must be frozen as descriptive evidence and must not be used to define a 2026 rule after seeing which phenotype happened to explain the old winners.

## Add new information where the current data has a blind spot

### N3 — DFS pick'em desk ecology, including informative quote presence

The current Odds API ingestion has conventional player props and alternate ladders, but the reviewed repository contains no `us_dfs`, PrizePicks, Underdog, Dabble, DraftKings Pick6, or multiplier integration.

The Odds API currently documents a separate `us_dfs` region covering Dabble, DraftKings Pick6, PrizePicks, and Underdog. It also documents non-default selections in alternate markets and warns that DFS odds are indicative because prices may depend on a user's selections ([bookmaker/DFS coverage](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html)). Its v4 API exposes `includeMultipliers`; the paid historical event endpoint says additional/player/alternate markets are available after 2023-05-03 at five-minute snapshots ([v4 API documentation](https://the-odds-api.com/liveapi/guides/v4/)).

Treat this as a new desk-ecology source, not as a calibrated SGP probability. Capture at fixed pre-lock horizons:

- platform, market, player mapping, line, side, displayed price/multiplier, market timestamp, snapshot timestamp;
- platform count and platform entropy per player/market;
- consensus line, robust dispersion, alternate-selection asymmetry, and multiplier extremeness;
- first appearance, last appearance, and quote age;
- explicit tombstones for a line that disappears while the rest of the platform remains healthy;
- platform-wide outage/maintenance flags so missingness is not blindly labeled as information.

The vendor itself notes that bookmakers can temporarily disappear for maintenance or integration reasons, so presence/absence needs platform-health controls ([Odds API bookmaker notes](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html#notes)). `includeBetLimits` exists mainly for exchanges, so limits should be a coverage census, not an assumed player-prop field ([API parameter documentation](https://the-odds-api.com/liveapi/guides/v4/)).

Use the source in three increasingly expensive gates:

1. **Outcome-blind coverage gate:** PIT timestamp validity, name resolution, platforms/markets per slate, multiplier availability, quota cost, outage rate, and historical availability.
2. **Atomic predictive gate:** does desk breadth, dispersion, quote age, or multiplier information improve held-out player opportunity/tail calibration over the existing prop consensus and projection? Use real-versus-knockoff/stale-snapshot controls.
3. **Candidate gate:** on the exact D800 pool, does the feature family improve near-tie ordering or outside-bank expected max enough to change K80?

Only then feed it to a world law or selector. This source is attractive because independent pick'em desks may encode role confidence and tail/floor judgments that are absent from a two-book mean. It may also be redundant or promotional noise; the gates are designed to find out cheaply.

### N4 — Covariate-conditioned extremal dependence, not another pooled copula repair

ECC, min-KL tilting, and a coherent regime overlay failing does not establish that conditional tail dependence is absent. It establishes that those pooled/fixed repairs did not transport. NFL co-booms should change with role concentration, participation uncertainty, spread/total, pace, protection, coverage, weather, and opponent response.

Fit at the **team-game/role** unit, not at the 72-slate or candidate-row unit:

- represent players by role (`QB`, `RB1`, `WR1`, `WR2`, `TE1`, opponent bring-back role), never identity;
- calibrate marginal residuals first;
- model a small set of joint tail events conditional on frozen covariates;
- partially pool by role and state, with season-forward fitting;
- allow both asymptotic dependence and weakening tail dependence rather than assuming one class;
- introduce latent game factors only if the small model earns them.

Covariate-dependent extremal models are designed specifically for dependence that changes with context ([Mhalla, de Carvalho, and Chavez-Demoulin, “Regression-type models for extremal dependence”](https://www.maths.ed.ac.uk/~mdecarv/papers/mhalla2019.pdf)). Conditional-extremes work also warns that tail-dependence class and extrapolation assumptions matter ([Tendijck, Tawn, and Jonathan, *Extremes* 2023](https://link.springer.com/article/10.1007/s10687-022-00453-7)). If dimensionality later becomes a problem, sparse extremal graphs with low-rank latent components are a relevant template, but their Hüsler-Reiss assumptions should be tested rather than imported wholesale ([Engelke and Taeb, JMLR 2025](https://www.jmlr.org/papers/v26/24-0472.html)). Quantile regression forests are a conservative baseline for conditional marginal quantiles before any extreme-tail layer ([Meinshausen, JMLR 2006](https://www.jmlr.org/papers/v7/meinshausen06a.html)).

The first experiment should be intentionally small:

1. QB plus two same-team receiving roles and one opponent role.
2. Covariates limited to participation/route concentration, game total/spread, and one pace/pass-rate block.
3. Compare the incumbent dependence law, a covariate-free extremal model, and the covariate-conditioned model.
4. Primary upstream gates: season-forward Brier/log score for prespecified joint exceedances, conditional calibration by state, and variogram/energy score.
5. No lineup generation until the conditional model wins upstream and produces material law disagreement on frozen candidates.
6. Then one equal-budget generation arm plus cross-scoring by the incumbent law.

This is the most plausible genuinely new construction intervention, but it has a high overfitting risk. The thousands of team-games help; the truly extreme joint events remain sparse. Regularization and a small state vocabulary are more important than model sophistication.

## Add a genuinely different candidate-support mechanism

### N5 — Compile the legal lineup space and sample configurations directly

The present generator repeatedly solves one optimum per world, with no-good constraints for additional lineups. Prior Gumbel and multi-optimum experiments changed perturbations or local output, but they did not construct an explicit probability distribution over the full legal configuration space.

A decision diagram represents sequential decisions as paths and can merge equivalent remaining subproblems, sometimes compactly representing an exponential discrete space. Exact diagrams can still blow up, while restricted/relaxed diagrams trade completeness for tractability ([van Hoeve, INFORMS 2024](https://pubsonline.informs.org/doi/abs/10.1287/educ.2024.0276)). Dynamic-programming/decision-diagram methods can also support exact weighted sampling of constraint-satisfying assignments ([Dudek, Shrotri, and Vardi, IJCAI 2022](https://www.ijcai.org/proceedings/2022/250)).

By analogy, compile one slate's legal DFS rosters with state for:

- position/slot counts;
- salary used;
- team/game counts needed by the house laws;
- QB stack and bring-back satisfaction;
- RB-DST and two-RB exclusions;
- exact uniqueness.

For an additive frozen critic `q(L)`, compute path partition weights and sample legal lineups from

```text
P_tau(L) ∝ exp(q(L) / tau).
```

Use a small fixed set of critic laws and temperatures selected from outcome-free simulation quantiles. Score every sampled roster under outside laws and deduplicate only after preserving sampling/proposer probability.

This differs from player-level perturb-and-MAP: perturb-and-MAP is an inference construction around repeated optimization ([Bertasius et al., AISTATS 2017](https://proceedings.mlr.press/v54/bertasius17a.html)); a compiled sampler assigns explicit configuration-level mass and can sample many near-optimal paths without relying on which player perturbation happens to win the MILP.

Run this only as a bounded feasibility spike:

1. prove exact legal-count and weighted-normalizer parity on tiny fixtures;
2. prove sampled legality and approximate frequency parity against exact enumeration on reduced slates;
3. attempt one representative full slate with a hard memory/time cap;
4. compare unique candidates, unique cores, independent-critic frontier, and oracle-by-CPU against CBC at equal wall time;
5. stop if the exact diagram explodes or the sampled pool is merely a smoother copy of the incumbent pool.

Pairwise and nonlinear lineup features can make the diagram state explode. Version 1 should sample under additive critics and let the common outside critic judge the union. This idea cannot repair a wrong football law; it is worth building only if PREREG-060 or later diagnostics show a supply problem under a critic that has already passed.

## Use the 51 winners harder without turning them into 51,000 fake observations

### N6 — One-case-per-slate matched winner retrieval challenges

Do not train an unrestricted selector on 51 winner rows, duplicate them, or surround each winner with thousands of controls and then report row-level significance. Use each winner once as a challenge case.

For each winner slate:

1. Leave the entire slate out of fitting.
2. Generate a fixed legal decoy set matched on salary band, stack topology, game concentration, incumbent projection decile, and—where PIT-valid—ownership band.
3. Insert the winner with its identity/source hidden from the scorer.
4. Score once with a model and hyperparameters frozen without that slate.
5. Report winner percentile, reciprocal rank, top-10/top-50 retrieval, and season-block results.
6. Log one immutable evaluation per model identity. A model may not be adjusted and reevaluated on the same challenge set as though the second result were fresh.

This tests the exact question that AUC on ordinary candidate rows does not: can the pre-lock features distinguish the realized contest winner from structurally comparable legal alternatives? It is still development evidence because the program has already seen these historical outcomes. The valid use is model criticism and feature-family triage. Only future 2026 winners can support adoption.

If the compiled sampler in N5 works, it can create decoys uniformly or with known conditional weights. Until then, use one deterministic matched-generation protocol and keep its sampling probabilities.

## Paid-source priority

The next dollar should buy a different belief, not another correlated column.

1. **No new purchase before exploiting the current Odds API surface.** Run the `us_dfs`/multiplier coverage and quota census, then begin prospective capture. Historical additional markets are advertised from May 2023, but cost and actual NFL/pick'em coverage must be measured before a backfill.
2. **ETR independent projections/ownership are the highest-priority external purchase or integration** if the license provides PIT historical snapshots. They can cross-score every candidate and represent an independent forecasting process. If only current-week values are available, use them prospectively; do not reconstruct history.
3. **Within Fantasy Points, ingest weekly role/participation outputs before matchup grades:** snaps, route share, target share, and PROE first; alignment/separation next; coverage matrices after that. The vendor describes those exact data families ([Fantasy Points Data Suite overview](https://newsletter.fantasypoints.com/p/fantasy-points-data-free-this-week)). The page does not establish revision-aware historical PIT semantics, so the ingestion contract still needs observed-at/source-version receipts.
4. **Tracking traits are next as a slowly varying prior**, especially separation/alignment/route traits. They should inform role/player residual models, not enter a giant candidate model raw.
5. **SIS/coverage matchup data is last until completeness and PIT provenance pass.** It is granular and attractive, but partial/quarantined coverage plus matchup variance makes it easier to overfit than independent projections or role shares.

Every paid source should pass, in order: coverage/PIT, atomic predictive value, correlation-preserving negative control, candidate ordering, then K80. A source that fails upstream should not be rescued by whichever downstream selector happens to win the exhausted historical panel.

## What to do with effective rank and “independent shots”

Do not maximize either quantity. They are properties of a score matrix under a chosen law, not product value.

Use these diagnostics instead:

- exact duplicate and near-duplicate tail-event masks;
- per-lineup removal loss in registered expected-max utility;
- marginal tail-event coverage under every accepted critic;
- common-factor exposure by game/role/participation state;
- worst-critic and posterior-mixture utility;
- turnover and score disagreement when a new information family is added.

A low-rank book can be correct when one game state is overwhelmingly likely and the lineups are high quality. A high-rank book can be a collection of independent bad bets. The only rank guardrail I would enforce is mechanical: reject exact duplicates and flag a book whose outcome-blind utility is carried by one candidate or one latent state. Do not require an arbitrary minimum entropy rank.

## Recommended execution sequence

```text
Finish 085 and PREREG-060 unchanged
                |
                v
Run N2 shock-equivalence audit (development explanation only)
                |
        +-------+--------+
        |                |
060 finds       060 pool is barren /
selection       critics cannot separate
opportunity              |
        |                 +--> N4 conditional-extremes upstream gate
        v                 |          |
KG5 as frozen, then       |          +--> one new-law generation arm if it passes
N1 KG5b if needed         |
                          +--> N5 compiled-sampler spike only when the critic is credible

In parallel, outcome-blind/prospective:
N3 us_dfs census and capture -> atomic gate -> later KG5/law feature

For model criticism only:
N6 one-case-per-slate winner challenges -> no historical promotion
```

Concrete next artifacts:

1. `selection_regret_shock_equivalence_v1.json` plus a short report with the concentration/persistence table.
2. `candidate_incidence_receipt_v1.json` per slate containing rank, singular spectrum summary, leverage distribution, and exact roster/pool identity.
3. `odds_us_dfs_coverage_census_v1.json` with endpoint/query parameters, quota cost, player/market resolution, platform health, and no outcomes.
4. A separately named KG5b preregistration if N1 is pursued; never edit a frozen KG5 result after reading it.
5. A two-stage conditional-extremes preregistration: upstream dependence scoring first, lineup generation only after a mechanical pass.
6. A one-slate decision-diagram feasibility note with a hard stop, not a platform rewrite.

## Ranking by expected research value

| Rank | Proposal | Main gap | Cost/risk | Why now |
|---:|---|---|---|---|
| 1 | N2 shock-equivalence audit | diagnosis/learnability | low; hindsight-only | tells whether the leverage headline is many signals or repeated luck before KG5 spend |
| 2 | N3 DFS desk ecology | new information | low-to-medium; vendor coverage risk | currently available API surface appears unused and can be captured prospectively immediately |
| 3 | N1 incidence-balanced KG5b | selection | medium; small-sample risk | directly treats duplicated outcome directions on the exact D800 pool |
| 4 | N4 conditional extremal dependence | law/construction | medium-high; tail sparsity | fixed dependence repairs failed, while the conditional football mechanism remains untreated |
| 5 | N6 winner challenge harness | measurement | low; historical contamination | uses 51 cases honestly and tests retrieval rather than row AUC |
| 6 | N5 compiled legal-space sampler | supply/compute | medium-high; state explosion | genuinely different proposal support, but valuable only after a credible critic exists |

## What I would not build next

- another fixed leverage/boom sleeve;
- another selector grid over the same D800 score matrix;
- an optimizer that targets entropy rank, `n_eff`, or a 194 coverage count directly;
- a high-capacity model trained as if candidate rows were independent;
- another pooled constant correlation/copula overlay;
- a full decision-diagram platform before a one-slate feasibility proof;
- a winner classifier that oversamples 51 cases;
- a raw feature dump from ETR/Fantasy Points/SIS into KG5 without source-block controls;
- an SGP proxy claim from pick'em multipliers. Pick'em data is a marginal desk signal unless actual pair prices are captured.

## Bottom line

The 13-point D800 oracle-to-book gap is a hindsight ceiling, not a forecast of recoverable gain. There is no evidence-backed basis to promise a particular point increase from these ideas. The highest-probability route is to stop asking increasingly similar selectors to resolve a belief error.

The most useful “overcoding” is instrumentation that makes false progress impossible:

- count independent roster-outcome directions, not rows;
- count independent football shocks behind the regret headline;
- make new sources beat correlation-preserving controls upstream;
- model tail dependence as conditional on football state;
- sample the legal configuration space explicitly only after the scoring law earns trust;
- reserve historical winners for locked retrieval challenges and 2026 for adoption.

That program can still produce a null. If it does, the null will say which layer lacks information instead of adding another 80-lineup book to the existing 176–178-point pile.
