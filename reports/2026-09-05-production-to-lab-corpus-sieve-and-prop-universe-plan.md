# Production-to-lab plan: conservative corpus sieve and prop-covered lineup admission

**Date:** 2026-09-05  
**Status:** proposed development program for lab review; not a launch contract or live-policy authorization  
**Production owner:** source identity, immutable build/launch, terminal release, independent read  
**Lab owner:** preregistration, implementation, mechanics gate, first read, and interpretation packet

## 1. Decision in one paragraph

Test this idea, but separate its two mechanisms. First perform an
outcome-disabled support census on the already frozen D800 pools. If every
scored slate/bank contains enough candidates, run one simple **prop-covered
lineup-admission** pilot: retain only candidates whose eight offensive players
each had at least one valid point-in-time player-prop quote; DST is exempt
because it has no comparable player-prop market. The treatment must use the
same candidates, matrices, judge, and selector as control--no regeneration or
replenishment. Separately, after SD-C identifies which candidates the current
judge overvalues, run one **conservative lineup-sieve** experiment on an
unchanged D800 pool. Do not combine the treatments initially, do not run a
cutoff grid, and do not make either rule universal. Only DraftKings legality
is universal. Any confirmed-unavailability exclusion remains an explicit,
named strategy input, not a universal corpus law.

The purpose is not to make the corpus smaller. It is to learn whether a
pre-lock negative screen can stop the selector from spending entries on
false-attractive candidates while preserving rare high-ceiling lineups.

## 2. Why this is worth testing, and what is already answered

Several prior results narrow the useful version of the idea:

1. Generic compression is a weak lead. In PREREG-029, MEAN/COV/QUOTA/RANK
   reduced roughly 575 candidates to 250; no rule beat COV and COV retained
   97.7% of the single-candidate corpus oracle. Removing the 575-to-250 stage
   also changed nothing in two reads. Merely deleting the current ranking's
   middle or bottom is therefore expected to be a no-op.
2. Hard participation filtering helped but was not best. PREREG-054's
   `P_ELIG` removed candidates containing a Doubtful or Questionable+DNP
   player and improved the raw historical result, but probabilistic `P_MIX`
   was materially better. This argues for uncertainty-aware treatment rather
   than declaring every questionable player worthless.
3. Blanket player removal destroyed real ceiling in the D6 census. Removing
   every candidate containing a modeled designated player reduced mean corpus
   oracle from about 195.19 to 190.04. Even a lineup-level
   `P(all active) >= 0.85` rule retained only about 192.44. Some uncertain
   players play and carry tournament-winning upside.
4. Participation-aware generation can improve supply. Experiment 093 raised
   one pool's mean oracle from 194.40 to 195.42. In experiment 094,
   redistribution increased 200+ candidates from 251 to 314 and mean corpus
   oracle from 193.95 to 194.51. The formal selection contrasts did not pass
   their family gates, so these are mechanism leads, not adoption results.
5. The conversion problem is real. Exact 094 lineage found 131 added 200+
   candidate instances and 68 displaced, for a net gain of 63; the incumbent
   selector captured only 18 of the 131 additions. Most added extreme-tail
   candidates were beneficiary-only.
6. SD-B reproduced every valid sealed greedy book and bounded the current
   judge-objective search gap at only 3.38%, while realized oracle-to-book
   regret averaged 12.68 points. The selector is solving the wrong belief
   surprisingly well. A sieve using only the same DEMAX signal is unlikely
   to fix that belief error.

The remaining opportunity is thus a screen driven by distinct point-in-time
information, or a conservative dominance rule that targets false attractors
near the top of the incumbent ranking. It is not indiscriminate corpus
shrinkage.

## 3. Questions and estimands

### Experiment P — strict prop-covered lineup admission

> On the identical frozen D800 candidate population and score matrices, does
> retaining only lineups whose eight offensive players all had a valid
> pre-lock prop quote improve the selected book relative to an equally sized,
> deterministically chosen neutral subset?

This is an **admission/retrieval-interface** estimand. It changes only which
already-generated candidates the selector may consider. Its primary contrast
tests whether prop coverage carries information beyond generic pool shrinkage.

### Experiment S — conservative candidate sieve

> On an identical frozen D800 candidate population, does removing candidates
> that are locally dominated across independent pre-lock evidence improve the
> selected book relative to a size-matched neutral removal?

This is an **admission/selection-interface** estimand. It must not regenerate
the candidate pool.

Do not describe either experiment as evidence that small corpora are better.
The comparison is about the information in the exclusion rule.

## 4. Shared scientific and operational boundaries

1. Complete SD-C revision 2, its terminal adjudication, first read, and
   immediate routing before either efficacy experiment claims a score lane.
   Lab may build the score-free support census and fixtures in parallel.
2. Use a new PREREG identifier and unused run prefixes. Experiment P reuses
   one exact sealed donor D800 population; it does not pool generations or
   create fresh generation worlds. The preregistration must bind its source
   commit, run IDs/banks, ordered candidate artifacts, 36-slate key manifest,
   decision/held-out matrices, judge, selector, and utility/veto contract. The
   default donor is the exact 2023-2024 subset of PREREG-065/094 `PG_CTRL`,
   because it is the current-policy D800 control judged by sealed `P_MIX`.
   If those artifacts cannot be reopened without crossing the outcome
   boundary, stop and nominate one other sealed current-policy donor before
   implementation; never union `PG_CTRL`, `PG_AWARE`, and `PG_REDIST`.
3. Historical outcomes are already development-exposed. Fresh world banks do
   not create a new holdout. Any favorable result may nominate a 2026
   prospective shadow, never direct paid adoption.
4. Freeze every player/candidate eligibility decision before settlement is
   opened. Candidate and exclusion artifacts must contain no realized points,
   active-after-lock label, final rank, payout, winner identity, or other
   outcome-derived field.
   Enforce this with an explicit source/table and column allowlist: neither the
   mask builder nor selector runner may open PREREG-064's released Parquet,
   settlement, actuals, or any outcome-bearing feature table. Those sources
   become readable only by the terminally released reader.
5. Use exact canonical player and nine-player roster identities. Preserve the
   complete admitted and excluded partitions; never retain only the survivors.
6. Keep the ordered D800 candidates, every decision and held-out matrix,
   judge banks, selection K, selector, and all unrelated laws identical within
   each comparison. If a later preregistration creates fresh evaluation
   matrices, it must do so for every arm from one frozen bank law and say so
   explicitly; this plan does not authorize that change.
7. No threshold, quote-age, prop-market, prune-fraction, model, weight, or
   sleeve grid. One frozen treatment per question.
8. No silent fallback. A support or feasibility failure is a result. It does
   not authorize widening the player universe or weakening the sieve.
9. Experiment P and Experiment S remain separate. A combined arm is earned
   only if both show useful, stable mechanisms and production later
   preregisters one 2-by-2 crossing.
10. Neither experiment changes Week-1 paid books, production scoring, or the
    standing rule that only DraftKings legality is universally required.

## 5. Work package P0 — outcome-disabled prop-coverage census

Run this first. It is cheap and decides whether strict all-eight prop coverage
can support an exact-K80 comparison on the frozen D800 candidates.

### 5.1 Source boundary

The existing corrected PREREG-064 extract establishes useful coverage facts:

- 36 Sunday-main development slates in 2023-2024;
- DraftKings and FanDuel historical sources only;
- 7,270 player-weeks and 74,291 paired output rows;
- every retained row strictly before common lock; and
- a typical retained horizon of roughly two hours before common lock.

That released Parquet also contains realized labels and is therefore **not**
an allowable pre-lock experiment input. Production or the lab must create a
separate score-free `prop_player_availability_v1` artifact from the frozen
pre-lock source projection in `nfl_raw.prop_lines`. It should contain only:

- season, week, slate, event/game identity, common-lock timestamp, and the raw
  source player string;
- canonical player ID, position, team, and DK salary-slate identity from the
  same frozen pre-lock player snapshot that underlies the donor D800 pool;
- bookmaker, market, outcome side, price, optional market point, source
  timestamp, quote age, and raw ingestion/source-row identity;
- identity-resolution method and source-health fields; and
- source URI/generation/SHA-256/bytes, query identity, code identity, and
  schema identity.

The root must be published last and generation-exactly reopen every child.

### 5.2 Frozen definition of prop covered

For the first pilot, define an offensive player as prop covered when at least
one raw `nfl_raw.prop_lines` row satisfies all of the following:

1. deterministic, unambiguous resolution to the donor pool's canonical
   salary-player identity using the pinned production identity resolver;
2. a source timestamp strictly before the earliest Sunday-main common lock;
3. a finite, valid price from DraftKings or FanDuel, plus a finite point where
   that market has a point (`player_anytime_td` is a one-way market and may
   legitimately omit it); and
4. market in this frozen six-market set:
   `player_pass_yds`, `player_pass_tds`, `player_rush_yds`,
   `player_reception_yds`, `player_receptions`, or `player_anytime_td`.

For line-bearing markets, require a complete quote at one bookmaker: both
normalized `Over` and `Under` sides at the same event, player, market, point,
and snapshot, each with a finite valid price. For `player_anytime_td`, require
the named-player outcome with a finite valid price; no opposite side or point
is expected. Bind the event to a game in that exact Sunday-main slate.

Within each exact `(event_id, bookmaker, raw_player, market, point,
outcome_side)` key, retain the latest row whose source timestamp is strictly
before common lock; use a stable source-row identity to reject unresolved
ties. Do not impose a quote-age cap in this first read. Carry source timestamp
and hours before common lock into the artifact and report their distribution.
A staleness cap or alternate-market expansion would be a separately frozen
future treatment, not a repair made after seeing support or scores.

Quote presence is the treatment. Do not require that the over or under is
favorable, do not use the realized result, and do not infer a missing quote to
mean the player is inactive.

Every QB/RB/WR/TE in a strict treatment lineup must be prop covered. DST is
explicitly exempt. Prop presence is not an active-player guarantee and must
not replace the participation model.

Raw prop rows contain names rather than GSIS IDs. Exact normalized matches and
the existing frozen deterministic alias map are allowed only when they resolve
to one salary player on one slate; ambiguous or unmatched names are excluded
and counted. No fuzzy or hand-edited match may be introduced after the support
census.

### 5.3 Source-health and support census

First publish the complete expected cell manifest, where a cell is exactly
`(season, week, bank, generation_arm)`, and hash its ordered 36-slate key set.
Left-join prop coverage onto this authority so a missing source week produces
zero support rather than disappearing. Require each donor cell to contain
exactly 800 unique canonical roster hashes, each with nine unique players and
exactly eight offensive players plus DST; otherwise stop before the prop
join.

The corrected 2023-2024 common-lock join suggests that raw player coverage is
approximately 21.7% at QB, 41.5-45.4% at RB, 39.7-40.7% at WR, and 41.1-42.1%
at TE; DST coverage is zero by design. Those rates show that at least one
legal roster may be possible, but they do **not** establish 80 eligible D800
candidates in every cell. Before outcomes or candidate scores, report by
slate and position:

- DK-salary player count and prop-covered count/rate;
- coverage by bookmaker and market;
- quote-age distribution and unmapped-player count;
- salary, incumbent-projection, and role deciles from the frozen donor player
  snapshot for covered versus uncovered players, without realized outcomes;
- for every existing D800 candidate, the count from 0 through 8 of offensive
  players who are prop covered;
- exact counts of unique all-eight and at-least-seven roster hashes by cell;
- retained share by source/family and the deterministic roster hashes of the
  admitted and excluded partitions; and
- whether every proposed scored slate/bank has at least 80 all-eight
  candidates.

Freeze the score cohort from this outcome-disabled census. A source-wide
outage or fewer than 80 unique all-eight roster hashes in **any** proposed
scored cell makes the strict exact-K80 experiment infeasible as specified.
Stop and return the census; do not drop the cell, pad with uncovered players,
regenerate the pool, or dynamically relax to seven of eight. The census may
nominate a
separate, prospectively frozen at-least-seven experiment, but that is not an
automatic arm in this plan.

## 6. Experiment P — strict prop-covered lineup admission

### 6.1 Arms

Use one fixed-pool, three-arm family:

- **`P_FULL`** — the full frozen D800 pool and current selector, unchanged.
- **`P_RANDOM_MATCHED`** — within each slate/bank, retain a deterministic
  outcome-free random subset with exactly the same candidate count as
  `P_ALL8`; then run the unchanged selector.
- **`P_ALL8`** — from the same D800 pool, retain only candidates whose eight
  offensive players satisfy the frozen `prop_covered` definition; then run
  the unchanged selector. DST is exempt.

Candidate identities and score matrices are identical before admission. No
arm may generate, replenish, pad, rescore, or alter a candidate. All arms use
the same judge banks and final selector and must produce exact K80 in every
scored cell. `P_ALL8 - P_RANDOM_MATCHED` is the primary information-bearing
contrast; `P_ALL8 - P_FULL` is secondary context. The matched arm is required
because merely reducing a selector's feasible set can change greedy order.

Filtering is mask-only and order-preserving across every decision and
held-out matrix. Choose neutral membership before settlement by frozen
SHA-256 rank, then restore the donor D800 row order before selection.
`P_RANDOM_MATCHED` is count-matched within `(season, week, bank,
generation_arm)`, not claimed to match phenotype or family composition. Its
seed, hash-ranking algorithm, and membership artifact are frozen before the
reader can open outcomes. Before efficacy, `P_FULL` must reproduce the donor
K80 book byte-for-byte.

Do not add `PROP_7_OF_8`, `PROP_CORE_ONLY`, quote-count, bookmaker-count, or
favorable-line arms. Those are possible successors only after a clear first
read. If the P0 census cannot support all-eight at exact K80 everywhere, stop
without an efficacy score. An at-least-seven rule may run later only as a
separately frozen family with its own neutral match; it may never appear as a
slate-specific fallback.

### 6.2 Primary and required co-reports

Reuse the exact PREREG-065 registered K80 winner-CDF utility and bank-veto
implementation, pinned by source SHA, as the single primary outcome; do not
silently substitute a later score or objective. Average paired bank effects
within historical slate, then perform the preregistered season-clustered
inference. Banks are repeated simulations, not independent observations.
Headline only the 36 covered 2023-2024 slates; do not pad 2021-2022 with
no-op cells. The reader must also report:

- raw weekly maximum and K3/K10/K20/K57/K80 nested views;
- weeks and candidate instances at 187/194/200/210/220/230/240;
- full-pool, all-eight eligible-pool, and neutral eligible-pool oracles;
  selected-book maximum; and each eligible-oracle-to-book plus
  full-oracle-to-book regret;
- candidate retention, selected-book turnover, and deterministic matched-arm
  membership;
- realized inactive-player contamination as a reader-only safety outcome;
- covered/uncovered player counts by position, salary, role, and family;
- retained and removed candidate accounting by canonical roster hash,
  including removed candidates at 200/210/220/230+;
- W/L/T by week, bank and season, plus A5 nested K3/K10/K20/K57 views;
- ownership, salary, source/family, and phenotype shifts; and
- all source-health and delivery shortfalls.

Filtering cannot raise the oracle of the original D800 pool. Its possible
value is improving the quality of the feasible subset and helping the current
selector convert more of the already-present ceiling.

Because the covered cohort has only two seasons, this is a development-only
nomination screen and cannot satisfy the ordinary multi-season adoption law.
Freeze this exact nomination criterion before settlement: the primary
`P_ALL8 - P_RANDOM_MATCHED` 95% interval lower bound is above zero; the
existing bank veto does not fire; both season means are nonnegative; the raw
K80 mean versus `P_FULL` is positive; selected-book week counts at 220 and 230
do not decline versus `P_FULL`; and realized inactive contamination does not
rise versus `P_FULL`. Passing can nominate only a 2026 prospective shadow.

### 6.3 Frozen interpretation

- **The frozen nomination criterion passes:** prop availability is a promising
  false-attractor screen. Nominate one 2026 strict prop-covered shadow; do not
  adopt it for paid entries.
- **The raw book beats full but the primary does not beat matched under the
  frozen criterion:** the change is consistent with generic
  pruning, not information in prop availability. Close the hard rule.
- **Eligible-pool oracle remains useful but the selected book does not:** the
  prop-covered subset still contains ceiling that the current belief cannot
  convert. Send its exact first-loss lineage to routed selector work; do not
  tune the availability rule on these outcomes.
- **Either selected 220/230 count declines, contamination rises, or raw K80
  mean is nonpositive versus full:** reject the hard rule even if a
  lower-threshold mean improves. A soft prop-presence feature requires a
  separately frozen mechanism.
- **Support is thin:** no efficacy inference. Return the score-free census.
- **Benefit exists only on the 36 covered slates:** report it only for that
  cohort. Never call it a full-history or global result.

### 6.4 Earned successor: prop-covered player-universe generation

The operator's proposed “generate only from players with props” variation is
the logical successor, not part of the first read. It is earned if the
fixed-pool screen passes, or if P0 proves the D800 pool has too few all-eight
candidates but a separate outcome-disabled optimizer census proves that the
strict player universe can reliably deliver 800 unique legal candidates per
cell. Freeze it as a distinct generation estimand: current D800 generation
versus identical 800-solve generation restricted to prop-covered offensive
players, followed by the identical judge and selector. Report both pool
ceiling and book conversion. Do not reuse the fixed-pool admission result as
evidence that generation will help, and do not combine generation restriction
with the later targeted sieve in its first read.

## 7. Work package S0 — freeze a conservative lineup-sieve rule

Begin implementation only after the SD-C first read identifies whether the
relevant error is global calibration, participation-specific calibration, or
top-rank phenotype recall. The rule must use that routed information without
refitting on the evaluation outcomes.

Because SD-C's outcome-open read chooses this rule family, any S result on the
same historical cohort is **exploratory**, even if its scalar inputs are fitted
walk-forward. It may refine a 2026 prospective shadow but cannot confirm the
outcome-adaptively chosen sieve. A confirmatory historical claim would require
a genuinely outer walk-forward design in which every target season's entire
rule-family choice uses earlier seasons only.

The recommended first rule is **local Pareto dominance**, not bottom-percent
deletion:

1. Candidate A is considered only against near-substitutes sharing at least
   eight of nine rostered players. This prevents a generic score from deleting
   an otherwise unique game story.
2. Candidate B can dominate A only when B is no worse on every available
   frozen pre-lock dimension and strictly better on at least one:
   - disjoint held-out-bank tail utility under the SD-C-routed corrected
     belief;
   - lineup `P(all active)` from the frozen participation input;
   - coverage-adjusted market/prop contribution; and
   - redundancy or unique-scenario contribution under the existing lineage
     trace.
3. Missing information protects A from pruning on that dimension. Missing
   props are not automatically bad.
4. A cannot be pruned when it is the sole representative of a protected
   beneficiary, source/family, game-state, or held-out tail signature.
5. Dominance is computed simultaneously from the full pre-prune comparison
   graph. No sequential deletion may change whether a later candidate is
   dominated. Canonical roster SHA-256 orders output only; it does not turn
   equality into strict dominance.

Any correction estimated from realized calibration data must be fitted
walk-forward: target season S may use seasons strictly before S only. The
SD-C read may choose the broad mechanism family, but it may not supply a
target-season fitted value or target-season outcome feature.

The lab may propose a simpler mathematically equivalent rule before freeze.
It may not substitute a fitted black-box classifier or a percentile sweep.
Before implementation, S0 must bind the exact scalar value and direction for
each dimension, missingness behavior, comparison graph, protected phenotype
vocabulary, and simultaneous-pruning algorithm.

## 8. Experiment S — candidate sieve on the identical D800 pool

### 8.1 Arms

- **`S_FULL`** — unchanged D800 pool and current selector.
- **`S_NEUTRAL`** — remove exactly the same count as the targeted sieve within
  each slate/bank/family using a frozen outcome-free seed, from the same
  prune-eligible universe and under the same representation protections.
- **`S_TARGETED`** — remove only candidates meeting the frozen local-dominance
  rule.

`S_TARGETED - S_NEUTRAL` is the information-bearing comparison. `S_FULL` is a
context arm showing the cost or benefit of shrinking the feasible set. The
neutral arm is necessary because a smaller pool can alter greedy order even
when the removals contain no useful information.

Generation, candidate identities, score matrices, judge banks, and K80 are
identical across arms. The sieve may not create a candidate and cannot claim
to increase corpus ceiling.

Run an outcome-disabled S support census before efficacy. Every frozen cell
must retain at least 80 unique roster hashes under both targeted and neutral
rules. If any cell fails, stop the whole S experiment; do not truncate
pruning, alter the rule, or drop the cell. Freeze exact per-stratum neutral
removal counts and membership before settlement.

### 8.2 Required read

Report the same K and tail grid as Experiment P, plus:

- number and percentage pruned per slate;
- selected-before-prune, selected-after-prune, and first-loss stage;
- realized 200+/210+/220+/230+ candidates retained and falsely removed;
- retained pool oracle and threshold recall;
- count of removed candidates that beat the original book maximum;
- which dominance dimensions fired and their overlap;
- beneficiary/source/family/game-state representation before and after; and
- targeted-versus-neutral paired uncertainty.

### 8.3 Frozen interpretation

- S0 must replace this template with exact interval, sign, threshold, and
  contamination criteria before launch. If those frozen criteria pass against
  both neutral and full, the exploratory read may nominate one prospective
  sieve shadow; this document does not itself define a pass.
- Equality with full means the removed rows were already irrelevant; close
  this sieve rather than pruning more aggressively.
- Equality with neutral means any change came from pool size, not the signal;
  close this rule.
- Any tail-safety or contamination veto frozen by S0 blocks nomination even
  alongside a mean gain.

## 9. Mechanics and evidence contract

Before either efficacy launch, the lab should return:

1. a frozen design mapping every possible result to a disposition;
2. the score-free prop-availability or sieve artifact schema;
3. exact admitted/excluded lineage keyed by roster SHA-256;
4. a real-artifact outcome-disabled support census and mechanics smoke;
5. runner, reader, mechanics gate, and focused behavioral tests;
6. fail-closed checks for PIT cutoff, source health, player mapping, exact
   candidate counts, exact K, and treatment engagement;
7. one immutable-source launch contract with unused banks/prefixes and the
   unchanged compute envelope;
8. a reader that cannot open settlement until production publishes a clean
   terminal cohort release; and
9. a first-read transcript plus machine-readable result and explicit statement
   that no live policy changed.

Tests must demonstrate rejection of post-lock quotes, a forged player or
roster identity, an unmapped prop row, DST being accidentally excluded,
hidden treatment fallback, duplicate candidates, count mismatch, missing
neutral match, missing expected cells, silently dropped source weeks, changed
matrix row order, non-reproduction of the full-control book, and any
unauthorized source or outcome field in a pre-lock artifact.

## 10. Minimal execution order

1. **Now, score-free:** build `prop_player_availability_v1`, apply it to every
   frozen D800 candidate, and run P0's 0-through-8 coverage census.
2. If and only if every scored cell contains at least 80 all-eight candidates,
   lab returns one frozen fixed-pool Experiment-P package for production
   review. Otherwise it returns the census and stops this arm. Do not launch
   while SD-C owns the active path.
3. Complete SD-C revision 2, first read, and routing.
4. Run Experiment P at the next production-authorized slot if its support
   gate passed.
5. Use SD-C's routed calibration/phenotype conclusion to freeze S0; run one
   Experiment-S package, not a sieve grid.
6. Stop after the two first reads. A passing P may earn the separate strict
   player-universe generation test in Section 6.4. Only after independently
   useful generation and sieve mechanisms exist should production nominate a
   fresh-bank generation-by-sieve crossing.

## 11. Expected value and principal risk

The prop-covered arm is attractive because market makers choose which players
receive markets, so quote presence may encode expected participation and role
confidence even when the quote level adds little beyond the incumbent model.
Prior evidence makes this test plausible but does not settle it: PREREG-007's
45/55 market blend improved K80 by about 1.09 across 89 slates and about 2.71
on its covered cohort, while the later market-tail disagreement treatment
failed and experiment 092's M2 judge was essentially null. None of those
tests isolated binary quote availability.

The hard screen is dangerous because quote presence is missing-not-at-random:
it reflects role, popularity, bookmaker coverage, position, collection
timing, injury news, source outages, and commercial priorities. It may remove
the cheap, low-owned breakout players a large-field tournament strategy
needs. Nor is it a participation substitute: an outcome-open audit found
roughly 9-10% inactive contamination even among covered RB/WR/TE player-weeks.
Quote horizons also include a long tail (roughly two hours at the median but
up to about five days), which is why the first arm records staleness rather
than inventing a post-hoc age cutoff.

The experiment is therefore worthwhile precisely as a strict, easily
interpreted pilot. A positive result earns a shadow. A negative result closes
the hard rule without implying that prop levels, ladders, dispersion, or
movement are useless as softer features.

## 12. Evidence locations

The implementation and review should reopen these sources rather than rely on
the prose summary above:

- production raw-prop ingestion and PIT fields:
  `src/nfl_dfs/ingest/oddsapi_import.py`;
- current market feature construction:
  `src/nfl_dfs/models/prop_market.py`;
- corrected common-lock extract and role-field audit:
  `/home/erich/projects/nfl-predictions-prereg064-extract/reports/2026-09-03-prereg064-market-extract-and-role-field-audit.md`;
- frozen market experiment contract:
  `/home/erich/projects/nfl2-sdc-launch-binding/PREREG-064.md`;
- participation-generation and redistribution evidence:
  `/home/erich/projects/nfl2-sdc-launch-binding/PREREG-063.md` and
  `/home/erich/projects/nfl2-sdc-launch-binding/PREREG-065.md`;
- prior market-blend result:
  `/home/erich/projects/nfl2-sdc-launch-binding/results/032-PREREG-007-report.json`;
- SD-B search-versus-belief diagnosis:
  `/home/erich/projects/nfl2-sdc-launch-binding/reports/2026-09-05-sd-b-greedy-certificate-read.md`; and
- current generation/selection follow-up boundary:
  `/home/erich/projects/nfl-predictions-week1-pmix-live-certification/reports/2026-09-04-production-to-lab-generation-selection-followup-plan.md`.

## 13. Lab response requested

Please respond with only:

1. whether the exact score-free prop mask can be reconstructed from
   `nfl_raw.prop_lines` without using an outcome-bearing released Parquet;
2. the exact all-eight and at-least-seven candidate counts in every frozen
   D800 slate/bank cell, and whether all-eight supports exact K80 everywhere;
3. any conflict between the proposed local-dominance fields and the SD-C
   artifact schema;
4. a simpler equivalent neutral-control design, if available; and
5. the earliest unused PREREG/experiment identity and cloud slot after SD-C.

No experiment needs to stop for this planning work, and this document itself
authorizes no build or launch.
