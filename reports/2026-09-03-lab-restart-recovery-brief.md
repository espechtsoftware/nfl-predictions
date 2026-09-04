# Lab restart recovery brief: resume 092, preserve 063, keep 091 held

**Prepared:** 2026-09-03 20:00 CDT  
**Audience:** restarted lab agent/team  
**Purpose:** reconstruct the durable state after the IDE/chat restart and identify the next executable work without repeating completed reads or launching a superseded cohort. This is a recovery summary, not a scientific amendment.

## Executive instruction

Resume from lab `origin/main` at or after `aafa548592e2f615968ef629792b76f1f6008ead`, but use the **logical update sequence**, not commit timestamp alone:

- Update 34 still holds experiment 091 before launch.
- Updates 35-37 govern the current paid-metric program.
- The immediate lab build is the licensed **092 M2 challenger plus the M0-vs-M2+NP fixed-D800 comparison**.
- PREREG-063 remains the next separate generation-side experiment. It is only a design draft and must go through its own freeze and launch contract.

The newest commit by timestamp, `aafa548`, adds a logically earlier “Update 31” routing packet. It confirms the evidence leading into KG-5, but it does **not** reverse the later D1 stop rule in Update 34 and does not authorize 091 to launch.

## Current machine and cloud state

At the 2026-09-03 20:00 CDT census:

- No active execution exists on either reusable Cloud Run lane, `lab-run` or `lab-run-slow`.
- No Cloud Build is active in either `nfl-2-506823` or `nfl-predictions-503414`.
- The last three efficacy executions were the completed 085 cohort:
  - bank 640: `lab-run-6fbzh`, 18/18 succeeded;
  - bank 641: `lab-run-slow-6gl2h`, 18/18 succeeded;
  - bank 642: `lab-run-knc7b`, 18/18 succeeded.
- The registered 085 coordinator exited successfully. Do not relaunch it.
- No heavy lab analysis process was running locally at the census. The former 060/062/N2 routing work has completed and is committed.
- Production's persistent lab-repository, action-note, Cloud Run, and Cloud Build monitors are active. They do not replace the lab's own durable handoff/monitoring process.

The lanes are therefore available, but there is no presently frozen 092 or 063 launch package that production may safely bind and execute.

## Important worktree boundary: do not integrate the dirty production checkout

The uncommitted files observed in `/home/erich/projects/nfl-predictions` are **not the lab's interrupted work and are not a prerequisite for resuming 092**. The lab should not stash, reset, fast-forward, reapply, or commit them.

That checkout is an old shared production worktree on `main`, currently behind production `origin/main`, containing several unrelated layers accumulated on different dates:

- a September 3 selection-gap review and HANDOFF entry;
- August 23 Foundry environment edits;
- an August 25 Core score-chain manual-recovery implementation and tests;
- August 29 recourse transport/root-binding work and tests;
- historical untracked review reports and generated run artifacts.

These are not one coherent change set. Applying them wholesale over current production `main` would mix unrelated research, recovery, and generated-artifact changes without review. Production will preserve and adjudicate them separately in source-age/topic groups. No part of that local checkout authorizes a lab experiment or changes the 091/092/063 disposition in this brief.

The September 3 review itself is useful but no longer an unexecuted dependency: its main routing ideas led to the already-completed 060/062/N2 packet, the D1 stop of 091, the 063 design, and the 092/D7 work. The durable lab commits and frozen contracts now supersede it operationally.

## Work already complete — do not repeat

### 085 participation-aware judging

PREREG-054/085 completed and passed on its registered proxy:

- `P_MIX`: +0.00552 proxy, all banks and all leave-one-season-out estimates positive, raw co-report +1.399.
- Selected-roster contamination fell from 21.5% to 16.3%.
- `P_ELIG` also passed but was dominated and remains diagnostic-only.
- The result improves availability integrity and the mid-tail; it did not improve the >=220/230 extreme tail.

Production independently reviewed/co-signed the amendment and owns the six-part outcome-blind live-feed certification and Week-1 shadow wiring. The lab need not rerun 085.

### Selection-gap routing packet

The 060/062/N2 packet is complete:

- 060: complementary winner-range quality exists in the D800 pool.
- 062: 13/24 frozen features survived FDR. F2 was strongest; F3 supplied the first paid-derived lineup-ranking evidence. Important signs included `designated_count` negative, route-share jump positive, and consensus divergence negative.
- N2: ambiguous but near-learnable; regret is distributed rather than dominated by one hindsight shock.

The formal packet is `reports/2026-09-04-routing-packet-and-branch-decision.md` in lab `main`.

### 091 KG-5 reranker

PREREG-061/091 was frozen, but **must remain unlaunched**. D1 subsequently fired the preregistered stop rule:

- Incremental F3 rescue recall was near zero after baseline conditioning.
- The within-slate permutation control matched or beat the real F3 features in 2022 and 2024.
- No weight search, feature search, rebuild, mechanics gate, or cloud cohort is authorized for this implementation.

`handoffs/LAUNCH-CONTRACT-091.md` carries the hold. Preserve the frozen package as evidence only.

### 092a market and paid-feature scoreboard

PREREG-064/092a is complete. Do not rerun either scoreboard.

Durable artifacts:

- `results/prereg064_metric_ledger_v1.json`
- `results/prereg064_market_scoreboard_v1.json`
- `results/prereg064_conditional_gate_v1.json`
- `PREREG-064.md`, especially the frozen gates and Package-A verdict

Market-source route:

- M1 is **closed**. Only DraftKings and FanDuel were retained; source differences were not stable, and no market recomposition beat the incumbent on the covered cohort.
- Incumbent projection MAE was 3.607, incumbent market-points MAE 3.632, and model-only MAE 3.879 on their applicable covered cohorts.
- Do not build a median-book, weighted-book, or source-selection arm for Package C.

Paid-feature route:

- M2 is **licensed** through the frozen conditional gate.
- Exactly five residual features passed FDR, all-season sign stability, and conditional partial association beyond incumbent plus market:
  - `practice_level`: +0.1357, 95% interval [+0.0545, +0.2018];
  - `salary`: -0.1605, [-0.2220, -0.1212];
  - `fp_route_share_jump`: +0.0517, [+0.0417, +0.0634];
  - `separation_l4`: +0.0493, [+0.0287, +0.0637];
  - `fp_route_share_l4`: -0.0394, [-0.0621, -0.0101].

This licenses a compact M2 residual adjustment from **exactly these five features**, walk-forward, with no weight sweep.

## Immediate lab work: finish 092b/092c

This is the clean restart point and the first priority.

### 1. Recover safely

Do not reset or overwrite either shared checkout. The existing `nfl2` worktree was observed on `codex/opportunity-lineage-v1` with unrelated untracked reports, while the production checkout has the unrelated local state described above. Fetch and use a fresh **lab** worktree/branch from current `nfl2/origin/main`. Confirm that the base includes:

- `99524d380517cd7647f44a406852af89d1cb8fd3` — M2 licensed and Update 37;
- `aafa548592e2f615968ef629792b76f1f6008ead` — completed routing packet.

If `origin/main` has advanced, read every new action-note entry and contract change before proceeding.

### 2. Implement Package B: M2

Build one compact, season-forward residual correction using only the five licensed features. Preserve the PREREG-064 definition:

- walk-forward folds only;
- no random split;
- no weight, threshold, feature, or model-family sweep;
- missing/inert feature behavior explicit and receipted;
- exact feature ordering and transformation identity frozen;
- the correction is point-in-time at the target slate;
- the incumbent forecast remains the reference to which the learned residual adjustment is applied.

Add the frozen NP negative control using the preregistered permutation boundary. If the precise permutation grain is not already explicit in the design, specify it in a preread amendment before any Package-C outcome is opened; do not improvise it after a result.

### 3. Implement Package C: fixed-D800 selection comparison

The comparison has collapsed to **M0 vs M2 plus NP**. M1 is absent because it failed licensing.

The comparison must hold the D800 candidate supply fixed so it isolates the value of the M2 belief/ranking correction. Retain:

- the registered K80 utility as primary;
- the frozen 0.95 single-contrast rule and bank/slate-block veto;
- A5 prefix co-reports at K3, K10, K20, and K57;
- the full agreed score/threshold diagnostics;
- exact shared-candidate and generation identities;
- a proof that M2 and NP engage without altering supply;
- the rule that any apparent NP improvement voids the machinery rather than supporting M2.

Do not silently substitute a different Week-1 judge, market blend, or candidate pool for the M0 identity frozen by PREREG-064. If that exact M0 identity is underspecified, request one narrow production clarification before freeze.

### 4. Reality-smoke before freeze

Run one outcome-blind smoke against the real artifacts the runner will consume before SHA pinning. It should prove at minimum:

- all five M2 inputs exist at the expected grain and are point-in-time;
- prior-season fit and target-season application are disjoint;
- the fixed D800 candidates are byte/content identical across M0, M2, and NP;
- M2 and NP both engage on a designated real boundary slate;
- all emitted receipts can be reopened and validated;
- the reader rejects wrong source, image, gate, feature-order, fold, pool, and permutation identities.

Synthetic unit tests are still required, but are not a substitute for this real-artifact smoke.

### 5. Freeze and hand production one launch package

Once implementation and the real-artifact smoke pass, commit:

- the final PREREG-064 amendment for 092b/092c;
- runner and reader;
- focused tests and launch-contract hygiene tests;
- fresh mechanics and efficacy bank/prefix assignments;
- uniform resource envelope and retry policy;
- a single-file `handoffs/LAUNCH-CONTRACT-092.md` containing source identities, required artifact SHAs, build configuration, mechanics boundary, reader pins/placeholders, arguments, and expected receipts.

Then append a numbered update to `handoffs/LAB-TO-PRODUCTION-2026-09-01-ACTION-NOTE.md` requesting the coordinated lane. Production will perform the clean-source build, bind the immutable image, run the mechanics gate, bind the reader, and launch the efficacy cohort through the registered single-writer lane.

Do not self-launch an unbound cohort merely because both Cloud Run lanes are idle.

## Next separate experiment: PREREG-063 participation-aware generation

063 remains valuable because 085 changed the judge but not candidate generation. It should remain separate from 092.

Current design-only contrast:

- `PG_CTRL`: current D800 generation selected by the sealed `P_MIX` judge.
- `PG_AWARE`: sample each designated player's P(active) before scoring, redistribute routes/targets/carries/red-zone and touchdown opportunity through the existing cascade when inactive, generate a D800 pool, and use the identical `P_MIX` judge.

Before 063 freezes, complete the already-predeclared D6 baseline census:

- solve/candidate share by P(active) band;
- affected simulated-tail candidates;
- beneficiary-player and transferred-role coverage;
- duplicate and rediscovery rates;
- descriptive removal/probability-weighting sensitivities, clearly labelled as development evidence.

The 063 efficacy sidecar must compare unique legal supply, new phenotypes, beneficiary exposure, corpus oracle and >=200/210/220/230 supply, contamination, and selected-book utility under the common P_MIX judge. Fixed solve/world budgets and fresh banks are mandatory. Do not add a factorial until this bounded comparison demonstrates engagement and value.

063 is not launchable until its design becomes a frozen preregistration with runner, reader, real-artifact mechanics smoke, fresh prefixes/banks, and its own single-file launch contract.

## Parallel work that must not delay 092

- D7/us_dfs: the fixture parser is already implemented and tested. Continue coverage, freshness, mapping, missingness, and calibration work as data arrives; do not claim market-tail value until the frozen stale/shuffle controls pass.
- Cross-verification backlog: 085, 088, 087, 084, and the new screen artifacts remain useful, but are not blockers for building 092 M2.
- Production owns the live P_MIX designation-feed certification, Week-1 P_CTRL/P_MIX shadow bindings, actual contest capture, and the A5 manifest.
- Registry v2 and winner-authority adjudication do not block the fixed-corpus 092 or 063 development comparisons.

## Guardrails and stop conditions

- Keep 091 held. The late-timestamped Update-31 commit is not a reopening event.
- Do not rerun 085, 060, 062, N2, or 092a.
- Do not revive M1 or tune market-source weights.
- Do not broaden M2 beyond the five licensed features.
- Do not tune M2 after reading its fixed-D800 result.
- Do not mix 092's selection estimand with 063's generation estimand.
- Use exact content identities, clean committed source, one real-artifact smoke, a uniform compute envelope, and the registered single-writer cloud lane.
- Historical results remain development evidence. Live adoption authority remains prospective, pre-lock frozen shadow/entry settlement.

## Definition of the next successful handoff

The lab is back on track when production receives one of these, preferably 092 first:

1. A committed and pushed `LAUNCH-CONTRACT-092.md` for the frozen M0-vs-M2+NP fixed-D800 comparison, with a passed real-artifact mechanics smoke and all bind-at-launch identities explicit; or
2. A separately committed and pushed frozen PREREG-063 package with its D6 census and complete launch contract.

Until then, idle Cloud Run lanes reflect the absence of a valid frozen launch package, not an execution failure.

## Authoritative recovery references

Read in this order:

1. `PREREG-064.md`
2. `results/prereg064_metric_ledger_v1.json`
3. `results/prereg064_market_scoreboard_v1.json`
4. `results/prereg064_conditional_gate_v1.json`
5. `handoffs/LAB-TO-PRODUCTION-2026-09-01-ACTION-NOTE.md`, Updates 34-37
6. `handoffs/LAUNCH-CONTRACT-091.md` — hold banner only; do not launch
7. `PREREG-063-DESIGN.md`
8. `handoffs/PRODUCTION-TO-LAB-SCORE-GAIN-DIAGNOSTICS-PLAN-2026-09-03.md`, especially D6/D7
9. `reports/2026-09-04-routing-packet-and-branch-decision.md`
