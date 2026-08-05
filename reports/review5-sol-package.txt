# Independent review #5 (2026-08-05): the generator frontier

You are the third independent reviewer of a DraftKings NFL DFS system
(two Gemini review rounds preceded you; every finding was implemented
and tested same-day — see "State of play"). You have access to the
codebase; this document gives you the evidence base and the frontier.
Be adversarial: do not restate our conclusions, attack them. Every
prior reviewer's testable claim went to a six-season panel within
hours. Yours will too.

Ignore `reports/review-archive/` (superseded historical briefs) and
treat ledger addenda 58-77 in `reports/2026-07-25-system-study.md` as
the authoritative record wherever this summary compresses.

## 0. State of play — what the last 24 hours already resolved

Read this first so you don't re-litigate closed questions:

- **Selection is exonerated.** The strongest selection-defect
  hypothesis (binary greedy coverage scatters co-booms; fix = a
  log-sum-exp depth-rewarding objective) was implemented exactly as
  its proposer specified and run on the full panel: tails 25/107 vs
  control 25/107, mean best 179.3 vs 179.7 — its own pre-registered
  falsification triggered. Decisive detail: the WEEKLY MAX lineup was
  byte-identical to control in all six seasons. Every selector finds
  the same ceiling; the ceiling is a property of the candidate pool.
  **The wall is the generator.**
- **The ownership barbell null**: replacing our smooth chalk fade
  with a winner-anatomy barbell constraint (>=3 sub-5%-owned skill
  players + >=2 mega-chalk) scored 24/107 vs 25 control. The
  constraint verifiably fired (portfolio chalk level 0.39 vs 0.26).
- **The alternate architecture is at exact parity**: a from-scratch
  construction (per-world argmax as primary generator +
  beat-the-field-bar selection) scores 25/107 = control, once its
  field bar was empirically calibrated (sample-max + 0.256 sd,
  measured from 63 real contests).
- **Field co-ownership independence is mildly conservative, not
  naive-optimistic**: from 74 real contests' full per-entry
  standings, the median joint/product inflation of top-20 owned
  pairs is 0.87 (p90 1.08; only 0.3% of pairs exceed 1.5x; 20% are
  repelled below 0.67x by cap substitution). Max chalk-pair
  inflation 1.7x (RB + own DST). Showdown-format caveat applies.
- **Our own difficulty diagnostics are Gaussian and wrong in our
  favor**: summing per-week Gaussian-implied P(clear 194) predicts
  17.9 clears for our portfolio; it actually clears 25. The boom
  entries carry a heavy right tail the normal fit can't see. (So any
  "your sim says N@237 = trillions" argument is measuring the
  diagnostic's normality assumption, not the sim.)
- **The assembly batteries are in** (2025, 40 entries): best-entry
  overlap with the hindsight optimal is below the random null for
  EVERY construction — control 2.00 (null 2.38), LSE 1.78 (2.30),
  alternate architecture 1.56 (2.37). LSE's second pre-registered
  falsification also triggered. Below-null overlap is a structural
  property of world-coverage portfolio selection, not an algorithm
  defect. One mechanism lead: the alternate architecture's
  per-world-argmax generator puts MORE of the optimal slate in the
  pool (81.2% vs 77.8%; optimal QB present 15/18 vs 13/18) at equal
  capture — more raw material, same concentration failure.
- **Two deletions just passed their pre-registered tests** (both
  rules were pre-ensemble adoptions never re-validated after the
  ensemble): removing the chalk fade scored 26/107 (never negative
  in any season); removing the punt mandate + punt-boom valuation
  scored 26/107 with a BETTER mean best (180.6 vs 179.7) and the
  program's highest-ever single score (271.1). A combined-deletion
  interaction guard is running; defaults flip only if it holds >=25.
  Treat the fade and the punt mandate as dead unless the guard
  fails.
- **4-entry concentration refuted**: forcing all 4 small-contest
  entries onto one QB family scored 1/107 vs the fixed-line slice's
  3/107 (mean best ~143 vs ~152).
- **In flight right now** (results may exist by the time you reply;
  we'll share): SHARP — conditional-peak "glass cannon" selection
  (sharp-alpha LSE ranks candidates by their own best worlds;
  registered prediction: null-or-worse, since selection is
  exonerated). HYPER — manufactured collinear game scripts: for the
  top 8 games by projected total, a synthetic world where every
  in-game player sits at his own p98 SIMULTANEOUSLY, MILP-solved,
  injected into the candidate pool. And DELETE2 — the combined
  deletion guard above.

## 1. What the system is

- **Task**: 40-50 lineups/week into DraftKings NFL tournaments
  (a "Milly Maker": ~150k entries, top-heavy payout; plus ~20k-entry
  qualifiers where only ~top-4 seats matter). Lineup = QB, 2-3 RB,
  3-4 WR, 1-2 TE, FLEX, DST under a $50,000 cap.
- **Data**: free only. nflverse play-by-play (2016-2025), DK salaries,
  historical contest standings + ownership for ~107 main-slate weeks
  (2019, 2021-2025), sportsbook prop lines, weather. BigQuery;
  Cloud Run jobs (incl. L4 GPU) for all heavy compute.
- **Player model**: per-component LightGBM ensembles (3 seeded
  column-shuffled members averaged; the ensemble was the single
  largest gain of the program: 25 vs 14 same-build control), trained
  walk-forward, strictly point-in-time. Per-player quantile marginals
  from TabPFN (zero-shot tabular transformer), cached; the sim
  samples those marginals, correlated by a possession-level Markov
  game simulator. Prop-market distributions blended in (validated
  blend weight ~0.45).
- **Construction** (`src/nfl_dfs/backtest/engine.py`,
  `src/nfl_dfs/optimizer/lineup.py`): simulate ~2,000 correlated
  worlds/slate; candidates from (a) per-world argmax MILP solves
  ("boom": 13% of candidates, ~54% of weekly bests), (b) diverse
  mean-objective MILPs, (c) leverage/game-stack/dark-game batches.
  Validated hard rules: QB+2 same-team pass-catchers + opponent
  bring-back; one sub-$4k punt valued at its p90 (deletion PASSED —
  treat as dead); chalk fade on our objective (deletion PASSED —
  treat as dead); salary floor $49k; sub-$4k punt-boom archetype
  boost (dies with the punt deletion).
- **Selection** (`select_tail_entries`): greedy max-coverage over
  worlds on P(best-of-N >= line). Entries are co-equal; the system
  cannot rank its own entries within a week (best scorer's selection
  rank: median 20-22 of 40; uniform).
- **Evaluation**: six-season deterministic replay panels on Cloud
  Run; co-run controls; LOSO adoption rule (>=4/6 seasons positive,
  <=1 negative); vacuity checks (byte-identical arms = dead lever);
  70+-addendum experiment ledger with cause-of-death burials
  (`reports/2026-07-25-system-study.md`).

**Headline metric**: weeks (of 107) where best-of-40 clears 194 (the
MINIMUM winning Milly line in our data; average winning line ~237).
Sealed system: **25/107**, mean best 179.7, median contest percentile
14.1%.

## 2. The measured frontier — what any improvement must now explain

- **The assembly numbers**: hindsight-optimal lineups average ~268.
  Real winners capture ~88% of weekly optimal. Our best-of-150: 69%.
  84% of optimal players appear somewhere in our pool; the best entry
  holds 1.87 of the optimal 8 — below the exposure-preserving random
  null (2.51). LSE's falsification proved this is NOT a selection
  artifact: **the candidate pool does not contain the co-boom
  combinations.**
- **Environment-gating**: we clear the line when the slate booms
  (cleared weeks: entry-score mean 131, sd 28.4; missed: 122, 22.9).
  Player identification is not the binding constraint; the sim's/
  generator's coverage of extreme slate environments may be.
- **EVT context** (verified): naive Gaussian extreme-value scaling
  puts best-of-40 at ~sqrt(ln40/ln150k) ~= 55% of a 150k-field max;
  we measure 69% (heavy-tailed construction), humans-in-aggregate
  88%. The remaining 19 points cannot come from marginal-projection
  accuracy (proven three ways); they must come from combination
  structure and/or field exploitation.
- **Winner anatomy** (74 contests, full per-entry standings): ONLY
  the winner stratum is contrarian (own-sum ~235 vs 245-254 for ALL
  other strata including 2nd-10th) and unique (~85% duplicated vs
  ~97%). Near-winners are chalk mirrors that split prizes.

## 3. The graveyard (attack a burial's method or move on — do not re-suggest)

All six-season panel tests vs the sealed 25 control, post-ensemble,
deterministic, vacuity-checked. Selection: LSE alpha=0.08 (25, own
falsification), BARBELL (24), dollars-objective at 4 entries (null),
PEAK_SLICE reserve-slots-for-peak (21), QB-cap MAX_QBS (held).
Generation: q99 ceiling-wildcard injection (23), N_BOOM dose 100
(25), loosened stacks x2 (17, 17), no-stack batch (0 survivors),
vacancy-boost v2 (21), VALUE2E cheap-stud tier (26, noise), WR-boom
mid-band (null), dark-game dose (adopted at default, extra null),
showdown-fade (x2 vacuous then null), DIV_TILT prop-divergence
(pending-null), script-feedback (null post-ensemble), rookie-widen
(negative), alt-ceiling (negative post-ensemble). Models: HistGB
ensemble member (21 — family diversity subtracts), LEM learned game
sim (failed rollout gate 2/5), TabPFN-mean-swap (null; marginals
adopted, means not), MODEL_ENSEMBLE=5 (no gain over 3). Ops: legal
late-swap q90-chase (+0.9, null; hindsight-perfect +69 unreachable).
Post-ensemble law: three pre-ensemble "wins" inverted when re-tested
— any pre-ensemble verdict you see in the ledger is unreliable in
both directions.

## 4. Code map (you have the repo)

- `src/nfl_dfs/backtest/engine.py` — candidate generation + selection
  (tail_select_lineups; HYPER_BOOM/M4_QBLOCK levers at top of the
  generator section; _select_qb_concentrated).
- `src/nfl_dfs/optimizer/lineup.py` — MILP (optimize), stack rules,
  punt/value/barbell constraints, select_tail_entries +
  _select_lse_entries.
- `src/nfl_dfs/backtest/replay.py` — the replay harness: slate
  build, ownership model, leverage fade, TabPFN marginal plumbing,
  draw shaping, diagnostics (entries-to-line, entry anatomy, capture
  rates, duplication).
- `src/nfl_dfs/models/components.py` — per-component ensemble;
  `models/ownership.py` — ownership booster.
- `src/nfl_dfs/graph/` — possession-Markov game sim.
- `scripts/diagnose_portfolio.py` — the assembly battery.
- `reports/2026-07-25-system-study.md` — the 75-addendum ledger
  (Addenda 58-75 cover everything summarized here).

## 5. Questions

1. **Generator surgery**: given that the pool lacks co-boom
  combinations, what SPECIFIC change to candidate generation (code
  change in engine.py/lineup.py, panel-testable) would you make
  beyond the in-flight HYPER_BOOM? If your answer is a variant of
  q99-injection, boom-dose, or stack-loosening, explain why the
  graveyard's version tested wrong.
2. **Is HYPER_BOOM designed right?** p98-per-player within one game,
  others at median, top-8 games by projected total. Critique the
  design: quantile choice, game selection (projected total vs
  volatility vs Vegas total), one-game-at-a-time vs correlated
  multi-game, injection-via-pool vs forced slots.
3. **The 88%-vs-69% decomposition**: winners' extra 19 points of
  capture — how much is (a) combination structure we can build, (b)
  100k-entry-scale luck we cannot, (c) field-blind spots we could
  exploit with the September standings data? Propose a measurement
  that splits (a) from (b) using data we already hold (the
  74-contest archive, hindsight optima, our replay exports).
4. **What would you DELETE or simplify**, given code access? Name the
  file/rule and the panel test that justifies removal.
5. **September build priority**: skeleton-resampler field model
  (resample real lineup archetypes onto current players) vs
  duplication-penalty selection vs per-contest line models vs
  something else — rank, with the deciding evidence for your #1.
6. **The meta-question**: three reviews and ~20 arms have produced
  zero adoptions since the ensemble. Is the correct posture for
  September "operate, collect real 2026 standings, stop testing" —
  or do you see a class of experiment we are systematically not
  running?

Answer with numbered findings: claim, mechanism, concrete code-level
test, falsification condition. Constraints: free data only; solo
operator; six-season walk-forward panels with co-run controls are
the only accepted evidence; BigQuery + Cloud Run.
