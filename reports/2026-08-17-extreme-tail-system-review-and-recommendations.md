# External review: an ideal extreme-tail lineup system and a path from the current project

**Date:** 2026-08-17<br>
**Scope:** DraftKings NFL Classic, with the primary objective of producing at least one exceptionally high-scoring lineup each week<br>
**Primary project entry point:** [`2026-08-17-external-reviewer-briefing-v2.md`](2026-08-17-external-reviewer-briefing-v2.md)<br>
**Status:** Independent design and code review. This document proposes experiments; it does not promote a new production policy.

## Executive assessment

This project is substantially closer to the right problem than a conventional fantasy optimizer. It models a joint score distribution, generates a fixed-cardinality book, evaluates the maximum score of that book, separates generation from selection, uses point-in-time data, and has unusually strong controls against retrospective overfitting. Those are real advantages. The current evidence also correctly says that the main remaining loss is in **construction**, not in reordering the existing candidate pool.

The largest gap from an ideal system is architectural: candidates are still mostly created as individually attractive lineups—additive MILP optima, optima in individual simulated worlds, or template variants—and only afterward assembled into a portfolio. The ideal system would create each new lineup for its **marginal contribution to the portfolio’s still-uncovered tail states**. It would also simulate every roster slot, treat strategic stacking conventions as hypotheses rather than universal laws, sample rare states from the same probability law more efficiently, and protect the book against plausible model misspecification.

My highest-priority recommendations are:

1. Build a portfolio-aware tail column generator that solves directly for the next lineup’s marginal tail coverage.
2. Add a discrete, correlated DST outcome model. At present DST is effectively constant across lineup worlds, which is a material structural omission for an extreme-score objective.
3. Insert a new forensic layer between “best DraftKings-legal lineup” and “best lineup under production strategy rules.” The current H→P→C→S decomposition cannot measure tail score excluded by hard stacking and anti-correlation rules.
4. Use weighted rare-event sampling—adaptive splitting or conditional sequential Monte Carlo—to obtain more same-law 220–250-point states rather than deforming or merely reranking a finite set of ordinary worlds.
5. Select against a small, explicitly separated set of plausible belief laws, with a worst-law floor, instead of relying on a single blended law.
6. Continue the exact-N, recourse-aware, coherent model/market-state, constraint-lattice, and stack-core×shell work already in flight. These are pointed in the right direction.
7. Do not make expected dollars or simulated contest wins a production objective yet. The current field simulator has a legality defect and the warehouse does not contain the contest-fill data needed to make that objective credible.

The strongest preseason opportunities are recommendations 1–5. They can be developed and mechanically evaluated without observing a 2026 DFS outcome. Production promotion should still require the project’s frozen prospective process.

## What the current system gets right

The production design has several features that an ideal extreme-tail system should retain:

- The utility is attached to a **book of lineups**, not just to individual projection accuracy.
- Player outcomes are generated jointly through a possession/game simulation rather than by independently sampling nine marginal projections.
- Marginal distributions are shaped and calibrated, while market information is incorporated rather than treated as an infallible point estimate.
- Common random numbers, fixed budgets, deterministic tie-breaking, source receipts, point-in-time joins, and immutable execution images make comparisons interpretable.
- The project distinguishes the simulator law, candidate generator, selector, and downstream endpoint. Its recent separation of production-multinomial, fitted-Dirichlet, and finite-K/SIS-ASOE evidence is essential.
- The H→P→C→S forensic decomposition has located the dominant observed loss between the player universe and generated candidates. The corrected average gaps of approximately 4.06, 68.91, and 5.01 points make another selector-only sweep a poor default bet.
- CBWU-OI’s improvement in candidate quality and pair/stack-core reach, coupled with lower player breadth, is useful evidence: useful diversity is **combination support**, not simply the number of distinct players.
- Negative results are documented and scoped. This makes it possible to recommend genuinely different mechanisms rather than cosmetically renaming closed ones.

These strengths should not be diluted. The recommendations below change where optimization effort is spent; they do not argue for looser experimental discipline.

## Current architecture versus an ideal architecture

| Dimension | Current system | Ideal extreme-tail system | Consequence of the gap |
|---|---|---|---|
| Primary utility | Coverage above a fixed 194-point line, with nested-threshold reporting | A preregistered utility of the weekly book maximum; contest-relative utility when a credible field model exists | A binary 194 target can optimize the shoulder while treating 195 and 245 as equivalent |
| Joint outcome law | Correlated offense simulation; blended marginal means; DST constant within worlds | Event-coherent, calibrated distribution for all nine slots, with explicit alternative belief states | Defensive booms and some cross-player event identities cannot drive construction |
| Scenario supply | About 50,000 ordinary Monte Carlo worlds across the production seed blocks | Ordinary worlds plus weighted, same-law rare-event strata | Very high thresholds have low effective sample size and unstable support |
| Candidate generation | Additive objectives, single-world optima, role/game templates, then deduplication | Portfolio-aware column generation: each new lineup maximizes residual tail value | A lineup useful only in combination may never enter the pool |
| Strategic rules | QB+2, bringback, RB–DST and same-team-RB rules are generally hard | DraftKings legality is hard; strategic rules define weighted archetypes or small sleeves | Valid but unusual winning stories may be excluded before the forensic H endpoint |
| Portfolio selection | Greedy fixed-line coverage over a static pool | Integrated generation/selection under diminishing returns and model stress tests | Selector saturation is mistaken for system saturation when the pool is the bottleneck |
| Contest and entry count | Production book is designed around N=80; low-N use can inherit an 80-book ordering | Exact-N books plus one weekly master allocation across contests and late-swap states | A good 80-set need not have a good first 1, 3, 20, or 40 entries |
| Opponent field | Simplified ownership sampler and stylized payout curve | Legal, contest-specific, correlated field with duplication and tie splitting | Simulated dollar results are not reliable enough for policy choice |
| Model risk | One production law at the money endpoint; other laws tested separately | Explicit mixture/ambiguity set with law-specific results and a robustness floor | A simulated pass under one misspecified law can fail on real outcomes |
| Validation | Strong PIT, preregistration, endpoint separation, and prospective requirements | Retain these; add numerical rare-event checks, proper multivariate scores, and sequential prospective evidence | Governance is already a strength, but a few rules are currently broader than the evidence supports |

## Concrete code and data findings

### 1. DST has a projected distribution but not a lineup-world distribution

`src/nfl_dfs/inference/dst_projections.py` produces means, quantiles, and standard deviations. However, `src/nfl_dfs/inference/live_lineups.py` marks live DST rows with `draw_idx=-1`, the production path disables `DST_CORR_DRAWS`, and `_row_draws` in `src/nfl_dfs/backtest/engine.py` therefore returns the same projected DST score in every simulated world. Consequently:

- the selector cannot prefer a lineup because its DST booms in a particular world;
- DST cannot create or cover a rare lineup state;
- covariance with the opposing QB, receivers, game scoring, sacks, turnovers, and the DST’s own running game is absent from the book objective; and
- every lineup’s modeled tail variance is understated by one of its nine slots.

The previously rejected `DST_CORR_DRAWS` experiment does not close this issue. That experiment applied a relatively simple continuous multiplier/anti-correlation mechanism under an earlier downstream system. A discrete event model of sacks, turnovers, return/defensive touchdowns, safeties, blocked kicks, and points-allowed bands is a different mechanism. The repository’s own transfer rules also say that a result under a materially different downstream stack is not automatically current production evidence.

### 2. The existing forensic ceiling is strategy-constrained

The reported chain should be expanded from:

`H → P → C → S`

to:

`H_DK-legal → H_strategy → P → C → S`

`H_strategy` is the hindsight optimum under the frozen production construction rules. It therefore cannot reveal a winning lineup eliminated by QB+2, bringback, RB-versus-DST, same-team RB, or another strategic constraint. The small H→P player-support gap is not evidence that those rules are harmless; the excluded lineup is outside H itself.

This is particularly important in tails. A rule can be correct on average while deleting the one low-frequency story that wins a week. The in-flight constraint lattice is the right first diagnostic, but testing exactly one violated rule at a time does not measure coherent joint exceptions.

### 3. Candidate generation is mainly individual-lineup optimization

`src/nfl_dfs/backtest/engine.py` and `src/nfl_dfs/optimizer/lineup.py` create candidates from additive tournament projections, top simulated worlds, role scenarios, quarterback/game-stack variants, and repeated optimization with overlap restrictions. Those are useful sources, but most solves answer a form of “what is one strong lineup under this objective or world?”

The actual portfolio question is different: “given the 79 lineups already selected, which legal 80th lineup adds the most value in tail states the book does not cover?” A candidate can be mediocre by every standalone ranking yet be the best complement to the book. Post-generation greedy selection cannot recover such a lineup if it was never generated.

### 4. Fixed 194 is a useful benchmark, not a universal winning line

The production selector and CBWU admission logic are centered on 194. The application contains a provisional `tail_line_for_field` heuristic, but it is not the production law and is anchored to a small historical winner sample. A fixed line is valuable for stable comparisons, but it is not equivalent to either:

- maximizing the raw weekly maximum score, or
- maximizing the probability of beating a contest-specific field after duplicates and ties.

The current failure of 200/210/220 selector variants is evidence about **reordering the current candidate pool**. It does not show that higher-threshold information is useless during candidate generation, where the measured gap is much larger.

### 5. The current field model is not suitable for money-law decisions

`sample_field` in `src/nfl_dfs/backtest/field.py` retries a sampled lineup when it exceeds the salary cap, but retains the first sampled lineup as a fallback. If all retries are over the cap, that over-cap lineup can be appended to the field. This is a deterministic code-level reason not to treat the current simulated field as a legal DraftKings population.

There are broader limitations: independent slot sampling does not reproduce lineup-level stacking, salary use, duplication, or correlated ownership; FLEX position mass is simplistic; and the payout model does not split prizes among duplicated/tied lineups. Therefore the historical rejection of a dollars selector is valid for that tested implementation, but it is not evidence that contest-aware optimization is intrinsically unhelpful.

The warehouse reinforces the caution. Read-only BigQuery inspection found:

- `nfl_raw.dk_contest_fills` is empty;
- `nfl_raw.contest_ownership` has substantial 2022–2025 ownership coverage but no populated fantasy-score field in the inspected rows;
- `nfl_predictions.live_candidates` does not contain a complete prospective 2026 candidate/outcome panel; and
- 2026 player-prop coverage is currently one book and one market, while `prop_lines_shadow` is empty.

This is enough for a raw-score system and for some coherent source-state experiments. It is not enough to calibrate a realistic field, duplication model, payout objective, or cross-book player-prop dispersion law.

## Recommended adaptations

### Priority 1: portfolio-aware tail column generation

**Channel:** construction<br>
**Law:** current production-multinomial law for the first test<br>
**Endpoint:** candidate quality first; then simulated selector endpoint<br>
**2026 outcomes required:** no

This is the recommendation with the clearest connection to the measured P→C loss.

Let `B` be the current book, `S(l,w)` the score of lineup `l` in world `w`, and `m(w)` the best score already attained by `B` in that world. Define the next candidate by its exact marginal portfolio value:

`Δ(l | B) = Σ_w q(w) [u(max(m(w), S(l,w))) - u(m(w))]`

For binary coverage at threshold `T`, worlds already cleared receive zero weight and the pricing problem becomes a legal-lineup MILP that maximizes newly cleared weighted worlds. With binary `y_w` variables and ordinary roster `x_p` variables, impose:

`Σ_p score(p,w) x_p ≥ T - M_w(1-y_w)`

and maximize `Σ_w q(w)y_w` over a manageable active set of hard worlds. For a richer raw-tail objective, introduce `y_(w,t)` at preregistered thresholds such as 194, 210, 230, and 240, with weights fixed before the test.

A practical pilot is:

1. Seed the book with the best current production candidate.
2. Choose 64–256 residual worlds that are uncovered, barely covered, or underrepresented by game/stack core. Keep world weights.
3. Solve the pricing MILP for the lineup with greatest marginal gain.
4. Cross-score the new lineup over all production worlds, update `m(w)`, and repeat.
5. Use no-good cuts or pair/core novelty cuts to enumerate several near-optimal shells when the same core repeatedly wins.
6. Admit exactly the same unique post-dedup candidate count as the production control before running the unchanged selector.

This is not another selector. It is not CE/Gumbel world deformation, ATLAS world ranking, or “more candidates.” It can generate a lineup that is not the optimum in any single world but is the best missing complement to the current book.

**Preseason gate:** On the frozen production worlds, require better attainable candidate quality at fixed unique candidate count, non-worse 194 coverage, and improvement at least once in the 210+ region. Report pair reach, stack-core reach, player reach, source attribution, solver status, and the number of generated columns that survive deduplication. If it cannot improve the candidate endpoint before real outcomes are viewed, stop it.

### Priority 2: an event-based, correlated DST world model

**Channel:** joint outcome law and construction<br>
**Law:** new, explicitly labeled DST-augmented research law until prospectively validated<br>
**Endpoint:** calibration/mechanics, then candidate and selector endpoints<br>
**2026 outcomes required:** no for construction and freezing; yes for final transfer

Build DST score from discrete components available in historical play-by-play and team context:

- sacks and pressure-driven sack states;
- interceptions and fumble recoveries;
- defensive, fumble-return, and kick-return touchdowns;
- safeties and blocked kicks;
- points-allowed bands; and
- any DraftKings yards-allowed component that applies to the contest rules in force.

Couple these events to the opponent offense and game state. An interception must hurt the relevant opposing offensive state; defensive touchdowns should not be an independent Gaussian bonus; sacks should relate to pass volume, quarterback pressure tendency, and negative game script; a lead-RB-plus-DST blowout story should be available as a coherent joint state.

Use rank remapping or another marginal-preserving transformation so that adding dependence does not silently destroy the calibrated DST marginal. Validate the distribution of 15+, 20+, and 25+ DST scores, not only mean and variance. Also report covariance with opposing QB/WR/TE scores, own-team RB scores, game total, and spread.

**Preseason gate:** Treat archived seasons as model characterization, not a new outcome-tuned production promotion. Require point-in-time marginal calibration, sensible joint event identities, better multivariate proper scores, and meaningful new candidate/story support. Freeze the model before 2026 evaluation. If the mechanism merely reproduces the old continuous anti-correlation multiplier or damages marginal calibration, reject it.

### Priority 3: turn strategic constraints into an archetype mixture

**Channel:** feasible support and construction<br>
**Law:** unchanged production outcome law<br>
**Endpoint:** new `H_DK-legal → H_strategy` diagnostic, then candidate endpoint<br>
**2026 outcomes required:** no for simulated/support work; yes for promotion

Keep DraftKings roster, salary, team, and lock rules hard. Treat empirical strategy rules as probabilistic priors over lineup stories:

- conventional pocket-QB double stack plus bringback;
- rushing-QB single stack with optional or no bringback;
- concentrated shootout double stack;
- lead RB + DST positive-script stack;
- low-total defensive slugfest;
- injury-condensed two-RB or unusual same-team usage state; and
- game-onslaught structures with a deliberately thin shell elsewhere.

The in-flight exactly-one-rule constraint lattice is a good screening test. The next step should be a very small, preregistered **coherent exception sleeve**, not global relaxation. For example, allow RB+DST only in worlds whose team wins comfortably and whose opponent pass/turnover state supports the story. Allow no bringback only for a rushing-QB or blowout state that explains it. A rule exception without a matching world story is just noise.

Add `H_DK-legal` to future descriptive forensics so the system can quantify the ceiling cost of strategy rules separately from player-pool and generator loss. Retain the evidence that the $49,000 salary floor has not cost observed hindsight ceiling; it does not need to be relaxed merely for novelty.

**Preseason gate:** Limit the sleeve to a fixed small budget—consistent with the existing ≤8-lineup constraint-lattice protocol—and require conditional novelty plus pair/core reach. Do not promote a rule exception on simulated score alone.

### Priority 4: same-law rare-event scenario supply

**Channel:** world sampling and construction<br>
**Law:** the same production law, with likelihood/stratum weights preserved<br>
**Endpoint:** numerical accuracy and candidate quality<br>
**2026 outcomes required:** no

At 230–250 points, ordinary Monte Carlo can provide very few relevant lineup states even with 50,000 worlds. The answer is not necessarily to tilt the production law. Use adaptive multilevel splitting, subset simulation, or conditional sequential Monte Carlo to sample more often from the production law conditional on increasingly extreme attainable scores.

ATLAS already computes a useful reaction coordinate: the best attainable score in a world under its frozen feasibility rules. Instead of only reranking a finite collection of ordinary worlds, use that coordinate to define levels, resample promising simulator latent states, mutate them through valid simulator transitions, and retain the probability weights needed to estimate the original-law objective. Add story/diversity strata so one dominant game does not consume the rare-event sample.

This is materially different from the closed CE/Gumbel family:

- the target probability law is unchanged;
- the goal is lower Monte Carlo variance and better support in rare strata;
- every conditional world carries an auditable weight; and
- unconditional estimates can be checked against ordinary Monte Carlo at thresholds with adequate sample size.

**Preseason gate:** Before using a single generated lineup, demonstrate agreement with ordinary Monte Carlo at 187 and 194, stable estimates across independent seed blocks, higher effective sample size at 220+, and no unweighted contamination of the money law. Then use the weighted rare worlds as the active scenario set for portfolio column generation.

### Priority 5: a robust portfolio across separated belief laws

**Channel:** model risk, construction, and selection<br>
**Law:** multiple labeled laws; never pool their evidence without attribution<br>
**Endpoint:** simulated robustness, then prospective outcome transfer<br>
**2026 outcomes required:** no for freezing; yes for final adoption

The project has repeatedly seen mechanisms pass under a simulator and fail against realized outcomes. That is evidence of model risk, not merely bad luck. An ideal book should be good under several plausible beliefs:

- current production blend;
- coherent model-source state;
- coherent market-source state;
- a small number of frozen role/injury states;
- DST-augmented state when available; and
- any alternative dependence law that survives its own source validation.

Optimize a transparent combination such as:

`(1 - λ) × weighted-average utility + λ × worst-law utility`

with `λ` fixed in advance. A simpler first test is to maximize the production objective subject to a no-material-harm floor under each alternative law. This is a distributionally robust portfolio, not an assertion that all laws are equally true.

The coherent model/market-state generator already in flight is the correct precursor. The current row-wise 45/55 mean blend can construct a state that no source actually believes. Source-coherent worlds preserve slate-level covariance in model error and market error. Current 2026 prop coverage is too thin for a rich cross-book dispersion model, so begin with model-versus-market source states and collect the richer data prospectively.

**Preseason gate:** Keep every law’s results separate, require the production law not to regress materially, and report which candidates each law contributes. Reject a robust book whose apparent protection comes only from duplicating one game core across laws.

### Priority 6: exact-N weekly books and recourse-aware allocation

**Channel:** portfolio construction and execution<br>
**Law:** current production law initially<br>
**Endpoint:** exact requested entry count and late-swap value<br>
**2026 outcomes required:** no for implementation; prospective execution data for calibration

The existing exact-N result—that ranking helps N=1 and N=3, remains positive at N=20, and decays below zero by N=40—is consistent with fixed-cardinality portfolio theory: the best small portfolio is not generally a prefix of the best 80-lineup portfolio. Use the already licensed shadows at N=1, N=3, and N=20. Retain the incumbent prefix at N=40 unless a genuinely new generator or weekly-master mechanism—not another target sweep—earns a separately frozen test.

For the stated raw-score goal, duplicate use of the same lineup in multiple contests adds no new weekly score opportunity. The weekly master should therefore maximize genuinely distinct exposure across all entries unless the financial objective explicitly rewards reuse. If contest and bankroll rules permit more entries, a capacity curve should determine whether additional genuinely distinct columns add tail coverage; N=80 should be an operating point, not a mathematical constant.

The recourse-aware initial-book work is especially promising. DraftKings locks players at their scheduled game times and permits late swap for players whose games have not started, so lineup value is multi-stage rather than purely static ([official contest rules](https://help.draftkings.com/hc/en-us/articles/4405229758867-Fantasy-Sports-Contest-Rules-Scoring-Overview-US)). The initial book should preserve distinct late-game completion sets and swap paths conditional on early results. A lineup with slightly lower pre-lock utility can be better if it retains a high-value pivot when the early core fails or a lower-duplicated block when it succeeds.

**Preseason gate:** Preserve the frozen exact-N dispositions: prospective shadows at N=1/3/20 and incumbent control at N=40. A new weekly master should compare exact requested cardinalities using deterministic two-pass ties without rerunning the closed N=40 selector family. For recourse, score the initial book by expected post-swap utility under frozen early-game states and require feasible, legal swap paths—not merely more late players.

### Priority 7: rebuild the field layer before using expected dollars

**Channel:** opponent/contest model<br>
**Law:** a future contest-specific field law, separate from the player outcome law<br>
**Endpoint:** legal-field calibration, duplication, placement, and payout<br>
**2026 outcomes required:** yes for credible calibration

First fix the mechanical layer:

- never retain an over-cap sampled lineup;
- enforce all DraftKings legality deterministically;
- model stack, salary, team, and FLEX distributions jointly;
- generate duplicate lineups naturally rather than forcing uniqueness;
- split prizes correctly for ties/duplicates; and
- distinguish single-entry, three-max, qualifier, and large multi-entry populations.

Then collect, with source receipts and timestamps:

- contest ID, slate, field size, entry limit, entry fee, and payout ladder;
- complete or sufficiently deep standings and lineup compositions;
- duplicate counts and prize splitting;
- final ownership and late-swap state; and
- the project’s submitted lineup, pre-lock probability, and realized result.

Only after those checks should the ideal money objective become something like the probability that at least one project lineup beats the legal field, or expected payout net of duplication. Until then, raw book maximum should remain the production objective and expected dollars should be a diagnostic. This conclusion supports the current refusal to promote a dollars selector, while narrowing the meaning of that negative result to the tested field implementation.

## How I would define the ideal objective

The project should make the distinction between two goals explicit.

For **raw weekly score**, define:

`M(B,w) = max_(l in B) S(l,w)`

and optimize `E[u(M)]`, where `u` is fixed before outcomes. A single fixed threshold uses `u(M)=1[M≥194]`. A more faithful extreme-tail utility could be a sparse convex ladder that assigns additional value to 210, 230, and 240 rather than treating all clears equally. The project’s nested-threshold hierarchy can supply the weights; the critical change is using the utility during generation, not merely reranking the same pool.

For **winning a tournament**, the correct state includes the field:

`M_margin(B,w,f) = max_(l in B) {S(l,w) - winning_field_score(w,f)}`

plus duplicate-adjusted payouts. This objective requires a legal and calibrated field model. It should not be approximated by changing 194 through a field-size heuristic alone.

The two objectives often agree, but not always. Ownership is secondary for raw maximum score; it matters strongly for contest rank and duplicate-adjusted payout. The system should not let an implicit mixture of these utilities drive production choices.

## Rules and “laws” that deserve revision

### Preserve these rules

- Point-in-time features and source validation.
- Walk-forward or prospective evaluation.
- Preregistration before inspecting the relevant outcome.
- Deterministic execution, common random numbers, immutable images, and durable artifacts.
- Separate claims by simulator law, endpoint, and downstream stack.
- Fixed-budget comparisons, support census, candidate-source attribution, and exact unique post-dedup counts.
- The prohibition on promoting a simulator-only improvement directly to the money law.

These rules prevent more false progress than they cost.

### Narrow or revise these rules

1. **Hard strategy constraints should not be called legality.** Only platform requirements should define the universal feasible set. Empirical stacking rules should define archetype weights, sleeves, or conditional exceptions.

2. **The H endpoint should not hide constraint loss.** Add `H_DK-legal → H_strategy` before the existing forensic chain. Without it, the conclusion that construction dominates is incomplete.

3. **Fixed 194 should be a reproducible benchmark, not a permanent universal target.** Retain it for comparability. In parallel, preregister a raw-tail utility curve and eventually a contest-specific field-relative objective.

4. **“Selection is closed” should remain scoped to the current pool, law, and selector family.** A materially changed candidate generator, DST law, rare-event sample, or robust multi-law objective changes the problem. It does not justify another arbitrary threshold sweep on the current candidates.

5. **“Marginals are exhausted” should be position- and mechanism-specific.** Offensive marginal work may be exhausted under the tested stack; DST does not currently have a simulated world marginal at all.

6. **Equal candidate budget is an experimental control, not necessarily the production optimum.** Every generator test should retain a matched-budget comparison, but also report a same-law capacity frontier so compute budget is not mistaken for an immutable modeling law.

7. **Historical closure should close claims, not conceal correctness defects or genuinely different mechanisms.** The illegal-field fallback is a correctness issue. A discrete event DST model is not the previously tested scalar DST correlation. Portfolio column generation is not a selector retry. All still require a newly frozen protocol and prospective transfer.

8. **One-shot pass/fail rules at very sparse thresholds can be underpowered.** Preserve the operator’s highest-threshold hierarchy, but preregister paired confidence intervals, the complete tail-utility curve, the number of distinct changed slates, and an always-valid sequential prospective rule. This prevents one 240-point event from being either ignored by an average or overinterpreted by a tiny count.

9. **A fixed candidate budget should not require a fixed native supply.** CBWU-OI correctly showed that a larger native union can produce a better fixed admitted set. Continue separating native supply, admission budget, and final selected N.

## What not to prioritize now

- Another selector-only threshold or expected-score sweep over the current pool.
- Generic Gumbel, CE, or world-tilting variants that do not preserve the production-law estimand.
- Promoting ATLAS because it improves attainable quality under a research law. Its current concentration in dominant games and reduced pair breadth are material, and law transfer remains required.
- A generic replay of the old TD-ledger idea. If production-law diagnostics confirm undercoupled direct QB-receiver events and overcoupled touchdown multiplicity, the next model should be a sparse event-identity/state-machine repair, not a global dependence increase.
- “More diversity” measured only by unique players. CBWU-OI already shows why pair, stack-core, shell, and conditional novelty are more informative.
- A deeper marginal prediction model without a downstream mechanism. Current evidence says prediction work must earn value through construction.
- Expected dollars from the existing field simulator.
- Increasing candidate count without a matched-budget comparison and capacity curve.

## A concrete preseason work sequence

### Track A: no-outcome production-law improvements

1. Freeze the current production worlds, source receipts, unique candidate budget, and selector.
2. Implement the residual-world portfolio column generator.
3. Test candidate endpoint first; stop before outcome evaluation if it does not improve attainable portfolio quality.
4. Add weighted same-law rare-event worlds only after numerical agreement with ordinary Monte Carlo.
5. Combine the two: use rare-event residual worlds as the pricing set, then cross-score every column on the ordinary production worlds.

### Track B: feasible-support audit

1. Complete the frozen constraint lattice.
2. Add the `H_DK-legal → H_strategy` layer to the forensic schema.
3. Define no more than a few story-coherent exception archetypes.
4. Give the exception sleeve a fixed, small budget and require conditional novelty.

### Track C: alternative-law models

1. Build the event-based DST shadow law.
2. Complete the coherent model/market-source generator.
3. Construct a robust book with production no-harm floors and full law attribution.
4. Freeze all transfer rules before 2026 outcomes are available.

### Track D: execution and data

1. Continue exact-N and recourse-aware book work.
2. Fix field legality before interpreting any money-law simulation.
3. Start durable contest-fill, duplication, payout, ownership, late-swap, and candidate/outcome capture in Week 1.
4. Record player-prop source, book, market, and snapshot timing so coherent multi-source states can become data-supported later in the season.

## Suggested experiment registry

| Experiment | New mechanism? | Initial law | Primary no-outcome gate | Prospective endpoint |
|---|---:|---|---|---|
| Residual-world portfolio column generation | Yes | Production | Fixed-budget candidate attainable quality and conditional novelty | Weekly maximum / nested thresholds |
| Event-based DST worlds | Yes | DST-augmented research | Marginal calibration, event coherence, support gain | Production-law transfer after freeze |
| Strategy-archetype sleeve | Extension of in-flight lattice | Production | `H_DK-legal → H_strategy`, pair/core reach | 2026 exact-N book result |
| Weighted rare-event scenario supply | Yes | Production estimand | Unbiased lower-threshold estimates and 220+ effective sample size | Candidate/selector transfer |
| Robust multi-belief book | Yes | Multiple, labeled | Production no-harm and worst-law floor | Prospective realized tail result |
| Exact-N weekly master | In flight | Production | Exact-N simulated utility and feasible allocation | Contest-class and weekly maximum |
| Recourse-aware initial book | In flight | Production | Legal swap paths and option value | Post-swap weekly maximum |
| Legal contest-field model | Repair/new model | Field-specific | 100% legal samples, calibration, duplicates/ties | Expected payout diagnostic, then policy |

## Research basis

The recommended direction is consistent with several relevant research streams:

- Hunter, Vielma, and Zaman formulate DFS as a fixed-cardinality, top-heavy portfolio problem and exploit the submodular structure of the probability that at least one lineup wins: [“Picking Winners in Daily Fantasy Sports Using Integer Programming”](https://arxiv.org/abs/1604.01455).
- Haugh and Singal explicitly model opponents and top-heavy reward in a strategic DFS portfolio framework: [“How to Play Fantasy Sports Strategically (and Win)”](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528).
- Adaptive multilevel splitting supplies a principled way to obtain more rare-event samples without redefining the underlying probability target: [Cérou and Guyader review](https://pubs.aip.org/aip/cha/article/29/4/043108/1027309/Adaptive-multilevel-splitting-Historical).
- Distributionally robust optimization provides the formal basis for optimizing against an ambiguity set rather than trusting one estimated law: [Delage and Ye](https://pubsonline.informs.org/doi/10.1287/opre.1090.0741).
- Proper scoring rules provide a better calibration framework for probabilistic simulations than point-error metrics alone: [Gneiting and Raftery](https://doi.org/10.1198/016214506000001437). The [variogram score](https://journals.ametsoc.org/view/journals/mwre/143/4/mwr-d-14-00269.1.xml) is particularly relevant when validating multivariate dependence.
- Decision-focused learning explains why improved predictive loss need not improve the downstream lineup decision: [Donti, Amos, and Kolter](https://arxiv.org/abs/1809.05504).
- DraftKings’ official [Classic overview](https://help.draftkings.com/hc/en-us/articles/24807418578707-Game-Style-Classic-Overview-US) and [contest rules](https://help.draftkings.com/hc/en-us/articles/4405229758867-Fantasy-Sports-Contest-Rules-Scoring-Overview-US) should remain the source of truth for roster, scoring, lock, and late-swap mechanics.

## Verification and corrections (added 2026-08-17, second reviewer)

The load-bearing claims in this document were independently checked against the
code and the warehouse. **All of them hold.** Nothing in the original text
required retraction; this section records the verification, strengthens two
findings the review understated, and adds four technical caveats and two gaps.

### Independently verified

| claim | status | evidence |
|---|---|---|
| DST is constant across all simulated worlds | **confirmed** | `src/nfl_dfs/inference/live_lineups.py:334` sets `"draw_idx": -1`; `src/nfl_dfs/inference/production_policy.py:176` ships `DST_CORR_DRAWS: ""`; `src/nfl_dfs/backtest/engine.py:636` documents that `draw_idx == -1` rows "get their static projection in every sim" |
| `sample_field` can emit an over-cap lineup | **confirmed** | `src/nfl_dfs/backtest/field.py:131-133` |
| H is strategy-constrained, not DK-legal | **confirmed** | `_solve_oracle` (`src/nfl_dfs/research/final_forensic.py:878`) takes `qb_stack_min`/`bring_back_min`; `full_oracle` and `support_oracle` both receive them |
| Corrected gaps are 4.06 / 68.91 / 5.01 | **confirmed** | `reports/2026-08-15-post-forensic-exact-stack-addendum-result.md` |
| `nfl_raw.dk_contest_fills` is empty | **confirmed** | 0 rows |
| 2026 prop coverage is one book, one market | **confirmed** | 898 rows, all `draftkings` / `player_anytime_td` |

### Correction 1 — finding 2 is stronger than stated, and partly already measured

The review argues that `H` hides strategy-constraint loss. That is correct, and
the corrected forensic makes it sharper than the text implies: the exact-stack
addendum re-solved H, P and the recourse oracles under the **full production
QB+2 / one-bring-back contract**, not a loose approximation.

**The size of the effect is also already partly measured.** Relaxing that
contract to QB+1 / no-bring-back is precisely what moved the published gaps:

| gap | QB+2 / BB1 (production contract) | QB+1 / BB0 (loose) |
|---|---:|---:|
| H − P | 4.057 | 3.583 |
| **P − C** | **68.914** | **78.994** |

Relaxing the stack mandate by one partner and one bring-back raises the
hindsight pool oracle by roughly **10 points**. A fully DK-legal `H` can only be
higher. So `H_DK-legal − H_strategy` is not a speculative quantity — it is
already known to be **large**, and no layer of the current decomposition reports
it. This materially raises the priority of the `H_DK-legal` layer and of
Priority 3.

### Correction 2 — the field defect is worse than described

The review says `sample_field` "retains the first sampled lineup as a fallback."
Accurate. Two further details matter for anyone fixing it:

- the variable is named `best` and the docstring claims the function keeps "the
  best attempt," but the code performs **no comparison at all** — it keeps the
  *first* attempt. Name and docstring are both wrong, which is how the behaviour
  survived review;
- the fallback assignment is inside the retry loop, so it fires whenever attempt
  one is over cap, regardless of whether a later attempt would have been legal.

This is a correctness defect in shipped code, is a few lines, and does not need
a protocol. It should be fixed independently of whether the dollars objective is
ever pursued.

### Added caveats, by priority

**Priority 1 — tighten the big-M.** The indicator constraint
`Σ_p score(p,w) x_p ≥ T - M_w(1-y_w)` has a notoriously weak LP relaxation with
a loose `M_w`. Set `M_w = T - (minimum attainable legal score in world w)`, not
a generic large constant. This matters operationally: the ATLAS grids consumed
six attempts partly on CBC memory and solver failures with *smaller* models than
this pricing MILP, so the pilot must be sized against that history from the
start, single-threaded and with retained solver logs.

**Priority 1 — predeclare the band.** CBWU-OI improved 194/200/210 and left
220/230/240 exactly tied. The honest prior is that a breadth-increasing
construction mechanism moves the shoulder, not the extreme. Say so before the
result lands, so a shoulder-only outcome reads as confirmation.

**Priority 2 — DST dependence is two-sided.** DraftKings DST scoring is
dominated by points-allowed bands, so a booming DST is largely a world in which
the *opposing offense collapses*. Introducing real DST dependence will therefore
**reduce** tail coverage for lineups stacking that offense at the same time as
it creates new DST-driven states. The net effect on book maximum is genuinely
ambiguous, and the protocol should predeclare that rather than treating any
decline as a defect.

**Priority 4 — confirm a prerequisite before queueing.** The proposal requires
resampling promising simulator latent states and mutating them through valid
simulator transitions. The possession simulator does not obviously support
restart-from-latent-state; if it does not, that capability is a prerequisite
project, not an implementation detail, and it should be scoped before this arm
takes a slot.

**Priority 5 — sequence it last.** A worst-law floor reduces the *variance* of
outcomes across belief laws; it does not raise the tail. When the measured
problem is that 230 is reached on 1 of 54 slates, robustness is second-order to
Priorities 1, 2 and 4.

### Gap 1 — selector stability is not addressed

CBWU-OI produced a better candidate pool that selects **less reproducibly**:
bootstrap pairwise exact-80 overlap `61.13 → 54.58` (−6.55), disjoint-half
`65.69 → 60.87` (−4.81). Priority 1 is designed to change the pool
*substantially* more than CBWU-OI did. Book reproducibility under world
resampling must therefore be re-measured on any column-generated pool — it
cannot be assumed to carry over, and a book whose membership is unstable across
resamples is an operational risk even when its `C` is better.

### Gap 2 — the queue has one heavy slot

This document proposes five new workstreams. The project has **one 32 GiB
research slot**, currently held by ATLAS repair6 → historical score v4, with the
constraint lattice, coherent model/market state, stack-core × shell and
recourse-aware initial book already queued behind it.

These recommendations should therefore be read as a **re-prioritization, not an
addition**. Concretely: Priorities 1 and 2 are better bets than stack-core ×
shell — which is an independent fallback construction grid whose mechanism is a
variant of what CBWU-OI already established — and should displace it rather than
queue behind it.

## Bottom line

The project should not respond to the remaining gap by searching harder for one better player projection or one better selector. The evidence points to a more specific redesign:

> Generate lineups as marginal columns for a portfolio, in weighted rare states drawn from a fully specified nine-slot joint law, while treating strategy as a mixture of coherent stories and protecting the final book against plausible model error.

That design targets the measured construction bottleneck, can begin in the current preseason, and preserves the project’s strongest asset: disciplined separation between attractive simulated evidence and a policy that has actually earned the right to touch money.
