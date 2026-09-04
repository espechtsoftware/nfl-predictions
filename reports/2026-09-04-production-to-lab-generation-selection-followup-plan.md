# Production-to-lab plan: convert improved corpus supply into a better selected book

**Date:** 2026-09-04

**Status:** production-authored execution plan for lab review and implementation

**Source clarification:** the document `reports/2026-09-04-lab-suggestions-on-generation-selection-brief.md` was supplied by an independent assistant. It is useful input, but it is not a lab-authored commitment, result, or authorization.

## 1. Purpose

The immediate scientific problem is narrower than rebuilding the full optimizer:

> Recent generation treatments are creating more high-scoring candidates, but the selector is capturing too little of that added supply. Determine whether the newly identified beneficiary phenotype can retrieve those candidates prospectively; if it cannot, move directly to one walk-forward learned selector. Then test the winning retrieval method jointly with generation on fresh banks.

This plan deliberately avoids a feature grid, rescue-dose sweep, or another generic schema project. It defines one cheap diagnostic gate, one routed selector experiment, and one final generation-by-retrieval crossing.

## 2. Evidence motivating the plan

The following are descriptive facts from already opened, sealed work. They are not a new adoption claim:

1. PREREG-065 / experiment 094 increased corpus supply much more than it improved the selected K80 book.
2. Exact roster-hash lineage shows that redistribution added 131 candidate instances scoring at least 200 and displaced 68, for a net gain of 63.
3. Of the 131 added candidates scoring at least 200, 103 were beneficiary-only. The same phenotype accounted for 48/59 added candidates at least 210, 18/21 at least 220, and 6/6 at least 230.
4. The incumbent DEMAX selector captured only 18/131 of the added candidates scoring at least 200, while the control had selected 17/68 of the displaced candidates scoring at least 200.
5. PREREG-062 found that ordinary candidate features were weak at identifying unselected candidates that would beat the selected-book maximum. No feature survived its frozen rescue-relevance FDR cut. The best descriptive associations were small: `market_points_sum` about +0.029 and `sim_mean` about +0.020.
6. The raw designation count has a different interpretation from beneficiary status. Roster exposure to a designated player has been negatively associated with outcomes, whereas the added high scorers are concentrated among teammates who benefit when a designated player is absent.
7. PREREG-060 suggests that novelty can behave differently at small K than at K80. That is relevant to the actual nested K3/K10/K20/K57 contest allocation, but it is not yet a licensed live policy.

The correct reading is therefore not “generation is solved.” Generation found a promising phenotype and added some extreme-tail candidates, but the present retrieval law did not reliably convert that supply into a stronger book.

## 3. Immutable boundaries

1. **Do not amend, delay, or add endpoints to PREREG-066 / experiment 095.** Its four cells, family, reader, prefixes, banks 690–692, and interpretation remain frozen.
2. **Experiment 091 remains held.** This plan does not authorize launching it, changing it, or relabeling it as the proposed successor.
3. No 095 outcome may influence 095 code, arms, endpoints, or pass rule.
4. Any score-bearing follow-up must use unused fresh banks, one frozen control, a fixed admission/selection budget, and a preregistered interpretation table.
5. Candidate-only lineage must be frozen before settlement joins. Outcomes enter only through the reader or a separately bound post-settlement sidecar.
6. The lab implements and performs the first read only after production review. Production owns immutable builds, registered Cloud Run launches, gate receipts, and the independent read.
7. Week-1 capture, P_MIX certification, and contest/shadow binding remain dated production work and must not be delayed by this research.

## 4. Work package A — prepare the 095 lineage diagnostic now

This work may proceed while 095 computes because it does not read outcomes or change 095.

### A1. Freeze the candidate-lineage interface

For every 095 candidate, emit or reconstruct the following by exact `(season, week, bank, generation_arm, roster_sha256)` identity:

- generation arm: `CTRL` or `REDIST`;
- selection membership and rank for `DEMAX` and `NOV`;
- `redist_only`, `ctrl_only`, or shared-pool status;
- `beneficiary_only` as defined by the frozen redistribution trace;
- count of designated players actually rostered;
- identifiers of the designated player or players linked to each beneficiary;
- point-in-time active-probability value, timestamp, source class/support, and missingness for each linked designation;
- frozen pre-lock judge values, candidate ranks, count-match identity, family, structure, ownership, market, boom, and correlation fields already available in the trace;
- exact source, image, run, schema, and artifact hashes.

Do not require `REDIST_ONLY` as a future live feature: it requires both generation pools and is a counterfactual research label. `beneficiary_only` and its linked pre-lock participation confidence are the deployable features.

### A2. Add fail-closed tests

At minimum, tests must reject:

- a roster hash that does not join one-to-one within slate/bank/pool;
- a beneficiary without a linked designation;
- a post-lock status or outcome field in the candidate artifact;
- a missing or mismatched P_MIX/designation source identity;
- duplicate candidate rows hidden by serialization;
- recomputation of a selection flag under a different selector identity;
- any candidate count or K that differs from the sealed 095 receipt.

### A3. Deliverable

Produce one candidate-only schema fixture and an outcome-disabled real-artifact smoke. Do not open the 095 settlement and do not publish an efficacy claim.

## 5. Work package B — one beneficiary rescue-relevance gate after 095 seals

This is a diagnostic gate, not a score-bearing arm and not a 24-feature resweep.

### B1. Cohort

Run the statistic only if the sealed 095 result leaves redistributed supply scientifically eligible for a follow-up. Use all sealed 095 banks and slates. The primary candidate universe is:

- candidates in the `REDIST` pool;
- not selected by the `REDIST_DEMAX` control book;
- exact settled score joined by canonical roster hash;
- no row chosen or excluded after inspecting its score.

### B2. Prespecified feature and target

- Feature `B`: the binary, pre-lock `beneficiary_only` flag.
- Target `Y`: `1` when an unselected candidate's realized score exceeds the realized maximum of its same-slate `REDIST_DEMAX` book; otherwise `0`.

Use the exact PREREG-062 rescue-relevance machinery: within-slate Spearman association between `B` and `Y`, mean over supported slates, season-clustered bootstrap with 20,000 draws and seed 62, weekly sign-flip statistic, and leave-one-season-out cuts. Because this is one newly prespecified hypothesis, do not rerun the old 23-feature family or describe this as an FDR survivor.

Also report, descriptively:

- supported slates, seasons, candidates, and rescue events;
- `P(Y=1 | B=1)` and `P(Y=1 | B=0)` with candidate and slate denominators;
- risk difference and odds ratio;
- prevalence of `B` among all unselected candidates and among rescuers;
- the same values by bank and season.

### B3. Frozen routing rule

Before computing the statistic, freeze the following disposition:

- **RESCUE_ELIGIBLE:** point estimate is positive, the season-clustered 95% interval excludes zero on the positive side, at least three of four leave-one-season-out cuts are positive, and the cohort includes at least three seasons with both beneficiary and non-beneficiary candidates plus at least 30 total rescue events.
- **INSUFFICIENT_SUPPORT:** the support requirement is not met. Do not force a rescue experiment; route to the learned selector.
- **RESCUE_NOT_SUPPORTED:** every other result. Do not run a beneficiary-only rescue cohort; route to the learned selector.

This is intentionally a demanding screen. The existing rescue base rate is weak, and a separate score-bearing cohort is warranted only if beneficiary status is materially different from the near-null generic feature field.

## 6. Work package C — route exactly one next selector experiment

Only one branch receives the next score-bearing slot.

### Route C1 — compact beneficiary rescue, only after `RESCUE_ELIGIBLE`

Use the same redistributed D800 pool and sealed P_MIX judge for both arms.

- **Control:** the current `REDIST_DEMAX` book.
- **Treatment:** `REDIST_BEN_RESCUE`, identical to the control except for one fixed rescue sleeve of 8 seats in K80.
- **Eligibility:** unselected `beneficiary_only` candidates with a valid linked designation and point-in-time participation confidence from the frozen P_MIX input.
- **Priority:** use the existing frozen judge's marginal book value, adjusted by the predeclared linked-absence confidence. Do not introduce a second learned score.
- **Replacement:** iteratively add the highest-priority eligible candidate and remove the incumbent with the smallest loss under that same frozen judge, subject to exact K80, legality, uniqueness, and the existing portfolio constraints.
- **Dose:** exactly 8 attempted replacements; no 2/4/8/16 ladder. If fewer than 8 eligible replacements exist, disclose the shortfall and apply the preregistered vacuity rule.
- **Held-out geometry:** calculate coverage and correlation diagnostics on a disjoint held-out P_MIX world bank, never the selection worlds.

The primary endpoint should be the same winner-CDF-based weekly-book objective used by the current generation/retrieval program, with one paired treatment-versus-control contrast and the usual bank/LOSO safeguards. Raw weekly max and thresholds 194/200/210/220/230 are co-reports.

### Route C2 — one walk-forward learned hybrid after `INSUFFICIENT_SUPPORT` or `RESCUE_NOT_SUPPORTED`

Do not launch frozen experiment 091. Draft a new successor protocol on fresh banks, reusing audited modules only by pinned byte identity.

- **Control:** the current eligible deployed/historical selector on the same redistributed D800 pool and P_MIX judge.
- **Treatment:** one walk-forward hybrid selector, trained only on prior-season candidate data.
- **Base family:** the already frozen F2 beliefs/market/ownership family.
- **Required sign split:** separate features for designated players rostered and beneficiary-of-designated-absence exposure. Never pass an unsplit generic designation count as a substitute.
- **Optional paid-derived continuation:** include the already specified F3 family as one nested block only if its point-in-time coverage and source hashes pass. No individual-feature cherry-picking.
- **Model/dose:** one model class and one fixed hybrid weight chosen before the fresh-bank outcomes; no weight, feature, model, or rescue-dose grid.
- **Walk-forward law:** season `S` may train only on seasons `< S`; the earliest unsupported season must degenerate to control and be disclosed.

The primary endpoint and co-reports are the same as Route C1. A learned model must publish fold identities, feature availability, missingness, predictions, and exact training-row hashes.

## 7. Mandatory diagnostics for whichever route runs

These diagnostics explain a verdict; they do not become extra primary contrasts.

### D1. Added-versus-displaced accounting

For every threshold in 194/200/210/220/230, report:

- candidates added, displaced, and shared;
- selected counts and selection rates for each cohort;
- treatment-only and control-only selected lineups;
- realized score distribution of both sides;
- beneficiary-only and designated-rostered shares.

A score verdict must never be quoted without its displacement cost. If the frozen reader does not already support this, publish a deterministic companion artifact keyed to the exact sealed runs rather than amending a running reader.

### D2. Sign-separated calibration

Report candidate and selected-book calibration separately for:

1. a designated player rostered;
2. a beneficiary rostered while the linked designated player is absent from the lineup;
3. neither condition;
4. both conditions, if possible.

At settlement, stratify beneficiary performance by whether the linked designated player actually played or sat. Actual status is diagnostic only. A live policy may use only timestamped pre-lock participation probabilities and their support class.

### D3. Tail quality and complementarity

On an independent world bank, keep these names distinct:

- entropy effective rank of the selected-lineup correlation matrix;
- independent-equivalent tail-shot count at each relevant threshold;
- simulated book exceedance and winner-CDF proxy;
- marginal expected-max contribution.

Do not use higher independence alone as an adoption gate. T3 showed that independence and candidate quality can move in opposite directions.

### D4. Spike robustness

Apply the existing N2 decomposition to treatment-only rescues and classify their advantage as clamp-robust or dominated by a single-player spike. This is a descriptive fragility label, not permission to tune a new clamp on the same outcomes.

### D5. Small-K views

Report the frozen nested K3/K10/K20/K57/K80 prefixes. These are co-reports, not a redefinition of the primary K80 verdict.

If both K3 and K10 treatment estimates are positive, each is positive in at least two of three banks, and neither shows a severe tail-quality or contamination veto, the result may **nominate** one separate fresh-bank mixed-policy experiment: the routed alternative selector for qualifier books and DEMAX for the K57 Milly book. It does not pass 095 or the current selector experiment and may not be adopted directly.

## 8. Work package D — final generation-by-retrieval crossing

If and only if Route C1 or C2 produces an eligible selector, run one final fresh-bank 2-by-2 crossing:

- control generation × control retrieval;
- control generation × routed retrieval;
- redistributed/participation-aware generation × control retrieval;
- redistributed/participation-aware generation × routed retrieval.

Use equal generation and selection budgets, one shared judge, disjoint held-out worlds, exact count matching within generation rows, and a preregistered interaction. This crossing determines whether supply and retrieval gains combine, substitute for one another, or interfere. Do not infer stacking from separate experiments.

## 9. Required artifacts and review gates

For each new score-bearing experiment, the lab should provide production with:

1. a design document with every outcome mapped to a disposition;
2. runner, reader, mechanics gate, and focused behavioral tests;
3. an outcome-disabled real-artifact smoke showing that generation/selection actually engages;
4. exact source and runtime-artifact hashes;
5. a single-file launch contract with unused banks/prefixes and compute estimate;
6. a candidate-only trace schema and no-outcome proof;
7. full-suite and lint results;
8. after production's immutable build, an independent reproduction of the mechanics receipt;
9. after all clean terminals, one first-read transcript committed with the sealing commit;
10. an explicit statement that experiment 091 remained held and no live policy changed.

Production then performs the independent read, ledger cross-check, and HANDOFF update. Only the operator can authorize a live-money or Week-1 entered-book change.

## 10. Immediate lab sequence

1. Review this plan and flag only a conflicting schema, unavailable input, invalid statistic, or simpler equivalent implementation.
2. While 095 runs, implement Work Package A and an outcome-disabled fixture/smoke. Do not touch frozen 095 files.
3. Wait for the sealed 095 result and production's independent read.
4. If redistributed supply remains eligible, freeze and run Work Package B exactly once.
5. Route to C1 or C2 by the frozen gate; do not run both.
6. Return a single launch contract for the routed score-bearing experiment.
7. Preserve the final 2-by-2 crossing as the decision-bearing confirmation after the routed selector earns it.

This plan is intentionally aggressive about learning while conservative about retrospective overfitting: one phenotype gate, one selector intervention, and one final crossing.
