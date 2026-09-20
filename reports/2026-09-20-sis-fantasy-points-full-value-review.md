# SIS and Fantasy Points: full data-surface and coverage-value review

**Date:** 2026-09-20  
**Scope:** repository code, acquisition plans, handoffs, outcome-blind audits, completed historical diagnostics, and the paid-source ladder. No new vendor requests, production changes, or current-week outcome reads were made for this review.

## Executive finding

SIS and Fantasy Points are not useless, but the project has mostly tested them as **small marginal feature blocks or mean-edge retrieval annotations**. That is a poor match for several of the strongest fields these vendors provide.

The evidence supports four conclusions:

1. **Fantasy Points Route Share has real signal**, especially for tight ends and mid-priced WR/TE players. It is highly correlated with snap share for WRs, but it captures route participation that snaps miss for TEs. The live 2026 weekly route-share path is the clearest immediate value.
2. **Fantasy Points coverage data has been tested against performance**, but the tested aggregates were weak or failed. Prior-season receiver Man/Zone and shell-fit features produced a tiny, unstable improvement; same-season last-four coverage failed its support and Brier gates; QB shell-fit failed its tail gate. This does not test individual defender coverage, route-level matchup, red-zone route participation, or combined coverage-plus-role states.
3. **SIS team context has been tested mostly as lagged averages**, where broad pass-defense EPA is redundant and QB/RB marginal arms failed their tail gates. SIS pass-defense tail fields showed a modest historical 220+ effect, but only on a narrow finite-K historical panel; the live shadow is still required. SIS player/defender-grain coverage and alignment data have not received a valid predictive test. The receiver-copula attempt was untestable because its calibration cells had insufficient support, not because the underlying data was proven worthless.
4. **The biggest demonstrated loss is retrieval, not source quality.** In the 54-slate paid-source ladder, turning sources on/off changed hundreds of component values and replaced most selected rows, yet all cells admitted a ceiling around 181 while the candidate pool contained 202.7. Mean-edge admission discarded the extreme tail regardless of vendor. The next value test must therefore combine source features with a tail-aware admission/selection test.

The right decision is to keep the subscriptions long enough to run a properly wired incremental shadow, with special emphasis on route participation, coverage/role interactions, and SIS player-level coverage. Do not renew indefinitely on faith, but do not cancel based on the current marginal tests.

## What each source actually offers

### Fantasy Points

The audited Data Suite exposes substantially more than the four fields currently visible in the live model:

| Family | Available information | Repository status and assessment |
|---|---|---|
| Weekly usage | Fantasy points, snap share, route share, target share, offensive/defensive PROE | Route share is captured weekly and is non-redundant; snap/target/PROE are largely redundant with existing PBP features. Weekly coverage is not offered by this menu. |
| Advanced receiving | TPRR, aDOT, air-yard share, YPRR, first-read rate, expected fantasy points per route | Historical prior-season and same-season support paths exist. Broad advanced receiving diagnostics were mixed/failed; these metrics have not been tested as a role-conditioned tail model. |
| Advanced rushing | i5 rate, missed tackles forced per attempt, yards after contact per attempt, stuff rate | Imported historically, but no convincing prospective tail test has established value. |
| Advanced passing | CPOE, aDOT, deep-throw rate, time-to-throw, pressure-to-sack rate, checkdown/RPO and related last-four fields | Last-four passing table and importer exist. It is not a live production feature path; a strict walk-forward gate is still required. |
| Receiver coverage | Man/Zone TPRR, YPRR, FP/RR, separation; Cover 2/3/4/6 separation and shell rates | Tested as prior-season matchup edges (weak/unstable) and same-season last-four (failed support and Brier gates). |
| QB shell matrix | Offense by Man/Zone and one-high/two-high shell with fantasy points per dropback; Cover 0/1/2/3/4/6 rates | Tested and failed the registered aggregate 30-point Brier gate. |
| Receiver alignment | Wide, slot, inline, backfield route counts and shares | Imported in a prior-window table; not tested as an interaction with role, opponent shell, or concentration. |
| Route shape | Horizontal, vertical, static, shallow/underneath, backfield route shares | Imported in a last-four table; no decision-bearing tail test has established value. |
| Defense coverage matrix | Team shell deployment and FP/dropback allowed by shell | Used for QB shell-fit and receiver coverage joins; aggregate shell results failed. |
| Advanced support fields | Red-zone route participation exists in the Separation-by-Coverage export; weekly target/carry red-zone data exists internally | Red-zone route participation is not currently in the feature path and is a promising, distinct touchdown-ceiling hypothesis. |
| Live matchup reports | WR, OL/DL and QB matchup reports, plus other matchup annotations | Week 1 files were archived, but there is no BigQuery load or production feature join. They currently cannot affect scores or selection. |
| Ownership | Projected ownership from a separate Fantasy Points website session | Collector is not yet a complete frozen 2026 input; ownership is a contest/duplication feature, not a player-score feature. |

### SIS

The audited SIS NFL subscription exposes player and team leaderboards with game splits, week ranges, opponent, alignment, route, depth, coverage shell, pressure, motion, formation, situation, and other filters. The broad report families are:

| Family | Available information | Repository status and assessment |
|---|---|---|
| Passing totals/value | Dropbacks, attempts, completions, catchable/on-target, gross/net yards, air yards, intended air yards, TD/INT, sacks, pressures; Points Earned/PAA/EPA/PAR/WAR, boom/bust | Team totals/value are ingested. Team lagged QB-line arm failed its tail gate. Player passing is not in the live feature path. |
| Receiving totals/value | Routes, targets/quality, air yards, YAC/contact, DPI, YPRR, aDOT/aDOC, receiver rating, Points Earned/PAA/EPA/PAR/WAR, boom/bust | Catalogued as high priority; broad team receiving tranche is not yet a tested production feature. Player receiver splits are not yet used in a validated tail model. |
| Rushing totals/value | Attempts, yards after contact, broken/missed tackles, hit at line, stuffs, designed gap, EPA/PAA/PAR/WAR, boom/bust | Team run context is ingested. RB opponent run-tail arm failed proper tail-score gates. Granular gap/box/scheme interactions remain untested. |
| Pass defense totals/value | Coverage snaps, targets, catchable/completions allowed, intended air yards, deserved catch rate, rating against, yards/coverage snap, Points Saved/PAA/EPA/PAR/WAR, boom/bust | Team fields are ingested; broad lagged EPA is redundant. SIS pass-tail features showed a modest historical 220+ result, pending prospective replication. |
| Pass rush totals/value | Pass snaps/rushes, sacks, unblocked sacks, hurries, hits, knockdowns, pressures, deflections, Points Saved/PAA/PAR/WAR | Partly ingested in team context; not separately evaluated in a valid player-tail or lineup test. |
| Run defense totals/value | Run/rush snaps, tackle depth, TFL/stuffs, broken/missed tackles, Points Saved/PAA/PAR/WAR | Ingested in team run context; tested as a marginal RB opponent feature and failed its tail gate. |
| Blocking totals/value | Overall/pass/run snaps, blown blocks, holds, Points Earned/PAA/PAR/WAR; Runs to Gap and Adjusted Blown Blocks | Broad team blocking fields are ingested; QB-line arm failed its 30-point gate. Runs-to-Gap and adjusted-blown-block detail remain untested. |
| Player/defender coverage | Coverage snaps, targets, completions, yards, TDs by defender and Wide/Slot alignment | Historical receiver-copula acquisition exists. Its calibration design had no eligible multiplicity cells, so it was inconclusive rather than a valid rejection. This is the most important SIS gap. |
| Alignment/ASOE | Wide/slot attempt composition and opponent-adjusted alignment share | ASOE allocation mechanism exists and was tested as a score-free allocation study; it is not a live production feature. |
| Situational splits | Down/distance, field position, quarter, score/time, personnel, formation, motion, pressure, route, shell and blocking scheme | Mostly only catalogued. These are potentially high-value interaction axes but must be requested as small, predeclared slices rather than mined freely. |
| Other products | Injury data, weekly projections, tendencies, on/off splits, participation/frame-timer and player/snap projections | Not exposed by the current authenticated NFL leaderboard surface; entitlement and price must be confirmed before treating them as available. |

## What the coverage evidence says

Coverage has been correlated with realized performance in several historical reads, so the question has not been ignored. The results are narrower than the broad “coverage is useless” conclusion:

- Prior-season FP receiver coverage-fit used opponent-weighted Man/Zone TPRR, YPRR, FP/RR and shell separation. It improved aggregate 30-point Brier by only about 0.21%, worsened 20-point Brier and MAE, had only 62 observed 30-point events, and changed sign across held-out seasons. This is a weak calibration signal, not a reliable ranking signal.
- The FP coverage-tail union changed 33 selected slots but tied the incumbent on every one of 107 historical slate maxima. The mechanism moved rows without moving the outcome ceiling.
- Same-season last-four FP coverage failed its 30% support gate (roughly 22–23% support) and worsened aggregate 30-point Brier. Sparse early-window coverage is a real limitation.
- FP QB shell-fit cleared its coverage support gate but worsened aggregate 30-point Brier, 20-point Brier, and residual MAE.
- SIS team-context audit found small but repeatable associations: opponent pass-defense EPA with TE residuals was positive in all three seasons, and QB/RB blocking directions were mechanically coherent. The formal QB-line and RB-run-tail gates still failed. These associations should not be converted into coefficients without a new walk-forward gate.
- Route participation is the strongest coverage-adjacent result. At matched projections, high prior route share was roughly +0.6 to +1.0 DK points above projection, with the clearest 30-point lift in the 10–14 projection band. Route share and snap share are very collinear for WRs (r≈0.97), but less so for TEs (r≈0.90); that is exactly where route information adds role clarity.

## What is being used incorrectly or incompletely

1. **Live Fantasy Points matchup CSVs stop at archival storage.** They have no BigQuery load and no feature join, so capture success cannot affect Sunday scores.
2. **SIS weekly load provenance is not yet durable enough for experiments.** The newer loader needs a non-null source identity and ingestion timestamp, exact schedule-universe completeness, deterministic create-once write identity, post-write hash/key verification, and a scheduled caller.
3. **SIS team metrics are averaged before testing.** Averaging broad lagged rates erases the situation that may matter: pressure × QB style, shell × route/alignment, blocking × run concept, and defender × receiver concentration.
4. **The paid ladder used mean-edge admission.** Its source cells changed the books, but mean-edge admission discarded the candidate tail. Source value cannot be judged solely downstream of that bottleneck.
5. **Coverage data is mostly prior-season or four-game aggregates.** The current tests do not preserve uncertainty, shrink sparse cells toward position/team priors, or explicitly model role changes and red-zone route participation.
6. **Player-level SIS coverage is not connected to receiver identities in a predictive test.** The existing copula attempt aggregated defender outcomes into dependence fields and then failed support calibration. It never tested a direct matchup feature such as expected coverage snaps, target share allowed, or defender quality against the specific receiver.

## Experiments that can reveal additional value

### A. Coverage/role incremental forecast test (highest-value FP test)

On a common frozen player-week universe, compare the production baseline with:

1. baseline + route share;
2. baseline + route share × position interactions (especially TE);
3. baseline + red-zone route participation;
4. baseline + route share × target share × projection band;
5. baseline + predeclared FP coverage edges, with shrinkage and support indicators.

Use walk-forward player residual MAE/CRPS/Brier-20/Brier-30, calibration by position and projection band, and candidate admission/selected-book turnover. Do not hand-rank coverage edges. The red-zone route and TE interaction are new questions and are not closed by the prior coverage failures.

### B. SIS player-coverage matchup test

Use the existing Wide/Slot defender history to construct only predeclared features:

- opponent expected coverage snaps by alignment;
- target rate and yards allowed per coverage snap, shrunk by coverage snaps;
- defender target/coverage quality residual relative to team baseline;
- receiver alignment share × opponent alignment allowance;
- concentration/dispersion of coverage responsibility, not just team averages.

Require at least two independent seasons or a declared current-season support floor, keep missing distinct from zero, and compare against an identity-only team-shell baseline. The first gate should be player-level forecast calibration, not lineup selection. If it passes, run a separate lineup shadow. This is different from the failed SIS marginal and untestable copula mechanisms.

### C. Tail-aware paid-source retrieval test

Re-run the FP/SIS 2×2 source ablation with two admission policies on the same candidate/world matrices:

- current top-200 mean-edge admission;
- top-200 admission by a frozen tail-aware score combining mean, P200/P220, and uncertainty/coverage support.

Keep free/Odds/SIS/FP/all-three source cells separate. Report pool ceiling, admitted ceiling, K20/K40/K80 maxima, 200+/210+/220+ clears, and source-by-policy interaction. This directly tests whether the earlier null was caused by retrieval rather than source signal.

### D. SIS situation-slice tests

Do not download every Cartesian combination. Freeze three small bundles:

- QB: pressure/clean-pocket × opponent pass rush;
- WR/TE: alignment/route family × opponent shell;
- RB: box count/run concept × run-defense value and adjusted blown blocks.

Use strict prior windows, shrinkage, support reporting, and one walk-forward model gate per bundle. The purpose is to test conditional mechanisms that team averages cannot represent.

### E. Live matchup integration shadow

For Fantasy Points WR/OL/DL/QB matchup reports, first repair the source table identity and schedule gate, load them into a point-in-time research table, and compare baseline versus matchup features on held-out slates. Track player residuals, candidate entry, selected membership and first-entry order. No production use should occur from browser capture alone.

## Renewal recommendation

- **Fantasy Points:** renew for one bounded evaluation period if the cost is acceptable, because weekly Route Share has demonstrated signal and the untested red-zone/role path is plausible. Do not pay indefinitely for broad coverage fields without running the TE/route/red-zone test and the live matchup join.
- **SIS:** renew for one bounded evaluation period if the player-level coverage/alignment data and pass-tail shadow can be captured reliably. The team marginal channel is weak, but SIS offers the most promising untested defender-grain and situational fields. If the vendor cannot supply stable identity-sidecars, complete snapshots, or a repeatable weekly cadence, the subscription is not justified.
- **Do not treat the historical paid-source ladder as a final vendor verdict.** It established that the tested consumers reshuffle lineups and that the current mean-edge admission loses the pool tail. It did not test the best available coverage/role representation or a tail-aware consumer.

## Recommended next three actions

1. Repair and validate the SIS/FP source-bound weekly tables, then run the common-universe incremental shadow with source influence traces.
2. Run the FP route-share × TE/red-zone-role forecast test; this is the most likely near-term source improvement.
3. Run the SIS player-coverage Wide/Slot matchup support census and score-free feature gate. Only after those pass should we spend lineup-shadow compute.

## References

- [Fantasy Points utilization review](/home/erich/projects/nfl-predictions/reports/2026-08-11-fantasy-points-data-utilization.md)
- [Fantasy Points coverage inventory](/home/erich/projects/nfl-predictions/reports/2026-08-13-wr-defense-coverage-test-inventory.md)
- [SIS subscription inventory](/home/erich/projects/nfl-predictions/reports/2026-08-13-sis-nfl-subscription-inventory.md)
- [SIS team-context audit](/home/erich/projects/nfl-predictions/reports/2026-08-13-sis-team-context-feature-audit.md)
- [SIS pass-tail result](/home/erich/projects/nfl-predictions/reports/2026-08-14-sis-pass-tail-exact80-result.md)
- [SIS run-tail result](/home/erich/projects/nfl-predictions/reports/2026-08-14-sis-run-tail-final-served-result.md)
- [Paid-source influence ladder](/home/erich/projects/nfl-predictions/reports/2026-09-15-paid-source-influence-ladder-direct.md)
- [Production paid-source update review](/home/erich/projects/nfl-predictions/reports/2026-09-20-production-paid-source-update-review.md)
