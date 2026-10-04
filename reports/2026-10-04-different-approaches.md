# Completely different approaches (2026-10-04)

**For:** the operator (what to pursue) and the reviewer (novelty and design).
**Asked:** "think completely outside of the box and for the process of adding lineups to the corpus, consider
completely different technologies, completely different approaches, and the same for every aspect of just adding
things to the corpus, putting lineups together, selecting them, sorting them."
**Status:** nominations only. Nothing changes the money path. Each item lists its closest prior attempt so the
reviewer can rule on novelty.

## 1. Where outside-the-box thinking can pay, per the evidence

- **Generation (the corpus) is not the bottleneck.**
  - Every player in the W1–3 winning lineups was in our pool (81/81).
  - In W3 the pool held 200+ rows that we did not enter.
  - Some twenty generator families are closed (CE, Schaake, EPI, Gumbel, covering arrays, anchor/LNS, medoid worlds,
    learned templates, ...).
  - A different *generator* is the least likely place to win. The one generation idea below changes what the corpus is
    *for*, not how it is sampled.
- **The money is lost in selection, information and contest choice.**
  - Lifetime ROI is −83.5%; the qualifier class returns −96%.
  - The entered book has lost to simple baselines.
  - So most ideas below target selection (what to enter), information (what we know that the field doesn't) and the
    contest itself (where and against whom).

## 2. The 09-25 outside-the-box round, and what to do with it

`reports/2026-09-25-outside-the-box-strategy-research.md` (R1–R19) and its plan
(`reports/2026-09-25-plan-from-outside-the-box-review.md`) already nominated many "different" ideas. Their status, and
my recommendation for each:

| 09-25 idea | Status | Recommendation |
|---|---|---|
| R17 inverse-optimisation field model (a random-utility model on the captured lineups) | Logged, "needs a sponsor" | **Sponsor it now: it IS study 10** (the field-behaviour model). Fit the crowd's implied values and stacking beliefs |
| R14 LLM news agent as a FACT EXTRACTOR (structured, timestamped, append-only), graded 4–6 weeks before any use | Planned Weeks 6–8 | **Start the logging now.** It costs nothing on the money path, and the grading clock only starts when logging does. We already store FP article text |
| R12 duplication-aware payoff | Folded into PREREG-L07 | Pair it with study 10 and P8 |
| R6 market-consistent worlds (per-game entropy pooling) | Weeks 6–8 | Keep. Note: P6-style coupling repair is closed; R6 changes the marginals, not the coupling |
| R7 a third, empirical critic; disagreement-aware selection (the optimizer's curse) | Weeks 6–8 | Keep. It is the principled answer to "Skattebo/Wicks"-type over-trust in thin edges |
| R2 follow the crowd's information, fade only its recency-chasing | PREREG-L07 | Status to confirm (R2(a)/(b)) |
| R10 information coefficients in the scoreboard | Planned 09-28 | Status to confirm; fits P3 |
| R16 public betting splits as an ownership signal | Logged | See X6 (generalised to public attention) |
| Alternate prop ladders | Tested: the mechanism gate failed (09-02 review) | Closed |
| Same-game-parlay prices as correlation | No provider route (09-02) | Blocked |
| Kalshi | Null in W3 | Closed |
| Simulator coupling repair, pace=vegas | Closed (reviewer 10-04) | Closed |

## 3. New approaches (beyond both rounds)

### X1. Scenario arbitrage: leverage on whole game scripts, not single players
- **Idea.** The ownership term and the field sleeve work player by player. Large-field contests are won by being right
  about a *scenario* that the field under-plays: a shootout in game G, a blowout in H, a backup RB's takeover.
  - Use the market (totals, spreads, team totals) for each scenario's probability.
  - Use the field-behaviour model (study 10) for the share of the FIELD built on it (QB stacks of that game, bring-backs,
    the game's total ownership).
  - Over-allocate our tail rows where probability ÷ field share is highest.
- **Why different.** It moves leverage from player marginals to the combinations that decide tournaments. It needs no
  better projection, only a better model of the field (which we can now build) and the market (which we trust most).
- **Closest prior.** R12 duplication (player-combination level); medoid/coherent worlds (closed, but those were
  *generators*); P(top-N) selection (negative). The difference: the decision variable is the allocation of rows across
  scenarios, priced against the field's allocation.
- **First test.** Outcome-blind: on W1–4, compute each game scenario's market probability vs the field's share from
  `contest_entries`, and show how large the mispricings are. If they are small, stop.

### X2. A field-softness index: choose contests by WHO you play, not only by payout
- **Idea.** From 1.49M lineups with entry names, measure each contest type's field:
  - the share of entries from multi-entry "sharks" (max-entry users, repeat top finishers);
  - the share of dominated lineups (salary left on the table, no correlation, ruled-out players);
  - duplication.
- **Why.** P1 asks where we are +EV given our results. X2 asks why: some contest types are simply softer. Combined
  with P1, it turns contest choice from ROI history (noisy) into a structural measure (stable).
- **Closest prior.** R13 contest economics (rake only). New: the opponent-quality measure.
- **First test.** Descriptive, outcome-blind (lineup construction only) on W1–4. Then check whether softness predicts
  our realized cash rate by contest type.

### X3. A portfolio of methods with online allocation (a bandit across strategies)
- **Idea.** Stop choosing ONE book-building method from a historical panel. Run several distinct methods every week:
  - the current book;
  - simple baselines (P3);
  - FP-term and lag-term variants;
  - a field-like book.

  Grade them weekly on tickets and line hits, and shift the ENTRY allocation toward methods with posterior evidence of
  edge (Thompson sampling with a conservative prior; most weight on the incumbent until evidence accrues).
- **Why different.** It accepts that the panel cannot settle the deep tail (057) and that the season is short. The
  system learns which approach works *this* season, with a principled exploration cost.
- **Closest prior.** P3 (benchmarks only), adoption track v2 (manual decisions). New: automatic, posterior-driven
  allocation.
- **First test.** Paper only: simulate the allocation rule on the P3 arms' weekly results as they accrue. Money only
  after the operator adopts the rule.

### X4. The operator's own signal, logged and graded
- **Idea.** The operator flagged Flowers (scored), Skattebo and Wicks (doubted) and the Bears DST in real time.
  - Log his pre-lock reads in a small form: "like", "fade", "worried about"; timestamped before lock.
  - Grade them weekly against our projection residuals.
  - If a human signal has edge, a small operator-tilt sleeve is a legitimate arm.
- **Why different.** Every other input is a machine signal. A human with a strong prior is a distinct information
  source, and it costs nothing to measure.
- **First test.** Start logging Week 5 (the dashboard could host the form). Grade after about 6 weeks.

### X5. Frequent-pattern mining: which COMBINATIONS win more than the field plays them
- **Idea.** Association-rule mining (support, lift) on winners vs the field: which player pairs, triples and stack
  shapes appear in the top 0.1% far more often than their field frequency, across weeks. The Neo4j graph is built for
  exactly these queries.
- **Why different.** It finds interaction structure directly from real outcomes rather than through a simulator whose
  coupling is known to be wrong.
- **Closest prior.** Study 2a (how leaders use popular players); stack studies. New: a systematic search with lift and
  false-discovery control.
- **Guard.** Many combinations means many false positives. Use study 9's guard: explore, then a frozen short-list,
  confirmed on other weeks and seasons.

### X6. Public attention as an ownership signal
- **Idea.** Ownership is driven by attention: article mentions (A3 counts FP titles), public betting splits (R16),
  social-media mention volume (Reddit r/dfsports, X), Google Trends.
  - Capture an attention index per player pre-lock.
  - Test it against realized ownership BEYOND FP's projection.
- **Why.** Ownership errors are where leverage lives. FP is a strong baseline; residual attention may explain its
  misses.
- **First test.** Capture only (prospective). O1-style reading after 4 weeks.

### X7. A language model as a lineup CRITIC (long shot)
- **Idea.** Ask a reasoning model, pre-lock, to critique each candidate lineup's game-script coherence (does the stack
  make sense given the matchup, injuries and news?) and score it.
- **Prior: low.** It can only be tested prospectively, because models know historical results. It is noisy and slow.
- **Do only** as a logged side arm if X3's framework exists.

### X8. A graph neural network over the player–team–opponent graph (long shot)
- **Idea.** Learn interaction effects (QB–WR synergy, opponent coverage fit) from the graph instead of hand features.
- **Prior: low.** Projection skill is dominated by the market. **Do only if** study 9 finds real interaction signal
  that linear models miss.

### X9. A different corpus: build it to SPAN scenarios, not to maximise score per world
- **Idea.** Today's supply takes the best lineup in each simulated world (boom). Instead, generate the corpus to cover
  the scenario grid from X1 (each game × {shootout, normal, low}, key role changes), with K lineups per cell, so
  selection can allocate by scenario.
- **Why.** This is the generation change that X1 needs. It is different in purpose, not in sampler.
- **Closest prior.** Medoid / coherent member worlds (closed as *selection* improvements). Note the risk: it may
  repeat their null.
- **Do only if** X1's outcome-blind mispricing check is large.

## 4. What I would not do
- Another generator family aimed at a higher score per world (the closed list is long; the pool is not the
  bottleneck).
- Re-propose finish-probability (P(top-N)) selection (negative, 098) or simulator coupling (closed).
- Use any language model to forecast outcomes (markets beat them near resolution; the 09-25 evidence).

## 5. Recommended picks
1. **Start now (logging, no money-path change):** R14 LLM fact log; X4 operator-signal log; X6 attention capture. Their
   grading clocks start only when capture starts.
2. **Build with study 10:** R17 inverse-optimisation field model. Then X1's outcome-blind mispricing check and X2 field
   softness. They share the same data and code.
3. **Wire with P3:** X3, paper only.
4. **Later or conditional:** X5 (after study 9's guard exists), X9 (only if X1 shows large mispricing), X7/X8 (long
   shots).
