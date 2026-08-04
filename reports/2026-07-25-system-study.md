# System study: replayed picks, weekly confidence, and what actually matters

*2026-07-25. All results from season replays: models trained strictly on
seasons before the replayed one, projections built through the production
path (cold-start fill → components → simulation → calibration), scored
against actual DK points. Reproduce with `nfl-dfs replay --season N` and
the study scripts referenced at the bottom.*

## 1. What would we have picked in 2025, and how did it fare?

2025 has no real DK salaries (see the data deficiency log), so salaries
were **imputed** from a position + trailing-production model fit on
2014–2021 (~$96–196 per trailing point over a $2.2–4.3k base). Points are
real; the salary-cap constraint is approximate. 20 GPP entries per week,
core optimizer settings.

| Metric (17 weeks) | Result |
|---|---|
| Mean best-entry score | **181.7** |
| Best week | **248.4** (week 15) |
| Weeks best entry ≥ 190 | **5 / 17** |
| Weeks best entry ≥ 170 | 12 / 17 |
| Mean median-entry score | ~152 |

Against the ~190–200 "near the top" bar: the best of 20 entries clears it
roughly **once every 3–4 weeks**, and is in striking distance (170+) most
weeks. That's the honest shape of DFS: no projection system hits the
winning line weekly, because winning lineups require multiple tail
outcomes. The week-15 winner is instructive — the system's projections
were near-consensus (Hurts, CMC, Chase), and the 248 came from cheap
ceiling hits it deliberately rostered: Kyle Pitts ($3.8k imputed, 13.5
projected, **48.6 actual**) and Amon-Ra St. Brown (19.9 projected, 44.4
actual). The p90/ceiling objective on variation spots is doing its job.

For calibration: real 2021 salaries + the sharp simulated field put
double-up ROI at +51% (see README replay findings) — the cash-game
signal remains the more reliable evidence of edge than any GPP score.

## 2. Does confidence improve as the season unfolds?

Per-week averages across five replayed seasons (2018–2021, 2025). Week 1
never appears — every player needs ≥1 prior game to have features, which
is itself the honest answer about opening week.

| Window | MAE | Rank corr | Edge vs naive (MAE) |
|---|---|---|---|
| Early (W2–4) | 5.35 | 0.62 | **+0.89** |
| Late (W9+) | 5.15 | 0.61 | +0.23 |

Three findings, one of them counterintuitive:

1. **Absolute accuracy improves modestly** through the season (~4% MAE),
   flattening around week 8. Data accumulation helps, but multi-season
   priors mean the model never starts from scratch.
2. **Rank ordering doesn't improve** (~0.61 all season) — the model's
   ability to sort players is as good in September as December.
3. **The model's *edge* is largest early.** In weeks 2–4 the naive
   trailing-average is terrible (MAE 5.9–6.9) because samples are tiny,
   while the model leans on multi-season history, Vegas, roles, and draft
   capital. By late season simple heuristics catch up. Strategically:
   **early season is when this system is most valuable relative to the
   field**, not least — the intuition that "we should wait until we have
   more data" has it backwards, as long as bankroll sizing respects the
   slightly higher absolute error.

Calibration (p10 ≈ 8–9%, p90 ≈ 87–89%) is stable across all weeks.

## 3. Which metrics actually matter?

Two lenses on 2025 replays: drop-one-group ablations (retrain without a
feature group, measure MAE change) and LightGBM gain importances.

| Config | MAE | Δ vs full |
|---|---|---|
| Full model | 4.934 | — |
| minus Vegas (implied total, spread, script) | 4.982 | **+0.048** |
| minus production trail (dk_points_l4/std/vol) | 4.971 | +0.037 |
| minus usage (shares, WOPR, smoothed RZ) | 4.968 | +0.034 |
| minus role/next-man-up | 4.958 | +0.024 |
| minus defense (all allowed metrics) | 4.942 | +0.008 |
| minus salary | 4.921 | **−0.013** |

Gain importances (opportunity models): `wopr_l4` + `target_share_l4`
carry **67%** of the targets model; `carry_share_l4` alone is 60% of the
carries model.

Reading it honestly:

- **Opportunity metrics are the engine** (WOPR, shares, snaps). Ablation
  deltas look small only because feature groups are redundant — trailing
  production partially proxies usage — but the importances show where the
  models actually look.
- **Vegas is the least replaceable group**: nothing else encodes game
  environment.
- **Defense-allowed features contribute almost nothing** to projections
  (+0.008). This retroactively validates skipping paid DVOA — if our free
  defense metrics barely move MAE, a better version of them can't move it
  much either. (They remain useful for the dashboard/research layer.)
- **Salary looked like noise on 2025 (−0.013 when removed) but this was
  a null-era artifact, verified and kept.** A follow-up ablation on 2021 —
  where training salary coverage is complete — shows salary *helps*:
  +0.010 MAE and rank correlation 0.611 → 0.599 without it. The 2025 harm
  comes from 2022–2025 training rows being salary-null (RotoGuru gap), so
  learned salary splits get NaN-routed on recent data. Decision: keep the
  features; the problem self-heals from 2026 as the live `ingest-dk`
  salary log accumulates. Revisit only if a 2027 ablation still shows
  harm.
- The new role/next-man-up group (+0.024) earns its place — comparable to
  usage's marginal contribution despite being days old.

## 4. Salaried-season lineup scores (real salaries)

With real 2014–2021 salaries, same 20-entry GPP structure:

| Season | Weeks | Mean best entry | Max | Weeks ≥190 | Weeks ≥170 | Mean median entry |
|---|---|---|---|---|---|---|
| 2018 | 16 | 169.3 | 205.9 | 3 | 7 | 141.0 |
| 2019 | 16 | 165.4 | 222.6 | 4 | 7 | 138.0 |
| 2020 | 16 | 166.1 | 203.1 | 3 | 9 | 135.9 |
| 2021 | 17 | 161.9 | 199.5 | 2 | 8 | 134.8 |
| **All** | **65** | **165.6** | 222.6 | **12 (18%)** | 31 (48%) | 137.4 |

Under real salary constraints the best of 20 entries clears 190 about
**once every 5–6 weeks** and reaches 170+ about half the time. Note these
run ~15 points below the 2025 imputed-salary numbers — imputation smooths
real pricing inefficiencies in our favor, so treat the real-salary table
as the truthful baseline and the 2025 figures as directionally right but
flattering. Both are consistent with the +51–69% double-up ROI story:
this system's measurable edge is steadier accuracy, not weekly jackpot
lineups — exactly what cash games pay for and GPPs only occasionally do.

## Reproducibility

- `nfl-dfs replay --season N [--contest gpp|double_up] [--sharp F]`
- Study scripts (session scratchpad, reproducible from this report's
  descriptions): weekly metrics grid, 2025 imputed-salary picks, ablation
  matrix. Weekly metrics CSV archived in this directory.


## Addendum: advanced-metric research and implementation (same day)

Follow-up research on high-value fantasy metrics (volume dominance, air-yards
target quality, TD-history instability, NGS over-expected stability) led to
four new strictly-prior features via `015a_player_week_advanced.sql`:
end-zone targets (air yards >= distance to goal), deep targets (20+ air
yards), NGS separation, and NGS stacked-box rate.

Measured verdict — honest: **no meaningful lift today.** Replay deltas were
within noise (2021 +0.007 MAE, 2025 −0.005 MAE / +0.003 rank corr), and gain
shares show why: `wopr_l4` + `rz20_targets_smoothed` already encode the
target-quality and TD-opportunity signal the research recommends — the
existing featureset was ahead of the critique. Kept anyway: zero measured
cost, sound mechanism (separation reaches 4.2% of the TD model's gain), and
the table doubles as research data (end-zone target leaderboards).

Deliberately NOT implemented, with reasons:
- **DVOA (paid)** — our ablation shows defense features contribute +0.008
  MAE total; a better defense metric cannot matter much (see §3).
- **NGS RYOE / YAC-over-expected** — public research shows near-zero
  year-over-year stability; they grade highlights, not futures.
- **Routes run / targets-per-route-run** — the one genuinely valuable
  missing metric; no free source exists (PFF/FTN paid tiers). Logged in the
  data deficiency table.


## Addendum 2: entry-construction matrix (new features live)

Re-ran 2025 with the advanced features in the retrained models, plus a
2x2 of entry objective {blended mean, p90 ceiling} x stacking {none, QB
stack >=1}, validated on 2021 real salaries:

| Season | Objective | Stack | Mean best | >=190 | >=170 |
|---|---|---|---|---|---|
| 2025 (imputed) | mean | none | 177.5 | 5/17 | 9/17 |
| 2025 (imputed) | mean | QB stack | 180.3 | 6/17 | 11/17 |
| 2025 (imputed) | p90 | QB stack | 182.6 | 6/17 | 9/17 |
| 2021 (real) | mean | none | 159.2 | 0/17 | 5/17 |
| 2021 (real) | mean | QB stack | **160.7** | **1/17** | 6/17 |
| 2021 (real) | p90 | none/stack | 156.6–156.9 | 0/17 | 2–3/17 |

Adopted: **QB stacking is now the GPP replay default** — it helps on both
salary regimes. Rejected: the p90 entry objective — flattering on imputed
salaries, harmful on real ones (pays real cap dollars for variance).
2025 with the new features scores in line with the pre-feature run
(177–183 vs 181.7 mean best), consistent with Addendum 1's redundancy
verdict.


## Addendum 3: real 2025 salaries land (DiscoveryLab) + Showdown replay

SportsDataIO's free personal-use DiscoveryLab tier turned out to serve
REAL DraftKings data for the most recent season — verified 13,406 salary
rows (100% clean $100-multiples) plus per-player actual DK points and DST
scoring. That removes the imputation asterisk from every 2025 number and
adds Captain Mode replay capability.

### Classic, real 2025 salaries (20 GPP entries/week)

| Metric | Imputed (old) | **Real** |
|---|---|---|
| Mean best entry | 181.7 | **158.5** |
| Max | 248.4 | 220.5 (wk 12) |
| Weeks ≥190 | 5/17 | **2/17** |
| GPP ROI (sharp field) | +202% | **+112%** |
| Double-up ROI | — | **+65.3%** (best of all 5 real seasons) |
| Projection MAE | 4.93 | **4.91** (real salary features helped) |

The imputed numbers were ~20 best-entry points and ~2x GPP ROI flattering,
exactly as suspected. The five-season real-salary story is now fully
consistent: double-up ROI +51% to +69% every season, best-of-20 clears
190 in roughly 1-of-6 weeks.

### Showdown Captain Mode, 2025 (first ever; 41 Thu/Mon slates, 20 entries)

| Metric | Result |
|---|---|
| Mean best entry / hindsight-optimal | 100.3 / 128.0 |
| Mean capture of optimal | **78.8%** (median 80.6%) |
| Slates ≥90% capture | 7/41 |

Capture (best entry / perfect-knowledge lineup for that slate) is the
headline metric because absolute showdown scores swing with the game.
~80% median capture from a 20-entry batch is a solid baseline; the gap
concentrates in slates where a low-projected player boomed (the classic
showdown loss mode). No field/ROI simulation — no showdown ownership model
exists yet; this measures lineup quality, not contest economics.
Machinery: `nfl-dfs import-discoverylab-showdown` + `nfl-dfs
replay-showdown` (backtest/showdown_replay.py).

Remaining salary gap: 2022-2024 only (DiscoveryLab paid tiers may cover
them; unverified). The deficiency-log entry is updated accordingly.


## Addendum 4: anatomy of actual 2025 Milly Maker winners (dfsarmy.com)

Winning-lineup data for three 2025 weeks, vs our replay entries:

| Week | Winning score | Our best of 20 | QB ownership | Game-stack size / pts | Sub-$4k booms |
|---|---|---|---|---|---|
| 7 | 249.6 | 155 | Herbert 6.0% ($6.4k) | 4-man + bring-back / 131 | Gadsden $3.3k @ 1.4% (32.4 pts) |
| 12 | 277.0 | 220 | Winston **3.97%** ($4.6k) | 4-man / 204 | Henry $3.9k (27.5 pts) |
| 15 | 236.0 | 170 | Goff 3.71% ($6.1k) | **5-man** / 198 | Parkinson $3.2k @ 7.3% (24.5) |

Every winner shares four elements our construction never produces:

1. **Sub-7%-owned QB, often cheap.** Week 12's Winston is the archetype —
   a next-man-up starter our vacated-opportunity features exist to detect,
   but our mean-objective optimizer will never roster a modestly-projected
   $4.6k QB. Ownership leverage, not projection, is what made him right.
2. **One massive game stack (4-5 players, 53-80% of all points).** Our
   qb_stack_min=1 is a different sport. Winners bet an entire game
   environment; we sprinkle correlation.
3. **At least one sub-$4k punt that boomed** (usually a 1-7% owned TE).
   Our optimizer structurally avoids low-projection punts.
4. **Chalk only where safe** (stud RB/WR at 23-39%), full $50k.

Diagnosis: our entries optimize the projection mean, which lands them
chalk-adjacent by construction — good for cash (+51-69% double-up ROI
every season) and top-20% finishes (median 19.5%), structurally unable to
win a 150k-entry contest. Winning scores (236-277) sit 2-4 sigma above
our best-entry distribution (mean 158, max 220).

### Recommended build: tournament ("milly") entry mode — a barbell

Keep most entries mean-optimal (the measured cash edge), add N leverage
entries per week:

- **Full game-stack construction**: for the 2-3 highest-total games, force
  QB + 3-4 pass catchers + bring-back from that game per entry.
- **Punt slot**: require >=1 player <=$4k, selected by p90 among players
  flagged by vacated-opportunity/depth-promotion (the Winston/Gadsden
  detector we already compute) — p90 failed as a whole-lineup objective
  but is right for the punt slot, where only ceiling matters.
- **Chalk fade**: penalize our naive-ownership proxy in leverage entries
  until real ownership data accrues (collection starts week 1 via
  import-ownership).
- **New replay metric**: P(any entry >= 240) and distance-to-winning-line,
  not mean best — the tail is the target.

### Full-season correction (all 17 weeks, reports/2025-milly-winners.csv)

The 3-week sample overstated some elements. Complete 2025 winner stats:

| Element | Full-season truth |
|---|---|
| Winning score | mean **236.9**, min **193.9** (wk 1), max 277.0 |
| QB ownership | mean 8.7%; sub-10% in 11/17 (65%) — common, not universal |
| Largest game stack | mean **3.2 players** — the 4-5-man stacks were outliers |
| **Sub-$4k player scoring 15+** | **16/17 weeks (94%) — the near-universal signature** |

Revised priorities for tournament mode: (1) the punt slot is the
signature, not a garnish — a cheap boom appeared in 94% of winners, and
our vacated-opportunity/depth features are the natural detector; (2)
low-owned QB second (65%); (3) game stacks third — 3-4 correlated players
suffice, our qb_stack machinery is closer than the sample suggested.
Also: the minimum winning score (193.9) is inside our current best-entry
range — in the softest weeks, consistency alone nearly competes; the gap
is concentrated in normal-to-high scoring weeks.

Not yet implemented; measured next via replay once built.


## Addendum 5: what elevated the winning punts (traced to our features)

The 10 skill punts from 2025 Milly winners, traced to their point-in-time
training rows (7 other winners used a cheap DST as the sub-$4k play):

- **3/10 next-man-up inheritors** — vacated-opportunity features fired
  hard: Hutchinson wk8 vac_tgt 0.464 (7.5x league mean 0.062), Wilson
  wk11 0.185, Boutte wk6 vac_car 0.168. The injury-elevation hypothesis
  is real and our detector sees it.
- **4/10 mispriced starters** — depth rank 1-2, snap share 0.67-0.91,
  yet priced $3.2-3.9k: DK price lag on established roles (Parkinson's
  usage trend 1.37). Salary-lag, not injury. p90 punt valuation captures
  these because ceilings load on snaps/usage.
- **3/10 rookies/new roles** (Gadsden, Fannin, wk-1) — cold-start rows
  absent from the training table (gp>=1 filter) but present in the
  inference table with depth/draft priors; the punt slot can reach them
  live even though replays undercount them.
- **DST-as-punt in 7/17 winners** — our punt constraint counts DSTs, so
  construction already permits this dominant pattern.

Implication: the punt slot needs no extra machinery — p90 valuation +
vacated features + inference-table cold-start rows cover all three skill
archetypes; replay-based punt validation slightly understates live punt
quality because rookies are invisible to the training panel.


## Addendum 6: season-wide leverage anatomy (all 153 winning roster spots)

All 17 Milly-winning rosters (136 skill players + 17 DSTs;
reports/2025-milly-rosters.csv) classified against point-in-time warehouse
signals. Signals: injury_vacated (teammate vacated share >=0.10),
secure_role_slump (depth<=2, snaps>=55%, trailing points <60% of the boom),
secure_role, no_history (rookie/returner), other.

| Tier | injury | slumping starter | secure role | no history | other |
|---|---|---|---|---|---|
| Punt <=4k (19) | **42%** | 37% | 5% | 5% | 11% |
| Mid 4-7k (86) | **30%** | **29%** | 16% | 10% | 14% |
| Stud 7k+ (31) | 16% | 32% | 45% | 6% | 0% |

Findings:
- The injury/vacated-opportunity mechanism is the single largest driver at
  the punt tier (42%) and a co-lead at mid salary (30%) — stronger up the
  salary scale than the 3-week sample suggested.
- The equal co-driver is the **slumping secure starter** (depth 1-2,
  55%+ snaps, depressed trailing points): 29-37% of every tier, and the
  hardest boomers of all (32.2 avg points vs 27.9 for injury plays) —
  the field's recency bias is the other exploitable inefficiency.
- Both mechanisms are already what our construction targets: vacated
  features + p90 punts catch the injury tier; usage-first projections +
  chalk fade catch the under-owned slumping starters.
- Studs in winning lineups are mostly just studs (77% secure roles) —
  leverage lives below $7k.

## Addendum 7 (2026-07-26): 2023-2024 Milly winners — the anatomy is stable

Collected 31 winning rosters from dfsarmy (2023: 16 weeks; 2024: 15 weeks;
missing weeks have no live article) into `reports/milly_rosters_2023_2024.csv`,
and classified the 248 skill spots against `player_week_training`
(223/248 = 90% matched; 2024 articles abbreviate names, matched via
initial+lastname+position).

**Winning lines are consistent across three seasons.**

| season | weeks | mean win | min win |
|--------|-------|----------|---------|
| 2023 | 16 | 238.6 | 215.8 |
| 2024 | 15 | 230.4 | 178.3 |
| 2025 | 17 | 237.0 | 194.0 |

The ~237 average target we replay against is not a 2025 quirk. The min
line varies a lot (178-216) — some weeks are winnable at scores our
best-of-40 already reaches (2025 wk12 hit 197.8).

**The punt boom is a stable signature, not a 2025 artifact.** A sub-$4k
player scored 15+ in 14/16 weeks (2023) and 11/15 (2024) — 80.6% overall
vs 94% in 2025. Punt-slot-required construction is validated across three
seasons.

**DST-as-punt is far more common historically than in 2025**: 14/16
(2023) and 15/15 (2024) winning lineups used a sub-$4k DST, vs 7/17 in
2025. Cheap DST is the default salary-relief valve for winners.

**Mechanism shares (matched spots)**: vacated-opportunity signal
(>10% team vacated target/carry share) on 20% (2023) / 29% (2024) of all
spots and 27% of punt-tier spots; secure starters (depth<=2, snaps>=55%)
fill ~70% of mid/stud spots, echoing 2025's 77%. The "slumping secure
starter" share reads lower here (4-8%) than 2025's 29-37%, but the slump
definition is sensitive to the trailing-window threshold — treat the
2025 figure as the calibrated one, this as directional confirmation that
secure-role players below their season mean recur in winners.

**Ownership**: winners are not chalk stacks — mean ownership ~10% (punt),
13-15% (mid), 11-15% (stud); mean winning-QB ownership 8.2%. Supports our
leverage penalty and low-owned QB stacking.

Net: every construction constant we set from 2025 (punt slot, chalk fade,
~237 tail target) is confirmed by 2023-2024. One candidate tweak: bias
the punt slot toward cheap DST more often (winners do it 29/31 weeks in
2023-24).

## Addendum 8 (2026-07-26): head-to-head (last meeting) features — null result

Question (user): do we consider what happened the last time these two teams
played? We didn't — and a walk-forward ablation confirms we shouldn't.

Two point-in-time features (`faced_opp_prior` within 2 seasons, and the
player's `dk_points_last_vs_opp` from that meeting; 40.4% of panel rows have
a prior meeting), added to the canonical featureset and evaluated with
identical seeds:

| season | MAE base | MAE +h2h | delta | rank_corr base | +h2h | delta |
|--------|----------|----------|-------|----------------|------|-------|
| 2024 | 5.0384 | 5.0264 | -0.012 | 0.5317 | 0.5310 | -0.0007 |
| 2025 | 4.8995 | 4.9002 | +0.001 | 0.5579 | 0.5596 | +0.0017 |

Deltas are noise-sized and sign-flip between seasons. Consistent with the
literature (1-2 game samples, roster/coach turnover) and with our earlier
advanced-metrics ablations: opponent info is already carried by trailing
defense-vs-position form + the Vegas blend. Not adopted.

## Addendum 9 (2026-07-26): consistent cheap overperformers — real trait, already priced

Question (user): are there low-dollar players that consistently overperform?

**Descriptively, yes** (25,701 player-weeks at <=$5k, 2014-2021 + 2025;
boom = 3x+ salary value):
- Split-half boom-rate correlation 0.214; first-half boomers (>=50% rate)
  keep booming at 27.4% vs 20.6% base — a persistent ~+7pt edge.
- Cross-season correlation 0.175 (DK eventually reprices).
- The 2025 archetypes: min-priced starting TEs (Parkinson 62% boom at
  $2.9k avg, Strange, Barner, Tonges) and young QBs priced below role
  (Shough, McCarthy 67%). Sticky bottom-of-scale pricing = the
  "mispriced starter" Milly mechanism seen from the other side.

**As model features, no.** value_l8 (trailing pts/$1k) +
cheap_boom_rate_prior, walk-forward:

| eval season | MAE base | +value | rank_corr base | +value | cheap MAE base | +value |
|-------------|----------|--------|----------------|--------|----------------|--------|
| 2025 | 4.9121 | 4.8990 | 0.5574 | 0.5608 | 4.0333 | 4.0103 |
| 2021 | 5.1704 | 5.1914 | 0.5350 | 0.5330 | 4.2289 | 4.2266 |

2025's apparent gain sign-flips on 2021 — same mirage shape as the h2h
ablation. Salary + dk_points_l4 already encode "cheap player scoring
well"; the explicit framing adds nothing robust. Not adopted. The
construction side already exploits the trait: punt slots are picked by
p90 value, which is exactly where these players surface.

## Addendum 10 (2026-07-26): how many entries to reach a Milly line? Entry count is not the lever

New replay output (`_entries_to_line`): per week, fit the score distribution
of our 40 generated entries, then solve order statistics for the N where
best-of-N clears a line with 50% probability. 2025, correlated sim:

- **Line 194 (min 2025 winning line): median N ~824k.** Reachable within a
  150k-entry field in 8/17 weeks; within DK's 150-entry/user cap in ~2
  weeks (wk12 N=40, wk17 N=104).
- **Line 237 (avg winning line): median N ~10^15.** Effectively
  unreachable at any entry count from the current entry distribution.

The diagnostic is the sd column: weeks with entry-pool sd >=18 (wks 10,
12, 15) need N in the hundreds-to-thousands; weeks with sd ~10-13 need
millions+. Our weekly entry sd is 10-24 while the winning line sits
4-6 sd above our mean. More entries sample the same thin-tailed
distribution; the field's 150k entries win because they span thousands of
*constructions*, i.e. a much wider distribution.

Conclusion: scaling from 40 toward 150 entries buys little on a median
week. The lever is entry-pool variance — deliberately lower-mean,
higher-variance construction (concentrated 4-5-man game stacks, #6) and
selecting entries on P(>= line) against correlated draws (#5). Caveat:
normal fit thins the right tail, so absolute Ns are order-of-magnitude
pessimistic; the variance-vs-N relationship is the robust finding.

## Addendum 11 (2026-07-26): tail-objective selection validated — biggest single gain yet

Full-season 2025 replay with issue #5 live (boom-draw candidates + greedy
sim-coverage selection at line 194), vs the pre-#5 baseline:

| metric | baseline | tail-objective | 
|--------|----------|----------------|
| mean best-of-40 | 160.5 | **177.1** |
| season max | 192.2 | **208.7** |
| weeks >= 194 (min Milly line) | 0/17 | **2/17** (wks 2, 9*) |
| entry-pool sd (range) | 10-24 | **16-32** |
| median N@194 (entries for 50% best-of-N) | ~824,000 | **306** |
| weeks with 194 reachable in a 150k field | 8/17 | **16/17** |
| weeks with 237 reachable in a 150k field | 1/17 | 5/17 |
| median field finish | 11.6% | 14.2% |

(*wk2 best 208.7, wk9 196.1.) The mechanism worked exactly as addendum
10 predicted: variance was the lever. Boom-draw candidates ("what wins
if the slate booms like THIS sim") widened per-week entry sd, and
coverage selection stopped stacking redundant near-identical entries.
Median entries-to-line collapsed from ~824k to ~306 — the 194 line moved
from practically unreachable to within a 150k field's grasp in 16/17
weeks, and week 12/17-type weeks now need only 29/14 entries.

The cost is the expected one: median finish slipped 11.6% -> 14.2%
(entries are individually lower-mean, higher-variance). For a
tournament-only player this is the correct trade — cash-line finishes
don't pay; tails do. Issue #6 (concentrated game buckets) remains open
as a further variance lever.

## Addendum 12 (2026-07-26): construction ladder A/B/C/D — Vegas-first DST is the win

Four full-season 2025 replays, each layering one change (baseline =
addendum 11's tail selection: mean best 177.1, max 208.7, 2/17 >= 194):

| run | change | mean best | >=194 | med finish | med N@194 | 237 in 150k |
|-----|--------|-----------|-------|------------|-----------|-------------|
| A | + concentrated game stacks | 177.5 | 2/17 | 13.5% | 278 | 7/17 |
| B | + DST punt bonus 1.5 | 177.5 | 2/17 | 13.5% | 278 | 7/17 |
| C | + QB-experience DST adj | 177.2 | 2/17 | 13.7% | 228 | 9/17 |
| D | + Vegas-first DST model | **180.1** | **5/17** | **13.2%** | 394 | 7/17 |

Verdicts:
- **Game stacks (A): adopted.** Small clean gain, deep tail 5/17 -> 7/17.
- **DST punt bonus (B): null, stays off.** Byte-identical to A (env var
  verified in-container): the punt slot + salary cap already produce the
  winners' cheap-DST pattern; a +1.5 objective tilt flips no solves.
- **QB-experience adj (C): adopted** (superseded by D, which contains it).
- **Vegas-first DST (D): adopted — biggest realized-tail gain of the day.**
  Five weeks now clear the 194 minimum Milly line (2, 9, 12, 16, 17; best
  202.2/208.7), mean best 180.1, and median finish improved to 13.2% —
  better mean AND better tail. Weeks 16/17 jumped +21/+10 pts vs run C.
- Honest nuance: D's *extrapolated* N@237 (normal-fit) reads worse than
  C's while its realized results are strictly better — the thin-tailed
  normal fit under-credits distributions that concentrate mass in real
  boom scenarios. Realized best-of-40 is the ground truth; the fit is a
  progress proxy.

Week-of-work summary: baseline -> D took the season from 0 weeks over any
winning line to 5/17 over the minimum line, mean best 160.5 -> 180.1.

## Addendum 13 (2026-07-26): diagnostics + min-spend adopted; rankings are cosmetic

- **Min-spend floor $49k adopted** (run I, lever verified active: 0% of
  entries left >$1k vs 7% before): mean best-of-40 180.1 -> **182.3**,
  max/194-count unchanged, median finish 13.2 -> 13.9%. (Run G was void —
  env var landed on an image without the lever.)
- **Neither ranking predicts the weekly best entry.** Best scorer's rank:
  selection order — median 15, top-5 0/17, top-10 6/17; app confidence
  formula — median 17, top-5 2/17, top-10 3/17 (below chance). Guidance:
  spread all 40 entries; rankings are ordering cosmetics.
- **Entry anatomy: the punt decides.** Weekly best vs rest is structurally
  identical (game concentration 4.3, QB stack 2.0, chalk, ~$49.7k spent);
  the separator is punt production: 21.0 pts (best) vs 13.5 (rest).
  Boom-draw generator produced 11-12/17 weekly bests from ~58% pool share.
  Next lever: punt diversity + selection (Vegas DST, p90 punts).
- **Prop lines backfilled**: The Odds API, 2023-2025, kickoff-2h
  snapshots, DK+FanDuel, ~2,500 rows/week -> nfl_raw.prop_lines. Next:
  de-vig -> DK-point medians -> market blend -> validation replay.

## Addendum 14 (2026-07-26): prop-market blend validated — best accuracy and best tail

Run J (2025, blend w=0.45 over 4,104/4,687 rows = 88% line coverage):
- **MAE 4.664** — beats model-only (4.909) and market-only (4.786); the
  blend outperforms both parents, as the architecture predicted.
- **Mean best-of-40 184.3** (run I: 182.3); **6/17 weeks >= 194** (was 5);
  median N@194 208 (was 394), 17/17 weeks reachable in a 150k field.
  Median finish 14.2% (13.9) — the usual small cash-side trade.
- Day ledger, baseline -> J: mean best 160.5 -> **184.3**; weeks over the
  minimum Milly line 0 -> **6 of 17**; projection MAE 4.905 -> **4.664**.
- Adopted for replays. Pre-season TODO: live weekly prop snapshot job
  (the historical importer's endpoints, current-events variant) so
  production Sundays get the same blend; The Odds API $30/mo in-season.

## Addendum 15 (2026-07-28): closing audit — blend weight confirmed, system settled

Blend-weight sweep (run K, 2025 blended rows): optimum w=0.40
(MAE 4.6311) vs current 0.45 (4.6331) — flat basin 0.30-0.50, difference
is noise. Kept at 0.45. Audit verdict: no further pre-season changes
carry positive expected value. Remaining levers correctly wait for
in-season data: real ownership (leverage + field calibration), prop-line
movement signals, and the ownership prediction model. Note: the Tuesday
scheduler chain fired live for the first time this morning.

## Addendum 16 (2026-07-29): punt-market lift and 470-candidate pool — both null

- Punt-boom study stands (market-implied >8 pts -> 24.6% boom vs 5.4%
  base; vacated signal only 6.5%) but the explicit 1.6x punt valuation
  changed nothing in replay (run M: 181.2/5/17 vs 181.6/5/17) — the
  blend already delivers the market signal to punt projections.
  Reverted; the finding's value was already banked in the props blend.
- 470-candidate selection audit (run L, CAND_MULT=8/N_BOOM=150):
  realized tail slightly worse (178.3, 4/17, 15.0% finish) despite a
  much wider fitted tail (N@237 847k vs 5.4M) — selection already
  extracts what generation produces at ~132 candidates. Defaults kept;
  compute better spent elsewhere. Remaining levers are in-season only.

## Addendum 17 (2026-07-29): line movement — closes absorb the news (null)

Tuesday-open backfill complete (54 weeks, DK opens). On 624 player-weeks
with open+close+actuals: close-only R=0.467 vs close+movement R=0.471,
movement beta -0.30 — no signal beyond the closing line, bucket means
flat after conditioning on close. Verdict: the kickoff-2h close already
absorbs the week's news; movement modeling unnecessary. In-season this
validates the design: always blend from the LATEST pre-lock snapshot.
Remaining information plays: showdown modernization (#10) and the
ownership model on live standings (#11).

## Addendum 18 (2026-07-30): capture, anti-correlation, duplication — investigation closed

- **Capture rates (run N)**: our 40 held the slate's single best punt
  14/17 weeks (36.8 distinct punts held/wk) and best QB 9/17 (misses only
  4.3 pts deep). Marginal selection is near-ceiling; the residual gap to
  237 is JOINT capture (right punt + right stack in one roster) — the
  structural 40-vs-150k frontier.
- **Anti-correlation A/B (run O, N_NOSTACK=60)**: stack-free candidates
  took 17% of slots but produced only 2/17 bests; tail slightly worse
  (180.4/4/17 vs 181.5/5/17). Null — stacking stays mandatory.
- **Duplication risk (run O)**: est copies in a 150k field — median
  0.000, max 0.0, 0/680 entries with >=1 expected copy. Our entries are
  effectively unique; no underspend/uniqueness engineering warranted,
  and full-spend adoption carries no dup cost. Recheck with the real
  ownership model in-season.

## Addendum 19 (2026-07-30): mid-tier QB diversity — null; QB weakness is epistemic, not structural

Run Q (N_MIDQB=12, top mid-tier QBs by simulated p90, locked+stacked):
midqb candidates took 10% of slots but produced 0/17 weekly bests; QB
capture unchanged (9/17, distinct QBs 12.3 -> 13.1); tail identical
(181.4/5/17 vs 181.5/5/17). Verdict: the selector's QB concentration is
the correct trade — forcing QB breadth builds weaker rosters that never
win weeks. QB remains the weakest position (rank corr 0.463, 17/41
top-scorer misses) because QB outcomes (rushing TDs, game script) are
irreducibly noisy and the market prices QBs efficiently. Miss-pattern
loop closed; generator stays env-gated off.

## Addendum 20 (2026-07-30): dark-game stacks ADOPTED — the user's hypothesis wins

Study: 29% of matched 2025 Milly winners stacked a game ranked 8th-14th
by Vegas total — a zone our generators never touched. Run R (one 5-man
stack from each game ranked 5-14): mean best 181.5 -> **184.2**, weeks
>=194 5 -> **6/17**, median finish 12.3% (best ever), max 209.4. The
dark generator took 10% of slots and produced **5/17 weekly bests**
(2.9x its share) — strongest per-slot generator measured. Adopted as
default (N_DARKGAME=10). Rookie-ramp draft-prior A/B (run S) queued;
its baseline is now 184.2.

## Addendum 21 (2026-07-30): draft-capital cold-start priors — null; pre-season book closed

Run S (DRAFT_PRIORS=1: R1 RBs x1.3, rookie TEs x0.6, rookie WRs x0.9 on
cold-start opportunity): MAE 4.666 vs 4.664, tail identical to run R
(184.2 / 6/17 / 12.3%). The rookie-ramp patterns are real (study above)
but the props blend already prices rookies — stays env-gated off.

**Final pre-season configuration** (all replay-validated): correlated
sim + props blend (w=0.45) + Vegas-first DST + tail selection over
lev/boom/game/dark generators + min-spend 49k + punt slot + chalk fade.
2025: MAE 4.664, mean best-of-40 184.2, 6/17 weeks over the min Milly
line, median finish 12.3%. In-season queue: issues #10, #11, #12.

## Addendum 22 (2026-07-30): alt-line ceiling bump — null, not adopted

The market-ceiling signal is real predictively (top-quartile ceiling
room booms 21.4% vs 13%, corr 0.259 — study stands) but run T
(ALT_CEIL=0.4 on <=6.5k salaries) was mixed-within-noise: mean best
185.1 (+0.9), weeks >=194 down 6 -> 5, median finish 12.3 -> 14.2%.
The simulated p90 + boom draws already price ceiling room where it
matters. ALT_CEIL stays env-gated off; market_ceilings() remains
available as a feature source (candidate input for the ownership model
and the possession simulator's usage draws). Cloud roadmap worker
(routine trig_01T9os88Tr7iqJvedtLtmh9Y) continues issue #13 via PRs.

## Addendum 23 (2026-07-31): qualifier tail-line targeting — null for construction

Context change: primary 2026 contest is DK Championship qualifiers
(~20k entries), not the 150k Milly the tail_line=194 anchor came from.
Gumbel scaling (line ~ sqrt(ln N), anchored 150k -> 194) estimates a
20k qualifier winning line of ~187.6; the dashboard contest picker now
labels confidence against the chosen field's line (commit fcff4c0).

Run U (Cloud Run): identical construction, selection targeting
P(best >= 187.6), simulated field 20k at sharp=0.25. Result vs the
last persisted comparator (run T, itself within noise of adopted run
R): mean best 183.5 vs 185.1, weeks >= 187.6 **8/17 vs 9/17**, weeks
>= 194 identical 5/17. 398/680 lineups came out identical; 13/17 weeks
the best score didn't move at all. Tag mix shifted mildly toward boom
(53% -> 62% of selected slots) with no payoff. Lowering the target
line does NOT increase how often we cross the lower line — selection
is saturated at this candidate pool, same conclusion as the CAND_MULT
and N_BOOM depth ablations.

**Decision: no qualifier construction mode.** tail_line stays 194 for
replay/selection; the field-size picker remains what it demonstrably
is — an honest confidence-labeling and ordering device, not a lineup
changer. Worth keeping in mind: the sharper simulated field (0.25 vs
0.15 optimizer share) moved median finish 14.2% -> 18.9%, a fair
warning that qualifier fields are harder per entry than the Milly.
Real qualifier standings in-season (queue item 7) replace the 187.6
estimate with the observed seat line and re-test. Rosters:
reports/2025-replay-lineups-qualifier.csv (tags included).

## Addendum 24 (2026-08-01): Milly punt booms vs the next-man-up detector — partial hit, archetype finding

The handoff's open analysis: do the 2025 Milly winners' sub-$4k punt
booms (punt_4k columns, reports/2025-milly-winners.csv) show elevated
team_vacated_*/depth_rank in player_week_training THAT week — i.e.,
would the next-man-up detector have flagged them prospectively?
(Point-in-time is preserved: training windows end at 1 PRECEDING, so
these are exactly the signals available before lock.)

Of 17 winning punts: **7 are DSTs** (41% — outside the detector's
universe entirely), 10 are skill players, 9 matchable to training rows
(Juwan Johnson has no week-1 row — cold-start edge).

- **Detector hits, 3/9:** Xavier Hutchinson (wk 8, 95.9th pctl
  vacated-target — maximally flagged), Michael Wilson (wk 11, 72.7th
  tgt), Kayshon Boutte (wk 6, 78.1st pctl vacated-carry). The
  injury-replacement archetype the detector was built for.
- **Detector misses, 6/9 — but they share an archetype:** Ferguson,
  Hunter Henry, Fannin, Parkinson, Gadsden, (Johnson wk 1) are all
  **starting TEs at min price** — depth_rank 1 (or newly 1: Gadsden was
  rank 2 through wk 6, rank 1 at his wk-7 boom), vacated share ~0.
  Nothing was vacated; DK's TE pricing compression just puts real
  starters at $3.2-3.9k.

Conclusions: (1) the vacated-share detector is real but covers only ~1/3
of player punt booms — keep it, don't over-weight it; (2) the dominant
winning-punt archetypes are *cheap starting TEs* and *DSTs*, which are
availability/pricing phenomena, not injury cascades — punt selection
should ensure the p90-valued punt pool isn't crowding these out in favor
of cascade candidates; (3) a *depth-rank transition* signal (rank 2 -> 1
in recent weeks, Gadsden case) may prospectively catch newly-promoted
min-priced starters the static rank misses — cheap feature, untested.

## Addendum 25 (2026-08-01): possession sim 3-arm A/B — team arm adopted

Engine: drive-state Markov chain, transitions FITTED from pbp 2018-2025
(48,528 drives; game_sim.py docstring has fit semantics + artifacts).
2025 GPP replay, 40 entries, identical settings across arms:

| arm | mean best | >=194 | median finish |
|---|---|---|---|
| lognormal (fresh baseline 2026-07-31) | 188.0 | 6/17 | 14.1% |
| possession, shared factor | 185.6 | 5/17 | 15.1% |
| possession, TEAM factors | **188.4** | **7/17** | 14.4% |

Recorded bar (Addendum 21): 184.2 / 6-17 / 12.3%. The team arm matches
or beats every headline: best mean-best and best tail-week count of any
recorded run. The feared shootout-stack degradation from dropping the
corr=1 shared factor did NOT appear (punt capture 16/17 vs 14/17;
QB-held 11/17 vs 12/17 — a wash), consistent with the fit's measurement
that real cross-team scoring correlation is ~0.016. **Adopted**:
GAME_SIM_MODE=possession set on the project-slate job env (replay jobs
left unset so future A/Bs keep a lognormal control). Queued next arms on
top of possession-team: GAME_SIM_USAGE=dirichlet (correlated usage
draws), GAME_SIM_PACE=vegas (drive counts conditioned on game totals),
and the depth_rank_delta feature build.

## Addendum 26 (2026-08-01): off-season sprint scorecard — five A/Bs resolved

All on 2025 replays against the adopted possession-team base (Addendum
25: 188.4 mean-best / 7-17 >=194 / 14.4%). Run-to-run noise band for
identical configs measured at roughly +/-5 on mean-best (183.5-188.4).

| experiment | result | verdict |
|---|---|---|
| Possession sim, team factors (GAME_SIM_MODE=possession) | 188.4 / 7-17 / 14.4% | **ADOPTED** (Addendum 25; live on project-slate) |
| Showdown sim-mode (SHOWDOWN_SIM / app `sim` flag) | capture 85.0% vs 80.7%, >=90%-capture slates 16/41 vs 8/41 | **ADOPTED** — decisive; live default in /showdown/lineups |
| Vegas-pace drive counts (GAME_SIM_PACE=vegas) | 185.6 / 5-17 / 14.4% | null — gate stays off (mean-preservation leaves pace only heteroskedasticity) |
| Dirichlet usage draws (GAME_SIM_USAGE=dirichlet) | 177.3 / 3-17 / 14.6% | NEGATIVE at K=20 — off; punt pool widened (52 held) but capture fell (13/17); concentration scale is the retune knob |
| depth_rank_delta feature | 183.8 / 6-17 / 16.4% | neutral (within noise) — feature kept in featureset, re-evaluate on 2026 weeks |

Also seeded (not A/B-able until in-season): ownership model
(models/ownership.py, `nfl-dfs train-ownership`), awaiting week-1
standings imports.

## Addendum 27 (2026-08-01): determinism, folklore tests, and the final pre-season state

**The replay pipeline is DETERMINISTIC** (three identical confirmation
runs to the decimal). All comparisons below are exact, not statistical;
earlier "run-to-run noise" was data-vintage drift. Corollary guardrail:
exact measurement makes single-season overfitting EASIER — adopt only
mechanism-backed, decent-sized effects; small exact wins get recorded
and re-tested on 2026 data, not chased.

**Final adopted configuration** (GAME_SIM_MODE=possession + fitted
transitions + team factors + ref_flags_prior + neutral_pass_rate_l6;
depth_rank_delta and team_ol_out excluded):
**mean best-of-40 189.5, 8/17 weeks >= 194, max 228.5, median 15.5%** —
best recorded values on every tail metric (week began at 184.2 / 6-17).

Exact A/B ledger this cycle (comparator 189.5/8-17 unless noted):
| lever | result | verdict |
|---|---|---|
| refs + neutral pass rate | +0.1 mean, median 16.4->13.6 (vs delta base) | adopted |
| depth_rank_delta | -4.6 mean (proven by determinism) | removed |
| team_ol_out | 180.8 / 4-17 (-8.7, -4 weeks) | removed same day |
| DST_CORR_DRAWS (anti-corr DST draws) | 188.5 / 8-17 / 16.1% | null at first calibration; gate kept — refit magnitude from data in-season |
| LEV_POS_WEIGHTS (Levitan tilt) | 182.4 / 5-17 | negative; gate kept |
| generator mix (2 variants) | 186.0-187.3, -1 tail week | closed null — default allocation wins; losing generators contribute coverage diversity |

Folklore measurements (2,195 games 2018-25 unless noted): QB-WR1 .446,
QB-TE1 .311, QB-WR3 .265 (the one under-priced pair), QB-oppQB .199
(the ".58" claim fails), QB-RB1 .082, favRB-oppQB .076, WR1-oppTE1
.067, WR1-oppWR1 .104 (bring-back value is tail-conditional, not
linear — which is why the sim prices worlds, not pairs). Wind: uniform
within-player degradation, NO short-area shift. Dome-to-cold: dome
teams degrade LESS than outdoor teams (claim backwards). Underdog-RB
garbage pairing: corr .04. Milly winners' implied-total tier: 1/17 from
top-3, 10/17 from rank 11+ (median implied 24.5) — the dark-game thesis
confirmed from an independent angle.

Feature-lesson: both single quick-add features (delta, OL) hurt; the
paired environment features helped. New features must each pass their
own exact replay before shipping — the harness makes that a 35-minute
question.

## Addendum 28 (2026-08-01): assumption audit — all four pre-A/B rules validated; candidate features closed

**The pre-A/B assumption audit** (each rule removed for one exact run vs
the 189.5/8-17 shipping config; env levers LEV_PENALTY / PUNT_MIN /
STACK_BRING_BACK / STACK_QB_MIN / FORBID_RB_DST now permanent):

| rule removed | result | cost | verdict |
|---|---|---|---|
| bring-back mandate | 183.9 / 4-17 | -5.6 / -4 weeks | KEEP — most load-bearing rule; note linear WR1-oppWR1 corr is only .10, tail dependence is what pays |
| mandatory sub-$4k punt | 185.1 / 5-17 | -4.4 / -3 | KEEP — now causal, not just "94% of winners" correlation |
| RB-vs-DST ban | 185.3 / 5-17 | -4.2 / -3 | KEEP |
| chalk fade (25.0 -> 0) | 187.5 / 6-17 | -2.0 / -2 | KEEP — smallest edge; the in-season ownership model is the upgrade path |

**Candidate features closed** (EXTRA_FEATURES harness; each one exact run):
pace_env_l6 182.0/5-17, opp_blitz_rate_l6 183.2/7-17 (median 13.5 but
-6.3 mean), team_top2_target_share_l6 183.8/5-17. Combined with
depth_rank_delta (-4.6) and team_ol_out (-8.7), that is FIVE consecutive
single-feature failures with the same signature — better typical-week
calibration paid for out of the tails. Standing law: model features are
guilty until proven innocent by their own replay; construction RULES
(above) are where the edge actually lives.

**DST_CORR_DRAWS closed**: refit to measured moments (corr -0.491,
rel-sd 0.93, from 4,390 team-games 2018-25 — the first attempt was
backwards on both axes) still tests negative: 186.5/5-17. Constant DST
projections in entry selection are not a deficiency. Gate remains in
code as tested-twice-negative.

Also this cycle: deploy/deploy_jobs.sh reconciled with live infra
(every cadence verified); candidate-feature env harness makes any
future feature one rebuild + one 35-min run from an exact verdict.

## Addendum 29 (2026-08-01): the LineStar backfill — multi-season era begins

**Data acquired** (ingest/linestar_backfill.py, LineStar public API):
DK salaries 2022-2024 (45k rows; full 2014-2025 coverage, replayable
seasons 3 -> 6) and — the larger prize — REAL DK contest ownership,
2022-2025: 103,556 rows across 1,258 contests. The in-season ownership
queue's data blocker is gone before the season starts.

**Ownership model** (models/ownership.py): trained on 2022-24, evaluated
on 7,327 held-out 2025 rows: corr 0.727 vs naive value-rank 0.548 — the
pre-registered wire-in criterion met. OWN_MODEL=1 wires it (walk-forward
per replay season) into the chalk fade and the simulated field. First
exact result: construction unchanged (185.2/5-17 = baseline), median
finish 16.8% -> 23.4% — a REALISM upgrade, not a performance knob; the
model field is the truer, harder yardstick for future A/Bs.

**Selection-bias correction**: the salary-enriched training data moved
the 2025 replay from 189.5/8-17 to 185.1/5-17. Read honestly: a week of
exact config selection ON 2025 replays partially overfit 2025; richer
data regressed it. This is the problem the backfill exists to solve —
verdicts from here on aggregate across seasons.

**First 2023 contest replay ever**: 172.4 mean-best / 2-17 >=194 /
median 12.8% (the best median of any season). 194 is a 2025 anchor;
median-finish percentile is the season-portable metric. Backfill
hardening en route fixed four latent bugs: training-table dupes
(mid-week trades), 019's rotoguru_gid grouping, the 'Def'-only DST
loader (actuals now computed from pbp), and a QB-starts merge fan-out.

**Also resolved**: conformal prediction declined (sim p90 coverage
already 0.912 vs 0.90 target; miscalibrated p10 is unconsumed); RL for
construction declined (one-shot combinatorial problem, MILP+greedy is
1-1/e near-optimal; the ownership-aware objective it gestures at is
OWN_MODEL, tested above); Neo4j declined again (NetworkX at this scale).
NGS candidates (qb_cpoe_l6, qb_time_to_throw_l6) are materialized and
one EXTRA_FEATURES command away from their arms — untested, prior
against per the feature law. /market page live: prop-market
disagreement + line movement (odds_movement view).

## Addendum 30 (2026-08-01): the six-season baseline panel

One configuration (the shipping config: possession-team engine, fitted
transitions, refs+neutral-pass features, naive field), every replayable
season, exact numbers. The pre-season reference every future idea must
move — judged on the PANEL, not any single season (Addendum 29's
selection-bias lesson).

| season | mean best | max week | >=194 | >=237 | median finish |
|---|---|---|---|---|---|
| 2019 | 190.8 | 271.1 | 5/16 | 2/16 | 11.6% |
| 2021 | 173.8 | 249.9 | 3/17 | 1/17 | 13.3% |
| 2022 | 171.4 | 196.2 | 2/17 | 0/17 | 14.4% |
| 2023 | 172.4 | 206.7 | 2/17 | 0/17 | 12.8% |
| 2024 | 177.4 | 203.3 | 1/17 | 0/17 | 16.0% |
| 2025 | 185.1 | 233.9 | 5/17 | 0/17 | 16.8% |

Panel aggregates: 18/101 weeks >= 194; mean best-of-40 avg 178.5;
median-finish avg 14.2% (range 11.6-16.8 -- tight across six seasons
spanning wildly different scoring environments, confirming it as the
season-portable metric). Mean-best tracks era scoring (2019's shootout
league: 190.8; the 2022-23 dead-ball era: ~172), so absolute tail lines
must be era-anchored -- 194 is a 2025 number. 2022 and 2024 are the
first-ever replays of those seasons (LineStar salary backfill).

## Addendum 31 (2026-08-01): salary-feature ablation — hypothesis falsified, features validated

First experiment under the multi-season protocol. Hypothesis (from the
enrichment regression + the feature law): salary/salary_delta_wow are
consensus features that eat tails; removing them might help. DROP_FEATURES
ablation across all six seasons: tail weeks 18 -> 11 (panel), mean-best
avg 178.5 -> 175.2, vs a modest median improvement. VERDICT: salary
features decisively earn their slots -- they are value-detection FUELING
tails, not consensus dampening them. The 2025-only enrichment regression
was era/data-shift noise, not a salary indictment. Methodological
exhibit: per-season deltas ranged +1.4 to -11.5 -- any single season
could have "proven" either conclusion. Panels or nothing.

Post-script to Addendum 31 — the training-adjustments question, closed:
(1) salary features: panel-validated above. (2) Recency weighting:
already implemented (models/weights.py, 3-season half-life exponential
decay, season-level only); tuning the half-life is a refused
hyperparameter sweep. (3) In-season weekly retraining (current-season
weeks entering the training set): queued, requires per-week retrain
replays (~17x cost) to validate. (4) Hyperparameters, p10 floor
calibration, further features: refused with reasons on record. The
fitting layer is sound as configured.

## Addendum 32 (2026-08-01): qb_cpoe_l6 — the first feature to pass, adopted

Six-season panel, EXTRA_FEATURES=qb_cpoe_l6 vs the Addendum-30 baseline:
tail weeks 18 -> 23 of 101 (+28% on the paying metric; up in 4 seasons,
down only in 2023), mean-best avg flat (178.5 -> 178.3), median avg flat.
First survivor of the feature law after five failures -- and it came from
the audit's one unused raw table (ngs_passing). ADOPTED into
NUMERIC_FEATURES; by determinism the CPOE panel IS the new baseline
panel (2019: 186.9/6-16/10.8 · 2021: 177.1/5/12.5 · 2022: 174.3/3/15.8 ·
2023: 167.8/1/15.9 · 2024: 175.5/1/16.3 · 2025: 188.1/7/15.1).
qb_time_to_throw_l6 panel launched next on this new baseline.

## Addendum 33 (2026-08-01): qb_time_to_throw_l6 — declined; the ledger closes

Six-season panel vs the CPOE baseline: tail weeks 23 -> 17 (-6; down in
three seasons, up in one), mean flat. NOT adopted; remains a registered
candidate. Final feature score: 7 tested under exact discipline, 1
adopted (qb_cpoe_l6). Every queued experiment in the project's history
now has a recorded verdict. The shipping baseline is the Addendum-32
CPOE panel: 23/101 weeks >= 194, median-finish avg 14.3%, live on
project-slate/train-weekly/app.

## Addendum 34 (2026-08-01): column-order sensitivity discovered; dollars selection declined; canonical ordering adopted

The night's three verdicts:
1. **Column-order sensitivity.** A "determinism anomaly" (2019 baseline
   shifting 186.9 -> 181.8 across images with identical feature sets)
   was isolated by control run: LightGBM split tie-breaking depends on
   feature COLUMN ORDER. EXTRA_FEATURES arms append candidates last;
   adoption inserts them mid-list -- same features, different order,
   different (equally valid) model, ~+/-5 mean-best of order luck.
   Consequence: single-run A/Bs were exact only up to ordering; the
   panel discipline absorbs this, single-season adoptions don't. FIX:
   build_X now sorts active features alphabetically -- candidate arms
   and post-adoption baselines train byte-identical models forever.
   The sort is itself one final re-ordering, so the six-season harvest
   (next) defines the definitive shipping baseline.
2. **SELECT_OBJ=dollars declined.** Expected-dollars selection lost on
   every metric INCLUDING ROI (tails 9 vs 21 across the panel). Root
   cause recorded: a 1,000-lineup field resolves ranks to 1e-3 of
   field, but the GPP curve concentrates payouts at 1e-5 -- the
   estimator cannot see first place. Fix path: tail-resolved field
   estimation (importance-sample the top of the field). Code + gate
   remain.
3. **OWN_MODEL yardstick: available, deferred.** Fallback verified
   clean (walk-forward: 2019-22 have no prior ownership data and
   reproduce the naive field exactly). Standard yardstick stays naive
   for ledger continuity; the model field becomes natural in-season
   when weekly refits give it fresh data.

## Addendum 35 (2026-08-01): the selection-objective panel — dollars fix validated, tail-coverage retained; OWN_MODEL rejected

The user stopped the final harvest so the Addendum 34 fix path could be
tested BEFORE the definitive run — the right call. Commit 27ddf23
implemented tail-resolved rank estimation in select_dollar_entries:
empirical rank when >=10 sampled field lineups score above a candidate,
else a parametric normal tail capped at (count+1)/n. A regression test
pins the failure (two candidates both beating the whole sampled field
must rank by depth into the true tail).

Three arms, six seasons, one canonical-ordering image (all include
GAME_SIM_MODE=possession), plus a deconfounding re-run:

1. **OWN_MODEL=1 rejected as a replay field.** 2019-22 reproduce the
   naive field exactly (walk-forward, no prior data). In 2023-25 where
   it binds: tails equal, median finish roughly DOUBLES (13.6->25.8,
   16.3->25.3, 14.6->20.7%), ROI collapses (+44,792 -> +3,118%). The
   pre-canonical "Wave A tails 21" was order luck. The naive yardstick
   stays; the ownership model remains valuable where validated —
   leverage/chalk analysis and live-season use after weekly refits.
2. **The dollars fix is real.** First run was contaminated by
   OWN_MODEL; re-run clean on 2023-25, the fix's effect stands alone:
   2023 median 26.4->16.0%, ROI +3,113 -> +44,794%. The estimator can
   now see the top of the field (Addendum 34's exact defect).
3. **Tail-coverage retained as shipping default.** Clean six-season
   comparison: tails 15 vs 15; >=237 weeks 2 vs 1 — tail-coverage
   caught 2021's 238.9 slate-breaker, dollars topped out at 206.4 that
   season; median 14.6 vs 15.1%; ROI +219,749 vs +257,008% for
   dollars. The dollars objective buys mid-distribution ROI (+17%) at
   the cost of extreme-tail depth — exactly the trade a 35-40 entry
   Milly strategy must refuse. **SELECT_OBJ=dollars is now a validated
   lever for the ~20k qualifier contest mix**, where advancement/ROI
   dominates and the 237 anchor is irrelevant.

Note the baseline ledger shift: on the canonical-ordering image the
six-season panel reads 15/101 tail weeks (was 23/101 pre-canonical,
Addendum 32) — order luck cut both ways and the honest number is the
reproducible one. The sequential harvest running now (baseline config)
defines the shipping baseline and produces the per-year lineup book.

## Addendum 36 (2026-08-01): harvest attribution — the assembly gap; concentration levers tested, declined for GPP

Full attribution sweep over the harvest lineup book (four analyses, all
deterministic against the 49f8dac baseline):

1. **The ceiling always exists.** Perfect-hindsight optimal (MILP over
   actuals, 8 skill slots + our DST) scored >=194 in 101/101 weeks and
   >=237 in 99/101 (avg ~283). Our capture: 63.5% of optimal; a 237
   Milly winner runs ~84%. Misses are never "the slate had no ceiling."
2. **Identification is fine; assembly is the gap.** 71% of each week's
   top-3 actual scorers per position appear somewhere in our 40; the
   slate's #1 QB is rostered 71% of weeks; entry diversity healthy (14%
   pairwise overlap, ~120 unique players/week). But the 40 spread over
   ~16 distinct QBs (~2.5 tickets/stack), and the best single-lineup
   overlap with the weekly optimal-8 is TWO players in the median week
   (2.8 in boom weeks). Right stacks, wrong pieces.
3. **Punt anatomy validated, punt quality poor.** Optimal lineups carry
   ~1.0 sub-$4k skill player (the mandatory-punt rule matches winning
   anatomy). Our punts: mean 7.3 pts, 45% under 5. A perfect
   same-position punt swap crosses 194 in 16 of 28 near-miss weeks
   (oracle bound). Punt-boom prediction (Addendum 24 next-man-up
   detector) is now the highest-value untested lever.
4. **The near-miss band is dense**: 28 weeks at 180-194.

Levers built and tested (eb69be0, env-gated, off by default):
MAX_QBS (distinct-QB cap in tail selection, cap-aware greedy) and
N_QB_VARIANTS (per-top-QB catcher-combination candidates). Six-season
panel vs the 49f8dac baseline (tails / >=237 / median / ROI):
baseline 15 / 2 / 14.6% / +220k; cap8+var4 14 / 1 / 14.2% / +248k;
cap12+var4 15 / 1 / 13.7% / +244k; cap8-only 13 / 1 / +249k.

Verdict: **declined for the GPP default.** Every arm loses 2021 week
5's 238.9 (one of only two >=237 weeks in six seasons — the 4-Raven
Lamar build survives only under uncapped coverage), and none adds tail
weeks. Concentration buys mid-distribution consistency (median and ROI
up in every arm) at the extreme tail's expense — the same trade
direction as dollars selection, and the same reason to refuse it for
the Milly. cap12+var4 joins SELECT_OBJ=dollars as a validated
qualifier-mix candidate (equal 194-tails, better median, +11% ROI).

The assembly gap is real but is evidently not closed by concentration
alone: with the cap on, selection holds more combos of the stacks the
MODEL likes, which converts only when the projections rank the right
stacks. The binding constraint under the cap becomes projection quality
on stack ordering, not coverage breadth. Remaining levers from this
sweep, in value order: (a) punt-boom scoring in the punt slot
(next-man-up + depth-rank transition, Addendum 24), (b) stack-ordering
quality (QB p90 calibration), (c) nothing else visible in the book.

## Addendum 37 (2026-08-02): PUNT_BOOM adopted at +2 — the first strict improvement of the program

The Addendum 36 fix path, built and validated in one cycle. The lever
(f9b2886): punt-priced skill players matching a winning-punt archetype
get +PUNT_BOOM points on OUR objective only (field untouched, same
asymmetry as the chalk fade). Archetypes from the Addendum 24 study of
actual Milly-winning punts, all point-in-time from player_week_training:
cheap starting TEs (depth_rank 1), newly-promoted rank-1s (prev rank
>= 2), top-decile within-week vacated share (>0).

Six-season dose-response panel vs the 49f8dac baseline
(tails / >=237 / median / ROI / mean-best):

- baseline:      15 / 2 / 14.6% / +220k / 178.4
- PUNT_BOOM=2:   **16 / 2 / 14.4% / +256k / 179.7**  <- adopted
- PUNT_BOOM=4:   15 / 1 / 14.7% / +241k / 178.8
- PUNT_BOOM=8:   14 / 0 / 14.8% / +223k / 178.4

+2 is the only configuration in the entire off-season program to beat
the baseline on EVERY headline metric simultaneously — one more tail
week (2022), both >=237 slate-breakers kept, median, ROI, and mean-best
all better. The dose-response is textbook: at +4/+8 the boost overrides
the p90 punt valuation and forces archetype punts into lineups that
didn't want them, killing 2019's 271.1 and 2021's 238.9. The signal
helps as a tiebreak among near-equal punts and hurts as a mandate.

Adoption: default PUNT_BOOM=2 in code on BOTH paths — replay
(build_slates) and the live app pool (_player_pool via
punt_boom_flags_live, which unions training history with the upcoming
week's player_week_inference rows so a fresh promotion is visible in
its first week). Env still overrides; 0 disables. The shipping baseline
of record is now the PB2 row; the six-season lineup book is being
regenerated to match.

## Addendum 38 (2026-08-02): real Milly winners 2019/2023/2024 — the honest bar, and where the 55 points live

The user supplied player-level Milly-winning rosters for 2019, 2023 and
2024 (reports/milly-winners-2019-2023-2024.csv; 2024 wk9 is a duplicate
of wk7 in the source and is excluded). Combined with the 2025 file this
gives 68 real per-week winning lines — now wired into replay reporting
(backtest/real_lines.py, "vs REAL winning lines" output row).

**Ground truth vs our book: beat the actual same-week winner 1/64
weeks** (2024 wk10, a 178.3 line). Mean gap 51-68 pts by season. Real
lines: median ~237 (2023-25) but 252 in 2019; season minima 178-222.
The long-standing "194 min line" was a season minimum, not a typical
bar — and 2025's softest line (193.9) was WEEK 1, the week replays
never covered until today's cold-start fix. The market is most beatable
exactly where our validation was blind.

**Winner anatomy (50 lineups):** ~120% summed ownership (~13%/player),
~2 sub-5% players, ~1.9 chalk (>=20%) pieces, punt in 73%, salary to
the cap. QB: 60% under $6.5k, mean 8.3% owned. Boom density: 3.4
players >=30 pts and ~1.0 >=40 per winner (ours: 1.8 and 0.6).

**Slot decomposition of the gap** (winners vs our weekly-best):
WR 29.9 vs 19.9 (x3 slots = ~30 pts — THE deficit), TE 21.5 vs 15.4,
DST 16.7 vs 12.7, RB 26.8 vs 22.0, QB 32.6 vs 28.3. Winning WRs are
mid-priced eruptions (Fuller 56.7 @ $4.5k, Jennings 49.5 @ $4.1k).
67% of winning players were already somewhere in our 40 that week —
identification holds, assembly + WR-ceiling capture fail.

Prescriptions queued (both already-coded env levers, panel next):
N_MIDQB (winner QBs are exactly mid-priced low-owned) and
LEV_POS_WEIGHTS (Levitan: crowd accurate on RB chalk, weak on WR/TE/DST
— fade where the crowd is wrong). Strategy implication unchanged but
sharpened: 4 Milly entries are lottery tickets against a 237 median;
the ~187 qualifier line (cleared 7/17 weeks in 2025) is where the
edge actually cashes.

## Addendum 39 (2026-08-03): the rebuild-nondeterminism incident — and the corrected 9-arm verdicts

A 9-arm panel (rest-week training exclusion, draw widening x2, FTN
features x2, WR levers x2, ownership-shape constraint, DST bonus) came
back with a shared fingerprint: unrelated selection-only arms all showed
2021 at ~170 mean-best vs the prior control's 178.8 — byte-identical
ROIs across arms that shouldn't share anything. A clean CONTROL arm on
the same image reproduced the shifted numbers exactly, proving the
cause: **feature-table REBUILDS are not deterministic** (BigQuery
tie-breaking; the FTN-column rebuild between panels silently moved the
shared baseline). Replays are exact within a table build; a rebuild is
a new world.

**New law: after any build-features run, every panel co-runs its own
CONTROL arm on the same table build.** (CLAUDE.md, validation laws.)

Corrected verdicts vs the same-build control (16/107 tails):
TRAIN_MAX_WEEK=16 **+5** (21; retrain reshuffle inflates it — see
Addendum 40's combo), SIM_WIDEN_DRAWS=fitted **+4** (20, +1 >=237),
EXTRA=pa_rate_l6 +3 (19), widen-WR-bump +1, FTN pressure / WR-punt
archetype / MIN_LOWOWN=2 / DST_PUNT_BONUS all 0, WR_BOOM=2 **-3**
(declined). SIMS30K (32Gi retry after 12Gi OOM): +2 tails with the
program's best ROI and medians — not worth 3x compute as the panel
default; recorded as a live-Sunday candidate (one slate, pennies).

## Addendum 40 (2026-08-03): EW adopted — the largest gain of the program; live sim-mode closes the fidelity gap

**Final single-lever panel** (same-build control 16/107): BIGPLAY=1
(deep-threat house-call mixture) 16 tails but +1 >=237 (2019 244.2),
best-of-night ROI and 4/6 better medians — flavor, not tails.
EMP_MARGINALS=1 (empirical per-position/tier families from the
NFL-DFS-Tools fit, rank-reordered onto our copula, moments preserved)
**+5 CLEAN** (21; models byte-identical to control — no reshuffle
excuse). LEV_SHAPE=sqrt 16 tails but the night's best median (13.1%) —
qualifier pile.

**Combo panel:** EMPMARG x WIDENFIT ("EW") **24/107 tails, 2 >=237
weeks — the strongest configuration in program history** (2019: mean
best 195.2, 8/17 tail weeks). EMPMARG x TRAINW16 23. All three stacked
20 (2024 collapsed to 0 — triple-stack overshoots; rest-week exclusion
stays a recorded lever, its solo +5 mostly retrain shuffle).

**ADOPTED: SIM_WIDEN_DRAWS=fitted + EMP_MARGINALS=1 as code defaults**
(backtest.replay.apply_draw_shape). Mechanism, in one line: the fitted
widening supplies the width the calibration always measured as missing,
and the empirical families shape that width into realistic right-skew —
composed, mean-preserving, correlation structure untouched.

**Live fidelity fix (the biggest architectural find of the audit):**
the live CLASSIC path had never consumed draws — plain MILP + a
normal-approximation ranking — so every draws-side gain existed only in
replays. inference/live_lineups.py now runs the validated pipeline on
the live slate (features -> cold-start -> components -> usage notes ->
correlated sims -> EW shaping -> market blend as an additive mean shift
-> replay-identical tournament tilts -> boom-draw candidates ->
tail-coverage selection), POST /lineups sim=true by default with a
fail-safe MILP fallback (locks/bans/slate-restricted requests use the
MILP path). What was validated is now what fires on Sundays.

Also this cycle: repo-mining rounds 2-3 (RTS field-model blueprint with
measured 0.43->0.72 dupe-correlation value; Picking Winners overlap
datapoint; DK standings purge ~4 days -> Mon/Tue download law),
vendor-methodology audit (Lev% shipped on lineup cards; salary-residual
et al. recorded), and the pre-built September machinery: lossless
contest-entry import, field-calibration harness, accuracy grading,
proj_tail ceiling lever, external-projection consensus diff. The EW
harvest (sequential, weeks 1-18, book export) is the shipping baseline
of record; its numbers land in six-season-harvest-summary.md.

## Addendum 41 (2026-08-03): EW-book attribution + the closing proposal panel — the program ends at a measured local optimum

**EW harvest of record: 23/107 tails, 2 >=237, mean best 180.6, first
WEEK-1 replays (2019 wk1 = 199.3, a tail week), and the program's first
real head-to-head win vs an actual same-week Milly winner (2024 wk10).**
Book: six-season-harvest-summary.md + six-season-replay-lineups.csv
(4,280 lineups).

Attribution sweep on the new book: vs the PB2 book EW converted 15
weeks and regressed 9 (net +6 on common weeks) — it reshapes selection,
not uniformly lifts. QB slot nearly closed (30.3 vs winners' 32.6),
boom density 2.01/lineup (from 1.8; winners 3.4), punt oracle partially
harvested (10/24 near-misses from 16/28). Remaining gaps: WR slot 20.9
vs 29.9, TE slot regressed to 13.1 under the empirical TE family.

Closing proposal panel (co-run CONTROL reproduced the harvest exactly —
the new law works): SHAPE_MIX=0.5 (hedge shaped/raw worlds) 20 tails —
mixing DILUTES the shaped edge, declined; BIGPLAY on EW 22 (2022 max
240.3) — declined; EMP_POS without TE 23 — equal, declined (churn
without gain). With EWT (20) and SIMS30K (+2 at 3x cost) earlier, five
attack angles have failed to beat EW. The pre-season program closes at
a measured local optimum; remaining upside is in-season data (field
calibration, qualifier curves, ownership refits) rather than more
pre-season search. Levers all remain env-gated for future panels.

## Addendum 42 (2026-08-03): the FINAL EXAM — every survivor and graveyard retry, one panel, one control

Ten arms, six seasons each (2019, 2021–2025), all on the same table build
and image; CONTROL reproduces the EW baseline exactly (23/107 ≥194 tail
weeks; the 2019 execution's metrics were recovered from Cloud Logging
after a truncated log fetch — job succeeded, fetch didn't).

| Arm | Levers | Tails ≥194 | Δ | Mean best | Median fin % |
|---|---|---|---|---|---|
| CONTROL | (EW baseline) | 23 | — | 178.7 | 15.1 |
| **QBVAR4** | N_QB_VARIANTS=4 | **25** | **+2** | 178.8 | 15.0 |
| OWNFADE | OWN_MODEL=fade | 24 | +1 | 178.9 | 14.7 |
| COMBO2 | PUNT_MAX=3500 + no game-stack batches | 24 | +1 | 178.6 | 15.6 |
| PMAX3500 | PUNT_MAX=3500 | 23 | 0 | 178.7 | 15.0 |
| NOGSTACK | N_GAMESTACK=0, N_DARKGAME=0 | 23 | 0 | 178.6 | 15.3 |
| RATEDW | RATE_DENOM_WEIGHTS=1 | 23 | 0 | 179.3 | **14.6** |
| VALUE2 | VALUE2_MIN=2 | 22 | −1 | 178.6 | 15.2 |
| WRBOOM1 | WR_BOOM=1 | 22 | −1 | 178.7 | 15.1 |
| TMW17 | TRAIN_MAX_WEEK=17 | 21 | −2 | 177.6 | 14.9 |

Verdicts: QBVAR4 is the lone clear positive and the adoption leader —
consistent with Addendum 36's qualifier finding (best median) now
carrying the Milly tail too. OWNFADE's +1 with the best-median tie
(14.7) makes it the second candidate. COMBO2 (+1) beats its own parts
(both 0), a real interaction. VALUE2/WRBOOM1/TMW17 are rejected and
return to the graveyard with proper burials (correctly tested this
time). Because +1/+2 on 107 weeks is within tie-breaking distance, the
QF (QBVAR4+OWNFADE) and QFC (QF + COMBO2's pair) combination arms are
running before anything is adopted — combos have failed to add before
(Addendum 33).

Also in this pass, all committed pre-panel: thesis constraints
(per-combo portfolio floors through the sim path and POST /lineups),
the showdown captain board (salary-free p_top/p_top6 from the build's
draws + salary-aware CPT/FLEX-optimal rates counted over every per-draw
MILP solve, rendered under the showdown lineups), and the XFP +
schedule-context candidate features (017j: opportunity-valued FP from
2014–18 bucket rates; net_rest_diff; body_clock_hour) — table rebuild
deliberately held until the running panel queue drains. Node-checking
every served page's inline JS surfaced two pre-existing page-breaking
newline-escape bugs in the late-swap prompts, now fixed.

**Showdown bring-back A/B (2025, 43 slates, 40 entries):** CONTROL 82.3%
mean capture, 10/43 slates ≥90%; SHOWDOWN_BRING_BACK=1 82.4%, 10/43. A
wash — the pass-position captain almost always carries an opposing
bring-back organically in the correlated draws, so the hard constraint
binds too rarely to move capture. Stays OFF by default; it remains a
free judgment lever for slates where the field will captain a one-sided
blowout script.

**Punt-shape / graveyard-retry panel (same image and tables, exam CONTROL
= control):** PSLOPE (PUNT_SLOPE=1) 23 tails, PSTRICT (punt_elig
eligibility) 23, LOWSAL (10-lineup min-salary-47k batch) 23 — all exact
nulls; the salary-related graveyard verdicts are confirmed under their
"different approach" retries and stay buried. DIRK8
(GAME_SIM_USAGE=dirichlet, K=8) 11 tails / mean 175.0 — a severe
regression: sharpening usage concentration collapses tail weeks, so the
K=20-null verdict was about the MODE being neutral, not about K being
mis-tuned. Default usage mode retained.

## Addendum 43 (2026-08-03): research rounds 7-8 — three offline verdicts (TabPFN, conformal, persona field)

Scripts preserved in `scripts/`; all on the real panel, walk-forward
2019-24 train -> 2025 test (the validation law, one split).

**TabPFN-v2 beats our LightGBM shape zero-shot.** 8k-row context, no
training, CPU: RMSE 6.539 vs 6.580, pinball90 1.347 vs 1.388 (better at
ALL four positions), q90 coverage 0.908 vs LGB's 0.870 under-coverage —
the first model to arrive properly calibrated out of the box. Caveats:
reference was the quick-LGB stand-in (not the component system); v2.5+
weights are license-gated (priorlabs.ai, TABPFN_TOKEN); CPU inference
(~9 min per 5k predictions at 8k context) is too slow for replay panels
— adoption path is the licensed API or a GPU job, queued as the first
post-season-start model experiment. Full-context (29k) confirmation run
in flight.

**Conformal calibration: real, small, direction-confirming.** Raw LGB
q90 under-covers (0.870, QB worst at 0.839); a single CQR shift (+1.31
pts, calibrated on 2024) restores 0.899 AND improves pinball (1.378 vs
1.399). Gaussian mean+1.28sd covers only 0.836 — independent
confirmation of the EW/empirical-marginals adoption. Candidate use: a
per-season conformal shift on the projection layer; low priority while
EMP_MARGINALS carries the same correction inside the sim.

**LLM persona field passes the offline screen — decisively, with a
contamination asterisk.** Four personas (casual 55 / value 25 / sharp 15
/ homer 5), public info only (salary, l4 form, Vegas totals), aggregate
exposure vs REAL pct_drafted from imported contests (raw.contest_ownership,
72 weeks of 2022-25 — the data was already in house): Spearman 0.554 vs
naive_ownership 0.393, MAE 0.851 vs 1.156 share-points, persona better
on all three test weeks (w5/w10/w15 2025), gap widest late season (.502
vs .233). ASTERISK: the LLM's training window includes the 2025 season,
so memorized hindsight may inflate this; the clean test is live 2026
weeks. Verdict: mechanism validated, cost trivial (~4 calls/slate);
promote to a September live shadow scored by the field-calibration
harness against real standings before any adoption into the field sim.

## Addendum 44 (2026-08-03): causal vacated-opportunity study — who actually captures absent teammates' usage

Research round 9's causal-ML item, run as an event study on 2019-2025
(scripts/causal_vacated_study.py): treatment = team-weeks where a
target hog (trailing share >=18%, 553 events) or carry hog (>=35%, 369
events) is absent; outcome = each teammate's ACTUAL share minus his own
trailing expectation; uplift vs no-absence control weeks, by (position x
depth) cell.

Findings, both t>2.8 in the load-bearing cells:
- **Vacated targets flow LATERALLY, not down:** WR2 +2.61 share pts,
  WR1 +2.51, WR3 +1.86, TE1/TE2 +1.2-1.4 — and RBs capture ~nothing
  (RB1 +0.71 at t=1.9, RB3 +0.23). The "check-down bump" folklore fails.
- **Vacated carries CONCENTRATE:** RB2 +15.8 share pts (t=10.8), RB1
  +9.5, RB3 +7.5; receivers/TEs gain ~nothing from a lost carry hog.
- Accounting honesty: teammates in the panel capture only ~10 of the
  mean 25.5 vacated share pts — the remainder goes to call-ups outside
  the panel — so the CELL STRUCTURE is the finding, not the absolutes.

Shipped as EXTRA_FEATURES candidates `vacated_capture_tgt`/`_car`
(021/023: team vacated sum x empirical cell capture rate — the
interaction the team-level-sum feature left for the GBM to discover).
Final-panel arm VACC judges them; the raw team-level features stay.
