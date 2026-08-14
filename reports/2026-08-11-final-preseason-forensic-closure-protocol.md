# Final preseason forensic closure protocol

Date: 2026-08-11. This tracked protocol strengthens the operator-supplied
`reports/2026-08-11-end-of-program-forensic-analysis-plan.md` without changing
that outside-review document. It is mandatory once the historical research
queue is exhausted; it does not stop, replace or reorder the active queue.

The retrospective may use all realized historical outcomes, so its outputs are
hypothesis-generating and operational only. It may choose the 2026 prospective
research charter, data-collection priorities, contest/entry allocation rules
that depend only on pre-lock information, and the kill list. It may not promote
or retune a historical arm.

## 1. Start condition and outcome freeze

Do not run an outcome query for this analysis until one tracked freeze commit
proves all of the following:

1. Every preregistered historical arm in `HANDOFF.md`, the scoring roadmap and
   the graph/dependence queue has a terminal pass/reject/neutral/invalid status.
   A merely expensive or inconvenient arm is not exhausted. Invalid arms must
   either receive their licensed mechanism-preserving repair or be closed with
   the reason.
2. No historical scoring Cloud Run execution is active, and every durable run
   id, image digest, panel id, protocol hash and terminal artifact is in the
   repository. Prospective 2026 shadows may remain scheduled.
3. The final adopted production policy, fallback policy, exact-80 source panel
   and feature/cache versions are named and deployment-verified.
4. All known point-in-time, universe, salary, identity and live-join repairs
   that affect the final production path have completed their coordinated
   feature rebuild, retraining and validation. The analysis must not compare a
   repaired live path with stale historical snapshots without labeling that
   difference.
5. A complete arm ledger is frozen before results: launched, never launched,
   duplicate mechanism, invalid execution, licensed repair, gate, result,
   operator override, cloud cost and current production relevance.

The freeze commit must pin one immutable analysis image, all consumed table and
panel ids, source row/key counts and hashes, contest files, scoring rules,
metric definitions, analysis list and output schemas. Anything added after the
first outcome query is marked `post-hoc` and cannot enter the prospective
charter without new-season confirmation.

## 2. Corrected additive opportunity decomposition

The original plan's proposed “best 80-subset achievable from the candidate
pool” always contains the pool-oracle lineup, so that layer is mathematically
zero for a weekly-maximum objective. Replace it with this exact decomposition
on each of the 107 canonical slates:

| quantity | exact definition |
|---|---|
| `H` full-universe hindsight oracle | Best legal nine-player lineup from the exact salary-listed Sunday-main contest universe, scored by authoritative actuals |
| `P` player-support oracle | Best legal lineup using only players who appear in at least one generated candidate in the final pool |
| `C` candidate oracle | Highest actual score among generated legal candidates |
| `S` selected result | Highest actual score among the submitted/final selected entries |

The additive gaps are:

- **player-support gap:** `H - P` — high-value players never reached any
  generated roster;
- **construction gap:** `P - C` — the right players existed in support but
  were not assembled together;
- **selection gap:** `C - S` — the candidate existed but the final book omitted
  it; and
- **realized selected score:** `S`.

All four quantities require exact historical DK positions, salaries, Sunday
main membership, stack and salary legality. Record solver status, roster and a
second independent legality/score reconstruction. Report points and threshold
crossing attribution at 187/194/200/210/220/230/240. Also compare `S` with the
known winner, fifth-place, cash and payout thresholds only where those contest
facts are actually available; do not force a contest benchmark into the
additive `H-S` identity.

## 3. Portfolio outcomes, entry count and money

Weekly maximum remains the operator's primary historical utility, but the
analysis must not silently equate it with ROI. For every final book report:

- weekly maximum plus top-3/top-5/top-10 entry scores and the distribution of
  all submitted entries;
- threshold counts and margins at 187 through 240;
- duplicate roster count, player and stack exposures, and marginal gain from
  each additional entry block;
- nested, outcome-blind selector books at 20, 40 and 80 entries. Test higher
  counts only when the historical contest rules and available candidate pool
  make them legal; do not extrapolate an interpolated 120/150/200 curve; and
- cost per slate, total entry fees and the operator's declared tail-first
  utility alongside any dollar estimate.

First inventory contest data by slate. Where full standings, score-to-rank
cutoffs, entry fee and prize ladder exist, score every submitted entry and
compute exact gross payout, net profit, ROI, cash rate, top-1% rate and maximum
drawdown. Where only winner lines, top finishers or marginal ownership exist,
report only the identifiable rank/payout interval or threshold utility.
Independent-player simulations from marginal ownership are not a field-score
“bound”; player outcomes and roster construction are correlated. They may be
shown only as a labeled sensitivity model.

Use sum of log ownership/product ownership only as a duplication proxy. Where
2025 or prospective standings include actual rosters, measure empirical
duplicates and calibrate the proxy before applying it elsewhere. Compare our
book with places 1--5 and broader top finishes whenever those rows exist, not
only the winner.

## 4. Player, marginal and dependence diagnostics

Run a single player-to-portfolio capture funnel for every slate:

1. salary-listed players and realized 20/25/30/35-point scorers;
2. players present in the final snapshot with a usable served distribution;
3. players appearing in any candidate;
4. players appearing in selected entries and their exposure; and
5. players in the best selected, candidate-oracle, support-oracle and
   full-universe-oracle lineups.

Attribute every consequential miss to the first failed stage and summarize by
position, salary, realized ownership, role-change/vacancy state, data support,
generator tag and season. Separately analyze high-scoring candidates that were
not selected, including roster distance and which selection worlds/objectives
preferred their replacements.

For the final served player distributions report MAE/rank correlation for
means, CRPS where draws exist, interval coverage, and Brier/reliability at
20/25/30 points. Stratify by position, salary, active status, ownership band,
week, role-change state and presence of sparse/vendor inputs. Always show
support counts and season splits. Compare component, cache and final-served
predictions only through already-frozen outputs; the retrospective cannot fit
a new blend.

Because a DFS lineup is a joint-tail object, add dependence calibration:
same-team and opposing-player score covariance; QB-single/double-stack and
bring-back co-exceedance; game-level shootout tails; and simulated-versus-
realized joint 20/30-point event rates. This distinguishes marginal error from
copula/rank-coupling error and feeds the already-preregistered graph/dependence
research only prospectively.

## 5. Candidate generation and selection forensics

Retain the original plan's rank-skill census, tag yield, salary/position spend,
shape inventory and near-miss frontier with these additions:

- Use slate-clustered intervals and per-season estimates for all candidate
  correlations. Include calibration of `p_line`/support probability, not only
  Spearman rank.
- Report candidates generated, unique legal rosters, selected rosters and
  threshold clears per unit of generation time and per thousand candidates.
- Map generator overlap with an arm/tag Jaccard graph so nominally distinct
  mechanisms that produce the same rosters are counted once.
- Decompose exposure constraints, coverage saturation and tie-breaking. For
  each selection miss, state whether the oracle added a new covered world or
  was dominated under the frozen selector's actual information.
- Reconstruct the exact selection at every tested entry count from pre-lock
  fields. Actual scores may evaluate it but never choose its order.

A signal or tag can be closed only with its eligible support, uncertainty,
season behavior and mechanism overlap recorded. A poor average alone does not
close a rare-tail mechanism; conversely, one outcome-viewed extreme does not
license a new historical arm.

## 6. Regimes, drift and actionability

Regime analysis is useful only if its state is observable before lineup lock.
Freeze bin boundaries and minimum support before results. For game count,
market totals/spreads, weather forecasts, week/season phase, salary dispersion
and ownership concentration, report the opportunity decomposition, complete
portfolio grid and leave-one-season-out direction stability.

Realized “chalk busted” versus “chalk won” is an outcome label and cannot
directly determine how many entries to buy before lock. It is descriptive
unless a separately specified pre-lock predictor of that state is available.
Every proposed contest/entry-allocation rule must therefore include:

- the exact pre-lock inputs and availability timestamp;
- a frozen mapping from those inputs to allocation;
- support and sensitivity to bin definitions;
- leave-one-season-out behavior; and
- a prospective 2026 falsification/grade rule.

Analyze failure autocorrelation within seasons, separating season boundaries
and accounting for shared teams/players. Report recency/era sensitivity, but do
not pick a historical cutoff after viewing which one looks best.

## 7. Data, point-in-time and operational forensics

Expand the original data census into a live-readiness audit:

- raw and modeled source coverage, null rates, key duplication and unresolved
  identities by season/week/position;
- feature error conditional on missingness, plus whether missingness was itself
  exposed to each learner;
- exact source timestamp/window available at the common slate lock for every
  active and candidate field, including Fantasy Points and ownership inputs;
- historical-training versus live-inference join parity, upcoming-row presence
  and source-family recomputation of strictly-prior rolling fields;
- salary/DST/full-contest universe reconciliation and authoritative-score
  parity; and
- complete reconciliation of every README deficiency-log row, backup table and
  weekly licensed-data acquisition requirement.

Run a Week-1 dress rehearsal from acquisition through DraftKings-ready CSV:
scheduled ingestion, vendor download/validation, feature build, registry/cache
load, projection, 20/40/80 lineup generation, UI/API policy identity, slate-
specific draftable IDs, export validation, artifact backup, alerts, failure
recovery and fallback labeling. Verify Cloud Run job/service digests, IAM/auth,
quotas, scheduler times/time zone and rollback. Do not spend contest entries or
publish external data during this rehearsal.

## 8. Experiment-program meta-analysis

The final report must reconcile every experiment, not just panels still easy to
query. Produce:

- a preregistration/gate compliance table, including invalid runs and licensed
  repairs;
- effect sizes on the common corrected universe, while preserving each arm's
  original immutable verdict and operator override;
- arm-to-arm mechanism and candidate-overlap maps to expose repeated tests of
  the same idea;
- season and slate paired deltas, bootstrap/sign intervals and sensitivity to
  influential weeks;
- cloud/runtime/data cost and score opportunity per mechanism family; and
- a multiple-analysis disclosure. Exploratory intervals rank prospective work;
  they are not retroactive significance tests or adoption gates.

Cross-panel shrinkage/meta-analysis may estimate how large an effect future
gates should demand, but launched arms are a selected sample. Report that
selection and never use the analysis to revive a rejected historical arm.

Before any cross-panel main-effect or interaction model is fit, construct the
complete panel-by-mechanism design matrix. Report its rank, aliased columns,
cell support and every estimable contrast. A common-slate fixed effect removes
slate level but does not manufacture a crossed factor cell that was never
launched. Report interaction coefficients only for factor pairs with identified
contrasts; otherwise record them as unidentifiable. Every panel row must also
name its experimental stage/channel, exact incumbent context and downstream
transfer boundary. These retrospective estimates remain charter inputs only.

## 9. Required outputs

The immutable run produces machine-readable tables plus concise tracked
reports:

1. provenance manifest and complete arm ledger;
2. 107-slate corrected opportunity decomposition with oracle rosters;
3. portfolio/entry-count/contest-money report with identifiability flags;
4. player capture, calibration and dependence report;
5. construction, selection, regime and data-quality report;
6. experiment meta-analysis and kill list;
7. Week-1 operational readiness checklist with pass/fail owners; and
8. ranked 2026 prospective charter and opportunity register.

Add a ninth output: an **exhaustion certificate**. It must inventory every
mechanism family—player marginals/calibration, availability/role change,
market/vendor data, game/player dependence, candidate generation, roster
construction, portfolio selection, ownership/field modeling, contest choice,
entry count/bankroll, data/PIT integrity and operations—and map every known
idea to one of: terminal historical result, duplicate mechanism, prospective-
only test, data-blocked, disproven prerequisite or explicitly deferred with a
falsifiable trigger. An empty research queue without this taxonomy is not proof
that the preseason program was exhausted.

The kill list and exhaustion certificate are grain-bound. Every coverage entry
must name its source construct, player/defender/team grain, lookback, matchup
crossing, model location and gate. Seed them from
`reports/2026-08-13-coverage-grain-bind-and-kill-list.md`: historical team-shell
proxies may be closed while PFR secondary quality, `top_cb_out`, prospective
vendor matchup grades and named WR/CB assignment retain separate dispositions.
The final closure cannot silently call an active production feature validated
because an adjacent construct failed. The frozen PFR `DROP_FEATURES` obligation
must be terminal or explicitly deferred with a prospective falsifier.

Each opportunity-register row must include layer, mechanism, evidence class,
support, effect and interval, expected tail-threshold value, identifiable dollar
value/range, required data, point-in-time availability, implementation/cloud
cost, earliest decision time, prospective test, falsifier, power/sample target,
dependencies, duplication with prior arms and disposition. “Interesting” is
not a disposition.

## 10. Execution order and completion gate

1. Freeze provenance, closure checklist, analyses, schemas and arm ledger.
2. Validate all inputs without querying outcomes; abort on key/panel drift.
3. Run the corrected `H/P/C/S` decomposition and capture funnel first.
4. Run portfolio/entry-count and identifiable contest-money analyses.
5. Run marginal/dependence, generation/selection and data/PIT diagnostics.
6. Run frozen pre-lock regime and experiment meta-analyses.
7. Synthesize the register, kill list, 2026 charter and Week-1 checklist.
8. Run an adversarial completeness pass against repository reports, README
   deficiencies, commit history, cloud executions and the mechanism taxonomy;
   reconcile every orphaned suggestion/run and publish the exhaustion
   certificate.
9. Have an independent deterministic verifier reproduce every score, legality
   check, aggregate and report hash from the manifest. The verifier must also
   rerun score-source parity, salary/position legality, duplicate detection and
   selected-book reconstruction from raw immutable inputs rather than trusting
   analysis intermediates.

The preseason program is complete only when all nine outputs are committed and
pushed, the opportunity register has no unresolved unlabeled item, the
exhaustion certificate accounts for every mechanism family and repository
suggestion, the Week-1 dress rehearsal passes or has an explicit operator-owned
blocker, and no historical result has been converted into an unregistered
production change.

## 11. Alternative analytical frames addendum

The later operator-supplied
`reports/2026-08-12-alternative-analytical-frames.md` is incorporated through
`reports/2026-08-12-alternative-analytical-frames-reconciliation.md`. Freeze
the following additions with the main analysis manifest before the first
forensic outcome query:

1. A paired, nonstationarity-aware GEV/EVT diagnostic of exact-80 weekly
   maxima, with empirical threshold estimates, paired slate bootstrap,
   leave-one-season-out and influential-week sensitivity. It is a diagnostic,
   never a retroactive or extrapolation-only adoption gate.
2. Per-slate covariance- and correlation-participation ratios, eigenvalue
   concentration, first-PC-deflated spectra, tail-event counts/overlap and
   nested 20/40/80 marginal diversity from the checksummed
   candidate-by-world score artifacts. Include same-world top-mean and twenty
   deterministic random-book controls. Label the results model-implied and
   likely optimistic rather than a formal bound, and repeat them for any
   selected dependence law.
3. Slate-relative rank diagnostics by position and salary-relevant strata:
   Spearman, top-tail average precision, preregistered NDCG and whether each
   treatment changed the actual ordering used by construction.
4. Historical ownership as a player-slate crowd-consensus diagnostic after
   field-size-weighted aggregation of repeated contests. Live use requires a
   timestamped pre-lock projection; realized ownership may not enter a lineup
   decision.
5. Position-stratified player/team-game/game/opponent/residual variance
   components and separately reported upper-tail dependence.
6. Winner inverse-belief distance only after `H/P/C/S` assigns the first failed
   layer, with fixed L1/L2 norms and both candidate-set and legal-universe
   feasibility where tractable.
7. A small, fixed, leave-one-season-out pre-lock slate-opportunity diagnostic.
   No realized chalk state or post-lock input may drive entry allocation.

These additions remain subject to the protocol's no-historical-promotion rule.
They may size and rank the prospective 2026 charter, not revive an arm.
For a future G2 book, freeze independent selection and measurement world halves
or independent seeded world books before generation; same-world controls alone
do not remove selector in-sample bias. In a future not-yet-frozen exact-80
protocol, a stable valid EVT result that materially contradicts an empirical
grid pass triggers mandatory disclosure and an explicit operator production
decision, not an automatic veto or a new promotion path.

## 12. Final-evidence amendments (2026-08-14, outcome-free)

These requirements incorporate the terminal pass-tail, selector-resampling and
multi-seed reports. They use only already-recorded results and do not query a
new outcome.

1. **Keep production evidence scopes exact.** The v4 live policy is
   `classic-k1-role12-boom40-poscal-cbwu-v4`: K=1 marginals, role12 + boom40,
   position calibration and the fixed-budget five-search/five-world `CBWU`
   mechanism. Its component/position evidence spans the corrected 107-slate
   panel, while the CBWU mechanism was decided on the separately frozen
   54-slate 2023--2025 factorial. Do not manufacture a nonexistent 107-slate
   historical v4 book or attribute the 54-slate CBWU scores to all 107 slates.
   Report each estimand on its actual eligible slate set, then use the first
   2026 pre-lock v4 artifacts for prospective verification.
2. **Reconstruct CBWU mechanically before analyzing it.** Require all five
   registered projection/role seed pairs, identical player universes, native
   candidate-total reconstruction, first-source roster deduplication, the
   score-blind fixed quota/fill allocation, exact R0 candidate budget, five
   equal 10,000-world blocks, unchanged line-194 greedy selection and exactly
   80 selected rosters. Reproduce the report hash
   `a41d3427aa267ed9ab52753a898f14135caa9bd42c11c645d92eccffbb170239`.
   Contrast `C0W0`, `C0WU`, `CUW0`, `CUWU`, `CBW0` and `CBWU` without treating
   the larger `CU` pool as an unconfounded mechanism effect.
3. **Separate algorithmic variability from entry value.** Give the five native
   seed-book envelope and pairwise overlaps equal billing with across-slate
   uncertainty. The selector diagnostic's disjoint-half overlap of 54.28/80 is
   roster reproducibility, not “54 effective entries.” Economic marginal value
   of entries 41--80 requires nested pre-lock 20/40/80 books plus identifiable
   payouts/duplicates. Bootstrap-mean bagging is algebraically closed and must
   not re-enter the opportunity register under another name.
4. **Report breadth, not only nested threshold totals.** Every arm contrast and
   opportunity-register row must include gross improving/worsening crossings,
   net crossings, unique seed/slate events, distinct improved/worsened/changed
   calendar slates and the actual slate identifiers at each threshold. Nested
   deltas at 240/230/220/210/200/194/187 are not additive evidence. Influential
   slate and leave-one-season-out diagnostics accompany, but cannot rewrite,
   each frozen verdict.
5. **Preserve the pass-tail transfer boundary.** The selected SIS pass-tail
   cache/schedules belong to the finite-K research path and are not part of the
   K=1 v4 money policy. Its deciding >=220 improvement spans only two calendar
   slates, and 2025 is negative below 220. Carry those facts into the kill list
   and into the preregistered 2026 finite-K shadow checks at Weeks 4, 8, 13 and
   18; do not use the retrospective to silently add the cache to v4.
6. **Audit the candidate/world interaction explicitly.** The complete design
   matrix must distinguish candidate search seed, world seed, candidate budget,
   marginal law, dependence law and selector. Report only estimable contrasts.
   `CBWU` licenses new independent search/world evidence at fixed candidate
   budget; it does not validate sample splitting, a new selector line, unequal
   seed weighting, seed selection, or another candidate multiple.
7. **Add production transport and latency to the operational audit.** Week-1
   rehearsal must prove five complete native searches, one ownership-shadow
   snapshot, no auxiliary native candidate persistence, one final 50,000-world
   candidate artifact, source-seed provenance, exact policy headers and CSV,
   fail-closed behavior for a missing block, and acceptable user-facing build
   latency. Measure peak memory/runtime and set service timeout/CPU/concurrency
   from evidence before real entries; do not respond to latency by dropping a
   seed or world block.
