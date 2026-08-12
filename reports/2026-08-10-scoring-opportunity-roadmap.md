# Scoring opportunity roadmap — 2026-08-10

This is a prioritized research queue. The operator revised the operational
decision law on 2026-08-10 to prioritize the highest weekly portfolio score;
the complete compatible-arm review is in
`reports/2026-08-10-tail-first-adoption-review.md`. Scientific gate results
remain immutable, but an explicitly labeled operator override may promote a
mechanically valid arm when an older score gate conflicts with that utility.

Queue addendum (2026-08-11): graph/dependence ideas are reconciled and ordered
in `reports/2026-08-11-graph-dependence-research-queue.md`. The first new item
is a score-free, walk-forward archetype-pair co-exceedance topology diagnostic;
an upper-tail QB bi-factor copula is conditional on that evidence. Participation
embeddings are exploratory, the field-neighbourhood graph waits for complete
2026 standings/payout ladders, and Neo4j/GNN/LLM projection work is not queued.

Point-in-time addendum (2026-08-11): the latest static join/accuracy review is
reconciled in `reports/2026-08-11-pit-join-audit-reconciliation.md`. Four
candidate team-context tables require live upcoming rows, the modeled defense
position aggregation must use exact player-week positions, and dynamic
source-recomputed leakage checks need staged expansion by feature family.
Those plumbing repairs precede any candidate promotion and the next normal
feature rebuild; they do not reorder the frozen active-label → SCHED → team-QB
marginal sequence.
Dynamic source-family expansions now independently reconstruct the three active
trailing-production fields, four advanced opportunity/NGS fields, the adopted
neutral-pass ratio and both QB NGS windows, including sample volatility, exact
missing-spine semantics and cross-season ordering. Smoothed usage and injury/
vacancy remain next.

Closure addendum (2026-08-11): after every historical arm reaches a terminal
state, run the mandatory end-of-preseason forensic protocol in
`reports/2026-08-11-final-preseason-forensic-closure-protocol.md`. It corrects
the zero-valued layer in the outside proposal, decomposes player support from
lineup construction and selection, adds identifiable ROI/contest analysis,
joint-tail calibration, complete experiment/PIT reconciliation and a Week-1
dress rehearsal. It is a prospective-charter and readiness gate only; it may
not promote or retune a historical arm.

## Evidence that sets the priorities

- The accepted true-80 book clears 200 on 18/107 slates, 210 on 11, and 220
  on 5. Its pool oracle clears those lines on 22/13/5, so the current pool has
  only four nonredundant recoverable 200-point weeks.
- Among 68 known Millionaire winners, the accepted pool misses 36 player slots
  on 28 weeks. WR and TE account for 23 of the 36, and the omitted players
  average +13.30 points above their pre-lock projection. Those omitted slots
  average $4,128 salary and 5.88% realized ownership, with 61.1% below 5%;
  covered winner slots average $5,644 and 13.88%. Eleven misses are fast-role
  players and six are vacancy/promotions. This supports better cheap-player
  role beliefs, not another generic ownership-score penalty.
- Fast role growth and vacancy/promotion beat same-slate, same-position
  matched controls in every season. Their existing TabPFN tails are already
  reasonably calibrated, so a generic variance increase is unlikely to be
  the answer. The preregistered role-belief candidate panel is testing whether
  alternative role beliefs assemble better rosters.
- Known winner salary totals are usually near $50,000, and the prior no-floor
  arm was rejected. QB+2+bring-back and stack-loosening alternatives also
  lost substantial tails in prior valid tests. These are closed, not new
  opportunities.

## Priority 1 — role union promoted under the revised operator policy

The valid union created 1,269 novel role rosters and 11 realized frontier
weeks, but zero new 200-point weeks on slates whose source oracle was below
200. Its original frozen gate therefore remains failed and the equal-budget
fixed panel remains unlaunched. The operator has now made an explicit
tail-first policy override: the same 80 final entries improved selected
210/220/230/240 from `11/5/2/1` to `12/6/3/2`, improved paired weekly maxima
on 15 slates versus 6 declines, and raised mean weekly maximum by 1.448.
Policy `classic-k1-ce12-role12-boom28-v2` replaced the prior policy on
2026-08-10 after the separately trained role registry and live path reproduced
the exact frozen mechanism. Do not tune the seed, six inputs, or dose. The
prior policy remains the labeled fail-safe implementation.

## Priority 2 — acquire route/role data if the historical export is usable

Before spending, run a no-cost pass-participation proxy study. The installed
`nflreadpy` client currently returns 46,168 / 45,919 / 45,184 play rows for
2023 / 2024 / 2025 from `load_participation`, including the eleven offensive
player IDs on each play. Joining those rows to `qb_dropback` and red-zone
field position can recover each receiver's share of team dropbacks spent on
the field, its week-over-week change, and teammate-vacancy redistribution.
This is not routes run: an on-field receiver can block, stay in protection,
or release without being represented by the play-level `route` value. It is
also season-delayed, so it cannot be served point-in-time for a current week.

Use the proxy only as a purchase/mechanism diagnostic on the 2023-2025
history. Build lagged features from the prior game, then compare frozen
walk-forward 2024 and 2025 player-level residual and 20-point tail forecasts
with and without pass-play participation. Existing projection, salary,
position, target/snap shares and vacancy fields are the control inputs. If
the added fields do not improve aggregate held-out Brier and residual MAE,
they do not support buying a route feed. If they do, proceed to the paid
export below, because only that source can supply true routes and a live
weekly update. No lineup outcome or candidate panel is part of this proxy
gate.

Completed result: immutable execution `pass-participation-proxy-vmxdq`
improved held-out aggregate residual MAE `3.71089→3.67957`, 20-point Brier
`0.045375→0.045226`, and WR/TE Brier `0.039258→0.039082` across 9,887
2024-2025 player-weeks. Both primary metrics improved in both seasons, so the
frozen disposition is `supports-paid-route-trial`. The effect is modest; use
it to justify the measured true-route export trial, not to forecast a large
lineup-score lift.

Source:

- <https://github.com/nflverse/nflreadr/releases>

Fantasy Points Data is the best sub-$200 candidate found. Its official
material lists weekly route share and target share, advanced receiving,
coverage/alignment/separation data, and CSV/Excel export. Its separation data
is advertised on a route-by-route basis back to 2022. The announced 2026 Data
Suite list price is $200 and its early-bird price was $160, so purchase only
if checkout or a valid promotion puts it below the operator's $200 ceiling.

Acquisition status (2026-08-10): the operator purchased the standalone Data
Suite at the $200 ceiling. Full-history export access is not yet verified.
Preserve every vendor download byte-for-byte before normalization. The first
pass requests separate 2022, 2023, 2024 and 2025 all-week/all-team exports for
all six Weekly Reports: Fantasy Points Scored, Snap Share, Route Share, Target
Share, offense PROE and defense PROE. Route/target/snap are the primary player
opportunity inputs; the two PROE reports are secondary team-context candidates;
Fantasy Points Scored is an identity/scoring audit rather than a replacement
for the existing authoritative DraftKings labels. Also request unfiltered
season exports from Advanced Receiving. If the interface limits exports to one
week, preserve the original per-week files rather than combining them by hand.

Sources:

- <https://newsletter.fantasypoints.com/p/fantasy-points-data-free-this-week>
- <https://newsletter.fantasypoints.com/p/average-separation-score-fantasy-points-data>
- <https://newsletter.fantasypoints.com/p/early-bird-discount-2026>

Before any experiment, verify that the subscription permits CSV export for the
full 2022-2025 weekly history rather than current-season-only views. The first
requested Advanced Receiving fields are:

1. routes run and route participation;
2. targets per route run and first-read target share;
3. slot/wide/inline alignment shares;
4. average depth of target and air-yard share by alignment;
5. separation/win rate by route and coverage; and
6. red-zone/end-zone routes and targets.

The evaluation must be walk-forward and point-in-time: a week's charting may
only predict later weeks. Start with a player-level held-out calibration and
20/30-point tail gate, then require a candidate-union oracle gain before any
fixed-budget lineup panel. Do not add all fields at once to the production
model.

SportsDataIO Discovery Lab is not the first choice. Its official personal-use
tier is $99/month and real data is next-day delayed, but its public advanced
metric list does not establish that the route-level fields are included in
that tier. FTN's direct historical data products begin far above the budget.

Two lower-cost fallbacks merit a support/export question, not an immediate
purchase. Reception Perception's $99.99/year tier advertises all historical
NFL data tables, while lower tiers describe WR route/coverage/alignment and TE
route/coverage data. It is likely better for receiver skill and separation
traits than for complete weekly opportunity: its public page does not promise
CSV export, every slate player, routes run, or RB receiving routes. Sports
Info Solutions lists a $99.99 one-month NFL DataHub tier with CSV export, but
its public pricing page does not enumerate route-participation fields or
retained seasons. Ask both the same full-history/raw-export question only if
Fantasy Points cannot satisfy it. Neither displaces Fantasy Points for the
measured dropback-participation signal without complete player-week route
volume.

Sources:

- <https://sportsdata.io/developers>
- <https://sportsdata.io/files/SDio_NFL_Advanced_Metrics.pdf>
- <https://ftnfantasy.com/data>
- <https://receptionperception.com/subscription-page-new/>
- <https://store.sportsinfosolutions.com/>

## Priority 2A — market-tail disagreement from data already in house

DraftKings alternate pass/rush/receiving-yard ladders already cover every
corrected Sunday-main slate in 2024 and 2025. Before purchasing data or
spending more Odds API quota, test whether the signed disagreement between
the incumbent production tail and a single position-primary market tail adds
held-out 30-point player signal. Enforce one common slate lock; do not use a
late game's kickoff as its private cutoff.

This does not reopen the rejected `ALT_CEIL` objective tilt. A passing
player-level gate licenses only one twelve-candidate union on the current
role-union v2 book; final scoring and selection remain on incumbent worlds.
The complete frozen construction, 2024-to-2025 gate and current tail-first
promotion law are in
`reports/2026-08-10-market-tail-disagreement-experiment.md`.

Completed result: immutable execution `market-tail-diagnostic-jg52t` covered
all 36 recent slates but failed the frozen mechanism gate. The signed
residual separation reversed in 2024, and held-out 2025 30-point Brier
worsened slightly `0.0305295→0.0305408`. No candidate union is licensed and
this historical alternate-ladder mechanism is closed without quota spend.

## Priority 2B — free lagged NGS receiver traits

NFL Next Gen Stats weekly receiving data provide separation, cushion,
intended air depth, air-yard share and YAC above expectation with stable GSIS
IDs. Production already uses same-season separation plus PBP-derived air
share/aDOT; the actual incremental question is cross-season carry-forward
and the missing cushion/YACOE descriptors. A strictly prior observation
covers about 88% of candidate-used WR/TE roster appearances in the preserved
historical universe. Protocol
`reports/2026-08-10-ngs-receiver-tail-experiment.md` freezes a score-free
2019--2025 construction and 2024/2025 walk-forward 30-point Brier gate before
outcomes are queried. Run it only after the corrected K1 control is complete.
A pass licenses one feature/candidate-union design; it is not direct model or
lineup adoption and does not replace true route-volume data.

## Priority 3 — a credit-capped Odds API opportunity pilot

The existing vendor can supply historical player props from May 3, 2023.
Historical event odds cost 10 credits per region, market, and event. A Sunday
main-only pilot should therefore use no more than three volume markets—pass
attempts, rush attempts, and receptions or completions—at one frozen pre-lock
snapshot. It should hard-stop before 20,000 credits and preserve at least
75,000 of the current plan's quota.

Sources:

- <https://the-odds-api.com/historical-odds-data/>
- <https://the-odds-api.com/sports-odds-data/betting-markets.html>

The pilot question is narrow: do market-implied opportunity distributions
improve held-out role/tail calibration over our model, especially for
fast-role and vacancy states? It is not a blind nine-market backfill. No quota
may be spent until the exact event count and credit ceiling are printed and
approved.

## Priority 3A — corrected role/no-floor candidate union

The no-floor policy remains inferior as a standalone book, but its preserved
pre-correction pool contributes 7,848 rosters absent from the role-union pool
(73.35 per slate) without increasing the final entry count. The combination
of the two candidate sets has never been tested. Protocol
`reports/2026-08-10-corrected-floor-union-experiment.md` freezes one exact
added-budget union before corrected control scores are complete. It may run
only after the corrected K1→CE→role chain establishes a valid source, and it
must retain every source roster, add the exact binary no-floor control, return
80 unique entries, and pass the 240→230→220→210 law. No intermediate floor,
quota, selector, or retry is allowed.

## Priority 4 — prospective field and selector evidence

- Freeze 187- and 200-point K=1 coverage books beside the 194 control. On the
  known accepted panel, 200 coverage changes the 200/210 counts from 18/11 to
  19/12; 187 coverage changes them to 17/13 while leaving 220/230/240 counts
  unchanged. These outcome-viewed tradeoffs justify prospective collection,
  not historical adoption. Policy `tail-first-v6-20260810` freezes both at
  the same early/late snapshots and adds the separately preregistered
  220→210→200 lexicographic extreme-tail book.
- Keep the implemented standings importer strict and retain top-20 ordered
  lineups plus full ownership after every 2026 main slate. Historical project
  data has winner rosters but not the old top-20 fields, so this cannot be
  reconstructed honestly.
- Shadow the already-defined deterministic lexicographic one-swap portfolio
  refinement prospectively as frozen policy `tail-first-v6-20260810`. It
  recovered the 2021 week-4 215.38 pool oracle in an outcome-viewed diagnostic,
  which is insufficient for historical adoption but enough to justify a
  zero-tuning shadow. Grade it only after frozen real outcomes accumulate.
  Implementation commit `b90047b` passed Cloud Build
  `7ab5a1e2-1994-4ec5-8ac8-a188669b54c5` (716 passed, 2 skipped); the two
  paused freezer jobs use immutable digest `sha256:603d20c0...` and retain
  their original schedules/resources.
- Use real large-field ownership to simulate opponent portfolios and payout,
  not merely to add another ownership penalty to our score. Optimization
  research supports maximizing the chance at least one lineup wins under a
  top-heavy payout and explicitly modeling opponents; the previously rejected
  ownership arm did neither.

Sources:

- <https://arxiv.org/abs/1604.01455>
- <https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528>

## Priority 5 — prospective multi-threshold and rare-support estimation

The accepted selector maximizes world coverage at one comparison line, 194.
That was a useful historical benchmark, but it is not a complete expression
of the operator's preference for one exceptional 210-240 lineup. After the
currently building 187/194/200 prospective books are deployed, extend only
the *prospective* candidate snapshots to retain 210- and 220-point support
masks. Freeze one deterministic lexicographic book that maximizes uncovered
220 worlds, then 210, then 200, with individual support probability and
simulated mean as fixed tiebreakers. Do not back-select its rules from the 107
known weekly scores, and do not change the adopted 194 book.

The deeper follow-on is an estimator test, not another CE candidate retry.
The adopted CE generator already uses learned rare worlds to create lineups,
but its importance weights are explicitly candidate-only; every candidate's
selection support is still estimated from the ordinary production worlds.
Those weights **cannot be reused directly** for support estimation: CE's
bounded knobs deform deterministic player means and do not constitute an
alternate draw from the possession simulator with a known density ratio.

The first prerequisite is therefore to expose a small set of the production
simulator's own continuous latent variables and their exact log density, then
define an absolutely continuous mixture proposal over those same variables.
Only a proposal whose likelihood ratio reproduces analytically solvable toy
events and ordinary Monte Carlo estimates may attempt to estimate lineup
`P(score >= 210)` and `P(score >= 220)`. Preserve an ordinary-mixture
component so multiple important regions are not dropped. If an exact density
ratio cannot be written and tested, close this idea; self-normalized weights
from CE mean deformations are not an acceptable approximation.

The mechanism must pass before any portfolio is frozen:

1. likelihood ratios reproduce normalized mass and analytic toy-event
   probabilities, then weighted estimates reproduce ordinary-world 187/194
   probabilities within their registered Monte Carlo confidence intervals;
2. effective sample size is at least 25% of the nominal sample and no single
   world carries more than 1% normalized weight;
3. across five fixed independent seeds, median relative standard error at
   210/220 falls by at least 25% for candidates with nonzero ordinary support;
4. player marginal means and quantiles are unchanged, because this is an
   estimator of the existing distribution rather than a new player belief;
5. the ranked top-80 set is stable enough that pairwise roster overlap rises
   by at least 10 percentage points versus equal-cost ordinary simulation.

Failure closes the weighted-support estimator without a historical scoring
panel. A pass licenses only the prospective lexicographic shadow above. This
separates the measured candidate-generation success of CE from the still
unresolved problem of accurately ranking very rare lineup tails.

Sources:

- <https://pubsonline.informs.org/doi/abs/10.1287/ijoc.1060.0176>
- <https://pubsonline.informs.org/doi/10.1287/opre.1080.0558>
- <https://pubsonline.informs.org/doi/10.1287/mnsc.2023.4973>

## Lower priority

A new deep generative copula or diffusion model is not justified yet. The
conditional-dependence arm already failed its gate, and only 107 realized
slates are available for portfolio scoring. Revisit multivariate calibration
after route/role data and prospective top-20 field data expand the evidence,
not as another large model fitted to the same outcomes.
