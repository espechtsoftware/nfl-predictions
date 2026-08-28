# Raising the weekly best-of-book score: outside research, plan critique, and suggestions

**Date:** 2026-08-27
**Author:** Claude (Fable 5), at the operator's request
**Status:** advisory. Outcome-blind with respect to any new outcome read; every number quoted below is taken from already-published, tracked reports or from public sources. Nothing here authorizes an outcome query, a production default change, or a contest-entry change.
**Objective addressed:** maximize the average (and tail) of the *weekly maximum* realized DK score across the entered book — one exceptional lineup per Sunday main slate — with 230+ as the operator's aspirational target and 194/200 as the measured working lines.

---

## 0. What was reviewed

- Repository: last ~40 commits on `main` (R6 full-union freeze → grade → score release → attribution release → deep review → belief-world contracts → fixed-G0 matchup authority), `HANDOFF.md` updates 179–182, `CLAUDE.md`.
- Plan in progress: `reports/2026-08-27-r6-corpus-selection-deep-review.md` (implementer diagnosis + lead-architect adoption review, Lanes 0–5), `reports/2026-08-24-big-picture-review-response.md`, `reports/2026-08-19-large-field-tournament-winning-strategy-plan.md`.
- Evidence: `reports/2026-08-27-r6-full-union-realized-score-results.md`, winner-law/anatomy/structure/world-optima results (2026-08-19), beat-the-winner scorecard (2026-08-20), system-study Addenda 96–120, greenfield redesign note.
- Code map of the simulator (structural Poisson×Gamma component sampler → rank-preserving TabPFN quantile reshaping → possession-Markov game factors → additive prop-market mean shift; TD ledger / big-play mixture / Vegas pace / Dirichlet usage all built but OFF in production; greedy world-coverage and ladder selectors in `optimizer/lineup.py`; late-swap/recourse modules in `optimizer/late_swap.py`, `inference/recourse_worlds.py`, `analysis/recourse_aware_initial.py`).
- Outside research: DFS portfolio literature (Hunter–Vielma–Zaman; Haugh–Singal; Liu–Liu–Teo; Bergman et al.; Kim et al. March Madness), max-of-k / order-statistic selection theory (Mehta–Nagarajan–Ravi; Fikioris et al. ITCS 2025; extreme bandits; pass@k policy optimization; quality-diversity guarantees; extreme conformal prediction), and practitioner winner analyses (ETR/Levitan top-10 census, 4for4, FantasyLabs, DFS Army, RotoGrinders, SpikeWeek correlation tables). Sources are linked inline.

---

## 1. The state of play, in the numbers that matter

| Fact | Value | Source |
|---|---|---|
| Exact-80 book, mean weekly max (54-slate R6 panel, best final-fit selector) | **178.4** | R6 score results |
| Book clears 194 / 200 / 210 / 220 / 230 (weeks of 54) | ~9 / 7 / 5 / 4 / 2 | R6 score results, deep review |
| Corpus (≈3,690 distinct lineups/slate) contains a 200+ / 220+ / 230+ lineup | 29 / 10 / 3 weeks of 54 | deep review |
| Best single 80-book converts an available 200+ week | **7 of 29 (24%)** | deep review |
| Union of all eight 80-books (≈205 distinct lineups) converts | 10 of 29 (34%) | deep review |
| Corpus oracle vs recorded Milly winner | beats it **1 of 51**; mean gap **−30.0** | deep review |
| Money book vs winner (older panel) | 0 of 50; median gap +53 | beat-the-winner scorecard |
| Milly winner scores 2023–25 | median 233, p10 205, min 178 | winner registry |
| Public $20 Milly average winning score | 2022 ≈241, 2023 ≈238, 2024 ≈229, 2025 ≈236 (range 194–277) | [DFS Army](https://www.dfsarmy.com/2026/01/nfl-dfs-week-18-draftkings-milly-maker-review), [SI](https://www.si.com/onsi/fantasy/dfs/draftkings-millionaire-maker-winning-dfs-stacks-lessons-past-champions) |
| Winner slots absent from *every* candidate | 33/612 (5%), averaging 22.7 actual vs 7.2 projected | Addendum 116 |
| Realized 230+ lineups' simulated >230 worlds (of 50,000) | 1–22 | deep review |
| Selector-name diversity | ladders share 79.8/80 lineups; Jaccard 0.995 | deep review |
| Candidate shape | Legacy incumbent corpus: 100% QB+2+bring-back, a shape holding 16% of winners. Current R6 seven-profile union: relaxed profiles present, and 6 of 7 realized 230+ lineups came only from relaxed arms | structure census (legacy), deep review (R6) |
| Raw candidate doubling (CAND_MULT 2→4) | +4 pool-oracle 200+ weeks, selected 210+ fell 5→2 | Addendum 117 |
| Late-swap score alpha (q90-chasing from the ordinary book) | +0.9 mean best; hindsight-perfect swap bound +69 | Addendum 67 |
| Market movement / cross-book dispersion / tracking traits as projection signal | all null | Addenda 96, 96b |

Two derived observations the plan does not yet state plainly:

**(a) Retrieval is approximately random at 200+.** Using the deep review's own numbers (≈279 realized 200+ rows over 29 opportunity slates ≈ 9.6 per opportunity slate, N ≈ 3,690, K = 80), a uniformly random 80-lineup book would hit an available 200+ week with probability ≈ 1 − (1 − 9.6/3690)^80 ≈ **19%**. The best selector hit 24%. The eight-book union at its actual cardinality (~205) has a random reference of ≈ 41% and achieved 34% — *below* random. (These are back-of-envelope; the lead review's A2 amendment asks for the exact per-slate `1 − C(N−M,K)/C(N,K)` null, which should be computed. The heavy skew in M across slates will move the exact number, but not the conclusion.) Under the current belief law, the selector adds almost nothing at 200+; the only way to raise conversion without better beliefs is to raise the **density** of tail lineups in the corpus so that even near-random retrieval finds them.

**(b) The corpus is not dense in the tail, and the simulator does not know where the tail is.** 279 of 199,244 rows (0.14%) scored 200+; 7 (0.0035%) scored 230+. Realized tail lineups typically ranked in the thousands by simulated mean and had single-digit simulated >230 counts. A 30-point oracle gap to the winner therefore has two components: an irreducible part (the winner is the realized max over ~150k tickets — N1d showed a correct law would still put winners past p99.9 of their own distribution) and a reducible part (our candidates carry too little *real* joint-tail mass where reality puts it).

---

## 2. Assessment of the plan in progress

**Where the plan is right (and I would not relitigate):** the two-stage population/retrieval decomposition; "230 ≠ winning"; relaxed construction arms; the seven arms being structurally but not epistemically diverse; pure T230 too sparse; independent common-random-number evaluation banks; keeping the eight books as controls; a parallel field-model track; outcome-free screening before any labeled read; walk-forward calibration folds `CAL19/WF21/HOLD22`; no promotion from the spent 54.

**Where I would push back or re-weight:**

1. **The plan is still belief-centric when the objective is union-centric.** Lanes 1–3 are all about assigning more simulated probability to the right lineups. The external theory is unambiguous that when no entry's mean is anywhere near the threshold, the optimal portfolio is *variance-seeking per entry* and *anti-correlated across entries* (Haugh–Singal Prop 4.1, Fikioris et al.), and that required diversity rises as the within-pool signal falls toward zero (Kim et al.). The project measured that signal at ρ ≈ 0.03. The plan has no lane whose primary endpoint is "effective number of independent tail shots in the book". Section 3, R3 proposes one.

2. **The scheduler experiment (Lane 1) is the most *visible* misalignment, not the most *valuable* one.** Ranking visit-worlds by legal attainable optimum will find higher simulated optima in the same law. But N1c showed that world optima are not what wins (0/51 winners are any world's optimum; deep optima carry ~3× the never-realized excess of winning rosters), and Addendum 117 showed more optima from the same law degraded the selected tail. Lane 1 is cheap and should run, but its expected effect on realized 230+ is small. I would run it at low priority and not let it gate anything.

3. **The belief-law lane should start with the game-environment mechanisms that are already built and OFF**, not with new rare-breakout proposals. The production possession sim has team factors that are nearly independent across teams, and the Vegas-pace conditioning, TD ledger, Dirichlet usage competition, and big-play mixture are all implemented but disabled. Public correlation tables put WR1–opposing-WR1 at **0.56, higher than same-team WR1–WR2 (0.345)** ([SpikeWeek](https://spikeweek.com/visualizing-single-game-correlation/)) — a cross-team shootout channel the current law structurally under-produces, and the exact channel that game over-stacks (5–6 players from one game, common in 2024–25 winners) need. This is consistent with the project's own remeasurement (generic teammate booms over-coupled, QB→WR under-coupled). See R1.

4. **The fixed 194/230 lines should become a slate-conditional random benchmark.** Winning scores ranged 194–277 in 2025. The big-picture review already proposed a slate-conditional threshold; the plan dropped it. See R4.

5. **The biggest single lever is entry count, and the plan treats it as out of scope.** Coverage-in-k is log-linear over four orders of magnitude in the best-studied max-of-k setting ([Large Language Monkeys](https://arxiv.org/abs/2407.21787)); the project's own realized k-curve (mean weekly max 148.5 / 163.2 / 178.4 at 4 / 14 / 80 entries) is ~+9–12 points per ln-unit of k. Extrapolating to DK's 150-entry Milly cap predicts roughly **+5 points of mean weekly max** — more than three times the best selector gain ever measured (+1.55). See R5.

6. **Late swap is the only in-week source of genuinely new information and the plan does not mention it.** Addendum 67's null tested q90-chasing from an ordinary book. The recourse-aware initial-book protocol (frozen 2026-08-17) is the right design and should be elevated, because realized 1 p.m. results are exactly the "genuinely new pre-lock signal" that reopens selection under Addendum 95. See R6.

7. **Process overhead is now a first-order cost.** 182 handoff updates and ~50 R6 reports in about ten days, with most of them provenance plumbing. The lead review already separates "safe to test now" from "eligible to promote"; I would go further and give simulated-only experiments a receipt-light fast lane (one manifest, one hash, no root-last publication) so that a dozen belief/portfolio variants can be screened per day before Week 1. The irreplaceable clock is prospective field capture (§3, R8), not paperwork.

---

## 3. Recommendations, ranked by expected effect on the weekly maximum

Each item states: what, why (evidence), novelty against the ledger, how to test cheaply, and a rough expected magnitude. "Ledger status" is my reading of Addenda 60–120 and the 2026-08 reports; please correct me where a later verdict exists.

### R1 — Repair the shootout channel: a two-regime game-environment law built from mechanisms already in the codebase

**What.** Add a per-game latent regime (ordinary / shootout) that, in the shootout state, jointly raises pace (drive count), neutral pass rate, and both teams' team factors, with the mixture weight conditioned on pre-lock features (implied total, spread, both teams' pace and PROE, weather). Implement it as a composition of `GAME_SIM_PACE=vegas`, the Dirichlet usage allocator, and a calibrated cross-team factor correlation — all present in `models/simulate.py` / `models/game_sim.py` — rather than new machinery.

**Why.** Every 230+ lineup in R6 had six players ≥20 and 3–5 players ≥30; a 230 lineup needs ~25.5 points per slot, which under near-independent team factors is astronomically unlikely and under a shootout regime is routine. The current law's cross-team factor correlation is ~0.02; public tables put opposing-WR1 correlation at 0.56 and QB–opposing-DST at −0.46 ([FantasyLabs](https://www.fantasylabs.com/articles/another-look-at-nfl-correlations/)). 4for4's tail co-exceedance benchmarks (QB+WR1 ≥50 pts in 15.3% of games, ≥70 in 2.1%; QB+WR1+RB1 ≥75 in 7.8%; QB+WR1+WR2+RB1 ≥100 in 3.5% — [4for4](https://www.4for4.com/2018/preseason/definitive-guide-stacking-draftkings)) give an **outcome-blind calibration target** the law can be tested against without touching lineup outcomes.

**Ledger status.** Partly new. Schaake (rejected: worse variogram and tail Brier), conditional templates (better variogram, worse joint-q90 Brier), and the Gumbel QB factor (research) all tried to fix dependence *at the rank level on top of fixed marginals*. None changed the game-state generator itself, and none targeted the cross-team channel. The 2026-08-19 plan named "QB-to-WR under-coupled" but proposed no cross-team mechanism.

**Test.** (i) Reproduce the co-exceedance table from realized 2018–2025 box scores (nflverse, free); (ii) score the incumbent law and the two-regime law on it walk-forward, plus joint-q90 tail Brier and variogram (existing `research/dependence.py`); (iii) if the joint tail passes without marginal degradation, run the R6 population census (opportunity weeks at 200/220/230, tail density) under the new law with the *same* seven arms and solve budget. One image, one paired arm.

**Expected magnitude.** This is the only lever I can see that plausibly moves 230+ availability from 3/54 toward 8–10/54. It will not, by itself, fix retrieval.

### R2 — Give the marginals a real breakout component, with base rates from history rather than from the quantile extrapolation

**What.** Replace the linear extrapolation beyond TabPFN q99 with an explicit per-player mixture: `(1 − π) · TabPFN quantile curve + π · role-jump component`, where π is a walk-forward calibrated probability of a usage jump from pre-lock structural features (depth-chart slot, teammate injury designation, snap/target trend over the last 3 weeks, rookie/new-team flag, preseason usage, red-zone share) and the jump component is the empirical score distribution of historical players who *did* jump. Score it by exceedance calibration at 20/25/30/40 by position and projection tier, and by `E[score | score ≥ q85]` (the "conditional ceiling"), which practitioners find separates players with identical q85 ([FantasyLabs](https://www.fantasylabs.com/articles/understanding-ceiling-projections-gpps/)).

**Why.** The 33 winner slots absent from every candidate averaged +15.5 surprise (22.7 actual vs 7.2 projected), concentrated at WR/TE; Achane (sim mean 2.6 → 54.3), Bowers (11.1 → 46.3), London, Dowdle drove the R6 misses. The winner-anatomy audit found the opposite defect at the other end — deep optima built on single-player spikes that have never happened (+19.3 never-realized excess). Both are marginal-tail *shape* errors: too much mass on impossible spikes for high-projection players, too little on plausible jumps for low-projection players. A mixture with base-rate π fixes both directions at once; a uniform tail widen/shrink cannot.

**Ledger status.** Lane 2's "role-state mixture" is this idea; what is new is (a) using historical jump base rates rather than a tilted proposal with likelihood weights, and (b) the conditional-ceiling evaluation metric. Tracking traits (null) and market dispersion (null) are not needed for π.

**Test.** Outcome-bearing only at the player level (walk-forward seasons ≤2022 for fit, 2023–25 as calibration holdout — the plan's `CAL19/WF21/HOLD22` folds). Then population census under the new marginals. No lineup outcome read required until the sparse comparison.

**Expected magnitude.** Medium on 200/210 availability; necessary but not sufficient for 230.

### R3 — Build the book for effective independent tail shots, and report that number every week

**What.** Three coupled changes to the 80-entry book, all testable on the frozen R6 world matrices without any outcome read:

1. **Effective tail-shot diagnostic.** From the candidate×world indicator matrix restricted to tail events (≥ ladder rungs), compute the book's tail-event correlation matrix and its effective rank / `(Σλ)²/Σλ²`. Report it beside every selector result. Today no report says whether an 80-book is 80 shots or 12.
2. **Anti-correlated ("evil-twin") pairing as a selection primitive.** After each greedy pick, allow the next pick to be chosen from candidates whose tail-event vector is *negatively* correlated with the running book (home pass-stack vs. away pass-stack in the same game; RB+DST vs. opposing QB+2; 1 p.m.-heavy vs. 4 p.m.-heavy). Liu–Liu–Teo's DRO formulation recovers exactly this "evil twin" structure endogenously ([POMS 2023](https://journals.sagepub.com/doi/full/10.1111/poms.14013); [DeStefano–Doyle](https://math.dartmouth.edu/~doyle/docs/twin/twin.pdf)), and Bergman et al. found optimal two-entry sets "often score on opposite sides of their expectation" ([arXiv 2112.07002](https://arxiv.org/abs/2112.07002)).
3. **Overlap cap γ as an explicit, slate-conditional dial.** Hunter–Vielma–Zaman measured γ = 4 of 9 optimal on >9-game slates and 7 on <4-game slates ([arXiv 1604.01455](https://arxiv.org/abs/1604.01455)); Kim et al. proved diversity should increase as the signal becomes less informative ([arXiv 2407.13438](https://arxiv.org/abs/2407.13438)). A 13-game main slate with ρ ≈ 0.03 within-pool signal is the far end of both axes: try γ ∈ {3,4,5} against the incumbent (which has no explicit cap; the ladders' 0.995 Jaccard says the effective cap is high).

**Why.** `P(max ≥ T)` is a union probability. With positively correlated entries it collapses toward the single best entry; with disjoint tail events it approaches the sum. The multiplier available between those extremes is up to ~80×; nothing in the current selector family measures where the book sits on that axis. Theory (Haugh–Singal Prop 4.1(i)) also says each entry should individually be variance-seeking (`argmax μ + λσ²`, λ > 0) when no entry's mean reaches the benchmark; `boom` solves are implicitly variance-seeking, `lev` may not be — worth an audit.

**Ledger status.** The greedy scenario-coverage objective *is already* the incumbent (the outside memo's "novel scenario-coverage IP" is not new here), expected-max was tested (176.5 vs 178.4), and top-quantile ranking was tested (Addendum 114: recovers two misses, loses others). What is new: the effective-shots diagnostic, negative-correlation pairing, an explicit γ sweep, and the per-entry variance audit. The greenfield note already argued "uniqueness as a hard trait"; this is its measurable form.

**Test.** Fully simulated on frozen R6 candidates/worlds; freeze books on bank A, evaluate on bank B with common random numbers (Lane 4 tooling). One sparse labeled read later.

**Expected magnitude.** Small-to-medium on mean weekly max; potentially large on 220/230 *conversion* given availability, because that is exactly where union probability matters most.

### R4 — Replace fixed lines with a slate-conditional random benchmark

**What.** Model the field-max score `T_s` per slate from the winner registry and standings (51+ Milly winners plus the 2019–2024 CSVs), conditional on slate features (number of games, sum of implied totals, count of games with total ≥ 48, wind/weather flags, week number), using a GPD/extreme-conformal tail so the model is valid far into the tail ([Extreme Conformal Prediction](https://arxiv.org/pdf/2505.08578)). The selection objective becomes `P(max_i S_i ≥ T_s)` with `T_s` integrated over its predictive distribution, which reduces to a ladder whose rungs and weights move with the slate.

**Why.** The 2025 winning scores ran 194 (Week 1) to 277 (Week 12). A fixed 230 line over-spends entries on slates where 210 wins and cannot see the slates where 250 is needed. The plan's fixed ladder `200/210/220` with weights `1/4/12` is a hand-picked convexity guess. Haugh–Singal's entire edge over Hunter et al. came from modeling the benchmark as random rather than fixed ([Mgmt Sci 2021](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528)).

**Ledger status.** New as a selection input. The big-picture review proposed it; Addendum 68 (the F2 Gumbel-IID fix, empirical constant 0.256 field-SD) is the existing field-max calibration and should be the starting point. Note the winner-score *series* was judged selection noise for law calibration (N1d) — that finding is about calibrating the player law, not about modeling `T_s` itself, so this is ledger-legal.

**Test.** Walk-forward on seasons; report predictive coverage of realized winning scores; then run the ladder-with-random-rungs selector on the frozen R6 matrices as a registered challenger.

**Expected magnitude.** Small on mean weekly max; direct on the *contest* objective; also gives the operator a weekly "what score wins this slate" number.

### R5 — Quantify and then use the entry-count lever

**What.** Compute the realized k-curve on the frozen R6 books beyond 80 (nested prefixes 4/14/80 exist; extend to 100/120/150 on the frozen corpus with the incumbent selector, outcome-blind on the selection side, one grade read). Fit `mean weekly max ≈ a + b·ln(k)` and the threshold-hit curves `P(max ≥ t | k)`. Present the operator with dollars-per-point at each k and per contest.

**Why.** The published law is log-linear coverage in k over four orders of magnitude ([Large Language Monkeys](https://arxiv.org/abs/2407.21787); mechanism in [arXiv 2502.17578](https://arxiv.org/pdf/2502.17578)); the R6 4/14/80 points fit it. The extrapolation says 80→150 is worth ≈ +5 mean weekly max and roughly proportionally more 200+/210+ weeks — the largest number on this page. DK's Milly cap is 150; the qualifier contests have their own caps. It is an operator bankroll decision, but it should be made with the curve in hand.

**Ledger status.** The B1 volume-admission shadow (5→51 books raised selected mean 178.4→181.1 at fixed 80) addressed *candidate* volume, not *entry* volume. Entry count as a lever is acknowledged in Workstream E ("MORE ENTRIES per slate") but never quantified.

**Expected magnitude.** Largest available, at linear cost in entry fees.

### R6 — Late swap as a best-of-N policy (elevate the frozen recourse-aware protocol)

**What.** Two pieces. (i) *Initial book:* select the 80 for option value — every entry carries at least two 4:05/4:25 slots, split across the two or three highest-total late games, so the book is re-shapeable (this is `recourse_aware_initial.py`, frozen 2026-08-17, unrun). (ii) *3:55 p.m. policy:* classify entries by realized-so-far + reachable ceiling. Entries still able to reach `T_s`: re-solve late slots for maximum conditional variance on the remaining games (the over-stack of the single best remaining game). Entries that cannot reach it: convert into fresh evil-twin tickets on the late games (they cost nothing extra). Entries near the top: protect.

**Why.** Realized 1 p.m. scores are the only genuinely new information that arrives inside the decision window, so this satisfies Addendum 95's reopening condition literally. The hindsight bound is +69 mean best (Addendum 67); the +0.9 null was for a q90-chasing rule applied to a book not built for it. Practitioners run exactly this triage ("chase ceiling when behind, protect when ahead" — [Stokastic](https://www.stokastic.com/news/nfl-dfs-late-swap-strategy-with-stokastics-nfl-dfs-sims-ac11/); [RotoGrinders](https://rotogrinders.com/lessons/draftkings-strategy-and-utilizing-the-late-swap-feature-2709715)).

**Ledger status.** Tested once (null) with the wrong initial book; the corrected two-stage design is frozen but unexecuted. Late-game player *ownership* is also revealed post-lock, which the fade could exploit (noted in Addendum 67, never built).

**Test.** The frozen 54-shard score-free execution protocol already exists; run it. Its gate is a simulated p230 recourse-ceiling gain plus retention guards; a pass licenses a 2026 shadow. I would also add the trailing-entry "fresh ticket" rule as a second registered variant.

**Expected magnitude.** Unknown but the ceiling is enormous; this is the cheapest uncontested lever on the page and it uses information no competitor model has pre-lock.

### R7 — Allocate the generation budget across arms by realized tail index, walk-forward

**What.** Treat the generation arms (`boom`, `lev`, `dark`, `game`, the seven constraint profiles, and any new belief laws) as arms of an *extreme bandit*: allocate next season's solve budget in proportion to each arm's estimated upper-tail heaviness of realized candidate scores (a per-arm GPD shape / exceedance rate above 200 on prior seasons), not by hit-rate or mean.

**Why.** When only the maximum matters, the optimal policy plays the heaviest-tailed arm, not the highest-mean arm ([Carpentier & Valko 2014](https://papers.nips.cc/paper/5379-extreme-bandits); [David & Shimkin](https://arxiv.org/pdf/1512.07650)). The project already knows this qualitatively ("`dark` is the best value-per-candidate batch"; relaxed arms produced 6 of 7 realized 230+), but allocation is still equal across arms.

**Ledger status.** New as a rule. The A10 caution (arm exclusivity is not an allocation score) is right; the fix is exposure-normalized tail rates estimated on seasons *prior* to the one being allocated, which is walk-forward rather than panel-mined.

**Test.** Fit on 2019–2022 arm outcomes, allocate for 2023–25, compare corpus tail density at equal solver work against equal allocation.

### R8 — Prospective field capture is the scarcest asset; do it before Week 1 no matter what else slips

`contest_entries` has never received a row; DK purges standings in ~4 days; top-N rosters (not just #1), pre-lock projected ownership (ETR/Fantasy Points), and actual ownership are the inputs for everything in the field/duplication lane and for R4. Missed weeks are unrecoverable. The measured template for winners — cumulative ownership ≈ field (113% vs 114%), but **product** of ownership about half the field's; 2.3 sub-5% players; 88% of winners carry a ≥25%-owned player ([ETR/Levitan](https://establishtherun.com/levitan-winning-draftkings-milly-maker-trends/); [4for4](https://www.4for4.com/gpp-leverage-scores-balancing-value-ownership-dfs)) — implies the chalk fade should penalize Σ log(own) (≈ duplication probability) and be *capped*, not minimized. That is a field-lane change with zero effect on the raw-score objective and should not be prioritized over R1–R6 for the score target, but the data collection cannot wait.

### R9 — Structural quotas: let the law decide, but make sure the generator can express what wins

The winner data conflict with each other in a way that matters: the project's 51 #1 finishers are 22% naked-QB and 61% no-bring-back, whereas ETR's 452 top-10 finishers are *less* naked-QB than the field (6.4% vs 17.4%) and QB+2 is their largest single edge (41% vs 29%). #1 finishes are lottery-shaped; top-10s are edge-shaped. The right response is not a new mandate but coverage: ensure the arms can produce (a) 5–6-player single-game over-stacks (2024–25 winners; needs R1 to be valued), (b) QB-less RB+DST secondary stacks (present in 7 of 33 winners in one census), (c) sub-$6k QB funding three studs (45% of top-10s), and (d) cross-game "evil twins" (R3). The relaxed-arm results already show the machinery is there; what is missing is simulated support (R1/R2) and a book objective that keeps them (R3).

### R10 — Smaller, cheaper items

- **DST tail model.** Ownership-to-score correlation is lowest at DST (0.21 vs 0.47–0.55 elsewhere — ETR), meaning the field is worst there; a dedicated DST tail (sacks, turnovers, return/defensive TDs vs. opposing pressure and QB turnover-worthy-play rate) is unexplored in the ledger beyond scorer fixes.
- **max@k reweighting for generator hyperparameters.** The pass@k estimator's order-statistic weights ([arXiv 2505.15201](https://arxiv.org/abs/2505.15201), Eq. 14) give a low-variance signal for tuning generation settings on historical weeks where n > k candidates exist. Use only on seasons before the evaluation fold; it is panel mining otherwise.
- **Quality-diversity archive (Lane 3).** Keep it; the theory backs it (MAP-Elites achieves the optimal `1 − 1/e` on monotone submodular objectives where plain evolutionary search needs exponential time — [arXiv 2401.10539](https://arxiv.org/pdf/2401.10539)). Index cells by *tail-event signature* (which games/sides the lineup's tail depends on), not only by roster shape; that makes the archive the natural supplier of anti-correlated entries for R3.
- **Metric hygiene.** Report a ≥220 gate beside 194/200 in every table; 194 is the historical *floor* of winning scores, not a winning score.

---

## 4. What I would stop or deprioritize

- **More selector variants on the same score matrix.** Eight books at Jaccard 0.995 was the lesson. Until R1/R2 change the matrix, selector work should be limited to R3's diagnostics and the γ/anti-correlation primitives.
- **Pure T230 as a backbone**, for the reasons the deep review gives.
- **Raw candidate multiples** (closed by Addendum 117) and **more i.i.d. worlds** from the same law (the tail worlds are what matter; importance-sample or regime-condition instead).
- **Neo4j/UI/sidecar work before Week 1**, as the lead review already says.
- **Winner-implied law calibration** (demoted by N1d) and **regret-targeted generation** (superseded by N1c).

---

## 5. A concrete ten-day sequence before Week 1

1. **Day 1–2:** field-capture verification (R8); run the frozen recourse-aware initial-book execution (R6-i) as-is; compute the exact per-slate random-book null and the effective-tail-shots diagnostic on the frozen R6 books (R3-1) — all outcome-free or already-authorized reads.
2. **Day 2–4:** build the co-exceedance calibration table from realized box scores and score the incumbent law against it (R1 step i–ii); build the k-curve from frozen prefixes (R5).
3. **Day 4–7:** two-regime game law (R1) and breakout mixture (R2) as one image each; walk-forward player-level calibration only; population census on the R6 slate set.
4. **Day 7–9:** one joint 80-book challenger with evil-twin pairing + γ cap + slate-conditional ladder (R3 + R4) frozen on bank A, evaluated on bank B.
5. **Day 9–10:** designate the 2026 prospective primary (my recommendation: the R1×R3 crossing, with R6 as an exploratory shadow), freeze, and ship as shadows alongside the incumbent. Use the spent 54 slates once, as development evidence, exactly as the lead review prescribes.

---

## 6. Honest framing of what is achievable

Beating the #1 finisher of a 150k-entry field on a given week is a lottery-shaped event even for a perfect model (N1d). What *is* controllable is the thickness of each ticket's real tail and the number of effectively independent tickets. Today the book delivers ~178 mean weekly max, clears 200 in ~13% of weeks and 230 in ~4%. The levers above, in order of my confidence in their size: entry count (R5), late-swap recourse (R6), the shootout law (R1), book anti-correlation (R3), breakout marginals (R2), then the rest. If R1–R3 land and the book goes to 150 entries, I would expect the 200+ rate to roughly double and 230+ weeks to become an every-few-weeks event rather than an annual one; I would not expect, and would not promise, consistent Milly wins from any of it.

---

## Sources

Academic: [Hunter, Vielma, Zaman — Picking Winners](https://arxiv.org/abs/1604.01455) · [Haugh & Singal — How to Play Fantasy Sports Strategically](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528) ([preprint](http://www.columbia.edu/~mh2078/DFS_Revision_1_May2019.pdf)) · [Liu, Liu, Teo — Diversification through Portfolio Optimization](https://journals.sagepub.com/doi/full/10.1111/poms.14013) · [DeStefano & Doyle — Evil Twin](https://math.dartmouth.edu/~doyle/docs/twin/twin.pdf) · [Bergman et al. — Expected max of two Gaussians](https://arxiv.org/abs/2112.07002) · [Kim et al. — Madness of Multiple Entries](https://arxiv.org/abs/2407.13438) · [Mehta, Nagarajan, Ravi — Hitting the High Notes](https://arxiv.org/abs/2012.07935) · [Fikioris et al. — Data-Driven Solution Portfolios](https://arxiv.org/abs/2412.00717) · [Carpentier & Valko — Extreme Bandits](https://papers.nips.cc/paper/5379-extreme-bandits) · [Pass@K Policy Optimization](https://arxiv.org/abs/2505.15201) · [Large Language Monkeys](https://arxiv.org/abs/2407.21787) · [QD provably helpful](https://arxiv.org/pdf/2401.10539) · [Extreme Conformal Prediction](https://arxiv.org/pdf/2505.08578) · [Mlčoch et al. — generative models for DFS](https://onlinelibrary.wiley.com/doi/10.1111/itor.13344) · [Risk-taking in tournaments review](https://www.researchgate.net/publication/330264090_A_review_on_risk-taking_in_tournaments)

Practitioner: [ETR/Levitan winning Milly trends](https://establishtherun.com/levitan-winning-draftkings-milly-maker-trends/) · [ETR 2023 how to win](https://establishtherun.com/levitan-how-to-win-draftkings-milly-maker-in-2023/) · [4for4 stacking guide](https://www.4for4.com/2018/preseason/definitive-guide-stacking-draftkings) · [4for4 leverage scores](https://www.4for4.com/gpp-leverage-scores-balancing-value-ownership-dfs) · [SpikeWeek correlations](https://spikeweek.com/visualizing-single-game-correlation/) · [FantasyLabs correlations](https://www.fantasylabs.com/articles/another-look-at-nfl-correlations/) · [FantasyLabs ceiling projections](https://www.fantasylabs.com/articles/understanding-ceiling-projections-gpps/) · [FantasyLabs Wk5 2025 Milly review](https://www.fantasylabs.com/articles/nfl-dfs-week-5-millionaire-maker-review-breaking-down-the-winning-lineup-3/) · [DFS Army Milly reviews](https://www.dfsarmy.com/2026/01/nfl-dfs-week-18-draftkings-milly-maker-review) · [SI — lessons from past champions](https://www.si.com/onsi/fantasy/dfs/draftkings-millionaire-maker-winning-dfs-stacks-lessons-past-champions) · [RotoGrinders duplication](https://rotogrinders.com/articles/draftkings-milly-maker-strategy-avoiding-lineup-duplication-748722) · [RotoGrinders late swap](https://rotogrinders.com/lessons/draftkings-strategy-and-utilizing-the-late-swap-feature-2709715) · [Stokastic late swap](https://www.stokastic.com/news/nfl-dfs-late-swap-strategy-with-stokastics-nfl-dfs-sims-ac11/) · [DK Network Wk12 2025 winner (277.04, Winston 4%)](https://dknetwork.draftkings.com/2025/11/24/draftkings-fantasy-football-millionaire-winning-lineup-breakdown-week-12-2025/)
