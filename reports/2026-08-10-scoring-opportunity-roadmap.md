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
  not historical adoption. Policy `tail-first-v4-20260810` freezes both at
  the same early/late snapshots.
- Keep the implemented standings importer strict and retain top-20 ordered
  lineups plus full ownership after every 2026 main slate. Historical project
  data has winner rosters but not the old top-20 fields, so this cannot be
  reconstructed honestly.
- Shadow the already-defined deterministic lexicographic one-swap portfolio
  refinement prospectively as frozen policy `tail-first-v4-20260810`. It
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

## Lower priority

A new deep generative copula or diffusion model is not justified yet. The
conditional-dependence arm already failed its gate, and only 107 realized
slates are available for portfolio scoring. Revisit multivariate calibration
after route/role data and prospective top-20 field data expand the evidence,
not as another large model fitted to the same outcomes.
