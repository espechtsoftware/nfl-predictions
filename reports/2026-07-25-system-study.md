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
