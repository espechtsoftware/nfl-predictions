# Scoring opportunity roadmap — 2026-08-10

This is a prioritized research queue, not permission to change the adopted
lineup policy. The live baseline remains `classic-k1-ce12-boom28-v1` until a
preregistered historical or prospective gate passes.

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

## Priority 1 — finish the frozen role-belief panel

Complete the union and, only if its role-specific 200-point oracle gate
passes, the equal-budget fixed panel. Do not tune the seed, six inputs, dose,
or gate after outcomes. This is the only active historical scoring arm.

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

Sources:

- <https://newsletter.fantasypoints.com/p/fantasy-points-data-free-this-week>
- <https://newsletter.fantasypoints.com/p/average-separation-score-fantasy-points-data>
- <https://newsletter.fantasypoints.com/p/early-bird-discount-2026>

Before purchase, verify that the subscription permits CSV export for the
full 2022-2025 weekly history rather than current-season-only views. The first
requested fields are:

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

Sources:

- <https://sportsdata.io/developers>
- <https://sportsdata.io/files/SDio_NFL_Advanced_Metrics.pdf>
- <https://ftnfantasy.com/data>

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

## Priority 4 — prospective field and selector evidence

- Freeze 187- and 200-point K=1 coverage books beside the 194 control. On the
  known accepted panel, 200 coverage changes the 200/210 counts from 18/11 to
  19/12; 187 coverage changes them to 17/13 while leaving 220/230/240 counts
  unchanged. These outcome-viewed tradeoffs justify prospective collection,
  not historical adoption. Policy `tail-first-v5-20260810` freezes both at
  the same early/late snapshots and adds the separately preregistered
  220→210→200 lexicographic extreme-tail book.
- Keep the implemented standings importer strict and retain top-20 ordered
  lineups plus full ownership after every 2026 main slate. Historical project
  data has winner rosters but not the old top-20 fields, so this cannot be
  reconstructed honestly.
- Shadow the already-defined deterministic lexicographic one-swap portfolio
  refinement prospectively as frozen policy `tail-first-v5-20260810`. It
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
