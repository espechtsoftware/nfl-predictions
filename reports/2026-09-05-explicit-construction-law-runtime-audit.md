# Explicit Construction-Law Runtime Audit

**Status:** Independent review repairs applied; focused tests pending  
**Date:** 2026-09-05  
**Audited source:** production `origin/main` at `562d9208ab73335b3c6c50c98642e894fac09dad`  
**Scope:** Classic lineup construction, generation, replay, live/API entry points, candidate receipts, and interpretation of prior evidence  
**Method:** Read-only source audit followed by a bounded, behavior-preserving base-receipt hardening. No cloud execution, deployment, scoring, entry, manifest, frozen artifact, or live policy/default was changed.

## Executive conclusion

There is no universal Classic rule requiring a QB, a same-team WR, and an opposing WR. The Classic optimizer's bare defaults are neutral: DraftKings roster legality is enforced, while all eight stack/RB relationship settings default to zero or false. When a bring-back is requested, however, the eligible opponent may be an RB, WR, or TE—not only a WR.

The current named incumbent policy intentionally imposes stronger construction: at least two same-team QB catchers, at least one opposing RB/WR/TE, no RB against the opposing DST, no two RBs from the same team, minimum salary 49,000, at least two games, and maximum overlap seven. The named legality-only policy neutralizes those named restrictions.

The central defect is not evidence that the current money path silently dropped its intended incumbent rules. The central defect is that the system does not yet carry a complete, immutable, candidate-aligned identity of the construction actually enforced. The generic engine can create heterogeneous candidate families using additional locks, game requirements, salary bands, overlap limits, and objectives while attaching one global base-policy receipt to the whole batch. Several legacy scripts also constructed partial versions of the incumbent rules manually. Therefore some old results can be interpreted only as tests under their observed mechanics, not as proof of either the full incumbent policy or pure DraftKings legality.

The correction should be version-forward and bounded:

1. Preserve the current named policies and their behavior.
2. Introduce a complete base construction-policy identity and a separate per-candidate overlay identity.
3. Bind and verify those identities at runtime rather than reconstructing them after optimization.
4. Record whether every requested rule was actually active for the available player pool.
5. Audit and classify prior evidence; do not rerun everything.
6. Retest only decision-bearing comparisons whose mechanics cannot be reconstructed or whose missing rule could plausibly change the arm contrast.

This work is important for causal interpretation and safe comparison of generation strategies. It is not a reason to stop or rewrite frozen experiments, and it should not be used to erase valid prior scoring results merely because their receipts are less complete than the proposed standard.

## 1. Questions answered

### 1.1 Does every Classic lineup require QB + catcher(s) + opposing WR?

No.

- `src/nfl_dfs/optimizer/lineup.py:78-92` defines all eight `StackRules` fields with neutral defaults.
- `src/nfl_dfs/optimizer/lineup.py:330-331` applies stack constraints only when a `StackRules` object is supplied; a neutral object adds no substantive stack restriction.
- `src/nfl_dfs/optimizer/lineup.py:504-518` defines an activated bring-back as any opposing RB, WR, or TE.
- `src/nfl_dfs/research/corpus_r6_population_profiles_v1.py:87-90` explicitly records that there is no global opposing-WR hard rule.

An arbitrary thesis or experiment can lock a QB, same-team receiver, and opposing receiver together, but that is an experiment overlay, not a universal Classic law. The relevant dynamic thesis logic is in `src/nfl_dfs/backtest/engine.py:1313-1340`.

Showdown is a separate product and should not be used to infer Classic behavior. `src/nfl_dfs/optimizer/showdown.py:110-130` has a `SHOWDOWN_BRING_BACK` rule that can require an opposing pass-position player for a pass-position captain.

### 1.2 What does the current named incumbent policy require?

`src/nfl_dfs/optimizer/construction_presets.py:122-140` defines the two named presets. The incumbent preset currently resolves to:

- `qb_stack_min = 2`;
- `bring_back_min = 1`;
- `forbid_rb_vs_dst = true`;
- `forbid_two_rb_same_team = true`;
- minimum salary 49,000;
- minimum two represented games;
- maximum overlap seven;
- punt threshold 4,000 with a minimum count of zero, so the punt rule is inactive.

The legality-only preset resolves to neutral `StackRules`, minimum salary zero, minimum one represented game, and maximum overlap eight. It is a named base policy; it is not yet a complete statement that every candidate produced by the full engine has no additional family-specific construction overlay.

### 1.3 Is current production necessarily running the wrong policy?

No such conclusion is supported by this audit. `src/nfl_dfs/inference/production_policy.py:201-306` filters the live engine environment and explicitly overwrites controlled construction levers. That substantially protects the current live-money path from ambient environment leakage. The remaining issue is proof: `public_identity` at `src/nfl_dfs/inference/production_policy.py:497-595` reconstructs an identity from configured values rather than proving the arguments and constraints observed by every lower-level optimizer call.

## 2. Observed mechanics map

| Surface | Observed behavior | Evidence | Consequence |
|---|---|---|---|
| Bare Classic optimizer | Salary cap 50,000, nine roster slots, DraftKings position constraints, maximum eight from one team, and minimum one game are default primitives. | `src/nfl_dfs/optimizer/lineup.py:26-42`, `178-242` | DraftKings legality and a few implementation defaults exist independently of named presets. |
| Stack defaults | All eight `StackRules` values default to neutral. | `src/nfl_dfs/optimizer/lineup.py:78-92` | QB/catcher/bring-back rules are not universal at optimizer-core level. |
| Stack semantics | Activated QB stack counts same-team WR/TE catchers; activated bring-back accepts opposing RB/WR/TE. RB-vs-DST and same-team-RB rules are independently switchable. | `src/nfl_dfs/optimizer/lineup.py:463-564` | “Opposing WR required” is an inaccurate description of the Classic rule. |
| Named presets | `dk-classic-legality-only-v1` and `classic-incumbent-gpp-v1` are self-hashed base-policy receipts. | `src/nfl_dfs/optimizer/construction_presets.py:19-20`, `64-96`, `122-140` | Good foundation, but not a complete runtime identity. |
| Preset override surface | Resolver exposes only QB minimum, bring-back minimum, the two RB prohibitions, salary floor, game minimum, overlap, and punt settings. | `src/nfl_dfs/optimizer/construction_presets.py:144-204` | Four `StackRules` dimensions cannot be represented through this high-level resolver: QB maximum, bring-back maximum, require RB-vs-DST, and require two same-team RBs. |
| Environment rules | Punt, value, ownership barbell, game cap, and low-ownership rules are independently activated through environment inputs. | `src/nfl_dfs/optimizer/lineup.py:244-313` | A base stack receipt alone does not identify the feasible set. |
| Dynamic restrictions | Game locks, player locks/bans, and prior-lineup no-good/overlap restrictions are passed independently. | `src/nfl_dfs/optimizer/lineup.py:315-328`, `334-460`, `567-668` | Candidate construction depends on unreceipted overlays. |
| Core-and-variations | Scout overlap is hard-coded at six; core locks and later overlap are derived dynamically. | `src/nfl_dfs/optimizer/lineup.py:1041-1099` | `/lineups/core` cannot be described by the base preset alone. |
| Candidate engine | Base, open, single-stack, hyper, conditional-extreme, role, gumbel, no-stack, low-salary, QD, QB-variant, top-game, dark-game, route/coverage, and thesis families use different overlays. | `src/nfl_dfs/backtest/engine.py:970-1055`, `1225-1232`, `1313-1425`, `1534-2160` | One batch may contain multiple effective construction policies. |
| Candidate batch receipt | A single global construction-preset receipt is stored for a heterogeneous batch. | `src/nfl_dfs/backtest/engine.py:2247-2319`, especially `2267-2269` | The receipt proves configured base intent, not candidate-level effective mechanics. |
| Batch validation | Matrix shapes, player universe, and duplicate conditions are checked; construction identity and conformance are not. | `src/nfl_dfs/backtest/engine.py:133-179` | Missing, mismatched, or stale construction identities can pass validation. |
| Candidate transforms | Transforms may replace candidates after generation without a construction-identity preservation check. | `src/nfl_dfs/backtest/engine.py:2324-2340` | Post-generation lineage can lose the mechanics that created the roster. |
| Engine fallback | Non-tail fallback does not preserve the construction receipt through the same path. | `src/nfl_dfs/backtest/engine.py:2886-2930`, `2959-2993` | Receipt behavior depends on execution route. |
| API | The request resolves a named preset but passes stack, environment, and receipt separately, then dynamically stamps or reconstructs identity after execution. | `src/nfl_dfs/app/main.py:78-103`, `2484-2495`, `2527-2567`, `2596-2619`, `2712-2741` | Requested policy can be reported without proof that the returned lineup observed exactly that policy. |
| Core API | Reports the base preset but not the hard-coded scout overlap and derived core locks. | `src/nfl_dfs/app/main.py:2871-2911` | Receipt is incomplete for the actual core-generation procedure. |
| Live generation | Accepts stack, policy environment, and optional receipt independently; the eligible pool is separately filtered by allowed IDs, salary overrides, bans, and notes. | `src/nfl_dfs/inference/live_lineups.py:521-553`, `682-713`, `867-1080` | Input-universe identity and construction identity must be joined but kept distinct. |
| Live note failure | A notes-data failure can log and continue without notes. | `src/nfl_dfs/inference/live_lineups.py:940-970` | The effective player universe may differ from configured intent unless activation is recorded or failure is policy-controlled. |
| Replay | One route calls the optimizer without a receipt; another resolves from ambient environment and changes stacking based on a contest-name substring. | `src/nfl_dfs/backtest/replay.py:1296-1313`, `1821-1869` | Historical replay can silently use a different construction policy based on invocation context. |
| Field simulation | Sharp-field generation uses bare `optimize_many`. | `src/nfl_dfs/backtest/field.py:37-76` | Rank and ROI comparisons may depend on an implicit field-construction policy even when our lineup scores do not. |
| Multiseed/CBWU | Validates roster shape and universe, rebuilds `Lineup` objects, and aggregates receipts without requiring equality or preserving candidate-level identity. | `src/nfl_dfs/inference/multiseed_portfolio.py:32-69`, `124-320` | Dynamic attributes can be lost and unexplained mixed-policy books are not rejected. |
| Foundry reference | Foundry has typed stack/constraint doses, compiled profiles, replay binding, and independent outcome audits. | `src/nfl_dfs/research/corpus_legal_feasibility.py:437-532`, `1751-1918`, `3085-3140`, `4489-4522`, `6144-6176` | This is the best existing pattern to generalize rather than inventing a parallel receipt system. |
| Population-profile reference | F7/F8/F9 explicitly define relaxed/exact constructions, inherited surfaces, source/solver bindings, and runtime audits. | `src/nfl_dfs/research/corpus_r6_population_profiles_v1.py:58-109`, `172-289`, `425-487`, `515-644`, `761-859`, `981-1039` | The repository already demonstrates the desired separation of named experimental construction and runtime validation. |

## 3. Severity-ranked findings

### P0 — a global receipt can describe a heterogeneous candidate batch

The generic backtest engine derives many candidate families with different locks, salary bands, exact stack conditions, game concentration, overlap settings, and objective floors, but stores one base construction receipt for the whole `CandidateBatch`. The validator does not require a candidate-aligned effective-policy identity.

This is the highest-severity scientific issue because it can make two candidate pools appear mechanically identical when their feasible sets differ. It also prevents reliable Neo4j first-loss analysis: a candidate can be attributed to a generation family, but the exact effective constraints that admitted or excluded it are not uniformly recoverable from the batch receipt.

Required disposition: introduce a candidate-aligned effective construction ID and make the batch validator reject missing or unknown identities for new-format runs.

### P0 — some legacy scripts named or implied a policy they did not fully instantiate

Several scripts manually construct a subset of what is now the named incumbent policy:

- `scripts/run_b1_corpus_tail_panel_producer.py:921-943` uses QB +2, bring-back +1, and the RB-vs-DST prohibition, but omits the same-team-RB prohibition.
- `scripts/run_atlas_minimal_world_selection_c.py:262-286` has the same omission.
- `scripts/run_atlas_cbc_failure_diagnostic.py:180-184`, its resource diagnostic at `352-356`, interaction parity at `151-155`, and matched-diversity MVP at `228-229` use QB +2 and bring-back +1 while omitting both RB prohibitions.
- `src/nfl_dfs/research/residual_world_columns.py:3438-3506` explicitly hard-codes the full incumbent construction while describing the model as legal-lineup construction. It is source-controlled and interpretable, but it is not DraftKings-legality-only.

This does not imply that the reported scores are false. It means the experiment must be labeled by the mechanics actually executed. Any claim specifically contrasting “full incumbent” with “legality only” needs a roster/source audit before adoption.

Required disposition: build an interpretation ledger from source pins and stored rosters. Retest only a decision-bearing contrast when its effective mechanics cannot be reconstructed or materially violate its stated estimand.

### P1 — API, live, and replay identities are reconstructed rather than observed

High-level paths commonly pass three independent objects—`stack`, a policy environment, and an optional receipt—to lower-level code. The API then adds receipt attributes after optimization, and replay has both an unreceipted direct route and an ambient-environment route. This permits configured intent and observed execution to diverge without a hard failure.

Required disposition: resolve one typed construction object once at the boundary, compile constraints only from that object plus an explicit overlay, and return the observed effective identity from the optimizer. Assert requested identity equals observed identity.

### P1 — requested rules may be silently inactive or weakened

Some requested rules are applied only when the eligible player pool supports them:

- punt constraint only when eligible punt IDs exist (`lineup.py:244-255`);
- value constraint only when enough eligible value IDs exist (`256-267`);
- ownership barbell only when ownership exists and enough players qualify (`269-287`);
- low-ownership minimum is reduced to the number available (`304-313`);
- game lock is omitted when too few eligible IDs exist (`315-319`).

In addition, `PUNT_STRICT` and `OWN_BARBELL` use raw truthiness (`247`, `275`), so a bypass caller providing the string `"0"` would activate them. The named preset adapter currently emits empty or `1`, which avoids this issue on that path, but the primitive remains unsafe for other callers.

Required disposition: every new run records requested value, eligible count, applied value, and activation status. A requested-but-unenforceable mandatory rule must fail closed; a deliberately degradable rule must record the degradation explicitly.

### P1 — “legality-only preset” is not synonymous with “pure legality-only generation” in the full engine

Even with a neutral base stack preset, the engine can add candidates using defaults such as QB variants, top/dark game families, game locks, and family-specific overlap. Examples include default QB variants at `engine.py:1967`, default game-stack families in the engine signature at `1093-1096`, and default dark-game candidates at `2117`.

Those restrictions may be legitimate held-constant generation recipes. The problem is terminology and identity: satisfying the neutral base preset does not prove absence of stricter candidate-family overlays.

Required disposition: call the base policy “DK-legality base” and separately identify every generation overlay. Reserve “pure DK-only generation” for a run whose overlay is explicitly neutral and independently audited as such.

### P2 — field and Showdown policy need separate identities

Field construction changes contest-rank and ROI evidence even when it does not change our realized lineup points. Showdown has product-specific bring-back behavior. Neither should be folded into the Classic construction identity.

Required disposition: create separate field-simulation and Showdown policy identities, or explicitly mark those surfaces out of scope for Classic receipts.

## 4. Important subtlety: a neutral `StackRules` object is not identical to no stack object

`StackRules()` is truthy, so `lineup.py:330-331` invokes the constraint-building path even when every setting is neutral. The feasible set should remain unchanged, but adding vacuous constraints can affect solver ordering or tie behavior. For exact replay, distinguish:

- no stack object supplied;
- a neutral stack object supplied and compiled;
- a non-neutral stack object supplied.

This is a reproducibility detail, not evidence of a score bias. It belongs in the runtime receipt and parity test.

## 5. Legacy evidence classification and disposition

The right response is classification, not blanket invalidation.

| Tier | Evidence standard | Interpretation | Action |
|---|---|---|---|
| A | Complete runtime-bound identity plus an independent roster audit | Strong evidence under the named mechanics | Retain. No retest solely because Policy V2 is introduced. Foundry direct parametric and F7-F9-style runs are the reference pattern. |
| B | Source-pinned and declaratively receipted, but passed as independent stack/environment/receipt values or recorded only at batch level | Valid result under reconstructable mechanics, with a receipt limitation | Add a mechanics caveat and run a stored-roster conformance audit before a decision-bearing adoption claim. |
| C | Manual partial `StackRules`, ambiguous policy label, or no runtime receipt | Score remains observable; the named-policy causal interpretation is not established | Reconstruct the exact source mechanics. Retest only if the result is still decision-bearing and the omitted rule could change the arm contrast. |
| D | Frozen or in-flight experiment using a pre-V2 contract | Governed by its frozen contract, not retroactively by V2 | Do not modify or interrupt. Seal and interpret under the frozen mechanics; version forward afterward. |

### 5.1 Construction-allocation crossing

`src/nfl_dfs/research/corpus_r6_construction_allocation_cross_v1.py` is stronger than generic engine evidence:

- cells and receipts are explicit (`101-119`, `527-536`);
- expected environment fields are validated (`539-629`);
- the native builder receives environment and receipt (`1980-2041`);
- metadata receipt equality is checked (`1777-1778`);
- selected rosters are independently audited against named preset minima (`1080-1146`, `2125-2128`).

Its limitation is directional: verifying that selected rosters satisfy a base preset does not prove that extra family-specific restrictions were absent. Therefore the crossing is valid as a test of the base construction factor with the rest of the generation recipe held constant. It should not be described as proof of unrestricted pure-DK generation. Do not rerun it unless an adoption decision specifically depends on the stronger pure-DK claim.

### 5.2 Immediate lab evidence disposition

The companion source-and-artifact audit in the lab repository is
`reports/2026-09-05-construction-law-evidence-audit.md` at commit `0b38aff`.
Its practical classification is:

| Experiment | What it actually establishes | Disposition |
|---|---|---|
| 043 | A genuine DK-only generation comparison; boom-first improved the K100 result by 6.03 points within that domain. | Retain. This is the cleanest completed evidence that boom-first supply is not dependent on the incumbent hard stack law. |
| 016 | A topology relaxation that still retained other house constraints. | Relabel as partial relaxation; do not call it DK-only and do not rerun merely for naming. |
| 062 | The house-supply result survives, but its `dk_only` row completes an already generated house candidate universe under a DK-only oracle. | Retain as `HOUSE_SUPPLY -> DK_ONLY_ORACLE_COMPLETION`; it is not evidence from DK-only generation. |
| 081 | Repeats the 062 supply/completion ambiguity, uses non-exact core completion, skips the unstacked class, and opens outcomes before its branch decision. | Do not run the current implementation. Repair the runner only if the question remains decision-bearing; otherwise prefer the clean CP-1 law ablation. |

This evidence does not justify discarding the boom-first finding or replaying
the entire historical program. It does justify refusing the shorthand
“FREE” or “DK-only” unless both candidate generation and admission were
neutral with respect to the named construction law.

## 6. Required runtime identity design

### 6.1 `ConstructionPolicyV2`: immutable base feasible-set identity

Preserve the existing named IDs and values, but represent all of the following explicitly:

- universal legality contract version and hash;
- salary cap/budget;
- roster size and positional-slot rules;
- maximum players per team;
- all eight `StackRules` fields:
  - QB stack minimum and maximum;
  - bring-back minimum and maximum;
  - forbid and require RB-vs-DST;
  - forbid and require two same-team RBs;
- minimum and maximum salary;
- minimum represented games;
- maximum players per game;
- punt threshold, minimum, and strictness;
- value threshold/minimum;
- ownership-barbell thresholds/minima;
- low-ownership threshold/minimum;
- maximum overlap.

The high-level resolver must expose all eight stack dimensions. The current behavior remains available under its existing named preset; this change is about completeness and proof, not a default change.

### 6.2 `ConstructionOverlayV1`: candidate-specific effective restrictions

Keep dynamic experiment mechanics separate from the reusable base:

- locked and banned player IDs;
- no-good roster identities and overlap relation;
- locked game and required game-player count;
- salary band and family-specific game cap;
- objective and interaction floors that restrict feasibility;
- candidate family, ordinal, and provenance;
- thesis/combo-lock identity;
- core/scout derivation identity.

The effective construction ID should hash:

1. base policy receipt;
2. overlay receipt;
3. input-universe identity.

Generation-plan, simulator, selector, and settlement identities remain separate receipts joined through the run/candidate ID. Do not collapse all research identity into one oversized construction object.

### 6.3 Activation receipt

For each conditional rule record:

- requested setting;
- relevant data/source presence;
- eligible-player count;
- applied setting;
- status: active, neutral, explicitly degraded, or failed;
- reason when degraded or failed.

This closes the gap where a receipt says a rule was requested even though the optimizer silently omitted or weakened it.

## 7. Bounded implementation map

### Phase 1 — types, compiler, and auditor; no behavior change

1. Extend the existing preset model in `optimizer/construction_presets.py` to a complete versioned base-policy representation while retaining the v1 reader.
2. Reuse the rule inventory in `research/effective_policy_rule_inventory.py`; its header correctly says it is a source contract rather than a runtime receipt (`1-11`), and its rule/environment classification (`177-440`, `1344-1477`, `1525-1756`) should remain the canonical inventory.
3. Add the overlay and activation receipt types.
4. Create one compiler from base policy plus overlay to optimizer primitives.
5. Add an independent conformance auditor that checks the returned roster and reports activated/degraded rules.
6. Keep the existing optimizer primitive temporarily for frozen research entry points, with an explicit exception ledger.

### Phase 2 — candidate-aligned engine identity

1. At every candidate-family branch in `backtest/engine.py`, derive a typed overlay.
2. Extend `CandidateBatch` to hold a candidate-aligned effective-policy ID array and a deduplicated receipt map.
3. Require `_validate_candidate_batch` to reject missing, unknown, or length-mismatched construction IDs.
4. Require candidate transforms to preserve an existing identity or emit a new valid one.
5. Preserve the exact construction identity on the returned `Lineup`; do not rely on dynamic post-hoc attributes.

### Phase 3 — API, live, replay, and multiseed migration

1. API resolves one policy object at request ingress, passes it through the optimizer, and returns the observed runtime identity. Assert requested equals observed.
2. `/lineups/core` includes explicit scout/core overlays.
3. Live generation keeps the eligible-pool/input receipt separate but joins it to the construction receipt; notes-data failure follows an explicit fail/degrade policy.
4. Replay parses environment once at CLI ingress. Replace contest-name substring behavior with an explicit versioned contest-to-policy mapping.
5. Both tail and non-tail engine routes return the observed identity.
6. Give field simulation its own explicit policy identity.
7. CBWU/multiseed preserves candidate identities when rebuilding lineup objects and rejects unexplained mixed-policy native books.

### Phase 4 — fail closed and enforce the architecture

1. Prohibit independent high-level `stack=`, free-form construction environment, and optional receipt triplets in production/API/live/replay call sites.
2. Add a static/AST check with an exception ledger for frozen research entry points.
3. Reject requested-but-unenforceable mandatory rules.
4. Permit documented degradable rules only when their activation receipt records the applied value and reason.

### Phase 5 — Foundry and future manifests

1. Add `min_games` to Foundry's `ConstraintDose`; it is currently hard-coded to one in the fresh model at `corpus_legal_feasibility.py:3138`.
2. Add the legality-contract version/hash to future Foundry manifests.
3. Do not rewrite old manifests or invalidate old runs; the v1 reader remains available for exact historical interpretation.

## 8. Bounded retest plan

### 8.1 First, reconstruct without recomputing

For each decision-relevant legacy result:

1. Resolve its exact source commit, entry point, environment, manifest, and stored roster artifacts.
2. Reconstruct the actually instantiated stack and construction settings from source.
3. Audit stored candidate and selected rosters against:
   - DraftKings legality;
   - the stated named policy;
   - the reconstructed observed policy;
   - the policy dimension suspected to be missing.
4. Count violations by arm, slate, stage, and whether the violating roster changed the selected book.
5. Reclassify the evidence into Tier A/B/C/D.

If both arms used the same reconstructable mechanics and the missing restriction has no differential incidence, retain the comparison with a corrected label. Do not spend a cloud panel merely to upgrade receipt format.

### 8.2 Retest only when all three conditions hold

A paired frozen-pool retest is warranted only when:

1. the result still affects an adoption or production decision;
2. the effective mechanics cannot be reconstructed confidently, or observed violations differ materially by arm;
3. the missing or extra rule could plausibly change the estimand rather than only its label.

Use the same frozen pools, seeds, scoring data, admission budget, selector, and read contract. Change only the construction-policy binding. Preregister the contrast before the realized read; do not inspect outcomes to decide which legacy results to rerun.

### 8.3 Minimum forward validation

Before making the new receipt mandatory:

1. exact behavior-parity test for the current incumbent preset;
2. exact behavior-parity test for the current legality-only base preset;
3. negative tests for mismatched stack, environment, overlay, and input-universe receipts;
4. family table covering base, open, single, no-stack, low-salary, QD, QB-variant, top-game, dark-game, route/coverage, and thesis candidates;
5. batch rejection tests for missing and unknown candidate identities;
6. multiseed rejection of unexplained mixed identities;
7. activation tests for empty/insufficient eligible sets and string-valued booleans;
8. one candidate-only live smoke with no scoring, entry, publication, or paid action;
9. a small exact-parity panel on frozen slates before broader adoption.

No historical full-panel rerun is required merely because the runtime receipt becomes more complete.

## 9. Acceptance criteria

The work is complete when all of the following are true:

- Every newly produced Classic candidate has exactly one immutable base policy ID, one overlay ID, one input-universe ID, and one effective construction ID.
- Every returned lineup is independently audited against the effective policy.
- Requested, applied, degraded, and inactive rules are distinguishable in the receipt.
- A heterogeneous candidate batch cannot carry only one unexplained global construction receipt.
- API, live, replay, and multiseed cannot report a requested policy as observed unless the optimizer returns the matching identity.
- Current incumbent and legality-only behavior pass exact parity tests.
- All eight stack dimensions are representable at the high-level policy boundary.
- Contest-name strings and ambient environment cannot silently choose a replay construction policy.
- Field-simulation and Showdown identities cannot be confused with Classic lineup construction.
- Frozen and in-flight experiments remain unchanged and interpretable under their original contracts.
- Legacy results have an evidence-tier and mechanics label; only decision-bearing ambiguous results enter the retest queue.

## 10. Recommended terminology

Use precise labels in reports and UI:

- **DraftKings legality:** salary/roster/position/team legality required by the contest.
- **DK-legality base policy:** the named neutral base policy, before candidate-family overlays.
- **Incumbent GPP base policy:** the current named stack, RB, salary, games, and overlap restrictions.
- **Construction overlay:** candidate-specific locks, bans, game concentration, salary bands, overlap/no-good sets, or feasibility floors.
- **Effective construction policy:** base plus overlay plus the input-universe identity and activation record.
- **Pure DK-only generation:** reserved for a neutral base and neutral overlay, independently audited.
- **Generation recipe:** candidate families and allocation; not interchangeable with construction legality.
- **Selection policy:** ranking/book selection from an already generated candidate population; kept distinct from construction.

## 11. Decision recommendation

Adopt the explicit-policy architecture prospectively, while preserving current behavior under named identities. Treat the missing runtime binding as a priority provenance defect, not as evidence that all prior scoring work is invalid. Immediately audit the few decision-bearing legacy claims that were described as full-incumbent or legality-only despite using manual/partial settings. Keep all other old evidence with accurate mechanics labels, and reserve recomputation for comparisons where the construction mismatch can actually change the decision.

The direct operational answer is therefore:

- No, the Classic core does not universally require QB/catcher/bring-back construction.
- Yes, many current production and research routes deliberately request such construction.
- No, an opponent WR specifically is not universally required; the incumbent bring-back can be RB/WR/TE.
- Yes, some older tests need relabeling or targeted audit because they manually instantiated only part of the intended law.
- No, the repository should not rerun every historical experiment.
- Yes, all future generation, selection, replay, and live evidence should carry a complete observed construction identity so this question can be answered from the artifact itself rather than by source archaeology.

## 12. Independent review and bounded repair disposition

An independent static review found no P0 defect in the behavior-preserving
base-receipt implementation. It approved the branch for focused tests once
PREREG-069 releases the workstation's sole local-compute slot, but it did not
approve deployment or a claim that candidate-level effective construction is
complete.

The review found and repaired five bounded P1 edges without changing a
construction value, generator allocation, selector, score, or production
default:

1. `build_sim_lineups` now authenticates a supplied receipt against the exact
   `StackRules` and runtime environment at function ingress, before live model
   lookup, world creation, optional persistence, or its multiseed branch. The
   engine repeats the check immediately before row-draw materialization and
   candidate solves as defense in depth.
2. A candidate batch with no supplied receipt is now labeled
   `unreceipted`; it can no longer carry the misleading
   `base-policy-only-v1` scope label. This preserves legacy/frozen callers
   while making their evidence boundary explicit.
3. The plain-MILP API identity, adopted production public identity, and core
   API response now disclose `construction_receipt_scope` consistently. The
   label remains `base-policy-only-v1`; it does not claim that locks, bans,
   core derivation, or candidate-family overlays are covered.
4. Focused negative tests now cover tail-engine failure before row-draw
   materialization, live failure before slate/world construction, and
   non-tail replay failure before optimizer entry. Receipt scope labels are
   also pinned. The generic primitive keeps an optional receipt only for
   backward compatibility; absence is observable, and Phase 4 still owns the
   exception ledger and mandatory-receipt enforcement for new production
   entry points.
5. `resolve_construction_preset_from_environment(..., use_stack=False)` now
   resets all fields from a neutral `StackRules()` object, not only the four
   historical stack fields. This prevents a future named base with nonneutral
   maximum/required relations from leaking those relations through a claimed
   stack bypass. No new ambient environment key was introduced.

Static validation after the repairs consists of successful in-memory Python
compilation of the six changed Python files and a clean `git diff --check`.
Ruff is not installed in the shared production virtual environment, so no
Ruff result is claimed. Pytest was deliberately not executed while the live
PREREG-069 census owns local compute.

The remaining hold is narrow and explicit: run the focused construction
preset tests after PREREG-069 exits, rebase onto current production `main`,
and independently inspect the rebased diff before commit. Candidate-aligned
overlay and activation identities remain Phases 2–4; until those land, call
this receipt a verified base-policy receipt, never a complete effective
construction receipt or pure-DK-generation proof.
