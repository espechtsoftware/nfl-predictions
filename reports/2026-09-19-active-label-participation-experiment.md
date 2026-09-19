# Active-label TabPFN × participation: preparation protocol

September 19, 2026. Owner: laptop; production supplies artifact lineage and isolated GPU execution support. Risk class C for the predictive law and S for its downstream selection transfer. Earliest shadow: Week 3. Earliest entered use: Week 3 only if a concrete candidate passes its transfer/release review and the operator adopts it; no promise of that readiness. Otherwise the next supported week, without a 2027-only restriction.

## Question and existing evidence

Does the current TabPFN label population already account for some inactivity, and does adding an explicit participation mixture improve or distort the **final** law? The August 12 PIT-clean active-label experiment already selected an active-only historical cache (107 slates, 220 counts 2→2, 210 counts 4→6, mean maximum +0.5125). That is development evidence under its named downstream chain, not a prospective Week-3 result. See [source review](2026-09-19-availability-law-source-review.md).

The live generator admits inactive zero labels, while component fits use active rows; the lab then shapes and recenters the incumbent draws. Counts of inactive labels cannot identify the final zero mass or prove double-counting. The experiment must measure the consumed forecasts and resulting lineups.

## Four arms, one interpretation

| Arm | TabPFN training labels | Explicit participation |
|---|---|---|
| A | current eligible labels | off |
| B | active-only, same context-selection algorithm | off |
| C | current eligible labels | existing frozen participation map |
| D | active-only, same context-selection algorithm | same frozen map |

Hold the component models, market inputs/blend, feature snapshot, projection/scoring code, legal universe, simulation seeds, candidate pool, book size and delivered-order helper fixed in the first stage. Fit A and B on the same image, cutoff and frozen training snapshot. Removing rows can change a capped context sample; retain selected row identities and report exactly that change. Do not describe it as a pure relabelling of identical context. No context-size/hyperparameter grid. The strict-prior filter must remain intact.

Distinguish two transfer stages. First, trace the full forecast consumer: raw quantiles → served means → transformed/recentered incumbent law → optional participation → fixed-corpus selection → delivered ordering. Hsim is held fixed except for any **explicitly documented** dependency on changed served means; report that dependency and its effect, rather than claiming a fixed hsim if the production contract recalibrates it. Second, only if the first stage is active and useful, regenerate candidates under the nominated law at a fixed solve budget and compare with a co-run control. Report natural unique-candidate yield as well as the fixed-corpus comparison.

## Required outputs and decision record

- Identity/support: exact A/B training rows before/after context sampling by season, position and active flag; target-key coverage; quantile order/finite checks; prelock status-source time; count of changed/unchanged final forecasts. Missing availability does not imply confirmed active. Confirmed inactive handling remains the established eligibility contract.
- Forecast diagnostics: paired empirical-distribution CRPS; mean bias and squared error for served means; median MAE; zero-score mass; q10/q50/q90 coverage and upper-tail pinball scores. Activity prediction and positive scoring conditional on playing are reported separately. Ground truth and missing-stat semantics must be explicit.
- Interactions: B−A, C−A, D−B, D−C, and (D−B)−(C−A), with all four arms printed. No post-result choice of the favorable factor or metric. Game/slate clustering, never thousands of overlapping lineups as independent evidence.
- Selection transfer: expected maximum, the labelled GLOBAL proxy and P220 under separate fixed audit laws; first delivered entry, declared prefixes and contest blocks; membership/exposure shifts and every material loss. Re-evaluating each arm only under its own law is insufficient. Simulated improvements remain conditional model evidence.
- Prospective record: freeze paired forecasts/books before lock, carry all ready arms forward, evaluate after settlement using the reviewed scorer. Candidate-specific use can be recommended using prior and current evidence with uncertainty; the historical verdict is not rewritten.

## Start now / dependencies

Production is asked to locate `tabpfn_active_label_treatment_v2`, its accepted artifacts, and the exact deployed context sampler; provide a counts/identity-only snapshot before fitting. Laptop prepares the consumer comparison and reviews context selection. The first run uses a small synthetic-label/full-path smoke and one actual target-week forecast **without outcome access**, then the declared fixed four arms; expensive panel work is conditional on that trace being nonvacuous.

Readiness is **protocol prepared, model execution not yet launched**. Before any fitted comparison, freeze an execution supplement with table/object generations, source/image identities, arm namespaces, selected target population, status map, seeds, cost/timeout and actual output schemas. Those missing identities are execution dependencies, not unanswered strategic permission questions. Scratch writes belong to an isolated lab/scratch namespace and the shared GPU job requires its ordinary lane and restoration receipt. The live cache remains the current adopted artifact until a separately reviewed release.
