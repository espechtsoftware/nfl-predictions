# Paid data: current use, evidence, opportunities, and renewal decisions

**Prepared September 18, 2026 for Erich.** Review of `nfl-predictions` at `2b6ed3bd` and the Sunday live-builder branch in `nfl2` at `e7255e98`. Documentation and read-only inspection only; no models, lineups, experiments, subscriptions, or schedules changed.

> **Follow-up, September 18:** Erich authorized the staged experiments. The [first-stage results](2026-09-18-paid-source-experiment-preflight-results.md) verify actual registered feature contracts and show that the SIS/Route shadow schedulers are paused. SIS becomes eligible from Week 5; it is not an already-running study ending in Week 5. Renewal recommendations here do not cancel the newly authorized research.

## Recommendation

**Keep The Odds API for the NFL season. Do not renew SIS automatically for the current application. Use the remaining Fantasy Points subscription, but do not commit to its next renewal solely on the current app's performance.** A short research extension is a separate decision, justified only by a specific experiment with an owner, budget, and stop date.

The statement “SIS and Fantasy Points don't affect scores or selections” needs qualification:

- **Current entered Sunday lineups:** I found no adopted direct SIS or licensed Fantasy Points feature in the reviewed decision path. The source code, deployed model-job configuration, and handoffs support that conclusion. Downloading their data does not mean the money-lineup model uses it.
- **Historical experiments and separate shadows:** both sources absolutely have changed predictions, simulation dependence, admissions, or lineup membership. Some narrow experiments passed their rules. Most did not establish a dependable improvement in the selected book.
- **Actual fantasy scores:** no source changes what players score. The relevant question is whether it improves our predictions and decisions. “No measured improvement” and “not consumed” are different findings.

The recommendation against an automatic renewal is a spending decision under limited evidence, **not a conclusion that either vendor's entire dataset is useless or exhausted**.

| Source | Current Sunday decision use | Strongest established case | Renewal recommendation |
|---|---|---|---|
| The Odds API | Player props feed the market projection, normally 55% of the blended mean for covered players; the live builder centers worlds on these production projections | Active operational dependency, useful market information, historical blend evidence | Keep in season; choose the smallest plan covering measured live usage and reserve |
| Fantasy Points Data Suite | Route data reaches feature tables, but its four licensed route features are optional research features; separate route registries/shadows exist | Useful proprietary participation/alignment information; historical research influence, but no robust adopted lineup benefit | Use paid-through access; no next-term renewal solely for today's model; consider only a bounded new-information study |
| SIS NFL DataHub | Separate research/shadow paths; no direct SIS input found in canonical production feature SQL or adopted money policy | Selected finite-usage pass-tail and joint alignment-allocation research; weak retrieval finish signal | Do not renew the recurring research subscription without an explicit next experiment needing fresh SIS data |

## What I verified, and what remains uncertain

I traced ingestion, feature SQL, model feature contracts, projection blending, simulation centering, research consumers, Sunday tooling, deployment declarations, and current Cloud Run job configurations. I reviewed the operating handoff, project briefing, historical study ledger, vendor-specific reviews and their corrections, direct paid-source experiment reports and machine dispositions, and the lab's licensed-data authority handoff.

The [deployed configuration extract](reviews/evidence/2026-09-18-paid-source-deployed-job-config.json) records selected nonsecret fields for six jobs. `project-slate` uses `tail_k1`, ensemble 1, blend model weight 0.45. `train-weekly-k1` has no `EXTRA_FEATURES`; its role sibling adds ordinary usage features. The route sibling explicitly uses `tail_k1_route` and the four `fp_route_*` features. The SIS job is explicitly `shadow-sis-pass-tail-paired`. These are separate model/consumer identities.

A job existing is not proof it has run successfully this week. I did not download serialized production models, audit every historical execution, rerun expensive outcome experiments, open 990/991 outcomes, or authenticate into billing accounts. Therefore this is strong source/configuration evidence for current wiring, not a fresh measured “vendor off changes exactly zero bytes” replay of Sunday's final artifact. That final audit is specified below. Actual invoices, renewal dates, discounts and plan entitlements remain account-specific.

## 1. The Odds API

### How it enters the application

The project uses **the-odds-api.com**, not the similarly named domain without hyphens.

1. [`oddsapi_import.py`](../src/nfl_dfs/ingest/oddsapi_import.py) collects historical/live player props into `nfl_raw.prop_lines`: passing yards and TDs, rushing yards, receiving yards, receptions, anytime TD. Historical imports use DraftKings/FanDuel and event-relative snapshots; downstream consumers enforce a common Sunday-main cutoff.
2. [`prop_market.py`](../src/nfl_dfs/models/prop_market.py) pairs over/under prices, removes two-way vig, converts lines to component means, maps names to player IDs, and sums DK-scoring components. Anytime TD uses a one-sided hold assumption and a Poisson conversion. It is an estimated fantasy-point proxy, not a complete vendor fantasy projection.
3. [`run_projections.py`](../src/nfl_dfs/inference/run_projections.py) asks for at least two markets per player and uses a 30% slate coverage gate. Above that gate, players with props use them; others retain DK points-per-game where available. Below it, the entire market vector remains DK PPG. Exceptions also fall back.
4. [`blend.py`](../src/nfl_dfs/models/blend.py) combines **45% model + 55% market** where a market value exists. Where both prop and PPG market proxies are missing, it falls back to the model. This is not a 55% prop contribution for every player.
5. The current lab live builder, [`live_week.py` at e7255e98](https://github.com/espechtsoftware/nfl2/blob/e7255e98bf87297452befb61fb508ad4b368b59f/scripts/live_week.py), with `NFL2_LIVE_CENTER=production`, loads the newest production projection batch and centers generation/selection worlds on those means. It does not blend them a second time. Consequently props can change generated candidates, the selected book, and its ordering even though the selector does not query Odds API directly.

There are additional consumers, but their status matters:

- Alternate-line quantiles in [`market_implied.py`](../src/nfl_dfs/inference/market_implied.py) support the market-tail/watchlist endpoint. The module explicitly describes them as diagnostic rather than a silently adopted feature.
- [`week1_market_move.py`](../scripts/week1_market_move.py) and spreadsheet tooling report movement and vanished-line flags. An output labeled “veto candidate” is not authority to remove a player absent the project's actual status rules.
- Extra attempts/completions/interceptions/combined markets are collected into `prop_lines_shadow`; `us_dfs` has a separate collection. Collection is not proof of model use.
- [`odds_job.py`](../src/nfl_dfs/ingest/odds_job.py) records game spreads/totals/moneylines in `odds_snapshots`; `odds_movement` and the market UI consume that history. **The canonical game-environment feature SQL currently derives totals and spreads from `raw.schedules`, through `012_schedule_long.sql` and `016_team_week_context.sql`.** I did not find a canonical feature join replacing those values with the paid game-odds snapshots. Do not attribute every “Vegas” input to this subscription.

### Value evidence and limitations

[System-study Addendum 14](2026-07-25-system-study.md) reported better 2025 player MAE for the blend (4.664 versus 4.909 model-only and 4.786 market-only) and a favorable selected-book comparison on that earlier stack. Those are historical development results, not a current guarantee.

**The later Addendum 106 must accompany that headline:** a purpose-built model-only deletion was mechanically valid but `unsupported-neutral`. Mean selected best fell 173.06 to 172.14; some thresholds improved and others worsened; neither direction passed its strong-support rule. The blend remained the operational default without strong causal proof of present tournament return. This tempers, but does not reverse, the keep recommendation.

The Week-2 operating handoff documents a concrete operational failure: sparse props triggered DK-PPG fallback, making the next week's projections closely echo the prior week's scores. Refreshing after the props pull corrected the source and reduced the extreme projection inflation. That demonstrates a material consumer and a dangerous fallback, not a controlled estimate of subscription ROI.

### Fixes and higher-value uses to investigate

**First, improve the data already purchased.**

- **Coherent snapshots:** the current production and lab latest-row keys include `point`. When a standard line moves, an old point can survive beside the new one. Over/under sides can also come from different observations. This was flagged in the earlier transition review. Select the latest coherent bookmaker/event/market snapshot first, then retain its actual ladder. Distinguish a real alternate ladder from a sequence of obsolete main lines.
- **Completeness by position/component:** two markets do not necessarily constitute a complete QB/RB/WR expectation. Missing reception, passing-TD, bonus, turnover or other scoring components need explicit treatment; absence must not become a true zero. Report actual market composition, not just market count.
- **Accurate lineage logging:** the `market blend source: props` log currently counts all finite market-vector rows, including fallback PPG rows. The true prop mask already exists. Log props, PPG and model-only counts separately, alongside age and cutoff.
- **Fallback continuity:** the 30% gate can switch many players at once when coverage crosses a boundary. Test a position-aware, explicitly labeled fallback under an approved change; do not just delete the gate on Sunday.
- **Production/lab parity:** the lab fallback uses a different main-line conversion and anytime-TD hold adjustment from production. Current production centering reduces exposure for matched players, but unmatched rows still require an explicit parity contract.
- **Fresh information:** compare the same book-building policy on early versus late, prelock-coherent snapshots. Separate news/market updates from changes in solve dose or selector. This is more credible than repeatedly fitting another blend weight on the old panel.
- **Distribution information:** attempts and receptions may constrain opportunity more directly than point means; coherent alternate ladders may inform uncertainty. Test one frozen role/volume extension only after provenance and coverage pass. Market marginals alone do not identify teammate correlations.

## 2. Fantasy Points

### Acquisition is considerably broader than production consumption

The app has browser-assisted collection/imports for weekly Route Share, prior-season Advanced/coverage reports, exact-window same-season reports, alignment data, and prospective live matchup reports. Current weekly orchestration collects the prior completed week's Route Share from Week 2, and alignment windows from Week 5. Week-2 capture reportedly imported **265 Week-1 route rows** and captured three live matchup CSVs; this is recorded in operating-handoff defect 28.

The trace for Route Share is:

`fantasy_points_route_share → 017k_fantasy_points_route.sql → player_week_training / player_week_inference → OPTIONAL model features`.

The final arrow is the important one. In [`featureset.py`](../src/nfl_dfs/models/featureset.py), `fp_route_share_last`, `fp_route_share_l4`, `fp_route_share_jump`, and `fp_route_cross_season` are in `CANDIDATE_FEATURES`, excluded unless requested through `EXTRA_FEATURES`. Canonical [`tabpfn_gen/features.txt`](../scripts/tabpfn_gen/features.txt) also omits them. Deployed route jobs use their own registry. A feature table containing a column does not establish prediction influence.

Likewise, a locally computed feature named `xfp_l4` is built from play-by-play in `017j_xfp_schedule.sql`; its Fantasy Points conceptual lineage does not make it a licensed-feed dependency.

**Ownership is a separate product/consumer.** A collector writes `fantasy_points_projected_ownership`, but the briefing says the ownership product is outside the operator's Data Suite plan and handoffs record unavailable/empty ownership values. I found the collector, not an adopted canonical ownership-model consumer of that table. Do not renew Data Suite on the assumption that it supplies usable DFS ownership or vendor projections. Verify the actual entitlement and populated fields first.

### The historical record is more extensive than “we forgot to use routes”

| Test/use | Recorded result | What it establishes |
|---|---|---|
| Initial weekly Route player-tail test | Small favorable 20/30-point calibration; residual mean MAE worsened | Some signal in that auxiliary test, not a production mean fix |
| Route component/final-served test | Final Brier and quantiles identical after shared TabPFN remapping | An upstream route effect was erased in the marginal channel; rank dependence could still differ |
| **Later direct Route-in-TabPFN test** | Tail pinball ratio 1.009900, zero of three positions improving | Moving the same four features into the surviving marginal channel was already tried and failed its tail gate |
| Route rank and midpoint-shrinkage tests | Failed; shrinkage dependence-loss ratio 2.073476 | These exact dependence constructions were not successful |
| Prior Advanced, same-season passing, route shape, same-season coverage, Defense PROE, QB shell | Recorded failures under their respective gates | Several apparently obvious suggestions are already tested; not all failures share the same cause |
| FP×SIS retrieval ablation, September 15 | Large membership change, no positive FP co-primary | FP was consumed in that retrieval pipeline but did not earn adoption |

The [machine disposition index](reviews/evidence/2026-09-18-fantasy-points-disposition-index.json), [final-served Route report](2026-08-11-route-share-final-served-result.md), [mechanism-queue verification](2026-08-14-mechanism-queue-verification.md), and HANDOFF's Route-channel completion record substantiate these distinctions.

Earlier documents recommended Defense PROE and direct Route modeling; later reports show those tests happened. I would not propose them again as untried. Similarly, an early claim that Advanced reports were necessarily stale was corrected when the vendor's week filters were verified: selected-window exports can produce strictly prior same-season data.

### What might still earn additional value

The most plausible remaining question is **new role information after a change**, rather than another generic four-week Route feature bundle. A recent injury, new starter, personnel change, or returning player may make past targets a poor measure of next week's opportunity. Route participation, routes on pass plays, first-read opportunities and red-zone routes could help estimate that change if those exact fields are available and timely.

That remains a hypothesis. First prove novelty against existing snap/target shares, depth charts, injury states, prices and props. The 2026 prospective design must define the change cohort before games and use the full eligible cohort, not select examples after a breakout. The treatment must reach the final conditional opportunity/distribution model; another erased component tweak is not useful.

A fresh product audit is also justified: the vendor's [Data Suite 2.0 change log](https://fantasypointsdata.com/whats-new) documents a changing surface. That is a reason to verify available fields/export semantics, not evidence that new UI features improve this model. No bulk collection or new product purchase is warranted before a specific field/support census.

## 3. SIS

### What is used

SIS DataHub supplies charted team context, pass/run-defense characteristics, blocking information, alignment-attempt composition, and acquired player/defender data used in dedicated research consumers. The reviewed canonical production feature SQL has no direct `sis_*` table reference. The adopted policy does not enable the SIS allocation flag or substitute the SIS marginal cache.

There are nevertheless real SIS consumers:

- **Pass-tail:** prior opponent defensive Boom%, Bust%, and pass-rush pressure enter an isolated TabPFN treatment; paired prospective cache and book machinery exists.
- **ASOE alignment allocation:** Fantasy Points offensive alignment and SIS defensive attempt composition jointly alter within-team target allocation/rank structure. This is a joint information product; do not attribute its effect entirely to SIS.
- **Matchup retrieval:** component construction converts FP/SIS inputs into player matchup scores, eligibility/support, and candidate admission order; a fixed simulator then selects lineups.
- **Receiver copula:** a separate defender/alignment-conditioned dependence treatment was built and calibrated, but could not pass its required-support gate.

The Week-5 start of the current SIS weekly pass-tail acquisition is deliberate: it needs four completed prior weeks. Missing Week-2 current-season SIS rows do not prove a failed download. It also does not imply the Week-2 money build receives a SIS benefit.

### Evidence worth preserving

| Mechanism | Result | Renewal implication |
|---|---|---|
| QB offensive-line marginal bundle | Better central metrics, failed 30-point gate | Weak case for that exact use |
| RB run-defense / run-tail bundles | Failed; run-tail worsened registered upper-tail metrics | Do not repeat merely because the fields sound relevant to upside |
| SIS pass-tail final-served | Passed; pinball ratio 0.995032, mostly QB improvement | Genuine narrow positive distributional evidence |
| Pass-tail five-seed exact-80 | Selected under the frozen tail-first rule: ≥220 seed-weeks 3→5; mean maximum −0.421 | Gains concentrated in two distinct improving slates; finite-usage research, not current-money proof |
| Joint FP/SIS ASOE | Selected finite-usage research: ≥210 seed-weeks 14→16; mean maximum +0.352 | A second positive mechanism; no automatic transfer into the K=1 money law |
| Receiver-copula calibration | Invalid/inconclusive because required calibration support absent | Not evidence that the mechanism was harmful; do not call it a tested negative |
| September retrieval | SIS K20 simulated-field finish contrast passed; points/K40/K80 did not establish value | Weak, narrow signal suitable only for further evidence |

See [pass-tail exact-80](2026-08-14-sis-pass-tail-exact80-result.md), [pass-tail calibration](2026-08-13-sis-pass-tail-final-served-result.md), [ASOE reconciliation](2026-08-15-external-reviewer-briefing-review-reconciliation.md), and [receiver-copula support failure](2026-08-15-sis-receiver-copula-calibration-result.md).

Some older reviews call SIS allocation “already in production.” The later reconciliation explicitly corrects that: it was selected in the **finite-K research baseline**, not the separate K=1 money policy. This distinction is supported by the current policy/configuration trace.

### Remaining research opportunity

Receiver-specific conditional allocation remains more plausible than another broad team-average quality bonus, but it is not a brand-new idea: it was attempted and encountered support limitations. A successor would need a genuinely supportable population/design, documented shrinkage, current defender availability, and a prospective test. It must not simply lower the old failed gate or pick the best old calibration strength.

Alignment crossing is probabilistic matchup context, **not a known named cornerback-to-receiver assignment**. Do not market or model it as shadow coverage unless such assignments are actually acquired. Preserve team opportunity totals when redistributing targets, and measure QB–receiver, receiver–receiver and opponent dependence separately.

At SIS's recurring cost, I would not keep paying indefinitely for this possibility. Require an outcome-free support census and a scheduled experiment before buying an extension.

## 4. What the September vendor experiments do—and do not—say

The [September 15 influence ladder](2026-09-15-paid-source-influence-ladder-direct.md) tested four FP/SIS cells on 54 historical slates. Candidate rosters and 40,000-world score matrices were fixed. Vendor slices were removed before constructing components; top-200 matchup admission was followed by coverage-at-194 selection.

**Wiring worked in that pipeline:** FP removal yielded K80 Jaccard 0.131 versus all-on; SIS removal yielded 0.260. Those are large lineup membership changes. They do not establish that those same consumers run in today's Sunday build.

At K20, FP's points contrast was +0.64 with interval [−3.71,+5.44]; SIS's was +1.20 [−1.13,+4.00]. SIS's simulated-field best-finish contrast was +0.0191 [+0.0030,+0.0399], passing the frozen rule, but based on three season clusters, a 24/14 win/loss split, and no corresponding K40/K80 effect. It was not observed contest profit. The historical field used real ownership information; that is not a deployable prelock ownership forecast.

The [admission-cap follow-up](2026-09-15-admission-cap-lever-result.md) expanded admission without establishing a primary improvement. Its source-on/off contrast at `capall` remained inconclusive. **However, `capall` did not mean the identical full pool for both source states:** source-dependent qualification admitted about 3,317 candidates with both sources and 951 without. The report discloses this. It is a bundled support/admission contrast, not a pure common-pool scoring comparison.

Neither experiment retrained the terminal player distribution with vendor data or allowed vendor-informed candidate generation. A null cannot close those untested consumers. Conversely, a hypothetical generator benefit cannot rescue a failed retrieval result. The experiments lower the renewal case for the tested use; they do not establish that all remaining regret is recoverable, that the vendor has no information, or that a particular tail-calibration repair must succeed.

## 5. Operational issues affecting value

| Issue | Consequence | Recommended action |
|---|---|---|
| Both vendor sessions checked even when SIS is not needed | An expired SIS session blocked Week-2 FP capture | Decouple required-session checks by scheduled steps; retain strict checks for steps actually run |
| Warehouse presence confused with active model use | Paid inputs appear important in handoffs despite being excluded by feature contracts | Publish a per-build source/consumer receipt |
| Legacy research-policy wording | Finite-K ASOE/pass-tail selection misread as money deployment | Label adopted, research baseline, shadow, failed and untestable explicitly |
| Current-year/window-specific collectors | A collector existing does not ensure correct next-season or earliest-week behavior | Validate source season, window, capture time, source publication time where available, and lock cutoff |
| Historical vendor data reconstructed later | Week cutoff alone does not establish what revisions were knowable on that date | Preserve prospective captures and label historical publication-time uncertainty |
| Source-dependent missingness/qualification | Removing a vendor can change population as well as information | Report full-system and common-eligible-population effects separately |
| SIS caps, identity and rate limits | Incomplete exports or ambiguous joins can dilute signal before modeling | Retain cap detection, stable-ID sidecars, denominator/support checks and bounded request plans |

These are proposed changes, not fixes made during this review. Collection and archives have research value, but rows accumulated are not a performance metric.

## 6. The next experiments I recommend

Run these sequentially as capacity permits; this does not displace the agreed known-law E0 work or authorize a launch.

### A. Current-build source influence audit — first, no outcomes

Freeze one existing coming-week input snapshot, exact model/cache identities, current live builder and seed set. Trace source observations through final means, quantiles, dependence, candidate membership, selected membership and first-K order.

For Odds API, distinguish removing the prop contribution from replacing it with PPG; those answer different questions. For FP/SIS, show whether disabling their direct consumers is genuinely inert in the adopted path. An unchanged upstream SQL column is insufficient; inspect serialized feature names and cache lineage. Keep separate shadows separate. Do not consume credit-heavy new vendor pulls for this audit.

**Deliverable:** a small source-impact table attached to each build. If FP/SIS money outputs are unchanged, that confirms the integration conclusion, not information worthlessness.

### B. Odds feed integrity and freshness — highest operational priority

First test moved-line and mismatched-side fixtures, partial market coverage and the gate boundary. Then freeze one corrected market-proxy implementation, compare it to the current implementation on coherent retained snapshots, and record coverage, age, projection changes and forecast calibration. Pair early/late prelock snapshots under the same solver budget and selector. Keep simulated optimization gain separate from realized improvement.

**Stop rule:** no broad tail-feature or blend-weight search until the input invariants pass. Fresh 2026 paired books are the confirmation source; old panels are development.

### C. FP role-change information — bounded novelty test before a model

Audit exact available participation/red-zone/first-read fields on a predeclared set of all eligible role changes. Quantify missingness, time-to-availability, agreement with existing sources, and novelty conditional on props and injury/usage inputs. If there is no timely incremental information, stop without a new model.

If support passes, freeze one conditional opportunity treatment that conserves team opportunity and reaches the final served law. Compare to the current role model at equal compute. Evaluate opportunity/count calibration first, then paired candidate supply and prefix/book performance. Do not rerun the already-failed four-feature Route cache or rank-shrinkage arms under a new name.

### D. SIS value decision — support and transfer before renewal

Choose **one** path: verify whether the existing pass-tail/ASOE prospective shadow is producing valid paired artifacts, or design a supported successor to the receiver-allocation study. Verify that it addresses the current simulator rather than a different finite-K baseline. Do not fund both by default.

For a successor, document how its information set or representation differs from the completed tests; census the smallest calibration cells before any effect read. If no supportable, affordable experiment exists before renewal, stop paying for fresh SIS access.

For all outcome studies, predeclare one primary prefix/objective, report K1/K10/K20/K40/K80 diagnostics and 220+ events, use independent selection/audit worlds, report all banks and seasons, and retain paired slate/season uncertainty. A few favorable seed-weeks are not independent Sunday replications. Field-rank and payout claims require actual contest/ownership/tie/duplication assumptions, not just a fixed score threshold.

## 7. Renewal economics and decision triggers

Public prices checked September 18, 2026; **these are not verified charges to Erich's account**.

| Product | Public reference | Decision |
|---|---|---|
| The Odds API | $30/month for 20,000 credits; $59/month for 100,000; historical odds included on paid plans | Keep; use request-audit/remaining-credit telemetry to pick the plan. Historical backfills and live consumption have different costs. Avoid speculative upgrades |
| Fantasy Points Data Suite | Vendor's 2026 announcement lists $200 regular price; its $160 early-bird offer is historical, not a current quote | Use existing access. Decide next renewal after prospective evidence or a specifically funded new-information study |
| SIS NFL DataHub | Official store search extract lists $99.99/month or $749.99/year; direct store fetch timed out | No automatic monthly/annual renewal for today's app. An annual commitment is not justified by the present evidence |

Sources: [Odds API pricing](https://the-odds-api.com/), [Fantasy Points 2026 announcement](https://newsletter.fantasypoints.com/p/early-bird-discount-2026), [SIS official store](https://store.sportsinfosolutions.com/). SIS projections are a separate product; the lower projection price is not the DataHub price. Fantasy Points [subscription guidance](https://support.fantasypoints.com/hc/en-us/articles/360042163112-When-does-my-subscription-expire) describes seasonal expiration the following March 31; verify the account rather than assuming access ends one year after purchase.

The application-value break-even is:

`expected incremental net contest return + value assigned to research/personal use > subscription + incremental compute + maintenance time`.

We do not currently have a defensible dollar estimate for FP/SIS incremental contest return. Do not convert a 1.9-percentile-point research finish result into dollars without the actual payout/duplication model. Likewise, the value of an Odds API dependency is not established by the arbitrary number of lines of code consuming it.

**My concrete decision if renewal were due today:** retain Odds API; decline SIS renewal for this app; decline a new FP term solely for this app, while using already-paid access and preserving the option of a bounded research purchase. FP has a lower carrying cost and potentially useful role information; SIS requires a stronger near-term case at its recurring price. If Erich values either product independently for manual research, that is legitimate additional utility, separate from automated lineup performance.

Before stopping a feed operationally, make a small dependency plan: keep lawful retained archives, identify shadow jobs/import checks that expect live access, and label unavailable sources explicitly. Do not allow cancellation to cause silent stale-data fallback or block unrelated collection. No subscription changes were made here.

## Evidence map

- Current consumer contracts: `src/nfl_dfs/models/featureset.py`, `components.py`, `blend.py`, `prop_market.py`; `inference/run_projections.py`, `production_policy.py`, `live_lineups.py`; `scripts/tabpfn_gen/{gen.py,features.txt}`; `deploy/deploy_jobs.sh`.
- Acquisition: `ingest/oddsapi_import.py`, `odds_job.py`; `ops/weekly_vendor_data.py`, `fantasy_points_downloads.py`, `fantasy_points_matchups.py`, `fantasy_points_ownership.py`, `sis_downloads.py`; weekly import modules and `sql/features/017k_fantasy_points_route.sql`.
- Current operations: [Week-2 handoff](2026-09-15-week2-operating-handoff.md), especially defects 25/27/28 and Wednesday capture; [new-model briefing](2026-09-14-project-briefing-for-a-new-model.md); production `HANDOFF.md` corrections and source-v3 history.
- FP historical corrections: [utilization reconciliation](2026-08-11-fantasy-points-utilization-reconciliation.md), [redundancy audit](2026-08-11-fantasy-points-redundancy-audit.md), [mechanism queue](2026-08-14-mechanism-queue-verification.md), machine disposition index linked above. Early “still untested” recommendations are superseded where later runs exist.
- SIS history: [plan-gap reconciliation](2026-08-13-sis-plan-coverage-gap-reconciliation.md), [QB line result](2026-08-13-sis-qb-line-final-served-result.md), [run-tail review](2026-08-14-sis-run-tail-result-review.md), pass-tail/ASOE/copula reports linked above. Broad closure rhetoric is not adopted as a scientific finding.
- Retrieval evidence: `scripts/paid_source_ladder_direct_v1.py`, `paid_source_admission_cap_v1.py`, `research/corpus_r6_paid_source_ablation_v1.py`; [ladder report](2026-09-15-paid-source-influence-ladder-direct.md), [cap report](2026-09-15-admission-cap-lever-result.md), their committed manifests/read tables/transcripts.
- Lab handoff: `handoffs/LAB-TO-PRODUCTION-2026-09-01-ACTION-NOTE.md`, Update 285 licensed-data authority census; current production handoff documents the later Week-3/Week-4 boundary resolution.

Historical numeric results above are attributed to existing reports, not presented as newly rerun independent experiments. This review proposes a narrower, testable plan rather than claiming all remaining data value has been found.
