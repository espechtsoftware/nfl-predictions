# Neo4j, Fantasy Points, and SIS influence review

**Date:** 2026-09-10  
**Audience:** production and lab owners  
**Scope:** read-only review of `nfl-predictions`, `nfl2`, durable experiment
artifacts, and relevant primary research. No model, graph, cloud job, live policy,
or contest entry was changed.

## Executive verdict

The short answer is **partly, but not yet end to end**.

1. **Neo4j has been used productively**, but chiefly as a lineage and diagnostic
   index. The first graph exposed a real structural selection failure: strong
   historical lineups with fewer conventional stack relationships and broader
   game coverage were disproportionately absent from final books. The newer
   PREREG-083 graph cleanly separates candidate supply from finite-book
   selection and shows that the treatment supplied two 220-point lineups but
   selected neither. Those are useful, actionable findings.

2. **The Neo4j analyses do not establish the value of Fantasy Points (FP) or
   Sports Info Solutions (SIS).** The first graph did not attach point-in-time
   paid traits. The PREREG-083 graph records that paid-source-named columns
   exist, but the experiment did not vary either source or its consumers.
   Neo4j can retrieve the affected cohort; the graph itself does not turn an
   observational association into an incremental or causal estimate.[6]

3. **Outside Neo4j, both vendors have been evaluated in narrower experiments.**
   FP route share slightly improved a player-level tail score at fit time but
   was erased by the final served marginal transformation. FP coverage changed
   hundreds of candidates and 33 selected slots in each direction, yet every
   weekly maximum and threshold count tied. SIS pass-tail and adjusted-sack-
   over-expected (ASOE) treatments changed selected books and produced small,
   mixed historical tail gains. This proves that some paid inputs can affect
   player distributions and lineup selection. It does **not** prove stable
   tournament value, live 2026 value, or the value of individual SIS/FP data
   points.

4. **The repository already contains the best immediate experiment:** a
   prespecified FP-on/off × SIS-on/off retrieval-only factorial ablation. It
   physically removes raw slices, recomputes downstream components, preserves
   candidates and worlds, traces player-edge and lineup-support changes, and
   grades K1 through K80. As of this review, that experiment has not produced a
   durable run under its designated GCS prefix. The registry correctly still
   says `source_value_established=false` and `value_claim=not_evaluated`.

5. **The present scoring bottleneck is not primarily a Neo4j problem.** On the
   newest evidence, candidate completion loses roughly 58 points relative to
   the best roster available from touched players, while K80 ordering loses
   roughly five to six points relative to the supplied candidate oracle. The
   graph should remain a compact evidence index. Near-term compute should go to
   the already-built paid-source ablation and the lab's belief-gated completion
   lane, not to a larger graph or graph-algorithm project.

The recommended decision is therefore: **run the existing four-cell paid-source
ablation unchanged; add a small stage-influence sidecar to its outputs; then
separately test generation/completion effects prospectively. Do not claim that
FP or SIS is valuable merely because a column is present, a model assigns it a
coefficient, or a graph query finds a correlated cohort.**

## What is happening now

This review used the governing documents and recent history from both
repositories, not only the checked-out commits. The production checkout was on
local `main` at `8d7140f4`, three commits ahead of and 449 commits behind its
tracking branch, with extensive pre-existing changes. Fetched production
history was reviewed through `d45d5e6d` on `origin/main` and through the newer
diagnostic commits `9c283ac0`, `98d046aa`, and `37298ff2`. The lab checkout was
on a dirty feature branch; its fetched history was reviewed through
`49ee33a` on `origin/main` and the newer PREREG-083 through PREREG-086 work up
to `83dd02d`. No checkout or merge was performed.

`nfl2` does not contain a `CLAUDE.md` or `HANDOFF.md` in the checked-out or
fetched main history. Its operative equivalents are `LAB_RULES.md`,
`COORDINATION.md`, `LEDGER.md`, the active action note, and preregistrations.
The lab's influence-trace rule is exactly the right frame for this question:
source changes must be followed through player means/tails, dependence,
candidate membership, selected-book membership, and field/ownership behavior.
If an early stage does not change, later effects are not testable; if early
stages change but the final book does not, the intervening machinery erased the
signal.[1]

The current team objective is no longer a generic average-score proxy. The
documented ladder is slate-level winner-equivalent maximum, field win, and
ultimately expected settled payout. K20 is the bankroll-relevant primary
prefix; K80 remains a useful experimental diagnostic. Any paid-data test should
therefore report K20 and K80, the 200–240 point thresholds, best-treatment rank,
ordering discrimination, and prefix regret rather than only player-level loss
or full-pool correlation.

## Evidence map: where vendor influence is and is not measured

| Stage | Question | Current FP evidence | Current SIS evidence | Neo4j coverage | Verdict |
|---|---|---|---|---|---|
| Point-in-time source | Was the observation knowable before lock? | Historical strict-lag slices exist; a 2026 live matchup seal was captured | Historical PIT slices exist; no adopted Week 1 live SIS query was found | Provenance can be indexed | Partial; snapshot presence is not consumption |
| Component construction | Did the source alter a modeled football quantity? | Route, alignment, receiver/defense shell components exist | Defender alignment, run context, pass-tail, ASOE paths exist | E0 omitted them; PREREG-083 did not intervene on them | Narrow tests only |
| Player distribution | Did means, quantiles, or tails move? | Route fit moved Brier slightly; served route did not; coverage moved calibration slightly | Pass-tail and ASOE moved served distributions | Not represented in E0 | Yes for selected bundles, not individual fields |
| Dependence/joint law | Did teammate/opponent joint behavior move? | Route dependence treatment was tried and failed; coverage treatment changed roster supply | Pass-tail/ASOE treatments changed joint draws | Structural relationships represented, source deltas not | Mixed |
| Candidate generation | Did different legal rosters become available? | Coverage exact-80 union added 432 novel candidates; planned factorial intentionally fixes candidates | Some SIS tests fixed or shared supply; generation effect not isolated | E0 and PREREG-083 are strong supply indexes | Incomplete by source |
| Admission/ranking | Did paid data alter priority? | Four-cell runner is designed to answer; no durable result | Same | PREREG-083 diagnoses generic ranking, not vendor value | Not yet answered jointly |
| Selected book | Did K20/K80 composition or exposure change? | Coverage changed 33 selected slots each way but score grid tied | Pass-tail and ASOE changed selected books | Strong membership representation | Yes in narrow retrospective tests |
| Realized tail | Did fixed-budget score, field rank, or payout improve? | No convincing lineup-level gain | Small mixed historical gains; no production adoption | Grades can be joined, but source intervention is absent | Not established |
| Live policy | Is the source affecting 2026 submitted books? | Week 1 book documentation names simulations, props, and TabPFN, not paid matchups | No live use shown | No live attribution graph | No evidence found |

This table highlights the central analytical mistake to avoid: **available data
is not necessarily transformed data; transformed data is not necessarily
served data; served data is not necessarily candidate supply; supply is not
selection; selection is not tournament value.**

## How Neo4j has actually been used

### E0: a useful structural failure map

The bounded local E0 load used Neo4j 5.26.30 against a localhost fixture. Its
working corpus covered 54 slates, 199,244 candidates, 378,000 visits, 29,605
player-slate records, 2,592 books, 207,360 book selections, 432 final-fit K80
books, and 34,560 final-fit selections. The analysis found 279 historical
lineups scoring at least 200 points. Only 38 appeared in any final-fit book;
241 did not. There were 29 opportunity slates and only 10 conversions.[2]

The graph made the miss pattern legible. Among eligible 200-point lineups, the
captured set contained:

- none of 48 lineups with zero QB teammates;
- none of 43 with one QB teammate;
- two of 129 with two QB teammates;
- six of 55 with three QB teammates;
- one of four with four QB teammates;
- none of 124 lineups whose largest same-game group was three or less; and
- none of 37 lineups spanning at least seven games.

Captured 200-point lineups averaged 2.211 QB teammates versus 1.651 among
misses, and a 4.105 maximum same-game group versus 3.585 among misses. Only
four of 34 eligible 220-point lineups were captured. The best missed scores
included 241.10, 239.96, 239.10, and 235.60. This is strong evidence that the
production process under-supplied or filtered some flatter, cross-game winning
phenotypes. It justifies experiments on structural diversity, completion, and
selection.

It does **not** identify the paid source responsible. The E0 attribution shards
explicitly had `point_in_time_player_traits_attached=null`. The graph contained
player identity, position, team, opponent, game, salary, roster structure,
arm/block, final-book membership, and realized roster score. It did not contain
FP or SIS features, their as-of timestamps, player-distribution deltas,
ownership/leverage, full selector transitions, official winners, or per-player
realized contribution. The correct E0 conclusion is
`FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK`, not “the source caused the loss” and not
even necessarily “the selector caused the loss.”[3]

### Canonical v3: authority hardening, not a value test

The September 7 canonical-v3 work hardened exact suite authority,
pre-contact guards, replay identity, and provenance. Focused validation passed
104/104. This is valuable operational work: an influence claim is meaningless
if a graph silently combines the wrong slate, source generation, or selector
law. The schema's generic `CorpusRetrievalEntity` nodes and
`CORPUS_RELATION` edges can index immutable object authorities and selection
ranks. But no graph load, score, model, or live policy changed in that step.
It cannot be cited as FP/SIS performance evidence.

### PREREG-083: clear supply-versus-selection evidence

The newer local PREREG-083 load is a better experiment index. It loaded 28,165
nodes and 165,889 relationships; the shared fixture then held 32,600 nodes and
174,536 relationships. Every one of 12,960 roster nodes had exactly nine
player edges. Membership reconciled to 5,760 selected and 8,640 unselected
rosters. Control and treatment each contributed 36 slates, 7,200 candidate
occurrences, and 2,880 selected K80 occurrences.[4]

The graph distinguishes failure modes:

- Control supplied 12 candidates at 200+ and selected seven; treatment supplied
  12 and selected eight.
- Control supplied one candidate at 220+ and selected it; treatment supplied
  two at 220+ and selected neither.
- Treatment improved mean maximum at every reported prefix: K1 122.693 versus
  116.214, K20 168.508 versus 166.191, and K80 180.922 versus 178.792.
- Neither arm supplied a 230-point candidate.
- Served/simulation mean had only modest realized-score correlation
  (approximately 0.217/0.240), while q90 and q99 were weaker. Salary and simple
  structure were near zero.

That supports two conclusions. First, ranking leaves valuable supplied
candidates unused at finite K. Second, ranking alone cannot manufacture the
230+ supply that is absent. The companion bottleneck audit quantifies this:
candidate-oracle regret is about 18 points at K20 and five to six points at
K80, while the broader 72-slate funnel attributes roughly 58 points to
completion/candidate-supply loss relative to the best lineup available from
touched players.[5]

Again, this is **not a paid-source ablation**. The graph contains a knowledge-
gap indicator that paid-source-named columns are present, but PREREG-083 did
not turn FP or SIS off, change a consumer, or establish completeness. Any
vendor conclusion from these nodes would be an observational inference across
an experiment designed to answer a different question.

### Overall Neo4j assessment

Neo4j is earning its keep in four roles:

1. reconciling large many-to-many lineage across slates, candidates, books,
   players, arms, and grades;
2. finding structurally coherent missed cohorts that are awkward to express as
   one flat join;
3. separating “not supplied,” “supplied but not admitted,” and “admitted but
   not selected”; and
4. preserving queryable authority back to immutable JSON/CSV/object artifacts.

The numerical artifacts should remain authoritative. A property graph stores
nodes, relationships, labels, and properties; graph projections deliberately
select topology and properties for an analysis.[6] Neither abstraction supplies
an experimental counterfactual. The graph should index interventions and
their consequences, while paired estimators, bootstrap routines, and frozen
graders remain outside it.

## What the existing FP and SIS experiments say

### Fantasy Points

**Route share.** A strict-lag route-share fit covered about 82–83% of relevant
rows and evaluated 13,288 held-out examples. Overall 30-point Brier score moved
from 0.00968358 to 0.00965675; WR/TE Brier moved from 0.00763166 to
0.00760188. The 20-point score improved slightly, while MAE worsened from
2.88299 to 2.89248. This was enough to license one narrow lineup test, not to
establish source value.[7]

At the final served layer, the control and treatment became numerically
identical on 13,876 rows: Brier-20, Brier-30, q90, q95, and q99 all tied. The
TabPFN rank remap restored the same marginal plus market mean, erasing the
route signal. A later dependence-only route treatment did not rescue it; one
registered treatment was actively harmful under its equal-family comparison.
This is an exemplary influence-trace result: the source moved a fit metric, but
the serving transform erased the path before lineup value could be credited.[8]

**Coverage matchup.** A fitted player-level gate produced another very small
30-point Brier improvement, from 0.01813348 to 0.01809495, with worse 2025
performance and weak feature correlations. The exact-80 union nevertheless
added 432 novel candidates and swapped 33 selected slots in each direction.
All 107 weekly maxima and every reported score-threshold count tied. The source
therefore demonstrated a mechanism for changing roster identity but no measured
tail-score value under that experiment.

**Current live state.** A September 9 FP live matchup seal exists for 32 pairs
with a 2025/vendor-prior-season-early basis. That proves capture and authority,
not consumption. The current Week 1 published-book documentation instead names
current simulations, props, and TabPFN inputs. No evidence reviewed here shows
that the live book changed because of the sealed FP matchup rows.

### Sports Info Solutions

**Pass-tail dependence.** The score-free served gate improved held-out CRPS
from 2.7322923 to 2.7233727 while preserving row means, with the clearest gains
at QB and TE. In the licensed exact-80 selection test, treatment increased
selected 220+ seed-books from three to five, 210+ from 11 to 13, 200+ from 20
to 23, and 194+ from 37 to 38. Mean weekly maximum fell from 173.8999 to
173.4789, however, with a paired interval of approximately [-1.509, 0.700].
The gains were concentrated in two calendar slates and mixed by season.[9]

**ASOE.** The SIS ASOE treatment also passed a score-free first stage and was
selected at beta 0.0777118 in its historical exact-80 research read. It moved
210+ seed-weeks from 14 to 16 and 187+ from 58 to 64, while 194, 200, 220,
230, and 240 counts tied at 42, 26, five, one, and zero. Mean maximum improved
about 0.352 points, with a wide interval of approximately [-1.223, 1.949].
This is suggestive but not decisive.

**Other SIS paths.** The reviewed QB line and RB run-defense marginal tests
worsened 30-point Brier score and did not earn lineup reads. A receiver-copula
path lacked sufficient support for a held-out lineup conclusion. These
negative and untestable results matter: selecting only the pass-tail and ASOE
stories would materially overstate the source portfolio.

### What can honestly be claimed

The evidence supports the following sentence:

> Some FP and SIS feature bundles have changed player distributions, candidate
> identity, or selected-book identity in controlled historical tests; SIS has
> produced small mixed tail improvements in two selected research mechanisms,
> while FP has not produced a convincing lineup-level score gain.

It does not support any of these stronger statements:

- “FP data improves tournament performance.”
- “SIS is worth its cost in production.”
- “A particular FP or SIS field causes player X to be selected.”
- “Neo4j proved which vendor produces winners.”
- “The same result will hold in 2026 live contests.”

Most existing treatments are **bundles**. They establish the value, or lack of
value, of a prespecified transformation of several observations. A feature
coefficient, split gain, SHAP value, or graph association can describe how a
fitted model uses a field, but it does not by itself identify the field's
incremental causal contribution. SHAP is explicitly an additive model-
explanation framework; SAGE extends the idea to global predictive power and
interactions.[10][11] Both are useful diagnostics, not substitutes for source
removal and end-to-end replay.

## The existing four-cell experiment is the right next move

`paid_source_ablation_registry_v1.py` registers
`fp-sis-retrieval-only-cross-v1` with four cells:

| Cell | Fantasy Points | SIS |
|---|---:|---:|
| FP+ / SIS+ | on | on |
| FP− / SIS+ | off | on |
| FP+ / SIS− | on | off |
| FP− / SIS− | off | off |

The implementation is unusually strong in several respects:[12]

- It physically removes raw slices before component construction instead of
  replacing unavailable values with zero.
- It holds candidate and world bytes identical, so the contrast isolates the
  retrieval/admission/selection consumer rather than quietly changing supply.
- It recomputes FP shell fit, SIS run context, and joint alignment/workload
  components; joint components are unavailable when either required source is
  absent.
- It records raw and component changes, percentile changes, player-edge value
  and rank changes, joint-component loss, admission-order turnover, selected
  K80 turnover/order, and selected marginal-new-world traces.
- The grader joins outcomes only after the decision artifacts are frozen and
  reports candidate, admitted, and selected ceilings; K1/3/5/10/20/40/57/80;
  187–240 thresholds; supply-to-selection conversion; and regret.
- It computes conditional FP effects, conditional SIS effects, and the FP×SIS
  interaction rather than making an invalid additive vendor claim.

A two-factor interaction is exactly what is needed when the same football
concept can be represented jointly by vendor features. Standard two-factor
models separate factor A, factor B, and an A×B interaction instead of assuming
independence.[13]

The source preflight found 64,715 rows across six relations: 46,008 FP rows and
18,707 SIS rows, under a 2026-08-31 BigQuery snapshot. The normalized and
seven-pack builds completed, but the handoff explicitly said that no E5 runtime
execution had launched. A read-only listing on 2026-09-10 found no objects at
`gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-paid-source-fp-sis/`.
Accordingly, the four-cell source-value result does not yet exist durably.

This experiment has one deliberate limitation: because candidate supply is
byte-identical, it measures **retrieval, admission, and selection value only**.
It cannot answer whether FP or SIS would help a generator discover a lineup
that is missing from all four shared candidate pools. That is a feature, not a
bug, as long as the claim remains narrow. Generation/completion must be a
separate follow-up.

## Recommendations

### P0 — Execute and independently grade the existing 2×2 ablation

Do not build a replacement first. Reconfirm the frozen snapshot, image digest,
candidate/world identities, outcome quarantine, and fixed resource budget;
then run task 0, the full four cells, and the independent grader exactly as
registered. Use one launch cohort and immutable per-cell receipts. Do not tune
thresholds after seeing outcomes.

Primary decision outputs should be:

- K20 raw weekly maximum and K20 slate winner-equivalent maximum;
- K80 equivalents as the larger diagnostic book;
- 200, 210, 220, 230, and 240 conversion at pool, admitted, and selected stages;
- best-treatment rank, NDCG or another frozen rank-sensitive diagnostic, and
  prefix regret;
- selected player exposure deltas by position, team, game, salary band, and
  feature-change cohort; and
- conditional FP, conditional SIS, and interaction estimates.

NDCG is useful here because it discounts relevance by rank rather than treating
the 1st and 80th positions alike.[14] It should remain a diagnostic alongside
the actual K-prefix objective, not replace it.

### P1 — Add a compact stage-influence sidecar, then index it in Neo4j

The ablation already computes almost all required facts. Persist one normalized
sidecar keyed by immutable experiment, slate, cell, player/candidate, and
selection authorities. The minimum records should include:

| Record | Required fields |
|---|---|
| Source observation | vendor, raw feature family, value/missingness, source object/generation, as-of, lock time, age |
| Component delta | control/treatment value, availability, percentile and rank delta |
| Player distribution delta | mean, q75/q90/q95/q99, threshold probabilities, joint-law membership |
| Candidate delta | roster key, generation membership, aggregate support and changed-player count |
| Admission decision | eligibility, pre/post rank, cutoff margin, rejection reason |
| Selection decision | selected prefix, order, marginal new worlds, displacement partner |
| Grade | realized score, threshold indicators, slate winner-equivalent value, field rank/payout when authoritative |

Mirror only the identities and stage relationships into Neo4j:

```text
(SourceSnapshot)-[:PROVIDED]->(FeatureObservation)
(FeatureObservation)-[:CHANGED]->(PlayerSlateFeature)
(PlayerSlateFeature)-[:ALTERED]->(PlayerDistribution)
(Candidate)-[:CONTAINS]->(PlayerSlate)
(Candidate)-[:EVALUATED_BY]->(AdmissionDecision)
(AdmissionDecision)-[:FED]->(SelectionDecision)
(SelectionDecision)-[:MEMBER_OF]->(Book)
(Candidate)-[:GRADED_BY]->(OutcomeGrade)
```

Keep dense simulation matrices, world-by-candidate scores, and numerical
bootstrap arrays in immutable objects. The graph should carry their hashes and
authorities, not duplicate them.

Three bounded graph queries then become genuinely useful:

1. **Changed feature → changed exposure:** find player-slates whose source
   removal changes a component or tail probability, then compare candidate and
   selected exposure within the same slate and cell pair.
2. **First erased stage:** find source-sensitive player-slates whose candidate
   exposure changes but selected exposure does not, or candidates whose
   admission rank improves but selection order does not.
3. **Supply-to-score cohorts:** retrieve source-sensitive 200+/220+ candidates
   that were supplied, admitted, selected, or omitted in each cell.

These queries create auditable cohorts. The paired experiment—not Cypher—is
what identifies the treatment contrast.

### P2 — Test generation/completion separately

After the retrieval-only read, reuse the same four source cells in a separately
named generator/completion experiment. Hold solver law, seed budget, worlds,
and selection law fixed while allowing paid features to affect seed selection
or completion priorities. Report:

- new player-slate support;
- new legal roster count and phenotype coverage;
- candidate-oracle K20/K80 maximum;
- completion regret relative to best touched-player roster;
- overlap and novel 200+/220+/230+ supply; and
- how much downstream selection preserves or erases the new supply.

This should follow, not interrupt, PREREG-086's outcome-disabled mechanics
work. That lane already demonstrates legal multi-player seed expansion,
multiple distinct completions, critic disagreement, and disjoint worlds. The
next scientific question is whether the mechanism supplies better rosters—not
whether its graph representation is more elaborate.

### P3 — Attribute feature families hierarchically

If the 2×2 source result is promising, decompose it in this order:

1. vendor on/off;
2. prespecified component family on/off (route/alignment/shell, defender/run,
   and joint components);
3. raw feature groups within only the winning family; and
4. individual observations only for explanation or a fresh prospective test.

Use retraining/recomputation or conditional group ablation. Avoid unrestricted
row permutation for correlated football features: it creates unrealistic
feature combinations and can force model extrapolation.[15] Use SHAP/SAGE as
descriptive screens to identify candidate groups, never as the adoption gate.

Freeze a modest family before outcome read and control multiplicity. The
Benjamini–Hochberg procedure controls false discovery rate across a prespecified
set of hypotheses, but temporal/slate dependence and adaptive reuse still
require conservative interpretation.[16] A clean hierarchy is preferable to
hundreds of nominal p-values.

### P4 — Establish 2026 prospective shadow evidence

Historical panels are heavily exposed and suitable for development, not a
final live value claim. Before each slate locks, freeze all four shadow books
from the exact available source states, without using post-lock observations.
Record data age and missingness as features of the decision, not as after-the-
fact excuses. Keep K20 primary and K80 diagnostic. Accumulate the full season
or a prespecified information boundary before adoption.

If field entries, ownership, and payouts are authoritative, extend grading
from realized DK score to rank, duplication-adjusted payout, and expected
settled payout. Otherwise stop at the last authoritative objective and label
the result honestly.

### P5 — Improve probabilistic calibration and finite-book ordering together

The lab's newest results show why these must be separate axes:

- PREREG-084 improved full-pool Spearman ordering, but K20 utility intervals
  crossed zero and no 200+ tail value appeared.
- PREREG-085's set-aware learner was roughly flat/slightly positive on control
  but materially worse on the direct-tail arm, especially at K80.
- Its calibration audit found expected 200+ counts exceeding observed counts;
  direct-tail observed-minus-expected intervals were negative.

Proper scoring rules reward honest probabilistic forecasts through calibration
and sharpness.[17] They should be reported for player and lineup thresholds,
but the selection gate must remain the fixed-budget book objective. A model can
be better calibrated and still rank the wrong finite set; it can rank the full
pool better and still fail at K20.

## Exact analysis contract

For each slate (s), let (Y_{s,ab}(K)) be the frozen book objective at prefix
(K), with (a=1) for FP present and (b=1) for SIS present. Report both
conditional source effects:

```text
FP | SIS on  = mean_s[Y_s,11(K) - Y_s,01(K)]
FP | SIS off = mean_s[Y_s,10(K) - Y_s,00(K)]
SIS | FP on  = mean_s[Y_s,11(K) - Y_s,10(K)]
SIS | FP off = mean_s[Y_s,01(K) - Y_s,00(K)]
interaction  = mean_s[Y_s,11(K) - Y_s,10(K) - Y_s,01(K) + Y_s,00(K)]
```

Compute the same contrasts for each influence stage, not just realized score:

1. raw support, staleness, and missingness;
2. component availability/value/rank;
3. player mean, tail, and joint-law changes;
4. candidate support and aggregate lineup support;
5. admission rank and cutoff crossing;
6. selected order, exposure, turnover, and marginal new worlds;
7. K20/K80 score, thresholds, field rank, and payout where authoritative.

Pair within slate and preserve slate/season clusters. Candidate rows and player
rows are not independent observations. Clustered bootstrap methods exist
precisely because within-cluster residuals can be correlated.[18] With only a
few NFL seasons, report season effects and leave-one-season-out stability in
addition to intervals; do not hide instability behind a huge candidate-row
sample size.

Before reading outcomes, freeze:

- the primary K, objective, and threshold family;
- the exact inclusion/support rule;
- handling of missing source values;
- source freshness and lock-time guards;
- per-cell compute and candidate/world identity;
- bootstrap unit, seed registry, and interval rule;
- interaction interpretation; and
- adoption, near-miss, and stop rules.

## Suggested execution sequence

### Immediate

1. Treat the current empty GCS prefix as “not run,” not as failure or zero
   effect.
2. Reconcile the registered source snapshot and exact image/build authorities.
3. Launch the existing task-0 preflight and stop on any candidate/world byte
   mismatch, post-lock source observation, or unequal resource budget.
4. Run the four frozen cells and independent grade once.
5. Publish the influence ladder even if the final score is tied; a source can
   be valuable for diagnosis yet erased before selection, as route share was.

### After the first read

- If no player/component values change, close the source wiring question and
  debug consumption before discussing value.
- If player values change but candidate/admission/selection do not, locate the
  erasing transform and do not run a score-heavy expansion.
- If selection changes but K20/K80 outcomes do not, close the exact retrieval
  use unless a separate prospective information-value argument was frozen.
- If one source has a stable favorable conditional effect, run a fresh source-
  family decomposition and prospective shadow; do not immediately deploy.
- If interaction dominates, price and operate the pair as a joint information
  product. Do not allocate the interaction arbitrarily to one vendor.

### In parallel

Continue the bounded completion lane because the observed opportunity is much
larger there. Do not spend the heavy-command lane on graph expansion unless a
specific evidence query is impossible with the proposed sidecar plus current
schema.

## Risks and interpretation limits

- The historical panel has been repeatedly examined. Confidence intervals do
  not erase adaptive research exposure.
- Fixed-candidate paid-source ablation cannot measure source-driven discovery.
- Feature missingness can be informative; physical removal must remain
  distinguishable from vendor-observed null or zero.
- Vendor fields are correlated and often jointly transformed. Individual-field
  attribution may be unstable even when a source bundle is valuable.
- A selected-book score increase on 36–54 slates can be concentrated in one or
  two weeks. Always show slate and season contributions.
- Realized roster score is not equal to tournament profit. Field strength,
  ownership, duplication, payout rules, late news, and entry allocation mediate
  bankroll value.
- Neo4j is not the numerical authority and should not become a second mutable
  copy of dense experiment data.
- Current production and lab checkouts are dirty and production is substantially
  divergent from fetched main. Integrate this documentation carefully rather
  than committing unrelated state.

## Final decision table

| Question | Answer now | Evidence needed to upgrade the answer |
|---|---|---|
| Has Neo4j improved understanding of the lineup pipeline? | Yes | Continue bounded reconciliation and influence queries |
| Has Neo4j shown FP or SIS incremental value? | No | Source-intervened cells linked to graph stages and independent grades |
| Do FP/SIS data ever affect player or lineup decisions? | Yes, in narrow historical tests | Full 2×2 influence trace and prospective replication |
| Has FP improved realized selected-book tails? | Not convincingly | Favorable fixed-budget source ablation plus fresh shadow |
| Has SIS improved realized selected-book tails? | Small, mixed research evidence | Stable K20/K80 conditional effect and fresh shadow |
| Are individual paid fields attributable today? | No | Hierarchical conditional ablation with multiplicity control |
| Are current Week 1 books proven to consume FP/SIS? | No evidence found | Immutable live consumer lineage and paired shadow books |
| Should more Neo4j infrastructure be the next priority? | No | Only if a named influence query is blocked by current index/sidecar |
| What should run next? | Existing FP×SIS 2×2 retrieval ablation | Then source-sensitive completion/generation experiment |

## Sources

### Repository and durable project evidence

1. Production `README.md`, `CLAUDE.md`, and `HANDOFF.md`; lab `README.md`,
   `LAB_RULES.md`, `COORDINATION.md`, `LEDGER.md`, active action note, and recent
   Git history, reviewed 2026-09-10.
2. `d9cfad118157297581d3b53c8de4d9b419cf1e1f:reports/2026-09-02-neo4j-immediate-weakness-read.md`.
3. `02e0c2836ae0987851bcc980efb5a62ce974c559:reports/2026-09-02-production-to-lab-neo4j-score-priority-note.md`
   and
   `45641c93c92778519111bc3f4108bad13eb35d62:reports/2026-09-03-neo4j-selection-gap-pipeline-status-and-next-experiment.md`.
4. `98d046aaa0a8b103ffd734a7ec369d0162f798c3:reports/2026-09-10-prereg083-local-neo4j-load-and-ranking-audit.md`.
5. `37298ff22cbb3a098fb307e0e4c6c303cffaa2d3:reports/2026-09-10-scoring-bottleneck-and-week1-ordering-audit.md`.
6. Neo4j, “Graph database concepts,” and “Projecting graphs,” official
   documentation: <https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/>
   and
   <https://neo4j.com/docs/graph-data-science/current/management-ops/graph-creation/graph-project/>.
7. [Fantasy Points route-share experiment](./2026-08-10-fantasy-points-route-share-experiment.md).
8. [Fantasy Points route-share final served result](./2026-08-11-route-share-final-served-result.md)
   and production/lab experiment chronology in `HANDOFF.md` / `LEDGER.md`.
9. [SIS pass-tail final served result](./2026-08-13-sis-pass-tail-final-served-result.md)
   and [SIS pass-tail exact-80 result](./2026-08-14-sis-pass-tail-exact80-result.md).
10. Scott M. Lundberg and Su-In Lee, “A Unified Approach to Interpreting Model
    Predictions,” NeurIPS 2017:
    <https://proceedings.neurips.cc/paper/7062-a-unified-approach-to-interpreting-model-predictions.pdf>.
11. Ian Covert, Scott M. Lundberg, and Su-In Lee, “Understanding Global Feature
    Contributions With Additive Importance Measures,” NeurIPS 2020:
    <https://papers.nips.cc/paper/2020/file/c7bf0b7c1a86d5eb3be2c722cf2cf746-Paper.pdf>.
12. [Paid-source ablation registry](../src/nfl_dfs/research/paid_source_ablation_registry_v1.py),
    [runner](../src/nfl_dfs/research/corpus_r6_paid_source_ablation_v1.py),
    associated grader/tests, and the 2026-08-30 through 2026-08-31 production
    handoff entries.
13. NIST/SEMATECH, “Two-Factor Designs,” *e-Handbook of Statistical Methods*:
    <https://www.itl.nist.gov/div898/handbook/prc/section4/prc437.htm>.
14. Kalervo Järvelin and Jaana Kekäläinen, “Cumulated Gain-Based Evaluation of
    IR Techniques,” *ACM Transactions on Information Systems* 20(4), 2002:
    <https://dl.acm.org/doi/10.1145/582415.582418>.
15. Giles Hooker, Lucas Mentch, and Siyu Zhou, “Unrestricted Permutation Forces
    Extrapolation: Variable Importance Requires at Least One More Model, or
    There Is No Free Variable Importance,” 2019:
    <https://arxiv.org/abs/1905.03151>.
16. Yoav Benjamini and Yosef Hochberg, “Controlling the False Discovery Rate,”
    *Journal of the Royal Statistical Society B* 57(1), 1995:
    <https://rss.onlinelibrary.wiley.com/doi/10.1111/j.2517-6161.1995.tb02031.x>.
17. Tilmann Gneiting and Adrian E. Raftery, “Strictly Proper Scoring Rules,
    Prediction, and Estimation,” *Journal of the American Statistical
    Association* 102(477), 2007:
    <https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf>.
18. A. Colin Cameron, Jonah B. Gelbach, and Douglas L. Miller, “Bootstrap-Based
    Improvements for Inference with Clustered Errors,” NBER Technical Working
    Paper 344, 2007: <https://www.nber.org/papers/t0344>.

### Newest lab reads included in the review

- `a6d3742344653231558afe32905b76f5a40e4741:reports/2026-09-10-prereg084-tail-sorter-final.md`.
- `c9eb836aa7ba4d280f65306bd45a2049dab5240a:reports/2026-09-10-prereg085-setaware-and-calibration-read.md`.
- PREREG-086 outcome-disabled mechanics history through lab commit `83dd02d`.
