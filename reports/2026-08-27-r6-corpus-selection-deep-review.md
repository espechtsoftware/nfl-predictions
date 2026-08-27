# R6 corpus population and 80-entry selection: deep review

- Date: 2026-08-27
- Repository head reviewed: `3e28b54656590284e2a7044ac67dfe35b5b9410b` (`main`)
- Performance release reviewed: `9d37548d` / sealed by `2d80c115`
- Decision status: descriptive diagnosis and prospective recommendations only; no promotion is authorized

## Executive conclusion

The system has two distinct problems, and treating them as one would send the next experiment in the wrong direction.

1. **Winning-lineup population is the dominant first-place problem.** Among 51 slates with a governed comparable winning score, the full R6 corpus reached or beat the recorded winner score once. The corpus oracle trailed the recorded winner by 30.03 points per matched slate on average. A better selector cannot select a contest-winning lineup that was never generated.
2. **Retrieval is nevertheless a large problem at reachable, lower tail levels.** The corpus contained at least one 200-point lineup on 29 of 54 slates, but the diagnostic union of all eight 80-entry selector books found one on only 10 of those 29 slates. The best single 80-entry book did so on 7. At 230 points, the corpus supplied only three opportunities; the selector union converted two, and the best broad tail-ladder book also converted two.

The correct next move is therefore **not another small selector sweep and not simply more candidates from the same law**. It is a stage-gated, equal-compute population experiment that creates genuinely different tail beliefs and high-quality structural niches, followed by one joint 80-entry selector that is robust across those genuinely different beliefs. Corpus ceiling must be evaluated before retrieval so a population gain cannot be hidden by selector behavior.

A fixed 230-point target must also be kept separate from “winning.” None of the seven R6 lineups scoring at least 230 beat the recorded winner on its slate. The only recorded-winner-score-beating corpus lineup scored 197.24 in a week whose recorded winning score was 193.94.

## Scope, provenance, and important boundaries

This review used the already-published, immutable R6 full-union artifacts. It did not regenerate candidates, rerun a selector, rescore a lineup, or issue another historical-outcome query.

Primary immutable inputs:

- realized grade root: `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-realized-grades/20260826-foundry-v12-r6-full-union-realized-v2/realized-grade-root.json`, generation `1787823913707002`, SHA-256 `7e5da240f6ad3978553fa3101e12d4414c993f9547bb76cfa999cf32acdb6dfc`
- panel freeze: `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-freezes/20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json`, generation `1787756181440564`, SHA-256 `57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467`
- fixed panel index: generation `1787663639938214`, SHA-256 `4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9`
- later-source freeze: generation `1787367678830738`, SHA-256 `c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a`
- outcome snapshot: generation `1787813630972164`, SHA-256 `3e03387372bb9326d260d951059f8b6bfb56104207d88656ec4ec158c89d54ce`

All 54 generation-pinned grade shards were read. The frozen task results and world arrays were read for the four slates needed for exact target attribution (`2023-w02`, `2023-w03`, `2023-w04`, and `2025-w09`). A read-only stream over all 54 frozen task results supplied the corpus-wide arm/occurrence census. One BigQuery lookup resolved player IDs to names; it selected names only and did not read scores or outcomes.

The analysis unit called a “lineup occurrence” below is one distinct lineup within one slate. The same nine-player roster identity on different slates is not treated as the same observation. Candidate outcomes within a slate are extremely dependent and must not be treated as independent statistical samples.

Unavailable and therefore not claimed here:

- full contest fields, actual contest rank, duplication, payout, and ROI;
- whether the 197.24 lineup was literally entered by somebody or would have won after all contest rules and ties;
- causal effects of individual generation arms (the arm results are overlapping, descriptive ancestry);
- pre-lock ownership and all desired point-in-time player traits for every attributed row;
- a reliable fitted model of 230+ traits: there are only seven such lineups.

## Review of the latest commits

The repository advanced while this review was running. Current `HEAD` is `3e28b546`, preceded by `07566839`. The aggregate performance report itself was published in `9d37548d` and sealed in `2d80c115`.

### What `07566839` and `3e28b546` do well

`07566839` adds the no-rescore attribution core. It exact-joins a frozen task result to an already-published realized grade and emits lineup roster, persisted realized score, descriptive generation ancestry, scope membership, book membership, and selector trace. Its stated boundaries are correct: it does not create per-player realized contributions, field ranks, ownership, payout, or ROI.

`3e28b546` adds a generation-pinned, root-last publisher and independent reopener for the 54 attribution shards. The guards are appropriately conservative:

- exact-open of the pinned panel and grade identities;
- a closed 111-object panel allowlist;
- no outcome-source reader and no scoring call;
- predecessor validation before create-once publication;
- exact byte comparison for resumability;
- root publication only after all 54 shards validate and reopen.

The tracked handoff reports 49 focused tests passing in 19.9 seconds and a production root-only preflight. I found no performance-science conclusion in these two commits that contradicts the frozen data and no reason to reinterpret the score report because of the release plumbing.

### Limitation, not a defect

Despite the subject “Publish root-last R6 attribution release,” the handoff explicitly says that no attribution output had yet been published at the reviewed commit. The commit implements and tests the publisher; it does not itself contain the completed 54-slate attribution dataset. Consequently, it improves reproducibility but does not answer whether high scorers existed or why they were missed. The analysis below answers those questions directly from the frozen predecessor artifacts. The publisher should not be invoked merely to validate this report; its separately governed next action remains in `HANDOFF.md`.

The aggregate report in `9d37548d` correctly identifies the tail ladder as the best final-fit 80-entry strategy on mean weekly maximum, but aggregate selected-book summaries alone conceal the most important decomposition: corpus availability versus conditional retrieval. Calling the tail ladder the leader is accurate; treating its +1.553 mean-score edge over coverage-194 as the main system bottleneck would not be.

### P2 analytical cautions in the new attribution schema

Static review found no P0/P1 correctness or no-rescore defect, but two summary semantics deserve explicit warnings:

- `selected_any`, `missed_by_every_book`, and their counts aggregate all 48 books across five holdout scopes plus the all-block final-fit scope. They do **not** mean “selected in a deployable final 80.” Deployment analysis must filter `scope_ordinal == 5` and `fit_scope_id == "all-block-final-fit"`. Every selection result in this report uses that final-fit scope.
- marginal selector traces are emitted for selected lineup IDs, not counterfactual gains for every unselected candidate. The release can establish ex-post score regret and exact membership, but cannot by itself distinguish model blindness from modeled-but-redundant misses. The diagnoses below therefore use the frozen task/world artifacts in addition to the grades. A future outcome-blind sidecar should expose simulated mean, threshold support, and counterfactual pick-80 marginal gain for audited candidates without rescoring.

## The population-to-selection funnel

### Corpus population

Across 54 slates:

| Quantity | Result |
|---|---:|
| Nominal generation outputs | 378,000 = 54 slates × 7 arms × 1,000 visits |
| Distinct lineup occurrences | 199,244 |
| Unique yield from nominal outputs | 52.71% |
| Duplicate/repeated nominal outputs | 47.29% |
| Distinct corpus size per slate, mean / median | 3,689.70 / 3,677 |
| Distinct corpus size per slate, min / max | 3,490 / 3,993 |
| All-lineup realized mean / median | 111.13 / 110.06 |
| Corpus-oracle weekly maximum, mean / median | 202.66 / 203.48 |
| Corpus-oracle weekly maximum, min / max | 160.46 / 242.36 |

The eight all-block final-fit books contain 640 slots per slate in total, but their union is only 204.85 distinct lineups per slate on average (range 181–229). Across the panel, that union contains 11,062 lineup occurrences, just 5.55% of the corpus. This union is a diagnostic upper bound across eight alternative 80-entry books; it is not itself a legal 80-entry deployment.

### Availability and conditional retrieval

| Realized threshold | Corpus lineup occurrences | Slates with corpus opportunity | Slates hit by union of 8 books | Union conversion given opportunity | Best single 80-entry slate hits |
|---:|---:|---:|---:|---:|---:|
| 187 | 887 | 44 | 24 | 54.5% | 17 |
| 194 | 483 | 36 | 16 | 44.4% | 9 |
| 200 | 279 | 29 | 10 | 34.5% | 7 |
| 210 | 105 | 18 | 6 | 33.3% | 5 |
| 220 | 34 | 10 | 4 | 40.0% | 4 |
| 230 | 7 | 3 | 2 | 66.7% | 2 |
| 240 | 2 | 2 | 2 | 100.0% | 2 |

At 200, the best single books were regime-robust ladder and strict-230 coverage with 7 of 54 weekly hits; that is only 7 of the 29 weeks in which a 200-point corpus lineup existed. The ordinary and block-supported tail ladders each hit 6. At 230, the ordinary and block-supported ladders converted two of the three available weeks, while the pure 230 selector converted one.

The all-strategy diagnostic union had a weekly maximum of 186.03 on average, versus the corpus oracle's 202.66. Mean regret was 16.63, median regret 17.10, and maximum regret 43.60. It selected the exact corpus oracle on only 9 of 54 slates. Each individual strategy selected the corpus oracle on only 3–5 slates.

Largest diagnostic-union misses:

| Slate | Corpus oracle | Best in union of all books | Regret |
|---|---:|---:|---:|
| 2023-w09 | 229.60 | 186.00 | 43.60 |
| 2023-w15 | 209.66 | 168.52 | 41.14 |
| 2024-w09 | 209.76 | 169.90 | 39.86 |
| 2024-w13 | 189.56 | 151.56 | 38.00 |
| 2024-w05 | 223.58 | 190.98 | 32.60 |
| 2025-w09 | 234.34 | 201.98 | 32.36 |

The stage decomposition is therefore unambiguous:

- **Recorded winner:** population ceiling fails on 50 of 51 comparable slates; selection fails on the sole recoverable slate.
- **230 points:** population ceiling fails on 51 of 54 slates; among the three available opportunities, the selector union and a broad tail-ladder book each recover two.
- **200 points:** population supplies 29 opportunities; the selector union recovers 10 and the best deployable 80-entry book recovers 7. Retrieval is a major bottleneck here.

## Did winning lineups exist in the corpus?

Only one slate's corpus contained a lineup that reached the governed recorded winning score:

| Winner comparison over 51 matched slates | Count |
|---|---:|
| Corpus max reaches or beats recorded winner | 1 |
| Corpus max within 10 points | 2 |
| Corpus max within 25 points | 20 |
| Oracle minus winner, mean / median | -30.03 / -28.38 |
| Oracle minus winner, min / max | -55.60 / +3.30 |

The sole recoverable slate was `2023-w02`:

- recorded winner score: 193.94;
- corpus oracle: 197.24;
- second candidate above the winner line: 195.64;
- best lineup selected by the union of all eight books: 176.12;
- selection regret to the corpus oracle: 21.12.

Both winner-score-beating candidates were Daniel Jones / Giants passing-game constructions, used $49,600–$49,700 of salary, and were modeled as ordinary-to-weak lineups rather than tail priorities. They are evidence of a belief/ranking miss, not proof of a greedy tie-breaking bug.

For the 197.24 lineup (`838d2cbca6c…`):

- exclusive source arm: remove-bring-back;
- three Giants paired with the quarterback and no Arizona bring-back;
- simulation mean 109.01, rank 2,670 of 3,835;
- simulated event counts out of 50,000 worlds: 230 at 194, 138 above 200, 49 above 210, 17 above 220, and 7 above 230;
- corresponding corpus ranks: 871, 811, 867, 856, and 653;
- at selection pick 80, its marginal gains lost to the selected cutoff under every strategy: 42 vs 82 for coverage-194, 33 vs 68 for strict-200, 169 vs 526 for the tail ladder, 845 vs 2,630 for block-supported tail, 5 vs 12 for strict-230, 0.0517 vs 0.0963 for expected-max, and 109.01 vs 118.89 for mean.

The 195.64 candidate (`09dae6d783c0…`) was similarly ranked near 2,680 by simulation mean, had only 76 simulated 200+ worlds and 8 simulated 230+ worlds, and lost every pick-80 marginal comparison. One candidate had no bring-back and one had one; the actionable commonality is not a rigid stacking rule, but that the realized Giants game outcome sat far above the model support assigned to the rosters.

The wording must remain “recorded-winner-score-beating corpus lineup.” Without the full contest field, ties, and settlement rules, this analysis cannot assert that it would literally have won the contest.

## Did 230-point lineups exist, and what did they have in common?

Seven lineups reached at least 230, on only three slates:

| Slate / lineup prefix | Score | Recorded winner | Selected by final-fit books | Source ancestry | QB stack / bring-back | Games / teams | Salary | Sim mean rank | Simulated >230 worlds |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| 2023-w03 `14013aae314c` | 242.36 | 296.38 | 7 of 8 (not T230) | 4 arms; incumbent shape | 3 / 1 | 5 / 6 | 49,500 | 6 / 3,648 | 19 / 50,000 |
| 2023-w03 `588c26a092b3` | 239.96 | 296.38 | none | remove-bring-back only | 2 / 0 | 7 / 7 | 50,000 | 3,106 / 3,648 | 1 / 50,000 |
| 2023-w03 `6db4967817af` | 239.10 | 296.38 | mean only | remove-QB-stack only | 1 / 1 | 7 / 8 | 49,900 | 5 / 3,648 | 2 / 50,000 |
| 2023-w03 `fdfab78bd83a` | 235.60 | 296.38 | none | allow-RB-vs-DST only | 2 / 1 | 5 / 6 | 49,800 | 478 / 3,648 | 10 / 50,000 |
| 2023-w03 `246a9ca0922d` | 230.24 | 296.38 | mean only | remove-QB-stack only | 0 / 2 | 7 / 8 | 49,800 | 3 / 3,648 | 4 / 50,000 |
| 2023-w04 `ba74e11a953e` | 241.10 | 253.70 | 6 of 8 | remove-bring-back only | 3 / 0 | 4 / 4 | 49,600 | 678 / 3,575 | 22 / 50,000 |
| 2025-w09 `4531567002c5` | 234.34 | 264.70 | none | remove-bring-back only | 2 / 0 | 7 / 7 | 49,700 | 1,696 / 3,733 | 4 / 50,000 |

Observed common traits, all ex post:

- every lineup had exactly six players score at least 20 fantasy points;
- each had three to five players score at least 30;
- top-three-player realized totals ranged from 108.70 to 135.06 (mean 119.69);
- even these extreme lineups carried a lowest individual score of only 4.2–9.1;
- all spent $49,500–$50,000, leaving at most $500;
- flex was WR four times, TE twice, and RB once.

What they **did not** have in common is just as important:

- QB stack counts ranged from 0 to 3;
- bring-backs ranged from 0 to 2;
- they spanned 4–7 games and 4–8 teams;
- one had a naked quarterback;
- one contained an RB against its own DST;
- none used two same-team running backs.

Six of seven were exclusive to one relaxed generation arm: three remove-bring-back, two remove-QB-stack, and one allow-RB-vs-DST. Only the 242.36 lineup had incumbent shape and appeared under multiple arms. This is strong evidence that a rigid incumbent-only construction law would have removed most observed tail successes. It is **not** enough evidence to mandate “no bring-back” or another hindsight rule: seven rows over three slates cannot distinguish structure from the particular realized player explosions.

The six-players-over-20 and near-full-salary findings are descriptions of the realized score arithmetic, not usable pre-lock predictors by themselves. A system needs beliefs that assign more probability to the players jointly producing those outcomes.

## Why were high scorers not selected?

There are two empirically different miss modes.

### 1. Model-support failure

Several eventual tail lineups looked weak in the 50,000 discovery worlds:

- `2023-w03 588c…` scored 239.96 but had simulation mean rank 3,106 and only one simulated >230 event. De'Von Achane had simulated mean about 2.60 and realized 54.3. The lineup's pick-80 tail-ladder gain was 34 versus a cutoff of 537; its strict-230 gain was 1 versus 12.
- `2025-w09 4531…` scored 234.34 but had simulation mean rank 1,696, >200-event rank 1,913, and >220-event rank 2,515. Its tail-ladder gain was 129 versus 660 and strict-230 gain 3 versus 15. Brock Bowers (simulated mean 11.11, actual 46.3), Drake London (14.76, actual 41.8), and Rico Dowdle (10.67, actual 31.1) drove the miss.
- both `2023-w02` winner-score-beating candidates sat around rank 2,670 by simulated mean and below every marginal cutoff.
- `2023-w03 6db…` and `246a…` were mean ranks 5 and 3 and were selected by the mean book, but their simulated extreme tails were thin: only 2 and 4 >230 worlds. This is a distribution-shape miss even when the central mean was favorable.

No selector operating only on these same worlds can consistently recover lineups to which the model assigns negligible or incorrectly shaped tail mass. Adding another algebraic transformation of the same score matrix is unlikely to cure this class.

### 2. Portfolio crowding under the model

`2023-w03 fdfa…` was not invisible. It ranked 255th by both 194 and 200 event counts, had events in all five blocks, and produced 10 simulated >230 worlds. But by pick 80, much of its simulated success overlapped scenarios already covered by the selected book. Its marginal gains were below the boundary: 58 vs 69 at strict 200, 223 vs 537 on the tail ladder, 7 vs 12 at strict 230, and 0.0694 vs 0.0928 for expected-max.

Likewise, the realized 242.36 oracle in `2023-w03` had 19 >230 events but added only 10 new >230 worlds at T230 pick 80, versus the selected cutoff of 12. Seven other selectors took it; the pure 230 selector did not. That is not a score-sorting mistake. It is the intended diminishing-return behavior interacting with a very sparse event.

The fix for this class is a better joint 80-entry objective and genuinely different scenario/model channels—not simply ranking individual `p230` and not arbitrary roster-overlap quotas.

## Review of corpus population mechanics

The current population mechanism is exact and reproducible, but its search allocation is poorly aligned with the stated goal.

For each slate it:

1. ranks each of five 10,000-world blocks by the sum of **all player draws on the slate** and retains 200 worlds per block;
2. for each retained world, solves one exact MILP optimum under each of seven constraint profiles;
3. produces 7,000 nominal outputs per slate;
4. deduplicates exact nine-player rosters by first occurrence and admits the full unique union.

The seven profiles are incumbent, remove salary floor, remove QB stack, remove bring-back, allow RB-vs-DST, allow two same-team RBs, and remove all five shared constraints.

### Finding: the world visit priority is not a feasible-lineup ceiling

`player_draws.sum(axis=0)` rewards a world in which many mutually exclusive players score well, including players who cannot coexist because of positions, teams, salary, or roster size. The actual objective is the best legal nine-player sum. Total slate draw is a cheap heuristic, but it is not an upper bound tightly coupled to the attainable lineup maximum. It can spend expensive MILP visits on globally hot but combinatorially unhelpful worlds while missing a world with one attainable, concentrated optimal roster.

The first population experiment should replace this scheduler with a cheap, legal-aware attainable-ceiling bound or a two-stage approximation while holding arms and solve budget fixed.

### Finding: almost half the solve output is repeated

Only 52.71% of the 378,000 nominal outputs become distinct slate-lineup occurrences. The generator has no unique-fill retry, no no-good feedback between visits, and no candidate-family injection. Repeated optima are therefore expected, but 47.29% repetition is a substantial compute allocation signal.

This does not imply “generate more random lineups.” A prior candidate-multiple experiment already added pool opportunities but degraded selected extreme-tail behavior. It suggests spending a fixed solver-stage budget on the next-best **high-quality distinct** solution in a world/niche when the first optimum is already in the archive, and judging the treatment first on corpus oracle/availability.

### Finding: the incumbent arm is almost entirely covered by relaxed supersets

Across the 54 slates, every arm has 54,000 source presences. Yet only 30 lineup occurrences are exclusive to the incumbent arm. Descriptive exclusive contributions were:

| Exclusive source arm | Exclusive distinct rows | Exclusive >=200 | Exclusive >=220 | Exclusive >=230 |
|---|---:|---:|---:|---:|
| incumbent | 30 | 0 | 0 | 0 |
| allow-two-RB | 2,083 | 4 | 0 | 0 |
| allow-RB-vs-DST | 4,120 | 9 | 1 | 1 |
| remove-salary-floor | 10,093 | 9 | 1 | 0 |
| remove-bring-back | 37,180 | 57 | 9 | 3 |
| remove-QB-stack | 38,873 | 55 | 5 | 2 |
| remove-all-five | 38,544 | 35 | 2 | 0 |

Overall, 130,923 of 199,244 corpus rows (65.71%) are exclusive to a single arm. Of the 279 rows at 200+, 169 (60.57%) are exclusive; of 34 at 220+, 18 are exclusive; and of seven at 230+, six are exclusive.

These are overlapping ancestry statistics, not randomized arm treatment effects. Still, they show that equal solve allocation is not equal marginal corpus contribution. A prospective treatment can retain an incumbent sentinel while reallocating redundant incumbent visits to distinct alternatives or new belief laws. It should not delete the incumbent outright based on this outcome-viewed panel.

### Finding: all seven arms share one epistemic model

The arms vary feasibility constraints, but all solve the same scheduled worlds from the same player-draw law. They are structurally diverse, not epistemically diverse. Five R0–R4 blocks are different random blocks from that same registered law. Calling a selector robust across those blocks establishes Monte Carlo stability under one model; it does not establish robustness to projection error, role uncertainty, alternative dependence, or market disagreement.

That distinction explains why constraint relaxations produced most 230+ candidates while several remained essentially absent from the model's tail.

## Review of the 80-entry selection mechanics

The eight strategies are sensible implementations of their registered objectives:

- greedy distinct-world coverage at 194;
- greedy distinct-world coverage above 200;
- weighted distinct-world coverage above 200/210/220 with weights 1/4/12;
- top simulated mean;
- greedy marginal expected book maximum;
- the same tail ladder scaled by number of supporting random blocks;
- leximin block-robust tail coverage;
- greedy distinct-world coverage above 230.

The evidence does not point to an elementary greedy implementation bug. On missed targets, exact pick-80 marginal gains are below the selected cutoff. A prior audit also found the incumbent coverage selector essentially solved its own objective. The core issue is objective/model alignment.

### The selector variants are much less diverse than their names imply

Across 54 all-block books:

- ordinary and block-supported tail ladders intersect on 79.78 of 80 lineups on average;
- they have identical sets on 48 of 54 slates and identical order on 47;
- their mean Jaccard similarity is 0.9946;
- block-supported tail contributes only four lineup occurrences not found in the other seven strategies, and ordinary tail contributes only two;
- regime-robust and ordinary tail intersect on 65.43 of 80 on average;
- coverage-194 intersects with expected-max on 63.15 and strict-200 on 63.04;
- mean-score is the genuinely different book, contributing 3,183 marginal-unique lineup occurrences (58.94 per slate); strict-230 contributes 838 (15.52 per slate).

Thus eight selector labels do not create eight independent channels. Most use the same score matrix and select the same tail-supported core. If the goal is one deployable book of 80, the design should optimize one portfolio across materially different belief channels rather than union or choose among near-duplicate complete books after the fact.

### Pure T230 is too sparse to be the backbone

For the seven eventual 230+ lineups, the model generated only 1–22 >230 events out of 50,000 worlds. On key slates the 80th pick added only 12–15 new >230 worlds. Small tail-count and overlap differences then control selection. The broad 200/210/220 ladder recovered both 240+ weeks and two of three 230+ opportunity weeks; strict T230 recovered only one.

Use T230 as a diagnostic or a limited channel until the simulator deliberately and correctly supplies more rare-event samples. The lower ladder rungs provide variance reduction and useful intermediate evidence.

### Expected-max is already present and does not solve model misspecification

The expected-max book directly greedily maximizes the simulated per-world maximum of the selected 80. Its realized mean weekly maximum was 176.54, below the tail ladder's 178.44, and it recovered six 200+ weeks. This falsifies the simple recommendation “change the objective to expected maximum” under the current beliefs. Expected-order-statistic methods remain valuable controls, but improving optimization against the wrong joint distribution will not recover model-blind outcomes.

## What external research implies here

The useful lesson from adjacent fields is to diversify **quality-bearing beliefs and outcome modes**, not merely roster overlap.

### DFS portfolio research

Hunter, Vielma, and Zaman formulate fixed-cardinality DFS portfolio selection around the probability that at least one entry wins, a submodular objective, and motivate high expected score, sufficient variance, and limited correlation with prior entries ([paper](https://arxiv.org/abs/1604.01455)). This supports joint portfolio optimization rather than selecting 80 individually attractive rows. The current world-coverage selector is already a more direct scenario-based form of this idea, so a generic variance or overlap constraint is not a novel cure.

Haugh and Singal model top-heavy DFS expected reward while explicitly modeling opponents' team selection and propose a multiple-entry algorithm ([Management Science](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528)). This matters because “score 230” and “beat a field” are different objectives. To optimize winning rather than a score proxy, the system eventually needs a point-in-time field/ownership/duplication model and contest-specific payout threshold. That model must remain separate from realized contest outcomes at selection time.

### Expected order statistics

Mehta et al. study selecting `k` uncertain items to maximize the expected highest value and provide approximation results, including a top-quantile rule under independence and monotone-hazard assumptions ([NeurIPS 2020](https://proceedings.neurips.cc/paper_files/paper/2020/hash/b6417f112bd27848533e54885b66c288-Abstract.html)). A top-quantile book is a useful registered benchmark. NFL lineups are highly dependent and need not satisfy those assumptions, and R6 already shows an expected-max selector can fail when its input distribution misses the relevant mode.

### Robust submodular selection

Krause et al.'s submodular saturation framework selects a set robust across multiple submodular objectives and can trade expected- and worst-case performance ([JMLR](https://www.jmlr.org/papers/v9/krause08b.html)). Distributionally robust submodular work similarly addresses generalization when the stochastic objective is observed through a limited sample ([Staib, Wilder, and Jegelka](https://arxiv.org/abs/1802.05249)). The direct application is robustness across **different calibrated model laws**, not merely five seeds from one law.

### Rare-target search and multifidelity learning

Active search asks how to find as many rare valuable items as possible under a fixed budget and shows the value of nonmyopic exploration/exploitation ([Jiang et al., ICML 2017](https://proceedings.mlr.press/v70/jiang17d.html)). Multifidelity active search adds cheap surrogate evaluations, such as simulations, alongside expensive ground-truth labels ([Nguyen, Modiri, and Garnett](https://arxiv.org/abs/2106.06356)). These ideas map better to allocating offseason generation/model experiments than to live book selection: simulations are cheap fidelities; realized weeks are scarce, expensive labels; and 230+ rows are rare targets.

### Quality-diversity search

MAP-Elites maintains high-quality solutions across predeclared behavioral niches and can improve both diversity and the best discovered solution ([Mouret and Clune](https://arxiv.org/abs/1504.04909)). This maps naturally to a candidate archive indexed by outcome-blind structural descriptors such as stack count, bring-back count, game concentration, flex position, salary band, and belief-law source. It is a corpus-generation mechanism, not evidence that every niche deserves equal entries in the final book.

Determinantal point processes combine quality and diversity in subset selection ([Kulesza and Taskar](https://arxiv.org/abs/1207.6083)). They are a possible benchmark, but roster-feature repulsion is secondary here because score-scenario coverage already discourages redundant outcomes. A DPP cannot recover a lineup that the model gives low quality.

### Rare-event simulation

The cross-entropy method adaptively tilts a simulation distribution toward a rare event and uses importance sampling to retain valid probability estimates ([Homem-de-Mello](https://pubsonline.informs.org/doi/abs/10.1287/ijoc.1060.0176)). Rare dependent portfolio events often require proposals tailored to multiple failure/success modes; mixture importance sampling is used for that reason ([Glasserman and Juneja](https://pubsonline.informs.org/doi/abs/10.1287/moor.1070.0276)). The R6 analogue is a mixture of calibrated “breakout,” game-environment, and role-uncertainty proposals. Samples must retain likelihood/proposal weights; tilted worlds cannot be counted as ordinary equal-probability worlds.

### Joint-distribution validation

Proper multivariate forecast evaluation matters because extreme lineups depend on player correlations. Scheuerer and Hamill show that the common energy score can be relatively insensitive to misspecified correlation and introduce variogram scores that are more discriminating ([NOAA-hosted paper](https://repository.library.noaa.gov/view/noaa/22327/)). The repository already tested a conditional dependence variant that improved variogram error but worsened the joint-q90 tail Brier score. That failed gate is useful evidence: better generic dependence fit is not sufficient unless the specific joint upper tail improves too.

## Prioritized recommendations

### P0 — change the scoreboard before changing the mechanism

For every frozen or prospective slate, publish a two-stage funnel at thresholds 187/194/200/210/220/230 and at the governed field threshold:

1. `population_available(t)`: whether any corpus lineup reaches `t`;
2. `population_count(t)`: number of distinct corpus lineups reaching `t`;
3. `selected_hit(t)`: whether the exact 80-entry book reaches `t`;
4. `conditional_conversion(t) = selected_hit(t) / population_available(t)` across slates;
5. corpus-oracle and selected-book regret to both the corpus oracle and recorded winner;
6. simulated support of realized tail rows: mean rank, threshold-count rank, block support, and pick-80 marginal gain/cutoff.

This prevents a selector improvement from being blamed for an absent corpus and prevents a larger corpus from being credited when the book still cannot retrieve it.

Maintain two explicit target families:

- score objective: probability at least one of 80 exceeds 200/220/230;
- contest objective: probability at least one of 80 beats a simulated field maximum after duplication/payout effects.

Do not call 230 “winning.”

### P1 — run one equal-compute, legal-aware world-scheduling treatment

The cleanest next causal test holds the seven constraint profiles, simulated law, 1,000 visits per arm, candidate admission, and selector bundle fixed. Change only the retained-world scheduler from total slate draw to a cheap estimate/bound of the best **legal attainable lineup score** in that world.

Possible implementations, in order of cost:

1. a position/salary-aware relaxation that upper-bounds the legal nine-player optimum;
2. a short-list heuristic that assembles the best feasible positional core;
3. a two-stage schedule that applies the cheap bound to all 10,000 worlds per block and exact-solves only the top 200.

Predeclare one version, not a grid. Judge it first on population opportunity counts and corpus-oracle winner gap under equal solve count. Only if that gate passes should its frozen candidate pool enter the same retrieval comparison. This directly tests the most visibly misaligned part of the current population algorithm.

### P1 — create genuinely different tail-belief producers

Develop prospectively frozen world laws that differ in epistemic assumptions, for example:

- calibrated baseline/marginal law;
- role-change and playing-time uncertainty mixture;
- correlated game-environment ceiling law;
- market-disagreement or model-ensemble law;
- rare-breakout importance proposal with correct likelihood weights.

The specific player examples above show why: Achane, Bowers, London, and Dowdle outcomes were not merely unselected; the relevant lineups received too little simulated tail mass. The remedy must allocate probability to plausible pre-lock breakout modes without using realized outcomes to name future players.

Validate each law walk-forward on player exceedance reliability and lineup-level 200/210/220 tail discrimination, with slate-clustered uncertainty. At 230, seven positives are enough for a diagnostic miss list, not parameter fitting. Preserve the repository's existing requirement that dependence changes pass both joint-tail and marginal gates.

### P1 — turn repeated solves into quality-diverse alternatives

Add a fixed-budget candidate archive with pre-lock descriptors. When a world/profile optimum is already present, spend a bounded remaining solver-stage budget on a no-good-constrained next solution or the best solution in an underfilled quality niche. Candidate descriptors should be frozen before outcomes and can include:

- QB stack count;
- bring-back count;
- primary game concentration;
- total games and teams;
- flex position;
- salary-left band;
- allowed-constraint profile;
- belief-law/source mode.

Require a simulated quality floor within each niche; do not fill weak cells for diversity alone. Retain a small incumbent sentinel and all materially distinct relaxed profiles. Compare at the same number of MILP solver stages, not just the same nominal visits. The immediate goal is higher corpus availability, not a larger raw row count.

### P1 — select one joint 80-entry book across model laws

Once at least two independently calibrated belief laws exist, replace eight parallel complete books with one portfolio objective over all laws. A useful form is a weighted tail ladder within each law plus a robust-saturation term that prevents any one law from receiving negligible coverage. Preserve diminishing returns at the scenario level.

An engineering shadow starting point—not a promoted allocation—is:

- a robust 200/210/220 ladder backbone;
- a limited strict-230/rare-proposal channel;
- a central-quality or top-quantile guardrail;
- a small model-disagreement / quality-diversity reserve.

Choose slot counts prospectively and hold them fixed. Do not choose the best of eight 80-entry books after viewing outcomes. Report each channel's marginal unique scenario coverage and realized opportunity conversion.

### P2 — add a field model for the actual winning objective

Hitting a raw score is not equivalent to winning. Acquire and freeze, where legally available:

- point-in-time ownership projections and their uncertainty;
- contest size and payout structure;
- a pre-lock opponent-lineup generator;
- duplication estimates and contest-field maximum distributions.

Then score a candidate by simulated probability of beating the field (or expected top-heavy payout), not only by exceeding a fixed line. Keep the fixed 200/220/230 metrics as interpretable diagnostics. Never use realized ownership or the actual winning lineup as a live selection input.

### P2 — use the spent panel for taxonomy, not another tuning sweep

Classify every realized 200+ and 220+ candidate into preregistered diagnostic buckets:

- model-blind: low individual tail support;
- modeled-but-redundant: good individual support, low pick-80 marginal gain;
- boundary/tie: marginally below cutoff;
- selected.

There are 279 rows at 200+, which may support slate-grouped descriptive or cross-fitted work. There are only 34 at 220+ and seven at 230+. Do not train a flexible reranker on seven positives. A new reranker is justified only after adding genuinely new point-in-time features or beliefs; earlier ranking/hedge audits did not improve the aggregate target reliably.

## A concrete experimental sequence for the next assistant

1. **Finish provenance, not science:** complete/reopen the separately governed attribution publication only under the existing handoff instructions. Do not rescore or query outcomes.
2. **Publish the funnel metrics:** implement reusable, no-rescore aggregation from attribution shards for population availability, selector conversion, miss taxonomy, arm overlap, and strategy overlap. Reproduce the headline counts in this report exactly.
3. **Register one scheduler treatment:** legal-attainable world ranking versus current total-slate-sum ranking, equal profiles and solve count. Freeze before any additional outcome join.
4. **Evaluate population first:** opportunity weeks at 200/220/230, corpus-oracle weekly max, recorded-winner gap, unique yield, and season stability. If it does not improve the population gate, stop.
5. **Evaluate retrieval second:** run the already-frozen selector bundle on both fixed corpora. This separates fill from selection.
6. **Build a prospective independent-belief shadow:** only after the scheduler result, add one registered alternative tail law with likelihood/provenance semantics and evaluate calibration before lineup outcomes.
7. **Combine only passing laws into one 80-book robust selector:** keep the current tail ladder as the incumbent backbone; T230 and expected-max remain controls until they show prospective value.

Recommended minimum reporting table for every treatment:

| Stage | Primary metrics | Guardrails |
|---|---|---|
| Belief/world law | player exceedance calibration; lineup 200/210/220 discrimination; joint-tail score | marginal calibration; PIT purity; season stability |
| Corpus | opportunity weeks; tail-row counts; oracle max; winner gap | exact solve budget; unique yield; legal validity |
| Retrieval | conditional conversion; selected weekly max; corpus regret | exact 80; model/channel exposure; no outcome input |
| Contest | beats-field probability / expected payout | ownership calibration; duplication; contest specificity |

## What not to do next

- Do not multiply raw candidates again under the same law. The prior candidate-doubling treatment added opportunities without reliably improving selected extreme outcomes.
- Do not repeat an all-boom allocation or another small threshold/selector sweep on these known outcomes.
- Do not hard-code remove-bring-back, naked-QB, full-salary, or six-players-over-20 rules from seven ex-post rows.
- Do not treat five random blocks from one simulator as five model regimes.
- Do not use roster overlap, DPP diversity, or a no-good archive as a substitute for simulated outcome quality.
- Do not deploy pure T230 as the whole book while its events are this sparse.
- Do not claim the expected-max objective is absent; it was tested and did not overcome belief error.
- Do not optimize the 230 proxy and describe the result as a winning strategy.

## Bottom line

R6 demonstrated that relaxed construction families matter: six of seven 230+ lineups would have been absent under incumbent shape alone. It also demonstrated that the present model/world law usually does not populate a winning lineup and frequently assigns weak tail support to the high scorers it does populate. The selector then compounds the problem by converting only about one-third of available 200-point weeks, while several nominally different selectors mostly choose the same lineups.

The highest-value path is:

**legal-aware and rare-mode-aware population -> independently calibrated belief laws -> one robust joint 80-entry portfolio -> field-aware winning objective.**

Measure and gate each arrow separately. That is the shortest route to learning whether the next gain came from finding better candidates, believing in them for defensible pre-lock reasons, or allocating the 80 slots more effectively.
