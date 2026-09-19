# Recent project reviews and research reports

Canonical reading copies are in this project's `reports/` folder. Open this index from
`/home/erich/projects/nfl-predictions/reports/RECENT-REVIEWS.md`; a review worktree is not needed.

| Document | Purpose |
|---|---|
| [Paid-source experiment plan](2026-09-18-paid-source-experiment-plan.md) | Authorized first-stage scope and routing |
| [Paid-source preflight results](2026-09-18-paid-source-experiment-preflight-results.md) | Registered models, Odds fixtures, vendor support and paused shadow schedules |
| [Paid data usage and renewal review](2026-09-18-paid-data-usage-and-renewal-review.md) | Odds API, SIS and Fantasy Points: current use, historical evidence, proposed tests and renewal advice |
| [220+ research agenda](2026-09-17-research-agenda-220-plus.md) | Improving candidate supply, selection and spreadsheet prefixes |
| [Transition code review](reviews/2026-09-17-transition-code-review.md) | Code findings and synthetic evidence; subsequent fixes are tracked in the handoff and follow-up reports |
| [Next-week plan and replies](2026-09-18-reply-and-next-week-plan.md) | E0 artifact census, bounded pilot and review follow-ups |
| [Satellite discussion and E0 agreement](2026-09-18-satellite-reply-and-plan-agreement.md) | Contest allocation assumptions, proxy limitations and agreed experiment sequence |
| [PREREG-101 independent review](2026-09-18-prereg101-independent-review.md) | Statistical identification and implementation issues identified before launch |

The reports retain their original dates and conclusions. They are historical records, not instructions
to undo later decisions: the satellite layout was subsequently changed by Erich, and the workstation
accepted the PREREG-101 critique and withdrew launch readiness in favor of staged E0 work.
Consult [the project handoff](../HANDOFF.md) and the other agent's dated replies for later dispositions.

Supporting files are in [reviews/evidence/](reviews/evidence/). Synthetic scripts there are review
reproductions, not additional application tests or instructions to run experiments.

Consolidated September 18, 2026 at Erich's request. Source commits: production `43568eea`
(transition/research reports), `930ee8b2` (paid-source report), and lab `de2f497`
(PREREG-101 review). Original commits remain in Git history; use these main-project paths for reading.

- [E0 known-law experiment results — September 18](2026-09-18-e0-known-law-results.md): completed synthetic selection-precision study; peer review pending.

- [E0b candidate-count results](2026-09-18-e0-candidate-count-results.md): 2000 synthetic K1 selections; distinguishes estimate optimism from true selection loss.
- [D800 archive readiness](2026-09-18-e0-archive-readiness.md): identity census and saved-bank provenance.

- [E0c archived D800 resampling results](2026-09-18-e0c-archive-resampling-results.md): 15 K80 selections, exact finite-law evaluation; no actual outcomes.

- [E0d retrieval swap results](2026-09-18-e0d-retrieval-swap-results.md): three swaps; small K80 gain, prefix screen failed.

- [Week2 current-selector diagnostic](2026-09-18-week2-current-selector-diagnostic.md): exact90-row reproduction,97-entry extension and component tail disagreement.

- [Week2 component-gap decomposition](2026-09-18-week2-component-gap-results.md):12.73points associated withmeans,6.98with residualdistribution; diagnostic only.

- [Same-book contest allocation](2026-09-19-contest-allocation-results.md): one qualifying exchange improves both affected blocks under both models; full-book 220+ coverage is unchanged.

- [Fixed-K retrieval result](2026-09-19-fixed-k-retrieval-results.md): 965 coverage-improving replacement pairs screened; none preserve every declared component, prefix and contest guard.

- [Hsim role and missing-history trace](2026-09-19-hsim-role-trace-results.md): archived opportunity priors are missing; six selected WRs have zero hsim support and one selected QB receives no simulated passing production.

- [Whole-book retrieval guard](2026-09-19-fixed-k-tradeoff-results.md): removing prefix/block constraints still leaves no passing pair under all six whole-book component checks.

- [Route Share participation support](2026-09-19-route-role-support-results.md): five of six selected zero-support WRs have positive prior-week routes; repair the free-data baseline before measuring incremental vendor value.

- [Salary-week repair validation](2026-09-19-salary-week-repair-validation.md): real root cause, actual-SQL fixtures, historical parity and recovered prior usage; full isolated build pending.

- [Exact hsim replay](2026-09-19-hsim-replay-preflight-results.md): unchanged source and authenticated inputs reproduce all 4.35 million archived scores exactly.

- [Hsim game-input defect](2026-09-19-hsim-game-input-defect.md) and [schedule-only sensitivity](2026-09-19-schedule-only-hsim-results.md): frozen game lines differ from the live frame and affect25/97 selected memberships; efficacy not established.

- [Fixed-calibration schedule audit](2026-09-19-schedule-fixedcal-hsim-results.md): fresh final-world evaluation with saved calibration; small corrected-law difference, intervals spanning zero.

- [Usage-only hsim result](2026-09-19-usage-only-hsim-results.md): restored prior usage changes48/97memberships and recovers five WRs' opportunity support; independent repaired-hsim audit gains are conditional model evidence.

- [Live game-input repair validation](2026-09-19-live-hsim-game-input-repair-validation.md): 16 tests, exact numerical parity and full CLI rehearsal pass; release pending.
- [TabPFN cache follow-up](2026-09-19-tabpfn-live-cache-followup.md): complete Week 2 support, distinct consumers and isolated-refresh constraints.

- [Combined usage/game-line sensitivity](2026-09-19-usage-schedule-factorial-results.md): all four cases completed; usage drives the selection change, with no clear extra gain from game lines after usage under the corrected simulator.
