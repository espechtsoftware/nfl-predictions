# Production review for the lab: corpus-selection intelligence, participation, external supply, and P0 lineage

**Date:** 2026-09-01  
**Audience:** lab engineering/research team and production engineering  
**Primary material reviewed:** `/home/erich/projects/nfl2/reports/2026-08-31-corpus-selection-intelligence-and-panel-experiment-plan.md`  
**Lab implementation reviewed:** `ee4d2ecf06056ed294f82e88f3ae8c78b2275156`  
**Production reference reviewed:** `de790205` plus the frozen historical/live implementations cited below

## Executive disposition

The audit's central architecture is correct and should be adopted: evaluate the exact paid-size book, separate candidate population/proposal from criticism/retrieval, use the slate as the experimental unit, and require every purportedly useful feature to survive the complete path to realized K80 results. The proposed canonical candidate ledger is also the right foundation for the long-planned Neo4j intelligence layer.

There are, however, four immediate corrections and one important interpretation boundary:

1. **Do not freeze the `proj_tourney_v2` implementation in lab commit `ee4d2ec` as production parity.** It is not the production formula. The current live call disables ownership completely and changes punt handling. The exact correction is specified below.
2. **The new all-route lineage and universe receipt are useful starts but are not yet complete enough to support the claims made for them.** Anchor and LNS attempt ledgers are not passed through; leverage attempt accounting is partly inferred; and the universe receipt is aggregate rather than a row-level inclusion/exclusion ledger.
3. **Treat the participation issue as a high-priority scoring experiment, but reuse/cross the existing production latent-role machinery rather than beginning with an independent Bernoulli-zero model as if no implementation existed.** Absence must change teammate opportunity, not merely zero one player's score.
4. **The current lab live path does not actually enforce exact requested K or independently revalidate the complete named lineup contract.** Both selection and `assert_book` use `min(entries, len(cands))`, so a candidate shortfall can silently produce a smaller book; the assertion then checks only nine distinct IDs and duplicate rosters. Require exactly the requested K and canonical full-contract validation before a live receipt.
5. **The external-v1 defect blocks only a same-house-domain efficacy claim and Experiment 072's intended use.** It does not invalidate the reported/pipeline-DK-valid rosters for all purposes and does not block 068, 069, 071, the current valid production book, or unrelated lab experiments. The owner-directed architecture still makes only DraftKings legality universal; stacking and bring-back laws are named, testable strategy arms.

No valid in-flight fixed-image job needs to be stopped because of this review. No broad rerun of all historical arms is requested. Correct future receipts and retest only finalist packages if the participation treatment proves useful.

## Decision table

| Area | Disposition | What it blocks now | Owner / next action |
|---|---|---|---|
| Exact-K, proposal-versus-critic architecture | Adopt architecture; repair live enforcement | Week-1 receipt until exact requested K and full-contract validation are fail-closed | Lab removes the `min(...)` shortfall escape and revalidates the complete named contract |
| `proj_tourney` parity | **Correction required before live receipt** | Claim of production-parity Week-1 generation under `ee4d2ec` | Lab ports the exact formula and receipt contract; production reviews the patch |
| Frame/universe receipt | Adopt direction; complete implementation | Complete eligibility-forensics claim | Lab adds row-level disposition and hashes |
| All-route source lineage | Adopt direction; complete implementation | Source-credit/Shapley/Neo4j attribution claim | Lab passes ledgers through every family and preserves all attempts |
| Participation/eligibility law | High-priority efficacy experiment | No current book or unrelated experiment | Lab runs P1; production supplies existing latent-role implementation and lineage |
| External corpus v1 | Frozen, immutable, unsuitable for same-house efficacy | Experiment 072 and any native-house efficacy claim from v1 | Lab has correctly amended/frozen it; build v2 only after full contract parity |
| External proposer generally | Still worth testing | Nothing beyond v1-specific use | Compare v2 with count/time-matched additional native generation |
| Neo4j intelligence | Proceed after canonical ledger schema freezes | Nothing in current scoring queue | Store entities/relations and artifact references, not world matrices themselves |

## 1. Participation finding: verified, important, and narrower than its headline

### Reproduced evidence

Production component training is conditional on `was_active = true`. An independent reproduction of the frozen selected panel found:

- **1,428 of 7,120 selected rosters (20.056%)** contained at least one skill player later recorded as not participating.
- The seasonal rates were **33.681% in 2022**, **35.903% in 2023**, and **28.889% in 2024**.
- The 1,715 nonparticipating player appearances were:

| Position | Appearances | Share |
|---|---:|---:|
| WR | 745 | 43.4% |
| RB | 682 | 39.8% |
| TE | 243 | 14.2% |
| QB | 45 | 2.6% |

The injury-status values attached to those appearances were zero `Out`, 241 `Doubtful`, 453 `Questionable`, and 1,021 missing. This confirms that the existing panel had already excluded known-Out players. Therefore the proper baseline is not an untreated population that still contains known-Out players.

### Required terminology and regime audit

`was_active` is not an official game-day active-list label. In `sql/features/014_player_week_usage.sql`, it means that a salary-listed player had either a recorded stat line or a non-null offensive snap record; `sql/features/021_player_week_training.sql` carries that label into training. A false value can represent a true inactive, an identity/source gap, or a dressed player with no recorded trace.

The P1 label should therefore be called **observed participation/appearance**, not official activation. The abrupt historical regime change also has to be audited before fitting: early seasons show roughly 0.1–0.5% nonparticipation while 2022–24 are near 46% at the player-row level. A model that learns this source transition instead of football participation would be misleading.

The 20.056% roster rate is a contamination or opportunity bound. It is **not** an estimate of a 20% score gain, nor evidence that every affected roster would be improved by removing one player.

### The baseline and arms production recommends

Use these exact arm semantics:

1. **`BASE_PROD`** — current production hard exclusion of known O/IR/report-Out players plus the existing known-inactive opportunity cascade.
2. **`DOUBTFUL_HARD`** — `BASE_PROD` plus point-in-time Doubtful exclusion.
3. **`LATENT_PARTICIPATION`** — a walk-forward participation/role-state treatment, sampled coherently before conditional point production and accompanied by teammate opportunity redistribution.
4. **`ACTIVE_ORACLE`** — outcome-only upper bound, never adoptable and never allowed into pre-lock artifacts.

The current production live route already removes known Out/IR players and applies teammate opportunity redistribution in `src/nfl_dfs/inference/live_lineups.py` and `src/nfl_dfs/inference/cascade_adjust.py`. Do not credit this existing behavior as a new arm.

### Reuse the existing five-state production mechanism

Production already has a prospective five-state model in `src/nfl_dfs/research/latent_role_state.py`:

- `inactive`, `dormant`, `rotation`, `secondary`, and `primary` states;
- walk-forward multinomial probabilities;
- point-in-time injury and practice inputs;
- joint state worlds;
- zero inactive emissions, role-share emissions, and team-share caps;
- a validated live scenario factory.

The relevant design and validation records are:

- `reports/2026-08-15-prospective-latent-role-state-protocol.md`
- `reports/2026-08-15-latent-role-state-score-free-audit.md`
- `reports/2026-08-15-latent-role-live-factory-implementation.md`

This mechanism is prospective/shadow-only and is not the current money law. It should remain immutable under its original identity. For P1, port or cross its mechanism under a **new retrospective experiment identity** rather than silently changing the old artifact.

Two additions are needed. First, the existing state model covers RB/WR/TE, so add a low-capacity QB binary participation/status treatment or an explicit QB rule. Second, do not independently draw one zero/nonzero bit per component/candidate use and leave the rest of the offense unchanged. Draw one state per player **within each simulated world**, share it across every component and candidate use of that player in that world, allow it to vary across worlds, and redistribute or renormalize missing target/carry opportunity among teammates. Otherwise the treatment simulates disappearing offense rather than next-man-up football.

The existing prospective mechanism originally changes candidate proposals and then can score them under incumbent worlds. The audit's P1 asks a somewhat different question: changing the common generative law. The implementation and report must state which estimand is being tested. If attribution matters, run the candidate-only and law-level uses as distinct cells.

P1 reporting should include exact K20/K40/K80, realized weekly maximum, threshold weeks, candidate oracle/regret, selected-player nonparticipation contamination, calibration, candidate/book turnover, and source/coverage mix with slate-level paired uncertainty. If P1 is positive, cross only the surviving BF_DUAL and FU_DUAL packages under the corrected law; do not rerun every historical arm.

## 2. External corpus: exact defect, correct scope

All 72 immutable v1 files and manifest hashes were independently revalidated. The counts reproduce exactly:

- 21,600 requested and delivered rosters reported as DraftKings-valid by the external pipeline and its old partial validator;
- 1,703 retained as purportedly “house valid”;
- only 245 actually satisfy the native QB-plus-two-catchers/bring-back contract;
- 1,458 have exactly one same-team catcher;
- 24 of 72 slates have no native-house-valid retained roster.

The defect was the old lab validator counting the quarterback toward `qb_stack_min`, while the native optimizer counts WR/TE teammates excluding the quarterback. Bring-back enforcement was also conditional on that incorrect mate count.

The lab response is correct so far:

- commit `2e26f66` repaired stack and bring-back boundary semantics;
- PREREG-042 amendment 1 invalidated v1 for the planned same-house-domain efficacy read;
- v1 remains immutable;
- no 072 efficacy bank launched;
- 072 was removed from the corrected queue;
- the focused validator suite passed 6/6.

The precise interpretation matters. The owner has directed that only DraftKings legality is universal. Thus v1 is **invalid for a claim that it samples the native house domain**, not universally invalid as external supply. Because the exported/validated schema lacks `game_id` and the validator has not proved maximum-team/minimum-games parity, call the 21,600 rows **reported or pipeline-DK-valid**, not independently proven fully DK-valid, until full-contract revalidation succeeds. House QB-plus-two, bring-back, salary-floor, and similar topology laws must remain named strategy profiles.

Only the 1,703 retained rows are present in the v1 JSON artifacts. If the lab wants a robust DK-only external arm, the 21,600 outputs need to be regenerated under a versioned contract unless a separate immutable raw artifact exists.

Before external v2, close one remaining validator gap: the repaired `validate_roster` still does not accept `game_id` and therefore cannot independently enforce the full native profile's minimum-games and maximum-eight-from-one-team constraints in `src/nfl2/core/lineup.py`. Establish parity for the whole named contract, not only stack boundaries.

External v2 should:

- name exact contract IDs such as `dk_classic_v1` and `house_qb2_bb1_floor49_v1`;
- configure the intended topology in pydfs and independently validate every returned roster afterward;
- persist all DK-valid outputs, plus per-contract validation and rejection reasons;
- enforce a minimum delivered unique count;
- compare external supply with **count- and time-matched additional native boom generation**;
- report all-route overlap and selected-book share.

This is first a correctness repair and then a solver/search-inductive-bias experiment. The external proposer sees the same mean vector; by itself it does not add new football information.

## 3. Production decision on the P0 `proj_tourney` contract

### Exact production formula

The historical production snapshot can be reconstructed on all 40,387 rows with zero maximum absolute error using:

```text
base_i = max(mean_projection_i, generation_bank_p90_i)  if salary_i <= 4000
         mean_projection_i                               otherwise

proj_tourney_i = base_i - 25 * own_est_i
```

The production implementations are in:

- `src/nfl_dfs/backtest/replay.py:1150-1218`
- `src/nfl_dfs/inference/live_lineups.py:456-497`
- `src/nfl_dfs/optimizer/lineup.py:36` (`LEVERAGE_PENALTY = 25.0`)
- `src/nfl_dfs/inference/production_policy.py:247` (the frozen policy currently disables the trained ownership model, so the production fallback is the naive ownership vector)

The ownership penalty applies to **every** player, including cheap players, after the punt base is raised to at least p90. Optional position weights, nonlinear shapes, divergence tilts, and punt bonuses are off in the relevant frozen base contract.

### Why lab commit `ee4d2ec` is not production parity

`src/nfl2/pipeline.py:270-291` currently implements:

```text
salary <= 4000: p90
salary > 4000:  mean - fade * ownership, but only if both are explicitly passed
```

`scripts/live_week.py:119-121` calls it without `own_est` and without a fade, so the actual live formula is simply p90 below $4,000 and mean above $4,000. The receipt explicitly says the fade is inactive.

This differs from production in three decision-bearing ways:

1. it omits the ownership fade for every player;
2. it omits the ownership fade from cheap players even in its optional ownership branch;
3. it uses raw p90 rather than `max(mean, p90)` for the cheap-player base.

It also has no focused parity test in the current lab test tree, and its receipt does not hash the input/output vectors. Therefore `pt_v2` must not enter a Week-1 live receipt under a production-parity label.

### Required amendment

Port the exact formula above. Use the production naive-ownership implementation for the current frozen contract unless a separately named ownership-model arm is explicitly authorized. Do not silently use a zero vector. If the ownership source is unavailable, either fail the research-parity build or emit a **different formula ID** for an explicitly degraded live fallback.

A suggested formula identity is:

```text
production_naive_fade_punt_p90_v1
```

The receipt must include at least:

- formula ID and implementation/code identity;
- penalty `25.0`, leverage scale `1.0`, linear shape, and all optional tilts off;
- mean-vector source and SHA-256;
- generation-bank identity/seed, p90 quantile and method, and p90-vector SHA-256;
- ownership method/source and ownership-vector SHA-256;
- fallback reason, if any;
- final `proj_tourney` vector SHA-256.

Add boundary/parity tests for salary 4,000 versus 4,001, p90 below/above mean, ownership on every salary band, missing ownership fail/degraded behavior, stable hashing, and exact reconstruction of the frozen 40,387-row snapshot.

This is a parity repair, not a new scoring arm and not a reason to rerun fixed-image jobs that did not use the new live code.

## 4. P0 items 4–6: approved direction, incomplete current implementation

### Exact-K and full-contract validation

The live script selects `min(entries, len(cands))`, and `assert_book` defines its required size the same way. That makes a short candidate corpus fail open: a request for 80 or 90 entries can emit fewer entries and still pass. Replace this with an exact equality requirement against the requested `entries`; candidate shortfall must stop the build.

The current assertion checks only distinct candidate indices, distinct nine-player ID sets, and roster size. Before the live receipt is accepted, reopen the written book and independently validate every roster under the complete named contract: slot composition, salary cap and any named floor, team/game constraints, duplicate IDs, exact K, and whichever strategy topology profile the receipt claims. DraftKings legality and named strategy rules must be reported separately.

### Frame/universe receipt

`frame_universe_receipt` in `src/nfl2/live.py` records useful aggregate coverage, and the surrounding live diagnostic records excluded names for some filters. It does not yet provide the promised row-level answer to “why was every salary/roster row included or excluded?” because it runs on the already-filtered frame and returns counts rather than a canonical disposition ledger.

Add one row per salary/universe candidate with a stable player/slate key, inclusion boolean, ordered reason codes, roster-status source/value, injury source/value/timestamp, feature availability, market availability, fallback route, and input snapshot identity. Hash that ledger and include its artifact URI in the live receipt. Keep actual scores, `was_active`, and settled values out of it.

### All-route discovery lineage

The exposure ledger is the right design, but `src/nfl2/admission.py:41-55` currently calls `generate_anchors` and `destroy_repair` **without** their supported `ledger=ledger` argument. Only aggregate family summaries are appended. Consequently `attach_all_tags` cannot recover anchor/LNS rediscoveries, despite its “every family” docstring.

Pass the shared ledger into both calls and persist, for every attempt before deduplication:

- canonical roster ID/hash;
- proposal family/profile/contract/law;
- world/anchor/parent/core identity as applicable;
- attempt order and stable attempt ID;
- `new`, `duplicate`, `infeasible`, `error`, or `timeout` disposition;
- duplicate target identity;
- solve duration and resource envelope.

`generate_candidates` also synthesizes `exhausted` leverage records because `optimize_many` hides its internal retries/terminal cause. That is acceptable only if labeled aggregate/inferred. For exact solve accounting, instrument `optimize_many` at the attempt boundary rather than presenting inferred rows as observed attempt histories.

Persist `all_tags`/all discovery edges with the candidate artifact, not only as an in-memory attribute. “First source” can remain as a derived convenience field but must not be the attribution basis.

### Required reconciliation

For each family and the total corpus, freeze and reconcile:

```text
requested attempts
= new + duplicate + infeasible + error + timeout
```

Also reconcile persisted unique candidates to the set of all `new` canonical roster IDs. Source-effect analysis should use leave-one-source-out and Shapley/permutation attribution after this lineage exists; first-tag counts are order-biased.

## 5. What the audit does and does not change in the active research program

The audit does not invalidate prior scoring work wholesale. Participation is a common upstream limitation that may interact with generation and retrieval arms, but that interaction is an empirical question.

- Continue valid 068, 069, and 071 work under their frozen identities.
- Keep external 072 closed against v1.
- Do not stall unrelated scoring experiments behind P1.
- If P1 produces a material, stable realized-book improvement, retest only finalist BF_DUAL and FU_DUAL packages under the corrected law.
- Treat the existing 20.1% rate as a reason to test, not as an effect estimate.
- Treat the 575-to-250 admission result as nearly lossless; do not spend the near-term budget on another admission ranker without new evidence.
- Continue prioritizing belief/critic calibration and genuinely different proposal families, because current evidence points there rather than to shallow compression.

The safe interim Week-1 core remains BF_DUAL under the latest decision brief. FU_DUAL remains the aggressive, unresolved option. This review does not itself authorize either a new money allocation or a new sleeve.

Historical/live parity receipts must also expose market-match coverage, injury coverage, TabPFN coverage, ownership source, and every degraded fallback. A live shakedown with sparse market matches, no injury rows, or no TabPFN rows is an operational smoke, not evidence of historical-method parity.

## 6. Neo4j: how this work becomes durable lineup intelligence

The canonical candidate ledger is the missing bridge between experiments and the requested knowledge graph. Once its schema is stable, represent at least these entities:

- `CandidateLineup`
- `ProposalAttempt` and `ProposalFamily`
- `ContractVersion`
- `SimulationLawVersion`
- `Selector/BookStrategy`
- `Slate`
- `Player`
- `Settlement`
- `ExperimentRun`

Useful relationships include:

- `DISCOVERED_BY`
- `PROPOSED_IN`
- `SATISFIES_CONTRACT`
- `SCORED_UNDER`
- `SELECTED_IN`
- `CONTAINS_PLAYER`
- `SETTLED_AS`
- `DUPLICATE_OF`

This supports the questions the owner has consistently asked: which proposal families discover high scorers, which high-scoring candidates are lost before the book, which contracts suppress or retain them, which traits recur in winners and 200-plus corpus lineups, and which selectors turn available supply into realized K80 results.

Do **not** store 10,000-world matrices as Neo4j properties. Keep large matrices in immutable Parquet/NPZ/object storage. Neo4j should store their URI, generation/version, byte count, SHA-256, law/seed identity, and selected marginal summaries. This keeps the graph queryable and makes every result traceable without turning it into a matrix store.

The same player/slate/candidate IDs must be used from pre-lock generation through settlement. Pre-lock nodes and edges must never contain outcomes; `Settlement` edges are appended only after the frozen book/corpus is closed.

## 7. Acceptance gates for the next lab handoff

Production will consider P0 items 3–6 ready for the live receipt when all of the following are true:

- exact production `proj_tourney` reconstruction passes on the frozen snapshot and salary-boundary fixtures;
- the written book has exactly the requested K and every roster independently passes the complete named contract;
- ownership is present and identified, or the formula has an explicitly different degraded ID;
- formula input/output hashes are receipted;
- every generator family passes its real attempt ledger through the same canonical schema;
- all-route tags are persisted and survive artifact reopen;
- attempt accounting reconciles exactly, with inferred aggregate states labeled as such;
- the universe artifact gives a row-level eligibility disposition and source/timestamp lineage;
- no outcome, `was_active`, settled score, or post-lock feature enters any pre-lock artifact;
- candidate, contract, law, selector, frame, and matrix artifacts have versioned identities and hashes;
- focused tamper/parity/reopen tests pass.

For P1, production additionally wants the source-regime audit, explicit current-baseline semantics, coherent teammate redistribution, a QB treatment, exact-K endpoints, and finalist-only crossing rules frozen before realized outcomes are read.

For external v2, production additionally wants full named-contract parity, immutable full-output persistence, post-generation validation, and a count/time-matched native control.

## Final message to the lab

The audit is valuable and the research direction is approved. The participation signal is real enough to deserve immediate, careful testing; the external-v1 mismatch has been scoped and handled correctly; and the lineage work is exactly what production needs for long-term Foundry/Neo4j intelligence.

The immediate live-receipt blockers are bounded: the tournament objective in `ee4d2ec` is a newly defined no-ownership objective rather than the frozen production objective; requested K can fail open; and the full named roster contract is not independently revalidated. Please amend those surfaces before a live receipt. At the same time, finish the row-level universe ledger and pass the existing ledger through anchor/LNS so “all-route” really means all routes. These corrections do not require redesigning the experiment program, adding arms, or interrupting valid fixed-image work.
